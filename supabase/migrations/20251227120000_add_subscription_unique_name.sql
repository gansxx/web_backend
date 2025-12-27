-- =====================================================
-- Add unique_name Column to Subscription Table
-- =====================================================
-- Created: 2025-12-27
-- Purpose: Add unique_name column to store server-side unique identifier
--          for subscription renewals (format: email_timestamp)
-- Dependencies: 20251225120000_subscription_tables.sql
-- =====================================================

-- =====================================================
-- 1. Add unique_name column to subscription table
-- =====================================================
DO $$
DECLARE
    app_schema TEXT := get_schema_name();
BEGIN
    -- Add unique_name column
    EXECUTE format('
        ALTER TABLE %I.subscription
        ADD COLUMN IF NOT EXISTS unique_name text',
        app_schema
    );

    -- Create index for unique_name lookup
    EXECUTE format('
        CREATE INDEX IF NOT EXISTS idx_subscription_unique_name
        ON %I.subscription(unique_name)
        WHERE unique_name IS NOT NULL',
        app_schema
    );

    RAISE NOTICE 'Added unique_name column to subscription table in schema: %', app_schema;
END $$;

-- =====================================================
-- 2. Create function to update subscription with unique_name
-- =====================================================
CREATE OR REPLACE FUNCTION update_subscription_product_with_unique_name(
    p_stripe_subscription_id text,
    p_product_id uuid,
    p_unique_name text DEFAULT NULL
) RETURNS boolean AS $$
DECLARE
    app_schema TEXT := get_schema_name();
    rows_affected INTEGER;
BEGIN
    EXECUTE format('
        UPDATE %I.subscription
        SET product_id = COALESCE($1, product_id),
            unique_name = COALESCE($2, unique_name),
            updated_at = now()
        WHERE stripe_subscription_id = $3',
        app_schema
    )
    USING p_product_id, p_unique_name, p_stripe_subscription_id;

    GET DIAGNOSTICS rows_affected = ROW_COUNT;
    RETURN rows_affected > 0;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- =====================================================
-- 3. Comment on the new column
-- =====================================================
DO $$
DECLARE
    app_schema TEXT := get_schema_name();
BEGIN
    EXECUTE format('
        COMMENT ON COLUMN %I.subscription.unique_name IS
        ''Server-side unique identifier for subscription renewals. Format: email_timestamp (e.g., user@example.com_1737456789)''',
        app_schema
    );
END $$;
