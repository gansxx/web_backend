"""
Stripe 支付 API 路由

提供以下端点：
- POST /stripe/create-payment-intent - 创建支付意图
- POST /stripe/webhook - 接收 Stripe Webhook 回调
- GET /stripe/payment-status/{order_id} - 查询支付状态
"""
#该路由暂时弃用，未来考虑删除

# from typing import Any, Dict

# from fastapi import APIRouter, Request, HTTPException, Header
# from pydantic import BaseModel, EmailStr, Field
# from loguru import logger

# from center_management.db.base_config import BaseConfig
# from payments.stripe_payment import (
#     StripePaymentService,
#     create_payment_session,
# )

# router = APIRouter(prefix="/stripe", tags=["stripe"])


# # ========== Pydantic 模型定义 ==========

# class CreatePaymentIntentRequest(BaseModel):
#     """创建支付意图请求"""
#     product_name: str = Field(..., description="产品名称")
#     trade_num: int = Field(..., description="交易数量")
#     amount: int = Field(..., gt=0, description="金额（分），必须大于0")
#     currency: str = Field(default="usd", description="货币代码（ISO 4217），如 'usd', 'cny'")
#     email: EmailStr = Field(..., description="客户邮箱")
#     phone: str = Field(default="", description="客户手机号")


# class PaymentIntentResponse(BaseModel):
#     """支付意图响应"""
#     success: bool
#     order_id: str = None
#     payment_intent_id: str = None
#     client_secret: str = None
#     customer_id: str = None
#     amount: int = None
#     currency: str = None
#     status: str = None
#     error: str = None


# class PaymentStatusResponse(BaseModel):
#     """支付状态响应"""
#     success: bool
#     order_id: str = None
#     payment_provider: str = None
#     stripe_payment_intent_id: str = None
#     stripe_payment_status: str = None
#     order_status: str = None
#     amount: int = None
#     product_name: str = None
#     created_at: str = None
#     error: str = None


# # ========== API 端点 ==========

# @router.post("/create-payment-intent", response_model=PaymentIntentResponse)
# async def create_payment_intent(request: CreatePaymentIntentRequest) -> PaymentIntentResponse:
#     """
#     创建 Stripe 支付意图

#     流程：
#     1. 在数据库中创建订单记录
#     2. 创建 Stripe Payment Intent
#     3. 更新订单记录关联 Payment Intent ID
#     4. 返回 client_secret 供前端完成支付
#     """
#     try:
#         # 初始化数据库配置
#         db = BaseConfig()

#         # 创建支付会话
#         payment_result = create_payment_session(
#             product_name=request.product_name,
#             amount=request.amount,
#             currency=request.currency,
#             customer_email=request.email,
#             customer_phone=request.phone if request.phone else None,
#             order_id=None  # 暂时不传，稍后更新
#         )

#         if not payment_result.get("success"):
#             logger.error(f"Failed to create Stripe payment session: {payment_result.get('error')}")
#             return PaymentIntentResponse(
#                 success=False,
#                 error=payment_result.get("error", "Failed to create payment session")
#             )

#         # 在数据库中创建订单
#         try:
#             params = {
#                 "p_product_name": request.product_name,
#                 "p_trade_num": request.trade_num,
#                 "p_amount": request.amount,
#                 "p_email": request.email,
#                 "p_phone": request.phone or "",
#                 "p_stripe_payment_intent_id": payment_result["payment_intent_id"],
#                 "p_stripe_customer_id": payment_result.get("customer_id"),
#             }
#             response = db.supabase.rpc("insert_stripe_order", params).execute()
#             order_id = response.data
#             logger.info(f"Created Stripe order in database: {order_id}")

#         except Exception as db_error:
#             logger.error(f"Failed to create order in database: {db_error}")
#             # 尝试取消 Stripe Payment Intent
#             StripePaymentService.cancel_payment_intent(payment_result["payment_intent_id"])
#             return PaymentIntentResponse(
#                 success=False,
#                 error="Failed to create order in database"
#             )

#         # 返回成功响应
#         return PaymentIntentResponse(
#             success=True,
#             order_id=str(order_id),
#             payment_intent_id=payment_result["payment_intent_id"],
#             client_secret=payment_result["client_secret"],
#             customer_id=payment_result.get("customer_id"),
#             amount=payment_result["amount"],
#             currency=payment_result["currency"],
#             status=payment_result["status"]
#         )

#     except Exception as e:
#         logger.error(f"Error in create_payment_intent: {e}")
#         return PaymentIntentResponse(
#             success=False,
#             error=str(e)
#         )


# @router.post("/webhook")
# async def stripe_webhook(
#     request: Request,
#     stripe_signature: str = Header(None, alias="stripe-signature")
# ):
#     """
#     处理 Stripe Webhook 事件

#     重要事件：
#     - payment_intent.succeeded: 支付成功
#     - payment_intent.payment_failed: 支付失败
#     - payment_intent.canceled: 支付取消
#     """
#     if not stripe_signature:
#         logger.error("Missing Stripe signature header")
#         raise HTTPException(status_code=400, detail="Missing signature header")

#     try:
#         # 读取原始请求体
#         payload = await request.body()

#         # 验证 Webhook 签名
#         event = StripePaymentService.verify_webhook_signature(
#             payload=payload,
#             signature=stripe_signature
#         )

#         if not event:
#             logger.error("Invalid webhook signature")
#             raise HTTPException(status_code=400, detail="Invalid signature")

#         # 处理事件
#         event_type = event["type"]
#         event_data = event["data"]["object"]

#         logger.info(f"Processing Stripe webhook event: {event_type}")

#         # 初始化数据库配置
#         db = BaseConfig()

#         # 根据事件类型处理
#         if event_type == "payment_intent.succeeded":
#             # 支付成功
#             payment_intent_id = event_data["id"]
#             await _handle_payment_success(db, payment_intent_id, event_data)

#         elif event_type == "payment_intent.payment_failed":
#             # 支付失败
#             payment_intent_id = event_data["id"]
#             await _handle_payment_failed(db, payment_intent_id, event_data)

#         elif event_type == "payment_intent.canceled":
#             # 支付取消
#             payment_intent_id = event_data["id"]
#             await _handle_payment_canceled(db, payment_intent_id, event_data)

#         elif event_type in ["payment_intent.processing", "payment_intent.requires_action"]:
#             # 支付处理中或需要额外操作
#             payment_intent_id = event_data["id"]
#             await _handle_payment_processing(db, payment_intent_id, event_data)

#         else:
#             logger.info(f"Unhandled event type: {event_type}")

#         return {"success": True, "event_type": event_type}

#     except HTTPException:
#         raise
#     except Exception as e:
#         logger.error(f"Error processing webhook: {e}")
#         raise HTTPException(status_code=500, detail=str(e))


# @router.get("/payment-status/{order_id}", response_model=PaymentStatusResponse)
# async def get_payment_status(order_id: str) -> PaymentStatusResponse:
#     """
#     查询订单支付状态

#     Args:
#         order_id: 订单UUID

#     Returns:
#         订单状态信息
#     """
#     try:
#         db = BaseConfig()

#         # 使用 RPC 函数查询订单（支持动态 schema）
#         response = db.supabase.rpc("get_order_by_id", {
#             "p_order_id": order_id
#         }).execute()

#         if not response.data or len(response.data) == 0:
#             return PaymentStatusResponse(
#                 success=False,
#                 error="Order not found"
#             )

#         order = response.data[0]

#         # 如果是 Stripe 订单，同步最新状态
#         if order.get("payment_provider") == "stripe" and order.get("stripe_payment_intent_id"):
#             payment_intent = StripePaymentService.retrieve_payment_intent(
#                 order["stripe_payment_intent_id"]
#             )
#             if payment_intent:
#                 # 更新数据库状态（如果有变化）
#                 if payment_intent.status != order.get("stripe_payment_status"):
#                     db.supabase.rpc("update_stripe_payment_status", {
#                         "p_stripe_payment_intent_id": payment_intent.id,
#                         "p_stripe_payment_status": payment_intent.status
#                     }).execute()
#                     order["stripe_payment_status"] = payment_intent.status

#         return PaymentStatusResponse(
#             success=True,
#             order_id=order["id"],
#             payment_provider=order.get("payment_provider", "unknown"),
#             stripe_payment_intent_id=order.get("stripe_payment_intent_id"),
#             stripe_payment_status=order.get("stripe_payment_status"),
#             order_status=order.get("status"),
#             amount=order.get("amount"),
#             product_name=order.get("product_name"),
#             created_at=order.get("created_at")
#         )

#     except Exception as e:
#         logger.error(f"Error getting payment status: {e}")
#         return PaymentStatusResponse(
#             success=False,
#             error=str(e)
#         )


# # ========== 辅助函数 ==========

# async def _handle_payment_success(db: BaseConfig, payment_intent_id: str, event_data: Dict[str, Any]):
#     """处理支付成功事件"""
#     try:
#         params = {
#             "p_stripe_payment_intent_id": payment_intent_id,
#             "p_stripe_payment_status": "succeeded",
#             "p_order_status": "已支付"
#         }
#         db.supabase.rpc("update_stripe_payment_status", params).execute()
#         logger.info(f"Updated order status to 'succeeded' for payment_intent: {payment_intent_id}")
#     except Exception as e:
#         logger.error(f"Failed to update payment success status: {e}")


# async def _handle_payment_failed(db: BaseConfig, payment_intent_id: str, event_data: Dict[str, Any]):
#     """处理支付失败事件"""
#     try:
#         params = {
#             "p_stripe_payment_intent_id": payment_intent_id,
#             "p_stripe_payment_status": "payment_failed",
#             "p_order_status": "支付失败"
#         }
#         db.supabase.rpc("update_stripe_payment_status", params).execute()
#         logger.warning(f"Payment failed for payment_intent: {payment_intent_id}")
#     except Exception as e:
#         logger.error(f"Failed to update payment failed status: {e}")


# async def _handle_payment_canceled(db: BaseConfig, payment_intent_id: str, event_data: Dict[str, Any]):
#     """处理支付取消事件"""
#     try:
#         params = {
#             "p_stripe_payment_intent_id": payment_intent_id,
#             "p_stripe_payment_status": "canceled",
#             "p_order_status": "已取消"
#         }
#         db.supabase.rpc("update_stripe_payment_status", params).execute()
#         logger.info(f"Payment canceled for payment_intent: {payment_intent_id}")
#     except Exception as e:
#         logger.error(f"Failed to update payment canceled status: {e}")


# async def _handle_payment_processing(db: BaseConfig, payment_intent_id: str, event_data: Dict[str, Any]):
#     """处理支付处理中事件"""
#     try:
#         status = event_data.get("status", "processing")
#         params = {
#             "p_stripe_payment_intent_id": payment_intent_id,
#             "p_stripe_payment_status": status,
#             "p_order_status": "处理中"
#         }
#         db.supabase.rpc("update_stripe_payment_status", params).execute()
#         logger.info(f"Payment processing for payment_intent: {payment_intent_id}")
#     except Exception as e:
#         logger.error(f"Failed to update payment processing status: {e}")
