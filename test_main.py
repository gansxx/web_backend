from fastapi import FastAPI, HTTPException, Depends, Response, Request, Cookie
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, EmailStr
from supabase import create_client, Client
from loguru import logger
import os
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

app = FastAPI(title="Supabase Login Demo")

# 从环境变量读取配置
SUPABASE_URL = os.getenv('SUPABASE_URL', 'http://localhost:8000')
SUPABASE_ANON_KEY = os.getenv('ANON_KEY', 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyAgCiAgICAicm9sZSI6ICJhbm9uIiwKICAgICJpc3MiOiAic3VwYWJhc2UtZGVtbyIsCiAgICAiaWF0IjogMTY0MTc2OTIwMCwKICAgICJleHAiOiAxNzk5NTM1NjAwCn0.dc_X5iR_VP_qT0zsiyj_I_OZ2T9FtRU2BBNWN8Bu4GE')
FRONTEND_URL = os.getenv('FRONTEND_URL', 'http://localhost:3000')
logger.info(f"SUPABASE_URL: {SUPABASE_URL}")
logger.info(f"ANON_KEY:{SUPABASE_ANON_KEY}")
logger.info(f"FRONTEND_URL:{FRONTEND_URL}")

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
async def recall(req: EmailRequest):
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
async def recall_reset(req: ResetPasswordRequest):
    try:
        # 先验证OTP码
        logger.debug(f"req.code是{req.code}")
        logger.debug(f"新密码是{req.new_password}")
        verify_res = supabase.auth.verify_otp({
            "email": req.email, 
            "token": req.code, 
            "type": "email"
        })
        
        if verify_res.user is None:
            return JSONResponse(status_code=400, content={"error": "验证码错误或已过期"})
        
        # 验证成功后，使用admin权限重置密码
        # 注意：这需要配置适当的权限或使用admin key
        try:
            # 使用admin API重置密码
            service_role_key = os.getenv('SERVICE_ROLE_KEY')
            if not service_role_key:
                logger.warning("未配置SERVICE_ROLE_KEY，无法自动重置密码")
                return {
                    "msg": "验证码验证成功，但密码重置需要管理员权限",
                    "verified": True,
                    "email": req.email,
                    "note": "请联系管理员重置密码"
                }
            
            admin_supabase = create_client(SUPABASE_URL, service_role_key)
            
            # 更新用户密码
            update_res = admin_supabase.auth.admin.update_user_by_id(
                verify_res.user.id,
                {"password": req.new_password}
            )
            
            if update_res.user:
                logger.info(f"用户 {req.email} 密码重置成功")
                return {"msg": "密码重置成功，请使用新密码登录"}
            else:
                return JSONResponse(status_code=500, content={"error": "密码重置失败"})
                
        except Exception as admin_error:
            logger.error(f"管理员API调用失败: {str(admin_error)}")
            # 如果admin API不可用，提供替代方案
            return JSONResponse(status_code=400, content={
                "error": "验证码验证成功，但密码重置需要管理员权限",
                "verified": True,
                "email": req.email,
                "note": "请联系管理员重置密码"
            })
            
    except Exception as e:
        logger.error(f"密码重置失败: {str(e)}")
        # 检查是否是验证码过期错误
        if "expired" in str(e).lower() or "invalid" in str(e).lower():
            return JSONResponse(status_code=400, content={"error": "验证码已过期，请重新发送"})
        return JSONResponse(status_code=400, content={"error": "密码重置失败", "detail": str(e)})

@app.post("/login")
async def login(req: AuthRequest, response: Response):
    try:
        res = supabase.auth.sign_in_with_password({"email": req.email, "password": req.password})
    except Exception as e:
        logger.info(f"{req.email}用户登录失败")
        return JSONResponse(status_code=400, content={"error": "登录失败,输入密码或账号有误"})
        # return {"msg": "登录失败,输入密码或账号有误", "access_token": ""}
        # raise HTTPException(401, detail="登录失败")

    # 登录成功后同样写入 cookie，便于前端 middleware 放行
    response.set_cookie(
        key="access_token",
        value=res.session.access_token,
        httponly=True,
        samesite="lax",
        secure=False,  # 本地 http 开发用 False；上生产必须 True
        max_age=res.session.expires_in,
        path="/",
    )
    response.set_cookie(
        key="refresh_token",
        value=res.session.refresh_token,
        httponly=True,
        samesite="lax",
        secure=False,
        max_age=60 * 60 * 24 * 30,
        path="/",
    )
    return {"msg": "登录成功", "access_token": res.session.access_token}

# 发送邮箱验证码
@app.post("/otp/send")
async def otp_send(req: EmailRequest):
    try:
        # should_create_user=True：不存在时自动创建
        supabase.auth.sign_in_with_otp({"email": req.email, "should_create_user": True})
        # send OTP 通常不返回 session，若有异常 SDK 会抛错或返回 error
        return {"ok": True}
    except Exception as e:
        return JSONResponse(status_code=400, content={"error": "发送失败", "detail": str(e)})

# 校验验证码并设置 cookie
@app.post("/otp/verify")
async def otp_verify(req: VerifyOtpRequest, response: Response):
    try:
        res = supabase.auth.verify_otp({"email": req.email, "token": req.code, "type": "email"})
    except Exception as e:
        return JSONResponse(status_code=400, content={"error": "验证码错误或已过期"})

    response.set_cookie(
        key="access_token",
        value=res.session.access_token,
        httponly=True,
        samesite="lax",
        secure=False,  # 本地 http 开发用 False；上生产必须 True
        max_age=res.session.expires_in,
        path="/",
    )
    response.set_cookie(
        key="refresh_token",
        value=res.session.refresh_token,
        httponly=True,
        samesite="lax",
        secure=False,
        max_age=60 * 60 * 24 * 30,
        path="/",
    )
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
    response.delete_cookie("access_token", path="/")
    response.delete_cookie("refresh_token", path="/")
    return {"ok": True}

# 健康检查端点
@app.get("/health")
async def health_check():
    return {"status": "healthy", "timestamp": "2025-01-27T12:00:00Z"}