"""
Unified Configuration System for VPS Management

Handles configuration loading and provider-specific parameter mapping.
"""

import os
import json
import configparser
from pathlib import Path
from typing import Dict, Any, Optional, Union
from dataclasses import dataclass, field

from .exceptions import VPSConfigError
from .base import VPSConfig


@dataclass
class ProviderCredentials:
    """Container for provider-specific credentials"""
    provider: str
    credentials: Dict[str, str] = field(default_factory=dict)
    region: Optional[str] = None

    def get_credential(self, key: str, default: Optional[str] = None) -> Optional[str]:
        """Get a credential value with optional default"""
        return self.credentials.get(key, default)

    def validate(self) -> bool:
        """Validate that required credentials are present"""
        required_keys = self._get_required_keys()
        missing_keys = [key for key in required_keys if key not in self.credentials]
        if missing_keys:
            raise VPSConfigError(f"Missing required credentials for {self.provider}: {missing_keys}")
        return True

    def _get_required_keys(self) -> list:
        """Get list of required credential keys for the provider"""
        provider_requirements = {
            'vultr': ['api_key'],
            'aws_ec2': ['access_key_id', 'secret_access_key'],
            'aws_lightsail': ['access_key_id', 'secret_access_key']
        }
        return provider_requirements.get(self.provider, [])


class ConfigManager:
    """
    Unified configuration manager supporting multiple formats and providers
    """

    def __init__(self, config_dir: Optional[Union[str, Path]] = None):
        """
        Initialize configuration manager

        Args:
            config_dir: Directory containing configuration files
        """
        if config_dir is None:
            config_dir = Path(__file__).parent.parent
        self.config_dir = Path(config_dir)
        self._provider_configs = {}
        self._credentials = {}

    def load_credentials_from_env(self, provider: str) -> ProviderCredentials:
        """
        Load credentials from environment variables

        Args:
            provider: Provider name (vultr, aws_ec2, aws_lightsail)

        Returns:
            ProviderCredentials object
        """
        creds = ProviderCredentials(provider=provider)

        if provider == 'vultr':
            creds.credentials = {
                'api_key': os.getenv('VULTR_API_KEY', '')
            }
        elif provider in ['aws_ec2', 'aws_lightsail']:
            creds.credentials = {
                'access_key_id': os.getenv('AWS_ACCESS_KEY_ID', ''),
                'secret_access_key': os.getenv('AWS_SECRET_ACCESS_KEY', ''),
                'session_token': os.getenv('AWS_SESSION_TOKEN', '')  # Optional
            }
            creds.region = os.getenv('AWS_DEFAULT_REGION')

        # Remove empty credentials
        creds.credentials = {k: v for k, v in creds.credentials.items() if v}

        return creds

    def load_credentials_from_file(self, provider: str, file_path: Optional[Union[str, Path]] = None) -> ProviderCredentials:
        """
        Load credentials from configuration file

        Args:
            provider: Provider name
            file_path: Path to credentials file (optional)

        Returns:
            ProviderCredentials object
        """
        if file_path is None:
            file_path = self.config_dir / f"{provider}_credentials.json"

        file_path = Path(file_path)

        if not file_path.exists():
            raise VPSConfigError(f"Credentials file not found: {file_path}")

        try:
            with open(file_path, 'r') as f:
                data = json.load(f)

            creds = ProviderCredentials(
                provider=provider,
                credentials=data.get('credentials', {}),
                region=data.get('region')
            )

            return creds

        except (json.JSONDecodeError, KeyError) as e:
            raise VPSConfigError(f"Invalid credentials file format: {e}")

    def get_credentials(self, provider: str, prefer_env: bool = True) -> ProviderCredentials:
        """
        Get credentials for a provider, trying multiple sources

        Args:
            provider: Provider name
            prefer_env: Whether to prefer environment variables over files

        Returns:
            ProviderCredentials object
        """
        if provider in self._credentials:
            return self._credentials[provider]

        creds = None

        if prefer_env:
            # Try environment first
            try:
                creds = self.load_credentials_from_env(provider)
                creds.validate()
            except VPSConfigError:
                # Fall back to file
                try:
                    creds = self.load_credentials_from_file(provider)
                    creds.validate()
                except VPSConfigError:
                    pass
        else:
            # Try file first
            try:
                creds = self.load_credentials_from_file(provider)
                creds.validate()
            except VPSConfigError:
                # Fall back to environment
                try:
                    creds = self.load_credentials_from_env(provider)
                    creds.validate()
                except VPSConfigError:
                    pass

        if creds is None:
            raise VPSConfigError(f"No valid credentials found for provider: {provider}")

        self._credentials[provider] = creds
        return creds

    def load_instance_config(self, provider: str, config_file: Optional[Union[str, Path]] = None) -> VPSConfig:
        """
        Load instance configuration from file

        Args:
            provider: Provider name
            config_file: Path to configuration file (optional)

        Returns:
            VPSConfig object
        """
        if config_file is None:
            # Try multiple common config file names
            possible_files = [
                self.config_dir / f"{provider}_config.json",
                self.config_dir / f"{provider}_config.ini",
                self.config_dir / "server_detail.ini",  # Legacy support
                self.config_dir / "vps_config.json"
            ]

            config_file = None
            for file_path in possible_files:
                if file_path.exists():
                    config_file = file_path
                    break

            if config_file is None:
                raise VPSConfigError("No configuration file found")

        config_file = Path(config_file)

        if config_file.suffix.lower() == '.json':
            return self._load_json_config(config_file, provider)
        elif config_file.suffix.lower() == '.ini':
            return self._load_ini_config(config_file, provider)
        else:
            raise VPSConfigError(f"Unsupported config file format: {config_file.suffix}")

    def _load_json_config(self, file_path: Path, provider: str) -> VPSConfig:
        """Load configuration from JSON file"""
        try:
            with open(file_path, 'r') as f:
                data = json.load(f)

            # Handle provider-specific section
            config_data = data.get(provider, data)

            return VPSConfig(**config_data)

        except (json.JSONDecodeError, TypeError, KeyError) as e:
            raise VPSConfigError(f"Invalid JSON config format: {e}")

    def _load_ini_config(self, file_path: Path, provider: str) -> VPSConfig:
        """Load configuration from INI file"""
        try:
            config = configparser.ConfigParser()
            config.read(file_path)

            # Try provider-specific section first, then default section
            section_name = provider if provider in config.sections() else 'server_detail'
            if section_name not in config.sections():
                section_name = config.sections()[0] if config.sections() else 'DEFAULT'

            section = config[section_name]

            # Map INI keys to VPSConfig fields
            config_data = self._map_ini_to_config(section, provider)

            return VPSConfig(**config_data)

        except (configparser.Error, KeyError, TypeError) as e:
            raise VPSConfigError(f"Invalid INI config format: {e}")

    def _map_ini_to_config(self, section: configparser.SectionProxy, provider: str) -> Dict[str, Any]:
        """Map INI section data to VPSConfig fields"""
        mapping = {
            'region': 'region',
            'plan': 'instance_type',
            'label': 'name',
            'os_id': 'os_id'
        }

        config_data = {}

        for ini_key, config_key in mapping.items():
            if ini_key in section:
                value = section[ini_key]
                # Convert os_id to int if needed
                if config_key == 'os_id' and value.isdigit():
                    value = int(value)
                config_data[config_key] = value

        # Add any additional keys not in the mapping
        for key, value in section.items():
            if key not in mapping:
                config_data[key] = value

        return config_data

    def save_config(self, provider: str, config: VPSConfig, file_path: Optional[Union[str, Path]] = None) -> None:
        """
        Save configuration to file

        Args:
            provider: Provider name
            config: VPSConfig object to save
            file_path: Path to save file (optional)
        """
        if file_path is None:
            file_path = self.config_dir / f"{provider}_config.json"

        file_path = Path(file_path)
        file_path.parent.mkdir(parents=True, exist_ok=True)

        with open(file_path, 'w') as f:
            json.dump({provider: config.to_dict()}, f, indent=2)


# Global config manager instance
config_manager = ConfigManager()


def get_provider_credentials(provider: str) -> ProviderCredentials:
    """Get credentials for a provider"""
    return config_manager.get_credentials(provider)


def get_instance_config(provider: str, config_file: Optional[Union[str, Path]] = None) -> VPSConfig:
    """Get instance configuration for a provider"""
    return config_manager.load_instance_config(provider, config_file)