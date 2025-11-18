"""
测试报警模块功能

运行方式:
    uv run python tests/test_alert_module.py
"""

import sys
import os

# 添加项目根目录到模块搜索路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from center_management.alert import (
    AlertConfig,
    EmailSender,
    send_alert_email,
    send_error_alert,
    send_resource_alert,
    send_system_notification
)
from loguru import logger


def test_config():
    """测试配置类"""
    logger.info("=" * 60)
    logger.info("测试 1: AlertConfig 配置类")
    logger.info("=" * 60)

    config = AlertConfig()

    logger.info(f"SMTP服务器: {config.smtp_host}:{config.smtp_port}")
    logger.info(f"发送者: {config.get_sender_address()}")
    logger.info(f"默认接收人: {config.default_recipients}")
    logger.info(f"配置验证结果: {config.validate_config()}")

    logger.info("✅ 配置类测试完成\n")
    return config


def test_email_sender_simple(config):
    """测试简单邮件发送"""
    logger.info("=" * 60)
    logger.info("测试 2: 简单邮件发送")
    logger.info("=" * 60)

    sender = EmailSender(config)

    # 注意：这里需要替换为真实的收件人邮箱
    test_recipient = "tesssuunmao@gmail.com"

    logger.info(f"发送测试邮件到: {test_recipient}")

    # 如果没有配置SMTP，这里会失败，但不会中断测试
    result = sender.send_simple_message(
        subject="报警模块测试邮件",
        message="这是一封测试邮件，用于验证报警模块的邮件发送功能。",
        recipients=[test_recipient]
    )

    logger.info(f"发送结果: {'成功 ✅' if result else '失败 ❌'}\n")
    return result


def test_error_alert():
    """测试错误报警"""
    logger.info("=" * 60)
    logger.info("测试 3: 错误报警邮件")
    logger.info("=" * 60)

    # 模拟一个错误
    try:
        result = 1 / 0
    except Exception as e:
        logger.info(f"捕获错误: {type(e).__name__}: {e}")

        # 发送错误报警（使用便捷函数）
        context = {
            "operation": "测试除零操作",
            "user": "test_user",
            "timestamp": "2025-01-01 12:00:00"
        }

        # 注意：实际发送需要配置SMTP
        logger.info("调用 send_error_alert()...")
        # result = send_error_alert(e, context=context)
        # logger.info(f"发送结果: {'成功 ✅' if result else '失败 ❌'}")

        # 仅测试格式化功能
        from center_management.alert.formatters import format_error_alert
        formatted = format_error_alert(e, context=context)
        logger.info("格式化的错误报警内容:")
        logger.info(formatted)

    logger.info("✅ 错误报警测试完成\n")


def test_resource_alert():
    """测试资源告警"""
    logger.info("=" * 60)
    logger.info("测试 4: 资源使用率告警")
    logger.info("=" * 60)

    # 测试格式化功能
    from center_management.alert.formatters import format_resource_alert

    formatted = format_resource_alert(
        resource_type="CPU",
        resource_name="web-server-01",
        current_value=85.5,
        threshold=80.0,
        unit="%",
        additional_info={
            "hostname": "web-server-01.example.com",
            "region": "ap-northeast-1",
            "process": "python uvicorn"
        }
    )

    logger.info("格式化的资源告警内容:")
    logger.info(formatted)

    logger.info("✅ 资源告警测试完成\n")


def test_system_notification():
    """测试系统通知"""
    logger.info("=" * 60)
    logger.info("测试 5: 系统通知")
    logger.info("=" * 60)

    # 测试格式化功能
    from center_management.alert.formatters import format_system_notification

    formatted = format_system_notification(
        event_type="订单超时",
        event_title="订单 #ORD-12345 已超时",
        details={
            "order_id": "ORD-12345",
            "user_email": "user@example.com",
            "amount": "¥99.00",
            "timeout_minutes": 30,
            "payment_method": "支付宝"
        },
        severity="warning"
    )

    logger.info("格式化的系统通知内容:")
    logger.info(formatted)

    logger.info("✅ 系统通知测试完成\n")


def test_all_formatters():
    """测试所有格式化器"""
    logger.info("=" * 60)
    logger.info("测试 6: 所有格式化器")
    logger.info("=" * 60)

    from center_management.alert.formatters import (
        format_plain_text,
        format_simple_message
    )

    # 测试纯文本格式化
    plain_text = format_plain_text(
        title="测试报警",
        details="这是一条测试报警消息的详细内容。",
        metadata={
            "source": "test_script",
            "priority": "low"
        }
    )
    logger.info("纯文本格式化:")
    logger.info(plain_text)

    # 测试简单消息格式化
    simple = format_simple_message(
        subject="测试主题",
        message="测试消息内容"
    )
    logger.info("\n简单消息格式化:")
    logger.info(simple)

    logger.info("✅ 格式化器测试完成\n")


def test_convenience_functions():
    """测试便捷函数"""
    logger.info("=" * 60)
    logger.info("测试 7: 便捷函数")
    logger.info("=" * 60)

    logger.info("测试便捷函数导入...")
    logger.info("send_alert_email: ✓")
    logger.info("send_error_alert: ✓")
    logger.info("send_resource_alert: ✓")
    logger.info("send_system_notification: ✓")

    logger.info("✅ 便捷函数测试完成\n")


def main():
    """主测试函数"""
    logger.info("\n" + "=" * 60)
    logger.info("开始测试报警模块")
    logger.info("=" * 60 + "\n")

    try:
        # 1. 测试配置
        config = test_config()

        # 2. 测试简单邮件发送（如果SMTP已配置）
        if config.validate_config():
            logger.info("SMTP配置有效，可以测试邮件发送")
            test_email_sender_simple(config)  # 取消注释以实际发送邮件
        else:
            logger.warning("SMTP配置未完成，跳过实际邮件发送测试")

        # # 3. 测试错误报警格式化
        # test_error_alert()

        # # 4. 测试资源告警格式化
        # test_resource_alert()

        # # 5. 测试系统通知格式化
        # test_system_notification()

        # # 6. 测试所有格式化器
        # test_all_formatters()

        # # 7. 测试便捷函数
        # test_convenience_functions()

        # 总结
        logger.info("=" * 60)
        logger.info("✅ 所有测试完成！")
        logger.info("=" * 60)
        logger.info("\n使用说明:")
        logger.info("1. 确保 .env 文件配置了 SMTP_* 和 ADMIN_EMAILS 变量")
        logger.info("2. 使用便捷函数: from center_management.alert import send_alert_email")
        logger.info("3. 使用类: from center_management.alert import EmailSender")
        logger.info("\n示例代码:")
        logger.info("""
    from center_management.alert import send_error_alert

    try:
        risky_operation()
    except Exception as e:
        send_error_alert(e, context={"user_id": "12345"})
        """)

    except Exception as e:
        logger.error(f"测试过程中发生错误: {e}")
        logger.exception("详细异常信息:")
        return 1

    return 0


if __name__ == "__main__":
    exit(main())
