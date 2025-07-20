"""
Test D2 Sourcing Hunter.io Provider

Unit tests for the Hunter.io API client provider
focusing on email discovery and verification functionality.
"""
import pytest

from d2_sourcing.providers.hunter import HunterAPI

# Mark entire module as unit test
pytestmark = pytest.mark.unit


class TestHunterAPI:
    """Test HunterAPI class"""

    def test_hunter_api_initialization_default(self):
        """Test Hunter API initialization with default parameters"""
        hunter = HunterAPI()
        assert hunter.api_key is None

    def test_hunter_api_initialization_with_key(self):
        """Test Hunter API initialization with API key"""
        api_key = "test-api-key-123"
        hunter = HunterAPI(api_key=api_key)
        assert hunter.api_key == api_key

    def test_domain_search_basic(self):
        """Test basic domain search functionality"""
        hunter = HunterAPI(api_key="test-key")
        domain = "example.com"

        result = hunter.domain_search(domain)

        assert isinstance(result, dict)
        assert "data" in result
        assert result["data"]["domain"] == domain
        assert "emails" in result["data"]
        assert "organization" in result["data"]
        assert isinstance(result["data"]["emails"], list)

    def test_domain_search_with_kwargs(self):
        """Test domain search with additional parameters"""
        hunter = HunterAPI()
        domain = "testcompany.com"

        result = hunter.domain_search(domain, limit=10, offset=0, type="personal")

        assert result["data"]["domain"] == domain
        assert isinstance(result["data"]["emails"], list)

    def test_email_finder_basic(self):
        """Test basic email finder functionality"""
        hunter = HunterAPI(api_key="test-key")
        domain = "company.com"
        first_name = "John"
        last_name = "Doe"

        result = hunter.email_finder(domain, first_name, last_name)

        assert isinstance(result, dict)
        assert "data" in result
        assert result["data"]["email"] == "john@company.com"
        assert "score" in result["data"]
        assert "sources" in result["data"]
        assert isinstance(result["data"]["sources"], list)

    def test_email_finder_case_handling(self):
        """Test email finder handles name case correctly"""
        hunter = HunterAPI()
        domain = "example.org"
        first_name = "JANE"  # Uppercase input
        last_name = "SMITH"  # Uppercase input

        result = hunter.email_finder(domain, first_name, last_name)

        # Should normalize to lowercase
        assert result["data"]["email"] == "jane@example.org"

    def test_email_finder_with_kwargs(self):
        """Test email finder with additional parameters"""
        hunter = HunterAPI()
        domain = "startup.io"
        first_name = "Alice"
        last_name = "Johnson"

        result = hunter.email_finder(domain, first_name, last_name, max_duration=10)

        assert result["data"]["email"] == "alice@startup.io"
        assert result["data"]["score"] == 0  # Default mock score

    def test_email_verifier_basic(self):
        """Test basic email verification functionality"""
        hunter = HunterAPI(api_key="test-key")
        email = "test@example.com"

        result = hunter.email_verifier(email)

        assert isinstance(result, dict)
        assert "data" in result
        assert result["data"]["email"] == email
        assert "result" in result["data"]
        assert "score" in result["data"]
        assert result["data"]["result"] == "unknown"  # Default mock result
        assert result["data"]["score"] == 0  # Default mock score

    def test_email_verifier_various_emails(self):
        """Test email verifier with various email formats"""
        hunter = HunterAPI()

        emails = ["user@domain.com", "first.last@company.org", "test123@startup.io", "admin@subdomain.example.com"]

        for email in emails:
            result = hunter.email_verifier(email)
            assert result["data"]["email"] == email
            assert result["data"]["result"] == "unknown"

    def test_email_verifier_with_kwargs(self):
        """Test email verifier with additional parameters"""
        hunter = HunterAPI()
        email = "verify@test.com"

        result = hunter.email_verifier(email, timeout=30, smtp_check=True)

        assert result["data"]["email"] == email
        assert result["data"]["result"] == "unknown"

    def test_multiple_api_operations(self):
        """Test performing multiple API operations in sequence"""
        hunter = HunterAPI(api_key="integration-test-key")
        domain = "multitest.com"

        # Domain search
        domain_result = hunter.domain_search(domain)
        assert domain_result["data"]["domain"] == domain

        # Email finder
        finder_result = hunter.email_finder(domain, "Test", "User")
        assert finder_result["data"]["email"] == "test@multitest.com"

        # Email verifier
        email_to_verify = finder_result["data"]["email"]
        verify_result = hunter.email_verifier(email_to_verify)
        assert verify_result["data"]["email"] == email_to_verify

    def test_api_consistency(self):
        """Test API response consistency across methods"""
        hunter = HunterAPI()

        # All methods should return dict with 'data' key
        domain_result = hunter.domain_search("consistency.com")
        finder_result = hunter.email_finder("consistency.com", "Test", "Case")
        verify_result = hunter.email_verifier("test@consistency.com")

        assert isinstance(domain_result, dict) and "data" in domain_result
        assert isinstance(finder_result, dict) and "data" in finder_result
        assert isinstance(verify_result, dict) and "data" in verify_result

    def test_api_key_persistence(self):
        """Test that API key is maintained across operations"""
        api_key = "persistent-key-123"
        hunter = HunterAPI(api_key=api_key)

        # Perform multiple operations
        hunter.domain_search("keytest.com")
        hunter.email_finder("keytest.com", "Key", "Test")
        hunter.email_verifier("key@keytest.com")

        # API key should remain unchanged
        assert hunter.api_key == api_key

    def test_empty_string_handling(self):
        """Test handling of empty string inputs"""
        hunter = HunterAPI()

        # Test with empty domain
        result = hunter.domain_search("")
        assert result["data"]["domain"] == ""

        # Test with empty names
        result = hunter.email_finder("test.com", "", "")
        assert result["data"]["email"] == "@test.com"

        # Test with empty email
        result = hunter.email_verifier("")
        assert result["data"]["email"] == ""

    def test_special_character_handling(self):
        """Test handling of special characters in inputs"""
        hunter = HunterAPI()

        # Test domain with special characters
        domain = "test-company.co.uk"
        result = hunter.domain_search(domain)
        assert result["data"]["domain"] == domain

        # Test names with special characters
        result = hunter.email_finder("company.com", "Jean-Luc", "O'Connor")
        assert "jean-luc@company.com" == result["data"]["email"]

        # Test email with plus addressing
        email = "user+tag@domain.com"
        result = hunter.email_verifier(email)
        assert result["data"]["email"] == email
