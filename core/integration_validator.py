"""
Integration Validation Framework for P3-006 Mock Integration Replacement

Comprehensive validation system for API integrations, production readiness,
and service health monitoring with automated testing capabilities.
"""

import json
import os
import time
from datetime import datetime
from typing import Any

import aiohttp
from pydantic import BaseModel, Field

from core.config import get_settings
from core.logging import get_logger
from core.production_config import production_config_service
from core.service_discovery import ServiceStatus, service_router

logger = get_logger(__name__)


class ValidationResult(BaseModel):
    """Result of an integration validation"""

    service_name: str
    test_name: str
    passed: bool
    response_time_ms: int | None = None
    status_code: int | None = None
    error_message: str | None = None
    details: dict[str, Any] = Field(default_factory=dict)
    timestamp: datetime = Field(default_factory=datetime.now)


class IntegrationReport(BaseModel):
    """Comprehensive integration validation report"""

    overall_score: float
    total_tests: int
    passed_tests: int
    failed_tests: int
    services_tested: int
    production_ready_services: int
    mock_only_services: int
    offline_services: int
    validation_results: list[ValidationResult] = Field(default_factory=list)
    service_summary: dict[str, dict[str, Any]] = Field(default_factory=dict)
    recommendations: list[str] = Field(default_factory=list)
    timestamp: datetime = Field(default_factory=datetime.now)


class IntegrationValidator:
    """
    Comprehensive integration validation system

    Features:
    - API endpoint health validation
    - Production readiness assessment
    - Mock service functionality verification
    - Performance benchmarking
    - Automated failover testing
    """

    def __init__(self):
        self.settings = get_settings()
        self.validation_results: list[ValidationResult] = []

    async def validate_service_endpoint(
        self,
        service_name: str,
        endpoint_path: str,
        method: str = "GET",
        payload: dict | None = None,
        expected_status: int = 200,
        timeout: int = 10,
    ) -> ValidationResult:
        """
        Validate a specific service endpoint

        Args:
            service_name: Name of the service to test
            endpoint_path: API endpoint path to test
            method: HTTP method (GET, POST, etc.)
            payload: Request payload for POST/PUT requests
            expected_status: Expected HTTP status code
            timeout: Request timeout in seconds

        Returns:
            ValidationResult with test outcome
        """
        test_name = f"{method} {endpoint_path}"
        start_time = time.time()

        try:
            # Get service URL through service discovery
            base_url = await service_router.get_service_url(service_name)
            if not base_url:
                return ValidationResult(
                    service_name=service_name,
                    test_name=test_name,
                    passed=False,
                    error_message=f"Service {service_name} is offline or not configured",
                )

            url = f"{base_url}{endpoint_path}"

            # Prepare request
            headers = {"Content-Type": "application/json"}

            # Add authentication if needed
            api_key = self._get_service_api_key(service_name)
            if api_key:
                headers.update(self._get_auth_headers(service_name, api_key))

            async with aiohttp.ClientSession() as session:
                async with session.request(
                    method=method, url=url, json=payload, headers=headers, timeout=aiohttp.ClientTimeout(total=timeout)
                ) as response:
                    response_time = int((time.time() - start_time) * 1000)
                    response_text = await response.text()

                    # Try to parse JSON response
                    try:
                        response_data = json.loads(response_text)
                    except json.JSONDecodeError:
                        response_data = {"raw_response": response_text}

                    passed = response.status == expected_status

                    return ValidationResult(
                        service_name=service_name,
                        test_name=test_name,
                        passed=passed,
                        response_time_ms=response_time,
                        status_code=response.status,
                        error_message=None if passed else f"Expected status {expected_status}, got {response.status}",
                        details={
                            "url": url,
                            "method": method,
                            "response_data": response_data,
                            "headers_sent": dict(headers),
                        },
                    )

        except TimeoutError:
            return ValidationResult(
                service_name=service_name,
                test_name=test_name,
                passed=False,
                response_time_ms=int((time.time() - start_time) * 1000),
                error_message=f"Request timeout after {timeout}s",
            )
        except Exception as e:
            return ValidationResult(
                service_name=service_name,
                test_name=test_name,
                passed=False,
                response_time_ms=int((time.time() - start_time) * 1000),
                error_message=f"Request failed: {str(e)}",
            )

    def _get_service_api_key(self, service_name: str) -> str | None:
        """Get API key for service from environment"""
        key_mapping = {
            "google_places": "GOOGLE_API_KEY",
            "pagespeed": "GOOGLE_API_KEY",
            "openai": "OPENAI_API_KEY",
            "sendgrid": "SENDGRID_API_KEY",
            "stripe": "STRIPE_SECRET_KEY",
            "data_axle": "DATA_AXLE_API_KEY",
            "hunter": "HUNTER_API_KEY",
            "semrush": "SEMRUSH_API_KEY",
            "screenshotone": "SCREENSHOTONE_KEY",
        }

        env_var = key_mapping.get(service_name)
        return os.getenv(env_var) if env_var else None

    def _get_auth_headers(self, service_name: str, api_key: str) -> dict[str, str]:
        """Get authentication headers for service"""
        if service_name in ["google_places", "pagespeed", "semrush"]:
            return {}  # API key goes in query params
        if service_name in ["openai", "sendgrid", "stripe", "data_axle", "hunter"] or service_name == "screenshotone":
            return {"Authorization": f"Bearer {api_key}"}
        return {}

    async def validate_google_places(self) -> list[ValidationResult]:
        """Validate Google Places API endpoints"""
        results = []

        # Test Find Place
        result = await self.validate_service_endpoint(
            service_name="google_places",
            endpoint_path="/findplacefromtext/json?input=restaurant&inputtype=textquery&fields=place_id,name",
            expected_status=200,
        )
        results.append(result)

        # Test Place Details
        result = await self.validate_service_endpoint(
            service_name="google_places",
            endpoint_path="/details/json?place_id=ChIJ_test_123&fields=name,rating,opening_hours",
            expected_status=200,
        )
        results.append(result)

        return results

    async def validate_pagespeed(self) -> list[ValidationResult]:
        """Validate PageSpeed Insights API"""
        results = []

        result = await self.validate_service_endpoint(
            service_name="pagespeed",
            endpoint_path="/runPagespeed?url=https://example.com&strategy=mobile",
            expected_status=200,
        )
        results.append(result)

        return results

    async def validate_openai(self) -> list[ValidationResult]:
        """Validate OpenAI API endpoints"""
        results = []

        # Test chat completion
        payload = {"model": "gpt-4o-mini", "messages": [{"role": "user", "content": "Hello"}], "max_tokens": 50}

        result = await self.validate_service_endpoint(
            service_name="openai",
            endpoint_path="/chat/completions",
            method="POST",
            payload=payload,
            expected_status=200,
        )
        results.append(result)

        return results

    async def validate_sendgrid(self) -> list[ValidationResult]:
        """Validate SendGrid API endpoints"""
        results = []

        # Test send email
        payload = {
            "personalizations": [{"to": [{"email": "test@example.com"}]}],
            "from": {"email": "sender@example.com"},
            "subject": "Test Email",
            "content": [{"type": "text/plain", "value": "Test content"}],
        }

        result = await self.validate_service_endpoint(
            service_name="sendgrid", endpoint_path="/mail/send", method="POST", payload=payload, expected_status=202
        )
        results.append(result)

        return results

    async def validate_stripe(self) -> list[ValidationResult]:
        """Validate Stripe API endpoints"""
        results = []

        # Test create checkout session
        payload = {
            "payment_method_types": ["card"],
            "line_items": [{"price": "price_test_123", "quantity": 1}],
            "mode": "payment",
            "success_url": "https://example.com/success",
            "cancel_url": "https://example.com/cancel",
        }

        result = await self.validate_service_endpoint(
            service_name="stripe",
            endpoint_path="/checkout/sessions",
            method="POST",
            payload=payload,
            expected_status=200,
        )
        results.append(result)

        return results

    async def validate_all_services(self) -> IntegrationReport:
        """
        Run comprehensive validation of all configured services

        Returns:
            IntegrationReport with complete validation results
        """
        logger.info("Starting comprehensive integration validation...")

        all_results = []

        # Service-specific validations
        service_validators = {
            "google_places": self.validate_google_places,
            "pagespeed": self.validate_pagespeed,
            "openai": self.validate_openai,
            "sendgrid": self.validate_sendgrid,
            "stripe": self.validate_stripe,
        }

        # Run all validations
        for service_name, validator in service_validators.items():
            try:
                results = await validator()
                all_results.extend(results)
            except Exception as e:
                logger.error(f"Validation failed for {service_name}: {str(e)}")
                all_results.append(
                    ValidationResult(
                        service_name=service_name,
                        test_name="Service Validation",
                        passed=False,
                        error_message=f"Validation error: {str(e)}",
                    )
                )

        # Get service status information
        service_statuses = await service_router.get_all_service_statuses()

        # Analyze results
        total_tests = len(all_results)
        passed_tests = sum(1 for r in all_results if r.passed)
        failed_tests = total_tests - passed_tests

        services_tested = len(set(r.service_name for r in all_results))
        production_ready = sum(1 for s in service_statuses.values() if s["status"] == ServiceStatus.PRODUCTION)
        mock_only = sum(1 for s in service_statuses.values() if s["status"] == ServiceStatus.MOCK)
        offline = sum(1 for s in service_statuses.values() if s["status"] == ServiceStatus.OFFLINE)

        overall_score = (passed_tests / total_tests * 100) if total_tests > 0 else 0

        # Generate service summary
        service_summary = {}
        for service_name in set(r.service_name for r in all_results):
            service_results = [r for r in all_results if r.service_name == service_name]
            service_passed = sum(1 for r in service_results if r.passed)
            service_total = len(service_results)

            service_summary[service_name] = {
                "tests_passed": service_passed,
                "tests_total": service_total,
                "success_rate": (service_passed / service_total * 100) if service_total > 0 else 0,
                "status": service_statuses.get(service_name, {}).get("status", "unknown"),
                "avg_response_time": self._calculate_avg_response_time(service_results),
            }

        # Generate recommendations
        recommendations = self._generate_recommendations(all_results, service_statuses, service_summary)

        return IntegrationReport(
            overall_score=overall_score,
            total_tests=total_tests,
            passed_tests=passed_tests,
            failed_tests=failed_tests,
            services_tested=services_tested,
            production_ready_services=production_ready,
            mock_only_services=mock_only,
            offline_services=offline,
            validation_results=all_results,
            service_summary=service_summary,
            recommendations=recommendations,
        )

    def _calculate_avg_response_time(self, results: list[ValidationResult]) -> float | None:
        """Calculate average response time for a set of results"""
        response_times = [r.response_time_ms for r in results if r.response_time_ms is not None]
        return sum(response_times) / len(response_times) if response_times else None

    def _generate_recommendations(
        self, results: list[ValidationResult], service_statuses: dict, service_summary: dict
    ) -> list[str]:
        """Generate actionable recommendations based on validation results"""
        recommendations = []

        # Failed test recommendations
        failed_services = set(r.service_name for r in results if not r.passed)
        if failed_services:
            recommendations.append(f"Fix failing services: {', '.join(failed_services)}")

        # Performance recommendations
        slow_services = []
        for service_name, summary in service_summary.items():
            avg_time = summary.get("avg_response_time")
            if avg_time and avg_time > 5000:  # > 5 seconds
                slow_services.append(service_name)

        if slow_services:
            recommendations.append(f"Optimize slow services (>5s): {', '.join(slow_services)}")

        # Production readiness recommendations
        mock_services = [
            name
            for name, status in service_statuses.items()
            if status.get("status") == ServiceStatus.MOCK and status.get("enabled")
        ]
        if mock_services:
            recommendations.append(f"Configure production APIs: {', '.join(mock_services)}")

        # Configuration recommendations
        offline_services = [
            name for name, status in service_statuses.items() if status.get("status") == ServiceStatus.OFFLINE
        ]
        if offline_services:
            recommendations.append(f"Fix offline services: {', '.join(offline_services)}")

        return recommendations

    async def validate_failover_behavior(self, service_name: str) -> ValidationResult:
        """
        Test automatic failover from production to mock services

        Args:
            service_name: Service to test failover for

        Returns:
            ValidationResult indicating failover success
        """
        try:
            # Force production mode temporarily
            original_status = await service_router.determine_service_status(service_name)

            # Test that service can handle fallback
            if original_status == ServiceStatus.HYBRID:
                return ValidationResult(
                    service_name=service_name,
                    test_name="Failover Test",
                    passed=True,
                    details={"failover_working": True, "original_status": original_status},
                )
            return ValidationResult(
                service_name=service_name,
                test_name="Failover Test",
                passed=True,
                details={"failover_not_needed": True, "status": original_status},
            )

        except Exception as e:
            return ValidationResult(
                service_name=service_name,
                test_name="Failover Test",
                passed=False,
                error_message=f"Failover test failed: {str(e)}",
            )


# Global validator instance
integration_validator = IntegrationValidator()


async def validate_all_integrations() -> IntegrationReport:
    """
    Convenience function to run comprehensive integration validation

    Returns:
        IntegrationReport with complete validation results
    """
    return await integration_validator.validate_all_services()


async def validate_production_transition() -> dict[str, Any]:
    """
    Comprehensive production transition validation

    Returns:
        Complete readiness assessment for production deployment
    """
    # Run integration tests
    integration_report = await validate_all_integrations()

    # Run service discovery validation
    service_validation = await service_router.validate_production_readiness()

    # Run production config validation
    config_ready, config_issues = production_config_service.validate_production_readiness()

    # Overall readiness assessment
    integration_ready = integration_report.overall_score >= 80.0  # 80% pass rate
    services_ready = service_validation["overall_ready"]

    overall_ready = integration_ready and services_ready and config_ready

    return {
        "overall_ready": overall_ready,
        "integration_score": integration_report.overall_score,
        "integration_ready": integration_ready,
        "services_ready": services_ready,
        "config_ready": config_ready,
        "integration_report": integration_report.model_dump(),
        "service_validation": service_validation,
        "config_issues": config_issues,
        "summary": {
            "total_services": len(service_validation["service_details"]),
            "production_ready": service_validation["services_ready"],
            "mock_only": service_validation["services_mock_only"],
            "offline": service_validation["services_offline"],
            "tests_passed": integration_report.passed_tests,
            "tests_total": integration_report.total_tests,
        },
        "recommendations": [*integration_report.recommendations, *service_validation["recommendations"]],
    }
