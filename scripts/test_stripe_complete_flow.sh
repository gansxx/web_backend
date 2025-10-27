#!/bin/bash

# Stripe 完整支付流程测试脚本
# 用途：创建支付意图 → CLI 确认支付 → 验证状态

set -e  # 遇到错误立即退出

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# API 基础 URL
API_BASE_URL="${API_BASE_URL:-http://localhost:8001}"

echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${BLUE}     Stripe 完整支付流程自动化测试${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""

# 解析参数
PAYMENT_SCENARIO="${1:-success}"

case "$PAYMENT_SCENARIO" in
  success)
    SCENARIO_NAME="支付成功"
    PAYMENT_METHOD="pm_card_visa"
    EXPECTED_STATUS="succeeded"
    ;;
  failed)
    SCENARIO_NAME="支付失败"
    PAYMENT_METHOD="pm_card_chargeDeclined"
    EXPECTED_STATUS="payment_failed"
    ;;
  canceled)
    SCENARIO_NAME="支付取消"
    PAYMENT_METHOD=""  # 不需要支付方法,直接取消
    EXPECTED_STATUS="canceled"
    ;;
  *)
    echo -e "${RED}❌ 无效的测试场景: $PAYMENT_SCENARIO${NC}"
    echo ""
    echo "使用方法:"
    echo "  $0 [success|failed|canceled]"
    echo ""
    echo "示例:"
    echo "  $0 success   # 测试支付成功流程"
    echo "  $0 failed    # 测试支付失败流程"
    echo "  $0 canceled  # 测试支付取消流程"
    exit 1
    ;;
esac

echo -e "📋 测试场景: ${GREEN}${SCENARIO_NAME}${NC}"
echo ""

# ============================================
# 步骤 1: 检查前置条件
# ============================================

echo -e "${YELLOW}🔍 步骤 1: 检查前置条件${NC}"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# 检查 API 服务
echo -n "  检查 API 服务... "
if curl -s -f "$API_BASE_URL/health" > /dev/null 2>&1; then
  echo -e "${GREEN}✅ 运行中${NC}"
else
  echo -e "${RED}❌ 未运行${NC}"
  echo ""
  echo "请先启动后端服务:"
  echo "  uv run python run.py"
  exit 1
fi

# 检查 Stripe CLI
echo -n "  检查 Stripe CLI... "
if command -v stripe &> /dev/null; then
  echo -e "${GREEN}✅ 已安装${NC}"
else
  echo -e "${RED}❌ 未安装${NC}"
  echo ""
  echo "请安装 Stripe CLI:"
  echo "  macOS: brew install stripe/stripe-cli/stripe"
  echo "  Linux: https://github.com/stripe/stripe-cli/releases"
  exit 1
fi

# 检查 jq
echo -n "  检查 jq 工具... "
if command -v jq &> /dev/null; then
  echo -e "${GREEN}✅ 已安装${NC}"
else
  echo -e "${RED}❌ 未安装${NC}"
  echo ""
  echo "请安装 jq:"
  echo "  macOS: brew install jq"
  echo "  Linux: apt-get install jq 或 yum install jq"
  exit 1
fi

echo ""

# ============================================
# 步骤 2: 创建支付意图
# ============================================

echo -e "${YELLOW}💳 步骤 2: 创建支付意图${NC}"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

TIMESTAMP=$(date +%s)
EMAIL="test_${TIMESTAMP}@example.com"

PAYLOAD=$(cat <<EOF
{
  "product_name": "测试 - ${SCENARIO_NAME}",
  "trade_num": 1,
  "amount": 999,
  "currency": "usd",
  "email": "$EMAIL",
  "phone": "+1234567890"
}
EOF
)

echo "  请求数据:"
echo "$PAYLOAD" | jq .

RESPONSE=$(curl -s -X POST "$API_BASE_URL/stripe/create-payment-intent" \
  -H "Content-Type: application/json" \
  -d "$PAYLOAD")

echo ""
echo "  响应数据:"
echo "$RESPONSE" | jq .

# 提取关键信息
SUCCESS=$(echo "$RESPONSE" | jq -r '.success')
ORDER_ID=$(echo "$RESPONSE" | jq -r '.order_id')
PAYMENT_INTENT_ID=$(echo "$RESPONSE" | jq -r '.payment_intent_id')
CLIENT_SECRET=$(echo "$RESPONSE" | jq -r '.client_secret')

if [ "$SUCCESS" != "true" ]; then
  echo -e "${RED}❌ 创建支付意图失败${NC}"
  exit 1
fi

echo ""
echo -e "  ${GREEN}✅ 支付意图创建成功${NC}"
echo -e "  订单ID: ${BLUE}$ORDER_ID${NC}"
echo -e "  Payment Intent ID: ${BLUE}$PAYMENT_INTENT_ID${NC}"
echo ""

# ============================================
# 步骤 3: 使用 Stripe CLI 确认支付
# ============================================

echo -e "${YELLOW}⚡ 步骤 3: 使用 Stripe CLI 确认支付${NC}"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

if [ "$PAYMENT_SCENARIO" == "canceled" ]; then
  # 取消支付
  echo "  执行命令: stripe payment_intents cancel $PAYMENT_INTENT_ID"
  stripe payment_intents cancel "$PAYMENT_INTENT_ID" > /dev/null 2>&1
  echo -e "  ${GREEN}✅ 支付已取消${NC}"
else
  # 确认支付
  echo "  执行命令: stripe payment_intents confirm $PAYMENT_INTENT_ID --payment-method $PAYMENT_METHOD"

  if stripe payment_intents confirm "$PAYMENT_INTENT_ID" --payment-method "$PAYMENT_METHOD" > /dev/null 2>&1; then
    echo -e "  ${GREEN}✅ 支付确认成功${NC}"
  else
    if [ "$PAYMENT_SCENARIO" == "failed" ]; then
      echo -e "  ${GREEN}✅ 支付按预期失败${NC}"
    else
      echo -e "  ${RED}❌ 支付确认失败${NC}"
      exit 1
    fi
  fi
fi

echo ""
echo "  等待 webhook 处理... (3秒)"
sleep 3
echo ""

# ============================================
# 步骤 4: 验证订单状态
# ============================================

echo -e "${YELLOW}🔎 步骤 4: 验证订单状态${NC}"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

STATUS_RESPONSE=$(curl -s "$API_BASE_URL/stripe/payment-status/$ORDER_ID")

echo "  订单状态查询结果:"
echo "$STATUS_RESPONSE" | jq .

STRIPE_STATUS=$(echo "$STATUS_RESPONSE" | jq -r '.stripe_payment_status')
ORDER_STATUS=$(echo "$STATUS_RESPONSE" | jq -r '.order_status')

echo ""
echo -e "  Stripe 支付状态: ${BLUE}$STRIPE_STATUS${NC}"
echo -e "  订单状态: ${BLUE}$ORDER_STATUS${NC}"
echo ""

# 验证状态
if [ "$STRIPE_STATUS" == "$EXPECTED_STATUS" ]; then
  echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
  echo -e "${GREEN}✅ 测试通过! 支付状态符合预期: $EXPECTED_STATUS${NC}"
  echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
else
  echo -e "${RED}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
  echo -e "${RED}❌ 测试失败! 期望: $EXPECTED_STATUS, 实际: $STRIPE_STATUS${NC}"
  echo -e "${RED}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
  exit 1
fi

echo ""
echo "📝 测试摘要:"
echo "  - 测试场景: $SCENARIO_NAME"
echo "  - 订单ID: $ORDER_ID"
echo "  - Payment Intent ID: $PAYMENT_INTENT_ID"
echo "  - 客户邮箱: $EMAIL"
echo "  - 支付状态: $STRIPE_STATUS"
echo "  - 订单状态: $ORDER_STATUS"
echo ""
