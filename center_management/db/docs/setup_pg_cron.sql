-- PostgreSQL 自动执行设置脚本
-- 此脚本用于启用 pg_cron 扩展并设置自动超时检查

-- ==========================================
-- 第一步：启用 pg_cron 扩展（需要超级用户权限）
-- ==========================================

-- 在 PostgreSQL 配置文件 postgresql.conf 中添加：
-- shared_preload_libraries = 'pg_cron'
-- cron.database_name = 'postgres'  -- 或者您的数据库名称

-- 重启 PostgreSQL 服务后执行以下命令：
CREATE EXTENSION IF NOT EXISTS pg_cron;

-- ==========================================
-- 第二步：设置自动超时检查任务
-- ==========================================

-- 方法1：直接通过 SQL 设置定时任务
SELECT cron.schedule(
    'order-timeout-check',                    -- 任务名称
    '*/1 * * * *',                           -- cron 表达式：每分钟执行一次
    'SELECT tests.check_timeout_orders();'   -- 要执行的SQL命令
);

-- 方法2：使用我们创建的管理函数
-- SELECT tests.setup_automatic_timeout_check();

-- ==========================================
-- 第三步：验证和管理定时任务
-- ==========================================

-- 查看所有定时任务
SELECT * FROM cron.job;

-- 查看定时任务执行历史
SELECT * FROM cron.job_run_details 
WHERE jobname = 'order-timeout-check' 
ORDER BY start_time DESC 
LIMIT 10;

-- 停止特定定时任务
-- SELECT cron.unschedule('order-timeout-check');

-- ==========================================
-- 第四步：监控和日志
-- ==========================================

-- 创建日志表用于记录自动检查结果（可选）
CREATE TABLE IF NOT EXISTS tests.timeout_check_log (
    id SERIAL PRIMARY KEY,
    check_time TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    processed_count INTEGER,
    status TEXT
);

-- 创建带日志记录的超时检查函数
CREATE OR REPLACE FUNCTION tests.check_timeout_orders_with_log()
RETURNS INTEGER
LANGUAGE plpgsql
AS $$
DECLARE
    timeout_count INTEGER;
BEGIN
    -- 执行超时检查
    timeout_count := tests.check_timeout_orders();
    
    -- 记录到日志表
    INSERT INTO tests.timeout_check_log (processed_count, status)
    VALUES (timeout_count, 'success');
    
    RETURN timeout_count;
EXCEPTION WHEN OTHERS THEN
    -- 记录错误
    INSERT INTO tests.timeout_check_log (processed_count, status)
    VALUES (0, 'error: ' || SQLERRM);
    
    RAISE;
END;
$$;

-- 如果需要带日志的定时任务，可以更新任务：
-- SELECT cron.unschedule('order-timeout-check');
-- SELECT cron.schedule(
--     'order-timeout-check-with-log',
--     '*/1 * * * *',
--     'SELECT tests.check_timeout_orders_with_log();'
-- );

-- ==========================================
-- 常用的 Cron 表达式示例
-- ==========================================

-- '*/1 * * * *'    -- 每分钟
-- '*/5 * * * *'    -- 每5分钟  
-- '0 * * * *'      -- 每小时的整点
-- '0 */6 * * *'    -- 每6小时
-- '0 9 * * *'      -- 每天上午9点
-- '0 9 * * 1'      -- 每周一上午9点
-- '0 0 1 * *'      -- 每月1日午夜

-- ==========================================
-- 权限设置
-- ==========================================

-- 授予必要的权限
GRANT SELECT ON cron.job TO service_role;
GRANT SELECT ON cron.job_run_details TO service_role;

-- 如果使用日志表
GRANT SELECT, INSERT ON tests.timeout_check_log TO service_role;
GRANT USAGE ON SEQUENCE tests.timeout_check_log_id_seq TO service_role;