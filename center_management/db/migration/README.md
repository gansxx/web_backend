# PostgreSQL 数据库远程复制工具

这个工具支持在本地和远程 PostgreSQL 数据库之间复制数据，特别适合通过网关 IP 访问远程数据库的场景。

## 文件结构

```
center_management/db/migration/
├── pg_dump_remote.py      # 主脚本
├── remote_db_config.py    # 数据库配置管理
├── backups/              # 备份文件目录
├── README.md             # 使用说明
└── examples.sh           # 使用示例脚本
```

## 环境要求

1. **Python 依赖**: 已添加到 `pyproject.toml`
   - `psycopg2-binary>=2.9.7`
   - `loguru`
   - `python-dotenv`

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
- **远程**: 通过 `gateway_ip:5438` → 远程数据库容器
- **本地**: 通过 `localhost:5438` → 本地 Docker 容器
- **端口映射**: 5438 (外部) → 5432 (PostgreSQL 内部)

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

## 安全注意事项

1. **密码保护**: 密码通过环境变量传递，不会在命令行显示
2. **网络安全**: 远程连接通过指定的网关 IP 进行
3. **备份管理**: 定期清理旧备份文件以节省磁盘空间
4. **权限控制**: 确保只有授权用户可以访问生产数据库

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
| `--list` | 列出备份文件 | |
| `--cleanup` | 清理旧备份 | `--cleanup --keep 10` |