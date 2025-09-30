# 工单系统测试指南

## ✅ 导入测试通过

`test_ticket_db.py` 的导入问题已解决！测试脚本现在可以正确导入 `TicketConfig` 类。

## 📋 测试前置条件

### 1. 确保 Supabase 服务运行

```bash
# 检查 Docker 容器状态
docker ps | grep supabase

# 如果未运行，启动 Supabase
cd /root/self_code/web_backend
docker compose up -d
```

### 2. 运行数据库迁移

**必须先运行迁移，创建 ticket 表和相关函数**：

```bash
cd /root/self_code/web_backend/center_management/db/migration

# 方式 1: 使用自动迁移工具（推荐）
uv run python pg_dump_remote.py --schema-init --target local

# 方式 2: 手动执行 SQL
source ../../../.env
psql "postgresql://postgres:$POSTGRES_PASSWORD@localhost:5438/postgres" \
  -v ON_ERROR_STOP=1 -1 \
  -f sql_schema_migration/ticket_system.sql
```

**预期输出**:
```
INFO - 应用数据库迁移到 local 数据库...
INFO - 自动发现 3 个迁移文件: order_refactored.sql, product_refactored.sql, ticket_system.sql
INFO - 应用迁移: order_refactored.sql
SUCCESS - 迁移完成: order_refactored.sql
INFO - 应用迁移: product_refactored.sql
SUCCESS - 迁移完成: product_refactored.sql
INFO - 应用迁移: ticket_system.sql
SUCCESS - 迁移完成: ticket_system.sql
```

### 3. 验证表和函数是否创建

```bash
source .env
psql "postgresql://postgres:$POSTGRES_PASSWORD@localhost:5438/postgres" -c "
SELECT get_schema_name();
SELECT COUNT(*) FROM test.ticket;
SELECT proname FROM pg_proc WHERE proname LIKE '%ticket%';
"
```

**预期输出**:
```
 get_schema_name
-----------------
 test

 count
-------
     0

              proname
-----------------------------------
 insert_ticket
 fetch_user_tickets
 update_ticket_status
 fetch_all_tickets
```

## 🧪 运行测试

### 数据库层测试

```bash
cd /root/self_code/web_backend/center_management/db
uv run python test_ticket_db.py
```

**预期输出**:
```
INFO - === 开始测试工单数据库操作 ===
INFO - ✅ TicketConfig 初始化成功
INFO - --- 测试 1: 插入工单 ---
INFO - ✅ 插入工单成功，ID: xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx
INFO - --- 测试 2: 查询用户工单 ---
INFO - ✅ 查询成功，找到 2 个工单
INFO - --- 测试 3: 更新工单状态 ---
INFO - ✅ 更新工单状态成功
...
```

### API 端到端测试

**必须先启动 API 服务**:

```bash
# 终端 1: 启动 API 服务
cd /root/self_code/web_backend
uv run python run.py

# 终端 2: 运行测试
uv run python test_ticket_api.py
```

**预期输出**:
```
=== 步骤 1: 用户认证 ===
✅ 登录成功

=== 步骤 2: 创建工单 ===
✅ 工单创建成功:
  ticket_id: xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx
  message: 工单创建成功，工单号: ...

=== 步骤 4: 获取工单列表 ===
✅ 成功获取 4 个工单:
  - [open] 测试工单 - API测试 (优先级: high)
  - [open] 登录问题 (优先级: urgent)
  ...
```

## 🔍 故障排查

### 问题 1: "Could not find the function public.insert_ticket"

**原因**: 数据库迁移未执行

**解决**:
```bash
cd /root/self_code/web_backend/center_management/db/migration
uv run python pg_dump_remote.py --schema-init --target local
```

### 问题 2: "Supabase 未初始化" 或连接错误

**原因**: Supabase 服务未运行

**解决**:
```bash
cd /root/self_code/web_backend
docker compose up -d

# 检查服务状态
docker ps | grep postgres
```

### 问题 3: "ModuleNotFoundError: No module named 'center_management'"

**原因**: 从错误的目录运行测试

**解决**: 确保从 `center_management/db/` 目录运行
```bash
cd /root/self_code/web_backend/center_management/db
uv run python test_ticket_db.py
```

### 问题 4: 权限错误 "permission denied"

**原因**: PostgreSQL 用户权限不足

**解决**:
```bash
# 重新运行迁移（会自动授权）
cd center_management/db/migration
uv run python pg_dump_remote.py --schema-init --target local
```

### 问题 5: "Could not find the function" 但函数确实存在

**原因**: PostgREST schema cache 未更新

**症状**:
- 数据库中可以查到函数: `\df insert_ticket` 显示函数存在
- 但 RPC 调用失败: `Could not find the function public.insert_ticket in the schema cache`
- PostgREST 日志显示 functions 数量少于实际数量

**解决**:
```bash
# 方法 1: 发送 PostgreSQL NOTIFY 刷新 cache
source .env
psql "postgresql://postgres:$POSTGRES_PASSWORD@localhost:5438/postgres" \
  -c "NOTIFY pgrst, 'reload schema'"

# 方法 2: 重启 PostgREST 容器
docker restart supabase-rest

# 验证 cache 已刷新
docker logs supabase-rest 2>&1 | tail -10
# 应该看到: "Schema cache loaded X Functions" (X 应该包含新函数)
```

**预防**:
- 执行数据库迁移后，始终刷新 PostgREST cache
- 可以将刷新命令添加到迁移脚本中自动执行

## 📊 测试覆盖范围

### test_ticket_db.py 测试项目
- ✅ TicketConfig 初始化
- ✅ 插入工单（带各种优先级）
- ✅ 查询用户工单列表
- ✅ 更新工单状态
- ✅ 根据ID查询工单详情（使用 fetch_user_tickets + 过滤）
- ✅ 按状态筛选工单（使用 fetch_all_tickets）
- ✅ 统计用户工单数量（使用 len(fetch_user_tickets())）
- ✅ 管理员查询所有工单（带优先级筛选）
- ✅ 参数验证（无效优先级拒绝）

### test_ticket_api.py 测试项目
- ✅ 用户注册/登录
- ✅ 创建工单（带认证）
- ✅ 批量创建多个工单
- ✅ 获取用户工单列表
- ✅ 获取工单详情
- ✅ 未授权访问拦截

## 🎯 快速测试流程

```bash
# 1. 确保在正确目录
cd /root/self_code/web_backend

# 2. 启动 Supabase（如果未运行）
docker compose up -d

# 3. 运行数据库迁移
cd center_management/db/migration
uv run python pg_dump_remote.py --schema-init --target local

# 4. 运行数据库测试
cd ..
uv run python test_ticket_db.py

# 5. 启动 API 服务（新终端）
cd /root/self_code/web_backend
uv run python run.py

# 6. 运行 API 测试（新终端）
cd /root/self_code/web_backend
uv run python test_ticket_api.py
```

## ✅ 成功标志

测试成功的标志：
- 所有测试步骤显示 ✅
- 无 ❌ 错误标记
- 数据库中可以查询到测试数据
- API 返回正确的 JSON 格式

## 📝 注意事项

1. **先运行迁移再测试**: 迁移必须在测试前完成
2. **保持服务运行**: Supabase 必须在后台运行
3. **清理测试数据**: 测试会在数据库中创建实际数据，可以手动清理：
   ```sql
   DELETE FROM test.ticket WHERE user_email = 'test_user@example.com';
   ```
4. **并发测试**: API 测试需要独立的终端窗口