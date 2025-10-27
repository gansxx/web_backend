#!/bin/bash

# Stripe Webhook 事件触发测试脚本
# 用途：手动触发各种 Stripe 事件来测试 webhook 处理

echo "🧪 Stripe Webhook 事件触发测试"
echo ""
echo "⚠️  前提条件："
echo "  1. Stripe CLI webhook 转发必须正在运行"
echo "  2. 后端服务必须正在运行 (http://localhost:8001)"
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# 检查是否有参数
if [ -z "$1" ]; then
    echo "📋 可用的测试事件："
    echo ""
    echo "  1. payment_intent.succeeded       - 支付成功"
    echo "  2. payment_intent.payment_failed  - 支付失败"
    echo "  3. payment_intent.canceled        - 支付取消"
    echo "  4. payment_intent.processing      - 支付处理中"
    echo ""
    echo "使用方法："
    echo "  ./test_stripe_webhook_trigger.sh <事件名称>"
    echo ""
    echo "示例："
    echo "  ./test_stripe_webhook_trigger.sh payment_intent.succeeded"
    exit 0
fi

EVENT_TYPE=$1

echo "🎯 触发事件: $EVENT_TYPE"
echo ""

# 触发事件
stripe trigger $EVENT_TYPE

echo ""
echo "✅ 事件已触发，请检查："
echo "  1. Stripe CLI 转发窗口的日志"
echo "  2. 后端服务日志 (loguru 输出)"
echo "  3. 数据库订单状态变化"
