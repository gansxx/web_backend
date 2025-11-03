terraform {
  required_providers {
    alicloud = {
      source  = "aliyun/alicloud"
      version = ">= 1.203.0"   # 或写 latest
    }
  }
}

provider "alicloud" {
  region = "cn-shenzhen"
}



# 用模板启动ecs
resource "alicloud_instance" "from_template" {
  launch_template_id      = "lt-wz9g3b8paafo1mq42el7"
  launch_template_version = "1"
}
#输出ip
output "ecs_public_ip" {
  value = alicloud_instance.from_template.public_ip
}
#同时将输出的ip解析到dns地址上
resource "null_resource" "dns_update" {
  provisioner "local-exec" {
    command = <<EOT
      terraform output -json ecs_public_ip > ecs_ip_preview.json
      uv run preview_dns.py
    EOT
  }

  depends_on = [
    alicloud_instance.from_template
  ]
}
