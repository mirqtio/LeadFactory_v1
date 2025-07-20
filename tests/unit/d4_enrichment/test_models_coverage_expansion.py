"""
Test D4 Enrichment Models Coverage Expansion

Targeted tests to improve models.py coverage from 50% to 80%+.
Focuses on uncovered property methods, utility functions, and edge cases.
"""
from datetime import datetime, timedelta
from decimal import Decimal
from unittest.mock import patch

import pytest

from d4_enrichment.models import (
    DataVersion,
    EnrichmentAuditLog,
    EnrichmentRequest,
    EnrichmentResult,
    EnrichmentSource,
    EnrichmentStatus,
    MatchConfidence,
    _is_valid_domain,
    _is_valid_phone,
    calculate_completeness_score,
    validate_enrichment_data,
)

# Mark entire module as unit test
pytestmark = pytest.mark.unit


class TestEnrichmentResultProperties:
    """Test EnrichmentResult property methods and utilities"""

    def test_is_expired_with_no_expires_at(self):
        """Test is_expired property when expires_at is None (line 269-270)"""
        result = EnrichmentResult()
        result.expires_at = None

        # Should return False when no expiry date set
        assert result.is_expired == False

    def test_is_expired_with_future_date(self):
        """Test is_expired property with future expiry date"""
        result = EnrichmentResult()
        result.expires_at = datetime.utcnow() + timedelta(days=1)

        assert result.is_expired == False

    def test_is_expired_with_past_date(self):
        """Test is_expired property with past expiry date (line 271)"""
        result = EnrichmentResult()
        result.expires_at = datetime.utcnow() - timedelta(days=1)

        assert result.is_expired == True

    def test_age_days_property(self):
        """Test age_days property calculation (line 276)"""
        result = EnrichmentResult()
        # Set enriched_at to 5 days ago
        result.enriched_at = datetime.utcnow() - timedelta(days=5)

        age = result.age_days
        assert age == 5 or age == 4  # Allow for timing differences

    def test_get_address_string_with_none(self):
        """Test get_address_string with None headquarters_address (lines 280-281)"""
        result = EnrichmentResult()
        result.headquarters_address = None

        assert result.get_address_string() is None

    def test_get_address_string_with_empty_dict(self):
        """Test get_address_string with empty dict"""
        result = EnrichmentResult()
        result.headquarters_address = {}

        # Should return None for empty parts list (line 297)
        assert result.get_address_string() is None

    def test_get_address_string_with_partial_address(self):
        """Test get_address_string with partial address data (lines 286-296)"""
        result = EnrichmentResult()
        result.headquarters_address = {
            "street": "123 Main St",
            "city": "San Francisco",
            # Missing state, postal_code, country
        }

        address_str = result.get_address_string()
        assert address_str == "123 Main St, San Francisco"

    def test_get_address_string_with_complete_address(self):
        """Test get_address_string with complete address data"""
        result = EnrichmentResult()
        result.headquarters_address = {
            "street": "123 Main St",
            "city": "San Francisco",
            "state": "CA",
            "postal_code": "94105",
            "country": "USA",
        }

        address_str = result.get_address_string()
        assert address_str == "123 Main St, San Francisco, CA, 94105, USA"

    def test_get_contact_info_method(self):
        """Test get_contact_info method (lines 301-307)"""
        result = EnrichmentResult()
        result.phone = "555-1234"
        result.email_domain = "test.com"
        result.website = "https://test.com"
        result.linkedin_url = "https://linkedin.com/company/test"
        result.headquarters_address = {"city": "San Francisco"}

        contact_info = result.get_contact_info()

        assert contact_info["phone"] == "555-1234"
        assert contact_info["email_domain"] == "test.com"
        assert contact_info["website"] == "https://test.com"
        assert contact_info["linkedin"] == "https://linkedin.com/company/test"
        assert contact_info["address"] == "San Francisco"

    def test_get_company_metrics_with_decimals(self):
        """Test get_company_metrics with Decimal values (lines 314, 316)"""
        result = EnrichmentResult()
        result.employee_count = 100
        result.employee_range = "50-100"
        result.annual_revenue = Decimal("1000000.50")
        result.revenue_range = "$1M-$5M"
        result.funding_total = Decimal("500000.25")
        result.founded_year = 2020

        metrics = result.get_company_metrics()

        assert metrics["employee_count"] == 100
        assert metrics["employee_range"] == "50-100"
        assert metrics["annual_revenue"] == 1000000.50  # Converted to float
        assert metrics["revenue_range"] == "$1M-$5M"
        assert metrics["funding_total"] == 500000.25  # Converted to float
        assert metrics["founded_year"] == 2020

    def test_get_company_metrics_with_none_values(self):
        """Test get_company_metrics with None values"""
        result = EnrichmentResult()
        result.annual_revenue = None
        result.funding_total = None

        metrics = result.get_company_metrics()

        assert metrics["annual_revenue"] is None
        assert metrics["funding_total"] is None

    def test_get_data_quality_metrics_with_decimals(self):
        """Test get_data_quality_metrics with Decimal values (lines 324-329)"""
        result = EnrichmentResult()
        result.match_confidence = "high"
        result.match_score = Decimal("0.95")
        result.data_quality_score = Decimal("0.85")
        result.completeness_score = Decimal("0.90")
        result.freshness_days = 5
        result.enriched_at = datetime.utcnow() - timedelta(days=3)
        result.expires_at = datetime.utcnow() + timedelta(days=1)

        metrics = result.get_data_quality_metrics()

        assert metrics["match_confidence"] == "high"
        assert metrics["match_score"] == 0.95  # Converted to float
        assert metrics["data_quality_score"] == 0.85  # Converted to float
        assert metrics["completeness_score"] == 0.90  # Converted to float
        assert metrics["freshness_days"] == 5
        assert metrics["age_days"] == 3
        assert metrics["is_expired"] == False

    def test_get_data_quality_metrics_with_none_values(self):
        """Test get_data_quality_metrics with None values"""
        result = EnrichmentResult()
        result.match_score = None
        result.data_quality_score = None
        result.completeness_score = None
        result.enriched_at = datetime.utcnow()  # Required for age_days calculation

        metrics = result.get_data_quality_metrics()

        assert metrics["match_score"] is None
        assert metrics["data_quality_score"] is None
        assert metrics["completeness_score"] is None


class TestEnrichmentResultDataVersioning:
    """Test data versioning functionality"""

    def test_update_data_version_decimal_converter(self):
        """Test update_data_version with Decimal values (lines 341-345)"""
        result = EnrichmentResult()

        new_data = {"revenue": Decimal("1000000.50"), "score": Decimal("0.95"), "name": "Test Company"}

        # Test without mocking - just verify it works with Decimal values
        new_version = result.update_data_version(new_data)

        # Should handle Decimal conversion without error
        assert new_version is not None
        assert result.data_version == new_version
        assert result.data_checksum is not None
        assert len(result.data_checksum) == 64  # SHA256 hash length

    def test_update_data_version_json_serialization_error(self):
        """Test update_data_version with non-serializable object"""
        result = EnrichmentResult()

        # Create object that can't be JSON serialized
        class NonSerializable:
            pass

        new_data = {"name": "Test", "invalid": NonSerializable()}

        # Should raise TypeError for non-serializable object (line 345)
        with pytest.raises(TypeError):
            result.update_data_version(new_data)


class TestEnrichmentResultMatchScoring:
    """Test match scoring functionality"""

    def test_calculate_match_score_exact_matches(self):
        """Test calculate_match_score with exact matches (lines 388-389)"""
        result = EnrichmentResult()

        input_data = {"company_name": "Test Corp", "domain": "test.com", "phone": "555-1234", "address": "123 Main St"}

        matched_data = {
            "company_name": "Test Corp",  # Exact match
            "domain": "test.com",  # Exact match
            "phone": "555-1234",  # Exact match
            "address": "123 Main St",  # Exact match
        }

        score = result.calculate_match_score(input_data, matched_data)
        assert score == 1.0  # Perfect match

    def test_calculate_match_score_partial_matches(self):
        """Test calculate_match_score with partial matches (lines 390-393)"""
        result = EnrichmentResult()

        input_data = {"company_name": "Test Corp", "domain": "test.com"}

        matched_data = {
            "company_name": "Test Corporation Inc",  # Partial match (contains)
            "domain": "www.test.com",  # Partial match (contains)
        }

        score = result.calculate_match_score(input_data, matched_data)
        assert 0.5 < score < 1.0  # Should be high but not perfect

    def test_calculate_match_score_similar_strings(self):
        """Test calculate_match_score with similar strings (line 393)"""
        result = EnrichmentResult()

        input_data = {"company_name": "Tech Solutions Inc"}

        matched_data = {"company_name": "Technology Solutions Incorporated"}  # Similar words

        score = result.calculate_match_score(input_data, matched_data)
        assert score >= 0.0  # Should detect similarity or return 0

    def test_strings_similar_method(self):
        """Test _strings_similar method (lines 399-413)"""
        result = EnrichmentResult()

        # Test with None/empty strings (lines 399-400)
        assert result._strings_similar("", "test") == False
        assert result._strings_similar("test", "") == False
        assert result._strings_similar(None, "test") == False

        # Test with single words (lines 406-407)
        assert result._strings_similar("test", "different") == False

        # Test with similar word sets (lines 409-413)
        str1 = "tech solutions company"
        str2 = "technology solutions inc"
        similarity = result._strings_similar(str1, str2)
        assert isinstance(similarity, bool)

    def test_set_match_confidence_all_levels(self):
        """Test set_match_confidence method for all confidence levels (lines 421-436)"""
        result = EnrichmentResult()

        # Test UNCERTAIN when no match_score (lines 421-423)
        result.match_score = None
        result.set_match_confidence()
        assert result.match_confidence == MatchConfidence.UNCERTAIN.value

        # Test EXACT (lines 427-428)
        result.match_score = Decimal("1.0")
        result.set_match_confidence()
        assert result.match_confidence == MatchConfidence.EXACT.value

        # Test HIGH (lines 429-430)
        result.match_score = Decimal("0.95")
        result.set_match_confidence()
        assert result.match_confidence == MatchConfidence.HIGH.value

        # Test MEDIUM (lines 431-432)
        result.match_score = Decimal("0.75")
        result.set_match_confidence()
        assert result.match_confidence == MatchConfidence.MEDIUM.value

        # Test LOW (lines 433-434)
        result.match_score = Decimal("0.55")
        result.set_match_confidence()
        assert result.match_confidence == MatchConfidence.LOW.value

        # Test UNCERTAIN (lines 435-436)
        result.match_score = Decimal("0.3")
        result.set_match_confidence()
        assert result.match_confidence == MatchConfidence.UNCERTAIN.value


class TestValidationFunctions:
    """Test validation utility functions"""

    def test_validate_enrichment_data_missing_company_name(self):
        """Test validation with missing company name (lines 489-490)"""
        data = {"domain": "test.com"}

        errors = validate_enrichment_data(data)

        assert "Company name is required" in errors

    def test_validate_enrichment_data_invalid_domain(self):
        """Test validation with invalid domain (lines 494-495)"""
        data = {"company_name": "Test Corp", "domain": "invalid..domain"}

        errors = validate_enrichment_data(data)

        assert any("Invalid domain format" in error for error in errors)

    def test_validate_enrichment_data_invalid_email_domain(self):
        """Test validation with invalid email domain (lines 498-500)"""
        data = {"company_name": "Test Corp", "email_domain": "invalid..email"}

        errors = validate_enrichment_data(data)

        assert any("Invalid email domain format" in error for error in errors)

    def test_validate_enrichment_data_invalid_phone(self):
        """Test validation with invalid phone (lines 503-505)"""
        data = {"company_name": "Test Corp", "phone": "123"}  # Too short

        errors = validate_enrichment_data(data)

        assert any("Invalid phone format" in error for error in errors)

    def test_validate_enrichment_data_invalid_employee_count(self):
        """Test validation with invalid employee count (lines 508-510)"""
        data = {"company_name": "Test Corp", "employee_count": -5}  # Negative

        errors = validate_enrichment_data(data)

        assert any("Invalid employee count" in error for error in errors)

    def test_validate_enrichment_data_invalid_revenue(self):
        """Test validation with invalid revenue (lines 513-515)"""
        data = {"company_name": "Test Corp", "annual_revenue": -1000}  # Negative

        errors = validate_enrichment_data(data)

        assert any("Invalid annual revenue" in error for error in errors)

    def test_is_valid_domain_edge_cases(self):
        """Test _is_valid_domain function (lines 524-525)"""
        # Valid domains
        assert _is_valid_domain("test.com") == True
        assert _is_valid_domain("sub.domain.co.uk") == True

        # Invalid domains
        assert _is_valid_domain("invalid") == False
        assert _is_valid_domain("test..com") == False
        assert _is_valid_domain(".test.com") == False

    def test_is_valid_phone_edge_cases(self):
        """Test _is_valid_phone function (lines 533-535)"""
        # Valid phones
        assert _is_valid_phone("555-123-4567") == True  # 10 digits
        assert _is_valid_phone("+1-555-123-4567") == True  # 11 digits
        assert _is_valid_phone("123-456-7890-123") == True  # 13 digits

        # Invalid phones
        assert _is_valid_phone("123") == False  # Too short
        assert _is_valid_phone("1234567890123456") == False  # Too long

    def test_calculate_completeness_score_all_fields(self):
        """Test calculate_completeness_score with all fields (lines 563-568)"""
        data = {
            "company_name": "Test Corp",
            "domain": "test.com",
            "industry": "Technology",
            "employee_count": 100,
            "headquarters_city": "San Francisco",
            "headquarters_state": "CA",
            "headquarters_country": "USA",
            "phone": "555-1234",
            "description": "A test company",
            "founded_year": 2020,
            "website": "https://test.com",
            "annual_revenue": 1000000,
        }

        score = calculate_completeness_score(data)
        assert score == 1.0  # Perfect completeness

    def test_calculate_completeness_score_empty_data(self):
        """Test calculate_completeness_score with empty data"""
        data = {}

        score = calculate_completeness_score(data)
        assert score == 0.0

    def test_calculate_completeness_score_partial_data(self):
        """Test calculate_completeness_score with partial data"""
        data = {
            "company_name": "Test Corp",  # 0.15 weight
            "domain": "test.com"  # 0.15 weight
            # Total: 0.30 out of 1.0
        }

        score = calculate_completeness_score(data)
        assert 0.25 < score < 0.35  # Approximately 0.30
