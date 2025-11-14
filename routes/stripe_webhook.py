from fastapi import APIRouter, HTTPException, Request, Header, BackgroundTasks
from loguru import logger
import os

#需要旧函数的多余部分去掉，以及临时文件的清理
# 2.将生成产品的generate_product逻辑单独独立出来管理，以方便兼容未来其他支付方式
router = APIRouter(tags=["webhook_stripe"])
@router.post(f"/webhook/stripe")
async def stripe_webhook_handler(
    request: Request,
    background_tasks: BackgroundTasks,
    stripe_signature: str = Header(None, alias="stripe-signature")
):
    f"""处理Stripe webhook回调 - 支付成功后异步生成产品"""
    if not stripe_signature:
        logger.error("缺少 Stripe 签名头")
        raise HTTPException(400, detail="缺少签名")

    try:
        # 获取原始请求体
        #可以考虑将验证webhook签名处逻辑单独打包成一个函数
        payload = await request.body()

        # 验证webhook签名
        from payments.stripe_payment import StripePaymentService
        event = StripePaymentService.verify_webhook_signature(
            payload=payload,
            signature=stripe_signature
        )

        if not event:
            logger.error("Webhook签名验证失败")
            raise HTTPException(400, detail="签名验证失败")

        event_type = event.get("type")
        logger.info(f"收到Stripe webhook事件: {event_type}")

        # 处理 Checkout Session 完成事件（新增）
        #在这里加入处理具体传入套餐的逻辑，但需要现在base_plan.py中加入获取套餐逻辑
        if event_type == "checkout.session.completed":
            session = event["data"]["object"]
            session_id = session.get("id")
            payment_status = session.get("payment_status")
            metadata = session.get("metadata", {})
            order_id = metadata.get("order_id")
            customer_email = metadata.get("customer_email")
            product_id=metadata.get("product_id")

            logger.info(f"💳 Checkout 支付成功 - Session: {session_id}, Order: {order_id}, Payment Status: {payment_status}")

            # 只有支付状态为 paid 时才处理
            if payment_status != "paid":
                logger.warning(f"⚠️ Checkout Session {session_id} 支付状态不是 paid: {payment_status}")
                return {"status": "received", "message": "支付状态非 paid"}

            if not order_id:
                logger.error(f"Checkout Session {session_id} 缺少 order_id")
                return {"status": "error", "message": "缺少订单ID"}

            # 1. 更新订单支付状态
            from center_management.db.order import OrderConfig
            order_config = OrderConfig()

            try:
                success = order_config.update_order_status(order_id, "已支付")
                if not success:
                    logger.error(f"更新订单状态失败，订单ID: {order_id}")
                    return {"status": "error", "message": "更新订单状态失败"}
                logger.info(f"✅ 订单支付状态更新成功，订单ID: {order_id}")

                # 2. 更新产品生成状态为"生成中"
                order_config.update_product_status(order_id, "processing")
                logger.info(f"📝 订单产品状态更新为: processing")

            except Exception as e:
                logger.error(f"更新订单状态失败: {e}")
                return {"status": "error", "message": str(e)}

            # 3. 添加后台任务生成产品（异步执行，不阻塞webhook响应）
            #这里应该根据product_id来选择具体执行什么任务
            background_tasks.add_task(
                generate_product_background,
                product_id=product_id,
                order_id=order_id,
                customer_email=customer_email,
                customer_phone=""  # Checkout 不需要手机号
            )

            logger.info(f"🚀 已启动后台任务生成产品，订单: {order_id}")

            # 4. 立即返回成功响应给Stripe（< 1秒）
            return {
                "status": "success",
                "message": "支付成功，产品生成中",
                "order_id": order_id
            }
            

        # 处理其他事件类型
        elif event_type == "payment_intent.payment_failed":
            payment_intent = event["data"]["object"]
            payment_intent_id = payment_intent.get("id")
            metadata = payment_intent.get("metadata", {})
            order_id = metadata.get("order_id")

            logger.warning(f"支付失败 - Payment Intent: {payment_intent_id}, Order: {order_id}")

            # 可选：更新订单状态为失败
            if order_id:
                from center_management.db.order import OrderConfig
                order_config = OrderConfig()
                order_config.update_order_status(order_id, "支付失败")

            return {"status": "received", "message": "支付失败事件已接收"}

        else:
            logger.info(f"收到未处理的事件类型: {event_type}")
            return {"status": "received", "message": f"事件 {event_type} 已接收"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"处理webhook失败: {e}")
        raise HTTPException(500, detail=f"处理webhook失败: {str(e)}")
    
async def generate_product_background(
        product_id:str,
        order_id: str,
        customer_email: str,
        customer_phone: str
    ):
        f"""后台任务：生成{product_id}产品"""
        from center_management.db.order import OrderConfig
        from center_management.db.product import ProductConfig
        from center_management.backend_api_v3 import test_add_user_v3
        from center_management.node_manage import NodeProxy
        from routes.base_plan import  PlanConfig
        import json
        from pathlib import Path

        order_config = OrderConfig()
        product_config = ProductConfig()
        
        #依照product_id将产品json加载为对应的config（product_id必须等于文件名）
        try:
            data = Path(__file__).resolve().parent.parent / f'data/products/{product_id}.json'
            with open(data,'r') as f:
                _data=json.load(f)
                config=PlanConfig(**_data)
        except Exception as e:
            logger.error(f"文件名可能不存在,报错:{e}")

        try:
            logger.info(f"🚀 [后台任务] 开始为订单 {order_id} 生成{product_id}产品...")

            # 获取网关配置(不同配置网关不同)
            hostname = config.get_gateway_ip()
            gateway_user = os.getenv('gateway_user', 'admin')
            key_file = 'id_ed25519'

            # 使用NodeProxy连接并生成真实订阅URL
            logger.info(f"正在为用户 {customer_email} 生成{config.plan_name}订阅链接...")
            logger.info(f"连接服务器: {hostname}, 用户: {gateway_user}")
            proxy = NodeProxy(hostname, 22, gateway_user, key_file)

            # 调用test_add_user_v3生成订阅URL
            subscription_url = test_add_user_v3(
                proxy,
                name_arg=customer_email,
                url=config.domain_url,
                alias=config.url_alias,
                verify_link=True,
                max_retries=1,
                up_mbps=config.up_mbps,
                down_mbps=config.down_mbps,
            )

            if not subscription_url:
                raise Exception("订阅链接生成失败")

            logger.info(f"✅ {config.plan_name}订阅链接生成成功: {subscription_url}")

            # 插入产品数据
            product_id = product_config.insert_product(
                product_name=config.plan_name,
                subscription_url=subscription_url,
                email=customer_email,
                phone=customer_phone,
                duration_days=config.duration_days
            )

            logger.info(f"✅ 产品数据插入成功，产品ID: {product_id}")

            # 更新订单产品状态为"已完成"
            order_config.update_product_status(order_id, "completed")

            logger.info(f"🎉 [后台任务] 订单 {order_id} {config.plan_name}产品生成完成！")

        except Exception as e:
            logger.error(f"❌ [后台任务] 订单 {order_id} 产品生成失败: {e}")
            # 更新订单产品状态为"生成失败"
            try:
                order_config.update_product_status(order_id, "failed")
            except Exception as update_error:
                logger.error(f"更新订单产品状态为failed失败: {update_error}")
    
    
