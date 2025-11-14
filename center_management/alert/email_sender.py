"""
alert/email_sender.py - 邮件发送器

提供通用的邮件发送功能，支持报警和通知场景。
"""

import smtplib
import socket
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import List, Optional, Dict, Any
from loguru import logger
import time

from .config import AlertConfig
from .formatters import (
    format_plain_text,
    format_error_alert,
    format_resource_alert,
    format_system_notification,
    format_simple_message
)


class EmailSender:
    """邮件发送器类

    提供各种类型的邮件发送功能，包括：
    - 通用邮件发送
    - 错误报警
    - 资源告警
    - 系统通知
    """

    def __init__(self, config: Optional[AlertConfig] = None):
        """初始化邮件发送器

        Args:
            config: 报警配置对象，如果未提供则自动创建
        """
        self.config = config or AlertConfig()

        # 验证配置
        if not self.config.validate_config():
            logger.warning("邮件配置验证失败，部分功能可能无法正常使用")

        logger.info("邮件发送器初始化成功")

    def send_email(
        self,
        to: str,
        subject: str,
        content: str,
        retry_count: int = 3,
        retry_delay: float = 2.0
    ) -> bool:
        """发送纯文本邮件（核心函数）

        Args:
            to: 收件人邮箱
            subject: 邮件主题
            content: 邮件内容（纯文本）
            retry_count: 重试次数（默认3次）
            retry_delay: 重试延迟秒数（默认2秒）

        Returns:
            bool: 是否发送成功
        """
        for attempt in range(1, retry_count + 1):
            try:
                # 创建邮件
                msg = MIMEText(content, 'plain', 'utf-8')
                msg['Subject'] = subject
                msg['From'] = self.config.get_sender_address()
                msg['To'] = to

                logger.info(
                    f"准备发送邮件 (尝试 {attempt}/{retry_count}) - "
                    f"收件人: {to}, 主题: {subject}, "
                    f"SMTP服务器: {self.config.smtp_host}:{self.config.smtp_port}"
                )

                # 连接SMTP服务器并发送
                # 根据端口选择SSL或普通连接
                use_ssl = self.config.smtp_port == 465
                connection_type = "SMTP_SSL (端口465)" if use_ssl else f"SMTP (端口{self.config.smtp_port})"
                logger.debug(f"🔌 开始连接SMTP服务器: {self.config.smtp_host}:{self.config.smtp_port} 使用{connection_type} (超时: 10秒)")

                # 根据端口选择不同的连接方式
                if use_ssl:
                    # 465端口使用SSL连接
                    server = smtplib.SMTP_SSL(
                        self.config.smtp_host,
                        self.config.smtp_port,
                        timeout=10
                    )
                else:
                    # 其他端口使用普通连接 + STARTTLS
                    server = smtplib.SMTP(
                        self.config.smtp_host,
                        self.config.smtp_port,
                        timeout=10
                    )

                try:
                    logger.debug(f"✅ TCP连接建立成功 (使用{connection_type})")

                    # 启用调试输出 (仅在第一次尝试时)
                    if attempt == 1:
                        server.set_debuglevel(1)

                    # 非SSL端口需要启用STARTTLS
                    if not use_ssl:
                        logger.debug(f"🔐 启用STARTTLS加密...")
                        server.starttls()
                        logger.debug(f"✅ STARTTLS启用成功")

                    # 如果需要认证
                    if self.config.smtp_user and self.config.smtp_pass:
                        logger.debug(f"🔐 开始SMTP认证 - 用户名: {self.config.smtp_user}")
                        try:
                            server.login(self.config.smtp_user, self.config.smtp_pass)
                            logger.debug(f"✅ SMTP认证成功")
                        except smtplib.SMTPAuthenticationError as auth_err:
                            logger.error(
                                f"❌ SMTP认证失败详情:\n"
                                f"  用户名: {self.config.smtp_user}\n"
                                f"  服务器: {self.config.smtp_host}:{self.config.smtp_port}\n"
                                f"  错误信息: {auth_err}\n"
                                f"  可能原因:\n"
                                f"  1. 用户名或授权码错误\n"
                                f"  2. QQ邮箱需要使用授权码而非QQ密码\n"
                                f"  3. 未开启SMTP服务\n"
                                f"  4. IP被限制或账号被暂时封禁"
                            )
                            raise
                    else:
                        logger.warning(f"⚠️ 未配置SMTP认证信息，尝试匿名发送")

                    logger.debug(f"📤 开始发送邮件消息...")
                    server.send_message(msg)
                    logger.info(f"✅ 邮件发送成功: {to} - {subject}")

                    # 邮件发送成功,尝试正常关闭连接
                    # 某些SMTP服务器(如QQ邮箱)在QUIT时可能返回异常响应,但不影响邮件发送
                    try:
                        server.quit()
                    except Exception as quit_err:
                        logger.debug(f"⚠️ QUIT命令响应异常(可忽略): {quit_err}")

                    return True

                finally:
                    # 确保连接被关闭
                    try:
                        if server.sock:
                            server.close()
                    except:
                        pass

            except smtplib.SMTPAuthenticationError as e:
                # 认证失败已在上面详细记录
                return False  # 认证失败不重试

            except smtplib.SMTPConnectError as e:
                logger.error(
                    f"❌ SMTP连接错误 (尝试 {attempt}/{retry_count}):\n"
                    f"  错误类型: SMTPConnectError\n"
                    f"  错误信息: {e}\n"
                    f"  可能原因:\n"
                    f"  1. SMTP服务器地址或端口错误\n"
                    f"  2. 防火墙阻止连接\n"
                    f"  3. SMTP服务器不可达或宕机\n"
                    f"  4. 网络连接问题"
                )
                if attempt < retry_count:
                    logger.info(f"⏳ 等待 {retry_delay} 秒后重试...")
                    time.sleep(retry_delay)
                    continue

            except smtplib.SMTPServerDisconnected as e:
                logger.error(
                    f"❌ SMTP服务器断开连接 (尝试 {attempt}/{retry_count}):\n"
                    f"  错误类型: SMTPServerDisconnected\n"
                    f"  错误信息: {e}\n"
                    f"  可能原因:\n"
                    f"  1. 服务器主动断开连接（超时或限制）\n"
                    f"  2. 网络不稳定导致连接中断\n"
                    f"  3. SMTP服务器负载过高"
                )
                if attempt < retry_count:
                    logger.info(f"⏳ 等待 {retry_delay} 秒后重试...")
                    time.sleep(retry_delay)
                    continue

            except smtplib.SMTPException as e:
                logger.error(
                    f"❌ SMTP协议错误 (尝试 {attempt}/{retry_count}):\n"
                    f"  错误类型: {type(e).__name__}\n"
                    f"  错误信息: {e}\n"
                    f"  建议:\n"
                    f"  1. 检查SMTP服务器配置是否正确\n"
                    f"  2. 查看SMTP服务器日志获取详细信息\n"
                    f"  3. 确认邮件格式是否符合要求"
                )
                if attempt < retry_count:
                    logger.info(f"⏳ 等待 {retry_delay} 秒后重试...")
                    time.sleep(retry_delay)
                    continue

            except socket.timeout as e:
                logger.error(
                    f"❌ 连接超时 (尝试 {attempt}/{retry_count}):\n"
                    f"  超时时间: 10秒\n"
                    f"  错误信息: {e}\n"
                    f"  可能原因:\n"
                    f"  1. 网络延迟过高\n"
                    f"  2. SMTP服务器响应缓慢\n"
                    f"  3. 被防火墙或安全组限制\n"
                    f"  4. SMTP端口被封禁"
                )
                if attempt < retry_count:
                    logger.info(f"⏳ 等待 {retry_delay} 秒后重试...")
                    time.sleep(retry_delay)
                    continue

            except OSError as e:
                logger.error(
                    f"❌ 操作系统错误 (尝试 {attempt}/{retry_count}):\n"
                    f"  错误类型: {type(e).__name__}\n"
                    f"  错误代码: {e.errno if hasattr(e, 'errno') else 'N/A'}\n"
                    f"  错误信息: {e}\n"
                    f"  可能原因:\n"
                    f"  1. 网络不可达\n"
                    f"  2. DNS解析失败\n"
                    f"  3. 连接被拒绝\n"
                    f"  4. 系统资源不足"
                )
                if attempt < retry_count:
                    logger.info(f"⏳ 等待 {retry_delay} 秒后重试...")
                    time.sleep(retry_delay)
                    continue

            except Exception as e:
                logger.error(
                    f"❌ 未知错误 (尝试 {attempt}/{retry_count}):\n"
                    f"  错误类型: {type(e).__name__}\n"
                    f"  错误信息: {e}\n"
                    f"  建议: 请检查日志获取详细堆栈信息",
                    exc_info=True
                )
                if attempt < retry_count:
                    logger.info(f"⏳ 等待 {retry_delay} 秒后重试...")
                    time.sleep(retry_delay)
                    continue

        logger.error(f"❌ 邮件发送失败（已重试{retry_count}次）: {to} - {subject}")
        return False

    def send_to_multiple(
        self,
        recipients: List[str],
        subject: str,
        content: str
    ) -> Dict[str, bool]:
        """向多个收件人发送邮件

        Args:
            recipients: 收件人列表
            subject: 邮件主题
            content: 邮件内容

        Returns:
            Dict[str, bool]: 每个收件人的发送结果 {email: success}
        """
        results = {}
        for recipient in recipients:
            success = self.send_email(recipient, subject, content)
            results[recipient] = success

        success_count = sum(1 for success in results.values() if success)
        logger.info(
            f"批量发送完成: 成功 {success_count}/{len(recipients)}, "
            f"失败 {len(recipients) - success_count}"
        )

        return results

    def send_alert(
        self,
        alert_type: str,
        title: str,
        details: str,
        metadata: Optional[Dict[str, Any]] = None,
        recipients: Optional[List[str]] = None
    ) -> bool:
        """发送通用报警邮件

        Args:
            alert_type: 报警类型（用于邮件主题）
            title: 报警标题
            details: 报警详细信息
            metadata: 元数据（可选）
            recipients: 收件人列表，如果未指定则使用默认列表

        Returns:
            bool: 是否全部发送成功
        """
        # 格式化邮件内容
        content = format_plain_text(title, details, metadata)

        # 确定收件人
        recipients = self.config.get_recipients(recipients)
        if not recipients:
            logger.error("未指定收件人且未配置默认收件人")
            return False

        # 发送邮件
        subject = f"【{alert_type}】{title}"
        results = self.send_to_multiple(recipients, subject, content)

        # 返回是否全部成功
        return all(results.values())

    def send_error_alert(
        self,
        error: Exception,
        context: Optional[Dict[str, Any]] = None,
        recipients: Optional[List[str]] = None,
        include_traceback: bool = True
    ) -> bool:
        """发送错误报警邮件

        Args:
            error: 异常对象
            context: 错误上下文信息
            recipients: 收件人列表
            include_traceback: 是否包含堆栈跟踪

        Returns:
            bool: 是否发送成功
        """
        # 格式化错误内容
        content = format_error_alert(error, context, include_traceback)

        # 确定收件人
        recipients = self.config.get_recipients(recipients)
        if not recipients:
            logger.error("未指定收件人且未配置默认收件人")
            return False

        # 发送邮件
        error_type = type(error).__name__
        subject = f"【系统错误】{error_type}: {str(error)[:50]}"
        results = self.send_to_multiple(recipients, subject, content)

        return all(results.values())

    def send_resource_alert(
        self,
        resource_type: str,
        resource_name: str,
        current_value: float,
        threshold: float,
        unit: str = "%",
        additional_info: Optional[Dict[str, Any]] = None,
        recipients: Optional[List[str]] = None
    ) -> bool:
        """发送资源使用率告警邮件

        Args:
            resource_type: 资源类型
            resource_name: 资源名称
            current_value: 当前使用值
            threshold: 告警阈值
            unit: 单位
            additional_info: 额外信息
            recipients: 收件人列表

        Returns:
            bool: 是否发送成功
        """
        # 格式化告警内容
        content = format_resource_alert(
            resource_type,
            resource_name,
            current_value,
            threshold,
            unit,
            additional_info
        )

        # 确定收件人
        recipients = self.config.get_recipients(recipients)
        if not recipients:
            logger.error("未指定收件人且未配置默认收件人")
            return False

        # 发送邮件
        subject = f"【资源告警】{resource_type} - {resource_name} 使用率: {current_value:.1f}{unit}"
        results = self.send_to_multiple(recipients, subject, content)

        return all(results.values())

    def send_system_notification(
        self,
        event_type: str,
        event_title: str,
        details: Dict[str, Any],
        severity: str = "info",
        recipients: Optional[List[str]] = None
    ) -> bool:
        """发送系统通知邮件

        Args:
            event_type: 事件类型
            event_title: 事件标题
            details: 事件详情
            severity: 严重程度（info/warning/error/critical）
            recipients: 收件人列表

        Returns:
            bool: 是否发送成功
        """
        # 格式化通知内容
        content = format_system_notification(event_type, event_title, details, severity)

        # 确定收件人
        recipients = self.config.get_recipients(recipients)
        if not recipients:
            logger.error("未指定收件人且未配置默认收件人")
            return False

        # 发送邮件
        severity_prefix = {
            "info": "信息",
            "warning": "警告",
            "error": "错误",
            "critical": "严重"
        }.get(severity, "通知")

        subject = f"【{severity_prefix}】{event_type} - {event_title}"
        results = self.send_to_multiple(recipients, subject, content)

        return all(results.values())

    def send_simple_message(
        self,
        subject: str,
        message: str,
        recipients: Optional[List[str]] = None
    ) -> bool:
        """发送简单消息邮件

        Args:
            subject: 主题
            message: 消息内容
            recipients: 收件人列表

        Returns:
            bool: 是否发送成功
        """
        # 格式化消息
        content = format_simple_message(subject, message)

        # 确定收件人
        recipients = self.config.get_recipients(recipients)
        if not recipients:
            logger.error("未指定收件人且未配置默认收件人")
            return False

        # 发送邮件
        results = self.send_to_multiple(recipients, subject, content)

        return all(results.values())
