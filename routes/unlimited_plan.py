"""
无限流量套餐路由 - 基于base_plan抽象基类实现
299元/年无限流量套餐，带宽 20↑/10↓ Mbps，独立网关和域名
"""
from routes.base_plan import create_plan_router, PlanConfig
from loguru import logger
from routes.config_loader import load_plan_config

# 无限流量套餐配置
config = load_plan_config("unlimited")

# 创建路由
router = create_plan_router(config)

logger.info("✅ 无限流量套餐路由初始化完成")
