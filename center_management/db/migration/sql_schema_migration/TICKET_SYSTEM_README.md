# 工单系统数据库迁移说明

## 概述

工单系统使用与 order_refactored.sql 相同的架构模式，支持：
- 用户级别工单管理
- 基于邮箱的用户隔离
- 优先级和状态管理
- 元数据存储（user_agent, ip_address 等）

## 数据库结构

### ticket 表

| 字段 | 类型 | 说明 |
|------|------|------|
| id | uuid | 主键，自动生成 |
| created_at | timestamptz | 创建时间，自动设置 |
| updated_at | timestamptz | 更新时间，自动更新 |
| user_email | text | 用户邮箱（必填） |
| phone | text | 用户电话（可选，默认空字符串） |
| subject | text | 工单标题（必填） |
| priority | text | 优先级：高/中/低（必填） |
| category | text | 工单类别（必填） |
| description | text | 工单描述（必填） |
| status | text | 状态：处理中/已解决（默认：处理中） |
| metadata | jsonb | 元数据（可选） |

### 索引
- `ticket_user_email_idx`: 用户邮箱索引（加速查询）
- `ticket_status_idx`: 状态索引（筛选查询）
- `ticket_created_at_idx`: 创建时间降序索引（排序）

## RPC 函数

### 1. insert_ticket
插入新工单

**参数:**
- `p_user_email` (text): 用户邮箱
- `p_subject` (text): 工单标题
- `p_priority` (text): 优先级（高/中/低）
- `p_category` (text): 工单类别
- `p_description` (text): 工单描述
- `p_phone` (text, optional): 用户电话
- `p_metadata` (jsonb, optional): 元数据

**返回:** uuid - 新工单ID

### 2. fetch_user_tickets
查询用户的所有工单

**参数:**
- `p_user_email` (text): 用户邮箱

**返回:** 工单列表（按创建时间降序）

### 3. update_ticket_status
更新工单状态

**参数:**
- `p_ticket_id` (uuid): 工单ID
- `p_status` (text): 新状态（处理中/已解决）

**返回:** boolean - 是否更新成功

### 4. fetch_all_tickets
查询所有工单（管理员功能）

**参数:**
- `p_status` (text, optional): 筛选状态
- `p_priority` (text, optional): 筛选优先级
- `p_limit` (integer, default 100): 返回数量限制
- `p_offset` (integer, default 0): 偏移量

**返回:** 工单列表

## 执行迁移

### 方式 1: 直接执行（推荐）

```bash
# 加载环境变量
source .env

# 执行迁移（原子性）
psql "postgresql://postgres:$POSTGRES_PASSWORD@localhost:5438/postgres" \
  -v ON_ERROR_STOP=1 \
  -1 \
  -f supabase/migrations/ticket_system.sql
```

### 方式 2: 分步执行

```bash
# 1. 进入 psql
psql "postgresql://postgres:$POSTGRES_PASSWORD@localhost:5438/postgres"

# 2. 在 psql 中执行
\i supabase/migrations/ticket_system.sql
```

## 验证迁移

### 1. 检查表是否创建

```sql
SELECT get_schema_name();  -- 查看当前 schema

-- 检查 ticket 表
SELECT * FROM test.ticket LIMIT 1;

-- 检查索引
SELECT indexname FROM pg_indexes WHERE tablename = 'ticket';
```

### 2. 测试 RPC 函数

```sql
-- 插入测试工单
SELECT insert_ticket(
    'test@example.com',
    '测试工单',
    '高',
    '技术支持',
    '测试描述',
    '13800138000',
    '{"source": "test"}'::jsonb
);

-- 查询用户工单
SELECT * FROM fetch_user_tickets('test@example.com');

-- 更新工单状态
SELECT update_ticket_status(
    'your-ticket-uuid-here',
    '已解决'
);
```

## Python 使用示例

### 初始化

```python
from center_management.db.ticket import TicketConfig

ticket_db = TicketConfig()
```

### 插入工单

```python
ticket_id = ticket_db.insert_ticket(
    user_email="user@example.com",
    subject="登录问题",
    priority="高",
    category="技术支持",
    description="无法登录系统",
    phone="13800138000",
    metadata={"source": "web"}
)
```

### 查询用户工单

```python
tickets = ticket_db.fetch_user_tickets("user@example.com")
for ticket in tickets:
    print(f"{ticket['subject']} - {ticket['status']}")
```

### 更新工单状态

```python
success = ticket_db.update_ticket_status(ticket_id, "已解决")
```

## API 端点

### POST /support/submit_ticket
创建新工单（需要登录）

**请求体:**
```json
{
  "subject": "工单标题",
  "priority": "high",  // low/normal/high/urgent
  "category": "技术支持",
  "description": "详细描述"
}
```

**响应:**
```json
{
  "success": true,
  "ticket_id": "uuid",
  "message": "工单创建成功"
}
```

### GET /support/tickets
获取当前用户的所有工单（需要登录）

**响应:**
```json
[
  {
    "id": "uuid",
    "subject": "工单标题",
    "priority": "high",
    "category": "技术支持",
    "status": "open",
    "created_at": "2025-01-27T10:00:00Z"
  }
]
```

### GET /support/tickets/{ticket_id}
获取工单详情（需要登录，仅可查看自己的工单）

## 测试

### 1. 数据库测试

```bash
cd center_management/db
uv run python test_ticket_db.py
```

### 2. API 端到端测试

```bash
# 确保服务运行在 localhost:8001
uv run python test_ticket_api.py
```

## 注意事项

1. **Schema 控制**: 迁移使用 `get_schema_name()` 函数获取 schema 名称，确保与 order_refactored.sql 一致
2. **权限设置**: 所有函数和表都授予了 `service_role` 权限
3. **数据隔离**: 用户只能查看和操作自己的工单（通过 email 筛选）
4. **自动更新**: `updated_at` 字段通过触发器自动更新
5. **参数验证**: priority 和 status 字段有数据库级别的约束验证

## 故障排查

### 问题: "Schema configuration not found"

**原因:** 未执行 order_refactored.sql 迁移

**解决:**
```bash
# 先执行 order_refactored.sql
psql "postgresql://..." -v ON_ERROR_STOP=1 -1 -f supabase/migrations/order_refactored.sql

# 再执行 ticket_system.sql
psql "postgresql://..." -v ON_ERROR_STOP=1 -1 -f supabase/migrations/ticket_system.sql
```

### 问题: "Invalid priority value"

**原因:** 使用了错误的优先级值

**解决:** 使用正确的中文值：高、中、低

### 问题: RPC 函数调用失败

**原因:** 可能是权限问题

**解决:**
```sql
-- 检查权限
SELECT has_function_privilege('service_role', 'insert_ticket(text,text,text,text,text,text,jsonb)', 'EXECUTE');

-- 重新授权
GRANT EXECUTE ON FUNCTION insert_ticket(...) TO service_role;
```