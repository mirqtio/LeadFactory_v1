"""
Test Enrichment Models - Task 040

Tests for enrichment models ensuring all acceptance criteria are met:
- Enrichment result model
- Match confidence tracking
- Source attribution
- Data versioning
"""
import json
import sys
import uuid
from datetime import datetime, timedelta
from decimal import Decimal

import pytest

sys.path.insert(0, "/app")

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from d4_enrichment.models import (
    DataVersion,
    EnrichmentAuditLog,
    EnrichmentRequest,
    EnrichmentResult,
    EnrichmentSource,
    EnrichmentStatus,
    MatchConfidence,
    calculate_completeness_score,
    validate_enrichment_data,
)
from database.models import Base


class TestTask040AcceptanceCriteria:
    """Test that Task 040 meets all acceptance criteria"""

    @pytest.fixture(scope="session")
    def test_engine(self):
        """Create test database engine"""
        engine = create_engine("sqlite:///:memory:", echo=False)
        return engine

    @pytest.fixture(scope="session")
    def test_session_factory(self, test_engine):
        """Create test session factory"""
        Base.metadata.create_all(test_engine)
        SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)
        return SessionLocal

    @pytest.fixture
    def test_session(self, test_session_factory):
        """Create test database session"""
        session = test_session_factory()
        try:
            yield session
        finally:
            # Clean up by rolling back any uncommitted changes
            session.rollback()
            # Clear all data from all tables to ensure test isolation
            for table in reversed(Base.metadata.sorted_tables):
                session.execute(table.delete())
            session.commit()
            session.close()

    @pytest.fixture
    def sample_enrichment_data(self):
        """Sample enrichment data for testing"""
        return {
            "company_name": "Acme Corporation",
            "legal_name": "Acme Corporation LLC",
            "domain": "acme.com",
            "website": "https://www.acme.com",
            "description": "Leading provider of enterprise software solutions",
            "industry": "Software",
            "employee_count": 150,
            "employee_range": "100-200",
            "founded_year": 2010,
            "headquarters_address": {
                "street": "123 Main St",
                "city": "San Francisco",
                "state": "CA",
                "postal_code": "94105",
                "country": "United States",
            },
            "headquarters_city": "San Francisco",
            "headquarters_state": "CA",
            "headquarters_country": "United States",
            "phone": "+1-555-123-4567",
            "email_domain": "acme.com",
            "annual_revenue": Decimal("5000000.00"),
            "technologies": ["Python", "React", "PostgreSQL"],
            "logo_url": "https://logo.acme.com/logo.png",
        }

    def test_enrichment_result_model(self, test_session, sample_enrichment_data):
        """
        Test enrichment result model structure

        Acceptance Criteria: Enrichment result model
        """
        # Create enrichment request first
        request = EnrichmentRequest(
            business_id="biz_test_001",
            requested_sources=["clearbit", "apollo"],
            status=EnrichmentStatus.IN_PROGRESS.value,
        )
        test_session.add(request)
        test_session.commit()

        # Create enrichment result
        result = EnrichmentResult(
            request_id=request.id,
            business_id="biz_test_001",
            source=EnrichmentSource.CLEARBIT.value,
            match_confidence=MatchConfidence.HIGH.value,
            match_score=Decimal("0.95"),
            data_version="20240101_abc123",
            **sample_enrichment_data,
        )

        test_session.add(result)
        test_session.commit()

        # Verify model structure
        assert result.id is not None
        assert result.business_id == "biz_test_001"
        assert result.source == EnrichmentSource.CLEARBIT.value
        assert result.company_name == "Acme Corporation"
        assert result.domain == "acme.com"
        assert result.employee_count == 150
        assert result.annual_revenue == Decimal("5000000.00")
        assert result.enriched_at is not None

        # Test relationships
        assert result.request.id == request.id
        assert len(request.results) == 1
        assert request.results[0].id == result.id

        # Test model methods
        assert result.age_days >= 0
        assert not result.is_expired  # No expiry set

        contact_info = result.get_contact_info()
        assert contact_info["phone"] == "+1-555-123-4567"
        assert contact_info["website"] == "https://www.acme.com"

        metrics = result.get_company_metrics()
        assert metrics["employee_count"] == 150
        assert metrics["annual_revenue"] == 5000000.00

        print("✓ Enrichment result model works correctly")

    def test_match_confidence_tracking(self, test_session):
        """
        Test match confidence tracking functionality

        Acceptance Criteria: Match confidence tracking
        """
        result = EnrichmentResult(
            business_id="biz_test_002",
            source=EnrichmentSource.APOLLO.value,
            match_score=Decimal("0.85"),
            data_version="20240101_def456",
            enriched_at=datetime.utcnow(),  # Set enriched_at to current time
        )

        # Test match confidence calculation
        input_data = {
            "company_name": "Test Company Inc",
            "domain": "testcompany.com",
            "phone": "+1-555-999-8888",
        }

        matched_data = {
            "company_name": "Test Company Inc.",
            "domain": "testcompany.com",
            "phone": "+1-555-999-8888",
            "address": "456 Test St",
        }

        score = result.calculate_match_score(input_data, matched_data)
        assert 0.8 <= score <= 1.0  # Should be high confidence

        result.match_score = Decimal(str(score))
        result.set_match_confidence()

        # Test confidence enum setting
        assert result.match_confidence in [
            MatchConfidence.EXACT.value,
            MatchConfidence.HIGH.value,
            MatchConfidence.MEDIUM.value,
        ]

        # Test different confidence levels
        test_scores = [
            (Decimal("1.0"), MatchConfidence.EXACT),
            (Decimal("0.95"), MatchConfidence.HIGH),
            (Decimal("0.75"), MatchConfidence.MEDIUM),
            (Decimal("0.55"), MatchConfidence.LOW),
            (Decimal("0.30"), MatchConfidence.UNCERTAIN),
        ]

        for score, expected_confidence in test_scores:
            result.match_score = score
            result.set_match_confidence()
            assert result.match_confidence == expected_confidence.value

        # Test data quality metrics
        result.data_quality_score = Decimal("0.92")
        result.completeness_score = Decimal("0.88")
        result.freshness_days = 5

        quality_metrics = result.get_data_quality_metrics()
        assert quality_metrics["match_score"] == 0.30  # Last score set
        assert quality_metrics["data_quality_score"] == 0.92
        assert quality_metrics["completeness_score"] == 0.88
        assert quality_metrics["freshness_days"] == 5

        print("✓ Match confidence tracking works correctly")

    def test_source_attribution(self, test_session):
        """
        Test source attribution functionality

        Acceptance Criteria: Source attribution
        """
        # Test different enrichment sources
        sources_data = [
            {
                "source": EnrichmentSource.CLEARBIT.value,
                "source_record_id": "clearbit_123456",
                "source_url": "https://clearbit.com/companies/123456",
            },
            {
                "source": EnrichmentSource.APOLLO.value,
                "source_record_id": "apollo_789012",
                "source_url": "https://apollo.io/companies/789012",
            },
            {
                "source": EnrichmentSource.LINKEDIN.value,
                "source_record_id": "linkedin_345678",
                "source_url": "https://linkedin.com/company/test-company",
            },
        ]

        results = []
        for i, source_data in enumerate(sources_data):
            result = EnrichmentResult(
                business_id=f"biz_test_00{i+3}",
                request_id=f"req_test_00{i+3}",  # Add required request_id
                data_version=f"20240101_{i+1:06d}",
                enriched_at=datetime.utcnow(),  # Add required enriched_at
                match_confidence=MatchConfidence.HIGH.value,  # Add required match_confidence
                **source_data,
            )
            results.append(result)
            test_session.add(result)

        test_session.commit()

        # Verify source attribution is properly stored
        for i, result in enumerate(results):
            source_data = sources_data[i]
            assert result.source == source_data["source"]
            assert result.source_record_id == source_data["source_record_id"]
            assert result.source_url == source_data["source_url"]

        # Test querying by source
        clearbit_results = (
            test_session.query(EnrichmentResult)
            .filter_by(source=EnrichmentSource.CLEARBIT.value)
            .all()
        )
        assert len(clearbit_results) == 1
        assert clearbit_results[0].source_record_id == "clearbit_123456"

        print("✓ Source attribution works correctly")

    def test_data_versioning(self, test_session):
        """
        Test data versioning functionality

        Acceptance Criteria: Data versioning
        """
        result = EnrichmentResult(
            business_id="biz_test_006",
            request_id="req_test_006",
            source=EnrichmentSource.CLEARBIT.value,
            data_version="initial_version",
            company_name="Original Company Name",
            match_confidence=MatchConfidence.HIGH.value,
            enriched_at=datetime.utcnow(),
        )

        test_session.add(result)
        test_session.commit()

        # Test version update with new data
        new_data = {
            "company_name": "Updated Company Name",
            "employee_count": 200,
            "annual_revenue": Decimal("10000000.00"),
        }

        old_version = result.data_version
        new_version = result.update_data_version(new_data)

        # Verify version changed
        assert new_version != old_version
        assert result.data_version == new_version
        assert result.data_checksum is not None
        assert len(result.data_checksum) == 64  # SHA256 hex length

        # Test DataVersion dataclass
        data_version_obj = DataVersion(
            version=new_version,
            created_at=datetime.utcnow(),
            source=EnrichmentSource.CLEARBIT,
            checksum=result.data_checksum,
            schema_version="1.0",
        )

        assert data_version_obj.version == new_version
        assert data_version_obj.source == EnrichmentSource.CLEARBIT
        assert data_version_obj.schema_version == "1.0"

        # Test versioning with different data produces different checksums
        new_data_2 = {"company_name": "Another Company Name", "employee_count": 300}

        old_checksum = result.data_checksum
        result.update_data_version(new_data_2)

        assert result.data_checksum != old_checksum

        print("✓ Data versioning works correctly")

    def test_enrichment_request_model(self, test_session):
        """Test enrichment request model"""
        request = EnrichmentRequest(
            business_id="biz_test_007",
            requested_sources=["clearbit", "apollo", "linkedin"],
            priority="high",
            requested_by="user_123",
            timeout_seconds=600,
            include_contacts=True,
            include_financial_data=True,
        )

        test_session.add(request)
        test_session.commit()

        # Verify request structure
        assert request.id is not None
        assert request.business_id == "biz_test_007"
        assert request.requested_sources == ["clearbit", "apollo", "linkedin"]
        assert request.priority == "high"
        assert request.status == EnrichmentStatus.PENDING.value
        assert request.total_sources == 0  # Default
        assert request.include_financial_data is True

        # Test status updates
        request.status = EnrichmentStatus.IN_PROGRESS.value
        request.started_at = datetime.utcnow()
        request.total_sources = 3
        request.completed_sources = 1

        test_session.commit()

        updated_request = (
            test_session.query(EnrichmentRequest).filter_by(id=request.id).first()
        )
        assert updated_request.status == EnrichmentStatus.IN_PROGRESS.value
        assert updated_request.started_at is not None
        assert updated_request.total_sources == 3

        print("✓ Enrichment request model works correctly")

    def test_data_validation(self):
        """Test data validation functions"""
        # Test valid data
        valid_data = {
            "company_name": "Valid Company",
            "domain": "valid.com",
            "email_domain": "valid.com",
            "phone": "+1-555-123-4567",
            "employee_count": 100,
            "annual_revenue": 1000000,
        }

        errors = validate_enrichment_data(valid_data)
        assert len(errors) == 0

        # Test invalid data
        invalid_data = {
            "domain": "invalid_domain",
            "email_domain": "invalid_email_domain",
            "phone": "123",
            "employee_count": -10,
            "annual_revenue": -1000,
        }

        errors = validate_enrichment_data(invalid_data)
        assert len(errors) > 0
        assert any("Company name is required" in error for error in errors)
        assert any("Invalid domain format" in error for error in errors)
        assert any("Invalid phone format" in error for error in errors)
        assert any("Invalid employee count" in error for error in errors)
        assert any("Invalid annual revenue" in error for error in errors)

        print("✓ Data validation works correctly")

    def test_completeness_score_calculation(self):
        """Test completeness score calculation"""
        # Test complete data
        complete_data = {
            "company_name": "Complete Company",
            "domain": "complete.com",
            "industry": "Technology",
            "employee_count": 100,
            "headquarters_city": "San Francisco",
            "headquarters_state": "CA",
            "headquarters_country": "US",
            "phone": "+1-555-123-4567",
            "description": "A complete company description",
            "founded_year": 2020,
            "website": "https://complete.com",
            "annual_revenue": 5000000,
        }

        score = calculate_completeness_score(complete_data)
        assert score == 1.0  # Should be complete

        # Test partial data
        partial_data = {
            "company_name": "Partial Company",
            "domain": "partial.com",
            "industry": "Technology",
        }

        score = calculate_completeness_score(partial_data)
        assert 0.0 < score < 1.0  # Should be partial

        # Test empty data
        empty_data = {}
        score = calculate_completeness_score(empty_data)
        assert score == 0.0

        print("✓ Completeness score calculation works correctly")

    def test_audit_logging(self, test_session):
        """Test enrichment audit logging"""
        audit_log = EnrichmentAuditLog(
            business_id="biz_test_008",
            action="enrich",
            source=EnrichmentSource.CLEARBIT.value,
            user_id="user_123",
            old_values={"company_name": "Old Name"},
            new_values={"company_name": "New Name"},
            changes={"company_name": {"old": "Old Name", "new": "New Name"}},
            api_cost_usd=Decimal("0.50"),
        )

        test_session.add(audit_log)
        test_session.commit()

        # Verify audit log
        assert audit_log.id is not None
        assert audit_log.business_id == "biz_test_008"
        assert audit_log.action == "enrich"
        assert audit_log.timestamp is not None
        assert audit_log.api_cost_usd == Decimal("0.50")

        print("✓ Audit logging works correctly")

    def test_model_indexing_and_constraints(self, test_session):
        """Test database indexes and constraints"""
        # Test unique constraint on business_id + source + data_version
        result1 = EnrichmentResult(
            business_id="biz_test_009",
            request_id="req_test_009",
            source=EnrichmentSource.CLEARBIT.value,
            data_version="v1.0",
            company_name="Test Company",
            match_confidence=MatchConfidence.HIGH.value,
            enriched_at=datetime.utcnow(),
        )

        result2 = EnrichmentResult(
            business_id="biz_test_009",
            request_id="req_test_009_2",
            source=EnrichmentSource.CLEARBIT.value,
            data_version="v1.0",  # Same version - should violate constraint
            company_name="Test Company 2",
            match_confidence=MatchConfidence.HIGH.value,
            enriched_at=datetime.utcnow(),
        )

        test_session.add(result1)
        test_session.commit()

        # This should raise an integrity error due to unique constraint
        test_session.add(result2)

        with pytest.raises(Exception):  # IntegrityError in real database
            test_session.commit()

        test_session.rollback()

        # Test that different versions work fine
        result3 = EnrichmentResult(
            business_id="biz_test_009",
            request_id="req_test_009_3",
            source=EnrichmentSource.CLEARBIT.value,
            data_version="v2.0",  # Different version - should work
            company_name="Test Company 3",
            match_confidence=MatchConfidence.HIGH.value,
            enriched_at=datetime.utcnow(),
        )

        test_session.add(result3)
        test_session.commit()  # Should succeed

        print("✓ Model indexing and constraints work correctly")

    def test_enrichment_comprehensive_workflow(
        self, test_session, sample_enrichment_data
    ):
        """Test comprehensive enrichment workflow"""
        # Step 1: Create enrichment request
        request = EnrichmentRequest(
            business_id="biz_comprehensive_001",
            requested_sources=["clearbit", "apollo"],
            priority="high",
            include_contacts=True,
            include_financial_data=True,
        )
        test_session.add(request)
        test_session.commit()

        # Step 2: Start enrichment process
        request.status = EnrichmentStatus.IN_PROGRESS.value
        request.started_at = datetime.utcnow()
        request.total_sources = 2

        # Step 3: Create enrichment results from multiple sources
        clearbit_result = EnrichmentResult(
            request_id=request.id,
            business_id="biz_comprehensive_001",
            source=EnrichmentSource.CLEARBIT.value,
            source_record_id="clearbit_999",
            match_confidence=MatchConfidence.HIGH.value,
            match_score=Decimal("0.95"),
            data_version="20240101_clearbit",
            enrichment_cost_usd=Decimal("2.50"),
            **sample_enrichment_data,
        )

        apollo_data = sample_enrichment_data.copy()
        apollo_data.update(
            {
                "employee_count": 155,  # Slightly different data
                "technologies": ["Python", "React", "MongoDB"],  # Different tech stack
            }
        )

        apollo_result = EnrichmentResult(
            request_id=request.id,
            business_id="biz_comprehensive_001",
            source=EnrichmentSource.APOLLO.value,
            source_record_id="apollo_888",
            match_confidence=MatchConfidence.MEDIUM.value,
            match_score=Decimal("0.80"),
            data_version="20240101_apollo",
            enrichment_cost_usd=Decimal("1.50"),
            **apollo_data,
        )

        test_session.add_all([clearbit_result, apollo_result])

        # Step 4: Update request status
        request.completed_sources = 2
        request.status = EnrichmentStatus.COMPLETED.value
        request.completed_at = datetime.utcnow()

        test_session.commit()

        # Step 5: Verify complete workflow
        final_request = (
            test_session.query(EnrichmentRequest).filter_by(id=request.id).first()
        )

        assert final_request.status == EnrichmentStatus.COMPLETED.value
        assert len(final_request.results) == 2
        assert final_request.completed_sources == 2

        # Verify results from different sources
        results_by_source = {r.source: r for r in final_request.results}

        clearbit_res = results_by_source[EnrichmentSource.CLEARBIT.value]
        apollo_res = results_by_source[EnrichmentSource.APOLLO.value]

        assert clearbit_res.employee_count == 150
        assert apollo_res.employee_count == 155
        assert clearbit_res.match_confidence == MatchConfidence.HIGH.value
        assert apollo_res.match_confidence == MatchConfidence.MEDIUM.value

        # Test cost tracking
        total_cost = sum(r.enrichment_cost_usd for r in final_request.results)
        assert total_cost == Decimal("4.00")

        print("✓ Comprehensive enrichment workflow works correctly")


# Allow running this test file directly
if __name__ == "__main__":
    import asyncio

    async def run_tests():
        test_instance = TestTask040AcceptanceCriteria()

        print("📊 Running Task 040 Enrichment Models Tests...")
        print()

        try:
            # Create test database
            from sqlalchemy import create_engine
            from sqlalchemy.orm import sessionmaker

            engine = create_engine("sqlite:///:memory:", echo=False)
            Base.metadata.create_all(engine)
            SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

            session = SessionLocal()

            # Sample data
            sample_data = {
                "company_name": "Test Corporation",
                "domain": "test.com",
                "employee_count": 100,
                "annual_revenue": Decimal("1000000.00"),
            }

            # Run all acceptance criteria tests
            test_instance.test_enrichment_result_model(session, sample_data)
            test_instance.test_match_confidence_tracking(session)
            test_instance.test_source_attribution(session)
            test_instance.test_data_versioning(session)
            test_instance.test_enrichment_request_model(session)
            test_instance.test_data_validation()
            test_instance.test_completeness_score_calculation()
            test_instance.test_audit_logging(session)
            test_instance.test_enrichment_comprehensive_workflow(session, sample_data)

            session.close()

            print()
            print("🎉 All Task 040 acceptance criteria tests pass!")
            print("   - Enrichment result model: ✓")
            print("   - Match confidence tracking: ✓")
            print("   - Source attribution: ✓")
            print("   - Data versioning: ✓")

        except Exception as e:
            print(f"❌ Test failed: {e}")
            import traceback

            traceback.print_exc()

    # Run tests
    asyncio.run(run_tests())
