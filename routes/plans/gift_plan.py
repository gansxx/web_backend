#todo:重构free_plan,去除冗余逻辑同时复用基本类
from fastapi import APIRouter, HTTPException, Response, Request, Cookie,BackgroundTasks
from loguru import logger
from typing import Dict, Any, List
from pydantic import BaseModel

router = APIRouter(tags=["gift_plan"])


def generate_trade_number() -> int:
    """生成交易号，暂时默认返回1"""
    return 1


class FreePlanResponse(BaseModel):
    has_free_plan: bool
    free_plans: List[Dict[str, Any]]
    all_products: List[Dict[str, Any]]


class FreePlanPurchaseRequest(BaseModel):
    phone: str = ""
    plan_id: str = "gift"  # 套餐ID，默认为免费套餐
    plan_name: str = "礼品套餐"  # 套餐名称
    duration_days: int = 90  # 套餐时长，默认30天

@router.post("/user/gift-plan/purchase")
async def purchase_free_plan(
    request: Request,
    response: Response,
    background_tasks: BackgroundTasks,
    purchase_data: FreePlanPurchaseRequest,
    token: str | None = None,
    access_token: str | None = Cookie(default=None),
    refresh_token: str | None = Cookie(default=None),
):
    """购买免费套餐的完整流程（包含内置的免费套餐检查）"""
    supabase = getattr(request.app.state, "supabase", None)
    pd_db = getattr(request.app.state, "pd_db", None)
    do_refresh = getattr(request.app.state, "refresh_session_and_set_cookies", None)

    if not supabase:
        raise HTTPException(500, detail="后端未初始化")
    if not pd_db:
        raise HTTPException(500, detail="数据库未初始化")

    token_to_use = token or access_token
    if not token_to_use:
        raise HTTPException(401, detail="未登录")

    try:
        # 获取用户信息
        try:
            _res = supabase.auth.get_user(token_to_use)
        except Exception as e:
            msg = str(e).lower()
            if refresh_token and ("expired" in msg or "invalid" in msg) and callable(do_refresh):
                logger.info("access_token 失效，尝试 refresh_token 刷新后重试 /user/free-plan/purchase")
                new_at = do_refresh(response, refresh_token)
                if not new_at:
                    raise HTTPException(401, detail="登录已过期，请重新登录")
                _res = supabase.auth.get_user(new_at)
            else:
                raise

        user = getattr(_res, "user", None)
        if not user or not getattr(user, "email", None):
            raise HTTPException(401, detail="未登录或用户无邮箱信息")

        email = user.email
        if not isinstance(email, str) or not email:
            raise HTTPException(401, detail="未登录或用户无邮箱信息")

        logger.info(f"用户 {email} 开始购买套餐: {purchase_data.plan_name}")

        # 1. 检查用户是否已有礼品套餐（仅针对礼品套餐）
        if purchase_data.plan_id == "gift":
            from center_management.db.product import ProductConfig
            product_config = ProductConfig()
            user_products = product_config.fetch_product_user(user_email=email)

            for product in user_products:
                if isinstance(product, dict):
                    product_name = product.get("product_name", "")
                    if product_name and "礼品套餐" in str(product_name).lower():
                        logger.warning(f"用户 {email} 已有礼品套餐，拒绝购买")
                        raise HTTPException(400, detail="您已经拥有礼品套餐，无法重复购买")

        # 2. 生成交易号
        trade_num = generate_trade_number()

        # 3. 插入订单
        from center_management.db.order import OrderConfig
        order_config = OrderConfig()

        try:
            order_id = order_config.insert_order(
                product_name=purchase_data.plan_name,
                trade_num=trade_num,
                amount=0,  # 免费套餐金额为0
                email=email,
                phone=purchase_data.phone,
                payment_provider=purchase_data.plan_id  # 免费套餐标识
            )
            logger.info(f"订单插入成功，订单ID: {order_id}, 支付方式: free")
        except Exception as e:
            logger.error(f"插入订单失败: {e}")
            raise HTTPException(500, detail="创建订单失败")

        #付费套餐在这里插入第三方支付组件
        # 4. 更新订单状态为已支付
        try:
            success = order_config.update_order_status(order_id, "已支付")
            if not success:
                logger.error(f"更新订单状态失败，订单ID: {order_id}")
                raise HTTPException(500, detail="更新订单状态失败")
            logger.info(f"订单状态更新成功，订单ID: {order_id}")
        except Exception as e:
            logger.error(f"更新订单状态失败: {e}")
            raise HTTPException(500, detail="更新订单状态失败")

        # 5. 使用后台任务异步生成订阅链接和产品
        background_tasks.add_task(
                free_product_background,
                order_id=order_id,
                plan_name=purchase_data.plan_name,
                email=email,
                phone=purchase_data.phone,
                duration_days=360
        )

        # 7. 返回成功响应
        return {
            "success": True,
            "message": f"{purchase_data.plan_name}获取成功",
            "order_id": order_id,
            "plan_name": purchase_data.plan_name
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"购买礼品套餐失败: {e}")
        raise HTTPException(500, detail="购买失败")
    
async def free_product_background(
    order_id: str,
    plan_name: str,
    email: str,
    phone: str,
    duration_days: int
):
    """后台任务：异步生成订阅链接和产品数据"""
    try:
        # 导入必要的模块
        from center_management.backend_api_v3 import test_add_user_v3
        from center_management.node_manage import NodeProxy
        from dotenv import load_dotenv
        import os

        # 加载环境变量
        load_dotenv()

        # 获取网关配置 (从环境变量)
        hostname = os.getenv('gateway_ip')
        gateway_user = os.getenv('gateway_user', 'admin')  # 默认为 admin
        if not hostname:
            logger.error("❌ gateway_ip 环境变量未设置")
            raise HTTPException(500, detail="服务器配置错误")

        key_file = 'id_ed25519'

        # 使用NodeProxy连接并生成真实订阅URL
        logger.info(f"[后台任务] 正在为用户 {email} 生成订阅链接... 连接服务器: {hostname}, 用户: {gateway_user}")
        proxy = NodeProxy(hostname, 22, gateway_user, key_file)

        # 调用test_add_user_v3生成订阅URL (使用v3自动端口分配)
        subscription_url = test_add_user_v3(
            proxy,
            name_arg=email,
            url='jiasu.selfgo.asia',
            alias='gift_plan',
            verify_link=True,
            max_retries=1,
            up_mbps=20,
            down_mbps=20,
        )

        if subscription_url:
            logger.info(f"✅ [后台任务] 订阅链接生成成功: {subscription_url}")
        else:
            logger.error(f"❌ [后台任务] 为用户{email}生成订阅链接失败")
            raise HTTPException(500, detail="订阅链接生成失败")

    except Exception as e:
        logger.error(f"[后台任务] 生成订阅链接时发生错误: {e}")
        raise HTTPException(500, detail=f"生成订阅链接时发生错误: {str(e)}")

    logger.info(f"最终订阅链接: {subscription_url}")

    # 6. 调用insert_product插入产品数据
    from center_management.db.product import ProductConfig
    product_config = ProductConfig()
    try:
        product_id = product_config.insert_product(
            product_name=plan_name,
            subscription_url=subscription_url,
            email=email,
            phone=phone,
            duration_days=duration_days
        )
        logger.info(f"产品数据插入成功，产品ID: {product_id}")

        # 更新订单产品状态为"已完成"
        from center_management.db.order import OrderConfig
        order_config = OrderConfig()
        order_config.update_product_status(order_id, "completed")

        logger.info(f"🎉 [后台任务] 订单 {order_id} {plan_name}产品生成完成！")
    except Exception as e:
        logger.error(f"插入产品数据失败: {e}")
        raise HTTPException(500, detail="创建产品失败")
    return 