# 工单答复功能实施文档

## 📋 功能概述

为工单系统添加了管理员答复功能和邮件通知系统，允许客服人员直接在系统中答复用户工单，并自动发送邮件通知。

## ✨ 新增功能

### 1. 数据库层面
- ✅ ticket 表新增 `reply` 字段（TEXT，管理员答复内容）
- ✅ ticket 表新增 `replied_at` 字段（TIMESTAMPTZ，答复时间）
- ✅ 更新 `update_ticket_status` 函数支持答复参数
- ✅ 新增 `get_ticket_by_id` 函数用于查询单个工单
- ✅ 更新 `fetch_user_tickets` 和 `fetch_all_tickets` 返回答复字段

### 2. Python 数据库操作层
- ✅ `TicketConfig.update_ticket_status()` 新增 `reply` 参数
- ✅ `TicketConfig.get_ticket_by_id()` 新方法
- ✅ `TicketConfig.send_ticket_reply_email()` 邮件发送功能

### 3. API 路由层
- ✅ `GET /support/tickets` 返回数据包含 `reply` 和 `replied_at`
- ✅ `GET /support/tickets/{ticket_id}` 返回完整答复信息
- ✅ `PATCH /support/tickets/{ticket_id}/reply` 新端点（管理员答复）

### 4. 邮件通知系统
- ✅ HTML + 纯文本双格式邮件
- ✅ 使用环境变量配置 SMTP
- ✅ 可选开关控制是否发送邮件

## 🚀 部署步骤

### 1. 执行数据库迁移

```bash
# 加载环境变量
source .env

# 执行迁移 SQL
uv run center_management/db/migration/pg_dump_remote.py --schema-init
```

### 2. 验证迁移结果

```bash
# 检查新字段是否已添加
psql "postgresql://postgres:$POSTGRES_PASSWORD@localhost:5438/postgres" \
  -c "SELECT column_name, data_type FROM information_schema.columns WHERE table_name = 'ticket' AND column_name IN ('reply', 'replied_at');"
```

预期输出：
```
 column_name |          data_type
-------------+-----------------------------
 reply       | text
 replied_at  | timestamp with time zone
```

### 3. 配置 SMTP（可选，用于邮件通知）

在 `.env` 文件中确认以下配置：

```bash
# SMTP 邮件服务器配置
SMTP_HOST=smtp.example.com          # SMTP 服务器地址
SMTP_PORT=587                        # SMTP 端口
SMTP_USER=your_email@example.com    # SMTP 用户名
SMTP_PASS=your_password              # SMTP 密码
SMTP_ADMIN_EMAIL=support@example.com # 发件人邮箱
SMTP_SENDER_NAME=客服支持            # 发件人名称

# 前端URL（用于邮件中的链接）
FRONTEND_URL=https://your-domain.com
```

### 4. 重启服务

```bash
# 重启主 API 服务
uv run python run.py
```

## 📝 API 使用示例

### 1. 管理员答复工单

**请求**：
```http
PATCH /support/tickets/{ticket_id}/reply
Content-Type: application/json
Cookie: access_token=xxx; refresh_token=xxx

{
  "status": "已解决",
  "reply": "感谢您的反馈！我们已经解决了您的问题。",
  "send_email": true
}
```

**响应**：
```json
{
  "success": true,
  "message": "工单答复成功",
  "ticket_id": "uuid-here",
  "email_sent": true
}
```

### 2. 查看工单列表（包含答复状态）

**请求**：
```http
GET /support/tickets
Cookie: access_token=xxx
```

**响应**：
```json
[
  {
    "id": "uuid-1",
    "subject": "登录问题",
    "priority": "高",
    "category": "技术支持",
    "status": "已解决",
    "created_at": "2025-10-02T10:00:00Z",
    "reply": "问题已解决",
    "replied_at": "2025-10-02T11:00:00Z"
  }
]
```

### 3. 查看工单详情

**请求**：
```http
GET /support/tickets/{ticket_id}
Cookie: access_token=xxx
```

**响应**：
```json
{
  "id": "uuid",
  "subject": "登录问题",
  "description": "无法登录账号",
  "priority": "高",
  "category": "技术支持",
  "status": "已解决",
  "reply": "您的问题已解决，请重新尝试登录。",
  "replied_at": "2025-10-02T11:00:00Z",
  "created_at": "2025-10-02T10:00:00Z",
  "updated_at": "2025-10-02T11:00:00Z"
}
```

## 🧪 测试

### 运行集成测试

```bash
# 运行完整的工单系统测试（包含答复功能测试）
uv run python test_ticket_api.py
```

测试流程包括：
1. ✅ 用户注册/登录
2. ✅ 创建工单
3. ✅ 查询工单列表
4. ✅ 查询工单详情
5. ✅ **管理员答复工单**（新）
6. ✅ **验证答复已保存**（新）
7. ✅ 未授权访问测试

### 手动测试邮件功能

```python
from center_management.db.ticket import TicketConfig

ticket_db = TicketConfig()
success = ticket_db.send_ticket_reply_email(
    user_email="test@example.com",
    ticket_subject="测试工单",
    reply_content="这是测试答复",
    ticket_id="test-uuid"
)
print(f"邮件发送: {'成功' if success else '失败'}")
```

## 📧 邮件模板预览

用户收到的答复邮件包含：

**主题**：`您的工单已收到回复 - {工单标题}`

**内容**：
- 工单标题
- 客服答复内容（支持换行）
- 查看详情按钮（链接到工单详情页）
- 客服签名

支持 HTML 和纯文本两种格式，确保在各种邮件客户端中正常显示。

## ⚠️ 注意事项

### 权限控制
当前答复接口需要用户登录，但**尚未实现严格的管理员权限验证**。

建议添加管理员验证：
```python
# 在 routes/ticket.py 的 reply_to_ticket 函数中
ADMIN_EMAILS = os.getenv('ADMIN_EMAILS', '').split(',')
if user_email not in ADMIN_EMAILS:
    raise HTTPException(403, detail="无管理员权限")
```

或使用基于角色的权限系统（RBAC）。

### SMTP 配置
- 如果未配置 SMTP，设置 `send_email: false` 避免邮件发送失败
- 测试环境建议使用 MailHog 或类似的测试邮件服务器
- 生产环境建议使用可靠的 SMTP 服务（如 SendGrid, AWS SES）

### 数据库兼容性
- 新增字段允许 NULL，向后兼容现有数据
- 已有工单的 `reply` 和 `replied_at` 为 NULL
- 数据库函数已更新权限（service_role）

## 🔧 故障排查

### 问题 1: 数据库迁移失败
```bash
# 检查函数是否存在
psql "postgresql://postgres:$POSTGRES_PASSWORD@localhost:5438/postgres" \
  -c "\df get_ticket_by_id"

# 如果不存在，重新执行迁移
```

### 问题 2: 邮件发送失败
```bash
# 检查 SMTP 配置
echo $SMTP_HOST
echo $SMTP_PORT

# 测试 SMTP 连接
telnet $SMTP_HOST $SMTP_PORT
```

### 问题 3: API 返回 500 错误
```bash
# 查看日志
uv run python run.py

# 检查是否所有依赖都已安装
uv sync
```

## 📁 文件清单

### 新增文件
- `center_management/db/migration/sql_schema_migration/ticket_system_add_reply.sql`
- `TICKET_REPLY_README.md`（本文件）

### 修改文件
- `center_management/db/ticket.py`
  - `update_ticket_status()` 方法签名更新
  - 新增 `get_ticket_by_id()` 方法
  - 新增 `send_ticket_reply_email()` 方法
- `routes/ticket.py`
  - 新增 `TicketReplyRequest` 模型
  - 新增 `reply_to_ticket` 端点
  - 更新 `get_user_tickets` 返回字段
- `test_ticket_api.py`
  - 修正优先级字段（使用中文）
  - 新增 `test_reply_to_ticket()` 测试
  - 新增 `test_check_reply()` 测试
  - 更新 `run_all_tests()` 流程

## 🎯 后续改进建议

1. **权限系统**：实现完整的 RBAC 或基于角色的权限控制
2. **工单分类**：添加工单优先级自动调整逻辑
3. **通知扩展**：支持短信、站内信等多种通知方式
4. **答复历史**：记录所有答复历史（当前只保存最新答复）
5. **模板系统**：预设常用答复模板提高客服效率
6. **SLA 管理**：添加工单响应时间追踪和提醒

## 📞 支持

如有问题，请查看：
- 主项目文档：`CLAUDE.md`
- 数据库迁移文件：`center_management/db/migration/sql_schema_migration/`
- 测试文件：`test_ticket_api.py`
