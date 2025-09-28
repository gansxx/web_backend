"""
Vultr VPS Provider Implementation

Vultr-specific implementation of the VPS provider interface.
"""

import json
import requests
from typing import Dict, List, Optional, Any
from loguru import logger

from .base import VPSProvider, VPSInstance, VPSConfig, VPSStatus
from .exceptions import VPSError, VPSConnectionError, VPSAuthError, VPSNotFoundError, VPSOperationError


class VultrProvider(VPSProvider):
    """Vultr VPS provider implementation"""

    BASE_URL = "https://api.vultr.com/v2"

    def __init__(self, credentials: Dict[str, str], region: Optional[str] = None):
        """
        Initialize Vultr provider

        Args:
            credentials: Dictionary containing 'api_key'
            region: Default region for operations
        """
        super().__init__(credentials, region)
        self.api_key = credentials.get('api_key')
        if not self.api_key:
            raise VPSAuthError("Vultr API key is required")

    @property
    def provider_name(self) -> str:
        """Return the name of the provider"""
        return "vultr"

    def _initialize_client(self) -> Dict[str, str]:
        """Initialize and return the HTTP headers for Vultr API"""
        return {
            'Authorization': f'Bearer {self.api_key}',
            'Content-Type': 'application/json',
        }

    def _make_request(self, method: str, endpoint: str, data: Optional[Dict] = None) -> Dict[str, Any]:
        """
        Make HTTP request to Vultr API

        Args:
            method: HTTP method (GET, POST, DELETE, etc.)
            endpoint: API endpoint
            data: Request payload

        Returns:
            Response data as dictionary

        Raises:
            VPSConnectionError: If request fails
            VPSAuthError: If authentication fails
        """
        url = f"{self.BASE_URL}/{endpoint.lstrip('/')}"
        headers = self.client

        try:
            if method.upper() == 'GET':
                response = requests.get(url, headers=headers, timeout=30)
            elif method.upper() == 'POST':
                response = requests.post(url, headers=headers, json=data, timeout=30)
            elif method.upper() == 'DELETE':
                response = requests.delete(url, headers=headers, timeout=30)
            elif method.upper() == 'PATCH':
                response = requests.patch(url, headers=headers, json=data, timeout=30)
            else:
                raise VPSError(f"Unsupported HTTP method: {method}")

            if response.status_code == 401:
                raise VPSAuthError("Invalid Vultr API key")
            elif response.status_code == 404:
                raise VPSNotFoundError("Resource not found")
            elif response.status_code >= 400:
                error_msg = f"Vultr API error {response.status_code}: {response.text}"
                raise VPSOperationError(error_msg)

            # Handle empty responses (like DELETE operations)
            if response.status_code == 204:
                return {}

            return response.json()

        except requests.RequestException as e:
            raise VPSConnectionError(f"Failed to connect to Vultr API: {e}")
        except json.JSONDecodeError as e:
            raise VPSError(f"Invalid JSON response from Vultr API: {e}")

    def _map_vultr_status(self, vultr_status: str) -> VPSStatus:
        """Map Vultr status to unified VPSStatus"""
        status_mapping = {
            'pending': VPSStatus.PENDING,
            'installing': VPSStatus.PENDING,
            'active': VPSStatus.RUNNING,
            'running': VPSStatus.RUNNING,
            'stopped': VPSStatus.STOPPED,
            'suspended': VPSStatus.STOPPED,
            'resizing': VPSStatus.REBOOTING,
        }
        return status_mapping.get(vultr_status.lower(), VPSStatus.UNKNOWN)

    def _vultr_instance_to_vps_instance(self, vultr_data: Dict[str, Any]) -> VPSInstance:
        """Convert Vultr instance data to VPSInstance"""
        return VPSInstance(
            id=vultr_data['id'],
            name=vultr_data.get('label', ''),
            status=self._map_vultr_status(vultr_data.get('status', 'unknown')),
            ip_address=vultr_data.get('main_ip'),
            private_ip=vultr_data.get('internal_ip'),
            region=vultr_data.get('region'),
            instance_type=vultr_data.get('plan'),
            os=vultr_data.get('os'),
            created_at=vultr_data.get('date_created'),
            provider_data=vultr_data
        )

    def create_instance(self, config: VPSConfig) -> str:
        """
        Create a new Vultr instance

        Args:
            config: VPS configuration

        Returns:
            Instance ID
        """
        data = {
            'region': config.region,
            'plan': config.instance_type,
            'label': config.name,
            'os_id': int(config.os_id),
            'backups': 'enabled' if config.backup_enabled else 'disabled',
        }

        # Add optional parameters
        if config.user_data:
            data['user_data'] = config.user_data

        if config.script_id:
            data['script_id'] = config.script_id

        if config.ssh_key_id:
            if isinstance(config.ssh_key_id, list):
                data['sshkey_id'] = config.ssh_key_id
            else:
                data['sshkey_id'] = [config.ssh_key_id]

        if config.tags:
            data['tag'] = list(config.tags.keys())[0] if config.tags else ''

        try:
            response = self._make_request('POST', '/instances', data)
            instance_id = response['instance']['id']
            logger.info(f"Created Vultr instance: {instance_id}")
            return instance_id

        except KeyError as e:
            raise VPSError(f"Unexpected response format from Vultr API: {e}")

    def delete_instance(self, instance_id: str) -> bool:
        """
        Delete a Vultr instance

        Args:
            instance_id: ID of the instance to delete

        Returns:
            True if successful
        """
        try:
            self._make_request('DELETE', f'/instances/{instance_id}')
            logger.info(f"Deleted Vultr instance: {instance_id}")
            return True

        except VPSNotFoundError:
            logger.warning(f"Instance {instance_id} not found for deletion")
            return False

    def reboot_instance(self, instance_id: str) -> bool:
        """
        Reboot a Vultr instance

        Args:
            instance_id: ID of the instance to reboot

        Returns:
            True if successful
        """
        try:
            data = {'instance_ids': [instance_id]}
            self._make_request('POST', '/instances/reboot', data)
            logger.info(f"Rebooted Vultr instance: {instance_id}")
            return True

        except VPSNotFoundError:
            logger.warning(f"Instance {instance_id} not found for reboot")
            return False

    def start_instance(self, instance_id: str) -> bool:
        """
        Start a Vultr instance

        Args:
            instance_id: ID of the instance to start

        Returns:
            True if successful
        """
        try:
            data = {'instance_ids': [instance_id]}
            self._make_request('POST', '/instances/start', data)
            logger.info(f"Started Vultr instance: {instance_id}")
            return True

        except VPSNotFoundError:
            logger.warning(f"Instance {instance_id} not found for start")
            return False

    def stop_instance(self, instance_id: str) -> bool:
        """
        Stop a Vultr instance

        Args:
            instance_id: ID of the instance to stop

        Returns:
            True if successful
        """
        try:
            data = {'instance_ids': [instance_id]}
            self._make_request('POST', '/instances/halt', data)
            logger.info(f"Stopped Vultr instance: {instance_id}")
            return True

        except VPSNotFoundError:
            logger.warning(f"Instance {instance_id} not found for stop")
            return False

    def get_instance(self, instance_id: str) -> Optional[VPSInstance]:
        """
        Get information about a specific Vultr instance

        Args:
            instance_id: ID of the instance

        Returns:
            VPSInstance object or None if not found
        """
        try:
            response = self._make_request('GET', f'/instances/{instance_id}')
            return self._vultr_instance_to_vps_instance(response['instance'])

        except VPSNotFoundError:
            logger.warning(f"Instance {instance_id} not found")
            return None

    def list_instances(self) -> List[VPSInstance]:
        """
        List all Vultr instances

        Returns:
            List of VPSInstance objects
        """
        try:
            response = self._make_request('GET', '/instances')
            instances = []

            for instance_data in response.get('instances', []):
                instances.append(self._vultr_instance_to_vps_instance(instance_data))

            return instances

        except Exception as e:
            logger.error(f"Failed to list Vultr instances: {e}")
            return []

    def get_instance_ip(self, instance_id: str) -> Optional[str]:
        """
        Get the public IP address of a Vultr instance

        Args:
            instance_id: ID of the instance

        Returns:
            IP address or None if not available
        """
        try:
            response = self._make_request('GET', f'/instances/{instance_id}/ipv4')
            ipv4s = response.get('ipv4s', [])

            if ipv4s:
                return ipv4s[0]['ip']

            return None

        except VPSNotFoundError:
            logger.warning(f"Instance {instance_id} not found")
            return None

    def list_regions(self) -> List[Dict[str, str]]:
        """
        List available Vultr regions

        Returns:
            List of region information
        """
        try:
            response = self._make_request('GET', '/regions')
            regions = []

            for region_data in response.get('regions', []):
                regions.append({
                    'id': region_data['id'],
                    'name': region_data.get('city', ''),
                    'country': region_data.get('country', ''),
                    'continent': region_data.get('continent', ''),
                    'available': region_data.get('options', [])
                })

            return regions

        except Exception as e:
            logger.error(f"Failed to list Vultr regions: {e}")
            return []

    def list_instance_types(self, region: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        List available Vultr plans/instance types

        Args:
            region: Region to get plans for (optional)

        Returns:
            List of instance type information
        """
        try:
            response = self._make_request('GET', '/plans')
            plans = []

            for plan_data in response.get('plans', []):
                # Filter by region if specified
                if region and region not in plan_data.get('locations', []):
                    continue

                plans.append({
                    'id': plan_data['id'],
                    'name': plan_data.get('type', ''),
                    'vcpu_count': plan_data.get('vcpu_count', 0),
                    'ram': plan_data.get('ram', 0),
                    'disk': plan_data.get('disk', 0),
                    'bandwidth': plan_data.get('bandwidth', 0),
                    'monthly_cost': plan_data.get('monthly_cost', 0),
                    'locations': plan_data.get('locations', [])
                })

            return plans

        except Exception as e:
            logger.error(f"Failed to list Vultr plans: {e}")
            return []

    def list_operating_systems(self) -> List[Dict[str, Any]]:
        """
        List available operating systems

        Returns:
            List of OS information
        """
        try:
            response = self._make_request('GET', '/os')
            operating_systems = []

            for os_data in response.get('os', []):
                operating_systems.append({
                    'id': os_data['id'],
                    'name': os_data.get('name', ''),
                    'arch': os_data.get('arch', ''),
                    'family': os_data.get('family', '')
                })

            return operating_systems

        except Exception as e:
            logger.error(f"Failed to list Vultr operating systems: {e}")
            return []


# Legacy compatibility functions for existing code
def create_new_instance(region: str, plan: str, label: str, os_id: int, **kwargs) -> str:
    """
    Legacy function for creating Vultr instances

    Args:
        region: Vultr region
        plan: Vultr plan ID
        label: Instance label
        os_id: Operating system ID
        **kwargs: Additional parameters

    Returns:
        Instance ID
    """
    from .config import get_provider_credentials

    try:
        credentials = get_provider_credentials('vultr')
        provider = VultrProvider(credentials.credentials, region)

        config = VPSConfig(
            region=region,
            instance_type=plan,
            name=label,
            os_id=os_id,
            **kwargs
        )

        return provider.create_instance(config)

    except Exception as e:
        logger.error(f"Legacy create_new_instance failed: {e}")
        raise


def get_instance_ip(instance_id: str) -> Optional[str]:
    """
    Legacy function for getting instance IP

    Args:
        instance_id: Instance ID

    Returns:
        IP address or None
    """
    from .config import get_provider_credentials

    try:
        credentials = get_provider_credentials('vultr')
        provider = VultrProvider(credentials.credentials)
        return provider.get_instance_ip(instance_id)

    except Exception as e:
        logger.error(f"Legacy get_instance_ip failed: {e}")
        return None


def delete_instance(instance_id: str) -> bool:
    """
    Legacy function for deleting instances

    Args:
        instance_id: Instance ID

    Returns:
        True if successful
    """
    from .config import get_provider_credentials

    try:
        credentials = get_provider_credentials('vultr')
        provider = VultrProvider(credentials.credentials)
        return provider.delete_instance(instance_id)

    except Exception as e:
        logger.error(f"Legacy delete_instance failed: {e}")
        return False