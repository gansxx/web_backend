# 数据库模块目录结构

## 概述

此目录包含数据库操作相关的所有代码、测试和文档。

## 目录结构

```
center_management/db/
├── README.md                 # 本文件，目录结构说明
├── base_config.py           # 共享的数据库配置基类
├── order.py                 # 订单管理类
├── product.py              # 产品管理类  
├── test_go_db.py           # 主要测试文件（保持在根目录）
├── docs/                   # 文档文件夹
│   ├── AUTO_EXECUTION_GUIDE.md      # 自动执行设置指南
│   ├── ORDER_TIMEOUT_DOCS.md        # 订单超时功能文档
│   ├── REFACTOR_SUMMARY.md          # 重构总结文档
│   └── setup_pg_cron.sql            # pg_cron设置脚本
├── test_scripts/           # 测试脚本文件夹
│   ├── test_auto_timeout.py         # 自动超时功能测试
│   ├── test_order_timeout.py        # 订单超时管理测试
│   ├── test_refactored_code.py      # 重构代码验证测试
│   └── test_refactored_order.py     # 重构订单功能测试
└── tests/                  # 原有的测试目录
```

## 核心模块

### base_config.py
- **功能**: 数据库连接的基础配置类
- **包含**: `BaseConfig` 类，提供统一的 Supabase 连接管理

### order.py  
- **功能**: 订单管理功能
- **包含**: `OrderConfig` 类
- **主要方法**:
  - `insert_order()` - 插入订单（包含自动超时跟踪）
  - `update_order_status()` - 更新订单状态
  - `fetch_order_user()` - 获取用户订单
  - `check_timeout_orders()` - 检查超时订单
  - `process_order_timeouts()` - 手动执行超时检查
  - `check_cron_job_status()` - 检查定时任务状态

### product.py
- **功能**: 产品管理功能  
- **包含**: `ProductConfig` 类
- **主要方法**:
  - `insert_data()` - 插入产品数据（通过RPC）
  - `fetch_data_user()` - 获取用户产品数据

## 使用方法

### 基本使用

```python
# 导入模块
from order import OrderConfig
from product import ProductConfig

# 创建实例
order_config = OrderConfig()
product_config = ProductConfig()

# 使用功能
order_id = order_config.insert_order("产品名", 123, 100, "user@email.com", "phone")
```

### 运行测试

```bash
# 主要测试（在根目录运行）
cd /root/supabase_backend/center_management/db
python test_go_db.py

# 其他测试（在test_scripts目录运行）
cd test_scripts
python test_auto_timeout.py
python test_order_timeout.py  
python test_refactored_code.py
python test_refactored_order.py
```

## 文档

所有相关文档都位于 `docs/` 文件夹中：

- **AUTO_EXECUTION_GUIDE.md**: 如何设置订单超时的自动检查功能
- **ORDER_TIMEOUT_DOCS.md**: 订单超时管理功能的详细说明
- **REFACTOR_SUMMARY.md**: 代码重构的总结和变更说明
- **setup_pg_cron.sql**: PostgreSQL pg_cron扩展的设置脚本

## 测试脚本

所有测试脚本都位于 `test_scripts/` 文件夹中：

- **test_auto_timeout.py**: 测试自动超时检查功能
- **test_order_timeout.py**: 测试订单超时管理的完整流程
- **test_refactored_code.py**: 验证代码重构后的基本功能
- **test_refactored_order.py**: 测试重构后的订单功能

## 注意事项

1. **导入路径**: 测试脚本已经更新了导入路径以正确引用父目录中的模块
2. **主测试文件**: `test_go_db.py` 保持在根目录，作为主要的测试入口
3. **模块依赖**: 所有模块都依赖于 `base_config.py` 提供的基础配置
4. **数据库权限**: 确保相关的数据库函数和表已经正确创建并授予了适当权限
5. **自动超时检查**: 定时任务在数据库初始化时自动创建，每5分钟执行一次超时检查

## 开发指南

### 添加新功能
1. 在相应的配置类中添加新方法
2. 确保继承自 `BaseConfig` 
3. 添加相应的测试脚本到 `test_scripts/`
4. 更新文档

### 运行完整测试
```bash
# 在根目录运行主测试
python test_go_db.py

# 批量运行所有测试脚本
cd test_scripts
for test in test_*.py; do 
    echo "Running $test..."
    python "$test"
    echo "---"
done
```