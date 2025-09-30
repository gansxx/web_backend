#!/usr/bin/env python3
"""
工单系统 API 端到端测试
测试完整的工单创建和查询流程（需要用户登录）
"""

import requests
from loguru import logger
import json
import sys


# API 基础地址
API_BASE = "http://localhost:8001"

# 测试用户信息
TEST_USER = {
    "email": "test_ticket@example.com",
    "password": "TestPassword123!"
}


def register_or_login():
    """注册或登录测试用户"""
    logger.info("=== 步骤 1: 用户认证 ===")

    # 尝试注册
    try:
        resp = requests.post(f"{API_BASE}/signup", json=TEST_USER, timeout=10)
        if resp.status_code == 200:
            logger.info("✅ 用户注册成功")
        else:
            logger.info(f"ℹ️ 用户可能已存在: {resp.status_code}")
    except Exception as e:
        logger.warning(f"⚠️ 注册请求失败: {e}")

    # 登录获取 session
    try:
        resp = requests.post(
            f"{API_BASE}/login",
            json=TEST_USER,
            timeout=10,
            allow_redirects=False
        )

        if resp.status_code in (200, 302):
            logger.info("✅ 登录成功")
            # 提取 cookies
            cookies = resp.cookies
            logger.info(f"获得 cookies: {list(cookies.keys())}")
            return cookies
        else:
            logger.error(f"❌ 登录失败: {resp.status_code} - {resp.text}")
            return None
    except Exception as e:
        logger.error(f"❌ 登录请求异常: {e}")
        return None


def test_create_ticket(cookies):
    """测试创建工单"""
    logger.info("\n=== 步骤 2: 创建工单 ===")

    ticket_data = {
        "subject": "测试工单 - API测试",
        "priority": "high",
        "category": "技术支持",
        "description": "这是一个通过 API 测试创建的工单，测试用户认证和数据库集成。"
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
            logger.info(f"✅ 工单创建成功:")
            logger.info(f"  ticket_id: {result.get('ticket_id')}")
            logger.info(f"  message: {result.get('message')}")
            return result.get('ticket_id')
        else:
            logger.error(f"❌ 创建工单失败: {resp.status_code}")
            logger.error(f"响应: {resp.text}")
            return None
    except Exception as e:
        logger.error(f"❌ 请求异常: {e}")
        return None


def test_create_multiple_tickets(cookies):
    """创建多个测试工单"""
    logger.info("\n=== 步骤 3: 创建多个工单 ===")

    tickets = [
        {
            "subject": "登录问题",
            "priority": "urgent",
            "category": "账号问题",
            "description": "无法登录账号"
        },
        {
            "subject": "功能咨询",
            "priority": "normal",
            "category": "一般咨询",
            "description": "如何使用某个功能"
        },
        {
            "subject": "付费问题",
            "priority": "high",
            "category": "支付问题",
            "description": "支付失败"
        }
    ]

    created_ids = []
    for ticket_data in tickets:
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
                created_ids.append(ticket_id)
                logger.info(f"✅ 创建工单: {ticket_data['subject']} (ID: {ticket_id})")
            else:
                logger.warning(f"⚠️ 创建失败: {ticket_data['subject']}")
        except Exception as e:
            logger.error(f"❌ 请求异常: {e}")

    logger.info(f"\n共创建 {len(created_ids)} 个工单")
    return created_ids


def test_get_user_tickets(cookies):
    """测试获取用户工单列表"""
    logger.info("\n=== 步骤 4: 获取工单列表 ===")

    try:
        resp = requests.get(
            f"{API_BASE}/support/tickets",
            cookies=cookies,
            timeout=10
        )

        if resp.status_code == 200:
            tickets = resp.json()
            logger.info(f"✅ 成功获取 {len(tickets)} 个工单:")
            for ticket in tickets:
                logger.info(f"  - [{ticket.get('status')}] {ticket.get('subject')} (优先级: {ticket.get('priority')})")
            return tickets
        else:
            logger.error(f"❌ 获取工单列表失败: {resp.status_code}")
            logger.error(f"响应: {resp.text}")
            return []
    except Exception as e:
        logger.error(f"❌ 请求异常: {e}")
        return []


def test_get_ticket_detail(cookies, ticket_id):
    """测试获取工单详情"""
    logger.info(f"\n=== 步骤 5: 获取工单详情 ===")

    try:
        resp = requests.get(
            f"{API_BASE}/support/tickets/{ticket_id}",
            cookies=cookies,
            timeout=10
        )

        if resp.status_code == 200:
            ticket = resp.json()
            logger.info(f"✅ 成功获取工单详情:")
            logger.info(f"  标题: {ticket.get('subject')}")
            logger.info(f"  优先级: {ticket.get('priority')}")
            logger.info(f"  状态: {ticket.get('status')}")
            logger.info(f"  描述: {ticket.get('description')}")
            logger.info(f"  创建时间: {ticket.get('created_at')}")
            return ticket
        else:
            logger.error(f"❌ 获取工单详情失败: {resp.status_code}")
            logger.error(f"响应: {resp.text}")
            return None
    except Exception as e:
        logger.error(f"❌ 请求异常: {e}")
        return None


def test_unauthorized_access():
    """测试未登录访问（应该失败）"""
    logger.info("\n=== 步骤 6: 测试未登录访问 ===")

    try:
        resp = requests.get(f"{API_BASE}/support/tickets", timeout=10)
        if resp.status_code == 401:
            logger.info("✅ 未登录访问被正确拒绝 (401)")
        else:
            logger.warning(f"⚠️ 未登录访问返回: {resp.status_code} (预期 401)")
    except Exception as e:
        logger.error(f"❌ 请求异常: {e}")


def run_all_tests():
    """运行所有测试"""
    logger.info("=" * 60)
    logger.info("开始工单系统 API 端到端测试")
    logger.info("=" * 60)

    # 1. 登录
    cookies = register_or_login()
    if not cookies:
        logger.error("❌ 无法获取登录凭证，测试终止")
        sys.exit(1)

    # 2. 创建单个工单
    ticket_id = test_create_ticket(cookies)
    if not ticket_id:
        logger.warning("⚠️ 工单创建失败，但继续测试")

    # 3. 创建多个工单
    created_ids = test_create_multiple_tickets(cookies)

    # 4. 获取工单列表
    tickets = test_get_user_tickets(cookies)

    # 5. 获取工单详情（如果有工单）
    if tickets and len(tickets) > 0:
        first_ticket_id = tickets[0].get('id')
        test_get_ticket_detail(cookies, first_ticket_id)
    elif ticket_id:
        test_get_ticket_detail(cookies, ticket_id)

    # 6. 测试未授权访问
    test_unauthorized_access()

    logger.info("\n" + "=" * 60)
    logger.info("测试完成")
    logger.info("=" * 60)


if __name__ == "__main__":
    try:
        run_all_tests()
    except KeyboardInterrupt:
        logger.info("\n测试被用户中断")
        sys.exit(0)
    except Exception as e:
        logger.error(f"\n测试过程中发生未处理的异常: {e}")
        sys.exit(1)