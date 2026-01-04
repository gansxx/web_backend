#!/bin/bash
# =====================================================
# 构建并推送容器镜像到阿里云 ACR
# =====================================================
# 单独的镜像构建推送脚本，不涉及 Terraform 部署
# =====================================================

set -e

# 颜色输出
GREEN='\033[0;32m'
BLUE='\033[0;34m'
RED='\033[0;31m'
NC='\033[0m'

log_info() { echo -e "${BLUE}[INFO]${NC} $1"; }
log_success() { echo -e "${GREEN}[SUCCESS]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }

# =====================================================
# 加载配置
# =====================================================

if [ ! -f "../.env" ]; then
    log_error "未找到 .env 文件"
    exit 1
fi

source ../.env

# 检查必需变量
if [ -z "$ACR_REGISTRY" ] || [ -z "$ACR_NAMESPACE" ]; then
    log_error "请在 .env 中配置 ACR_REGISTRY 和 ACR_NAMESPACE"
    exit 1
fi

# 设置镜像信息
IMAGE_NAME="${IMAGE_NAME:-web-backend}"
IMAGE_TAG="${IMAGE_TAG:-latest}"
PLATFORM="${PLATFORM:-linux/amd64}"

FULL_IMAGE="${ACR_REGISTRY}/${ACR_NAMESPACE}/${IMAGE_NAME}:${IMAGE_TAG}"

log_info "镜像配置:"
log_info "  名称: ${IMAGE_NAME}"
log_info "  标签: ${IMAGE_TAG}"
log_info "  完整地址: ${FULL_IMAGE}"
log_info "  平台: ${PLATFORM}"

# =====================================================
# 构建镜像
# =====================================================

log_info "🔨 构建 Docker 镜像..."

cd ..  # 进入项目根目录

docker build \
    -f Dockerfile.fc \
    -t "${IMAGE_NAME}:${IMAGE_TAG}" \
    -t "${FULL_IMAGE}" \
    --platform "${PLATFORM}" \
    .

log_success "镜像构建完成"

cd deployment

# =====================================================
# 登录 ACR
# =====================================================

log_info "🔐 登录阿里云容器镜像服务..."

if [ -z "$ALICLOUD_ACCESS_KEY" ] || [ -z "$ALICLOUD_SECRET_KEY" ]; then
    log_error "请在 .env 中配置 ALICLOUD_ACCESS_KEY 和 ALICLOUD_SECRET_KEY"
    exit 1
fi

echo "${ALICLOUD_SECRET_KEY}" | docker login \
    --username="${ALICLOUD_ACCESS_KEY}" \
    --password-stdin \
    "${ACR_REGISTRY}"

log_success "登录成功"

# =====================================================
# 推送镜像
# =====================================================

log_info "📤 推送镜像到 ACR..."

docker push "${FULL_IMAGE}"

log_success "推送完成: ${FULL_IMAGE}"

# =====================================================
# 完成
# =====================================================

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "✅ 镜像已成功推送"
echo ""
echo "📋 镜像信息:"
echo "  ${FULL_IMAGE}"
echo ""
echo "📝 下一步:"
echo "  1. 在 terraform_fc.tfvars 中设置 container_image = \"${FULL_IMAGE}\""
echo "  2. 执行 ./deploy_fc.sh --skip-build --skip-push 部署到 FC"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
