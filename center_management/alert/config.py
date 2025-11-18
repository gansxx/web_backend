"""
alert/config.py - 报警模块配置类

该模块提供报警系统的配置管理，包括SMTP邮件服务器配置。
复用项目中现有的SMTP环境变量配置。
"""

import os
from typing import List, Optional
from email.utils import formataddr
from loguru import logger
from center_management.db.base_config import BaseConfig


class AlertConfig(BaseConfig):
    """报警配置类

    负责管理报警系统的配置，包括：
    - SMTP邮件服务器配置（从环境变量读取）
    - 报警接收人列表
    - 发送者信息
    """

    def __init__(self):
        """初始化报警配置"""
        super().__init__()

        # SMTP服务器配置（从环境变量读取）
        self.smtp_host = os.getenv('SMTP_HOST', 'localhost')
        self.smtp_port = int(os.getenv('SMTP_PORT', '25'))
        self.smtp_user = os.getenv('SMTP_USER', '')
        self.smtp_pass = os.getenv('SMTP_PASS', '')

        # 发送者信息
        self.smtp_sender_name = os.getenv('SMTP_SENDER_NAME', '系统报警')
        self.smtp_admin_email = os.getenv('SMTP_ADMIN_EMAIL', 'admin@example.com')

        # 默认接收人列表（从ADMIN_EMAILS环境变量读取）
        admin_emails_str = os.getenv('ADMIN_EMAILS', '')
        self.default_recipients = [
            email.strip()
            for email in admin_emails_str.split(',')
            if email.strip()
        ]

        # 前端URL（用于邮件中的链接）
        self.frontend_url = os.getenv('FRONTEND_URL', 'http://localhost:3000')

        logger.info(
            f"报警配置初始化成功 - "
            f"SMTP服务器: {self.smtp_host}:{self.smtp_port}, "
            f"发送者: {self.smtp_sender_name} <{self.smtp_admin_email}>, "
            f"默认接收人数: {len(self.default_recipients)}"
        )

    def get_sender_address(self) -> str:
        """获取发送者邮箱地址（带名称格式）

        Returns:
            str: 格式化的发送者地址，如 "系统报警 <admin@example.com>"
                 使用 formataddr 正确编码中文名称以符合RFC标准
        """
        return formataddr((self.smtp_sender_name, self.smtp_admin_email))

    def get_recipients(self, custom_recipients: Optional[List[str]] = None) -> List[str]:
        """获取报警接收人列表

        Args:
            custom_recipients: 自定义接收人列表（可选）

        Returns:
            List[str]: 接收人邮箱列表，如果未指定custom_recipients则返回默认列表
        """
        if custom_recipients:
            return custom_recipients

        if not self.default_recipients:
            logger.warning("未配置默认接收人列表，请检查ADMIN_EMAILS环境变量")

        return self.default_recipients

    def validate_config(self) -> bool:
        """验证配置是否完整

        Returns:
            bool: 配置是否有效
        """
        if not self.smtp_host:
            logger.error("SMTP服务器地址未配置")
            return False

        if not self.smtp_admin_email:
            logger.error("管理员邮箱未配置")
            return False

        if self.smtp_user and not self.smtp_pass:
            logger.warning("已配置SMTP用户名但未配置密码")

        return True
