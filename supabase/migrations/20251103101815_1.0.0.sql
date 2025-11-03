-- Merged on 2025-11-03 10:18:15

-- ===== /root/self_code/web_backend/center_management/db/migration/sql_schema_migration/20251017210439_schema_init.sql =====
-- =====================================================
-- Schema 初始化脚本
-- =====================================================
-- 功能：创建和配置业务逻辑 schema，为所有业务表提供统一的命名空间
-- 创建日期：2025-10-02
-- 执行顺序：必须在所有其他迁移脚本之前执行
-- 使用方法：psql -v ON_ERROR_STOP=1 -f 00_schema_init.sql
-- =====================================================

-- =====================================================
-- 配置说明
-- =====================================================
-- 修改第23行的 'tests' 值可以控制整个项目使用的 schema 名称
-- 支持的 schema 名称：
--   - 'tests': 测试环境
--   - 'production': 生产环境
--   - 自定义名称
-- =====================================================

-- 1. 创建 schema 配置表（存储当前使用的 schema 名称）
CREATE TABLE IF NOT EXISTS schema_config (
    schema_name TEXT PRIMARY KEY,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- 2. 创建并配置业务 schema
DO $$
DECLARE
    app_schema TEXT := 'products';  -- 在此处修改 schema 名称
BEGIN
    -- 创建 schema（如果不存在）
    IF NOT EXISTS (SELECT 1 FROM information_schema.schemata WHERE schema_name = app_schema) THEN
        EXECUTE format('CREATE SCHEMA %I', app_schema);
        RAISE NOTICE 'Created schema: %', app_schema;
    ELSE
        RAISE NOTICE 'Schema already exists: %', app_schema;
    END IF;

    -- 将当前 schema 名称保存到配置表
    INSERT INTO schema_config (schema_name) VALUES (app_schema)
    ON CONFLICT (schema_name) DO UPDATE SET created_at = NOW();

    RAISE NOTICE 'Schema configuration updated: %', app_schema;
END $$;

-- 3. 确保 pg_cron 扩展存在（用于定时任务，如订单超时检查）
CREATE EXTENSION IF NOT EXISTS pg_cron;

-- 4. 创建获取 schema 名称的辅助函数
-- 所有业务逻辑脚本通过此函数获取当前 schema 名称
CREATE OR REPLACE FUNCTION get_schema_name()
RETURNS TEXT AS $$
DECLARE
    result_schema TEXT;
BEGIN
    -- 从配置表中获取最新的 schema 名称
    SELECT schema_name INTO result_schema
    FROM schema_config
    ORDER BY created_at DESC
    LIMIT 1;

    -- 如果没有找到配置，报错提示
    IF result_schema IS NULL THEN
        RAISE EXCEPTION 'Schema configuration not found. Please run 00_schema_init.sql first.';
    END IF;

    RETURN result_schema;
END;
$$ LANGUAGE plpgsql STABLE;

-- 5. 授予必要的权限
GRANT EXECUTE ON FUNCTION get_schema_name() TO service_role;

-- 6. 验证配置
DO $$
DECLARE
    current_schema TEXT := get_schema_name();
BEGIN
    RAISE NOTICE '====================================================';
    RAISE NOTICE 'Schema initialization completed successfully';
    RAISE NOTICE 'Current schema: %', current_schema;
    RAISE NOTICE 'Schema config table: public.schema_config';
    RAISE NOTICE 'Helper function: public.get_schema_name()';
    RAISE NOTICE 'pg_cron extension: installed';
    RAISE NOTICE '====================================================';
    RAISE NOTICE 'Next steps:';
    RAISE NOTICE '  1. Run order_refactored.sql';
    RAISE NOTICE '  2. Run product_refactored.sql';
    RAISE NOTICE '  3. Run ticket_system.sql';
    RAISE NOTICE '  4. Run other migration scripts as needed';
    RAISE NOTICE '====================================================';
END $$;

-- ===== /root/self_code/web_backend/center_management/db/migration/sql_schema_migration/20251017210440_order_refactored.sql =====
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
-- ===== /root/self_code/web_backend/center_management/db/migration/sql_schema_migration/20251017210441_product_refactored.sql =====
-- =====================================================
-- 产品管理脚本
-- =====================================================
-- 功能：创建产品相关表和管理函数
-- 使用方法: psql -v ON_ERROR_STOP=1 -f product_refactored.sql
-- =====================================================
-- 前置依赖：
--   必须先执行 00_schema_init.sql 初始化 schema 配置
--   该脚本依赖 get_schema_name() 函数获取 schema 名称
-- =====================================================

-- 1. 创建 test_products 表
DO $$
DECLARE
    app_schema TEXT := get_schema_name();
BEGIN
    EXECUTE format('
        CREATE TABLE IF NOT EXISTS %I.test_products (
            id uuid not null default gen_random_uuid (),
            product_name text null,
            subscription_url text null,
            email text null,
            phone text null,
            buy_time timestamp with time zone null default now(),
            end_time timestamp with time zone null,
            constraint test_products_pkey primary key (id)
        ) TABLESPACE pg_default',
        app_schema
    );
END $$;

-- 2. 创建产品相关函数
-- 获取用户产品查询函数
CREATE OR REPLACE FUNCTION fetch_user_products(
    p_user_email text default null,
    p_phone text default null
)
RETURNS TABLE (
    product_name text,
    subscription_url text,
    email text,
    phone text,
    buy_time  timestamptz,
    end_time timestamptz
)
LANGUAGE plpgsql
STABLE
AS $$
DECLARE
    app_schema TEXT := get_schema_name();
BEGIN
    IF p_user_email IS NOT NULL AND p_user_email <> '' THEN
        RETURN QUERY EXECUTE format('
            SELECT sp.product_name, sp.subscription_url::text, sp.email, sp.phone, sp.buy_time, sp.end_time
            FROM %I.test_products sp
            WHERE sp.email = %L',
            app_schema, p_user_email
        );
        RETURN;
    END IF;

    IF p_phone IS NOT NULL AND p_phone <> '' THEN
        RETURN QUERY EXECUTE format('
            SELECT sp.product_name, sp.subscription_url::text, sp.email, sp.phone, sp.buy_time, sp.end_time
            FROM %I.test_products sp
            WHERE sp.phone = %L',
            app_schema, p_phone
        );
        RETURN;
    END IF;

    RETURN;
END;
$$;

-- 插入产品函数
CREATE OR REPLACE FUNCTION insert_product(
    p_product_name text,
    p_subscription_url text,
    p_email text,
    p_phone text,
    p_time_plan interval
)
RETURNS uuid
LANGUAGE plpgsql
AS $$
DECLARE
    new_id uuid;
    calculated_end_time timestamptz;
    app_schema TEXT := get_schema_name();
BEGIN
    -- 计算结束时间：当前时间 + 时间计划
    calculated_end_time := now() + p_time_plan;

    EXECUTE format('
        INSERT INTO %I.test_products (product_name, subscription_url, email, phone, buy_time, end_time)
        VALUES (%L, %L, %L, %L, now(), %L)
        RETURNING id',
        app_schema, p_product_name, p_subscription_url, p_email, p_phone, calculated_end_time
    ) INTO new_id;

    RETURN new_id;
END;
$$;

-- 更新产品到期时间函数
CREATE OR REPLACE FUNCTION update_product_end_time(
    p_id uuid,
    p_end_time timestamptz
)
RETURNS boolean
LANGUAGE plpgsql
AS $$
DECLARE
    rows_affected integer;
    app_schema TEXT := get_schema_name();
BEGIN
    EXECUTE format('
        UPDATE %I.test_products
        SET end_time = %L
        WHERE id = %L',
        app_schema, p_end_time, p_id
    );

    GET DIAGNOSTICS rows_affected = ROW_COUNT;
    RETURN rows_affected > 0;
END;
$$;

-- 获取产品信息函数
CREATE OR REPLACE FUNCTION get_product_info(
    p_id uuid
)
RETURNS TABLE (
    id uuid,
    product_name text,
    subscription_url text,
    email text,
    phone text,
    buy_time timestamptz,
    end_time timestamptz
)
LANGUAGE plpgsql
STABLE
AS $$
DECLARE
    app_schema TEXT := get_schema_name();
BEGIN
    RETURN QUERY EXECUTE format('
        SELECT id, product_name, subscription_url, email, phone, buy_time, end_time
        FROM %I.test_products
        WHERE id = %L',
        app_schema, p_id
    );
END;
$$;

-- 删除过期产品函数
CREATE OR REPLACE FUNCTION delete_expired_products()
RETURNS integer
LANGUAGE plpgsql
AS $$
DECLARE
    deleted_count integer := 0;
    app_schema TEXT := get_schema_name();
BEGIN
    EXECUTE format('
        DELETE FROM %I.test_products
        WHERE end_time < now()
        RETURNING id',
        app_schema
    );

    GET DIAGNOSTICS deleted_count = ROW_COUNT;
    RETURN deleted_count;
END;
$$;

-- 3. 设置权限
DO $$
DECLARE
    app_schema TEXT := get_schema_name();
BEGIN
    EXECUTE format('GRANT USAGE ON SCHEMA %I TO service_role', app_schema);
    EXECUTE format('GRANT SELECT ON %I.test_products TO service_role', app_schema);
    EXECUTE format('GRANT INSERT ON %I.test_products TO service_role', app_schema);
    EXECUTE format('GRANT UPDATE ON %I.test_products TO service_role', app_schema);
    EXECUTE format('GRANT DELETE ON %I.test_products TO service_role', app_schema);
END $$;

GRANT EXECUTE ON FUNCTION fetch_user_products(text, text) TO service_role;
GRANT EXECUTE ON FUNCTION insert_product(text, text, text, text, interval) TO service_role;
GRANT EXECUTE ON FUNCTION update_product_end_time(uuid, timestamptz) TO service_role;
GRANT EXECUTE ON FUNCTION get_product_info(uuid) TO service_role;
GRANT EXECUTE ON FUNCTION delete_expired_products() TO service_role;
GRANT EXECUTE ON FUNCTION get_schema_name() TO service_role;

-- 4. 完成提示
DO $$
DECLARE
    app_schema TEXT := get_schema_name();
BEGIN
    RAISE NOTICE 'Product migration completed successfully for schema: %', app_schema;
    RAISE NOTICE 'Schema name is controlled by the configuration table at the top of this file';
END $$;
-- ===== /root/self_code/web_backend/center_management/db/migration/sql_schema_migration/20251017210442_auth_user_webhook.sql =====
-- =====================================================
-- Auth Users Webhook 通知系统
-- =====================================================
-- 功能：当 auth.users 表插入新用户时，通过 webhook 发送通知
-- 创建日期：2025-10-11
-- 依赖：00_schema_init.sql (需要先执行以创建必要的扩展)
-- 使用方法：
--   1. 在 .env 中配置 USER_WEBHOOK_URL
--   2. psql -v ON_ERROR_STOP=1 -f auth_user_webhook.sql
-- =====================================================

-- 1. 启用 pg_net 扩展（用于异步 HTTP 请求，不阻塞数据库操作）
CREATE EXTENSION IF NOT EXISTS pg_net;

-- 2. 创建 webhook 触发函数
-- 该函数会在新用户插入时被调用，发送 HTTP POST 请求到配置的 webhook URL
CREATE OR REPLACE FUNCTION notify_new_user()
RETURNS TRIGGER AS $$
DECLARE
    webhook_url TEXT;
    payload JSONB;
    request_id BIGINT;
BEGIN
    -- 从环境变量或配置表中获取 webhook URL
    -- 注意：这里假设你会通过其他方式注入 webhook_url
    -- 如果使用 Supabase，可以使用 vault 存储敏感配置

    -- 临时方案：直接在这里设置 webhook URL
    -- 生产环境建议使用 Supabase Vault 或环境变量
    -- webhook_url := current_setting('app.webhook_url', true);

    -- 如果没有配置 webhook URL，跳过通知
    -- webhook_url := current_setting('app.user_webhook_url', true);
    -- IF webhook_url IS NULL OR webhook_url = '' THEN
    --     RAISE NOTICE 'Webhook URL not configured, skipping notification';
    --     RETURN NEW;
    -- END IF;

    -- 注意：由于 PostgreSQL 不能直接访问环境变量
    -- 你需要通过以下方式之一配置 webhook_url：
    -- 方式1: ALTER DATABASE postgres SET app.user_webhook_url = 'your_url';
    -- 方式2: 在代码中通过 Supabase Vault 存储
    -- 方式3: 创建配置表存储 webhook_url

    -- 暂时使用占位符，实际使用时需要替换
    -- 请在下面的 'YOUR_WEBHOOK_URL_HERE' 处填入实际的 webhook URL
    webhook_url := 'YOUR_WEBHOOK_URL_HERE';

    -- 如果是占位符，给出警告但不失败
    IF webhook_url = 'YOUR_WEBHOOK_URL_HERE' THEN
        RAISE WARNING 'Webhook URL not configured! Please update auth_user_webhook.sql with your actual webhook URL';
        RETURN NEW;
    END IF;

    -- 构建 JSON payload
    payload := jsonb_build_object(
        'type', 'user.created',
        'timestamp', NOW(),
        'data', jsonb_build_object(
            'user_id', NEW.id,
            'email', NEW.email,
            'created_at', NEW.created_at,
            'confirmed_at', NEW.confirmed_at,
            'email_confirmed_at', NEW.email_confirmed_at
        )
    );

    -- 使用 pg_net 发送异步 HTTP POST 请求
    -- 这不会阻塞数据库操作
    SELECT INTO request_id net.http_post(
        url := webhook_url,
        body := payload,
        headers := '{"Content-Type": "application/json"}'::JSONB,
        timeout_milliseconds := 5000
    );

    -- 记录请求 ID（可选，用于调试）
    RAISE NOTICE 'Webhook notification sent for user %. Request ID: %', NEW.email, request_id;

    RETURN NEW;
EXCEPTION
    WHEN OTHERS THEN
        -- 如果 webhook 发送失败，记录错误但不影响用户创建
        RAISE WARNING 'Failed to send webhook notification: %', SQLERRM;
        RETURN NEW;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- 3. 在 auth.users 表上创建触发器
-- 当插入新用户时自动触发
DROP TRIGGER IF EXISTS on_auth_user_created ON auth.users;

CREATE TRIGGER on_auth_user_created
    AFTER INSERT ON auth.users
    FOR EACH ROW
    EXECUTE FUNCTION notify_new_user();

-- 4. 授予必要的权限
GRANT USAGE ON SCHEMA net TO service_role;
GRANT EXECUTE ON FUNCTION notify_new_user() TO service_role;

-- 5. 创建配置表用于存储 webhook URL（推荐方式）
-- 这样可以在不修改 SQL 的情况下更新 webhook URL
-- 使用动态 schema 而不是 public schema
DO $$
DECLARE
    app_schema TEXT := get_schema_name();
BEGIN
    EXECUTE format('
        CREATE TABLE IF NOT EXISTS %I.webhook_config (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL,
            description TEXT,
            updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
        )', app_schema);

    -- 插入默认配置（需要手动更新为实际的 webhook URL）
    EXECUTE format('
        INSERT INTO %I.webhook_config (key, value, description)
        VALUES (
            ''user_webhook_url'',
            ''YOUR_WEBHOOK_URL_HERE'',
            ''Webhook URL for new user notifications''
        )
        ON CONFLICT (key) DO NOTHING', app_schema);

    RAISE NOTICE 'Created table: %.webhook_config', app_schema;
END $$;

-- 6. 更新函数以使用配置表（使用动态 schema）
CREATE OR REPLACE FUNCTION notify_new_user()
RETURNS TRIGGER AS $$
DECLARE
    webhook_url TEXT;
    payload JSONB;
    request_id BIGINT;
    app_schema TEXT;
BEGIN
    -- 获取配置的 schema 名称
    SELECT get_schema_name() INTO app_schema;

    -- 从配置表中读取 webhook URL（使用动态 schema）
    EXECUTE format('SELECT value FROM %I.webhook_config WHERE key = ''user_webhook_url''', app_schema)
    INTO webhook_url;

    -- 如果没有配置或是占位符，跳过通知
    IF webhook_url IS NULL OR webhook_url = '' OR webhook_url = 'YOUR_WEBHOOK_URL_HERE' THEN
        RAISE NOTICE 'Webhook URL not configured, skipping notification for user %', NEW.email;
        RETURN NEW;
    END IF;

    -- 构建 JSON payload
    payload := jsonb_build_object(
        'type', 'user.created',
        'timestamp', NOW(),
        'data', jsonb_build_object(
            'user_id', NEW.id,
            'email', NEW.email,
            'created_at', NEW.created_at,
            'confirmed_at', NEW.confirmed_at,
            'email_confirmed_at', NEW.email_confirmed_at,
            'phone', NEW.phone
        )
    );

    -- 使用 pg_net 发送异步 HTTP POST 请求
    SELECT INTO request_id net.http_post(
        url := webhook_url,
        body := payload,
        headers := '{"Content-Type": "application/json"}'::JSONB,
        timeout_milliseconds := 5000
    );

    RAISE NOTICE 'Webhook notification sent for user %. Request ID: %', NEW.email, request_id;

    RETURN NEW;
EXCEPTION
    WHEN OTHERS THEN
        RAISE WARNING 'Failed to send webhook notification: %', SQLERRM;
        RETURN NEW;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- 7. 验证配置（使用动态 schema）
DO $$
DECLARE
    current_webhook_url TEXT;
    app_schema TEXT := get_schema_name();
BEGIN
    EXECUTE format('SELECT value FROM %I.webhook_config WHERE key = ''user_webhook_url''', app_schema)
    INTO current_webhook_url;

    RAISE NOTICE '====================================================';
    RAISE NOTICE 'Auth user webhook setup completed successfully';
    RAISE NOTICE '====================================================';
    RAISE NOTICE 'Extension: pg_net installed';
    RAISE NOTICE 'Function: notify_new_user() created';
    RAISE NOTICE 'Trigger: on_auth_user_created on auth.users';
    RAISE NOTICE 'Config table: %.webhook_config', app_schema;
    RAISE NOTICE 'Current webhook URL: %', current_webhook_url;
    RAISE NOTICE '====================================================';

    IF current_webhook_url = 'YOUR_WEBHOOK_URL_HERE' THEN
        RAISE NOTICE '⚠️  WARNING: Please update the webhook URL!';
        RAISE NOTICE '';
        RAISE NOTICE 'Update using SQL:';
        RAISE NOTICE 'UPDATE %.webhook_config SET value = ''your_actual_url'' WHERE key = ''user_webhook_url'';', app_schema;
        RAISE NOTICE '';
        RAISE NOTICE 'Or in psql:';
        RAISE NOTICE 'psql -c "UPDATE %.webhook_config SET value = ''YOUR_URL'' WHERE key = ''user_webhook_url'';"', app_schema;
    ELSE
        RAISE NOTICE '✅ Webhook URL is configured';
    END IF;

    RAISE NOTICE '====================================================';
END $$;

-- ===== /root/self_code/web_backend/center_management/db/migration/sql_schema_migration/20251017210443_ticket_system.sql =====
-- =====================================================
-- 工单管理系统
-- =====================================================
-- 功能：创建工单相关表和管理函数
-- 使用方法: psql -v ON_ERROR_STOP=1 -f ticket_system.sql
-- =====================================================
-- 前置依赖：
--   必须先执行 00_schema_init.sql 初始化 schema 配置
--   该脚本依赖 get_schema_name() 函数获取 schema 名称
-- =====================================================

-- 1. 创建 ticket 表
DO $$
DECLARE
    app_schema TEXT := get_schema_name();
BEGIN
    EXECUTE format('
        CREATE TABLE IF NOT EXISTS %I.ticket (
            id uuid not null default gen_random_uuid(),
            created_at timestamp with time zone not null default now(),
            updated_at timestamp with time zone not null default now(),
            user_email text not null,
            phone text null default '''',
            subject text not null,
            priority text not null check (priority in (''高'', ''中'', ''低'')),
            category text not null,
            description text not null,
            status text not null default ''处理中'' check (status in (''处理中'', ''已解决'')),
            metadata jsonb null,
            constraint ticket_pkey primary key (id)
        ) TABLESPACE pg_default',
        app_schema
    );

    -- 为常用查询字段创建索引
    EXECUTE format('CREATE INDEX IF NOT EXISTS ticket_user_email_idx ON %I.ticket(user_email)', app_schema);
    EXECUTE format('CREATE INDEX IF NOT EXISTS ticket_status_idx ON %I.ticket(status)', app_schema);
    EXECUTE format('CREATE INDEX IF NOT EXISTS ticket_created_at_idx ON %I.ticket(created_at DESC)', app_schema);

    RAISE NOTICE 'Created ticket table in schema: %', app_schema;
END $$;

-- 2. 创建自动更新 updated_at 的触发器函数
CREATE OR REPLACE FUNCTION update_ticket_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- 3. 为 ticket 表添加更新触发器
DO $$
DECLARE
    app_schema TEXT := get_schema_name();
BEGIN
    EXECUTE format('
        DROP TRIGGER IF EXISTS ticket_updated_at_trigger ON %I.ticket;
        CREATE TRIGGER ticket_updated_at_trigger
        BEFORE UPDATE ON %I.ticket
        FOR EACH ROW
        EXECUTE FUNCTION update_ticket_updated_at()',
        app_schema, app_schema
    );
END $$;

-- 4. 创建插入工单函数
CREATE OR REPLACE FUNCTION insert_ticket(
    p_user_email text,
    p_subject text,
    p_priority text,
    p_category text,
    p_description text,
    p_phone text default '',
    p_metadata jsonb default null
)
RETURNS uuid
LANGUAGE plpgsql
AS $$
DECLARE
    new_id uuid;
    app_schema TEXT := get_schema_name();
BEGIN
    -- 验证 priority 值
    IF p_priority NOT IN ('高', '中', '低') THEN
        RAISE EXCEPTION 'Invalid priority value. Must be one of: 高, 中, 低';
    END IF;

    -- 插入工单
    EXECUTE format('
        INSERT INTO %I.ticket (user_email, subject, priority, category, description, phone, metadata)
        VALUES (%L, %L, %L, %L, %L, %L, %L)
        RETURNING id',
        app_schema, p_user_email, p_subject, p_priority, p_category, p_description, p_phone, p_metadata
    ) INTO new_id;

    RETURN new_id;
END;
$$;

-- 5. 创建查询用户工单函数
-- 先删除旧版本（如果存在）以避免签名冲突
DROP FUNCTION IF EXISTS fetch_user_tickets(text);

CREATE OR REPLACE FUNCTION fetch_user_tickets(
    p_user_email text
)
RETURNS TABLE (
    id uuid,
    subject text,
    priority text,
    category text,
    description text,
    status text,
    phone text,
    created_at timestamptz,
    updated_at timestamptz,
    metadata jsonb
)
LANGUAGE plpgsql
STABLE
AS $$
DECLARE
    app_schema TEXT := get_schema_name();
BEGIN
    IF p_user_email IS NULL OR p_user_email = '' THEN
        RAISE EXCEPTION 'User email is required';
    END IF;

    RETURN QUERY EXECUTE format('
        SELECT t.id, t.subject, t.priority, t.category, t.description,
               t.status, t.phone, t.created_at, t.updated_at, t.metadata
        FROM %I.ticket t
        WHERE t.user_email = %L
        ORDER BY t.created_at DESC',
        app_schema, p_user_email
    );
END;
$$;

-- 6. 创建更新工单状态函数
CREATE OR REPLACE FUNCTION update_ticket_status(
    p_ticket_id uuid,
    p_status text
)
RETURNS boolean
LANGUAGE plpgsql
AS $$
DECLARE
    rows_affected integer;
    app_schema TEXT := get_schema_name();
BEGIN
    -- 验证 status 值
    IF p_status NOT IN ('处理中', '已解决') THEN
        RAISE EXCEPTION 'Invalid status value. Must be one of: 处理中, 已解决';
    END IF;

    EXECUTE format('
        UPDATE %I.ticket
        SET status = %L
        WHERE id = %L',
        app_schema, p_status, p_ticket_id
    );

    GET DIAGNOSTICS rows_affected = ROW_COUNT;
    RETURN rows_affected > 0;
END;
$$;

-- 7. 创建查询所有工单函数（管理员用）
-- 先删除旧版本（如果存在）以避免签名冲突
DROP FUNCTION IF EXISTS fetch_all_tickets(text, text, integer, integer);

CREATE OR REPLACE FUNCTION fetch_all_tickets(
    p_status text default null,
    p_priority text default null,
    p_limit integer default 100,
    p_offset integer default 0
)
RETURNS TABLE (
    id uuid,
    user_email text,
    phone text,
    subject text,
    priority text,
    category text,
    description text,
    status text,
    created_at timestamptz,
    updated_at timestamptz,
    metadata jsonb
)
LANGUAGE plpgsql
STABLE
AS $$
DECLARE
    app_schema TEXT := get_schema_name();
    where_clause text := '';
BEGIN
    -- 构建 WHERE 子句
    IF p_status IS NOT NULL THEN
        where_clause := format('WHERE status = %L', p_status);
    END IF;

    IF p_priority IS NOT NULL THEN
        IF where_clause = '' THEN
            where_clause := format('WHERE priority = %L', p_priority);
        ELSE
            where_clause := where_clause || format(' AND priority = %L', p_priority);
        END IF;
    END IF;

    RETURN QUERY EXECUTE format('
        SELECT t.id, t.user_email, t.phone, t.subject, t.priority, t.category,
               t.description, t.status, t.created_at, t.updated_at, t.metadata
        FROM %I.ticket t
        %s
        ORDER BY t.created_at DESC
        LIMIT %L OFFSET %L',
        app_schema, where_clause, p_limit, p_offset
    );
END;
$$;

-- 8. 设置权限
DO $$
DECLARE
    app_schema TEXT := get_schema_name();
BEGIN
    EXECUTE format('GRANT USAGE ON SCHEMA %I TO service_role', app_schema);
    EXECUTE format('GRANT SELECT ON %I.ticket TO service_role', app_schema);
    EXECUTE format('GRANT INSERT ON %I.ticket TO service_role', app_schema);
    EXECUTE format('GRANT UPDATE ON %I.ticket TO service_role', app_schema);
    EXECUTE format('GRANT DELETE ON %I.ticket TO service_role', app_schema);
END $$;

GRANT EXECUTE ON FUNCTION insert_ticket(text, text, text, text, text, text, jsonb) TO service_role;
GRANT EXECUTE ON FUNCTION fetch_user_tickets(text) TO service_role;
GRANT EXECUTE ON FUNCTION update_ticket_status(uuid, text) TO service_role;
GRANT EXECUTE ON FUNCTION fetch_all_tickets(text, text, integer, integer) TO service_role;
GRANT EXECUTE ON FUNCTION update_ticket_updated_at() TO service_role;

-- 9. 完成提示
DO $$
DECLARE
    app_schema TEXT := get_schema_name();
BEGIN
    RAISE NOTICE 'Ticket system migration completed successfully for schema: %', app_schema;
    RAISE NOTICE 'Created tables: ticket';
    RAISE NOTICE 'Created functions: insert_ticket, fetch_user_tickets, update_ticket_status, fetch_all_tickets';
    RAISE NOTICE 'Priority values: 高, 中, 低';
    RAISE NOTICE 'Status values: 处理中, 已解决';
END $$;
-- ===== /root/self_code/web_backend/center_management/db/migration/sql_schema_migration/20251017210444_ticket_system_add_reply.sql =====
-- =====================================================
-- 工单系统添加答复功能
-- =====================================================
-- 功能：为工单表添加管理员答复字段，并更新相关函数
-- 创建日期：2025-10-02
-- 使用方法: psql -v ON_ERROR_STOP=1 -f ticket_system_add_reply.sql
-- =====================================================
-- 前置依赖：
--   1. 必须先执行 00_schema_init.sql 初始化 schema 配置
--   2. 必须先执行 ticket_system.sql 创建 ticket 表
--   该脚本依赖 get_schema_name() 函数获取 schema 名称
-- =====================================================

-- 1. 为 ticket 表添加答复相关字段
DO $$
DECLARE
    app_schema TEXT := get_schema_name();
BEGIN
    -- 添加 reply 字段（管理员答复内容）
    EXECUTE format('
        ALTER TABLE %I.ticket
        ADD COLUMN IF NOT EXISTS reply TEXT NULL',
        app_schema
    );

    -- 添加 replied_at 字段（答复时间）
    EXECUTE format('
        ALTER TABLE %I.ticket
        ADD COLUMN IF NOT EXISTS replied_at TIMESTAMPTZ NULL',
        app_schema
    );

    RAISE NOTICE 'Added reply and replied_at columns to ticket table in schema: %', app_schema;
END $$;

-- 2. 替换 update_ticket_status 函数（支持答复参数）
-- Drop all versions of the function to avoid signature conflicts
DROP FUNCTION IF EXISTS update_ticket_status(uuid, text);
DROP FUNCTION IF EXISTS update_ticket_status(uuid, text, text);

CREATE OR REPLACE FUNCTION update_ticket_status(
    p_ticket_id uuid,
    p_status text,
    p_reply text DEFAULT NULL
)
RETURNS boolean
LANGUAGE plpgsql
AS $$
DECLARE
    rows_affected integer;
    app_schema TEXT := get_schema_name();
BEGIN
    -- 验证 status 值
    IF p_status NOT IN ('处理中', '已解决') THEN
        RAISE EXCEPTION 'Invalid status value. Must be one of: 处理中, 已解决';
    END IF;

    -- 更新工单状态和答复
    IF p_reply IS NOT NULL AND p_reply != '' THEN
        -- 如果提供了答复，同时更新 reply 和 replied_at
        EXECUTE format('
            UPDATE %I.ticket
            SET status = %L,
                reply = %L,
                replied_at = NOW()
            WHERE id = %L',
            app_schema, p_status, p_reply, p_ticket_id
        );
    ELSE
        -- 如果没有提供答复，只更新状态
        EXECUTE format('
            UPDATE %I.ticket
            SET status = %L
            WHERE id = %L',
            app_schema, p_status, p_ticket_id
        );
    END IF;

    GET DIAGNOSTICS rows_affected = ROW_COUNT;
    RETURN rows_affected > 0;
END;
$$;

-- 3. 创建根据 ID 获取工单详情的函数（新函数）
CREATE OR REPLACE FUNCTION get_ticket_by_id(
    p_ticket_id uuid
)
RETURNS TABLE (
    id uuid,
    created_at timestamptz,
    updated_at timestamptz,
    user_email text,
    phone text,
    subject text,
    priority text,
    category text,
    description text,
    status text,
    reply text,
    replied_at timestamptz,
    metadata jsonb
)
LANGUAGE plpgsql
STABLE
AS $$
DECLARE
    app_schema TEXT := get_schema_name();
BEGIN
    RETURN QUERY EXECUTE format('
        SELECT t.id, t.created_at, t.updated_at, t.user_email, t.phone,
               t.subject, t.priority, t.category, t.description, t.status,
               t.reply, t.replied_at, t.metadata
        FROM %I.ticket t
        WHERE t.id = %L',
        app_schema, p_ticket_id
    );
END;
$$;

-- 4. 替换 fetch_user_tickets 函数（包含答复字段）
DROP FUNCTION IF EXISTS fetch_user_tickets(text);

CREATE OR REPLACE FUNCTION fetch_user_tickets(
    p_user_email text
)
RETURNS TABLE (
    id uuid,
    subject text,
    priority text,
    category text,
    description text,
    status text,
    phone text,
    created_at timestamptz,
    updated_at timestamptz,
    reply text,
    replied_at timestamptz,
    metadata jsonb
)
LANGUAGE plpgsql
STABLE
AS $$
DECLARE
    app_schema TEXT := get_schema_name();
BEGIN
    IF p_user_email IS NULL OR p_user_email = '' THEN
        RAISE EXCEPTION 'User email is required';
    END IF;

    RETURN QUERY EXECUTE format('
        SELECT t.id, t.subject, t.priority, t.category, t.description,
               t.status, t.phone, t.created_at, t.updated_at,
               t.reply, t.replied_at, t.metadata
        FROM %I.ticket t
        WHERE t.user_email = %L
        ORDER BY t.created_at DESC',
        app_schema, p_user_email
    );
END;
$$;

-- 5. 替换 fetch_all_tickets 函数（包含答复字段）
DROP FUNCTION IF EXISTS fetch_all_tickets(text, text, integer, integer);

CREATE OR REPLACE FUNCTION fetch_all_tickets(
    p_status text default null,
    p_priority text default null,
    p_limit integer default 100,
    p_offset integer default 0
)
RETURNS TABLE (
    id uuid,
    user_email text,
    phone text,
    subject text,
    priority text,
    category text,
    description text,
    status text,
    created_at timestamptz,
    updated_at timestamptz,
    reply text,
    replied_at timestamptz,
    metadata jsonb
)
LANGUAGE plpgsql
STABLE
AS $$
DECLARE
    app_schema TEXT := get_schema_name();
    where_clause text := '';
BEGIN
    -- 构建 WHERE 子句
    IF p_status IS NOT NULL THEN
        where_clause := format('WHERE status = %L', p_status);
    END IF;

    IF p_priority IS NOT NULL THEN
        IF where_clause = '' THEN
            where_clause := format('WHERE priority = %L', p_priority);
        ELSE
            where_clause := where_clause || format(' AND priority = %L', p_priority);
        END IF;
    END IF;

    RETURN QUERY EXECUTE format('
        SELECT t.id, t.user_email, t.phone, t.subject, t.priority, t.category,
               t.description, t.status, t.created_at, t.updated_at,
               t.reply, t.replied_at, t.metadata
        FROM %I.ticket t
        %s
        ORDER BY t.created_at DESC
        LIMIT %L OFFSET %L',
        app_schema, where_clause, p_limit, p_offset
    );
END;
$$;

-- 6. 更新权限设置
-- 注意：这里授予新签名的权限
GRANT EXECUTE ON FUNCTION update_ticket_status(uuid, text, text) TO service_role;
GRANT EXECUTE ON FUNCTION get_ticket_by_id(uuid) TO service_role;
GRANT EXECUTE ON FUNCTION fetch_user_tickets(text) TO service_role;
GRANT EXECUTE ON FUNCTION fetch_all_tickets(text, text, integer, integer) TO service_role;

-- 7. 完成提示
DO $$
DECLARE
    app_schema TEXT := get_schema_name();
BEGIN
    RAISE NOTICE 'Ticket reply feature migration completed successfully for schema: %', app_schema;
    RAISE NOTICE 'Added columns: reply, replied_at';
    RAISE NOTICE 'Updated functions: update_ticket_status (new signature with reply parameter)';
    RAISE NOTICE 'Recreated functions: fetch_user_tickets, fetch_all_tickets (with reply fields)';
    RAISE NOTICE 'Created new function: get_ticket_by_id';
END $$;

-- ===== /root/self_code/web_backend/center_management/db/migration/sql_schema_migration/20251017210445_ticket_auto_resolve_trigger.sql =====
-- =====================================================
-- 工单系统自动解决触发器
-- =====================================================
-- 功能：当工单添加管理员答复时，自动将状态更新为"已解决"并记录答复时间
-- 创建日期：2025-10-02
-- 使用方法: psql -v ON_ERROR_STOP=1 -f ticket_auto_resolve_trigger.sql
-- =====================================================
-- 前置依赖：
--   1. 必须先执行 00_schema_init.sql 初始化 schema 配置
--   2. 必须先执行 ticket_system.sql 创建 ticket 表
--   该脚本依赖 get_schema_name() 函数获取 schema 名称
-- =====================================================

-- 1. 创建触发器函数：当添加或更新答复时自动解决工单
CREATE OR REPLACE FUNCTION auto_resolve_ticket_on_reply()
RETURNS TRIGGER AS $$
BEGIN
    -- 检查是否设置了答复（reply 不为空）
    IF NEW.reply IS NOT NULL AND NEW.reply != '' THEN
        -- 检查是否是新添加答复或更新答复
        IF (OLD.reply IS NULL OR OLD.reply = '') OR (OLD.reply != NEW.reply) THEN
            -- 自动设置状态为"已解决"
            NEW.status := '已解决';
            -- 自动设置答复时间为当前时间
            NEW.replied_at := NOW();

            RAISE NOTICE 'Auto-resolved ticket % due to reply addition/update', NEW.id;
        END IF;
    END IF;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- 2. 为 ticket 表创建 BEFORE UPDATE 触发器
DO $$
DECLARE
    app_schema TEXT := get_schema_name();
BEGIN
    -- 删除已存在的触发器（如果存在）
    EXECUTE format('
        DROP TRIGGER IF EXISTS ticket_auto_resolve_trigger ON %I.ticket',
        app_schema
    );

    -- 创建新触发器
    EXECUTE format('
        CREATE TRIGGER ticket_auto_resolve_trigger
        BEFORE UPDATE ON %I.ticket
        FOR EACH ROW
        EXECUTE FUNCTION auto_resolve_ticket_on_reply()',
        app_schema
    );

    RAISE NOTICE 'Created auto-resolve trigger for ticket table in schema: %', app_schema;
END $$;

-- 3. 授予权限
GRANT EXECUTE ON FUNCTION auto_resolve_ticket_on_reply() TO service_role;

-- 4. 完成提示
DO $$
DECLARE
    app_schema TEXT := get_schema_name();
BEGIN
    RAISE NOTICE 'Ticket auto-resolve trigger migration completed successfully for schema: %', app_schema;
    RAISE NOTICE 'Created function: auto_resolve_ticket_on_reply()';
    RAISE NOTICE 'Created trigger: ticket_auto_resolve_trigger';
    RAISE NOTICE 'Behavior: When reply is added (NULL/empty -> non-empty), automatically set status="已解决" and replied_at=NOW()';
END $$;

-- ===== /root/self_code/web_backend/center_management/db/migration/sql_schema_migration/20251017210446_r2_package_system.sql =====
-- =====================================================
-- R2 Package Management System
-- =====================================================
-- Description: Database schema for Cloudflare R2 software package distribution
-- Dependencies: Requires 00_schema_init.sql (for get_schema_name() function)
-- Version: 2.0 - Updated to use dynamic schema
-- Created: 2025-10-15
-- Updated: 2025-10-15 - Moved to dynamic schema

-- 1. Create r2_packages table in configured schema
DO $$
DECLARE
    app_schema TEXT := get_schema_name();
BEGIN
    EXECUTE format('
        CREATE TABLE IF NOT EXISTS %I.r2_packages (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            package_name TEXT NOT NULL,
            version TEXT NOT NULL,
            r2_key TEXT NOT NULL UNIQUE,
            file_size BIGINT NOT NULL,
            file_hash TEXT NOT NULL,
            hash_algorithm TEXT NOT NULL DEFAULT ''sha256'',
            description TEXT,
            tags JSONB DEFAULT ''[]''::jsonb,
            is_public BOOLEAN DEFAULT false,
            uploader_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
            download_count INTEGER DEFAULT 0,
            status TEXT NOT NULL DEFAULT ''active'' CHECK (status IN (''active'', ''archived'', ''deleted'')),
            metadata JSONB DEFAULT ''{}''::jsonb,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

            CONSTRAINT r2_packages_version_check CHECK (version ~ ''^[0-9]+\.[0-9]+\.[0-9]+(-[a-zA-Z0-9.-]+)?(\+[a-zA-Z0-9.-]+)?$'')
        )', app_schema);

    RAISE NOTICE 'Created table: %.r2_packages', app_schema;
END $$;

-- 2. Create indexes for performance optimization
DO $$
DECLARE
    app_schema TEXT := get_schema_name();
BEGIN
    EXECUTE format('CREATE INDEX IF NOT EXISTS idx_r2_packages_name_version ON %I.r2_packages(package_name, version)', app_schema);
    EXECUTE format('CREATE INDEX IF NOT EXISTS idx_r2_packages_uploader ON %I.r2_packages(uploader_id)', app_schema);
    EXECUTE format('CREATE INDEX IF NOT EXISTS idx_r2_packages_status ON %I.r2_packages(status)', app_schema);
    EXECUTE format('CREATE INDEX IF NOT EXISTS idx_r2_packages_created_at ON %I.r2_packages(created_at DESC)', app_schema);
    EXECUTE format('CREATE INDEX IF NOT EXISTS idx_r2_packages_is_public ON %I.r2_packages(is_public) WHERE is_public = true', app_schema);
    EXECUTE format('CREATE INDEX IF NOT EXISTS idx_r2_packages_tags ON %I.r2_packages USING GIN(tags)', app_schema);

    -- Unique constraint for package name + version combination
    EXECUTE format('CREATE UNIQUE INDEX IF NOT EXISTS idx_r2_packages_unique_name_version ON %I.r2_packages(package_name, version) WHERE status != ''deleted''', app_schema);

    RAISE NOTICE 'Created indexes for: %.r2_packages', app_schema;
END $$;

-- 3. Create download history table
DO $$
DECLARE
    app_schema TEXT := get_schema_name();
BEGIN
    EXECUTE format('
        CREATE TABLE IF NOT EXISTS %I.r2_package_downloads (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            package_id UUID NOT NULL REFERENCES %I.r2_packages(id) ON DELETE CASCADE,
            user_id UUID REFERENCES auth.users(id) ON DELETE SET NULL,
            ip_address INET,
            user_agent TEXT,
            downloaded_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )', app_schema, app_schema);

    EXECUTE format('CREATE INDEX IF NOT EXISTS idx_r2_downloads_package ON %I.r2_package_downloads(package_id)', app_schema);
    EXECUTE format('CREATE INDEX IF NOT EXISTS idx_r2_downloads_user ON %I.r2_package_downloads(user_id)', app_schema);
    EXECUTE format('CREATE INDEX IF NOT EXISTS idx_r2_downloads_time ON %I.r2_package_downloads(downloaded_at DESC)', app_schema);

    RAISE NOTICE 'Created table: %.r2_package_downloads', app_schema;
END $$;

-- 4. Function: Update updated_at timestamp automatically
CREATE OR REPLACE FUNCTION update_r2_package_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- 5. Create trigger for updated_at
DO $$
DECLARE
    app_schema TEXT := get_schema_name();
BEGIN
    EXECUTE format('DROP TRIGGER IF EXISTS trigger_r2_package_updated_at ON %I.r2_packages', app_schema);
    EXECUTE format('
        CREATE TRIGGER trigger_r2_package_updated_at
        BEFORE UPDATE ON %I.r2_packages
        FOR EACH ROW
        EXECUTE FUNCTION update_r2_package_updated_at()', app_schema);

    RAISE NOTICE 'Created trigger: trigger_r2_package_updated_at on %.r2_packages', app_schema;
END $$;

-- 6. Function: Increment download count and log download
CREATE OR REPLACE FUNCTION record_r2_package_download(
    p_package_id UUID,
    p_user_id UUID DEFAULT NULL,
    p_ip_address INET DEFAULT NULL,
    p_user_agent TEXT DEFAULT NULL
)
RETURNS VOID AS $$
DECLARE
    app_schema TEXT := get_schema_name();
BEGIN
    -- Increment download count
    EXECUTE format('
        UPDATE %I.r2_packages
        SET download_count = download_count + 1
        WHERE id = $1', app_schema)
    USING p_package_id;

    -- Log download event
    EXECUTE format('
        INSERT INTO %I.r2_package_downloads (package_id, user_id, ip_address, user_agent)
        VALUES ($1, $2, $3, $4)', app_schema)
    USING p_package_id, p_user_id, p_ip_address, p_user_agent;
END;
$$ LANGUAGE plpgsql;

-- 7. Function: Get package statistics
CREATE OR REPLACE FUNCTION get_r2_package_stats(p_package_name TEXT DEFAULT NULL)
RETURNS TABLE (
    package_name TEXT,
    total_versions INTEGER,
    total_downloads BIGINT,
    total_size_bytes BIGINT,
    total_size_mb NUMERIC,
    latest_version TEXT,
    latest_upload_date TIMESTAMPTZ
) AS $$
DECLARE
    app_schema TEXT := get_schema_name();
BEGIN
    RETURN QUERY EXECUTE format('
        SELECT
            p.package_name,
            COUNT(DISTINCT p.version)::INTEGER as total_versions,
            SUM(p.download_count)::BIGINT as total_downloads,
            SUM(p.file_size)::BIGINT as total_size_bytes,
            ROUND(SUM(p.file_size)::NUMERIC / (1024 * 1024), 2) as total_size_mb,
            (SELECT version FROM %I.r2_packages
             WHERE package_name = p.package_name AND status = ''active''
             ORDER BY created_at DESC LIMIT 1) as latest_version,
            MAX(p.created_at) as latest_upload_date
        FROM %I.r2_packages p
        WHERE p.status = ''active''
            AND ($1 IS NULL OR p.package_name = $1)
        GROUP BY p.package_name', app_schema, app_schema)
    USING p_package_name;
END;
$$ LANGUAGE plpgsql;

-- 8. Function: Clean up old archived versions
CREATE OR REPLACE FUNCTION cleanup_old_r2_packages(p_days_threshold INTEGER DEFAULT 90)
RETURNS TABLE (
    package_id UUID,
    package_name TEXT,
    version TEXT,
    r2_key TEXT
) AS $$
DECLARE
    app_schema TEXT := get_schema_name();
BEGIN
    RETURN QUERY EXECUTE format('
        UPDATE %I.r2_packages
        SET status = ''deleted''
        WHERE status = ''archived''
            AND updated_at < NOW() - ($1 || '' days'')::INTERVAL
        RETURNING id, package_name, version, r2_key', app_schema)
    USING p_days_threshold;
END;
$$ LANGUAGE plpgsql;

-- 9. Function: Search packages by name or tags
CREATE OR REPLACE FUNCTION search_r2_packages(
    p_search_term TEXT DEFAULT NULL,
    p_tags TEXT[] DEFAULT NULL,
    p_is_public BOOLEAN DEFAULT NULL,
    p_limit INTEGER DEFAULT 50,
    p_offset INTEGER DEFAULT 0
)
RETURNS TABLE (
    id UUID,
    package_name TEXT,
    version TEXT,
    description TEXT,
    tags JSONB,
    is_public BOOLEAN,
    download_count INTEGER,
    file_size BIGINT,
    created_at TIMESTAMPTZ
) AS $$
DECLARE
    app_schema TEXT := get_schema_name();
BEGIN
    RETURN QUERY EXECUTE format('
        SELECT
            p.id,
            p.package_name,
            p.version,
            p.description,
            p.tags,
            p.is_public,
            p.download_count,
            p.file_size,
            p.created_at
        FROM %I.r2_packages p
        WHERE p.status = ''active''
            AND ($1 IS NULL OR
                 p.package_name ILIKE ''%%'' || $1 || ''%%'' OR
                 p.description ILIKE ''%%'' || $1 || ''%%'')
            AND ($2 IS NULL OR p.tags ?| $2)
            AND ($3 IS NULL OR p.is_public = $3)
        ORDER BY p.created_at DESC
        LIMIT $4
        OFFSET $5', app_schema)
    USING p_search_term, p_tags, p_is_public, p_limit, p_offset;
END;
$$ LANGUAGE plpgsql;

-- 10. Function: Get package versions with pagination
CREATE OR REPLACE FUNCTION get_r2_package_versions(
    p_package_name TEXT,
    p_limit INTEGER DEFAULT 20,
    p_offset INTEGER DEFAULT 0
)
RETURNS TABLE (
    id UUID,
    version TEXT,
    file_size BIGINT,
    download_count INTEGER,
    status TEXT,
    created_at TIMESTAMPTZ
) AS $$
DECLARE
    app_schema TEXT := get_schema_name();
BEGIN
    RETURN QUERY EXECUTE format('
        SELECT
            p.id,
            p.version,
            p.file_size,
            p.download_count,
            p.status,
            p.created_at
        FROM %I.r2_packages p
        WHERE p.package_name = $1
            AND p.status IN (''active'', ''archived'')
        ORDER BY p.created_at DESC
        LIMIT $2
        OFFSET $3', app_schema)
    USING p_package_name, p_limit, p_offset;
END;
$$ LANGUAGE plpgsql;

-- 11. Enable Row Level Security (RLS)
DO $$
DECLARE
    app_schema TEXT := get_schema_name();
BEGIN
    EXECUTE format('ALTER TABLE %I.r2_packages ENABLE ROW LEVEL SECURITY', app_schema);
    EXECUTE format('ALTER TABLE %I.r2_package_downloads ENABLE ROW LEVEL SECURITY', app_schema);

    RAISE NOTICE 'Enabled RLS on tables in schema: %', app_schema;
END $$;

-- 12. Drop existing policies if they exist
DO $$
DECLARE
    app_schema TEXT := get_schema_name();
BEGIN
    EXECUTE format('DROP POLICY IF EXISTS "r2_packages_select_public" ON %I.r2_packages', app_schema);
    EXECUTE format('DROP POLICY IF EXISTS "r2_packages_select_own" ON %I.r2_packages', app_schema);
    EXECUTE format('DROP POLICY IF EXISTS "r2_packages_insert_auth" ON %I.r2_packages', app_schema);
    EXECUTE format('DROP POLICY IF EXISTS "r2_packages_update_own" ON %I.r2_packages', app_schema);
    EXECUTE format('DROP POLICY IF EXISTS "r2_packages_delete_own" ON %I.r2_packages', app_schema);
    EXECUTE format('DROP POLICY IF EXISTS "r2_downloads_select_own_packages" ON %I.r2_package_downloads', app_schema);
    EXECUTE format('DROP POLICY IF EXISTS "r2_downloads_insert_system" ON %I.r2_package_downloads', app_schema);

    RAISE NOTICE 'Dropped existing RLS policies for schema: %', app_schema;
END $$;

-- 13. Create RLS Policies
DO $$
DECLARE
    app_schema TEXT := get_schema_name();
BEGIN
    -- Policy: Public packages are readable by everyone
    EXECUTE format('
        CREATE POLICY "r2_packages_select_public" ON %I.r2_packages
        FOR SELECT
        USING (is_public = true AND status = ''active'')', app_schema);

    -- Policy: Users can read their own packages
    EXECUTE format('
        CREATE POLICY "r2_packages_select_own" ON %I.r2_packages
        FOR SELECT
        USING (auth.uid() = uploader_id)', app_schema);

    -- Policy: Authenticated users can insert packages
    EXECUTE format('
        CREATE POLICY "r2_packages_insert_auth" ON %I.r2_packages
        FOR INSERT
        WITH CHECK (auth.uid() = uploader_id)', app_schema);

    -- Policy: Users can update their own packages
    EXECUTE format('
        CREATE POLICY "r2_packages_update_own" ON %I.r2_packages
        FOR UPDATE
        USING (auth.uid() = uploader_id)', app_schema);

    -- Policy: Users can delete their own packages (soft delete via status)
    EXECUTE format('
        CREATE POLICY "r2_packages_delete_own" ON %I.r2_packages
        FOR UPDATE
        USING (auth.uid() = uploader_id AND status = ''deleted'')', app_schema);

    -- Policy: Users can view download history of their packages
    EXECUTE format('
        CREATE POLICY "r2_downloads_select_own_packages" ON %I.r2_package_downloads
        FOR SELECT
        USING (
            EXISTS (
                SELECT 1 FROM %I.r2_packages
                WHERE id = package_id AND uploader_id = auth.uid()
            )
        )', app_schema, app_schema);

    -- Policy: System can insert download records (via function)
    EXECUTE format('
        CREATE POLICY "r2_downloads_insert_system" ON %I.r2_package_downloads
        FOR INSERT
        WITH CHECK (true)', app_schema);

    RAISE NOTICE 'Created RLS policies for schema: %', app_schema;
END $$;

-- 14. Grant necessary permissions
DO $$
DECLARE
    app_schema TEXT := get_schema_name();
BEGIN
    EXECUTE format('GRANT SELECT, INSERT, UPDATE ON %I.r2_packages TO authenticated', app_schema);
    EXECUTE format('GRANT SELECT, INSERT ON %I.r2_package_downloads TO authenticated', app_schema);
    EXECUTE format('GRANT USAGE ON ALL SEQUENCES IN SCHEMA %I TO authenticated', app_schema);

    EXECUTE format('GRANT SELECT, INSERT, UPDATE ON %I.r2_packages TO service_role', app_schema);
    EXECUTE format('GRANT SELECT, INSERT ON %I.r2_package_downloads TO service_role', app_schema);
    EXECUTE format('GRANT USAGE ON ALL SEQUENCES IN SCHEMA %I TO service_role', app_schema);

    RAISE NOTICE 'Granted permissions for schema: %', app_schema;
END $$;

-- 15. Add comments for documentation
DO $$
DECLARE
    app_schema TEXT := get_schema_name();
BEGIN
    EXECUTE format('COMMENT ON TABLE %I.r2_packages IS ''Software packages stored in Cloudflare R2 with version management''', app_schema);
    EXECUTE format('COMMENT ON TABLE %I.r2_package_downloads IS ''Download history tracking for R2 packages''', app_schema);
END $$;

COMMENT ON FUNCTION record_r2_package_download IS 'Records a package download and increments counter';
COMMENT ON FUNCTION get_r2_package_stats IS 'Returns aggregated statistics for packages';
COMMENT ON FUNCTION cleanup_old_r2_packages IS 'Marks old archived packages as deleted for cleanup';
COMMENT ON FUNCTION search_r2_packages IS 'Full-text search across package names, descriptions, and tags';
COMMENT ON FUNCTION get_r2_package_versions IS 'Returns all versions of a specific package with pagination';

-- 16. Create view for package overview
DO $$
DECLARE
    app_schema TEXT := get_schema_name();
BEGIN
    EXECUTE format('DROP VIEW IF EXISTS %I.r2_packages_overview', app_schema);
    EXECUTE format('
        CREATE VIEW %I.r2_packages_overview AS
        SELECT
            p.id,
            p.package_name,
            p.version,
            p.description,
            p.tags,
            p.is_public,
            p.file_size,
            p.download_count,
            p.status,
            p.created_at,
            u.email as uploader_email
        FROM %I.r2_packages p
        JOIN auth.users u ON p.uploader_id = u.id
        WHERE p.status = ''active''', app_schema, app_schema);

    EXECUTE format('COMMENT ON VIEW %I.r2_packages_overview IS ''Convenient view of active packages with uploader information''', app_schema);

    RAISE NOTICE 'Created view: %.r2_packages_overview', app_schema;
END $$;

-- 17. Grant function execution permissions
GRANT EXECUTE ON FUNCTION update_r2_package_updated_at() TO service_role;
GRANT EXECUTE ON FUNCTION record_r2_package_download(UUID, UUID, INET, TEXT) TO service_role;
GRANT EXECUTE ON FUNCTION get_r2_package_stats(TEXT) TO service_role;
GRANT EXECUTE ON FUNCTION cleanup_old_r2_packages(INTEGER) TO service_role;
GRANT EXECUTE ON FUNCTION search_r2_packages(TEXT, TEXT[], BOOLEAN, INTEGER, INTEGER) TO service_role;
GRANT EXECUTE ON FUNCTION get_r2_package_versions(TEXT, INTEGER, INTEGER) TO service_role;

GRANT EXECUTE ON FUNCTION record_r2_package_download(UUID, UUID, INET, TEXT) TO authenticated;
GRANT EXECUTE ON FUNCTION get_r2_package_stats(TEXT) TO authenticated;
GRANT EXECUTE ON FUNCTION search_r2_packages(TEXT, TEXT[], BOOLEAN, INTEGER, INTEGER) TO authenticated;
GRANT EXECUTE ON FUNCTION get_r2_package_versions(TEXT, INTEGER, INTEGER) TO authenticated;

-- 18. CRUD Functions for schema-agnostic operations

-- Function: Create package
CREATE OR REPLACE FUNCTION create_r2_package(
    p_package_name TEXT,
    p_version TEXT,
    p_r2_key TEXT,
    p_file_size BIGINT,
    p_file_hash TEXT,
    p_hash_algorithm TEXT,
    p_uploader_id UUID,
    p_description TEXT DEFAULT NULL,
    p_tags JSONB DEFAULT '[]'::jsonb,
    p_is_public BOOLEAN DEFAULT false,
    p_metadata JSONB DEFAULT '{}'::jsonb
)
RETURNS TABLE (
    id UUID,
    package_name TEXT,
    version TEXT,
    r2_key TEXT,
    file_size BIGINT,
    file_hash TEXT,
    hash_algorithm TEXT,
    uploader_id UUID,
    description TEXT,
    tags JSONB,
    is_public BOOLEAN,
    download_count INTEGER,
    status TEXT,
    metadata JSONB,
    created_at TIMESTAMPTZ,
    updated_at TIMESTAMPTZ
) AS $$
DECLARE
    app_schema TEXT := get_schema_name();
BEGIN
    RETURN QUERY EXECUTE format('
        INSERT INTO %I.r2_packages (
            package_name, version, r2_key, file_size, file_hash, hash_algorithm,
            uploader_id, description, tags, is_public, metadata
        )
        VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11)
        RETURNING id, package_name, version, r2_key, file_size, file_hash, hash_algorithm,
                  uploader_id, description, tags, is_public, download_count, status, metadata,
                  created_at, updated_at', app_schema)
    USING p_package_name, p_version, p_r2_key, p_file_size, p_file_hash, p_hash_algorithm,
          p_uploader_id, p_description, p_tags, p_is_public, p_metadata;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- Function: Get package by ID
CREATE OR REPLACE FUNCTION get_r2_package_by_id(p_package_id UUID)
RETURNS TABLE (
    id UUID,
    package_name TEXT,
    version TEXT,
    r2_key TEXT,
    file_size BIGINT,
    file_hash TEXT,
    hash_algorithm TEXT,
    uploader_id UUID,
    description TEXT,
    tags JSONB,
    is_public BOOLEAN,
    download_count INTEGER,
    status TEXT,
    metadata JSONB,
    created_at TIMESTAMPTZ,
    updated_at TIMESTAMPTZ
) AS $$
DECLARE
    app_schema TEXT := get_schema_name();
BEGIN
    RETURN QUERY EXECUTE format('
        SELECT id, package_name, version, r2_key, file_size, file_hash, hash_algorithm,
               uploader_id, description, tags, is_public, download_count, status, metadata,
               created_at, updated_at
        FROM %I.r2_packages
        WHERE id = $1', app_schema)
    USING p_package_id;
END;
$$ LANGUAGE plpgsql;

-- Function: Get package by name and version
CREATE OR REPLACE FUNCTION get_r2_package(
    p_package_name TEXT,
    p_version TEXT
)
RETURNS TABLE (
    id UUID,
    package_name TEXT,
    version TEXT,
    r2_key TEXT,
    file_size BIGINT,
    file_hash TEXT,
    hash_algorithm TEXT,
    uploader_id UUID,
    description TEXT,
    tags JSONB,
    is_public BOOLEAN,
    download_count INTEGER,
    status TEXT,
    metadata JSONB,
    created_at TIMESTAMPTZ,
    updated_at TIMESTAMPTZ
) AS $$
DECLARE
    app_schema TEXT := get_schema_name();
BEGIN
    RETURN QUERY EXECUTE format('
        SELECT id, package_name, version, r2_key, file_size, file_hash, hash_algorithm,
               uploader_id, description, tags, is_public, download_count, status, metadata,
               created_at, updated_at
        FROM %I.r2_packages
        WHERE package_name = $1
          AND version = $2
          AND status = ''active''', app_schema)
    USING p_package_name, p_version;
END;
$$ LANGUAGE plpgsql;

-- Function: Update package metadata
CREATE OR REPLACE FUNCTION update_r2_package(
    p_package_id UUID,
    p_description TEXT DEFAULT NULL,
    p_tags JSONB DEFAULT NULL,
    p_is_public BOOLEAN DEFAULT NULL,
    p_status TEXT DEFAULT NULL,
    p_metadata JSONB DEFAULT NULL
)
RETURNS TABLE (
    id UUID,
    package_name TEXT,
    version TEXT,
    r2_key TEXT,
    file_size BIGINT,
    file_hash TEXT,
    hash_algorithm TEXT,
    uploader_id UUID,
    description TEXT,
    tags JSONB,
    is_public BOOLEAN,
    download_count INTEGER,
    status TEXT,
    metadata JSONB,
    created_at TIMESTAMPTZ,
    updated_at TIMESTAMPTZ
) AS $$
DECLARE
    app_schema TEXT := get_schema_name();
    update_query TEXT;
BEGIN
    update_query := format('UPDATE %I.r2_packages SET ', app_schema);

    IF p_description IS NOT NULL THEN
        update_query := update_query || 'description = $1, ';
    END IF;
    IF p_tags IS NOT NULL THEN
        update_query := update_query || 'tags = $2, ';
    END IF;
    IF p_is_public IS NOT NULL THEN
        update_query := update_query || 'is_public = $3, ';
    END IF;
    IF p_status IS NOT NULL THEN
        update_query := update_query || 'status = $4, ';
    END IF;
    IF p_metadata IS NOT NULL THEN
        update_query := update_query || 'metadata = $5, ';
    END IF;

    -- Remove trailing comma and space
    update_query := RTRIM(update_query, ', ');
    update_query := update_query || format(' WHERE id = $6 RETURNING id, package_name, version, r2_key, file_size, file_hash, hash_algorithm, uploader_id, description, tags, is_public, download_count, status, metadata, created_at, updated_at');

    RETURN QUERY EXECUTE update_query
    USING p_description, p_tags, p_is_public, p_status, p_metadata, p_package_id;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- Function: Delete package (soft or hard delete)
CREATE OR REPLACE FUNCTION delete_r2_package(
    p_package_id UUID,
    p_hard_delete BOOLEAN DEFAULT false
)
RETURNS BOOLEAN AS $$
DECLARE
    app_schema TEXT := get_schema_name();
    rows_affected INTEGER;
BEGIN
    IF p_hard_delete THEN
        -- Hard delete: permanently remove from database
        EXECUTE format('DELETE FROM %I.r2_packages WHERE id = $1', app_schema)
        USING p_package_id;
    ELSE
        -- Soft delete: mark as deleted
        EXECUTE format('UPDATE %I.r2_packages SET status = ''deleted'' WHERE id = $1', app_schema)
        USING p_package_id;
    END IF;

    GET DIAGNOSTICS rows_affected = ROW_COUNT;
    RETURN rows_affected > 0;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- Function: List user packages
CREATE OR REPLACE FUNCTION list_user_r2_packages(
    p_user_id UUID,
    p_limit INTEGER DEFAULT 50,
    p_offset INTEGER DEFAULT 0
)
RETURNS TABLE (
    id UUID,
    package_name TEXT,
    version TEXT,
    r2_key TEXT,
    file_size BIGINT,
    file_hash TEXT,
    hash_algorithm TEXT,
    uploader_id UUID,
    description TEXT,
    tags JSONB,
    is_public BOOLEAN,
    download_count INTEGER,
    status TEXT,
    metadata JSONB,
    created_at TIMESTAMPTZ,
    updated_at TIMESTAMPTZ
) AS $$
DECLARE
    app_schema TEXT := get_schema_name();
BEGIN
    RETURN QUERY EXECUTE format('
        SELECT id, package_name, version, r2_key, file_size, file_hash, hash_algorithm,
               uploader_id, description, tags, is_public, download_count, status, metadata,
               created_at, updated_at
        FROM %I.r2_packages
        WHERE uploader_id = $1
          AND status = ''active''
        ORDER BY created_at DESC
        LIMIT $2 OFFSET $3', app_schema)
    USING p_user_id, p_limit, p_offset;
END;
$$ LANGUAGE plpgsql;

-- Function: List public packages
CREATE OR REPLACE FUNCTION list_public_r2_packages(
    p_limit INTEGER DEFAULT 50,
    p_offset INTEGER DEFAULT 0
)
RETURNS TABLE (
    id UUID,
    package_name TEXT,
    version TEXT,
    r2_key TEXT,
    file_size BIGINT,
    file_hash TEXT,
    hash_algorithm TEXT,
    uploader_id UUID,
    description TEXT,
    tags JSONB,
    is_public BOOLEAN,
    download_count INTEGER,
    status TEXT,
    metadata JSONB,
    created_at TIMESTAMPTZ,
    updated_at TIMESTAMPTZ
) AS $$
DECLARE
    app_schema TEXT := get_schema_name();
BEGIN
    RETURN QUERY EXECUTE format('
        SELECT id, package_name, version, r2_key, file_size, file_hash, hash_algorithm,
               uploader_id, description, tags, is_public, download_count, status, metadata,
               created_at, updated_at
        FROM %I.r2_packages
        WHERE is_public = true
          AND status = ''active''
        ORDER BY created_at DESC
        LIMIT $1 OFFSET $2', app_schema)
    USING p_limit, p_offset;
END;
$$ LANGUAGE plpgsql;

-- Function: Check package exists
CREATE OR REPLACE FUNCTION check_r2_package_exists(
    p_package_name TEXT,
    p_version TEXT
)
RETURNS BOOLEAN AS $$
DECLARE
    app_schema TEXT := get_schema_name();
    package_count INTEGER;
BEGIN
    EXECUTE format('
        SELECT COUNT(*) FROM %I.r2_packages
        WHERE package_name = $1
          AND version = $2
          AND status != ''deleted''', app_schema)
    INTO package_count
    USING p_package_name, p_version;

    RETURN package_count > 0;
END;
$$ LANGUAGE plpgsql;

-- Function: Get download history
CREATE OR REPLACE FUNCTION get_r2_download_history(
    p_package_id UUID,
    p_limit INTEGER DEFAULT 50,
    p_offset INTEGER DEFAULT 0
)
RETURNS TABLE (
    id UUID,
    package_id UUID,
    user_id UUID,
    ip_address INET,
    user_agent TEXT,
    downloaded_at TIMESTAMPTZ
) AS $$
DECLARE
    app_schema TEXT := get_schema_name();
BEGIN
    RETURN QUERY EXECUTE format('
        SELECT id, package_id, user_id, ip_address, user_agent, downloaded_at
        FROM %I.r2_package_downloads
        WHERE package_id = $1
        ORDER BY downloaded_at DESC
        LIMIT $2 OFFSET $3', app_schema)
    USING p_package_id, p_limit, p_offset;
END;
$$ LANGUAGE plpgsql;

-- 19. Grant execution permissions for new functions
GRANT EXECUTE ON FUNCTION create_r2_package(TEXT, TEXT, TEXT, BIGINT, TEXT, TEXT, UUID, TEXT, JSONB, BOOLEAN, JSONB) TO service_role;
GRANT EXECUTE ON FUNCTION get_r2_package_by_id(UUID) TO service_role, authenticated;
GRANT EXECUTE ON FUNCTION get_r2_package(TEXT, TEXT) TO service_role, authenticated;
GRANT EXECUTE ON FUNCTION update_r2_package(UUID, TEXT, JSONB, BOOLEAN, TEXT, JSONB) TO service_role;
GRANT EXECUTE ON FUNCTION delete_r2_package(UUID, BOOLEAN) TO service_role;
GRANT EXECUTE ON FUNCTION list_user_r2_packages(UUID, INTEGER, INTEGER) TO service_role, authenticated;
GRANT EXECUTE ON FUNCTION list_public_r2_packages(INTEGER, INTEGER) TO service_role, authenticated, anon;
GRANT EXECUTE ON FUNCTION check_r2_package_exists(TEXT, TEXT) TO service_role, authenticated;
GRANT EXECUTE ON FUNCTION get_r2_download_history(UUID, INTEGER, INTEGER) TO service_role, authenticated;

-- 20. Add function comments
COMMENT ON FUNCTION create_r2_package IS 'Creates a new package record in the configured schema';
COMMENT ON FUNCTION get_r2_package_by_id IS 'Retrieves package by UUID';
COMMENT ON FUNCTION get_r2_package IS 'Retrieves active package by name and version';
COMMENT ON FUNCTION update_r2_package IS 'Updates package metadata fields';
COMMENT ON FUNCTION delete_r2_package IS 'Deletes package (soft delete by default)';
COMMENT ON FUNCTION list_user_r2_packages IS 'Lists all packages uploaded by a specific user';
COMMENT ON FUNCTION list_public_r2_packages IS 'Lists all public packages';
COMMENT ON FUNCTION check_r2_package_exists IS 'Checks if a package version exists';
COMMENT ON FUNCTION get_r2_download_history IS 'Retrieves download history for a package';

-- Success message
DO $$
DECLARE
    app_schema TEXT := get_schema_name();
BEGIN
    RAISE NOTICE '====================================================';
    RAISE NOTICE 'R2 Package Management System schema created successfully';
    RAISE NOTICE 'Schema: %', app_schema;
    RAISE NOTICE 'Tables: %.r2_packages, %.r2_package_downloads', app_schema, app_schema;
    RAISE NOTICE 'Functions: 15 package management functions (6 existing + 9 CRUD)';
    RAISE NOTICE 'RLS Policies: 7 security policies';
    RAISE NOTICE 'View: %.r2_packages_overview', app_schema;
    RAISE NOTICE '====================================================';
END $$;

-- ===== /root/self_code/web_backend/center_management/db/migration/sql_schema_migration/20251017210447_r2_fix_tags_double_serialization.sql =====
-- =====================================================
-- Fix R2 Package Tags Double-Serialization Issue
-- =====================================================
-- Description: Fixes tags field that were double-serialized as JSON strings
--              instead of proper JSONB arrays
-- Bug: Tags stored as "[\"production\"]" instead of ["production"]
-- Created: 2025-10-17
-- Updated: 2025-10-17 - Renamed to 11_r2_fix_tags_double_serialization.sql
-- Dependencies: Requires 10_r2_package_system.sql to be run first

-- Fix tags double-serialization in r2_packages table
DO $$
DECLARE
    app_schema TEXT := get_schema_name();
    affected_count INTEGER := 0;
BEGIN
    -- Fix tags that are stored as JSON strings instead of JSONB arrays
    -- Pattern: tags value starts with a quote followed by [ (indicating string-wrapped JSON)
    -- We need to extract the string value first, then parse it as JSONB
    EXECUTE format('
        UPDATE %I.r2_packages
        SET tags = CASE
            -- If tags is a JSONB string (jsonb_typeof returns ''string''), extract and parse it
            WHEN jsonb_typeof(tags) = ''string'' THEN (tags #>> ''{}''::text[])::jsonb
            -- Otherwise keep as-is (already correct JSONB array)
            ELSE tags
        END
        WHERE jsonb_typeof(tags) = ''string''
    ', app_schema);

    GET DIAGNOSTICS affected_count = ROW_COUNT;

    RAISE NOTICE 'Fixed % packages with double-serialized tags in schema: %', affected_count, app_schema;

    -- Verify the fix by showing sample tags
    EXECUTE format('
        SELECT package_name, version, tags
        FROM %I.r2_packages
        LIMIT 5
    ', app_schema);

END $$;

-- Add comment
COMMENT ON FUNCTION get_schema_name IS 'Migration script to fix double-serialized tags in R2 packages';

-- Success message
DO $$
DECLARE
    app_schema TEXT := get_schema_name();
BEGIN
    RAISE NOTICE '====================================================';
    RAISE NOTICE 'R2 Package Tags Double-Serialization Fix Applied';
    RAISE NOTICE 'Schema: %', app_schema;
    RAISE NOTICE 'All tags fields have been corrected to proper JSONB format';
    RAISE NOTICE '====================================================';
END $$;

-- ===== /root/self_code/web_backend/center_management/db/migration/sql_schema_migration/20251022113527_create_admin_user.sql =====
-- Create admin user for R2 package management
-- This migration creates a system admin user for managing packages
--
-- IMPORTANT: This migration only creates the user structure.
-- The admin password must be set separately using Supabase Auth API or Dashboard.
-- See instructions at the bottom of this file for password setup.

-- Create a fixed UUID for the admin user
-- Using a deterministic UUID for consistency across environments
CREATE EXTENSION IF NOT EXISTS pgcrypto;
DO $$
DECLARE
  admin_user_id UUID := 'a0000000-0000-0000-0000-000000000001';
  admin_email TEXT := 'admin@local.com';
BEGIN
  -- Check if user already exists
  IF NOT EXISTS (SELECT 1 FROM auth.users WHERE id = admin_user_id) THEN
    -- Insert admin user into auth.users with empty password
    -- Password will be set via Supabase Auth API after migration
    INSERT INTO auth.users (
      id,
      instance_id,
      email,
      encrypted_password,
      email_confirmed_at,
      created_at,
      updated_at,
      role,
      aud,
      confirmation_token,
      recovery_token,
      email_change_token_new,
      email_change
    ) VALUES (
      admin_user_id,
      '00000000-0000-0000-0000-000000000000',
      admin_email,
      '', -- Password will be set via Supabase Auth API
      NOW(),
      NOW(),
      NOW(),
      'authenticated',
      'authenticated',
      '',
      '',
      '',
      ''
    );

    -- Insert identity for the user (required for Supabase Auth)
    -- Note: email is a generated column and should not be manually inserted
    INSERT INTO auth.identities (
      id,
      provider_id,
      user_id,
      identity_data,
      provider,
      last_sign_in_at,
      created_at,
      updated_at
    ) VALUES (
      gen_random_uuid(),
      admin_user_id::text, -- provider_id is required and must be text
      admin_user_id,
      jsonb_build_object(
        'sub', admin_user_id::text,
        'email', admin_email,
        'email_verified', true,
        'phone_verified', false
      ),
      'email',
      NOW(),
      NOW(),
      NOW()
    );

    RAISE NOTICE 'Admin user created with email: %', admin_email;
    RAISE NOTICE 'Password must be set via Supabase Auth API or Dashboard before login!';
  ELSE
    RAISE NOTICE 'Admin user already exists with email: %', admin_email;
  END IF;
END $$;

-- Comment for documentation
COMMENT ON EXTENSION pgcrypto IS 'Used for UUID generation and cryptographic functions';

-- Verify the user was created
DO $$
BEGIN
  IF EXISTS (SELECT 1 FROM auth.users WHERE email = 'admin@local.com') THEN
    RAISE NOTICE '✓ Admin user structure created successfully';
  ELSE
    RAISE EXCEPTION '✗ Admin user creation failed';
  END IF;
END $$;

-- ================================================================================
-- PASSWORD SETUP INSTRUCTIONS
-- ================================================================================
--
-- This migration creates the admin user structure but does NOT set a password.
-- You MUST set the admin password using one of these methods:
--
-- METHOD 1: Supabase Dashboard (Recommended for initial setup)
-- 1. Go to your Supabase project dashboard
-- 2. Navigate to Authentication > Users
-- 3. Find the admin@local.com user
-- 4. Click "Reset password" and set a secure password
--
-- METHOD 2: Supabase Client API (For automated deployment)
--
-- /*
-- import { createClient } from '@supabase/supabase-js'
--
-- const supabase = createClient(
--   'your-project-url',
--   'your-service-role-key'
-- )
--
-- async function setAdminPassword() {
--   const { data, error } = await supabase.auth.admin.updateUserById(
--     'a0000000-0000-0000-0000-000000000001',
--     { password: 'your-secure-password-here' }
--   )
--
--   if (error) {
--     console.error('Failed to set admin password:', error)
--   } else {
--     console.log('Admin password set successfully')
--   }
-- }
--
-- setAdminPassword()
-- */
--
-- SECURITY NOTES:
-- - Use a strong password (12+ characters, mixed case, numbers, symbols)
-- - Change the default email from admin@local.com in production
-- - Store the password securely in your environment variables or vault
-- - Consider using multi-factor authentication for admin accounts
--
-- ================================================================================

-- ===== /root/self_code/web_backend/center_management/db/migration/sql_schema_migration/20251022113528_r2_init.sql =====
-- =====================================================
-- R2 packages 初始化数据脚本
-- =====================================================
-- 功能：向 r2_packages 表中插入初始包数据
-- 使用方法：psql -v ON_ERROR_STOP=1 -f 20251022113528_r2_init.sql
-- =====================================================
-- 前置依赖：
--   1. 必须先执行 00_schema_init.sql 初始化 schema 配置
--   2. 必须先执行 10_r2_package_system.sql 创建 r2_packages 表
--   3. 必须先执行 20251022113527_create_admin_user.sql 创建管理员用户
-- =====================================================

-- Admin user UUID (must match the one created in 20251022113527_create_admin_user.sql)
-- This ensures proper foreign key relationships
DO $$
DECLARE
  app_schema TEXT := get_schema_name();
  admin_user_id UUID := 'a0000000-0000-0000-0000-000000000001';
BEGIN
  -- Verify admin user exists before inserting packages
  IF NOT EXISTS (SELECT 1 FROM auth.users WHERE id = admin_user_id) THEN
    RAISE EXCEPTION 'Admin user not found. Please run 20251022113527_create_admin_user.sql first';
  END IF;

  -- Insert R2 package records
  -- Using INSERT with ON CONFLICT to make this migration idempotent
  EXECUTE format('
    INSERT INTO %I.r2_packages (
      id,
      package_name,
      version,
      r2_key,
      file_size,
      file_hash,
      hash_algorithm,
      description,
      tags,
      is_public,
      uploader_id,
      download_count,
      status,
      metadata,
      created_at,
      updated_at
    ) VALUES
    -- Package 1: v2rayN Android APK
    (
      $1,
      ''v2rayN_android.apk'',
      ''1.0.0'',
      ''packages/v2rayN_android.apk/1.0.0/v2rayN_android.apk'',
      35654848,
      ''093a2fe5322e95994fcca2cf442e8569843aa365844fd3f0f2e1424ee16b39ec'',
      ''sha256'',
      NULL,
      ''["production"]''::jsonb,
      FALSE,
      $3,
      5,
      ''active'',
      ''{}''::jsonb,
      ''2025-10-16 23:46:08.939376+08''::timestamptz,
      ''2025-10-19 23:54:09.762063+08''::timestamptz
    ),
    -- Package 2: v2rayN Windows ZIP
    (
      $2,
      ''v2rayN_windows.zip'',
      ''1.0.0'',
      ''packages/v2rayN_windows.zip/1.0.0/v2rayN_windows.zip'',
      105194701,
      ''be3d10425c2d02a9de3065e3b07644505f3edfb40a0a2dddb7f6662d7414dbcd'',
      ''sha256'',
      ''v2rayN for windows'',
      ''["production"]''::jsonb,
      FALSE,
      $3,
      15,
      ''active'',
      ''{}''::jsonb,
      ''2025-10-17 14:09:39.986945+08''::timestamptz,
      ''2025-10-19 23:54:09.464797+08''::timestamptz
    )
    ON CONFLICT (id) DO UPDATE SET
      uploader_id = EXCLUDED.uploader_id,
      updated_at = NOW()
  ', app_schema)
  USING
    '01b9a3b5-6186-4f5a-8c6f-1f2626efb509'::uuid,  -- $1: Package 1 ID
    '05ce3687-c358-4d60-84e7-07e2a89393f3'::uuid,  -- $2: Package 2 ID
    admin_user_id;                                   -- $3: Admin user ID for uploader_id

  RAISE NOTICE '✓ Successfully inserted/updated % R2 packages', 2;
END $$;

-- Verify the data was inserted correctly
DO $$
DECLARE
  app_schema TEXT := get_schema_name();
  package_count INTEGER;
  admin_user_id UUID := 'a0000000-0000-0000-0000-000000000001';
BEGIN
  -- Count packages owned by admin
  EXECUTE format('
    SELECT COUNT(*) FROM %I.r2_packages WHERE uploader_id = $1
  ', app_schema) INTO package_count USING admin_user_id;

  IF package_count >= 2 THEN
    RAISE NOTICE '✓ Verification successful: % packages found for admin user', package_count;
  ELSE
    RAISE WARNING '⚠ Expected at least 2 packages for admin user, found %', package_count;
  END IF;

  -- Verify r2_packages_overview view has data
  EXECUTE format('
    SELECT COUNT(*) FROM %I.r2_packages_overview WHERE uploader_email = $1
  ', app_schema) INTO package_count USING 'admin@localhost';

  IF package_count >= 2 THEN
    RAISE NOTICE '✓ View verification successful: % packages in r2_packages_overview', package_count;
  ELSE
    RAISE WARNING '⚠ Expected at least 2 packages in overview, found %', package_count;
  END IF;

  -- Add helpful comments
  EXECUTE format('COMMENT ON TABLE %I.r2_packages IS ''Storage for R2 package metadata with version control''', app_schema);

  RAISE NOTICE '====================================================';
  RAISE NOTICE 'R2 packages initialization completed successfully';
  RAISE NOTICE 'Schema: %', app_schema;
  RAISE NOTICE 'Packages inserted: 2';
  RAISE NOTICE '====================================================';
END $$;

-- ===== /root/self_code/web_backend/center_management/db/migration/sql_schema_migration/20251023211114_stripe_integration.sql =====
-- =====================================================
-- Stripe 支付集成迁移
-- =====================================================
-- 功能：扩展订单表以支持 Stripe 支付
-- 使用方法: psql -v ON_ERROR_STOP=1 -f 12_stripe_integration.sql
-- =====================================================
-- 前置依赖：
--   必须先执行 01_order_refactored.sql 创建订单表
-- =====================================================

-- 1. 添加 Stripe 相关字段到 order 表
DO $$
DECLARE
    app_schema TEXT := get_schema_name();
BEGIN
    -- 添加支付提供商字段（默认为 h5zhifu 保持向后兼容）
    EXECUTE format('
        ALTER TABLE %I.order
        ADD COLUMN IF NOT EXISTS payment_provider text DEFAULT ''h5zhifu'',
        ADD COLUMN IF NOT EXISTS stripe_payment_intent_id text,
        ADD COLUMN IF NOT EXISTS stripe_customer_id text,
        ADD COLUMN IF NOT EXISTS stripe_payment_status text
    ', app_schema);

    RAISE NOTICE 'Added Stripe fields to order table in schema: %', app_schema;
END $$;

-- 2. 创建索引以优化 Stripe 相关查询
DO $$
DECLARE
    app_schema TEXT := get_schema_name();
BEGIN
    EXECUTE format('
        CREATE INDEX IF NOT EXISTS idx_order_payment_provider
        ON %I.order(payment_provider)
    ', app_schema);

    EXECUTE format('
        CREATE INDEX IF NOT EXISTS idx_order_stripe_payment_intent
        ON %I.order(stripe_payment_intent_id)
        WHERE stripe_payment_intent_id IS NOT NULL
    ', app_schema);

    EXECUTE format('
        CREATE INDEX IF NOT EXISTS idx_order_stripe_customer
        ON %I.order(stripe_customer_id)
        WHERE stripe_customer_id IS NOT NULL
    ', app_schema);

    RAISE NOTICE 'Created Stripe-related indexes in schema: %', app_schema;
END $$;

-- 3. 创建 Stripe 订单插入函数
CREATE OR REPLACE FUNCTION insert_stripe_order(
    p_product_name text,
    p_trade_num int4,
    p_amount int4,
    p_email text,
    p_phone text,
    p_stripe_payment_intent_id text,
    p_stripe_customer_id text DEFAULT NULL
)
RETURNS uuid
LANGUAGE plpgsql
AS $$
DECLARE
    new_id uuid;
    check_time timestamp with time zone;
    app_schema TEXT := get_schema_name();
BEGIN
    -- 插入 Stripe 订单
    EXECUTE format('
        INSERT INTO %I.order (
            product_name,
            trade_num,
            amount,
            email,
            phone,
            payment_provider,
            stripe_payment_intent_id,
            stripe_customer_id,
            stripe_payment_status
        )
        VALUES (%L, %L, %L, %L, %L, %L, %L, %L, %L)
        RETURNING id',
        app_schema,
        p_product_name,
        p_trade_num,
        p_amount,
        p_email,
        p_phone,
        'stripe',
        p_stripe_payment_intent_id,
        p_stripe_customer_id,
        'pending'
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

-- 4. 创建更新 Stripe 支付状态函数
CREATE OR REPLACE FUNCTION update_stripe_payment_status(
    p_stripe_payment_intent_id text,
    p_stripe_payment_status text,
    p_order_status text DEFAULT NULL
)
RETURNS boolean
LANGUAGE plpgsql
AS $$
DECLARE
    rows_affected integer;
    app_schema TEXT := get_schema_name();
    final_order_status text;
BEGIN
    -- 如果未提供订单状态，根据支付状态自动设置
    IF p_order_status IS NULL THEN
        CASE p_stripe_payment_status
            WHEN 'succeeded' THEN final_order_status := '已支付';
            WHEN 'processing' THEN final_order_status := '处理中';
            WHEN 'requires_payment_method' THEN final_order_status := '待支付';
            WHEN 'canceled' THEN final_order_status := '已取消';
            ELSE final_order_status := '处理中';
        END CASE;
    ELSE
        final_order_status := p_order_status;
    END IF;

    EXECUTE format('
        UPDATE %I.order
        SET stripe_payment_status = %L,
            status = %L
        WHERE stripe_payment_intent_id = %L',
        app_schema,
        p_stripe_payment_status,
        final_order_status,
        p_stripe_payment_intent_id
    );

    GET DIAGNOSTICS rows_affected = ROW_COUNT;
    RETURN rows_affected > 0;
END;
$$;

-- 5. 创建通过 Stripe Payment Intent ID 查询订单函数
CREATE OR REPLACE FUNCTION get_order_by_stripe_payment_intent(
    p_stripe_payment_intent_id text
)
RETURNS TABLE (
    id uuid,
    product_name text,
    trade_num int4,
    amount int4,
    email text,
    phone text,
    status text,
    payment_provider text,
    stripe_payment_intent_id text,
    stripe_customer_id text,
    stripe_payment_status text,
    created_at timestamptz
)
LANGUAGE plpgsql
STABLE
AS $$
DECLARE
    app_schema TEXT := get_schema_name();
BEGIN
    RETURN QUERY EXECUTE format('
        SELECT
            id,
            product_name,
            trade_num,
            amount,
            email,
            phone,
            status,
            payment_provider,
            stripe_payment_intent_id,
            stripe_customer_id,
            stripe_payment_status,
            created_at
        FROM %I.order
        WHERE stripe_payment_intent_id = %L',
        app_schema, p_stripe_payment_intent_id
    );
END;
$$;

-- 6. 创建通过 Stripe Customer ID 查询订单函数
CREATE OR REPLACE FUNCTION get_orders_by_stripe_customer(
    p_stripe_customer_id text
)
RETURNS TABLE (
    id uuid,
    product_name text,
    trade_num int4,
    amount int4,
    email text,
    phone text,
    status text,
    stripe_payment_intent_id text,
    stripe_payment_status text,
    created_at timestamptz
)
LANGUAGE plpgsql
STABLE
AS $$
DECLARE
    app_schema TEXT := get_schema_name();
BEGIN
    RETURN QUERY EXECUTE format('
        SELECT
            id,
            product_name,
            trade_num,
            amount,
            email,
            phone,
            status,
            stripe_payment_intent_id,
            stripe_payment_status,
            created_at
        FROM %I.order
        WHERE stripe_customer_id = %L
        ORDER BY created_at DESC',
        app_schema, p_stripe_customer_id
    );
END;
$$;

-- 7. 设置权限
DO $$
DECLARE
    app_schema TEXT := get_schema_name();
BEGIN
    EXECUTE format('GRANT SELECT, UPDATE ON %I.order TO service_role', app_schema);
END $$;

GRANT EXECUTE ON FUNCTION insert_stripe_order(text, int4, int4, text, text, text, text) TO service_role;
GRANT EXECUTE ON FUNCTION update_stripe_payment_status(text, text, text) TO service_role;
GRANT EXECUTE ON FUNCTION get_order_by_stripe_payment_intent(text) TO service_role;
GRANT EXECUTE ON FUNCTION get_orders_by_stripe_customer(text) TO service_role;
GRANT EXECUTE ON FUNCTION get_schema_name() TO service_role;

-- 8. 完成提示
DO $$
DECLARE
    app_schema TEXT := get_schema_name();
BEGIN
    RAISE NOTICE '=================================================';
    RAISE NOTICE 'Stripe integration migration completed successfully';
    RAISE NOTICE 'Schema: %', app_schema;
    RAISE NOTICE '=================================================';
    RAISE NOTICE 'Added fields:';
    RAISE NOTICE '  - payment_provider (default: h5zhifu)';
    RAISE NOTICE '  - stripe_payment_intent_id';
    RAISE NOTICE '  - stripe_customer_id';
    RAISE NOTICE '  - stripe_payment_status';
    RAISE NOTICE '=================================================';
    RAISE NOTICE 'New functions available:';
    RAISE NOTICE '  - insert_stripe_order()';
    RAISE NOTICE '  - update_stripe_payment_status()';
    RAISE NOTICE '  - get_order_by_stripe_payment_intent()';
    RAISE NOTICE '  - get_orders_by_stripe_customer()';
    RAISE NOTICE '=================================================';
END $$;

-- ===== /root/self_code/web_backend/center_management/db/migration/sql_schema_migration/20251023220517_fix_table_ownership.sql =====
-- =====================================================
-- 修复表所有权迁移（作为 supabase_admin 运行）
-- =====================================================
-- 功能：将 order 和 order_timeout_tracker 表的所有权统一为 postgres 用户
-- 原因：某些表由 supabase_admin 创建，导致后续迁移失败
-- 使用方法:
--   使用 supabase_admin 运行（推荐）:
--     PGPASSWORD=... psql -U supabase_admin -d postgres -f 11_fix_table_ownership.sql
--   或在现有连接中以 supabase_admin 身份执行（通过 SET ROLE）
-- =====================================================

-- 临时切换到 supabase_admin 角色以执行所有权转移
DO $$
DECLARE
    app_schema TEXT := get_schema_name();
    original_role TEXT := current_user;
    can_set_role BOOLEAN := FALSE;
BEGIN
    -- 尝试切换到 supabase_admin 角色
    BEGIN
        SET LOCAL ROLE supabase_admin;
        can_set_role := TRUE;
        RAISE NOTICE 'Switched to supabase_admin role';
    EXCEPTION WHEN OTHERS THEN
        RAISE NOTICE 'Cannot switch to supabase_admin, current user: %', current_user;
        can_set_role := FALSE;
    END;

    IF can_set_role THEN
        -- 修改 order 表所有权
        EXECUTE format('ALTER TABLE IF EXISTS %I.order OWNER TO postgres', app_schema);
        RAISE NOTICE 'Changed ownership of %I.order to postgres', app_schema;

        -- 修改 order_timeout_tracker 表所有权
        EXECUTE format('ALTER TABLE IF EXISTS %I.order_timeout_tracker OWNER TO postgres', app_schema);
        RAISE NOTICE 'Changed ownership of %I.order_timeout_tracker to postgres', app_schema;

        -- 恢复原始角色
        EXECUTE format('SET LOCAL ROLE %I', original_role);
    ELSE
        RAISE WARNING 'Migration requires supabase_admin privileges. Please run as: psql -U supabase_admin';
        RAISE WARNING 'Skipping ownership changes. Subsequent migrations may fail.';
    END IF;
END $$;

-- 完成提示
DO $$
DECLARE
    app_schema TEXT := get_schema_name();
BEGIN
    RAISE NOTICE '=================================================';
    RAISE NOTICE 'Table ownership migration completed';
    RAISE NOTICE 'Schema: %', app_schema;
    RAISE NOTICE 'Tables updated:';
    RAISE NOTICE '  - %I.order -> postgres', app_schema;
    RAISE NOTICE '  - %I.order_timeout_tracker -> postgres', app_schema;
    RAISE NOTICE '=================================================';
END $$;

-- ===== /root/self_code/web_backend/center_management/db/migration/sql_schema_migration/20251023222618_add_get_order_by_id.sql =====
-- =====================================================
-- 添加 get_order_by_id 函数
-- =====================================================
-- 功能：通过订单 ID 查询订单详情（支持动态 schema）
-- 用途：为 Stripe 支付状态查询提供 RPC 函数支持
-- 执行方式：
--   psql "postgresql://postgres:$POSTGRES_PASSWORD@localhost:5438/postgres" \
--     -v ON_ERROR_STOP=1 \
--     -f center_management/db/migration/sql_schema_migration/13_add_get_order_by_id.sql
-- =====================================================

-- 创建 get_order_by_id 函数
CREATE OR REPLACE FUNCTION public.get_order_by_id(p_order_id uuid)
RETURNS TABLE(
    id uuid,
    product_name text,
    trade_num integer,
    amount integer,
    email text,
    phone text,
    status text,
    payment_provider text,
    stripe_payment_intent_id text,
    stripe_customer_id text,
    stripe_payment_status text,
    created_at timestamp with time zone
)
LANGUAGE plpgsql
STABLE
AS $function$
DECLARE
    app_schema TEXT := get_schema_name();
BEGIN
    RETURN QUERY EXECUTE format('
        SELECT
            id,
            product_name,
            trade_num,
            amount,
            email,
            phone,
            status,
            payment_provider,
            stripe_payment_intent_id,
            stripe_customer_id,
            stripe_payment_status,
            created_at
        FROM %I.order
        WHERE id = %L',
        app_schema, p_order_id
    );
END;
$function$;

-- 完成提示
DO $$
BEGIN
    RAISE NOTICE '=================================================';
    RAISE NOTICE 'Added get_order_by_id function';
    RAISE NOTICE 'Function: public.get_order_by_id(uuid)';
    RAISE NOTICE 'Purpose: Query order details by order ID';
    RAISE NOTICE '=================================================';
END $$;

-- ===== /root/self_code/web_backend/center_management/db/migration/sql_schema_migration/20251027101157_add_product_status.sql =====
-- =====================================================
-- 添加 product_status 字段用于异步产品生成跟踪
-- =====================================================
-- 功能：为 order 表添加产品生成状态跟踪
-- 使用方法: psql -U postgres -v ON_ERROR_STOP=1 -f 13_add_product_status.sql
-- =====================================================
-- 前置依赖：
--   必须先执行 01_order_refactored.sql 创建订单表
-- =====================================================

BEGIN;

-- Add product_status column to order table
DO $$
DECLARE
    app_schema TEXT := get_schema_name();
BEGIN
    -- 添加产品状态字段
    EXECUTE format('
        ALTER TABLE %I.order
        ADD COLUMN IF NOT EXISTS product_status text DEFAULT ''pending'' NOT NULL
    ', app_schema);

    RAISE NOTICE '✓ Added product_status column to %.order table', app_schema;

    -- 添加注释
    EXECUTE format('
        COMMENT ON COLUMN %I.order.product_status IS
        ''Product generation status: pending, processing, completed, failed''
    ', app_schema);

    -- 创建索引
    EXECUTE format('
        CREATE INDEX IF NOT EXISTS idx_order_product_status
        ON %I.order(product_status)
    ', app_schema);

    RAISE NOTICE '✓ Created index on product_status';
END $$;

-- Create function to update product status
CREATE OR REPLACE FUNCTION update_product_status(
    p_order_id uuid,
    p_status text
) RETURNS boolean
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
DECLARE
    app_schema TEXT := get_schema_name();
    v_valid_statuses text[] := ARRAY['pending', 'processing', 'completed', 'failed'];
    v_updated boolean;
BEGIN
    -- Validate status value
    IF p_status = ANY(v_valid_statuses) THEN
        EXECUTE format('
            UPDATE %I.order
            SET product_status = $1
            WHERE id = $2
        ', app_schema) USING p_status, p_order_id;

        GET DIAGNOSTICS v_updated = ROW_COUNT;

        IF v_updated THEN
            RAISE NOTICE '✓ Updated order % product_status to %', p_order_id, p_status;
            RETURN TRUE;
        ELSE
            RAISE NOTICE '✗ Order % not found', p_order_id;
            RETURN FALSE;
        END IF;
    ELSE
        RAISE EXCEPTION 'Invalid status: %. Must be one of: %', p_status, v_valid_statuses;
    END IF;
END;
$$;

COMMENT ON FUNCTION update_product_status IS 'Update product generation status for an order';

-- Create function to get product status
CREATE OR REPLACE FUNCTION get_product_status(
    p_order_id uuid
) RETURNS text
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
DECLARE
    app_schema TEXT := get_schema_name();
    v_status text;
BEGIN
    EXECUTE format('
        SELECT product_status FROM %I.order
        WHERE id = $1
    ', app_schema) INTO v_status USING p_order_id;

    IF v_status IS NOT NULL THEN
        RETURN v_status;
    ELSE
        RAISE NOTICE '✗ Order % not found', p_order_id;
        RETURN NULL;
    END IF;
END;
$$;

COMMENT ON FUNCTION get_product_status IS 'Get product generation status for an order';

-- Create function to get orders by product status
CREATE OR REPLACE FUNCTION get_orders_by_product_status(
    p_status text DEFAULT NULL,
    p_limit integer DEFAULT 100
) RETURNS TABLE (
    id uuid,
    product_name text,
    email text,
    phone text,
    status text,
    product_status text,
    created_at timestamptz
)
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
DECLARE
    app_schema TEXT := get_schema_name();
BEGIN
    IF p_status IS NULL THEN
        RETURN QUERY EXECUTE format('
            SELECT
                o.id,
                o.product_name,
                o.email,
                o.phone,
                o.status,
                o.product_status,
                o.created_at
            FROM %I.order o
            ORDER BY o.created_at DESC
            LIMIT $1
        ', app_schema) USING p_limit;
    ELSE
        RETURN QUERY EXECUTE format('
            SELECT
                o.id,
                o.product_name,
                o.email,
                o.phone,
                o.status,
                o.product_status,
                o.created_at
            FROM %I.order o
            WHERE o.product_status = $1
            ORDER BY o.created_at DESC
            LIMIT $2
        ', app_schema) USING p_status, p_limit;
    END IF;
END;
$$;

COMMENT ON FUNCTION get_orders_by_product_status IS 'Get orders filtered by product status with pagination';

-- Grant permissions
GRANT EXECUTE ON FUNCTION update_product_status TO authenticated;
GRANT EXECUTE ON FUNCTION get_product_status TO authenticated;
GRANT EXECUTE ON FUNCTION get_orders_by_product_status TO authenticated;

-- Success notification
DO $$
BEGIN
    RAISE NOTICE '=== Migration 13 completed successfully ===';
    RAISE NOTICE 'Added product_status tracking for async product generation';
END $$;

COMMIT;

-- ===== /root/self_code/web_backend/center_management/db/migration/sql_schema_migration/20251027173847_fix_insert_order_payment_provider.sql =====
-- =====================================================
-- 修复 insert_order 函数：添加 payment_provider 参数
-- =====================================================
-- 功能：更新 insert_order() 函数以支持显式传递 payment_provider
-- 使用方法: psql -v ON_ERROR_STOP=1 -f 14_fix_insert_order_payment_provider.sql
-- =====================================================
-- 前置依赖：
--   必须先执行 01_order_refactored.sql 和 12_stripe_integration.sql
-- =====================================================

-- 1. 删除旧版本的 insert_order 函数
DROP FUNCTION IF EXISTS insert_order(text, int4, int4, text, text);

-- 2. 创建新版本的 insert_order 函数（添加 payment_provider 参数，无默认值）
CREATE OR REPLACE FUNCTION insert_order(
    p_product_name text,
    p_trade_num int4,
    p_amount int4,
    p_email text,
    p_phone text,
    p_payment_provider text  -- 新增必需参数
)
RETURNS uuid
LANGUAGE plpgsql
AS $$
DECLARE
    new_id uuid;
    check_time timestamp with time zone;
    app_schema TEXT := get_schema_name();
BEGIN
    -- 插入订单（包含 payment_provider）
    EXECUTE format('
        INSERT INTO %I.order (product_name, trade_num, amount, email, phone, payment_provider)
        VALUES (%L, %L, %L, %L, %L, %L)
        RETURNING id',
        app_schema, p_product_name, p_trade_num, p_amount, p_email, p_phone, p_payment_provider
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

-- 3. 设置权限
GRANT EXECUTE ON FUNCTION insert_order(text, int4, int4, text, text, text) TO service_role;

-- 4. 完成提示
DO $$
BEGIN
    RAISE NOTICE '=================================================';
    RAISE NOTICE 'insert_order function updated successfully';
    RAISE NOTICE '=================================================';
    RAISE NOTICE 'Changes:';
    RAISE NOTICE '  - Added required parameter: p_payment_provider';
    RAISE NOTICE '  - No default value (explicit value required)';
    RAISE NOTICE '  - Updated INSERT to include payment_provider field';
    RAISE NOTICE '=================================================';
    RAISE NOTICE 'IMPORTANT: All callers must now provide payment_provider';
    RAISE NOTICE '=================================================';
END $$;

-- ===== /root/self_code/web_backend/center_management/db/migration/sql_schema_migration/20251027175640_add_update_order_payment_info.sql =====
-- =====================================================
-- 添加更新订单支付信息函数
-- =====================================================
-- 功能：创建函数用于更新订单的支付提供商特定字段
-- 使用方法: psql -v ON_ERROR_STOP=1 -f 15_add_update_order_payment_info.sql
-- =====================================================
-- 前置依赖：
--   必须先执行 12_stripe_integration.sql（添加 Stripe 字段）
-- =====================================================

-- 创建更新订单支付信息函数
CREATE OR REPLACE FUNCTION update_order_payment_info(
    p_order_id uuid,
    p_stripe_payment_intent_id text DEFAULT NULL,
    p_stripe_customer_id text DEFAULT NULL,
    p_stripe_payment_status text DEFAULT NULL
)
RETURNS boolean
LANGUAGE plpgsql
AS $$
DECLARE
    rows_affected integer;
    app_schema TEXT := get_schema_name();
BEGIN
    -- 动态更新订单的 Stripe 字段（仅更新非 NULL 参数）
    EXECUTE format('
        UPDATE %I.order
        SET
            stripe_payment_intent_id = COALESCE(%L, stripe_payment_intent_id),
            stripe_customer_id = COALESCE(%L, stripe_customer_id),
            stripe_payment_status = COALESCE(%L, stripe_payment_status)
        WHERE id = %L',
        app_schema,
        p_stripe_payment_intent_id,
        p_stripe_customer_id,
        p_stripe_payment_status,
        p_order_id
    );

    GET DIAGNOSTICS rows_affected = ROW_COUNT;
    RETURN rows_affected > 0;
END;
$$;

-- 设置权限
GRANT EXECUTE ON FUNCTION update_order_payment_info(uuid, text, text, text) TO service_role;

-- 完成提示
DO $$
BEGIN
    RAISE NOTICE '=================================================';
    RAISE NOTICE 'update_order_payment_info function created successfully';
    RAISE NOTICE '=================================================';
    RAISE NOTICE 'Function signature:';
    RAISE NOTICE '  update_order_payment_info(';
    RAISE NOTICE '    p_order_id uuid,';
    RAISE NOTICE '    p_stripe_payment_intent_id text DEFAULT NULL,';
    RAISE NOTICE '    p_stripe_customer_id text DEFAULT NULL,';
    RAISE NOTICE '    p_stripe_payment_status text DEFAULT NULL';
    RAISE NOTICE '  )';
    RAISE NOTICE '=================================================';
    RAISE NOTICE 'Usage: Updates Stripe-specific fields in order table';
    RAISE NOTICE 'Only non-NULL parameters will be updated (COALESCE)';
    RAISE NOTICE '=================================================';
END $$;

-- ===== /root/self_code/web_backend/center_management/db/migration/sql_schema_migration/20251027221500_add_stripe_checkout_session_id.sql =====
-- =====================================================
-- 功能说明：为 orders 表添加 Stripe Checkout Session ID 字段
-- =====================================================
-- 前置依赖：
--   1. 必须先执行 00_schema_init.sql (或 20251017210439_schema_init.sql) 初始化 schema 配置
--   2. 必须已存在 orders 表
-- =====================================================

DO $$
DECLARE
    app_schema TEXT := get_schema_name();
BEGIN
    -- 添加 stripe_checkout_session_id 字段
    EXECUTE format('
        ALTER TABLE %I.order
        ADD COLUMN IF NOT EXISTS stripe_checkout_session_id TEXT;
    ', app_schema);

    -- 添加索引以提高查询性能
    EXECUTE format('
        CREATE INDEX IF NOT EXISTS idx_orders_checkout_session_id
        ON %I.order (stripe_checkout_session_id)
        WHERE stripe_checkout_session_id IS NOT NULL;
    ', app_schema);

    RAISE NOTICE '✅ orders 表已添加 stripe_checkout_session_id 字段和索引';
END $$;

-- ===== /root/self_code/web_backend/center_management/db/migration/sql_schema_migration/20251028105110_update_payment_info_add_checkout_session.sql =====
-- =====================================================
-- 迁移文件：扩展 update_order_payment_info 函数支持 checkout_session_id
-- =====================================================
-- 功能说明：
--   扩展现有的 update_order_payment_info() 函数，添加对 stripe_checkout_session_id 字段的支持
--   这样可以通过统一的数据库函数更新所有 Stripe 相关的支付信息
--
-- 前置依赖：
--   1. 必须先执行 00_schema_init.sql (20251017210439) 初始化 schema 配置
--   2. 必须先执行 20251027175640_add_update_order_payment_info.sql 创建基础函数
--   3. 必须先执行 20251027221500_add_stripe_checkout_session_id.sql 添加字段
--
-- 修改内容：
--   - 为 update_order_payment_info() 函数添加 p_stripe_checkout_session_id 参数
--   - 在 UPDATE 语句中添加对 stripe_checkout_session_id 字段的更新逻辑
--
-- 使用示例：
--   SELECT update_order_payment_info(
--       'order-uuid-here',
--       NULL,  -- payment_intent_id
--       NULL,  -- customer_id
--       NULL,  -- payment_status
--       'cs_test_xxx'  -- checkout_session_id
--   );
-- =====================================================

-- 删除旧版本函数（如果存在）
DROP FUNCTION IF EXISTS update_order_payment_info(uuid, text, text, text);

-- 创建扩展版本的函数，支持 checkout_session_id
CREATE OR REPLACE FUNCTION update_order_payment_info(
    p_order_id uuid,
    p_stripe_payment_intent_id text DEFAULT NULL,
    p_stripe_customer_id text DEFAULT NULL,
    p_stripe_payment_status text DEFAULT NULL,
    p_stripe_checkout_session_id text DEFAULT NULL  -- 新增参数
)
RETURNS boolean
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
DECLARE
    rows_affected integer;
    app_schema TEXT := get_schema_name();
BEGIN
    -- 使用动态 SQL 和 COALESCE 只更新提供的字段
    EXECUTE format('
        UPDATE %I.order
        SET
            stripe_payment_intent_id = COALESCE($1, stripe_payment_intent_id),
            stripe_customer_id = COALESCE($2, stripe_customer_id),
            stripe_payment_status = COALESCE($3, stripe_payment_status),
            stripe_checkout_session_id = COALESCE($4, stripe_checkout_session_id)
        WHERE id = $5',
        app_schema
    )
    USING
        p_stripe_payment_intent_id,
        p_stripe_customer_id,
        p_stripe_payment_status,
        p_stripe_checkout_session_id,
        p_order_id;

    -- 获取影响的行数
    GET DIAGNOSTICS rows_affected = ROW_COUNT;

    -- 返回是否成功更新（true = 找到并更新了订单，false = 未找到订单）
    RETURN rows_affected > 0;
END;
$$;

-- 添加函数注释
COMMENT ON FUNCTION update_order_payment_info(uuid, text, text, text, text) IS
'更新订单的 Stripe 支付信息。只更新传入的非 NULL 字段。
参数：
  - p_order_id: 订单 ID (必需)
  - p_stripe_payment_intent_id: Stripe Payment Intent ID (可选)
  - p_stripe_customer_id: Stripe Customer ID (可选)
  - p_stripe_payment_status: Stripe 支付状态 (可选)
  - p_stripe_checkout_session_id: Stripe Checkout Session ID (可选)
返回：
  - boolean: true 表示订单找到并更新成功，false 表示未找到订单';

-- 授予执行权限
GRANT EXECUTE ON FUNCTION update_order_payment_info(uuid, text, text, text, text) TO authenticated;
GRANT EXECUTE ON FUNCTION update_order_payment_info(uuid, text, text, text, text) TO anon;
GRANT EXECUTE ON FUNCTION update_order_payment_info(uuid, text, text, text, text) TO service_role;

-- 测试函数（可选 - 需要存在的订单 ID）
-- SELECT update_order_payment_info(
--     'your-order-uuid'::uuid,
--     NULL,
--     NULL,
--     NULL,
--     'cs_test_example_session_id'
-- );

-- ===== /root/self_code/web_backend/center_management/db/migration/sql_schema_migration/20251028105608_add_get_order_by_checkout_session.sql =====
-- =====================================================
-- 迁移文件：添加根据 Checkout Session ID 查询订单的 RPC 函数
-- =====================================================
-- 功能说明：
--   创建 get_order_by_checkout_session() 函数，通过 Stripe Checkout Session ID 查询订单
--   这样可以通过 PostgREST API 访问 tests schema 中的订单数据
--
-- 前置依赖：
--   1. 必须先执行 00_schema_init.sql (20251017210439) 初始化 schema 配置
--   2. 必须先执行 20251027221500_add_stripe_checkout_session_id.sql 添加字段
--
-- 使用示例：
--   SELECT * FROM get_order_by_checkout_session(
--       'cs_test_xxx',
--       'user@example.com'
--   );
-- =====================================================

-- 创建查询函数
CREATE OR REPLACE FUNCTION get_order_by_checkout_session(
    p_checkout_session_id text,
    p_user_email text
)
RETURNS TABLE (
    id uuid,
    status text,
    product_status text,
    product_name text,
    amount integer,
    email text,
    created_at timestamptz
)
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
DECLARE
    app_schema TEXT := get_schema_name();
BEGIN
    -- 使用动态 SQL 查询 order 表
    RETURN QUERY EXECUTE format('
        SELECT
            id,
            status,
            product_status,
            product_name,
            amount,
            email,
            created_at
        FROM %I.order
        WHERE stripe_checkout_session_id = $1
          AND email = $2
        LIMIT 1',
        app_schema
    )
    USING p_checkout_session_id, p_user_email;
END;
$$;

-- 添加函数注释
COMMENT ON FUNCTION get_order_by_checkout_session(text, text) IS
'根据 Stripe Checkout Session ID 查询订单。
参数：
  - p_checkout_session_id: Stripe Checkout Session ID
  - p_user_email: 用户邮箱（用于安全验证）
返回：
  - 订单数据记录，包含 id, status, product_status, product_name, amount, email, created_at';

-- 授予执行权限
GRANT EXECUTE ON FUNCTION get_order_by_checkout_session(text, text) TO authenticated;
GRANT EXECUTE ON FUNCTION get_order_by_checkout_session(text, text) TO anon;
GRANT EXECUTE ON FUNCTION get_order_by_checkout_session(text, text) TO service_role;
