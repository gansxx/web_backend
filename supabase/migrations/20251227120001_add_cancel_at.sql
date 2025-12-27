-- =====================================================
-- Add cancel_at Column and Update Functions
-- =====================================================
-- Created: 2025-12-27
-- Purpose: Add cancel_at timestamp and cancellation_details support
-- Dependencies: 20251225120000_subscription_tables.sql
-- =====================================================

-- =====================================================
-- 1. Add cancel_at column to subscription table
-- =====================================================
DO $$
DECLARE
    app_schema TEXT := get_schema_name();
BEGIN
    -- Add cancel_at column (when subscription is scheduled to cancel)
    EXECUTE format('
        ALTER TABLE %I.subscription
        ADD COLUMN IF NOT EXISTS cancel_at timestamp with time zone',
        app_schema
    );

    -- Create index for cancel_at lookup
    EXECUTE format('
        CREATE INDEX IF NOT EXISTS idx_subscription_cancel_at
        ON %I.subscription(cancel_at)
        WHERE cancel_at IS NOT NULL',
        app_schema
    );

    RAISE NOTICE 'Added cancel_at column to subscription table in schema: %', app_schema;
END $$;

-- =====================================================
-- 2. Update update_subscription_status function
-- =====================================================
-- Drop old function signature
DROP FUNCTION IF EXISTS update_subscription_status(
    text, text, timestamptz, timestamptz, boolean, timestamptz, timestamptz
);

-- Create new function with cancel_at and cancellation_details support
CREATE OR REPLACE FUNCTION update_subscription_status(
    p_stripe_subscription_id text,
    p_status text,
    p_current_period_start timestamptz DEFAULT NULL,
    p_current_period_end timestamptz DEFAULT NULL,
    p_cancel_at_period_end boolean DEFAULT NULL,
    p_canceled_at timestamptz DEFAULT NULL,
    p_ended_at timestamptz DEFAULT NULL,
    p_cancel_at timestamptz DEFAULT NULL,
    p_cancellation_details jsonb DEFAULT NULL
)
RETURNS boolean
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
DECLARE
    app_schema TEXT := get_schema_name();
    affected_rows integer;
    current_metadata jsonb;
BEGIN
    -- Get current metadata if updating cancellation_details
    IF p_cancellation_details IS NOT NULL THEN
        EXECUTE format('
            SELECT metadata FROM %I.subscription
            WHERE stripe_subscription_id = $1',
            app_schema
        )
        INTO current_metadata
        USING p_stripe_subscription_id;

        -- Merge cancellation_details into metadata
        current_metadata := COALESCE(current_metadata, '{}'::jsonb);
        current_metadata := current_metadata || jsonb_build_object('cancellation_details', p_cancellation_details);
    END IF;

    -- Update subscription
    EXECUTE format('
        UPDATE %I.subscription
        SET
            status = $1,
            current_period_start = COALESCE($2, current_period_start),
            current_period_end = COALESCE($3, current_period_end),
            cancel_at_period_end = COALESCE($4, cancel_at_period_end),
            canceled_at = COALESCE($5, canceled_at),
            ended_at = COALESCE($6, ended_at),
            cancel_at = COALESCE($7, cancel_at),
            metadata = COALESCE($8, metadata),
            updated_at = now()
        WHERE stripe_subscription_id = $9',
        app_schema
    )
    USING
        p_status,
        p_current_period_start,
        p_current_period_end,
        p_cancel_at_period_end,
        p_canceled_at,
        p_ended_at,
        p_cancel_at,
        current_metadata,
        p_stripe_subscription_id;

    GET DIAGNOSTICS affected_rows = ROW_COUNT;
    RETURN affected_rows > 0;
END;
$$;

-- Grant permissions
GRANT EXECUTE ON FUNCTION update_subscription_status TO service_role;

-- =====================================================
-- 3. Add column comment for documentation
-- =====================================================
DO $$
DECLARE
    app_schema TEXT := get_schema_name();
BEGIN
    EXECUTE format('
        COMMENT ON COLUMN %I.subscription.cancel_at IS
        ''Timestamp when subscription is scheduled to cancel (from Stripe cancel_at field)''',
        app_schema
    );
END $$;

-- =====================================================
-- 4. Verification
-- =====================================================
DO $$
DECLARE
    app_schema TEXT := get_schema_name();
BEGIN
    RAISE NOTICE '====================================================';
    RAISE NOTICE 'Add cancel_at migration completed successfully';
    RAISE NOTICE 'Schema: %', app_schema;
    RAISE NOTICE '====================================================';
    RAISE NOTICE 'Created:';
    RAISE NOTICE '  - Column: %.subscription.cancel_at', app_schema;
    RAISE NOTICE '  - Index: idx_subscription_cancel_at';
    RAISE NOTICE '  - Updated: update_subscription_status() function';
    RAISE NOTICE '====================================================';
END $$;
