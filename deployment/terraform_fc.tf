# =====================================================
# 阿里云 Function Compute 容器部署配置
# =====================================================
# 功能说明：
#   - 部署 Web Backend API 到阿里云 Function Compute
#   - 支持容器镜像方式部署（Custom Container）
#   - 自动配置 HTTP 触发器和自定义域名
#   - 支持 VPC 网络访问（可选，用于访问 RDS/Redis 等）
# =====================================================

terraform {
  required_version = ">= 1.0"

  required_providers {
    alicloud = {
      source  = "aliyun/alicloud"
      version = ">= 1.203.0"
    }
  }
}

# =====================================================
# Provider 配置
# =====================================================

provider "alicloud" {
  region     = var.region
  access_key = var.alicloud_access_key
  secret_key = var.alicloud_secret_key
}

# =====================================================
# FC 服务定义
# =====================================================

resource "alicloud_fc_service" "web_backend" {
  name        = var.fc_service_name
  description = "Web Backend API Service - FastAPI + Supabase"

  # 日志配置（可选）
  dynamic "log_config" {
    for_each = var.enable_logging ? [1] : []
    content {
      project                 = var.sls_project
      logstore                = var.sls_logstore
      enable_instance_metrics = true
      enable_request_metrics  = true
    }
  }

  # VPC 配置（如果需要访问私有网络资源）
  dynamic "vpc_config" {
    for_each = var.enable_vpc ? [1] : []
    content {
      vpc_id            = var.vpc_id
      vswitch_ids       = var.vswitch_ids
      security_group_id = var.security_group_id
    }
  }

  # NAS 配置（如果需要持久化存储）
  dynamic "nas_config" {
    for_each = var.enable_nas ? [1] : []
    content {
      user_id  = var.nas_user_id
      group_id = var.nas_group_id

      dynamic "mount_points" {
        for_each = var.nas_mount_points
        content {
          server_addr = mount_points.value.server_addr
          mount_dir   = mount_points.value.mount_dir
        }
      }
    }
  }

  # 角色配置（访问其他阿里云服务的权限）
  role = var.fc_role_arn != "" ? var.fc_role_arn : null

  # 互联网访问（如果函数需要访问外网）
  internet_access = var.internet_access
}

# =====================================================
# FC 函数定义（容器镜像模式）
# =====================================================

resource "alicloud_fc3_function" "web_api" {
  function_name = var.fc_function_name
  description   = "Web Backend API - Main FastAPI Application"

  # 运行时配置
  runtime = "custom-container"
  handler = "not-used"  # 容器模式下不使用

  # 容器镜像配置
  custom_container_config {
    image = var.container_image
    port  = var.container_port

    # 启动命令（可选，默认使用 Dockerfile CMD）
    command = var.container_command
    args    = var.container_args

    # 镜像加速（可选）
    acceleration_type = var.enable_image_acceleration ? "Default" : "None"
  }

  # 资源配置
  memory_size = var.memory_size  # MB
  timeout     = var.timeout      # 秒

  # 实例并发数（单个实例可处理的并发请求数）
  instance_concurrency = var.instance_concurrency

  # 环境变量
  environment_variables = merge(
    var.environment_variables,
    {
      # FC 特定配置
      BIND_ADDRESS      = "0.0.0.0:${var.container_port}"
      ENVIRONMENT       = "production"
      USE_GUNICORN      = "true"
      GUNICORN_WORKERS  = "1"  # FC 建议单 worker
      GUNICORN_TIMEOUT  = tostring(var.timeout)
    }
  )

  # CPU 配置（可选）
  cpu = var.cpu_size

  # 磁盘大小（临时存储）
  disk_size = var.disk_size

  # 实例生命周期配置
  instance_lifecycle_config {
    pre_freeze {
      handler = ""
      timeout = 3
    }
    pre_stop {
      handler = ""
      timeout = 3
    }
  }
}

# =====================================================
# HTTP 触发器
# =====================================================

resource "alicloud_fc3_trigger" "http" {
  function_name = alicloud_fc3_function.web_api.function_name
  trigger_name  = "${var.fc_function_name}-http-trigger"
  description   = "HTTP Trigger for Web API"

  trigger_type = "http"

  trigger_config = jsonencode({
    authType = var.http_auth_type  # anonymous, function
    methods  = ["GET", "POST", "PUT", "DELETE", "PATCH", "HEAD", "OPTIONS"]

    # 是否禁用 URL 解码（建议启用）
    disableURLInternet = false
  })

  # 调用方式
  invocation_role = var.trigger_role_arn != "" ? var.trigger_role_arn : null

  # 限流配置（可选）
  qualifier = "LATEST"
}

# =====================================================
# 自定义域名（可选）
# =====================================================

resource "alicloud_fc3_custom_domain" "api" {
  count = var.enable_custom_domain ? 1 : 0

  custom_domain_name = var.custom_domain_name
  protocol           = var.enable_https ? "HTTP,HTTPS" : "HTTP"

  # 路由配置
  route_config {
    routes {
      path          = "/*"
      function_name = alicloud_fc3_function.web_api.function_name
      qualifier     = "LATEST"

      # 重写配置（可选）
      # rewrite_config {
      #   equal_rules {
      #     match       = "/api/v1"
      #     replacement = "/"
      #   }
      # }
    }
  }

  # TLS 配置
  dynamic "tls_config" {
    for_each = var.enable_https ? [1] : []
    content {
      min_version    = "TLSv1.2"
      max_version    = "TLSv1.3"
      cipher_suites  = ["TLS_ECDHE_RSA_WITH_AES_128_GCM_SHA256", "TLS_ECDHE_RSA_WITH_AES_256_GCM_SHA384"]

      # SSL 证书配置
      cert_config {
        cert_name   = var.ssl_cert_name
        certificate = var.ssl_certificate
        private_key = var.ssl_private_key
      }
    }
  }

  # WAF 配置（可选）
  waf_config {
    enable_waf = var.enable_waf
  }
}

# =====================================================
# 预留实例（可选 - 用于避免冷启动）
# =====================================================

resource "alicloud_fc3_provision_config" "web_api_provision" {
  count = var.enable_provision ? 1 : 0

  function_name = alicloud_fc3_function.web_api.function_name

  # 预留实例配置
  target                  = var.provision_target  # 预留实例数量
  always_allocate_cpu     = true
  scheduled_actions       = var.provision_scheduled_actions
  target_tracking_policies = var.provision_target_tracking_policies
}

# =====================================================
# 别名配置（可选 - 用于灰度发布）
# =====================================================

resource "alicloud_fc3_alias" "production" {
  count = var.enable_alias ? 1 : 0

  alias_name    = "production"
  function_name = alicloud_fc3_function.web_api.function_name
  description   = "Production environment alias"

  version_id = var.alias_version_id != "" ? var.alias_version_id : "LATEST"

  # 灰度流量配置（可选）
  dynamic "additional_version_weight" {
    for_each = var.canary_version_weight
    content {
      version_id = additional_version_weight.key
      weight     = additional_version_weight.value
    }
  }
}

# =====================================================
# 异步调用配置（可选）
# =====================================================

resource "alicloud_fc3_async_invoke_config" "web_api_async" {
  count = var.enable_async_invoke ? 1 : 0

  function_name = alicloud_fc3_function.web_api.function_name

  # 异步调用配置
  max_async_event_age_in_seconds = var.async_max_event_age
  max_async_retry_attempts       = var.async_max_retry_attempts

  # 目标配置（失败后的处理）
  destination_config {
    on_failure {
      destination = var.async_failure_destination
    }
    on_success {
      destination = var.async_success_destination
    }
  }
}

# =====================================================
# Outputs
# =====================================================

output "fc_service_id" {
  description = "FC 服务 ID"
  value       = alicloud_fc_service.web_backend.id
}

output "fc_function_id" {
  description = "FC 函数 ID"
  value       = alicloud_fc3_function.web_api.function_id
}

output "http_trigger_url" {
  description = "HTTP 触发器 URL（公网访问地址）"
  value       = alicloud_fc3_trigger.http.url_internet
  sensitive   = false
}

output "http_trigger_url_intranet" {
  description = "HTTP 触发器 URL（内网访问地址）"
  value       = alicloud_fc3_trigger.http.url_intranet
  sensitive   = false
}

output "custom_domain_url" {
  description = "自定义域名访问地址"
  value       = var.enable_custom_domain ? "https://${var.custom_domain_name}" : "未配置自定义域名"
}

output "container_image" {
  description = "部署的容器镜像"
  value       = var.container_image
}

output "function_arn" {
  description = "函数 ARN"
  value       = alicloud_fc3_function.web_api.function_arn
}

# =====================================================
# DNS 自动更新（可选 - 类似 preview_dns.py）
# =====================================================

resource "null_resource" "dns_update" {
  count = var.enable_dns_update ? 1 : 0

  provisioner "local-exec" {
    command = <<EOT
      echo '{"url": "${alicloud_fc3_trigger.http.url_internet}"}' > fc_url.json
      # 可以在这里调用 DNS 更新脚本
      # uv run update_fc_dns.py
    EOT
  }

  depends_on = [
    alicloud_fc3_trigger.http
  ]

  triggers = {
    # 当触发器 URL 变化时重新执行
    trigger_url = alicloud_fc3_trigger.http.url_internet
  }
}
