from fastapi import APIRouter, HTTPException, Response, Request, Cookie
from loguru import logger

router = APIRouter(tags=["user"])


@router.get("/user/products")
async def get_user_products(
    request: Request,
    response: Response,
    token: str | None = None,
    access_token: str | None = Cookie(default=None),
    refresh_token: str | None = Cookie(default=None),
):
    supabase = getattr(request.app.state, "supabase", None)
    spdb = getattr(request.app.state, "spdb", None)
    do_refresh = getattr(request.app.state, "refresh_session_and_set_cookies", None)
    if not supabase:
        raise HTTPException(500, detail="Supabase 未初始化")
    if not spdb:
        raise HTTPException(500, detail="数据库未初始化")

    token_to_use = token or access_token
    if not token_to_use:
        raise HTTPException(401, detail="未登录")

    try:
        try:
            _res = supabase.auth.get_user(token_to_use)
        except Exception as e:
            msg = str(e).lower()
            if refresh_token and ("expired" in msg or "invalid" in msg) and callable(do_refresh):
                logger.info("access_token 失效，尝试 refresh_token 刷新后重试 /user/products")
                new_at = do_refresh(response, refresh_token)
                if not new_at:
                    raise HTTPException(401, detail="登录已过期，请重新登录")
                _res = supabase.auth.get_user(new_at)
            else:
                raise
        user = getattr(_res, "user", None)
        if not user or not getattr(user, "email", None):
            raise HTTPException(401, detail="未登录或用户无邮箱信息")
        email = user.email
        if not isinstance(email, str) or not email:
            raise HTTPException(401, detail="未登录或用户无邮箱信息")

        logger.info(f"查询用户产品: {email}")
        data = spdb.fetch_data_user(user_email=email)
        return data or []
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取用户产品失败: {e}")
        raise HTTPException(500, detail="查询失败")


@router.get("/user/orders")
async def get_user_orders(
    request: Request,
    response: Response,
    token: str | None = None,
    access_token: str | None = Cookie(default=None),
    refresh_token: str | None = Cookie(default=None),
):
    supabase = getattr(request.app.state, "supabase", None)
    spdb = getattr(request.app.state, "spdb", None)
    do_refresh = getattr(request.app.state, "refresh_session_and_set_cookies", None)
    if not supabase:
        raise HTTPException(500, detail="Supabase 未初始化")
    if not spdb:
        raise HTTPException(500, detail="数据库未初始化")

    token_to_use = token or access_token
    if not token_to_use:
        raise HTTPException(401, detail="未登录")

    try:
        try:
            _user_res = supabase.auth.get_user(token_to_use)
        except Exception as e:
            msg = str(e).lower()
            if refresh_token and ("expired" in msg or "invalid" in msg) and callable(do_refresh):
                logger.info("access_token 失效，尝试 refresh_token 刷新后重试 /user/orders")
                new_at = do_refresh(response, refresh_token)
                if not new_at:
                    raise HTTPException(401, detail="登录已过期，请重新登录")
                _user_res = supabase.auth.get_user(new_at)
            else:
                raise
        user = getattr(_user_res, "user", None)
        if not user or not getattr(user, "email", None):
            raise HTTPException(401, detail="未登录或用户无邮箱信息")
        email = user.email
        if not isinstance(email, str) or not email:
            raise HTTPException(401, detail="未登录或用户无邮箱信息")
        logger.info(f"查询用户订单: {email}")
        data = spdb.fetch_order_user(user_email=email)
        return data or []
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取用户订单失败: {e}")
        raise HTTPException(500, detail="查询失败")
