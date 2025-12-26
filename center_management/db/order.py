from center_management.db.base_config import BaseConfig
from loguru import logger
from postgrest.exceptions import APIError

class OrderConfig(BaseConfig):
    """订单数据库配置类"""
    def __init__(self):
        super().__init__()
        logger.info("订单配置初始化成功")
    
    def insert_order(self, product_name: str, trade_num: int, amount: int, email: str, phone: str, payment_provider: str, subscription_type: str = "one_time"):
        """插入新订单（包含超时跟踪）

        Args:
            product_name: 产品名称
            trade_num: 交易号
            amount: 金额（分）
            email: 用户邮箱
            phone: 用户手机号
            payment_provider: 支付提供商（如：stripe, h5zhifu, free）
            subscription_type: 订单类型（one_time: 一次性购买, subscription: 订阅）
        """
        try:
            params = {
                "p_product_name": product_name,
                "p_trade_num": trade_num,
                "p_amount": amount,
                "p_email": email,
                "p_phone": phone,
                "p_payment_provider": payment_provider,
                "p_subscription_type": subscription_type
            }
            response = self.supabase.rpc("insert_order", params).execute()
            logger.info(f"插入订单成功，订单ID: {response.data}，支付方式: {payment_provider}，类型: {subscription_type}，已设置10分钟超时跟踪")
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
            # 使用 tests schema（从 get_schema_name() 获取）
            query = self.supabase.schema("tests").table("order").select("id, product_name, status, created_at, trade_num, amount, email, phone")
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

    def update_product_status(self, order_id: str, status: str):
        """更新订单的产品生成状态

        Args:
            order_id: 订单ID
            status: 产品状态 (pending/processing/completed/failed)

        Returns:
            bool: 更新是否成功
        """
        try:
            params = {
                "p_order_id": order_id,
                "p_status": status
            }
            response = self.supabase.rpc("update_product_status", params).execute()
            success = response.data
            if success:
                logger.info(f"更新订单产品状态成功，订单ID: {order_id}, 新状态: {status}")
            else:
                logger.warning(f"更新订单产品状态失败，未找到订单ID: {order_id}")
            return success
        except APIError as e:
            logger.error(f"更新订单产品状态失败: {e}")
            raise e

    def get_product_status(self, order_id: str) -> str:
        """获取订单的产品生成状态

        Args:
            order_id: 订单ID

        Returns:
            str: 产品状态 (pending/processing/completed/failed) 或 None
        """
        try:
            params = {"p_order_id": order_id}
            response = self.supabase.rpc("get_product_status", params).execute()
            status = response.data
            if status:
                logger.info(f"获取订单产品状态成功，订单ID: {order_id}, 状态: {status}")
            else:
                logger.warning(f"未找到订单ID: {order_id}")
            return status
        except APIError as e:
            logger.error(f"获取订单产品状态失败: {e}")
            return None

    def get_orders_by_product_status(self, status: str = None, limit: int = 100):
        """根据产品生成状态获取订单列表

        Args:
            status: 产品状态过滤 (可选)
            limit: 返回记录数限制

        Returns:
            list: 订单列表
        """
        try:
            params = {
                "p_status": status,
                "p_limit": limit
            }
            response = self.supabase.rpc("get_orders_by_product_status", params).execute()
            orders = response.data or []
            logger.info(f"获取订单列表成功，状态: {status or 'all'}, 数量: {len(orders)}")
            return orders
        except APIError as e:
            logger.error(f"获取订单列表失败: {e}")
            return []

    def update_payment_info(
        self,
        order_id: str,
        stripe_payment_intent_id: str = None,
        stripe_customer_id: str = None,
        stripe_payment_status: str = None
    ) -> bool:
        """更新订单的支付提供商特定信息

        Args:
            order_id: 订单ID
            stripe_payment_intent_id: Stripe Payment Intent ID (可选)
            stripe_customer_id: Stripe Customer ID (可选)
            stripe_payment_status: Stripe 支付状态 (可选)

        Returns:
            bool: 更新是否成功
        """
        try:
            params = {
                "p_order_id": order_id,
                "p_stripe_payment_intent_id": stripe_payment_intent_id,
                "p_stripe_customer_id": stripe_customer_id,
                "p_stripe_payment_status": stripe_payment_status
            }
            response = self.supabase.rpc("update_order_payment_info", params).execute()
            success = response.data
            if success:
                logger.info(f"更新订单支付信息成功，订单ID: {order_id}, Payment Intent: {stripe_payment_intent_id}")
            else:
                logger.warning(f"更新订单支付信息失败，未找到订单ID: {order_id}")
            return success
        except APIError as e:
            logger.error(f"更新订单支付信息失败: {e}")
            raise e

    def update_checkout_session_id(
        self,
        order_id: str,
        checkout_session_id: str
    ) -> bool:
        """更新订单的 Stripe Checkout Session ID

        使用数据库 RPC 函数 update_order_payment_info() 来更新，
        保持与其他支付信息更新操作的一致性

        Args:
            order_id: 订单ID
            checkout_session_id: Stripe Checkout Session ID

        Returns:
            bool: 更新是否成功
        """
        try:
            # PostgREST 要求显式传递所有参数，即使是 NULL
            params = {
                "p_order_id": order_id,
                "p_stripe_payment_intent_id": None,
                "p_stripe_customer_id": None,
                "p_stripe_payment_status": None,
                "p_stripe_checkout_session_id": checkout_session_id
            }
            response = self.supabase.rpc("update_order_payment_info", params).execute()
            success = response.data

            if success:
                logger.info(f"✅ 订单 {order_id} 的 Checkout Session ID 更新成功: {checkout_session_id}")
            else:
                logger.warning(f"⚠️ 未找到订单ID: {order_id}")

            return success

        except APIError as e:
            logger.error(f"❌ 更新订单 Checkout Session ID 失败: {e}")
            return False

    def get_order_by_checkout_session(
        self,
        checkout_session_id: str,
        user_email: str
    ):
        """根据 Stripe Checkout Session ID 查询订单

        使用数据库 RPC 函数查询，保证跨 schema 访问的一致性

        Args:
            checkout_session_id: Stripe Checkout Session ID
            user_email: 用户邮箱（用于安全验证）

        Returns:
            订单数据字典，如果不存在则返回 None
        """
        try:
            params = {
                "p_checkout_session_id": checkout_session_id,
                "p_user_email": user_email
            }
            response = self.supabase.rpc("get_order_by_checkout_session", params).execute()

            if response.data and len(response.data) > 0:
                order = response.data[0]
                logger.info(f"✅ 找到订单: {order['id']} (Session: {checkout_session_id})")
                return order
            else:
                logger.warning(f"⚠️ 未找到匹配的订单 (Session: {checkout_session_id}, Email: {user_email})")
                return None

        except APIError as e:
            logger.error(f"❌ 查询订单失败: {e}")
            return None