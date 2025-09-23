# 订单超时管理功能文档

## 概述

为订单系统添加了自动超时管理功能，当订单在10分钟内未被处理时，系统会自动将其状态更新为"已超时"。

## 新增的数据库结构

### 1. 超时跟踪表 (order_timeout_tracker)

```sql
create table tests.order_timeout_tracker (
  id uuid not null default gen_random_uuid(),
  order_id uuid not null references tests.order(id) on delete cascade,
  created_at timestamp with time zone not null default now(),
  check_at timestamp with time zone not null,
  processed boolean not null default false,
  constraint order_timeout_tracker_pkey primary key (id),
  constraint order_timeout_tracker_order_id_unique unique (order_id)
);
```

**字段说明：**
- `id`: 跟踪记录的唯一标识
- `order_id`: 关联的订单ID
- `created_at`: 跟踪记录创建时间
- `check_at`: 预定的超时检查时间（订单创建时间 + 10分钟）
- `processed`: 是否已处理该跟踪记录

### 2. 索引

```sql
create index idx_order_timeout_check_at on tests.order_timeout_tracker (check_at, processed);
create index idx_order_timeout_order_id on tests.order_timeout_tracker (order_id);
```

## 新增的函数

### 1. `insert_order_with_timeout()` - 带超时跟踪的订单插入

```sql
insert_order_with_timeout(
  p_product_name text,
  p_trade_num int4,
  p_amount int4,
  p_email text,
  p_phone text
) returns uuid
```

**功能：**
- 创建新订单
- 自动在超时跟踪表中创建记录，设置10分钟后的检查时间
- 使用事务确保数据一致性
- 返回新创建的订单UUID

**使用示例：**
```python
params = {
    "p_product_name": "VPN套餐",
    "p_trade_num": 12345,
    "p_amount": 100,
    "p_email": "user@example.com",
    "p_phone": "1234567890"
}
response = supabase.rpc("insert_order_with_timeout", params).execute()
order_id = response.data
```

### 2. `check_timeout_orders()` - 检查并处理超时订单

```sql
check_timeout_orders() returns int
```

**功能：**
- 查找所有到达检查时间且未处理的跟踪记录
- 检查对应订单的状态
- 如果状态仍为"处理中"，则更新为"已超时"
- 标记跟踪记录为已处理
- 返回处理的超时订单数量

**使用示例：**
```python
response = supabase.rpc("check_timeout_orders").execute()
timeout_count = response.data
print(f"处理了 {timeout_count} 个超时订单")
```

### 3. `process_order_timeouts()` - 批量处理超时订单

```sql
process_order_timeouts() returns json
```

**功能：**
- 调用 `check_timeout_orders()` 函数
- 返回包含处理结果的JSON对象

**返回格式：**
```json
{
  "processed_count": 5,
  "timestamp": "2025-09-22T10:30:00Z",
  "message": "已处理 5 个超时订单"
}
```

**使用示例：**
```python
response = supabase.rpc("process_order_timeouts").execute()
result = response.data
print(result["message"])
```

### 4. `cleanup_processed_timeout_trackers()` - 清理已处理的跟踪记录

```sql
cleanup_processed_timeout_trackers(p_days_old int default 7) returns int
```

**功能：**
- 删除指定天数前的已处理跟踪记录
- 默认清理7天前的记录
- 返回删除的记录数量

**使用示例：**
```python
# 清理3天前的记录
params = {"p_days_old": 3}
response = supabase.rpc("cleanup_processed_timeout_trackers", params).execute()
deleted_count = response.data
print(f"清理了 {deleted_count} 个记录")
```

## 工作流程

1. **创建订单**：调用 `insert_order_with_timeout()` 创建订单和超时跟踪记录
2. **自动检查**：系统定期调用 `check_timeout_orders()` 检查超时订单
3. **状态更新**：如果订单超时且状态仍为"处理中"，自动更新为"已超时"
4. **维护清理**：定期调用 `cleanup_processed_timeout_trackers()` 清理旧记录

## 权限设置

已为 `service_role` 授予所有相关表和函数的必要权限：

```sql
-- 表权限
GRANT SELECT, INSERT, UPDATE, DELETE ON tests.order_timeout_tracker TO service_role;

-- 函数权限
GRANT EXECUTE ON FUNCTION insert_order_with_timeout(text, int4, int4, text, text) TO service_role;
GRANT EXECUTE ON FUNCTION check_timeout_orders() TO service_role;
GRANT EXECUTE ON FUNCTION process_order_timeouts() TO service_role;
GRANT EXECUTE ON FUNCTION cleanup_processed_timeout_trackers(int) TO service_role;
```

## Python 集成

更新 `OrderConfig` 类以支持新功能：

```python
class OrderConfig(BaseConfig):
    def insert_order_with_timeout(self, product_name: str, trade_num: int, amount: int, email: str, phone: str):
        """插入带超时跟踪的订单"""
        params = {
            "p_product_name": product_name,
            "p_trade_num": trade_num,
            "p_amount": amount,
            "p_email": email,
            "p_phone": phone
        }
        response = self.supabase.rpc("insert_order_with_timeout", params).execute()
        return response.data
    
    def check_timeout_orders(self):
        """检查并处理超时订单"""
        response = self.supabase.rpc("check_timeout_orders").execute()
        return response.data
    
    def process_order_timeouts(self):
        """批量处理超时订单"""
        response = self.supabase.rpc("process_order_timeouts").execute()
        return response.data
```

## 定时任务建议

建议设置定时任务（如 cron job 或定时器）定期执行超时检查：

```bash
# 每分钟检查一次超时订单
* * * * * /path/to/your/timeout_checker.py

# 每天清理一次已处理的跟踪记录
0 2 * * * /path/to/your/cleanup_script.py
```

## 测试

使用提供的测试脚本验证功能：

```bash
cd /root/supabase_backend/center_management/db
python test_order_timeout.py
```

## 注意事项

1. **性能考虑**：大量订单时，建议批量处理超时检查
2. **索引优化**：已创建必要索引以提高查询性能
3. **数据清理**：定期清理已处理的跟踪记录以保持表的性能
4. **监控**：建议监控超时订单的数量和处理情况
5. **时区处理**：所有时间戳都使用 `timestamp with time zone` 类型确保时区一致性