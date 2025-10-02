#!/usr/bin/env python3
"""
PostgreSQL 数据库远程复制工具

支持功能:
1. 从远程数据库导出数据到本地文件
2. 从本地文件导入数据到本地数据库
3. 直接从远程数据库同步到本地数据库
4. 支持全库或指定表导出

使用示例:
    # 从远程导出全库
    python pg_dump_remote.py --export --source remote --output backup.sql

    # 导出指定表
    python pg_dump_remote.py --export --source remote --tables "orders,products" --output tables.sql

    # 导入本地
    python pg_dump_remote.py --import --file backup.sql --target local

    # 直接同步（导出+导入）
    python pg_dump_remote.py --sync --source remote --target local
"""

import os
import sys
import argparse
import subprocess
import tempfile
from datetime import datetime
from pathlib import Path
from loguru import logger
from remote_db_config import RemoteDbConfig
from ssh_tunnel import SSHTunnelManager


class PgDumpTool:
    """PostgreSQL 数据库导出导入工具"""

    def __init__(self, use_tunnel: bool = None):
        """
        初始化工具
        
        Args:
            use_tunnel: 是否使用SSH隧道（None=自动检测，True=强制使用，False=不使用）
        """
        self.project_root = Path(__file__).parent.parent.parent.parent
        self.backup_dir = self.project_root / 'center_management' / 'db' / 'migration' / 'backups'
        self.backup_dir.mkdir(exist_ok=True)
        self._use_tunnel_override = use_tunnel
        self._active_tunnel: SSHTunnelManager = None

    def check_pg_tools(self):
        """检查 pg_dump 和 psql 工具是否可用"""
        required_tools = ['pg_dump', 'psql']
        missing_tools = []

        for tool in required_tools:
            try:
                result = subprocess.run([tool, '--version'],
                                      capture_output=True, text=True, timeout=5)
                if result.returncode == 0:
                    logger.info(f"{tool} 可用: {result.stdout.strip()}")
                else:
                    missing_tools.append(tool)
            except (subprocess.TimeoutExpired, FileNotFoundError):
                missing_tools.append(tool)

        if missing_tools:
            logger.error(f"缺少必要工具: {', '.join(missing_tools)}")
            logger.info("请安装 PostgreSQL 客户端工具:")
            logger.info("Ubuntu/Debian: sudo apt-get install postgresql-client")
            logger.info("CentOS/RHEL: sudo yum install postgresql")
            logger.info("macOS: brew install postgresql")
            return False

        return True

    def _setup_ssh_tunnel(self, db_config: RemoteDbConfig):
        """
        设置SSH隧道（如果需要）

        Args:
            db_config: 数据库配置对象

        Returns:
            SSHTunnelManager instance or None
        """
        # 检查是否需要SSH隧道
        use_tunnel = self._use_tunnel_override
        if use_tunnel is None:
            use_tunnel = db_config.requires_ssh_tunnel()

        if not use_tunnel:
            return None

        # 获取SSH隧道配置
        tunnel_config = db_config.get_ssh_tunnel_config()
        if not tunnel_config:
            logger.warning("SSH隧道已启用但配置不完整，将尝试直接连接")
            return None

        try:
            tunnel = SSHTunnelManager(**tunnel_config)
            tunnel.start()
            self._active_tunnel = tunnel
            logger.success("SSH隧道已建立")
            return tunnel
        except Exception as e:
            logger.error(f"SSH隧道建立失败: {e}")
            raise

    def _cleanup_ssh_tunnel(self):
        """清理SSH隧道"""
        if self._active_tunnel:
            try:
                self._active_tunnel.stop()
                self._active_tunnel = None
                logger.info("SSH隧道已关闭")
            except Exception as e:
                logger.warning(f"关闭SSH隧道时出错: {e}")

    def generate_timestamp_filename(self, prefix="backup", suffix=".sql"):
        """生成带时间戳的文件名"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        return f"{prefix}_{timestamp}{suffix}"

    def export_database(self, source_type='remote', output_file=None, tables=None,
                       data_only=False, schema_only=False):
        """
        导出数据库

        Args:
            source_type: 数据源类型 ('remote' 或 'local')
            output_file: 输出文件路径，如果为空则自动生成
            tables: 要导出的表名列表，如果为空则导出全库
            data_only: 只导出数据，不导出结构
            schema_only: 只导出结构，不导出数据
        """
        logger.info(f"开始导出 {source_type} 数据库")

        # 获取数据库配置
        db_config = RemoteDbConfig(source_type)
        
        # 设置SSH隧道（如果需要）
        tunnel = None
        try:
            if source_type == 'remote':
                tunnel = self._setup_ssh_tunnel(db_config)
            
            # 测试连接
            if not db_config.test_connection():
                logger.error(f"无法连接到 {source_type} 数据库")
                return False

            postgres_config = db_config.get_postgres_config()

            # 生成输出文件名
            if not output_file:
                if tables:
                    table_str = "_".join(tables.split(",")[:3])  # 最多取前3个表名
                    prefix = f"tables_{table_str}"
                elif schema_only:
                    prefix = "schema"
                elif data_only:
                    prefix = "data"
                else:
                    prefix = f"full_{source_type}"

                output_file = self.backup_dir / self.generate_timestamp_filename(prefix)
            else:
                output_file = Path(output_file)
                if not output_file.is_absolute():
                    output_file = self.backup_dir / output_file

            # 构建 pg_dump 命令
            cmd = [
                'pg_dump',
                '--host', postgres_config['host'],
                '--port', str(postgres_config['port']),
                '--username', postgres_config['user'],
                '--dbname', postgres_config['database'],
                '--no-password',  # 使用环境变量传递密码
                '--verbose',
                '--file', str(output_file)
            ]

            # 添加选项
            if schema_only:
                cmd.append('--schema-only')
            elif data_only:
                cmd.append('--data-only')

            if tables:
                for table in tables.split(','):
                    table = table.strip()
                    if table:
                        cmd.extend(['--table', table])

            # 设置环境变量传递密码
            env = os.environ.copy()
            env['PGPASSWORD'] = postgres_config['password']

            logger.info(f"执行命令: {' '.join(cmd[:-2])} --file {output_file}")
            result = subprocess.run(cmd, env=env, capture_output=True,
                                  text=True, timeout=300)

            if result.returncode == 0:
                file_size = output_file.stat().st_size
                logger.success(f"导出成功: {output_file} ({file_size} bytes)")
                if result.stdout:
                    logger.debug(f"pg_dump 输出: {result.stdout}")
                return str(output_file)
            else:
                logger.error(f"导出失败: {result.stderr}")
                if output_file.exists():
                    output_file.unlink()  # 删除失败的文件
                return False

        except subprocess.TimeoutExpired:
            logger.error("导出超时（5分钟）")
            return False
        except Exception as e:
            logger.error(f"导出过程中发生错误: {str(e)}")
            return False
        finally:
            # 清理SSH隧道
            if tunnel and source_type == 'remote':
                self._cleanup_ssh_tunnel()

    def import_database(self, sql_file, target_type='local', clean_first=False, stop_services=True):
        """
        导入数据库

        Args:
            sql_file: SQL 文件路径
            target_type: 目标数据库类型 ('local' 或 'remote')
            clean_first: 是否先清理目标数据库
            stop_services: 是否停止Supabase服务以避免schema冲突
        """
        sql_file = Path(sql_file)
        if not sql_file.exists():
            logger.error(f"SQL 文件不存在: {sql_file}")
            return False

        logger.info(f"开始导入到 {target_type} 数据库: {sql_file}")

        # 获取数据库配置
        db_config = RemoteDbConfig(target_type)
        
        # 设置SSH隧道（如果需要）
        tunnel = None
        services_stopped = False
        
        try:
            if target_type == 'remote':
                tunnel = self._setup_ssh_tunnel(db_config)
            
            # 测试连接
            if not db_config.test_connection():
                logger.error(f"无法连接到 {target_type} 数据库")
                return False

            postgres_config = db_config.get_postgres_config()

            # 停止Supabase服务以避免schema自动重建
            if target_type == 'local' and clean_first and stop_services:
                logger.warning("停止Supabase服务以避免schema冲突...")
                stop_cmd = [
                    'docker', 'compose', 'stop',
                    'auth', 'rest', 'storage', 'realtime',
                    'kong', 'meta', 'supavisor'
                ]

                result = subprocess.run(stop_cmd, capture_output=True, text=True, cwd='/root/self_code/web_backend')
                if result.returncode == 0:
                    logger.info("Supabase服务已停止")
                    services_stopped = True
                else:
                    logger.warning(f"停止服务时出现警告: {result.stderr}")

            # 如果需要清理数据库
            if clean_first:
                logger.warning("清理目标数据库中的数据...")
                if not self.clean_database(target_type):
                    logger.error("清理数据库失败")
                    return False

            # 构建 psql 命令
            cmd = [
                'psql',
                '--host', postgres_config['host'],
                '--port', str(postgres_config['port']),
                '--username', postgres_config['user'],
                '--dbname', postgres_config['database'],
                '--no-password',
                '--file', str(sql_file),
                '--echo-errors',
                '-v', 'ON_ERROR_STOP=1'
            ]

            # 设置环境变量传递密码
            env = os.environ.copy()
            env['PGPASSWORD'] = postgres_config['password']

            logger.info(f"执行导入命令...")
            result = subprocess.run(cmd, env=env, capture_output=True,
                                  text=True, timeout=600)

            if result.returncode == 0:
                logger.success("数据导入成功")
                if result.stdout:
                    logger.debug(f"psql 输出: {result.stdout}")
                return True
            else:
                logger.error(f"数据导入失败: {result.stderr}")
                return False

        except subprocess.TimeoutExpired:
            logger.error("导入超时（10分钟）")
            return False
        except Exception as e:
            logger.error(f"导入过程中发生错误: {str(e)}")
            return False
        finally:
            # 重启Supabase服务
            if services_stopped:
                logger.info("重启Supabase服务...")
                start_cmd = [
                    'docker', 'compose', 'start',
                    'auth', 'rest', 'storage', 'realtime',
                    'kong', 'meta', 'supavisor'
                ]

                result = subprocess.run(start_cmd, capture_output=True, text=True, cwd='/root/self_code/web_backend')
                if result.returncode == 0:
                    logger.success("Supabase服务已重启")
                else:
                    logger.error(f"重启服务失败: {result.stderr}")
            
            # 清理SSH隧道
            if tunnel and target_type == 'remote':
                self._cleanup_ssh_tunnel()

    def clean_database(self, target_type='local'):
        """清理数据库（删除所有扩展、Supabase schemas和表）"""
        logger.warning(f"清理 {target_type} 数据库...")

        db_config = RemoteDbConfig(target_type)
        postgres_config = db_config.get_postgres_config()

        env = os.environ.copy()
        env['PGPASSWORD'] = postgres_config['password']

        try:
            # Phase 0: Drop PostgreSQL extensions first (they auto-create schemas)
            extensions = [
                'pgsodium', 'pg_cron', 'pg_net', 'pg_graphql',
                'pgcrypto', 'uuid-ossp', 'pg_stat_statements', 'timescaledb',
                'http', 'pg_tle', 'plpgsql_check'
            ]
            
            logger.info(f"清理 PostgreSQL extensions: {', '.join(extensions)}")
            
            for extension in extensions:
                drop_extension_sql = f"DROP EXTENSION IF EXISTS \"{extension}\" CASCADE;"
                
                cmd_drop_ext = [
                    'psql',
                    '--host', postgres_config['host'],
                    '--port', str(postgres_config['port']),
                    '--username', postgres_config['user'],
                    '--dbname', postgres_config['database'],
                    '--no-password',
                    '--command', drop_extension_sql
                ]
                
                result = subprocess.run(cmd_drop_ext, env=env, capture_output=True, text=True)
                if result.returncode == 0:
                    logger.debug(f"已删除 extension: {extension}")
                else:
                    logger.debug(f"Extension {extension} 不存在或已删除")

            # Phase 1: Drop Supabase schemas
            supabase_schemas = [
                '_realtime', 'auth', 'storage', 'extensions',
                'graphql_public', 'pgsodium', 'pgsodium_masks',
                'realtime', 'supabase_functions', 'vault', 'net'
            ]
            
            logger.info(f"清理 Supabase schemas: {', '.join(supabase_schemas)}")
            
            for schema in supabase_schemas:
                drop_schema_sql = f"DROP SCHEMA IF EXISTS {schema} CASCADE;"
                
                cmd_drop_schema = [
                    'psql',
                    '--host', postgres_config['host'],
                    '--port', str(postgres_config['port']),
                    '--username', postgres_config['user'],
                    '--dbname', postgres_config['database'],
                    '--no-password',
                    '--command', drop_schema_sql
                ]
                
                result = subprocess.run(cmd_drop_schema, env=env, capture_output=True, text=True)
                if result.returncode == 0:
                    logger.debug(f"已删除 schema: {schema}")
                else:
                    logger.debug(f"Schema {schema} 不存在或已删除")

            # Phase 2: Drop remaining tables in public schema
            # 获取所有用户表的命令
            sql_get_tables = """
            SELECT tablename FROM pg_tables
            WHERE schemaname = 'public'
            AND tablename NOT LIKE 'pg_%'
            AND tablename NOT LIKE '_realtime%'
            AND tablename NOT LIKE 'buckets'
            AND tablename NOT LIKE 'objects'
            AND tablename NOT LIKE 'migrations';
            """

            cmd = [
                'psql',
                '--host', postgres_config['host'],
                '--port', str(postgres_config['port']),
                '--username', postgres_config['user'],
                '--dbname', postgres_config['database'],
                '--no-password',
                '--tuples-only',
                '--command', sql_get_tables
            ]

            result = subprocess.run(cmd, env=env, capture_output=True, text=True)
            if result.returncode != 0:
                logger.error(f"获取表列表失败: {result.stderr}")
                return False

            tables = [line.strip() for line in result.stdout.split('\n')
                     if line.strip()]

            if not tables:
                logger.info("没有找到需要清理的表")
            else:
                logger.info(f"找到 {len(tables)} 个表需要清理: {', '.join(tables)}")

                # 删除所有表
                drop_tables_sql = "DROP TABLE IF EXISTS " + ", ".join(tables) + " CASCADE;"

                cmd_drop = [
                    'psql',
                    '--host', postgres_config['host'],
                    '--port', str(postgres_config['port']),
                    '--username', postgres_config['user'],
                    '--dbname', postgres_config['database'],
                    '--no-password',
                    '--command', drop_tables_sql
                ]

                result = subprocess.run(cmd_drop, env=env, capture_output=True, text=True)
                if result.returncode != 0:
                    logger.error(f"数据库清理失败: {result.stderr}")
                    return False

            logger.success("数据库清理完成")
            return True

        except Exception as e:
            logger.error(f"清理数据库时发生错误: {str(e)}")
            return False

    def apply_migrations(self, target_type='local', migration_files=None, drop_existing=True):
        """
        应用数据库迁移脚本

        Args:
            target_type: 目标数据库类型 ('local' 或 'remote')
            migration_files: 要应用的迁移文件列表，默认为自动扫描 sql_schema_migration 目录下所有 .sql 文件
            drop_existing: 是否先删除已存在的函数（解决权限冲突）

        Returns:
            bool: 成功返回 True，失败返回 False
        """
        logger.info(f"应用数据库迁移到 {target_type} 数据库...")

        # 迁移文件路径 - 使用本地 sql_schema_migration 目录
        migrations_dir = Path(__file__).parent / 'sql_schema_migration'

        # 自动发现迁移文件
        if migration_files is None:
            # 扫描目录中所有 .sql 文件（排除非迁移文件）
            all_sql_files = sorted(migrations_dir.glob('*.sql'))
            migration_files = []

            for sql_file in all_sql_files:
                filename = sql_file.name
                # 排除备份、测试等非迁移文件
                if not any(exclude in filename.lower() for exclude in ['backup', 'test', 'temp', 'old']):
                    migration_files.append(filename)

            if not migration_files:
                logger.warning(f"未在 {migrations_dir} 中找到任何迁移文件")
                return False

            logger.info(f"自动发现 {len(migration_files)} 个迁移文件: {', '.join(migration_files)}")

        db_config = RemoteDbConfig(target_type)
        postgres_config = db_config.get_postgres_config()

        # 设置环境变量
        env = os.environ.copy()
        env['PGPASSWORD'] = postgres_config['password']

        # 设置SSH隧道（如果需要）
        tunnel = None
        if target_type == 'remote':
            tunnel = self._setup_ssh_tunnel(db_config)
            if tunnel:
                postgres_config = tunnel

        try:
            # 授予 postgres 用户 schema 权限（解决权限问题）
            # 使用 supabase_admin 用户执行授权（与 postgres 使用相同密码）
            logger.info("使用 supabase_admin 授予 postgres 用户 schema 权限...")
            grant_sqls = [
                "GRANT CREATE ON SCHEMA test TO postgres;",
                "GRANT ALL PRIVILEGES ON SCHEMA test TO postgres;",
                "GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA test TO postgres;",
                "GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA test TO postgres;",
                "GRANT ALL PRIVILEGES ON ALL FUNCTIONS IN SCHEMA test TO postgres;"
            ]

            for grant_sql in grant_sqls:
                psql_cmd = [
                    'psql',
                    '--host', postgres_config['host'],
                    '--port', str(postgres_config['port']),
                    '--username', 'supabase_admin',  # 使用 supabase_admin 授权
                    '--dbname', postgres_config['database'],
                    '--no-password',
                    '--command', grant_sql
                ]

                result = subprocess.run(psql_cmd, env=env, capture_output=True, text=True)
                if result.returncode == 0:
                    logger.debug(f"权限授予成功: {grant_sql}")

            # 先删除可能存在的冲突函数（解决权限问题）
            if drop_existing:
                logger.info("删除已存在的函数以避免权限冲突...")
                functions_to_drop = [
                    'get_schema_name()',
                    'fetch_user_orders(text, text)',
                    'insert_order(text, int4, int4, text, text)',
                    'update_order_status(uuid, text)',
                    'check_and_expire_orders()',
                    'create_order_timeout_cron_job()',
                    'fetch_user_products(text, text)',
                    'insert_product(text, text, text, text, interval)',
                    'update_product_end_time(uuid, timestamptz)',
                    'get_product_info(uuid)',
                    'delete_expired_products()'
                ]

                for func in functions_to_drop:
                    drop_sql = f"DROP FUNCTION IF EXISTS {func} CASCADE;"

                    psql_cmd = [
                        'psql',
                        '--host', postgres_config['host'],
                        '--port', str(postgres_config['port']),
                        '--username', postgres_config['user'],
                        '--dbname', postgres_config['database'],
                        '--no-password',
                        '--command', drop_sql
                    ]

                    result = subprocess.run(psql_cmd, env=env, capture_output=True, text=True)
                    if result.returncode == 0:
                        logger.debug(f"已删除函数: {func}")

            for migration_file in migration_files:
                migration_path = migrations_dir / migration_file

                if not migration_path.exists():
                    logger.warning(f"迁移文件不存在: {migration_path}")
                    continue

                logger.info(f"应用迁移: {migration_file}")

                psql_cmd = [
                    'psql',
                    '--host', postgres_config['host'],
                    '--port', str(postgres_config['port']),
                    '--username', postgres_config['user'],
                    '--dbname', postgres_config['database'],
                    '--no-password',
                    '-v', 'ON_ERROR_STOP=1',  # 遇到错误立即停止
                    '-1',  # 在单个事务中执行
                    '-f', str(migration_path)
                ]

                result = subprocess.run(psql_cmd, env=env, capture_output=True, text=True)

                if result.returncode != 0:
                    logger.error(f"迁移失败: {migration_file}")
                    logger.error(f"错误信息: {result.stderr}")
                    return False

                # 显示成功消息
                if result.stdout:
                    for line in result.stdout.splitlines():
                        if 'NOTICE' in line:
                            logger.info(line.strip())

                logger.success(f"迁移完成: {migration_file}")

            logger.success("所有迁移脚本应用完成")
            return True

        except Exception as e:
            logger.error(f"应用迁移时发生错误: {str(e)}")
            return False
        finally:
            # 清理SSH隧道
            if tunnel and target_type == 'remote':
                self._cleanup_ssh_tunnel()

    def _grant_data_permissions(self, target_type='local', schema='test'):
        """
        授予postgres用户数据操作权限（DELETE、INSERT）
        使用 supabase_admin 用户执行（与postgres使用相同密码）

        Args:
            target_type: 目标数据库类型
            schema: Schema 名称
        """
        logger.info("使用 supabase_admin 授予 postgres 用户数据权限...")

        db_config = RemoteDbConfig(target_type)
        postgres_config = db_config.get_postgres_config()

        # 设置环境变量（使用同一密码）
        env = os.environ.copy()
        env['PGPASSWORD'] = postgres_config['password']

        # 授权SQL
        grant_sqls = [
            f"GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA {schema} TO postgres;",
            f"GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA {schema} TO postgres;",
        ]

        for grant_sql in grant_sqls:
            psql_cmd = [
                'psql',
                '--host', postgres_config['host'],
                '--port', str(postgres_config['port']),
                '--username', 'supabase_admin',  # 使用 supabase_admin 授权
                '--dbname', postgres_config['database'],
                '--no-password',
                '--command', grant_sql
            ]

            result = subprocess.run(psql_cmd, env=env, capture_output=True, text=True)
            if result.returncode == 0:
                logger.debug(f"权限授予成功: {grant_sql}")
            else:
                logger.warning(f"权限授予警告: {result.stderr}")

    def _get_business_tables(self, target_type='local', exclude_tables=None):
        """
        动态从数据库获取所有业务表列表
        
        Args:
            target_type: 目标数据库类型
            exclude_tables: 要排除的表列表（格式: ['schema.table', ...]）
            
        Returns:
            list: 业务表列表，格式为 ['schema.table', ...]
        """
        try:
            db_config = RemoteDbConfig(target_type)
            postgres_config = db_config.get_postgres_config()
            
            # 设置环境变量
            env = os.environ.copy()
            env['PGPASSWORD'] = postgres_config['password']
            
            # 定义要排除的系统 schema
            system_schemas = [
                '_realtime', 'extensions', 'graphql_public',
                'pgsodium', 'pgsodium_masks', 'realtime',
                'supabase_functions', 'vault', 'net', 'pg_catalog',
                'information_schema', 'pg_toast', 'cron', 'pg_temp'
            ]
            
            # 定义要排除的内部跟踪表
            internal_tables = [
                'auth.schema_migrations',
                'storage.migrations',
                'supabase_migrations.schema_migrations',
                'public.schema_config',
                'realtime.schema_migrations',
                'realtime.subscription',
            ]
            
            # 如果用户提供了额外的排除表，添加到列表
            if exclude_tables:
                internal_tables.extend(exclude_tables)
            
            # 构建 SQL 查询：获取所有非系统 schema 的表
            schema_filter = "', '".join(system_schemas)
            table_filter = "', '".join([f"{t.split('.')[0]}.{t.split('.')[1]}" for t in internal_tables])
            
            sql_query = f"""
            SELECT schemaname || '.' || tablename as full_table_name
            FROM pg_tables
            WHERE schemaname NOT IN ('{schema_filter}')
              AND schemaname || '.' || tablename NOT IN ('{table_filter}')
            ORDER BY schemaname, tablename;
            """
            
            # 执行查询
            cmd = [
                'psql',
                '--host', postgres_config['host'],
                '--port', str(postgres_config['port']),
                '--username', 'supabase_admin',
                '--dbname', postgres_config['database'],
                '--no-password',
                '--tuples-only',  # 只输出数据，不含表头
                '--no-align',     # 不对齐
                '-c', sql_query
            ]
            
            result = subprocess.run(cmd, env=env, capture_output=True, text=True)
            
            if result.returncode != 0:
                logger.error(f"查询业务表失败: {result.stderr}")
                return []
            
            # 解析结果
            tables = [line.strip() for line in result.stdout.strip().split('\n') if line.strip()]
            
            logger.info(f"发现 {len(tables)} 个业务表")
            logger.debug(f"业务表列表: {', '.join(tables)}")
            
            return tables
            
        except Exception as e:
            logger.error(f"获取业务表列表失败: {str(e)}")
            return []

    def _truncate_all_business_tables(self, target_type='local', exclude_tables=None):
        """
        清空所有业务schema中的表数据（动态查询版本）

        Args:
            target_type: 目标数据库类型
            exclude_tables: 额外要排除的表列表（格式: ['schema.table', ...]）

        Returns:
            bool: 成功返回 True
        """
        try:
            db_config = RemoteDbConfig(target_type)
            postgres_config = db_config.get_postgres_config()

            # 设置环境变量
            env = os.environ.copy()
            env['PGPASSWORD'] = postgres_config['password']

            # 动态获取业务表列表
            logger.info("动态查询业务表列表...")
            business_tables = self._get_business_tables(target_type, exclude_tables)
            
            if not business_tables:
                logger.warning("未找到需要清空的业务表")
                return True

            logger.info(f"清空 {len(business_tables)} 个业务表数据...")
            
            success_count = 0
            skip_count = 0
            
            for table in business_tables:
                try:
                    # 使用 psql 执行 TRUNCATE
                    cmd = [
                        'psql',
                        '--host', postgres_config['host'],
                        '--port', str(postgres_config['port']),
                        '--username', 'supabase_admin',
                        '--dbname', postgres_config['database'],
                        '--no-password',
                        '-c', f'TRUNCATE TABLE {table} CASCADE;'
                    ]
                    
                    result = subprocess.run(cmd, env=env, capture_output=True, text=True)
                    
                    if result.returncode == 0:
                        logger.debug(f"已清空表: {table}")
                        success_count += 1
                    else:
                        # 表可能不存在或有其他问题，跳过
                        logger.debug(f"跳过表 {table}: {result.stderr.strip()}")
                        skip_count += 1
                        
                except Exception as e:
                    logger.debug(f"跳过表 {table}: {str(e)}")
                    skip_count += 1

            logger.success(f"业务表数据清空完成 (成功: {success_count}, 跳过: {skip_count})")
            return True

        except Exception as e:
            logger.error(f"清空表数据失败: {str(e)}")
            return False

    def _export_data_with_truncate(self, source_type='remote', output_file=None,
                                   tables=None, schema='test', sync_all_schemas=False):
        """
        导出数据并包含清空表的语句(使用 DELETE)

        Args:
            source_type: 源数据库类型
            output_file: 输出文件路径
            tables: 要导出的表列表
            schema: Schema 名称（当 sync_all_schemas=False 时使用）
            sync_all_schemas: 是否同步所有业务 schema（包括 auth, storage 等）

        Returns:
            bool: 成功返回 True
        """
        db_config = RemoteDbConfig(source_type)

        # 设置SSH隧道（如果需要）
        tunnel = None
        try:
            if source_type == 'remote':
                tunnel = self._setup_ssh_tunnel(db_config)

            # 获取数据库配置（隧道建立后会返回更新的配置）
            postgres_config = db_config.get_postgres_config()

            # 设置环境变量
            env = os.environ.copy()
            env['PGPASSWORD'] = postgres_config['password']

            # 构建 pg_dump 命令
            cmd = [
                'pg_dump',
                '--host', postgres_config['host'],
                '--port', str(postgres_config['port']),
                '--username', postgres_config['user'],
                '--dbname', postgres_config['database'],
                '--no-password',
                '--data-only',  # 只导出数据
                '--column-inserts',  # 使用 INSERT 格式，更灵活
                '--no-owner',  # 不包含所有者信息
                '--no-privileges',  # 不包含权限信息
            ]

            # 选择要导出的 schema
            if sync_all_schemas:
                # 导出所有业务 schema，排除系统 schema
                logger.info("导出所有业务 schema 数据（包括 test, auth, storage 等）")

                # 排除 Supabase 系统 schema
                exclude_schemas = [
                    '_realtime', 'extensions', 'graphql_public',
                    'pgsodium', 'pgsodium_masks', 'realtime',
                    'supabase_functions', 'vault', 'net', 'pg_catalog',
                    'information_schema', 'pg_toast', 'cron'
                ]

                for exclude_schema in exclude_schemas:
                    cmd.extend(['--exclude-schema', exclude_schema])
                
                # 排除内部跟踪表（避免主键冲突）
                exclude_tables = [
                    'auth.schema_migrations',    # Auth 迁移跟踪
                    'storage.migrations',         # Storage 迁移跟踪
                    'supabase_migrations.schema_migrations',  # Supabase 迁移跟踪
                    'public.schema_config',       # Schema 配置表（由迁移脚本创建）
                ]
                
                for exclude_table in exclude_tables:
                    cmd.extend(['--exclude-table', exclude_table])
                    
                logger.info(f"排除内部跟踪表: {', '.join(exclude_tables)}")
            else:
                # 只导出指定 schema
                if schema:
                    cmd.extend(['--schema', schema])

            # 指定表（只在单 schema 模式下有效）
            if tables and not sync_all_schemas:
                for table in tables:
                    cmd.extend(['--table', f'{schema}.{table}'])

            # 输出文件
            cmd.extend(['--file', output_file])

            logger.info(f"导出数据: {' '.join(cmd[:-2])}... --file {output_file}")

            result = subprocess.run(cmd, env=env, capture_output=True, text=True)

            if result.returncode != 0:
                logger.error(f"导出失败: {result.stderr}")
                return False

            # 注意：全 schema 模式下不添加 DELETE 语句，因为我们不知道所有表名
            # 只在单 schema 模式下添加 DELETE
            if not sync_all_schemas:
                # 在导出的 SQL 文件前面添加 DELETE 语句
                with open(output_file, 'r') as f:
                    original_content = f.read()

                # 生成 DELETE 语句
                if tables:
                    tables_to_delete = tables
                else:
                    # 如果未指定表，则跳过 DELETE 语句生成
                    # 使用 --all-schemas 模式或明确指定表名
                    logger.warning("未指定表名，跳过 DELETE 语句生成")
                    logger.info("建议使用 --all-schemas 或明确指定 --tables 参数")
                    tables_to_delete = []

                if tables_to_delete:
                    delete_statements = '\n'.join([
                        f"DELETE FROM {schema}.{table};" for table in tables_to_delete
                    ])

                    # 写回文件（DELETE + 原内容）
                    with open(output_file, 'w') as f:
                        f.write("-- Auto-generated DELETE statements\n")
                        f.write(delete_statements)
                        f.write("\n\n")
                        f.write("-- Original data dump\n")
                        f.write(original_content)

            file_size = Path(output_file).stat().st_size
            logger.success(f"导出成功: {output_file} ({file_size} bytes)")
            return True

        except Exception as e:
            logger.error(f"导出数据失败: {str(e)}")
            return False
        finally:
            # 清理SSH隧道
            if tunnel and source_type == 'remote':
                self._cleanup_ssh_tunnel()

    def truncate_tables(self, target_type='local', tables=None, schema='test'):
        """
        清空表数据但保留结构

        Args:
            target_type: 目标数据库类型 ('local' 或 'remote')
            tables: 要清空的表列表，默认为 ['order', 'test_products']
            schema: Schema 名称，默认为 'test2'

        Returns:
            bool: 成功返回 True，失败返回 False
        """
        logger.info(f"清空 {target_type} 数据库表数据...")

        # 检查表参数
        if tables is None:
            logger.error("未指定要清空的表")
            logger.info("请使用 --tables 参数明确指定表名，例如: --tables 'order,test_products'")
            logger.info("或使用 _truncate_all_business_tables() 方法清空所有业务表")
            return False

        db_config = RemoteDbConfig(target_type)
        postgres_config = db_config.get_postgres_config()

        # 设置环境变量
        env = os.environ.copy()
        env['PGPASSWORD'] = postgres_config['password']

        # 设置SSH隧道（如果需要）
        tunnel = None
        if target_type == 'remote':
            tunnel = self._setup_ssh_tunnel(db_config)
            if tunnel:
                postgres_config = tunnel

        try:
            # 构建 TRUNCATE 语句
            table_list = ', '.join([f'{schema}.{table}' for table in tables])
            truncate_sql = f"TRUNCATE TABLE {table_list} CASCADE;"

            logger.info(f"执行清空语句: {truncate_sql}")

            psql_cmd = [
                'psql',
                '--host', postgres_config['host'],
                '--port', str(postgres_config['port']),
                '--username', postgres_config['user'],
                '--dbname', postgres_config['database'],
                '--no-password',
                '--command', truncate_sql
            ]

            result = subprocess.run(psql_cmd, env=env, capture_output=True, text=True)

            if result.returncode != 0:
                logger.error(f"清空表失败: {result.stderr}")
                return False

            logger.success(f"表数据已清空: {', '.join(tables)}")
            return True

        except Exception as e:
            logger.error(f"清空表时发生错误: {str(e)}")
            return False
        finally:
            # 清理SSH隧道
            if tunnel and target_type == 'remote':
                self._cleanup_ssh_tunnel()

    def sync_data_only(self, source_type='remote', target_type='local',
                      tables=None, apply_schema=True, schema='test', sync_all_schemas=False):
        """
        只同步数据，不管理系统 schema

        Args:
            source_type: 源数据库类型 ('local' 或 'remote')
            target_type: 目标数据库类型 ('local' 或 'remote')
            tables: 要同步的表列表
            apply_schema: 是否先应用迁移脚本
            schema: Schema 名称，默认为 'test'
            sync_all_schemas: 是否同步所有业务 schema（包括 auth, storage 等）

        Returns:
            bool: 成功返回 True，失败返回 False

        工作流程:
        1. [可选] 应用迁移脚本初始化/更新表结构
        2. 从源数据库导出数据 (--data-only，可选所有 schema 或单个 schema)
        3. [全schema模式] 清空目标表数据
        4. 导入数据到目标数据库
        """
        mode = "所有业务schema" if sync_all_schemas else f"{schema} schema"
        logger.info(f"开始数据同步 [{mode}]: {source_type} -> {target_type}")

        temp_file = None
        try:
            # Step 1: 应用迁移脚本（如果需要）
            if apply_schema:
                logger.info("Step 1: 应用迁移脚本...")
                if not self.apply_migrations(target_type):
                    logger.error("迁移脚本应用失败")
                    return False
            else:
                logger.info("Step 1: 跳过schema初始化")

            # Step 2: 导出源数据库数据
            logger.info("Step 2: 导出并同步数据...")

            # 确定文件名前缀
            prefix = 'all_schemas' if sync_all_schemas else f'{schema}_schema'
            temp_file = self.backup_dir / f'data_only_{prefix}_{source_type}_{datetime.now().strftime("%Y%m%d_%H%M%S")}.sql'

            # 导出数据
            success = self._export_data_with_truncate(
                source_type=source_type,
                output_file=str(temp_file),
                tables=tables,
                schema=schema,
                sync_all_schemas=sync_all_schemas
            )

            if not success:
                logger.error("数据导出失败")
                return False

            # Step 3: 授予权限（如果是本地数据库）
            if target_type == 'local':
                logger.info("Step 3a: 授予数据操作权限...")
                self._grant_data_permissions(target_type, schema)

            # Step 3b: 清空目标表（全schema模式）
            if sync_all_schemas:
                logger.info("Step 3b: 清空目标表数据...")
                if not self._truncate_all_business_tables(target_type):
                    logger.warning("部分表清空失败，继续导入...")

            # Step 4: 导入数据
            logger.info(f"Step 4: 导入数据到目标数据库...")
            success = self.import_database(
                sql_file=str(temp_file),
                target_type=target_type,
                clean_first=False,  # 不需要清理整个数据库
                stop_services=False  # 不需要停止服务，只是导入数据
            )

            if success:
                logger.success(f"数据同步完成: {source_type} -> {target_type}")
                logger.info(f"数据备份保存在: {temp_file}")
            else:
                logger.error("数据导入失败")

            return success

        except Exception as e:
            logger.error(f"数据同步失败: {str(e)}")
            return False

    def sync_database(self, source_type='remote', target_type='local',
                     tables=None, clean_first=False, stop_services=True):
        """
        直接同步数据库（导出 + 导入）

        Args:
            source_type: 源数据库类型
            target_type: 目标数据库类型
            tables: 要同步的表
            clean_first: 是否先清理目标数据库
            stop_services: 是否停止Supabase服务
        """
        logger.info(f"开始同步数据库: {source_type} -> {target_type}")

        # 导出数据
        temp_file = None
        try:
            temp_file = self.export_database(source_type, tables=tables)
            if not temp_file:
                return False

            # 导入数据
            success = self.import_database(temp_file, target_type, clean_first, stop_services)

            if success:
                logger.success(f"数据库同步完成: {source_type} -> {target_type}")

            return success

        except Exception as e:
            logger.error(f"同步过程中发生错误: {str(e)}")
            return False
        finally:
            # 清理临时文件（可选）
            if temp_file and Path(temp_file).exists():
                logger.info(f"备份文件已保存: {temp_file}")

    def list_backups(self):
        """列出所有备份文件"""
        if not self.backup_dir.exists():
            logger.info("备份目录不存在")
            return

        backup_files = list(self.backup_dir.glob("*.sql"))
        if not backup_files:
            logger.info("没有找到备份文件")
            return

        logger.info(f"备份目录: {self.backup_dir}")
        logger.info("备份文件列表:")

        for backup_file in sorted(backup_files, key=lambda x: x.stat().st_mtime, reverse=True):
            size = backup_file.stat().st_size
            mtime = datetime.fromtimestamp(backup_file.stat().st_mtime)
            size_mb = size / (1024 * 1024)

            print(f"  {backup_file.name:40} {size_mb:8.2f} MB  {mtime.strftime('%Y-%m-%d %H:%M:%S')}")

    def cleanup_old_backups(self, keep_count=10):
        """清理旧的备份文件，只保留最新的几个"""
        backup_files = sorted(self.backup_dir.glob("*.sql"),
                            key=lambda x: x.stat().st_mtime, reverse=True)

        if len(backup_files) <= keep_count:
            logger.info(f"当前有 {len(backup_files)} 个备份文件，无需清理")
            return

        old_files = backup_files[keep_count:]
        for old_file in old_files:
            old_file.unlink()
            logger.info(f"删除旧备份: {old_file.name}")

        logger.success(f"清理完成，保留最新 {keep_count} 个备份文件")


def main():
    """主函数"""
    parser = argparse.ArgumentParser(description='PostgreSQL 数据库远程复制工具')

    # 主要操作
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--export', action='store_true', help='导出数据库')
    group.add_argument('--import', dest='import_db', action='store_true', help='导入数据库')
    group.add_argument('--sync', action='store_true', help='同步数据库（导出+导入，完整备份模式）')
    group.add_argument('--data-only-sync', action='store_true',
                      help='只同步数据（推荐：先应用迁移脚本，再同步数据）')
    group.add_argument('--schema-init', action='store_true',
                      help='只初始化schema（应用迁移脚本）')
    group.add_argument('--list', action='store_true', help='列出备份文件')
    group.add_argument('--cleanup', action='store_true', help='清理旧备份文件')
    group.add_argument('--test', action='store_true', help='测试数据库连接')

    # 数据库相关参数
    parser.add_argument('--source', choices=['local', 'remote'], default='remote',
                       help='源数据库类型')
    parser.add_argument('--target', choices=['local', 'remote'], default='local',
                       help='目标数据库类型')

    # 文件相关参数
    parser.add_argument('--output', help='输出文件路径（用于导出）')
    parser.add_argument('--file', help='SQL文件路径（用于导入）')

    # 导出选项
    parser.add_argument('--tables', help='要导出的表名，用逗号分隔')
    parser.add_argument('--schema-only', action='store_true', help='只导出结构')
    parser.add_argument('--data-only', action='store_true', help='只导出数据')

    # 导入选项
    parser.add_argument('--clean', action='store_true', help='导入前清理目标数据库')
    parser.add_argument('--no-stop-services', action='store_true',
                       help='导入时不停止Supabase服务（高级用户）')

    # 数据同步选项
    parser.add_argument('--skip-schema-init', action='store_true',
                       help='跳过schema初始化（仅同步数据，用于--data-only-sync）')
    parser.add_argument('--schema', default='test',
                       help='Schema名称（默认: test）')
    parser.add_argument('--all-schemas', action='store_true',
                       help='同步所有业务schema数据（包括test, auth, storage等，排除系统schema）')

    # 清理选项
    parser.add_argument('--keep', type=int, default=10, help='保留备份文件数量')

    # SSH隧道选项
    parser.add_argument('--use-tunnel', action='store_true',
                       help='强制使用SSH隧道（覆盖环境变量配置）')
    parser.add_argument('--no-tunnel', action='store_true',
                       help='强制不使用SSH隧道（覆盖环境变量配置）')

    args = parser.parse_args()

    # 确定SSH隧道使用模式
    use_tunnel = None
    if args.use_tunnel:
        use_tunnel = True
    elif args.no_tunnel:
        use_tunnel = False

    # 确定是否停止服务
    stop_services = not args.no_stop_services

    # 创建工具实例
    tool = PgDumpTool(use_tunnel=use_tunnel)

    # 检查必要工具
    if not tool.check_pg_tools():
        sys.exit(1)

    # 执行对应操作
    if args.test:
        logger.info("测试数据库连接...")
        local_config = RemoteDbConfig('local')
        remote_config = RemoteDbConfig('remote')

        # 测试本地连接
        local_ok = local_config.test_connection()
        
        # 测试远程连接 - 需要先建立SSH隧道
        remote_ok = False
        tunnel = None
        try:
            if remote_config.requires_ssh_tunnel() or use_tunnel:
                logger.info("建立SSH隧道用于远程连接测试...")
                tunnel = tool._setup_ssh_tunnel(remote_config)
            
            remote_ok = remote_config.test_connection()
        finally:
            if tunnel:
                tool._cleanup_ssh_tunnel()

        if local_ok and remote_ok:
            logger.success("所有数据库连接正常")
        else:
            logger.error("部分数据库连接失败")

    elif args.export:
        result = tool.export_database(
            source_type=args.source,
            output_file=args.output,
            tables=args.tables,
            schema_only=args.schema_only,
            data_only=args.data_only
        )
        if not result:
            sys.exit(1)

    elif args.import_db:
        if not args.file:
            logger.error("导入操作需要指定 --file 参数")
            sys.exit(1)

        success = tool.import_database(
            sql_file=args.file,
            target_type=args.target,
            clean_first=args.clean,
            stop_services=stop_services
        )
        if not success:
            sys.exit(1)

    elif args.sync:
        success = tool.sync_database(
            source_type=args.source,
            target_type=args.target,
            tables=args.tables,
            clean_first=args.clean,
            stop_services=stop_services
        )
        if not success:
            sys.exit(1)

    elif args.data_only_sync:
        # 数据同步模式（推荐）
        apply_schema = not args.skip_schema_init

        success = tool.sync_data_only(
            source_type=args.source,
            target_type=args.target,
            tables=args.tables.split(',') if args.tables else None,
            apply_schema=apply_schema,
            schema=args.schema,
            sync_all_schemas=args.all_schemas
        )
        if not success:
            sys.exit(1)

    elif args.schema_init:
        # 只初始化schema
        success = tool.apply_migrations(
            target_type=args.target
        )
        if not success:
            sys.exit(1)

        # 提醒用户重启 PostgREST 以刷新 schema 缓存
        if args.target == 'local':
            logger.warning("⚠️  重要提醒：schema 初始化完成后，请手动重启 PostgREST 容器以刷新 schema 缓存")
            logger.warning("   执行命令: docker restart supabase-rest")
            logger.warning("   否则新创建的函数可能无法通过 Supabase RPC 调用")

    elif args.list:
        tool.list_backups()

    elif args.cleanup:
        tool.cleanup_old_backups(args.keep)

    logger.success("操作完成")


if __name__ == '__main__':
    main()