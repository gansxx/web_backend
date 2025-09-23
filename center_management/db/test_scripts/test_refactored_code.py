#!/usr/bin/env python3
"""
测试重构后的代码结构
"""
import sys
import os
from loguru import logger

# 添加父目录到Python路径
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# 测试导入
try:
    from base_config import BaseConfig
    from order import OrderConfig  
    from product import ProductConfig
    logger.info("所有模块导入成功")
except ImportError as e:
    logger.error(f"模块导入失败: {e}")
    exit(1)

def test_base_config():
    """测试基础配置"""
    logger.info("=== 测试基础配置 ===")
    try:
        base = BaseConfig()
        client = base.get_client()
        logger.info("BaseConfig 初始化成功")
        return True
    except Exception as e:
        logger.error(f"BaseConfig 测试失败: {e}")
        return False

def test_order_config():
    """测试订单配置"""
    logger.info("=== 测试订单配置 ===")
    try:
        order = OrderConfig()
        logger.info("OrderConfig 初始化成功")
        return True
    except Exception as e:
        logger.error(f"OrderConfig 测试失败: {e}")
        return False

def test_product_config():
    """测试产品配置"""
    logger.info("=== 测试产品配置 ===")
    try:
        product = ProductConfig()
        logger.info("ProductConfig 初始化成功")
        return True
    except Exception as e:
        logger.error(f"ProductConfig 测试失败: {e}")
        return False

def main():
    """主测试函数"""
    logger.info("开始测试重构后的代码结构")
    
    tests = [
        ("基础配置测试", test_base_config),
        ("订单配置测试", test_order_config),
        ("产品配置测试", test_product_config),
    ]
    
    passed = 0
    failed = 0
    
    for test_name, test_func in tests:
        logger.info(f"\n运行测试: {test_name}")
        if test_func():
            passed += 1
            logger.info(f"✅ {test_name} 通过")
        else:
            failed += 1
            logger.error(f"❌ {test_name} 失败")
    
    logger.info(f"\n测试总结:")
    logger.info(f"通过: {passed}")
    logger.info(f"失败: {failed}")
    logger.info(f"总计: {passed + failed}")
    
    if failed == 0:
        logger.info("🎉 所有测试通过！重构成功！")
        return 0
    else:
        logger.error("⚠️  有测试失败，请检查代码")
        return 1

if __name__ == "__main__":
    exit(main())