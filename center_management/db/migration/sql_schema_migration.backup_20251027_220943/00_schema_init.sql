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
    app_schema TEXT := 'tests';  -- 在此处修改 schema 名称
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
