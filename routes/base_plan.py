"""
抽象基类模块 - 提供套餐路由的公共逻辑
支持通过配置创建不同套餐的路由（高级套餐、无限流量套餐等）
"""
from fastapi import APIRouter, HTTPException, Response, Request, Cookie, Header, BackgroundTasks
from pydantic import BaseModel
from loguru import logger
from typing import Dict, Any, List, Optional
from dataclasses import dataclass
import os


@dataclass
class PlanConfig:
    """套餐配置类 - 定义套餐的所有参数"""
    plan_name: str          # 套餐名称（如"高级套餐"）
    plan_id: str            # 套餐ID（如"advanced"）
    plan_keyword: str       # 套餐识别关键字（用于subscription_url匹配）
    plan_price_env: str     # 价格环境变量名（如"ADVANCED_PLAN_PRICE"）
    plan_currency_env: str  # 货币环境变量名（如"ADVANCED_PLAN_CURRENCY"）
    gateway_ip_env: str     # 网关IP环境变量名（如"advanced_gateway_ip"）
    domain_url: str         # 域名（如"advanced.selfgo.asia"）
    url_alias: str          # 别名（如"advanced_plan"）
    up_mbps: int            # 上传带宽（Mbps）
    down_mbps: int          # 下载带宽（Mbps）
    duration_days: int = 365  # 套餐时长（天）

    def get_price(self) -> int:
        """从环境变量读取价格（单位：分）"""
        default_price = "0"
        price = int(os.getenv(self.plan_price_env, default_price))
        if price == 0:
            logger.warning(f"环境变量 {self.plan_price_env} 未设置或为0")
        return price

    def get_currency(self) -> str:
        """从环境变量读取货币"""
        return os.getenv(self.plan_currency_env, "cny")

    def get_gateway_ip(self) -> str:
        """从环境变量读取网关IP"""
        gateway_ip = os.getenv(self.gateway_ip_env)
        if not gateway_ip:
            raise ValueError(f"环境变量 {self.gateway_ip_env} 未设置")
        return gateway_ip


# Pydantic 模型
class PlanResponse(BaseModel):
    """套餐检查响应模型"""
    has_plan: bool
    plans: List[Dict[str, Any]]
    all_products: List[Dict[str, Any]]


class PlanPurchaseRequest(BaseModel):
    """套餐购买请求模型"""
    phone: str = ""
    plan_id: str  # 套餐ID
    plan_name: str  # 套餐名称
    duration_days: int = 365  # 套餐时长，默认365天
    payment_method: str  # 支付方式：stripe 或 h5zhifu
    pay_type: str = "alipay"  # h5zhifu专用：alipay 或 wechat


class PlanPurchaseResponse(BaseModel):
    """套餐购买响应模型"""
    success: bool
    message: str
    order_id: Optional[str] = None
    provider: str  # 支付提供商：stripe 或 h5zhifu
    payment_data: Dict[str, Any]  # 统一的支付数据结构
    amount: int
    currency: str
    plan_name: str


def generate_trade_number() -> int:
    """生成交易号，暂时默认返回1"""
    return 1


def create_plan_router(config: PlanConfig) -> APIRouter:
    """
    基于配置创建套餐路由

    Args:
        config: 套餐配置对象

    Returns:
        APIRouter: 包含所有套餐端点的路由器
    """
    router = APIRouter(tags=[config.plan_id])

    # 从配置获取价格和货币（在路由创建时读取）
    PLAN_PRICE = config.get_price()
    PLAN_CURRENCY = config.get_currency()
    WEBHOOK_BASE_URL = os.getenv("WEBHOOK_BASE_URL", "https://api.selfgo.asia")

    logger.info(f"=== 创建套餐路由: {config.plan_name} ===")
    logger.info(f"  套餐ID: {config.plan_id}")
    logger.info(f"  价格: {PLAN_PRICE}分")
    logger.info(f"  货币: {PLAN_CURRENCY}")
    logger.info(f"  网关: {config.gateway_ip_env}")
    logger.info(f"  域名: {config.domain_url}")

    @router.get(f"/user/{config.plan_id}-plan")
    async def check_plan(
        request: Request,
        response: Response,
        token: str | None = None,
        access_token: str | None = Cookie(default=None),
        refresh_token: str | None = Cookie(default=None),
    ):
        f"""检查用户是否拥有{config.plan_name}，返回布尔值和详细信息"""
        supabase = getattr(request.app.state, "supabase", None)
        pd_db = getattr(request.app.state, "pd_db", None)
        do_refresh = getattr(request.app.state, "refresh_session_and_set_cookies", None)

        if not supabase:
            raise HTTPException(500, detail="Supabase 未初始化")
        if not pd_db:
            raise HTTPException(500, detail="数据库未初始化")

        token_to_use = token or access_token
        if not token_to_use:
            raise HTTPException(401, detail="未登录")

        try:
            # 获取用户信息
            try:
                _res = supabase.auth.get_user(token_to_use)
            except Exception as e:
                msg = str(e).lower()
                if refresh_token and ("expired" in msg or "invalid" in msg) and callable(do_refresh):
                    logger.info(f"access_token 失效，尝试 refresh_token 刷新后重试 /user/{config.plan_id}-plan")
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

            logger.info(f"检查用户{config.plan_name}: {email}")

            # 调用 fetch_product_user 获取用户产品数据
            from center_management.db.product import ProductConfig
            product_config = ProductConfig()
            user_products = product_config.fetch_product_user(user_email=email)

            if not user_products:
                return {
                    "has_plan": False,
                    "plans": [],
                    "all_products": []
                }

            # 检查是否有指定套餐（通过关键字识别）
            plans = []
            all_products = []

            for product in user_products:
                all_products.append(product)

                # 检查 subscription_url 中是否包含套餐标识
                if isinstance(product, dict):
                    subscription_url = product.get("subscription_url", "")
                    if subscription_url and config.plan_keyword in str(subscription_url).lower():
                        plans.append(product)

            has_plan = len(plans) > 0

            logger.info(f"用户 {email} {config.plan_name}检查结果: {has_plan}, 找到 {len(plans)} 个套餐")

            return {
                "has_plan": has_plan,
                "plans": plans,
                "all_products": all_products
            }

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"检查用户{config.plan_name}失败: {e}")
            raise HTTPException(500, detail="查询失败")

    @router.get(f"/user/{config.plan_id}-plan/simple")
    async def check_plan_simple(
        request: Request,
        response: Response,
        token: str | None = None,
        access_token: str | None = Cookie(default=None),
        refresh_token: str | None = Cookie(default=None),
    ):
        f"""简化版本：仅返回布尔值表示用户是否有{config.plan_name}"""
        supabase = getattr(request.app.state, "supabase", None)
        pd_db = getattr(request.app.state, "pd_db", None)
        do_refresh = getattr(request.app.state, "refresh_session_and_set_cookies", None)

        if not supabase:
            raise HTTPException(500, detail="Supabase 未初始化")
        if not pd_db:
            raise HTTPException(500, detail="数据库未初始化")

        token_to_use = token or access_token
        if not token_to_use:
            raise HTTPException(401, detail="未登录")

        try:
            # 获取用户信息
            try:
                _res = supabase.auth.get_user(token_to_use)
            except Exception as e:
                msg = str(e).lower()
                if refresh_token and ("expired" in msg or "invalid" in msg) and callable(do_refresh):
                    logger.info(f"access_token 失效，尝试 refresh_token 刷新后重试 /user/{config.plan_id}-plan/simple")
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

            logger.info(f"简化检查用户{config.plan_name}: {email}")

            # 调用 fetch_product_user 获取用户产品数据
            from center_management.db.product import ProductConfig
            product_config = ProductConfig()
            user_products = product_config.fetch_product_user(user_email=email)

            if not user_products:
                return {"has_plan": False}

            # 检查是否有指定套餐
            for product in user_products:
                if isinstance(product, dict):
                    subscription_url = product.get("subscription_url", "")
                    if subscription_url and config.plan_keyword in str(subscription_url).lower():
                        logger.info(f"用户 {email} 拥有{config.plan_name}")
                        return {"has_plan": True}

            logger.info(f"用户 {email} 没有{config.plan_name}")
            return {"has_plan": False}

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"检查用户{config.plan_name}失败: {e}")
            raise HTTPException(500, detail="查询失败")

    @router.get("/user/order-status/{order_id}")
    async def get_order_product_status(
        order_id: str,
        request: Request,
        response: Response,
        token: str | None = None,
        access_token: str | None = Cookie(default=None),
        refresh_token: str | None = Cookie(default=None),
    ):
        """查询订单的产品生成状态（供前端轮询使用）"""
        supabase = getattr(request.app.state, "supabase", None)
        do_refresh = getattr(request.app.state, "refresh_session_and_set_cookies", None)

        if not supabase:
            raise HTTPException(500, detail="Supabase 未初始化")

        token_to_use = token or access_token
        if not token_to_use:
            raise HTTPException(401, detail="未登录")

        try:
            # 获取用户信息
            try:
                _res = supabase.auth.get_user(token_to_use)
            except Exception as e:
                msg = str(e).lower()
                if refresh_token and ("expired" in msg or "invalid" in msg) and callable(do_refresh):
                    logger.info("access_token 失效，尝试 refresh_token 刷新后重试")
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
            logger.info(f"查询订单状态: order_id={order_id}, user={email}")

            # 获取订单产品生成状态
            from center_management.db.order import OrderConfig
            order_config = OrderConfig()

            product_status = order_config.get_product_status(order_id)

            if product_status is None:
                raise HTTPException(404, detail="订单不存在")

            # 状态消息映射
            status_messages = {
                "pending": "订单已创建，等待支付",
                "processing": "支付成功，产品生成中，预计3-10秒",
                "completed": "产品生成完成，可以开始使用",
                "failed": "产品生成失败，请联系客服"
            }

            return {
                "order_id": order_id,
                "product_status": product_status,
                "message": status_messages.get(product_status, "未知状态"),
                "is_completed": product_status == "completed",
                "is_failed": product_status == "failed",
                "should_continue_polling": product_status in ["pending", "processing"]
            }

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"查询订单状态失败: {e}")
            raise HTTPException(500, detail="查询失败")

    @router.get("/user/order-by-session/{session_id}")
    async def get_order_by_session(
        session_id: str,
        request: Request,
        response: Response,
        token: str | None = None,
        access_token: str | None = Cookie(default=None),
        refresh_token: str | None = Cookie(default=None),
    ):
        """根据 Stripe Checkout Session ID 查询订单ID"""
        supabase = getattr(request.app.state, "supabase", None)
        do_refresh = getattr(request.app.state, "refresh_session_and_set_cookies", None)

        if not supabase:
            raise HTTPException(500, detail="Supabase 未初始化")

        token_to_use = token or access_token
        if not token_to_use:
            raise HTTPException(401, detail="未登录")

        try:
            # 获取用户信息
            try:
                _res = supabase.auth.get_user(token_to_use)
            except Exception as e:
                msg = str(e).lower()
                if refresh_token and ("expired" in msg or "invalid" in msg) and callable(do_refresh):
                    logger.info("access_token 失效，尝试 refresh_token 刷新")
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
            logger.info(f"查询订单 by Checkout Session: session_id={session_id}, user={email}")

            # 从数据库查询订单
            from center_management.db.order import OrderConfig
            order_config = OrderConfig()

            order = order_config.get_order_by_checkout_session(session_id, email)

            if not order:
                raise HTTPException(404, detail="订单不存在或不属于当前用户")

            return {
                "order_id": order["id"],
                "order_status": order["status"],
                "product_status": order.get("product_status", "pending")
            }

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"查询订单失败: {e}")
            raise HTTPException(500, detail="查询失败")

    @router.post(f"/user/{config.plan_id}-plan/purchase")
    async def purchase_plan(
        request: Request,
        response: Response,
        purchase_data: PlanPurchaseRequest,
        token: str | None = None,
        access_token: str | None = Cookie(default=None),
        refresh_token: str | None = Cookie(default=None),
    ):
        f"""购买{config.plan_name} - 创建Stripe/h5zhifu支付会话"""
        supabase = getattr(request.app.state, "supabase", None)
        pd_db = getattr(request.app.state, "pd_db", None)
        do_refresh = getattr(request.app.state, "refresh_session_and_set_cookies", None)

        if not supabase:
            raise HTTPException(500, detail="后端未初始化")
        if not pd_db:
            raise HTTPException(500, detail="数据库未初始化")

        token_to_use = token or access_token
        if not token_to_use:
            raise HTTPException(401, detail="未登录")

        try:
            # 获取用户信息
            try:
                _res = supabase.auth.get_user(token_to_use)
            except Exception as e:
                msg = str(e).lower()
                if refresh_token and ("expired" in msg or "invalid" in msg) and callable(do_refresh):
                    logger.info(f"access_token 失效，尝试 refresh_token 刷新后重试 /user/{config.plan_id}-plan/purchase")
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

            logger.info(f"用户 {email} 开始购买{config.plan_name}: {purchase_data.plan_name}")

            # 1. 生成交易号
            trade_num = generate_trade_number()

            # 2. 插入订单（状态：待支付）
            from center_management.db.order import OrderConfig
            order_config = OrderConfig()

            try:
                order_id = order_config.insert_order(
                    product_name=purchase_data.plan_name,
                    trade_num=trade_num,
                    amount=PLAN_PRICE,
                    email=email,
                    phone=purchase_data.phone,
                    payment_provider=purchase_data.payment_method
                )
                logger.info(f"订单插入成功，订单ID: {order_id}, 金额: {PLAN_PRICE}分, 支付方式: {purchase_data.payment_method}")
            except Exception as e:
                logger.error(f"插入订单失败: {e}")
                raise HTTPException(500, detail="创建订单失败")

            # 3. 验证并创建支付会话
            from payments.payment_factory import PaymentFactory, PaymentProvider

            # 验证支付方式
            if not PaymentFactory.validate_provider(purchase_data.payment_method):
                raise HTTPException(
                    400,
                    detail=f"不支持的支付方式: {purchase_data.payment_method}，支持的支付方式: {PaymentFactory.get_supported_providers()}"
                )

            try:
                provider = PaymentProvider(purchase_data.payment_method)
                provider_name = purchase_data.payment_method
                logger.info(f"使用支付方式: {provider_name}")

                # 根据支付方式准备不同的参数
                if provider == PaymentProvider.STRIPE:
                    # Stripe Checkout 参数
                    frontend_url = os.getenv("FRONTEND_URL")
                    success_url = f"{frontend_url}/dashboard?session_id={{CHECKOUT_SESSION_ID}}"
                    cancel_url = f"{frontend_url}/dashboard"

                    payment_params = {
                        "currency": PLAN_CURRENCY,
                        "customer_email": email,
                        "order_id": order_id,
                        "success_url": success_url,
                        "cancel_url": cancel_url
                    }
                    payment_currency = PLAN_CURRENCY
                elif provider == PaymentProvider.H5ZHIFU:
                    # h5zhifu 参数（从环境变量读取配置）
                    h5_app_id = os.getenv("H5ZHIFU_APP_ID")
                    h5_secret_key = os.getenv("H5ZHIFU_SECRET_KEY")
                    h5_notify_url = os.getenv("H5ZHIFU_NOTIFY_URL", f"{WEBHOOK_BASE_URL}/webhook/h5zhifu/{config.plan_id}-plan")

                    if not h5_app_id or not h5_secret_key:
                        logger.error("h5zhifu 配置不完整：缺少 H5ZHIFU_APP_ID 或 H5ZHIFU_SECRET_KEY")
                        raise HTTPException(500, detail="h5zhifu 支付配置错误，请联系管理员")

                    payment_params = {
                        "app_id": h5_app_id,
                        "secret_key": h5_secret_key,
                        "out_trade_no": trade_num,
                        "pay_type": purchase_data.pay_type,
                        "notify_url": h5_notify_url,
                        "attach": order_id  # 附加订单ID用于回调识别
                    }
                    payment_currency = "cny"  # h5zhifu 使用人民币
                else:
                    raise HTTPException(500, detail="不支持的支付方式")

                # 调用支付服务创建支付
                payment_result = None
                if provider == PaymentProvider.STRIPE:
                    # 使用 Stripe Checkout Session
                    from payments.stripe_payment import StripePaymentService
                    #计划修改此处在这里加入plan_id方便追踪产品
                    payment_result = StripePaymentService.create_checkout_session(
                        product_name=purchase_data.plan_name,
                        amount=PLAN_PRICE,
                        product_id=config.plan_id,
                        currency=PLAN_CURRENCY,
                        customer_email=email,
                        order_id=order_id,
                        success_url=success_url,
                        cancel_url=cancel_url
                    )
                else:
                    # 使用 PaymentFactory 处理其他支付方式
                    payment_result = PaymentFactory.create_payment(
                        provider=provider,
                        product_name=purchase_data.plan_name,
                        amount=PLAN_PRICE,
                        email=email,
                        phone=purchase_data.phone,
                        **payment_params
                    )

                if not payment_result.get("success"):
                    error_msg = payment_result.get("error", "创建支付会话失败")
                    logger.error(f"创建{provider_name}支付失败: {error_msg}")
                    raise HTTPException(500, detail=f"创建支付失败: {error_msg}")

                logger.info(f"✅ {provider_name}支付会话创建成功")

                # 统一返回格式
                payment_data = {}
                if provider == PaymentProvider.STRIPE:
                    payment_data = {
                        "checkout_session_id": payment_result.get("checkout_session_id"),
                        "checkout_url": payment_result.get("checkout_url")
                    }

                    # 更新订单，记录 Stripe Checkout Session ID
                    checkout_session_id = payment_result.get("checkout_session_id")
                    if checkout_session_id:
                        try:
                            order_config.update_checkout_session_id(
                                order_id=order_id,
                                checkout_session_id=checkout_session_id
                            )
                            logger.info(f"✅ 订单 Checkout Session ID 已记录: {checkout_session_id}")
                        except Exception as update_error:
                            logger.error(f"⚠️ 更新订单 Checkout Session ID 失败: {update_error}")
                            # 不抛出异常，因为支付已创建成功，允许继续

                elif provider == PaymentProvider.H5ZHIFU:
                    payment_data = {
                        "payment_url": payment_result.get("payment_url"),
                        "out_trade_no": payment_result.get("out_trade_no")
                    }

                return {
                    "success": True,
                    "message": f"{provider_name}支付会话创建成功，请完成支付",
                    "order_id": order_id,
                    "provider": provider_name,
                    "payment_data": payment_data,
                    "amount": PLAN_PRICE,
                    "currency": payment_currency,
                    "plan_name": purchase_data.plan_name
                }

            except HTTPException:
                raise
            except Exception as e:
                logger.error(f"创建支付会话失败: {e}")
                raise HTTPException(500, detail=f"创建支付失败: {str(e)}")

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"购买{config.plan_name}失败: {e}")
            raise HTTPException(500, detail="购买失败")



    return router
