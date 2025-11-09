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
    is_free: bool = False   # 是否为免费套餐（免费套餐跳过支付流程）

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
        background_tasks: BackgroundTasks,
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

            # 1. 免费套餐检查（仅针对免费套餐）
            if config.is_free:
                from center_management.db.product import ProductConfig
                product_config = ProductConfig()
                user_products = product_config.fetch_product_user(user_email=email)

                for product in user_products:
                    if isinstance(product, dict):
                        subscription_url = product.get("subscription_url", "")
                        if subscription_url and "free" in str(subscription_url).lower():
                            logger.warning(f"用户 {email} 已有免费套餐，拒绝购买")
                            raise HTTPException(400, detail="您已经拥有免费套餐，无法重复购买")

            # 2. 生成交易号
            trade_num = generate_trade_number()

            # 3. 插入订单（状态：待支付）
            from center_management.db.order import OrderConfig
            order_config = OrderConfig()

            try:
                order_id = order_config.insert_order(
                    product_name=purchase_data.plan_name,
                    trade_num=trade_num,
                    amount=0 if config.is_free else PLAN_PRICE,
                    email=email,
                    phone=purchase_data.phone,
                    payment_provider="free" if config.is_free else purchase_data.payment_method
                )
                logger.info(f"订单插入成功，订单ID: {order_id}, 金额: {0 if config.is_free else PLAN_PRICE}分, 支付方式: {'free' if config.is_free else purchase_data.payment_method}")
            except Exception as e:
                logger.error(f"插入订单失败: {e}")
                raise HTTPException(500, detail="创建订单失败")

            # 4. 免费套餐直接处理，付费套餐走支付流程
            if config.is_free:
                # 免费套餐：直接标记为已支付并异步生成产品
                try:
                    # 更新订单状态为已支付
                    success = order_config.update_order_status(order_id, "已支付")
                    if not success:
                        logger.error(f"更新订单状态失败，订单ID: {order_id}")
                        raise HTTPException(500, detail="更新订单状态失败")

                    # 更新产品状态为生成中
                    order_config.update_product_status(order_id, "processing")
                    logger.info(f"✅ 免费套餐订单状态更新成功，订单ID: {order_id}")

                    # 启动后台任务异步生成产品
                    background_tasks.add_task(
                        generate_product_background,
                        product_id=config.plan_id,
                        order_id=order_id,
                        customer_email=email,
                        customer_phone=purchase_data.phone
                    )

                    logger.info(f"🚀 已启动后台任务生成免费套餐产品，订单: {order_id}")

                    # 立即返回成功响应
                    return {
                        "success": True,
                        "message": f"{purchase_data.plan_name}获取成功，产品生成中",
                        "order_id": order_id,
                        "provider": "free",
                        "payment_data": {},
                        "amount": 0,
                        "currency": "free",
                        "plan_name": purchase_data.plan_name
                    }
                except Exception as e:
                    logger.error(f"处理免费套餐失败: {e}")
                    raise HTTPException(500, detail=f"处理免费套餐失败: {str(e)}")

            # 5. 付费套餐：验证并创建支付会话
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

    # async def generate_product_background(
    #     order_id: str,
    #     customer_email: str,
    #     customer_phone: str
    # ):
    #     f"""后台任务：生成{config.plan_name}产品"""
    #     from center_management.db.order import OrderConfig
    #     from center_management.db.product import ProductConfig
    #     from center_management.backend_api_v2 import test_add_user_v2
    #     from center_management.node_manage import NodeProxy

    #     order_config = OrderConfig()
    #     product_config = ProductConfig()

    #     try:
    #         logger.info(f"🚀 [后台任务] 开始为订单 {order_id} 生成{config.plan_name}产品...")

    #         # 获取网关配置
    #         hostname = config.get_gateway_ip()
    #         gateway_user = os.getenv('gateway_user', 'admin')
    #         key_file = 'id_ed25519'

    #         # 使用NodeProxy连接并生成真实订阅URL
    #         logger.info(f"正在为用户 {customer_email} 生成{config.plan_name}订阅链接...")
    #         logger.info(f"连接服务器: {hostname}, 用户: {gateway_user}")
    #         proxy = NodeProxy(hostname, 22, gateway_user, key_file)

    #         # 调用test_add_user_v2生成订阅URL
    #         subscription_url = test_add_user_v2(
    #             proxy,
    #             name_arg=customer_email,
    #             url=config.domain_url,
    #             alias=config.url_alias,
    #             verify_link=True,
    #             max_retries=1,
    #             up_mbps=config.up_mbps,
    #             down_mbps=config.down_mbps,
    #         )

    #         if not subscription_url:
    #             raise Exception("订阅链接生成失败")

    #         logger.info(f"✅ {config.plan_name}订阅链接生成成功: {subscription_url}")

    #         # 插入产品数据
    #         product_id = product_config.insert_product(
    #             product_name=config.plan_name,
    #             subscription_url=subscription_url,
    #             email=customer_email,
    #             phone=customer_phone,
    #             duration_days=config.duration_days
    #         )

    #         logger.info(f"✅ 产品数据插入成功，产品ID: {product_id}")

    #         # 更新订单产品状态为"已完成"
    #         order_config.update_product_status(order_id, "completed")

    #         logger.info(f"🎉 [后台任务] 订单 {order_id} {config.plan_name}产品生成完成！")

    #     except Exception as e:
    #         logger.error(f"❌ [后台任务] 订单 {order_id} 产品生成失败: {e}")
    #         # 更新订单产品状态为"生成失败"
    #         try:
    #             order_config.update_product_status(order_id, "failed")
    #         except Exception as update_error:
    #             logger.error(f"更新订单产品状态为failed失败: {update_error}")

    # @router.post(f"/webhook/stripe/{config.plan_id}-plan")
    # async def stripe_webhook_handler(
    #     request: Request,
    #     background_tasks: BackgroundTasks,
    #     stripe_signature: str = Header(None, alias="stripe-signature")
    # ):
    #     f"""处理Stripe webhook回调 - 支付成功后异步生成产品"""
    #     if not stripe_signature:
    #         logger.error("缺少 Stripe 签名头")
    #         raise HTTPException(400, detail="缺少签名")

    #     try:
    #         # 获取原始请求体
    #         payload = await request.body()

    #         # 验证webhook签名
            
    #         from payments.stripe_payment import StripePaymentService
    #         event = StripePaymentService.verify_webhook_signature(
    #             payload=payload,
    #             signature=stripe_signature
    #         )

    #         if not event:
    #             logger.error("Webhook签名验证失败")
    #             raise HTTPException(400, detail="签名验证失败")

    #         event_type = event.get("type")
    #         logger.info(f"收到Stripe webhook事件: {event_type}")

    #         # 处理 Checkout Session 完成事件（新增）
    #         if event_type == "checkout.session.completed":
    #             import json
    #             logger.debug("开始解析")
    #             data_in=json.loads(payload)
    #             with open("result.json", "w", encoding="utf-8") as f:
    #                 json.dump(data_in, f, ensure_ascii=False, indent=2)
    #                 logger.debug("保存成功")
    #             session = event["data"]["object"]
    #             session_id = session.get("id")
    #             payment_status = session.get("payment_status")
    #             metadata = session.get("metadata", {})
    #             order_id = metadata.get("order_id")
    #             customer_email = metadata.get("customer_email")

    #             logger.info(f"💳 Checkout 支付成功 - Session: {session_id}, Order: {order_id}, Payment Status: {payment_status}")

    #             # 只有支付状态为 paid 时才处理
    #             if payment_status != "paid":
    #                 logger.warning(f"⚠️ Checkout Session {session_id} 支付状态不是 paid: {payment_status}")
    #                 return {"status": "received", "message": "支付状态非 paid"}

    #             if not order_id:
    #                 logger.error(f"Checkout Session {session_id} 缺少 order_id")
    #                 return {"status": "error", "message": "缺少订单ID"}

    #             # 1. 更新订单支付状态
    #             from center_management.db.order import OrderConfig
    #             order_config = OrderConfig()

    #             try:
    #                 success = order_config.update_order_status(order_id, "已支付")
    #                 if not success:
    #                     logger.error(f"更新订单状态失败，订单ID: {order_id}")
    #                     return {"status": "error", "message": "更新订单状态失败"}
    #                 logger.info(f"✅ 订单支付状态更新成功，订单ID: {order_id}")

    #                 # 2. 更新产品生成状态为"生成中"
    #                 order_config.update_product_status(order_id, "processing")
    #                 logger.info(f"📝 订单产品状态更新为: processing")

    #             except Exception as e:
    #                 logger.error(f"更新订单状态失败: {e}")
    #                 return {"status": "error", "message": str(e)}

    #             # 3. 添加后台任务生成产品（异步执行，不阻塞webhook响应）
    #             background_tasks.add_task(
    #                 generate_product_background,
    #                 order_id=order_id,
    #                 customer_email=customer_email,
    #                 customer_phone=""  # Checkout 不需要手机号
    #             )

    #             logger.info(f"🚀 已启动后台任务生成产品，订单: {order_id}")

    #             # 4. 立即返回成功响应给Stripe（< 1秒）
    #             return {
    #                 "status": "success",
    #                 "message": "支付成功，产品生成中",
    #                 "order_id": order_id
    #             }

    #         # 处理 Payment Intent 支付成功事件（保留向后兼容）
    #         elif event_type == "payment_intent.succeeded":
    #             payment_intent = event["data"]["object"]
    #             payment_intent_id = payment_intent.get("id")
    #             metadata = payment_intent.get("metadata", {})
    #             order_id = metadata.get("order_id")
    #             customer_email = metadata.get("customer_email")
    #             customer_phone = metadata.get("customer_phone", "")

    #             logger.info(f"💳 支付成功 - Payment Intent: {payment_intent_id}, Order: {order_id}")

    #             if not order_id:
    #                 logger.error(f"Payment Intent {payment_intent_id} 缺少 order_id")
    #                 return {"status": "error", "message": "缺少订单ID"}

    #             # 更新订单状态为已支付
    #             from center_management.db.order import OrderConfig
    #             order_config = OrderConfig()

    #             try:
    #                 # 1. 更新订单支付状态
    #                 success = order_config.update_order_status(order_id, "已支付")
    #                 if not success:
    #                     logger.error(f"更新订单状态失败，订单ID: {order_id}")
    #                     return {"status": "error", "message": "更新订单状态失败"}
    #                 logger.info(f"✅ 订单支付状态更新成功，订单ID: {order_id}")

    #                 # 2. 更新产品生成状态为"生成中"
    #                 order_config.update_product_status(order_id, "processing")
    #                 logger.info(f"📝 订单产品状态更新为: processing")

    #             except Exception as e:
    #                 logger.error(f"更新订单状态失败: {e}")
    #                 return {"status": "error", "message": str(e)}

    #             # 3. 添加后台任务生成产品（异步执行，不阻塞webhook响应）
    #             background_tasks.add_task(
    #                 generate_product_background,
    #                 order_id=order_id,
    #                 customer_email=customer_email,
    #                 customer_phone=customer_phone
    #             )

    #             logger.info(f"🚀 已启动后台任务生成产品，订单: {order_id}")

    #             # 4. 立即返回成功响应给Stripe（< 1秒）
    #             return {
    #                 "status": "success",
    #                 "message": "支付成功，产品生成中，请等待3-10秒",
    #                 "order_id": order_id
    #             }

    #         # 处理其他事件类型
    #         elif event_type == "payment_intent.payment_failed":
    #             payment_intent = event["data"]["object"]
    #             payment_intent_id = payment_intent.get("id")
    #             metadata = payment_intent.get("metadata", {})
    #             order_id = metadata.get("order_id")

    #             logger.warning(f"支付失败 - Payment Intent: {payment_intent_id}, Order: {order_id}")

    #             # 可选：更新订单状态为失败
    #             if order_id:
    #                 from center_management.db.order import OrderConfig
    #                 order_config = OrderConfig()
    #                 order_config.update_order_status(order_id, "支付失败")

    #             return {"status": "received", "message": "支付失败事件已接收"}

    #         else:
    #             logger.info(f"收到未处理的事件类型: {event_type}")
    #             return {"status": "received", "message": f"事件 {event_type} 已接收"}

    #     except HTTPException:
    #         raise
    #     except Exception as e:
    #         logger.error(f"处理webhook失败: {e}")
    #         raise HTTPException(500, detail=f"处理webhook失败: {str(e)}")

    return router


# ============================================================================
# 公共函数：异步产品生成（适用于所有套餐）
# ============================================================================

async def generate_product_background(
    product_id: str,
    order_id: str,
    customer_email: str,
    customer_phone: str
):
    """
    后台任务：异步生成产品（适用于所有套餐）

    Args:
        product_id: 产品ID（如"free", "advanced", "unlimited"）
        order_id: 订单ID
        customer_email: 客户邮箱
        customer_phone: 客户手机号

    功能：
        1. 从JSON配置文件加载产品配置
        2. 连接网关生成订阅链接
        3. 插入产品数据到数据库
        4. 更新订单产品状态为completed
    """
    from center_management.db.order import OrderConfig
    from center_management.db.product import ProductConfig
    from center_management.backend_api_v2 import test_add_user_v2
    from center_management.node_manage import NodeProxy
    import json
    from pathlib import Path

    order_config = OrderConfig()
    product_config = ProductConfig()

    # 根据 product_id 加载配置
    try:
        data_path = Path(__file__).resolve().parent.parent / f'data/products/{product_id}.json'
        with open(data_path, 'r', encoding='utf-8') as f:
            _data = json.load(f)
            config = PlanConfig(**_data)
    except Exception as e:
        logger.error(f"❌ 加载产品配置失败 {product_id}.json: {e}")
        try:
            order_config.update_product_status(order_id, "failed")
        except Exception as update_error:
            logger.error(f"更新订单产品状态为failed失败: {update_error}")
        return

    try:
        logger.info(f"🚀 [后台任务] 开始为订单 {order_id} 生成 {config.plan_name} 产品...")

        # 获取网关配置
        hostname = config.get_gateway_ip()
        gateway_user = os.getenv('gateway_user', 'admin')
        key_file = 'id_ed25519'

        # 生成订阅链接
        logger.info(f"正在为用户 {customer_email} 生成订阅链接...")
        logger.info(f"连接服务器: {hostname}, 用户: {gateway_user}")
        proxy = NodeProxy(hostname, 22, gateway_user, key_file)

        subscription_url = test_add_user_v2(
            proxy,
            name_arg=customer_email,
            url=config.domain_url,
            alias=config.url_alias,
            verify_link=True,
            max_retries=1,
            up_mbps=config.up_mbps,
            down_mbps=config.down_mbps,
        )

        if not subscription_url:
            raise Exception("订阅链接生成失败")

        logger.info(f"✅ {config.plan_name} 订阅链接生成成功: {subscription_url}")

        # 插入产品数据
        product_db_id = product_config.insert_product(
            product_name=config.plan_name,
            subscription_url=subscription_url,
            email=customer_email,
            phone=customer_phone,
            duration_days=config.duration_days
        )

        logger.info(f"✅ 产品数据插入成功，产品ID: {product_db_id}")

        # 更新订单产品状态为"已完成"
        order_config.update_product_status(order_id, "completed")

        logger.info(f"🎉 [后台任务] 订单 {order_id} {config.plan_name} 产品生成完成！")

    except Exception as e:
        logger.error(f"❌ [后台任务] 订单 {order_id} 产品生成失败: {e}")
        # 更新订单产品状态为"生成失败"
        try:
            order_config.update_product_status(order_id, "failed")
        except Exception as update_error:
            logger.error(f"更新订单产品状态为failed失败: {update_error}")
