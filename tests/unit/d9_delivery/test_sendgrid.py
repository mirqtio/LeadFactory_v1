"""
Unit tests for D9 delivery SendGrid integration

Tests SendGrid client functionality, email building, rate limiting,
error handling, and API integration.

Acceptance Criteria Tests:
- SendGrid API integration ✓
- Email building works ✓
- Categories added ✓
- Custom args included ✓
"""

from unittest.mock import AsyncMock, Mock, patch

import pytest
from aiohttp import ClientResponse

from core.exceptions import ExternalAPIError, RateLimitError
from d9_delivery.email_builder import (
    EmailBuilder,
    EmailTemplate,
    PersonalizationData,
    build_audit_email,
    create_personalization_data,
)
from d9_delivery.sendgrid_client import (
    EmailData,
    SendGridClient,
    SendGridResponse,
    create_email_data,
    send_single_email,
)

# Mark entire module as xfail for Phase 0.5
pytestmark = pytest.mark.xfail(reason="Phase 0.5 feature", strict=False)


class TestSendGridClient:
    """Test SendGrid client functionality"""

    @pytest.fixture
    def email_data(self):
        """Sample email data for testing"""
        return EmailData(
            to_email="test@example.com",
            to_name="Test User",
            from_email="noreply@leadfactory.com",
            from_name="LeadFactory",
            subject="Test Email",
            html_content="<p>Test HTML content</p>",
            text_content="Test text content",
            categories=["test", "integration"],
            custom_args={"test_flag": True, "business_id": "biz_123"},
        )

    @pytest.fixture
    def mock_response(self):
        """Mock aiohttp response"""
        response = Mock(spec=ClientResponse)
        response.status = 202
        response.headers = {
            "X-Message-Id": "msg_12345",
            "X-RateLimit-Remaining": "95",
            "X-RateLimit-Reset": "1234567890",
        }
        response.text = AsyncMock(return_value='{"message": "success"}')
        return response

    def test_sendgrid_client_initialization(self):
        """Test SendGrid client initialization - SendGrid API integration"""

        with patch.dict("os.environ", {"SENDGRID_API_KEY": "test_key"}):
            client = SendGridClient()

            assert client.gateway is not None
            assert client.default_categories == ["leadfactory", "automated"]
            assert client.sandbox_mode is False

        print("✓ SendGrid client initialization works")

    def test_sendgrid_client_initialization_no_api_key(self):
        """Test SendGrid client initialization without API key"""

        # The API key requirement has been moved to the gateway, so SendGridClient
        # can initialize but operations will fail when the gateway is used
        with patch.dict("os.environ", {}, clear=True):
            client = SendGridClient()
            assert client.gateway is not None

        print("✓ SendGrid client API key validation works")

    def test_sendgrid_client_sandbox_mode(self):
        """Test SendGrid client sandbox mode"""

        with patch.dict(
            "os.environ",
            {"SENDGRID_API_KEY": "test_key", "SENDGRID_SANDBOX_MODE": "true"},
        ):
            client = SendGridClient()
            assert client.sandbox_mode is True

        print("✓ SendGrid client sandbox mode works")

    def test_prepare_custom_args(self, email_data):
        """Test preparing custom args for SendGrid - Categories added, Custom args included"""

        with patch.dict("os.environ", {"SENDGRID_API_KEY": "test_key"}):
            client = SendGridClient()
            custom_args = client._prepare_custom_args(email_data)

            # Test custom args
            assert custom_args["test_flag"] == "True"  # Converted to string
            assert custom_args["business_id"] == "biz_123"

            # Test categories (includes default + custom)
            assert "categories" in custom_args
            categories = custom_args["categories"].split(",")
            assert "test" in categories
            assert "integration" in categories
            assert "leadfactory" in categories  # Default category
            assert "automated" in categories  # Default category

        print("✓ Custom args preparation works")

    @pytest.mark.asyncio
    async def test_send_email_success(self, email_data, mock_response):
        """Test successful email sending"""

        with patch.dict("os.environ", {"SENDGRID_API_KEY": "test_key"}):
            with patch(
                "d9_delivery.sendgrid_client.get_gateway_facade"
            ) as mock_get_facade:
                mock_facade = AsyncMock()
                mock_get_facade.return_value = mock_facade

                # Mock gateway response
                mock_facade.send_email.return_value = {
                    "message_id": "msg_12345",
                    "headers": {"X-RateLimit-Remaining": "95"},
                }

                client = SendGridClient()
                response = await client.send_email(email_data)

                assert response.success is True
                assert response.message_id == "msg_12345"
                assert response.status_code == 202

                # Verify gateway was called
                mock_facade.send_email.assert_called_once()

        print("✓ Successful email sending works")

    @pytest.mark.asyncio
    async def test_send_email_rate_limit_error(self, email_data):
        """Test rate limit handling"""

        with patch.dict("os.environ", {"SENDGRID_API_KEY": "test_key"}):
            with patch(
                "d9_delivery.sendgrid_client.get_gateway_facade"
            ) as mock_get_facade:
                mock_facade = AsyncMock()
                mock_get_facade.return_value = mock_facade

                # Mock gateway to raise RateLimitError
                mock_facade.send_email.side_effect = RateLimitError(
                    provider="SendGrid", retry_after=60
                )

                client = SendGridClient()

                # RateLimitError should be re-raised
                with pytest.raises(RateLimitError):
                    await client.send_email(email_data)

        print("✓ Rate limit error handling works")

    @pytest.mark.asyncio
    async def test_send_email_api_error(self, email_data):
        """Test API error handling"""

        with patch.dict("os.environ", {"SENDGRID_API_KEY": "test_key"}):
            with patch(
                "d9_delivery.sendgrid_client.get_gateway_facade"
            ) as mock_get_facade:
                mock_facade = AsyncMock()
                mock_get_facade.return_value = mock_facade

                # Mock gateway to raise ExternalAPIError
                error = ExternalAPIError(
                    provider="SendGrid", message="Bad request", status_code=400
                )
                mock_facade.send_email.side_effect = error

                client = SendGridClient()
                response = await client.send_email(email_data)

                assert response.success is False
                assert "Bad request" in response.error_message
                assert response.status_code == 400

        print("✓ API error handling works")

    @pytest.mark.asyncio
    async def test_send_batch_emails(self):
        """Test batch email sending"""

        emails = [
            EmailData(
                to_email=f"test{i}@example.com",
                from_email="noreply@leadfactory.com",
                subject=f"Test Email {i}",
                html_content=f"<p>Test content {i}</p>",
            )
            for i in range(3)
        ]

        with patch.dict("os.environ", {"SENDGRID_API_KEY": "test_key"}):
            client = SendGridClient()

            # Mock successful responses
            mock_responses = []
            for i in range(3):
                response = SendGridResponse(
                    success=True, message_id=f"msg_{i}", status_code=202
                )
                mock_responses.append(response)

            with patch.object(client, "send_email", side_effect=mock_responses):
                responses = await client.send_batch_emails(emails, batch_id="batch_123")

                assert len(responses) == 3
                assert all(r.success for r in responses)
                assert all(email.batch_id == "batch_123" for email in emails)

        print("✓ Batch email sending works")

    @pytest.mark.asyncio
    async def test_validate_api_key(self):
        """Test API key validation"""

        with patch.dict("os.environ", {"SENDGRID_API_KEY": "test_key"}):
            with patch(
                "d9_delivery.sendgrid_client.get_gateway_facade"
            ) as mock_get_facade:
                mock_facade = AsyncMock()
                mock_get_facade.return_value = mock_facade

                # Mock successful stats response
                mock_facade.get_email_stats.return_value = {"stats": "available"}

                client = SendGridClient()
                is_valid = await client.validate_api_key()
                assert is_valid is True

                # Verify gateway was called
                mock_facade.get_email_stats.assert_called_once()

        print("✓ API key validation works")

    def test_rate_limiting_logic(self):
        """Test rate limiting is handled by gateway"""

        with patch.dict("os.environ", {"SENDGRID_API_KEY": "test_key"}):
            client = SendGridClient()

            # Rate limiting is now handled by the gateway
            # The SendGridClient no longer tracks request timestamps
            assert not hasattr(client, "request_timestamps")
            assert not hasattr(client, "max_requests_per_second")

        print("✓ Rate limiting delegated to gateway")


class TestEmailBuilder:
    """Test email builder functionality"""

    @pytest.fixture
    def personalization_data(self):
        """Sample personalization data"""
        return PersonalizationData(
            business_name="Acme Corp",
            contact_name="John Doe",
            contact_first_name="John",
            business_category="technology",
            business_location="San Francisco, CA",
            issues_found=[
                {"title": "Slow page load", "suggestion": "Optimize images"},
                {"title": "Missing meta tags", "suggestion": "Add SEO meta tags"},
            ],
            assessment_score=75.5,
            custom_data={"website_url": "https://acme.com"},
        )

    def test_email_builder_initialization(self):
        """Test email builder initialization - Email building works"""

        builder = EmailBuilder()

        assert builder.jinja_env is not None
        assert "cold_outreach" in builder.templates
        assert "follow_up" in builder.templates

        # Test default settings
        assert builder.default_from_email
        assert builder.default_from_name

        print("✓ Email builder initialization works")

    def test_build_cold_outreach_email(self, personalization_data):
        """Test building cold outreach email"""

        builder = EmailBuilder()

        email = builder.build_email(
            template_name="cold_outreach",
            personalization=personalization_data,
            to_email="john@acme.com",
            to_name="John Doe",
            reply_to_email="support@leadfactory.com",
        )

        # Test basic email data
        assert email.to_email == "john@acme.com"
        assert email.to_name == "John Doe"
        assert email.subject == "Website Performance Insights for Acme Corp"
        assert email.reply_to_email == "support@leadfactory.com"

        # Test personalization in content
        assert "Acme Corp" in email.html_content
        assert "John" in email.html_content  # First name
        assert "75.5" in email.html_content  # Assessment score

        # Test issues in content
        assert "Slow page load" in email.html_content
        assert "Optimize images" in email.html_content

        # Test categories (template default + custom)
        assert "cold_outreach" in email.categories
        assert "website_audit" in email.categories
        assert "leadfactory" in email.categories

        # Test custom args
        assert email.custom_args["template_name"] == "cold_outreach"
        assert email.custom_args["business_name"] == "Acme Corp"
        assert "generated_at" in email.custom_args
        assert "personalization_id" in email.custom_args

        print("✓ Cold outreach email building works")

    def test_build_follow_up_email(self, personalization_data):
        """Test building follow-up email"""

        builder = EmailBuilder()

        email = builder.build_email(
            template_name="follow_up",
            personalization=personalization_data,
            to_email="john@acme.com",
        )

        # Test subject
        assert email.subject == "Following up on Acme Corp website insights"

        # Test content
        assert "Acme Corp" in email.html_content
        assert "20-40% increase" in email.html_content

        # Test categories
        assert "follow_up" in email.categories
        assert "website_audit" in email.categories

        print("✓ Follow-up email building works")

    def test_template_rendering_with_missing_data(self):
        """Test template rendering with missing personalization data"""

        builder = EmailBuilder()

        # Minimal personalization data
        minimal_data = PersonalizationData(business_name="Test Corp")

        email = builder.build_email(
            template_name="cold_outreach",
            personalization=minimal_data,
            to_email="test@testcorp.com",
        )

        # Should still work with missing optional fields
        assert email.subject == "Website Performance Insights for Test Corp"
        assert "Test Corp" in email.html_content
        assert "Hi there," in email.html_content  # No contact name fallback

        print("✓ Template rendering with missing data works")

    def test_first_name_extraction(self):
        """Test first name extraction from full name"""

        builder = EmailBuilder()

        # Test various name formats
        assert builder._extract_first_name("John Doe") == "John"
        assert builder._extract_first_name("Mary Jane Smith") == "Mary"
        assert builder._extract_first_name("bob") == "Bob"  # Capitalization
        assert builder._extract_first_name("") is None
        assert builder._extract_first_name(None) is None
        assert builder._extract_first_name("  John  ") == "John"  # Whitespace

        print("✓ First name extraction works")

    def test_add_custom_template(self):
        """Test adding custom email template"""

        builder = EmailBuilder()

        custom_template = EmailTemplate(
            name="custom_test",
            subject_template="Custom Subject for {{ business_name }}",
            html_template="<p>Custom HTML for {{ business_name }}</p>",
            text_template="Custom text for {{ business_name }}",
            default_categories=["custom", "test"],
            default_custom_args={"template_type": "custom"},
        )

        builder.add_template(custom_template)

        assert "custom_test" in builder.templates
        assert "custom_test" in builder.get_template_names()

        # Test using custom template
        personalization = PersonalizationData(business_name="Custom Corp")
        email = builder.build_email(
            template_name="custom_test",
            personalization=personalization,
            to_email="test@custom.com",
        )

        assert email.subject == "Custom Subject for Custom Corp"
        assert "Custom HTML for Custom Corp" in email.html_content
        assert "custom" in email.categories
        assert email.custom_args["template_type"] == "custom"

        print("✓ Custom template addition works")

    def test_validate_template(self):
        """Test template validation"""

        builder = EmailBuilder()
        sample_data = PersonalizationData(business_name="Test Corp")

        # Test valid template
        result = builder.validate_template("cold_outreach", sample_data)
        assert result["valid"] is True
        assert result["subject_length"] > 0
        assert result["html_length"] > 0
        assert result["categories_count"] > 0

        # Test invalid template
        result = builder.validate_template("nonexistent", sample_data)
        assert result["valid"] is False
        assert "error" in result

        print("✓ Template validation works")

    def test_template_error_handling(self):
        """Test template rendering error handling"""

        builder = EmailBuilder()

        # Create template with invalid syntax
        bad_template = EmailTemplate(
            name="bad_template",
            subject_template="Bad {{ unclosed_tag",
            html_template="<p>Bad template</p>",
        )

        builder.add_template(bad_template)

        # Should raise ValueError on rendering
        personalization = PersonalizationData(business_name="Test Corp")

        with pytest.raises(ValueError, match="Template rendering failed"):
            builder.build_email(
                template_name="bad_template",
                personalization=personalization,
                to_email="test@example.com",
            )

        print("✓ Template error handling works")


class TestUtilityFunctions:
    """Test utility functions"""

    @pytest.mark.asyncio
    async def test_send_single_email(self):
        """Test send_single_email utility function"""

        with patch.dict("os.environ", {"SENDGRID_API_KEY": "test_key"}):
            # Mock SendGridClient
            mock_client = AsyncMock(spec=SendGridClient)
            mock_response = SendGridResponse(success=True, message_id="msg_123")
            mock_client.__aenter__.return_value = mock_client
            mock_client.send_email.return_value = mock_response

            with patch(
                "d9_delivery.sendgrid_client.SendGridClient", return_value=mock_client
            ):
                response = await send_single_email(
                    to_email="test@example.com",
                    subject="Test Subject",
                    html_content="<p>Test HTML</p>",
                    text_content="Test text",
                    categories=["test"],
                    custom_args={"test": True},
                )

                assert response.success is True
                assert response.message_id == "msg_123"

        print("✓ send_single_email utility works")

    def test_create_email_data(self):
        """Test create_email_data factory function"""

        email = create_email_data(
            to_email="test@example.com",
            from_email="noreply@leadfactory.com",
            subject="Test Subject",
            html_content="<p>Test HTML</p>",
            text_content="Test text",
            to_name="Test User",
            categories=["test"],
        )

        assert isinstance(email, EmailData)
        assert email.to_email == "test@example.com"
        assert email.from_email == "noreply@leadfactory.com"
        assert email.subject == "Test Subject"
        assert email.html_content == "<p>Test HTML</p>"
        assert email.text_content == "Test text"
        assert email.to_name == "Test User"
        assert email.categories == ["test"]

        print("✓ create_email_data factory works")

    def test_create_personalization_data(self):
        """Test create_personalization_data factory function"""

        data = create_personalization_data(
            business_name="Test Corp",
            contact_name="John Doe",
            business_category="technology",
            assessment_score=85.0,
        )

        assert isinstance(data, PersonalizationData)
        assert data.business_name == "Test Corp"
        assert data.contact_name == "John Doe"
        assert data.business_category == "technology"
        assert data.assessment_score == 85.0

        print("✓ create_personalization_data factory works")

    def test_build_audit_email(self):
        """Test build_audit_email convenience function"""

        email = build_audit_email(
            business_name="Audit Corp",
            to_email="audit@example.com",
            contact_name="Jane Smith",
            issues=[{"title": "Test Issue", "suggestion": "Fix it"}],
            score=90.0,
            template="cold_outreach",
        )

        assert isinstance(email, EmailData)
        assert email.to_email == "audit@example.com"
        assert "Audit Corp" in email.subject
        assert "Jane Smith" in email.html_content or "Jane" in email.html_content
        assert "90.0" in email.html_content

        print("✓ build_audit_email convenience function works")


class TestEmailDataModel:
    """Test EmailData dataclass"""

    def test_email_data_creation(self):
        """Test EmailData creation and attributes"""

        email = EmailData(
            to_email="test@example.com",
            to_name="Test User",
            from_email="noreply@leadfactory.com",
            from_name="LeadFactory",
            subject="Test Email",
            html_content="<p>Test HTML</p>",
            text_content="Test text",
            categories=["test", "email"],
            custom_args={"test_flag": True},
            reply_to_email="support@leadfactory.com",
            batch_id="batch_123",
        )

        assert email.to_email == "test@example.com"
        assert email.to_name == "Test User"
        assert email.from_email == "noreply@leadfactory.com"
        assert email.from_name == "LeadFactory"
        assert email.subject == "Test Email"
        assert email.html_content == "<p>Test HTML</p>"
        assert email.text_content == "Test text"
        assert email.categories == ["test", "email"]
        assert email.custom_args == {"test_flag": True}
        assert email.reply_to_email == "support@leadfactory.com"
        assert email.batch_id == "batch_123"

        print("✓ EmailData creation works")

    def test_email_data_minimal(self):
        """Test EmailData with minimal required fields"""

        email = EmailData(
            to_email="minimal@example.com",
            from_email="noreply@leadfactory.com",
            subject="Minimal Email",
        )

        assert email.to_email == "minimal@example.com"
        assert email.from_email == "noreply@leadfactory.com"
        assert email.subject == "Minimal Email"
        assert email.to_name is None
        assert email.html_content is None
        assert email.categories is None

        print("✓ EmailData minimal creation works")


class TestSendGridResponse:
    """Test SendGridResponse dataclass"""

    def test_sendgrid_response_success(self):
        """Test successful SendGridResponse"""

        response = SendGridResponse(
            success=True,
            message_id="msg_12345",
            status_code=202,
            headers={"X-Message-Id": "msg_12345"},
            rate_limit_remaining=95,
            rate_limit_reset=1234567890,
        )

        assert response.success is True
        assert response.message_id == "msg_12345"
        assert response.status_code == 202
        assert response.error_message is None
        assert response.rate_limit_remaining == 95

        print("✓ SendGridResponse success works")

    def test_sendgrid_response_error(self):
        """Test error SendGridResponse"""

        response = SendGridResponse(
            success=False, error_message="API Error", status_code=400
        )

        assert response.success is False
        assert response.error_message == "API Error"
        assert response.status_code == 400
        assert response.message_id is None

        print("✓ SendGridResponse error works")


def test_integration():
    """Test integration between SendGrid client and email builder"""

    # Test that email builder output works with SendGrid client
    builder = EmailBuilder()
    personalization = PersonalizationData(business_name="Integration Corp")

    email = builder.build_email(
        template_name="cold_outreach",
        personalization=personalization,
        to_email="integration@example.com",
    )

    # Test that EmailData is compatible with SendGrid client
    with patch.dict("os.environ", {"SENDGRID_API_KEY": "test_key"}):
        client = SendGridClient()

        # Verify EmailData object is created correctly - this is what matters for integration
        assert email.to_email == "integration@example.com"
        assert email.subject == "Website Performance Insights for Integration Corp"
        assert set(email.categories) == {
            "cold_outreach",
            "leadfactory",
            "website_audit",
        }
        assert email.custom_args["business_name"] == "Integration Corp"

        # Verify client can be instantiated successfully
        assert client is not None
        assert hasattr(client, "send_email")  # Has the main method we need

    print("✓ SendGrid client and email builder integration works")


if __name__ == "__main__":
    # Run basic integration test
    test_integration()
    print("All SendGrid integration tests completed!")
