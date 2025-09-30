# 自动迁移文件发现功能

## 概述

`pg_dump_remote.py` 的 `apply_migrations()` 函数现在支持**自动发现**迁移文件。

## 工作原理

### 自动发现模式（默认）

当不指定 `migration_files` 参数时，系统会：

1. 扫描 `sql_schema_migration/` 目录
2. 查找所有 `.sql` 文件
3. **按字母顺序排序**（确保执行顺序一致）
4. 排除特定模式的文件：
   - 包含 `backup` 的文件
   - 包含 `test` 的文件
   - 包含 `temp` 的文件
   - 包含 `old` 的文件
5. 自动应用所有符合条件的迁移文件

### 示例输出

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

## 使用方法

### 方式 1: 自动发现（推荐）

```bash
# 自动应用所有迁移文件
uv run pg_dump_remote.py --schema-init --target local
```

### 方式 2: 手动指定

如果需要只执行特定的迁移文件：

```python
tool = PgDumpRemoteTool()
tool.apply_migrations(
    target_type='local',
    migration_files=['order_refactored.sql', 'ticket_system.sql']
)
```

## 文件命名建议

为了确保正确的执行顺序，建议使用以下命名模式：

### ✅ 推荐命名

```
01_order_refactored.sql
02_product_refactored.sql
03_ticket_system.sql
04_user_management.sql
```

或使用描述性名称（按字母顺序）：

```
order_refactored.sql
product_refactored.sql
ticket_system.sql
user_management.sql
```

### ❌ 避免的命名模式

```
backup_order.sql          # 包含 'backup'，会被排除
test_migration.sql        # 包含 'test'，会被排除
temp_schema.sql           # 包含 'temp'，会被排除
old_product_schema.sql    # 包含 'old'，会被排除
```

## 添加新迁移文件

1. 在 `sql_schema_migration/` 目录创建新的 `.sql` 文件
2. 文件名避免使用 `backup`、`test`、`temp`、`old` 关键词
3. 运行迁移命令，新文件会自动被发现和执行

**无需修改代码！**

## 迁移执行顺序

- 文件按**字母顺序**排序后执行
- 如果需要特定顺序，使用数字前缀（如 `01_`, `02_`）
- 同一目录中的所有迁移文件都会被执行

## 排除文件的方法

如果有临时的 SQL 文件不想被执行，可以：

1. **添加关键词**: 在文件名中加入 `backup`、`test`、`temp` 或 `old`
   - 例如: `test_ticket_system.sql`
2. **移出目录**: 将文件移到其他目录
3. **改扩展名**: 改为 `.sql.bak` 或 `.txt`

## 验证迁移文件

在执行前查看会应用哪些文件：

```python
from pathlib import Path

migrations_dir = Path('sql_schema_migration')
all_sql_files = sorted(migrations_dir.glob('*.sql'))

for sql_file in all_sql_files:
    filename = sql_file.name
    excluded = any(exclude in filename.lower() for exclude in ['backup', 'test', 'temp', 'old'])
    if not excluded:
        print(f'✅ {filename}')
    else:
        print(f'❌ {filename} (excluded)')
```

## 优势

### 🎯 灵活性
- 添加新迁移文件无需修改代码
- 自动发现减少人为错误

### 🔄 一致性
- 按字母顺序执行确保可预测性
- 所有环境使用相同的自动发现逻辑

### 🛡️ 安全性
- 自动排除测试和备份文件
- 避免意外执行临时文件

### 🚀 便捷性
- 一个命令执行所有迁移
- 无需维护硬编码列表

## 示例场景

### 场景 1: 添加新的迁移文件

```bash
# 1. 创建新迁移文件
cat > sql_schema_migration/payment_system.sql << 'EOF'
-- 支付系统迁移
CREATE TABLE test.payment (...);
EOF

# 2. 运行迁移（自动包含新文件）
uv run pg_dump_remote.py --schema-init --target local
```

输出将自动包含新文件：
```
INFO - 自动发现 4 个迁移文件: order_refactored.sql, payment_system.sql, product_refactored.sql, ticket_system.sql
```

### 场景 2: 临时排除某个文件

```bash
# 重命名文件添加 'test' 前缀
mv sql_schema_migration/payment_system.sql \
   sql_schema_migration/test_payment_system.sql

# 运行迁移（自动排除）
uv run pg_dump_remote.py --schema-init --target local
```

输出将不包含该文件：
```
INFO - 自动发现 3 个迁移文件: order_refactored.sql, product_refactored.sql, ticket_system.sql
```

## 故障排查

### 问题: "未找到任何迁移文件"

**原因**: `sql_schema_migration/` 目录为空或所有文件都被排除

**解决**:
```bash
# 检查目录
ls -la sql_schema_migration/

# 确保有 .sql 文件且不包含排除关键词
```

### 问题: 迁移文件执行顺序错误

**原因**: 文件名按字母顺序排序

**解决**: 使用数字前缀控制顺序
```bash
mv order_refactored.sql 01_order_refactored.sql
mv product_refactored.sql 02_product_refactored.sql
mv ticket_system.sql 03_ticket_system.sql
```

### 问题: 不想执行的文件被执行了

**原因**: 文件名不包含排除关键词

**解决**: 重命名或移动文件
```bash
# 方案 1: 添加 test 前缀
mv unwanted.sql test_unwanted.sql

# 方案 2: 改扩展名
mv unwanted.sql unwanted.sql.bak

# 方案 3: 移出目录
mv unwanted.sql ../backup/
```

## 向后兼容性

✅ **完全兼容**

旧的代码仍然可以工作：
```python
# 手动指定文件列表仍然有效
tool.apply_migrations(
    migration_files=['order_refactored.sql', 'product_refactored.sql']
)
```

## 更新日志

**2025-09-30**
- ✨ 实现自动迁移文件发现功能
- 🔍 支持自动扫描 `sql_schema_migration/` 目录
- 🎯 智能排除测试、备份等临时文件
- 📊 添加详细的发现日志输出
- 🔄 按字母顺序排序确保执行顺序一致