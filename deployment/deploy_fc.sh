#!/bin/bash
# =====================================================
# 阿里云 Function Compute 自动部署脚本
# =====================================================
# 功能：
#   1. 构建容器镜像
#   2. 推送到阿里云容器镜像服务（ACR）
#   3. 使用 Terraform 部署 FC 函数
#   4. 输出访问地址
# =====================================================

set -e  # 遇到错误立即退出

# 颜色输出
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 日志函数
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# =====================================================
# 配置检查
# =====================================================

log_info "🔍 检查配置文件..."

# 检查是否在 deployment 目录
if [ ! -f "terraform_fc.tf" ]; then
    log_error "请在 deployment 目录下执行此脚本"
    exit 1
fi

# 检查环境变量文件
if [ ! -f "../.env" ]; then
    log_error "未找到 .env 文件"
    exit 1
fi

# 加载环境变量
log_info "📥 加载环境变量..."
source ../.env

# 检查必需的环境变量
required_vars=(
    "ALICLOUD_ACCESS_KEY"
    "ALICLOUD_SECRET_KEY"
    "ACR_REGISTRY"
    "ACR_NAMESPACE"
)

for var in "${required_vars[@]}"; do
    if [ -z "${!var}" ]; then
        log_error "环境变量 $var 未设置"
        exit 1
    fi
done

# 设置默认值
IMAGE_NAME="${IMAGE_NAME:-web-backend}"
IMAGE_TAG="${IMAGE_TAG:-latest}"
REGION="${REGION:-cn-shenzhen}"

# 完整镜像地址
FULL_IMAGE="${ACR_REGISTRY}/${ACR_NAMESPACE}/${IMAGE_NAME}:${IMAGE_TAG}"

log_success "配置检查完成"
log_info "  镜像地址: ${FULL_IMAGE}"
log_info "  区域: ${REGION}"

# =====================================================
# 选项解析
# =====================================================

SKIP_BUILD=false
SKIP_PUSH=false
SKIP_DEPLOY=false
DESTROY=false
TFVARS_FILE="terraform_fc.tfvars"

while [[ $# -gt 0 ]]; do
    case $1 in
        --skip-build)
            SKIP_BUILD=true
            shift
            ;;
        --skip-push)
            SKIP_PUSH=true
            shift
            ;;
        --skip-deploy)
            SKIP_DEPLOY=true
            shift
            ;;
        --destroy)
            DESTROY=true
            shift
            ;;
        --var-file)
            TFVARS_FILE="$2"
            shift 2
            ;;
        --help)
            echo "用法: $0 [选项]"
            echo ""
            echo "选项:"
            echo "  --skip-build      跳过镜像构建"
            echo "  --skip-push       跳过镜像推送"
            echo "  --skip-deploy     跳过 Terraform 部署"
            echo "  --destroy         销毁 FC 资源"
            echo "  --var-file FILE   指定变量文件（默认: terraform_fc.tfvars）"
            echo "  --help            显示帮助信息"
            echo ""
            echo "环境变量:"
            echo "  IMAGE_NAME        镜像名称（默认: web-backend）"
            echo "  IMAGE_TAG         镜像标签（默认: latest）"
            echo "  REGION            阿里云区域（默认: cn-shenzhen）"
            exit 0
            ;;
        *)
            log_error "未知选项: $1"
            exit 1
            ;;
    esac
done

# =====================================================
# 销毁模式
# =====================================================

if [ "$DESTROY" = true ]; then
    log_warning "⚠️  即将销毁 Function Compute 资源！"
    read -p "确认销毁？(yes/no): " confirm
    if [ "$confirm" != "yes" ]; then
        log_info "取消销毁"
        exit 0
    fi

    log_info "🗑️  执行 Terraform Destroy..."
    terraform destroy -var-file="${TFVARS_FILE}" -auto-approve

    log_success "✅ 资源已销毁"
    exit 0
fi

# =====================================================
# 步骤 1: 构建 Docker 镜像
# =====================================================

if [ "$SKIP_BUILD" = false ]; then
    log_info "🔨 开始构建 Docker 镜像..."

    cd ..  # 回到项目根目录

    # 使用 Dockerfile.fc
    docker build \
        -f Dockerfile.fc \
        -t "${IMAGE_NAME}:${IMAGE_TAG}" \
        -t "${FULL_IMAGE}" \
        --platform linux/amd64 \
        .

    log_success "镜像构建完成: ${IMAGE_NAME}:${IMAGE_TAG}"

    cd deployment  # 返回 deployment 目录
else
    log_warning "⏭️  跳过镜像构建"
fi

# =====================================================
# 步骤 2: 推送镜像到 ACR
# =====================================================

if [ "$SKIP_PUSH" = false ]; then
    log_info "📤 登录阿里云容器镜像服务..."

    # 登录 ACR
    echo "${ALICLOUD_SECRET_KEY}" | docker login \
        --username="${ALICLOUD_ACCESS_KEY}" \
        --password-stdin \
        "${ACR_REGISTRY}"

    log_success "ACR 登录成功"

    log_info "📤 推送镜像到 ACR..."
    docker push "${FULL_IMAGE}"

    log_success "镜像推送完成: ${FULL_IMAGE}"
else
    log_warning "⏭️  跳过镜像推送"
fi

# =====================================================
# 步骤 3: Terraform 部署
# =====================================================

if [ "$SKIP_DEPLOY" = false ]; then
    log_info "🚀 开始 Terraform 部署..."

    # 检查变量文件
    if [ ! -f "${TFVARS_FILE}" ]; then
        log_error "变量文件不存在: ${TFVARS_FILE}"
        log_info "请基于 terraform_fc.tfvars.example 创建配置文件"
        exit 1
    fi

    # 初始化 Terraform（如果需要）
    if [ ! -d ".terraform" ]; then
        log_info "📦 初始化 Terraform..."
        terraform init
    fi

    # 执行 Terraform Plan
    log_info "📋 生成执行计划..."
    terraform plan -var-file="${TFVARS_FILE}" -out=tfplan

    # 确认部署
    log_warning "⚠️  即将部署到阿里云 Function Compute"
    read -p "确认部署？(yes/no): " confirm
    if [ "$confirm" != "yes" ]; then
        log_info "取消部署"
        rm -f tfplan
        exit 0
    fi

    # 执行部署
    log_info "🚀 执行部署..."
    terraform apply tfplan

    # 清理计划文件
    rm -f tfplan

    log_success "✅ 部署完成！"

    # 输出访问地址
    log_info "📡 获取访问地址..."
    echo ""
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    terraform output -json | python3 -c "
import json
import sys
data = json.load(sys.stdin)
print('🌐 访问地址:')
print(f\"  公网: {data.get('http_trigger_url', {}).get('value', 'N/A')}\")
print(f\"  内网: {data.get('http_trigger_url_intranet', {}).get('value', 'N/A')}\")
if data.get('custom_domain_url', {}).get('value'):
    print(f\"  自定义域名: {data['custom_domain_url']['value']}\")
print()
print('🎯 镜像信息:')
print(f\"  {data.get('container_image', {}).get('value', 'N/A')}\")
print()
print('📦 函数信息:')
print(f\"  ARN: {data.get('function_arn', {}).get('value', 'N/A')}\")
"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo ""

    # 测试健康检查
    log_info "🏥 测试健康检查..."
    TRIGGER_URL=$(terraform output -json | python3 -c "import json,sys; print(json.load(sys.stdin).get('http_trigger_url', {}).get('value', ''))")

    if [ -n "$TRIGGER_URL" ]; then
        sleep 5  # 等待函数启动
        if curl -f -s "${TRIGGER_URL}/health" > /dev/null; then
            log_success "健康检查通过"
        else
            log_warning "健康检查失败（函数可能还在初始化）"
        fi
    fi

else
    log_warning "⏭️  跳过 Terraform 部署"
fi

# =====================================================
# 完成
# =====================================================

log_success "🎉 所有步骤完成！"

# 显示后续操作建议
echo ""
echo "📝 后续操作:"
echo "  1. 测试 API: curl \${TRIGGER_URL}/health"
echo "  2. 查看日志: 阿里云控制台 -> 函数计算 -> 日志查询"
echo "  3. 更新函数: 修改代码后重新运行此脚本"
echo "  4. 销毁资源: $0 --destroy"
echo ""
