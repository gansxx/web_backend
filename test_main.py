from fastapi import FastAPI, HTTPException, Depends, Response, Request, Cookie
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, EmailStr
from supabase import create_client, Client
from loguru import logger
import os
from dotenv import load_dotenv
from urllib.parse import urlparse
import requests
import json

# 加载环境变量
load_dotenv()

app = FastAPI(title="Supabase Login Demo")

# 从环境变量读取配置
SUPABASE_URL = os.getenv('SUPABASE_URL', 'http://localhost:8000')
SUPABASE_ANON_KEY = os.getenv('ANON_KEY', 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyAgCiAgICAicm9sZSI6ICJhbm9uIiwKICAgICJpc3MiOiAic3VwYWJhc2UtZGVtbyIsCiAgICAiaWF0IjogMTY0MTc2OTIwMCwKICAgICJleHAiOiAxNzk5NTM1NjAwCn0.dc_X5iR_VP_qT0zsiyj_I_OZ2T9FtRU2BBNWN8Bu4GE')
FRONTEND_URL = os.getenv('FRONTEND_URL', 'http://localhost:3000')
TURNSTILE_SECRET_KEY = os.getenv('TURNSTILE_SECRET_KEY', '')
logger.info(f"SUPABASE_URL: {SUPABASE_URL}")
logger.info(f"ANON_KEY:{SUPABASE_ANON_KEY}")
logger.info(f"FRONTEND_URL:{FRONTEND_URL}")
service_role_key_env = os.getenv('SERVICE_ROLE_KEY')
masked_service = (
    service_role_key_env[:6] + "..." + service_role_key_env[-6:]
    if service_role_key_env and len(service_role_key_env) > 12 else ("MISSING" if not service_role_key_env else "MASKED")
)
logger.info(f"SERVICE_ROLE_KEY: {masked_service}")

# 依据 FRONTEND_URL 推导 Cookie 域与安全策略
_parsed_frontend = urlparse(FRONTEND_URL)
_frontend_host = _parsed_frontend.hostname or "localhost"
_frontend_scheme = _parsed_frontend.scheme or "http"
COOKIE_SECURE = _frontend_scheme == "https"
# 生产（可能跨站）场景：SameSite=None；本地开发：Lax
COOKIE_SAMESITE = "none" if COOKIE_SECURE else "lax"
# 域名策略：localhost/127.0.0.1 不设置 domain；其他情况设置为前端主机名
COOKIE_DOMAIN = None if _frontend_host in ("localhost", "127.0.0.1") or "." not in _frontend_host else _frontend_host
logger.info(
    f"Cookie Policy -> secure={COOKIE_SECURE}, samesite={COOKIE_SAMESITE}, domain={COOKIE_DOMAIN or '(unset)'}"
)

# Turnstile verification helper (async)
async def verify_turnstile(req: Request) -> tuple[bool, str | None]:
    """Validate Cloudflare Turnstile token from header (preferred) or JSON body.
    Returns (ok, reason)
    """
    try:
        token = req.headers.get('cf-turnstile-response')
        if not token:
            # Optional fallback: JSON body fields
            try:
                if req.headers.get('content-type', '').lower().startswith('application/json'):
                    body = await req.json()
                    token = body.get('cf_turnstile_response') or body.get('turnstileToken') or body.get('turnstile')
            except Exception:
                token = None
        if not token:
            return False, 'missing_token'
        if not TURNSTILE_SECRET_KEY:
            logger.warning('TURNSTILE_SECRET_KEY 未配置，跳过 Turnstile 校验（仅用于本地开发）')
            return True, None
        resp = requests.post(
            'https://challenges.cloudflare.com/turnstile/v0/siteverify',
            data={'secret': TURNSTILE_SECRET_KEY, 'response': token},
            timeout=5,
        )
        data = resp.json()
        if data.get('success'):
            return True, None
        else:
            logger.info(f"Turnstile 验证失败: {data}")
            return False, (data.get('error-codes') or ['verify_failed'])[0]
    except Exception as e:
        logger.error(f"Turnstile 校验异常: {e}")
        return False, 'verify_exception'

def set_auth_cookies(response: Response, access_token: str, refresh_token: str, access_expires_in: int) -> None:
    """统一设置鉴权 Cookie，确保跨域兼容（SameSite=None; Secure 且带 domain）。"""
    response.set_cookie(
        key="access_token",
        value=access_token,
        httponly=True,
        samesite=COOKIE_SAMESITE,
        secure=COOKIE_SECURE,
        max_age=access_expires_in,
        path="/",
        domain=COOKIE_DOMAIN,
    )
    response.set_cookie(
        key="refresh_token",
        value=refresh_token,
        httponly=True,
        samesite=COOKIE_SAMESITE,
        secure=COOKIE_SECURE,
        max_age=60 * 60 * 24 * 30,
        path="/",
        domain=COOKIE_DOMAIN,
    )

def clear_auth_cookies(response: Response) -> None:
    """统一清除鉴权 Cookie，使用同样的 domain/path/samesite 以确保删除生效。"""
    response.delete_cookie("access_token", path="/", domain=COOKIE_DOMAIN, samesite=COOKIE_SAMESITE)
    response.delete_cookie("refresh_token", path="/", domain=COOKIE_DOMAIN, samesite=COOKIE_SAMESITE)

# 创建 Supabase 客户端
supabase: Client = create_client(SUPABASE_URL, SUPABASE_ANON_KEY)

# 允许前端 (Next.js) 跨域携带 cookie
app.add_middleware(
    CORSMiddleware,
    allow_origins=[FRONTEND_URL, "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class AuthRequest(BaseModel):
    email: EmailStr
    password: str

class EmailRequest(BaseModel):
    email: EmailStr

class VerifyOtpRequest(BaseModel):
    email: EmailStr
    code: str  # 邮件中的 6 位（或你配置的长度）

class ResetPasswordRequest(BaseModel):
    email: EmailStr
    code: str  # 验证码
    new_password: str  # 新密码

@app.post("/signup")
async def signup(req: AuthRequest):
    try:
        res = supabase.auth.sign_up({"email": req.email, "password": req.password})
    except Exception as e:
        # 统一错误返回结构
        return JSONResponse(status_code=400, content={"error": "注册失败", "detail": str(e)})
    return {"msg": "注册成功", "user": res.user.dict()}

# 密码找回 - 发送重置密码邮件
@app.post("/recall")
async def recall(req: EmailRequest, request: Request):
    ok, reason = await verify_turnstile(request)
    if not ok:
        return JSONResponse(status_code=400, content={"error": "人机验证失败", "detail": reason})
    try:
        # 验证邮箱是否存在用户
        res = supabase.auth.sign_in_with_otp({
            "email": req.email, 
            "should_create_user": False,
            "options": {
                "email_redirect_to": f"{FRONTEND_URL}/recall"
            }
        })
        logger.info(f"密码重置邮件已发送到: {req.email}")
        return {"msg": "密码重置邮件已发送，请检查您的邮箱", "email": req.email}
    except Exception as e:
        logger.error(f"发送密码重置邮件失败: {str(e)}")
        # 为了安全，不暴露具体错误信息
        return {"msg": "如果该邮箱已注册，密码重置邮件将发送到您的邮箱"}


# 重置密码
@app.post("/recall/reset")
async def recall_reset(req: ResetPasswordRequest, request: Request):
    ok, reason = await verify_turnstile(request)
    if not ok:
        return JSONResponse(status_code=400, content={"error": "人机验证失败", "detail": reason})
    try:
        # 1) 验证 OTP 码
        logger.debug(f"recall_reset: 验证邮箱={req.email} 的 OTP")
        verify_res = supabase.auth.verify_otp({
            "email": req.email,
            "token": req.code,
            "type": "email",
        })

        if verify_res.user is None:
            return JSONResponse(status_code=400, content={"error": "验证码错误或已过期"})

        # 2) 优先使用当前会话更新密码（无需 service role）
        try:
            logger.debug("recall_reset: 尝试使用会话调用 auth.update_user 更新密码")
            upd = supabase.auth.update_user({"password": req.new_password})
            if getattr(upd, "user", None):
                logger.info(f"用户 {req.email} 使用会话更新密码成功")
                return {"msg": "密码重置成功，请使用新密码登录"}
        except Exception as session_update_err:
            logger.warning(f"使用会话更新密码失败，将回退到管理员API: {session_update_err}")

        # 3) 回退方案：使用管理员密钥
        service_role_key = os.getenv("SERVICE_ROLE_KEY")
        if not service_role_key:
            logger.warning("未配置 SERVICE_ROLE_KEY，无法使用管理员API重置密码")
            return JSONResponse(status_code=400, content={
                "error": "验证码验证成功，但服务端未配置管理员密钥，无法自动重置",
                "verified": True,
                "email": req.email,
                "note": "请联系管理员或稍后重试"
            })

        try:
            admin_supabase = create_client(SUPABASE_URL, service_role_key)
            update_res = admin_supabase.auth.admin.update_user_by_id(
                verify_res.user.id,
                {"password": req.new_password},
            )
            if getattr(update_res, "user", None):
                logger.info(f"用户 {req.email} 通过管理员API重置密码成功")
                return {"msg": "密码重置成功，请使用新密码登录"}
            logger.error("管理员API返回无用户对象，重置失败")
            return JSONResponse(status_code=500, content={"error": "密码重置失败"})
        except Exception as admin_error:
            # 典型错误：invalid JWT -> SERVICE_ROLE_KEY 与后端 JWT_SECRET 不匹配
            masked_key = (
                service_role_key[:6] + "..." + service_role_key[-6:]
                if len(service_role_key) > 12 else "(长度过短)"
            )
            logger.error(
                "管理员API调用失败: %s | 请检查 SERVICE_ROLE_KEY 是否来自同一 Supabase 实例，且与后端 JWT_SECRET 一致；当前 SUPABASE_URL=%s, SERVICE_ROLE_KEY(prefix/suffix)=%s",
                str(admin_error), SUPABASE_URL, masked_key,
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

@app.post("/login")
async def login(req: AuthRequest, response: Response, request: Request):
    ok, reason = await verify_turnstile(request)
    if not ok:
        return JSONResponse(status_code=400, content={"error": "人机验证失败", "detail": reason})
    try:
        res = supabase.auth.sign_in_with_password({"email": req.email, "password": req.password})
    except Exception as e:
        logger.info(f"{req.email}用户登录失败")
        return JSONResponse(status_code=400, content={"error": "登录失败,输入密码或账号有误"})
        # return {"msg": "登录失败,输入密码或账号有误", "access_token": ""}
        # raise HTTPException(401, detail="登录失败")

    # 登录成功后同样写入 cookie，便于前端 middleware 放行
    set_auth_cookies(response, res.session.access_token, res.session.refresh_token, res.session.expires_in)
    return {"msg": "登录成功", "access_token": res.session.access_token}

# 发送邮箱验证码
@app.post("/otp/send")
async def otp_send(req: EmailRequest, request: Request):
    ok, reason = await verify_turnstile(request)
    if not ok:
        return JSONResponse(status_code=400, content={"error": "人机验证失败", "detail": reason})
    try:
        # should_create_user=True：不存在时自动创建
        supabase.auth.sign_in_with_otp({"email": req.email, "should_create_user": True})
        # send OTP 通常不返回 session，若有异常 SDK 会抛错或返回 error
        return {"ok": True}
    except Exception as e:
        return JSONResponse(status_code=400, content={"error": "发送失败", "detail": str(e)})

# 校验验证码并设置 cookie
@app.post("/otp/verify")
async def otp_verify(req: VerifyOtpRequest, response: Response, request: Request):
    ok, reason = await verify_turnstile(request)
    if not ok:
        return JSONResponse(status_code=400, content={"error": "人机验证失败", "detail": reason})
    try:
        res = supabase.auth.verify_otp({"email": req.email, "token": req.code, "type": "email"})
    except Exception as e:
        return JSONResponse(status_code=400, content={"error": "验证码错误或已过期"})

    set_auth_cookies(response, res.session.access_token, res.session.refresh_token, res.session.expires_in)
    return {"ok": True}

# 支持从 cookie 读取 token（也兼容 ?token=... 方式）
@app.get("/me")
async def me(token: str | None = None, access_token: str | None = Cookie(default=None)):
    token_to_use = token or access_token
    if not token_to_use:
        raise HTTPException(401, detail="未登录")
    user = supabase.auth.get_user(token_to_use).user
    return user.dict() if user else {"detail": "未登录"}

# 退出登录：清除 cookie
@app.post("/logout")
async def logout(response: Response):
    clear_auth_cookies(response)
    return {"ok": True}

# 健康检查端点
@app.get("/health")
async def health_check():
    return {"status": "healthy", "timestamp": "2025-01-27T12:00:00Z"}