"""
Factory for creating D0 Gateway API clients
"""

import threading
from typing import Any

from core.config import get_settings
from core.logging import get_logger

from .base import BaseAPIClient
from .providers.dataaxle import DataAxleClient
from .providers.google_places import GooglePlacesClient
from .providers.humanloop import HumanloopClient
from .providers.hunter import HunterClient
from .providers.openai import OpenAIClient
from .providers.pagespeed import PageSpeedClient
from .providers.screenshotone import ScreenshotOneClient
from .providers.semrush import SEMrushClient
from .providers.sendgrid import SendGridClient
from .providers.stripe import StripeClient


class GatewayClientFactory:
    """Thread-safe factory for creating API clients"""

    _instance = None
    _lock = threading.Lock()
    _initialized = False

    def __new__(cls):
        """Implement thread-safe singleton pattern"""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        """Initialize factory if not already initialized"""
        if not self._initialized:
            with self._lock:
                if not self._initialized:
                    self.logger = get_logger("gateway.factory", domain="d0")
                    self.settings = get_settings()

                    # Registry of available providers
                    self._providers: dict[str, type[BaseAPIClient]] = {
                        "pagespeed": PageSpeedClient,
                        "openai": OpenAIClient,
                        "humanloop": HumanloopClient,
                        "sendgrid": SendGridClient,
                        "stripe": StripeClient,
                        "dataaxle": DataAxleClient,
                        "hunter": HunterClient,
                        "semrush": SEMrushClient,
                        "screenshotone": ScreenshotOneClient,
                        "google_places": GooglePlacesClient,
                    }

                    # Cache for created instances
                    self._client_cache: dict[str, BaseAPIClient] = {}
                    self._cache_lock = threading.Lock()

                    self.__class__._initialized = True
                    self.logger.info("Gateway client factory initialized")

    def register_provider(self, provider_name: str, client_class: type[BaseAPIClient]) -> None:
        """
        Register a new provider with the factory

        Args:
            provider_name: Name of the provider
            client_class: Client class that inherits from BaseAPIClient
        """
        if not issubclass(client_class, BaseAPIClient):
            raise ValueError(f"Client class {client_class} must inherit from BaseAPIClient")

        with self._lock:
            self._providers[provider_name] = client_class
            self.logger.info(f"Registered provider: {provider_name}")

    def get_provider_names(self) -> list[str]:
        """Get list of registered provider names"""
        return list(self._providers.keys())

    def create_client(self, provider: str, use_cache: bool = True, **kwargs) -> BaseAPIClient:
        """
        Create or retrieve a client for the specified provider

        Args:
            provider: Provider name (pagespeed, openai, sendgrid, stripe)
            use_cache: Whether to use cached instances
            **kwargs: Additional configuration for the client

        Returns:
            API client instance

        Raises:
            ValueError: If provider is not registered
        """
        if provider not in self._providers:
            available = ", ".join(self._providers.keys())
            raise ValueError(f"Unknown provider '{provider}'. Available: {available}")

        # Check cache first if enabled
        if use_cache:
            with self._cache_lock:
                if provider in self._client_cache:
                    self.logger.debug(f"Returning cached client for {provider}")
                    return self._client_cache[provider]

        # Create new client instance
        try:
            client_class = self._providers[provider]

            # Get provider-specific configuration
            config = self._get_provider_config(provider)
            config.update(kwargs)  # Allow override with kwargs

            # Only pass api_key to client constructor
            # Other config is handled by BaseAPIClient
            client_kwargs = {"api_key": config.get("api_key")}

            # Special handling for ScreenshotOne which needs secret_key
            if provider == "screenshotone" and "api_secret" in config:
                client_kwargs["secret_key"] = config["api_secret"]

            client = client_class(**client_kwargs)

            # Cache the instance if caching is enabled
            if use_cache:
                with self._cache_lock:
                    self._client_cache[provider] = client

            self.logger.info(f"Created new client for {provider}")
            return client

        except Exception as e:
            self.logger.error(f"Failed to create client for {provider}: {e}")
            raise

    def _get_provider_config(self, provider: str) -> dict[str, Any]:
        """
        Get configuration for a specific provider

        Args:
            provider: Provider name

        Returns:
            Configuration dictionary
        """
        config = {}

        # Provider-specific configuration
        if provider == "pagespeed":
            config["api_key"] = getattr(self.settings, "pagespeed_api_key", None)

        elif provider == "openai":
            config["api_key"] = getattr(self.settings, "openai_api_key", None)

        elif provider == "sendgrid":
            config["api_key"] = getattr(self.settings, "sendgrid_api_key", None)

        elif provider == "stripe":
            config["api_key"] = getattr(self.settings, "stripe_secret_key", None)

        elif provider == "dataaxle":
            config["api_key"] = getattr(self.settings, "data_axle_api_key", None)

        elif provider == "hunter":
            config["api_key"] = getattr(self.settings, "hunter_api_key", None)
        elif provider == "semrush":
            config["api_key"] = getattr(self.settings, "semrush_api_key", None)
        elif provider == "screenshotone":
            config["api_key"] = getattr(self.settings, "screenshotone_key", None)
            config["api_secret"] = getattr(self.settings, "screenshotone_secret", None)
        elif provider == "google_places":
            config["api_key"] = getattr(self.settings, "google_api_key", None)
        elif provider == "humanloop":
            config["api_key"] = getattr(self.settings, "humanloop_api_key", None)

        # Common configuration
        config.update(
            {
                "timeout": getattr(self.settings, "api_timeout", 30),
                "max_retries": getattr(self.settings, "api_max_retries", 3),
                "debug": getattr(self.settings, "debug", False),
            }
        )

        return config

    def invalidate_cache(self, provider: str | None = None) -> None:
        """
        Invalidate cached client instances

        Args:
            provider: Specific provider to invalidate, or None for all
        """
        with self._cache_lock:
            if provider:
                if provider in self._client_cache:
                    del self._client_cache[provider]
                    self.logger.info(f"Invalidated cache for {provider}")
            else:
                self._client_cache.clear()
                self.logger.info("Invalidated all cached clients")

    def get_client_status(self) -> dict[str, Any]:
        """
        Get status of all registered providers and cached clients

        Returns:
            Status dictionary
        """
        with self._cache_lock:
            cached_providers = list(self._client_cache.keys())

        return {
            "registered_providers": list(self._providers.keys()),
            "cached_clients": cached_providers,
            "total_providers": len(self._providers),
            "cached_count": len(cached_providers),
            "factory_initialized": self._initialized,
        }

    def health_check(self) -> dict[str, Any]:
        """
        Perform health check on factory and providers

        Returns:
            Health check results
        """
        results = {
            "factory_healthy": True,
            "providers": {},
            "overall_status": "healthy",
        }

        # Check each provider
        for provider_name in self._providers:
            try:
                # Try to create a client (without caching for health check)
                self.create_client(provider_name, use_cache=False)

                # Basic connectivity check
                provider_status = {
                    "status": "healthy",
                    "client_created": True,
                    "error": None,
                }

                # Provider-specific health checks could be added here

            except Exception as e:
                provider_status = {
                    "status": "unhealthy",
                    "client_created": False,
                    "error": str(e),
                }
                results["overall_status"] = "degraded"

            results["providers"][provider_name] = provider_status

        return results


# Global factory instance
_factory_instance = None


def get_gateway_factory() -> GatewayClientFactory:
    """
    Get the global gateway factory instance

    Returns:
        GatewayClientFactory instance
    """
    global _factory_instance
    if _factory_instance is None:
        _factory_instance = GatewayClientFactory()
    return _factory_instance


def create_client(provider: str, **kwargs) -> BaseAPIClient:
    """
    Convenience function to create a client using the global factory

    Args:
        provider: Provider name
        **kwargs: Additional configuration

    Returns:
        API client instance
    """
    factory = get_gateway_factory()
    return factory.create_client(provider, **kwargs)


def register_provider(provider_name: str, client_class: type[BaseAPIClient]) -> None:
    """
    Convenience function to register a provider with the global factory

    Args:
        provider_name: Name of the provider
        client_class: Client class
    """
    factory = get_gateway_factory()
    factory.register_provider(provider_name, client_class)


def get_available_providers() -> list[str]:
    """
    Get list of available provider names

    Returns:
        List of provider names
    """
    factory = get_gateway_factory()
    return factory.get_provider_names()
