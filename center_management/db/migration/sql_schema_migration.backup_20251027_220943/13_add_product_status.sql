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
