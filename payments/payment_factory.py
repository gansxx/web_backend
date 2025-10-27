"""
支付工厂模块

统一管理多种支付方式的路由和处理逻辑。
当前支持：
- h5zhifu：中国支付网关（支付宝/微信）
- stripe：国际支付网关（信用卡/借记卡）
"""

from __future__ import annotations

from enum import Enum
from typing import Any, Dict, Optional

from loguru import logger

from payments.h5zhifu import H5PayRequest, create_h5_order
from payments.stripe_payment import create_payment_session


class PaymentProvider(str, Enum):
    """支付提供商枚举"""
    H5ZHIFU = "h5zhifu"
    STRIPE = "stripe"


class PaymentFactory:
    """支付工厂类"""

    @staticmethod
    def create_payment(
        provider: PaymentProvider,
        product_name: str,
        amount: int,
        email: str,
        phone: str,
        **kwargs
    ) -> Dict[str, Any]:
        """
        创建支付订单（统一接口）

        Args:
            provider: 支付提供商
            product_name: 产品名称
            amount: 金额（分）
            email: 客户邮箱
            phone: 客户手机号
            **kwargs: 支付提供商特定参数

        Returns:
            支付创建结果字典
        """
        if provider == PaymentProvider.H5ZHIFU:
            return PaymentFactory._create_h5zhifu_payment(
                product_name=product_name,
                amount=amount,
                email=email,
                phone=phone,
                **kwargs
            )
        elif provider == PaymentProvider.STRIPE:
            return PaymentFactory._create_stripe_payment(
                product_name=product_name,
                amount=amount,
                email=email,
                phone=phone,
                **kwargs
            )
        else:
            logger.error(f"Unsupported payment provider: {provider}")
            return {
                "success": False,
                "error": f"Unsupported payment provider: {provider}"
            }

    @staticmethod
    def _create_h5zhifu_payment(
        product_name: str,
        amount: int,
        email: str,
        phone: str,
        **kwargs
    ) -> Dict[str, Any]:
        """
        创建 h5zhifu 支付订单

        Required kwargs:
            - app_id: int
            - secret_key: str
            - out_trade_no: str
            - pay_type: str ('alipay' | 'wechat')
            - notify_url: str
        Optional kwargs:
            - attach: str
            - dry_run: bool (default: False)
        """
        try:
            # 提取必需参数
            app_id = kwargs.get("app_id")
            secret_key = kwargs.get("secret_key")
            out_trade_no = kwargs.get("out_trade_no")
            pay_type = kwargs.get("pay_type", "alipay")
            notify_url = kwargs.get("notify_url")
            attach = kwargs.get("attach")
            dry_run = kwargs.get("dry_run", False)

            # 验证必需参数
            if not all([app_id, secret_key, out_trade_no, notify_url]):
                return {
                    "success": False,
                    "error": "Missing required parameters for h5zhifu payment",
                    "provider": "h5zhifu"
                }

            # 创建 H5 支付请求
            request = H5PayRequest(
                app_id=int(app_id),
                out_trade_no=out_trade_no,
                description=product_name,
                pay_type=pay_type,
                amount=amount,
                notify_url=notify_url,
                attach=attach
            )

            # 调用 h5zhifu API
            result = create_h5_order(request, secret_key, dry_run=dry_run)

            if dry_run:
                return {
                    "success": True,
                    "provider": "h5zhifu",
                    "dry_run": True,
                    "request_url": result["request_url"],
                    "payload": result["payload"]
                }

            # 检查响应状态
            if result.get("status_code") == 200 and result.get("response"):
                response_data = result["response"]
                return {
                    "success": True,
                    "provider": "h5zhifu",
                    "out_trade_no": out_trade_no,
                    "payment_url": response_data.get("pay_url"),
                    "response": response_data
                }
            else:
                return {
                    "success": False,
                    "provider": "h5zhifu",
                    "error": "Failed to create h5zhifu payment",
                    "status_code": result.get("status_code"),
                    "raw_response": result.get("raw_text")
                }

        except Exception as e:
            logger.error(f"Error creating h5zhifu payment: {e}")
            return {
                "success": False,
                "provider": "h5zhifu",
                "error": str(e)
            }

    @staticmethod
    def _create_stripe_payment(
        product_name: str,
        amount: int,
        email: str,
        phone: str,
        **kwargs
    ) -> Dict[str, Any]:
        """
        创建 Stripe 支付订单

        Optional kwargs:
            - currency: str (default: 'usd')
            - order_id: str (用于关联数据库订单)
        """
        try:
            currency = kwargs.get("currency", "usd")
            order_id = kwargs.get("order_id")

            # 调用 Stripe 支付会话创建
            result = create_payment_session(
                product_name=product_name,
                amount=amount,
                currency=currency,
                customer_email=email,
                customer_phone=phone,
                order_id=order_id
            )

            if result.get("success"):
                return {
                    "success": True,
                    "provider": "stripe",
                    "payment_intent_id": result["payment_intent_id"],
                    "client_secret": result["client_secret"],
                    "customer_id": result.get("customer_id"),
                    "amount": result["amount"],
                    "currency": result["currency"],
                    "status": result["status"]
                }
            else:
                return {
                    "success": False,
                    "provider": "stripe",
                    "error": result.get("error", "Unknown error")
                }

        except Exception as e:
            logger.error(f"Error creating Stripe payment: {e}")
            return {
                "success": False,
                "provider": "stripe",
                "error": str(e)
            }

    @staticmethod
    def validate_provider(provider: str) -> bool:
        """验证支付提供商是否支持"""
        try:
            PaymentProvider(provider)
            return True
        except ValueError:
            return False

    @staticmethod
    def get_supported_providers() -> list[str]:
        """获取支持的支付提供商列表"""
        return [provider.value for provider in PaymentProvider]


# 便捷函数
def create_payment_by_provider(
    provider_name: str,
    product_name: str,
    amount: int,
    email: str,
    phone: str,
    **kwargs
) -> Dict[str, Any]:
    """
    通过提供商名称创建支付

    Args:
        provider_name: 支付提供商名称字符串
        product_name: 产品名称
        amount: 金额（分）
        email: 客户邮箱
        phone: 客户手机号
        **kwargs: 提供商特定参数

    Returns:
        支付创建结果
    """
    if not PaymentFactory.validate_provider(provider_name):
        return {
            "success": False,
            "error": f"Invalid payment provider: {provider_name}",
            "supported_providers": PaymentFactory.get_supported_providers()
        }

    provider = PaymentProvider(provider_name)
    return PaymentFactory.create_payment(
        provider=provider,
        product_name=product_name,
        amount=amount,
        email=email,
        phone=phone,
        **kwargs
    )


# 导出接口
__all__ = [
    "PaymentFactory",
    "PaymentProvider",
    "create_payment_by_provider",
]
