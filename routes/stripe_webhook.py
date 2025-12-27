from fastapi import APIRouter, HTTPException, Request, Header, BackgroundTasks
from loguru import logger
from datetime import datetime
import os

#需要旧函数的多余部分去掉，以及临时文件的清理
# 2.将生成产品的generate_product逻辑单独独立出来管理，以方便兼容未来其他支付方式
router = APIRouter(tags=["webhook_stripe"])

def get_subscription_id_from_invoice(invoice: dict) -> str | None:
    """
    从 invoice 对象中提取 subscription_id

    支持多种 Stripe API 版本：
    - 旧版本: invoice.subscription (顶层字段)
    - 新版本: invoice.parent.subscription_details.subscription
    - 备选: invoice.lines.data[0].parent.subscription_item_details.subscription

    Returns:
        subscription_id 或 None
    """
    # 方法 1: 尝试从顶层获取 (旧版本 API)
    subscription_id = invoice.get("subscription")
    if subscription_id:
        return subscription_id

    # 方法 2: 从 parent.subscription_details 获取 (新版本 API)
    parent = invoice.get("parent", {})
    if parent and parent.get("type") == "subscription_details":
        subscription_details = parent.get("subscription_details", {})
        subscription_id = subscription_details.get("subscription")
        if subscription_id:
            return subscription_id

    # 方法 3: 从 lines 中获取 (备选方案)
    lines = invoice.get("lines", {}).get("data", [])
    if lines:
        first_line_parent = lines[0].get("parent", {})
        if first_line_parent.get("type") == "subscription_item_details":
            sub_item_details = first_line_parent.get("subscription_item_details", {})
            subscription_id = sub_item_details.get("subscription")
            if subscription_id:
                return subscription_id

    return None
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

        # 处理 Checkout Session 完成事件
        if event_type == "checkout.session.completed":
            session = event["data"]["object"]
            session_id = session.get("id")
            mode = session.get("mode")  # 'payment' or 'subscription'
            payment_status = session.get("payment_status")
            metadata = session.get("metadata", {})
            customer_email = metadata.get("customer_email")

            logger.info(f"💳 Checkout completed - Session: {session_id}, Mode: {mode}, Payment Status: {payment_status}")

            # Handle subscription mode
            if mode == "subscription":
                return await handle_subscription_checkout_completed(
                    session, background_tasks
                )

            # Handle one-time payment mode (existing logic)
            order_id = metadata.get("order_id")
            product_id = metadata.get("product_id")

            logger.info(f"💳 One-time payment - Order: {order_id}")

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

        # 处理订阅更新事件
        elif event_type == "customer.subscription.updated":
            subscription = event["data"]["object"]
            return await handle_subscription_updated(subscription)

        # 处理订阅删除/取消事件
        elif event_type == "customer.subscription.deleted":
            subscription = event["data"]["object"]
            return await handle_subscription_deleted(subscription)

        # 处理续费成功事件
        elif event_type == "invoice.paid":
            invoice = event["data"]["object"]

            # 使用辅助函数获取 subscription_id（支持多种 Stripe API 版本）
            subscription_id = get_subscription_id_from_invoice(invoice)
            billing_reason = invoice.get("billing_reason")
            customer_email = invoice.get("customer_email")

            # 添加详细日志
            logger.info(f"📧 Invoice.paid event - subscription_id: {subscription_id}, billing_reason: {billing_reason}, customer: {customer_email}")

            if subscription_id:
                logger.debug("进行订阅续期")
                return await handle_invoice_paid(invoice, background_tasks)
            else:
                logger.warning(f"⚠️ Invoice.paid 事件但无 subscription_id - 可能是一次性支付发票")
                return {"status": "received", "message": "Non-subscription invoice"}

        # 处理续费失败事件
        elif event_type == "invoice.payment_failed":
            invoice = event["data"]["object"]
            subscription_id = invoice.get("subscription")
            if subscription_id:
                return await handle_invoice_payment_failed(invoice)
            return {"status": "received", "message": "Non-subscription invoice"}
            

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
        from routes.plans.base_plan import  PlanConfig
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


# =====================================================
# Subscription Event Handlers
# =====================================================

async def handle_subscription_checkout_completed(session: dict, background_tasks):
    """
    Handle subscription checkout completion

    This is triggered when user completes subscription checkout with card binding.
    For trial subscriptions, payment_status may be 'no_payment_required'.

    新流程：
    1. 通过 checkout_session_id 查找并更新订单状态
    2. 创建 subscription 记录
    3. 生成产品
    """
    session_id = session.get("id")
    subscription_id = session.get("subscription")
    customer_id = session.get("customer")
    customer_email = session.get("customer_email") or session.get("customer_details", {}).get("email")
    metadata = session.get("metadata", {})
    plan_id = metadata.get("plan_id", "monthly_subscription")
    order_id = metadata.get("order_id")  # 从 metadata 获取订单ID

    logger.info(f"📦 Subscription checkout completed - Session: {session_id}, Subscription: {subscription_id}, Order: {order_id}")

    if not subscription_id:
        logger.error(f"Subscription ID missing in checkout session {session_id}")
        return {"status": "error", "message": "Subscription ID missing"}

    if not customer_email:
        logger.error(f"Customer email missing in checkout session {session_id}")
        return {"status": "error", "message": "Customer email missing"}

    # 新增：更新订单状态
    if order_id:
        from center_management.db.order import OrderConfig
        order_config = OrderConfig()
        try:
            # 更新订单支付状态
            success = order_config.update_order_status(order_id, "已支付")
            if success:
                logger.info(f"✅ 订阅订单支付状态更新成功，订单ID: {order_id}")
                # 更新产品生成状态为"生成中"
                order_config.update_product_status(order_id, "processing")
            else:
                logger.warning(f"⚠️ 订阅订单状态更新失败，未找到订单ID: {order_id}")
        except Exception as e:
            logger.error(f"更新订阅订单状态失败: {e}")
            # 不阻断流程，继续处理订阅
    else:
        logger.warning(f"⚠️ Subscription checkout session {session_id} 未关联订单ID")

    try:
        # Retrieve full subscription details from Stripe
        from payments.stripe_subscription import StripeSubscriptionService
        subscription = StripeSubscriptionService.get_subscription(subscription_id)

        if not subscription:
            logger.error(f"Failed to retrieve subscription {subscription_id}")
            return {"status": "error", "message": "Failed to retrieve subscription"}

        # DEBUG: Log the subscription type and structure
        # import json
        # logger.info(f"🔍 DEBUG - Subscription type: {type(subscription)}")
        # logger.info(f"🔍 DEBUG - Subscription dict keys: {list(dict(subscription).keys())}")

        # Convert to dict for easier access
        sub_dict = dict(subscription)
        # logger.info(f"🔍 DEBUG - Subscription data: {json.dumps(sub_dict, indent=2, default=str)}")

        # Extract subscription details - use dict-style access for compatibility
        status = sub_dict.get("status", "incomplete")

        # Extract timestamps - check for None specifically, not falsy values (0 is a valid timestamp!)
        current_period_start_ts = sub_dict.get("current_period_start")
        current_period_end_ts = sub_dict.get("current_period_end")
        trial_start_ts = sub_dict.get("trial_start")
        trial_end_ts = sub_dict.get("trial_end")

        # Check if timestamps are None (not just falsy, since 0 is a valid timestamp)
        if current_period_start_ts is None or current_period_end_ts is None:
            # For trial subscriptions, use trial period as current period
            if trial_start_ts is not None and trial_end_ts is not None:
                logger.info(f"⚠️ Using trial period as current period for trialing subscription")
                current_period_start_ts = trial_start_ts
                current_period_end_ts = trial_end_ts
            else:
                logger.error(f"❌ Missing ALL period timestamps in subscription {subscription_id}")
                logger.error(f"Available keys: {list(sub_dict.keys())}")
                return {"status": "error", "message": "Invalid subscription data - missing period timestamps"}

        # Convert timestamps
        current_period_start = datetime.fromtimestamp(current_period_start_ts)
        current_period_end = datetime.fromtimestamp(current_period_end_ts)
        trial_start = datetime.fromtimestamp(trial_start_ts) if trial_start_ts else None
        trial_end = datetime.fromtimestamp(trial_end_ts) if trial_end_ts else None

        logger.info(f"📅 Period: {current_period_start} → {current_period_end}")
        logger.info(f"🎁 Trial: {trial_start} → {trial_end}")

        # Safely extract price_id
        price_id = ""
        items = sub_dict.get("items", {})
        if items and items.get("data") and len(items.get("data", [])) > 0:
            price_id = items["data"][0].get("price", {}).get("id", "")

        logger.info(f"💰 Price ID: {price_id}")

        # Ensure customer_id is valid
        if not customer_id:
            logger.error(f"Missing customer_id in checkout session {session_id}")
            return {"status": "error", "message": "Missing customer ID"}

        # Insert subscription record into database
        from center_management.db.subscription import get_subscription_config
        sub_config = get_subscription_config()

        sub_config.insert_subscription(
            user_email=customer_email,
            stripe_customer_id=customer_id,
            stripe_subscription_id=subscription_id,
            stripe_price_id=price_id,
            status=status,
            current_period_start=current_period_start,
            current_period_end=current_period_end,
            trial_start=trial_start,
            trial_end=trial_end,
            plan_id=plan_id,
            metadata=metadata
        )

        logger.info(f"✅ Subscription record created: {subscription_id} for {customer_email}")

        # Generate product in background
        background_tasks.add_task(
            generate_subscription_product_background,
            subscription_id=subscription_id,
            customer_email=customer_email,
            plan_id=plan_id,
            order_id=order_id
        )

        logger.info(f"🚀 Background task started for subscription product generation")

        return {
            "status": "success",
            "message": "Subscription created",
            "subscription_id": subscription_id
        }

    except Exception as e:
        logger.error(f"Error handling subscription checkout: {e}")
        return {"status": "error", "message": str(e)}


async def handle_subscription_updated(subscription: dict):
    """Handle subscription update events (status change, renewal, cancellation, etc.)"""
    subscription_id = subscription.get("id")
    status = subscription.get("status")
    cancel_at_period_end = subscription.get("cancel_at_period_end", False)
    current_period_start_ts = subscription.get("current_period_start")
    current_period_end_ts = subscription.get("current_period_end")

    # Extract cancellation information
    cancel_at_ts = subscription.get("cancel_at")
    cancellation_details = subscription.get("cancellation_details")

    logger.info(f"🔄 Subscription updated: {subscription_id} -> status: {status}, cancel_at_period_end: {cancel_at_period_end}")

    # Log cancellation information if present
    if cancel_at_ts:
        logger.info(f"⚠️ Subscription scheduled to cancel at: {datetime.fromtimestamp(cancel_at_ts)}")
    if cancellation_details:
        logger.info(f"📝 Cancellation details: {cancellation_details}")

    if not subscription_id or not status:
        logger.error("Missing required subscription data")
        return {"status": "error", "message": "Invalid subscription data"}

    try:
        from center_management.db.subscription import get_subscription_config
        sub_config = get_subscription_config()

        # Prepare cancellation parameters
        cancel_at = datetime.fromtimestamp(cancel_at_ts) if cancel_at_ts else None

        # Only save cancellation_details if cancel_at is not null (user is canceling)
        details_to_save = None
        if cancel_at and cancellation_details:
            details_to_save = cancellation_details
            logger.info(f"💾 Saving cancellation feedback: {details_to_save}")

        # Update subscription in database
        sub_config.update_subscription_status(
            stripe_subscription_id=subscription_id,
            status=status,
            current_period_start=datetime.fromtimestamp(current_period_start_ts) if current_period_start_ts else None,
            current_period_end=datetime.fromtimestamp(current_period_end_ts) if current_period_end_ts else None,
            cancel_at_period_end=cancel_at_period_end,
            cancel_at=cancel_at,
            cancellation_details=details_to_save
        )

        logger.info(f"✅ Subscription {subscription_id} updated in database")

        return {"status": "success", "message": "Subscription updated"}

    except Exception as e:
        logger.error(f"Error updating subscription: {e}")
        return {"status": "error", "message": str(e)}


async def handle_subscription_deleted(subscription: dict):
    """Handle subscription deletion/cancellation events"""
    subscription_id = subscription.get("id")
    ended_at_ts = subscription.get("ended_at")

    logger.info(f"❌ Subscription deleted/canceled: {subscription_id}")

    if not subscription_id:
        logger.error("Missing subscription_id in deletion event")
        return {"status": "error", "message": "Invalid subscription data"}

    try:
        from center_management.db.subscription import get_subscription_config
        sub_config = get_subscription_config()

        # Update subscription status to canceled
        sub_config.update_subscription_status(
            stripe_subscription_id=subscription_id,
            status="canceled",
            ended_at=datetime.fromtimestamp(ended_at_ts) if ended_at_ts else datetime.now()
        )

        logger.info(f"✅ Subscription {subscription_id} marked as canceled")

        # TODO: Optionally deactivate user's product/service here

        return {"status": "success", "message": "Subscription canceled"}

    except Exception as e:
        logger.error(f"Error handling subscription deletion: {e}")
        return {"status": "error", "message": str(e)}


async def handle_invoice_paid(invoice: dict, background_tasks):
    """Handle successful invoice payment (subscription renewal)"""

    # 使用辅助函数获取 subscription_id（支持多种 Stripe API 版本）
    subscription_id = get_subscription_id_from_invoice(invoice)
    customer_email = invoice.get("customer_email")
    billing_reason = invoice.get("billing_reason")  # 'subscription_cycle', 'subscription_create', etc.

    logger.info(f"💰 Invoice paid for subscription {subscription_id}, reason: {billing_reason}")

    # Skip if this is the initial subscription creation (already handled)
    if billing_reason == "subscription_create":
        logger.info(f"Skipping subscription_create invoice - already handled in checkout")
        return {"status": "received", "message": "Initial invoice, already handled"}

    if not subscription_id:
        logger.error("Missing subscription_id in invoice")
        return {"status": "error", "message": "Invalid invoice data"}

    try:
        from center_management.db.subscription import get_subscription_config
        sub_config = get_subscription_config()

        # 优先从 invoice 中获取 period 信息（避免额外 API 调用）
        # invoice.lines.data[0].period 包含订阅周期信息
        current_period_start_ts = None
        current_period_end_ts = None

        # 方法 1: 从 invoice lines 中获取订阅周期
        lines = invoice.get("lines", {}).get("data", [])
        if lines:
            period = lines[0].get("period", {})
            current_period_start_ts = period.get("start")
            current_period_end_ts = period.get("end")
            logger.info(f"📅 Period from invoice lines: {current_period_start_ts} → {current_period_end_ts}")

        # 方法 2: 如果 lines 中没有，尝试从 Stripe API 获取订阅详情
        if not current_period_start_ts or not current_period_end_ts:
            logger.info(f"📞 Fetching subscription details from Stripe API...")
            from payments.stripe_subscription import StripeSubscriptionService
            subscription = StripeSubscriptionService.get_subscription(subscription_id)

            if subscription:
                # Use dict-style access for compatibility
                current_period_start_ts = subscription.get("current_period_start")
                current_period_end_ts = subscription.get("current_period_end")
                logger.info(f"📅 Period from Stripe API: {current_period_start_ts} → {current_period_end_ts}")

        if current_period_start_ts and current_period_end_ts:
            current_period_start = datetime.fromtimestamp(current_period_start_ts)
            current_period_end = datetime.fromtimestamp(current_period_end_ts)

            sub_config.update_subscription_status(
                stripe_subscription_id=subscription_id,
                status="active",
                current_period_start=current_period_start,
                current_period_end=current_period_end
            )

            logger.info(f"✅ Subscription {subscription_id} renewed until {current_period_end}")

            # For subscription renewal (not initial creation), extend user expiration
            if billing_reason == "subscription_cycle":
                logger.info(f"🔄 This is a renewal event, extending user expiration...")
                background_tasks.add_task(
                    extend_subscription_product,
                    subscription_id=subscription_id,
                    customer_email=customer_email
                )
                logger.info(f"🚀 Background task started for subscription renewal")
        else:
            logger.warning(f"Missing period timestamps in subscription {subscription_id}")

        return {"status": "success", "message": "Renewal processed"}

    except Exception as e:
        logger.error(f"Error handling invoice paid: {e}")
        return {"status": "error", "message": str(e)}


async def handle_invoice_payment_failed(invoice: dict):
    """Handle failed invoice payment"""
    subscription_id = invoice.get("subscription")
    attempt_count = invoice.get("attempt_count", 0)

    logger.warning(f"⚠️ Invoice payment failed for subscription {subscription_id}, attempt: {attempt_count}")

    if not subscription_id:
        logger.error("Missing subscription_id in failed invoice")
        return {"status": "error", "message": "Invalid invoice data"}

    try:
        from center_management.db.subscription import get_subscription_config
        sub_config = get_subscription_config()

        # Update subscription status to past_due
        sub_config.update_subscription_status(
            stripe_subscription_id=subscription_id,
            status="past_due"
        )

        logger.info(f"Subscription {subscription_id} marked as past_due")

        # TODO: Optionally send email notification to user

        return {"status": "received", "message": "Payment failure recorded"}

    except Exception as e:
        logger.error(f"Error handling payment failure: {e}")
        return {"status": "error", "message": str(e)}


async def extend_subscription_product(
    subscription_id: str,
    customer_email: str
):
    """Background task: Extend user expiration for subscription renewal"""
    from center_management.db.subscription import get_subscription_config
    from center_management.backend_api_v3 import update_user
    from center_management.node_manage import NodeProxy
    from pathlib import Path
    import json

    try:
        logger.info(f"🚀 [Background] Extending subscription for {subscription_id}...")

        # Step 1: Get subscription info from database
        sub_config = get_subscription_config()
        subscription = sub_config.get_subscription_by_stripe_id(subscription_id)

        if not subscription:
            logger.error(f"Subscription {subscription_id} not found in database")
            return

        plan_id = subscription.get('plan_id')
        logger.info(f"Subscription plan: {plan_id}")

        # Get unique_name for renewal (fallback to customer_email if not available)
        unique_name = subscription.get('unique_name')
        if unique_name:
            logger.info(f"Using unique_name for renewal: {unique_name}")
        else:
            logger.warning(f"No unique_name found for subscription {subscription_id}, falling back to customer_email")
            unique_name = customer_email

        # Step 2: Load plan configuration to get duration_days
        data_path = Path(__file__).resolve().parent.parent / f'data/products/subscription/{plan_id}.json'

        if not data_path.exists():
            logger.error(f"Product config not found: {data_path}")
            return

        with open(data_path, 'r') as f:
            config_data = json.load(f)

        duration_days = config_data.get('duration_days', 30)
        logger.info(f"Extending by {duration_days} days")

        # Step 3: Get gateway configuration
        hostname = config_data.get('gateway_ip') or os.getenv('gateway_ip')
        gateway_user = os.getenv('gateway_user', 'admin')
        key_file = 'id_ed25519'

        logger.info(f"Connecting to server: {hostname}, user: {gateway_user}")

        # Step 4: Connect to remote server
        proxy = NodeProxy(hostname, 22, gateway_user, key_file)

        # Step 5: Call update_user to extend expiration using unique_name
        result = update_user(
            proxy,
            name_arg=unique_name,
            days=duration_days,
            max_retries=3
        )

        if not result:
            logger.error(f"❌ Failed to extend subscription for {unique_name}")
            # Optional: Update subscription status or send notification
            return

        logger.info(f"✅ Extended subscription for {unique_name}")
        logger.info(f"  Old expiration: {result.get('old_expires_date', 'N/A')}")
        logger.info(f"  New expiration: {result.get('new_expires_date', 'N/A')}")
        logger.info(f"  Days extended: {result.get('days_extended', duration_days)}")

        logger.info(f"🎉 [Background] Subscription {subscription_id} renewal completed!")

    except Exception as e:
        logger.error(f"❌ [Background] Failed to extend subscription: {e}")
        logger.exception("Detailed error:")


async def generate_subscription_product_background(
    subscription_id: str,
    customer_email: str,
    plan_id: str,
    order_id: str | None = None
):
    """Background task: Generate product for new subscription"""
    from center_management.db.subscription import get_subscription_config
    from center_management.db.product import ProductConfig
    from center_management.db.order import OrderConfig
    from center_management.backend_api_v3 import add_user_subscription
    from center_management.node_manage import NodeProxy
    from routes.plans.base_plan import PlanConfig, SubscriptionPlanConfig
    import json
    from pathlib import Path

    sub_config = get_subscription_config()
    product_config = ProductConfig()
    order_config = OrderConfig() if order_id else None

    try:
        logger.info(f"🚀 [Background] Generating product for subscription {subscription_id}...")

        # Load product configuration from JSON (优先从 subscription 子目录加载)
        base_path = Path(__file__).resolve().parent.parent / 'data/products'
        # 尝试从 subscription 子目录加载
        data_path = base_path / f'subscription/{plan_id}.json'
        if not data_path.exists():
            # 回退到根目录（兼容旧配置）
            data_path = base_path / f'{plan_id}.json'

        if not data_path.exists():
            logger.error(f"Product config not found: {data_path}")
            if order_config and order_id:
                order_config.update_product_status(order_id, "failed")
            return

        with open(data_path, 'r') as f:
            _data = json.load(f)
            # 根据配置文件内容选择合适的配置类
            # 如果包含 stripe_price_id_env 字段，说明是订阅套餐
            if 'stripe_price_id_env' in _data:
                config = SubscriptionPlanConfig(**_data)
                logger.debug(f"config.gateway_ip_env是:{config.gateway_ip_env}")
            else:
                config = PlanConfig(**_data)

        # Get gateway configuration
        hostname = config.get_gateway_ip()
        gateway_user = os.getenv('gateway_user', 'admin')
        key_file = 'id_ed25519'

        # Connect and generate subscription URL
        logger.info(f"Connecting to server: {hostname}, user: {gateway_user}")
        proxy = NodeProxy(hostname, 22, gateway_user, key_file)

        subscription_url, unique_name = add_user_subscription(
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
            raise Exception("Failed to generate subscription URL")

        logger.info(f"✅ Subscription URL generated: {subscription_url}")
        logger.info(f"✅ Unique name: {unique_name}")

        # Insert product data
        new_product_id = product_config.insert_product(
            product_name=config.plan_name,
            subscription_url=subscription_url,
            email=customer_email,
            phone="",
            duration_days=config.duration_days
        )

        logger.info(f"✅ Product inserted: {new_product_id}")

        # Update subscription with product_id and unique_name
        sub_config.update_subscription_product_with_unique_name(
            stripe_subscription_id=subscription_id,
            product_id=new_product_id,
            unique_name=unique_name
        )

        # 更新订单产品状态为"已完成"
        if order_config and order_id:
            order_config.update_product_status(order_id, "completed")
            logger.info(f"✅ 订单 {order_id} 产品状态更新为 completed")

        logger.info(f"🎉 [Background] Subscription {subscription_id} product generation completed!")

    except Exception as e:
        logger.error(f"❌ [Background] Failed to generate subscription product: {e}")
        # 更新订单产品状态为"失败"
        if order_config and order_id:
            try:
                order_config.update_product_status(order_id, "failed")
                logger.info(f"⚠️ 订单 {order_id} 产品状态更新为 failed")
            except Exception as update_error:
                logger.error(f"更新订单产品状态失败: {update_error}")

