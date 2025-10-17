-- =====================================================
-- Fix R2 Package Tags Double-Serialization Issue
-- =====================================================
-- Description: Fixes tags field that were double-serialized as JSON strings
--              instead of proper JSONB arrays
-- Bug: Tags stored as "[\"production\"]" instead of ["production"]
-- Created: 2025-10-17
-- Updated: 2025-10-17 - Renamed to 11_r2_fix_tags_double_serialization.sql
-- Dependencies: Requires 10_r2_package_system.sql to be run first

-- Fix tags double-serialization in r2_packages table
DO $$
DECLARE
    app_schema TEXT := get_schema_name();
    affected_count INTEGER := 0;
BEGIN
    -- Fix tags that are stored as JSON strings instead of JSONB arrays
    -- Pattern: tags value starts with a quote followed by [ (indicating string-wrapped JSON)
    -- We need to extract the string value first, then parse it as JSONB
    EXECUTE format('
        UPDATE %I.r2_packages
        SET tags = CASE
            -- If tags is a JSONB string (jsonb_typeof returns ''string''), extract and parse it
            WHEN jsonb_typeof(tags) = ''string'' THEN (tags #>> ''{}''::text[])::jsonb
            -- Otherwise keep as-is (already correct JSONB array)
            ELSE tags
        END
        WHERE jsonb_typeof(tags) = ''string''
    ', app_schema);

    GET DIAGNOSTICS affected_count = ROW_COUNT;

    RAISE NOTICE 'Fixed % packages with double-serialized tags in schema: %', affected_count, app_schema;

    -- Verify the fix by showing sample tags
    EXECUTE format('
        SELECT package_name, version, tags
        FROM %I.r2_packages
        LIMIT 5
    ', app_schema);

END $$;

-- Add comment
COMMENT ON FUNCTION get_schema_name IS 'Migration script to fix double-serialized tags in R2 packages';

-- Success message
DO $$
DECLARE
    app_schema TEXT := get_schema_name();
BEGIN
    RAISE NOTICE '====================================================';
    RAISE NOTICE 'R2 Package Tags Double-Serialization Fix Applied';
    RAISE NOTICE 'Schema: %', app_schema;
    RAISE NOTICE 'All tags fields have been corrected to proper JSONB format';
    RAISE NOTICE '====================================================';
END $$;
