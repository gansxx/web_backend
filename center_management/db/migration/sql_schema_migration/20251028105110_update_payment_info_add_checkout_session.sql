-- =====================================================
-- 迁移文件：扩展 update_order_payment_info 函数支持 checkout_session_id
-- =====================================================
-- 功能说明：
--   扩展现有的 update_order_payment_info() 函数，添加对 stripe_checkout_session_id 字段的支持
--   这样可以通过统一的数据库函数更新所有 Stripe 相关的支付信息
--
-- 前置依赖：
--   1. 必须先执行 00_schema_init.sql (20251017210439) 初始化 schema 配置
--   2. 必须先执行 20251027175640_add_update_order_payment_info.sql 创建基础函数
--   3. 必须先执行 20251027221500_add_stripe_checkout_session_id.sql 添加字段
--
-- 修改内容：
--   - 为 update_order_payment_info() 函数添加 p_stripe_checkout_session_id 参数
--   - 在 UPDATE 语句中添加对 stripe_checkout_session_id 字段的更新逻辑
--
-- 使用示例：
--   SELECT update_order_payment_info(
--       'order-uuid-here',
--       NULL,  -- payment_intent_id
--       NULL,  -- customer_id
--       NULL,  -- payment_status
--       'cs_test_xxx'  -- checkout_session_id
--   );
-- =====================================================

-- 删除旧版本函数（如果存在）
DROP FUNCTION IF EXISTS update_order_payment_info(uuid, text, text, text);

-- 创建扩展版本的函数，支持 checkout_session_id
CREATE OR REPLACE FUNCTION update_order_payment_info(
    p_order_id uuid,
    p_stripe_payment_intent_id text DEFAULT NULL,
    p_stripe_customer_id text DEFAULT NULL,
    p_stripe_payment_status text DEFAULT NULL,
    p_stripe_checkout_session_id text DEFAULT NULL  -- 新增参数
)
RETURNS boolean
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
DECLARE
    rows_affected integer;
    app_schema TEXT := get_schema_name();
BEGIN
    -- 使用动态 SQL 和 COALESCE 只更新提供的字段
    EXECUTE format('
        UPDATE %I.order
        SET
            stripe_payment_intent_id = COALESCE($1, stripe_payment_intent_id),
            stripe_customer_id = COALESCE($2, stripe_customer_id),
            stripe_payment_status = COALESCE($3, stripe_payment_status),
            stripe_checkout_session_id = COALESCE($4, stripe_checkout_session_id)
        WHERE id = $5',
        app_schema
    )
    USING
        p_stripe_payment_intent_id,
        p_stripe_customer_id,
        p_stripe_payment_status,
        p_stripe_checkout_session_id,
        p_order_id;

    -- 获取影响的行数
    GET DIAGNOSTICS rows_affected = ROW_COUNT;

    -- 返回是否成功更新（true = 找到并更新了订单，false = 未找到订单）
    RETURN rows_affected > 0;
END;
$$;

-- 添加函数注释
COMMENT ON FUNCTION update_order_payment_info(uuid, text, text, text, text) IS
'更新订单的 Stripe 支付信息。只更新传入的非 NULL 字段。
参数：
  - p_order_id: 订单 ID (必需)
  - p_stripe_payment_intent_id: Stripe Payment Intent ID (可选)
  - p_stripe_customer_id: Stripe Customer ID (可选)
  - p_stripe_payment_status: Stripe 支付状态 (可选)
  - p_stripe_checkout_session_id: Stripe Checkout Session ID (可选)
返回：
  - boolean: true 表示订单找到并更新成功，false 表示未找到订单';

-- 授予执行权限
GRANT EXECUTE ON FUNCTION update_order_payment_info(uuid, text, text, text, text) TO authenticated;
GRANT EXECUTE ON FUNCTION update_order_payment_info(uuid, text, text, text, text) TO anon;
GRANT EXECUTE ON FUNCTION update_order_payment_info(uuid, text, text, text, text) TO service_role;

-- 测试函数（可选 - 需要存在的订单 ID）
-- SELECT update_order_payment_info(
--     'your-order-uuid'::uuid,
--     NULL,
--     NULL,
--     NULL,
--     'cs_test_example_session_id'
-- );
