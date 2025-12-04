# Auth User Signup Webhook 配置指南

## 文件信息

**Migration 文件**: `20251124160728_auth_user_signup_webhook.sql`

**功能**: 当新用户在 `auth.users` 表中注册时，自动发送邮件通知到 `1214250247@qq.com`

## 配置步骤

### 1. 应用 Migration

```bash
# 方法 A：使用 psql 直接执行
source .env
psql "postgresql://postgres:$POSTGRES_PASSWORD@localhost:5438/postgres" \
  -v ON_ERROR_STOP=1 \
  -f supabase/migrations/20251124160728_auth_user_signup_webhook.sql
```

### 2. 配置数据库参数

由于 PostgreSQL 无法直接访问操作系统环境变量，需要将配置写入数据库参数：

```bash
# 从 .env.docker 文件读取配置
source .env.docker

# 设置数据库参数
psql "postgresql://postgres:$POSTGRES_PASSWORD@localhost:5438/postgres" <<EOF
-- 设置 Supabase URL（Docker 内部访问）
ALTER DATABASE postgres SET app.supabase_url = '$SUPABASE_URL';

-- 设置 ANON_KEY
ALTER DATABASE postgres SET app.anon_key = '$ANON_KEY';

-- 重新加载配置
SELECT pg_reload_conf();
EOF
```

**或者手动设置**（如果自动脚本不工作）：

```sql
-- 连接到数据库
psql "postgresql://postgres:YOUR_PASSWORD@localhost:5438/postgres"

-- 设置参数
ALTER DATABASE postgres SET app.supabase_url = 'http://host.docker.internal:8000';
ALTER DATABASE postgres SET app.anon_key = 'YOUR_ANON_KEY_FROM_ENV_FILE';

-- 重新加载
SELECT pg_reload_conf();

-- 验证配置
SELECT current_setting('app.supabase_url', true);
SELECT current_setting('app.anon_key', true);
```

### 3. 验证 Edge Function 已部署

确认 `resend-email` Edge Function 已经部署并可访问：

```bash
# 测试 Edge Function（从宿主机）
curl -X POST http://localhost:8000/functions/v1/resend-email \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $ANON_KEY" \
  -d '{
    "to": "1214250247@qq.com",
    "subject": "测试邮件",
    "html": "<p>这是一封测试邮件</p>"
  }'
```

## 手动测试 Webhook

### 测试方法 1: 创建新用户（通过 Supabase Auth）

```bash
# 使用 Supabase Auth API 注册新用户
curl -X POST http://localhost:8000/auth/v1/signup \
  -H "apikey: $ANON_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "email": "test@example.com",
    "password": "testpassword123"
  }'
```

### 测试方法 2: 直接插入到 auth.users（仅用于测试）

```sql
-- 连接到数据库
psql "postgresql://postgres:$POSTGRES_PASSWORD@localhost:5438/postgres"

-- 插入测试用户（触发器会自动执行）
INSERT INTO auth.users (
    instance_id,
    id,
    aud,
    role,
    email,
    encrypted_password,
    email_confirmed_at,
    created_at,
    updated_at
) VALUES (
    '00000000-0000-0000-0000-000000000000',
    gen_random_uuid(),
    'authenticated',
    'authenticated',
    'webhook-test@example.com',
    crypt('password123', gen_salt('bf')),
    NOW(),
    NOW(),
    NOW()
);
```

### 检查日志

```bash
# 查看触发器执行日志
docker logs supabase-db 2>&1 | grep "Webhook notification"

# 查看 Edge Function 日志
docker logs supabase-edge-functions 2>&1 | tail -50
```

## Webhook Payload 结构

触发器会发送以下格式的 JSON payload 到 Edge Function：

```json
{
  "type": "INSERT",
  "table": "users",
  "schema": "auth",
  "record": {
    "id": "uuid",
    "email": "user@example.com",
    "phone": null,
    "created_at": "2025-11-24T16:00:00Z",
    "confirmed_at": null,
    "email_confirmed_at": null,
    "last_sign_in_at": null,
    "role": "authenticated"
  },
  "to": "1214250247@qq.com",
  "subject": "[Z加速] 新用户注册: user@example.com"
}
```

## 邮件内容

由于未提供 `html` 参数，Edge Function 会使用默认的格式化模板，包含：

- 事件类型（INSERT）
- 表名（users）
- Schema（auth）
- 时间戳（中国时区）
- 完整的用户记录 JSON 数据

## 故障排查

### 问题 1: 没有收到邮件

**检查步骤**:

1. 确认数据库参数已设置：
   ```sql
   SELECT current_setting('app.supabase_url', true);
   SELECT current_setting('app.anon_key', true);
   ```

2. 检查触发器是否存在：
   ```sql
   SELECT * FROM pg_trigger WHERE tgname = 'on_auth_user_signup';
   ```

3. 查看数据库日志：
   ```bash
   docker logs supabase-db 2>&1 | grep -i "webhook\|warning\|error"
   ```

4. 验证 Edge Function 可访问：
   ```bash
   curl http://localhost:8000/functions/v1/resend-email
   ```

### 问题 2: 用户注册失败

触发器包含完整的错误处理，即使 webhook 失败也不会阻止用户注册。检查日志中的 WARNING 消息。

### 问题 3: 权限错误

```sql
-- 重新授予权限
GRANT USAGE ON SCHEMA net TO service_role;
GRANT EXECUTE ON FUNCTION notify_user_signup() TO service_role;
GRANT EXECUTE ON FUNCTION notify_user_signup() TO postgres;
```

## 修改配置

### 更改收件人邮箱

编辑 migration 文件第 76 行：
```sql
'to', 'new-email@example.com',
```

然后重新应用 migration。

### 更改邮件主题

编辑 migration 文件第 77 行：
```sql
'subject', '[自定义前缀] 新用户: ' || user_email
```

### 自定义 HTML 模板

在 payload 中添加 `html` 参数：
```sql
payload := jsonb_build_object(
    -- ... 其他字段 ...
    'to', '1214250247@qq.com',
    'subject', '[Z加速] 新用户注册: ' || user_email,
    'html', '<h1>新用户注册</h1><p>邮箱: ' || user_email || '</p>'
);
```

## 卸载

如需移除这个 webhook：

```sql
-- 删除触发器
DROP TRIGGER IF EXISTS on_auth_user_signup ON auth.users;

-- 删除函数
DROP FUNCTION IF EXISTS notify_user_signup();

-- 清除数据库参数
ALTER DATABASE postgres RESET app.supabase_url;
ALTER DATABASE postgres RESET app.anon_key;
```
