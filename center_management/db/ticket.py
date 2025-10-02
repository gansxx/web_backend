from center_management.db.base_config import BaseConfig
from loguru import logger
from postgrest.exceptions import APIError
from typing import List, Dict, Any, Optional
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import os


class TicketConfig(BaseConfig):
    """工单数据库配置类"""

    def __init__(self):
        super().__init__()
        logger.info("工单配置初始化成功")

    def insert_ticket(
        self,
        user_email: str,
        subject: str,
        priority: str,
        category: str,
        description: str,
        phone: str = "",
        metadata: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        插入新工单

        Args:
            user_email: 用户邮箱
            subject: 工单标题
            priority: 优先级 (高/中/低)
            category: 工单类别
            description: 工单描述
            phone: 用户电话（可选）
            metadata: 元数据（如 user_agent, ip_address 等）

        Returns:
            str: 新工单的 UUID
        """
        try:
            # 验证 priority 值
            if priority not in ['高', '中', '低']:
                raise ValueError(f"Invalid priority: {priority}. Must be one of: 高, 中, 低")

            params = {
                "p_user_email": user_email,
                "p_subject": subject,
                "p_priority": priority,
                "p_category": category,
                "p_description": description,
                "p_phone": phone,
                "p_metadata": metadata
            }
            response = self.supabase.rpc("insert_ticket", params).execute()
            ticket_id = response.data
            logger.info(f"插入工单成功，工单ID: {ticket_id}, 用户: {user_email}, 优先级: {priority}")
            return ticket_id
        except ValueError as e:
            logger.error(f"工单参数验证失败: {e}")
            raise e
        except APIError as e:
            logger.error(f"插入工单失败: {e}")
            raise e

    def fetch_user_tickets(self, user_email: str) -> List[Dict[str, Any]]:
        """
        获取用户的所有工单

        Args:
            user_email: 用户邮箱

        Returns:
            List[Dict]: 工单列表
        """
        try:
            if not user_email:
                raise ValueError("user_email is required")

            params = {"p_user_email": user_email}
            response = self.supabase.rpc("fetch_user_tickets", params).execute()
            tickets = response.data or []
            logger.info(f"获取用户工单成功，用户: {user_email}, 工单数: {len(tickets)}")
            return tickets
        except ValueError as e:
            logger.error(f"参数验证失败: {e}")
            raise e
        except APIError as e:
            logger.error(f"获取用户工单失败: {e}")
            return []

    def update_ticket_status(
        self,
        ticket_id: str,
        status: str,
        reply: Optional[str] = None
    ) -> bool:
        """
        更新工单状态（可选添加答复）

        Args:
            ticket_id: 工单ID
            status: 新状态 (处理中/已解决)
            reply: 管理员答复内容（可选）

        Returns:
            bool: 是否更新成功
        """
        try:
            # 验证 status 值
            if status not in ['处理中', '已解决']:
                raise ValueError(f"Invalid status: {status}. Must be one of: 处理中, 已解决")

            params = {
                "p_ticket_id": ticket_id,
                "p_status": status,
                "p_reply": reply
            }
            response = self.supabase.rpc("update_ticket_status", params).execute()
            success = response.data
            if success:
                logger.info(f"更新工单状态成功，工单ID: {ticket_id}, 新状态: {status}, 是否包含答复: {reply is not None}")
            else:
                logger.warning(f"工单状态更新失败，未找到工单ID: {ticket_id}")
            return success
        except ValueError as e:
            logger.error(f"状态验证失败: {e}")
            raise e
        except APIError as e:
            logger.error(f"更新工单状态失败: {e}")
            raise e

    def get_ticket_by_id(self, ticket_id: str) -> Optional[Dict[str, Any]]:
        """
        根据工单ID获取工单详情

        Args:
            ticket_id: 工单ID

        Returns:
            Optional[Dict]: 工单详情，如果不存在返回 None
        """
        try:
            params = {"p_ticket_id": ticket_id}
            response = self.supabase.rpc("get_ticket_by_id", params).execute()
            tickets = response.data or []
            if tickets and len(tickets) > 0:
                logger.info(f"获取工单详情成功，工单ID: {ticket_id}")
                return tickets[0]
            else:
                logger.warning(f"工单不存在，工单ID: {ticket_id}")
                return None
        except APIError as e:
            logger.error(f"获取工单详情失败: {e}")
            return None

    def send_ticket_reply_email(
        self,
        user_email: str,
        ticket_subject: str,
        reply_content: str,
        ticket_id: str
    ) -> bool:
        """
        发送工单答复邮件通知

        Args:
            user_email: 用户邮箱
            ticket_subject: 工单标题
            reply_content: 答复内容
            ticket_id: 工单ID

        Returns:
            bool: 是否发送成功
        """
        try:
            # 从环境变量获取 SMTP 配置
            smtp_host = os.getenv('SMTP_HOST', 'localhost')
            smtp_port = int(os.getenv('SMTP_PORT', '25'))
            smtp_user = os.getenv('SMTP_USER', '')
            smtp_pass = os.getenv('SMTP_PASS', '')
            smtp_sender_name = os.getenv('SMTP_SENDER_NAME', '客服支持')
            smtp_admin_email = os.getenv('SMTP_ADMIN_EMAIL', 'support@example.com')
            frontend_url = os.getenv('FRONTEND_URL', 'http://localhost:3000')

            # 创建邮件
            msg = MIMEMultipart('alternative')
            msg['Subject'] = f'您的工单已收到回复 - {ticket_subject}'
            msg['From'] = f'{smtp_sender_name} <{smtp_admin_email}>'
            msg['To'] = user_email

            # 邮件内容（纯文本版本）
            text_content = f"""
尊敬的用户，

您提交的工单「{ticket_subject}」已收到客服回复：

{reply_content}

您可以登录系统查看完整工单详情：
{frontend_url}/support/tickets/{ticket_id}

此致
{smtp_sender_name}
            """.strip()

            # 邮件内容（HTML版本）
            html_content = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <style>
        body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
        .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
        .header {{ background-color: #4CAF50; color: white; padding: 10px; text-align: center; }}
        .content {{ background-color: #f9f9f9; padding: 20px; margin: 20px 0; border-radius: 5px; }}
        .reply {{ background-color: white; padding: 15px; margin: 15px 0; border-left: 4px solid #4CAF50; }}
        .footer {{ text-align: center; color: #666; font-size: 12px; margin-top: 20px; }}
        .button {{ background-color: #4CAF50; color: white; padding: 10px 20px; text-decoration: none; border-radius: 5px; display: inline-block; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h2>工单回复通知</h2>
        </div>
        <div class="content">
            <p>尊敬的用户，</p>
            <p>您提交的工单「<strong>{ticket_subject}</strong>」已收到客服回复：</p>
            <div class="reply">
                {reply_content.replace(chr(10), '<br>')}
            </div>
            <p style="text-align: center; margin-top: 20px;">
                <a href="{frontend_url}/support/tickets/{ticket_id}" class="button">查看工单详情</a>
            </p>
        </div>
        <div class="footer">
            <p>此致<br>{smtp_sender_name}</p>
        </div>
    </div>
</body>
</html>
            """.strip()

            # 添加纯文本和HTML内容
            part1 = MIMEText(text_content, 'plain', 'utf-8')
            part2 = MIMEText(html_content, 'html', 'utf-8')
            msg.attach(part1)
            msg.attach(part2)

            # 发送邮件
            logger.info(f"准备发送工单答复邮件到: {user_email}, SMTP服务器: {smtp_host}:{smtp_port}")

            with smtplib.SMTP(smtp_host, smtp_port, timeout=10) as server:
                # 如果需要认证
                if smtp_user and smtp_pass:
                    server.login(smtp_user, smtp_pass)

                server.send_message(msg)
                logger.info(f"工单答复邮件发送成功: {user_email}")
                return True

        except Exception as e:
            logger.error(f"发送工单答复邮件失败: {e}")
            return False

    def fetch_all_tickets(
        self,
        status: Optional[str] = None,
        priority: Optional[str] = None,
        limit: int = 100,
        offset: int = 0
    ) -> List[Dict[str, Any]]:
        """
        获取所有工单（管理员功能）

        Args:
            status: 筛选状态（可选）
            priority: 筛选优先级（可选）
            limit: 返回数量限制
            offset: 偏移量

        Returns:
            List[Dict]: 工单列表
        """
        try:
            params = {
                "p_status": status,
                "p_priority": priority,
                "p_limit": limit,
                "p_offset": offset
            }
            response = self.supabase.rpc("fetch_all_tickets", params).execute()
            tickets = response.data or []
            logger.info(f"获取所有工单成功，数量: {len(tickets)}, 筛选条件: status={status}, priority={priority}")
            return tickets
        except APIError as e:
            logger.error(f"获取所有工单失败: {e}")
            return []