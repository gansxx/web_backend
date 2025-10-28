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
