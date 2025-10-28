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
