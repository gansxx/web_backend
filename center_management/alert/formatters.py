"""
alert/formatters.py - 报警邮件内容格式化工具

提供各种类型报警邮件的纯文本格式化功能。
"""

from typing import Dict, Any, Optional
from datetime import datetime
import traceback


def format_plain_text(title: str, details: str, metadata: Optional[Dict[str, Any]] = None) -> str:
    """通用纯文本格式化

    Args:
        title: 报警标题
        details: 报警详细信息
        metadata: 元数据字典（可选）

    Returns:
        str: 格式化后的纯文本内容
    """
    content_lines = [
        "=" * 60,
        f"【报警通知】{title}",
        "=" * 60,
        "",
        "详细信息:",
        "-" * 60,
        details,
        "-" * 60,
        ""
    ]

    # 添加元数据
    if metadata:
        content_lines.append("附加信息:")
        for key, value in metadata.items():
            content_lines.append(f"  {key}: {value}")
        content_lines.append("")

    # 添加时间戳
    content_lines.extend([
        f"报警时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        "",
        "=" * 60
    ])

    return "\n".join(content_lines)


def format_error_alert(
    error: Exception,
    context: Optional[Dict[str, Any]] = None,
    include_traceback: bool = True
) -> str:
    """格式化错误报警信息

    Args:
        error: 异常对象
        context: 错误上下文信息（如请求参数、用户信息等）
        include_traceback: 是否包含完整堆栈跟踪

    Returns:
        str: 格式化后的错误报警内容
    """
    error_type = type(error).__name__
    error_msg = str(error)

    content_lines = [
        "=" * 60,
        "【系统错误报警】",
        "=" * 60,
        "",
        f"错误类型: {error_type}",
        f"错误信息: {error_msg}",
        ""
    ]

    # 添加上下文信息
    if context:
        content_lines.append("错误上下文:")
        content_lines.append("-" * 60)
        for key, value in context.items():
            content_lines.append(f"  {key}: {value}")
        content_lines.append("-" * 60)
        content_lines.append("")

    # 添加堆栈跟踪
    if include_traceback:
        tb_str = ''.join(traceback.format_exception(type(error), error, error.__traceback__))
        content_lines.extend([
            "堆栈跟踪:",
            "-" * 60,
            tb_str,
            "-" * 60,
            ""
        ])

    # 添加时间戳
    content_lines.extend([
        f"发生时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        "",
        "请尽快处理该错误！",
        "",
        "=" * 60
    ])

    return "\n".join(content_lines)


def format_resource_alert(
    resource_type: str,
    resource_name: str,
    current_value: float,
    threshold: float,
    unit: str = "%",
    additional_info: Optional[Dict[str, Any]] = None
) -> str:
    """格式化资源使用率告警信息

    Args:
        resource_type: 资源类型（如 CPU、内存、带宽）
        resource_name: 资源名称（如服务器名、服务名）
        current_value: 当前使用值
        threshold: 告警阈值
        unit: 单位（默认为%）
        additional_info: 额外信息

    Returns:
        str: 格式化后的资源告警内容
    """
    # 判断告警级别
    if current_value >= threshold * 1.2:
        level = "严重"
        symbol = "🔴"
    elif current_value >= threshold:
        level = "警告"
        symbol = "⚠️"
    else:
        level = "提醒"
        symbol = "ℹ️"

    content_lines = [
        "=" * 60,
        f"{symbol} 【资源使用率告警 - {level}】",
        "=" * 60,
        "",
        f"资源类型: {resource_type}",
        f"资源名称: {resource_name}",
        f"当前使用: {current_value:.2f}{unit}",
        f"告警阈值: {threshold:.2f}{unit}",
        f"超出比例: {((current_value / threshold - 1) * 100):.1f}%",
        ""
    ]

    # 添加额外信息
    if additional_info:
        content_lines.append("详细信息:")
        content_lines.append("-" * 60)
        for key, value in additional_info.items():
            content_lines.append(f"  {key}: {value}")
        content_lines.append("-" * 60)
        content_lines.append("")

    # 添加时间戳和建议
    content_lines.extend([
        f"检测时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        "",
        "建议操作:",
        "  1. 检查资源使用详情",
        "  2. 分析异常增长原因",
        "  3. 必要时进行资源扩容",
        "",
        "=" * 60
    ])

    return "\n".join(content_lines)


def format_system_notification(
    event_type: str,
    event_title: str,
    details: Dict[str, Any],
    severity: str = "info"
) -> str:
    """格式化系统通知信息

    Args:
        event_type: 事件类型（如 订单超时、支付异常、部署完成）
        event_title: 事件标题
        details: 事件详情字典
        severity: 严重程度（info/warning/error/critical）

    Returns:
        str: 格式化后的系统通知内容
    """
    # 根据严重程度选择符号
    severity_symbols = {
        "info": "ℹ️",
        "warning": "⚠️",
        "error": "❌",
        "critical": "🔴"
    }
    symbol = severity_symbols.get(severity, "📢")

    # 严重程度中文
    severity_cn = {
        "info": "信息",
        "warning": "警告",
        "error": "错误",
        "critical": "严重"
    }
    severity_text = severity_cn.get(severity, "通知")

    content_lines = [
        "=" * 60,
        f"{symbol} 【系统通知 - {severity_text}】",
        "=" * 60,
        "",
        f"事件类型: {event_type}",
        f"事件标题: {event_title}",
        ""
    ]

    # 添加详细信息
    if details:
        content_lines.append("事件详情:")
        content_lines.append("-" * 60)
        for key, value in details.items():
            # 格式化显示（处理嵌套字典和列表）
            if isinstance(value, (dict, list)):
                content_lines.append(f"  {key}:")
                content_lines.append(f"    {value}")
            else:
                content_lines.append(f"  {key}: {value}")
        content_lines.append("-" * 60)
        content_lines.append("")

    # 添加时间戳
    content_lines.extend([
        f"通知时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        "",
        "=" * 60
    ])

    return "\n".join(content_lines)


def format_simple_message(subject: str, message: str) -> str:
    """格式化简单消息

    Args:
        subject: 主题
        message: 消息内容

    Returns:
        str: 格式化后的消息
    """
    content_lines = [
        "=" * 60,
        f"【{subject}】",
        "=" * 60,
        "",
        message,
        "",
        f"发送时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        "",
        "=" * 60
    ]

    return "\n".join(content_lines)
