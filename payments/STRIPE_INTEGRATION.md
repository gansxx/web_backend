# Stripe 支付集成指南

本文档详细说明如何在 Supabase + FastAPI 后端中使用 Stripe 支付。

## 概览

- **支付方式**: 与现有 h5zhifu (支付宝/微信) 并存
- **支持功能**: 一次性支付、**月度订阅**、Webhook 回调、客户管理
- **支付提供商**: Stripe (国际支付) + h5zhifu (中国支付)

### 支付模式对比

| 功能 | 一次性支付 | 月度订阅 |
|------|-----------|---------|
| 计费模式 | 单次扣款 | 自动续费 |
| 试用期 | 不支持 | 30天免费（需绑卡） |
| 取消策略 | 不适用 | 周期结束生效 |
| 退款 | 支持 | 不支持 |
| 适用场景 | 流量包、一次性购买 | 月度会员 |

## 架构设计

### 一次性支付架构
```
┌─────────────┐
│   前端      │  Stripe.js + Payment Element
└──────┬──────┘
       │
       │ POST /stripe/create-payment-intent
       │ GET  /stripe/payment-status/{order_id}
       ▼
┌─────────────────────────────────┐
│  FastAPI Backend (Port 8001)    │
│  ┌──────────────────────────┐   │
│  │  routes/stripe_routes.py │   │
│  └────────┬─────────────────┘   │
│           │                      │
│  ┌────────▼──────────────────┐  │
│  │ payments/stripe_payment.py│  │
│  │ payments/payment_factory.py│ │
│  └────────┬──────────────────┘  │
│           │                      │
│  ┌────────▼──────────────────┐  │
│  │  Supabase Database        │  │
│  │  - order table            │  │
│  │  - order_timeout_tracker  │  │
│  └───────────────────────────┘  │
└─────────────────────────────────┘
       ▲
       │ POST /stripe/webhook
       │
┌──────┴──────┐
│   Stripe    │  Payment Intent Events
└─────────────┘
```

### 订阅支付架构
```
┌─────────────┐
│   前端      │  用户点击订阅
└──────┬──────┘
       │
       │ POST /subscription/purchase
       ▼
┌─────────────────────────────────────────────────────┐
│  FastAPI Backend (Port 8001)                        │
│  ┌────────────────────────────────────────────┐     │
│  │  routes/plans/subscription_plan.py         │     │
│  │  - /subscription/purchase (创建checkout)   │     │
│  │  - /subscription/status (查询状态)         │     │
│  │  - /subscription/cancel (取消订阅)         │     │
│  │  - /subscription/portal (客户门户)         │     │
│  └────────┬───────────────────────────────────┘     │
│           │                                          │
│  ┌────────▼───────────────────────────────────┐     │
│  │ payments/stripe_subscription.py            │     │
│  │ center_management/db/subscription.py       │     │
│  └────────┬───────────────────────────────────┘     │
│           │                                          │
│  ┌────────▼───────────────────────────────────┐     │
│  │  Supabase Database                         │     │
│  │  - subscription 表                         │     │
│  │  - order 表 (stripe_subscription_id)       │     │
│  └────────────────────────────────────────────┘     │
└─────────────────────────────────────────────────────┘
       ▲
       │ POST /stripe/webhook
       │ (Subscription Events)
       │
┌──────┴──────┐
│   Stripe    │
│  - checkout.session.completed (subscription)
│  - customer.subscription.updated
│  - customer.subscription.deleted
│  - invoice.paid
│  - invoice.payment_failed
└─────────────┘
```

## 文件结构

```
web_backend/
├── docs/
│   └── WEBHOOK_LOCAL_TESTING.md           # Webhook 本地测试详细指南
├── scripts/
│   ├── start_stripe_webhook.sh            # 启动 webhook 转发
│   └── test_stripe_webhook_trigger.sh     # 触发测试事件
├── payments/
│   ├── h5zhifu.py                # 现有中国支付网关
│   ├── stripe_payment.py         # Stripe 一次性支付模块
│   ├── stripe_subscription.py    # 🆕 Stripe 订阅支付模块
│   └── payment_factory.py        # 支付工厂路由器
├── routes/
│   ├── stripe_routes.py          # Stripe 一次性支付 API
│   ├── stripe_webhook.py         # Stripe Webhook 处理（含订阅事件）
│   └── plans/
│       └── subscription_plan.py  # 🆕 订阅 API 端点
├── center_management/
│   └── db/
│       └── subscription.py       # 🆕 订阅数据库操作
├── data/products/
│   └── monthly_subscription.json # 🆕 订阅产品配置
├── supabase/migrations/
│   ├── 12_stripe_integration.sql          # 一次性支付数据库迁移
│   └── 20251225120000_subscription_tables.sql  # 🆕 订阅数据库迁移
├── test_stripe_payment.py        # 集成测试脚本
├── .env                          # 环境配置（包含 Stripe 密钥）
└── STRIPE_INTEGRATION.md         # 本文档
```

## 快速开始

### 1. 安装依赖

```bash
uv sync
```

依赖已自动添加到 `pyproject.toml`:
- `stripe>=11.3.0`

### 2. 配置 Stripe API 密钥

在 `.env` 文件中配置 Stripe 密钥：

```bash
# Stripe Payment Configuration
STRIPE_SECRET_KEY=sk_test_your_stripe_secret_key_here
STRIPE_PUBLISHABLE_KEY=pk_test_your_stripe_publishable_key_here
STRIPE_WEBHOOK_SECRET=whsec_your_webhook_secret_here
```

**获取密钥:**
1. 注册/登录 [Stripe Dashboard](https://dashboard.stripe.com/)
2. 导航到 [API Keys](https://dashboard.stripe.com/apikeys)
3. 复制测试模式密钥 (以 `sk_test_` 开头)
4. **Webhook 密钥获取**:
   - **本地开发**: 使用 Stripe CLI（见下方步骤 5）
   - **生产环境**: 在 [Webhooks](https://dashboard.stripe.com/webhooks) 配置固定端点

### 3. 运行数据库迁移

```bash
source .env

psql "postgresql://postgres:$POSTGRES_PASSWORD@localhost:5438/postgres" \
  -v ON_ERROR_STOP=1 \
  -f supabase/migrations/12_stripe_integration.sql
```

**迁移内容:**
- 添加 `payment_provider`, `stripe_payment_intent_id`, `stripe_customer_id`, `stripe_payment_status` 字段到 `order` 表
- 创建索引优化 Stripe 查询
- 添加 Stripe 订单管理函数

### 4. 启动后端服务

```bash
uv run python run.py
```

服务将在 `http://localhost:8001` 运行。

### 5. 配置 Webhook 本地测试

**详细指南**: 参见 [`docs/WEBHOOK_LOCAL_TESTING.md`](docs/WEBHOOK_LOCAL_TESTING.md)

**快速开始**:

```bash
# 1. 安装 Stripe CLI
brew install stripe/stripe-cli/stripe  # macOS
# 或从 https://github.com/stripe/stripe-cli/releases 下载

# 2. 登录 Stripe 账户
stripe login

# 3. 启动 webhook 转发（使用脚本）
./scripts/start_stripe_webhook.sh

# 或直接运行命令
stripe listen --forward-to http://localhost:8001/stripe/webhook

# 4. 复制输出的 webhook signing secret 到 .env
# 例如: whsec_xxxxxxxxxxxxxxxxxxxxx
# 更新 .env 中的 STRIPE_WEBHOOK_SECRET

# 5. 重启后端服务以加载新的 secret
```

### 6. 测试集成

**基本功能测试**:
```bash
uv run python test_stripe_payment.py
```

测试脚本会：
- 验证 API 服务运行状态
- 测试支付意图创建
- 测试订单状态查询
- 验证支付工厂模式

**Webhook 事件测试**:
```bash
# 触发支付成功事件
./scripts/test_stripe_webhook_trigger.sh payment_intent.succeeded

# 或直接使用 Stripe CLI
stripe trigger payment_intent.succeeded
```

## API 端点

### POST /stripe/create-payment-intent

创建 Stripe 支付意图。

**请求体:**
```json
{
  "product_name": "VPN 订阅 - 月付",
  "trade_num": 1,
  "amount": 999,
  "currency": "usd",
  "email": "customer@example.com",
  "phone": "+1234567890"
}
```

**参数说明:**
- `product_name`: 产品名称
- `trade_num`: 交易数量
- `amount`: 金额（**单位：分**），例如 999 = $9.99
- `currency`: 货币代码（ISO 4217），如 `usd`, `eur`, `gbp`
- `email`: 客户邮箱（必需）
- `phone`: 客户手机号（可选）

**响应示例:**
```json
{
  "success": true,
  "order_id": "550e8400-e29b-41d4-a716-446655440000",
  "payment_intent_id": "pi_3L1234567890",
  "client_secret": "pi_3L1234567890_secret_abcdefgh123456",
  "customer_id": "cus_1234567890",
  "amount": 999,
  "currency": "usd",
  "status": "requires_payment_method"
}
```

**使用 client_secret 在前端完成支付:**
```javascript
// 前端集成示例（使用 Stripe.js）
const stripe = Stripe('pk_test_your_publishable_key');
const { error } = await stripe.confirmPayment({
  clientSecret: 'pi_xxx_secret_xxx',
  confirmParams: {
    return_url: 'https://yourdomain.com/payment-success',
  },
});
```

### GET /stripe/payment-status/{order_id}

查询订单支付状态。

**路径参数:**
- `order_id`: 订单 UUID

**响应示例:**
```json
{
  "success": true,
  "order_id": "550e8400-e29b-41d4-a716-446655440000",
  "payment_provider": "stripe",
  "stripe_payment_intent_id": "pi_3L1234567890",
  "stripe_payment_status": "succeeded",
  "order_status": "已支付",
  "amount": 999,
  "product_name": "VPN 订阅 - 月付",
  "created_at": "2025-01-23T10:30:00Z"
}
```

**Stripe 支付状态说明:**
- `requires_payment_method`: 等待支付方式
- `processing`: 处理中
- `succeeded`: 支付成功
- `canceled`: 已取消
- `payment_failed`: 支付失败

### POST /stripe/webhook

接收 Stripe Webhook 回调（由 Stripe 服务器调用）。

**支持的事件:**
- `payment_intent.succeeded`: 支付成功，自动更新订单状态为"已支付"
- `payment_intent.payment_failed`: 支付失败，更新订单状态为"支付失败"
- `payment_intent.canceled`: 支付取消，更新订单状态为"已取消"
- `payment_intent.processing`: 支付处理中
- `payment_intent.requires_action`: 需要额外操作（如 3D Secure）

**Webhook 签名验证:**
自动验证 `stripe-signature` 头，确保回调来自 Stripe 服务器。

## 数据库结构

### order 表新增字段

| 字段 | 类型 | 说明 | 默认值 |
|------|------|------|--------|
| `payment_provider` | text | 支付提供商 | 'h5zhifu' |
| `stripe_payment_intent_id` | text | Stripe Payment Intent ID | NULL |
| `stripe_customer_id` | text | Stripe Customer ID | NULL |
| `stripe_payment_status` | text | Stripe 支付状态 | NULL |

### 新增数据库函数

- `insert_stripe_order()`: 插入 Stripe 订单
- `update_stripe_payment_status()`: 更新 Stripe 支付状态
- `get_order_by_stripe_payment_intent()`: 通过 Payment Intent ID 查询订单
- `get_orders_by_stripe_customer()`: 查询客户的所有订单

## Webhook 配置

### 本地开发测试（使用 Stripe CLI）

1. **安装 Stripe CLI:**
   ```bash
   # macOS
   brew install stripe/stripe-cli/stripe

   # Linux
   wget https://github.com/stripe/stripe-cli/releases/download/vX.X.X/stripe_X.X.X_linux_x86_64.tar.gz
   tar -xvf stripe_*.tar.gz
   sudo mv stripe /usr/local/bin/
   ```

2. **登录 Stripe:**
   ```bash
   stripe login
   ```

3. **转发 Webhook 到本地:**
   ```bash
   stripe listen --forward-to http://localhost:8001/stripe/webhook
   ```

   这会输出 Webhook 签名密钥，复制到 `.env`:
   ```
   STRIPE_WEBHOOK_SECRET=whsec_xxxxxxxxxxxxxxxxxxxxx
   ```

4. **触发测试事件:**
   ```bash
   stripe trigger payment_intent.succeeded
   stripe trigger payment_intent.payment_failed
   ```

### 生产环境配置

1. 在 [Stripe Dashboard - Webhooks](https://dashboard.stripe.com/webhooks) 添加端点
2. 端点 URL: `https://yourdomain.com/stripe/webhook`
3. 选择要监听的事件:
   - `payment_intent.succeeded`
   - `payment_intent.payment_failed`
   - `payment_intent.canceled`
   - `payment_intent.processing`
4. 复制 Webhook 签名密钥到生产环境的 `.env`

## 前端集成
- 使用checkout处理前端事务


### Next.js 集成示例

```typescript
// app/checkout/page.tsx
'use client';

import { loadStripe } from '@stripe/stripe-js';
import { Elements } from '@stripe/react-stripe-js';
import CheckoutForm from '@/components/CheckoutForm';

const stripePromise = loadStripe(process.env.NEXT_PUBLIC_STRIPE_PUBLISHABLE_KEY!);

export default function CheckoutPage() {
  const [clientSecret, setClientSecret] = useState('');

  useEffect(() => {
    fetch('/api/create-payment-intent', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        product_name: 'VPN 订阅',
        amount: 999,
        email: user.email,
      }),
    })
      .then((res) => res.json())
      .then((data) => setClientSecret(data.client_secret));
  }, []);

  return (
    <>
      {clientSecret && (
        <Elements stripe={stripePromise} options={{ clientSecret }}>
          <CheckoutForm />
        </Elements>
      )}
    </>
  );
}
```

## 支付工厂模式

系统使用支付工厂模式统一管理多种支付方式。

### Python 使用示例

```python
from payments.payment_factory import create_payment_by_provider

# 创建 Stripe 支付
result = create_payment_by_provider(
    provider_name="stripe",
    product_name="VPN 订阅",
    amount=999,
    email="customer@example.com",
    phone="+1234567890",
    currency="usd",
    order_id="optional-order-uuid"
)

if result["success"]:
    print(f"Payment Intent ID: {result['payment_intent_id']}")
    print(f"Client Secret: {result['client_secret']}")
else:
    print(f"Error: {result['error']}")

# 创建 h5zhifu 支付（保持兼容）
result = create_payment_by_provider(
    provider_name="h5zhifu",
    product_name="VPN 订阅",
    amount=999,
    email="customer@example.com",
    phone="+86 138xxxxxxxx",
    app_id=12345,
    secret_key="your_h5zhifu_secret",
    out_trade_no="ORDER123456",
    pay_type="alipay",
    notify_url="https://yourdomain.com/notify"
)
```

## 错误处理

### 常见错误及解决方案

| 错误信息 | 原因 | 解决方案 |
|----------|------|----------|
| `STRIPE_SECRET_KEY not set` | 未配置 Stripe 密钥 | 在 `.env` 中设置 `STRIPE_SECRET_KEY` |
| `Invalid API key` | 密钥错误或已过期 | 检查 Stripe Dashboard 中的密钥 |
| `Invalid webhook signature` | Webhook 签名验证失败 | 确保 `STRIPE_WEBHOOK_SECRET` 正确 |
| `Order not found` | 订单 ID 不存在 | 检查订单是否已创建 |
| `Failed to create payment intent` | Stripe API 调用失败 | 检查网络连接和 API 密钥权限 |

### 日志查看

所有支付相关操作都会记录日志：

```bash
# 查看后端日志
uv run python run.py

# 日志示例
2025-01-23 10:30:00 | INFO | Created Stripe Payment Intent: pi_xxx for amount 999 usd
2025-01-23 10:30:15 | INFO | Updated order status to 'succeeded' for payment_intent: pi_xxx
```

## 安全最佳实践

1. **密钥管理:**
   - 使用测试密钥 (`sk_test_`) 进行开发
   - 生产环境使用生产密钥 (`sk_live_`)
   - 永远不要在前端代码或版本控制中暴露 Secret Key
   - 仅在前端使用 Publishable Key (`pk_test_` 或 `pk_live_`)

2. **Webhook 安全:**
   - 始终验证 Webhook 签名
   - 使用 HTTPS 端点接收 Webhook
   - 不要信任未经验证的 Webhook 数据

3. **金额处理:**
   - 所有金额使用整数（分）避免浮点数精度问题
   - 在服务器端验证金额，不信任前端传入的金额

4. **CORS 配置:**
   - 限制允许的前端域名
   - 在生产环境中禁用通配符 CORS

## 生产环境部署

### 环境变量配置

```bash
# 生产环境 .env
STRIPE_SECRET_KEY=sk_live_your_production_secret_key
STRIPE_PUBLISHABLE_KEY=pk_live_your_production_publishable_key
STRIPE_WEBHOOK_SECRET=whsec_your_production_webhook_secret

# 其他生产配置
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_ANON_KEY=your_production_anon_key
```

### 数据库迁移

在生产数据库中运行迁移：

```bash
psql "$PRODUCTION_DATABASE_URL" \
  -v ON_ERROR_STOP=1 \
  -f supabase/migrations/12_stripe_integration.sql
```

### 监控与告警

建议监控以下指标：
- 支付成功率
- Webhook 处理失败率
- 支付处理延迟
- 订单超时率

## 故障排查

### 问题：支付意图创建失败

**检查清单:**
1. 确认 `STRIPE_SECRET_KEY` 配置正确
2. 检查网络连接到 Stripe API
3. 查看后端日志中的详细错误信息
4. 验证请求参数格式是否正确

### 问题：Webhook 回调未触发

**检查清单:**
1. 确认 Webhook 端点 URL 可公开访问
2. 验证 Stripe Dashboard 中的 Webhook 配置
3. 检查 `STRIPE_WEBHOOK_SECRET` 是否正确
4. 使用 Stripe CLI 测试本地 Webhook

### 问题：订单状态未更新

**检查清单:**
1. 查看 Webhook 日志确认事件已收到
2. 检查数据库函数 `update_stripe_payment_status` 是否执行成功
3. 验证订单 ID 和 Payment Intent ID 是否正确关联

---

# 月度订阅功能

## 订阅功能概览

| 项目 | 配置 |
|------|------|
| 价格 | 25 HKD/月 |
| 试用期 | 30天免费（需绑卡） |
| 取消策略 | 周期结束后停止服务 |
| 降级策略 | 周期结束生效 |
| 升级/退款 | 不支持 |

## 订阅配置

### 环境变量

在 `.env` 中配置订阅相关变量：

```bash
# Stripe Subscription Configuration (月度订阅)
STRIPE_MONTHLY_PRICE_ID=price_xxxxxxxxxxxxxx    # Stripe Price ID
STRIPE_MONTHLY_PRODUCT_ID=prod_xxxxxxxxxxxxxx   # Stripe Product ID
SUBSCRIPTION_TRIAL_DAYS=30                       # 试用期天数
SUBSCRIPTION_MONTHLY_PRICE=2500                  # 月费（分），2500 = 25 HKD
SUBSCRIPTION_CURRENCY=hkd                        # 货币
subscription_gateway_ip=35.77.91.182             # 服务网关 IP
```

### Stripe Dashboard 配置

1. **创建 Product:**
   - 访问 [Stripe Dashboard - Products](https://dashboard.stripe.com/products)
   - 点击 "Add product"
   - 名称: "Monthly Subscription Plan"
   - 选择 "Recurring" 定价模式
   - 价格: 25 HKD/月

2. **复制 Price ID 和 Product ID:**
   - Price ID 格式: `price_xxxxxxxxxxxxxx`
   - Product ID 格式: `prod_xxxxxxxxxxxxxx`
   - 更新到 `.env` 文件

3. **配置 Webhook 事件:**
   - 访问 [Stripe Dashboard - Webhooks](https://dashboard.stripe.com/webhooks)
   - 添加以下事件：
     - `checkout.session.completed`
     - `customer.subscription.created`
     - `customer.subscription.updated`
     - `customer.subscription.deleted`
     - `invoice.paid`
     - `invoice.payment_failed`

### 运行数据库迁移

```bash
source .env

psql "postgresql://postgres:$POSTGRES_PASSWORD@localhost:5438/postgres" \
  -v ON_ERROR_STOP=1 \
  -f supabase/migrations/20251225120000_subscription_tables.sql
```

**迁移内容:**
- 创建 `subscription` 表
- 添加 `stripe_subscription_id` 和 `subscription_type` 字段到 `order` 表
- 创建订阅管理数据库函数

## 订阅 API 端点

### POST /subscription/purchase

创建订阅 Checkout Session（需登录）。

**请求体:**
```json
{
  "plan_id": "monthly_subscription"
}
```

**响应示例:**
```json
{
  "success": true,
  "message": "Subscription checkout created with 30 days free trial",
  "checkout_url": "https://checkout.stripe.com/c/pay/cs_test_xxx",
  "checkout_session_id": "cs_test_xxx"
}
```

**前端集成:**
```javascript
// 用户点击订阅按钮
const response = await fetch('/subscription/purchase', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  credentials: 'include', // 包含 cookies
  body: JSON.stringify({ plan_id: 'monthly_subscription' })
});

const data = await response.json();
if (data.success) {
  // 跳转到 Stripe Checkout 页面
  window.location.href = data.checkout_url;
}
```

### GET /subscription/status

查询用户订阅状态（需登录）。

**响应示例:**
```json
{
  "has_subscription": true,
  "subscription_status": "trialing",
  "current_period_end": "2025-02-25T00:00:00Z",
  "cancel_at_period_end": false,
  "trial_end": "2025-02-25T00:00:00Z",
  "is_trial": true,
  "stripe_subscription_id": "sub_xxxxx",
  "stripe_customer_id": "cus_xxxxx"
}
```

**订阅状态说明:**
- `trialing`: 试用期
- `active`: 正常订阅
- `past_due`: 付款逾期
- `canceled`: 已取消
- `incomplete`: 未完成
- `incomplete_expired`: 未完成已过期

### POST /subscription/cancel

取消订阅（需登录）。

**请求体:**
```json
{
  "at_period_end": true
}
```

**响应示例:**
```json
{
  "success": true,
  "message": "Subscription canceled. Access continues until 2025-02-25",
  "cancel_at_period_end": true,
  "current_period_end": "2025-02-25"
}
```

### POST /subscription/reactivate

恢复已取消的订阅（仅在周期结束前有效）。

**响应示例:**
```json
{
  "success": true,
  "message": "Subscription reactivated successfully"
}
```

### POST /subscription/portal

获取 Stripe 客户门户 URL。

**响应示例:**
```json
{
  "success": true,
  "portal_url": "https://billing.stripe.com/p/session/xxx"
}
```

用户可在门户中：
- 查看订阅详情
- 更新支付方式
- 查看发票历史
- 取消订阅

### GET /subscription/info

获取订阅计划信息（公开端点）。

**响应示例:**
```json
{
  "plan_name": "Monthly Subscription",
  "price": 2500,
  "currency": "hkd",
  "trial_days": 30,
  "billing_period": "monthly",
  "features": [
    "Full VPN access",
    "30 days free trial",
    "Cancel anytime",
    "Automatic renewal"
  ]
}
```

## 订阅 Webhook 事件

### checkout.session.completed (subscription mode)

用户完成 Checkout 后触发。

**处理逻辑:**
1. 解析订阅信息（subscription_id, customer_id）
2. 在数据库中创建订阅记录
3. 后台异步生成 VPN 产品
4. 更新 order 表关联

### customer.subscription.updated

订阅状态变更时触发。

**处理逻辑:**
1. 更新订阅状态（status）
2. 更新计费周期（current_period_start/end）
3. 更新取消标记（cancel_at_period_end）

### customer.subscription.deleted

订阅被删除/终止时触发。

**处理逻辑:**
1. 标记订阅为 canceled
2. 记录结束时间（ended_at）
3. 停止相关服务

### invoice.paid

发票支付成功（续费成功）。

**处理逻辑:**
1. 更新订阅周期
2. 确保服务继续有效
3. 创建续费订单记录

### invoice.payment_failed

发票支付失败。

**处理逻辑:**
1. 更新订阅状态为 `past_due`
2. 可选：发送提醒邮件
3. Stripe 会自动重试

## 订阅数据库结构

### subscription 表

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | uuid | 主键 |
| `user_email` | text | 用户邮箱 |
| `stripe_customer_id` | text | Stripe Customer ID |
| `stripe_subscription_id` | text | Stripe Subscription ID（唯一） |
| `stripe_price_id` | text | Stripe Price ID |
| `status` | text | 订阅状态 |
| `current_period_start` | timestamp | 当前周期开始 |
| `current_period_end` | timestamp | 当前周期结束 |
| `trial_start` | timestamp | 试用开始 |
| `trial_end` | timestamp | 试用结束 |
| `cancel_at_period_end` | boolean | 是否周期结束后取消 |
| `canceled_at` | timestamp | 取消时间 |
| `ended_at` | timestamp | 结束时间 |
| `plan_id` | text | 内部计划 ID |
| `product_id` | uuid | 关联产品 ID |
| `metadata` | jsonb | 额外元数据 |

### order 表新增字段

| 字段 | 类型 | 说明 |
|------|------|------|
| `stripe_subscription_id` | text | Stripe Subscription ID |
| `subscription_type` | text | 订阅类型 (one_time/subscription) |

## 订阅流程图

### 新用户订阅流程
```
用户点击订阅 → POST /subscription/purchase
       ↓
创建 Checkout Session (trial_period_days=30)
       ↓
用户跳转到 Stripe Checkout
       ↓
用户绑定银行卡/信用卡
       ↓
Checkout 完成 → Webhook: checkout.session.completed
       ↓
创建订阅记录 + 异步生成 VPN 产品
       ↓
用户开始 30 天试用期
```

### 取消订阅流程
```
用户点击取消 → POST /subscription/cancel
       ↓
调用 Stripe API (cancel_at_period_end=true)
       ↓
更新本地数据库 (cancel_at_period_end=true)
       ↓
用户继续使用至周期结束
       ↓
周期结束 → Webhook: customer.subscription.deleted
       ↓
标记订阅结束，停止服务
```

### 月度续费流程
```
周期结束前 → Stripe 自动扣款
       ↓
扣款成功 → Webhook: invoice.paid
       ↓
更新订阅周期 (current_period_start/end)
       ↓
服务继续有效
```

## 前端集成示例

### React 订阅按钮

```jsx
import { useState } from 'react';

function SubscribeButton() {
  const [loading, setLoading] = useState(false);

  const handleSubscribe = async () => {
    setLoading(true);
    try {
      const response = await fetch('/subscription/purchase', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'include',
        body: JSON.stringify({ plan_id: 'monthly_subscription' })
      });

      const data = await response.json();
      if (data.success) {
        window.location.href = data.checkout_url;
      } else {
        alert(data.message || 'Failed to create subscription');
      }
    } catch (error) {
      console.error('Subscription error:', error);
    } finally {
      setLoading(false);
    }
  };

  return (
    <button onClick={handleSubscribe} disabled={loading}>
      {loading ? '处理中...' : '开始 30 天免费试用'}
    </button>
  );
}
```

### 订阅状态显示

```jsx
import { useEffect, useState } from 'react';

function SubscriptionStatus() {
  const [status, setStatus] = useState(null);

  useEffect(() => {
    fetch('/subscription/status', { credentials: 'include' })
      .then(res => res.json())
      .then(data => setStatus(data));
  }, []);

  if (!status) return <div>加载中...</div>;

  if (!status.has_subscription) {
    return <div>您还没有订阅</div>;
  }

  return (
    <div>
      <p>订阅状态: {status.subscription_status}</p>
      <p>当前周期结束: {new Date(status.current_period_end).toLocaleDateString()}</p>
      {status.is_trial && <p>🎁 试用期中</p>}
      {status.cancel_at_period_end && <p>⚠️ 订阅将在周期结束后取消</p>}
    </div>
  );
}
```

---

## 扩展功能

### 未来可扩展的功能

1. **多币种支持:**
   - 自动汇率转换
   - 本地货币结算

2. **退款处理:**
   - 全额/部分退款
   - 退款通知

3. **发票生成:**
   - 自动生成发票
   - PDF 下载

4. **订阅升级/降级:**
   - 按比例计费
   - 立即生效或周期结束生效

## 参考资源

- [Stripe API 文档](https://stripe.com/docs/api)
- [Stripe Payment Intents](https://stripe.com/docs/payments/payment-intents)
- [Stripe Webhooks](https://stripe.com/docs/webhooks)
- [Stripe.js 集成](https://stripe.com/docs/js)
- [Stripe CLI](https://stripe.com/docs/stripe-cli)
- [Stripe 测试卡号](https://stripe.com/docs/testing)

## 支持

遇到问题？
1. 查看本文档的"故障排查"章节
2. 查看后端日志了解详细错误信息
3. 参考 Stripe 官方文档
4. 运行 `uv run python test_stripe_payment.py` 诊断问题

---

**版本**: 2.0.0
**最后更新**: 2025-12-25
**维护者**: Backend Team
**更新内容**: 添加月度订阅功能
