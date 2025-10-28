-- Create admin user for R2 package management
-- This migration creates a system admin user for managing packages
--
-- IMPORTANT: This migration only creates the user structure.
-- The admin password must be set separately using Supabase Auth API or Dashboard.
-- See instructions at the bottom of this file for password setup.

-- Create a fixed UUID for the admin user
-- Using a deterministic UUID for consistency across environments
CREATE EXTENSION IF NOT EXISTS pgcrypto;
DO $$
DECLARE
  admin_user_id UUID := 'a0000000-0000-0000-0000-000000000001';
  admin_email TEXT := 'admin@local.com';
BEGIN
  -- Check if user already exists
  IF NOT EXISTS (SELECT 1 FROM auth.users WHERE id = admin_user_id) THEN
    -- Insert admin user into auth.users with empty password
    -- Password will be set via Supabase Auth API after migration
    INSERT INTO auth.users (
      id,
      instance_id,
      email,
      encrypted_password,
      email_confirmed_at,
      created_at,
      updated_at,
      role,
      aud,
      confirmation_token,
      recovery_token,
      email_change_token_new,
      email_change
    ) VALUES (
      admin_user_id,
      '00000000-0000-0000-0000-000000000000',
      admin_email,
      '', -- Password will be set via Supabase Auth API
      NOW(),
      NOW(),
      NOW(),
      'authenticated',
      'authenticated',
      '',
      '',
      '',
      ''
    );

    -- Insert identity for the user (required for Supabase Auth)
    -- Note: email is a generated column and should not be manually inserted
    INSERT INTO auth.identities (
      id,
      provider_id,
      user_id,
      identity_data,
      provider,
      last_sign_in_at,
      created_at,
      updated_at
    ) VALUES (
      gen_random_uuid(),
      admin_user_id::text, -- provider_id is required and must be text
      admin_user_id,
      jsonb_build_object(
        'sub', admin_user_id::text,
        'email', admin_email,
        'email_verified', true,
        'phone_verified', false
      ),
      'email',
      NOW(),
      NOW(),
      NOW()
    );

    RAISE NOTICE 'Admin user created with email: %', admin_email;
    RAISE NOTICE 'Password must be set via Supabase Auth API or Dashboard before login!';
  ELSE
    RAISE NOTICE 'Admin user already exists with email: %', admin_email;
  END IF;
END $$;

-- Comment for documentation
COMMENT ON EXTENSION pgcrypto IS 'Used for UUID generation and cryptographic functions';

-- Verify the user was created
DO $$
BEGIN
  IF EXISTS (SELECT 1 FROM auth.users WHERE email = 'admin@local.com') THEN
    RAISE NOTICE '✓ Admin user structure created successfully';
  ELSE
    RAISE EXCEPTION '✗ Admin user creation failed';
  END IF;
END $$;

-- ================================================================================
-- PASSWORD SETUP INSTRUCTIONS
-- ================================================================================
--
-- This migration creates the admin user structure but does NOT set a password.
-- You MUST set the admin password using one of these methods:
--
-- METHOD 1: Supabase Dashboard (Recommended for initial setup)
-- 1. Go to your Supabase project dashboard
-- 2. Navigate to Authentication > Users
-- 3. Find the admin@local.com user
-- 4. Click "Reset password" and set a secure password
--
-- METHOD 2: Supabase Client API (For automated deployment)
--
-- /*
-- import { createClient } from '@supabase/supabase-js'
--
-- const supabase = createClient(
--   'your-project-url',
--   'your-service-role-key'
-- )
--
-- async function setAdminPassword() {
--   const { data, error } = await supabase.auth.admin.updateUserById(
--     'a0000000-0000-0000-0000-000000000001',
--     { password: 'your-secure-password-here' }
--   )
--
--   if (error) {
--     console.error('Failed to set admin password:', error)
--   } else {
--     console.log('Admin password set successfully')
--   }
-- }
--
-- setAdminPassword()
-- */
--
-- SECURITY NOTES:
-- - Use a strong password (12+ characters, mixed case, numbers, symbols)
-- - Change the default email from admin@local.com in production
-- - Store the password securely in your environment variables or vault
-- - Consider using multi-factor authentication for admin accounts
--
-- ================================================================================
