# Stripe 支付集成指南

本文档详细说明如何在 Supabase + FastAPI 后端中使用 Stripe 支付。

## 概览

- **支付方式**: 与现有 h5zhifu (支付宝/微信) 并存
- **支持功能**: 一次性支付、Webhook 回调、客户管理
- **支付提供商**: Stripe (国际支付) + h5zhifu (中国支付)

## 架构设计

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

## 文件结构

```
web_backend/
├── docs/
│   └── WEBHOOK_LOCAL_TESTING.md         # 🆕 Webhook 本地测试详细指南
├── scripts/
│   ├── start_stripe_webhook.sh          # 🆕 启动 webhook 转发
│   └── test_stripe_webhook_trigger.sh   # 🆕 触发测试事件
├── payments/
│   ├── h5zhifu.py              # 现有中国支付网关
│   ├── stripe_payment.py       # 新增：Stripe 支付模块
│   └── payment_factory.py      # 新增：支付工厂路由器
├── routes/
│   └── stripe_routes.py        # 新增：Stripe API 端点
├── supabase/migrations/
│   └── 12_stripe_integration.sql  # 数据库迁移
├── test_stripe_payment.py      # 集成测试脚本
├── .env                        # 环境配置（包含 Stripe 密钥）
└── STRIPE_INTEGRATION.md       # 本文档
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

### 使用 Stripe Payment Element（推荐）

Stripe Payment Element 是一个预构建的 UI 组件，自动处理支付方式。

**安装依赖:**
```bash
npm install @stripe/stripe-js @stripe/react-stripe-js
```

**React 集成示例:**

```jsx
import { loadStripe } from '@stripe/stripe-js';
import { Elements, PaymentElement, useStripe, useElements } from '@stripe/react-stripe-js';
import { useState } from 'react';

// 加载 Stripe（使用发布密钥）
const stripePromise = loadStripe('pk_test_your_publishable_key');

function CheckoutForm({ clientSecret }) {
  const stripe = useStripe();
  const elements = useElements();
  const [error, setError] = useState(null);
  const [processing, setProcessing] = useState(false);

  const handleSubmit = async (event) => {
    event.preventDefault();

    if (!stripe || !elements) return;

    setProcessing(true);

    const { error } = await stripe.confirmPayment({
      elements,
      confirmParams: {
        return_url: `${window.location.origin}/payment-success`,
      },
    });

    if (error) {
      setError(error.message);
      setProcessing(false);
    }
  };

  return (
    <form onSubmit={handleSubmit}>
      <PaymentElement />
      <button disabled={!stripe || processing}>
        {processing ? '处理中...' : '支付'}
      </button>
      {error && <div>{error}</div>}
    </form>
  );
}

export default function StripePaymentPage({ productName, amount }) {
  const [clientSecret, setClientSecret] = useState('');

  // 创建支付意图
  const createPaymentIntent = async () => {
    const response = await fetch('http://localhost:8001/stripe/create-payment-intent', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        product_name: productName,
        trade_num: 1,
        amount: amount, // 单位：分
        currency: 'usd',
        email: 'customer@example.com',
        phone: '+1234567890'
      }),
    });

    const data = await response.json();
    setClientSecret(data.client_secret);
  };

  // 在组件挂载时创建支付意图
  useEffect(() => {
    createPaymentIntent();
  }, []);

  return (
    <div>
      {clientSecret && (
        <Elements stripe={stripePromise} options={{ clientSecret }}>
          <CheckoutForm clientSecret={clientSecret} />
        </Elements>
      )}
    </div>
  );
}
```

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

## 扩展功能

### 未来可扩展的功能

1. **订阅计费（Subscriptions）:**
   - 定期扣款
   - 订阅升级/降级
   - 试用期管理

2. **多币种支持:**
   - 自动汇率转换
   - 本地货币结算

3. **退款处理:**
   - 全额/部分退款
   - 退款通知

4. **发票生成:**
   - 自动生成发票
   - PDF 下载

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

**版本**: 1.0.0
**最后更新**: 2025-01-23
**维护者**: Backend Team
