from fastapi import APIRouter, HTTPException, Request, Header, BackgroundTasks
from loguru import logger
import os

# 导入公共的异步产品生成函数
from routes.base_plan import generate_product_background

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


# 注意：generate_product_background 函数现已统一到 routes/base_plan.py 中
# 所有套餐（free, advanced, unlimited）共享同一个异步产品生成函数

