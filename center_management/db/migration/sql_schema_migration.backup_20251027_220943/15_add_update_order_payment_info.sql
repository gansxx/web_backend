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
