-- =====================================================
-- 更新 insert_order 函数：添加 subscription_type 参数
-- =====================================================
-- 功能：更新 insert_order() 函数以支持 subscription_type 参数
-- 使用方法: psql -v ON_ERROR_STOP=1 -f 20251226100000_update_insert_order_subscription_type.sql
-- =====================================================
-- 前置依赖：
--   1. 必须先执行 20251225120000_subscription_tables.sql（添加 subscription_type 列）
--   2. 必须先执行 20251027173847_fix_insert_order_payment_provider.sql
-- =====================================================

-- 1. 删除旧版本的 insert_order 函数
DROP FUNCTION IF EXISTS insert_order(text, int4, int4, text, text, text);

-- 2. 创建新版本的 insert_order 函数（添加 subscription_type 参数）
CREATE OR REPLACE FUNCTION insert_order(
    p_product_name text,
    p_trade_num int4,
    p_amount int4,
    p_email text,
    p_phone text,
    p_payment_provider text,
    p_subscription_type text DEFAULT 'one_time'  -- 新增参数：订单类型（one_time/subscription）
)
RETURNS uuid
LANGUAGE plpgsql
AS $$
DECLARE
    new_id uuid;
    check_time timestamp with time zone;
    app_schema TEXT := get_schema_name();
BEGIN
    -- 插入订单（包含 payment_provider 和 subscription_type）
    EXECUTE format('
        INSERT INTO %I.order (product_name, trade_num, amount, email, phone, payment_provider, subscription_type)
        VALUES (%L, %L, %L, %L, %L, %L, %L)
        RETURNING id',
        app_schema, p_product_name, p_trade_num, p_amount, p_email, p_phone, p_payment_provider, p_subscription_type
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
GRANT EXECUTE ON FUNCTION insert_order(text, int4, int4, text, text, text, text) TO service_role;

-- 4. 完成提示
DO $$
BEGIN
    RAISE NOTICE '=================================================';
    RAISE NOTICE 'insert_order function updated successfully';
    RAISE NOTICE '=================================================';
    RAISE NOTICE 'Changes:';
    RAISE NOTICE '  - Added optional parameter: p_subscription_type';
    RAISE NOTICE '  - Default value: one_time';
    RAISE NOTICE '  - Valid values: one_time, subscription';
    RAISE NOTICE '  - Updated INSERT to include subscription_type field';
    RAISE NOTICE '=================================================';
END $$;
