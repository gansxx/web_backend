"""
远程数据库配置管理类
支持本地和远程数据库连接配置
"""
import sys
import os
from pathlib import Path
from loguru import logger
from dotenv import load_dotenv
import psycopg2
from urllib.parse import urlparse

# 添加父目录到路径以便导入 base_config
sys.path.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
from base_config import BaseConfig


class RemoteDbConfig:
    """远程数据库配置管理类"""

    def __init__(self, config_type='local'):
        """
        初始化数据库配置

        Args:
            config_type (str): 配置类型，'local' 或 'remote'
        """
        self.config_type = config_type
        self.project_root = Path(__file__).parent.parent.parent.parent
        self.load_environment()

    def requires_ssh_tunnel(self) -> bool:
        """
        检查是否需要使用SSH隧道连接

        Returns:
            bool: True if SSH tunnel is required
        """
        if self.config_type != 'remote':
            return False

        use_tunnel = os.getenv('USE_SSH_TUNNEL', 'false').lower()
        return use_tunnel in ('true', '1', 'yes')

    def get_ssh_tunnel_config(self):
        """
        获取SSH隧道配置

        Returns:
            dict: SSH tunnel configuration or None if not configured
        """
        if not self.requires_ssh_tunnel():
            return None

        gateway_host = os.getenv('SSH_GATEWAY_HOST', '').strip("'\"")
        if not gateway_host:
            logger.warning("SSH_GATEWAY_HOST not configured")
            return None

        # Expand tilde in key_file path
        key_file = os.getenv('SSH_KEY_FILE', '')
        if key_file:
            key_file = str(Path(key_file).expanduser())

        config = {
            'gateway_host': gateway_host,
            'gateway_port': int(os.getenv('SSH_GATEWAY_PORT', '22')),
            'gateway_user': os.getenv('SSH_GATEWAY_USER', 'root'),
            'key_file': key_file,
            'remote_host': os.getenv('REMOTE_POSTGRES_HOST', 'db'),
            'remote_port': int(os.getenv('REMOTE_POSTGRES_PORT', '5438')),
            'local_port': int(os.getenv('LOCAL_remote_POSTGRES_PORT', '5439')),
        }

        logger.info(f"SSH隧道配置: {config['gateway_user']}@{config['gateway_host']}:{config['gateway_port']}")
        return config

    def load_environment(self):
        """加载对应的环境变量"""
        if self.config_type == 'remote':
            # 优先查找专用的迁移配置文件
            env_files_to_try = [
                self.project_root / '.env.migration',        # 第一优先级：专用迁移配置
                self.project_root / '.env.remote',           # 第二优先级：远程配置
                self.project_root / '.env.remote.example',   # 第三优先级：远程示例配置
                self.project_root / '.env.migration.example' # 第四优先级：迁移示例配置
            ]

            env_file = None
            for candidate in env_files_to_try:
                if candidate.exists():
                    env_file = candidate
                    break

            if env_file is None:
                logger.error("未找到任何远程数据库配置文件")
                logger.info("请创建以下任一配置文件：")
                logger.info("  推荐: .env.migration (复制 .env.migration.example)")
                logger.info("  或者: .env.remote")
                return

            if env_file.name == '.env.migration.example':
                logger.warning("正在使用示例配置文件，请创建实际的配置文件")
                logger.info("建议: cp .env.migration.example .env.migration")
            elif env_file.name != '.env.migration':
                logger.info(f"未找到 .env.migration，使用备选配置: {env_file.name}")

        else:
            env_file = self.project_root / '.env'

        if env_file and env_file.exists():
            load_dotenv(env_file, override=True)
            logger.info(f"已加载环境变量: {env_file}")

            # 验证必要的配置参数
            self._validate_config()
        else:
            logger.error(f"环境变量文件不存在: {env_file}")

    def _validate_config(self):
        """验证必要的配置参数"""
        if self.config_type == 'remote':
            # 验证远程配置的必要变量
            required_vars = ['REMOTE_POSTGRES_PASSWORD']
            missing_vars = []

            for var in required_vars:
                if not os.getenv(var):
                    missing_vars.append(var)

            if missing_vars:
                logger.error(f"缺少必要的远程数据库环境变量: {', '.join(missing_vars)}")
                logger.info("请检查你的 .env.migration 或 .env.remote 文件")
                logger.info("参考 .env.migration.example 文件了解所需配置")
        else:
            # 验证本地配置的必要变量
            required_vars = ['POSTGRES_PASSWORD']
            missing_vars = []

            for var in required_vars:
                if not os.getenv(var):
                    missing_vars.append(var)

            if missing_vars:
                logger.error(f"缺少必要的本地数据库环境变量: {', '.join(missing_vars)}")
                logger.info("请检查你的 .env 文件")

        # 对于远程配置,额外检查远程数据库IP或SSH隧道配置
        if self.config_type == 'remote':
            if self.requires_ssh_tunnel():
                # 验证SSH隧道配置
                gateway_host = os.getenv('SSH_GATEWAY_HOST', '').strip("'\"")
                if not gateway_host:
                    logger.warning("USE_SSH_TUNNEL=true 但 SSH_GATEWAY_HOST 未配置")
                    logger.info("请在配置文件中设置 SSH_GATEWAY_HOST")
                
                key_file = os.getenv('SSH_KEY_FILE', '').strip("'\"")
                if key_file and not Path(key_file).expanduser().exists():
                    logger.warning(f"SSH密钥文件不存在: {key_file}")
                    logger.info("请确保SSH_KEY_FILE指向有效的私钥文件")
            else:
                # 直接连接模式,检查远程数据库IP
                remote_db_ip = os.getenv('remote_db_ip', '').strip("'\"")
                if not remote_db_ip or remote_db_ip == 'YOUR_REMOTE_DB_IP_HERE':
                    logger.warning("remote_db_ip 未正确配置")
                    logger.info("请在配置文件中设置正确的远程数据库IP地址或启用SSH隧道")

    def get_postgres_config(self):
        """获取 PostgreSQL 连接配置"""
        if self.config_type == 'remote':
            # 远程数据库配置
            if self.requires_ssh_tunnel():
                # 使用SSH隧道时，连接到本地转发端口
                host = 'localhost'
                postgres_port = int(os.getenv('LOCAL_remote_POSTGRES_PORT', '5439'))
                logger.info("使用SSH隧道连接模式")
            else:
                # 直接连接模式
                remote_db_ip = os.getenv('remote_db_ip', '8.134.74.41').strip("'\"")
                postgres_port = int(os.getenv('REMOTE_POSTGRES_PORT', '5438'))
                host = remote_db_ip
                logger.info("使用直接连接模式")
        else:
            # 本地数据库配置
            host = 'localhost'
            postgres_port = int(os.getenv('POSTGRES_PORT_LOCAL', '5438'))  # 使用宿主机端口环境变量

        if self.config_type == 'remote':
            # 远程数据库配置 - 使用 REMOTE_ 前缀的变量
            config = {
                'host': host,
                'port': postgres_port,
                'database': os.getenv('REMOTE_POSTGRES_DB', 'postgres'),
                'user': 'postgres',
                'password': os.getenv('REMOTE_POSTGRES_PASSWORD'),
            }
        else:
            # 本地数据库配置 - 使用标准变量
            config = {
                'host': host,
                'port': postgres_port,
                'database': os.getenv('POSTGRES_DB', 'postgres'),
                'user': 'postgres',
                'password': os.getenv('POSTGRES_PASSWORD'),
            }

        logger.info(f"数据库配置 ({self.config_type}): {host}:{postgres_port}/{config['database']}")
        return config

    def get_connection_string(self):
        """获取 PostgreSQL 连接字符串"""
        config = self.get_postgres_config()
        return f"postgresql://{config['user']}:{config['password']}@{config['host']}:{config['port']}/{config['database']}"

    def test_connection(self):
        """测试数据库连接"""
        try:
            config = self.get_postgres_config()
            conn = psycopg2.connect(**config)
            cursor = conn.cursor()
            cursor.execute('SELECT version()')
            version = cursor.fetchone()
            cursor.close()
            conn.close()

            logger.success(f"数据库连接成功 ({self.config_type})")
            logger.info(f"PostgreSQL 版本: {version[0]}")
            return True

        except Exception as e:
            logger.error(f"数据库连接失败 ({self.config_type}): {str(e)}")
            return False

    def get_supabase_config(self):
        """获取 Supabase 配置（用于 API 访问）"""
        if self.config_type == 'remote':
            url = os.getenv('FRONTEND_URL', 'https://selfgo.asia')
            # 将前端 URL 转换为 Supabase API URL
            if url.startswith('https://'):
                url = url.replace('https://', 'https://api.')
            elif url.startswith('http://'):
                url = url.replace('http://', 'http://api.')
        else:
            url = os.getenv('SUPABASE_URL', 'http://localhost:8000')

        return {
            'url': url,
            'anon_key': os.getenv('ANON_KEY'),
            'service_role_key': os.getenv('SERVICE_ROLE_KEY')
        }


def main():
    """测试配置类"""
    logger.info("测试数据库配置类")

    # 测试本地配置
    logger.info("=== 测试本地数据库配置 ===")
    local_config = RemoteDbConfig('local')
    local_config.test_connection()

    # 测试远程配置
    logger.info("=== 测试远程数据库配置 ===")
    remote_config = RemoteDbConfig('remote')
    remote_config.test_connection()


if __name__ == '__main__':
    main()