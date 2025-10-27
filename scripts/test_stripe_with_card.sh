#!/bin/bash

# Stripe 测试银行卡支付流程
# 用途：使用 Stripe 测试卡号模拟真实用户支付

set -e

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m'

API_BASE_URL="${API_BASE_URL:-http://localhost:8001}"

echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${BLUE}   Stripe 测试银行卡支付流程${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""

# ============================================
# 显示可用的测试卡号
# ============================================

echo -e "${CYAN}💳 Stripe 测试卡号列表:${NC}"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "  1. 4242 4242 4242 4242  - Visa (支付成功)"
echo "  2. 4000 0027 6000 3184  - Visa (需要 3D Secure 验证)"
echo "  3. 4000 0000 0000 9995  - Visa (资金不足)"
echo "  4. 4000 0000 0000 0002  - Visa (卡被拒绝)"
echo "  5. 5555 5555 5555 4444  - Mastercard (支付成功)"
echo "  6. 3782 822463 10005    - American Express (支付成功)"
echo ""
echo "  CVV: 任意 3 位数字 (如: 123)"
echo "  到期日: 任意未来日期 (如: 12/25)"
echo ""
echo "  完整列表: https://stripe.com/docs/testing"
echo ""

# ============================================
# 选择测试卡号
# ============================================

echo -e "${YELLOW}请选择测试卡号 [1-6, 默认=1]:${NC} "
read -r CARD_CHOICE
CARD_CHOICE=${CARD_CHOICE:-1}

case "$CARD_CHOICE" in
  1)
    CARD_NUMBER="4242424242424242"
    CARD_NAME="Visa (支付成功)"
    PAYMENT_METHOD="pm_card_visa"
    EXPECTED_STATUS="succeeded"
    ;;
  2)
    CARD_NUMBER="4000002760003184"
    CARD_NAME="Visa (3D Secure)"
    PAYMENT_METHOD="pm_card_threeDSecure2Required"
    EXPECTED_STATUS="requires_action"
    ;;
  3)
    CARD_NUMBER="4000000000009995"
    CARD_NAME="Visa (资金不足)"
    PAYMENT_METHOD="pm_card_insufficient_funds"
    EXPECTED_STATUS="payment_failed"
    ;;
  4)
    CARD_NUMBER="4000000000000002"
    CARD_NAME="Visa (卡被拒绝)"
    PAYMENT_METHOD="pm_card_chargeDeclined"
    EXPECTED_STATUS="payment_failed"
    ;;
  5)
    CARD_NUMBER="5555555555554444"
    CARD_NAME="Mastercard (支付成功)"
    PAYMENT_METHOD="pm_card_mastercard"
    EXPECTED_STATUS="succeeded"
    ;;
  6)
    CARD_NUMBER="378282246310005"
    CARD_NAME="American Express (支付成功)"
    PAYMENT_METHOD="pm_card_amex"
    EXPECTED_STATUS="succeeded"
    ;;
  *)
    echo -e "${RED}❌ 无效选择，使用默认卡号${NC}"
    CARD_NUMBER="4242424242424242"
    CARD_NAME="Visa (支付成功)"
    PAYMENT_METHOD="pm_card_visa"
    EXPECTED_STATUS="succeeded"
    ;;
esac

echo ""
echo -e "已选择: ${GREEN}$CARD_NAME${NC}"
echo -e "卡号: ${BLUE}$CARD_NUMBER${NC}"
echo ""

# ============================================
# 步骤 1: 创建支付意图
# ============================================

echo -e "${YELLOW}💳 步骤 1: 创建支付意图${NC}"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

TIMESTAMP=$(date +%s)
EMAIL="cardtest_${TIMESTAMP}@example.com"

PAYLOAD=$(cat <<EOF
{
  "product_name": "测试商品 - ${CARD_NAME}",
  "trade_num": 1,
  "amount": 1999,
  "currency": "usd",
  "email": "$EMAIL",
  "phone": "+1234567890"
}
EOF
)

echo "  创建支付意图..."
RESPONSE=$(curl -s -X POST "$API_BASE_URL/stripe/create-payment-intent" \
  -H "Content-Type: application/json" \
  -d "$PAYLOAD")

SUCCESS=$(echo "$RESPONSE" | jq -r '.success')
ORDER_ID=$(echo "$RESPONSE" | jq -r '.order_id')
PAYMENT_INTENT_ID=$(echo "$RESPONSE" | jq -r '.payment_intent_id')
CLIENT_SECRET=$(echo "$RESPONSE" | jq -r '.client_secret')
AMOUNT=$(echo "$RESPONSE" | jq -r '.amount')

if [ "$SUCCESS" != "true" ]; then
  echo -e "${RED}❌ 创建支付意图失败${NC}"
  echo "$RESPONSE" | jq .
  exit 1
fi

echo -e "  ${GREEN}✅ 支付意图创建成功${NC}"
echo ""
echo "  订单信息:"
echo "    - 订单ID: $ORDER_ID"
echo "    - Payment Intent ID: $PAYMENT_INTENT_ID"
echo "    - 金额: \$$(echo "scale=2; $AMOUNT / 100" | bc)"
echo "    - 客户邮箱: $EMAIL"
echo ""

# ============================================
# 步骤 2: 使用测试卡号支付
# ============================================

echo -e "${YELLOW}💰 步骤 2: 使用测试卡号支付${NC}"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

echo "  卡号: $CARD_NUMBER"
echo "  类型: $CARD_NAME"
echo ""
echo "  执行支付..."

# 使用 Stripe CLI 确认支付
if stripe payment_intents confirm "$PAYMENT_INTENT_ID" \
  --payment-method "$PAYMENT_METHOD" > /dev/null 2>&1; then
  echo -e "  ${GREEN}✅ 支付请求已提交${NC}"
else
  if [[ "$EXPECTED_STATUS" == "payment_failed" ]]; then
    echo -e "  ${GREEN}✅ 支付按预期被拒绝${NC}"
  else
    echo -e "  ${YELLOW}⚠️  支付处理中或需要额外操作${NC}"
  fi
fi

echo ""
echo "  等待 webhook 处理... (3秒)"
sleep 3
echo ""

# ============================================
# 步骤 3: 验证支付结果
# ============================================

echo -e "${YELLOW}🔎 步骤 3: 验证支付结果${NC}"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

STATUS_RESPONSE=$(curl -s "$API_BASE_URL/stripe/payment-status/$ORDER_ID")

echo "  查询订单状态..."
echo ""

STRIPE_STATUS=$(echo "$STATUS_RESPONSE" | jq -r '.stripe_payment_status')
ORDER_STATUS=$(echo "$STATUS_RESPONSE" | jq -r '.order_status')
PRODUCT_NAME=$(echo "$STATUS_RESPONSE" | jq -r '.product_name')

echo "  订单详情:"
echo "    - 产品: $PRODUCT_NAME"
echo "    - Stripe 状态: $STRIPE_STATUS"
echo "    - 订单状态: $ORDER_STATUS"
echo "    - 金额: \$$(echo "scale=2; $AMOUNT / 100" | bc)"
echo ""

# ============================================
# 步骤 4: 显示测试结果
# ============================================

echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${BLUE}   测试结果${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""

case "$STRIPE_STATUS" in
  succeeded)
    echo -e "  状态: ${GREEN}✅ 支付成功${NC}"
    echo ""
    echo "  🎉 恭喜! 支付已完成"
    echo "  订单已标记为: $ORDER_STATUS"
    ;;
  processing)
    echo -e "  状态: ${YELLOW}⏳ 支付处理中${NC}"
    echo ""
    echo "  支付正在处理，请稍后查询订单状态"
    ;;
  requires_action)
    echo -e "  状态: ${YELLOW}🔐 需要额外验证${NC}"
    echo ""
    echo "  此卡需要 3D Secure 验证"
    echo "  在实际应用中，用户会被重定向到银行验证页面"
    ;;
  payment_failed)
    echo -e "  状态: ${RED}❌ 支付失败${NC}"
    echo ""
    echo "  支付被拒绝"
    echo "  原因: 卡被拒绝或资金不足"
    ;;
  canceled)
    echo -e "  状态: ${YELLOW}⛔ 支付已取消${NC}"
    ;;
  *)
    echo -e "  状态: ${YELLOW}❓ 未知状态: $STRIPE_STATUS${NC}"
    ;;
esac

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# ============================================
# 后续操作提示
# ============================================

echo -e "${CYAN}📝 后续操作:${NC}"
echo ""
echo "  1. 在 Stripe Dashboard 查看支付详情:"
echo "     https://dashboard.stripe.com/test/payments/$PAYMENT_INTENT_ID"
echo ""
echo "  2. 查询订单状态:"
echo "     curl $API_BASE_URL/stripe/payment-status/$ORDER_ID | jq ."
echo ""
echo "  3. 测试其他卡号:"
echo "     $0"
echo ""
echo "  4. 查看 Webhook 日志:"
echo "     stripe listen --print-json"
echo ""
