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