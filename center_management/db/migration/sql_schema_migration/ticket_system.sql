-- =====================================================
-- 工单管理系统
-- =====================================================
-- 功能：创建工单相关表和管理函数
-- 使用方法: psql -v ON_ERROR_STOP=1 -f ticket_system.sql
-- =====================================================
-- 前置依赖：
--   必须先执行 00_schema_init.sql 初始化 schema 配置
--   该脚本依赖 get_schema_name() 函数获取 schema 名称
-- =====================================================

-- 1. 创建 ticket 表
DO $$
DECLARE
    app_schema TEXT := get_schema_name();
BEGIN
    EXECUTE format('
        CREATE TABLE IF NOT EXISTS %I.ticket (
            id uuid not null default gen_random_uuid(),
            created_at timestamp with time zone not null default now(),
            updated_at timestamp with time zone not null default now(),
            user_email text not null,
            phone text null default '''',
            subject text not null,
            priority text not null check (priority in (''高'', ''中'', ''低'')),
            category text not null,
            description text not null,
            status text not null default ''处理中'' check (status in (''处理中'', ''已解决'')),
            metadata jsonb null,
            constraint ticket_pkey primary key (id)
        ) TABLESPACE pg_default',
        app_schema
    );

    -- 为常用查询字段创建索引
    EXECUTE format('CREATE INDEX IF NOT EXISTS ticket_user_email_idx ON %I.ticket(user_email)', app_schema);
    EXECUTE format('CREATE INDEX IF NOT EXISTS ticket_status_idx ON %I.ticket(status)', app_schema);
    EXECUTE format('CREATE INDEX IF NOT EXISTS ticket_created_at_idx ON %I.ticket(created_at DESC)', app_schema);

    RAISE NOTICE 'Created ticket table in schema: %', app_schema;
END $$;

-- 2. 创建自动更新 updated_at 的触发器函数
CREATE OR REPLACE FUNCTION update_ticket_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- 3. 为 ticket 表添加更新触发器
DO $$
DECLARE
    app_schema TEXT := get_schema_name();
BEGIN
    EXECUTE format('
        DROP TRIGGER IF EXISTS ticket_updated_at_trigger ON %I.ticket;
        CREATE TRIGGER ticket_updated_at_trigger
        BEFORE UPDATE ON %I.ticket
        FOR EACH ROW
        EXECUTE FUNCTION update_ticket_updated_at()',
        app_schema, app_schema
    );
END $$;

-- 4. 创建插入工单函数
CREATE OR REPLACE FUNCTION insert_ticket(
    p_user_email text,
    p_subject text,
    p_priority text,
    p_category text,
    p_description text,
    p_phone text default '',
    p_metadata jsonb default null
)
RETURNS uuid
LANGUAGE plpgsql
AS $$
DECLARE
    new_id uuid;
    app_schema TEXT := get_schema_name();
BEGIN
    -- 验证 priority 值
    IF p_priority NOT IN ('高', '中', '低') THEN
        RAISE EXCEPTION 'Invalid priority value. Must be one of: 高, 中, 低';
    END IF;

    -- 插入工单
    EXECUTE format('
        INSERT INTO %I.ticket (user_email, subject, priority, category, description, phone, metadata)
        VALUES (%L, %L, %L, %L, %L, %L, %L)
        RETURNING id',
        app_schema, p_user_email, p_subject, p_priority, p_category, p_description, p_phone, p_metadata
    ) INTO new_id;

    RETURN new_id;
END;
$$;

-- 5. 创建查询用户工单函数
-- 先删除旧版本（如果存在）以避免签名冲突
DROP FUNCTION IF EXISTS fetch_user_tickets(text);

CREATE OR REPLACE FUNCTION fetch_user_tickets(
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
               t.status, t.phone, t.created_at, t.updated_at, t.metadata
        FROM %I.ticket t
        WHERE t.user_email = %L
        ORDER BY t.created_at DESC',
        app_schema, p_user_email
    );
END;
$$;

-- 6. 创建更新工单状态函数
CREATE OR REPLACE FUNCTION update_ticket_status(
    p_ticket_id uuid,
    p_status text
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

    EXECUTE format('
        UPDATE %I.ticket
        SET status = %L
        WHERE id = %L',
        app_schema, p_status, p_ticket_id
    );

    GET DIAGNOSTICS rows_affected = ROW_COUNT;
    RETURN rows_affected > 0;
END;
$$;

-- 7. 创建查询所有工单函数（管理员用）
-- 先删除旧版本（如果存在）以避免签名冲突
DROP FUNCTION IF EXISTS fetch_all_tickets(text, text, integer, integer);

CREATE OR REPLACE FUNCTION fetch_all_tickets(
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
               t.description, t.status, t.created_at, t.updated_at, t.metadata
        FROM %I.ticket t
        %s
        ORDER BY t.created_at DESC
        LIMIT %L OFFSET %L',
        app_schema, where_clause, p_limit, p_offset
    );
END;
$$;

-- 8. 设置权限
DO $$
DECLARE
    app_schema TEXT := get_schema_name();
BEGIN
    EXECUTE format('GRANT USAGE ON SCHEMA %I TO service_role', app_schema);
    EXECUTE format('GRANT SELECT ON %I.ticket TO service_role', app_schema);
    EXECUTE format('GRANT INSERT ON %I.ticket TO service_role', app_schema);
    EXECUTE format('GRANT UPDATE ON %I.ticket TO service_role', app_schema);
    EXECUTE format('GRANT DELETE ON %I.ticket TO service_role', app_schema);
END $$;

GRANT EXECUTE ON FUNCTION insert_ticket(text, text, text, text, text, text, jsonb) TO service_role;
GRANT EXECUTE ON FUNCTION fetch_user_tickets(text) TO service_role;
GRANT EXECUTE ON FUNCTION update_ticket_status(uuid, text) TO service_role;
GRANT EXECUTE ON FUNCTION fetch_all_tickets(text, text, integer, integer) TO service_role;
GRANT EXECUTE ON FUNCTION update_ticket_updated_at() TO service_role;

-- 9. 完成提示
DO $$
DECLARE
    app_schema TEXT := get_schema_name();
BEGIN
    RAISE NOTICE 'Ticket system migration completed successfully for schema: %', app_schema;
    RAISE NOTICE 'Created tables: ticket';
    RAISE NOTICE 'Created functions: insert_ticket, fetch_user_tickets, update_ticket_status, fetch_all_tickets';
    RAISE NOTICE 'Priority values: 高, 中, 低';
    RAISE NOTICE 'Status values: 处理中, 已解决';
END $$;