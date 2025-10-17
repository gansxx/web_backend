-- =====================================================
-- R2 Package Management System
-- =====================================================
-- Description: Database schema for Cloudflare R2 software package distribution
-- Dependencies: Requires 00_schema_init.sql (for get_schema_name() function)
-- Version: 2.0 - Updated to use dynamic schema
-- Created: 2025-10-15
-- Updated: 2025-10-15 - Moved to dynamic schema

-- 1. Create r2_packages table in configured schema
DO $$
DECLARE
    app_schema TEXT := get_schema_name();
BEGIN
    EXECUTE format('
        CREATE TABLE IF NOT EXISTS %I.r2_packages (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            package_name TEXT NOT NULL,
            version TEXT NOT NULL,
            r2_key TEXT NOT NULL UNIQUE,
            file_size BIGINT NOT NULL,
            file_hash TEXT NOT NULL,
            hash_algorithm TEXT NOT NULL DEFAULT ''sha256'',
            description TEXT,
            tags JSONB DEFAULT ''[]''::jsonb,
            is_public BOOLEAN DEFAULT false,
            uploader_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
            download_count INTEGER DEFAULT 0,
            status TEXT NOT NULL DEFAULT ''active'' CHECK (status IN (''active'', ''archived'', ''deleted'')),
            metadata JSONB DEFAULT ''{}''::jsonb,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

            CONSTRAINT r2_packages_version_check CHECK (version ~ ''^[0-9]+\.[0-9]+\.[0-9]+(-[a-zA-Z0-9.-]+)?(\+[a-zA-Z0-9.-]+)?$'')
        )', app_schema);

    RAISE NOTICE 'Created table: %.r2_packages', app_schema;
END $$;

-- 2. Create indexes for performance optimization
DO $$
DECLARE
    app_schema TEXT := get_schema_name();
BEGIN
    EXECUTE format('CREATE INDEX IF NOT EXISTS idx_r2_packages_name_version ON %I.r2_packages(package_name, version)', app_schema);
    EXECUTE format('CREATE INDEX IF NOT EXISTS idx_r2_packages_uploader ON %I.r2_packages(uploader_id)', app_schema);
    EXECUTE format('CREATE INDEX IF NOT EXISTS idx_r2_packages_status ON %I.r2_packages(status)', app_schema);
    EXECUTE format('CREATE INDEX IF NOT EXISTS idx_r2_packages_created_at ON %I.r2_packages(created_at DESC)', app_schema);
    EXECUTE format('CREATE INDEX IF NOT EXISTS idx_r2_packages_is_public ON %I.r2_packages(is_public) WHERE is_public = true', app_schema);
    EXECUTE format('CREATE INDEX IF NOT EXISTS idx_r2_packages_tags ON %I.r2_packages USING GIN(tags)', app_schema);

    -- Unique constraint for package name + version combination
    EXECUTE format('CREATE UNIQUE INDEX IF NOT EXISTS idx_r2_packages_unique_name_version ON %I.r2_packages(package_name, version) WHERE status != ''deleted''', app_schema);

    RAISE NOTICE 'Created indexes for: %.r2_packages', app_schema;
END $$;

-- 3. Create download history table
DO $$
DECLARE
    app_schema TEXT := get_schema_name();
BEGIN
    EXECUTE format('
        CREATE TABLE IF NOT EXISTS %I.r2_package_downloads (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            package_id UUID NOT NULL REFERENCES %I.r2_packages(id) ON DELETE CASCADE,
            user_id UUID REFERENCES auth.users(id) ON DELETE SET NULL,
            ip_address INET,
            user_agent TEXT,
            downloaded_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )', app_schema, app_schema);

    EXECUTE format('CREATE INDEX IF NOT EXISTS idx_r2_downloads_package ON %I.r2_package_downloads(package_id)', app_schema);
    EXECUTE format('CREATE INDEX IF NOT EXISTS idx_r2_downloads_user ON %I.r2_package_downloads(user_id)', app_schema);
    EXECUTE format('CREATE INDEX IF NOT EXISTS idx_r2_downloads_time ON %I.r2_package_downloads(downloaded_at DESC)', app_schema);

    RAISE NOTICE 'Created table: %.r2_package_downloads', app_schema;
END $$;

-- 4. Function: Update updated_at timestamp automatically
CREATE OR REPLACE FUNCTION update_r2_package_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- 5. Create trigger for updated_at
DO $$
DECLARE
    app_schema TEXT := get_schema_name();
BEGIN
    EXECUTE format('DROP TRIGGER IF EXISTS trigger_r2_package_updated_at ON %I.r2_packages', app_schema);
    EXECUTE format('
        CREATE TRIGGER trigger_r2_package_updated_at
        BEFORE UPDATE ON %I.r2_packages
        FOR EACH ROW
        EXECUTE FUNCTION update_r2_package_updated_at()', app_schema);

    RAISE NOTICE 'Created trigger: trigger_r2_package_updated_at on %.r2_packages', app_schema;
END $$;

-- 6. Function: Increment download count and log download
CREATE OR REPLACE FUNCTION record_r2_package_download(
    p_package_id UUID,
    p_user_id UUID DEFAULT NULL,
    p_ip_address INET DEFAULT NULL,
    p_user_agent TEXT DEFAULT NULL
)
RETURNS VOID AS $$
DECLARE
    app_schema TEXT := get_schema_name();
BEGIN
    -- Increment download count
    EXECUTE format('
        UPDATE %I.r2_packages
        SET download_count = download_count + 1
        WHERE id = $1', app_schema)
    USING p_package_id;

    -- Log download event
    EXECUTE format('
        INSERT INTO %I.r2_package_downloads (package_id, user_id, ip_address, user_agent)
        VALUES ($1, $2, $3, $4)', app_schema)
    USING p_package_id, p_user_id, p_ip_address, p_user_agent;
END;
$$ LANGUAGE plpgsql;

-- 7. Function: Get package statistics
CREATE OR REPLACE FUNCTION get_r2_package_stats(p_package_name TEXT DEFAULT NULL)
RETURNS TABLE (
    package_name TEXT,
    total_versions INTEGER,
    total_downloads BIGINT,
    total_size_bytes BIGINT,
    total_size_mb NUMERIC,
    latest_version TEXT,
    latest_upload_date TIMESTAMPTZ
) AS $$
DECLARE
    app_schema TEXT := get_schema_name();
BEGIN
    RETURN QUERY EXECUTE format('
        SELECT
            p.package_name,
            COUNT(DISTINCT p.version)::INTEGER as total_versions,
            SUM(p.download_count)::BIGINT as total_downloads,
            SUM(p.file_size)::BIGINT as total_size_bytes,
            ROUND(SUM(p.file_size)::NUMERIC / (1024 * 1024), 2) as total_size_mb,
            (SELECT version FROM %I.r2_packages
             WHERE package_name = p.package_name AND status = ''active''
             ORDER BY created_at DESC LIMIT 1) as latest_version,
            MAX(p.created_at) as latest_upload_date
        FROM %I.r2_packages p
        WHERE p.status = ''active''
            AND ($1 IS NULL OR p.package_name = $1)
        GROUP BY p.package_name', app_schema, app_schema)
    USING p_package_name;
END;
$$ LANGUAGE plpgsql;

-- 8. Function: Clean up old archived versions
CREATE OR REPLACE FUNCTION cleanup_old_r2_packages(p_days_threshold INTEGER DEFAULT 90)
RETURNS TABLE (
    package_id UUID,
    package_name TEXT,
    version TEXT,
    r2_key TEXT
) AS $$
DECLARE
    app_schema TEXT := get_schema_name();
BEGIN
    RETURN QUERY EXECUTE format('
        UPDATE %I.r2_packages
        SET status = ''deleted''
        WHERE status = ''archived''
            AND updated_at < NOW() - ($1 || '' days'')::INTERVAL
        RETURNING id, package_name, version, r2_key', app_schema)
    USING p_days_threshold;
END;
$$ LANGUAGE plpgsql;

-- 9. Function: Search packages by name or tags
CREATE OR REPLACE FUNCTION search_r2_packages(
    p_search_term TEXT DEFAULT NULL,
    p_tags TEXT[] DEFAULT NULL,
    p_is_public BOOLEAN DEFAULT NULL,
    p_limit INTEGER DEFAULT 50,
    p_offset INTEGER DEFAULT 0
)
RETURNS TABLE (
    id UUID,
    package_name TEXT,
    version TEXT,
    description TEXT,
    tags JSONB,
    is_public BOOLEAN,
    download_count INTEGER,
    file_size BIGINT,
    created_at TIMESTAMPTZ
) AS $$
DECLARE
    app_schema TEXT := get_schema_name();
BEGIN
    RETURN QUERY EXECUTE format('
        SELECT
            p.id,
            p.package_name,
            p.version,
            p.description,
            p.tags,
            p.is_public,
            p.download_count,
            p.file_size,
            p.created_at
        FROM %I.r2_packages p
        WHERE p.status = ''active''
            AND ($1 IS NULL OR
                 p.package_name ILIKE ''%%'' || $1 || ''%%'' OR
                 p.description ILIKE ''%%'' || $1 || ''%%'')
            AND ($2 IS NULL OR p.tags ?| $2)
            AND ($3 IS NULL OR p.is_public = $3)
        ORDER BY p.created_at DESC
        LIMIT $4
        OFFSET $5', app_schema)
    USING p_search_term, p_tags, p_is_public, p_limit, p_offset;
END;
$$ LANGUAGE plpgsql;

-- 10. Function: Get package versions with pagination
CREATE OR REPLACE FUNCTION get_r2_package_versions(
    p_package_name TEXT,
    p_limit INTEGER DEFAULT 20,
    p_offset INTEGER DEFAULT 0
)
RETURNS TABLE (
    id UUID,
    version TEXT,
    file_size BIGINT,
    download_count INTEGER,
    status TEXT,
    created_at TIMESTAMPTZ
) AS $$
DECLARE
    app_schema TEXT := get_schema_name();
BEGIN
    RETURN QUERY EXECUTE format('
        SELECT
            p.id,
            p.version,
            p.file_size,
            p.download_count,
            p.status,
            p.created_at
        FROM %I.r2_packages p
        WHERE p.package_name = $1
            AND p.status IN (''active'', ''archived'')
        ORDER BY p.created_at DESC
        LIMIT $2
        OFFSET $3', app_schema)
    USING p_package_name, p_limit, p_offset;
END;
$$ LANGUAGE plpgsql;

-- 11. Enable Row Level Security (RLS)
DO $$
DECLARE
    app_schema TEXT := get_schema_name();
BEGIN
    EXECUTE format('ALTER TABLE %I.r2_packages ENABLE ROW LEVEL SECURITY', app_schema);
    EXECUTE format('ALTER TABLE %I.r2_package_downloads ENABLE ROW LEVEL SECURITY', app_schema);

    RAISE NOTICE 'Enabled RLS on tables in schema: %', app_schema;
END $$;

-- 12. Drop existing policies if they exist
DO $$
DECLARE
    app_schema TEXT := get_schema_name();
BEGIN
    EXECUTE format('DROP POLICY IF EXISTS "r2_packages_select_public" ON %I.r2_packages', app_schema);
    EXECUTE format('DROP POLICY IF EXISTS "r2_packages_select_own" ON %I.r2_packages', app_schema);
    EXECUTE format('DROP POLICY IF EXISTS "r2_packages_insert_auth" ON %I.r2_packages', app_schema);
    EXECUTE format('DROP POLICY IF EXISTS "r2_packages_update_own" ON %I.r2_packages', app_schema);
    EXECUTE format('DROP POLICY IF EXISTS "r2_packages_delete_own" ON %I.r2_packages', app_schema);
    EXECUTE format('DROP POLICY IF EXISTS "r2_downloads_select_own_packages" ON %I.r2_package_downloads', app_schema);
    EXECUTE format('DROP POLICY IF EXISTS "r2_downloads_insert_system" ON %I.r2_package_downloads', app_schema);

    RAISE NOTICE 'Dropped existing RLS policies for schema: %', app_schema;
END $$;

-- 13. Create RLS Policies
DO $$
DECLARE
    app_schema TEXT := get_schema_name();
BEGIN
    -- Policy: Public packages are readable by everyone
    EXECUTE format('
        CREATE POLICY "r2_packages_select_public" ON %I.r2_packages
        FOR SELECT
        USING (is_public = true AND status = ''active'')', app_schema);

    -- Policy: Users can read their own packages
    EXECUTE format('
        CREATE POLICY "r2_packages_select_own" ON %I.r2_packages
        FOR SELECT
        USING (auth.uid() = uploader_id)', app_schema);

    -- Policy: Authenticated users can insert packages
    EXECUTE format('
        CREATE POLICY "r2_packages_insert_auth" ON %I.r2_packages
        FOR INSERT
        WITH CHECK (auth.uid() = uploader_id)', app_schema);

    -- Policy: Users can update their own packages
    EXECUTE format('
        CREATE POLICY "r2_packages_update_own" ON %I.r2_packages
        FOR UPDATE
        USING (auth.uid() = uploader_id)', app_schema);

    -- Policy: Users can delete their own packages (soft delete via status)
    EXECUTE format('
        CREATE POLICY "r2_packages_delete_own" ON %I.r2_packages
        FOR UPDATE
        USING (auth.uid() = uploader_id AND status = ''deleted'')', app_schema);

    -- Policy: Users can view download history of their packages
    EXECUTE format('
        CREATE POLICY "r2_downloads_select_own_packages" ON %I.r2_package_downloads
        FOR SELECT
        USING (
            EXISTS (
                SELECT 1 FROM %I.r2_packages
                WHERE id = package_id AND uploader_id = auth.uid()
            )
        )', app_schema, app_schema);

    -- Policy: System can insert download records (via function)
    EXECUTE format('
        CREATE POLICY "r2_downloads_insert_system" ON %I.r2_package_downloads
        FOR INSERT
        WITH CHECK (true)', app_schema);

    RAISE NOTICE 'Created RLS policies for schema: %', app_schema;
END $$;

-- 14. Grant necessary permissions
DO $$
DECLARE
    app_schema TEXT := get_schema_name();
BEGIN
    EXECUTE format('GRANT SELECT, INSERT, UPDATE ON %I.r2_packages TO authenticated', app_schema);
    EXECUTE format('GRANT SELECT, INSERT ON %I.r2_package_downloads TO authenticated', app_schema);
    EXECUTE format('GRANT USAGE ON ALL SEQUENCES IN SCHEMA %I TO authenticated', app_schema);

    EXECUTE format('GRANT SELECT, INSERT, UPDATE ON %I.r2_packages TO service_role', app_schema);
    EXECUTE format('GRANT SELECT, INSERT ON %I.r2_package_downloads TO service_role', app_schema);
    EXECUTE format('GRANT USAGE ON ALL SEQUENCES IN SCHEMA %I TO service_role', app_schema);

    RAISE NOTICE 'Granted permissions for schema: %', app_schema;
END $$;

-- 15. Add comments for documentation
DO $$
DECLARE
    app_schema TEXT := get_schema_name();
BEGIN
    EXECUTE format('COMMENT ON TABLE %I.r2_packages IS ''Software packages stored in Cloudflare R2 with version management''', app_schema);
    EXECUTE format('COMMENT ON TABLE %I.r2_package_downloads IS ''Download history tracking for R2 packages''', app_schema);
END $$;

COMMENT ON FUNCTION record_r2_package_download IS 'Records a package download and increments counter';
COMMENT ON FUNCTION get_r2_package_stats IS 'Returns aggregated statistics for packages';
COMMENT ON FUNCTION cleanup_old_r2_packages IS 'Marks old archived packages as deleted for cleanup';
COMMENT ON FUNCTION search_r2_packages IS 'Full-text search across package names, descriptions, and tags';
COMMENT ON FUNCTION get_r2_package_versions IS 'Returns all versions of a specific package with pagination';

-- 16. Create view for package overview
DO $$
DECLARE
    app_schema TEXT := get_schema_name();
BEGIN
    EXECUTE format('DROP VIEW IF EXISTS %I.r2_packages_overview', app_schema);
    EXECUTE format('
        CREATE VIEW %I.r2_packages_overview AS
        SELECT
            p.id,
            p.package_name,
            p.version,
            p.description,
            p.tags,
            p.is_public,
            p.file_size,
            p.download_count,
            p.status,
            p.created_at,
            u.email as uploader_email
        FROM %I.r2_packages p
        JOIN auth.users u ON p.uploader_id = u.id
        WHERE p.status = ''active''', app_schema, app_schema);

    EXECUTE format('COMMENT ON VIEW %I.r2_packages_overview IS ''Convenient view of active packages with uploader information''', app_schema);

    RAISE NOTICE 'Created view: %.r2_packages_overview', app_schema;
END $$;

-- 17. Grant function execution permissions
GRANT EXECUTE ON FUNCTION update_r2_package_updated_at() TO service_role;
GRANT EXECUTE ON FUNCTION record_r2_package_download(UUID, UUID, INET, TEXT) TO service_role;
GRANT EXECUTE ON FUNCTION get_r2_package_stats(TEXT) TO service_role;
GRANT EXECUTE ON FUNCTION cleanup_old_r2_packages(INTEGER) TO service_role;
GRANT EXECUTE ON FUNCTION search_r2_packages(TEXT, TEXT[], BOOLEAN, INTEGER, INTEGER) TO service_role;
GRANT EXECUTE ON FUNCTION get_r2_package_versions(TEXT, INTEGER, INTEGER) TO service_role;

GRANT EXECUTE ON FUNCTION record_r2_package_download(UUID, UUID, INET, TEXT) TO authenticated;
GRANT EXECUTE ON FUNCTION get_r2_package_stats(TEXT) TO authenticated;
GRANT EXECUTE ON FUNCTION search_r2_packages(TEXT, TEXT[], BOOLEAN, INTEGER, INTEGER) TO authenticated;
GRANT EXECUTE ON FUNCTION get_r2_package_versions(TEXT, INTEGER, INTEGER) TO authenticated;

-- 18. CRUD Functions for schema-agnostic operations

-- Function: Create package
CREATE OR REPLACE FUNCTION create_r2_package(
    p_package_name TEXT,
    p_version TEXT,
    p_r2_key TEXT,
    p_file_size BIGINT,
    p_file_hash TEXT,
    p_hash_algorithm TEXT,
    p_uploader_id UUID,
    p_description TEXT DEFAULT NULL,
    p_tags JSONB DEFAULT '[]'::jsonb,
    p_is_public BOOLEAN DEFAULT false,
    p_metadata JSONB DEFAULT '{}'::jsonb
)
RETURNS TABLE (
    id UUID,
    package_name TEXT,
    version TEXT,
    r2_key TEXT,
    file_size BIGINT,
    file_hash TEXT,
    hash_algorithm TEXT,
    uploader_id UUID,
    description TEXT,
    tags JSONB,
    is_public BOOLEAN,
    download_count INTEGER,
    status TEXT,
    metadata JSONB,
    created_at TIMESTAMPTZ,
    updated_at TIMESTAMPTZ
) AS $$
DECLARE
    app_schema TEXT := get_schema_name();
BEGIN
    RETURN QUERY EXECUTE format('
        INSERT INTO %I.r2_packages (
            package_name, version, r2_key, file_size, file_hash, hash_algorithm,
            uploader_id, description, tags, is_public, metadata
        )
        VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11)
        RETURNING id, package_name, version, r2_key, file_size, file_hash, hash_algorithm,
                  uploader_id, description, tags, is_public, download_count, status, metadata,
                  created_at, updated_at', app_schema)
    USING p_package_name, p_version, p_r2_key, p_file_size, p_file_hash, p_hash_algorithm,
          p_uploader_id, p_description, p_tags, p_is_public, p_metadata;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- Function: Get package by ID
CREATE OR REPLACE FUNCTION get_r2_package_by_id(p_package_id UUID)
RETURNS TABLE (
    id UUID,
    package_name TEXT,
    version TEXT,
    r2_key TEXT,
    file_size BIGINT,
    file_hash TEXT,
    hash_algorithm TEXT,
    uploader_id UUID,
    description TEXT,
    tags JSONB,
    is_public BOOLEAN,
    download_count INTEGER,
    status TEXT,
    metadata JSONB,
    created_at TIMESTAMPTZ,
    updated_at TIMESTAMPTZ
) AS $$
DECLARE
    app_schema TEXT := get_schema_name();
BEGIN
    RETURN QUERY EXECUTE format('
        SELECT id, package_name, version, r2_key, file_size, file_hash, hash_algorithm,
               uploader_id, description, tags, is_public, download_count, status, metadata,
               created_at, updated_at
        FROM %I.r2_packages
        WHERE id = $1', app_schema)
    USING p_package_id;
END;
$$ LANGUAGE plpgsql;

-- Function: Get package by name and version
CREATE OR REPLACE FUNCTION get_r2_package(
    p_package_name TEXT,
    p_version TEXT
)
RETURNS TABLE (
    id UUID,
    package_name TEXT,
    version TEXT,
    r2_key TEXT,
    file_size BIGINT,
    file_hash TEXT,
    hash_algorithm TEXT,
    uploader_id UUID,
    description TEXT,
    tags JSONB,
    is_public BOOLEAN,
    download_count INTEGER,
    status TEXT,
    metadata JSONB,
    created_at TIMESTAMPTZ,
    updated_at TIMESTAMPTZ
) AS $$
DECLARE
    app_schema TEXT := get_schema_name();
BEGIN
    RETURN QUERY EXECUTE format('
        SELECT id, package_name, version, r2_key, file_size, file_hash, hash_algorithm,
               uploader_id, description, tags, is_public, download_count, status, metadata,
               created_at, updated_at
        FROM %I.r2_packages
        WHERE package_name = $1
          AND version = $2
          AND status = ''active''', app_schema)
    USING p_package_name, p_version;
END;
$$ LANGUAGE plpgsql;

-- Function: Update package metadata
CREATE OR REPLACE FUNCTION update_r2_package(
    p_package_id UUID,
    p_description TEXT DEFAULT NULL,
    p_tags JSONB DEFAULT NULL,
    p_is_public BOOLEAN DEFAULT NULL,
    p_status TEXT DEFAULT NULL,
    p_metadata JSONB DEFAULT NULL
)
RETURNS TABLE (
    id UUID,
    package_name TEXT,
    version TEXT,
    r2_key TEXT,
    file_size BIGINT,
    file_hash TEXT,
    hash_algorithm TEXT,
    uploader_id UUID,
    description TEXT,
    tags JSONB,
    is_public BOOLEAN,
    download_count INTEGER,
    status TEXT,
    metadata JSONB,
    created_at TIMESTAMPTZ,
    updated_at TIMESTAMPTZ
) AS $$
DECLARE
    app_schema TEXT := get_schema_name();
    update_query TEXT;
BEGIN
    update_query := format('UPDATE %I.r2_packages SET ', app_schema);

    IF p_description IS NOT NULL THEN
        update_query := update_query || 'description = $1, ';
    END IF;
    IF p_tags IS NOT NULL THEN
        update_query := update_query || 'tags = $2, ';
    END IF;
    IF p_is_public IS NOT NULL THEN
        update_query := update_query || 'is_public = $3, ';
    END IF;
    IF p_status IS NOT NULL THEN
        update_query := update_query || 'status = $4, ';
    END IF;
    IF p_metadata IS NOT NULL THEN
        update_query := update_query || 'metadata = $5, ';
    END IF;

    -- Remove trailing comma and space
    update_query := RTRIM(update_query, ', ');
    update_query := update_query || format(' WHERE id = $6 RETURNING id, package_name, version, r2_key, file_size, file_hash, hash_algorithm, uploader_id, description, tags, is_public, download_count, status, metadata, created_at, updated_at');

    RETURN QUERY EXECUTE update_query
    USING p_description, p_tags, p_is_public, p_status, p_metadata, p_package_id;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- Function: Delete package (soft or hard delete)
CREATE OR REPLACE FUNCTION delete_r2_package(
    p_package_id UUID,
    p_hard_delete BOOLEAN DEFAULT false
)
RETURNS BOOLEAN AS $$
DECLARE
    app_schema TEXT := get_schema_name();
    rows_affected INTEGER;
BEGIN
    IF p_hard_delete THEN
        -- Hard delete: permanently remove from database
        EXECUTE format('DELETE FROM %I.r2_packages WHERE id = $1', app_schema)
        USING p_package_id;
    ELSE
        -- Soft delete: mark as deleted
        EXECUTE format('UPDATE %I.r2_packages SET status = ''deleted'' WHERE id = $1', app_schema)
        USING p_package_id;
    END IF;

    GET DIAGNOSTICS rows_affected = ROW_COUNT;
    RETURN rows_affected > 0;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- Function: List user packages
CREATE OR REPLACE FUNCTION list_user_r2_packages(
    p_user_id UUID,
    p_limit INTEGER DEFAULT 50,
    p_offset INTEGER DEFAULT 0
)
RETURNS TABLE (
    id UUID,
    package_name TEXT,
    version TEXT,
    r2_key TEXT,
    file_size BIGINT,
    file_hash TEXT,
    hash_algorithm TEXT,
    uploader_id UUID,
    description TEXT,
    tags JSONB,
    is_public BOOLEAN,
    download_count INTEGER,
    status TEXT,
    metadata JSONB,
    created_at TIMESTAMPTZ,
    updated_at TIMESTAMPTZ
) AS $$
DECLARE
    app_schema TEXT := get_schema_name();
BEGIN
    RETURN QUERY EXECUTE format('
        SELECT id, package_name, version, r2_key, file_size, file_hash, hash_algorithm,
               uploader_id, description, tags, is_public, download_count, status, metadata,
               created_at, updated_at
        FROM %I.r2_packages
        WHERE uploader_id = $1
          AND status = ''active''
        ORDER BY created_at DESC
        LIMIT $2 OFFSET $3', app_schema)
    USING p_user_id, p_limit, p_offset;
END;
$$ LANGUAGE plpgsql;

-- Function: List public packages
CREATE OR REPLACE FUNCTION list_public_r2_packages(
    p_limit INTEGER DEFAULT 50,
    p_offset INTEGER DEFAULT 0
)
RETURNS TABLE (
    id UUID,
    package_name TEXT,
    version TEXT,
    r2_key TEXT,
    file_size BIGINT,
    file_hash TEXT,
    hash_algorithm TEXT,
    uploader_id UUID,
    description TEXT,
    tags JSONB,
    is_public BOOLEAN,
    download_count INTEGER,
    status TEXT,
    metadata JSONB,
    created_at TIMESTAMPTZ,
    updated_at TIMESTAMPTZ
) AS $$
DECLARE
    app_schema TEXT := get_schema_name();
BEGIN
    RETURN QUERY EXECUTE format('
        SELECT id, package_name, version, r2_key, file_size, file_hash, hash_algorithm,
               uploader_id, description, tags, is_public, download_count, status, metadata,
               created_at, updated_at
        FROM %I.r2_packages
        WHERE is_public = true
          AND status = ''active''
        ORDER BY created_at DESC
        LIMIT $1 OFFSET $2', app_schema)
    USING p_limit, p_offset;
END;
$$ LANGUAGE plpgsql;

-- Function: Check package exists
CREATE OR REPLACE FUNCTION check_r2_package_exists(
    p_package_name TEXT,
    p_version TEXT
)
RETURNS BOOLEAN AS $$
DECLARE
    app_schema TEXT := get_schema_name();
    package_count INTEGER;
BEGIN
    EXECUTE format('
        SELECT COUNT(*) FROM %I.r2_packages
        WHERE package_name = $1
          AND version = $2
          AND status != ''deleted''', app_schema)
    INTO package_count
    USING p_package_name, p_version;

    RETURN package_count > 0;
END;
$$ LANGUAGE plpgsql;

-- Function: Get download history
CREATE OR REPLACE FUNCTION get_r2_download_history(
    p_package_id UUID,
    p_limit INTEGER DEFAULT 50,
    p_offset INTEGER DEFAULT 0
)
RETURNS TABLE (
    id UUID,
    package_id UUID,
    user_id UUID,
    ip_address INET,
    user_agent TEXT,
    downloaded_at TIMESTAMPTZ
) AS $$
DECLARE
    app_schema TEXT := get_schema_name();
BEGIN
    RETURN QUERY EXECUTE format('
        SELECT id, package_id, user_id, ip_address, user_agent, downloaded_at
        FROM %I.r2_package_downloads
        WHERE package_id = $1
        ORDER BY downloaded_at DESC
        LIMIT $2 OFFSET $3', app_schema)
    USING p_package_id, p_limit, p_offset;
END;
$$ LANGUAGE plpgsql;

-- 19. Grant execution permissions for new functions
GRANT EXECUTE ON FUNCTION create_r2_package(TEXT, TEXT, TEXT, BIGINT, TEXT, TEXT, UUID, TEXT, JSONB, BOOLEAN, JSONB) TO service_role;
GRANT EXECUTE ON FUNCTION get_r2_package_by_id(UUID) TO service_role, authenticated;
GRANT EXECUTE ON FUNCTION get_r2_package(TEXT, TEXT) TO service_role, authenticated;
GRANT EXECUTE ON FUNCTION update_r2_package(UUID, TEXT, JSONB, BOOLEAN, TEXT, JSONB) TO service_role;
GRANT EXECUTE ON FUNCTION delete_r2_package(UUID, BOOLEAN) TO service_role;
GRANT EXECUTE ON FUNCTION list_user_r2_packages(UUID, INTEGER, INTEGER) TO service_role, authenticated;
GRANT EXECUTE ON FUNCTION list_public_r2_packages(INTEGER, INTEGER) TO service_role, authenticated, anon;
GRANT EXECUTE ON FUNCTION check_r2_package_exists(TEXT, TEXT) TO service_role, authenticated;
GRANT EXECUTE ON FUNCTION get_r2_download_history(UUID, INTEGER, INTEGER) TO service_role, authenticated;

-- 20. Add function comments
COMMENT ON FUNCTION create_r2_package IS 'Creates a new package record in the configured schema';
COMMENT ON FUNCTION get_r2_package_by_id IS 'Retrieves package by UUID';
COMMENT ON FUNCTION get_r2_package IS 'Retrieves active package by name and version';
COMMENT ON FUNCTION update_r2_package IS 'Updates package metadata fields';
COMMENT ON FUNCTION delete_r2_package IS 'Deletes package (soft delete by default)';
COMMENT ON FUNCTION list_user_r2_packages IS 'Lists all packages uploaded by a specific user';
COMMENT ON FUNCTION list_public_r2_packages IS 'Lists all public packages';
COMMENT ON FUNCTION check_r2_package_exists IS 'Checks if a package version exists';
COMMENT ON FUNCTION get_r2_download_history IS 'Retrieves download history for a package';

-- Success message
DO $$
DECLARE
    app_schema TEXT := get_schema_name();
BEGIN
    RAISE NOTICE '====================================================';
    RAISE NOTICE 'R2 Package Management System schema created successfully';
    RAISE NOTICE 'Schema: %', app_schema;
    RAISE NOTICE 'Tables: %.r2_packages, %.r2_package_downloads', app_schema, app_schema;
    RAISE NOTICE 'Functions: 15 package management functions (6 existing + 9 CRUD)';
    RAISE NOTICE 'RLS Policies: 7 security policies';
    RAISE NOTICE 'View: %.r2_packages_overview', app_schema;
    RAISE NOTICE '====================================================';
END $$;
