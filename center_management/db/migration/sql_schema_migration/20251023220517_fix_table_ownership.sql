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
