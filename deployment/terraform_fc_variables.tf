# =====================================================
# Terraform Variables for Function Compute Deployment
# =====================================================

# =====================================================
# 阿里云基础配置
# =====================================================

variable "region" {
  description = "阿里云地域"
  type        = string
  default     = "cn-shenzhen"
}

variable "alicloud_access_key" {
  description = "阿里云 Access Key"
  type        = string
  sensitive   = true
}

variable "alicloud_secret_key" {
  description = "阿里云 Secret Key"
  type        = string
  sensitive   = true
}

# =====================================================
# FC 服务配置
# =====================================================

variable "fc_service_name" {
  description = "FC 服务名称"
  type        = string
  default     = "web-backend-service"
}

variable "fc_function_name" {
  description = "FC 函数名称"
  type        = string
  default     = "web-api"
}

variable "fc_role_arn" {
  description = "FC 服务角色 ARN（用于访问其他阿里云服务）"
  type        = string
  default     = ""
}

# =====================================================
# 容器镜像配置
# =====================================================

variable "container_image" {
  description = "容器镜像地址（ACR 地址）"
  type        = string
  # 示例: registry.cn-shenzhen.aliyuncs.com/your-namespace/web-backend:latest
}

variable "container_port" {
  description = "容器监听端口"
  type        = number
  default     = 9000
}

variable "container_command" {
  description = "容器启动命令（可选，默认使用 Dockerfile CMD）"
  type        = list(string)
  default     = []
}

variable "container_args" {
  description = "容器启动参数（可选）"
  type        = list(string)
  default     = []
}

variable "enable_image_acceleration" {
  description = "是否启用镜像加速"
  type        = bool
  default     = true
}

# =====================================================
# 函数资源配置
# =====================================================

variable "memory_size" {
  description = "函数内存大小（MB）"
  type        = number
  default     = 512
  validation {
    condition     = var.memory_size >= 128 && var.memory_size <= 32768
    error_message = "内存大小必须在 128MB 到 32768MB 之间"
  }
}

variable "cpu_size" {
  description = "CPU 核数（可选，默认根据内存自动分配）"
  type        = number
  default     = null
}

variable "timeout" {
  description = "函数超时时间（秒）"
  type        = number
  default     = 300
  validation {
    condition     = var.timeout >= 1 && var.timeout <= 600
    error_message = "超时时间必须在 1 秒到 600 秒之间"
  }
}

variable "disk_size" {
  description = "临时磁盘大小（MB）"
  type        = number
  default     = 512
}

variable "instance_concurrency" {
  description = "单个实例并发数"
  type        = number
  default     = 100
  validation {
    condition     = var.instance_concurrency >= 1 && var.instance_concurrency <= 200
    error_message = "实例并发数必须在 1 到 200 之间"
  }
}

# =====================================================
# 环境变量配置
# =====================================================

variable "environment_variables" {
  description = "函数环境变量"
  type        = map(string)
  default     = {}
  sensitive   = true
}

# =====================================================
# HTTP 触发器配置
# =====================================================

variable "http_auth_type" {
  description = "HTTP 触发器认证类型"
  type        = string
  default     = "anonymous"
  validation {
    condition     = contains(["anonymous", "function"], var.http_auth_type)
    error_message = "认证类型必须是 anonymous 或 function"
  }
}

variable "trigger_role_arn" {
  description = "触发器角色 ARN"
  type        = string
  default     = ""
}

# =====================================================
# 自定义域名配置
# =====================================================

variable "enable_custom_domain" {
  description = "是否启用自定义域名"
  type        = bool
  default     = false
}

variable "custom_domain_name" {
  description = "自定义域名（例如：api.example.com）"
  type        = string
  default     = ""
}

variable "enable_https" {
  description = "是否启用 HTTPS"
  type        = bool
  default     = true
}

variable "ssl_cert_name" {
  description = "SSL 证书名称"
  type        = string
  default     = ""
}

variable "ssl_certificate" {
  description = "SSL 证书内容（PEM 格式）"
  type        = string
  default     = ""
  sensitive   = true
}

variable "ssl_private_key" {
  description = "SSL 私钥内容（PEM 格式）"
  type        = string
  default     = ""
  sensitive   = true
}

variable "enable_waf" {
  description = "是否启用 WAF 防护"
  type        = bool
  default     = false
}

# =====================================================
# VPC 网络配置
# =====================================================

variable "enable_vpc" {
  description = "是否启用 VPC 网络"
  type        = bool
  default     = false
}

variable "vpc_id" {
  description = "VPC ID"
  type        = string
  default     = ""
}

variable "vswitch_ids" {
  description = "交换机 ID 列表"
  type        = list(string)
  default     = []
}

variable "security_group_id" {
  description = "安全组 ID"
  type        = string
  default     = ""
}

variable "internet_access" {
  description = "函数是否可访问公网"
  type        = bool
  default     = true
}

# =====================================================
# 日志配置
# =====================================================

variable "enable_logging" {
  description = "是否启用日志服务"
  type        = bool
  default     = false
}

variable "sls_project" {
  description = "SLS 项目名称"
  type        = string
  default     = ""
}

variable "sls_logstore" {
  description = "SLS 日志库名称"
  type        = string
  default     = ""
}

# =====================================================
# NAS 存储配置
# =====================================================

variable "enable_nas" {
  description = "是否启用 NAS 存储"
  type        = bool
  default     = false
}

variable "nas_user_id" {
  description = "NAS 用户 ID"
  type        = number
  default     = 10003
}

variable "nas_group_id" {
  description = "NAS 组 ID"
  type        = number
  default     = 10003
}

variable "nas_mount_points" {
  description = "NAS 挂载点配置"
  type = list(object({
    server_addr = string
    mount_dir   = string
  }))
  default = []
}

# =====================================================
# 预留实例配置（避免冷启动）
# =====================================================

variable "enable_provision" {
  description = "是否启用预留实例"
  type        = bool
  default     = false
}

variable "provision_target" {
  description = "预留实例数量"
  type        = number
  default     = 1
}

variable "provision_scheduled_actions" {
  description = "定时伸缩配置"
  type = list(object({
    name             = string
    schedule_expression = string
    target           = number
  }))
  default = []
}

variable "provision_target_tracking_policies" {
  description = "目标追踪策略"
  type = list(object({
    name        = string
    metric_type = string
    metric_target = number
  }))
  default = []
}

# =====================================================
# 别名和版本配置（灰度发布）
# =====================================================

variable "enable_alias" {
  description = "是否启用别名"
  type        = bool
  default     = false
}

variable "alias_version_id" {
  description = "别名指向的版本 ID"
  type        = string
  default     = ""
}

variable "canary_version_weight" {
  description = "灰度版本流量权重配置（版本ID => 权重百分比）"
  type        = map(number)
  default     = {}
}

# =====================================================
# 异步调用配置
# =====================================================

variable "enable_async_invoke" {
  description = "是否启用异步调用配置"
  type        = bool
  default     = false
}

variable "async_max_event_age" {
  description = "异步事件最大存活时间（秒）"
  type        = number
  default     = 3600
}

variable "async_max_retry_attempts" {
  description = "异步调用最大重试次数"
  type        = number
  default     = 2
}

variable "async_failure_destination" {
  description = "异步调用失败后的目标（MNS Topic ARN）"
  type        = string
  default     = ""
}

variable "async_success_destination" {
  description = "异步调用成功后的目标（MNS Topic ARN）"
  type        = string
  default     = ""
}

# =====================================================
# DNS 自动更新配置
# =====================================================

variable "enable_dns_update" {
  description = "是否自动更新 DNS"
  type        = bool
  default     = false
}
