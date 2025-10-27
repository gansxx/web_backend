#!/bin/bash

# Stripe Webhook 本地测试脚本
# 用途：转发 Stripe Webhook 事件到本地后端服务

echo "🚀 启动 Stripe CLI Webhook 转发..."
echo ""
echo "📋 配置信息:"
echo "  本地后端地址: http://localhost:8001"
echo "  Webhook 端点: /stripe/webhook"
echo ""
echo "⚠️  请确保后端服务已启动 (uv run python run.py)"
echo ""
echo "✅ 转发成功后，Stripe CLI 会显示 webhook signing secret"
echo "   请复制该 secret 并更新到 .env 文件中的 STRIPE_WEBHOOK_SECRET"
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# 启动转发
stripe listen --forward-to http://localhost:8001/stripe/webhook

# 注意：
# 1. 转发过程中会生成临时的 webhook signing secret (whsec_...)
# 2. 每次重启都会生成新的 secret，需要更新 .env
# 3. 按 Ctrl+C 可以停止转发
