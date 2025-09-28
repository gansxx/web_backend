"""
Factory Pattern for VPS Provider Selection

Provides a unified interface for creating and managing VPS provider instances.
"""

from typing import Dict, Type, Optional, Any
from .base import VPSProvider
from .config import get_provider_credentials, ProviderCredentials
from .exceptions import VPSConfigError


class VPSFactory:
    """
    Factory class for creating VPS provider instances
    """

    _providers: Dict[str, Type[VPSProvider]] = {}

    @classmethod
    def register_provider(cls, name: str, provider_class: Type[VPSProvider]) -> None:
        """
        Register a VPS provider class

        Args:
            name: Provider name (e.g., 'vultr', 'aws_ec2', 'aws_lightsail')
            provider_class: Provider class that inherits from VPSProvider
        """
        if not issubclass(provider_class, VPSProvider):
            raise VPSConfigError(f"Provider class must inherit from VPSProvider: {provider_class}")

        cls._providers[name.lower()] = provider_class

    @classmethod
    def create_provider(cls, provider_name: str, credentials: Optional[ProviderCredentials] = None,
                       region: Optional[str] = None, **kwargs) -> VPSProvider:
        """
        Create a VPS provider instance

        Args:
            provider_name: Name of the provider
            credentials: Provider credentials (will be auto-loaded if not provided)
            region: Default region for operations
            **kwargs: Additional provider-specific arguments

        Returns:
            VPSProvider instance

        Raises:
            VPSConfigError: If provider is not supported or credentials are invalid
        """
        provider_name = provider_name.lower()

        if provider_name not in cls._providers:
            available = ', '.join(cls._providers.keys())
            raise VPSConfigError(f"Unsupported provider: {provider_name}. Available: {available}")

        # Auto-load credentials if not provided
        if credentials is None:
            credentials = get_provider_credentials(provider_name)

        # Validate credentials
        credentials.validate()

        # Use region from credentials if not specified
        if region is None:
            region = credentials.region

        # Create provider instance
        provider_class = cls._providers[provider_name]
        provider = provider_class(
            credentials=credentials.credentials,
            region=region,
            **kwargs
        )

        return provider

    @classmethod
    def get_supported_providers(cls) -> list:
        """
        Get list of supported provider names

        Returns:
            List of supported provider names
        """
        return list(cls._providers.keys())

    @classmethod
    def is_provider_supported(cls, provider_name: str) -> bool:
        """
        Check if a provider is supported

        Args:
            provider_name: Name of the provider

        Returns:
            True if supported, False otherwise
        """
        return provider_name.lower() in cls._providers


def get_provider(provider_name: str, credentials: Optional[ProviderCredentials] = None,
                region: Optional[str] = None, **kwargs) -> VPSProvider:
    """
    Convenience function to create a VPS provider instance

    Args:
        provider_name: Name of the provider
        credentials: Provider credentials (will be auto-loaded if not provided)
        region: Default region for operations
        **kwargs: Additional provider-specific arguments

    Returns:
        VPSProvider instance
    """
    return VPSFactory.create_provider(provider_name, credentials, region, **kwargs)


def list_providers() -> list:
    """
    Get list of supported providers

    Returns:
        List of supported provider names
    """
    return VPSFactory.get_supported_providers()


# Auto-register providers when they're imported
def _auto_register_providers():
    """Auto-register available provider implementations"""
    try:
        from .vultr import VultrProvider
        VPSFactory.register_provider('vultr', VultrProvider)
    except ImportError:
        pass

    try:
        from .aws_ec2 import AWSEC2Provider
        VPSFactory.register_provider('aws_ec2', AWSEC2Provider)
    except ImportError:
        pass

    try:
        from .aws_lightsail import AWSLightsailProvider
        VPSFactory.register_provider('aws_lightsail', AWSLightsailProvider)
    except ImportError:
        pass


# Initialize providers on module import
_auto_register_providers()


# Backward compatibility function
def create_vps_manager(provider_name: str, **kwargs) -> VPSProvider:
    """
    Create a VPS manager instance (legacy function name)

    Args:
        provider_name: Name of the provider
        **kwargs: Additional arguments

    Returns:
        VPSProvider instance
    """
    return get_provider(provider_name, **kwargs)