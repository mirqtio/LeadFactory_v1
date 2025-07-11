#!/usr/bin/env python3
"""
Production Configuration Validator - Task 090

Validates all production configuration settings, API keys, and environment variables
to ensure proper deployment readiness.

Acceptance Criteria:
- All secrets configured ✓
- API keys validated ✓  
- Database URL set ✓
- Monitoring configured ✓
"""

import os
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

import requests
import yaml


class ConfigValidator:
    """Validates production configuration settings"""

    def __init__(
        self,
        env_file: str = ".env.production",
        config_file: str = "config/production.yaml",
    ):
        """
        Initialize validator

        Args:
            env_file: Path to environment file
            config_file: Path to YAML config file
        """
        self.env_file = Path(env_file)
        self.config_file = Path(config_file)
        self.errors = []
        self.warnings = []
        self.env_vars = {}
        self.config = {}

        # Required environment variables
        self.required_env_vars = [
            "SECRET_KEY",
            "DATABASE_URL",
            "REDIS_URL",
            # "YELP_API_KEY", removed per P0-009
            "GOOGLE_PAGESPEED_API_KEY",
            "OPENAI_API_KEY",
            "STRIPE_SECRET_KEY",
            "STRIPE_WEBHOOK_SECRET",
            "SENDGRID_API_KEY",
        ]

        # Optional but recommended
        self.recommended_env_vars = [
            "RELEASE_VERSION",
            "DEPLOYMENT_DATE",
            "GIT_COMMIT",
            "BACKUP_S3_BUCKET",
            "ALERT_WEBHOOK_URL",
        ]

    def load_configuration(self) -> bool:
        """Load configuration files"""
        print("📋 Loading configuration files...")

        # Load environment file
        if not self.env_file.exists():
            self.errors.append(f"Environment file not found: {self.env_file}")
            return False

        try:
            with open(self.env_file, "r") as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#") and "=" in line:
                        key, value = line.split("=", 1)
                        self.env_vars[key.strip()] = value.strip()
        except Exception as e:
            self.errors.append(f"Error reading environment file: {e}")
            return False

        # Load YAML config
        if not self.config_file.exists():
            self.errors.append(f"Config file not found: {self.config_file}")
            return False

        try:
            with open(self.config_file, "r") as f:
                self.config = yaml.safe_load(f)
        except Exception as e:
            self.errors.append(f"Error reading YAML config: {e}")
            return False

        print(f"✅ Loaded {len(self.env_vars)} environment variables")
        print(f"✅ Loaded YAML configuration")
        return True

    def validate_environment_variables(self):
        """Validate all required environment variables are set"""
        print("\n🔐 Validating environment variables...")

        # Check required variables
        missing_required = []
        for var in self.required_env_vars:
            if (
                var not in self.env_vars
                or not self.env_vars[var]
                or self.env_vars[var].startswith("${")
            ):
                missing_required.append(var)

        if missing_required:
            self.errors.append(
                f"Missing required environment variables: {', '.join(missing_required)}"
            )
        else:
            print(
                f"✅ All {len(self.required_env_vars)} required environment variables are set"
            )

        # Check recommended variables
        missing_recommended = []
        for var in self.recommended_env_vars:
            if (
                var not in self.env_vars
                or not self.env_vars[var]
                or self.env_vars[var].startswith("${")
            ):
                missing_recommended.append(var)

        if missing_recommended:
            self.warnings.append(
                f"Missing recommended environment variables: {', '.join(missing_recommended)}"
            )

        # Validate specific formats
        self._validate_secret_key()
        self._validate_database_url()
        self._validate_redis_url()

    def _validate_secret_key(self):
        """Validate SECRET_KEY format and strength"""
        secret_key = self.env_vars.get("SECRET_KEY", "")

        if len(secret_key) < 50:
            self.errors.append("SECRET_KEY must be at least 50 characters long")

        if not re.search(r"[A-Za-z]", secret_key):
            self.warnings.append("SECRET_KEY should contain letters")

        if not re.search(r"[0-9]", secret_key):
            self.warnings.append("SECRET_KEY should contain numbers")

        if not re.search(r'[!@#$%^&*(),.?":{}|<>]', secret_key):
            self.warnings.append("SECRET_KEY should contain special characters")

    def _validate_database_url(self):
        """Validate DATABASE_URL format"""
        db_url = self.env_vars.get("DATABASE_URL", "")

        if not db_url.startswith(("postgresql://", "postgres://")):
            self.errors.append("DATABASE_URL must be a PostgreSQL connection string")
            return

        try:
            parsed = urlparse(db_url)
            if not parsed.hostname:
                self.errors.append("DATABASE_URL missing hostname")
            if not parsed.port:
                self.warnings.append("DATABASE_URL should specify port")
            if not parsed.username:
                self.errors.append("DATABASE_URL missing username")
            if not parsed.password:
                self.warnings.append("DATABASE_URL should include password")
        except Exception as e:
            self.errors.append(f"Invalid DATABASE_URL format: {e}")

    def _validate_redis_url(self):
        """Validate REDIS_URL format"""
        redis_url = self.env_vars.get("REDIS_URL", "")

        if not redis_url.startswith("redis://"):
            self.errors.append("REDIS_URL must be a Redis connection string")
            return

        try:
            parsed = urlparse(redis_url)
            if not parsed.hostname:
                self.errors.append("REDIS_URL missing hostname")
        except Exception as e:
            self.errors.append(f"Invalid REDIS_URL format: {e}")

    def validate_api_keys(self):
        """Validate API key formats and test connectivity"""
        print("\n🔑 Validating API keys...")

        # Validate formats
        # self._validate_yelp_key() removed per P0-009
        self._validate_pagespeed_key()
        self._validate_openai_key()
        self._validate_stripe_keys()
        self._validate_sendgrid_key()

    # _validate_yelp_key removed per P0-009

    def _validate_pagespeed_key(self):
        """Validate Google PageSpeed API key format"""
        key = self.env_vars.get("GOOGLE_PAGESPEED_API_KEY", "")
        if len(key) != 39:
            self.warnings.append("GOOGLE_PAGESPEED_API_KEY should be 39 characters")
        if not key.startswith("AIza"):
            self.warnings.append("GOOGLE_PAGESPEED_API_KEY should start with 'AIza'")

    def _validate_openai_key(self):
        """Validate OpenAI API key format"""
        key = self.env_vars.get("OPENAI_API_KEY", "")
        if not key.startswith("sk-"):
            self.errors.append("OPENAI_API_KEY must start with 'sk-'")
        elif len(key) < 50:
            self.warnings.append("OPENAI_API_KEY seems too short")

    def _validate_stripe_keys(self):
        """Validate Stripe API keys"""
        secret_key = self.env_vars.get("STRIPE_SECRET_KEY", "")
        if not secret_key.startswith("sk_"):
            self.errors.append("STRIPE_SECRET_KEY must start with 'sk_'")

        if secret_key.startswith("sk_test_"):
            self.warnings.append("STRIPE_SECRET_KEY appears to be a test key")
        elif not secret_key.startswith("sk_live_"):
            self.warnings.append(
                "STRIPE_SECRET_KEY should be 'sk_live_' for production"
            )

        webhook_secret = self.env_vars.get("STRIPE_WEBHOOK_SECRET", "")
        if not webhook_secret.startswith("whsec_"):
            self.errors.append("STRIPE_WEBHOOK_SECRET must start with 'whsec_'")

    def _validate_sendgrid_key(self):
        """Validate SendGrid API key format"""
        key = self.env_vars.get("SENDGRID_API_KEY", "")
        if not key.startswith("SG."):
            self.errors.append("SENDGRID_API_KEY must start with 'SG.'")
        elif len(key) < 60:
            self.warnings.append("SENDGRID_API_KEY seems too short")

    def validate_configuration_settings(self):
        """Validate YAML configuration settings"""
        print("\n⚙️  Validating configuration settings...")

        # Check app settings
        app_config = self.config.get("app", {})
        if app_config.get("environment") != "production":
            self.warnings.append("App environment should be 'production'")

        if app_config.get("debug", True):
            self.errors.append("Debug mode must be disabled in production")

        # Check database pool settings
        db_config = self.config.get("database", {})
        pool_size = db_config.get("pool_size", 0)
        if pool_size < 10:
            self.warnings.append(
                "Database pool_size should be at least 10 for production"
            )

        # Check Redis settings
        redis_config = self.config.get("redis", {})
        max_connections = redis_config.get("max_connections", 0)
        if max_connections < 20:
            self.warnings.append(
                "Redis max_connections should be at least 20 for production"
            )

        # Check monitoring
        monitoring = self.config.get("monitoring", {})
        if not monitoring.get("enabled", False):
            self.warnings.append("Monitoring should be enabled in production")

        # Check security settings
        security = self.config.get("security", {})
        cors = security.get("cors", {})
        allowed_origins = cors.get("allowed_origins", [])
        if not allowed_origins or "localhost" in str(allowed_origins):
            self.warnings.append(
                "CORS origins should not include localhost in production"
            )

        # Check performance settings
        performance = self.config.get("performance", {})
        workers = performance.get("workers", 1)
        if workers < 2:
            self.warnings.append("Should have at least 2 workers in production")

    def validate_monitoring_setup(self):
        """Validate monitoring configuration"""
        print("\n📊 Validating monitoring setup...")

        monitoring = self.config.get("monitoring", {})

        if not monitoring.get("enabled", False):
            self.errors.append("Monitoring must be enabled in production")
            return

        # Check Prometheus config
        prometheus = monitoring.get("prometheus", {})
        if not prometheus.get("port"):
            self.warnings.append("Prometheus port not configured")

        # Check health checks
        health_checks = self.config.get("health_checks", {})
        if not health_checks.get("enabled", False):
            self.warnings.append("Health checks should be enabled")

        required_checks = ["database", "redis", "external_apis"]
        configured_checks = health_checks.get("checks", [])
        missing_checks = [
            check for check in required_checks if check not in configured_checks
        ]
        if missing_checks:
            self.warnings.append(f"Missing health checks: {', '.join(missing_checks)}")

    def validate_deployment_readiness(self):
        """Validate deployment-specific settings"""
        print("\n🚀 Validating deployment readiness...")

        # Check deployment info
        deployment = self.config.get("deployment", {})

        required_deployment_fields = [
            "release_version",
            "deployment_date",
            "git_commit",
        ]
        for field in required_deployment_fields:
            if not deployment.get(field):
                self.warnings.append(f"Deployment {field} not set")

        # Check backup configuration
        backup = self.config.get("backup", {})
        if not backup.get("enabled", False):
            self.warnings.append("Backup should be enabled in production")

        if not backup.get("s3_bucket"):
            self.warnings.append("Backup S3 bucket not configured")

        # Check email configuration
        email = self.config.get("email", {})
        compliance = email.get("compliance", {})
        if not compliance.get("include_unsubscribe", False):
            self.errors.append("Email unsubscribe compliance must be enabled")

        if not compliance.get("physical_address"):
            self.errors.append("Physical address required for email compliance")

    def test_api_connectivity(self):
        """Test basic API connectivity (if keys are valid)"""
        print("\n🌐 Testing API connectivity...")

        # Only test if we have no errors so far
        if self.errors:
            print("⏭️  Skipping connectivity tests due to configuration errors")
            return

        # Test basic connectivity (non-intrusive)
        try:
            # Test Google PageSpeed API
            pagespeed_key = self.env_vars.get("GOOGLE_PAGESPEED_API_KEY")
            if pagespeed_key and not pagespeed_key.startswith("${"):
                response = requests.get(
                    f"https://www.googleapis.com/pagespeedonline/v5/runPagespeed",
                    params={
                        "url": "https://google.com",
                        "key": pagespeed_key,
                        "strategy": "desktop",
                    },
                    timeout=10,
                )
                if response.status_code == 200:
                    print("✅ Google PageSpeed API connectivity confirmed")
                else:
                    self.warnings.append(
                        f"Google PageSpeed API returned status {response.status_code}"
                    )
        except Exception as e:
            self.warnings.append(f"Could not test API connectivity: {e}")

    def generate_report(self) -> bool:
        """Generate validation report"""
        print("\n" + "=" * 80)
        print("🎯 PRODUCTION CONFIGURATION VALIDATION REPORT")
        print("=" * 80)

        print(
            f"\n📅 Validation Date: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC"
        )
        print(f"📁 Environment File: {self.env_file}")
        print(f"📁 Config File: {self.config_file}")

        # Summary
        if not self.errors and not self.warnings:
            print("\n✅ VALIDATION PASSED - Configuration is production ready!")
            return True

        # Errors
        if self.errors:
            print(f"\n❌ ERRORS ({len(self.errors)}):")
            for i, error in enumerate(self.errors, 1):
                print(f"   {i}. {error}")

        # Warnings
        if self.warnings:
            print(f"\n⚠️  WARNINGS ({len(self.warnings)}):")
            for i, warning in enumerate(self.warnings, 1):
                print(f"   {i}. {warning}")

        # Status
        if self.errors:
            print("\n❌ VALIDATION FAILED - Must fix errors before deployment")
            return False
        else:
            print("\n⚠️  VALIDATION PASSED WITH WARNINGS - Review recommended")
            return True

    def run_validation(self) -> bool:
        """Run complete validation process"""
        print("🚀 Starting Production Configuration Validation")
        print("=" * 60)

        # Load configuration
        if not self.load_configuration():
            self.generate_report()
            return False

        # Run all validations
        self.validate_environment_variables()
        self.validate_api_keys()
        self.validate_configuration_settings()
        self.validate_monitoring_setup()
        self.validate_deployment_readiness()
        self.test_api_connectivity()

        # Generate report
        return self.generate_report()


def main():
    """Main entry point"""
    import argparse

    parser = argparse.ArgumentParser(description="Validate production configuration")
    parser.add_argument(
        "--env-file", default=".env.production", help="Path to environment file"
    )
    parser.add_argument(
        "--config-file",
        default="config/production.yaml",
        help="Path to YAML config file",
    )
    parser.add_argument(
        "--check", action="store_true", help="Just check if files exist"
    )

    args = parser.parse_args()

    if args.check:
        # Simple check mode for CI
        env_exists = Path(args.env_file).exists()
        config_exists = Path(args.config_file).exists()

        print(f"Environment file exists: {env_exists}")
        print(f"Config file exists: {config_exists}")

        if env_exists and config_exists:
            print("✅ Configuration files present")
            sys.exit(0)
        else:
            print("❌ Missing configuration files")
            sys.exit(1)

    # Full validation
    validator = ConfigValidator(args.env_file, args.config_file)
    success = validator.run_validation()

    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
