#!/usr/bin/env python3
"""
测试订单超时自动执行功能
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
    logger.info("开始测试订单超时自动执行功能")
    
    # 初始化订单配置
    try:
        order_config = OrderConfig()
        logger.info("✅ OrderConfig 初始化成功")
    except Exception as e:
        logger.error(f"❌ OrderConfig 初始化失败: {e}")
        return
    
    # 测试1：检查当前定时任务状态
    logger.info("\n" + "="*60)
    logger.info("测试1：检查当前定时任务状态")
    try:
        jobs = order_config.check_cron_job_status()
        if jobs:
            logger.info(f"✅ 找到 {len(jobs)} 个相关定时任务")
            for job in jobs:
                logger.info(f"   - 任务ID: {job.get('jobid')}")
                logger.info(f"   - 调度表达式: {job.get('schedule')}")
                logger.info(f"   - 执行命令: {job.get('command')}")
                logger.info(f"   - 是否活跃: {job.get('active')}")
        else:
            logger.info("ℹ️  当前没有活跃的定时任务")
    except Exception as e:
        logger.error(f"❌ 检查定时任务状态失败: {e}")
    
    # 测试2：手动执行一次超时检查，验证功能
    logger.info("\n" + "="*60)
    logger.info("测试2：手动执行超时检查以验证功能")
    try:
        result = order_config.process_order_timeouts()
        logger.info(f"✅ 手动检查结果: {result}")
    except Exception as e:
        logger.error(f"❌ 手动超时检查失败: {e}")
    
    logger.info("\n" + "="*60)
    logger.info("🎉 自动执行功能测试完成！")
    
    logger.info("\n" + "="*25 + " 功能说明 " + "="*25)
    logger.info("📋 自动执行功能概述：")
    logger.info("   1. 使用 PostgreSQL pg_cron 扩展实现定时任务")
    logger.info("   2. 每5分钟自动执行 check_timeout_orders() 函数")
    logger.info("   3. 自动将超时订单状态从 '处理中' 更新为 '已超时'")
    logger.info("   4. 定时任务在数据库创建时自动设置，无需手动管理")
    
    logger.info("\n📝 使用方法：")
    logger.info("   • order_config.check_cron_job_status()           # 检查任务状态")
    logger.info("   • order_config.process_order_timeouts()          # 手动执行检查")
    
    logger.info("\n⚠️  注意事项：")
    logger.info("   • 需要数据库管理员启用 pg_cron 扩展")
    logger.info("   • 定时任务在数据库初始化时自动创建，持续运行")
    logger.info("   • 可通过日志监控自动检查的执行情况")

if __name__ == "__main__":
    main()