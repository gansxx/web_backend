# 阿里云 Function Compute 部署指南

本指南详细说明如何将 Web Backend API 部署到阿里云 Function Compute（函数计算）服务。

## 目录

- [概述](#概述)
- [前置条件](#前置条件)
- [快速开始](#快速开始)
- [详细步骤](#详细步骤)
- [配置说明](#配置说明)
- [常见问题](#常见问题)
- [最佳实践](#最佳实践)
- [故障排除](#故障排除)

---

## 概述

### 什么是 Function Compute？

阿里云函数计算（FC）是事件驱动的全托管计算服务，支持：
- **按需计费**：按实际调用次数和执行时间付费
- **自动弹性伸缩**：根据请求量自动扩缩容
- **零运维**：无需管理服务器
- **容器支持**：支持 Custom Container 运行时

### 部署架构

```
┌─────────────┐
│   用户请求   │
└──────┬──────┘
       │
       ▼
┌─────────────────────────────┐
│  HTTP 触发器 / 自定义域名    │
└──────┬──────────────────────┘
       │
       ▼
┌─────────────────────────────┐
│   Function Compute 实例     │
│  ┌─────────────────────┐   │
│  │  容器运行时          │   │
│  │  - FastAPI          │   │
│  │  - Gunicorn         │   │
│  │  - Python 3.12      │   │
│  └─────────────────────┘   │
└──────┬──────────────────────┘
       │
       ▼
┌─────────────────────────────┐
│   Supabase / 数据库         │
└─────────────────────────────┘
```

---

## 前置条件

### 1. 阿里云账号和权限

需要以下权限：
- **Function Compute（FC）**：创建服务、函数、触发器
- **容器镜像服务（ACR）**：推送和拉取镜像
- **RAM**：创建服务角色（如需访问其他云服务）
- **VPC**：配置 VPC 网络（可选）
- **日志服务（SLS）**：存储函数日志（可选）

### 2. 本地环境

```bash
# 必需工具
- Docker (>= 20.10)
- Terraform (>= 1.0)
- uv (Python 包管理器)
- bash
- curl

# 验证安装
docker --version
terraform --version
uv --version
```

### 3. 创建阿里云容器镜像服务命名空间

1. 登录[阿里云 ACR 控制台](https://cr.console.aliyun.com/)
2. 创建命名空间（例如：`web-backend`）
3. 记录注册表地址（例如：`registry.cn-shenzhen.aliyuncs.com`）

---

## 快速开始

### 方式一：一键部署（推荐）

```bash
# 1. 配置环境变量
cd /home/user/web_backend
cp deployment/.env.fc.example .env.fc
vim .env.fc  # 填写阿里云凭证和 ACR 配置

# 合并到主 .env 文件
cat .env.fc >> .env

# 2. 配置 Terraform 变量
cd deployment
cp terraform_fc.tfvars.example terraform_fc.tfvars
vim terraform_fc.tfvars  # 填写配置

# 3. 执行部署
./deploy_fc.sh
```

### 方式二：分步部署

```bash
# 步骤 1: 构建并推送镜像
cd deployment
./build_and_push_image.sh

# 步骤 2: 初始化 Terraform
terraform init

# 步骤 3: 预览部署计划
terraform plan -var-file=terraform_fc.tfvars

# 步骤 4: 执行部署
terraform apply -var-file=terraform_fc.tfvars
```

---

## 详细步骤

### 步骤 1: 配置环境变量

编辑项目根目录的 `.env` 文件，添加以下配置：

```bash
# 阿里云认证
ALICLOUD_ACCESS_KEY=LTAI5t...
ALICLOUD_SECRET_KEY=your-secret-key

# ACR 配置
ACR_REGISTRY=registry.cn-shenzhen.aliyuncs.com
ACR_NAMESPACE=web-backend

# 镜像配置（可选）
IMAGE_NAME=web-backend
IMAGE_TAG=latest
```

### 步骤 2: 配置 Terraform 变量

编辑 `deployment/terraform_fc.tfvars`：

```hcl
# 基础配置
region = "cn-shenzhen"
alicloud_access_key = "LTAI5t..."  # 或从环境变量读取
alicloud_secret_key = "your-secret-key"

# 容器镜像
container_image = "registry.cn-shenzhen.aliyuncs.com/web-backend/web-backend:latest"
container_port = 9000

# 资源配置
memory_size = 512
timeout = 300
instance_concurrency = 100

# 环境变量（敏感信息）
environment_variables = {
  SUPABASE_URL = "https://your-project.supabase.co"
  ANON_KEY = "eyJhbG..."
  SERVICE_ROLE_KEY = "eyJhbG..."
  POSTGRES_PASSWORD = "your-password"
  JWT_SECRET = "your-jwt-secret"
  FRONTEND_URL = "https://app.selfgo.asia"
}
```

### 步骤 3: 构建容器镜像

```bash
cd deployment

# 构建并推送镜像
./build_and_push_image.sh

# 或手动操作
cd ..
docker build -f Dockerfile.fc -t web-backend:latest --platform linux/amd64 .
docker tag web-backend:latest registry.cn-shenzhen.aliyuncs.com/web-backend/web-backend:latest
docker push registry.cn-shenzhen.aliyuncs.com/web-backend/web-backend:latest
```

### 步骤 4: 初始化 Terraform

```bash
cd deployment
terraform init
```

输出示例：
```
Initializing the backend...
Initializing provider plugins...
- Finding aliyun/alicloud versions matching ">= 1.203.0"...
- Installing aliyun/alicloud v1.262.0...

Terraform has been successfully initialized!
```

### 步骤 5: 预览部署计划

```bash
terraform plan -var-file=terraform_fc.tfvars
```

检查以下内容：
- ✅ 服务和函数配置正确
- ✅ 镜像地址正确
- ✅ 环境变量已设置
- ✅ 资源配置合理

### 步骤 6: 执行部署

```bash
terraform apply -var-file=terraform_fc.tfvars
```

部署时间：约 2-5 分钟

### 步骤 7: 验证部署

```bash
# 获取触发器 URL
TRIGGER_URL=$(terraform output -raw http_trigger_url)

# 测试健康检查
curl "${TRIGGER_URL}/health"

# 预期输出
# {"status": "healthy"}
```

---

## 配置说明

### 核心配置

| 配置项 | 说明 | 默认值 | 范围 |
|--------|------|--------|------|
| `memory_size` | 内存大小（MB） | 512 | 128-32768 |
| `cpu_size` | CPU 核数 | 自动 | 0.05-16 |
| `timeout` | 超时时间（秒） | 300 | 1-600 |
| `instance_concurrency` | 单实例并发数 | 100 | 1-200 |
| `container_port` | 容器端口 | 9000 | 1-65535 |

### 高级功能

#### 1. 自定义域名

```hcl
enable_custom_domain = true
custom_domain_name = "api.selfgo.asia"
enable_https = true

# 需要提供 SSL 证书
ssl_cert_name = "selfgo-ssl"
ssl_certificate = file("path/to/cert.pem")
ssl_private_key = file("path/to/key.pem")
```

#### 2. VPC 网络（访问 RDS/Redis）

```hcl
enable_vpc = true
vpc_id = "vpc-xxx"
vswitch_ids = ["vsw-xxx", "vsw-yyy"]
security_group_id = "sg-xxx"
```

#### 3. 预留实例（避免冷启动）

```hcl
enable_provision = true
provision_target = 2  # 保持 2 个实例常驻

# 定时伸缩
provision_scheduled_actions = [
  {
    name = "scale-up"
    schedule_expression = "cron(0 8 * * ? *)"  # 每天 8:00
    target = 5
  },
  {
    name = "scale-down"
    schedule_expression = "cron(0 22 * * ? *)"  # 每天 22:00
    target = 1
  }
]
```

#### 4. 日志服务

```hcl
enable_logging = true
sls_project = "fc-logs"
sls_logstore = "web-backend-logs"
```

#### 5. 灰度发布

```hcl
enable_alias = true
alias_version_id = "1"

# 90% 流量到版本 1，10% 到版本 2
canary_version_weight = {
  "1" = 90
  "2" = 10
}
```

---

## 常见问题

### Q1: 如何更新函数？

**方法 1: 更新代码**
```bash
# 1. 修改代码
# 2. 重新构建并推送镜像
./build_and_push_image.sh

# 3. 更新函数（Terraform 会检测镜像变化）
terraform apply -var-file=terraform_fc.tfvars
```

**方法 2: 使用新标签**
```bash
# 1. 构建新版本
IMAGE_TAG=v1.2.0 ./build_and_push_image.sh

# 2. 更新 terraform_fc.tfvars
container_image = "registry.cn-shenzhen.aliyuncs.com/web-backend/web-backend:v1.2.0"

# 3. 应用更新
terraform apply -var-file=terraform_fc.tfvars
```

### Q2: 如何查看日志？

**方法 1: 阿里云控制台**
1. 登录 [FC 控制台](https://fc.console.aliyun.com/)
2. 选择服务 → 函数 → 调用日志

**方法 2: 命令行（需要配置 SLS）**
```bash
# 使用阿里云 CLI
aliyun log get_logs \
  --project=fc-logs \
  --logstore=web-backend-logs \
  --from=-3600 \
  --to=now
```

### Q3: 冷启动时间太长怎么办？

**优化建议：**

1. **启用预留实例**
   ```hcl
   enable_provision = true
   provision_target = 1  # 至少保持 1 个实例
   ```

2. **启用镜像加速**
   ```hcl
   enable_image_acceleration = true
   ```

3. **减小镜像大小**
   - 使用多阶段构建
   - 清理不必要的依赖
   - 使用 Alpine 基础镜像

4. **增加内存**
   ```hcl
   memory_size = 1024  # 更多内存 = 更多 CPU = 更快启动
   ```

### Q4: 如何访问 VPC 内资源？

```hcl
# 1. 配置 VPC
enable_vpc = true
vpc_id = "vpc-xxx"
vswitch_ids = ["vsw-xxx"]
security_group_id = "sg-xxx"

# 2. 确保安全组规则允许访问
# 3. 数据库连接字符串使用内网地址
```

### Q5: 函数超时怎么办？

```hcl
# 1. 增加超时时间（最大 600 秒）
timeout = 600

# 2. 同时增加 Gunicorn 超时
environment_variables = {
  GUNICORN_TIMEOUT = "600"
}
```

### Q6: 如何配置自定义域名？

```bash
# 1. 在 terraform_fc.tfvars 中配置
enable_custom_domain = true
custom_domain_name = "api.selfgo.asia"

# 2. 在 DNS 提供商添加 CNAME 记录
# api.selfgo.asia CNAME xxx.cn-shenzhen.fc.aliyuncs.com

# 3. 配置 SSL 证书（推荐）
enable_https = true
ssl_certificate = file("cert.pem")
ssl_private_key = file("key.pem")
```

---

## 最佳实践

### 1. 成本优化

```hcl
# 开发环境：按量付费
enable_provision = false
memory_size = 512
instance_concurrency = 100

# 生产环境：预留实例 + 弹性伸缩
enable_provision = true
provision_target = 2  # 基础预留

provision_target_tracking_policies = [
  {
    name = "cpu-tracking"
    metric_type = "ProvisionedConcurrencyUtilization"
    metric_target = 0.7  # 70% 利用率时扩容
  }
]
```

### 2. 安全加固

```hcl
# 1. 启用 VPC（函数无法直接访问公网，更安全）
enable_vpc = true

# 2. 启用 HTTPS
enable_https = true

# 3. 使用函数签名认证
http_auth_type = "function"

# 4. 敏感信息使用 KMS 加密
environment_variables = {
  DB_PASSWORD = "kms://encrypted-value"
}
```

### 3. 高可用部署

```hcl
# 1. 多可用区部署
vswitch_ids = ["vsw-zone-a", "vsw-zone-b"]

# 2. 健康检查
# 确保应用实现 /health 端点

# 3. 监控告警
# 在阿里云 CloudMonitor 配置告警规则：
# - 函数错误率 > 5%
# - 函数超时次数 > 10
# - 函数并发数 > 阈值
```

### 4. CI/CD 集成

```yaml
# GitHub Actions 示例
name: Deploy to FC

on:
  push:
    branches: [main]

jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3

      - name: Build and Push Image
        env:
          ALICLOUD_ACCESS_KEY: ${{ secrets.ALICLOUD_ACCESS_KEY }}
          ALICLOUD_SECRET_KEY: ${{ secrets.ALICLOUD_SECRET_KEY }}
        run: |
          cd deployment
          ./build_and_push_image.sh

      - name: Deploy to FC
        run: |
          cd deployment
          terraform init
          terraform apply -var-file=terraform_fc.tfvars -auto-approve
```

---

## 故障排除

### 问题 1: 镜像拉取失败

**错误信息：**
```
Failed to pull image: registry.cn-shenzhen.aliyuncs.com/xxx/xxx:latest
```

**解决方案：**
1. 检查镜像是否存在
   ```bash
   docker pull registry.cn-shenzhen.aliyuncs.com/xxx/xxx:latest
   ```

2. 检查 FC 服务角色权限
   - 需要 `AliyunContainerRegistryReadOnlyAccess` 权限

3. 检查镜像仓库是否为私有
   - 私有仓库需要配置访问凭证

### 问题 2: 函数执行超时

**错误信息：**
```
Function execution timeout after 300 seconds
```

**解决方案：**
```hcl
# 增加超时时间
timeout = 600

# 调整 Gunicorn 配置
environment_variables = {
  GUNICORN_TIMEOUT = "600"
  GUNICORN_WORKERS = "1"  # FC 建议单 worker
}
```

### 问题 3: 内存不足

**错误信息：**
```
Process exited due to OOM (Out of Memory)
```

**解决方案：**
```hcl
# 增加内存
memory_size = 1024  # 从 512 增加到 1024
```

### 问题 4: 无法连接数据库

**检查清单：**
1. ✅ 是否启用 VPC 配置？
2. ✅ 安全组规则是否允许？
3. ✅ 数据库地址是否正确（内网 vs 公网）？
4. ✅ 环境变量是否设置？

```bash
# 测试数据库连接
TRIGGER_URL=$(terraform output -raw http_trigger_url)
curl "${TRIGGER_URL}/health"  # 检查健康状态
```

### 问题 5: Terraform 状态锁定

**错误信息：**
```
Error: Error locking state
```

**解决方案：**
```bash
# 强制解锁（谨慎使用）
terraform force-unlock <LOCK_ID>
```

---

## 性能基准

### 冷启动时间

| 配置 | 冷启动时间 | 说明 |
|------|-----------|------|
| 512MB 内存 | ~3-5 秒 | 标准配置 |
| 1024MB 内存 | ~2-3 秒 | 推荐配置 |
| 预留实例 | ~100ms | 无冷启动 |
| 镜像加速 | ~1-2 秒 | 启用加速 |

### 并发性能

| 实例配置 | 单实例 QPS | 并发数 |
|---------|-----------|--------|
| 512MB / 100 并发 | ~500 | 100 |
| 1024MB / 100 并发 | ~800 | 100 |
| 预留 5 实例 | ~4000 | 500 |

---

## 成本估算

### 按量付费示例

假设：
- 每天 100 万次请求
- 平均执行时间 100ms
- 内存 512MB

**计算：**
```
调用次数费用 = 1,000,000 * 0.0000002 = 0.2 元/天
执行时间费用 = 1,000,000 * 0.1 * (512/1024) * 0.00003417 = 1.71 元/天

总计：约 2 元/天 = 60 元/月
```

### 预留实例示例

预留 2 个实例（512MB）：
```
预留费用 = 2 * 512 * 0.000039 * 24 * 30 = 约 28 元/月
调用费用 = 按量计费（同上）

总计：约 88 元/月
```

---

## 相关文档

- [阿里云 FC 官方文档](https://help.aliyun.com/product/50980.html)
- [Terraform Alicloud Provider](https://registry.terraform.io/providers/aliyun/alicloud/latest/docs)
- [Docker 多架构构建](https://docs.docker.com/build/building/multi-platform/)
- [FastAPI 生产部署](https://fastapi.tiangolo.com/deployment/)

---

## 联系支持

如遇问题，请：
1. 查看本文档的[故障排除](#故障排除)部分
2. 查看阿里云 FC 控制台的调用日志
3. 提交 Issue 到项目仓库

---

**最后更新**: 2025-11-14
**适用版本**: Terraform >= 1.0, Alicloud Provider >= 1.203.0
