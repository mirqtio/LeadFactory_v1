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
    yelp_api_key: Optional[str] = Field(default=None)
    google_api_key: Optional[str] = Field(default=None)
    stripe_secret_key: Optional[str] = Field(default=None)
    stripe_publishable_key: Optional[str] = Field(default=None)
    stripe_webhook_secret: Optional[str] = Field(default=None)
    stripe_price_id: Optional[str] = Field(default=None)
    sendgrid_api_key: Optional[str] = Field(default=None)
    openai_api_key: Optional[str] = Field(default=None)

    # Email settings
    from_email: str = Field(default="noreply@leadfactory.com")
    from_name: str = Field(default="LeadFactory")

    # API Limits
    max_daily_emails: int = Field(default=100)
    max_daily_yelp_calls: int = Field(default=5000)
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

    @field_validator("secret_key")
    @classmethod
    def validate_secret_key(cls, v, info):
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
                "yelp": self.stub_base_url,
                "pagespeed": self.stub_base_url,
                "stripe": self.stub_base_url,
                "sendgrid": self.stub_base_url,
                "openai": self.stub_base_url,
            }
        else:
            return {
                "yelp": "https://api.yelp.com",
                "pagespeed": "https://www.googleapis.com",
                "stripe": "https://api.stripe.com",
                "sendgrid": "https://api.sendgrid.com",
                "openai": "https://api.openai.com",
            }

    def get_api_key(self, service: str) -> str:
        """Get API key for a service"""
        if self.use_stubs:
            return f"stub-{service}-key"

        keys = {
            "yelp": self.yelp_api_key,
            "google": self.google_api_key,
            "stripe": self.stripe_secret_key,
            "sendgrid": self.sendgrid_api_key,
            "openai": self.openai_api_key,
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
