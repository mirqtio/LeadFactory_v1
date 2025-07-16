"""
Configuration management using Pydantic Settings
Handles environment variables and validation
"""
import os
from functools import lru_cache
from typing import Dict, Optional

from pydantic import ConfigDict, Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings with environment variable support"""

    # Environment
    environment: str = Field(default="development")
    debug: bool = Field(default=False)
    testing: bool = Field(default=False)

    # Application
    app_name: str = "LeadFactory"
    app_version: str = "0.1.0"
    base_url: str = Field(default="http://localhost:8000")
    secret_key: str = Field(default="dev-secret-key-change-in-production")

    # Database
    database_url: str = Field(default="sqlite:///tmp/leadfactory.db")
    database_pool_size: int = Field(default=10)
    database_echo: bool = Field(default=False)

    # Redis
    redis_url: str = Field(default="redis://localhost:6379/0")
    cache_ttl: int = Field(default=3600)  # 1 hour default

    # External APIs
    use_stubs: bool = Field(default=True, description="Use stub server for all external APIs")
    stub_base_url: str = Field(default="http://localhost:5010")

    # Provider feature flags - Wave A (auto-disabled when USE_STUBS=true)
    enable_gbp: bool = Field(default=True, description="Enable Google Business Profile API")
    enable_pagespeed: bool = Field(default=True, description="Enable PageSpeed Insights API")
    enable_sendgrid: bool = Field(default=True, description="Enable SendGrid email delivery")
    enable_openai: bool = Field(default=True, description="Enable OpenAI API calls")

    # API Keys (only needed when USE_STUBS=false) - use SecretStr for sensitive data
    google_api_key: Optional[SecretStr] = Field(default=None)
    stripe_secret_key: Optional[SecretStr] = Field(default=None)
    stripe_publishable_key: Optional[str] = Field(default=None)
    stripe_webhook_secret: Optional[SecretStr] = Field(default=None)
    stripe_price_id: Optional[str] = Field(default=None)
    sendgrid_api_key: Optional[SecretStr] = Field(default=None)
    openai_api_key: Optional[SecretStr] = Field(default=None)
    openai_model: str = Field(default="gpt-4o-mini")

    # PRD v1.2 - Data Axle (trial)
    data_axle_api_key: Optional[SecretStr] = Field(default=None)
    data_axle_base_url: str = Field(default="https://api.data-axle.com/v2")
    data_axle_rate_limit_per_min: int = Field(default=200)

    # PRD v1.2 - Hunter.io
    hunter_api_key: Optional[SecretStr] = Field(default=None)
    hunter_rate_limit_per_min: int = Field(default=30)

    # PRD v1.2 - SEMrush
    semrush_api_key: Optional[SecretStr] = Field(default=None)
    semrush_daily_quota: int = Field(default=1000)

    # PRD v1.2 - ScreenshotOne
    screenshotone_key: Optional[SecretStr] = Field(default=None)
    screenshotone_secret: Optional[SecretStr] = Field(default=None)
    screenshotone_rate_limit_per_sec: int = Field(default=2)

    # Humanloop (for vision assessment)
    humanloop_api_key: Optional[SecretStr] = Field(default=None)

    # Email settings
    from_email: str = Field(default="noreply@leadfactory.com")
    from_name: str = Field(default="LeadFactory")

    # PRD v1.2 - API Limits
    max_daily_emails: int = Field(default=100000)
    max_businesses_per_batch: int = Field(default=50)

    # Performance
    request_timeout: int = Field(default=30)
    max_concurrent_assessments: int = Field(default=10)

    # Pricing
    report_price_cents: int = Field(default=19900)  # $199
    launch_discount_percent: int = Field(default=0)

    # Logging
    log_level: str = Field(default="INFO")
    log_format: str = Field(default="json")  # json or text

    # Monitoring
    prometheus_enabled: bool = Field(default=True)

    # Feature flags
    enable_enrichment: bool = Field(default=True)
    enable_llm_insights: bool = Field(default=True)
    enable_email_tracking: bool = Field(default=True)
    enable_experiments: bool = Field(default=False)

    # Phase 0.5 - Feature flags
    providers_data_axle_enabled: bool = Field(default=True)
    providers_hunter_enabled: bool = Field(default=False)
    lead_filter_min_score: float = Field(default=0.0)
    assessment_optional: bool = Field(default=True)

    # Phase 0.5 - Cost control
    cost_budget_usd: float = Field(default=1000.0)

    # Wave A/B feature flags for P0-005
    enable_emails: bool = Field(default=True)  # Wave A core feature
    enable_semrush: bool = Field(default=False)  # Wave B
    enable_lighthouse: bool = Field(default=False)  # Wave B
    enable_visual_analysis: bool = Field(default=False)  # Wave B
    enable_llm_audit: bool = Field(default=False)  # Wave B
    enable_cost_tracking: bool = Field(default=False)  # Wave B
    use_dataaxle: bool = Field(default=False)  # Wave B
    enable_cost_guardrails: bool = Field(default=False)  # Wave B
    daily_budget_cap: float = Field(default=100.0)  # USD
    per_lead_cap: float = Field(default=2.50)  # USD

    # P1-060 - Cost Guardrail Settings
    guardrail_global_daily_limit: float = Field(default=1000.0, description="Global daily spending limit in USD")
    guardrail_global_monthly_limit: float = Field(default=30000.0, description="Global monthly spending limit in USD")
    guardrail_provider_daily_limits: Dict[str, float] = Field(
        default={
            "openai": 500.0,
            "dataaxle": 300.0,
            "hunter": 100.0,
            "semrush": 200.0,
            "screenshotone": 50.0,
            "humanloop": 100.0,
        },
        description="Daily spending limits per provider in USD",
    )
    guardrail_warning_threshold: float = Field(default=0.8, ge=0.0, le=1.0, description="Warning threshold (0-1)")
    guardrail_critical_threshold: float = Field(default=0.95, ge=0.0, le=1.0, description="Critical threshold (0-1)")
    guardrail_alert_email: Optional[str] = Field(default=None, description="Email for guardrail alerts")
    guardrail_alert_slack_webhook: Optional[str] = Field(default=None, description="Slack webhook for guardrail alerts")
    guardrail_enable_circuit_breaker: bool = Field(default=True, description="Enable circuit breaker on cost limits")
    enable_report_lineage: bool = Field(default=True)  # P0-023
    enable_template_studio: bool = Field(default=True)  # P0-024
    enable_scoring_playground: bool = Field(default=True)  # P0-025
    enable_governance: bool = Field(default=True)  # P0-026

    @field_validator("environment")
    @classmethod
    def validate_environment(cls, v):
        allowed = ["development", "test", "staging", "production"]
        if v not in allowed:
            raise ValueError(f"Environment must be one of: {allowed}")
        return v

    @field_validator("database_url")
    @classmethod
    def validate_database_url(cls, v, info):
        if info.data.get("testing") and not v.startswith("sqlite"):
            # Force SQLite for testing
            return "sqlite:///tmp/test.db"
        return v

    @field_validator("use_stubs")
    @classmethod
    def validate_use_stubs(cls, v, info):
        # Force stubs in CI environment
        if os.getenv("CI") == "true":
            return True

        # Check if environment is test
        env = info.data.get("environment")
        if env == "test":
            return True

        # Don't validate production constraint here - it's handled in model_validator
        return v

    @field_validator("enable_gbp", "enable_pagespeed", "enable_sendgrid", "enable_openai", mode="before")
    @classmethod
    def disable_providers_when_using_stubs(cls, v, info):
        """Auto-disable all providers when USE_STUBS=true."""
        if info.data.get("use_stubs"):
            return False
        return v

    @field_validator("secret_key")
    @classmethod
    def validate_secret_key(cls, v, info):
        # Allow default secret key in CI environment
        if os.getenv("CI") == "true":
            return v

        if info.data.get("environment") == "production" and v == "dev-secret-key-change-in-production":
            raise ValueError("Secret key must be changed for production")
        return v

    @model_validator(mode="after")
    def validate_production_settings(self):
        """Validate production-specific settings after all fields are set"""
        if self.environment == "production" and self.use_stubs:
            raise ValueError("Production environment cannot run with USE_STUBS=true")

        # Validate API keys when providers are enabled and not using stubs
        if not self.use_stubs:
            if self.enable_gbp and not self.google_api_key:
                raise ValueError("Google API key required when GBP enabled and not using stubs")
            if self.enable_pagespeed and not self.google_api_key:
                raise ValueError("Google API key required when PageSpeed enabled and not using stubs")
            if self.enable_sendgrid and not self.sendgrid_api_key:
                raise ValueError("SendGrid API key required when SendGrid enabled and not using stubs")
            if self.enable_openai and not self.openai_api_key:
                raise ValueError("OpenAI API key required when OpenAI enabled and not using stubs")

        return self

    @property
    def is_production(self) -> bool:
        return self.environment == "production"

    @property
    def is_development(self) -> bool:
        return self.environment == "development"

    @property
    def api_base_urls(self) -> Dict[str, str]:
        """Get base URLs for external APIs"""
        if self.use_stubs:
            return {
                "google_places": self.stub_base_url,
                "pagespeed": self.stub_base_url,
                "stripe": self.stub_base_url,
                "sendgrid": self.stub_base_url,
                "openai": self.stub_base_url,
                "dataaxle": self.stub_base_url,
                "hunter": self.stub_base_url,
                "semrush": self.stub_base_url,
                "screenshotone": self.stub_base_url,
            }
        else:
            return {
                "google_places": "https://maps.googleapis.com",
                "pagespeed": "https://www.googleapis.com",
                "stripe": "https://api.stripe.com",
                "sendgrid": "https://api.sendgrid.com",
                "openai": "https://api.openai.com",
                "dataaxle": self.data_axle_base_url,
                "hunter": "https://api.hunter.io",
                "semrush": "https://api.semrush.com",
                "screenshotone": "https://api.screenshotone.com",
            }

    def get_api_key(self, service: str) -> str:
        """Get API key for a service"""
        if self.use_stubs:
            return f"stub-{service}-key"

        keys = {
            "google": self.google_api_key.get_secret_value() if self.google_api_key else None,
            "google_places": self.google_api_key.get_secret_value()
            if self.google_api_key
            else None,  # Google Places uses same API key
            "pagespeed": self.google_api_key.get_secret_value()
            if self.google_api_key
            else None,  # PageSpeed uses Google API key
            "stripe": self.stripe_secret_key.get_secret_value() if self.stripe_secret_key else None,
            "sendgrid": self.sendgrid_api_key.get_secret_value() if self.sendgrid_api_key else None,
            "openai": self.openai_api_key.get_secret_value() if self.openai_api_key else None,
            "dataaxle": self.data_axle_api_key.get_secret_value() if self.data_axle_api_key else None,
            "hunter": self.hunter_api_key.get_secret_value() if self.hunter_api_key else None,
            "semrush": self.semrush_api_key.get_secret_value() if self.semrush_api_key else None,
            "screenshotone": self.screenshotone_key.get_secret_value() if self.screenshotone_key else None,
            "humanloop": self.humanloop_api_key.get_secret_value() if self.humanloop_api_key else None,
        }

        key = keys.get(service)
        if not key:
            raise ValueError(f"API key not configured for {service}")
        return key

    model_config = ConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",  # Ignore extra environment variables
    )

    def model_dump(self, **kwargs):
        """Override to mask sensitive fields when serializing"""
        data = super().model_dump(**kwargs)

        # List of fields to mask
        sensitive_fields = [
            "secret_key",
            "openai_api_key",
            "sendgrid_api_key",
            "stripe_secret_key",
            "stripe_publishable_key",
            "stripe_webhook_secret",
            "hunter_api_key",
            "data_axle_api_key",
            "semrush_api_key",
            "screenshotone_key",
            "screenshotone_secret",
            "google_api_key",
        ]

        # Mask sensitive values
        for field in sensitive_fields:
            if field in data and data[field]:
                # Handle SecretStr values
                if hasattr(data[field], "get_secret_value"):
                    value = data[field].get_secret_value()
                else:
                    value = str(data[field])

                # Keep first 4 chars for identification
                if len(value) > 4:
                    data[field] = value[:4] + "*" * (len(value) - 4)
                else:
                    data[field] = "*" * len(value)

        return data


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance"""
    return Settings()


# Global settings instance
settings = get_settings()
