"""
AWS Lightsail VPS Provider Implementation

AWS Lightsail-specific implementation of the VPS provider interface.
"""

import time
from typing import Dict, List, Optional, Any, Union
from loguru import logger

from .base import VPSProvider, VPSInstance, VPSConfig, VPSStatus
from .exceptions import VPSError, VPSConnectionError, VPSAuthError, VPSNotFoundError, VPSOperationError

try:
    import boto3
    from botocore.exceptions import ClientError, NoCredentialsError, PartialCredentialsError
    BOTO3_AVAILABLE = True
except ImportError:
    BOTO3_AVAILABLE = False
    boto3 = None
    ClientError = None
    NoCredentialsError = None
    PartialCredentialsError = None


class AWSLightsailProvider(VPSProvider):
    """AWS Lightsail VPS provider implementation"""

    def __init__(self, credentials: Dict[str, str], region: Optional[str] = None):
        """
        Initialize AWS Lightsail provider

        Args:
            credentials: Dictionary containing AWS credentials
            region: Default region for operations
        """
        if not BOTO3_AVAILABLE:
            raise VPSError("boto3 is required for AWS Lightsail provider. Install with: pip install boto3")

        super().__init__(credentials, region)
        self.access_key_id = credentials.get('access_key_id')
        self.secret_access_key = credentials.get('secret_access_key')
        self.session_token = credentials.get('session_token')

        if not self.access_key_id or not self.secret_access_key:
            raise VPSAuthError("AWS access_key_id and secret_access_key are required")

        self.region = region or 'us-east-1'

    @property
    def provider_name(self) -> str:
        """Return the name of the provider"""
        return "aws_lightsail"

    def _initialize_client(self):
        """Initialize and return the AWS Lightsail client"""
        try:
            session_kwargs = {
                'aws_access_key_id': self.access_key_id,
                'aws_secret_access_key': self.secret_access_key,
                'region_name': self.region
            }

            if self.session_token:
                session_kwargs['aws_session_token'] = self.session_token

            session = boto3.Session(**session_kwargs)
            return session.client('lightsail')

        except (NoCredentialsError, PartialCredentialsError) as e:
            raise VPSAuthError(f"Invalid AWS credentials: {e}")
        except Exception as e:
            raise VPSConnectionError(f"Failed to initialize AWS Lightsail client: {e}")

    def _handle_aws_error(self, error: ClientError, operation: str = "operation"):
        """Handle AWS ClientError and convert to appropriate VPS exception"""
        error_code = error.response.get('Error', {}).get('Code', 'Unknown')
        error_message = error.response.get('Error', {}).get('Message', str(error))

        if error_code in ['NotFoundException', 'InvalidInputException']:
            raise VPSNotFoundError(f"Resource not found: {error_message}")
        elif error_code in ['AccessDeniedException', 'UnauthorizedOperation']:
            raise VPSAuthError(f"Access denied: {error_message}")
        elif error_code in ['InvalidParameterValueException', 'InvalidParameterException']:
            raise VPSError(f"Invalid parameter: {error_message}")
        elif error_code == 'ServiceException':
            raise VPSOperationError(f"Service error: {error_message}")
        else:
            raise VPSOperationError(f"AWS Lightsail {operation} failed ({error_code}): {error_message}")

    def _map_lightsail_state(self, lightsail_state: str) -> VPSStatus:
        """Map Lightsail instance state to unified VPSStatus"""
        state_mapping = {
            'pending': VPSStatus.PENDING,
            'running': VPSStatus.RUNNING,
            'shutting-down': VPSStatus.STOPPING,
            'terminated': VPSStatus.STOPPED,
            'stopping': VPSStatus.STOPPING,
            'stopped': VPSStatus.STOPPED,
            'rebooting': VPSStatus.REBOOTING,
        }
        return state_mapping.get(lightsail_state.lower(), VPSStatus.UNKNOWN)

    def _lightsail_instance_to_vps_instance(self, lightsail_instance: Dict[str, Any]) -> VPSInstance:
        """Convert Lightsail instance data to VPSInstance"""
        return VPSInstance(
            id=lightsail_instance['name'],  # Lightsail uses name as identifier
            name=lightsail_instance['name'],
            status=self._map_lightsail_state(lightsail_instance.get('state', {}).get('name', 'unknown')),
            ip_address=lightsail_instance.get('publicIpAddress'),
            private_ip=lightsail_instance.get('privateIpAddress'),
            region=lightsail_instance.get('location', {}).get('regionName'),
            instance_type=lightsail_instance.get('bundleId'),
            os=lightsail_instance.get('blueprintName'),
            created_at=lightsail_instance.get('createdAt', '').isoformat() if lightsail_instance.get('createdAt') else None,
            provider_data=lightsail_instance
        )

    def create_instance(self, config: VPSConfig) -> str:
        """
        Create a new Lightsail instance

        Args:
            config: VPS configuration

        Returns:
            Instance name (Lightsail identifier)
        """
        try:
            # Prepare creation parameters
            create_params = {
                'instanceNames': [config.name],
                'availabilityZone': f"{config.region}a",  # Default to 'a' zone
                'blueprintId': str(config.os_id),  # Blueprint ID
                'bundleId': config.instance_type,  # Bundle ID
            }

            # Add key pair if specified
            if config.ssh_key_id:
                key_name = config.ssh_key_id
                if isinstance(config.ssh_key_id, list):
                    key_name = config.ssh_key_id[0]
                create_params['keyPairName'] = key_name

            # Add user data if specified
            if config.user_data:
                create_params['userData'] = config.user_data

            # Add tags if specified
            if config.tags:
                tags = [{'key': k, 'value': v} for k, v in config.tags.items()]
                create_params['tags'] = tags

            # Create instance
            response = self.client.create_instances(**create_params)

            # Check for any errors in the operation
            operations = response.get('operations', [])
            if operations and operations[0].get('status') == 'Failed':
                error_details = operations[0].get('errorDetails', 'Unknown error')
                raise VPSOperationError(f"Failed to create Lightsail instance: {error_details}")

            logger.info(f"Created Lightsail instance: {config.name}")
            return config.name

        except ClientError as e:
            self._handle_aws_error(e, "instance creation")
        except Exception as e:
            raise VPSOperationError(f"Failed to create Lightsail instance: {e}")

    def delete_instance(self, instance_id: str) -> bool:
        """
        Delete a Lightsail instance

        Args:
            instance_id: Name of the instance to delete

        Returns:
            True if successful
        """
        try:
            self.client.delete_instance(instanceName=instance_id)
            logger.info(f"Deleted Lightsail instance: {instance_id}")
            return True

        except ClientError as e:
            if 'NotFoundException' in str(e):
                logger.warning(f"Instance {instance_id} not found for deletion")
                return False
            self._handle_aws_error(e, "instance deletion")
        except Exception as e:
            logger.error(f"Failed to delete Lightsail instance {instance_id}: {e}")
            return False

    def reboot_instance(self, instance_id: str) -> bool:
        """
        Reboot a Lightsail instance

        Args:
            instance_id: Name of the instance to reboot

        Returns:
            True if successful
        """
        try:
            self.client.reboot_instance(instanceName=instance_id)
            logger.info(f"Rebooted Lightsail instance: {instance_id}")
            return True

        except ClientError as e:
            if 'NotFoundException' in str(e):
                logger.warning(f"Instance {instance_id} not found for reboot")
                return False
            self._handle_aws_error(e, "instance reboot")
        except Exception as e:
            logger.error(f"Failed to reboot Lightsail instance {instance_id}: {e}")
            return False

    def start_instance(self, instance_id: str) -> bool:
        """
        Start a Lightsail instance

        Args:
            instance_id: Name of the instance to start

        Returns:
            True if successful
        """
        try:
            self.client.start_instance(instanceName=instance_id)
            logger.info(f"Started Lightsail instance: {instance_id}")
            return True

        except ClientError as e:
            if 'NotFoundException' in str(e):
                logger.warning(f"Instance {instance_id} not found for start")
                return False
            self._handle_aws_error(e, "instance start")
        except Exception as e:
            logger.error(f"Failed to start Lightsail instance {instance_id}: {e}")
            return False

    def stop_instance(self, instance_id: str) -> bool:
        """
        Stop a Lightsail instance

        Args:
            instance_id: Name of the instance to stop

        Returns:
            True if successful
        """
        try:
            self.client.stop_instance(instanceName=instance_id)
            logger.info(f"Stopped Lightsail instance: {instance_id}")
            return True

        except ClientError as e:
            if 'NotFoundException' in str(e):
                logger.warning(f"Instance {instance_id} not found for stop")
                return False
            self._handle_aws_error(e, "instance stop")
        except Exception as e:
            logger.error(f"Failed to stop Lightsail instance {instance_id}: {e}")
            return False

    def get_instance(self, instance_id: str) -> Optional[VPSInstance]:
        """
        Get information about a specific Lightsail instance

        Args:
            instance_id: Name of the instance

        Returns:
            VPSInstance object or None if not found
        """
        try:
            response = self.client.get_instance(instanceName=instance_id)
            instance = response.get('instance')

            if instance:
                return self._lightsail_instance_to_vps_instance(instance)

            return None

        except ClientError as e:
            if 'NotFoundException' in str(e):
                logger.warning(f"Instance {instance_id} not found")
                return None
            self._handle_aws_error(e, "get instance")
        except Exception as e:
            logger.error(f"Failed to get Lightsail instance {instance_id}: {e}")
            return None

    def list_instances(self) -> List[VPSInstance]:
        """
        List all Lightsail instances

        Returns:
            List of VPSInstance objects
        """
        try:
            response = self.client.get_instances()
            instances = []

            for instance in response.get('instances', []):
                instances.append(self._lightsail_instance_to_vps_instance(instance))

            return instances

        except ClientError as e:
            self._handle_aws_error(e, "list instances")
        except Exception as e:
            logger.error(f"Failed to list Lightsail instances: {e}")
            return []

    def get_instance_ip(self, instance_id: str) -> Optional[str]:
        """
        Get the public IP address of a Lightsail instance

        Args:
            instance_id: Name of the instance

        Returns:
            IP address or None if not available
        """
        instance = self.get_instance(instance_id)
        return instance.ip_address if instance else None

    def list_regions(self) -> List[Dict[str, str]]:
        """
        List available AWS Lightsail regions

        Returns:
            List of region information
        """
        try:
            response = self.client.get_regions()
            regions = []

            for region in response.get('regions', []):
                regions.append({
                    'id': region['name'],
                    'name': region['displayName'],
                    'description': region.get('description', ''),
                    'available': region.get('availabilityZones', [])
                })

            return regions

        except ClientError as e:
            self._handle_aws_error(e, "list regions")
        except Exception as e:
            logger.error(f"Failed to list Lightsail regions: {e}")
            return []

    def list_instance_types(self, region: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        List available Lightsail bundles (instance types)

        Args:
            region: Region to get bundles for (optional)

        Returns:
            List of instance type information
        """
        try:
            response = self.client.get_bundles()
            instance_types = []

            for bundle in response.get('bundles', []):
                # Filter by supported instance types if needed
                if bundle.get('supportedPlatforms'):
                    instance_types.append({
                        'id': bundle['bundleId'],
                        'name': bundle['name'],
                        'vcpu_count': bundle.get('cpuCount', 0),
                        'ram': bundle.get('ramSizeInGb', 0),
                        'disk': bundle.get('diskSizeInGb', 0),
                        'transfer': bundle.get('transferPerMonthInGb', 0),
                        'monthly_cost': bundle.get('price', 0),
                        'supported_platforms': bundle.get('supportedPlatforms', [])
                    })

            return instance_types

        except ClientError as e:
            self._handle_aws_error(e, "list bundles")
        except Exception as e:
            logger.error(f"Failed to list Lightsail bundles: {e}")
            return []

    def list_operating_systems(self) -> List[Dict[str, Any]]:
        """
        List available Lightsail blueprints (operating systems)

        Returns:
            List of OS/blueprint information
        """
        try:
            response = self.client.get_blueprints()
            operating_systems = []

            for blueprint in response.get('blueprints', []):
                operating_systems.append({
                    'id': blueprint['blueprintId'],
                    'name': blueprint['name'],
                    'description': blueprint.get('description', ''),
                    'type': blueprint.get('type', ''),
                    'platform': blueprint.get('platform', ''),
                    'version': blueprint.get('version', ''),
                    'min_power': blueprint.get('minPower', 0)
                })

            return operating_systems

        except ClientError as e:
            self._handle_aws_error(e, "list blueprints")
        except Exception as e:
            logger.error(f"Failed to list Lightsail blueprints: {e}")
            return []

    def create_key_pair(self, key_name: str) -> Dict[str, Any]:
        """
        Create a new key pair in Lightsail

        Args:
            key_name: Name for the key pair

        Returns:
            Key pair information including private key
        """
        try:
            response = self.client.create_key_pair(keyPairName=key_name)
            logger.info(f"Created Lightsail key pair: {key_name}")
            return response

        except ClientError as e:
            self._handle_aws_error(e, "key pair creation")
        except Exception as e:
            raise VPSOperationError(f"Failed to create key pair: {e}")

    def get_static_ip(self, static_ip_name: str) -> Dict[str, Any]:
        """
        Get information about a static IP

        Args:
            static_ip_name: Name of the static IP

        Returns:
            Static IP information
        """
        try:
            response = self.client.get_static_ip(staticIpName=static_ip_name)
            return response.get('staticIp', {})

        except ClientError as e:
            self._handle_aws_error(e, "get static IP")
        except Exception as e:
            logger.error(f"Failed to get static IP {static_ip_name}: {e}")
            return {}

    def attach_static_ip(self, static_ip_name: str, instance_id: str) -> bool:
        """
        Attach a static IP to an instance

        Args:
            static_ip_name: Name of the static IP
            instance_id: Name of the instance

        Returns:
            True if successful
        """
        try:
            self.client.attach_static_ip(
                staticIpName=static_ip_name,
                instanceName=instance_id
            )
            logger.info(f"Attached static IP {static_ip_name} to instance {instance_id}")
            return True

        except ClientError as e:
            self._handle_aws_error(e, "attach static IP")
        except Exception as e:
            logger.error(f"Failed to attach static IP: {e}")
            return False