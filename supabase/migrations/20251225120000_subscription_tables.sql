-- =====================================================
-- Stripe Subscription Tables Migration
-- =====================================================
-- Created: 2025-12-25
-- Purpose: Add subscription tracking for Stripe monthly subscriptions
-- Dependencies: 00_schema_init.sql (get_schema_name function)
-- =====================================================

-- =====================================================
-- 1. Create subscription table
-- =====================================================
DO $$
DECLARE
    app_schema TEXT := get_schema_name();
BEGIN
    EXECUTE format('
        CREATE TABLE IF NOT EXISTS %I.subscription (
            id uuid NOT NULL DEFAULT gen_random_uuid() PRIMARY KEY,
            created_at timestamp with time zone NOT NULL DEFAULT now(),
            updated_at timestamp with time zone NOT NULL DEFAULT now(),

            -- User identification
            user_email text NOT NULL,

            -- Stripe identifiers
            stripe_customer_id text NOT NULL,
            stripe_subscription_id text NOT NULL UNIQUE,
            stripe_price_id text NOT NULL,

            -- Subscription status
            -- Values: trialing, active, past_due, canceled, unpaid, incomplete, incomplete_expired
            status text NOT NULL DEFAULT ''trialing'',

            -- Period tracking
            current_period_start timestamp with time zone NOT NULL,
            current_period_end timestamp with time zone NOT NULL,
            trial_start timestamp with time zone,
            trial_end timestamp with time zone,

            -- Cancellation tracking
            cancel_at_period_end boolean DEFAULT false,
            canceled_at timestamp with time zone,
            ended_at timestamp with time zone,

            -- Product reference
            plan_id text NOT NULL,
            product_id uuid,

            -- Metadata
            metadata jsonb DEFAULT ''{}''
        )',
        app_schema
    );

    RAISE NOTICE 'Created subscription table in schema: %', app_schema;
END $$;

-- =====================================================
-- 2. Create indexes for subscription table
-- =====================================================
DO $$
DECLARE
    app_schema TEXT := get_schema_name();
BEGIN
    -- Index on user_email for user lookup
    EXECUTE format('
        CREATE INDEX IF NOT EXISTS idx_subscription_user_email
        ON %I.subscription(user_email)',
        app_schema
    );

    -- Index on stripe_subscription_id for webhook lookups
    EXECUTE format('
        CREATE INDEX IF NOT EXISTS idx_subscription_stripe_sub_id
        ON %I.subscription(stripe_subscription_id)',
        app_schema
    );

    -- Index on status for filtering active subscriptions
    EXECUTE format('
        CREATE INDEX IF NOT EXISTS idx_subscription_status
        ON %I.subscription(status)',
        app_schema
    );

    -- Index on period_end for renewal processing
    EXECUTE format('
        CREATE INDEX IF NOT EXISTS idx_subscription_period_end
        ON %I.subscription(current_period_end)',
        app_schema
    );

    -- Index on stripe_customer_id
    EXECUTE format('
        CREATE INDEX IF NOT EXISTS idx_subscription_customer_id
        ON %I.subscription(stripe_customer_id)',
        app_schema
    );

    RAISE NOTICE 'Created subscription indexes in schema: %', app_schema;
END $$;

-- =====================================================
-- 3. Add subscription fields to order table
-- =====================================================
DO $$
DECLARE
    app_schema TEXT := get_schema_name();
BEGIN
    -- Add stripe_subscription_id column
    EXECUTE format('
        ALTER TABLE %I.order
        ADD COLUMN IF NOT EXISTS stripe_subscription_id text',
        app_schema
    );

    -- Add subscription_type column (one_time or subscription)
    EXECUTE format('
        ALTER TABLE %I.order
        ADD COLUMN IF NOT EXISTS subscription_type text DEFAULT ''one_time''',
        app_schema
    );

    -- Create index for subscription orders
    EXECUTE format('
        CREATE INDEX IF NOT EXISTS idx_order_stripe_subscription
        ON %I.order(stripe_subscription_id)
        WHERE stripe_subscription_id IS NOT NULL',
        app_schema
    );

    RAISE NOTICE 'Added subscription fields to order table in schema: %', app_schema;
END $$;

-- =====================================================
-- 4. Create subscription functions
-- =====================================================

-- 4.1 Insert subscription function
CREATE OR REPLACE FUNCTION insert_subscription(
    p_user_email text,
    p_stripe_customer_id text,
    p_stripe_subscription_id text,
    p_stripe_price_id text,
    p_status text,
    p_current_period_start timestamptz,
    p_current_period_end timestamptz,
    p_trial_start timestamptz DEFAULT NULL,
    p_trial_end timestamptz DEFAULT NULL,
    p_plan_id text DEFAULT 'monthly_subscription',
    p_metadata jsonb DEFAULT '{}'
)
RETURNS uuid
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
DECLARE
    app_schema TEXT := get_schema_name();
    new_id uuid;
BEGIN
    EXECUTE format('
        INSERT INTO %I.subscription (
            user_email,
            stripe_customer_id,
            stripe_subscription_id,
            stripe_price_id,
            status,
            current_period_start,
            current_period_end,
            trial_start,
            trial_end,
            plan_id,
            metadata
        ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11)
        RETURNING id',
        app_schema
    )
    INTO new_id
    USING
        p_user_email,
        p_stripe_customer_id,
        p_stripe_subscription_id,
        p_stripe_price_id,
        p_status,
        p_current_period_start,
        p_current_period_end,
        p_trial_start,
        p_trial_end,
        p_plan_id,
        p_metadata;

    RETURN new_id;
END;
$$;

-- 4.2 Update subscription status function
CREATE OR REPLACE FUNCTION update_subscription_status(
    p_stripe_subscription_id text,
    p_status text,
    p_current_period_start timestamptz DEFAULT NULL,
    p_current_period_end timestamptz DEFAULT NULL,
    p_cancel_at_period_end boolean DEFAULT NULL,
    p_canceled_at timestamptz DEFAULT NULL,
    p_ended_at timestamptz DEFAULT NULL
)
RETURNS boolean
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
DECLARE
    app_schema TEXT := get_schema_name();
    affected_rows integer;
BEGIN
    EXECUTE format('
        UPDATE %I.subscription
        SET
            status = $1,
            current_period_start = COALESCE($2, current_period_start),
            current_period_end = COALESCE($3, current_period_end),
            cancel_at_period_end = COALESCE($4, cancel_at_period_end),
            canceled_at = COALESCE($5, canceled_at),
            ended_at = COALESCE($6, ended_at),
            updated_at = now()
        WHERE stripe_subscription_id = $7',
        app_schema
    )
    USING
        p_status,
        p_current_period_start,
        p_current_period_end,
        p_cancel_at_period_end,
        p_canceled_at,
        p_ended_at,
        p_stripe_subscription_id;

    GET DIAGNOSTICS affected_rows = ROW_COUNT;
    RETURN affected_rows > 0;
END;
$$;

-- 4.3 Get user active subscription function
CREATE OR REPLACE FUNCTION get_user_active_subscription(p_user_email text)
RETURNS TABLE (
    id uuid,
    user_email text,
    stripe_customer_id text,
    stripe_subscription_id text,
    stripe_price_id text,
    status text,
    current_period_start timestamptz,
    current_period_end timestamptz,
    trial_start timestamptz,
    trial_end timestamptz,
    cancel_at_period_end boolean,
    canceled_at timestamptz,
    plan_id text,
    product_id uuid,
    created_at timestamptz,
    updated_at timestamptz
)
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
DECLARE
    app_schema TEXT := get_schema_name();
BEGIN
    RETURN QUERY EXECUTE format('
        SELECT
            s.id,
            s.user_email,
            s.stripe_customer_id,
            s.stripe_subscription_id,
            s.stripe_price_id,
            s.status,
            s.current_period_start,
            s.current_period_end,
            s.trial_start,
            s.trial_end,
            s.cancel_at_period_end,
            s.canceled_at,
            s.plan_id,
            s.product_id,
            s.created_at,
            s.updated_at
        FROM %I.subscription s
        WHERE s.user_email = $1
          AND s.status IN (''trialing'', ''active'', ''past_due'')
        ORDER BY s.created_at DESC
        LIMIT 1',
        app_schema
    )
    USING p_user_email;
END;
$$;

-- 4.4 Get subscription by Stripe ID function
CREATE OR REPLACE FUNCTION get_subscription_by_stripe_id(p_stripe_subscription_id text)
RETURNS TABLE (
    id uuid,
    user_email text,
    stripe_customer_id text,
    stripe_subscription_id text,
    stripe_price_id text,
    status text,
    current_period_start timestamptz,
    current_period_end timestamptz,
    trial_start timestamptz,
    trial_end timestamptz,
    cancel_at_period_end boolean,
    canceled_at timestamptz,
    ended_at timestamptz,
    plan_id text,
    product_id uuid,
    unique_name text,
    created_at timestamptz,
    updated_at timestamptz
)
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
DECLARE
    app_schema TEXT := get_schema_name();
BEGIN
    RETURN QUERY EXECUTE format('
        SELECT
            s.id,
            s.user_email,
            s.stripe_customer_id,
            s.stripe_subscription_id,
            s.stripe_price_id,
            s.status,
            s.current_period_start,
            s.current_period_end,
            s.trial_start,
            s.trial_end,
            s.cancel_at_period_end,
            s.canceled_at,
            s.ended_at,
            s.plan_id,
            s.product_id,
            s.unique_name,
            s.created_at,
            s.updated_at
        FROM %I.subscription s
        WHERE s.stripe_subscription_id = $1',
        app_schema
    )
    USING p_stripe_subscription_id;
END;
$$;

-- 4.5 Mark subscription as canceled function
CREATE OR REPLACE FUNCTION mark_subscription_canceled(
    p_stripe_subscription_id text,
    p_cancel_at_period_end boolean DEFAULT true,
    p_canceled_at timestamptz DEFAULT NULL
)
RETURNS boolean
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
DECLARE
    app_schema TEXT := get_schema_name();
    affected_rows integer;
BEGIN
    EXECUTE format('
        UPDATE %I.subscription
        SET
            cancel_at_period_end = $1,
            canceled_at = COALESCE($2, now()),
            updated_at = now()
        WHERE stripe_subscription_id = $3',
        app_schema
    )
    USING
        p_cancel_at_period_end,
        p_canceled_at,
        p_stripe_subscription_id;

    GET DIAGNOSTICS affected_rows = ROW_COUNT;
    RETURN affected_rows > 0;
END;
$$;

-- 4.6 Update subscription product_id function
CREATE OR REPLACE FUNCTION update_subscription_product(
    p_stripe_subscription_id text,
    p_product_id uuid
)
RETURNS boolean
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
DECLARE
    app_schema TEXT := get_schema_name();
    affected_rows integer;
BEGIN
    EXECUTE format('
        UPDATE %I.subscription
        SET
            product_id = $1,
            updated_at = now()
        WHERE stripe_subscription_id = $2',
        app_schema
    )
    USING
        p_product_id,
        p_stripe_subscription_id;

    GET DIAGNOSTICS affected_rows = ROW_COUNT;
    RETURN affected_rows > 0;
END;
$$;

-- 4.7 Get all user subscriptions (including canceled)
CREATE OR REPLACE FUNCTION get_user_subscriptions(p_user_email text)
RETURNS TABLE (
    id uuid,
    stripe_subscription_id text,
    status text,
    current_period_start timestamptz,
    current_period_end timestamptz,
    trial_end timestamptz,
    cancel_at_period_end boolean,
    plan_id text,
    created_at timestamptz
)
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
DECLARE
    app_schema TEXT := get_schema_name();
BEGIN
    RETURN QUERY EXECUTE format('
        SELECT
            s.id,
            s.stripe_subscription_id,
            s.status,
            s.current_period_start,
            s.current_period_end,
            s.trial_end,
            s.cancel_at_period_end,
            s.plan_id,
            s.created_at
        FROM %I.subscription s
        WHERE s.user_email = $1
        ORDER BY s.created_at DESC',
        app_schema
    )
    USING p_user_email;
END;
$$;

-- =====================================================
-- 5. Grant permissions
-- =====================================================
GRANT EXECUTE ON FUNCTION insert_subscription TO service_role;
GRANT EXECUTE ON FUNCTION update_subscription_status TO service_role;
GRANT EXECUTE ON FUNCTION get_user_active_subscription TO service_role;
GRANT EXECUTE ON FUNCTION get_subscription_by_stripe_id TO service_role;
GRANT EXECUTE ON FUNCTION mark_subscription_canceled TO service_role;
GRANT EXECUTE ON FUNCTION update_subscription_product TO service_role;
GRANT EXECUTE ON FUNCTION get_user_subscriptions TO service_role;

-- =====================================================
-- 6. Verification
-- =====================================================
DO $$
DECLARE
    app_schema TEXT := get_schema_name();
BEGIN
    RAISE NOTICE '====================================================';
    RAISE NOTICE 'Subscription tables migration completed successfully';
    RAISE NOTICE 'Schema: %', app_schema;
    RAISE NOTICE '====================================================';
    RAISE NOTICE 'Created:';
    RAISE NOTICE '  - Table: %.subscription', app_schema;
    RAISE NOTICE '  - Indexes: idx_subscription_*';
    RAISE NOTICE '  - Order table columns: stripe_subscription_id, subscription_type';
    RAISE NOTICE '  - Functions: insert_subscription, update_subscription_status, etc.';
    RAISE NOTICE '====================================================';
END $$;
