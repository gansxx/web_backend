-- =====================================================
-- 订单管理脚本
-- =====================================================
-- 功能：创建订单相关表和自动超时处理逻辑
-- 使用方法: psql -v ON_ERROR_STOP=1 -f order_refactored.sql
-- =====================================================
-- 前置依赖：
--   必须先执行 00_schema_init.sql 初始化 schema 配置
--   该脚本依赖 get_schema_name() 函数获取 schema 名称
-- =====================================================

-- 1. 创建 order 表
DO $$
DECLARE
    app_schema TEXT := get_schema_name();
BEGIN
    EXECUTE format('
        CREATE TABLE IF NOT EXISTS %I.order (
            id uuid not null default gen_random_uuid (),
            created_at timestamp with time zone not null default now(),
            trade_num integer null,
            product_name text null,
            amount integer null,
            status text null default ''处理中'',
            email text null,
            phone text null,
            constraint order_pkey primary key (id)
        ) TABLESPACE pg_default',
        app_schema
    );
END $$;

-- 2. 创建 order_timeout_tracker 表
DO $$
DECLARE
    app_schema TEXT := get_schema_name();
BEGIN
    EXECUTE format('
        CREATE TABLE IF NOT EXISTS %I.order_timeout_tracker (
            id uuid not null default gen_random_uuid (),
            order_id uuid not null references %I.order(id) on delete cascade,
            check_at timestamp with time zone not null,
            processed boolean default false,
            processed_at timestamp with time zone,
            created_at timestamp with time zone default now(),
            constraint order_timeout_tracker_pkey primary key (order_id)
        )',
        app_schema, app_schema
    );
END $$;

-- 3. 创建订单相关函数
-- 订单查询函数
CREATE OR REPLACE FUNCTION fetch_user_orders(
    p_user_email text default null,
    p_phone text default null
)
RETURNS TABLE (
    product_name text,
    trade_num int4,
    amount int4,
    email text,
    phone text,
    created_at  timestamptz,
    status text
)
LANGUAGE plpgsql
STABLE
AS $$
DECLARE
    app_schema TEXT := get_schema_name();
BEGIN
    IF p_user_email IS NOT NULL AND p_user_email <> '' THEN
        RETURN QUERY EXECUTE format('
            SELECT sp.product_name, sp.trade_num::int4, sp.amount, sp.email, sp.phone, sp.created_at, sp.status
            FROM %I.order sp
            WHERE sp.email = %L',
            app_schema, p_user_email
        );
        RETURN;
    END IF;

    IF p_phone IS NOT NULL AND p_phone <> '' THEN
        RETURN QUERY EXECUTE format('
            SELECT sp.product_name, sp.subscription_url::text, sp.email, sp.phone, sp.created_at, sp.end_time
            FROM %I.test_products sp
            WHERE sp.phone = %L',
            app_schema, p_phone
        );
        RETURN;
    END IF;

    RETURN;
END;
$$;

-- 插入订单函数
CREATE OR REPLACE FUNCTION insert_order(
    p_product_name text,
    p_trade_num int4,
    p_amount int4,
    p_email text,
    p_phone text
)
RETURNS uuid
LANGUAGE plpgsql
AS $$
DECLARE
    new_id uuid;
    check_time timestamp with time zone;
    app_schema TEXT := get_schema_name();
BEGIN
    -- 插入订单
    EXECUTE format('
        INSERT INTO %I.order (product_name, trade_num, amount, email, phone)
        VALUES (%L, %L, %L, %L, %L)
        RETURNING id',
        app_schema, p_product_name, p_trade_num, p_amount, p_email, p_phone
    ) INTO new_id;

    -- 计算10分钟后的检查时间
    check_time := now() + interval '10 minutes';

    -- 插入超时跟踪记录
    EXECUTE format('
        INSERT INTO %I.order_timeout_tracker (order_id, check_at)
        VALUES (%L, %L)',
        app_schema, new_id, check_time
    );

    RETURN new_id;
END;
$$;

-- 更新订单状态函数
CREATE OR REPLACE FUNCTION update_order_status(
    p_id uuid,
    p_status text
)
RETURNS boolean
LANGUAGE plpgsql
AS $$
DECLARE
    rows_affected integer;
    app_schema TEXT := get_schema_name();
BEGIN
    EXECUTE format('
        UPDATE %I.order
        SET status = %L
        WHERE id = %L',
        app_schema, p_status, p_id
    );

    GET DIAGNOSTICS rows_affected = ROW_COUNT;
    RETURN rows_affected > 0;
END;
$$;

-- 订单超时检查函数
CREATE OR REPLACE FUNCTION check_and_expire_orders()
RETURNS integer
LANGUAGE plpgsql
AS $$
DECLARE
    expired_count integer := 0;
    expired_order RECORD;
    app_schema TEXT := get_schema_name();
BEGIN
    -- 查找过期订单
    FOR expired_order IN
        EXECUTE format('
            SELECT order_id
            FROM %I.order_timeout_tracker
            WHERE check_at <= now()
            AND processed = false',
            app_schema
        )
    LOOP
        -- 更新订单状态为过期
        EXECUTE format('
            UPDATE %I.order
            SET status = %L
            WHERE id = %L',
            app_schema, '已过期', expired_order.order_id
        );

        -- 标记为已处理
        EXECUTE format('
            UPDATE %I.order_timeout_tracker
            SET processed = true, processed_at = now()
            WHERE order_id = %L',
            app_schema, expired_order.order_id
        );

        expired_count := expired_count + 1;
    END LOOP;

    RETURN expired_count;
END;
$$;

-- 创建订单超时检查的定时任务
CREATE OR REPLACE FUNCTION create_order_timeout_cron_job()
RETURNS boolean
LANGUAGE plpgsql
AS $$
BEGIN
    -- 删除已存在的任务（如果存在）
    DELETE FROM cron.job WHERE jobname = 'check_expired_orders';

    -- 创建新的定时任务：每5分钟检查一次
    INSERT INTO cron.job (jobname, schedule, command, nodename, nodeport, database, username, active)
    VALUES (
        'check_expired_orders',
        '*/5 * * * *',
        'SELECT check_and_expire_orders();',
        current_setting('cron.host', true),
        current_setting('cron.port', true)::integer,
        current_database(),
        current_user,
        true
    );

    RETURN true;
END;
$$;

-- 4. 设置权限
DO $$
DECLARE
    app_schema TEXT := get_schema_name();
BEGIN
    EXECUTE format('GRANT USAGE ON SCHEMA %I TO service_role', app_schema);
    EXECUTE format('GRANT SELECT ON %I.order TO service_role', app_schema);
    EXECUTE format('GRANT INSERT ON %I.order TO service_role', app_schema);
    EXECUTE format('GRANT UPDATE ON %I.order TO service_role', app_schema);
    EXECUTE format('GRANT SELECT ON %I.order_timeout_tracker TO service_role', app_schema);
    EXECUTE format('GRANT INSERT ON %I.order_timeout_tracker TO service_role', app_schema);
    EXECUTE format('GRANT UPDATE ON %I.order_timeout_tracker TO service_role', app_schema);
END $$;

GRANT EXECUTE ON FUNCTION fetch_user_orders(text, text) TO service_role;
GRANT EXECUTE ON FUNCTION insert_order(text, int4, int4, text, text) TO service_role;
GRANT EXECUTE ON FUNCTION update_order_status(uuid, text) TO service_role;
GRANT EXECUTE ON FUNCTION check_and_expire_orders() TO service_role;
GRANT EXECUTE ON FUNCTION create_order_timeout_cron_job() TO service_role;
GRANT EXECUTE ON FUNCTION get_schema_name() TO service_role;

-- 5. 完成提示
DO $$
DECLARE
    app_schema TEXT := get_schema_name();
BEGIN
    RAISE NOTICE 'Order migration completed successfully for schema: %', app_schema;
    RAISE NOTICE 'Schema name is controlled by the configuration table at the top of this file';
END $$;