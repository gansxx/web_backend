-- =====================================================
-- 工单系统添加答复功能
-- =====================================================
-- 功能：为工单表添加管理员答复字段，并更新相关函数
-- 创建日期：2025-10-02
-- 使用方法: psql -v ON_ERROR_STOP=1 -f ticket_system_add_reply.sql
-- =====================================================
-- 前置依赖：
--   1. 必须先执行 00_schema_init.sql 初始化 schema 配置
--   2. 必须先执行 ticket_system.sql 创建 ticket 表
--   该脚本依赖 get_schema_name() 函数获取 schema 名称
-- =====================================================

-- 1. 为 ticket 表添加答复相关字段
DO $$
DECLARE
    app_schema TEXT := get_schema_name();
BEGIN
    -- 添加 reply 字段（管理员答复内容）
    EXECUTE format('
        ALTER TABLE %I.ticket
        ADD COLUMN IF NOT EXISTS reply TEXT NULL',
        app_schema
    );

    -- 添加 replied_at 字段（答复时间）
    EXECUTE format('
        ALTER TABLE %I.ticket
        ADD COLUMN IF NOT EXISTS replied_at TIMESTAMPTZ NULL',
        app_schema
    );

    RAISE NOTICE 'Added reply and replied_at columns to ticket table in schema: %', app_schema;
END $$;

-- 2. 替换 update_ticket_status 函数（支持答复参数）
DROP FUNCTION IF EXISTS update_ticket_status(uuid, text);

CREATE FUNCTION update_ticket_status(
    p_ticket_id uuid,
    p_status text,
    p_reply text DEFAULT NULL
)
RETURNS boolean
LANGUAGE plpgsql
AS $$
DECLARE
    rows_affected integer;
    app_schema TEXT := get_schema_name();
BEGIN
    -- 验证 status 值
    IF p_status NOT IN ('处理中', '已解决') THEN
        RAISE EXCEPTION 'Invalid status value. Must be one of: 处理中, 已解决';
    END IF;

    -- 更新工单状态和答复
    IF p_reply IS NOT NULL AND p_reply != '' THEN
        -- 如果提供了答复，同时更新 reply 和 replied_at
        EXECUTE format('
            UPDATE %I.ticket
            SET status = %L,
                reply = %L,
                replied_at = NOW()
            WHERE id = %L',
            app_schema, p_status, p_reply, p_ticket_id
        );
    ELSE
        -- 如果没有提供答复，只更新状态
        EXECUTE format('
            UPDATE %I.ticket
            SET status = %L
            WHERE id = %L',
            app_schema, p_status, p_ticket_id
        );
    END IF;

    GET DIAGNOSTICS rows_affected = ROW_COUNT;
    RETURN rows_affected > 0;
END;
$$;

-- 3. 创建根据 ID 获取工单详情的函数（新函数）
CREATE OR REPLACE FUNCTION get_ticket_by_id(
    p_ticket_id uuid
)
RETURNS TABLE (
    id uuid,
    created_at timestamptz,
    updated_at timestamptz,
    user_email text,
    phone text,
    subject text,
    priority text,
    category text,
    description text,
    status text,
    reply text,
    replied_at timestamptz,
    metadata jsonb
)
LANGUAGE plpgsql
STABLE
AS $$
DECLARE
    app_schema TEXT := get_schema_name();
BEGIN
    RETURN QUERY EXECUTE format('
        SELECT t.id, t.created_at, t.updated_at, t.user_email, t.phone,
               t.subject, t.priority, t.category, t.description, t.status,
               t.reply, t.replied_at, t.metadata
        FROM %I.ticket t
        WHERE t.id = %L',
        app_schema, p_ticket_id
    );
END;
$$;

-- 4. 替换 fetch_user_tickets 函数（包含答复字段）
DROP FUNCTION IF EXISTS fetch_user_tickets(text);

CREATE FUNCTION fetch_user_tickets(
    p_user_email text
)
RETURNS TABLE (
    id uuid,
    subject text,
    priority text,
    category text,
    description text,
    status text,
    phone text,
    created_at timestamptz,
    updated_at timestamptz,
    reply text,
    replied_at timestamptz,
    metadata jsonb
)
LANGUAGE plpgsql
STABLE
AS $$
DECLARE
    app_schema TEXT := get_schema_name();
BEGIN
    IF p_user_email IS NULL OR p_user_email = '' THEN
        RAISE EXCEPTION 'User email is required';
    END IF;

    RETURN QUERY EXECUTE format('
        SELECT t.id, t.subject, t.priority, t.category, t.description,
               t.status, t.phone, t.created_at, t.updated_at,
               t.reply, t.replied_at, t.metadata
        FROM %I.ticket t
        WHERE t.user_email = %L
        ORDER BY t.created_at DESC',
        app_schema, p_user_email
    );
END;
$$;

-- 5. 替换 fetch_all_tickets 函数（包含答复字段）
DROP FUNCTION IF EXISTS fetch_all_tickets(text, text, integer, integer);

CREATE FUNCTION fetch_all_tickets(
    p_status text default null,
    p_priority text default null,
    p_limit integer default 100,
    p_offset integer default 0
)
RETURNS TABLE (
    id uuid,
    user_email text,
    phone text,
    subject text,
    priority text,
    category text,
    description text,
    status text,
    created_at timestamptz,
    updated_at timestamptz,
    reply text,
    replied_at timestamptz,
    metadata jsonb
)
LANGUAGE plpgsql
STABLE
AS $$
DECLARE
    app_schema TEXT := get_schema_name();
    where_clause text := '';
BEGIN
    -- 构建 WHERE 子句
    IF p_status IS NOT NULL THEN
        where_clause := format('WHERE status = %L', p_status);
    END IF;

    IF p_priority IS NOT NULL THEN
        IF where_clause = '' THEN
            where_clause := format('WHERE priority = %L', p_priority);
        ELSE
            where_clause := where_clause || format(' AND priority = %L', p_priority);
        END IF;
    END IF;

    RETURN QUERY EXECUTE format('
        SELECT t.id, t.user_email, t.phone, t.subject, t.priority, t.category,
               t.description, t.status, t.created_at, t.updated_at,
               t.reply, t.replied_at, t.metadata
        FROM %I.ticket t
        %s
        ORDER BY t.created_at DESC
        LIMIT %L OFFSET %L',
        app_schema, where_clause, p_limit, p_offset
    );
END;
$$;

-- 6. 更新权限设置
-- 注意：这里授予新签名的权限
GRANT EXECUTE ON FUNCTION update_ticket_status(uuid, text, text) TO service_role;
GRANT EXECUTE ON FUNCTION get_ticket_by_id(uuid) TO service_role;
GRANT EXECUTE ON FUNCTION fetch_user_tickets(text) TO service_role;
GRANT EXECUTE ON FUNCTION fetch_all_tickets(text, text, integer, integer) TO service_role;

-- 7. 完成提示
DO $$
DECLARE
    app_schema TEXT := get_schema_name();
BEGIN
    RAISE NOTICE 'Ticket reply feature migration completed successfully for schema: %', app_schema;
    RAISE NOTICE 'Added columns: reply, replied_at';
    RAISE NOTICE 'Updated functions: update_ticket_status (new signature with reply parameter)';
    RAISE NOTICE 'Recreated functions: fetch_user_tickets, fetch_all_tickets (with reply fields)';
    RAISE NOTICE 'Created new function: get_ticket_by_id';
END $$;
