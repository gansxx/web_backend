#!/usr/bin/env python3
"""Create a Vultr instance and run the local init_env.sh remotely via SSH.

Usage examples:
  python deploy_and_init.py --key ~/.ssh/id_rsa --script ./init_env.sh

This script imports the existing create_new_instance/get_instance_ip functions from
the local vps management module and implements robust retry/timeout/error handling.
"""
import sys
import time
import socket
from pathlib import Path
import argparse
from loguru import logger as LOG
import json
import paramiko

# dynamically load local vps_vultur_manage.py to avoid package/relative import issues
here = Path(__file__).resolve().parent
vps_path = here / 'vps_vultur_manage.py'
if not vps_path.exists():
    raise FileNotFoundError(f"Required module not found: {vps_path}")
import importlib.util
spec = importlib.util.spec_from_file_location('vps_vultur_manage', str(vps_path))
vps_mod = importlib.util.module_from_spec(spec)
try:
    spec.loader.exec_module(vps_mod)
except Exception as e:
    # re-raise with clearer message
    raise RuntimeError(f"Failed to load vps_vultur_manage.py: {e}")

# dynamically load local node_manage.py
node_path = here / 'node_manage.py'
if not node_path.exists():
    raise FileNotFoundError(f"Required module not found: {node_path}")
spec_node = importlib.util.spec_from_file_location('node_manage', str(node_path))
node_mod = importlib.util.module_from_spec(spec_node)
try:
    spec_node.loader.exec_module(node_mod)
except Exception as e:
    # re-raise with clearer message
    raise RuntimeError(f"Failed to load node_manage.py: {e}")

create_new_instance = getattr(vps_mod, 'create_new_instance')
get_instance_ip = getattr(vps_mod, 'get_instance_ip')
get_instance_info = getattr(vps_mod, 'get_instance_info')
delete_instance = getattr(vps_mod, 'delete_instance')
execute_remote_command = getattr(vps_mod, 'execute_remote_command')

run_remote_self_sb_change = getattr(node_mod, 'run_remote_self_sb_change')


def wait_for_instance_ok(instance_id, timeout=300, poll_interval=10):
    start = time.time()
    while True:
        info = get_instance_info(instance_id)
        status = info.get('instance', {}).get('server_status')
        LOG.info(f"instance {instance_id} status: {status}")
        if status == 'ok':
            return True
        if time.time() - start > timeout:
            return False
        time.sleep(poll_interval)


def wait_for_ssh(host, port=22, timeout=180, interval=5):
    start = time.time()
    while True:
        try:
            with socket.create_connection((host, port), timeout=5):
                return True
        except Exception:
            if time.time() - start > timeout:
                return False
            time.sleep(interval)


def ssh_upload_and_exec(host, username, key_file, local_script, remote_path='/root/init_env.sh', connect_timeout=30, cmd_timeout=3600):
    """Upload local_script to remote_path, chmod +x and execute it; stream output.
    Returns (exit_status, stdout, stderr)
    """
    # Use key_filename when connecting for SFTP to avoid parsing private keys here.
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    LOG.info(f"Connecting to {host} as {username} for upload")
    try:
        client.connect(hostname=host, port=22, username=username, key_filename=str(key_file), timeout=connect_timeout)
    except Exception as e:
        LOG.error(f"SFTP connect failed to {host}: {e}")
        raise

    try:
        sftp = client.open_sftp()
        LOG.info(f"Uploading {local_script} -> {remote_path}")
        sftp.put(str(local_script), remote_path)
        sftp.chmod(remote_path, 0o755)
        sftp.close()
    finally:
        try:
            client.close()
        except Exception:
            pass

    # Use the provider's execute_remote_command to run the script (it handles key parsing)
    cmd = f"/bin/bash {remote_path}"
    LOG.info(f"Executing remote init script via provider interface: {cmd}")
    # execute_remote_command returns (exit_status, stdout, stderr).
    # Avoid logging stdout/stderr here to prevent noisy download logs on success.
    # The caller will log stdout/stderr only when rc != 0 (error case).
    rc, out, err = execute_remote_command(host, 22, username, str(key_file), cmd, timeout=cmd_timeout)
    return rc, out, err

def server_status_check(ip, args, instance_id=None, services_to_check=None):
    """
    检查远端服务是否正常启动。
    返回 True 表示全部正常，否则处理异常并返回 False。
    """
    if services_to_check is None:
        services_to_check = ['sing-box', 'v2api-persist.service']
    services_ok = True
    for svc in services_to_check:
        # 首先用 is-active 简短判断
        rc_s, out_s, err_s = execute_remote_command(ip, 22, args.user, str(args.key), f"sudo systemctl is-active --quiet {svc}", timeout=20)
        if rc_s == 0:
            LOG.info(f"Service {svc} is active on {ip}")
        else:
            services_ok = False
            # 拉取详细 status 供诊断
            rc_s2, out_s2, err_s2 = execute_remote_command(ip, 22, args.user, str(args.key), f"sudo systemctl status {svc} --no-pager", timeout=30)
            LOG.error(f"Service {svc} is NOT active on {ip}. systemctl status:\n{out_s2}\n{err_s2}")

    if not services_ok:
        LOG.error("One or more services failed to start on remote host")
        if instance_id and args.delete_on_fail:
            try:
                delete_instance(instance_id)
            except Exception as e:
                LOG.warning(f"Failed to delete instance {instance_id}: {e}")
        return False
    return True

def main(argv=None):
    p = argparse.ArgumentParser(description="Create instance and run init_env.sh remotely")
    p.add_argument('--key', required=False, default=str(Path(__file__).parent / 'id_ed25519'), help='SSH private key file path')
    p.add_argument('--user', default='root', help='SSH username')
    p.add_argument('--script', default=str(Path(__file__).resolve().parent / 'init_env.sh'), help='Local init script to upload')
    p.add_argument('--wait-time', type=int, default=300, help='Seconds to wait for instance to reach OK')
    p.add_argument('--ssh-wait', type=int, default=180, help='Seconds to wait for SSH port')
    p.add_argument('--delete-on-fail', action='store_true', help='Delete created instance on failure')
    p.add_argument('--no-create', action='store_true', help='Do not create instance; just use --ip to run script')
    p.add_argument('--ip', help='If --no-create, the target IP to connect to')
    args = p.parse_args(argv)

    local_script = Path(args.script)
    if not local_script.exists():
        LOG.error(f"Local script not found: {local_script}")
        return 2

    instance_id = None
    try:
        if args.no_create:
            if not args.ip:
                LOG.error("--no-create requires --ip")
                return 2
            ip = args.ip
        else:
            LOG.info("Creating new instance...")
            instance_id = create_new_instance()
            if not instance_id:
                LOG.error("create_new_instance failed to return an id")
                return 3
            LOG.info(f"Created instance id: {instance_id}")

            ok = wait_for_instance_ok(instance_id, timeout=args.wait_time)
            if not ok:
                LOG.error("Instance did not become ready in time")
                if args.delete_on_fail:
                    try:
                        delete_instance(instance_id)
                    except Exception as e:
                        LOG.warning(f"Failed to delete instance {instance_id}: {e}")
                return 4
            ip = get_instance_ip(instance_id)
            LOG.info(f"Instance {instance_id} IP: {ip}")

        LOG.info(f"Waiting for SSH on {ip}...")
        if not wait_for_ssh(ip, timeout=args.ssh_wait):
            LOG.error(f"SSH port not available on {ip} within timeout")
            if instance_id and args.delete_on_fail:
                try:
                    delete_instance(instance_id)
                except Exception as e:
                    LOG.warning(f"Failed to delete instance {instance_id}: {e}")
            return 5

        # attempt to upload and run script, retry a few times if transient failures
        attempts = 3
        for attempt in range(1, attempts + 1):
            try:
                rc, out, err = ssh_upload_and_exec(ip, args.user, args.key, local_script)
            except Exception as e:
                LOG.exception(f"SSH attempt failed on {ip}: {e}")
                if attempt < attempts:
                    time.sleep(5)
                    continue
                if instance_id and args.delete_on_fail:
                    try:
                        delete_instance(instance_id)
                    except Exception as e:
                        LOG.warning(f"Failed to delete instance {instance_id}: {e}")
                return 7
            if rc == 0:
                LOG.info("Remote init completed successfully")
                # 执行远端 self_sb_change.sh 创建默认用户 'test'
                key_file = str(Path(__file__).parent / 'id_ed25519')
                # exit_status, hy2_link, out_sb, err_sb = run_remote_self_sb_change(ip, 22, args.user, key_file, name_arg='test')
                # if exit_status != 0:
                #     LOG.error(f"Failed to run self_sb_change on {ip}: {err_sb}")
                #     if instance_id and args.delete_on_fail:
                #         try:
                #             delete_instance(instance_id)
                #         except Exception as e:
                #             LOG.warning(f"Failed to delete instance {instance_id}: {e}")
                #     return 6
                # LOG.info(f"Successfully created user 'test' on {ip}, hy2_link: {hy2_link}")
                # 检查远端服务状态
                status_ok = server_status_check(ip, args, instance_id, services_to_check=['sing-box'])
                if not status_ok:
                    return 6
                return 0
            else:
                LOG.error(f"Remote init failed with exit {rc}")
                if out:
                    LOG.error(f"Remote stdout (error case):\n{out}")
                if err:
                    LOG.error(f"Remote stderr (error case):\n{err}")
                if attempt < attempts:
                    LOG.info(f"Retrying ({attempt}/{attempts}) after failure...")
                    time.sleep(5)
                    continue
                else:
                    if instance_id and args.delete_on_fail:
                        try:
                            delete_instance(instance_id)
                            LOG.info(f"Deleted instance {instance_id} due to failure")
                        except Exception as e:
                            LOG.warning(f"Failed to delete instance {instance_id}: {e}")
                    return 6
    except KeyboardInterrupt:
        LOG.warning("Interrupted by user")
        return 130



if __name__ == '__main__':
    sys.exit(main())
