"""
Configuration for stub server usage
"""

import os
from typing import Any, Dict


class StubConfig:
    """Configuration for using stub servers in different environments"""

    def __init__(self):
        self.use_stubs = os.getenv("USE_STUBS", "true").lower() == "true"
        self.stub_base_url = os.getenv("STUB_BASE_URL", "http://localhost:5010")

    def get_api_urls(self) -> Dict[str, str]:
        """Get API URLs based on stub configuration"""
        if self.use_stubs:
            return {
                "pagespeed": f"{self.stub_base_url}",
                "stripe": f"{self.stub_base_url}",
                "sendgrid": f"{self.stub_base_url}",
                "openai": f"{self.stub_base_url}",
            }
        else:
            return {
                "pagespeed": "https://www.googleapis.com",
                "stripe": "https://api.stripe.com",
                "sendgrid": "https://api.sendgrid.com",
                "openai": "https://api.openai.com",
            }

    def get_headers(self, service: str) -> Dict[str, str]:
        """Get headers for API calls"""
        if self.use_stubs:
            # Stub server accepts any auth token
            return {"Authorization": f"Bearer stub-{service}-key"}
        else:
            # Real APIs need actual keys from environment
            api_keys = {
                "pagespeed": os.getenv("GOOGLE_API_KEY", ""),
                "stripe": os.getenv("STRIPE_SECRET_KEY", ""),
                "sendgrid": os.getenv("SENDGRID_API_KEY", ""),
                "openai": os.getenv("OPENAI_API_KEY", ""),
            }

            key = api_keys.get(service, "")
            if service == "sendgrid":
                return {"Authorization": f"Bearer {key}"}
            elif service == "stripe":
                return {"Authorization": f"Bearer {key}"}
            elif service == "openai":
                return {"Authorization": f"Bearer {key}"}
            elif service == "pagespeed":
                # PageSpeed uses API key in query params
                return {}
            else:
                return {}

    def should_verify_ssl(self) -> bool:
        """Whether to verify SSL certificates"""
        return not self.use_stubs

    def get_timeout(self) -> int:
        """Get request timeout in seconds"""
        return 5 if self.use_stubs else 30

    def get_retry_config(self) -> Dict[str, Any]:
        """Get retry configuration"""
        if self.use_stubs:
            return {
                "stop_after_attempt": 1,  # No retries for stubs
                "wait_exponential_multiplier": 0,
            }
        else:
            return {
                "stop_after_attempt": 3,
                "wait_exponential_multiplier": 1000,
                "wait_exponential_max": 10000,
            }


# Global instance
stub_config = StubConfig()
