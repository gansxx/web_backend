# SQL Schema Migration Files

## 文件命名规范

所有迁移文件必须使用数字前缀（两位数），以确保正确的执行顺序。

### 命名格式
```
<序号>_<描述性名称>.sql
```

### 当前迁移文件执行顺序

1. **00_schema_init.sql** - Schema初始化（必须第一个执行）
   - 创建schema配置表
   - 创建`get_schema_name()`辅助函数
   - 安装pg_cron扩展

2. **01_order_refactored.sql** - 订单系统
   - 创建订单表和相关函数
   - 依赖：00_schema_init.sql

3. **02_product_refactored.sql** - 产品系统
   - 创建产品表和相关函数
   - 依赖：00_schema_init.sql

4. **03_auth_user_webhook.sql** - 用户认证Webhook
   - 创建用户相关的webhook处理
   - 依赖：00_schema_init.sql

5. **04_ticket_system.sql** - 工单系统基础
   - 创建工单表和基础函数
   - 依赖：00_schema_init.sql

6. **05_ticket_system_add_reply.sql** - 工单回复功能
   - 扩展工单系统，添加回复功能
   - 依赖：04_ticket_system.sql

7. **06_ticket_auto_resolve_trigger.sql** - 工单自动解决触发器
   - 创建自动解决工单的触发器
   - 依赖：04_ticket_system.sql, 05_ticket_system_add_reply.sql

8. **10_r2_package_system.sql** - R2包管理系统
   - 创建R2包管理的表、函数、RLS策略
   - 依赖：00_schema_init.sql

9. **11_r2_fix_tags_double_serialization.sql** - R2标签双序列化修复
   - 修复tags字段的双序列化问题
   - 依赖：10_r2_package_system.sql

## 添加新迁移文件

### 步骤

1. **确定序号**
   - 如果是独立的新功能，使用下一个可用的十位数（20, 30, 40...）
   - 如果是对现有功能的扩展/修复，使用相关功能的序号+1（如11, 12, 13...）

2. **命名文件**
   ```
   <序号>_<功能描述>.sql
   ```
   例如：
   - `20_payment_system.sql` - 新的支付系统
   - `12_r2_add_analytics.sql` - R2系统的分析功能扩展

3. **文件头部注释**
   每个迁移文件必须包含以下信息：
   ```sql
   -- =====================================================
   -- <功能名称>
   -- =====================================================
   -- Description: <功能描述>
   -- Dependencies: <依赖的迁移文件>
   -- Version: <版本号>
   -- Created: <创建日期>
   -- =====================================================
   ```

4. **使用`get_schema_name()`**
   所有表、函数、触发器的创建都必须使用`get_schema_name()`来获取schema名称：
   ```sql
   DO $$
   DECLARE
       app_schema TEXT := get_schema_name();
   BEGIN
       EXECUTE format('CREATE TABLE IF NOT EXISTS %I.my_table (...)', app_schema);
   END $$;
   ```

## 执行迁移

### 本地数据库
```bash
# 初始化schema + 应用所有迁移
uv run python center_management/db/migration/pg_dump_remote.py \
  --schema-init \
  --target local

# 只初始化schema（不导入数据）
uv run python center_management/db/migration/pg_dump_remote.py \
  --schema-init \
  --target local
```

### 远程数据库
```bash
# 在远程服务器上执行（通过SSH）
ssh user@remote-server "cd /path/to/project && \
  uv run python center_management/db/migration/pg_dump_remote.py \
    --schema-init \
    --target local"
```

### 单个迁移文件
```bash
source .env
psql "postgresql://postgres:$POSTGRES_PASSWORD@localhost:5438/postgres" \
  -v ON_ERROR_STOP=1 \
  -f center_management/db/migration/sql_schema_migration/<文件名>.sql
```

## 重要提醒

1. **执行顺序**：迁移文件按照文件名的字母顺序执行，因此数字前缀至关重要
2. **依赖关系**：新迁移文件必须明确声明依赖关系，确保序号大于依赖文件
3. **测试环境**：新迁移文件必须先在测试环境验证，再应用到生产环境
4. **版本控制**：所有迁移文件必须提交到Git，不允许直接修改数据库
5. **幂等性**：迁移文件应该是幂等的，可以安全地多次执行
6. **回滚计划**：重要的结构变更应该准备回滚脚本

## 序号分配规则

- **00-09**: 核心基础设施（schema初始化等）
- **10-19**: R2包管理系统相关
- **20-29**: 预留（支付系统、通知系统等）
- **30-39**: 预留
- **40-49**: 预留
- ...

根据功能模块分配序号段，便于日后维护和扩展。
