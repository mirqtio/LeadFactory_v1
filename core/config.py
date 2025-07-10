"""
Configuration management using Pydantic Settings
Handles environment variables and validation
"""
import os
from functools import lru_cache
from typing import Any, Dict, Optional

from pydantic import ConfigDict, Field, field_validator
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
    use_stubs: bool = Field(default=True)
    stub_base_url: str = Field(default="http://localhost:5010")

    # API Keys (only needed when USE_STUBS=false)
    google_api_key: Optional[str] = Field(default=None)
    stripe_secret_key: Optional[str] = Field(default=None)
    stripe_publishable_key: Optional[str] = Field(default=None)
    stripe_webhook_secret: Optional[str] = Field(default=None)
    stripe_price_id: Optional[str] = Field(default=None)
    sendgrid_api_key: Optional[str] = Field(default=None)
    openai_api_key: Optional[str] = Field(default=None)
    openai_model: str = Field(default="gpt-4o-mini")

    # PRD v1.2 - Data Axle (trial)
    data_axle_api_key: Optional[str] = Field(default=None)
    data_axle_base_url: str = Field(default="https://api.data-axle.com/v1")
    data_axle_rate_limit_per_min: int = Field(default=200)

    # PRD v1.2 - Hunter.io
    hunter_api_key: Optional[str] = Field(default=None)
    hunter_rate_limit_per_min: int = Field(default=30)

    # PRD v1.2 - SEMrush
    semrush_api_key: Optional[str] = Field(default=None)
    semrush_daily_quota: int = Field(default=1000)

    # PRD v1.2 - ScreenshotOne
    screenshotone_key: Optional[str] = Field(default=None)
    screenshotone_secret: Optional[str] = Field(default=None)
    screenshotone_rate_limit_per_sec: int = Field(default=2)

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
        if os.getenv("CI") == "true" or info.data.get("environment") == "test":
            return True
        return v

    @field_validator("secret_key")
    @classmethod
    def validate_secret_key(cls, v, info):
        # Allow default secret key in CI environment
        if os.getenv("CI") == "true":
            return v

        if (
            info.data.get("environment") == "production"
            and v == "dev-secret-key-change-in-production"
        ):
            raise ValueError("Secret key must be changed for production")
        return v

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
            "google": self.google_api_key,
            "pagespeed": self.google_api_key,  # PageSpeed uses Google API key
            "stripe": self.stripe_secret_key,
            "sendgrid": self.sendgrid_api_key,
            "openai": self.openai_api_key,
            "dataaxle": self.data_axle_api_key,
            "hunter": self.hunter_api_key,
            "semrush": self.semrush_api_key,
            "screenshotone": self.screenshotone_key,
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


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance"""
    return Settings()


# Global settings instance
settings = get_settings()
