-- =====================================================
-- 添加 get_order_by_id 函数
-- =====================================================
-- 功能：通过订单 ID 查询订单详情（支持动态 schema）
-- 用途：为 Stripe 支付状态查询提供 RPC 函数支持
-- 执行方式：
--   psql "postgresql://postgres:$POSTGRES_PASSWORD@localhost:5438/postgres" \
--     -v ON_ERROR_STOP=1 \
--     -f supabase/migrations/13_add_get_order_by_id.sql
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
