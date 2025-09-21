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
        logger.info(f"SSH connection established to {hostname}:{port} as {username}")
        logger.info(f"Begin to Execute command on {hostname}:{port}: {command}")
        stdin, stdout, stderr = ssh.exec_command(command, timeout=timeout)
        
        out = stdout.read().decode('utf-8', errors='ignore')
        err = stderr.read().decode('utf-8', errors='ignore')
        try:
            exit_status = stdout.channel.recv_exit_status()
        except Exception:
            exit_status = 0
        return exit_status, out, err
    except Exception as e:
        logger.error(f"SSH attempt failed on {hostname}:{port}: {e}")
        return 255, '', str(e)
    finally:
        if ssh:
            try:
                logger.info("try to close ssh connection")
                ssh.close()
            except Exception:
                logger.warning("ssh close failed")
                pass


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
    

    
        


    