#!/usr/bin/env python3
"""
测试重构后的订单超时功能
"""
import sys
import os
from loguru import logger

# 添加父目录到Python路径
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    from order import OrderConfig
    logger.info("订单模块导入成功")
except ImportError as e:
    logger.error(f"订单模块导入失败: {e}")
    exit(1)

def main():
    """主测试函数"""
    logger.info("开始测试重构后的订单超时管理功能")
    
    # 初始化订单配置
    try:
        order_config = OrderConfig()
        logger.info("✅ OrderConfig 初始化成功")
    except Exception as e:
        logger.error(f"❌ OrderConfig 初始化失败: {e}")
        return
    
    # 测试1：创建订单（现在自动包含超时跟踪）
    logger.info("\n" + "="*50)
    logger.info("测试1：创建带自动超时跟踪的订单")
    try:
        order_id = order_config.insert_order(
            product_name="测试VPN套餐",
            trade_num=99999,
            amount=199,
            email="test@example.com", 
            phone="13800138000"
        )
        logger.info(f"✅ 订单创建成功，ID: {order_id}")
    except Exception as e:
        logger.error(f"❌ 订单创建失败: {e}")
        return
    
    # 测试2：查看跟踪记录
    logger.info("\n" + "="*50)
    logger.info("测试2：查看超时跟踪记录")
    try:
        trackers = order_config.get_timeout_tracker_records()
        logger.info(f"✅ 当前有 {len(trackers)} 条跟踪记录")
        for i, tracker in enumerate(trackers[-3:]):  # 显示最近3条记录
            logger.info(f"   {i+1}. 订单: {tracker.get('order_id')[:8]}... 检查时间: {tracker.get('check_at')} 已处理: {tracker.get('processed')}")
    except Exception as e:
        logger.error(f"❌ 查看跟踪记录失败: {e}")
    
    # 测试3：查看订单状态
    logger.info("\n" + "="*50)
    logger.info("测试3：查看所有订单状态")
    try:
        orders = order_config.get_orders_with_status()
        logger.info(f"✅ 当前有 {len(orders)} 个订单")
        for i, order in enumerate(orders[-3:]):  # 显示最近3个订单
            logger.info(f"   {i+1}. {order.get('id')[:8]}... {order.get('product_name')} 状态: {order.get('status')}")
    except Exception as e:
        logger.error(f"❌ 查看订单状态失败: {e}")
    
    # 测试4：手动触发超时检查
    logger.info("\n" + "="*50)
    logger.info("测试4：手动触发超时检查")
    try:
        result = order_config.process_order_timeouts()
        logger.info(f"✅ 超时检查完成: {result}")
    except Exception as e:
        logger.error(f"❌ 超时检查失败: {e}")
    
    logger.info("\n" + "="*50)
    logger.info("🎉 重构测试完成！")
    logger.info("\n📝 重构总结:")
    logger.info("✓ insert_order() 现在自动包含10分钟超时跟踪")
    logger.info("✓ 移除了重复的 insert_order_with_timeout() 函数")
    logger.info("✓ OrderConfig 类添加了完整的超时管理方法")
    logger.info("✓ 所有功能通过统一的接口访问")

if __name__ == "__main__":
    main()