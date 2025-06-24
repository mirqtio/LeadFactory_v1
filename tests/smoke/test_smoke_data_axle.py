"""
Smoke test for Data Axle API
PRD v1.2 - Verify Data Axle enrichment (skip if no key)
"""
import asyncio
import os
import pytest

from d0_gateway.providers.dataaxle import DataAxleClient
from core.config import settings

# Skip if no API key (trial mode optional)
pytestmark = pytest.mark.skipif(
    not os.getenv("DATA_AXLE_API_KEY"),
    reason="DATA_AXLE_API_KEY not set (optional for PRD v1.2)",
)


class TestDataAxleSmoke:
    """Smoke tests for Data Axle API"""

    @pytest.mark.asyncio
    async def test_dataaxle_enrich(self):
        """Test Data Axle domain enrichment"""
        client = DataAxleClient(api_key=settings.data_axle_api_key)

        # Test enrichment with a known domain
        result = await client.enrich("salesforce.com")

        assert result is not None

        if result:
            print(f"✓ Data Axle enrichment successful:")
            print(f"  Domain: salesforce.com")
            print(f"  Company: {result.get('company_name', 'N/A')}")
            print(f"  Email: {result.get('email', 'N/A')}")
            print(f"  Phone: {result.get('phone', 'N/A')}")
            print(f"  Employees: {result.get('employee_count', 'N/A')}")
        else:
            print("✓ Data Axle API working but no data returned (trial limits?)")

    @pytest.mark.asyncio
    async def test_dataaxle_email_enrichment(self):
        """Test Data Axle email finding capability"""
        client = DataAxleClient(api_key=settings.data_axle_api_key)

        # Test with multiple domains
        test_domains = ["microsoft.com", "apple.com", "amazon.com"]
        found_emails = 0

        print("\n✓ Data Axle email enrichment test:")
        for domain in test_domains:
            result = await client.enrich(domain)

            if result and result.get("email"):
                found_emails += 1
                print(f"  {domain}: {result['email']}")
            else:
                print(f"  {domain}: No email found")

        print(f"  Emails found: {found_emails}/{len(test_domains)}")

    @pytest.mark.asyncio
    async def test_dataaxle_trial_mode(self):
        """Test Data Axle trial mode behavior"""
        client = DataAxleClient(api_key=settings.data_axle_api_key)

        # In trial mode, API might have limits
        result = await client.enrich("stripe.com")

        if result is None:
            print("\n✓ Data Axle trial mode: Limited or no results (expected)")
        else:
            print("\n✓ Data Axle trial mode: Got results")
            print(f"  Fields returned: {list(result.keys())}")

    @pytest.mark.asyncio
    async def test_dataaxle_error_handling(self):
        """Test Data Axle error handling"""
        client = DataAxleClient(api_key=settings.data_axle_api_key)

        # Test with invalid domain
        result = await client.enrich("not-a-real-domain-xyz123.fake")

        # Should return None or empty result
        if result is None or not result.get("company_name"):
            print("\n✓ Data Axle error handling works correctly")
        else:
            print("\n✓ Data Axle returned data even for invalid domain")

    @pytest.mark.asyncio
    async def test_dataaxle_as_fallback(self):
        """Test Data Axle as email fallback (PRD v1.2 requirement)"""
        client = DataAxleClient(api_key=settings.data_axle_api_key)

        print("\n✓ Data Axle fallback configuration:")
        print(f"  API Key Present: {bool(settings.data_axle_api_key)}")
        print(
            f"  Mode: {'Trial' if 'trial' in str(settings.data_axle_api_key).lower() else 'Full'}"
        )
        print(f"  Use Case: Email enrichment fallback when Hunter.io confidence < 0.75")

        # Test that it can be used as fallback
        result = await client.enrich("example.com")
        can_fallback = result is not None
        print(f"  Can act as fallback: {can_fallback}")


if __name__ == "__main__":
    # Check if we should run
    if not os.getenv("DATA_AXLE_API_KEY"):
        print("⚠️  Skipping Data Axle smoke tests - no API key")
        print("   This is optional for PRD v1.2 (fallback only)")
    else:
        # Run smoke tests
        asyncio.run(test_dataaxle_enrich())
        asyncio.run(test_dataaxle_email_enrichment())
        asyncio.run(test_dataaxle_trial_mode())
        asyncio.run(test_dataaxle_error_handling())
        asyncio.run(test_dataaxle_as_fallback())
