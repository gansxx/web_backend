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


class PgDumpTool:
    """PostgreSQL 数据库导出导入工具"""

    def __init__(self):
        """初始化工具"""
        self.project_root = Path(__file__).parent.parent.parent.parent
        self.backup_dir = self.project_root / 'center_management' / 'db' / 'migration' / 'backups'
        self.backup_dir.mkdir(exist_ok=True)

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

        try:
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

    def import_database(self, sql_file, target_type='local', clean_first=False):
        """
        导入数据库

        Args:
            sql_file: SQL 文件路径
            target_type: 目标数据库类型 ('local' 或 'remote')
            clean_first: 是否先清理目标数据库
        """
        sql_file = Path(sql_file)
        if not sql_file.exists():
            logger.error(f"SQL 文件不存在: {sql_file}")
            return False

        logger.info(f"开始导入到 {target_type} 数据库: {sql_file}")

        # 获取数据库配置
        db_config = RemoteDbConfig(target_type)
        if not db_config.test_connection():
            logger.error(f"无法连接到 {target_type} 数据库")
            return False

        postgres_config = db_config.get_postgres_config()

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
            '--on-error-stop'
        ]

        # 设置环境变量传递密码
        env = os.environ.copy()
        env['PGPASSWORD'] = postgres_config['password']

        try:
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

    def clean_database(self, target_type='local'):
        """清理数据库（删除所有表）"""
        logger.warning(f"清理 {target_type} 数据库...")

        db_config = RemoteDbConfig(target_type)
        postgres_config = db_config.get_postgres_config()

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

        env = os.environ.copy()
        env['PGPASSWORD'] = postgres_config['password']

        try:
            result = subprocess.run(cmd, env=env, capture_output=True, text=True)
            if result.returncode != 0:
                logger.error(f"获取表列表失败: {result.stderr}")
                return False

            tables = [line.strip() for line in result.stdout.split('\n')
                     if line.strip()]

            if not tables:
                logger.info("没有找到需要清理的表")
                return True

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
            if result.returncode == 0:
                logger.success("数据库清理完成")
                return True
            else:
                logger.error(f"数据库清理失败: {result.stderr}")
                return False

        except Exception as e:
            logger.error(f"清理数据库时发生错误: {str(e)}")
            return False

    def sync_database(self, source_type='remote', target_type='local',
                     tables=None, clean_first=False):
        """
        直接同步数据库（导出 + 导入）

        Args:
            source_type: 源数据库类型
            target_type: 目标数据库类型
            tables: 要同步的表
            clean_first: 是否先清理目标数据库
        """
        logger.info(f"开始同步数据库: {source_type} -> {target_type}")

        # 导出数据
        temp_file = None
        try:
            temp_file = self.export_database(source_type, tables=tables)
            if not temp_file:
                return False

            # 导入数据
            success = self.import_database(temp_file, target_type, clean_first)

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
    group.add_argument('--sync', action='store_true', help='同步数据库（导出+导入）')
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

    # 清理选项
    parser.add_argument('--keep', type=int, default=10, help='保留备份文件数量')

    args = parser.parse_args()

    # 创建工具实例
    tool = PgDumpTool()

    # 检查必要工具
    if not tool.check_pg_tools():
        sys.exit(1)

    # 执行对应操作
    if args.test:
        logger.info("测试数据库连接...")
        local_config = RemoteDbConfig('local')
        remote_config = RemoteDbConfig('remote')

        local_ok = local_config.test_connection()
        remote_ok = remote_config.test_connection()

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
            clean_first=args.clean
        )
        if not success:
            sys.exit(1)

    elif args.sync:
        success = tool.sync_database(
            source_type=args.source,
            target_type=args.target,
            tables=args.tables,
            clean_first=args.clean
        )
        if not success:
            sys.exit(1)

    elif args.list:
        tool.list_backups()

    elif args.cleanup:
        tool.cleanup_old_backups(args.keep)

    logger.success("操作完成")


if __name__ == '__main__':
    main()