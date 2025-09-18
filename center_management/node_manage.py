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

def run_remote_self_sb_change(hostname, port, username, key_file, port_arg=None, name_arg=None, up_mbps=None, down_mbps=None, script_path='/root/sing-box-v2ray/self_sb_change.sh'):
	"""在远端执行已存在的 self_sb_change.sh 脚本以注册用户，并返回 hy2_link。

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
	logger.info(f"Executing remote script on {hostname}: {command}")

	exit_status, out, err = vps_mod.execute_remote_command(hostname, port, username, key_file, command)

	# 尝试从 stdout 中解析 hy2_link，脚本以打印 hy2_link 为最后一部分
	hy2_link = None
	if out:
		# 一般 hy2 链接的格式以 hysteria2:// 开头，尝试搜索第一个匹配项
		m = re.search(r"hysteria2://[A-Za-z0-9\-._~%:@/?&=+#]+", out)
		if m:
			hy2_link = m.group(0)

	return exit_status, hy2_link, out, err


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


def fetch_and_read_db(hostname, username, key_file, table_names=None, remote_path='/var/lib/sing-box/v2api_stats.db', remote_tmp='/tmp/v2api_stats_copy.db', timeout=10):
	"""从远端复制 sqlite DB（使用 VACUUM INTO 或 cp），下载并返回指定表的数据。

	参数:
		table_names: None 或 list[str]；为 None 时默认读取 ['users']。

	返回: dict, key 为表名, value 为 list[dict]（每行为 dict 列名->值）
	"""
	if table_names is None:
		table_names = ['users']

	logger.info(f"fetch_and_read_db: connecting to {hostname} user={username}")

	# Use central ssh_connect helper from vps_mod
	client = vps_mod.ssh_connect(hostname, 22, username, key_file, timeout=timeout)

	# Attempt to create a safe copy on the remote side to avoid reading a live DB
	cmd = f"sudo sqlite3 {remote_path} \"VACUUM INTO '{remote_tmp}';\" || sudo cp {remote_path} {remote_tmp}"
	stdin, stdout, stderr = client.exec_command(cmd, timeout=30)
	rc = stdout.channel.recv_exit_status()
	if rc != 0:
		# still continue to attempt to copy via sudo cp fallback if vacuum failed
		logger.warning(f"remote copy command returned {rc}; stderr={stderr.read().decode('utf-8', errors='ignore')}")

	sftp = client.open_sftp()
	local_tmp = tempfile.mktemp(suffix='.db')
	try:
		sftp.get(remote_tmp, local_tmp)
	finally:
		try:
			sftp.remove(remote_tmp)
		except Exception:
			pass
		sftp.close()
		try:
			client.close()
		except Exception:
			pass

	results = {}
	try:
		conn = sqlite3.connect(local_tmp)
		for table in table_names:
			try:
				cur = conn.execute(f'SELECT * FROM "{table}"')
			except Exception as e:
				logger.warning(f"Failed to query table {table}: {e}")
				results[table] = []
				continue
			cols = [d[0] for d in cur.description]
			rows = [dict(zip(cols, r)) for r in cur.fetchall()]
			results[table] = rows
		conn.close()
	finally:
		try:
			os.remove(local_tmp)
		except Exception:
			pass

	return results


def fetch_and_save_tables_csv(hostname, username, key_file, table_names, out_dir=None, **kwargs):
	"""Fetch specified tables from remote DB and save each table as CSV in out_dir.

	Returns list of written file paths.
	"""
	if out_dir is None:
		out_dir = Path('.').resolve()
	else:
		out_dir = Path(out_dir).resolve()
		out_dir.mkdir(parents=True, exist_ok=True)

	data = fetch_and_read_db(hostname, username, key_file, table_names=table_names, **kwargs)
	written = []
	import csv
	for table, rows in data.items():
		fname = out_dir / f"{hostname.replace(':','_')}.{table}.csv"
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
