"""
无限流量套餐路由 - 基于base_plan抽象基类实现
299元/年无限流量套餐，带宽 20↑/10↓ Mbps，独立网关和域名
"""
from routes.base_plan import create_plan_router, PlanConfig
from loguru import logger

# 无限流量套餐配置
config = PlanConfig(
    plan_name="无限流量套餐",
    plan_id="unlimited",
    plan_keyword="unlimited",
    plan_price_env="UNLIMITED_PLAN_PRICE",
    plan_currency_env="UNLIMITED_PLAN_CURRENCY",
    gateway_ip_env="unlimited_gateway_ip",
    domain_url="unlimited.selfgo.asia",
    url_alias="unlimited_plan",
    up_mbps=20,
    down_mbps=10,
    duration_days=365
)

# 创建路由
router = create_plan_router(config)

logger.info("✅ 无限流量套餐路由初始化完成")
