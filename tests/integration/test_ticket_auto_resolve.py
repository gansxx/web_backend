#!/usr/bin/env python3
"""
工单自动解决触发器测试
测试当添加 reply 时，ticket 状态自动变为"已解决"且 replied_at 自动更新
"""

import sys
from pathlib import Path

# 添加项目根目录到 Python 路径
sys.path.insert(0, str(Path(__file__).parent))

from center_management.db.ticket import TicketConfig
from loguru import logger
import time


def test_auto_resolve_on_reply():
    """测试添加答复时自动解决工单"""
    logger.info("=== 测试 1: 添加答复自动解决工单 ===")

    ticket_config = TicketConfig()

    # 1. 创建一个新工单（状态默认为"处理中"）
    ticket_id = ticket_config.insert_ticket(
        user_email="test_autoresolve@example.com",
        subject="测试自动解决功能",
        priority="中",
        category="技术支持",
        description="这是一个测试工单，用于验证自动解决功能"
    )
    logger.info(f"✅ 创建工单成功: {ticket_id}")

    # 2. 获取工单详情，验证初始状态
    ticket = ticket_config.get_ticket_by_id(ticket_id)
    assert ticket is not None, "工单不存在"
    assert ticket['status'] == '处理中', f"初始状态应为'处理中'，实际为: {ticket['status']}"
    assert ticket['reply'] is None or ticket['reply'] == '', "reply 应为空"
    assert ticket['replied_at'] is None, "replied_at 应为空"
    logger.info(f"✅ 初始状态验证通过: status={ticket['status']}, reply={ticket['reply']}, replied_at={ticket['replied_at']}")

    # 等待一秒确保时间戳不同
    time.sleep(1)

    # 3. 添加答复（使用 update_ticket_status 函数）
    success = ticket_config.update_ticket_status(
        ticket_id=ticket_id,
        status='处理中',  # 尝试设置为"处理中"，但触发器应该自动改为"已解决"
        reply="感谢您的反馈，问题已经解决。"
    )
    assert success, "更新工单失败"
    logger.info("✅ 添加答复成功")

    # 4. 再次获取工单详情，验证自动解决功能
    ticket = ticket_config.get_ticket_by_id(ticket_id)
    assert ticket is not None, "工单不存在"
    assert ticket['status'] == '已解决', f"添加答复后状态应自动变为'已解决'，实际为: {ticket['status']}"
    assert ticket['reply'] == "感谢您的反馈，问题已经解决。", "reply 内容不正确"
    assert ticket['replied_at'] is not None, "replied_at 应该被自动设置"
    logger.info(f"✅ 自动解决验证通过: status={ticket['status']}, replied_at={ticket['replied_at']}")

    logger.info("=" * 50)
    logger.info("✅ 测试 1 通过：添加答复时自动解决工单")
    logger.info("=" * 50)
    return ticket_id


def test_update_existing_reply():
    """测试更新已有答复时的行为"""
    logger.info("\n=== 测试 2: 更新已有答复 ===")

    ticket_config = TicketConfig()

    # 1. 创建工单并添加初始答复
    ticket_id = ticket_config.insert_ticket(
        user_email="test_update_reply@example.com",
        subject="测试更新答复",
        priority="低",
        category="一般咨询",
        description="测试更新答复功能"
    )

    ticket_config.update_ticket_status(
        ticket_id=ticket_id,
        status='处理中',
        reply="第一次答复"
    )

    # 获取第一次答复后的时间戳
    ticket = ticket_config.get_ticket_by_id(ticket_id)
    first_replied_at = ticket['replied_at']
    logger.info(f"✅ 第一次答复时间: {first_replied_at}")

    time.sleep(1)

    # 2. 更新答复内容
    ticket_config.update_ticket_status(
        ticket_id=ticket_id,
        status='处理中',  # 尝试改回"处理中"
        reply="第二次答复（更新内容）"
    )

    # 3. 验证更新后的状态
    ticket = ticket_config.get_ticket_by_id(ticket_id)
    assert ticket['status'] == '已解决', f"更新答复后状态仍应为'已解决'，实际为: {ticket['status']}"
    assert ticket['reply'] == "第二次答复（更新内容）", "reply 内容应该被更新"
    second_replied_at = ticket['replied_at']
    logger.info(f"✅ 第二次答复时间: {second_replied_at}")
    logger.info(f"✅ replied_at 已更新: {first_replied_at} -> {second_replied_at}")

    logger.info("=" * 50)
    logger.info("✅ 测试 2 通过：更新答复功能正常")
    logger.info("=" * 50)


def test_manual_status_override():
    """测试手动设置状态（不添加答复）"""
    logger.info("\n=== 测试 3: 手动设置状态（无答复） ===")

    ticket_config = TicketConfig()

    # 1. 创建工单
    ticket_id = ticket_config.insert_ticket(
        user_email="test_manual_status@example.com",
        subject="测试手动状态",
        priority="高",
        category="紧急问题",
        description="测试不添加答复时的状态更新"
    )

    # 2. 仅更新状态，不添加答复
    ticket_config.update_ticket_status(
        ticket_id=ticket_id,
        status='已解决',
        reply=None  # 不添加答复
    )

    # 3. 验证状态更新但 replied_at 仍为空
    ticket = ticket_config.get_ticket_by_id(ticket_id)
    assert ticket['status'] == '已解决', "手动设置状态应该成功"
    assert ticket['reply'] is None or ticket['reply'] == '', "reply 应该仍为空"
    assert ticket['replied_at'] is None, "replied_at 应该仍为空（因为没有添加答复）"
    logger.info(f"✅ 手动状态验证通过: status={ticket['status']}, reply={ticket['reply']}, replied_at={ticket['replied_at']}")

    logger.info("=" * 50)
    logger.info("✅ 测试 3 通过：手动设置状态不触发自动答复时间")
    logger.info("=" * 50)


def test_empty_reply_does_not_trigger():
    """测试空字符串答复不触发自动解决"""
    logger.info("\n=== 测试 4: 空字符串答复不触发 ===")

    ticket_config = TicketConfig()

    # 1. 创建工单
    ticket_id = ticket_config.insert_ticket(
        user_email="test_empty_reply@example.com",
        subject="测试空答复",
        priority="中",
        category="测试",
        description="测试空字符串答复行为"
    )

    # 2. 尝试使用空字符串答复
    ticket_config.update_ticket_status(
        ticket_id=ticket_id,
        status='处理中',
        reply=""  # 空字符串
    )

    # 3. 验证状态保持为"处理中"
    ticket = ticket_config.get_ticket_by_id(ticket_id)
    assert ticket['status'] == '处理中', f"空答复不应触发自动解决，状态应为'处理中'，实际为: {ticket['status']}"
    assert ticket['replied_at'] is None, "空答复不应设置 replied_at"
    logger.info(f"✅ 空答复验证通过: status={ticket['status']}, replied_at={ticket['replied_at']}")

    logger.info("=" * 50)
    logger.info("✅ 测试 4 通过：空字符串答复不触发自动解决")
    logger.info("=" * 50)


def main():
    """运行所有测试"""
    logger.info("\n" + "=" * 50)
    logger.info("开始测试工单自动解决触发器")
    logger.info("=" * 50 + "\n")

    try:
        # 测试 1: 添加答复自动解决
        test_auto_resolve_on_reply()

        # 测试 2: 更新已有答复
        test_update_existing_reply()

        # 测试 3: 手动设置状态（不添加答复）
        test_manual_status_override()

        # 测试 4: 空字符串答复不触发
        test_empty_reply_does_not_trigger()

        logger.info("\n" + "=" * 50)
        logger.info("🎉 所有测试通过！")
        logger.info("=" * 50)
        return 0

    except AssertionError as e:
        logger.error(f"\n❌ 测试失败: {e}")
        return 1
    except Exception as e:
        logger.error(f"\n❌ 测试出错: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    exit(main())
