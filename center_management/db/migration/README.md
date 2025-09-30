# PostgreSQL 数据库远程复制工具

这个工具支持在本地和远程 PostgreSQL 数据库之间复制数据，特别适合通过网关 IP 访问远程数据库的场景。

## 文件结构

```
center_management/db/migration/
├── pg_dump_remote.py      # 主脚本
├── remote_db_config.py    # 数据库配置管理
├── ssh_tunnel.py          # SSH隧道管理器
├── backups/              # 备份文件目录
├── README.md             # 使用说明
└── examples.sh           # 使用示例脚本
```

## 环境要求

1. **Python 依赖**: 已添加到 `pyproject.toml`
   - `psycopg2-binary>=2.9.7`
   - `loguru`
   - `python-dotenv`
   - `paramiko` (SSH隧道功能)

2. **系统工具**: PostgreSQL 客户端工具
   - Ubuntu/Debian: `sudo apt-get install postgresql-client`
   - CentOS/RHEL: `sudo yum install postgresql`
   - macOS: `brew install postgresql`

3. **环境变量配置**:
   - **本地配置**: `.env` 文件 (已存在)
   - **远程配置**: `.env.migration` 文件 (推荐) 或 `.env.remote` 文件
   - **配置模板**: `.env.migration.example` (专为数据库迁移设计)

## 配置说明

### 快速开始 - 配置远程数据库

1. **复制配置模板**:
   ```bash
   cp .env.migration.example .env.migration
   ```

2. **编辑配置文件**:
   ```bash
   # 编辑 .env.migration 文件，填入实际值
   gateway_ip='你的网关IP地址'
   POSTGRES_PASSWORD=你的远程数据库密码
   ```

3. **测试连接**:
   ```bash
   uv run python center_management/db/migration/pg_dump_remote.py --test
   ```

### 详细配置说明

#### 本地数据库配置
默认使用 `.env` 文件中的配置：
- **Host**: localhost
- **Port**: 5438 (Docker 映射端口)
- **Database**: postgres
- **User**: postgres
- **Password**: 来自 POSTGRES_PASSWORD 环境变量

#### 远程数据库配置
**推荐使用** `.env.migration` 文件，配置参数：

| 参数 | 说明 | 示例值 | 必需 |
|------|------|--------|------|
| `gateway_ip` | 网关IP地址 | `'192.168.1.100'` | ✅ |
| `POSTGRES_PASSWORD` | 数据库密码 | `your_password` | ✅ |
| `POSTGRES_DB` | 数据库名 | `postgres` | ❌ |
| `POSTGRES_HOST` | 主机名 | `db` | ❌ |
| `POSTGRES_PORT` | 内部端口 | `5432` | ❌ |

**配置文件优先级**:
1. `.env.migration` (推荐，专为迁移工具设计)
2. `.env.remote` (备选)
3. `.env.remote.example` (示例文件)
4. `.env.migration.example` (仅作参考)

#### 连接方式说明

**支持两种连接模式**:

1. **直接连接模式** (`USE_SSH_TUNNEL=false` 或未配置):
   - 通过 `remote_db_ip:REMOTE_POSTGRES_PORT` 直接连接远程数据库
   - 要求远程数据库端口对外开放
   - 配置简单，适合内网环境或已配置端口转发的场景

2. **SSH隧道模式** (`USE_SSH_TUNNEL=true`):
   - 本地脚本 → `localhost:LOCAL_remote_POSTGRES_PORT` (默认5439)
   - SSH隧道通过 `SSH_GATEWAY_HOST` 建立端口转发
   - 转发到远程数据库 `REMOTE_POSTGRES_HOST:REMOTE_POSTGRES_PORT`
   - 更安全，无需直接暴露数据库端口
   - 适合生产环境或需要通过跳板机访问的场景

**端口配置**:
- `REMOTE_POSTGRES_PORT` (5438): 远程数据库监听端口
- `LOCAL_remote_POSTGRES_PORT` (5439): 本地SSH隧道转发端口
- 本地数据库: `localhost:5438` → 本地 Docker 容器

## 使用方法

### 1. 测试数据库连接
```bash
uv run python center_management/db/migration/pg_dump_remote.py --test
```

### 2. 导出数据库

**从远程导出全库**
```bash
uv run python center_management/db/migration/pg_dump_remote.py --export --source remote
```

**从本地导出全库到指定文件**
```bash
uv run python center_management/db/migration/pg_dump_remote.py --export --source local --output my_backup.sql
```

**导出指定表**
```bash
uv run python center_management/db/migration/pg_dump_remote.py --export --source remote --tables "orders,products,users"
```

**只导出数据结构（不包含数据）**
```bash
uv run python center_management/db/migration/pg_dump_remote.py --export --source remote --schema-only
```

**只导出数据（不包含结构）**
```bash
uv run python center_management/db/migration/pg_dump_remote.py --export --source remote --data-only
```

### 3. 导入数据库

**从备份文件导入到本地数据库**
```bash
uv run python center_management/db/migration/pg_dump_remote.py --import --file backups/backup_20240101_120000.sql --target local
```

**导入前清理目标数据库**
```bash
uv run python center_management/db/migration/pg_dump_remote.py --import --file backup.sql --target local --clean
```

### 4. 直接同步数据库

**从远程同步到本地（最常用）**
```bash
uv run python center_management/db/migration/pg_dump_remote.py --sync --source remote --target local
```

**使用SSH隧道同步（强制启用）**
```bash
uv run python center_management/db/migration/pg_dump_remote.py --sync --source remote --target local --use-tunnel
```

**不使用SSH隧道同步（强制禁用）**
```bash
uv run python center_management/db/migration/pg_dump_remote.py --sync --source remote --target local --no-tunnel
```

**同步指定表**
```bash
uv run python center_management/db/migration/pg_dump_remote.py --sync --source remote --target local --tables "orders,products"
```

**同步前清理目标数据库**
```bash
uv run python center_management/db/migration/pg_dump_remote.py --sync --source remote --target local --clean
```

### 5. 备份管理

**列出所有备份文件**
```bash
uv run python center_management/db/migration/pg_dump_remote.py --list
```

**清理旧备份文件（只保留最新 5 个）**
```bash
uv run python center_management/db/migration/pg_dump_remote.py --cleanup --keep 5
```

## 常见使用场景

### 场景1: 开发环境同步生产数据
```bash
# 从远程生产数据库同步到本地开发环境
uv run python center_management/db/migration/pg_dump_remote.py --sync --source remote --target local --clean
```

### 场景2: 备份远程数据库
```bash
# 导出远程数据库的完整备份
uv run python center_management/db/migration/pg_dump_remote.py --export --source remote --output "prod_backup_$(date +%Y%m%d).sql"
```

### 场景3: 同步特定表的数据
```bash
# 只同步订单和产品表
uv run python center_management/db/migration/pg_dump_remote.py --sync --source remote --target local --tables "orders,products"
```

### 场景4: 数据库结构同步
```bash
# 只同步数据库结构（用于开发环境初始化）
uv run python center_management/db/migration/pg_dump_remote.py --export --source remote --schema-only
```

## SSH隧道模式详细说明

### 启用SSH隧道

在 `.env.migration` 文件中配置:

```bash
# 启用SSH隧道
USE_SSH_TUNNEL=true

# SSH网关配置
SSH_GATEWAY_HOST=8.134.74.41
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
   ssh -i ./center_management/id_ed25519 root@8.134.74.41
   ```

### 工作原理

```
┌─────────────┐                    ┌──────────────┐                 ┌──────────────┐
│  本地脚本    │ ─────────────────> │  SSH网关      │ ──────────────> │ 远程数据库    │
│             │  SSH Tunnel        │  (跳板机)     │  内网连接        │  (PostgreSQL) │
└─────────────┘                    └──────────────┘                 └──────────────┘
   localhost:5439                   8.134.74.41:22                    db:5438
```

### 优势

1. **安全性**: 数据库端口无需对外开放，只需开放SSH端口
2. **灵活性**: 支持通过跳板机访问内网数据库
3. **加密传输**: 所有数据通过SSH加密传输
4. **审计追踪**: SSH登录可记录审计日志

## 安全注意事项

1. **密码保护**: 密码通过环境变量传递，不会在命令行显示
2. **SSH密钥安全**:
   - 私钥文件权限设置为 600
   - 不要将私钥提交到版本控制系统
   - 定期轮换SSH密钥
3. **网络安全**:
   - 推荐使用SSH隧道模式
   - 仅在必要时开放数据库端口
4. **备份管理**: 定期清理旧备份文件以节省磁盘空间
5. **权限控制**: 确保只有授权用户可以访问生产数据库
6. **配置文件安全**:
   - `.env.migration` 文件权限设置为 600
   - 添加到 `.gitignore` 防止泄露

## 故障排除

### 连接问题
- 检查网关 IP 是否可达
- 验证端口是否开放（默认 5438）
- 确认数据库用户名密码正确

### 工具依赖
- 确保安装了 PostgreSQL 客户端工具
- 检查 Python 依赖是否完整安装

### 权限问题
- 确保数据库用户有足够的权限
- 检查防火墙和安全组设置

### SSH隧道问题
- **连接失败**: 检查 SSH_GATEWAY_HOST 和 SSH_GATEWAY_PORT
- **认证失败**: 验证 SSH_KEY_FILE 路径和权限 (chmod 600)
- **端口转发失败**: 确认SSH网关允许端口转发 (AllowTcpForwarding yes)
- **端口已占用**: 更改 LOCAL_remote_POSTGRES_PORT 到其他端口
- **测试SSH**: `ssh -i SSH_KEY_FILE SSH_GATEWAY_USER@SSH_GATEWAY_HOST`

## 日志和调试

工具使用 loguru 进行日志记录，会显示详细的操作信息和错误提示。如果遇到问题，请检查日志输出中的错误信息。

## 参数参考

| 参数 | 说明 | 示例 |
|------|------|------|
| `--test` | 测试数据库连接 | |
| `--export` | 导出数据库 | |
| `--import` | 导入数据库 | `--import --file backup.sql` |
| `--sync` | 同步数据库 | |
| `--source` | 源数据库 | `--source remote` |
| `--target` | 目标数据库 | `--target local` |
| `--output` | 输出文件 | `--output backup.sql` |
| `--file` | 输入文件 | `--file backup.sql` |
| `--tables` | 指定表名 | `--tables "orders,products"` |
| `--schema-only` | 只导出结构 | |
| `--data-only` | 只导出数据 | |
| `--clean` | 清理目标数据库 | |
| `--use-tunnel` | 强制使用SSH隧道 | |
| `--no-tunnel` | 强制不使用SSH隧道 | |
| `--list` | 列出备份文件 | |
| `--cleanup` | 清理旧备份 | `--cleanup --keep 10` |