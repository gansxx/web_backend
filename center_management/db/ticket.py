from center_management.db.base_config import BaseConfig
from loguru import logger
from postgrest.exceptions import APIError
from typing import List, Dict, Any, Optional


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

    def update_ticket_status(self, ticket_id: str, status: str) -> bool:
        """
        更新工单状态

        Args:
            ticket_id: 工单ID
            status: 新状态 (处理中/已解决)

        Returns:
            bool: 是否更新成功
        """
        try:
            # 验证 status 值
            if status not in ['处理中', '已解决']:
                raise ValueError(f"Invalid status: {status}. Must be one of: 处理中, 已解决")

            params = {
                "p_ticket_id": ticket_id,
                "p_status": status
            }
            response = self.supabase.rpc("update_ticket_status", params).execute()
            success = response.data
            if success:
                logger.info(f"更新工单状态成功，工单ID: {ticket_id}, 新状态: {status}")
            else:
                logger.warning(f"工单状态更新失败，未找到工单ID: {ticket_id}")
            return success
        except ValueError as e:
            logger.error(f"状态验证失败: {e}")
            raise e
        except APIError as e:
            logger.error(f"更新工单状态失败: {e}")
            raise e

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