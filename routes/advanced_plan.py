"""
高级套餐路由 - 基于base_plan抽象基类实现
99元/年高级套餐，带宽 50↑/50↓ Mbps
"""
from routes.base_plan import create_plan_router, PlanConfig
from loguru import logger
from routes.config_loader import load_plan_config

# 高级套餐配置

config = load_plan_config("advanced")

# 创建路由
router = create_plan_router(config)

logger.info("✅ 高级套餐路由初始化完成")
