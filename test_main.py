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
from center_management.db.product import ProductConfig
from center_management.db.order import OrderConfig
from center_management.db.ticket import TicketConfig

# 加载环境变量
load_dotenv()

app = FastAPI(title="Supabase Login Demo")

# 从环境变量读取配置
SUPABASE_URL = os.getenv('SUPABASE_URL', 'http://localhost:8000')
SUPABASE_ANON_KEY = os.getenv('ANON_KEY', 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyAgCiAgICAicm9sZSI6ICJhbm9uIiwKICAgICJpc3MiOiAic3VwYWJhc2UtZGVtbyIsCiAgICAiaWF0IjogMTY0MTc2OTIwMCwKICAgICJleHAiOiAxNzk5NTM1NjAwCn0.dc_X5iR_VP_qT0zsiyj_I_OZ2T9FtRU2BBNWN8Bu4GE')
FRONTEND_URL = os.getenv('FRONTEND_URL', 'http://localhost:3000')
TURNSTILE_SECRET_KEY = os.getenv('TURNSTILE_SECRET_KEY', '')
logger.info(f"SUPABASE_URL: {SUPABASE_URL}")
# logger.info(f"ANON_KEY:{SUPABASE_ANON_KEY}")
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

# 使用 refresh_token 刷新会话并回写 Cookie
def refresh_session_and_set_cookies(response: Response, refresh_token: str) -> str | None:
    """尝试使用 Supabase 刷新令牌接口刷新 access_token，并写入新 Cookie。
    返回新的 access_token；若失败返回 None。
    """
    try:
        url = f"{SUPABASE_URL.rstrip('/')}/auth/v1/token?grant_type=refresh_token"
        headers = {
            "apikey": SUPABASE_ANON_KEY,
            "authorization": f"Bearer {SUPABASE_ANON_KEY}",
            "content-type": "application/json",
        }
        payload = {"refresh_token": refresh_token}
        r = requests.post(url, headers=headers, json=payload, timeout=6)
        if r.status_code != 200:
            logger.warning(f"刷新令牌失败: {r.status_code} {r.text}")
            return None
        data = r.json() if r.content else {}
        access_token = data.get("access_token")
        new_refresh = data.get("refresh_token") or refresh_token
        expires_in = data.get("expires_in") or 3600
        if not access_token:
            logger.warning("刷新接口未返回 access_token")
            return None
        # 回写 Cookie
        set_auth_cookies(response, access_token, new_refresh, int(expires_in))
        logger.info("access_token 已通过 refresh_token 刷新并回写 Cookie")
        return access_token
    except Exception as e:
        logger.error(f"刷新会话异常: {e}")
        return None

# 创建 Supabase 客户端
supabase: Client = create_client(SUPABASE_URL, SUPABASE_ANON_KEY)

# 初始化 Supabase 产品数据库操作（使用 service role key）
try:
    pd_db = ProductConfig()
except Exception as e:
    logger.error(f"初始化 ProductConfig 失败: {e}")
    pd_db = None

# 初始化订单数据库操作
try:
    order_db = OrderConfig()
except Exception as e:
    logger.error(f"初始化 OrderConfig 失败: {e}")
    order_db = None

# 初始化工单数据库操作
try:
    ticket_db = TicketConfig()
except Exception as e:
    logger.error(f"初始化 TicketConfig 失败: {e}")
    ticket_db = None

# 将共享对象挂载到 app.state，供子路由访问
app.state.supabase = supabase
app.state.pd_db = pd_db
app.state.order_db = order_db
app.state.ticket_db = ticket_db
app.state.refresh_session_and_set_cookies = refresh_session_and_set_cookies
app.state.set_auth_cookies = set_auth_cookies
app.state.clear_auth_cookies = clear_auth_cookies
app.state.verify_turnstile = verify_turnstile
app.state.FRONTEND_URL = FRONTEND_URL
app.state.SUPABASE_URL = SUPABASE_URL

# 允许前端 (Next.js) 跨域携带 cookie
app.add_middleware(
    CORSMiddleware,
    allow_origins=[FRONTEND_URL, "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 注册拆分的用户数据路由
try:
    from routes.user_data import router as user_data_router
    app.include_router(user_data_router)
    logger.info("routes.user_data 已注册")
except Exception as _e:
    logger.error(f"注册 routes.user_data 失败: {_e}")

# 注册 auth 路由
try:
    from routes.auth import router as auth_router
    app.include_router(auth_router)
    logger.info("routes.auth 已注册")
except Exception as _e:
    logger.error(f"注册 routes.auth 失败: {_e}")

# 注册 free_plan 路由
try:
    from routes.free_plan import router as free_plan_router
    app.include_router(free_plan_router)
    logger.info("routes.free_plan 已注册")
except Exception as _e:
    logger.error(f"注册 routes.free_plan 失败: {_e}")

# 注册 ticket 路由
try:
    from routes.ticket import router as ticket_router
    app.include_router(ticket_router)
    logger.info("routes.ticket 已注册")
except Exception as _e:
    logger.error(f"注册 routes.ticket 失败: {_e}")

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

# 健康检查端点
@app.get("/health")
async def health_check():
    return {"status": "healthy", "timestamp": "2025-01-27T12:00:00Z"}
