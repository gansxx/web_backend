"""
Subscription Plan Routes - Factory Pattern Implementation

基于配置创建订阅套餐路由，支持多种订阅套餐的扩展。
购买流程与 base_plan.py 统一：先插入订单 → 创建支付会话 → 返回支付链接

Endpoints:
- POST /subscription/{plan_id}/purchase - 创建订阅 Checkout
- GET /subscription/{plan_id}/status - 获取用户订阅状态
- POST /subscription/{plan_id}/cancel - 取消订阅
- POST /subscription/{plan_id}/portal - 获取客户门户 URL
- POST /subscription/{plan_id}/reactivate - 重新激活订阅
- GET /subscription/{plan_id}/info - 获取订阅套餐信息（公开）
"""

from fastapi import APIRouter, HTTPException, Response, Request, Cookie
from pydantic import BaseModel
from loguru import logger
from typing import Optional, Dict, Any
import os
from datetime import datetime

from routes.plans.base_plan import SubscriptionPlanConfig, generate_trade_number


# Request/Response Models
class SubscriptionPurchaseRequest(BaseModel):
    """订阅购买请求"""
    phone: str = ""


class SubscriptionPurchaseResponse(BaseModel):
    """订阅购买响应"""
    success: bool
    message: str
    order_id: Optional[str] = None
    checkout_url: Optional[str] = None
    checkout_session_id: Optional[str] = None
    amount: int = 0
    currency: str = ""
    plan_name: str = ""


class SubscriptionCancelRequest(BaseModel):
    """订阅取消请求"""
    at_period_end: bool = True  # 默认：在当前周期结束后取消


class SubscriptionStatusResponse(BaseModel):
    """订阅状态响应"""
    has_subscription: bool
    subscription_status: Optional[str] = None
    current_period_end: Optional[str] = None
    cancel_at_period_end: bool = False
    trial_end: Optional[str] = None
    is_trial: bool = False
    stripe_subscription_id: Optional[str] = None
    stripe_customer_id: Optional[str] = None


def _get_user_from_token(request: Request, response: Response, token: str, refresh_token: Optional[str] = None):
    """从 token 获取用户信息的辅助函数"""
    supabase = getattr(request.app.state, "supabase", None)
    do_refresh = getattr(request.app.state, "refresh_session_and_set_cookies", None)

    if not supabase:
        raise HTTPException(500, detail="Supabase 未初始化")

    try:
        _res = supabase.auth.get_user(token)
    except Exception as e:
        msg = str(e).lower()
        if refresh_token and ("expired" in msg or "invalid" in msg) and callable(do_refresh):
            logger.info("access_token 已过期，尝试刷新")
            new_at = do_refresh(response, refresh_token)
            if not new_at:
                raise HTTPException(401, detail="会话已过期，请重新登录")
            _res = supabase.auth.get_user(new_at)
        else:
            raise HTTPException(401, detail="无效的 token")

    user = getattr(_res, "user", None)
    if not user or not getattr(user, "email", None):
        raise HTTPException(401, detail="未登录或用户无邮箱信息")

    return user


def create_subscription_plan_router(config: SubscriptionPlanConfig) -> APIRouter:
    """
    基于配置创建订阅套餐路由

    Args:
        config: 订阅套餐配置对象

    Returns:
        APIRouter: 包含所有订阅端点的路由器
    """
    router = APIRouter(tags=[f"subscription_{config.plan_id}"])

    # 从配置获取价格和货币
    PLAN_PRICE = config.get_price()
    PLAN_CURRENCY = config.get_currency()
    FRONTEND_URL = os.getenv("FRONTEND_URL", "")

    logger.info(f"=== 创建订阅套餐路由: {config.plan_name} ===")
    logger.info(f"  套餐ID: {config.plan_id}")
    logger.info(f"  价格: {PLAN_PRICE}分")
    logger.info(f"  货币: {PLAN_CURRENCY}")
    logger.info(f"  试用天数: {config.trial_days}")
    logger.info(f"  计费周期: {config.billing_period}")

    @router.post(f"/subscription/{config.plan_id}/purchase")
    async def purchase_subscription(
        request: Request,
        response: Response,
        purchase_data: SubscriptionPurchaseRequest,
        token: str | None = None,
        access_token: str | None = Cookie(default=None),
        refresh_token: str | None = Cookie(default=None),
    ) -> SubscriptionPurchaseResponse:
        """
        创建订阅 Checkout 会话

        流程：
        1. 验证用户登录
        2. 检查是否已有活跃订阅
        3. 插入订单记录（order 表）
        4. 创建 Stripe Subscription Checkout Session
        5. 更新订单 checkout_session_id
        6. 返回支付链接
        """
        token_to_use = token or access_token
        if not token_to_use:
            raise HTTPException(401, detail="未登录")

        try:
            user = _get_user_from_token(request, response, token_to_use, refresh_token)
            email = user.email

            logger.info(f"用户 {email} 开始购买订阅: {config.plan_name}")

            # 1. 检查是否已有活跃订阅
            from center_management.db.subscription import get_subscription_config
            sub_config = get_subscription_config()

            existing_sub = sub_config.get_user_active_subscription(email)
            if existing_sub:
                status = existing_sub.get("status", "")
                if status in ["trialing", "active"]:
                    logger.info(f"用户 {email} 已有活跃订阅: {status}")

                    # 返回结构化错误响应而不是抛出异常
                    status_text = {
                        "trialing": "试用中",
                        "active": "已激活"
                    }.get(status, status)

                    # 构建详细的错误信息
                    error_msg = f"您已有活跃订阅（状态: {status_text}）"
                    if existing_sub.get("current_period_end"):
                        from datetime import datetime
                        end_date = existing_sub.get("current_period_end")
                        if isinstance(end_date, str):
                            try:
                                end_dt = datetime.fromisoformat(end_date.replace('Z', '+00:00'))
                                error_msg += f"，有效期至 {end_dt.strftime('%Y-%m-%d')}"
                            except:
                                pass
                        elif isinstance(end_date, datetime):
                            error_msg += f"，有效期至 {end_date.strftime('%Y-%m-%d')}"

                    response.status_code = 400
                    return SubscriptionPurchaseResponse(
                        success=False,
                        message=error_msg,
                        order_id=None,
                        checkout_url=None,
                        plan_name=config.plan_name
                    )

            # 2. 生成交易号并插入订单
            trade_num = generate_trade_number()

            from center_management.db.order import OrderConfig
            order_config = OrderConfig()

            try:
                order_id = order_config.insert_order(
                    product_name=config.plan_name,
                    trade_num=trade_num,
                    amount=PLAN_PRICE,
                    email=email,
                    phone=purchase_data.phone,
                    payment_provider="stripe",
                    subscription_type="subscription"
                )
                logger.info(f"✅ 订单插入成功，订单ID: {order_id}, 类型: subscription")
            except Exception as e:
                logger.error(f"插入订单失败: {e}")
                response.status_code = 500
                return SubscriptionPurchaseResponse(
                    success=False,
                    message="创建订单失败，请稍后重试",
                    plan_name=config.plan_name
                )

            # 3. 创建 Stripe Subscription Checkout Session (动态创建产品)
            from payments.stripe_subscription import StripeSubscriptionService

            success_url = f"{FRONTEND_URL}/dashboard?subscription=success&session_id={{CHECKOUT_SESSION_ID}}"
            cancel_url = f"{FRONTEND_URL}/dashboard?subscription=canceled"

            result = StripeSubscriptionService.create_subscription_checkout_session(
                customer_email=email,
                success_url=success_url,
                cancel_url=cancel_url,
                amount_cents=PLAN_PRICE,
                currency=PLAN_CURRENCY,
                product_name=config.plan_name,
                interval=config.billing_period,
                trial_days=config.trial_days,
                plan_id=config.plan_id,
                metadata={
                    "customer_email": email,
                    "plan_id": config.plan_id,
                    "order_id": order_id,
                    "trial_days": str(config.trial_days)
                }
            )

            if not result.get("success"):
                error_msg = result.get("error", "创建 Checkout 会话失败")
                logger.error(f"创建订阅 Checkout 失败: {error_msg}")
                response.status_code = 500
                return SubscriptionPurchaseResponse(
                    success=False,
                    message=f"创建订阅失败: {error_msg}",
                    plan_name=config.plan_name
                )

            checkout_session_id = result.get("checkout_session_id")
            logger.info(f"✅ 订阅 Checkout Session 创建成功: {checkout_session_id}")

            # 4. 更新订单的 checkout_session_id
            if checkout_session_id:
                try:
                    order_config.update_checkout_session_id(
                        order_id=order_id,
                        checkout_session_id=checkout_session_id
                    )
                    logger.info(f"✅ 订单 Checkout Session ID 已记录: {checkout_session_id}")
                except Exception as update_error:
                    logger.error(f"⚠️ 更新订单 Checkout Session ID 失败: {update_error}")
                    # 不抛出异常，因为支付已创建成功

            return SubscriptionPurchaseResponse(
                success=True,
                message=f"订阅 Checkout 创建成功，包含 {config.trial_days} 天免费试用",
                order_id=order_id,
                checkout_url=result.get("checkout_url"),
                checkout_session_id=checkout_session_id,
                amount=PLAN_PRICE,
                currency=PLAN_CURRENCY,
                plan_name=config.plan_name
            )

        except HTTPException:
            # 保留未改造的 HTTPException（如未登录等）
            raise
        except Exception as e:
            logger.error(f"购买订阅失败: {e}", exc_info=True)
            response.status_code = 500
            return SubscriptionPurchaseResponse(
                success=False,
                message="购买订阅失败，请稍后重试",
                plan_name=config.plan_name
            )

    @router.get(f"/subscription/{config.plan_id}/status")
    async def get_subscription_status(
        request: Request,
        response: Response,
        token: str | None = None,
        access_token: str | None = Cookie(default=None),
        refresh_token: str | None = Cookie(default=None),
    ) -> SubscriptionStatusResponse:
        """获取用户当前订阅状态"""
        token_to_use = token or access_token
        if not token_to_use:
            raise HTTPException(401, detail="未登录")

        try:
            user = _get_user_from_token(request, response, token_to_use, refresh_token)
            email = user.email

            logger.info(f"检查订阅状态: {email}")

            from center_management.db.subscription import get_subscription_config
            sub_config = get_subscription_config()

            subscription = sub_config.get_user_active_subscription(email)

            if not subscription:
                return SubscriptionStatusResponse(
                    has_subscription=False,
                    subscription_status=None,
                    is_trial=False
                )

            status = subscription.get("status", "")
            trial_end = subscription.get("trial_end")
            current_period_end = subscription.get("current_period_end")

            # 判断是否在试用期
            is_trial = status == "trialing"
            if trial_end and isinstance(trial_end, str):
                try:
                    trial_end_dt = datetime.fromisoformat(trial_end.replace("Z", "+00:00"))
                    is_trial = datetime.now(trial_end_dt.tzinfo) < trial_end_dt
                except Exception:
                    pass

            return SubscriptionStatusResponse(
                has_subscription=True,
                subscription_status=status,
                current_period_end=current_period_end if isinstance(current_period_end, str) else str(current_period_end) if current_period_end else None,
                cancel_at_period_end=subscription.get("cancel_at_period_end", False),
                trial_end=trial_end if isinstance(trial_end, str) else str(trial_end) if trial_end else None,
                is_trial=is_trial,
                stripe_subscription_id=subscription.get("stripe_subscription_id"),
                stripe_customer_id=subscription.get("stripe_customer_id")
            )

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"获取订阅状态失败: {e}")
            raise HTTPException(500, detail="获取订阅状态失败")

    @router.post(f"/subscription/{config.plan_id}/cancel")
    async def cancel_subscription(
        request: Request,
        response: Response,
        cancel_data: SubscriptionCancelRequest,
        token: str | None = None,
        access_token: str | None = Cookie(default=None),
        refresh_token: str | None = Cookie(default=None),
    ):
        """
        取消订阅

        默认：在当前周期结束后取消（用户可继续使用至周期结束）
        """
        token_to_use = token or access_token
        if not token_to_use:
            raise HTTPException(401, detail="未登录")

        try:
            user = _get_user_from_token(request, response, token_to_use, refresh_token)
            email = user.email

            logger.info(f"用户 {email} 取消订阅 (at_period_end={cancel_data.at_period_end})")

            from center_management.db.subscription import get_subscription_config
            sub_config = get_subscription_config()

            subscription = sub_config.get_user_active_subscription(email)

            if not subscription:
                raise HTTPException(404, detail="未找到活跃订阅")

            stripe_subscription_id = subscription.get("stripe_subscription_id")
            if not stripe_subscription_id:
                raise HTTPException(500, detail="订阅 ID 未找到")

            from payments.stripe_subscription import StripeSubscriptionService

            result = StripeSubscriptionService.cancel_subscription(
                subscription_id=stripe_subscription_id,
                at_period_end=cancel_data.at_period_end
            )

            if not result.get("success"):
                error_msg = result.get("error", "取消订阅失败")
                logger.error(f"取消订阅失败: {error_msg}")
                raise HTTPException(500, detail=f"取消失败: {error_msg}")

            # 更新本地数据库
            sub_config.mark_subscription_canceled(
                stripe_subscription_id=stripe_subscription_id,
                cancel_at_period_end=cancel_data.at_period_end,
                canceled_at=datetime.utcnow()
            )

            current_period_end = result.get("current_period_end")
            end_date_str = ""
            if current_period_end:
                end_date = datetime.fromtimestamp(current_period_end)
                end_date_str = end_date.strftime("%Y-%m-%d")

            logger.info(f"✅ 订阅 {stripe_subscription_id} 已取消")

            return {
                "success": True,
                "message": f"订阅已取消。服务将持续到 {end_date_str}" if cancel_data.at_period_end else "订阅已立即取消",
                "cancel_at_period_end": cancel_data.at_period_end,
                "current_period_end": end_date_str
            }

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"取消订阅失败: {e}")
            raise HTTPException(500, detail="取消订阅失败")

    @router.post(f"/subscription/{config.plan_id}/reactivate")
    async def reactivate_subscription(
        request: Request,
        response: Response,
        token: str | None = None,
        access_token: str | None = Cookie(default=None),
        refresh_token: str | None = Cookie(default=None),
    ):
        """
        重新激活已标记取消的订阅

        仅当 cancel_at_period_end 为 True 且周期未结束时有效
        """
        token_to_use = token or access_token
        if not token_to_use:
            raise HTTPException(401, detail="未登录")

        try:
            user = _get_user_from_token(request, response, token_to_use, refresh_token)
            email = user.email

            logger.info(f"用户 {email} 重新激活订阅")

            from center_management.db.subscription import get_subscription_config
            sub_config = get_subscription_config()

            subscription = sub_config.get_user_active_subscription(email)

            if not subscription:
                raise HTTPException(404, detail="未找到可重新激活的订阅")

            if not subscription.get("cancel_at_period_end"):
                raise HTTPException(400, detail="订阅未计划取消")

            stripe_subscription_id = subscription.get("stripe_subscription_id")

            from payments.stripe_subscription import StripeSubscriptionService

            result = StripeSubscriptionService.reactivate_subscription(stripe_subscription_id)

            if not result.get("success"):
                error_msg = result.get("error", "重新激活失败")
                raise HTTPException(500, detail=f"重新激活失败: {error_msg}")

            # 更新本地数据库
            sub_config.update_subscription_status(
                stripe_subscription_id=stripe_subscription_id,
                status=result.get("status", "active"),
                cancel_at_period_end=False
            )

            logger.info(f"✅ 订阅 {stripe_subscription_id} 已重新激活")

            return {
                "success": True,
                "message": "订阅已重新激活"
            }

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"重新激活订阅失败: {e}")
            raise HTTPException(500, detail="重新激活订阅失败")

    @router.post(f"/subscription/{config.plan_id}/portal")
    async def get_customer_portal(
        request: Request,
        response: Response,
        token: str | None = None,
        access_token: str | None = Cookie(default=None),
        refresh_token: str | None = Cookie(default=None),
    ):
        """
        获取 Stripe 客户门户 URL

        用户可以：
        - 查看订阅详情
        - 更新支付方式
        - 查看发票历史
        - 取消订阅
        """
        token_to_use = token or access_token
        if not token_to_use:
            raise HTTPException(401, detail="未登录")

        try:
            user = _get_user_from_token(request, response, token_to_use, refresh_token)
            email = user.email

            logger.info(f"用户 {email} 请求客户门户")

            from center_management.db.subscription import get_subscription_config
            sub_config = get_subscription_config()

            subscription = sub_config.get_user_active_subscription(email)

            if not subscription:
                raise HTTPException(404, detail="未找到订阅")

            stripe_customer_id = subscription.get("stripe_customer_id")
            if not stripe_customer_id:
                raise HTTPException(500, detail="客户 ID 未找到")

            from payments.stripe_subscription import StripeSubscriptionService

            return_url = f"{FRONTEND_URL}/dashboard"
            result = StripeSubscriptionService.create_customer_portal_session(
                customer_id=stripe_customer_id,
                return_url=return_url
            )

            if not result.get("success"):
                error_msg = result.get("error", "创建门户会话失败")
                raise HTTPException(500, detail=f"获取门户失败: {error_msg}")

            logger.info(f"✅ 客户门户会话已创建: {email}")

            return {
                "success": True,
                "portal_url": result.get("portal_url")
            }

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"获取客户门户失败: {e}")
            raise HTTPException(500, detail="获取客户门户失败")

    @router.get(f"/subscription/{config.plan_id}/info")
    async def get_subscription_info():
        """获取订阅套餐信息（公开端点）"""
        return {
            "plan_name": config.plan_name,
            "plan_id": config.plan_id,
            "price": PLAN_PRICE,
            "currency": PLAN_CURRENCY,
            "trial_days": config.trial_days,
            "billing_period": config.billing_period,
            "features": [
                "完整 VPN 访问",
                f"{config.trial_days} 天免费试用",
                "随时取消",
                "自动续费"
            ]
        }

    return router


def load_subscription_config(plan_id: str) -> SubscriptionPlanConfig:
    """
    从 JSON 文件加载订阅套餐配置

    Args:
        plan_id: 套餐ID（对应 data/products/subscription/{plan_id}.json）

    Returns:
        SubscriptionPlanConfig 实例
    """
    import json
    from pathlib import Path

    config_path = Path(__file__).resolve().parent.parent.parent / f'data/products/subscription/{plan_id}.json'

    if not config_path.exists():
        raise FileNotFoundError(f"订阅套餐配置文件不存在: {config_path}")

    with open(config_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    return SubscriptionPlanConfig(**data)
