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


# def run_remote_self_sb_change(proxy, port_arg=None, name_arg=None, up_mbps=None, down_mbps=None, script_path='/root/sing-box-v2ray/self_sb_change.sh'):
# 	"""在远端执行已存在的 self_sb_change.sh 脚本以注册用户，并返回 hy2_link。

# 	参数:
# 		proxy: NodeProxy对象，用于SSH连接
# 		port_arg: 端口参数
# 		name_arg: 用户名参数
# 		up_mbps: 上传带宽限制
# 		down_mbps: 下载带宽限制
# 		script_path: 脚本路径

# 	返回值: (exit_status, hy2_link_or_none, stdout, stderr)
# 	"""
# 	args = []
# 	if port_arg is not None:
# 		args.append(f"-p {int(port_arg)}")
# 	if name_arg is not None:
# 		args.append(f"-n {shlex.quote(str(name_arg))}")
# 	if up_mbps is not None:
# 		args.append(f"-u {int(up_mbps)}")
# 	if down_mbps is not None:
# 		args.append(f"-d {int(down_mbps)}")

# 	argstr = ' '.join(args)
# 	command = f"sudo {script_path} {argstr}"
# 	logger.info(f"Executing remote script: {command}")

# 	exit_status, out, err = proxy.execute_command(command)

# 	# 尝试从 stdout 中解析 hy2_link，脚本以打印 hy2_link 为最后一部分
# 	hy2_link = None
# 	if out:
# 		# 一般 hy2 链接的格式以 hysteria2:// 开头，尝试搜索第一个匹配项
# 		m = re.search(r"hysteria2://[A-Za-z0-9\-._~%:@/?&=+#]+", out)
# 		if m:
# 			hy2_link = m.group(0)

# 	return exit_status, hy2_link, out, err

def run_add_user_v3(proxy, name_arg=None, alias=None,up_mbps=None,down_mbps=None,script_path='/root/sing-box-v2ray/sb_user_manager/add_user.py'):
    """在远端执行已存在的 add_user.py 脚本以注册用户，并返回 hy2_link。

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
        # 提取所有 hysteria2 链接（可能有多个）
        # 格式: hysteria2://password@server:port?...
        links = re.findall(r"hysteria2://[A-Za-z0-9\-._~%:@/?&=+#]+", out)
        if links:
            # 聚合所有链接为一个字符串（换行符分隔）
            hy2_link = '\n'.join(links)
            result['share_link'] = hy2_link
            result['link_count'] = len(links)

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


def run_update_user(proxy, name_arg=None, days=30, script_path='/root/sing-box-v2ray/sb_user_manager/update_user.py'):
    """在远端执行已存在的 update_user.py 脚本以更新用户到期时间。

    参数:
        proxy: NodeProxy对象，用于SSH连接
        name_arg: 用户名参数（邮箱地址）
        days: 延长天数（默认30天）
        script_path: 脚本路径

    返回值: (exit_status, result_dict, stdout, stderr)
        result_dict 包含:
        {
            'name': str,                    # 用户邮箱
            'old_expires_date': str,        # 原到期日期
            'new_expires_date': str,        # 新到期日期
            'days_extended': int,           # 延长天数
            'was_banned': bool,             # 是否曾被禁
            'unban_success': bool           # 解禁是否成功（如果有）
        }
    """
    args = []
    if name_arg is not None:
        args.append(f"-n {shlex.quote(str(name_arg))}")
    if days is not None:
        args.append(f"-d {int(days)}")

    argstr = ' '.join(args)
    command = f"sudo python3 {script_path} {argstr}"
    logger.info(f"Executing remote update script: {command}")

    exit_status, out, err = proxy.execute_command(command)

    # 解析输出
    result = {}

    if out and out.strip():
        # 提取用户名
        # 格式: "User: user@example.com"
        user_match = re.search(r"User:\s+([^\s]+)", out)
        if user_match:
            result['name'] = user_match.group(1)

        # 提取旧到期日期
        # 格式: "Old expiration:  Never" 或 "Old expiration:  2025-01-15 10:30:45"
        old_exp_match = re.search(r"Old expiration:\s+(.+)", out)
        if old_exp_match:
            result['old_expires_date'] = old_exp_match.group(1).strip()

        # 提取新到期日期
        # 格式: "New expiration:  2025-02-14 10:30:45"
        new_exp_match = re.search(r"New expiration:\s+(.+)", out)
        if new_exp_match:
            result['new_expires_date'] = new_exp_match.group(1).strip()

        # 提取延长天数
        # 格式: "Days extended:   30"
        days_match = re.search(r"Days extended:\s+(\d+)", out)
        if days_match:
            result['days_extended'] = int(days_match.group(1))

        # 检查是否曾被禁
        # 格式: "Was banned:      Yes" 或 "Was banned:      No"
        banned_match = re.search(r"Was banned:\s+(Yes|No)", out)
        if banned_match:
            result['was_banned'] = (banned_match.group(1) == 'Yes')
        else:
            result['was_banned'] = False

        # 检查解禁是否成功
        # 格式: "Unban status:    ✓ Successfully unbanned"
        unban_success_match = re.search(r"Unban status:\s+✓ Successfully unbanned", out)
        result['unban_success'] = bool(unban_success_match)

        # 如果没有提取到名称，使用传入的参数
        if 'name' not in result and name_arg:
            result['name'] = name_arg

    return exit_status, result if result else out, out, err


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


