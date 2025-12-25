from fastapi import APIRouter, HTTPException, Response, Request, Cookie
from fastapi.responses import JSONResponse, RedirectResponse
from pydantic import BaseModel, EmailStr
from supabase import create_client
from loguru import logger
import os

router = APIRouter(tags=["auth"])


class AuthRequest(BaseModel):
    email: EmailStr
    password: str


class EmailRequest(BaseModel):
    email: EmailStr


class VerifyOtpRequest(BaseModel):
    email: EmailStr
    code: str
    password: str  # 必填密码字段，用于注册时设置密码


class ResetPasswordRequest(BaseModel):
    email: EmailStr
    code: str
    new_password: str


async def _verify_turnstile(request: Request) -> tuple[bool, str | None]:
    vt = getattr(request.app.state, "verify_turnstile", None)
    if callable(vt):
        return await vt(request)  # type: ignore[misc]
    # 若未配置校验器，则默认放行（本地开发容错）
    return True, None


def _require_supabase(request: Request):
    supabase = getattr(request.app.state, "supabase", None)
    if not supabase:
        raise HTTPException(500, detail="Supabase 未初始化")
    return supabase


def _get_helpers(request: Request):
    return (
        getattr(request.app.state, "set_auth_cookies", None),
        getattr(request.app.state, "clear_auth_cookies", None),
        getattr(request.app.state, "refresh_session_and_set_cookies", None),
        getattr(request.app.state, "FRONTEND_URL", os.getenv("FRONTEND_URL", "http://localhost:3000")),
        getattr(request.app.state, "SUPABASE_URL", os.getenv("SUPABASE_URL", "")),
    )


def _is_localhost(request: Request) -> bool:
    """Check if request is from localhost"""
    client_host = request.client.host if request.client else None
    allowed_hosts = ['localhost', '127.0.0.1', '::1']
    return client_host in allowed_hosts


@router.post("/signup")
async def signup(req: AuthRequest, request: Request):
    supabase = _require_supabase(request)
    try:
        res = supabase.auth.sign_up({"email": req.email, "password": req.password})
        user = getattr(res, "user", None)
        return {"msg": "注册成功", "user": user.dict() if user else None}
    except Exception as e:
        return JSONResponse(status_code=400, content={"error": "注册失败", "detail": str(e)})


@router.post("/recall")
async def recall(req: EmailRequest, request: Request):
    supabase = _require_supabase(request)
    ok, reason = await _verify_turnstile(request)
    if not ok:
        return JSONResponse(status_code=400, content={"error": "人机验证失败", "detail": reason})
    try:
        _, _, _, FRONTEND_URL, _ = _get_helpers(request)
        supabase.auth.sign_in_with_otp({
            "email": req.email,
            "should_create_user": False,
            "options": {"email_redirect_to": f"{FRONTEND_URL}/recall"},
        })
        logger.info(f"密码重置邮件已发送到: {req.email}")
        return {"msg": "密码重置邮件已发送，请检查您的邮箱", "email": req.email}
    except Exception as e:
        logger.error(f"发送密码重置邮件失败: {str(e)}")
        return {"msg": "如果该邮箱已注册，密码重置邮件将发送到您的邮箱"}


@router.post("/recall/reset")
async def recall_reset(req: ResetPasswordRequest, request: Request):
    supabase = _require_supabase(request)
    ok, reason = await _verify_turnstile(request)
    if not ok:
        return JSONResponse(status_code=400, content={"error": "人机验证失败", "detail": reason})
    try:
        logger.debug(f"recall_reset: 验证邮箱={req.email} 的 OTP")
        verify_res = supabase.auth.verify_otp({
            "email": req.email,
            "token": req.code,
            "type": "email",
        })
        if getattr(verify_res, "user", None) is None:
            return JSONResponse(status_code=400, content={"error": "验证码错误或已过期"})

        # 优先使用当前会话更新密码
        try:
            upd = supabase.auth.update_user({"password": req.new_password})
            if getattr(upd, "user", None):
                logger.info(f"用户 {req.email} 使用会话更新密码成功")
                return {"msg": "密码重置成功，请使用新密码登录"}
        except Exception as session_update_err:
            logger.warning(f"使用会话更新密码失败，将回退到管理员API: {session_update_err}")

        service_role_key = os.getenv("SERVICE_ROLE_KEY")
        if not service_role_key:
            logger.warning("未配置 SERVICE_ROLE_KEY，无法使用管理员API重置密码")
            return JSONResponse(status_code=400, content={
                "error": "验证码验证成功，但服务端未配置管理员密钥，无法自动重置",
                "verified": True,
                "email": req.email,
                "note": "请联系管理员或稍后重试",
            })

        # 管理员重置
        try:
            _, _, _, _, SUPABASE_URL = _get_helpers(request)
            admin_supabase = create_client(SUPABASE_URL, service_role_key)
            update_res = admin_supabase.auth.admin.update_user_by_id(
                verify_res.user.id,  # type: ignore[attr-defined]
                {"password": req.new_password},
            )
            if getattr(update_res, "user", None):
                logger.info(f"用户 {req.email} 通过管理员API重置密码成功")
                return {"msg": "密码重置成功，请使用新密码登录"}
            logger.error("管理员API返回无用户对象，重置失败")
            return JSONResponse(status_code=500, content={"error": "密码重置失败"})
        except Exception as admin_error:
            masked_key = (
                service_role_key[:6] + "..." + service_role_key[-6:]
                if len(service_role_key) > 12 else "(长度过短)"
            )
            logger.error(
                "管理员API调用失败: %s | 请检查 SERVICE_ROLE_KEY 是否来自同一 Supabase 实例，且与后端 JWT_SECRET 一致",
                str(admin_error),
            )
            return JSONResponse(status_code=400, content={
                "error": "管理员密钥无效或与后端不匹配，无法重置密码",
                "detail": "invalid_service_role_key",
            })
    except Exception as e:
        logger.error(f"密码重置失败: {str(e)}")
        if "expired" in str(e).lower() or "invalid" in str(e).lower():
            return JSONResponse(status_code=400, content={"error": "验证码已过期，请重新发送"})
        return JSONResponse(status_code=400, content={"error": "密码重置失败", "detail": str(e)})


@router.post("/login")
async def login(req: AuthRequest, response: Response, request: Request):
    supabase = _require_supabase(request)
    set_auth_cookies, _, _, _, _ = _get_helpers(request)

    # Skip Turnstile verification for localhost (CLI access)
    if not _is_localhost(request):
        ok, reason = await _verify_turnstile(request)
        if not ok:
            logger.debug("人机验证失败")
            return JSONResponse(status_code=400, content={"error": "人机验证失败", "detail": reason})
    else:
        logger.debug("Localhost login - skipping Turnstile verification")

    try:
        res = supabase.auth.sign_in_with_password({"email": req.email, "password": req.password})
    except Exception:
        logger.info(f"{req.email}用户登录失败")
        return JSONResponse(status_code=400, content={"error": "登录失败,输入密码或账号有误"})

    session = getattr(res, "session", None)
    if not session or not getattr(session, "access_token", None):
        logger.debug("access_token未找到")
        return JSONResponse(status_code=400, content={"error": "登录失败"})
    # 登录成功写 cookie
    if callable(set_auth_cookies):
        set_auth_cookies(response, session.access_token, session.refresh_token, session.expires_in)  # type: ignore[arg-type]
    return {"msg": "登录成功", "access_token": session.access_token}


@router.post("/otp/send")
async def otp_send(req: EmailRequest, request: Request):
    supabase = _require_supabase(request)
    ok, reason = await _verify_turnstile(request)
    if not ok:
        logger.info("人机验证失败，拒绝发送 OTP")
        return JSONResponse(status_code=400, content={"error": "人机验证失败", "detail": reason})
    try:
        supabase.auth.sign_in_with_otp({"email": req.email, "should_create_user": True})
        return {"ok": True}
    except Exception as e:
        logger.error(f"发送 OTP 失败: {str(e)}")
        return JSONResponse(status_code=400, content={"error": "发送失败", "detail": str(e)})


@router.post("/otp/verify")
async def otp_verify(req: VerifyOtpRequest, response: Response, request: Request):
    supabase = _require_supabase(request)
    set_auth_cookies, _, _, _, _ = _get_helpers(request)
    ok, reason = await _verify_turnstile(request)
    if not ok:
        return JSONResponse(status_code=400, content={"error": "人机验证失败", "detail": reason})
    try:
        res = supabase.auth.verify_otp({"email": req.email, "token": req.code, "type": "email"})
    except Exception:
        return JSONResponse(status_code=400, content={"error": "验证码错误或已过期"})

    session = getattr(res, "session", None)
    if not session or not getattr(session, "access_token", None):
        return JSONResponse(status_code=400, content={"error": "登录失败"})

    # 验证密码不能为空
    if not req.password or not req.password.strip():
        return JSONResponse(status_code=400, content={"error": "密码不能为空"})

    # 在验证成功后设置密码
    try:
        supabase.auth.update_user({"password": req.password})
        logger.info(f"用户 {req.email} 注册时成功设置密码")
    except Exception as e:
        logger.error(f"设置密码失败: {str(e)}")
        return JSONResponse(status_code=500, content={"error": "注册成功但设置密码失败，请使用密码重置功能"})

    if callable(set_auth_cookies):
        set_auth_cookies(response, session.access_token, session.refresh_token, session.expires_in)  # type: ignore[arg-type]
    return {"ok": True}


@router.get("/me")
async def me(
    request: Request,
    response: Response,
    token: str | None = None,
    access_token: str | None = Cookie(default=None),
    refresh_token: str | None = Cookie(default=None),
):
    supabase = _require_supabase(request)
    _, _, do_refresh, _, _ = _get_helpers(request)

    # Support multiple token sources:
    # 1. Query parameter (?token=xxx)
    # 2. Cookie (access_token)
    # 3. Authorization header (Bearer xxx) - for CLI and API clients
    auth_header = request.headers.get("authorization") or request.headers.get("Authorization")
    bearer_token = None
    if auth_header and auth_header.startswith("Bearer "):
        bearer_token = auth_header[7:]  # Remove "Bearer " prefix

    token_to_use = token or bearer_token or access_token
    if not token_to_use:
        raise HTTPException(401, detail="未登录")
    try:
        try:
            res = supabase.auth.get_user(token_to_use)
        except Exception as e:
            msg = str(e).lower()
            if refresh_token and ("expired" in msg or "invalid" in msg) and callable(do_refresh):
                logger.info("access_token 失效，尝试使用 refresh_token 刷新后重试 /me")
                new_at = do_refresh(response, refresh_token)
                if not new_at:
                    raise HTTPException(401, detail="登录已过期，请重新登录")
                res = supabase.auth.get_user(new_at)
            else:
                raise
        user = getattr(res, "user", None)
        return user.dict() if user else {"detail": "未登录"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"/me 获取用户失败: {e}")
        raise HTTPException(500, detail="查询失败")
    
# @router.post("/login/google")
# async def Google_login(response: Response, request: Request):
#     supabase = _require_supabase(request)
#     response = supabase.auth.sign_in_with_oauth(
#     {"provider": "google",
#      token: response.credential,},
    
# )
    

@router.get("/google/url")
async def google_oauth_url(request: Request):
    """生成 Google OAuth URL (PKCE Flow)"""
    _, _, _, FRONTEND_URL, _ = _get_helpers(request)
    supabase = _require_supabase(request)

    try:
        # 使用 Supabase 的 OAuth URL 生成（PKCE Flow）
        # Callback URL 指向后端
        base_api_url=os.getenv('BACKEND_API_URL')
        backend_callback_url = f"{base_api_url}/google/callback"

        logger.info(f"[Google OAuth] 生成 OAuth URL, callback: {backend_callback_url}")

        res = supabase.auth.sign_in_with_oauth({
            "provider": "google",
            "options": {
                "redirect_to": backend_callback_url,
                "query_params": {
                    "access_type": "offline",
                    "prompt": "consent",
                },
            },
        })

        oauth_url = getattr(res, "url", None)
        if not oauth_url:
            raise HTTPException(500, detail="无法生成 OAuth URL")

        logger.info(f"[Google OAuth] OAuth URL 生成成功")
        return {"url": oauth_url}

    except Exception as e:
        logger.error(f"[Google OAuth] 生成 URL 失败: {str(e)}")
        raise HTTPException(500, detail=f"生成 Google OAuth URL 失败: {str(e)}")


@router.get("/google/callback")
async def google_oauth_callback(
    request: Request,
    response: Response,
    code: str | None = None,
    error: str | None = None,
):
    """处理 Google OAuth callback (PKCE Flow)"""
    supabase = _require_supabase(request)
    set_auth_cookies, _, _, FRONTEND_URL, _ = _get_helpers(request)

    logger.info(f"[Google OAuth Callback] Received callback")
    logger.info(f"[Google OAuth Callback] Code: {'✅ Present' if code else '❌ Missing'}")
    logger.info(f"[Google OAuth Callback] Error: {error if error else 'None'}")

    # 检查错误
    if error:
        logger.error(f"[Google OAuth Callback] OAuth error: {error}")
        error_url = f"{FRONTEND_URL}/signin?error={error}"
        return RedirectResponse(url=error_url, status_code=302)

    # 检查 code
    if not code:
        logger.error("[Google OAuth Callback] Missing code parameter")
        error_url = f"{FRONTEND_URL}/signin?error=missing_code"
        return RedirectResponse(url=error_url, status_code=302)

    try:
        # 使用 Supabase 交换 code 为 session (PKCE Flow)
        logger.info("[Google OAuth Callback] Exchanging code for session...")

        exchange_res = supabase.auth.exchange_code_for_session({"auth_code": code})
        session = getattr(exchange_res, "session", None)

        if not session or not getattr(session, "access_token", None):
            logger.error("[Google OAuth Callback] No session or access_token returned")
            raise HTTPException(500, detail="未能获取会话信息")

        logger.info(f"[Google OAuth Callback] Session obtained successfully")
        logger.info(f"[Google OAuth Callback] User email: {session.user.email if hasattr(session, 'user') else 'N/A'}")

        # 重定向到前端 dashboard
        dashboard_url = f"{FRONTEND_URL}/dashboard"
        logger.info(f"[Google OAuth Callback] Redirecting to: {dashboard_url}")

        # 创建重定向响应
        redirect_response = RedirectResponse(url=dashboard_url, status_code=302)

        # 设置 cookies（与 /login 相同的逻辑）
        if callable(set_auth_cookies):
            set_auth_cookies(
                redirect_response,
                session.access_token,
                session.refresh_token,
                session.expires_in or 3600
            )
            logger.info("[Google OAuth Callback] Cookies set successfully")

        return redirect_response

    except Exception as e:
        logger.error(f"[Google OAuth Callback] Error: {str(e)}")
        error_url = f"{FRONTEND_URL}/signin?error={str(e)}"
        return RedirectResponse(url=error_url, status_code=302)


@router.post("/logout")
async def logout(response: Response, request: Request):
    _, clear_auth_cookies, _, _, _ = _get_helpers(request)
    if callable(clear_auth_cookies):
        clear_auth_cookies(response)
    return {"ok": True}
