"""
Service Discovery Framework for P3-006 Mock Integration Replacement

Intelligent routing system that automatically switches between mock and production APIs
based on configuration, availability, and validation status.
"""
import asyncio
import os
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple, Union

import aiohttp
from pydantic import BaseModel, Field

from core.config import get_settings
from core.logging import get_logger
from core.production_config import production_config_service

logger = get_logger(__name__)


class ServiceStatus(str, Enum):
    """Service availability status"""

    MOCK = "mock"
    PRODUCTION = "production"
    HYBRID = "hybrid"
    OFFLINE = "offline"


class ServiceEndpoint(BaseModel):
    """Configuration for service endpoint"""

    name: str
    mock_url: str
    production_url: str
    health_check_path: str = "/health"
    timeout_seconds: int = 5
    required_env_vars: List[str] = Field(default_factory=list)
    api_key_header: Optional[str] = None


class ServiceDiscoveryConfig(BaseModel):
    """Service discovery configuration"""

    prefer_production: bool = False
    enable_fallback: bool = True
    health_check_interval: int = 60
    max_retries: int = 3
    endpoints: Dict[str, ServiceEndpoint] = Field(default_factory=dict)


class ServiceRouter:
    """
    Intelligent service router that manages mock/production API switching

    Features:
    - Automatic service discovery and health checking
    - Intelligent fallback from production to mock services
    - API key validation and availability checking
    - Configuration-driven routing decisions
    """

    def __init__(self, config: Optional[ServiceDiscoveryConfig] = None):
        self.settings = get_settings()
        self.config = config or self._get_default_config()
        self.service_status: Dict[str, ServiceStatus] = {}
        self.last_health_check: Dict[str, float] = {}
        self._session: Optional[aiohttp.ClientSession] = None

    def _get_default_config(self) -> ServiceDiscoveryConfig:
        """Get default service discovery configuration"""

        # Base URLs
        stub_base = self.settings.stub_base_url

        endpoints = {
            "google_places": ServiceEndpoint(
                name="Google Places API",
                mock_url=f"{stub_base}/maps/api/place",
                production_url="https://maps.googleapis.com/maps/api/place",
                health_check_path="/findplacefromtext/json?input=test&inputtype=textquery&key=test",
                required_env_vars=["GOOGLE_API_KEY"],
                api_key_header="key",
            ),
            "pagespeed": ServiceEndpoint(
                name="PageSpeed Insights API",
                mock_url=f"{stub_base}/pagespeedonline/v5",
                production_url="https://www.googleapis.com/pagespeedonline/v5",
                health_check_path="/runPagespeed?url=https://example.com&key=test",
                required_env_vars=["GOOGLE_API_KEY"],
                api_key_header="key",
            ),
            "openai": ServiceEndpoint(
                name="OpenAI API",
                mock_url=f"{stub_base}/v1",
                production_url="https://api.openai.com/v1",
                health_check_path="/models",
                required_env_vars=["OPENAI_API_KEY"],
                api_key_header="Authorization",
            ),
            "sendgrid": ServiceEndpoint(
                name="SendGrid API",
                mock_url=f"{stub_base}/v3",
                production_url="https://api.sendgrid.com/v3",
                health_check_path="/user/profile",
                required_env_vars=["SENDGRID_API_KEY"],
                api_key_header="Authorization",
            ),
            "stripe": ServiceEndpoint(
                name="Stripe API",
                mock_url=f"{stub_base}/v1",
                production_url="https://api.stripe.com/v1",
                health_check_path="/account",
                required_env_vars=["STRIPE_SECRET_KEY"],
                api_key_header="Authorization",
            ),
            "data_axle": ServiceEndpoint(
                name="Data Axle API",
                mock_url=f"{stub_base}/data-axle",
                production_url="https://api.data-axle.com",
                health_check_path="/status",
                required_env_vars=["DATA_AXLE_API_KEY"],
                api_key_header="Authorization",
            ),
            "hunter": ServiceEndpoint(
                name="Hunter.io API",
                mock_url=f"{stub_base}/hunter",
                production_url="https://api.hunter.io/v2",
                health_check_path="/account",
                required_env_vars=["HUNTER_API_KEY"],
                api_key_header="api_key",
            ),
            "semrush": ServiceEndpoint(
                name="SEMrush API",
                mock_url=f"{stub_base}/semrush",
                production_url="https://api.semrush.com",
                health_check_path="/analytics/v1/",
                required_env_vars=["SEMRUSH_API_KEY"],
                api_key_header="key",
            ),
            "screenshotone": ServiceEndpoint(
                name="ScreenshotOne API",
                mock_url=f"{stub_base}/screenshot",
                production_url="https://api.screenshotone.com",
                health_check_path="/take",
                required_env_vars=["SCREENSHOTONE_KEY", "SCREENSHOTONE_SECRET"],
                api_key_header="Authorization",
            ),
        }

        return ServiceDiscoveryConfig(
            prefer_production=not self.settings.use_stubs,
            enable_fallback=True,
            health_check_interval=60,
            max_retries=3,
            endpoints=endpoints,
        )

    async def _get_session(self) -> aiohttp.ClientSession:
        """Get or create aiohttp session"""
        if self._session is None or self._session.closed:
            timeout = aiohttp.ClientTimeout(total=30)
            self._session = aiohttp.ClientSession(timeout=timeout)
        return self._session

    async def close(self):
        """Close aiohttp session"""
        if self._session and not self._session.closed:
            await self._session.close()

    async def check_service_health(
        self, service_name: str, endpoint: ServiceEndpoint, use_production: bool = True
    ) -> Tuple[bool, str]:
        """
        Check health of a specific service endpoint

        Args:
            service_name: Name of the service
            endpoint: Service endpoint configuration
            use_production: Whether to check production (True) or mock (False)

        Returns:
            Tuple of (is_healthy, status_message)
        """
        try:
            session = await self._get_session()

            # Choose URL based on preference
            base_url = endpoint.production_url if use_production else endpoint.mock_url
            url = f"{base_url}{endpoint.health_check_path}"

            # Prepare headers if API key is required
            headers = {}
            if use_production and endpoint.api_key_header:
                api_key = self._get_api_key(service_name, endpoint)
                if api_key:
                    if endpoint.api_key_header == "Authorization":
                        headers["Authorization"] = f"Bearer {api_key}"
                    else:
                        headers[endpoint.api_key_header] = api_key
                else:
                    return False, f"Missing API key for {service_name}"

            async with session.get(url, headers=headers) as response:
                if response.status < 500:  # Accept 4xx as "service is up"
                    return True, f"Service healthy (status: {response.status})"
                else:
                    return False, f"Service unhealthy (status: {response.status})"

        except asyncio.TimeoutError:
            return False, "Health check timeout"
        except Exception as e:
            return False, f"Health check failed: {str(e)}"

    def _get_api_key(self, service_name: str, endpoint: ServiceEndpoint) -> Optional[str]:
        """Get API key for service from environment variables"""
        for env_var in endpoint.required_env_vars:
            value = os.getenv(env_var)
            if value:
                return value
        return None

    async def determine_service_status(self, service_name: str) -> ServiceStatus:
        """
        Determine the best routing status for a service

        Args:
            service_name: Name of the service to check

        Returns:
            ServiceStatus indicating how to route requests
        """
        if service_name not in self.config.endpoints:
            logger.warning(f"Unknown service: {service_name}")
            return ServiceStatus.OFFLINE

        endpoint = self.config.endpoints[service_name]

        # Check if we're forced to use stubs
        if self.settings.use_stubs:
            mock_healthy, _ = await self.check_service_health(service_name, endpoint, use_production=False)
            return ServiceStatus.MOCK if mock_healthy else ServiceStatus.OFFLINE

        # Check production readiness
        readiness = production_config_service.get_integration_readiness()
        service_ready = readiness.get(service_name, {}).get("ready", False)

        if not service_ready:
            # Production not configured, use mock
            mock_healthy, _ = await self.check_service_health(service_name, endpoint, use_production=False)
            return ServiceStatus.MOCK if mock_healthy else ServiceStatus.OFFLINE

        # Check production health
        prod_healthy, prod_msg = await self.check_service_health(service_name, endpoint, use_production=True)

        if prod_healthy:
            return ServiceStatus.PRODUCTION
        elif self.config.enable_fallback:
            # Fallback to mock if production fails
            mock_healthy, mock_msg = await self.check_service_health(service_name, endpoint, use_production=False)
            if mock_healthy:
                logger.warning(f"Production {service_name} unhealthy ({prod_msg}), falling back to mock ({mock_msg})")
                return ServiceStatus.HYBRID
            else:
                logger.error(f"Both production and mock {service_name} unhealthy")
                return ServiceStatus.OFFLINE
        else:
            return ServiceStatus.OFFLINE

    async def get_service_url(self, service_name: str, force_status: Optional[ServiceStatus] = None) -> Optional[str]:
        """
        Get the appropriate URL for a service based on its status

        Args:
            service_name: Name of the service
            force_status: Override automatic status determination

        Returns:
            Base URL for the service or None if offline
        """
        if service_name not in self.config.endpoints:
            return None

        endpoint = self.config.endpoints[service_name]
        status = force_status or await self.determine_service_status(service_name)

        self.service_status[service_name] = status

        if status == ServiceStatus.PRODUCTION:
            return endpoint.production_url
        elif status in [ServiceStatus.MOCK, ServiceStatus.HYBRID]:
            return endpoint.mock_url
        else:
            return None

    async def get_all_service_statuses(self) -> Dict[str, Dict[str, Any]]:
        """
        Get status information for all configured services

        Returns:
            Dictionary mapping service names to status information
        """
        statuses = {}

        for service_name, endpoint in self.config.endpoints.items():
            status = await self.determine_service_status(service_name)

            # Get readiness info
            readiness = production_config_service.get_integration_readiness()
            service_readiness = readiness.get(service_name, {})

            statuses[service_name] = {
                "name": endpoint.name,
                "status": status,
                "production_ready": service_readiness.get("ready", False),
                "enabled": service_readiness.get("enabled", False),
                "has_api_key": service_readiness.get("has_api_key", False),
                "current_url": await self.get_service_url(service_name, force_status=status),
                "mock_url": endpoint.mock_url,
                "production_url": endpoint.production_url,
            }

        return statuses

    async def validate_production_readiness(self) -> Dict[str, Any]:
        """
        Comprehensive production readiness validation

        Returns:
            Validation report with readiness status and recommendations
        """
        logger.info("Starting comprehensive production readiness validation...")

        # Get base production config validation
        is_ready, issues = production_config_service.validate_production_readiness()

        # Get service-specific status
        service_statuses = await self.get_all_service_statuses()

        # Analyze service readiness
        ready_services = []
        mock_only_services = []
        offline_services = []

        for service_name, status_info in service_statuses.items():
            if status_info["status"] == ServiceStatus.PRODUCTION:
                ready_services.append(service_name)
            elif status_info["status"] in [ServiceStatus.MOCK, ServiceStatus.HYBRID]:
                mock_only_services.append(service_name)
            else:
                offline_services.append(service_name)

        # Generate recommendations
        recommendations = []

        if offline_services:
            recommendations.append(f"Fix offline services: {', '.join(offline_services)}")

        if mock_only_services:
            recommendations.append(f"Configure production APIs for: {', '.join(mock_only_services)}")

        if self.settings.use_stubs and self.settings.environment == "production":
            recommendations.append("Disable USE_STUBS=false for production deployment")

        return {
            "overall_ready": is_ready and len(offline_services) == 0,
            "production_config_ready": is_ready,
            "services_ready": len(ready_services),
            "services_mock_only": len(mock_only_services),
            "services_offline": len(offline_services),
            "ready_services": ready_services,
            "mock_only_services": mock_only_services,
            "offline_services": offline_services,
            "service_details": service_statuses,
            "issues": issues,
            "recommendations": recommendations,
            "next_steps": self._generate_next_steps(service_statuses, issues),
        }

    def _generate_next_steps(self, service_statuses: Dict, issues: List[str]) -> List[str]:
        """Generate prioritized next steps for production readiness"""
        steps = []

        # Critical issues first
        critical_issues = [issue for issue in issues if "CRITICAL" in issue]
        if critical_issues:
            steps.append("1. Fix critical configuration issues immediately")

        # Offline services
        offline_services = [name for name, info in service_statuses.items() if info["status"] == ServiceStatus.OFFLINE]
        if offline_services:
            steps.append(f"2. Restore offline services: {', '.join(offline_services)}")

        # Production API configuration
        mock_only = [
            name for name, info in service_statuses.items() if info["status"] == ServiceStatus.MOCK and info["enabled"]
        ]
        if mock_only:
            steps.append(f"3. Configure production APIs: {', '.join(mock_only)}")

        # Final validation
        steps.append("4. Run comprehensive service validation")
        steps.append("5. Perform end-to-end testing with production APIs")

        return steps


# Global service router instance
service_router = ServiceRouter()


async def get_service_url(service_name: str) -> Optional[str]:
    """
    Convenience function to get service URL

    Args:
        service_name: Name of the service

    Returns:
        Base URL for the service or None if offline
    """
    return await service_router.get_service_url(service_name)


async def validate_all_services() -> Dict[str, Any]:
    """
    Convenience function to validate all services

    Returns:
        Comprehensive validation report
    """
    return await service_router.validate_production_readiness()
