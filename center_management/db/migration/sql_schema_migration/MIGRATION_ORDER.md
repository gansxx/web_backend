# SQL Migration Execution Order

This document provides the chronological order for executing SQL migrations in this directory.

## Migration Timeline

All migration files follow the naming convention: `YYYYMMDDHHmmss_description.sql`

### Execution Sequence

| # | Timestamp | Filename | Description |
|---|-----------|----------|-------------|
| 1 | 20251017210439 | 20251017210439_schema_init.sql | Initial schema setup |
| 2 | 20251017210440 | 20251017210440_order_refactored.sql | Order system refactoring |
| 3 | 20251017210441 | 20251017210441_product_refactored.sql | Product system refactoring |
| 4 | 20251017210442 | 20251017210442_auth_user_webhook.sql | Authentication webhook setup |
| 5 | 20251017210443 | 20251017210443_ticket_system.sql | Ticket system initialization |
| 6 | 20251017210444 | 20251017210444_ticket_system_add_reply.sql | Ticket reply functionality |
| 7 | 20251017210445 | 20251017210445_ticket_auto_resolve_trigger.sql | Automated ticket resolution |
| 8 | 20251017210446 | 20251017210446_r2_package_system.sql | R2 package management system |
| 9 | 20251017210447 | 20251017210447_r2_fix_tags_double_serialization.sql | Fix R2 tags serialization |
| 10 | 20251022194534 | 20251022113528_r2_init.sql | R2 system initialization |
| 11 | 20251022220041 | 20251022113527_create_admin_user.sql | Admin user creation |
| 12 | 20251023211114 | 20251023211114_stripe_integration.sql | Stripe payment integration |
| 13 | 20251023220517 | 20251023220517_fix_table_ownership.sql | Database table ownership fixes |
| 14 | 20251023222618 | 20251023222618_add_get_order_by_id.sql | Get order by ID function |
| 15 | 20251027101157 | 20251027101157_add_product_status.sql | Product status field addition |
| 16 | 20251027173847 | 20251027173847_fix_insert_order_payment_provider.sql | Fix order payment provider |
| 17 | 20251027175640 | 20251027175640_add_update_order_payment_info.sql | Update order payment info |

## Notes

### Historical Context
- Migrations 1-9 were initially created with numeric prefixes (00-11) on 2025-10-17
- The timestamps for these migrations were incremented by 1 second each to maintain execution order
- Migrations 10-11 were originally created with timestamp names and maintain their original timestamps
- Later migrations (12-17) use their actual file modification timestamps

### Execution Guidelines
1. **Always run migrations in sequential order** as shown in the table above
2. **Never skip migrations** - each migration may have dependencies on previous ones
3. **For new environments**: Run all migrations from #1 to the latest
4. **For existing environments**: Only run migrations that haven't been applied yet

### Special Notes
- Migration #13 (20251023220517_fix_table_ownership.sql) requires `supabase_admin` privileges
- Most other migrations can be run as the `postgres` user
- Some migrations may require specific environment variables or manual intervention - check individual migration files for details

## Running Migrations

### Using psql (postgres user)
```bash
source .env
psql "postgresql://postgres:$POSTGRES_PASSWORD@localhost:5438/postgres" -v ON_ERROR_STOP=1 -f center_management/db/migration/sql_schema_migration/[migration_file].sql
```

### Using psql (supabase_admin user) - for ownership migrations
```bash
source .env
PGPASSWORD=$POSTGRES_PASSWORD psql -U supabase_admin -h localhost -p 5438 -d postgres -v ON_ERROR_STOP=1 -f center_management/db/migration/sql_schema_migration/[migration_file].sql
```

## Migration Tracking

It's recommended to maintain a migration tracking table in your database to record which migrations have been applied. This helps prevent accidental re-application of migrations and provides an audit trail.
