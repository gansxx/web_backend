"""
免费套餐路由 - 基于base_plan抽象基类实现
30天免费套餐，带宽 8↑/8↓ Mbps

统一格式说明：
- 使用 base_plan.py 的 create_plan_router() 创建路由
- 配置存储在 data/products/free.json
- 支持异步产品生成（不阻塞HTTP请求）
- 通过 is_free=True 标志跳过支付流程
"""
from routes.base_plan import create_plan_router, PlanConfig
from loguru import logger

# 免费套餐配置
config = PlanConfig(
    plan_name="免费套餐",
    plan_id="free",
    plan_keyword="free",
    plan_price_env="FREE_PLAN_PRICE",
    plan_currency_env="FREE_PLAN_CURRENCY",
    gateway_ip_env="gateway_ip",
    domain_url="jiasu.selfgo.asia",
    url_alias="free_plan",
    up_mbps=8,
    down_mbps=8,
    duration_days=30,
    is_free=True  # 关键：标记为免费套餐，跳过支付流程
)

# 创建路由（自动包含所有端点）
# - GET /user/free-plan - 检查用户是否拥有免费套餐
# - GET /user/free-plan/simple - 简化版检查
# - POST /user/free-plan/purchase - 购买免费套餐（异步生成产品）
# - GET /user/order-status/{order_id} - 查询产品生成状态
router = create_plan_router(config)

logger.info("✅ 免费套餐路由初始化完成（统一格式）")
