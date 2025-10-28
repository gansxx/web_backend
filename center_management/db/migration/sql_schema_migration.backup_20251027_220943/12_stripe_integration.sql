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
