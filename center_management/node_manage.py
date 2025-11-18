from pathlib import Path
import shlex
import re
from loguru import logger
import importlib
import importlib.util
import subprocess
import paramiko
import sqlite3
import tempfile
import os
from contextlib import contextmanager


# Robustly load vps_vultur_manage whether this module is imported as a package
# or run from a notebook/script where relative imports fail.
try:
	# prefer normal import when running as package
	vps_mod = importlib.import_module('vps_vultur_manage')
except Exception:
	# fallback: load by file path from the same directory
	spec_path = Path(__file__).resolve().parent / 'vps_vultur_manage.py'
	spec = importlib.util.spec_from_file_location('vps_vultur_manage', str(spec_path))
	vps_mod = importlib.util.module_from_spec(spec)
	spec.loader.exec_module(vps_mod)


class NodeProxy:
	"""Node代理类，管理SSH连接并提供远程操作方法"""

	def __init__(self, hostname, port=22, username='root', key_file=None, timeout=30):
		self.hostname = hostname
		self.port = port
		self.username = username
		self.key_file = key_file
		self.timeout = timeout
		self._ssh_client = None
		self._connected = False

	def connect(self):
		"""建立SSH连接"""
		if not self._connected or not self._ssh_client:
			self._ssh_client = vps_mod.ssh_connect(self.hostname, self.port, self.username, self.key_file, self.timeout)
			self._connected = True
			logger.info(f"SSH连接已建立: {self.username}@{self.hostname}:{self.port}")
		return self._ssh_client

	def disconnect(self):
		"""断开SSH连接"""
		if self._ssh_client and self._connected:
			try:
				self._ssh_client.close()
				logger.info(f"SSH连接已断开: {self.username}@{self.hostname}:{self.port}")
			except Exception as e:
				logger.warning(f"关闭SSH连接失败: {e}")
			finally:
				self._ssh_client = None
				self._connected = False

	def execute_command(self, command, timeout=600):
		"""执行远程命令"""
		if not self._connected or not self._ssh_client:
			self.connect()
		return vps_mod.execute_remote_command_with_client(self._ssh_client, command, timeout, self.hostname)

	def get_sftp_client(self):
		"""获取SFTP客户端"""
		if not self._connected or not self._ssh_client:
			self.connect()
		return self._ssh_client.open_sftp()

	def __enter__(self):
		"""上下文管理器入口"""
		self.connect()
		return self

	def __exit__(self, exc_type, exc_val, exc_tb):
		"""上下文管理器出口"""
		self.disconnect()

	def __del__(self):
		"""析构函数，确保连接被断开"""
		if hasattr(self, '_connected') and self._connected:
			self.disconnect()


@contextmanager
def node_proxy_context(hostname, port=22, username='root', key_file=None, timeout=30):
	"""NodeProxy上下文管理器"""
	proxy = NodeProxy(hostname, port, username, key_file, timeout)
	try:
		proxy.connect()
		yield proxy
	finally:
		proxy.disconnect()

def run_remote_self_sb_change(proxy, port_arg=None, name_arg=None, up_mbps=None, down_mbps=None, script_path='/root/sing-box-v2ray/self_sb_change.sh'):
	"""在远端执行已存在的 self_sb_change.sh 脚本以注册用户，并返回 hy2_link。

	参数:
		proxy: NodeProxy对象，用于SSH连接
		port_arg: 端口参数
		name_arg: 用户名参数
		up_mbps: 上传带宽限制
		down_mbps: 下载带宽限制
		script_path: 脚本路径

	返回值: (exit_status, hy2_link_or_none, stdout, stderr)
	"""
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

def run_add_user_v3(proxy, name_arg=None, alias=None,up_mbps=None,down_mbps=None,script_path='/root/sing-box-v2ray/sb_user_manager/add_user.py'):
    """在远端执行已存在的 self_sb_change.sh 脚本以注册用户，并返回 hy2_link。

    参数:
        proxy: NodeProxy对象，用于SSH连接
        alias: 用户套餐计划，如
        name_arg: 用户名参数
        up_mbps: 上传带宽限制
        down_mbps: 下载带宽限制
        script_path: 脚本路径

    返回值: (exit_status, hy2_link_or_none, stdout, stderr)
    """
    args = []
    if name_arg is not None:
        args.append(f"-n {shlex.quote(str(name_arg))}")
    if up_mbps is not None:
        args.append(f"-u {int(up_mbps)}")
    if down_mbps is not None:
        args.append(f"-d {int(down_mbps)}")
    if alias is not None:
        args.append(f"-a {alias}")

    argstr = ' '.join(args)
    command = f"sudo python3 {script_path} {argstr}"
    logger.info(f"Executing remote script: {command}")

    exit_status, out, err = proxy.execute_command(command)

    # 远程脚本通过 SSH 返回纯文本输出，需要用正则表达式提取信息
    result = {}
    hy2_link = None

    if out and out.strip():
        # 尝试提取 hysteria2 链接
        # 格式: hysteria2://password@server:port?...
        link_match = re.search(r"hysteria2://[A-Za-z0-9\-._~%:@/?&=+#]+", out)
        if link_match:
            hy2_link = link_match.group(0)
            result['share_link'] = hy2_link

        # 尝试提取端口号
        # 格式: "✓ Allocated port: 28282"
        port_match = re.search(r"Allocated port:\s+(\d+)", out)
        if port_match:
            result['port'] = int(port_match.group(1))

        # 尝试提取套餐计划
        # 格式: "Adding user: xxx with plan: free_plan"
        plan_match = re.search(r"with plan:\s+(\w+)", out)
        if plan_match:
            result['plan'] = plan_match.group(1)

        # 尝试提取用户名
        # 格式: "Adding user: test_user@example.com"
        user_match = re.search(r"Adding user:\s+([^\s]+)", out)
        if user_match:
            result['name'] = user_match.group(1)

    return exit_status, hy2_link, result if result else out, err


def verify_hy2_link(uri, script_path=None, timeout=30, cwd=None):
	"""调用本地的 `link_verificate.sh` 脚本验证给定的 hysteria2 URI 是否可用。

	参数:
		uri: hysteria2 URI 字符串
		script_path: 可执行脚本路径；为 None 时默认使用同目录下的 `link_verificate.sh`
		timeout: 调用超时时间（秒）
		cwd: 运行脚本时的工作目录（可选）

	返回: (returncode, stdout, stderr, success)
		success 为布尔值，代表脚本返回码为 0
	"""
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

# 运行远端数据获取功能


def find_database_file(proxy, possible_paths=None, timeout=10):
	"""在远程服务器上查找数据库文件

	参数:
		proxy: NodeProxy对象，用于SSH连接
		possible_paths: 可能的数据库路径列表
		timeout: 超时时间

	返回: 找到的数据库文件路径，如果没找到返回None
	"""
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
	"""直接在远程服务器上查询数据库并返回数据（不复制文件）

	参数:
		proxy: NodeProxy对象，用于SSH连接
		table_names: 要查询的表名列表，None表示查询['users']
		db_path: 数据库文件路径，None表示自动查找
		timeout: 超时时间

	返回: dict, key为表名, value为list[dict]（每行为dict列名->值）
	"""
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
	"""Fetch specified tables from remote DB and save each table as CSV in out_dir.

	参数:
		proxy: NodeProxy对象，用于SSH连接
		table_names: 要查询的表名列表
		out_dir: 输出目录，None表示默认目录
		**kwargs: 其他参数

	返回: 写入的文件路径列表
	"""
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
	"""获取远端所有端口，并按协议名作为键，输出的端口列表为值。

	使用 netstat 或 ss 命令获取远端服务器上所有监听的端口，
	然后按协议类型（TCP/UDP）进行分组。

	参数:
		proxy: NodeProxy对象，用于SSH连接
		timeout: 连接超时时间，默认10秒

	返回:
		dict: 键为协议名（'tcp', 'udp', 'tcp6', 'udp6'），值为对应的端口列表
	"""
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
