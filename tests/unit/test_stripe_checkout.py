"""测试 Stripe Checkout Session 创建"""
import os
from dotenv import load_dotenv

load_dotenv()

# 测试 Stripe 配置
print("=" * 60)
print("环境变量检查")
print("=" * 60)
print(f"STRIPE_SECRET_KEY: {os.getenv('STRIPE_SECRET_KEY', 'NOT SET')[:30]}...")
print(f"FRONTEND_URL: {os.getenv('FRONTEND_URL', 'NOT SET')}")
print()

# 测试 Stripe SDK
try:
    import stripe
    print("✅ Stripe SDK 已安装")
    try:
        print(f"Stripe 版本: {stripe._version.VERSION}")
    except:
        print("Stripe 版本: (无法获取)")
except ImportError as e:
    print(f"❌ Stripe SDK 未安装: {e}")
    exit(1)

# 设置 API Key
stripe.api_key = os.getenv("STRIPE_SECRET_KEY")
if not stripe.api_key:
    print("❌ STRIPE_SECRET_KEY 未设置")
    exit(1)

print()
print("=" * 60)
print("测试 Checkout Session 创建")
print("=" * 60)

# 测试参数
product_name = "高级套餐"
amount = 9900  # 99.00 USD in cents
currency = "usd"
customer_email = "test@example.com"
order_id = "test-order-123"
success_url = "http://localhost:3000/dashboard?session_id={CHECKOUT_SESSION_ID}"
cancel_url = "http://localhost:3000/dashboard"

try:
    # 创建 Checkout Session
    checkout_session = stripe.checkout.Session.create(
        line_items=[{
            'price_data': {
                'currency': currency.lower(),
                'product_data': {
                    'name': product_name,
                },
                'unit_amount': amount,
            },
            'quantity': 1,
        }],
        mode='payment',
        success_url=success_url,
        cancel_url=cancel_url,
        payment_method_types=['card'],
        customer_email=customer_email,
        metadata={
            'order_id': order_id,
            'customer_email': customer_email,
        }
    )

    print("✅ Checkout Session 创建成功!")
    print(f"Session ID: {checkout_session.id}")
    print(f"Checkout URL: {checkout_session.url}")
    print(f"Payment Status: {checkout_session.payment_status}")

except stripe.StripeError as e:
    print(f"❌ Stripe 错误: {e}")
    print(f"错误类型: {type(e).__name__}")
    print(f"错误信息: {str(e)}")
except Exception as e:
    print(f"❌ 未知错误: {e}")
    print(f"错误类型: {type(e).__name__}")
