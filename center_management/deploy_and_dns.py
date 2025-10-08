#!/usr/bin/env python3
"""Create a Vultr instance, run init_env.sh, and configure DNS record.

This script extends deploy_and_init.py by adding automatic DNS configuration
after successful VPS deployment. The IP address is obtained from the deployment
process and configured to point to jiasu.selfgo.asia.

Usage examples:
  python deploy_and_dns.py --key ~/.ssh/id_rsa --script ./init_env.sh
  python deploy_and_dns.py --domain selfgo.asia --subdomain jiasu
  python deploy_and_dns.py --no-create --ip 1.2.3.4 --skip-dns
"""
import sys
import time
from pathlib import Path
import argparse
from loguru import logger as LOG

# Import the original deploy_and_init module
here = Path(__file__).resolve().parent
deploy_init_path = here / 'deploy_and_init.py'
if not deploy_init_path.exists():
    raise FileNotFoundError(f"Required module not found: {deploy_init_path}")

import importlib.util
spec = importlib.util.spec_from_file_location('deploy_and_init', str(deploy_init_path))
deploy_init_mod = importlib.util.module_from_spec(spec)
try:
    spec.loader.exec_module(deploy_init_mod)
except Exception as e:
    raise RuntimeError(f"Failed to load deploy_and_init.py: {e}")

# Import DNS client
dns_path = here / 'dns.py'
if not dns_path.exists():
    raise FileNotFoundError(f"Required module not found: {dns_path}")
spec_dns = importlib.util.spec_from_file_location('dns', str(dns_path))
dns_mod = importlib.util.module_from_spec(spec_dns)
try:
    spec_dns.loader.exec_module(dns_mod)
except Exception as e:
    raise RuntimeError(f"Failed to load dns.py: {e}")

DNSClient = getattr(dns_mod, 'DNSClient')

# Import necessary functions from deploy_and_init
create_new_instance = getattr(deploy_init_mod, 'create_new_instance')
get_instance_ip = getattr(deploy_init_mod, 'get_instance_ip')
get_instance_info = getattr(deploy_init_mod, 'get_instance_info')
delete_instance = getattr(deploy_init_mod, 'delete_instance')
execute_remote_command = getattr(deploy_init_mod, 'execute_remote_command')
wait_for_instance_ok = getattr(deploy_init_mod, 'wait_for_instance_ok')
wait_for_ssh = getattr(deploy_init_mod, 'wait_for_ssh')
ssh_upload_and_exec = getattr(deploy_init_mod, 'ssh_upload_and_exec')
server_status_check = getattr(deploy_init_mod, 'server_status_check')
run_remote_self_sb_change = getattr(deploy_init_mod, 'run_remote_self_sb_change')


def configure_dns(ip_address, domain, subdomain, dns_client=None):
    """
    Configure DNS record to point subdomain.domain to the given IP address.

    Strategy: First try to update existing record (to avoid multiple IPs on one domain),
    then create new record if update fails (record doesn't exist).

    Args:
        ip_address: The IP address to point to
        domain: The domain name (e.g., selfgo.asia)
        subdomain: The subdomain (e.g., jiasu)
        dns_client: Optional DNSClient instance, will create new one if None

    Returns:
        bool: True if DNS configuration succeeded, False otherwise
    """
    if dns_client is None:
        dns_client = DNSClient()

    full_domain = f"{subdomain}.{domain}"
    LOG.info(f"Configuring DNS: {full_domain} -> {ip_address}")

    try:
        # First, try to update existing record to avoid multiple IPs
        LOG.info(f"Attempting to update existing DNS record for {full_domain}")
        try:
            dns_client.update_record_ip(
                domain=domain,
                subdomain=subdomain,
                new_ip=ip_address,
                record_type="A",
                ttl=600
            )
            LOG.info(f"✓ Successfully updated DNS record: {full_domain} -> {ip_address}")
            return True
        except Exception as update_err:
            # If update fails, the record might not exist yet
            LOG.warning(f"Failed to update DNS record (might not exist): {update_err}")
            LOG.info("Attempting to create new DNS record")

            # Try to create a new record
            try:
                dns_client.create_record(
                    domain=domain,
                    value=ip_address,
                    subdomain=subdomain,
                    record_type="A",
                    ttl=600
                )
                LOG.info(f"✓ Successfully created DNS record: {full_domain} -> {ip_address}")
                return True
            except Exception as create_err:
                LOG.error(f"Failed to create DNS record: {create_err}")
                return False

    except Exception as e:
        LOG.error(f"Unexpected error during DNS configuration: {e}")
        return False


def verify_dns(domain, subdomain, expected_ip, max_wait=60, poll_interval=10):
    """
    Verify that DNS record has been propagated and resolves correctly.

    Args:
        domain: The domain name
        subdomain: The subdomain
        expected_ip: The expected IP address
        max_wait: Maximum seconds to wait for DNS propagation
        poll_interval: Seconds between DNS checks

    Returns:
        bool: True if DNS resolves correctly, False otherwise
    """
    dns_client = DNSClient()
    full_domain = f"{subdomain}.{domain}"

    LOG.info(f"Verifying DNS propagation for {full_domain} -> {expected_ip}")
    LOG.info(f"Note: DNS propagation may take a few minutes...")

    start_time = time.time()
    while time.time() - start_time < max_wait:
        is_match, resolved_ips = dns_client.dns_status(
            domain=domain,
            subdomain=subdomain,
            expected_ip=expected_ip
        )

        if is_match:
            LOG.info(f"✓ DNS verification successful: {full_domain} resolves to {expected_ip}")
            return True
        else:
            elapsed = int(time.time() - start_time)
            if resolved_ips:
                LOG.info(f"DNS resolves to {resolved_ips}, waiting for {expected_ip}... ({elapsed}s elapsed)")
            else:
                LOG.info(f"DNS not yet propagated, waiting... ({elapsed}s elapsed)")
            time.sleep(poll_interval)

    LOG.warning(f"DNS verification timed out after {max_wait}s")
    LOG.warning(f"DNS may still propagate - check manually with: dig {full_domain}")
    return False


def main(argv=None):
    p = argparse.ArgumentParser(
        description="Create instance, run init_env.sh, and configure DNS",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )

    # Original deploy_and_init arguments
    p.add_argument('--key', required=False,
                   default=str(Path(__file__).parent / 'id_ed25519'),
                   help='SSH private key file path')
    p.add_argument('--user', default='root', help='SSH username')
    p.add_argument('--script',
                   default=str(Path(__file__).resolve().parent / 'init_env.sh'),
                   help='Local init script to upload')
    p.add_argument('--wait-time', type=int, default=300,
                   help='Seconds to wait for instance to reach OK')
    p.add_argument('--ssh-wait', type=int, default=180,
                   help='Seconds to wait for SSH port')
    p.add_argument('--delete-on-fail', action='store_true',
                   help='Delete created instance on failure')
    p.add_argument('--no-create', action='store_true',
                   help='Do not create instance; just use --ip to run script')
    p.add_argument('--ip', help='If --no-create, the target IP to connect to')

    # DNS configuration arguments
    p.add_argument('--domain', default='selfgo.asia',
                   help='Domain name for DNS record (default: selfgo.asia)')
    p.add_argument('--subdomain', default='jiasu',
                   help='Subdomain for DNS record (default: jiasu)')
    p.add_argument('--skip-dns', action='store_true',
                   help='Skip DNS configuration step')
    p.add_argument('--verify-dns', action='store_true',
                   help='Verify DNS propagation after configuration')
    p.add_argument('--dns-wait', type=int, default=60,
                   help='Max seconds to wait for DNS verification')

    args = p.parse_args(argv)

    local_script = Path(args.script)
    if not local_script.exists():
        LOG.error(f"Local script not found: {local_script}")
        return 2

    instance_id = None
    ip = None

    try:
        # Step 1: Deploy VPS and run initialization
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

        # Step 2: Upload and execute initialization script
        attempts = 3
        init_success = False
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
                status_ok = server_status_check(ip, args, instance_id, services_to_check=['sing-box'])
                if not status_ok:
                    return 6
                init_success = True
                break
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

        if not init_success:
            LOG.error("Failed to initialize instance after all retries")
            return 6

        # Step 3: Configure DNS
        if args.skip_dns:
            LOG.info("Skipping DNS configuration (--skip-dns specified)")
            LOG.info(f"✓ Deployment completed successfully. Instance IP: {ip}")
            return 0

        LOG.info("=" * 60)
        LOG.info("Starting DNS configuration...")
        LOG.info("=" * 60)

        dns_success = configure_dns(ip, args.domain, args.subdomain)

        if not dns_success:
            LOG.error("DNS configuration failed")
            LOG.warning(f"Instance is running at {ip}, but DNS was not configured")
            return 8

        # Step 4: Optional DNS verification
        if args.verify_dns:
            LOG.info("Verifying DNS propagation...")
            verify_success = verify_dns(
                args.domain,
                args.subdomain,
                ip,
                max_wait=args.dns_wait
            )
            if not verify_success:
                LOG.warning("DNS verification did not complete within timeout")
                LOG.warning("DNS may still propagate - manual verification recommended")

        # Success
        full_domain = f"{args.subdomain}.{args.domain}"
        LOG.info("=" * 60)
        LOG.info("✓ Deployment and DNS configuration completed successfully!")
        LOG.info(f"Instance IP: {ip}")
        LOG.info(f"DNS Record: {full_domain} -> {ip}")
        LOG.info("=" * 60)
        return 0

    except KeyboardInterrupt:
        LOG.warning("Interrupted by user")
        return 130
    except Exception as e:
        LOG.exception(f"Unexpected error: {e}")
        return 1


if __name__ == '__main__':
    sys.exit(main())
