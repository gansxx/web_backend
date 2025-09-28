"""
AWS EC2 VPS Provider Implementation

AWS EC2-specific implementation of the VPS provider interface.
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


class AWSEC2Provider(VPSProvider):
    """AWS EC2 VPS provider implementation"""

    def __init__(self, credentials: Dict[str, str], region: Optional[str] = None):
        """
        Initialize AWS EC2 provider

        Args:
            credentials: Dictionary containing AWS credentials
            region: Default region for operations
        """
        if not BOTO3_AVAILABLE:
            raise VPSError("boto3 is required for AWS EC2 provider. Install with: pip install boto3")

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
        return "aws_ec2"

    def _initialize_client(self):
        """Initialize and return the AWS EC2 client"""
        try:
            session_kwargs = {
                'aws_access_key_id': self.access_key_id,
                'aws_secret_access_key': self.secret_access_key,
                'region_name': self.region
            }

            if self.session_token:
                session_kwargs['aws_session_token'] = self.session_token

            session = boto3.Session(**session_kwargs)
            return session.client('ec2')

        except (NoCredentialsError, PartialCredentialsError) as e:
            raise VPSAuthError(f"Invalid AWS credentials: {e}")
        except Exception as e:
            raise VPSConnectionError(f"Failed to initialize AWS EC2 client: {e}")

    def _handle_aws_error(self, error: ClientError, operation: str = "operation"):
        """Handle AWS ClientError and convert to appropriate VPS exception"""
        error_code = error.response.get('Error', {}).get('Code', 'Unknown')
        error_message = error.response.get('Error', {}).get('Message', str(error))

        if error_code in ['InvalidInstanceID.NotFound', 'InvalidInstance.NotFound']:
            raise VPSNotFoundError(f"Instance not found: {error_message}")
        elif error_code in ['UnauthorizedOperation', 'InvalidUserID.NotFound']:
            raise VPSAuthError(f"Access denied: {error_message}")
        elif error_code in ['InvalidParameterValue', 'InvalidParameter']:
            raise VPSError(f"Invalid parameter: {error_message}")
        else:
            raise VPSOperationError(f"AWS {operation} failed ({error_code}): {error_message}")

    def _map_ec2_state(self, ec2_state: str) -> VPSStatus:
        """Map EC2 instance state to unified VPSStatus"""
        state_mapping = {
            'pending': VPSStatus.PENDING,
            'running': VPSStatus.RUNNING,
            'shutting-down': VPSStatus.STOPPING,
            'terminated': VPSStatus.STOPPED,
            'stopping': VPSStatus.STOPPING,
            'stopped': VPSStatus.STOPPED,
            'rebooting': VPSStatus.REBOOTING,
        }
        return state_mapping.get(ec2_state.lower(), VPSStatus.UNKNOWN)

    def _ec2_instance_to_vps_instance(self, ec2_instance: Dict[str, Any]) -> VPSInstance:
        """Convert EC2 instance data to VPSInstance"""
        # Extract name from tags
        name = ''
        if 'Tags' in ec2_instance:
            for tag in ec2_instance['Tags']:
                if tag.get('Key') == 'Name':
                    name = tag.get('Value', '')
                    break

        return VPSInstance(
            id=ec2_instance['InstanceId'],
            name=name,
            status=self._map_ec2_state(ec2_instance['State']['Name']),
            ip_address=ec2_instance.get('PublicIpAddress'),
            private_ip=ec2_instance.get('PrivateIpAddress'),
            region=ec2_instance.get('Placement', {}).get('AvailabilityZone', '')[:-1],  # Remove zone letter
            instance_type=ec2_instance.get('InstanceType'),
            os=self._get_os_from_image_id(ec2_instance.get('ImageId')),
            created_at=ec2_instance.get('LaunchTime', '').isoformat() if ec2_instance.get('LaunchTime') else None,
            provider_data=ec2_instance
        )

    def _get_os_from_image_id(self, image_id: Optional[str]) -> Optional[str]:
        """Get OS information from AMI image ID"""
        if not image_id:
            return None

        try:
            response = self.client.describe_images(ImageIds=[image_id])
            if response['Images']:
                image = response['Images'][0]
                return image.get('Description', image.get('Name', 'Unknown'))
        except ClientError:
            pass

        return f"AMI: {image_id}"

    def create_instance(self, config: VPSConfig) -> str:
        """
        Create a new EC2 instance

        Args:
            config: VPS configuration

        Returns:
            Instance ID
        """
        try:
            # Prepare launch parameters
            launch_params = {
                'ImageId': str(config.os_id),  # AMI ID
                'InstanceType': config.instance_type,
                'MinCount': 1,
                'MaxCount': 1,
            }

            # Add key pair if specified
            if config.ssh_key_id:
                key_name = config.ssh_key_id
                if isinstance(config.ssh_key_id, list):
                    key_name = config.ssh_key_id[0]
                launch_params['KeyName'] = key_name

            # Add security groups if specified
            if config.security_groups:
                if config.subnet_id:
                    # For VPC instances, use SecurityGroupIds
                    launch_params['SecurityGroupIds'] = config.security_groups
                else:
                    # For EC2-Classic, use SecurityGroups
                    launch_params['SecurityGroups'] = config.security_groups

            # Add subnet if specified
            if config.subnet_id:
                launch_params['SubnetId'] = config.subnet_id

            # Add user data if specified
            if config.user_data:
                launch_params['UserData'] = config.user_data

            # Add monitoring if enabled
            if config.monitoring_enabled:
                launch_params['Monitoring'] = {'Enabled': True}

            # Create instance
            response = self.client.run_instances(**launch_params)
            instance_id = response['Instances'][0]['InstanceId']

            # Add tags including name
            tags = [{'Key': 'Name', 'Value': config.name}]
            if config.tags:
                for key, value in config.tags.items():
                    if key.lower() != 'name':  # Avoid duplicate Name tag
                        tags.append({'Key': key, 'Value': value})

            if tags:
                self.client.create_tags(Resources=[instance_id], Tags=tags)

            logger.info(f"Created EC2 instance: {instance_id}")
            return instance_id

        except ClientError as e:
            self._handle_aws_error(e, "instance creation")
        except Exception as e:
            raise VPSOperationError(f"Failed to create EC2 instance: {e}")

    def delete_instance(self, instance_id: str) -> bool:
        """
        Terminate an EC2 instance

        Args:
            instance_id: ID of the instance to terminate

        Returns:
            True if successful
        """
        try:
            self.client.terminate_instances(InstanceIds=[instance_id])
            logger.info(f"Terminated EC2 instance: {instance_id}")
            return True

        except ClientError as e:
            if 'InvalidInstanceID.NotFound' in str(e):
                logger.warning(f"Instance {instance_id} not found for termination")
                return False
            self._handle_aws_error(e, "instance termination")
        except Exception as e:
            logger.error(f"Failed to terminate EC2 instance {instance_id}: {e}")
            return False

    def reboot_instance(self, instance_id: str) -> bool:
        """
        Reboot an EC2 instance

        Args:
            instance_id: ID of the instance to reboot

        Returns:
            True if successful
        """
        try:
            self.client.reboot_instances(InstanceIds=[instance_id])
            logger.info(f"Rebooted EC2 instance: {instance_id}")
            return True

        except ClientError as e:
            if 'InvalidInstanceID.NotFound' in str(e):
                logger.warning(f"Instance {instance_id} not found for reboot")
                return False
            self._handle_aws_error(e, "instance reboot")
        except Exception as e:
            logger.error(f"Failed to reboot EC2 instance {instance_id}: {e}")
            return False

    def start_instance(self, instance_id: str) -> bool:
        """
        Start an EC2 instance

        Args:
            instance_id: ID of the instance to start

        Returns:
            True if successful
        """
        try:
            self.client.start_instances(InstanceIds=[instance_id])
            logger.info(f"Started EC2 instance: {instance_id}")
            return True

        except ClientError as e:
            if 'InvalidInstanceID.NotFound' in str(e):
                logger.warning(f"Instance {instance_id} not found for start")
                return False
            self._handle_aws_error(e, "instance start")
        except Exception as e:
            logger.error(f"Failed to start EC2 instance {instance_id}: {e}")
            return False

    def stop_instance(self, instance_id: str) -> bool:
        """
        Stop an EC2 instance

        Args:
            instance_id: ID of the instance to stop

        Returns:
            True if successful
        """
        try:
            self.client.stop_instances(InstanceIds=[instance_id])
            logger.info(f"Stopped EC2 instance: {instance_id}")
            return True

        except ClientError as e:
            if 'InvalidInstanceID.NotFound' in str(e):
                logger.warning(f"Instance {instance_id} not found for stop")
                return False
            self._handle_aws_error(e, "instance stop")
        except Exception as e:
            logger.error(f"Failed to stop EC2 instance {instance_id}: {e}")
            return False

    def get_instance(self, instance_id: str) -> Optional[VPSInstance]:
        """
        Get information about a specific EC2 instance

        Args:
            instance_id: ID of the instance

        Returns:
            VPSInstance object or None if not found
        """
        try:
            response = self.client.describe_instances(InstanceIds=[instance_id])

            for reservation in response['Reservations']:
                for instance in reservation['Instances']:
                    if instance['InstanceId'] == instance_id:
                        return self._ec2_instance_to_vps_instance(instance)

            return None

        except ClientError as e:
            if 'InvalidInstanceID.NotFound' in str(e):
                logger.warning(f"Instance {instance_id} not found")
                return None
            self._handle_aws_error(e, "get instance")
        except Exception as e:
            logger.error(f"Failed to get EC2 instance {instance_id}: {e}")
            return None

    def list_instances(self) -> List[VPSInstance]:
        """
        List all EC2 instances

        Returns:
            List of VPSInstance objects
        """
        try:
            response = self.client.describe_instances()
            instances = []

            for reservation in response['Reservations']:
                for instance in reservation['Instances']:
                    # Skip terminated instances
                    if instance['State']['Name'] != 'terminated':
                        instances.append(self._ec2_instance_to_vps_instance(instance))

            return instances

        except ClientError as e:
            self._handle_aws_error(e, "list instances")
        except Exception as e:
            logger.error(f"Failed to list EC2 instances: {e}")
            return []

    def get_instance_ip(self, instance_id: str) -> Optional[str]:
        """
        Get the public IP address of an EC2 instance

        Args:
            instance_id: ID of the instance

        Returns:
            IP address or None if not available
        """
        instance = self.get_instance(instance_id)
        return instance.ip_address if instance else None

    def list_regions(self) -> List[Dict[str, str]]:
        """
        List available AWS regions

        Returns:
            List of region information
        """
        try:
            response = self.client.describe_regions()
            regions = []

            for region in response['Regions']:
                regions.append({
                    'id': region['RegionName'],
                    'name': region['RegionName'],
                    'endpoint': region['Endpoint'],
                    'available': True
                })

            return regions

        except ClientError as e:
            self._handle_aws_error(e, "list regions")
        except Exception as e:
            logger.error(f"Failed to list AWS regions: {e}")
            return []

    def list_instance_types(self, region: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        List available EC2 instance types

        Args:
            region: Region to get instance types for (optional)

        Returns:
            List of instance type information
        """
        try:
            # Use different client for different region if specified
            client = self.client
            if region and region != self.region:
                session_kwargs = {
                    'aws_access_key_id': self.access_key_id,
                    'aws_secret_access_key': self.secret_access_key,
                    'region_name': region
                }
                if self.session_token:
                    session_kwargs['aws_session_token'] = self.session_token
                session = boto3.Session(**session_kwargs)
                client = session.client('ec2')

            response = client.describe_instance_types()
            instance_types = []

            for instance_type in response['InstanceTypes']:
                instance_types.append({
                    'id': instance_type['InstanceType'],
                    'name': instance_type['InstanceType'],
                    'vcpu_count': instance_type.get('VCpuInfo', {}).get('DefaultVCpus', 0),
                    'ram': instance_type.get('MemoryInfo', {}).get('SizeInMiB', 0),
                    'network_performance': instance_type.get('NetworkInfo', {}).get('NetworkPerformance', ''),
                    'supported_architectures': instance_type.get('ProcessorInfo', {}).get('SupportedArchitectures', [])
                })

            return instance_types

        except ClientError as e:
            self._handle_aws_error(e, "list instance types")
        except Exception as e:
            logger.error(f"Failed to list EC2 instance types: {e}")
            return []

    def list_operating_systems(self) -> List[Dict[str, Any]]:
        """
        List available AMIs (operating systems)

        Returns:
            List of OS/AMI information
        """
        try:
            # Get popular AMIs from Amazon
            response = self.client.describe_images(
                Owners=['amazon'],
                Filters=[
                    {'Name': 'state', 'Values': ['available']},
                    {'Name': 'root-device-type', 'Values': ['ebs']},
                ]
            )

            operating_systems = []

            # Limit to a reasonable number of recent AMIs
            images = sorted(response['Images'], key=lambda x: x.get('CreationDate', ''), reverse=True)[:50]

            for image in images:
                operating_systems.append({
                    'id': image['ImageId'],
                    'name': image.get('Name', ''),
                    'description': image.get('Description', ''),
                    'architecture': image.get('Architecture', ''),
                    'creation_date': image.get('CreationDate', ''),
                    'owner': image.get('OwnerId', '')
                })

            return operating_systems

        except ClientError as e:
            self._handle_aws_error(e, "list operating systems")
        except Exception as e:
            logger.error(f"Failed to list AMIs: {e}")
            return []