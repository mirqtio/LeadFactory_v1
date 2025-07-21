"""
Lighthouse assessor using actual Lighthouse CLI
PRD v1.2 - Website performance analysis

Timeout: 30s per audit
Cost: $0.00 (local execution)
Output: lighthouse_json column
Cache: 7 days
"""

import asyncio
import hashlib
import json
import os
from datetime import datetime, timedelta
from typing import Any

from core.config import get_settings
from core.logging import get_logger
from d3_assessment.assessors.base import AssessmentResult, BaseAssessor
from d3_assessment.exceptions import AssessmentTimeoutError
from d3_assessment.models import AssessmentType

logger = get_logger(__name__, domain="d3")


class LighthouseAssessor(BaseAssessor):
    """Assess website performance using actual Lighthouse CLI"""

    def __init__(self):
        super().__init__()
        self.timeout = 30  # 30 seconds per audit
        self.cache_dir = "/tmp/lighthouse_cache"
        self.cache_days = 7
        self.logger = logger

        # Create cache directory if it doesn't exist
        os.makedirs(self.cache_dir, exist_ok=True)

    @property
    def assessment_type(self) -> AssessmentType:
        return AssessmentType.LIGHTHOUSE

    def _get_cache_key(self, url: str) -> str:
        """Generate cache key for URL"""
        return hashlib.md5(url.encode()).hexdigest()

    def _get_cached_result(self, url: str) -> dict[str, Any] | None:
        """Get cached result if available and not expired"""
        cache_key = self._get_cache_key(url)
        cache_file = os.path.join(self.cache_dir, f"{cache_key}.json")

        if os.path.exists(cache_file):
            try:
                # Check if cache is still valid
                file_time = datetime.fromtimestamp(os.path.getmtime(cache_file))
                if datetime.now() - file_time < timedelta(days=self.cache_days):
                    with open(cache_file) as f:
                        logger.info(f"Using cached Lighthouse result for {url}")
                        return json.load(f)
            except Exception as e:
                logger.warning(f"Failed to read cache for {url}: {e}")

        return None

    def _save_to_cache(self, url: str, data: dict[str, Any]):
        """Save result to cache"""
        cache_key = self._get_cache_key(url)
        cache_file = os.path.join(self.cache_dir, f"{cache_key}.json")

        try:
            with open(cache_file, "w") as f:
                json.dump(data, f)
            logger.debug(f"Saved Lighthouse result to cache for {url}")
        except Exception as e:
            logger.warning(f"Failed to save cache for {url}: {e}")

    def _get_stub_data(self, url: str) -> dict[str, Any]:
        """Return stub data when USE_STUBS=true"""
        return {
            "scores": {"performance": 85, "accessibility": 92, "best-practices": 88, "seo": 90, "pwa": 75},
            "core_web_vitals": {
                "lcp": 2500,  # Largest Contentful Paint in ms
                "fid": 100,  # First Input Delay in ms
                "cls": 0.1,  # Cumulative Layout Shift
            },
            "metrics": {
                "first_contentful_paint": 1200,
                "speed_index": 2100,
                "time_to_interactive": 3500,
                "total_blocking_time": 200,
            },
            "opportunities": [
                {"id": "unused-css", "title": "Remove unused CSS", "savings_ms": 450},
                {"id": "uses-responsive-images", "title": "Properly size images", "savings_ms": 300},
            ],
            "diagnostics": [
                {"id": "font-display", "title": "Ensure text remains visible during webfont load", "score": 0.5}
            ],
            "fetch_time": datetime.utcnow().isoformat(),
            "lighthouse_version": "11.0.0",
            "user_agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "is_stub": True,
        }

    async def _run_lighthouse_audit(self, url: str) -> dict[str, Any]:
        """Run Lighthouse audit using actual Lighthouse CLI"""
        import tempfile

        # Create temporary file for Lighthouse output
        with tempfile.NamedTemporaryFile(mode="w+", suffix=".json", delete=False) as tmp_file:
            tmp_path = tmp_file.name

        try:
            # Run Lighthouse CLI with JSON output
            cmd = [
                "lighthouse",
                url,
                "--output=json",
                "--output-path=" + tmp_path,
                "--chrome-flags=--headless",
                "--quiet",
                "--max-wait-for-load=15000",
                "--timeout=30000",
                "--no-enable-error-reporting",
            ]

            logger.info(f"Running Lighthouse CLI: {' '.join(cmd)}")

            # Execute Lighthouse CLI
            process = await asyncio.create_subprocess_exec(
                *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
            )

            stdout, stderr = await process.communicate()

            if process.returncode != 0:
                logger.error(f"Lighthouse CLI failed with return code {process.returncode}")
                logger.error(f"STDERR: {stderr.decode()}")
                raise RuntimeError(f"Lighthouse CLI failed: {stderr.decode()}")

            # Read and parse the JSON output
            with open(tmp_path) as f:
                lighthouse_json = json.load(f)

            # Extract key data from Lighthouse JSON
            categories = lighthouse_json.get("categories", {})
            audits = lighthouse_json.get("audits", {})

            # Get scores (0-100)
            scores = {
                "performance": int(categories.get("performance", {}).get("score", 0) * 100),
                "accessibility": int(categories.get("accessibility", {}).get("score", 0) * 100),
                "best-practices": int(categories.get("best-practices", {}).get("score", 0) * 100),
                "seo": int(categories.get("seo", {}).get("score", 0) * 100),
                "pwa": int(categories.get("pwa", {}).get("score", 0) * 100),
            }

            # Extract Core Web Vitals
            core_web_vitals = {
                "lcp": audits.get("largest-contentful-paint", {}).get("numericValue", 0),
                "fid": audits.get("max-potential-fid", {}).get("numericValue", 0),
                "cls": audits.get("cumulative-layout-shift", {}).get("numericValue", 0),
            }

            # Extract other metrics
            metrics = {
                "first_contentful_paint": audits.get("first-contentful-paint", {}).get("numericValue", 0),
                "speed_index": audits.get("speed-index", {}).get("numericValue", 0),
                "time_to_interactive": audits.get("interactive", {}).get("numericValue", 0),
                "total_blocking_time": audits.get("total-blocking-time", {}).get("numericValue", 0),
            }

            # Extract opportunities
            opportunities = []
            for audit_key, audit_data in audits.items():
                if audit_data.get("details", {}).get("type") == "opportunity":
                    opportunities.append(
                        {
                            "id": audit_key,
                            "title": audit_data.get("title", ""),
                            "description": audit_data.get("description", ""),
                            "savings_ms": audit_data.get("numericValue", 0),
                        }
                    )

            # Extract diagnostics
            diagnostics = []
            for audit_key, audit_data in audits.items():
                if audit_data.get("scoreDisplayMode") == "binary" and audit_data.get("score", 1) < 1:
                    diagnostics.append(
                        {
                            "id": audit_key,
                            "title": audit_data.get("title", ""),
                            "description": audit_data.get("description", ""),
                            "score": audit_data.get("score", 0),
                        }
                    )

            result = {
                "scores": scores,
                "core_web_vitals": core_web_vitals,
                "metrics": metrics,
                "opportunities": opportunities,
                "diagnostics": diagnostics,
                "fetch_time": datetime.utcnow().isoformat(),
                "lighthouse_version": lighthouse_json.get("lighthouseVersion", "unknown"),
                "user_agent": lighthouse_json.get("userAgent", "unknown"),
                "full_lighthouse_json": lighthouse_json,  # Include full JSON for debugging
            }

            return result

        finally:
            # Clean up temporary file
            try:
                os.unlink(tmp_path)
            except:
                pass

    async def assess(self, url: str, business_data: dict[str, Any]) -> AssessmentResult:
        """
        Assess website performance using Lighthouse

        Args:
            url: Website URL to assess
            business_data: Business information (not used for Lighthouse)

        Returns:
            AssessmentResult with Lighthouse data
        """
        logger.info(f"LighthouseAssessor.assess called for URL: {url}")

        try:
            # Check if feature is enabled
            settings = get_settings()
            if not settings.enable_lighthouse:
                logger.info("Lighthouse feature is disabled")
                return AssessmentResult(
                    assessment_type=self.assessment_type,
                    status="skipped",
                    data={"lighthouse_json": {}},
                    error_message="Lighthouse feature is disabled",
                )

            # Use stub data if USE_STUBS=true
            if settings.use_stubs:
                logger.info("Using stub data for Lighthouse assessment")
                lighthouse_data = self._get_stub_data(url)
            else:
                # Check cache first
                lighthouse_data = self._get_cached_result(url)

                if lighthouse_data is None:
                    # Run actual Lighthouse audit with timeout
                    try:
                        lighthouse_data = await asyncio.wait_for(self._run_lighthouse_audit(url), timeout=self.timeout)
                        # Save to cache
                        self._save_to_cache(url, lighthouse_data)
                    except TimeoutError:
                        raise AssessmentTimeoutError(f"Lighthouse audit timed out after {self.timeout}s")

            # Extract metrics for quick access
            scores = lighthouse_data.get("scores", {})
            cwv = lighthouse_data.get("core_web_vitals", {})

            return AssessmentResult(
                assessment_type=self.assessment_type,
                status="completed",
                data={"lighthouse_json": lighthouse_data},
                metrics={
                    "performance_score": scores.get("performance", 0),
                    "accessibility_score": scores.get("accessibility", 0),
                    "best_practices_score": scores.get("best-practices", 0),
                    "seo_score": scores.get("seo", 0),
                    "pwa_score": scores.get("pwa", 0),
                    "lcp_ms": cwv.get("lcp"),
                    "fid_ms": cwv.get("fid"),
                    "cls_score": cwv.get("cls"),
                    "mobile_friendly": scores.get("performance", 0) >= 50,
                },
                cost=0.0,  # Local execution has no cost
            )

        except AssessmentTimeoutError:
            raise
        except Exception as e:
            logger.error(f"Lighthouse assessment failed for {url}: {e}")

            # Return minimal result with error
            return AssessmentResult(
                assessment_type=self.assessment_type,
                status="failed",
                data={"lighthouse_json": {}},
                error_message=f"Lighthouse audit error: {str(e)}",
            )

    def calculate_cost(self) -> float:
        """Lighthouse runs locally so has no API cost"""
        return 0.0

    def is_available(self) -> bool:
        """Check if Lighthouse assessor is available"""
        settings = get_settings()

        # Check if feature flag is enabled
        if not settings.enable_lighthouse:
            return False

        # If using stubs, always available
        if settings.use_stubs:
            return True

        # Check if Lighthouse CLI is installed
        try:
            import subprocess

            result = subprocess.run(["lighthouse", "--version"], capture_output=True, text=True)
            if result.returncode == 0:
                logger.info(f"Lighthouse CLI available: {result.stdout.strip()}")
                return True
            logger.warning("Lighthouse CLI not found")
            return False
        except Exception as e:
            logger.warning(f"Failed to check Lighthouse CLI: {e}")
            return False
