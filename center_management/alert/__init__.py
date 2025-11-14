"""
alert - 报警模块

提供通用的邮件报警和通知功能，支持：
- 系统错误报警
- 资源使用率告警
- 系统事件通知
- 自定义消息发送

快速使用：
    from center_management.alert import send_alert_email, EmailSender

    # 简单发送
    send_alert_email(
        subject="系统报警",
        content="发生错误",
        recipients=["admin@example.com"]
    )

    # 高级用法
    sender = EmailSender()
    sender.send_error_alert(exception_obj)
    sender.send_resource_alert("CPU", "server-01", 85.5, 80)
"""

from .config import AlertConfig
from .email_sender import EmailSender
from .formatters import (
    format_plain_text,
    format_error_alert,
    format_resource_alert,
    format_system_notification,
    format_simple_message
)

from typing import List, Optional, Dict, Any
from loguru import logger


# 全局单例实例（懒加载）
_global_sender: Optional[EmailSender] = None


def get_sender() -> EmailSender:
    """获取全局EmailSender单例实例

    Returns:
        EmailSender: 邮件发送器实例
    """
    global _global_sender
    if _global_sender is None:
        _global_sender = EmailSender()
        logger.debug("创建全局EmailSender实例")
    return _global_sender


# 便捷函数
def send_alert_email(
    subject: str,
    content: str,
    recipients: Optional[List[str]] = None
) -> bool:
    """快速发送报警邮件（便捷函数）

    Args:
        subject: 邮件主题
        content: 邮件内容
        recipients: 收件人列表，如果未指定则使用默认列表

    Returns:
        bool: 是否发送成功

    Example:
        >>> send_alert_email(
        ...     subject="数据库连接错误",
        ...     content="无法连接到主数据库",
        ...     recipients=["admin@example.com"]
        ... )
        True
    """
    sender = get_sender()
    return sender.send_simple_message(subject, content, recipients)


def send_error_alert(
    error: Exception,
    context: Optional[Dict[str, Any]] = None,
    recipients: Optional[List[str]] = None,
    include_traceback: bool = True
) -> bool:
    """快速发送错误报警（便捷函数）

    Args:
        error: 异常对象
        context: 错误上下文信息
        recipients: 收件人列表
        include_traceback: 是否包含堆栈跟踪

    Returns:
        bool: 是否发送成功

    Example:
        >>> try:
        ...     risky_operation()
        ... except Exception as e:
        ...     send_error_alert(e, context={"user_id": "12345"})
    """
    sender = get_sender()
    return sender.send_error_alert(error, context, recipients, include_traceback)


def send_resource_alert(
    resource_type: str,
    resource_name: str,
    current_value: float,
    threshold: float,
    unit: str = "%",
    additional_info: Optional[Dict[str, Any]] = None,
    recipients: Optional[List[str]] = None
) -> bool:
    """快速发送资源告警（便捷函数）

    Args:
        resource_type: 资源类型（如 CPU、内存、带宽）
        resource_name: 资源名称
        current_value: 当前使用值
        threshold: 告警阈值
        unit: 单位
        additional_info: 额外信息
        recipients: 收件人列表

    Returns:
        bool: 是否发送成功

    Example:
        >>> send_resource_alert(
        ...     resource_type="CPU",
        ...     resource_name="web-server-01",
        ...     current_value=85.5,
        ...     threshold=80.0
        ... )
        True
    """
    sender = get_sender()
    return sender.send_resource_alert(
        resource_type,
        resource_name,
        current_value,
        threshold,
        unit,
        additional_info,
        recipients
    )


def send_system_notification(
    event_type: str,
    event_title: str,
    details: Dict[str, Any],
    severity: str = "info",
    recipients: Optional[List[str]] = None
) -> bool:
    """快速发送系统通知（便捷函数）

    Args:
        event_type: 事件类型
        event_title: 事件标题
        details: 事件详情
        severity: 严重程度（info/warning/error/critical）
        recipients: 收件人列表

    Returns:
        bool: 是否发送成功

    Example:
        >>> send_system_notification(
        ...     event_type="订单超时",
        ...     event_title="订单 #12345 已超时",
        ...     details={"order_id": "12345", "timeout_minutes": 30},
        ...     severity="warning"
        ... )
        True
    """
    sender = get_sender()
    return sender.send_system_notification(
        event_type,
        event_title,
        details,
        severity,
        recipients
    )


# 导出所有公开API
__all__ = [
    # 类
    'AlertConfig',
    'EmailSender',
    # 格式化函数
    'format_plain_text',
    'format_error_alert',
    'format_resource_alert',
    'format_system_notification',
    'format_simple_message',
    # 便捷函数
    'send_alert_email',
    'send_error_alert',
    'send_resource_alert',
    'send_system_notification',
    'get_sender'
]
