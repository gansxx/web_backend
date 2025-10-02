#!/usr/bin/env python3
"""
管理员工单答复功能测试
测试新的 admin_email 参数验证逻辑
"""

import requests
from loguru import logger
import sys


API_BASE = "http://localhost:8001"

# 测试用户信息
TEST_USER = {
    "email": "test_ticket@example.com",
    "password": "TestPassword123!"
}

# 管理员邮箱（必须在 .env 的 ADMIN_EMAILS 中）
ADMIN_EMAIL = "1214250247@qq.com"
NON_ADMIN_EMAIL = "fake_admin@example.com"


def test_create_ticket_as_user():
    """用户创建工单"""
    logger.info("=== 测试 1: 用户创建工单 ===")

    # 1. 登录
    try:
        resp = requests.post(
            f"{API_BASE}/login",
            json=TEST_USER,
            timeout=10,
            allow_redirects=False
        )

        if resp.status_code not in (200, 302):
            logger.error(f"登录失败: {resp.status_code}")
            return None

        cookies = resp.cookies
        logger.info("✅ 用户登录成功")
    except Exception as e:
        logger.error(f"登录失败: {e}")
        return None

    # 2. 创建工单
    ticket_data = {
        "subject": "测试管理员答复功能",
        "priority": "高",
        "category": "技术支持",
        "description": "测试新的 admin_email 参数验证逻辑"
    }

    try:
        resp = requests.post(
            f"{API_BASE}/support/submit_ticket",
            json=ticket_data,
            cookies=cookies,
            timeout=10
        )

        if resp.status_code == 200:
            result = resp.json()
            ticket_id = result.get('ticket_id')
            logger.info(f"✅ 工单创建成功: {ticket_id}")
            return ticket_id
        else:
            logger.error(f"❌ 工单创建失败: {resp.status_code} - {resp.text}")
            return None
    except Exception as e:
        logger.error(f"❌ 创建工单异常: {e}")
        return None


def test_admin_get_all_tickets_valid():
    """测试管理员获取所有工单（有效邮箱）"""
    logger.info("\n=== 测试 2: 管理员获取所有工单（有效邮箱）===")

    try:
        resp = requests.get(
            f"{API_BASE}/support/admin/tickets",
            params={"admin_email": ADMIN_EMAIL},
            timeout=10
        )

        if resp.status_code == 200:
            tickets = resp.json()
            logger.info(f"✅ 成功获取 {len(tickets)} 个工单")
            return True
        else:
            logger.error(f"❌ 获取工单失败: {resp.status_code} - {resp.text}")
            return False
    except Exception as e:
        logger.error(f"❌ 请求异常: {e}")
        return False


def test_admin_get_all_tickets_invalid():
    """测试非管理员获取所有工单（无效邮箱）"""
    logger.info("\n=== 测试 3: 非管理员获取所有工单（应该失败）===")

    try:
        resp = requests.get(
            f"{API_BASE}/support/admin/tickets",
            params={"admin_email": NON_ADMIN_EMAIL},
            timeout=10
        )

        if resp.status_code == 403:
            logger.info("✅ 非管理员邮箱被正确拒绝 (403)")
            return True
        else:
            logger.error(f"⚠️ 未预期的状态码: {resp.status_code} (应该是 403)")
            return False
    except Exception as e:
        logger.error(f"❌ 请求异常: {e}")
        return False


def test_admin_reply_valid(ticket_id):
    """测试管理员答复工单（有效邮箱）"""
    logger.info("\n=== 测试 4: 管理员答复工单（有效邮箱）===")

    if not ticket_id:
        logger.warning("⚠️ 没有工单 ID，跳过测试")
        return False

    reply_data = {
        "status": "已解决",
        "reply": "您的问题已解决，感谢您的反馈！这是通过新的 admin_email 参数验证的测试。",
        "send_email": False,  # 测试环境不发送邮件
        "admin_email": ADMIN_EMAIL
    }

    try:
        resp = requests.patch(
            f"{API_BASE}/support/tickets/{ticket_id}/reply",
            json=reply_data,
            timeout=10
        )

        if resp.status_code == 200:
            result = resp.json()
            logger.info(f"✅ 答复成功: {result.get('message')}")
            logger.info(f"   邮件发送: {result.get('email_sent')}")
            return True
        else:
            logger.error(f"❌ 答复失败: {resp.status_code} - {resp.text}")
            return False
    except Exception as e:
        logger.error(f"❌ 请求异常: {e}")
        return False


def test_admin_reply_invalid(ticket_id):
    """测试非管理员答复工单（无效邮箱）"""
    logger.info("\n=== 测试 5: 非管理员答复工单（应该失败）===")

    if not ticket_id:
        logger.warning("⚠️ 没有工单 ID，跳过测试")
        return False

    reply_data = {
        "status": "处理中",
        "reply": "这是一个非管理员的尝试",
        "send_email": False,
        "admin_email": NON_ADMIN_EMAIL
    }

    try:
        resp = requests.patch(
            f"{API_BASE}/support/tickets/{ticket_id}/reply",
            json=reply_data,
            timeout=10
        )

        if resp.status_code == 403:
            logger.info("✅ 非管理员邮箱被正确拒绝 (403)")
            return True
        else:
            logger.error(f"⚠️ 未预期的状态码: {resp.status_code} (应该是 403)")
            logger.error(f"响应: {resp.text}")
            return False
    except Exception as e:
        logger.error(f"❌ 请求异常: {e}")
        return False


def main():
    """运行所有测试"""
    logger.info("=" * 60)
    logger.info("开始管理员工单答复功能测试")
    logger.info("=" * 60)

    # 测试 1: 创建工单
    ticket_id = test_create_ticket_as_user()

    # 测试 2: 管理员获取所有工单（有效）
    test_admin_get_all_tickets_valid()

    # 测试 3: 非管理员获取所有工单（无效）
    test_admin_get_all_tickets_invalid()

    # 测试 4: 管理员答复工单（有效）
    test_admin_reply_valid(ticket_id)

    # 测试 5: 非管理员答复工单（无效）
    test_admin_reply_invalid(ticket_id)

    logger.info("\n" + "=" * 60)
    logger.info("测试完成 ✅")
    logger.info("=" * 60)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        logger.info("\n测试被用户中断")
        sys.exit(0)
    except Exception as e:
        logger.error(f"\n测试过程中发生未处理的异常: {e}")
        sys.exit(1)
