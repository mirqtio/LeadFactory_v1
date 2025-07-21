"""
Health checker module for PRP-1060 deployment validation.

Provides comprehensive health checks for post-deployment validation
including HTTP endpoints, service status, and system resources.
"""

import asyncio
import logging
import time
from datetime import UTC, datetime
from typing import Any

import httpx
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class HealthCheckConfig(BaseModel):
    """Configuration for health checks."""

    base_url: str = Field(..., description="Base URL for health checks")
    timeout_seconds: int = Field(default=30, description="Request timeout")
    max_retries: int = Field(default=3, description="Maximum retry attempts")
    retry_delay: int = Field(default=5, description="Delay between retries")

    # Health check endpoints
    health_endpoint: str = Field(default="/health", description="Main health check endpoint")
    readiness_endpoint: str = Field(default="/ready", description="Readiness check endpoint")
    liveness_endpoint: str = Field(default="/alive", description="Liveness check endpoint")

    # Expected responses
    expected_status_codes: list[int] = Field(default=[200], description="Expected HTTP status codes")
    expected_content_patterns: list[str] = Field(default_factory=list, description="Expected content patterns")


class HealthCheckResult(BaseModel):
    """Result of a health check operation."""

    name: str = Field(..., description="Health check name")
    status: str = Field(..., description="Check status: healthy, unhealthy, timeout, error")
    response_time_ms: float = Field(default=0.0, description="Response time in milliseconds")

    # HTTP specific fields
    status_code: int | None = Field(None, description="HTTP status code")
    response_body: str = Field(default="", description="Response body (truncated)")
    headers: dict[str, str] = Field(default_factory=dict, description="Response headers")

    # Error information
    error: str = Field(default="", description="Error message if check failed")
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))

    # Metadata
    metadata: dict[str, Any] = Field(default_factory=dict, description="Additional check metadata")


class HealthChecker:
    """Comprehensive health checker for deployment validation."""

    def __init__(self, config: HealthCheckConfig):
        self.config = config

    async def run_all_checks(self) -> dict[str, Any]:
        """Run all health checks and return comprehensive results."""
        logger.info("Starting comprehensive health checks")

        start_time = time.time()

        # Run all checks concurrently
        check_tasks = [
            self.check_health_endpoint(),
            self.check_readiness_endpoint(),
            self.check_liveness_endpoint(),
            self.check_ssl_certificate(),
            self.check_response_headers(),
            self.check_load_time_performance(),
        ]

        results = await asyncio.gather(*check_tasks, return_exceptions=True)

        # Process results
        check_results = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                check_results.append(HealthCheckResult(name=f"check_{i}", status="error", error=str(result)))
            else:
                check_results.append(result)

        # Calculate overall health
        overall_status = self._calculate_overall_status(check_results)

        end_time = time.time()

        summary = {
            "overall_status": overall_status,
            "total_checks": len(check_results),
            "healthy_checks": len([r for r in check_results if r.status == "healthy"]),
            "unhealthy_checks": len([r for r in check_results if r.status in ["unhealthy", "error", "timeout"]]),
            "total_duration_ms": round((end_time - start_time) * 1000, 2),
            "timestamp": datetime.now(UTC).isoformat(),
            "checks": [result.model_dump() for result in check_results],
        }

        logger.info(f"Health checks completed: {overall_status}")
        return summary

    async def check_health_endpoint(self) -> HealthCheckResult:
        """Check main health endpoint."""
        return await self._check_endpoint(
            "health_endpoint", self.config.health_endpoint, expected_patterns=["healthy", "ok", "status"]
        )

    async def check_readiness_endpoint(self) -> HealthCheckResult:
        """Check readiness endpoint."""
        return await self._check_endpoint(
            "readiness_endpoint", self.config.readiness_endpoint, expected_patterns=["ready", "ok"]
        )

    async def check_liveness_endpoint(self) -> HealthCheckResult:
        """Check liveness endpoint."""
        return await self._check_endpoint(
            "liveness_endpoint", self.config.liveness_endpoint, expected_patterns=["alive", "ok", "live"]
        )

    async def check_ssl_certificate(self) -> HealthCheckResult:
        """Check SSL certificate validity."""
        logger.info("Checking SSL certificate")

        start_time = time.time()

        try:
            # Only check SSL if URL is HTTPS
            if not self.config.base_url.startswith("https://"):
                return HealthCheckResult(
                    name="ssl_certificate",
                    status="healthy",
                    response_time_ms=0,
                    metadata={"note": "HTTP endpoint, SSL not applicable"},
                )

            async with httpx.AsyncClient(
                timeout=self.config.timeout_seconds,
                verify=True,  # Enable SSL verification
            ) as client:
                response = await client.get(self.config.base_url + self.config.health_endpoint)

                end_time = time.time()
                response_time = (end_time - start_time) * 1000

                return HealthCheckResult(
                    name="ssl_certificate",
                    status="healthy",
                    response_time_ms=response_time,
                    status_code=response.status_code,
                    metadata={"tls_version": getattr(response, "tls_version", "unknown"), "ssl_verified": True},
                )

        except httpx.SSLError as e:
            return HealthCheckResult(
                name="ssl_certificate",
                status="unhealthy",
                error=f"SSL certificate error: {e}",
                response_time_ms=(time.time() - start_time) * 1000,
            )
        except Exception as e:
            return HealthCheckResult(
                name="ssl_certificate", status="error", error=str(e), response_time_ms=(time.time() - start_time) * 1000
            )

    async def check_response_headers(self) -> HealthCheckResult:
        """Check security and performance headers."""
        logger.info("Checking response headers")

        return await self._check_endpoint("response_headers", self.config.health_endpoint, check_headers=True)

    async def check_load_time_performance(self) -> HealthCheckResult:
        """Check load time performance."""
        logger.info("Checking load time performance")

        start_time = time.time()

        try:
            async with httpx.AsyncClient(timeout=self.config.timeout_seconds) as client:
                response = await client.get(self.config.base_url + self.config.health_endpoint)

                end_time = time.time()
                response_time = (end_time - start_time) * 1000

                # Determine performance status
                if response_time < 500:
                    status = "healthy"
                elif response_time < 2000:
                    status = "unhealthy"  # Warning level
                else:
                    status = "unhealthy"  # Critical level

                return HealthCheckResult(
                    name="load_time_performance",
                    status=status,
                    response_time_ms=response_time,
                    status_code=response.status_code,
                    metadata={
                        "performance_level": (
                            "excellent"
                            if response_time < 200
                            else "good"
                            if response_time < 500
                            else "fair"
                            if response_time < 1000
                            else "poor"
                        ),
                        "benchmark_500ms": response_time < 500,
                        "benchmark_1000ms": response_time < 1000,
                    },
                )

        except TimeoutError:
            return HealthCheckResult(
                name="load_time_performance",
                status="timeout",
                error="Performance check timed out",
                response_time_ms=self.config.timeout_seconds * 1000,
            )
        except Exception as e:
            return HealthCheckResult(
                name="load_time_performance",
                status="error",
                error=str(e),
                response_time_ms=(time.time() - start_time) * 1000,
            )

    async def _check_endpoint(
        self, name: str, endpoint: str, expected_patterns: list[str] | None = None, check_headers: bool = False
    ) -> HealthCheckResult:
        """Generic endpoint health check."""
        logger.info(f"Checking endpoint: {endpoint}")

        url = self.config.base_url + endpoint
        start_time = time.time()

        # Try with retries
        for attempt in range(self.config.max_retries):
            try:
                async with httpx.AsyncClient(timeout=self.config.timeout_seconds) as client:
                    response = await client.get(url)

                    end_time = time.time()
                    response_time = (end_time - start_time) * 1000

                    # Check status code
                    status_ok = response.status_code in self.config.expected_status_codes

                    # Check content patterns if specified
                    content_ok = True
                    if expected_patterns:
                        response_text = response.text.lower()
                        content_ok = any(pattern.lower() in response_text for pattern in expected_patterns)

                    # Analyze headers if requested
                    header_analysis = {}
                    if check_headers:
                        header_analysis = self._analyze_headers(response.headers)

                    # Determine overall status
                    if status_ok and content_ok:
                        status = "healthy"
                    else:
                        status = "unhealthy"

                    return HealthCheckResult(
                        name=name,
                        status=status,
                        response_time_ms=response_time,
                        status_code=response.status_code,
                        response_body=response.text[:500],  # Truncate
                        headers=dict(response.headers),
                        metadata={
                            "attempt": attempt + 1,
                            "status_code_ok": status_ok,
                            "content_patterns_ok": content_ok,
                            "expected_patterns": expected_patterns or [],
                            "header_analysis": header_analysis,
                        },
                    )

            except TimeoutError:
                if attempt < self.config.max_retries - 1:
                    logger.warning(f"Timeout on attempt {attempt + 1}, retrying...")
                    await asyncio.sleep(self.config.retry_delay)
                    continue
                return HealthCheckResult(
                    name=name,
                    status="timeout",
                    error=f"Endpoint timed out after {self.config.max_retries} attempts",
                    response_time_ms=self.config.timeout_seconds * 1000,
                    metadata={"final_attempt": attempt + 1},
                )

            except Exception as e:
                if attempt < self.config.max_retries - 1:
                    logger.warning(f"Error on attempt {attempt + 1}: {e}, retrying...")
                    await asyncio.sleep(self.config.retry_delay)
                    continue
                return HealthCheckResult(
                    name=name,
                    status="error",
                    error=str(e),
                    response_time_ms=(time.time() - start_time) * 1000,
                    metadata={"final_attempt": attempt + 1},
                )

        # Should not reach here
        return HealthCheckResult(name=name, status="error", error="Unexpected end of retry loop")

    def _analyze_headers(self, headers: dict[str, str]) -> dict[str, Any]:
        """Analyze response headers for security and performance."""
        analysis = {"security_headers": {}, "performance_headers": {}, "recommendations": []}

        # Security headers
        security_headers = {
            "X-Frame-Options": "present",
            "X-Content-Type-Options": "present",
            "X-XSS-Protection": "present",
            "Strict-Transport-Security": "present",
            "Content-Security-Policy": "present",
        }

        for header, status in security_headers.items():
            analysis["security_headers"][header] = header in headers
            if header not in headers:
                analysis["recommendations"].append(f"Add {header} header for security")

        # Performance headers
        performance_headers = {
            "Cache-Control": headers.get("Cache-Control", "not set"),
            "ETag": headers.get("ETag", "not set"),
            "Last-Modified": headers.get("Last-Modified", "not set"),
            "Content-Encoding": headers.get("Content-Encoding", "not set"),
        }

        analysis["performance_headers"] = performance_headers

        # Check for compression
        if "Content-Encoding" not in headers:
            analysis["recommendations"].append("Enable compression (gzip/brotli) for better performance")

        return analysis

    def _calculate_overall_status(self, results: list[HealthCheckResult]) -> str:
        """Calculate overall health status from individual check results."""
        if not results:
            return "unknown"

        # Count status types
        status_counts = {}
        for result in results:
            status_counts[result.status] = status_counts.get(result.status, 0) + 1

        # Determine overall status
        total_checks = len(results)
        healthy_count = status_counts.get("healthy", 0)
        unhealthy_count = status_counts.get("unhealthy", 0)
        error_count = status_counts.get("error", 0)
        timeout_count = status_counts.get("timeout", 0)

        # Calculate health percentage
        health_percentage = (healthy_count / total_checks) * 100

        if health_percentage == 100:
            return "healthy"
        if health_percentage >= 80:
            return "degraded"
        if health_percentage >= 50:
            return "unhealthy"
        return "critical"

    async def quick_health_check(self) -> bool:
        """Quick health check that returns True/False."""
        try:
            result = await self.check_health_endpoint()
            return result.status == "healthy"
        except Exception:
            return False
