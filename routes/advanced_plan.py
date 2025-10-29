"""
高级套餐路由 - 基于base_plan抽象基类实现
99元/年高级套餐，带宽 20↑/10↓ Mbps
"""
from routes.base_plan import create_plan_router, PlanConfig
from loguru import logger

# 高级套餐配置
config = PlanConfig(
    plan_name="高级套餐",
    plan_id="advanced",
    plan_keyword="advanced",
    plan_price_env="ADVANCED_PLAN_PRICE",
    plan_currency_env="ADVANCED_PLAN_CURRENCY",
    gateway_ip_env="advanced_gateway_ip",
    domain_url="advanced.selfgo.asia",
    url_alias="advanced_plan",
    up_mbps=20,
    down_mbps=10,
    duration_days=365
)

# 创建路由
router = create_plan_router(config)

logger.info("✅ 高级套餐路由初始化完成")
