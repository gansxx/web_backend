"""
Stripe 支付集成测试脚本

测试内容：
1. 创建 Stripe Payment Intent
2. 查询订单支付状态
3. 模拟 Webhook 回调处理

使用方法：
    uv run python test_stripe_payment.py
"""

import os
import sys
import time
from dotenv import load_dotenv
from loguru import logger
import requests

# 加载环境变量
load_dotenv()

# API 基础 URL
API_BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8001")


def test_create_payment_intent():
    """测试创建支付意图"""
    logger.info("=== 测试 1: 创建 Stripe Payment Intent ===")

    url = f"{API_BASE_URL}/stripe/create-payment-intent"

    # 测试数据
    payload = {
        "product_name": "测试产品 - VPN 订阅",
        "trade_num": 1,
        "amount": 999,  # 9.99 USD (单位：分)
        "currency": "usd",
        "email": "test@example.com",
        "phone": "+1234567890"
    }

    try:
        logger.info(f"发送请求到: {url}")
        logger.info(f"请求数据: {payload}")

        response = requests.post(url, json=payload)

        logger.info(f"响应状态码: {response.status_code}")
        logger.info(f"响应数据: {response.json()}")

        if response.status_code == 200:
            data = response.json()
            if data.get("success"):
                logger.success("✅ 支付意图创建成功!")
                logger.info(f"  订单ID: {data.get('order_id')}")
                logger.info(f"  Payment Intent ID: {data.get('payment_intent_id')}")
                logger.info(f"  Client Secret: {data.get('client_secret')[:30]}...")
                logger.info(f"  金额: {data.get('amount')} {data.get('currency').upper()}")
                logger.info(f"  状态: {data.get('status')}")
                return data
            else:
                logger.error(f"❌ 创建失败: {data.get('error')}")
                return None
        else:
            logger.error(f"❌ HTTP 错误: {response.status_code}")
            logger.error(f"响应: {response.text}")
            return None

    except Exception as e:
        logger.error(f"❌ 请求异常: {e}")
        return None


def test_get_payment_status(order_id: str):
    """测试查询支付状态"""
    logger.info(f"\n=== 测试 2: 查询支付状态 (订单ID: {order_id}) ===")

    url = f"{API_BASE_URL}/stripe/payment-status/{order_id}"

    try:
        logger.info(f"发送请求到: {url}")

        response = requests.get(url)

        logger.info(f"响应状态码: {response.status_code}")
        logger.info(f"响应数据: {response.json()}")

        if response.status_code == 200:
            data = response.json()
            if data.get("success"):
                logger.success("✅ 状态查询成功!")
                logger.info(f"  订单ID: {data.get('order_id')}")
                logger.info(f"  支付提供商: {data.get('payment_provider')}")
                logger.info(f"  Payment Intent ID: {data.get('stripe_payment_intent_id')}")
                logger.info(f"  Stripe 支付状态: {data.get('stripe_payment_status')}")
                logger.info(f"  订单状态: {data.get('order_status')}")
                logger.info(f"  产品名称: {data.get('product_name')}")
                logger.info(f"  金额: {data.get('amount')} 分")
                return data
            else:
                logger.error(f"❌ 查询失败: {data.get('error')}")
                return None
        else:
            logger.error(f"❌ HTTP 错误: {response.status_code}")
            return None

    except Exception as e:
        logger.error(f"❌ 请求异常: {e}")
        return None


def test_webhook_simulation():
    """Webhook 模拟测试说明"""
    logger.info("\n=== 测试 3: Webhook 回调处理 ===")
    logger.warning("⚠️  Webhook 测试需要使用 Stripe CLI 或实际支付来触发")
    logger.info("Stripe CLI 测试方法：")
    logger.info("  1. 安装 Stripe CLI: https://stripe.com/docs/stripe-cli")
    logger.info("  2. 登录: stripe login")
    logger.info("  3. 转发 webhook 到本地:")
    logger.info(f"     stripe listen --forward-to {API_BASE_URL}/stripe/webhook")
    logger.info("  4. 触发测试事件:")
    logger.info("     stripe trigger payment_intent.succeeded")
    logger.info("\n或者使用真实支付流程测试 Webhook")


def test_payment_factory():
    """测试支付工厂模式"""
    logger.info("\n=== 测试 4: 支付工厂模式 ===")

    try:
        from payments.payment_factory import PaymentFactory, PaymentProvider

        # 测试获取支持的支付提供商
        providers = PaymentFactory.get_supported_providers()
        logger.info(f"支持的支付提供商: {providers}")

        # 测试验证提供商
        is_valid_stripe = PaymentFactory.validate_provider("stripe")
        is_valid_h5zhifu = PaymentFactory.validate_provider("h5zhifu")
        is_valid_invalid = PaymentFactory.validate_provider("invalid")

        logger.info(f"  'stripe' 有效: {is_valid_stripe}")
        logger.info(f"  'h5zhifu' 有效: {is_valid_h5zhifu}")
        logger.info(f"  'invalid' 有效: {is_valid_invalid}")

        if is_valid_stripe and is_valid_h5zhifu and not is_valid_invalid:
            logger.success("✅ 支付工厂测试通过!")
        else:
            logger.error("❌ 支付工厂测试失败!")

    except Exception as e:
        logger.error(f"❌ 支付工厂测试异常: {e}")


def test_stripe_payment_module():
    """测试 Stripe 支付模块"""
    logger.info("\n=== 测试 5: Stripe 支付模块 ===")

    try:
        from payments.stripe_payment import StripePaymentService, StripePaymentRequest

        # 检查 Stripe 配置
        stripe_key = os.getenv("STRIPE_SECRET_KEY", "")
        if not stripe_key or stripe_key == "sk_test_your_stripe_secret_key_here":
            logger.warning("⚠️  STRIPE_SECRET_KEY 未配置或使用默认值")
            logger.info("请在 .env 文件中设置真实的 Stripe API 密钥")
            logger.info("获取地址: https://dashboard.stripe.com/apikeys")
            return

        logger.info(f"Stripe Secret Key: {stripe_key[:15]}...")

        # 测试金额格式化
        formatted = StripePaymentService.format_amount_for_display(999, "usd")
        logger.info(f"金额格式化测试: 999 分 = {formatted}")

        if formatted == "9.99 USD":
            logger.success("✅ Stripe 模块测试通过!")
        else:
            logger.error(f"❌ 金额格式化错误: 期望 '9.99 USD', 得到 '{formatted}'")

    except Exception as e:
        logger.error(f"❌ Stripe 模块测试异常: {e}")


def main():
    """主测试流程"""
    logger.info("=" * 60)
    logger.info("Stripe 支付集成测试")
    logger.info("=" * 60)

    # 检查 API 是否运行
    try:
        health_check = requests.get(f"{API_BASE_URL}/health", timeout=3)
        if health_check.status_code != 200:
            logger.error(f"❌ API 健康检查失败: {health_check.status_code}")
            logger.error("请确保后端服务正在运行: uv run python run.py")
            sys.exit(1)
    except requests.exceptions.RequestException as e:
        logger.error(f"❌ 无法连接到 API 服务器: {e}")
        logger.error(f"请确保后端服务正在运行在 {API_BASE_URL}")
        sys.exit(1)

    logger.success(f"✅ API 服务运行正常: {API_BASE_URL}")

    # 测试 5: Stripe 模块测试
    test_stripe_payment_module()

    # 测试 4: 支付工厂测试
    test_payment_factory()

    # 测试 1: 创建支付意图
    payment_result = test_create_payment_intent()

    if payment_result and payment_result.get("order_id"):
        # 等待 1 秒
        time.sleep(1)

        # 测试 2: 查询支付状态
        test_get_payment_status(payment_result["order_id"])
    else:
        logger.warning("⚠️  跳过支付状态查询测试（未创建订单）")

    # 测试 3: Webhook 说明
    test_webhook_simulation()

    logger.info("\n" + "=" * 60)
    logger.info("测试完成!")
    logger.info("=" * 60)

    # 提供后续步骤提示
    logger.info("\n📝 后续步骤:")
    logger.info("1. 在 .env 文件中配置真实的 Stripe API 密钥")
    logger.info("2. 运行数据库迁移:")
    logger.info("   source .env")
    logger.info('   psql "postgresql://postgres:$POSTGRES_PASSWORD@localhost:5438/postgres" \\')
    logger.info("     -v ON_ERROR_STOP=1 \\")
    logger.info("     -f supabase/migrations/12_stripe_integration.sql")
    logger.info("3. 使用 Stripe CLI 测试 Webhook:")
    logger.info(f"   stripe listen --forward-to {API_BASE_URL}/stripe/webhook")
    logger.info("4. 在前端集成 Stripe.js 和 Payment Element")
    logger.info("   文档: https://stripe.com/docs/payments/accept-a-payment")


if __name__ == "__main__":
    main()
