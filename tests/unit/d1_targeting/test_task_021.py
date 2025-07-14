"""
Test Task 021: Build target universe manager
Acceptance Criteria:
- CRUD operations work
- Geo conflict detection
- Priority scoring implemented
- Freshness tracking works
"""
import sys
from datetime import datetime, timedelta
from unittest.mock import Mock

import pytest

# Mark entire module as slow for CI optimization
pytestmark = pytest.mark.slow

# Ensure we can import our modules
sys.path.insert(0, "/app")

from d1_targeting.geo_validator import GeoConflict, GeoValidator
from d1_targeting.target_universe import TargetUniverseManager
from d1_targeting.types import VerticalMarket


class TestTask021AcceptanceCriteria:
    """Test that Task 021 meets all acceptance criteria"""

    def test_crud_operations_work(self):
        """Test that CRUD operations work for target universes"""
        # Setup mock session
        mock_session = Mock()
        mock_session.commit = Mock()
        mock_session.rollback = Mock()
        mock_session.add = Mock()
        mock_session.query = Mock()

        # Create manager with mock session
        manager = TargetUniverseManager(session=mock_session)

        # Test CREATE operation
        verticals = [VerticalMarket.RESTAURANTS, VerticalMarket.RETAIL]
        geography_config = {"constraints": [{"level": "state", "values": ["CA", "NY"]}]}

        universe = manager.create_universe(
            name="Test Universe",
            description="Test description",
            verticals=verticals,
            geography_config=geography_config,
        )

        # Verify universe was created
        assert universe.name == "Test Universe"
        assert universe.verticals == ["restaurants", "retail"]
        assert universe.geography_config == geography_config
        mock_session.add.assert_called_once()
        mock_session.commit.assert_called_once()

        # Test READ operation
        mock_session.query.return_value.filter_by.return_value.first.return_value = universe
        retrieved = manager.get_universe(universe.id)
        assert retrieved == universe

        # Test UPDATE operation
        updated = manager.update_universe(universe.id, name="Updated Name")
        assert updated.name == "Updated Name"

        # Test DELETE operation
        mock_session.query.return_value.filter.return_value.count.return_value = 0
        deleted = manager.delete_universe(universe.id)
        assert deleted is True
        assert universe.is_active is False

        print("✓ CRUD operations work")

    def test_geo_conflict_detection(self):
        """Test that geo conflict detection works"""
        validator = GeoValidator()

        # Test conflict detection with hierarchy conflict
        geography_config = {
            "constraints": [
                {"level": "country", "values": ["US"]},
                {"level": "state", "values": ["CA", "NY"]},  # Conflict with country
            ]
        }

        conflicts = validator.detect_conflicts(geography_config)

        # Should detect hierarchy conflict
        hierarchy_conflicts = [c for c in conflicts if c.conflict_type == "hierarchy_conflict"]
        assert len(hierarchy_conflicts) > 0
        assert hierarchy_conflicts[0].severity == "error"

        # Test format validation
        bad_format_config = {
            "constraints": [
                {"level": "zip_code", "values": ["12345", "invalid-zip"]},
                {"level": "state", "values": ["CA", "ZZ"]},  # ZZ is invalid
            ]
        }

        format_conflicts = validator.detect_conflicts(bad_format_config)
        format_errors = [c for c in format_conflicts if c.conflict_type == "format_error"]
        assert len(format_errors) >= 2

        # Test clean configuration
        clean_config = {"constraints": [{"level": "state", "values": ["CA", "NY"]}]}

        clean_conflicts = validator.detect_conflicts(clean_config)
        error_conflicts = [c for c in clean_conflicts if c.severity == "error"]
        assert len(error_conflicts) == 0

        print("✓ Geo conflict detection works")

    def test_priority_scoring_implemented(self):
        """Test that priority scoring is implemented"""
        # Setup mock session and universe
        mock_session = Mock()
        mock_session.query.return_value.filter_by.return_value.all.return_value = []

        manager = TargetUniverseManager(session=mock_session)

        # Create mock universe
        mock_universe = Mock()
        mock_universe.id = "test-id"
        mock_universe.actual_size = 5000
        mock_universe.qualified_count = 2500
        mock_universe.verticals = ["restaurants", "retail"]
        mock_universe.last_refresh = datetime.utcnow() - timedelta(hours=12)

        # Test priority calculation
        score = manager.calculate_universe_priority(mock_universe)

        # Verify score is valid
        assert isinstance(score, float)
        assert 0.0 <= score <= 1.0
        assert score > 0.0  # Should have some score based on metrics

        # Test ranking functionality
        mock_universes = [mock_universe]
        mock_session.query.return_value.filter_by.return_value.limit.return_value.all.return_value = mock_universes

        ranked = manager.rank_universes_by_priority(limit=10)

        assert len(ranked) == 1
        assert ranked[0][0] == mock_universe  # Universe object
        assert isinstance(ranked[0][1], float)  # Priority score

        print("✓ Priority scoring implemented")

    def test_freshness_tracking_works(self):
        """Test that freshness tracking works"""
        # Setup mock session
        mock_session = Mock()
        mock_session.commit = Mock()

        manager = TargetUniverseManager(session=mock_session)

        # Create mock universe
        mock_universe = Mock()
        mock_universe.actual_size = 1000
        mock_session.query.return_value.filter_by.return_value.first.return_value = mock_universe

        # Test freshness update
        manager.update_freshness_metrics("test-id")

        # Verify update occurred
        assert isinstance(mock_universe.last_refresh, datetime)
        assert mock_universe.actual_size >= 1000  # Should have grown
        mock_session.commit.assert_called_once()

        # Test freshness score calculation
        fresh_universe = Mock()
        fresh_universe.last_refresh = datetime.utcnow() - timedelta(hours=6)

        stale_universe = Mock()
        stale_universe.last_refresh = datetime.utcnow() - timedelta(hours=48)

        never_refreshed = Mock()
        never_refreshed.last_refresh = None

        fresh_score = manager.calculate_freshness_score(fresh_universe)
        stale_score = manager.calculate_freshness_score(stale_universe)
        never_score = manager.calculate_freshness_score(never_refreshed)

        # Verify freshness scoring works correctly
        assert fresh_score > stale_score > never_score
        assert 0.0 <= fresh_score <= 1.0
        assert never_score == 0.0

        # Test finding stale universes
        mock_session.query.return_value.filter.return_value.all.return_value = [stale_universe]
        stale_universes = manager.get_stale_universes(max_age_hours=24)
        assert len(stale_universes) == 1

        print("✓ Freshness tracking works")

    def test_all_required_files_exist(self):
        """Test that all required files from Task 021 exist and can be imported"""
        # Test target_universe.py
        manager = TargetUniverseManager()
        assert manager is not None

        # Test geo_validator.py
        validator = GeoValidator()
        assert validator is not None

        # Test that GeoConflict can be instantiated
        conflict = GeoConflict(
            conflict_type="test",
            description="test conflict",
            affected_constraints=["test"],
            severity="warning",
        )
        assert conflict.conflict_type == "test"

        print("✓ All required files exist and can be imported")

    def test_integration_with_existing_models(self):
        """Test integration with existing database models"""
        # Test that we can import and use the models
        from d1_targeting.models import Campaign, TargetUniverse

        # Test that models can be instantiated
        universe = TargetUniverse(
            name="Test Universe",
            verticals=["restaurants"],
            geography_config={},
            estimated_size=1000,
        )
        assert universe.name == "Test Universe"

        campaign = Campaign(name="Test Campaign", target_universe_id="test-id")
        assert campaign.name == "Test Campaign"

        print("✓ Integration with existing models works")


if __name__ == "__main__":
    # Allow running this test file directly
    test_instance = TestTask021AcceptanceCriteria()
    test_instance.test_crud_operations_work()
    test_instance.test_geo_conflict_detection()
    test_instance.test_priority_scoring_implemented()
    test_instance.test_freshness_tracking_works()
    test_instance.test_all_required_files_exist()
    test_instance.test_integration_with_existing_models()
    print("\n🎉 All Task 021 acceptance criteria tests pass!")
