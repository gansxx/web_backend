#!/usr/bin/env python3
"""
Multi-Cloud VPS Management Demo

This script demonstrates how to use the new multi-cloud VPS management system
to create, manage, and connect to VPS instances across different cloud providers.
"""

import os
import sys
import time
from pathlib import Path
from loguru import logger

# Add the current directory to Python path
sys.path.insert(0, str(Path(__file__).parent))

try:
    from .vps_manager import get_provider, VPSConfig, list_providers
    from .node_manage_v2 import CloudVPSManager, EnhancedNodeProxy
    DEMO_AVAILABLE = True
except ImportError as e:
    logger.error(f"VPS Manager not available: {e}")
    DEMO_AVAILABLE = False


def demo_list_providers():
    """Demo: List all supported cloud providers"""
    print("\n" + "="*50)
    print("SUPPORTED CLOUD PROVIDERS")
    print("="*50)

    if not DEMO_AVAILABLE:
        print("❌ VPS Manager not available")
        return

    providers = list_providers()
    for i, provider in enumerate(providers, 1):
        print(f"{i}. {provider.upper()}")

    print(f"\nTotal: {len(providers)} providers supported")


def demo_vultr_operations():
    """Demo: Vultr VPS operations"""
    print("\n" + "="*50)
    print("VULTR VPS OPERATIONS DEMO")
    print("="*50)

    if not DEMO_AVAILABLE:
        print("❌ VPS Manager not available")
        return

    try:
        # Initialize Vultr provider
        print("🔄 Initializing Vultr provider...")
        vultr = get_provider('vultr')
        print("✅ Vultr provider initialized")

        # List existing instances
        print("\n🔄 Listing existing Vultr instances...")
        instances = vultr.list_instances()
        print(f"✅ Found {len(instances)} instances")

        for instance in instances:
            print(f"  - {instance.name} ({instance.id}): {instance.status.value} - {instance.ip_address}")

        # List regions
        print("\n🔄 Listing available regions...")
        regions = vultr.list_regions()
        print(f"✅ Found {len(regions)} regions")
        for region in regions[:5]:  # Show first 5
            print(f"  - {region['id']}: {region['name']}")

        # List instance types
        print("\n🔄 Listing available instance types...")
        plans = vultr.list_instance_types()
        print(f"✅ Found {len(plans)} plans")
        for plan in plans[:5]:  # Show first 5
            print(f"  - {plan['id']}: {plan['vcpu_count']}vCPU, {plan['ram']}MB RAM")

    except Exception as e:
        print(f"❌ Vultr demo failed: {e}")


def demo_aws_ec2_operations():
    """Demo: AWS EC2 VPS operations"""
    print("\n" + "="*50)
    print("AWS EC2 VPS OPERATIONS DEMO")
    print("="*50)

    if not DEMO_AVAILABLE:
        print("❌ VPS Manager not available")
        return

    try:
        # Check if AWS credentials are available
        if not (os.getenv('AWS_ACCESS_KEY_ID') and os.getenv('AWS_SECRET_ACCESS_KEY')):
            print("⚠️  AWS credentials not found in environment variables")
            print("   Set AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY to run this demo")
            return

        # Initialize AWS EC2 provider
        print("🔄 Initializing AWS EC2 provider...")
        ec2 = get_provider('aws_ec2')
        print("✅ AWS EC2 provider initialized")

        # List existing instances
        print("\n🔄 Listing existing EC2 instances...")
        instances = ec2.list_instances()
        print(f"✅ Found {len(instances)} instances")

        for instance in instances:
            print(f"  - {instance.name} ({instance.id}): {instance.status.value} - {instance.ip_address}")

        # List regions
        print("\n🔄 Listing available regions...")
        regions = ec2.list_regions()
        print(f"✅ Found {len(regions)} regions")
        for region in regions[:5]:  # Show first 5
            print(f"  - {region['id']}: {region['name']}")

    except Exception as e:
        print(f"❌ AWS EC2 demo failed: {e}")


def demo_aws_lightsail_operations():
    """Demo: AWS Lightsail VPS operations"""
    print("\n" + "="*50)
    print("AWS LIGHTSAIL VPS OPERATIONS DEMO")
    print("="*50)

    if not DEMO_AVAILABLE:
        print("❌ VPS Manager not available")
        return

    try:
        # Check if AWS credentials are available
        if not (os.getenv('AWS_ACCESS_KEY_ID') and os.getenv('AWS_SECRET_ACCESS_KEY')):
            print("⚠️  AWS credentials not found in environment variables")
            print("   Set AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY to run this demo")
            return

        # Initialize AWS Lightsail provider
        print("🔄 Initializing AWS Lightsail provider...")
        lightsail = get_provider('aws_lightsail')
        print("✅ AWS Lightsail provider initialized")

        # List existing instances
        print("\n🔄 Listing existing Lightsail instances...")
        instances = lightsail.list_instances()
        print(f"✅ Found {len(instances)} instances")

        for instance in instances:
            print(f"  - {instance.name} ({instance.id}): {instance.status.value} - {instance.ip_address}")

        # List regions
        print("\n🔄 Listing available regions...")
        regions = lightsail.list_regions()
        print(f"✅ Found {len(regions)} regions")
        for region in regions[:5]:  # Show first 5
            print(f"  - {region['id']}: {region['name']}")

        # List bundles (instance types)
        print("\n🔄 Listing available bundles...")
        bundles = lightsail.list_instance_types()
        print(f"✅ Found {len(bundles)} bundles")
        for bundle in bundles[:5]:  # Show first 5
            print(f"  - {bundle['id']}: {bundle['vcpu_count']}vCPU, {bundle['ram']}GB RAM")

    except Exception as e:
        print(f"❌ AWS Lightsail demo failed: {e}")


def demo_cloud_vps_manager():
    """Demo: Cloud VPS Manager unified interface"""
    print("\n" + "="*50)
    print("CLOUD VPS MANAGER DEMO")
    print("="*50)

    if not DEMO_AVAILABLE:
        print("❌ VPS Manager not available")
        return

    try:
        # Initialize cloud VPS manager
        print("🔄 Initializing Cloud VPS Manager...")
        manager = CloudVPSManager()
        print("✅ Cloud VPS Manager initialized")

        # List instances from all providers
        for provider in ['vultr', 'aws_ec2', 'aws_lightsail']:
            try:
                print(f"\n🔄 Listing {provider.upper()} instances...")
                instances = manager.list_instances(provider)
                print(f"✅ Found {len(instances)} {provider} instances")

                for instance in instances:
                    print(f"  - {instance.name} ({instance.id}): {instance.status.value}")

            except Exception as e:
                print(f"⚠️  Failed to list {provider} instances: {e}")

    except Exception as e:
        print(f"❌ Cloud VPS Manager demo failed: {e}")


def demo_configuration_examples():
    """Demo: Show configuration examples"""
    print("\n" + "="*50)
    print("CONFIGURATION EXAMPLES")
    print("="*50)

    print("📄 Example VPS configurations:")

    # Vultr configuration
    print("\n🔸 Vultr Configuration:")
    vultr_config = {
        "region": "nrt",
        "instance_type": "vc2-1c-1gb",
        "name": "my-vultr-server",
        "os_id": 2136,
        "ssh_key_id": ["key-id-here"],
        "backup_enabled": False
    }
    print(f"   {vultr_config}")

    # AWS EC2 configuration
    print("\n🔸 AWS EC2 Configuration:")
    ec2_config = {
        "region": "us-east-1",
        "instance_type": "t3.micro",
        "name": "my-ec2-server",
        "os_id": "ami-0c02fb55956c7d316",
        "ssh_key_id": "my-keypair",
        "security_groups": ["sg-12345678"]
    }
    print(f"   {ec2_config}")

    # AWS Lightsail configuration
    print("\n🔸 AWS Lightsail Configuration:")
    lightsail_config = {
        "region": "us-east-1",
        "instance_type": "nano_2_0",
        "name": "my-lightsail-server",
        "os_id": "ubuntu_20_04",
        "ssh_key_id": "my-lightsail-key"
    }
    print(f"   {lightsail_config}")

    print("\n📁 Configuration file examples created:")
    print("   - vps_config.json")
    print("   - server_detail_multi.ini")
    print("   - *_credentials.json (template files)")


def demo_ssh_connection():
    """Demo: Enhanced SSH connection"""
    print("\n" + "="*50)
    print("ENHANCED SSH CONNECTION DEMO")
    print("="*50)

    if not DEMO_AVAILABLE:
        print("❌ VPS Manager not available")
        return

    print("📡 Enhanced SSH features:")
    print("   - Unified SSH interface across all cloud providers")
    print("   - Automatic key format detection (RSA, Ed25519, ECDSA)")
    print("   - Real-time command output streaming")
    print("   - Automatic timeout handling")
    print("   - Context manager support")

    print("\n💡 Usage example:")
    print("""
    # Create enhanced node proxy with cloud integration
    proxy = EnhancedNodeProxy(
        hostname="1.2.3.4",
        username="root",
        key_file="/path/to/key",
        provider="vultr",
        instance_id="abc123"
    )

    # Use context manager for automatic connection management
    with proxy:
        # Execute commands
        exit_code, stdout, stderr = proxy.execute_command("uname -a")

        # Get VPS instance information
        instance_info = proxy.get_instance_info()

        # Perform VPS operations
        proxy.reboot_instance()
    """)


def main():
    """Run all demos"""
    print("🚀 MULTI-CLOUD VPS MANAGEMENT SYSTEM DEMO")
    print("="*60)

    if not DEMO_AVAILABLE:
        print("❌ Demo not available. Please install the VPS manager dependencies.")
        return

    # Run all demos
    demo_list_providers()
    demo_configuration_examples()
    demo_vultr_operations()
    demo_aws_ec2_operations()
    demo_aws_lightsail_operations()
    demo_cloud_vps_manager()
    demo_ssh_connection()

    print("\n" + "="*60)
    print("✅ DEMO COMPLETED")
    print("="*60)
    print("\n💡 Next steps:")
    print("   1. Set up your cloud provider credentials")
    print("   2. Customize configuration files")
    print("   3. Create and manage VPS instances")
    print("   4. Use enhanced SSH connections")
    print("\n📚 For more information, see the documentation in the vps_manager package.")


if __name__ == "__main__":
    main()