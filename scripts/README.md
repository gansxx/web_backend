# Stripe Webhook 测试脚本

本目录包含用于 Stripe Webhook 本地测试的辅助脚本。

## 脚本说明

### 1. `start_stripe_webhook.sh`

**用途**: 启动 Stripe CLI webhook 转发，将 Stripe 事件转发到本地后端。

**前提条件**:
- 已安装 Stripe CLI
- 已运行 `stripe login` 登录
- 后端服务正在运行 (http://localhost:8001)

**使用方法**:
```bash
./scripts/start_stripe_webhook.sh
```

**输出**:
```
🚀 启动 Stripe CLI Webhook 转发...
> Ready! Your webhook signing secret is whsec_xxxxxxxxxxxxxxxxxxxxx
```

**重要**: 复制显示的 webhook signing secret 并更新到 `.env` 文件中的 `STRIPE_WEBHOOK_SECRET`。

---

### 2. `test_stripe_webhook_trigger.sh`

**用途**: 手动触发 Stripe 事件来测试 webhook 处理逻辑。

**前提条件**:
- `stripe listen` 正在运行（通过 `start_stripe_webhook.sh`）
- 后端服务正在运行
- `.env` 中的 `STRIPE_WEBHOOK_SECRET` 已更新

**使用方法**:
```bash
# 查看可用事件
./scripts/test_stripe_webhook_trigger.sh

# 触发支付成功事件
./scripts/test_stripe_webhook_trigger.sh payment_intent.succeeded

# 触发支付失败事件
./scripts/test_stripe_webhook_trigger.sh payment_intent.payment_failed

# 触发支付取消事件
./scripts/test_stripe_webhook_trigger.sh payment_intent.canceled
```

## 完整测试流程

### 终端 1: 启动后端服务
```bash
cd /root/self_code/web_backend
uv run python run.py
```

### 终端 2: 启动 Webhook 转发
```bash
./scripts/start_stripe_webhook.sh
# 复制显示的 webhook signing secret
```

### 终端 1: 更新 .env 并重启后端
```bash
# 编辑 .env，更新 STRIPE_WEBHOOK_SECRET
# Ctrl+C 停止服务
uv run python run.py
```

### 终端 3: 触发测试事件
```bash
# 触发支付成功
./scripts/test_stripe_webhook_trigger.sh payment_intent.succeeded
```

### 验证结果

1. **终端 2 (Stripe CLI)** 应显示:
```
2025-01-27 10:30:15   --> payment_intent.succeeded [evt_xxxxx]
2025-01-27 10:30:15   <-- [200] POST http://localhost:8001/stripe/webhook
```

2. **终端 1 (后端日志)** 应显示:
```
INFO | Processing Stripe webhook event: payment_intent.succeeded
INFO | Updated order status to 'succeeded' for payment_intent: pi_xxxxx
```

3. **数据库**应更新订单状态:
```bash
source .env
psql "postgresql://postgres:$POSTGRES_PASSWORD@localhost:5438/postgres" \
  -c "SELECT id, status, stripe_payment_status FROM \"order\" WHERE payment_provider = 'stripe' ORDER BY created_at DESC LIMIT 1;"
```

## 常见问题

### Q: 每次运行都要更新 webhook secret？

**A**: 是的。开发环境下，每次运行 `stripe listen` 都会生成新的临时 webhook signing secret。生产环境使用固定的 secret。

### Q: 如何调试 webhook 处理失败？

**A**:
1. 检查终端 2 的 Stripe CLI 输出，查看是否返回错误状态码
2. 查看终端 1 的后端日志，查找错误堆栈
3. 使用 `stripe listen --print-json` 查看完整 payload
4. 验证 `.env` 中的 `STRIPE_WEBHOOK_SECRET` 是否正确

### Q: 如何测试真实支付流程？

**A**:
1. 运行 `uv run python test_stripe_payment.py` 创建支付意图
2. 在前端或 Stripe Dashboard 使用测试卡号完成支付
3. Webhook 会自动触发并更新订单状态

## 更多信息

详细的 Webhook 测试指南请参见: [`../docs/WEBHOOK_LOCAL_TESTING.md`](../docs/WEBHOOK_LOCAL_TESTING.md)
