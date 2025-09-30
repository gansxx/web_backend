# 数据库迁移工具完整指南

这个工具支持在本地和远程 PostgreSQL 数据库之间复制数据，特别适合通过网关 IP 或 SSH 隧道访问远程数据库的场景。

## ✅ 测试验证状态

已完成全面测试，所有功能正常工作：
- ✅ 远程数据库连接（支持直连和SSH隧道）
- ✅ 导出 auth.users 和业务表数据
- ✅ 导入到本地数据库
- ✅ 数据完整性验证
- ✅ 动态表发现（自动识别所有业务表）

## 🚀 快速开始

### 1. 配置环境变量

复制配置模板并填入实际值：

```bash
# 复制配置模板
cp .env.migration.example .env.migration

# 编辑配置文件，填入以下关键信息
# - remote_db_ip: 你的远程数据库IP地址
# - REMOTE_POSTGRES_PASSWORD: 远程数据库密码
# - SSH配置（如果使用SSH隧道）
```

**配置示例** (`.env.migration`):
```bash
# 远程数据库配置
remote_db_ip=YOUR_REMOTE_IP_HERE
REMOTE_POSTGRES_PASSWORD=your_password_here
REMOTE_POSTGRES_HOST=127.0.0.1
REMOTE_POSTGRES_PORT=5438

# SSH隧道配置（可选）
USE_SSH_TUNNEL=true
SSH_GATEWAY_HOST=YOUR_GATEWAY_IP_HERE
SSH_KEY_FILE=~/.ssh/id_ed25519
```

### 2. 测试连接

```bash
uv run python center_management/db/migration/pg_dump_remote.py --test
```

### 3. 运行数据同步（推荐方式）⭐

```bash
# 同步所有业务数据（包括 auth.users, test.order, test.test_products 等）
uv run python center_management/db/migration/pg_dump_remote.py \
  --data-only-sync \
  --source remote \
  --target local \
  --all-schemas
```

## 📁 文件结构

```
center_management/db/migration/
├── pg_dump_remote.py              # 主脚本
├── remote_db_config.py            # 配置管理
├── ssh_tunnel.py                  # SSH隧道管理
├── MIGRATION_GUIDE.md             # 本文档
├── backups/                       # 备份文件目录
└── sql_schema_migration/          # 本地迁移脚本目录
    ├── order_refactored.sql       # 订单表迁移脚本
    └── product_refactored.sql     # 产品表迁移脚本
```

**重要说明：** `schema_init` 功能从 `sql_schema_migration/` 目录读取本地迁移脚本。

## 🔧 环境要求

### Python 依赖
已添加到 `pyproject.toml`：
- `psycopg2-binary>=2.9.7`
- `loguru`
- `python-dotenv`
- `paramiko` (SSH隧道功能)

### 系统工具
PostgreSQL 客户端工具：
- Ubuntu/Debian: `sudo apt-get install postgresql-client`
- CentOS/RHEL: `sudo yum install postgresql`
- macOS: `brew install postgresql`

### 环境变量配置
- **本地配置**: `.env` 文件（已存在）
- **远程配置**: `.env.migration` 文件（推荐）或 `.env.remote` 文件
- **配置模板**: `.env.migration.example`

## ⚙️ 配置详解

### 本地数据库配置
默认使用 `.env` 文件中的配置：
- **Host**: localhost
- **Port**: 5438（Docker 映射端口）
- **Database**: postgres
- **User**: postgres
- **Password**: 来自 POSTGRES_PASSWORD 环境变量

### 远程数据库配置

**配置文件优先级**:
1. `.env.migration`（推荐，专为迁移工具设计）
2. `.env.remote`（备选）
3. `.env.remote.example`（示例文件）
4. `.env.migration.example`（仅作参考）

**必需参数:**

| 参数 | 说明 | 示例值 | 必需 |
|------|------|--------|------|
| `remote_db_ip` | 网关IP地址 | `YOUR_IP_HERE` | ✅ |
| `REMOTE_POSTGRES_PASSWORD` | 数据库密码 | `your_password` | ✅ |
| `REMOTE_POSTGRES_DB` | 数据库名 | `postgres` | ❌ |
| `REMOTE_POSTGRES_HOST` | 主机名 | `db` 或 `127.0.0.1` | ❌ |
| `REMOTE_POSTGRES_PORT` | 内部端口 | `5438` | ❌ |

### 连接方式说明

工具支持两种连接模式：

#### 1. 直接连接模式（`USE_SSH_TUNNEL=false` 或未配置）

- 通过 `remote_db_ip:REMOTE_POSTGRES_PORT` 直接连接远程数据库
- 要求远程数据库端口对外开放
- 配置简单，适合内网环境或已配置端口转发的场景

#### 2. SSH隧道模式（`USE_SSH_TUNNEL=true`）✨

- 本地脚本 → `localhost:LOCAL_remote_POSTGRES_PORT`（默认5439）
- SSH隧道通过 `SSH_GATEWAY_HOST` 建立端口转发
- 转发到远程数据库 `REMOTE_POSTGRES_HOST:REMOTE_POSTGRES_PORT`
- **更安全**，无需直接暴露数据库端口
- 适合生产环境或需要通过跳板机访问的场景

**工作原理：**
```
┌─────────────┐                    ┌──────────────┐                 ┌──────────────┐
│  本地脚本    │ ─────────────────> │  SSH网关      │ ──────────────> │ 远程数据库    │
│             │  SSH Tunnel        │  (跳板机)     │  内网连接        │  (PostgreSQL) │
└─────────────┘                    └──────────────┘                 └──────────────┘
   localhost:5439                   SSH_GATEWAY_HOST                  db:5438
```

**端口配置说明：**
- `REMOTE_POSTGRES_PORT`（默认5438）：远程数据库监听端口
- `LOCAL_remote_POSTGRES_PORT`（默认5439）：本地SSH隧道转发端口
- 本地数据库：`localhost:5438` → 本地 Docker 容器

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
1. 应用迁移脚本初始化表结构（从 `supabase/migrations/`）
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
# 应用迁移脚本，创建/更新表结构（从 sql_schema_migration/）
uv run python center_management/db/migration/pg_dump_remote.py \
  --schema-init \
  --target local
```

**注意：** 此功能从 `sql_schema_migration/` 目录读取 SQL 文件，默认执行：
- `order_refactored.sql`
- `product_refactored.sql`

### 功能 3: 导出数据库

```bash
# 导出完整数据库（结构+数据）
uv run python center_management/db/migration/pg_dump_remote.py \
  --export \
  --source remote

# 只导出数据
uv run python center_management/db/migration/pg_dump_remote.py \
  --export \
  --source remote \
  --data-only

# 只导出结构
uv run python center_management/db/migration/pg_dump_remote.py \
  --export \
  --source remote \
  --schema-only

# 导出到指定文件
uv run python center_management/db/migration/pg_dump_remote.py \
  --export \
  --source remote \
  --output my_backup.sql
```

### 功能 4: 导入数据库

```bash
# 从备份文件导入到本地数据库
uv run python center_management/db/migration/pg_dump_remote.py \
  --import \
  --file backups/backup_20240101_120000.sql \
  --target local

# 导入前清理目标数据库
uv run python center_management/db/migration/pg_dump_remote.py \
  --import \
  --file backup.sql \
  --target local \
  --clean
```

### 功能 5: 同步特定 schema

```bash
# 只同步 test schema 的数据
uv run python center_management/db/migration/pg_dump_remote.py \
  --data-only-sync \
  --source remote \
  --target local \
  --schema test

# 同步指定表
uv run python center_management/db/migration/pg_dump_remote.py \
  --sync \
  --source remote \
  --target local \
  --tables "orders,products"
```

### 功能 6: 备份管理

```bash
# 列出所有备份文件
uv run python center_management/db/migration/pg_dump_remote.py --list

# 清理旧备份文件（只保留最新 5 个）
uv run python center_management/db/migration/pg_dump_remote.py --cleanup --keep 5
```

## 🔄 动态表发现机制

### ✅ 自动发现所有业务表

从现在开始，当你添加新的业务表时，**无需手动更新任何配置**！

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

## 🎯 常见使用场景

### 场景1: 开发环境同步生产数据

```bash
# 每天同步一次生产数据到本地（推荐）
uv run python center_management/db/migration/pg_dump_remote.py \
  --data-only-sync --source remote --target local --all-schemas
```

### 场景2: 备份远程数据库

```bash
# 创建完整备份
uv run python center_management/db/migration/pg_dump_remote.py \
  --export --source remote --output "prod_backup_$(date +%Y%m%d).sql"
```

### 场景3: 只更新表结构

```bash
# 应用新的迁移脚本到本地（从 sql_schema_migration/）
uv run python center_management/db/migration/pg_dump_remote.py \
  --schema-init --target local
```

### 场景4: 同步特定表的数据

```bash
# 只同步订单和产品表
uv run python center_management/db/migration/pg_dump_remote.py \
  --sync --source remote --target local --tables "orders,products"
```

## 🔐 SSH隧道模式详细配置

### 启用SSH隧道

在 `.env.migration` 文件中配置:

```bash
# 启用SSH隧道
USE_SSH_TUNNEL=true

# SSH网关配置
SSH_GATEWAY_HOST=YOUR_GATEWAY_IP_HERE
SSH_GATEWAY_PORT=22
SSH_GATEWAY_USER=root
SSH_KEY_FILE=./center_management/id_ed25519

# 远程数据库配置
REMOTE_POSTGRES_HOST=db
REMOTE_POSTGRES_PORT=5438
LOCAL_remote_POSTGRES_PORT=5439
```

### SSH密钥配置

1. **确保SSH密钥存在**:
   ```bash
   ls -la ./center_management/id_ed25519
   ```

2. **设置正确权限**:
   ```bash
   chmod 600 ./center_management/id_ed25519
   ```

3. **测试SSH连接**:
   ```bash
   ssh -i ./center_management/id_ed25519 root@YOUR_GATEWAY_IP_HERE
   ```

### 强制使用/不使用 SSH 隧道

```bash
# 强制使用 SSH 隧道（覆盖环境变量）
uv run python center_management/db/migration/pg_dump_remote.py \
  --data-only-sync --source remote --target local --all-schemas --use-tunnel

# 强制不使用 SSH 隧道
uv run python center_management/db/migration/pg_dump_remote.py \
  --data-only-sync --source remote --target local --all-schemas --no-tunnel
```

### SSH隧道优势

1. **安全性**: 数据库端口无需对外开放，只需开放SSH端口
2. **灵活性**: 支持通过跳板机访问内网数据库
3. **加密传输**: 所有数据通过SSH加密传输
4. **审计追踪**: SSH登录可记录审计日志

## 🔧 高级用法

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

## 📊 验证数据迁移

### 验证 auth.users 表

```bash
# 替换 YOUR_PASSWORD 为实际密码
psql "postgresql://postgres:YOUR_PASSWORD@localhost:5438/postgres" \
  -c "SELECT COUNT(*), MAX(created_at) FROM auth.users;"
```

### 验证业务表

```bash
# 检查订单表
psql "postgresql://postgres:YOUR_PASSWORD@localhost:5438/postgres" \
  -c "SELECT COUNT(*) FROM test.\"order\";"

# 检查产品表
psql "postgresql://postgres:YOUR_PASSWORD@localhost:5438/postgres" \
  -c "SELECT COUNT(*) FROM test.test_products;"
```

## 🔒 安全注意事项

### 密码保护
- 密码通过环境变量传递，不会在命令行显示
- 确保 `.env.migration` 已添加到 `.gitignore`
- 配置文件权限设置为 600: `chmod 600 .env.migration`

### SSH密钥安全
- 私钥文件权限必须为 600: `chmod 600 ~/.ssh/id_ed25519`
- 不要将私钥提交到版本控制
- 定期轮换SSH密钥

### 网络安全
- 推荐使用SSH隧道模式
- 仅在必要时开放数据库端口
- 使用防火墙和安全组限制访问

### 生产数据备份
- 定期备份远程数据库
- 使用 `--cleanup` 管理备份文件数量
- 定期验证备份可恢复性

### 权限控制
- 确保只有授权用户可以访问生产数据库
- 使用最小权限原则配置数据库用户

## ❓ 故障排除

### 连接问题

**症状**: 无法连接到数据库

**解决方案**:
- 检查网关 IP 是否可达: `ping YOUR_GATEWAY_IP`
- 验证端口是否开放: `telnet YOUR_GATEWAY_IP 5438`
- 确认数据库用户名密码正确
- 检查 `.env.migration` 配置文件

### SSH隧道问题

**连接失败**:
```bash
# 检查 SSH_GATEWAY_HOST 和 SSH_GATEWAY_PORT
ssh -i SSH_KEY_FILE SSH_GATEWAY_USER@SSH_GATEWAY_HOST
```

**认证失败**:
```bash
# 验证 SSH_KEY_FILE 路径和权限
chmod 600 ~/.ssh/id_ed25519
ls -la ~/.ssh/id_ed25519
```

**端口转发失败**:
- 确认SSH网关允许端口转发 (AllowTcpForwarding yes)
- 检查防火墙规则

**端口已占用**:
```bash
# 更改 LOCAL_remote_POSTGRES_PORT 到其他端口
# 在 .env.migration 中修改
LOCAL_remote_POSTGRES_PORT=5440
```

### 工具依赖问题

**缺少 PostgreSQL 客户端**:
```bash
# Ubuntu/Debian
sudo apt-get install postgresql-client

# CentOS/RHEL
sudo yum install postgresql

# macOS
brew install postgresql
```

**Python 依赖缺失**:
```bash
# 重新同步依赖
uv sync
```

### 权限问题

**数据库权限不足**:
- 确保数据库用户有足够的权限
- 检查是否需要 supabase_admin 权限
- 查看错误日志了解具体权限问题

**Schema 冲突错误**:
- 使用 `--data-only-sync` 而不是 `--sync`
- 这样只同步数据不改变结构

### 数据库连接测试

```bash
# 测试本地数据库
psql "postgresql://postgres:YOUR_PASSWORD@localhost:5438/postgres" -c "SELECT version();"

# 确保 Docker 容器运行中
docker ps | grep supabase-db
```

## 📝 参数完整参考

### 主要操作参数

| 参数 | 说明 | 示例 |
|------|------|------|
| `--test` | 测试数据库连接 | |
| `--export` | 导出数据库 | |
| `--import` | 导入数据库 | `--import --file backup.sql` |
| `--sync` | 同步数据库（完整） | |
| `--data-only-sync` | 只同步数据（推荐） | |
| `--schema-init` | 只初始化schema | |
| `--list` | 列出备份文件 | |
| `--cleanup` | 清理旧备份 | `--cleanup --keep 10` |

### 数据库相关参数

| 参数 | 说明 | 默认值 |
|------|------|--------|
| `--source` | 源数据库类型 | `remote` |
| `--target` | 目标数据库类型 | `local` |
| `--schema` | Schema名称 | `test` |
| `--all-schemas` | 同步所有业务schema | - |

### 文件相关参数

| 参数 | 说明 | 示例 |
|------|------|------|
| `--output` | 输出文件路径（导出） | `--output backup.sql` |
| `--file` | SQL文件路径（导入） | `--file backup.sql` |

### 导出选项

| 参数 | 说明 |
|------|------|
| `--tables` | 指定表名，逗号分隔 |
| `--schema-only` | 只导出结构 |
| `--data-only` | 只导出数据 |

### 导入选项

| 参数 | 说明 |
|------|------|
| `--clean` | 导入前清理目标数据库 |
| `--no-stop-services` | 导入时不停止Supabase服务 |

### 同步选项

| 参数 | 说明 |
|------|------|
| `--skip-schema-init` | 跳过schema初始化 |

### SSH隧道选项

| 参数 | 说明 |
|------|------|
| `--use-tunnel` | 强制使用SSH隧道 |
| `--no-tunnel` | 强制不使用SSH隧道 |

### 清理选项

| 参数 | 说明 | 默认值 |
|------|------|--------|
| `--keep` | 保留备份文件数量 | `10` |

## 🎓 最佳实践

### 日常开发

1. **每天同步数据**: 使用 `--data-only-sync --all-schemas`
2. **保持结构更新**: 定期执行 `--schema-init`
3. **验证数据**: 同步后验证关键表的记录数

### 生产备份

1. **定期备份**: 每周使用 `--export --source remote`
2. **备份管理**: 每月使用 `--cleanup --keep 10`
3. **异地存储**: 将备份文件复制到其他位置

### 安全策略

1. **使用SSH隧道**: 生产环境优先使用SSH隧道模式
2. **限制访问**: 只授予必要的数据库权限
3. **审计日志**: 定期检查数据库访问日志

### 性能优化

1. **压缩传输**: 大数据量时使用压缩
2. **并行处理**: 根据需要调整并发设置
3. **增量同步**: 只同步变化的数据（需自定义）

## 📖 日志和调试

工具使用 loguru 进行日志记录，会显示详细的操作信息和错误提示。

**日志级别**:
- `INFO`: 正常操作信息
- `DEBUG`: 详细调试信息
- `WARNING`: 警告信息
- `ERROR`: 错误信息
- `SUCCESS`: 成功完成信息

如果遇到问题，请检查日志输出中的错误信息，并参考故障排除章节。

## 📚 相关文档

- **PostgreSQL 官方文档**: https://www.postgresql.org/docs/
- **Supabase 文档**: https://supabase.com/docs
- **SSH 隧道配置**: https://www.ssh.com/academy/ssh/tunneling