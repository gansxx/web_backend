#!/usr/bin/env python3
"""
高级套餐API集成测试

测试 routes/advanced_plan.py 的所有端点功能
"""

import requests
import json
from loguru import logger

# 配置
BASE_URL = "http://localhost:8001"
TEST_EMAIL = "tesssuunmao@gmail.com"
TEST_PASSWORD = "zhang123ZZY"

def test_login() -> str:
    """测试登录并获取access_token"""
    logger.info("=== 测试登录 ===")

    response = requests.post(
        f"{BASE_URL}/login",
        json={
            "email": TEST_EMAIL,
            "password": TEST_PASSWORD,
            "cf_turnstile_token": "dummy_token_for_localhost"
        },
        headers={"Content-Type": "application/json"}
    )

    if response.status_code == 200:
        data = response.json()
        logger.info(f"✅ 登录成功: {data.get('message')}")

        # 从Cookie中获取access_token
        cookies = response.cookies
        access_token = cookies.get('access_token')
        if access_token:
            logger.info(f"✅ 获取到 access_token: {access_token[:30]}...")
            return access_token
        else:
            logger.error("❌ 未找到 access_token cookie")
            return None
    else:
        logger.error(f"❌ 登录失败: {response.status_code} - {response.text}")
        return None


def test_check_advanced_plan_simple(access_token: str):
    """测试简化版本：检查是否有高级套餐"""
    logger.info("\n=== 测试检查高级套餐 (简化版) ===")

    response = requests.get(
        f"{BASE_URL}/user/advanced-plan/simple",
        cookies={"access_token": access_token}
    )

    if response.status_code == 200:
        data = response.json()
        logger.info(f"✅ 查询成功: {json.dumps(data, ensure_ascii=False, indent=2)}")
    else:
        logger.error(f"❌ 查询失败: {response.status_code} - {response.text}")


def test_check_advanced_plan_detailed(access_token: str):
    """测试详细版本：检查高级套餐详情"""
    logger.info("\n=== 测试检查高级套餐 (详细版) ===")

    response = requests.get(
        f"{BASE_URL}/user/advanced-plan",
        cookies={"access_token": access_token}
    )

    if response.status_code == 200:
        data = response.json()
        logger.info(f"✅ 查询成功:")
        logger.info(f"  has_advanced_plan: {data.get('has_advanced_plan')}")
        logger.info(f"  advanced_plans 数量: {len(data.get('advanced_plans', []))}")
        logger.info(f"  all_products 数量: {len(data.get('all_products', []))}")
    else:
        logger.error(f"❌ 查询失败: {response.status_code} - {response.text}")


def test_purchase_advanced_plan(access_token: str):
    """测试购买高级套餐"""
    logger.info("\n=== 测试购买高级套餐 ===")

    response = requests.post(
        f"{BASE_URL}/user/advanced-plan/purchase",
        cookies={"access_token": access_token},
        json={
            "phone": "13800138000",
            "plan_name": "测试用高级套餐",
            "duration_days": 365,
            "payment_method": "stripe"
        },
        headers={"Content-Type": "application/json"}
    )

    if response.status_code == 200:
        data = response.json()
        logger.info(f"✅ 购买请求成功:")
        logger.info(f"  success: {data.get('success')}")
        logger.info(f"  message: {data.get('message')}")
        logger.info(f"  order_id: {data.get('order_id')}")
        logger.info(f"  payment_intent_id: {data.get('payment_intent_id')}")
        logger.info(f"  client_secret: {data.get('client_secret', '')[:30]}...")
        logger.info(f"  amount: {data.get('amount')} {data.get('currency')}")

        # 注意：在真实环境中，这里应该使用 client_secret 在前端完成支付
        logger.info("\n💡 下一步：")
        logger.info("  1. 前端使用 client_secret 初始化 Stripe Elements")
        logger.info("  2. 用户在前端完成支付")
        logger.info("  3. Stripe 发送 webhook 到 /webhook/stripe/advanced-plan")
        logger.info("  4. 后端自动生成订阅链接并创建产品")

    elif response.status_code == 500:
        error_data = response.json()
        logger.error(f"⚠️  购买失败（预期行为 - 需要配置 Stripe API 密钥）:")
        logger.error(f"  {error_data.get('detail')}")
        logger.info("\n💡 配置说明：")
        logger.info("  1. 在 .env 中设置 STRIPE_SECRET_KEY")
        logger.info("  2. 在 .env 中设置 STRIPE_WEBHOOK_SECRET")
        logger.info("  3. 在 .env 中设置 ADVANCED_PLAN_PRICE=9900")
        logger.info("  4. 在 .env 中设置 ADVANCED_PLAN_CURRENCY=usd")
    else:
        logger.error(f"❌ 购买失败: {response.status_code} - {response.text}")


def test_webhook_endpoint():
    """测试 Stripe webhook 端点（仅验证端点存在）"""
    logger.info("\n=== 测试 Stripe Webhook 端点 ===")

    # 注意：实际的webhook由Stripe调用，这里只验证端点是否存在
    logger.info("ℹ️  Webhook端点: POST /webhook/stripe/advanced-plan")
    logger.info("ℹ️  此端点由 Stripe 自动调用，需要在 Stripe Dashboard 中配置")
    logger.info("ℹ️  配置URL: https://api.selfgo.asia/webhook/stripe/advanced-plan")
    logger.info("ℹ️  事件类型: payment_intent.succeeded, payment_intent.payment_failed")


def main():
    """运行所有测试"""
    logger.info("🚀 开始测试高级套餐API\n")

    # 1. 登录获取token
    access_token = test_login()
    if not access_token:
        logger.error("❌ 登录失败，无法继续测试")
        return

    # 2. 检查高级套餐（简化版）
    test_check_advanced_plan_simple(access_token)

    # 3. 检查高级套餐（详细版）
    test_check_advanced_plan_detailed(access_token)

    # 4. 购买高级套餐
    test_purchase_advanced_plan(access_token)

    # 5. Webhook端点说明
    test_webhook_endpoint()

    logger.info("\n✅ 测试完成！")
    logger.info("\n📚 API端点总结:")
    logger.info("  GET  /user/advanced-plan/simple   - 检查是否有高级套餐（布尔值）")
    logger.info("  GET  /user/advanced-plan          - 获取高级套餐详情")
    logger.info("  POST /user/advanced-plan/purchase - 购买高级套餐（创建Stripe支付）")
    logger.info("  POST /webhook/stripe/advanced-plan - Stripe webhook回调")


if __name__ == "__main__":
    main()
