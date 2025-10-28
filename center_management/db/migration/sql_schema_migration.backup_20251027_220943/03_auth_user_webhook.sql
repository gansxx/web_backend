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
