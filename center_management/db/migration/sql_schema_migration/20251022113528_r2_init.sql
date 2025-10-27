-- Initialize R2 packages with sample data
-- This migration populates the r2_packages table with initial package data
-- All packages are owned by the admin user created in the previous migration

-- Admin user UUID (must match the one created in 20251022113527_create_admin_user.sql)
-- This ensures proper foreign key relationships
DO $$
DECLARE
  admin_user_id UUID := 'a0000000-0000-0000-0000-000000000001';
BEGIN
  -- Verify admin user exists before inserting packages
  IF NOT EXISTS (SELECT 1 FROM auth.users WHERE id = admin_user_id) THEN
    RAISE EXCEPTION 'Admin user not found. Please run 20251022113527_create_admin_user.sql first';
  END IF;

  -- Insert R2 package records
  -- Using INSERT with ON CONFLICT to make this migration idempotent
  INSERT INTO products.r2_packages (
    id,
    package_name,
    version,
    r2_key,
    file_size,
    file_hash,
    hash_algorithm,
    description,
    tags,
    is_public,
    uploader_id,
    download_count,
    status,
    metadata,
    created_at,
    updated_at
  ) VALUES
  -- Package 1: v2rayN Android APK
  (
    '01b9a3b5-6186-4f5a-8c6f-1f2626efb509',
    'v2rayN_android.apk',
    '1.0.0',
    'packages/v2rayN_android.apk/1.0.0/v2rayN_android.apk',
    35654848,
    '093a2fe5322e95994fcca2cf442e8569843aa365844fd3f0f2e1424ee16b39ec',
    'sha256',
    NULL,
    '["production"]'::jsonb,
    FALSE,
    admin_user_id, -- Updated to admin user
    5,
    'active',
    '{}'::jsonb,
    '2025-10-16 23:46:08.939376+08'::timestamptz,
    '2025-10-19 23:54:09.762063+08'::timestamptz
  ),
  -- Package 2: v2rayN Windows ZIP
  (
    '05ce3687-c358-4d60-84e7-07e2a89393f3',
    'v2rayN_windows.zip',
    '1.0.0',
    'packages/v2rayN_windows.zip/1.0.0/v2rayN_windows.zip',
    105194701,
    'be3d10425c2d02a9de3065e3b07644505f3edfb40a0a2dddb7f6662d7414dbcd',
    'sha256',
    'v2rayN for windows',
    '["production"]'::jsonb,
    FALSE,
    admin_user_id, -- Updated to admin user
    15,
    'active',
    '{}'::jsonb,
    '2025-10-17 14:09:39.986945+08'::timestamptz,
    '2025-10-19 23:54:09.464797+08'::timestamptz
  )
  ON CONFLICT (id) DO UPDATE SET
    uploader_id = EXCLUDED.uploader_id,
    updated_at = NOW();

  RAISE NOTICE '✓ Successfully inserted/updated % R2 packages', 2;
END $$;

-- Verify the data was inserted correctly
DO $$
DECLARE
  package_count INTEGER;
  admin_user_id UUID := 'a0000000-0000-0000-0000-000000000001';
BEGIN
  -- Count packages owned by admin
  SELECT COUNT(*) INTO package_count
  FROM products.r2_packages
  WHERE uploader_id = admin_user_id;

  IF package_count >= 2 THEN
    RAISE NOTICE '✓ Verification successful: % packages found for admin user', package_count;
  ELSE
    RAISE WARNING '⚠ Expected at least 2 packages for admin user, found %', package_count;
  END IF;

  -- Verify r2_packages_overview view has data
  SELECT COUNT(*) INTO package_count
  FROM products.r2_packages_overview
  WHERE uploader_email = 'admin@localhost';

  IF package_count >= 2 THEN
    RAISE NOTICE '✓ View verification successful: % packages in r2_packages_overview', package_count;
  ELSE
    RAISE WARNING '⚠ Expected at least 2 packages in overview, found %', package_count;
  END IF;
END $$;

-- Add helpful comments
COMMENT ON TABLE products.r2_packages IS 'Storage for R2 package metadata with version control';
