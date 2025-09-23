#!/usr/bin/env python3
"""
测试订单超时管理功能
"""
import sys
import os
from loguru import logger
import asyncio
import time

# 添加父目录到Python路径
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    from order import OrderConfig
    logger.info("订单模块导入成功")
except ImportError as e:
    logger.error(f"订单模块导入失败: {e}")
    exit(1)

class OrderTimeoutTester:
    """订单超时测试器"""
    
    def __init__(self):
        self.order_config = OrderConfig()
    
    def test_insert_order_with_timeout(self):
        """测试带超时跟踪的订单插入"""
        logger.info("=== 测试带超时跟踪的订单插入 ===")
        try:
            # 使用重构后的insert_order函数（已包含超时跟踪）
            order_id = self.order_config.insert_order(
                product_name="测试产品",
                trade_num=12345,
                amount=100,
                email="test@example.com",
                phone="1234567890"
            )
            logger.info(f"✅ 成功创建带超时跟踪的订单，ID: {order_id}")
            return order_id
        except Exception as e:
            logger.error(f"❌ 创建订单失败: {e}")
            return None
    
    def test_check_timeout_orders(self):
        """测试超时订单检查"""
        logger.info("=== 测试超时订单检查 ===")
        try:
            timeout_count = self.order_config.check_timeout_orders()
            logger.info(f"✅ 处理了 {timeout_count} 个超时订单")
            return timeout_count
        except Exception as e:
            logger.error(f"❌ 检查超时订单失败: {e}")
            return None
    
    def test_process_order_timeouts(self):
        """测试批量处理超时订单"""
        logger.info("=== 测试批量处理超时订单 ===")
        try:
            result = self.order_config.process_order_timeouts()
            logger.info(f"✅ 批量处理结果: {result}")
            return result
        except Exception as e:
            logger.error(f"❌ 批量处理超时订单失败: {e}")
            return None
    
    def test_cleanup_processed_trackers(self):
        """测试清理已处理的跟踪记录"""
        logger.info("=== 测试清理已处理的跟踪记录 ===")
        try:
            deleted_count = self.order_config.cleanup_processed_timeout_trackers(days_old=1)
            logger.info(f"✅ 清理了 {deleted_count} 个已处理的跟踪记录")
            return deleted_count
        except Exception as e:
            logger.error(f"❌ 清理跟踪记录失败: {e}")
            return None
    
    def test_view_timeout_tracker_table(self):
        """查看超时跟踪表内容"""
        logger.info("=== 查看超时跟踪表内容 ===")
        try:
            trackers = self.order_config.get_timeout_tracker_records()
            logger.info(f"✅ 当前跟踪记录数量: {len(trackers)}")
            for tracker in trackers:
                logger.info(f"   - 订单ID: {tracker.get('order_id')}, 检查时间: {tracker.get('check_at')}, 已处理: {tracker.get('processed')}")
            return trackers
        except Exception as e:
            logger.error(f"❌ 查看跟踪表失败: {e}")
            return []
    
    def test_view_orders_with_status(self):
        """查看订单及其状态"""
        logger.info("=== 查看订单及其状态 ===")
        try:
            orders = self.order_config.get_orders_with_status()
            logger.info(f"✅ 当前订单数量: {len(orders)}")
            for order in orders:
                logger.info(f"   - 订单ID: {order.get('id')[:8]}..., 产品: {order.get('product_name')}, 状态: {order.get('status')}, 创建时间: {order.get('created_at')}")
            return orders
        except Exception as e:
            logger.error(f"❌ 查看订单失败: {e}")
            return []

def main():
    """主测试函数"""
    logger.info("开始测试订单超时管理功能")
    
    tester = OrderTimeoutTester()
    
    # 测试步骤
    logger.info("\n" + "="*50)
    logger.info("第1步：创建带超时跟踪的订单")
    order_id = tester.test_insert_order_with_timeout()
    
    if order_id:
        logger.info("\n" + "="*50)
        logger.info("第2步：查看跟踪表内容")
        tester.test_view_timeout_tracker_table()
        
        logger.info("\n" + "="*50)
        logger.info("第3步：查看订单状态")
        tester.test_view_orders_with_status()
        
        logger.info("\n" + "="*50)
        logger.info("第4步：测试超时检查（立即执行，不等待10分钟）")
        tester.test_check_timeout_orders()
        
        logger.info("\n" + "="*50)
        logger.info("第5步：测试批量处理超时订单")
        tester.test_process_order_timeouts()
        
        logger.info("\n" + "="*50)
        logger.info("第6步：再次查看订单状态（验证是否有变化）")
        tester.test_view_orders_with_status()
        
        logger.info("\n" + "="*50)
        logger.info("第7步：测试清理功能")
        tester.test_cleanup_processed_trackers()
    
    logger.info("\n" + "="*50)
    logger.info("🎉 测试完成！")
    
    logger.info("\n" + "="*30 + " 使用说明 " + "="*30)
    logger.info("1. 使用 insert_order() 函数创建订单（自动包含超时跟踪）")
    logger.info("2. 系统会在10分钟后自动检查订单状态")
    logger.info("3. 如果订单仍为'处理中'状态，会自动更新为'已超时'")
    logger.info("4. 使用 process_order_timeouts() 可以手动触发超时检查")
    logger.info("5. 使用 cleanup_processed_timeout_trackers() 清理旧的跟踪记录")

if __name__ == "__main__":
    main()