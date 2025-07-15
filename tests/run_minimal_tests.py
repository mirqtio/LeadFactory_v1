#!/usr/bin/env python3
"""
Run minimal tests without pytest infrastructure.
This script runs basic smoke tests without requiring stub server or database.
"""
import os
import sys
import traceback

# Add project root to path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

# Set minimal environment
os.environ["USE_STUBS"] = "true"
os.environ["ENVIRONMENT"] = "test"
os.environ["SECRET_KEY"] = "test-secret-key"
os.environ["DATABASE_URL"] = "sqlite:///tmp/test.db"


def test_python_version():
    """Test Python version is 3.11"""
    print("Testing Python version...", end=" ")
    assert sys.version_info.major == 3
    assert sys.version_info.minor == 11
    print("✓")


def test_critical_imports():
    """Test that critical modules can be imported"""
    print("Testing critical imports...", end=" ")
    # Core imports
    from core.config import Settings
    from core.exceptions import LeadFactoryError
    
    # Database imports
    from database.base import Base
    from database.models import Business, Lead, Target, Batch
    
    # Model imports from actual domain modules
    from d1_targeting.models import TargetUniverse, Campaign
    from d2_sourcing.models import SourcedLocation
    from d3_assessment.models import AssessmentResult
    from d4_enrichment.models import EnrichmentRequest
    from d5_scoring.models import D5ScoringResult
    from d6_reports.models import ReportGeneration
    
    # Gateway imports
    from d0_gateway.base import BaseAPIClient
    print("✓")


def test_config_creation():
    """Test that configuration can be created"""
    print("Testing config creation...", end=" ")
    from core.config import Settings
    
    settings = Settings(
        database_url="sqlite:///test.db",
        secret_key="test-key",
        environment="test"
    )
    assert settings.environment == "test"
    print("✓")


def test_exception_hierarchy():
    """Test custom exception hierarchy"""
    print("Testing exception hierarchy...", end=" ")
    from core.exceptions import (
        LeadFactoryError,
        ConfigurationError,
        ValidationError,
        ExternalAPIError
    )
    
    # Test inheritance
    assert issubclass(ConfigurationError, LeadFactoryError)
    assert issubclass(ValidationError, LeadFactoryError)
    assert issubclass(ExternalAPIError, LeadFactoryError)
    
    # Test instantiation
    base_error = LeadFactoryError("test")
    assert str(base_error) == "test"
    print("✓")


def test_model_validation():
    """Test basic model validation without external dependencies"""
    print("Testing model validation...", end=" ")
    from d1_targeting.schemas import CreateTargetUniverseSchema, TargetingCriteriaSchema, GeographicConstraintSchema
    from d1_targeting.types import VerticalMarket, GeographyLevel
    from pydantic import ValidationError as PydanticValidationError
    
    # Valid input
    valid_target = CreateTargetUniverseSchema(
        name="Test Universe",
        description="Test description",
        targeting_criteria=TargetingCriteriaSchema(
            verticals=[VerticalMarket.RESTAURANTS],
            geographic_constraints=[
                GeographicConstraintSchema(
                    level=GeographyLevel.CITY,
                    values=["New York"]
                )
            ]
        )
    )
    assert valid_target.name == "Test Universe"
    
    # Invalid input
    try:
        invalid_target = CreateTargetUniverseSchema(name="Test")
        assert False, "Should have raised validation error"
    except PydanticValidationError:
        pass  # Expected
    print("✓")


def test_database_models():
    """Test database models can be instantiated"""
    print("Testing database models...", end=" ")
    from database.models import Business, Lead
    from datetime import datetime
    
    # Create instances (not persisted)
    business = Business(
        name="Test Business",
        city="New York",
        state="NY",
        created_at=datetime.utcnow()
    )
    assert business.name == "Test Business"
    
    lead = Lead(
        email="test@example.com",
        domain="example.com",
        company_name="Test Company",
        created_at=datetime.utcnow()
    )
    assert lead.email == "test@example.com"
    print("✓")


def main():
    """Run all minimal tests"""
    tests = [
        test_python_version,
        test_critical_imports,
        test_config_creation,
        test_exception_hierarchy,
        test_model_validation,
        test_database_models
    ]
    
    passed = 0
    failed = 0
    
    print("Running ultra-minimal tests without pytest infrastructure...")
    print("=" * 60)
    
    for test in tests:
        try:
            test()
            passed += 1
        except Exception as e:
            failed += 1
            print(f"\n✗ {test.__name__} failed:")
            traceback.print_exc()
            print()
    
    print("=" * 60)
    print(f"Results: {passed} passed, {failed} failed")
    
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())