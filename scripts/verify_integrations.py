#!/usr/bin/env python3
"""
External Integration Verification Script - Task 094

Verifies connectivity and configuration for all external API integrations
required for LeadFactory production deployment.

Acceptance Criteria:
- External APIs connected ✓
- SendGrid verified ✓
- Stripe test mode ✓
- All APIs responsive ✓
"""

import argparse
import json
import os
import sys
import time
from datetime import datetime
from typing import Any, Dict, List

import requests
import stripe
from sendgrid import SendGridAPIClient


class IntegrationVerifier:
    """Verifies external API integrations for LeadFactory"""

    def __init__(self, use_stubs: bool = False):
        """
        Initialize integration verifier

        Args:
            use_stubs: Use stub server instead of real APIs for testing
        """
        self.use_stubs = use_stubs
        self.stub_base_url = os.getenv("STUB_SERVER_URL", "http://localhost:5010")

        # Load API keys from environment
        self.api_keys = {
            # "yelp": removed per P0-009 - Yelp provider no longer supported
            "google_pagespeed": os.getenv("GOOGLE_PAGESPEED_API_KEY", ""),
            "openai": os.getenv("OPENAI_API_KEY", ""),
            "stripe_secret": os.getenv("STRIPE_SECRET_KEY", ""),
            "stripe_webhook": os.getenv("STRIPE_WEBHOOK_SECRET", ""),
            "sendgrid": os.getenv("SENDGRID_API_KEY", ""),
        }

        self.results = {}
        self.errors = []
        self.warnings = []

        # Set up Stripe
        if self.api_keys["stripe_secret"]:
            stripe.api_key = self.api_keys["stripe_secret"]

    # verify_yelp_integration removed per P0-009 - Yelp provider no longer supported

    def verify_google_pagespeed_integration(self) -> bool:
        """Verify Google PageSpeed Insights API integration"""
        service = "google_pagespeed"
        print("⚡ Verifying Google PageSpeed integration...")

        try:
            if self.use_stubs:
                url = f"{self.stub_base_url}/pagespeed/v5/runPagespeed"
                api_key = "stub_key"
            else:
                url = "https://www.googleapis.com/pagespeedonline/v5/runPagespeed"
                if not self.api_keys["google_pagespeed"]:
                    self.errors.append("GOOGLE_PAGESPEED_API_KEY not configured")
                    return False
                api_key = self.api_keys["google_pagespeed"]

            # Test PageSpeed analysis with simple URL
            params = {
                "url": "https://google.com",
                "key": api_key,
                "strategy": "desktop",
                "category": "performance",
            }

            start_time = time.time()
            response = requests.get(url, params=params, timeout=30)
            response_time = time.time() - start_time

            if response.status_code == 200:
                data = response.json()
                lighthouse_result = data.get("lighthouseResult", {})
                categories = lighthouse_result.get("categories", {})

                performance_score = None
                if "performance" in categories:
                    performance_score = categories["performance"].get("score", 0) * 100

                self.results[service] = {
                    "status": "connected",
                    "response_time": response_time,
                    "details": {
                        "test_url": params["url"],
                        "strategy": params["strategy"],
                        "performance_score": performance_score,
                        "lighthouse_version": lighthouse_result.get("lighthouseVersion"),
                        "api_endpoint": url.split("/v5")[0] + "/v5",
                    },
                }

                print(f"✅ Google PageSpeed API connected (response time: {response_time:.3f}s)")
                if performance_score is not None:
                    print(f"   Test analysis completed, performance score: {performance_score:.1f}/100")

                return True
            error_detail = response.text[:200] if response.text else "No error details"
            self.results[service] = {
                "status": "error",
                "error": f"HTTP {response.status_code}: {error_detail}",
            }
            self.errors.append(f"Google PageSpeed API returned HTTP {response.status_code}")
            return False

        except requests.exceptions.Timeout:
            self.results[service] = {
                "status": "timeout",
                "error": "Request timed out (PageSpeed analysis can be slow)",
            }
            self.warnings.append("Google PageSpeed API timed out (this is normal for complex pages)")
            return False
        except Exception as e:
            self.results[service] = {"status": "error", "error": str(e)}
            self.errors.append(f"Google PageSpeed API verification failed: {e}")
            return False

    def verify_openai_integration(self) -> bool:
        """Verify OpenAI API integration"""
        service = "openai"
        print("🤖 Verifying OpenAI integration...")

        try:
            if self.use_stubs:
                url = f"{self.stub_base_url}/openai/v1/chat/completions"
                headers = {"Authorization": "Bearer stub_token"}
            else:
                url = "https://api.openai.com/v1/chat/completions"
                if not self.api_keys["openai"]:
                    self.errors.append("OPENAI_API_KEY not configured")
                    return False
                headers = {"Authorization": f"Bearer {self.api_keys['openai']}"}

            # Test with minimal completion request
            payload = {
                "model": "gpt-4o-mini",
                "messages": [{"role": "user", "content": "Hello"}],
                "max_tokens": 5,
                "temperature": 0,
            }

            start_time = time.time()
            response = requests.post(url, headers=headers, json=payload, timeout=30)
            response_time = time.time() - start_time

            if response.status_code == 200:
                data = response.json()
                usage = data.get("usage", {})

                self.results[service] = {
                    "status": "connected",
                    "response_time": response_time,
                    "details": {
                        "model": payload["model"],
                        "prompt_tokens": usage.get("prompt_tokens", 0),
                        "completion_tokens": usage.get("completion_tokens", 0),
                        "total_tokens": usage.get("total_tokens", 0),
                        "api_endpoint": url.split("/v1")[0] + "/v1",
                    },
                }

                print(f"✅ OpenAI API connected (response time: {response_time:.3f}s)")
                print(f"   Model: {payload['model']}, Tokens used: {usage.get('total_tokens', 0)}")

                return True
            error_detail = response.text[:200] if response.text else "No error details"
            self.results[service] = {
                "status": "error",
                "error": f"HTTP {response.status_code}: {error_detail}",
            }
            self.errors.append(f"OpenAI API returned HTTP {response.status_code}")
            return False

        except Exception as e:
            self.results[service] = {"status": "error", "error": str(e)}
            self.errors.append(f"OpenAI API verification failed: {e}")
            return False

    def verify_stripe_integration(self) -> bool:
        """Verify Stripe payment integration"""
        service = "stripe"
        print("💳 Verifying Stripe integration...")

        try:
            if not self.api_keys["stripe_secret"]:
                self.errors.append("STRIPE_SECRET_KEY not configured")
                return False

            # Check if we're in test mode
            is_test_mode = self.api_keys["stripe_secret"].startswith("sk_test_")

            start_time = time.time()

            # Test account retrieval
            account = stripe.Account.retrieve()

            # Test creating a payment intent (in test mode)
            if is_test_mode:
                payment_intent = stripe.PaymentIntent.create(
                    amount=100,  # $1.00 in cents
                    currency="usd",
                    metadata={"test": "integration_verification"},
                )
                payment_intent_id = payment_intent.id
            else:
                payment_intent_id = "Live mode - not creating test payment"

            response_time = time.time() - start_time

            self.results[service] = {
                "status": "connected",
                "response_time": response_time,
                "details": {
                    "account_id": account.id,
                    "country": account.country,
                    "currency": account.default_currency,
                    "test_mode": is_test_mode,
                    "charges_enabled": account.charges_enabled,
                    "payouts_enabled": account.payouts_enabled,
                    "test_payment_intent": payment_intent_id,
                    "webhook_secret_configured": bool(self.api_keys["stripe_webhook"]),
                },
            }

            print(f"✅ Stripe API connected (response time: {response_time:.3f}s)")
            print(f"   Account: {account.id}, Country: {account.country}")
            print(f"   Mode: {'TEST' if is_test_mode else 'LIVE'}")
            print(f"   Charges enabled: {account.charges_enabled}")

            if not is_test_mode:
                self.warnings.append("Stripe is in LIVE mode - be careful with real transactions")

            if not self.api_keys["stripe_webhook"]:
                self.warnings.append("Stripe webhook secret not configured")

            return True

        except stripe.error.AuthenticationError:
            self.results[service] = {"status": "auth_error", "error": "Invalid API key"}
            self.errors.append("Stripe API key is invalid")
            return False
        except Exception as e:
            self.results[service] = {"status": "error", "error": str(e)}
            self.errors.append(f"Stripe API verification failed: {e}")
            return False

    def verify_sendgrid_integration(self) -> bool:
        """Verify SendGrid email integration"""
        service = "sendgrid"
        print("📧 Verifying SendGrid integration...")

        try:
            if not self.api_keys["sendgrid"]:
                self.errors.append("SENDGRID_API_KEY not configured")
                return False

            # Initialize SendGrid client
            sg = SendGridAPIClient(api_key=self.api_keys["sendgrid"])

            start_time = time.time()

            # Test API key validation by getting account details
            response = sg.client.user.account.get()
            response_time = time.time() - start_time

            if response.status_code == 200:
                account_data = json.loads(response.body)

                # Test sending capabilities by checking templates (doesn't send email)
                templates_response = sg.client.templates.get()
                templates_count = 0
                if templates_response.status_code == 200:
                    templates_data = json.loads(templates_response.body)
                    templates_count = len(templates_data.get("templates", []))

                self.results[service] = {
                    "status": "connected",
                    "response_time": response_time,
                    "details": {
                        "account_type": account_data.get("type", "unknown"),
                        "email": account_data.get("email", "unknown"),
                        "reputation": account_data.get("reputation", 0),
                        "templates_available": templates_count,
                        "api_key_type": "Valid API key" if response.status_code == 200 else "Invalid",
                    },
                }

                print(f"✅ SendGrid API connected (response time: {response_time:.3f}s)")
                print(f"   Account: {account_data.get('email', 'unknown')}")
                print(f"   Type: {account_data.get('type', 'unknown')}")
                print(f"   Templates: {templates_count} available")

                reputation = account_data.get("reputation", 0)
                if reputation < 80:
                    self.warnings.append(f"SendGrid reputation is low: {reputation}%")

                return True
            self.results[service] = {
                "status": "error",
                "error": f"HTTP {response.status_code}",
            }
            self.errors.append(f"SendGrid API returned HTTP {response.status_code}")
            return False

        except Exception as e:
            self.results[service] = {"status": "error", "error": str(e)}
            self.errors.append(f"SendGrid API verification failed: {e}")
            return False

    def test_stub_server(self) -> bool:
        """Test if stub server is available"""
        if not self.use_stubs:
            return True

        print(f"🔧 Testing stub server at {self.stub_base_url}...")

        try:
            response = requests.get(f"{self.stub_base_url}/health", timeout=5)
            if response.status_code == 200:
                print("✅ Stub server is available")
                return True
            self.warnings.append(f"Stub server returned HTTP {response.status_code}")
            return False
        except Exception as e:
            self.warnings.append(f"Stub server not available: {e}")
            return False

    def generate_report(self) -> dict[str, Any]:
        """Generate integration verification report"""
        connected_services = sum(1 for result in self.results.values() if result.get("status") == "connected")
        total_services = len(self.results)

        overall_status = "verified" if connected_services == total_services and not self.errors else "issues"

        report = {
            "timestamp": datetime.utcnow().isoformat(),
            "overall_status": overall_status,
            "test_mode": self.use_stubs,
            "summary": {
                "connected_services": connected_services,
                "total_services": total_services,
                "success_rate": (connected_services / total_services * 100) if total_services > 0 else 0,
            },
            "integrations": self.results,
            "errors": self.errors,
            "warnings": self.warnings,
        }

        return report

    def run_all_verifications(self, services: list[str] = None) -> bool:
        """Run all integration verifications"""
        print("🚀 Starting External Integration Verification")
        print("=" * 60)

        if self.use_stubs:
            print("🔧 Using stub server for testing")
            if not self.test_stub_server():
                print("⚠️  Continuing without stub server...")

        all_services = ["google_pagespeed", "openai", "stripe", "sendgrid"]  # yelp removed per P0-009
        services_to_verify = services or all_services

        verification_methods = {
            # "yelp": removed per P0-009
            "google_pagespeed": self.verify_google_pagespeed_integration,
            "openai": self.verify_openai_integration,
            "stripe": self.verify_stripe_integration,
            "sendgrid": self.verify_sendgrid_integration,
        }

        results = []
        for service in services_to_verify:
            if service in verification_methods:
                try:
                    result = verification_methods[service]()
                    results.append(result)
                except Exception as e:
                    self.errors.append(f"Unexpected error verifying {service}: {e}")
                    results.append(False)
                print()  # Add spacing between checks

        return all(results)


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(description="Verify external API integrations")
    parser.add_argument(
        "--services",
        nargs="+",
        choices=["yelp", "google_pagespeed", "openai", "stripe", "sendgrid"],
        help="Specific services to verify",
    )
    parser.add_argument("--use-stubs", action="store_true", help="Use stub server instead of real APIs")
    parser.add_argument("--json", action="store_true", help="Output results as JSON")

    args = parser.parse_args()

    # Initialize verifier
    verifier = IntegrationVerifier(use_stubs=args.use_stubs)

    # Run verifications
    success = verifier.run_all_verifications(args.services)

    # Generate report
    report = verifier.generate_report()

    if args.json:
        print(json.dumps(report, indent=2))
    else:
        # Print summary
        print("=" * 80)
        print("🎯 INTEGRATION VERIFICATION REPORT")
        print("=" * 80)

        print(f"\n📅 Verification Time: {report['timestamp']}")
        print(f"🔧 Test Mode: {'Stub server' if report['test_mode'] else 'Live APIs'}")
        print(f"🔗 Overall Status: {report['overall_status'].upper()}")
        print(
            f"📊 Success Rate: {report['summary']['connected_services']}/{report['summary']['total_services']} services ({report['summary']['success_rate']:.1f}%)"
        )

        if report["errors"]:
            print(f"\n❌ ERRORS ({len(report['errors'])}):")
            for i, error in enumerate(report["errors"], 1):
                print(f"   {i}. {error}")

        if report["warnings"]:
            print(f"\n⚠️  WARNINGS ({len(report['warnings'])}):")
            for i, warning in enumerate(report["warnings"], 1):
                print(f"   {i}. {warning}")

        if success and not report["errors"]:
            print("\n✅ ALL INTEGRATIONS VERIFIED!")
            print("\n📋 Next Steps:")
            print("   - APIs are ready for production use")
            print("   - Monitor rate limits and quotas")
            print("   - Test end-to-end workflows")
        else:
            print("\n❌ SOME INTEGRATIONS FAILED")
            print("\n📋 Required Actions:")
            print("   - Fix API key configuration")
            print("   - Verify network connectivity")
            print("   - Check service status pages")

    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
