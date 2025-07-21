"""
Production Configuration Service - P3-006 Mock Integration Replacement

Service to help transition from mock integrations to production APIs by providing
configuration validation, API key checking, and integration readiness assessment.
"""

from typing import Any

from core.config import get_settings
from core.logging import get_logger

logger = get_logger(__name__)


class ProductionConfigService:
    """
    Service for managing production configuration and API integration readiness

    Part of P3-006 Replace Mock Integrations initiative.
    """

    def __init__(self):
        self.settings = get_settings()
        self.logger = logger

    def get_integration_readiness(self) -> dict[str, dict[str, Any]]:
        """
        Assess readiness for each API integration

        Returns:
            Dict mapping integration names to readiness status
        """
        integrations = {
            "google_places": self._check_google_places_readiness(),
            "pagespeed": self._check_pagespeed_readiness(),
            "openai": self._check_openai_readiness(),
            "sendgrid": self._check_sendgrid_readiness(),
            "stripe": self._check_stripe_readiness(),
            "data_axle": self._check_data_axle_readiness(),
            "hunter": self._check_hunter_readiness(),
            "semrush": self._check_semrush_readiness(),
            "screenshotone": self._check_screenshotone_readiness(),
        }

        return integrations

    def get_production_config_recommendations(self) -> list[str]:
        """
        Get recommendations for production configuration

        Returns:
            List of configuration recommendations
        """
        recommendations = []

        # Check if still using stubs
        if self.settings.use_stubs:
            recommendations.append("Set USE_STUBS=false to enable production APIs")

        # Check environment
        if self.settings.environment != "production":
            recommendations.append("Set ENVIRONMENT=production for production deployment")

        # Check secret key
        if self.settings.secret_key == "dev-secret-key-change-in-production":
            recommendations.append("Set a secure SECRET_KEY for production")

        # Check database URL
        if "sqlite" in self.settings.database_url and self.settings.environment == "production":
            recommendations.append("Use PostgreSQL DATABASE_URL for production (not SQLite)")

        # Check API keys
        readiness = self.get_integration_readiness()
        for integration, status in readiness.items():
            if not status["ready"] and status["enabled"]:
                recommendations.append(f"Configure {integration.upper()}_API_KEY for {integration}")

        return recommendations

    def validate_production_readiness(self) -> tuple[bool, list[str]]:
        """
        Validate if the system is ready for production deployment

        Returns:
            Tuple of (is_ready, list_of_issues)
        """
        issues = []

        # Critical checks
        if self.settings.use_stubs and self.settings.environment == "production":
            issues.append("CRITICAL: Cannot run production with USE_STUBS=true")

        if self.settings.secret_key == "dev-secret-key-change-in-production":
            issues.append("CRITICAL: Must set secure SECRET_KEY for production")

        # Database check
        if "sqlite" in self.settings.database_url and self.settings.environment == "production":
            issues.append("WARNING: Consider using PostgreSQL instead of SQLite for production")

        # Essential API keys check
        essential_apis = ["google_places", "openai", "sendgrid"]
        readiness = self.get_integration_readiness()

        for api in essential_apis:
            if api in readiness and readiness[api]["enabled"] and not readiness[api]["ready"]:
                issues.append(f"WARNING: {api} is enabled but not configured properly")

        is_ready = len([issue for issue in issues if "CRITICAL" in issue]) == 0

        return is_ready, issues

    def get_environment_transition_plan(self) -> dict[str, Any]:
        """
        Get a plan for transitioning from development/staging to production

        Returns:
            Transition plan with steps and priorities
        """
        readiness = self.get_integration_readiness()
        recommendations = self.get_production_config_recommendations()
        is_ready, issues = self.validate_production_readiness()

        # Categorize integrations by readiness
        ready_integrations = [name for name, status in readiness.items() if status["ready"]]
        needs_config = [name for name, status in readiness.items() if status["enabled"] and not status["ready"]]
        optional_integrations = [name for name, status in readiness.items() if not status["enabled"]]

        return {
            "current_status": {
                "environment": self.settings.environment,
                "using_stubs": self.settings.use_stubs,
                "production_ready": is_ready,
            },
            "ready_integrations": ready_integrations,
            "needs_configuration": needs_config,
            "optional_integrations": optional_integrations,
            "critical_issues": [issue for issue in issues if "CRITICAL" in issue],
            "warnings": [issue for issue in issues if "WARNING" in issue],
            "recommendations": recommendations,
            "next_steps": self._get_next_steps(readiness, issues),
        }

    def _get_next_steps(self, readiness: dict, issues: list[str]) -> list[str]:
        """Generate prioritized next steps"""
        steps = []

        # Critical fixes first
        if any("CRITICAL" in issue for issue in issues):
            steps.append("1. Fix critical configuration issues")

        # Essential API configuration
        essential_not_ready = [
            name
            for name in ["google_places", "openai", "sendgrid"]
            if name in readiness and readiness[name]["enabled"] and not readiness[name]["ready"]
        ]

        if essential_not_ready:
            steps.append(f"2. Configure essential APIs: {', '.join(essential_not_ready)}")

        # Test integration
        steps.append("3. Test API integrations in staging environment")

        # Optional enhancements
        optional_ready = [
            name for name in ["data_axle", "hunter", "semrush"] if name in readiness and not readiness[name]["enabled"]
        ]

        if optional_ready:
            steps.append(f"4. Consider enabling optional APIs: {', '.join(optional_ready)}")

        # Final validation
        steps.append("5. Run full production readiness check")

        return steps

    def _check_google_places_readiness(self) -> dict[str, Any]:
        """Check Google Places API readiness"""
        has_key = bool(self.settings.google_api_key)
        enabled = self.settings.enable_gbp and not self.settings.use_stubs

        return {
            "ready": has_key and enabled,
            "enabled": enabled,
            "has_api_key": has_key,
            "service_name": "Google Places API",
            "required_env_vars": ["GOOGLE_API_KEY"],
            "cost_per_request": "$0.002",
        }

    def _check_pagespeed_readiness(self) -> dict[str, Any]:
        """Check PageSpeed Insights API readiness"""
        has_key = bool(self.settings.google_api_key)  # Same key as Places
        enabled = self.settings.enable_pagespeed and not self.settings.use_stubs

        return {
            "ready": has_key and enabled,
            "enabled": enabled,
            "has_api_key": has_key,
            "service_name": "PageSpeed Insights API",
            "required_env_vars": ["GOOGLE_API_KEY"],
            "cost_per_request": "Free (with quota limits)",
        }

    def _check_openai_readiness(self) -> dict[str, Any]:
        """Check OpenAI API readiness"""
        has_key = bool(self.settings.openai_api_key)
        enabled = self.settings.enable_openai and not self.settings.use_stubs

        return {
            "ready": has_key and enabled,
            "enabled": enabled,
            "has_api_key": has_key,
            "service_name": "OpenAI API",
            "required_env_vars": ["OPENAI_API_KEY"],
            "cost_per_request": "Variable (based on tokens)",
        }

    def _check_sendgrid_readiness(self) -> dict[str, Any]:
        """Check SendGrid API readiness"""
        has_key = bool(self.settings.sendgrid_api_key)
        enabled = self.settings.enable_sendgrid and not self.settings.use_stubs

        return {
            "ready": has_key and enabled,
            "enabled": enabled,
            "has_api_key": has_key,
            "service_name": "SendGrid Email API",
            "required_env_vars": ["SENDGRID_API_KEY"],
            "cost_per_request": "$0.0006 per email",
        }

    def _check_stripe_readiness(self) -> dict[str, Any]:
        """Check Stripe API readiness"""
        has_secret = bool(self.settings.stripe_secret_key)
        has_webhook_secret = bool(self.settings.stripe_webhook_secret)
        has_price_id = bool(self.settings.stripe_price_id)

        ready = has_secret and has_webhook_secret and has_price_id
        enabled = not self.settings.use_stubs  # Stripe doesn't have explicit enable flag

        return {
            "ready": ready and enabled,
            "enabled": enabled,
            "has_api_key": has_secret,
            "service_name": "Stripe Payment API",
            "required_env_vars": ["STRIPE_SECRET_KEY", "STRIPE_WEBHOOK_SECRET", "STRIPE_PRICE_ID"],
            "cost_per_request": "2.9% + $0.30 per transaction",
        }

    def _check_data_axle_readiness(self) -> dict[str, Any]:
        """Check Data Axle API readiness"""
        has_key = bool(self.settings.data_axle_api_key)
        enabled = self.settings.providers_data_axle_enabled and not self.settings.use_stubs

        return {
            "ready": has_key and enabled,
            "enabled": enabled,
            "has_api_key": has_key,
            "service_name": "Data Axle Business Data API",
            "required_env_vars": ["DATA_AXLE_API_KEY"],
            "cost_per_request": "Variable (trial available)",
        }

    def _check_hunter_readiness(self) -> dict[str, Any]:
        """Check Hunter.io API readiness"""
        has_key = bool(self.settings.hunter_api_key)
        enabled = self.settings.providers_hunter_enabled and not self.settings.use_stubs

        return {
            "ready": has_key and enabled,
            "enabled": enabled,
            "has_api_key": has_key,
            "service_name": "Hunter.io Email Finder API",
            "required_env_vars": ["HUNTER_API_KEY"],
            "cost_per_request": "Variable (based on plan)",
        }

    def _check_semrush_readiness(self) -> dict[str, Any]:
        """Check SEMrush API readiness"""
        has_key = bool(self.settings.semrush_api_key)
        enabled = self.settings.enable_semrush and not self.settings.use_stubs

        return {
            "ready": has_key and enabled,
            "enabled": enabled,
            "has_api_key": has_key,
            "service_name": "SEMrush API",
            "required_env_vars": ["SEMRUSH_API_KEY"],
            "cost_per_request": "Based on daily quota",
        }

    def _check_screenshotone_readiness(self) -> dict[str, Any]:
        """Check ScreenshotOne API readiness"""
        has_key = bool(self.settings.screenshotone_key)
        has_secret = bool(self.settings.screenshotone_secret)
        enabled = self.settings.enable_visual_analysis and not self.settings.use_stubs

        return {
            "ready": has_key and has_secret and enabled,
            "enabled": enabled,
            "has_api_key": has_key and has_secret,
            "service_name": "ScreenshotOne API",
            "required_env_vars": ["SCREENSHOTONE_KEY", "SCREENSHOTONE_SECRET"],
            "cost_per_request": "Based on usage plan",
        }


# Global service instance
production_config_service = ProductionConfigService()
