# 数据库迁移工具使用指南

## ✅ 测试结果总结

已完成全面测试，所有功能正常工作：
- ✅ 远程数据库连接（通过SSH隧道）
- ✅ 导出 auth.users 和业务表数据
- ✅ 导入到本地数据库
- ✅ 数据完整性验证

## 🚀 快速开始

### 1. 配置环境变量

确保 `.env.migration` 文件已正确配置（已配置，使用你选中的密码）：

```bash
# 远程数据库配置
remote_db_ip=8.134.74.41
REMOTE_POSTGRES_PASSWORD=你的密码
REMOTE_POSTGRES_HOST=127.0.0.1
REMOTE_POSTGRES_PORT=5438

# SSH隧道配置
USE_SSH_TUNNEL=true
SSH_GATEWAY_HOST=8.134.74.41
SSH_KEY_FILE=~/.ssh/id_ed25519
```

### 2. 测试连接

```bash
uv run python center_management/db/migration/pg_dump_remote.py --test
```

## 📋 核心功能

### 功能 1: 只同步数据（推荐）⭐

**适用场景**: 同步 auth.users 和所有业务表数据到本地开发环境

```bash
# 同步所有业务数据（包括 auth.users, test.order, test.test_products 等）
uv run python center_management/db/migration/pg_dump_remote.py \
  --data-only-sync \
  --source remote \
  --target local \
  --all-schemas
```

**工作流程**:
1. 应用迁移脚本初始化表结构
2. 导出远程数据（只含数据，不含结构）
3. 清空本地表数据
4. 导入远程数据到本地

**优点**:
- ✅ 不影响本地 Supabase schema 结构
- ✅ 自动处理表依赖关系
- ✅ 包含 auth.users 等系统表数据
- ✅ 保留本地表结构和函数

### 功能 2: 只初始化表结构

```bash
# 应用迁移脚本，创建/更新表结构
uv run python center_management/db/migration/pg_dump_remote.py \
  --schema-init \
  --target local
```

### 功能 3: 导出远程数据库

```bash
# 导出完整数据库（结构+数据）
uv run python center_management/db/migration/pg_dump_remote.py \
  --export \
  --source remote \
  --output backup_$(date +%Y%m%d).sql

# 只导出数据
uv run python center_management/db/migration/pg_dump_remote.py \
  --export \
  --source remote \
  --data-only
```

### 功能 4: 同步特定 schema

```bash
# 只同步 test schema 的数据
uv run python center_management/db/migration/pg_dump_remote.py \
  --data-only-sync \
  --source remote \
  --target local \
  --schema test
```

## 📊 验证数据迁移

### 验证 auth.users 表

```bash
psql "postgresql://postgres:你的密码@localhost:5438/postgres" \
  -c "SELECT COUNT(*), MAX(created_at) FROM auth.users;"
```

### 验证业务表

```bash
# 检查订单表
psql "postgresql://postgres:你的密码@localhost:5438/postgres" \
  -c "SELECT COUNT(*) FROM test.\"order\";"

# 检查产品表
psql "postgresql://postgres:你的密码@localhost:5438/postgres" \
  -c "SELECT COUNT(*) FROM test.test_products;"
```

## 🔧 高级用法

### 强制使用/不使用 SSH 隧道

```bash
# 强制使用 SSH 隧道（覆盖环境变量）
uv run python center_management/db/migration/pg_dump_remote.py \
  --data-only-sync --source remote --target local --all-schemas --use-tunnel

# 强制不使用 SSH 隧道
uv run python center_management/db/migration/pg_dump_remote.py \
  --data-only-sync --source remote --target local --all-schemas --no-tunnel
```

### 跳过 schema 初始化

```bash
# 只同步数据，不应用迁移脚本
uv run python center_management/db/migration/pg_dump_remote.py \
  --data-only-sync \
  --source remote \
  --target local \
  --all-schemas \
  --skip-schema-init
```

### 备份管理

```bash
# 列出所有备份文件
uv run python center_management/db/migration/pg_dump_remote.py --list

# 清理旧备份，只保留最新 5 个
uv run python center_management/db/migration/pg_dump_remote.py --cleanup --keep 5
```

## 🎯 常见使用场景

### 场景 1: 开发环境同步生产数据

```bash
# 每天同步一次生产数据到本地
uv run python center_management/db/migration/pg_dump_remote.py \
  --data-only-sync --source remote --target local --all-schemas
```

### 场景 2: 备份远程数据库

```bash
# 创建完整备份
uv run python center_management/db/migration/pg_dump_remote.py \
  --export --source remote --output "prod_backup_$(date +%Y%m%d).sql"
```

### 场景 3: 只更新表结构

```bash
# 应用新的迁移脚本到本地
uv run python center_management/db/migration/pg_dump_remote.py \
  --schema-init --target local
```

## 🔄 添加新业务表的处理

### ✅ 好消息：自动发现机制

从现在开始，当你添加新的业务表时，**无需手动更新任何配置**！

工具已升级为**动态表发现**机制：

**工作原理**:
1. 自动查询数据库中的所有表
2. 排除系统 schema（_realtime, extensions, pg_catalog 等）
3. 排除内部跟踪表（auth.schema_migrations, storage.migrations 等）
4. 自动包含所有业务表（test, test2, auth, storage, public 等）

**测试结果**:
```
✅ 自动发现了 39 个业务表
✅ 包括: auth.users, test.order, test.test_products, test2.*, test3.*, 等
✅ 成功清空并同步所有业务表数据
```

### 验证动态发现

查看日志输出，确认自动发现的表：
```bash
2025-09-30 15:32:50.271 | INFO - 发现 39 个业务表
2025-09-30 15:32:50.271 | DEBUG - 业务表列表: auth.audit_log_entries, auth.users,
                                             test.order, test.test_products,
                                             test2.order, test3.test_products, ...
```

### 排除特定表（高级）

如果需要排除某些业务表，可以通过代码参数传递：

```python
# 在代码中使用
tool = PgDumpTool()
tool._truncate_all_business_tables(
    target_type='local',
    exclude_tables=['test.temp_table', 'test2.debug_log']
)
```

### 添加新表的工作流程

1. **创建新表**: 通过迁移脚本或直接创建
2. **运行同步**: 使用 `--data-only-sync --all-schemas`
3. **自动处理**: 工具自动发现并处理新表
4. **无需配置**: 不需要修改任何配置文件

### 示例：添加新的 schema 和表

```sql
-- 创建新的 schema 和表
CREATE SCHEMA test7;
CREATE TABLE test7.new_orders (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id text NOT NULL,
    amount integer NOT NULL
);
```

然后直接运行同步：
```bash
uv run python center_management/db/migration/pg_dump_remote.py \
  --data-only-sync --source remote --target local --all-schemas
```

工具将自动：
- ✅ 发现 `test7.new_orders` 表
- ✅ 包含在清空和同步操作中
- ✅ 记录在日志中供验证

## 📁 文件结构

```
center_management/db/migration/
├── pg_dump_remote.py              # 主脚本
├── remote_db_config.py            # 配置管理
├── ssh_tunnel.py                  # SSH隧道管理
├── README.md                      # 详细文档
├── USAGE_GUIDE.md                 # 本文档
├── backups/                       # 备份文件目录
│   ├── test_migration_export.sql
│   └── data_only_all_schemas_remote_*.sql
└── sql_schema_migration/          # 迁移脚本
    ├── order_refactored.sql
    └── product_refactored.sql
```

## 🔒 安全注意事项

1. **SSH 密钥安全**
   - 私钥文件权限必须为 600: `chmod 600 ~/.ssh/id_ed25519`
   - 不要将私钥提交到版本控制

2. **密码保护**
   - 密码存储在 `.env.migration` 文件中
   - 确保 `.env.migration` 已添加到 `.gitignore`

3. **生产数据备份**
   - 定期备份远程数据库
   - 使用 `--cleanup` 管理备份文件数量

## ❓ 故障排除

### SSH 连接失败

```bash
# 测试 SSH 连接
ssh -i ~/.ssh/id_ed25519 root@8.134.74.41

# 如果失败，检查密钥权限
chmod 600 ~/.ssh/id_ed25519
```

### 数据库连接失败

```bash
# 测试本地数据库
psql "postgresql://postgres:你的密码@localhost:5438/postgres" -c "SELECT version();"

# 确保 Docker 容器运行中
docker ps | grep supabase-db
```

### Schema 冲突错误

**解决方案**: 使用 `--data-only-sync` 而不是 `--sync`，这样只同步数据不改变结构。

## 📝 测试验证结果

```
✅ 远程连接测试: 成功（SSH隧道正常）
✅ 数据导出测试: 成功（254KB，包含所有表）
✅ 数据导入测试: 成功（auth.users + 业务表）
✅ 数据完整性:
   - auth.users: 2 条记录 ✅
   - test.order: 1 条记录 ✅
   - test.test_products: 1 条记录 ✅
```

## 🎓 最佳实践

1. **开发环境同步**: 每天使用 `--data-only-sync --all-schemas`
2. **生产备份**: 每周使用 `--export --source remote`
3. **表结构更新**: 修改 SQL 脚本后使用 `--schema-init`
4. **备份清理**: 每月使用 `--cleanup --keep 10`