"""
Minimal test suite that doesn't require stub server
These tests verify basic functionality without external dependencies
"""
import os
import sys
import pytest

# Mark all tests in this module as no_stubs and minimal
pytestmark = [pytest.mark.no_stubs, pytest.mark.minimal]


def test_python_version():
    """Test Python version is 3.11"""
    assert sys.version_info.major == 3
    assert sys.version_info.minor == 11


def test_critical_imports():
    """Test that critical modules can be imported"""
    # Core imports
    from core.config import Settings
    from core.exceptions import LeadFactoryError
    
    # Database imports
    from database.base import Base
    from database.models import Business, Lead
    
    # Model imports from actual domain modules
    from d1_targeting.models import Target, Batch
    from d2_sourcing.models import SourcingRequest, SourcingResult
    from d3_assessment.models import AssessmentRequest, AssessmentResult
    from d4_enrichment.models import EnrichmentRequest, EnrichmentResult
    from d5_scoring.models import ScoringRequest, ScoringResult
    from d6_reports.models import ReportRequest, ReportResult
    
    # Gateway imports
    from d0_gateway.base import BaseAPIClient
    
    assert Settings is not None
    assert LeadFactoryError is not None
    assert Base is not None
    assert Business is not None
    assert Lead is not None
    assert Target is not None
    assert AssessmentRequest is not None
    assert EnrichmentRequest is not None
    assert ScoringRequest is not None
    assert ReportRequest is not None
    assert BaseAPIClient is not None


def test_config_defaults():
    """Test that configuration has sensible defaults"""
    from core.config import Settings
    
    # Create settings with minimal environment
    settings = Settings(
        database_url="sqlite:///test.db",
        secret_key="test-key",
        environment="test"
    )
    
    # Test defaults
    assert settings.environment == "test"
    # debug defaults to False in Settings, but we're testing config works
    assert settings.log_level == "INFO"  # Default log level
    assert settings.use_stubs is True  # Should default to True in test
    
    # Test that provider flags are disabled when using stubs
    assert settings.enable_gbp is False
    assert settings.enable_pagespeed is False
    assert settings.enable_sendgrid is False
    assert settings.enable_openai is False
    assert settings.enable_dataaxle is False
    assert settings.enable_hunter is False


def test_exception_hierarchy():
    """Test custom exception hierarchy"""
    from core.exceptions import (
        LeadFactoryError,
        ConfigurationError,
        ValidationError,
        ExternalAPIError,
        RateLimitError,
        NotFoundError
    )
    
    # Test inheritance
    assert issubclass(ConfigurationError, LeadFactoryError)
    assert issubclass(ValidationError, LeadFactoryError)
    assert issubclass(ExternalAPIError, LeadFactoryError)
    assert issubclass(RateLimitError, ExternalAPIError)
    assert issubclass(NotFoundError, LeadFactoryError)
    
    # Test instantiation
    base_error = LeadFactoryError("test")
    assert str(base_error) == "test"
    
    config_error = ConfigurationError("missing config")
    assert str(config_error) == "missing config"
    
    api_error = ExternalAPIError("API failed", "test", status_code=500)
    assert api_error.provider == "test"
    assert api_error.status_code == 500


def test_model_validation():
    """Test basic model validation without external dependencies"""
    from d1_targeting.models import Target
    from pydantic import ValidationError as PydanticValidationError
    
    # Valid input using actual Target model
    valid_target = Target(
        geo_value="New York",
        geo_type="city",
        vertical="restaurants"
    )
    assert valid_target.geo_value == "New York"
    assert valid_target.geo_type == "city"
    assert valid_target.vertical == "restaurants"
    
    # Invalid input - missing required fields
    try:
        invalid_target = Target(geo_value="Test")
        assert False, "Should have raised validation error"
    except PydanticValidationError as e:
        assert "geo_type" in str(e) or "vertical" in str(e)


def test_database_models():
    """Test database models can be instantiated"""
    from database.models import Business, Lead
    from datetime import datetime
    
    # Create business instance (not persisted)
    business = Business(
        name="Test Business",
        city="New York",
        state="NY",
        created_at=datetime.utcnow()
    )
    assert business.name == "Test Business"
    assert business.city == "New York"
    assert business.state == "NY"
    
    # Create lead instance (not persisted) - using correct fields
    lead = Lead(
        email="test@example.com",
        domain="example.com",
        company_name="Test Company",
        created_at=datetime.utcnow()
    )
    assert lead.email == "test@example.com"
    assert lead.domain == "example.com"
    assert lead.company_name == "Test Company"


def test_logger_creation():
    """Test logging configuration"""
    import logging
    from core.config import get_settings
    
    # Get settings to ensure logging is configured
    settings = get_settings()
    
    # Create a logger
    logger = logging.getLogger(__name__)
    assert logger is not None
    
    # Test logging doesn't error
    logger.debug("Debug message")
    logger.info("Info message")
    logger.warning("Warning message")
    logger.error("Error message")