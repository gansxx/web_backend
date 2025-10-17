#!/usr/bin/env python3
"""
工单数据库功能测试脚本
测试 TicketConfig 类的所有功能
"""

import sys
import os
from loguru import logger
import json

# 添加项目根目录到 Python 路径
# 当前文件: center_management/db/test_ticket_db.py
# 项目根目录: ../../ (向上两级)
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.normpath(os.path.join(current_dir, '..', '..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from center_management.db.ticket import TicketConfig


def test_ticket_operations():
    """测试工单的增删改查操作"""

    logger.info("=== 开始测试工单数据库操作 ===\n")

    # 初始化工单配置
    try:
        ticket_db = TicketConfig()
        logger.info("✅ TicketConfig 初始化成功\n")
    except Exception as e:
        logger.error(f"❌ TicketConfig 初始化失败: {e}")
        return

    # 测试邮箱
    test_email = "test_user@example.com"

    # 1. 插入工单
    logger.info("--- 测试 1: 插入工单 ---")
    try:
        metadata = {
            "user_agent": "Mozilla/5.0 Test",
            "ip_address": "127.0.0.1",
            "source": "test_script"
        }

        ticket_id_1 = ticket_db.insert_ticket(
            user_email=test_email,
            subject="测试工单 - 登录问题",
            priority="高",
            category="技术支持",
            description="我无法登录系统，一直提示密码错误",
            phone="13800138000",
            metadata=metadata
        )
        logger.info(f"✅ 插入工单成功，ID: {ticket_id_1}\n")

        ticket_id_2 = ticket_db.insert_ticket(
            user_email=test_email,
            subject="测试工单 - 功能咨询",
            priority="中",
            category="一般咨询",
            description="请问如何修改个人资料？",
            metadata=metadata
        )
        logger.info(f"✅ 插入第二个工单成功，ID: {ticket_id_2}\n")

    except Exception as e:
        logger.error(f"❌ 插入工单失败: {e}\n")
        return

    # 2. 查询用户工单
    logger.info("--- 测试 2: 查询用户工单 ---")
    try:
        tickets = ticket_db.fetch_user_tickets(user_email=test_email)
        logger.info(f"✅ 查询成功，找到 {len(tickets)} 个工单")
        for ticket in tickets:
            logger.info(f"  工单: {ticket.get('subject')} | 优先级: {ticket.get('priority')} | 状态: {ticket.get('status')}")
        logger.info("")
    except Exception as e:
        logger.error(f"❌ 查询用户工单失败: {e}\n")

    # 3. 更新工单状态
    logger.info("--- 测试 3: 更新工单状态 ---")
    try:
        success = ticket_db.update_ticket_status(ticket_id_1, "已解决")
        if success:
            logger.info(f"✅ 更新工单状态成功，工单 {ticket_id_1} 已标记为'已解决'\n")
        else:
            logger.warning(f"⚠️ 更新失败，可能工单不存在\n")
    except Exception as e:
        logger.error(f"❌ 更新工单状态失败: {e}\n")

    # 4. 根据ID查询工单（使用 fetch_user_tickets + 过滤）
    logger.info("--- 测试 4: 根据ID查询工单详情 ---")
    try:
        tickets = ticket_db.fetch_user_tickets(test_email)
        ticket = next((t for t in tickets if t.get('id') == ticket_id_1), None)
        if ticket:
            logger.info(f"✅ 查询成功:")
            logger.info(f"  标题: {ticket.get('subject')}")
            logger.info(f"  优先级: {ticket.get('priority')}")
            logger.info(f"  状态: {ticket.get('status')}")
            logger.info(f"  描述: {ticket.get('description')}")
            logger.info(f"  电话: {ticket.get('phone')}")
            logger.info(f"  创建时间: {ticket.get('created_at')}")
            logger.info("")
        else:
            logger.warning(f"⚠️ 未找到工单 {ticket_id_1}\n")
    except Exception as e:
        logger.error(f"❌ 查询工单详情失败: {e}\n")

    # 5. 查询按状态筛选（使用 fetch_all_tickets）
    logger.info("--- 测试 5: 查询处理中的工单 ---")
    try:
        processing_tickets = ticket_db.fetch_all_tickets(status="处理中", limit=10)
        logger.info(f"✅ 找到 {len(processing_tickets)} 个处理中的工单")
        for ticket in processing_tickets[:3]:  # 只显示前3个
            logger.info(f"  - {ticket.get('subject')} ({ticket.get('user_email')})")
        logger.info("")
    except Exception as e:
        logger.error(f"❌ 查询失败: {e}\n")

    # 6. 查询工单总数（使用 len(fetch_user_tickets())）
    logger.info("--- 测试 6: 查询用户工单总数 ---")
    try:
        user_tickets = ticket_db.fetch_user_tickets(test_email)
        count = len(user_tickets)
        logger.info(f"✅ 用户 {test_email} 共有 {count} 个工单\n")
    except Exception as e:
        logger.error(f"❌ 查询失败: {e}\n")

    # 7. 查询所有工单（管理员功能）
    logger.info("--- 测试 7: 查询所有工单（带筛选） ---")
    try:
        all_tickets = ticket_db.fetch_all_tickets(priority="高", limit=5)
        logger.info(f"✅ 找到 {len(all_tickets)} 个高优先级工单（最多5个）")
        for ticket in all_tickets:
            logger.info(f"  - {ticket.get('subject')} | 用户: {ticket.get('user_email')} | 状态: {ticket.get('status')}")
        logger.info("")
    except Exception as e:
        logger.error(f"❌ 查询失败: {e}\n")

    # 8. 测试无效参数
    logger.info("--- 测试 8: 测试参数验证 ---")
    try:
        ticket_db.insert_ticket(
            user_email=test_email,
            subject="无效优先级测试",
            priority="超高",  # 无效值
            category="测试",
            description="这应该失败"
        )
        logger.error("❌ 参数验证失败：应该拒绝无效的优先级值\n")
    except ValueError as e:
        logger.info(f"✅ 参数验证成功：{e}\n")
    except Exception as e:
        logger.info(f"✅ 捕获到数据库错误（预期）: {e}\n")

    logger.info("=== 工单数据库测试完成 ===\n")


if __name__ == "__main__":
    test_ticket_operations()