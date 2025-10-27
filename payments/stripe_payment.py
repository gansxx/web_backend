"""
Stripe 支付集成模块

文档：
- Stripe Python SDK: https://docs.stripe.com/api/python
- Payment Intents: https://docs.stripe.com/payments/payment-intents
- Webhooks: https://docs.stripe.com/webhooks

功能：
- 创建 Payment Intent（支付意图）
- 创建或获取 Customer（客户）
- 验证 Webhook 签名
- 处理支付状态更新

注意：
- amount 单位为分(int)
- 货币默认为 USD，可配置
- 所有 Stripe API 错误会被捕获并记录
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any, Dict, Optional

import stripe
from loguru import logger

# Stripe API 密钥配置
STRIPE_SECRET_KEY = os.getenv("STRIPE_SECRET_KEY", "")
STRIPE_WEBHOOK_SECRET = os.getenv("STRIPE_WEBHOOK_SECRET", "")

# 初始化 Stripe
if STRIPE_SECRET_KEY:
    stripe.api_key = STRIPE_SECRET_KEY
else:
    logger.warning("STRIPE_SECRET_KEY not set - Stripe payments will not work")


@dataclass
class StripePaymentRequest:
    """Stripe 支付请求数据"""
    amount: int  # 单位：分
    currency: str  # ISO 货币代码，如 'usd', 'cny'
    description: str
    customer_email: str
    customer_phone: Optional[str] = None
    metadata: Optional[Dict[str, str]] = None  # 自定义元数据


@dataclass
class StripeCustomerRequest:
    """Stripe 客户创建请求"""
    email: str
    name: Optional[str] = None
    phone: Optional[str] = None
    metadata: Optional[Dict[str, str]] = None


class StripePaymentService:
    """Stripe 支付服务"""

    @staticmethod
    def create_or_get_customer(request: StripeCustomerRequest) -> Optional[stripe.Customer]:
        """
        创建或获取 Stripe 客户

        Args:
            request: 客户信息请求

        Returns:
            Stripe Customer 对象，失败返回 None
        """
        try:
            # 先尝试查找现有客户
            customers = stripe.Customer.list(email=request.email, limit=1)
            if customers.data:
                logger.info(f"Found existing Stripe customer: {customers.data[0].id}")
                return customers.data[0]

            # 创建新客户
            customer_data = {"email": request.email}
            if request.name:
                customer_data["name"] = request.name
            if request.phone:
                customer_data["phone"] = request.phone
            if request.metadata:
                customer_data["metadata"] = request.metadata

            customer = stripe.Customer.create(**customer_data)
            logger.info(f"Created new Stripe customer: {customer.id}")
            return customer

        except stripe.StripeError as e:
            logger.error(f"Failed to create/get Stripe customer: {e}")
            return None

    @staticmethod
    def create_payment_intent(
        request: StripePaymentRequest,
        customer_id: Optional[str] = None,
        return_url: Optional[str] = None
    ) -> Optional[stripe.PaymentIntent]:
        """
        创建 Stripe Payment Intent

        Args:
            request: 支付请求数据
            customer_id: 可选的 Stripe 客户ID
            return_url: 支付完成后返回URL（用于支持支付宝、微信等重定向支付方式）

        Returns:
            Payment Intent 对象，失败返回 None
        """
        try:
            # 构建 Payment Intent 参数
            intent_data = {
                "amount": request.amount,
                "currency": request.currency.lower(),
                "description": request.description,
                "receipt_email": request.customer_email,
                "automatic_payment_methods": {
                    "enabled": True,
                    # 当前默认仅支持非重定向支付方式（信用卡/借记卡）
                    # 未来如需支持支付宝、微信等重定向支付，传入 return_url 即可自动启用
                    "allow_redirects": "always" if return_url else "never"
                },
            }

            # 添加 return_url（如果提供）
            if return_url:
                intent_data["return_url"] = return_url

            # 添加客户ID
            if customer_id:
                intent_data["customer"] = customer_id

            # 添加元数据
            if request.metadata:
                intent_data["metadata"] = request.metadata
            else:
                intent_data["metadata"] = {}

            # 添加客户联系信息到元数据
            intent_data["metadata"]["customer_email"] = request.customer_email
            if request.customer_phone:
                intent_data["metadata"]["customer_phone"] = request.customer_phone

            # 创建 Payment Intent
            payment_intent = stripe.PaymentIntent.create(**intent_data)
            logger.info(
                f"Created Stripe Payment Intent: {payment_intent.id} "
                f"for amount {request.amount} {request.currency}"
            )
            return payment_intent

        except stripe.StripeError as e:
            logger.error(f"Failed to create Stripe Payment Intent: {e}")
            return None

    @staticmethod
    def retrieve_payment_intent(payment_intent_id: str) -> Optional[stripe.PaymentIntent]:
        """
        获取 Payment Intent 详情

        Args:
            payment_intent_id: Payment Intent ID

        Returns:
            Payment Intent 对象，失败返回 None
        """
        try:
            payment_intent = stripe.PaymentIntent.retrieve(payment_intent_id)
            return payment_intent
        except stripe.StripeError as e:
            logger.error(f"Failed to retrieve Payment Intent {payment_intent_id}: {e}")
            return None

    @staticmethod
    def cancel_payment_intent(payment_intent_id: str) -> bool:
        """
        取消 Payment Intent

        Args:
            payment_intent_id: Payment Intent ID

        Returns:
            成功返回 True，失败返回 False
        """
        try:
            stripe.PaymentIntent.cancel(payment_intent_id)
            logger.info(f"Canceled Stripe Payment Intent: {payment_intent_id}")
            return True
        except stripe.StripeError as e:
            logger.error(f"Failed to cancel Payment Intent {payment_intent_id}: {e}")
            return False

    @staticmethod
    def verify_webhook_signature(
        payload: bytes,
        signature: str,
        secret: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """
        验证 Webhook 签名并解析事件

        Args:
            payload: 原始请求体（字节）
            signature: Stripe-Signature 头的值
            secret: Webhook 密钥，默认使用环境变量

        Returns:
            解析后的事件字典，失败返回 None
        """
        if secret is None:
            secret = STRIPE_WEBHOOK_SECRET

        if not secret:
            logger.error("STRIPE_WEBHOOK_SECRET not configured")
            return None

        try:
            event = stripe.Webhook.construct_event(payload, signature, secret)
            logger.info(f"Verified Stripe webhook event: {event['type']}")
            return event
        except ValueError as e:
            logger.error(f"Invalid webhook payload: {e}")
            return None
        except stripe.SignatureVerificationError as e:
            logger.error(f"Invalid webhook signature: {e}")
            return None

    @staticmethod
    def format_amount_for_display(amount: int, currency: str) -> str:
        """
        格式化金额用于显示

        Args:
            amount: 金额（分）
            currency: 货币代码

        Returns:
            格式化后的金额字符串
        """
        major_units = amount / 100
        currency_upper = currency.upper()
        return f"{major_units:.2f} {currency_upper}"


def create_payment_session(
    product_name: str,
    amount: int,
    currency: str,
    customer_email: str,
    customer_phone: Optional[str] = None,
    order_id: Optional[str] = None
) -> Dict[str, Any]:
    """
    创建完整的 Stripe 支付会话

    Args:
        product_name: 产品名称
        amount: 金额（分）
        currency: 货币代码
        customer_email: 客户邮箱
        customer_phone: 客户手机号（可选）
        order_id: 订单ID（可选，用于关联）

    Returns:
        包含 payment_intent 和 customer 信息的字典
    """
    service = StripePaymentService()

    # 创建或获取客户
    customer_request = StripeCustomerRequest(
        email=customer_email,
        phone=customer_phone,
        metadata={"source": "web_backend"}
    )
    customer = service.create_or_get_customer(customer_request)

    # 构建元数据
    metadata = {"product_name": product_name}
    if order_id:
        metadata["order_id"] = order_id

    # 创建支付意图
    payment_request = StripePaymentRequest(
        amount=amount,
        currency=currency,
        description=product_name,
        customer_email=customer_email,
        customer_phone=customer_phone,
        metadata=metadata
    )

    customer_id = customer.id if customer else None
    payment_intent = service.create_payment_intent(payment_request, customer_id)

    if not payment_intent:
        return {
            "success": False,
            "error": "Failed to create payment intent"
        }

    return {
        "success": True,
        "payment_intent_id": payment_intent.id,
        "client_secret": payment_intent.client_secret,
        "customer_id": customer_id,
        "amount": payment_intent.amount,
        "currency": payment_intent.currency,
        "status": payment_intent.status
    }


# 导出主要接口
__all__ = [
    "StripePaymentService",
    "StripePaymentRequest",
    "StripeCustomerRequest",
    "create_payment_session",
]
