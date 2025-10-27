# 代码库硬编码变量分析报告

## 概述

本报告基于对 `center_management` 目录和整个代码库的系统性搜索，识别并分析了所有硬编码变量，评估其安全风险并提供改进建议。

**统计摘要:**
- **center_management目录**: 约40+个硬编码变量
- **整个代码库**: 约60+个硬编码变量
- **数据库迁移工具**: 已修复2个，识别8个需改进项

**最新更新 (2025-09-30):**
- ✅ 修复了数据库迁移工具中的硬编码表名回退
- ✅ 修改 schema_init 从 `sql_schema_migration/` 目录读取迁移脚本
- 📋 新增数据库迁移工具硬编码值详细分析（见附录A）

## 📍 IP地址硬编码 (高优先级)

### center_management 目录

**生产环境IP:**
- `orchestrationer.py:23` - `"202.182.106.233"` (get_host函数返回值)
- `test_api.py:14` - `'45.32.252.106'` (测试服务器地址)

**示例和测试IP:**
- `demo_multi_cloud.py:278` - `"1.2.3.4"` (示例IP)
- `dns.py:32` - `"1.2.3.4"` (示例IP)
- `test_api.py:615,741` - `"1.2.3.4"` (用户输入提示)

**本地和私有网络:**
- `orchestrationer.py:30,189` - `'127.0.0.1,::1,192.168.0.0/16,10.0.0.0/8,172.16.0.0/12'` (默认允许IP)
- `test_ip_whitelist.py` - 多个测试IP地址
- `link_verificate.sh:148,166,171,187` - `127.0.0.1` (本地代理配置)

### 其他位置

**容器和服务配置:**
- `docker-compose.yml` - 多个 `0.0.0.0`, `127.0.0.1` (容器网络配置)
- `test_main.py:42,43,174` - `127.0.0.1` (本地测试地址)
- `supabase/config.toml` - 多个本地IP配置
- `run.py:23` - `0.0.0.0` (服务绑定地址)

## 🔌 端口硬编码

### center_management 目录

**服务端口:**
- `orchestrationer.py:196` - `port=8002` (orchestrationer服务端口)
- `test_ip_whitelist.py:15` - `"http://127.0.0.1:8002"` (测试URL)

**端口范围配置:**
- `smart_port_manager.py:97,219` - `min_port=10000, max_port=30000` (默认端口范围)
- `backend_api_v2.py:200,201` - `min_port=15000, max_port=16000` (测试端口范围)

**SSH和连接端口:**
- 多个文件中的 `port=22` (SSH默认端口)
- `link_verificate.sh:64` - `:9989` (示例端口)
- `link_verificate.sh:148,166,187` - `:1080` (本地代理端口)

### 其他位置

**主要服务端口:**
- `run.py:23` - `port=8000` (主API服务端口)
- `.env.example` - 多个端口配置:
  - `POSTGRES_PORT=5432`
  - `KONG_HTTP_PORT=8000`
  - `KONG_HTTPS_PORT=8443`
  - `STUDIO_PORT=3000`
  - `SMTP_PORT=2500`

## 🌐 URL硬编码

### center_management 目录

**API端点:**
- `cloud_pool_demo/vps_manager/vultr.py:19` - `"https://api.vultr.com/v2"`
- `vps_vultur_manage.py` - 多个Vultr API端点:
  - `'https://api.vultr.com/v2/instances'`
  - `'https://api.vultr.com/v2/instances/reboot'`
  - `f"https://api.vultr.com/v2/instances/{instance_id}/ipv4"`

**外部服务:**
- `node_meta.py:23` - `'https://icanhazip.com'` (IP查询服务)
- `link_verificate.sh:187` - `https://google.com` (连接测试)

**Git仓库 (包含认证信息):**
- `init_env.sh:29` - `"https://gansxx:8j8U_0Jz92LsthdG17GxYW86MQp1OjQ1NXEK.01.100h7pp8l@jihulab.com/gansxx/sing-box-v2ray.git"`

### 其他位置

**本地服务:**
- `base_config.py:12` - `'http://localhost:8000'` (Supabase URL默认值)
- `README_orchestrationer.md` - 多个localhost测试URL

## 📁 文件路径硬编码

### center_management 目录

**系统路径:**
- `node_meta.py:5` - `'/etc/s-box/server_ipcl.log'`
- `orchestrationer.py:141` - `"/root/notify.log"`

**脚本路径:**
- `node_manage.py:97` - `'/root/sing-box-v2ray/self_sb_change.sh'`
- `deploy_and_init.py:79` - `'/root/init_env.sh'`
- `init_env.sh:67,70` - `'./sb.sh'`, `'./sb_move.sh'`

**SSH密钥路径:**
- `backend_api_v2.py:18` - `'id_ed25519'`
- `deploy_and_init.py:145,216` - `'id_ed25519'`
- 多个文件中的 `'/root/.ssh/id_ed25519'`

**日志和配置:**
- `link_verificate.sh:28,39` - 日志文件路径

## 🔐 凭据和认证硬编码 (安全风险)

### 高风险项目

**SSH私钥文件:**
- `id_ed25519` - SSH私钥文件直接存储在代码库中

**认证URL:**
- `init_env.sh:29` - Git仓库URL包含明文访问令牌

**凭据模板:**
- `cloud_pool_demo/aws_ec2_credentials.json`
- `cloud_pool_demo/aws_lightsail_credentials.json`
- `cloud_pool_demo/vultr_credentials.json` (模板文件，但存在泄露风险)

### 中等风险项目

**环境变量引用:**
- 多个文件中对 `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY` 的硬编码引用
- `TENCENTCLOUD_SECRET_ID`, `TENCENTCLOUD_SECRET_KEY` 引用

## 🎯 网络配置硬编码

### IP白名单默认配置
- `orchestrationer.py:30` - 默认允许的IP范围:
  - `127.0.0.1` (本地回环)
  - `::1` (IPv6本地回环)
  - `192.168.0.0/16` (私有网络A类)
  - `10.0.0.0/8` (私有网络B类)
  - `172.16.0.0/12` (私有网络C类)

### 测试网络配置
- `link_verificate.sh` - `127.0.0.1:1080` (本地SOCKS5代理)
- 各种测试脚本中的私有网络地址示例

## ⚠️ 安全风险评估

### 🔴 高风险 (立即处理)

1. **SSH私钥泄露**: `id_ed25519` 文件直接存储在代码库中
   - **影响**: 可能导致服务器被未授权访问
   - **建议**: 立即从代码库删除，使用密钥管理服务

2. **认证令牌泄露**: `init_env.sh` 包含明文Git访问令牌
   - **影响**: Git仓库可能被未授权访问
   - **建议**: 撤销令牌，使用环境变量或密钥管理

3. **生产IP地址暴露**: `get_host()` 返回固定生产IP
   - **影响**: 暴露生产环境网络拓扑
   - **建议**: 移至环境变量或配置文件

### 🟡 中等风险 (优先处理)

1. **API端点硬编码**: Vultr等第三方服务的硬编码URL
   - **影响**: 缺乏环境隔离，难以测试和迁移
   - **建议**: 配置化管理

2. **默认端口配置**: 服务端口配置缺乏灵活性
   - **影响**: 部署灵活性差，可能与其他服务冲突
   - **建议**: 环境变量化

3. **测试数据混合**: 包含真实服务器地址的测试代码
   - **影响**: 可能意外影响生产环境
   - **建议**: 使用mock数据

### 🟢 低风险 (常规处理)

1. **本地配置**: localhost相关的硬编码
   - **影响**: 主要影响开发体验
   - **建议**: 逐步配置化

2. **示例数据**: 用于文档和示例的虚假数据
   - **影响**: 基本无安全风险
   - **建议**: 定期审查更新

## 📋 改进建议

### 立即执行

1. **移除敏感文件**:
   ```bash
   # 从代码库删除私钥
   git rm center_management/id_ed25519
   git commit -m "Remove SSH private key from repository"

   # 添加到.gitignore
   echo "*.key" >> .gitignore
   echo "id_*" >> .gitignore
   ```

2. **撤销和替换认证信息**:
   - 撤销 `init_env.sh` 中的Git访问令牌
   - 使用环境变量替换认证URL

### 短期改进

3. **环境变量化核心配置**:
   ```python
   # orchestrationer.py
   def get_host() -> str:
       return os.getenv('GATEWAY_HOST', '127.0.0.1')  # 默认本地

   # 服务端口配置
   PORT = int(os.getenv('ORCHESTRATIONER_PORT', '8002'))
   ```

4. **创建配置管理系统**:
   ```python
   # config/settings.py
   class Settings:
       gateway_host: str = Field(env='GATEWAY_HOST')
       orchestrationer_port: int = Field(env='ORCHESTRATIONER_PORT', default=8002)
       vultr_api_base: str = Field(env='VULTR_API_BASE', default='https://api.vultr.com/v2')
   ```

### 中期改进

5. **统一密钥管理**:
   - 实施 HashiCorp Vault 或 AWS Secrets Manager
   - 创建密钥轮换策略

6. **测试数据隔离**:
   - 创建专用的测试环境配置
   - 使用mock服务替代真实API调用

7. **配置验证机制**:
   ```python
   def validate_config():
       required_vars = ['GATEWAY_HOST', 'SERVICE_ROLE_KEY']
       missing = [var for var in required_vars if not os.getenv(var)]
       if missing:
           raise ConfigError(f"Missing required environment variables: {missing}")
   ```

### 长期改进

8. **配置中心化**:
   - 实施统一的配置管理服务
   - 支持动态配置更新

9. **安全扫描自动化**:
   - 集成代码安全扫描工具
   - 设置硬编码检测的CI/CD检查

10. **文档和培训**:
    - 建立安全编码规范
    - 团队安全意识培训

## 📊 优先级矩阵

| 类型 | 风险级别 | 数量 | 处理优先级 | 预估工时 |
|------|----------|------|------------|----------|
| SSH私钥 | 高 | 1 | P0 | 1小时 |
| 认证令牌 | 高 | 1 | P0 | 2小时 |
| 生产IP | 高 | 2 | P1 | 4小时 |
| API端点 | 中 | 10+ | P2 | 8小时 |
| 端口配置 | 中 | 15+ | P2 | 6小时 |
| 文件路径 | 低 | 20+ | P3 | 12小时 |
| 测试数据 | 低 | 10+ | P3 | 4小时 |

## 📝 检查清单

### 安全检查
- [ ] 移除代码库中的SSH私钥文件
- [ ] 撤销并替换暴露的访问令牌
- [ ] 审查所有凭据模板文件
- [ ] 验证.gitignore配置

### 配置管理
- [ ] 核心IP和端口环境变量化
- [ ] API端点配置化
- [ ] 创建配置验证机制
- [ ] 建立配置文档

### 测试和质量
- [ ] 测试数据与生产数据隔离
- [ ] 添加硬编码检测工具
- [ ] 更新CI/CD检查
- [ ] 代码审查规范更新

---

## 附录A: 数据库迁移工具硬编码值分析

### A.1 概述

**分析日期**: 2025-09-30
**分析范围**: `center_management/db/migration/`
**分析文件**: `pg_dump_remote.py`, `remote_db_config.py`, `ssh_tunnel.py`

### A.2 已修复问题 ✅

#### A.2.1 硬编码表名回退（优先级：高）

**位置**: `pg_dump_remote.py:911, 952`

**修复前**:
```python
# Line 911
tables_to_delete = tables if tables else ['order', 'test_products', 'order_timeout_tracker']

# Line 952
if tables is None:
    tables = ['order', 'test_products', 'order_timeout_tracker']
```

**修复后**:
```python
# Line 911: 现在会警告用户而不是使用硬编码回退
if tables:
    tables_to_delete = tables
else:
    logger.warning("未指定表名，跳过 DELETE 语句生成")
    logger.info("建议使用 --all-schemas 或明确指定 --tables 参数")
    tables_to_delete = []

# Line 960: 现在会报错而不是使用硬编码回退
if tables is None:
    logger.error("未指定要清空的表")
    logger.info("请使用 --tables 参数明确指定表名")
    return False
```

**修复原因**: 工具已有动态表发现功能（`_get_business_tables()`），不需要硬编码回退

### A.3 高优先级改进项（需要立即修复）

#### A.3.1 迁移文件列表硬编码

**位置**: `pg_dump_remote.py:489-492`
**问题**: 每次添加新迁移文件都需要修改代码

**当前代码**:
```python
if migration_files is None:
    migration_files = [
        'order_refactored.sql',
        'product_refactored.sql'
    ]
```

**当前已修改为**:
```python
# 使用本地 sql_schema_migration/ 目录
migrations_dir = Path(__file__).parent / 'sql_schema_migration'
```

**进一步优化建议**:
```python
# 自动发现 sql_schema_migration/ 目录下的所有 .sql 文件
if migration_files is None:
    migrations_dir = Path(__file__).parent / 'sql_schema_migration'
    migration_files = sorted([f.name for f in migrations_dir.glob('*.sql')])
    logger.info(f"自动发现 {len(migration_files)} 个迁移文件")
```

#### A.3.2 删除函数列表硬编码

**位置**: `pg_dump_remote.py:541-553`
**问题**: 每次添加新函数都需要更新此列表（11个函数名）

**建议方案**: 实现动态SQL查询
```python
def _get_functions_to_drop(self, target_type='local', schema='test'):
    """动态查询schema中的所有自定义函数"""
    sql_query = """
    SELECT routine_name || '(' ||
           string_agg(parameter_mode || ' ' || data_type, ', ') || ')'
    FROM information_schema.routines r
    LEFT JOIN information_schema.parameters p ON r.specific_name = p.specific_name
    WHERE r.routine_schema = %s AND r.routine_type = 'FUNCTION'
    GROUP BY routine_name, specific_name;
    """
```

### A.4 中优先级改进项

#### A.4.1 默认IP地址

**位置**: `remote_db_config.py:179`
**当前**: `remote_db_ip = os.getenv('remote_db_ip', '8.134.74.41')`
**问题**: 硬编码了生产IP作为默认值
**建议**: 移除默认值，要求必须配置

#### A.4.2 Schema名称硬编码

**位置**: `pg_dump_remote.py:516-520`
**当前**: 在授权SQL中硬编码 'test' schema
**问题**: 方法已有schema参数但未使用
**建议**: 使用参数化变量 `f"GRANT ... ON SCHEMA {schema} TO postgres;"`

#### A.4.3 系统Schema列表

**位置**: `pg_dump_remote.py:680-685, 860-865`（两处定义不一致）
**建议**: 提取为类常量
```python
class PgDumpTool:
    SYSTEM_SCHEMAS = frozenset([
        '_realtime', 'extensions', 'graphql_public',
        'pgsodium', 'pgsodium_masks', 'realtime',
        'supabase_functions', 'vault', 'net',
        'pg_catalog', 'information_schema', 'pg_toast',
        'cron', 'pg_temp'
    ])
```

#### A.4.4 内部跟踪表列表

**位置**: `pg_dump_remote.py:688-695, 871-876`（两处定义不一致）
**建议**: 提取为类常量
```python
class PgDumpTool:
    INTERNAL_TRACKING_TABLES = frozenset([
        'auth.schema_migrations',
        'storage.migrations',
        'supabase_migrations.schema_migrations',
        'public.schema_config',
        'realtime.schema_migrations',
        'realtime.subscription',
    ])
```

#### A.4.5 管理员用户名

**位置**: `pg_dump_remote.py` (4处: lines 528, 648, 718, 783)
**当前**: `'--username', 'supabase_admin'`
**评估**: supabase_admin 是系统标准用户
**建议**: 提取为类常量便于未来自定义

### A.5 低优先级（可接受）

以下硬编码值被评估为合理的默认配置，可保持现状：

- SSH默认端口 22 (`ssh_tunnel.py`)
- PostgreSQL默认端口 5438, 5439 (`remote_db_config.py`, `ssh_tunnel.py`)
- PostgreSQL默认数据库名 'postgres' (`remote_db_config.py`)
- PostgreSQL默认用户名 'postgres' (`remote_db_config.py`)

这些都是行业标准值，且已支持环境变量覆盖。

### A.6 实施建议

**Phase 1 (本周)**:
1. 实现迁移文件自动发现功能
2. 实现函数列表动态查询功能
3. 测试验证

**Phase 2 (本月)**:
3. 提取系统常量（schemas, tables）
4. 参数化schema名称
5. 统一两处不同的定义

**Phase 3 (下月)**:
6. 配置文件支持（可选）
7. 文档更新

### A.7 风险评估

- **高风险变更**: 无
- **中等风险**: 动态函数发现（需充分测试）
- **低风险**: 提取常量（纯重构）

### A.8 测试建议

```bash
# 测试动态表发现
uv run python center_management/db/migration/pg_dump_remote.py \
  --data-only-sync --source remote --target local --all-schemas

# 测试迁移文件自动发现
uv run python center_management/db/migration/pg_dump_remote.py \
  --schema-init --target local

# 验证数据完整性
psql "postgresql://postgres:PASSWORD@localhost:5438/postgres" \
  -c "SELECT COUNT(*) FROM auth.users;"
```

---

*报告生成时间: 2025年9月29日（更新: 2025年9月30日）*
*扫描范围: /root/self_code/web_backend/*
*下次审查建议: 3个月后*