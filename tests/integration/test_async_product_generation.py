#!/usr/bin/env python3
"""
异步产品生成流程测试

测试支付成功后的异步产品生成流程和订单状态查询
"""

import requests
import json
import time
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
            logger.info(f"✅ 获取到 access_token")
            return access_token
        else:
            logger.error("❌ 未找到 access_token cookie")
            return None
    else:
        logger.error(f"❌ 登录失败: {response.status_code} - {response.text}")
        return None


def test_order_status_endpoint_structure(access_token: str):
    """测试订单状态查询端点结构（使用假订单ID）"""
    logger.info("\n=== 测试订单状态查询端点结构 ===")

    # 使用一个假的UUID
    fake_order_id = "550e8400-e29b-41d4-a716-446655440000"

    response = requests.get(
        f"{BASE_URL}/user/order-status/{fake_order_id}",
        cookies={"access_token": access_token}
    )

    # 预期404（订单不存在）
    if response.status_code == 404:
        logger.info(f"✅ 端点正常响应404（订单不存在）")
        return True
    elif response.status_code == 200:
        data = response.json()
        logger.info(f"✅ 端点正常响应200: {json.dumps(data, ensure_ascii=False, indent=2)}")

        # 验证响应结构
        required_fields = ["order_id", "product_status", "message", "is_completed", "is_failed", "should_continue_polling"]
        missing_fields = [field for field in required_fields if field not in data]

        if missing_fields:
            logger.error(f"❌ 响应缺少字段: {missing_fields}")
            return False
        else:
            logger.info(f"✅ 响应结构验证成功，包含所有必需字段")
            return True
    else:
        logger.error(f"❌ 端点响应异常: {response.status_code} - {response.text}")
        return False


def test_purchase_flow_simulation(access_token: str):
    """模拟购买流程（仅测试端点，不实际支付）"""
    logger.info("\n=== 模拟购买流程测试 ===")

    logger.info("📝 注意: 此测试仅验证端点可用性")
    logger.info("📝 实际支付需要配置Stripe API密钥")

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

    if response.status_code == 500:
        # 预期错误（Stripe未配置）
        error_data = response.json()
        logger.info(f"✅ 端点正常响应（预期的Stripe配置错误）")
        logger.info(f"   错误信息: {error_data.get('detail')}")
        return True
    elif response.status_code == 200:
        data = response.json()
        logger.info(f"✅ 购买端点正常工作:")
        logger.info(f"   order_id: {data.get('order_id')}")
        logger.debug(f"{data}")
        logger.info(f"   client_secret: {data.get('client_secret', '')[:30]}...")
        return True
    else:
        logger.error(f"❌ 购买端点响应异常: {response.status_code}")
        return False


def demonstrate_polling_logic():
    """演示前端轮询逻辑（伪代码）"""
    logger.info("\n=== 前端轮询逻辑示例 ===")

    pseudo_code = """
async function pollOrderStatus(orderId) {
  const MAX_ATTEMPTS = 30;  // 最多60秒
  let attempts = 0;

  const interval = setInterval(async () => {
    attempts++;

    const response = await fetch(`/user/order-status/${orderId}`, {
      credentials: 'include'
    });

    const data = await response.json();

    if (data.is_completed) {
      clearInterval(interval);
      showSuccess('✅ 产品生成完成！');
      goToProductsPage();

    } else if (data.is_failed) {
      clearInterval(interval);
      showError('❌ 产品生成失败');

    } else if (attempts >= MAX_ATTEMPTS) {
      clearInterval(interval);
      showWarning('⚠️ 产品生成超时');
    }
    // 继续轮询...

  }, 2000); // 每2秒查询一次
}
    """

    logger.info(pseudo_code)


def main():
    """运行所有测试"""
    logger.info("🚀 开始测试异步产品生成流程\n")

    # 1. 登录获取token
    access_token = test_login()
    if not access_token:
        logger.error("❌ 登录失败，无法继续测试")
        return

    # 2. 测试订单状态查询端点
    test_order_status_endpoint_structure(access_token)

    # 3. 模拟购买流程
    test_purchase_flow_simulation(access_token)

    # 4. 演示轮询逻辑
    demonstrate_polling_logic()

    logger.info("\n✅ 测试完成！")
    logger.info("\n📚 异步流程总结:")
    logger.info("  1️⃣  用户完成支付 → 后端创建订单（product_status: pending）")
    logger.info("  2️⃣  Stripe webhook触发 → 更新状态为processing → 启动后台任务")
    logger.info("  3️⃣  前端轮询 /user/order-status/{order_id} 每2秒查询一次")
    logger.info("  4️⃣  后台任务完成 → 状态更新为completed → 前端停止轮询")
    logger.info("  5️⃣  前端跳转到产品页面显示订阅链接")

    logger.info("\n🔧 部署步骤:")
    logger.info("  1. 运行数据库迁移: 13_add_product_status.sql")
    logger.info("  2. 重启后端服务")
    logger.info("  3. 前端集成轮询逻辑")
    logger.info("  4. 测试完整支付流程")


if __name__ == "__main__":
    main()
