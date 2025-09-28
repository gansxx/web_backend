"""
Enhanced Node Management with Multi-Cloud VPS Support

Updated version of node_manage.py that integrates with the new VPS manager system.
Provides unified interface for managing nodes across multiple cloud providers.
"""

from pathlib import Path
import shlex
import re
from loguru import logger
import subprocess
import sqlite3
import tempfile
import os
import json
from contextlib import contextmanager
from typing import Optional, Dict, Any, List, Tuple

# Import the new VPS manager system
try:
    from .vps_manager import get_provider, VPSProvider, VPSInstance, VPSConfig
    from .vps_manager.ssh_manager import SSHManager, ssh_connection
    from .vps_manager.config import get_provider_credentials, get_instance_config
    VPS_MANAGER_AVAILABLE = True
except ImportError:
    VPS_MANAGER_AVAILABLE = False
    logger.warning("VPS Manager not available, falling back to legacy implementation")

# Fallback to legacy implementation if VPS manager is not available
if not VPS_MANAGER_AVAILABLE:
    try:
        # Legacy import for backward compatibility
        import importlib
        import importlib.util
        try:
            vps_mod = importlib.import_module('vps_vultr_manage')
        except Exception:
            spec_path = Path(__file__).resolve().parent / 'vps_vultr_manage.py'
            spec = importlib.util.spec_from_file_location('vps_vultr_manage', str(spec_path))
            vps_mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(vps_mod)
    except Exception as e:
        logger.error(f"Failed to load legacy VPS module: {e}")
        vps_mod = None


class EnhancedNodeProxy:
    """
    Enhanced Node代理类，支持多云VPS管理和SSH连接
    """

    def __init__(self, hostname: str, port: int = 22, username: str = 'root',
                 key_file: Optional[str] = None, timeout: int = 30,
                 provider: Optional[str] = None, instance_id: Optional[str] = None):
        """
        Initialize enhanced node proxy

        Args:
            hostname: Remote hostname or IP address
            port: SSH port (default: 22)
            username: SSH username (default: 'root')
            key_file: Path to private key file
            timeout: Connection timeout in seconds
            provider: VPS provider name (vultr, aws_ec2, aws_lightsail)
            instance_id: VPS instance ID for cloud operations
        """
        self.hostname = hostname
        self.port = port
        self.username = username
        self.key_file = key_file
        self.timeout = timeout
        self.provider_name = provider
        self.instance_id = instance_id

        # Initialize SSH manager
        self._ssh_manager = SSHManager(hostname, port, username, key_file, timeout)

        # Initialize VPS provider if available
        self._vps_provider: Optional[VPSProvider] = None
        if VPS_MANAGER_AVAILABLE and provider:
            try:
                self._vps_provider = get_provider(provider)
            except Exception as e:
                logger.warning(f"Failed to initialize VPS provider {provider}: {e}")

    def connect(self):
        """建立SSH连接"""
        return self._ssh_manager.connect()

    def disconnect(self):
        """断开SSH连接"""
        self._ssh_manager.disconnect()

    def execute_command(self, command: str, timeout: int = 600) -> Tuple[int, str, str]:
        """执行远程命令"""
        return self._ssh_manager.execute_command(command, timeout)

    def get_sftp_client(self):
        """获取SFTP客户端"""
        return self._ssh_manager.get_sftp_client()

    def get_instance_info(self) -> Optional[VPSInstance]:
        """
        获取VPS实例信息

        Returns:
            VPSInstance object or None if not available
        """
        if self._vps_provider and self.instance_id:
            return self._vps_provider.get_instance(self.instance_id)
        return None

    def reboot_instance(self) -> bool:
        """
        重启VPS实例

        Returns:
            True if successful, False otherwise
        """
        if self._vps_provider and self.instance_id:
            return self._vps_provider.reboot_instance(self.instance_id)
        return False

    def start_instance(self) -> bool:
        """
        启动VPS实例

        Returns:
            True if successful, False otherwise
        """
        if self._vps_provider and self.instance_id:
            return self._vps_provider.start_instance(self.instance_id)
        return False

    def stop_instance(self) -> bool:
        """
        停止VPS实例

        Returns:
            True if successful, False otherwise
        """
        if self._vps_provider and self.instance_id:
            return self._vps_provider.stop_instance(self.instance_id)
        return False

    def get_instance_ip(self) -> Optional[str]:
        """
        获取实例公网IP

        Returns:
            IP address or None
        """
        if self._vps_provider and self.instance_id:
            return self._vps_provider.get_instance_ip(self.instance_id)
        return self.hostname

    def __enter__(self):
        """上下文管理器入口"""
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """上下文管理器出口"""
        self.disconnect()

    def __del__(self):
        """析构函数，确保连接被断开"""
        if hasattr(self, '_ssh_manager'):
            self.disconnect()


class CloudVPSManager:
    """
    多云VPS管理器，提供统一的VPS创建、删除、管理接口
    """

    def __init__(self, default_provider: str = 'vultr'):
        """
        Initialize cloud VPS manager

        Args:
            default_provider: Default VPS provider to use
        """
        self.default_provider = default_provider

    def create_instance(self, provider: str, config_data: Optional[Dict[str, Any]] = None,
                       config_file: Optional[str] = None) -> Optional[str]:
        """
        创建VPS实例

        Args:
            provider: VPS provider name
            config_data: Configuration data dictionary
            config_file: Path to configuration file

        Returns:
            Instance ID if successful, None otherwise
        """
        if not VPS_MANAGER_AVAILABLE:
            logger.error("VPS Manager not available")
            return None

        try:
            # Get provider instance
            vps_provider = get_provider(provider)

            # Load configuration
            if config_data:
                config = VPSConfig(**config_data)
            elif config_file:
                from .vps_manager.config import config_manager
                config = config_manager.load_instance_config(provider, config_file)
            else:
                config = get_instance_config(provider)

            # Create instance
            instance_id = vps_provider.create_instance(config)
            logger.info(f"Created {provider} instance: {instance_id}")
            return instance_id

        except Exception as e:
            logger.error(f"Failed to create {provider} instance: {e}")
            return None

    def delete_instance(self, provider: str, instance_id: str) -> bool:
        """
        删除VPS实例

        Args:
            provider: VPS provider name
            instance_id: Instance ID

        Returns:
            True if successful, False otherwise
        """
        if not VPS_MANAGER_AVAILABLE:
            logger.error("VPS Manager not available")
            return False

        try:
            vps_provider = get_provider(provider)
            result = vps_provider.delete_instance(instance_id)
            if result:
                logger.info(f"Deleted {provider} instance: {instance_id}")
            return result

        except Exception as e:
            logger.error(f"Failed to delete {provider} instance {instance_id}: {e}")
            return False

    def list_instances(self, provider: str) -> List[VPSInstance]:
        """
        列出所有VPS实例

        Args:
            provider: VPS provider name

        Returns:
            List of VPSInstance objects
        """
        if not VPS_MANAGER_AVAILABLE:
            logger.error("VPS Manager not available")
            return []

        try:
            vps_provider = get_provider(provider)
            return vps_provider.list_instances()

        except Exception as e:
            logger.error(f"Failed to list {provider} instances: {e}")
            return []

    def get_instance(self, provider: str, instance_id: str) -> Optional[VPSInstance]:
        """
        获取VPS实例信息

        Args:
            provider: VPS provider name
            instance_id: Instance ID

        Returns:
            VPSInstance object or None
        """
        if not VPS_MANAGER_AVAILABLE:
            logger.error("VPS Manager not available")
            return None

        try:
            vps_provider = get_provider(provider)
            return vps_provider.get_instance(instance_id)

        except Exception as e:
            logger.error(f"Failed to get {provider} instance {instance_id}: {e}")
            return None

    def create_node_proxy(self, provider: str, instance_id: str,
                         username: str = 'root', key_file: Optional[str] = None) -> Optional[EnhancedNodeProxy]:
        """
        为VPS实例创建NodeProxy

        Args:
            provider: VPS provider name
            instance_id: Instance ID
            username: SSH username
            key_file: Path to private key file

        Returns:
            EnhancedNodeProxy instance or None
        """
        try:
            # Get instance information
            instance = self.get_instance(provider, instance_id)
            if not instance or not instance.ip_address:
                logger.error(f"Instance {instance_id} not found or has no IP address")
                return None

            # Create enhanced node proxy
            proxy = EnhancedNodeProxy(
                hostname=instance.ip_address,
                username=username,
                key_file=key_file,
                provider=provider,
                instance_id=instance_id
            )

            return proxy

        except Exception as e:
            logger.error(f"Failed to create node proxy for {provider} instance {instance_id}: {e}")
            return None


# Legacy compatibility classes and functions
class NodeProxy(EnhancedNodeProxy):
    """Legacy NodeProxy class for backward compatibility"""

    def __init__(self, hostname, port=22, username='root', key_file=None, timeout=30):
        super().__init__(hostname, port, username, key_file, timeout)

    def connect(self):
        """建立SSH连接 (Legacy method)"""
        if not VPS_MANAGER_AVAILABLE and vps_mod:
            # Use legacy implementation
            if not self._connected or not self._ssh_client:
                self._ssh_client = vps_mod.ssh_connect(self.hostname, self.port, self.username, self.key_file, self.timeout)
                self._connected = True
                logger.info(f"SSH连接已建立: {self.username}@{self.hostname}:{self.port}")
            return self._ssh_client
        else:
            return super().connect()

    def disconnect(self):
        """断开SSH连接 (Legacy method)"""
        if not VPS_MANAGER_AVAILABLE and hasattr(self, '_ssh_client'):
            # Use legacy implementation
            if self._ssh_client and getattr(self, '_connected', False):
                try:
                    self._ssh_client.close()
                    logger.info(f"SSH连接已断开: {self.username}@{self.hostname}:{self.port}")
                except Exception as e:
                    logger.warning(f"关闭SSH连接失败: {e}")
                finally:
                    self._ssh_client = None
                    self._connected = False
        else:
            super().disconnect()

    def execute_command(self, command, timeout=600):
        """执行远程命令 (Legacy method)"""
        if not VPS_MANAGER_AVAILABLE and vps_mod:
            # Use legacy implementation
            if not getattr(self, '_connected', False) or not getattr(self, '_ssh_client', None):
                self.connect()
            return vps_mod.execute_remote_command_with_client(self._ssh_client, command, timeout, self.hostname)
        else:
            return super().execute_command(command, timeout)


@contextmanager
def node_proxy_context(hostname, port=22, username='root', key_file=None, timeout=30):
    """NodeProxy上下文管理器 (Legacy function)"""
    proxy = NodeProxy(hostname, port, username, key_file, timeout)
    try:
        proxy.connect()
        yield proxy
    finally:
        proxy.disconnect()


@contextmanager
def enhanced_node_proxy_context(hostname, port=22, username='root', key_file=None, timeout=30,
                               provider=None, instance_id=None):
    """Enhanced NodeProxy context manager"""
    proxy = EnhancedNodeProxy(hostname, port, username, key_file, timeout, provider, instance_id)
    try:
        proxy.connect()
        yield proxy
    finally:
        proxy.disconnect()


# VPS management functions with multi-cloud support
def create_vps_instance(provider: str = 'vultr', **config_kwargs) -> Optional[str]:
    """
    Create a VPS instance using the specified provider

    Args:
        provider: VPS provider name (vultr, aws_ec2, aws_lightsail)
        **config_kwargs: Configuration parameters

    Returns:
        Instance ID if successful, None otherwise
    """
    manager = CloudVPSManager()
    return manager.create_instance(provider, config_kwargs)


def delete_vps_instance(provider: str, instance_id: str) -> bool:
    """
    Delete a VPS instance

    Args:
        provider: VPS provider name
        instance_id: Instance ID

    Returns:
        True if successful, False otherwise
    """
    manager = CloudVPSManager()
    return manager.delete_instance(provider, instance_id)


def list_vps_instances(provider: str) -> List[Dict[str, Any]]:
    """
    List VPS instances

    Args:
        provider: VPS provider name

    Returns:
        List of instance information dictionaries
    """
    manager = CloudVPSManager()
    instances = manager.list_instances(provider)
    return [instance.to_dict() for instance in instances]


def get_vps_instance_info(provider: str, instance_id: str) -> Optional[Dict[str, Any]]:
    """
    Get VPS instance information

    Args:
        provider: VPS provider name
        instance_id: Instance ID

    Returns:
        Instance information dictionary or None
    """
    manager = CloudVPSManager()
    instance = manager.get_instance(provider, instance_id)
    return instance.to_dict() if instance else None


# Keep all the existing functions from the original node_manage.py
def run_remote_self_sb_change(proxy, port_arg=None, name_arg=None, up_mbps=None, down_mbps=None, script_path='/root/sing-box-v2ray/self_sb_change.sh'):
    """在远端执行已存在的 self_sb_change.sh 脚本以注册用户，并返回 hy2_link。"""
    args = []
    if port_arg is not None:
        args.append(f"-p {int(port_arg)}")
    if name_arg is not None:
        args.append(f"-n {shlex.quote(str(name_arg))}")
    if up_mbps is not None:
        args.append(f"-u {int(up_mbps)}")
    if down_mbps is not None:
        args.append(f"-d {int(down_mbps)}")

    argstr = ' '.join(args)
    command = f"sudo {script_path} {argstr}"
    logger.info(f"Executing remote script: {command}")

    exit_status, out, err = proxy.execute_command(command)

    # 尝试从 stdout 中解析 hy2_link，脚本以打印 hy2_link 为最后一部分
    hy2_link = None
    if out:
        # 一般 hy2 链接的格式以 hysteria2:// 开头，尝试搜索第一个匹配项
        m = re.search(r"hysteria2://[A-Za-z0-9\-._~%:@/?&=+#]+", out)
        if m:
            hy2_link = m.group(0)

    return exit_status, hy2_link, out, err


def verify_hy2_link(uri, script_path=None, timeout=30, cwd=None):
    """调用本地的 `link_verificate.sh` 脚本验证给定的 hysteria2 URI 是否可用。"""
    if script_path is None:
        script_path = str(Path(__file__).resolve().parent / 'link_verificate.sh')

    # 使用 bash 来执行脚本以确保 shebang 行或 bash 特性能被正确处理
    cmd = ['bash', script_path, '-z', uri]
    logger.info(f"Verifying hy2 link via: {' '.join(shlex.quote(p) for p in cmd)}")
    try:
        proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=timeout, cwd=cwd)
        stdout = proc.stdout.decode('utf-8', errors='ignore')
        stderr = proc.stderr.decode('utf-8', errors='ignore')
        rc = proc.returncode
        success = (rc == 0)
        return rc, stdout, stderr, success
    except subprocess.TimeoutExpired as e:
        logger.exception('verify_hy2_link: subprocess timeout')
        out = getattr(e, 'stdout', b'') or b''
        err = getattr(e, 'stderr', b'') or b''
        return -1, out.decode('utf-8', errors='ignore'), err.decode('utf-8', errors='ignore'), False


def find_database_file(proxy, possible_paths=None, timeout=10):
    """在远程服务器上查找数据库文件"""
    if possible_paths is None:
        possible_paths = [
            '/var/lib/sing-box/v2api_stats.db',
            '/root/sing-box/v2api_stats.db',
            '/opt/sing-box/v2api_stats.db',
            '/usr/local/sing-box/v2api_stats.db',
            '/tmp/v2api_stats.db'
        ]

    logger.info("Searching for database file")

    for path in possible_paths:
        # 检查文件是否存在
        cmd = f"test -f '{path}' && echo 'exists' || echo 'not_exists'"
        exit_status, out, err = proxy.execute_command(cmd, timeout=timeout)

        if exit_status == 0 and 'exists' in out.strip():
            # 验证文件是否是有效的SQLite数据库
            cmd = f"file '{path}'"
            exit_status, out, err = proxy.execute_command(cmd, timeout=timeout)
            if exit_status == 0 and 'SQLite' in out:
                logger.info(f"Found database file: {path}")
                return path

    logger.warning("No valid database file found")
    return None


def fetch_db_data_direct(proxy, table_names=None, db_path=None, timeout=10):
    """直接在远程服务器上查询数据库并返回数据（不复制文件）"""
    if table_names is None:
        table_names = ['users']

    logger.info("Direct query database")

    # 如果没有指定数据库路径，自动查找
    if db_path is None:
        db_path = find_database_file(proxy, timeout=timeout)
        if not db_path:
            raise FileNotFoundError("Database file not found on remote server")

    logger.info(f"Using database: {db_path}")

    results = {}

    for table in table_names:
        try:
            logger.info(f"Querying table: {table}")

            # 检查表是否存在
            check_cmd = f"sqlite3 '{db_path}' \"SELECT name FROM sqlite_master WHERE type='table' AND name='{table}';\""
            exit_status, out, err = proxy.execute_command(check_cmd, timeout=timeout)

            if exit_status != 0 or not out.strip():
                logger.warning(f"Table {table} does not exist")
                results[table] = []
                continue

            # 查询表结构
            structure_cmd = f"sqlite3 '{db_path}' \"PRAGMA table_info('{table}');\""
            exit_status, out, err = proxy.execute_command(structure_cmd, timeout=timeout)

            if exit_status != 0:
                logger.warning(f"Failed to get structure for table {table}")
                results[table] = []
                continue

            # 解析表结构
            lines = out.strip().split('\n')
            columns = []
            for line in lines:
                if line.strip():
                    parts = line.split('|')
                    if len(parts) >= 2:
                        columns.append(parts[1])  # 列名在第二个位置

            if not columns:
                logger.warning(f"No columns found for table {table}")
                results[table] = []
                continue

            # 查询表数据，以JSON格式返回
            # 构建JSON对象字段映射
            json_mappings = []
            for col in columns:
                json_mappings.append(f"'{col}', {col}")
            json_mapping_str = ", ".join(json_mappings)
            query_cmd = f"sqlite3 '{db_path}' \"SELECT json_group_array(json_object({json_mapping_str})) FROM (SELECT * FROM '{table}');\""
            exit_status, out, err = proxy.execute_command(query_cmd, timeout=30)

            if exit_status != 0:
                logger.warning(f"Failed to query data from table {table}")
                results[table] = []
                continue

            # 解析JSON结果
            import json
            try:
                data = json.loads(out.strip())
                results[table] = data
            except json.JSONDecodeError as e:
                logger.warning(f"Failed to parse JSON from table {table}: {e}")
                # 回退到CSV格式
                csv_cmd = f"sqlite3 '{db_path}' \".headers on\" \".mode csv\" \"SELECT * FROM '{table}';\""
                exit_status, csv_out, csv_err = proxy.execute_command(csv_cmd, timeout=30)

                if exit_status == 0:
                    lines = csv_out.strip().split('\n')
                    if len(lines) > 1:
                        headers = [h.strip('"') for h in lines[0].split(',')]
                        rows = []
                        for line in lines[1:]:
                            if line.strip():
                                values = [v.strip('"') for v in line.split(',')]
                                rows.append(dict(zip(headers, values)))
                        results[table] = rows
                    else:
                        results[table] = []
                else:
                    results[table] = []

        except Exception as e:
            logger.error(f"Error querying table {table}: {e}")
            results[table] = []

    return results


def fetch_and_save_tables_csv(proxy, table_names, out_dir=None, **kwargs):
    """Fetch specified tables from remote DB and save each table as CSV in out_dir."""
    # 当未指定 out_dir 时，默认保存至 ./csv/ 目录下
    if out_dir is None:
        out_dir = (Path('.') / 'csv').resolve()
    else:
        out_dir = Path(out_dir).resolve()
    # 确保目录存在
    out_dir.mkdir(parents=True, exist_ok=True)

    # 使用新的直接查询方法获取数据
    data = fetch_db_data_direct(proxy, table_names=table_names, **kwargs)
    written = []
    import csv
    for table, rows in data.items():
        fname = out_dir / f"{table}.csv"
        if not rows:
            # create empty file with no rows
            with open(fname, 'w', newline='', encoding='utf-8') as f:
                pass
            written.append(str(fname))
            continue
        cols = list(rows[0].keys())
        with open(fname, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=cols)
            writer.writeheader()
            for r in rows:
                writer.writerow(r)
        written.append(str(fname))
    return written


def get_remote_ports_by_protocol(proxy, timeout=10):
    """获取远端所有端口，并按协议名作为键，输出的端口列表为值。"""
    logger.info("Getting remote ports")

    # 先尝试 ss 命令，如果失败则使用 netstat 命令
    cmd = "ss -tuln"
    exit_status, output, error = proxy.execute_command(cmd, timeout=timeout)

    # 如果 ss 命令失败，尝试使用 netstat
    if exit_status != 0:
        logger.warning("ss command failed, trying netstat...")
        cmd = "netstat -tuln"
        exit_status, output, error = proxy.execute_command(cmd, timeout=timeout)

        if exit_status != 0:
            logger.error(f"Both ss and netstat commands failed: {error}")
            return {}

    # 解析输出并按协议分组
    ports_by_protocol = {'tcp': [], 'udp': [], 'tcp6': [], 'udp6': []}

    for line in output.strip().split('\n'):
        line = line.strip()
        if not line or line.startswith('Netid') or line.startswith('Proto') or line.startswith('Active'):
            continue

        # 解析 ss/netstat 命令输出格式
        parts = line.split()
        if len(parts) >= 5:
            protocol = parts[0].lower()
            address = parts[4]  # Local Address:Port 在第5列

            # 处理 IPv6 地址格式 [::]:port 或 127.0.0.1:port
            if ']:' in address:
                # IPv6 地址格式 [addr]:port
                port_part = address.split(']:')[-1]
            elif ':' in address:
                # IPv4 地址格式 addr:port
                port_part = address.split(':')[-1]
            else:
                # 只有端口号的情况
                port_part = address

            # 移除可能的 * 前缀
            port_part = port_part.lstrip('*')

            if port_part.isdigit():
                port = int(port_part)

                # 根据地址类型判断协议版本
                if '[' in address or '::' in address:
                    # IPv6 地址
                    protocol_key = f"{protocol}6"
                else:
                    # IPv4 地址
                    protocol_key = protocol

                if protocol_key in ports_by_protocol:
                    if port not in ports_by_protocol[protocol_key]:
                        ports_by_protocol[protocol_key].append(port)

    # 过滤掉空列表并排序
    return {k: sorted(v) for k, v in ports_by_protocol.items() if v}