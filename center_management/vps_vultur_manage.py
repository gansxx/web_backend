import os
import requests
import json
from loguru import logger
import argparse
import time
from pathlib import Path
import configparser
import paramiko
import shlex
from dotenv import load_dotenv

# ① 把 .env 加载进环境变量
load_dotenv()   # 默认当前目录下的 .env

headers = {
    'Authorization': 'Bearer ' + os.getenv('VULTR_API_KEY', ''),
    'Content-Type': 'application/json',
}
# 获取当前脚本的绝对路径
script_path = Path(__file__).resolve()

# 获取当前脚本所在的目录
script_dir = script_path.parent

file_path =os.path.join(script_dir,'server_detail.ini')
config = configparser.ConfigParser()
config.read(file_path)
logger.info(f"读取配置文件: {file_path}")
df=config['server_detail']


region=df.get('region')
plan=df.get('plan')
label=df.get('label')
os_id=df.getint('os_id')
logger.debug(f"当前region是{region}")
#ToDo:添加从本地json文件中读取参数的代码，并增加选择区域的功能
def create_new_instance(region=region, plan=plan, label=label, os_id=os_id):
    """
    创建新的Vultr实例
    """
    # region对应地址，lax代表洛杉矶,ewr代表纽约,sgp代表新加坡
    # region可以通过https://api.vultr.com/v2/regions获取
    # plan对应地址，vc2-1c-1gb代表1核1G内存
    # label代表实例名称
    # os_id代表操作系统ID，可以通过https://api.vultr.com/v2/os获取
    # sshkey_id代表SSH Key的ID，可以通过https://api.vultr.com/v2/sshkeys获取
    #云端sshkey_id与本地测试不同
    json_data = {
        'region': region,
        'plan': plan,
        'label': label,
        'os_id': os_id,
        'user_data': 'QmFzZTY0IEV4YW1wbGUgRGF0YQ==',
        'backups': 'disabled',
        'script_id':'e154aeac-0221-45ef-98a3-59ec10c04c3f',
        'sshkey_id':['3f25451c-9da9-4c09-aabc-21ecd54dd647'],
    }

    response = requests.post('https://api.vultr.com/v2/instances', headers=headers, json=json_data)
    text=response.text
    json_data = json.loads(text)
    try:
        instance_id= json_data['instance']['id']
        return instance_id
    except KeyError:
        logger.error(f"创建实例失败: {json_data}")

def reboot_instance(instance_ids):
    url="https://api.vultr.com/v2/instances/reboot"
    json_data={
        "instance_ids" : instance_ids
    }
    response = requests.post(url, headers=headers, json=json_data)
    if response.status_code == 204:
        logger.info(f"Instance {instance_ids} 开始重启.")
    else:
        logger.warning(f"Failed to reboot instance {instance_ids}. Status code: {response.status_code}")

def get_info(url):
    """
    获取Vultr API的响应信息
    """
    response = requests.get(url, headers=headers)
    text = response.text
    json_data = json.loads(text)
    return json_data

def get_instance_ip(instance_id):
    #获取特定实例的IP地址
    url=f"https://api.vultr.com/v2/instances/{instance_id}/ipv4" 
    json_data=get_info(url)
    if 'ipv4s' not in json_data or not json_data['ipv4s']:
        raise ValueError(f"Instance {instance_id} has no IPv4 addresses assigned.")
    return json_data['ipv4s'][0]['ip'] 

def list_instances():
    """
    列出所有Vultr实例
    """
    url = "https://api.vultr.com/v2/instances"
    json_data = get_info(url)
    return json_data

def get_instance_info(instance_id):
    url=f"https://api.vultr.com/v2/instances/{instance_id}"
    json_data = get_info(url)
    return json_data

# 删除指定实例
def delete_instance(instance_id):
    json_data = list_instances()
    if json_data['instances']:
        url = f"https://api.vultr.com/v2/instances/{instance_id}"
        #发送delete请求
        response = requests.delete(url, headers=headers)
        if response.status_code == 204:
            logger.info(f"Instance {instance_id} 成功删除.")
        else:
            logger.warning(f"Failed to delete instance {instance_id}. Status code: {response.status_code}")
    else:
        logger.info("当前没有实例")
        return

def _load_private_key_try_all(key_file):
    """Try to load the private key with multiple Paramiko key classes.

    Returns a Paramiko PKey instance on success, or None if none could be loaded.
    """
    if not key_file:
        return None
    key_classes = [
        getattr(paramiko, 'RSAKey', None),
        getattr(paramiko, 'Ed25519Key', None),
        getattr(paramiko, 'ECDSAKey', None),
        getattr(paramiko, 'DSSKey', None),
    ]
    # If the key is in the new OpenSSH format, Paramiko's PKey parsers often
    # fail with struct errors; detect and skip trying to parse such files so
    # we can fall back to passing key_filename to ssh.connect().
    try:
        with open(key_file, 'r', encoding='utf-8', errors='ignore') as f:
            head = f.read(512)
            if 'BEGIN OPENSSH PRIVATE KEY' in head:
                logger.debug(f"Key {key_file} appears to be OpenSSH private key format; skip PKey parsing")
                return None
    except Exception:
        # couldn't read file; continue to attempt parse (will likely fail)
        logger.debug(f"Could not read key file header: {key_file}")

    for cls in key_classes:
        if not cls:
            continue
        try:
            return cls.from_private_key_file(key_file)
        except Exception as e:
            logger.debug(f"Key loader {cls.__name__} failed for {key_file}: {e}")
    return None


def execute_remote_command(hostname, port, username, key_file, command, timeout=600):
    """在远程服务器上通过 SSH 执行命令并返回 (exit_status, stdout, stderr).

    key_file may be a path to a private key; the function will try multiple
    Paramiko key types and fall back to passing key_filename to connect().
    """
    ssh = None
    try:
        ssh = ssh_connect(hostname, port, username, key_file, timeout=30)
        return execute_remote_command_with_client(ssh, command, timeout, hostname)
    except Exception as e:
        duration = time.time() - time.time()
        logger.error(f"[SSH] Exception on {hostname}:{port} after {duration:.1f}s: {e}")
        return 255, '', str(e)
    finally:
        if ssh:
            try:
                logger.info("Closing SSH connection")
                ssh.close()
            except Exception:
                logger.warning("ssh close failed")
                pass


def execute_remote_command_with_client(ssh_client, command, timeout=600, hostname=None):
    """使用已建立的SSH连接执行命令并返回 (exit_status, stdout, stderr).

    Args:
        ssh_client: 已连接的Paramiko SSHClient实例
        command: 要执行的命令
        timeout: 命令执行超时时间（秒）
        hostname: 主机名（用于日志记录）
    """
    start_ts = time.time()
    # 打印将要执行的命令（做长度截断，避免日志过长）
    _cmd_preview = command if isinstance(command, str) else str(command)
    if len(_cmd_preview) > 200:
        _cmd_preview = _cmd_preview[:200] + ' …(truncated)'

    host_info = hostname or ssh_client.get_transport().getpeername()[0] if ssh_client.get_transport() else "unknown"
    logger.info(f"[SSH] Exec on {host_info} -> {shlex.quote(_cmd_preview)}")

    try:
        transport = ssh_client.get_transport()
        if not transport:
            raise RuntimeError("SSH transport not available")
        chan = transport.open_session()
        # 显式经由 bash 执行，保证与交互式一致
        chan.exec_command(f"/bin/bash -lc {shlex.quote(command)}")
        chan.settimeout(1.0)

        stdout_buf = []
        stderr_buf = []

        while True:
            # 超时控制
            if timeout and (time.time() - start_ts) > timeout:
                try:
                    chan.close()
                except Exception:
                    pass
                raise TimeoutError(f"Remote command timed out after {timeout}s")

            # 实时读取 STDOUT
            try:
                if chan.recv_ready():
                    data = chan.recv(4096)
                    if data:
                        text = data.decode('utf-8', errors='ignore')
                        stdout_buf.append(text)
                        for line in text.splitlines():
                            logger.info(f"[SSH][STDOUT] {line}")
            except Exception:
                pass

            # 实时读取 STDERR
            try:
                if chan.recv_stderr_ready():
                    data_e = chan.recv_stderr(4096)
                    if data_e:
                        text_e = data_e.decode('utf-8', errors='ignore')
                        stderr_buf.append(text_e)
                        for line in text_e.splitlines():
                            logger.error(f"[SSH][STDERR] {line}")
            except Exception:
                pass

            if chan.exit_status_ready():
                break

            time.sleep(0.05)

        # 排空剩余数据
        drain_deadline = time.time() + 1.0
        while time.time() < drain_deadline:
            drained = False
            if chan.recv_ready():
                data = chan.recv(4096)
                if data:
                    text = data.decode('utf-8', errors='ignore')
                    stdout_buf.append(text)
                    for line in text.splitlines():
                        logger.info(f"[SSH][STDOUT] {line}")
                    drained = True
            if chan.recv_stderr_ready():
                data_e = chan.recv_stderr(4096)
                if data_e:
                    text_e = data_e.decode('utf-8', errors='ignore')
                    stderr_buf.append(text_e)
                    for line in text_e.splitlines():
                        logger.error(f"[SSH][STDERR] {line}")
                    drained = True
            if not drained:
                break

        try:
            exit_status = chan.recv_exit_status()
        except Exception:
            exit_status = 0

        out = ''.join(stdout_buf)
        err = ''.join(stderr_buf)

        duration = time.time() - start_ts
        if exit_status == 0:
            logger.info(f"[SSH] Done rc=0 in {duration:.1f}s on {host_info}")
        else:
            logger.error(f"[SSH] Failed rc={exit_status} in {duration:.1f}s on {host_info}")
        return exit_status, out, err
    except Exception as e:
        duration = time.time() - start_ts
        logger.error(f"[SSH] Exception on {host_info} after {duration:.1f}s: {e}")
        return 255, '', str(e)


def ssh_connect(hostname, port, username, key_file, timeout=30):
    """建立并返回一个 Paramiko SSHClient 已连接实例。

    抛出异常时表示连接失败。
    """
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())

    pkey = None
    if key_file:
        pkey = _load_private_key_try_all(key_file)

    connect_kwargs = {
        'hostname': hostname,
        'port': int(port) if port else 22,
        'username': username,
        'timeout': timeout,
    }
    if pkey:
        logger.debug("Using parsed PKey for SSH")
        connect_kwargs['pkey'] = pkey
    else:
        if key_file:
            logger.debug(f"Using key_filename for SSH: {key_file}")
            connect_kwargs['key_filename'] = key_file

    ssh.connect(**connect_kwargs)
    return ssh
    

# run_remote_self_sb_change 已迁移到 node_manage.py
    

    
        


    