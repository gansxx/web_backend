from base_config import BaseConfig
from loguru import logger
from postgrest.exceptions import APIError

class OrderConfig(BaseConfig):
    """订单数据库配置类"""
    def __init__(self):
        super().__init__()
        logger.info("订单配置初始化成功")
    
    def insert_order(self, product_name: str, trade_num: int, amount: int, email: str, phone: str):
        """插入新订单（包含超时跟踪）"""
        try:
            params = {
                "p_product_name": product_name,
                "p_trade_num": trade_num,
                "p_amount": amount,
                "p_email": email,
                "p_phone": phone
            }
            response = self.supabase.rpc("insert_order", params).execute()
            logger.info(f"插入订单成功，订单ID: {response.data}，已设置10分钟超时跟踪")
            return response.data  # 返回新订单的UUID
        except APIError as e:
            logger.error(f"插入订单失败: {e}")
            raise e
    
    def update_order_status(self, order_id: str, status: str):
        """更新订单状态"""
        try:
            params = {
                "p_id": order_id,
                "p_status": status
            }
            response = self.supabase.rpc("update_order_status", params).execute()
            success = response.data
            if success:
                logger.info(f"更新订单状态成功，订单ID: {order_id}, 新状态: {status}")
            else:
                logger.warning(f"订单状态更新失败，未找到订单ID: {order_id}")
            return success
        except APIError as e:
            logger.error(f"更新订单状态失败: {e}")
            raise e
    
    def fetch_order_user(self, user_email: str = "", phone: str = ""):
        """通过用户邮箱或手机号获取订单信息"""
        try:
            params = {
                "p_user_email": user_email or None,
                "p_phone": phone or None,
            }
            response = self.supabase.rpc("fetch_user_orders", params).execute()
            return response.data or []
        except APIError as e:
            logger.error(f"获取用户订单失败: {e}")
            return []
    
    def check_timeout_orders(self):
        """检查并处理超时订单"""
        try:
            response = self.supabase.rpc("check_timeout_orders").execute()
            timeout_count = response.data
            logger.info(f"处理了 {timeout_count} 个超时订单")
            return timeout_count
        except APIError as e:
            logger.error(f"检查超时订单失败: {e}")
            raise e
    
    def process_order_timeouts(self):
        """批量处理超时订单"""
        try:
            response = self.supabase.rpc("process_order_timeouts").execute()
            result = response.data
            logger.info(f"批量处理超时订单完成: {result.get('message', '未知')}")
            return result
        except APIError as e:
            logger.error(f"批量处理超时订单失败: {e}")
            raise e
    
    def cleanup_processed_timeout_trackers(self, days_old: int = 7):
        """清理已处理的超时跟踪记录"""
        try:
            params = {"p_days_old": days_old}
            response = self.supabase.rpc("cleanup_processed_timeout_trackers", params).execute()
            deleted_count = response.data
            logger.info(f"清理了 {deleted_count} 个已处理的跟踪记录")
            return deleted_count
        except APIError as e:
            logger.error(f"清理跟踪记录失败: {e}")
            raise e
    
    def get_timeout_tracker_records(self):
        """获取所有超时跟踪记录"""
        try:
            response = self.supabase.table("order_timeout_tracker").select("*").execute()
            return response.data or []
        except APIError as e:
            logger.error(f"获取跟踪记录失败: {e}")
            return []
    
    def get_orders_with_status(self, status: str = None):
        """获取订单及其状态"""
        try:
            query = self.supabase.table("order").select("id, product_name, status, created_at, trade_num, amount, email, phone")
            if status:
                query = query.eq("status", status)
            response = query.execute()
            return response.data or []
        except APIError as e:
            logger.error(f"获取订单失败: {e}")
            return []
    
    def check_cron_job_status(self):
        """检查定时任务状态"""
        try:
            response = self.supabase.rpc("check_cron_job_status").execute()
            jobs = response.data or []
            if jobs:
                for job in jobs:
                    logger.info(f"定时任务状态 - ID: {job.get('jobid')}, 调度: {job.get('schedule')}, 活跃: {job.get('active')}")
            else:
                logger.info("没有找到相关的定时任务")
            return jobs
        except APIError as e:
            logger.error(f"检查定时任务状态失败: {e}")
            return []