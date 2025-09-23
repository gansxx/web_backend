# 订单超时自动检查设置指南

## 概述

本指南介绍如何设置 `check_timeout_orders()` 函数的自动执行，确保订单超时检查能够定期自动运行。

## 方案选择

### 1. PostgreSQL pg_cron 扩展 (推荐)

**优点：**
- 在数据库层面运行，性能最佳
- 不依赖外部系统
- 事务安全性好
- 可以通过 SQL 直接管理

**缺点：**
- 需要超级用户权限启用扩展
- 需要重启 PostgreSQL 服务

### 2. 系统级 Cron Job

**优点：**
- 不需要修改数据库配置
- 灵活性高

**缺点：**
- 需要系统级访问权限
- 需要处理数据库连接和认证

### 3. 应用层定时任务

**优点：**
- 完全在应用控制范围内
- 易于调试和监控

**缺点：**
- 应用重启会中断任务
- 需要额外的任务调度框架

## PostgreSQL pg_cron 设置步骤

### 第1步：启用 pg_cron 扩展

#### 1.1 修改 PostgreSQL 配置

编辑 `postgresql.conf` 文件：

```ini
# 添加 pg_cron 到共享预加载库
shared_preload_libraries = 'pg_cron'

# 指定 cron 使用的数据库（通常是 postgres）
cron.database_name = 'postgres'
```

#### 1.2 重启 PostgreSQL 服务

```bash
# Ubuntu/Debian
sudo systemctl restart postgresql

# CentOS/RHEL
sudo systemctl restart postgresql

# Docker
docker-compose restart db
```

#### 1.3 创建扩展

以超级用户身份连接数据库并执行：

```sql
CREATE EXTENSION IF NOT EXISTS pg_cron;
```

### 第2步：设置自动任务

#### 方法A：使用我们提供的管理函数

```python
# Python 代码
from order import OrderConfig

order_config = OrderConfig()
result = order_config.setup_automatic_timeout_check()
print(result)
```

```sql
-- SQL 直接执行
SELECT tests.setup_automatic_timeout_check();
```

#### 方法B：直接使用 pg_cron API

```sql
-- 每分钟执行一次超时检查
SELECT cron.schedule(
    'order-timeout-check',                    -- 任务名称
    '*/1 * * * *',                           -- 每分钟执行
    'SELECT tests.check_timeout_orders();'   -- 执行的命令
);
```

### 第3步：验证设置

#### 3.1 检查任务状态

```python
# Python 代码
jobs = order_config.check_cron_job_status()
for job in jobs:
    print(f"任务ID: {job['jobid']}, 调度: {job['schedule']}, 活跃: {job['active']}")
```

```sql
-- SQL 查询
SELECT * FROM cron.job WHERE jobname = 'order-timeout-check';
```

#### 3.2 查看执行历史

```sql
SELECT 
    jobname,
    start_time,
    end_time,
    return_message,
    status
FROM cron.job_run_details 
WHERE jobname = 'order-timeout-check'
ORDER BY start_time DESC 
LIMIT 10;
```

### 第4步：监控和管理

#### 启动自动检查

```python
order_config.setup_automatic_timeout_check()
```

#### 停止自动检查

```python
order_config.stop_automatic_timeout_check()
```

#### 查看任务状态

```python
order_config.check_cron_job_status()
```

#### 手动执行检查

```python
order_config.process_order_timeouts()
```

## 系统级 Cron Job 设置

如果无法使用 pg_cron，可以设置系统级定时任务：

### 1. 创建执行脚本

```bash
#!/bin/bash
# /path/to/timeout_checker.sh

cd /root/supabase_backend/center_management/db
python3 -c "
from order import OrderConfig
config = OrderConfig()
result = config.process_order_timeouts()
print(f'Processed timeouts: {result}')
"
```

### 2. 设置权限

```bash
chmod +x /path/to/timeout_checker.sh
```

### 3. 添加到 crontab

```bash
# 编辑 crontab
crontab -e

# 添加以下行（每分钟执行一次）
*/1 * * * * /path/to/timeout_checker.sh >> /var/log/timeout_check.log 2>&1
```

## Cron 表达式参考

| 表达式 | 说明 |
|--------|------|
| `*/1 * * * *` | 每分钟 |
| `*/5 * * * *` | 每5分钟 |
| `0 * * * *` | 每小时整点 |
| `0 */6 * * *` | 每6小时 |
| `0 9 * * *` | 每天上午9点 |
| `0 9 * * 1` | 每周一上午9点 |
| `0 0 1 * *` | 每月1日午夜 |

## 监控和故障排除

### 1. 检查任务执行日志

```sql
-- 查看最近的执行记录
SELECT * FROM cron.job_run_details 
WHERE jobname = 'order-timeout-check'
ORDER BY start_time DESC;
```

### 2. 监控超时处理效果

```python
# 查看最近处理的超时订单
orders = order_config.get_orders_with_status('已超时')
print(f"当前超时订单数量: {len(orders)}")
```

### 3. 检查跟踪表状态

```python
# 查看跟踪记录
trackers = order_config.get_timeout_tracker_records()
processed = sum(1 for t in trackers if t['processed'])
total = len(trackers)
print(f"跟踪记录: {processed}/{total} 已处理")
```

### 4. 常见问题解决

#### 问题1：pg_cron 扩展不可用

```
错误: extension "pg_cron" is not available
```

**解决方案：**
1. 确认 pg_cron 已安装
2. 检查 `shared_preload_libraries` 配置
3. 重启 PostgreSQL 服务

#### 问题2：权限不足

```
错误: permission denied for schema cron
```

**解决方案：**
```sql
GRANT USAGE ON SCHEMA cron TO service_role;
GRANT SELECT ON cron.job TO service_role;
```

#### 问题3：任务不执行

**检查步骤：**
1. 确认任务已创建：`SELECT * FROM cron.job;`
2. 检查任务是否活跃：`active = true`
3. 查看执行日志：`SELECT * FROM cron.job_run_details;`
4. 手动测试函数：`SELECT tests.check_timeout_orders();`

## 最佳实践

### 1. 执行频率

- **生产环境：** 推荐每分钟执行一次
- **开发环境：** 可以设置为每5分钟或更长间隔
- **高负载系统：** 考虑每30秒执行一次

### 2. 监控建议

```python
# 定期检查定时任务健康状态
def check_cron_health():
    order_config = OrderConfig()
    
    # 检查任务是否存在
    jobs = order_config.check_cron_job_status()
    if not jobs:
        logger.warning("超时检查定时任务不存在！")
        return False
    
    # 检查最近是否有执行记录
    # 这里可以添加更详细的健康检查逻辑
    
    return True
```

### 3. 错误处理

```sql
-- 创建带错误处理的超时检查函数
CREATE OR REPLACE FUNCTION tests.safe_check_timeout_orders()
RETURNS INTEGER
LANGUAGE plpgsql
AS $$
DECLARE
    result INTEGER;
BEGIN
    BEGIN
        result := tests.check_timeout_orders();
        RETURN result;
    EXCEPTION WHEN OTHERS THEN
        -- 记录错误但不抛出异常，避免中断定时任务
        INSERT INTO tests.error_log (error_time, error_message) 
        VALUES (NOW(), 'Timeout check failed: ' || SQLERRM);
        RETURN 0;
    END;
END;
$$;
```

### 4. 性能优化

```sql
-- 对大量数据的性能优化版本
CREATE OR REPLACE FUNCTION tests.check_timeout_orders_batch(batch_size INTEGER DEFAULT 1000)
RETURNS INTEGER
LANGUAGE plpgsql
AS $$
DECLARE
    timeout_count INTEGER := 0;
    batch_count INTEGER;
BEGIN
    LOOP
        -- 批量处理以避免长时间锁表
        UPDATE tests.order 
        SET status = '已超时'
        WHERE id IN (
            SELECT o.id
            FROM tests.order o
            JOIN tests.order_timeout_tracker ott ON o.id = ott.order_id
            WHERE o.status = '处理中'
              AND ott.check_at <= NOW()
              AND ott.processed = false
            LIMIT batch_size
        );
        
        GET DIAGNOSTICS batch_count = ROW_COUNT;
        timeout_count := timeout_count + batch_count;
        
        -- 标记跟踪记录为已处理
        UPDATE tests.order_timeout_tracker 
        SET processed = true
        WHERE order_id IN (
            SELECT o.id
            FROM tests.order o
            WHERE o.status = '已超时'
              AND EXISTS (
                  SELECT 1 FROM tests.order_timeout_tracker ott2
                  WHERE ott2.order_id = o.id AND ott2.processed = false
              )
        );
        
        EXIT WHEN batch_count = 0;
    END LOOP;
    
    RETURN timeout_count;
END;
$$;
```

## 总结

通过以上设置，`check_timeout_orders()` 函数将自动定期执行，确保订单超时状态得到及时更新。建议在生产环境中使用 PostgreSQL pg_cron 扩展方案，因为它提供了最佳的性能和可靠性。