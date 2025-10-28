-- =====================================================
-- 迁移文件：添加根据 Checkout Session ID 查询订单的 RPC 函数
-- =====================================================
-- 功能说明：
--   创建 get_order_by_checkout_session() 函数，通过 Stripe Checkout Session ID 查询订单
--   这样可以通过 PostgREST API 访问 tests schema 中的订单数据
--
-- 前置依赖：
--   1. 必须先执行 00_schema_init.sql (20251017210439) 初始化 schema 配置
--   2. 必须先执行 20251027221500_add_stripe_checkout_session_id.sql 添加字段
--
-- 使用示例：
--   SELECT * FROM get_order_by_checkout_session(
--       'cs_test_xxx',
--       'user@example.com'
--   );
-- =====================================================

-- 创建查询函数
CREATE OR REPLACE FUNCTION get_order_by_checkout_session(
    p_checkout_session_id text,
    p_user_email text
)
RETURNS TABLE (
    id uuid,
    status text,
    product_status text,
    product_name text,
    amount integer,
    email text,
    created_at timestamptz
)
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
DECLARE
    app_schema TEXT := get_schema_name();
BEGIN
    -- 使用动态 SQL 查询 order 表
    RETURN QUERY EXECUTE format('
        SELECT
            id,
            status,
            product_status,
            product_name,
            amount,
            email,
            created_at
        FROM %I.order
        WHERE stripe_checkout_session_id = $1
          AND email = $2
        LIMIT 1',
        app_schema
    )
    USING p_checkout_session_id, p_user_email;
END;
$$;

-- 添加函数注释
COMMENT ON FUNCTION get_order_by_checkout_session(text, text) IS
'根据 Stripe Checkout Session ID 查询订单。
参数：
  - p_checkout_session_id: Stripe Checkout Session ID
  - p_user_email: 用户邮箱（用于安全验证）
返回：
  - 订单数据记录，包含 id, status, product_status, product_name, amount, email, created_at';

-- 授予执行权限
GRANT EXECUTE ON FUNCTION get_order_by_checkout_session(text, text) TO authenticated;
GRANT EXECUTE ON FUNCTION get_order_by_checkout_session(text, text) TO anon;
GRANT EXECUTE ON FUNCTION get_order_by_checkout_session(text, text) TO service_role;
