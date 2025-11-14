# 报警模块使用文档

## 概述

`center_management/alert` 模块提供通用的邮件报警和通知功能，支持多种场景的报警需求。

### 特性

- ✅ **通用邮件发送** - 支持纯文本邮件发送
- ✅ **错误报警** - 自动格式化异常堆栈跟踪
- ✅ **资源告警** - CPU、内存、带宽等资源监控告警
- ✅ **系统通知** - 订单超时、支付异常等业务事件通知
- ✅ **配置灵活** - 复用项目现有SMTP配置
- ✅ **便捷函数** - 提供快速调用接口
- ✅ **重试机制** - 自动重试失败的邮件发送

## 快速开始

### 1. 配置环境变量

确保 `.env` 文件包含以下配置：

```bash
# SMTP邮件服务器配置
SMTP_HOST=smtp.qq.com
SMTP_PORT=465
SMTP_USER=your_email@qq.com
SMTP_PASS=your_smtp_password
SMTP_SENDER_NAME=系统报警
SMTP_ADMIN_EMAIL=admin@example.com

# 报警接收人列表（逗号分隔）
ADMIN_EMAILS=admin1@example.com,admin2@example.com
```

### 2. 简单使用（便捷函数）

```python
from center_management.alert import send_alert_email

# 发送简单报警邮件
send_alert_email(
    subject="系统报警",
    content="数据库连接失败",
    recipients=["admin@example.com"]  # 可选，默认使用ADMIN_EMAILS
)
```

### 3. 错误报警

```python
from center_management.alert import send_error_alert

try:
    # 可能出错的操作
    risky_operation()
except Exception as e:
    # 自动发送错误报警（包含完整堆栈跟踪）
    send_error_alert(
        error=e,
        context={
            "user_id": "12345",
            "operation": "数据导入",
            "request_id": "req-abc123"
        }
    )
```

### 4. 资源告警

```python
from center_management.alert import send_resource_alert

# CPU使用率告警
send_resource_alert(
    resource_type="CPU",
    resource_name="web-server-01",
    current_value=85.5,
    threshold=80.0,
    unit="%",
    additional_info={
        "hostname": "web-server-01.example.com",
        "region": "ap-northeast-1"
    }
)

# 带宽使用告警
send_resource_alert(
    resource_type="带宽",
    resource_name="VPS-Tokyo-01",
    current_value=950.0,
    threshold=1000.0,
    unit="GB",
    additional_info={
        "total_bandwidth": "1000 GB/月",
        "remaining": "50 GB"
    }
)
```

### 5. 系统通知

```python
from center_management.alert import send_system_notification

# 订单超时通知
send_system_notification(
    event_type="订单超时",
    event_title="订单 #ORD-12345 已超时",
    details={
        "order_id": "ORD-12345",
        "user_email": "user@example.com",
        "amount": "¥99.00",
        "timeout_minutes": 30,
        "payment_method": "支付宝"
    },
    severity="warning"  # info/warning/error/critical
)

# 支付异常通知
send_system_notification(
    event_type="支付异常",
    event_title="支付回调验证失败",
    details={
        "order_id": "ORD-67890",
        "payment_gateway": "stripe",
        "error_code": "signature_invalid"
    },
    severity="error"
)
```

## 高级用法

### 使用 EmailSender 类

```python
from center_management.alert import EmailSender, AlertConfig

# 创建配置对象（可选，默认自动创建）
config = AlertConfig()

# 创建邮件发送器
sender = EmailSender(config)

# 发送自定义邮件
sender.send_email(
    to="user@example.com",
    subject="自定义主题",
    content="自定义内容",
    retry_count=3,      # 重试次数
    retry_delay=2.0     # 重试延迟（秒）
)

# 向多个收件人发送
results = sender.send_to_multiple(
    recipients=["admin1@example.com", "admin2@example.com"],
    subject="批量通知",
    content="这是批量发送的通知"
)
print(results)  # {'admin1@example.com': True, 'admin2@example.com': True}
```

### 自定义邮件格式

```python
from center_management.alert import EmailSender
from center_management.alert.formatters import format_plain_text

# 使用格式化工具创建自定义内容
content = format_plain_text(
    title="自定义报警",
    details="这是详细信息内容",
    metadata={
        "source": "custom_module",
        "timestamp": "2025-01-01 12:00:00"
    }
)

sender = EmailSender()
sender.send_email(
    to="admin@example.com",
    subject="自定义报警",
    content=content
)
```

## API 参考

### 便捷函数

#### `send_alert_email(subject, content, recipients=None)`
快速发送报警邮件

- **subject** (str): 邮件主题
- **content** (str): 邮件内容
- **recipients** (List[str], optional): 收件人列表
- **Returns**: bool - 是否发送成功

#### `send_error_alert(error, context=None, recipients=None, include_traceback=True)`
发送错误报警

- **error** (Exception): 异常对象
- **context** (dict, optional): 错误上下文信息
- **recipients** (List[str], optional): 收件人列表
- **include_traceback** (bool): 是否包含堆栈跟踪
- **Returns**: bool - 是否发送成功

#### `send_resource_alert(resource_type, resource_name, current_value, threshold, unit="%", additional_info=None, recipients=None)`
发送资源使用率告警

- **resource_type** (str): 资源类型（CPU、内存、带宽等）
- **resource_name** (str): 资源名称
- **current_value** (float): 当前使用值
- **threshold** (float): 告警阈值
- **unit** (str): 单位（默认 %）
- **additional_info** (dict, optional): 额外信息
- **recipients** (List[str], optional): 收件人列表
- **Returns**: bool - 是否发送成功

#### `send_system_notification(event_type, event_title, details, severity="info", recipients=None)`
发送系统通知

- **event_type** (str): 事件类型
- **event_title** (str): 事件标题
- **details** (dict): 事件详情
- **severity** (str): 严重程度（info/warning/error/critical）
- **recipients** (List[str], optional): 收件人列表
- **Returns**: bool - 是否发送成功

### EmailSender 类

#### `__init__(config=None)`
初始化邮件发送器

- **config** (AlertConfig, optional): 配置对象

#### `send_email(to, subject, content, retry_count=3, retry_delay=2.0)`
发送单封邮件

- **to** (str): 收件人邮箱
- **subject** (str): 邮件主题
- **content** (str): 邮件内容
- **retry_count** (int): 重试次数
- **retry_delay** (float): 重试延迟（秒）
- **Returns**: bool - 是否发送成功

#### `send_to_multiple(recipients, subject, content)`
向多个收件人发送邮件

- **recipients** (List[str]): 收件人列表
- **subject** (str): 邮件主题
- **content** (str): 邮件内容
- **Returns**: Dict[str, bool] - 每个收件人的发送结果

### AlertConfig 类

#### `__init__()`
初始化配置（自动从环境变量读取）

#### `get_sender_address()`
获取格式化的发送者地址

- **Returns**: str - 发送者地址（如 "系统报警 <admin@example.com>"）

#### `get_recipients(custom_recipients=None)`
获取收件人列表

- **custom_recipients** (List[str], optional): 自定义收件人
- **Returns**: List[str] - 收件人列表

#### `validate_config()`
验证配置是否完整

- **Returns**: bool - 配置是否有效

## 格式化工具

模块提供多种格式化函数用于创建标准化的邮件内容：

- `format_plain_text(title, details, metadata)` - 通用纯文本格式
- `format_error_alert(error, context, include_traceback)` - 错误报警格式
- `format_resource_alert(resource_type, resource_name, current_value, threshold, unit, additional_info)` - 资源告警格式
- `format_system_notification(event_type, event_title, details, severity)` - 系统通知格式
- `format_simple_message(subject, message)` - 简单消息格式

## 使用场景示例

### 1. 在 API 路由中捕获错误

```python
from fastapi import APIRouter
from center_management.alert import send_error_alert

router = APIRouter()

@router.post("/api/process")
async def process_data(data: dict):
    try:
        # 业务逻辑
        result = complex_operation(data)
        return {"status": "success", "result": result}
    except Exception as e:
        # 发送错误报警
        send_error_alert(
            error=e,
            context={
                "endpoint": "/api/process",
                "input_data": data,
                "user_id": data.get("user_id")
            }
        )
        raise
```

### 2. 在 orchestrationer 中监控带宽

```python
from center_management.alert import send_resource_alert

def check_bandwidth_usage(vps_name: str):
    current_usage = get_bandwidth_usage(vps_name)
    threshold = 1000.0  # GB

    if current_usage > threshold * 0.8:  # 80% 阈值
        send_resource_alert(
            resource_type="带宽",
            resource_name=vps_name,
            current_value=current_usage,
            threshold=threshold,
            unit="GB",
            additional_info={
                "usage_percentage": f"{(current_usage/threshold)*100:.1f}%",
                "monthly_limit": f"{threshold} GB"
            }
        )
```

### 3. 在订单超时检查中发送通知

```python
from center_management.alert import send_system_notification

def check_order_timeout(order_id: str):
    order = get_order(order_id)

    if is_timeout(order):
        send_system_notification(
            event_type="订单超时",
            event_title=f"订单 #{order_id} 已超时",
            details={
                "order_id": order_id,
                "user_email": order.user_email,
                "amount": f"¥{order.amount}",
                "created_at": order.created_at.isoformat(),
                "timeout_minutes": calculate_timeout_minutes(order)
            },
            severity="warning"
        )
```

## 测试

运行测试脚本验证模块功能：

```bash
uv run python tests/test_alert_module.py
```

## 注意事项

1. **SMTP配置**: 确保 `.env` 文件正确配置了 SMTP 相关变量
2. **邮件限制**: 注意邮件服务器的发送频率限制，避免被标记为垃圾邮件
3. **重试机制**: 默认重试3次，每次延迟2秒，可根据需要调整
4. **日志记录**: 所有操作都会记录详细日志，便于排查问题
5. **环境变量**: ADMIN_EMAILS 支持逗号分隔的多个邮箱地址

## 故障排查

### 邮件发送失败

1. 检查 SMTP 配置是否正确
2. 检查网络连接和防火墙设置
3. 验证 SMTP 用户名和密码
4. 查看日志输出的详细错误信息

### 未收到邮件

1. 检查垃圾邮件文件夹
2. 验证收件人邮箱地址是否正确
3. 检查邮件服务器日志
4. 确认 SMTP_ADMIN_EMAIL 配置正确

## 贡献与反馈

如有问题或建议，请在项目中提交 issue。
