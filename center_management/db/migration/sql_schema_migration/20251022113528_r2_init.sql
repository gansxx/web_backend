-- =====================================================
-- R2 packages 初始化数据脚本
-- =====================================================
-- 功能：向 r2_packages 表中插入初始包数据
-- 使用方法：psql -v ON_ERROR_STOP=1 -f 20251022113528_r2_init.sql
-- =====================================================
-- 前置依赖：
--   1. 必须先执行 00_schema_init.sql 初始化 schema 配置
--   2. 必须先执行 10_r2_package_system.sql 创建 r2_packages 表
--   3. 必须先执行 20251022113527_create_admin_user.sql 创建管理员用户
-- =====================================================

-- Admin user UUID (must match the one created in 20251022113527_create_admin_user.sql)
-- This ensures proper foreign key relationships
DO $$
DECLARE
  app_schema TEXT := get_schema_name();
  admin_user_id UUID := 'a0000000-0000-0000-0000-000000000001';
BEGIN
  -- Verify admin user exists before inserting packages
  IF NOT EXISTS (SELECT 1 FROM auth.users WHERE id = admin_user_id) THEN
    RAISE EXCEPTION 'Admin user not found. Please run 20251022113527_create_admin_user.sql first';
  END IF;

  -- Insert R2 package records
  -- Using INSERT with ON CONFLICT to make this migration idempotent
  EXECUTE format('
    INSERT INTO %I.r2_packages (
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
      $1,
      ''v2rayN_android.apk'',
      ''1.0.0'',
      ''packages/v2rayN_android.apk/1.0.0/v2rayN_android.apk'',
      35654848,
      ''093a2fe5322e95994fcca2cf442e8569843aa365844fd3f0f2e1424ee16b39ec'',
      ''sha256'',
      NULL,
      ''["production"]''::jsonb,
      FALSE,
      $3,
      5,
      ''active'',
      ''{}''::jsonb,
      ''2025-10-16 23:46:08.939376+08''::timestamptz,
      ''2025-10-19 23:54:09.762063+08''::timestamptz
    ),
    -- Package 2: v2rayN Windows ZIP
    (
      $2,
      ''v2rayN_windows.zip'',
      ''1.0.0'',
      ''packages/v2rayN_windows.zip/1.0.0/v2rayN_windows.zip'',
      105194701,
      ''be3d10425c2d02a9de3065e3b07644505f3edfb40a0a2dddb7f6662d7414dbcd'',
      ''sha256'',
      ''v2rayN for windows'',
      ''["production"]''::jsonb,
      FALSE,
      $3,
      15,
      ''active'',
      ''{}''::jsonb,
      ''2025-10-17 14:09:39.986945+08''::timestamptz,
      ''2025-10-19 23:54:09.464797+08''::timestamptz
    )
    ON CONFLICT (id) DO UPDATE SET
      uploader_id = EXCLUDED.uploader_id,
      updated_at = NOW()
  ', app_schema)
  USING
    '01b9a3b5-6186-4f5a-8c6f-1f2626efb509'::uuid,  -- $1: Package 1 ID
    '05ce3687-c358-4d60-84e7-07e2a89393f3'::uuid,  -- $2: Package 2 ID
    admin_user_id;                                   -- $3: Admin user ID for uploader_id

  RAISE NOTICE '✓ Successfully inserted/updated % R2 packages', 2;
END $$;

-- Verify the data was inserted correctly
DO $$
DECLARE
  app_schema TEXT := get_schema_name();
  package_count INTEGER;
  admin_user_id UUID := 'a0000000-0000-0000-0000-000000000001';
BEGIN
  -- Count packages owned by admin
  EXECUTE format('
    SELECT COUNT(*) FROM %I.r2_packages WHERE uploader_id = $1
  ', app_schema) INTO package_count USING admin_user_id;

  IF package_count >= 2 THEN
    RAISE NOTICE '✓ Verification successful: % packages found for admin user', package_count;
  ELSE
    RAISE WARNING '⚠ Expected at least 2 packages for admin user, found %', package_count;
  END IF;

  -- Verify r2_packages_overview view has data
  EXECUTE format('
    SELECT COUNT(*) FROM %I.r2_packages_overview WHERE uploader_email = $1
  ', app_schema) INTO package_count USING 'admin@localhost';

  IF package_count >= 2 THEN
    RAISE NOTICE '✓ View verification successful: % packages in r2_packages_overview', package_count;
  ELSE
    RAISE WARNING '⚠ Expected at least 2 packages in overview, found %', package_count;
  END IF;

  -- Add helpful comments
  EXECUTE format('COMMENT ON TABLE %I.r2_packages IS ''Storage for R2 package metadata with version control''', app_schema);

  RAISE NOTICE '====================================================';
  RAISE NOTICE 'R2 packages initialization completed successfully';
  RAISE NOTICE 'Schema: %', app_schema;
  RAISE NOTICE 'Packages inserted: 2';
  RAISE NOTICE '====================================================';
END $$;
