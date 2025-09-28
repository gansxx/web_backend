# Multi-Cloud VPS Management System

A unified interface for managing VPS instances across multiple cloud providers (Vultr, AWS EC2, AWS Lightsail) with enhanced SSH connectivity and session management.

## Features

### 🌐 Multi-Cloud Support
- **Vultr**: Full API integration with plans, regions, and instance management
- **AWS EC2**: Complete EC2 instance lifecycle management
- **AWS Lightsail**: Simplified cloud instances with unified interface

### 🔧 Unified Interface
- Single API for all cloud operations
- Consistent data models across providers
- Factory pattern for easy provider switching

### 🔐 Enhanced SSH Management
- Automatic key format detection (RSA, Ed25519, ECDSA, DSS)
- Real-time command output streaming
- Context manager support for automatic connection cleanup
- Legacy compatibility with existing code

### ⚙️ Flexible Configuration
- JSON and INI configuration file support
- Environment variable credential loading
- Provider-specific parameter mapping

## Architecture

```
vps_manager/
├── __init__.py              # Package exports
├── base.py                  # Abstract base classes
├── config.py                # Configuration management
├── factory.py               # Provider factory pattern
├── ssh_manager.py           # Enhanced SSH functionality
├── exceptions.py            # Custom exceptions
├── vultr.py                 # Vultr provider implementation
├── aws_ec2.py              # AWS EC2 provider implementation
└── aws_lightsail.py        # AWS Lightsail provider implementation
```

## Installation

### Prerequisites

```bash
# Base requirements
pip install requests loguru paramiko

# AWS support (optional)
pip install boto3

# Conda environment activation
conda activate proxy_manage  # or your preferred environment
```

### Package Installation

The package is designed to work with the existing codebase structure. Simply ensure the `vps_manager` directory is in your Python path.

## Quick Start

### 1. Basic Usage

```python
from vps_manager import get_provider, VPSConfig

# Create a provider instance
provider = get_provider('vultr')  # or 'aws_ec2', 'aws_lightsail'

# List instances
instances = provider.list_instances()
for instance in instances:
    print(f"{instance.name}: {instance.status.value} - {instance.ip_address}")

# Create new instance
config = VPSConfig(
    region='nrt',
    instance_type='vc2-1c-1gb',
    name='my-server',
    os_id=2136
)
instance_id = provider.create_instance(config)
```

### 2. Enhanced SSH Connection

```python
from node_manage_v2 import EnhancedNodeProxy

# Create enhanced proxy with cloud integration
proxy = EnhancedNodeProxy(
    hostname="192.168.1.100",
    username="root",
    key_file="/path/to/private/key",
    provider="vultr",
    instance_id="abc123"
)

# Use context manager
with proxy:
    # Execute commands
    exit_code, stdout, stderr = proxy.execute_command("uname -a")

    # Get cloud instance info
    instance_info = proxy.get_instance_info()

    # Perform cloud operations
    if proxy.reboot_instance():
        print("Instance rebooted successfully")
```

### 3. Cloud VPS Manager

```python
from node_manage_v2 import CloudVPSManager

manager = CloudVPSManager()

# Create instance
instance_id = manager.create_instance('vultr', {
    'region': 'nrt',
    'instance_type': 'vc2-1c-1gb',
    'name': 'test-server',
    'os_id': 2136
})

# Create node proxy for the instance
proxy = manager.create_node_proxy('vultr', instance_id)
if proxy:
    with proxy:
        proxy.execute_command("echo 'Hello from cloud!'")
```

## Configuration

### Environment Variables

```bash
# Vultr
export VULTR_API_KEY="your_vultr_api_key"

# AWS
export AWS_ACCESS_KEY_ID="your_access_key"
export AWS_SECRET_ACCESS_KEY="your_secret_key"
export AWS_DEFAULT_REGION="us-east-1"
```

### Configuration Files

#### JSON Format (`vps_config.json`)
```json
{
  "vultr": {
    "region": "nrt",
    "instance_type": "vc2-1c-1gb",
    "name": "my-vultr-server",
    "os_id": 2136,
    "ssh_key_id": ["key-id-here"],
    "backup_enabled": false
  },
  "aws_ec2": {
    "region": "us-east-1",
    "instance_type": "t3.micro",
    "name": "my-ec2-server",
    "os_id": "ami-0c02fb55956c7d316",
    "ssh_key_id": "my-keypair",
    "security_groups": ["sg-12345678"]
  }
}
```

#### INI Format (`server_detail_multi.ini`)
```ini
[vultr]
region=nrt
plan=vc2-1c-1gb
label=my-vultr-server
os_id=2136

[aws_ec2]
region=us-east-1
instance_type=t3.micro
name=my-ec2-server
os_id=ami-0c02fb55956c7d316
```

#### Credentials Files (`provider_credentials.json`)
```json
{
  "credentials": {
    "api_key": "${VULTR_API_KEY}"
  },
  "region": "nrt"
}
```

## Provider-Specific Information

### Vultr
- **Authentication**: API key
- **Regions**: Global data centers
- **Instance Types**: Plans (vc2-1c-1gb, etc.)
- **OS**: Numeric OS IDs
- **Features**: Scripts, SSH keys, backups

### AWS EC2
- **Authentication**: Access key + Secret key
- **Regions**: AWS regions (us-east-1, etc.)
- **Instance Types**: EC2 instance types (t3.micro, etc.)
- **OS**: AMI IDs (ami-xxxxxxxx)
- **Features**: Security groups, subnets, user data

### AWS Lightsail
- **Authentication**: Access key + Secret key
- **Regions**: Lightsail regions
- **Instance Types**: Bundles (nano_2_0, etc.)
- **OS**: Blueprint IDs (ubuntu_20_04, etc.)
- **Features**: Simple configuration, static IPs

## Migration from Legacy Code

### Automatic Migration
The system provides backward compatibility through wrapper functions:

```python
# Legacy code continues to work
from vps_vultr_manage import create_new_instance, get_instance_ip

# New unified interface (recommended)
from vps_manager import get_provider
```

### NodeProxy Migration
```python
# Old NodeProxy (still supported)
from node_manage import NodeProxy

# New Enhanced NodeProxy (recommended)
from node_manage_v2 import EnhancedNodeProxy
```

## Error Handling

The system provides comprehensive error handling:

```python
from vps_manager.exceptions import (
    VPSError, VPSConnectionError, VPSAuthError,
    VPSNotFoundError, VPSOperationError
)

try:
    provider = get_provider('vultr')
    instances = provider.list_instances()
except VPSAuthError:
    print("Authentication failed - check your API key")
except VPSConnectionError:
    print("Network connection failed")
except VPSError as e:
    print(f"VPS operation failed: {e}")
```

## Testing

### Run Demo Script
```bash
cd center_management
python demo_multi_cloud.py
```

### Manual Testing
```python
# Test provider availability
from vps_manager import list_providers
print("Supported providers:", list_providers())

# Test specific provider
from vps_manager import get_provider
vultr = get_provider('vultr')
print("Vultr regions:", len(vultr.list_regions()))
```

## Advanced Usage

### Custom Provider Implementation
```python
from vps_manager.base import VPSProvider
from vps_manager.factory import VPSFactory

class CustomProvider(VPSProvider):
    @property
    def provider_name(self):
        return "custom"

    def _initialize_client(self):
        # Your implementation
        pass

    # Implement other abstract methods...

# Register custom provider
VPSFactory.register_provider('custom', CustomProvider)
```

### Custom Configuration
```python
from vps_manager.config import ConfigManager

config_manager = ConfigManager('/custom/config/path')
credentials = config_manager.get_credentials('vultr')
config = config_manager.load_instance_config('vultr')
```

## Troubleshooting

### Common Issues

1. **Import Errors**
   ```bash
   # Ensure packages are installed
   pip install requests loguru paramiko boto3
   ```

2. **Authentication Failures**
   ```bash
   # Check environment variables
   echo $VULTR_API_KEY
   echo $AWS_ACCESS_KEY_ID
   ```

3. **Connection Issues**
   ```python
   # Test provider connectivity
   provider = get_provider('vultr')
   regions = provider.list_regions()  # Should not raise exception
   ```

### Debug Mode
```python
import logging
logging.basicConfig(level=logging.DEBUG)

# Enable debug logging
from loguru import logger
logger.add(sys.stderr, level="DEBUG")
```

## Performance Considerations

- **Connection Pooling**: SSH connections are managed efficiently with context managers
- **Lazy Loading**: Provider clients are initialized only when needed
- **Caching**: Configuration and credentials are cached for session reuse
- **Parallel Operations**: Multiple cloud operations can be performed concurrently

## Security Best Practices

1. **Environment Variables**: Store credentials in environment variables
2. **File Permissions**: Secure credential files (600 permissions)
3. **Key Management**: Use SSH key authentication over passwords
4. **Access Control**: Implement proper IAM policies for cloud accounts

## Contributing

### Adding New Providers
1. Create new provider class inheriting from `VPSProvider`
2. Implement all abstract methods
3. Add provider registration in `factory.py`
4. Create configuration templates
5. Add tests and documentation

### Code Style
- Follow PEP 8 guidelines
- Use type hints for function signatures
- Add comprehensive docstrings
- Include error handling for all operations

## Support

For issues and questions:
1. Check the troubleshooting section
2. Review error messages and logs
3. Verify configuration and credentials
4. Test with the demo script

## License

This code is part of the web backend project and follows the same licensing terms.