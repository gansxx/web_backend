-- =====================================================
-- 工单系统自动解决触发器
-- =====================================================
-- 功能：当工单添加管理员答复时，自动将状态更新为"已解决"并记录答复时间
-- 创建日期：2025-10-02
-- 使用方法: psql -v ON_ERROR_STOP=1 -f ticket_auto_resolve_trigger.sql
-- =====================================================
-- 前置依赖：
--   1. 必须先执行 00_schema_init.sql 初始化 schema 配置
--   2. 必须先执行 ticket_system.sql 创建 ticket 表
--   该脚本依赖 get_schema_name() 函数获取 schema 名称
-- =====================================================

-- 1. 创建触发器函数：当添加或更新答复时自动解决工单
CREATE OR REPLACE FUNCTION auto_resolve_ticket_on_reply()
RETURNS TRIGGER AS $$
BEGIN
    -- 检查是否设置了答复（reply 不为空）
    IF NEW.reply IS NOT NULL AND NEW.reply != '' THEN
        -- 检查是否是新添加答复或更新答复
        IF (OLD.reply IS NULL OR OLD.reply = '') OR (OLD.reply != NEW.reply) THEN
            -- 自动设置状态为"已解决"
            NEW.status := '已解决';
            -- 自动设置答复时间为当前时间
            NEW.replied_at := NOW();

            RAISE NOTICE 'Auto-resolved ticket % due to reply addition/update', NEW.id;
        END IF;
    END IF;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- 2. 为 ticket 表创建 BEFORE UPDATE 触发器
DO $$
DECLARE
    app_schema TEXT := get_schema_name();
BEGIN
    -- 删除已存在的触发器（如果存在）
    EXECUTE format('
        DROP TRIGGER IF EXISTS ticket_auto_resolve_trigger ON %I.ticket',
        app_schema
    );

    -- 创建新触发器
    EXECUTE format('
        CREATE TRIGGER ticket_auto_resolve_trigger
        BEFORE UPDATE ON %I.ticket
        FOR EACH ROW
        EXECUTE FUNCTION auto_resolve_ticket_on_reply()',
        app_schema
    );

    RAISE NOTICE 'Created auto-resolve trigger for ticket table in schema: %', app_schema;
END $$;

-- 3. 授予权限
GRANT EXECUTE ON FUNCTION auto_resolve_ticket_on_reply() TO service_role;

-- 4. 完成提示
DO $$
DECLARE
    app_schema TEXT := get_schema_name();
BEGIN
    RAISE NOTICE 'Ticket auto-resolve trigger migration completed successfully for schema: %', app_schema;
    RAISE NOTICE 'Created function: auto_resolve_ticket_on_reply()';
    RAISE NOTICE 'Created trigger: ticket_auto_resolve_trigger';
    RAISE NOTICE 'Behavior: When reply is added (NULL/empty -> non-empty), automatically set status="已解决" and replied_at=NOW()';
END $$;
