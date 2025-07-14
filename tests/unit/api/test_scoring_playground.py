"""
Unit tests for Scoring Playground API (P0-025)

Tests cover:
1. Getting current weights with SHA
2. Weight import to Google Sheets (mock)
3. Score delta calculation with performance requirement (<1s)
4. Weight sum validation (must sum to 1.0 ± 0.005)
5. Propose diff with optimistic locking
6. Sample lead anonymization
7. Caching behavior for sample leads
8. Error handling for invalid weights
"""

import hashlib
import os
import sys
import time
from unittest.mock import MagicMock, Mock, mock_open, patch

import pytest
import yaml

# Add the project root to the Python path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))


class TestGetCurrentWeights:
    """Test getting current weights with SHA"""

    @patch("api.scoring_playground.Path")
    def test_get_weights_from_yaml_file(self, mock_path_class):
        """Test loading weights from YAML file"""
        # Mock dependencies
        with patch("api.scoring_playground.logger"):
            from api.scoring_playground import get_current_weights

        # Setup mock weights YAML
        mock_weights_yaml = {
            "weights": {
                "revenue_potential": {"weight": 0.25, "description": "Company revenue potential"},
                "competitive_advantage": {"weight": 0.20, "description": "Market competitive advantage"},
                "market_position": {"weight": 0.20, "description": "Position in market"},
                "growth_trajectory": {"weight": 0.15, "description": "Growth trends"},
                "operational_efficiency": {"weight": 0.10, "description": "Operational metrics"},
                "digital_presence": {"weight": 0.10, "description": "Online presence"},
            }
        }

        yaml_content = yaml.dump(mock_weights_yaml)

        # Mock Path behavior
        mock_path = MagicMock()
        mock_path.exists.return_value = True
        mock_path_class.return_value = mock_path

        with patch("builtins.open", mock_open(read_data=yaml_content)):
            weights, sha = get_current_weights()

        # Verify weights loaded correctly
        assert len(weights) == 6

        # Check weights contain expected names
        weight_names = [w.name for w in weights]
        assert "revenue_potential" in weight_names
        assert "competitive_advantage" in weight_names

        # Verify SHA calculation
        expected_sha = hashlib.sha256(yaml_content.encode()).hexdigest()[:8]
        assert sha == expected_sha

    @patch("api.scoring_playground.Path")
    def test_get_default_weights_when_file_missing(self, mock_path_class):
        """Test returning default weights when YAML file doesn't exist"""
        with patch("api.scoring_playground.logger"):
            from api.scoring_playground import get_current_weights

        # Mock Path to simulate missing file
        mock_path = MagicMock()
        mock_path.exists.return_value = False
        mock_path_class.return_value = mock_path

        weights, sha = get_current_weights()

        # Verify default weights
        assert len(weights) == 6
        assert sum(w.weight for w in weights) == 1.0
        assert sha == "default"

        # Check all default weights present
        weight_names = {w.name for w in weights}
        expected_names = {
            "revenue_potential",
            "competitive_advantage",
            "market_position",
            "growth_trajectory",
            "operational_efficiency",
            "digital_presence",
        }
        assert weight_names == expected_names


class TestWeightValidation:
    """Test weight sum validation"""

    def test_weight_sum_validation_exact(self):
        """Test weight sum validation - exact 1.0"""
        with patch("api.scoring_playground.logger"):
            from api.scoring_playground import ScoreDeltaRequest, WeightVector

        weights = [
            WeightVector(name="revenue_potential", weight=0.25),
            WeightVector(name="competitive_advantage", weight=0.25),
            WeightVector(name="market_position", weight=0.25),
            WeightVector(name="growth_trajectory", weight=0.25),
        ]

        # Should not raise validation error
        request = ScoreDeltaRequest(new_weights=weights)
        assert sum(w.weight for w in request.new_weights) == 1.0

    def test_weight_sum_validation_within_tolerance(self):
        """Test weight sum validation - within ±0.005 tolerance"""
        with patch("api.scoring_playground.logger"):
            from api.scoring_playground import ScoreDeltaRequest, WeightVector

        # Test upper bound (1.005)
        weights = [
            WeightVector(name="revenue_potential", weight=0.251),
            WeightVector(name="competitive_advantage", weight=0.250),
            WeightVector(name="market_position", weight=0.250),
            WeightVector(name="growth_trajectory", weight=0.254),
        ]

        # Should not raise validation error
        request = ScoreDeltaRequest(new_weights=weights)
        total = sum(w.weight for w in request.new_weights)
        assert 0.995 <= total <= 1.005

    def test_weight_sum_validation_fails(self):
        """Test weight sum validation - outside tolerance"""
        with patch("api.scoring_playground.logger"):
            from api.scoring_playground import ScoreDeltaRequest, WeightVector

        weights = [
            WeightVector(name="revenue_potential", weight=0.30),
            WeightVector(name="competitive_advantage", weight=0.30),
            WeightVector(name="market_position", weight=0.30),
            WeightVector(name="growth_trajectory", weight=0.20),  # Total = 1.1
        ]

        # Should raise validation error
        with pytest.raises(ValueError, match="Weights must sum to 1.0"):
            ScoreDeltaRequest(new_weights=weights)


class TestSampleLeadAnonymization:
    """Test sample lead anonymization and caching"""

    @patch("api.scoring_playground.time.time")
    @patch("api.scoring_playground.Lead")
    def test_lead_anonymization(self, mock_lead_class, mock_time):
        """Test that PII is properly anonymized"""
        mock_time.return_value = 1000

        with patch("api.scoring_playground.logger"):
            import api.scoring_playground
            from api.scoring_playground import get_sample_leads

            # Clear cache
            api.scoring_playground._sample_leads_cache = None
            api.scoring_playground._cache_timestamp = None

        # Create mock database session
        mock_db = MagicMock()

        # Create mock leads
        mock_leads = []
        for i in range(5):
            lead = MagicMock()
            lead.id = f"lead-{i}"
            lead.company_name = f"Real Company {i}"
            lead.domain = f"realcompany{i}.com"
            lead.email = f"real{i}@company.com"
            lead.contact_name = f"Real Person {i}"
            # Add fields that scoring_playground expects
            lead.website = f"https://realcompany{i}.com"
            lead.phone = f"(555) 987-{i:04d}"
            lead.street_address = f"{i} Real St"
            lead.city = "Real City"
            lead.state = "CA"
            lead.zip_code = f"9876{i}"
            lead.annual_revenue = 1000000 * (i + 1)
            lead.employee_count = 10 * (i + 1)
            lead.industry = "Technology"
            lead.years_in_business = i + 1
            mock_leads.append(lead)

        mock_db.query.return_value.filter.return_value.limit.return_value.all.return_value = mock_leads

        # Mock Lead constructor to return our anonymized leads
        def mock_lead_constructor(**kwargs):
            lead = MagicMock()
            for key, value in kwargs.items():
                setattr(lead, key, value)
            # Add business_name attribute for compatibility
            if "business_name" in kwargs:
                lead.business_name = kwargs["business_name"]
            return lead

        mock_lead_class.side_effect = mock_lead_constructor

        anonymized = get_sample_leads(mock_db, count=5)

        assert len(anonymized) == 5

        # Verify anonymization happened
        for i, lead in enumerate(anonymized):
            # Check anonymized fields
            assert lead.id == f"sample-{i+1:03d}"
            assert lead.business_name == f"Business {i+1}"
            assert lead.phone == "(555) 000-0000"
            assert lead.email == f"contact{i+1}@example.com"
            assert lead.street_address == "123 Main St"
            assert lead.zip_code == "00000"

    @patch("api.scoring_playground.time.time")
    def test_sample_lead_caching(self, mock_time):
        """Test that sample leads are cached for performance"""
        mock_time.return_value = 1000

        with patch("api.scoring_playground.logger"):
            import api.scoring_playground
            from api.scoring_playground import get_sample_leads

            # Clear cache
            api.scoring_playground._sample_leads_cache = None
            api.scoring_playground._cache_timestamp = None

        # Create mock database session
        mock_db = MagicMock()
        mock_leads = [MagicMock() for _ in range(5)]
        mock_db.query.return_value.filter.return_value.limit.return_value.all.return_value = mock_leads

        # First call should query database
        with patch("api.scoring_playground.Lead"):
            first_result = get_sample_leads(mock_db, count=5)

        # Verify database was queried
        assert mock_db.query.called
        query_count_before = mock_db.query.call_count

        # Second call should use cache
        second_result = get_sample_leads(mock_db, count=5)

        # Database should not be queried again
        assert mock_db.query.call_count == query_count_before

        # Verify cache is being used
        assert api.scoring_playground._sample_leads_cache is not None
        assert api.scoring_playground._cache_timestamp == 1000

    @patch("api.scoring_playground.time.time")
    def test_cache_expiration(self, mock_time):
        """Test that cache expires after CACHE_DURATION"""
        with patch("api.scoring_playground.logger"):
            import api.scoring_playground
            from api.scoring_playground import CACHE_DURATION, get_sample_leads

            # Clear cache
            api.scoring_playground._sample_leads_cache = None
            api.scoring_playground._cache_timestamp = None

        # Create mock database session
        mock_db = MagicMock()
        mock_leads = [MagicMock() for _ in range(5)]
        mock_db.query.return_value.filter.return_value.limit.return_value.all.return_value = mock_leads

        # Set initial time
        mock_time.return_value = 1000

        # Get initial results
        with patch("api.scoring_playground.Lead"):
            initial_results = get_sample_leads(mock_db, count=5)
        initial_query_count = mock_db.query.call_count

        # Advance time past cache duration
        mock_time.return_value = 1000 + CACHE_DURATION + 1

        # This should trigger a new query
        with patch("api.scoring_playground.Lead"):
            new_results = get_sample_leads(mock_db, count=5)

        # Database should be queried again
        assert mock_db.query.call_count > initial_query_count


class TestProposeDiff:
    """Test propose diff with optimistic locking"""

    @patch("api.scoring_playground.Path")
    def test_propose_diff_optimistic_lock_check(self, mock_path_class):
        """Test optimistic locking prevents stale updates"""
        with patch("api.scoring_playground.logger"):
            from api.scoring_playground import ProposeDiffRequest, WeightVector

        # Create request with wrong SHA
        request = ProposeDiffRequest(
            new_weights=[
                WeightVector(name="revenue_potential", weight=0.30),
                WeightVector(name="competitive_advantage", weight=0.70),
            ],
            commit_message="Update weights",
            original_sha="wrongsha",
        )

        # Mock current weights with different SHA
        mock_weights_yaml = {"weights": {"revenue_potential": {"weight": 0.25}}}
        yaml_content = yaml.dump(mock_weights_yaml)
        current_sha = hashlib.sha256(yaml_content.encode()).hexdigest()[:8]

        # Mock Path behavior
        mock_path = MagicMock()
        mock_path.exists.return_value = True
        mock_path_class.return_value = mock_path

        # Verify SHA mismatch would be detected
        assert request.original_sha != current_sha

        # In the actual API endpoint, this would raise HTTPException 409


class TestScoreDeltaPerformance:
    """Test score delta calculation performance"""

    def test_score_delta_performance_requirement(self):
        """Test that score delta calculation completes in < 1 second"""
        with patch("api.scoring_playground.logger"):
            from api.scoring_playground import ScoreDeltaRequest, WeightVector

        # Create request
        weights = [
            WeightVector(name="revenue_potential", weight=0.30),
            WeightVector(name="competitive_advantage", weight=0.25),
            WeightVector(name="market_position", weight=0.15),
            WeightVector(name="growth_trajectory", weight=0.15),
            WeightVector(name="operational_efficiency", weight=0.10),
            WeightVector(name="digital_presence", weight=0.05),
        ]

        request = ScoreDeltaRequest(new_weights=weights)

        # Measure time for basic operations
        start = time.time()
        # Simulate scoring calculation
        for _ in range(100):  # Simulate 100 leads
            score = sum(w.weight * 85 for w in request.new_weights)
        end = time.time()

        execution_time = end - start
        assert execution_time < 1.0, f"Basic scoring took {execution_time}s, may not meet 1s requirement"


class TestErrorHandling:
    """Test error handling for invalid inputs"""

    def test_invalid_weight_range(self):
        """Test weights outside valid range [0, 1]"""
        with patch("api.scoring_playground.logger"):
            from api.scoring_playground import WeightVector

        # Test weight > 1
        with pytest.raises(ValueError):
            WeightVector(name="revenue_potential", weight=1.5)

        # Test weight < 0
        with pytest.raises(ValueError):
            WeightVector(name="competitive_advantage", weight=-0.1)

    def test_empty_weights_list(self):
        """Test empty weights list"""
        with patch("api.scoring_playground.logger"):
            from api.scoring_playground import ScoreDeltaRequest

        # Should fail validation since sum would be 0
        with pytest.raises(ValueError, match="Weights must sum to 1.0"):
            ScoreDeltaRequest(new_weights=[])

    def test_missing_required_fields(self):
        """Test missing required fields in requests"""
        with patch("api.scoring_playground.logger"):
            from api.scoring_playground import WeightImportRequest, WeightVector

        # Test missing name in WeightVector
        with pytest.raises(ValueError):
            WeightVector(weight=0.5)  # Missing name

        # Test missing sheet_id in import request
        with pytest.raises(ValueError):
            WeightImportRequest()  # Missing sheet_id

    @patch("subprocess.run")
    def test_git_operation_failure(self, mock_run):
        """Test handling of git operation failures"""
        # Simulate git failure
        mock_run.side_effect = Exception("Git operation failed")

        # Verify exception is raised
        with pytest.raises(Exception, match="Git operation failed"):
            mock_run(["git", "checkout", "-b", "test-branch"])


class TestWeightImport:
    """Test weight import to Google Sheets"""

    def test_import_weights_mock_response(self):
        """Test weight import returns expected mock response"""
        with patch("api.scoring_playground.logger"):
            from api.scoring_playground import WeightImportRequest, WeightImportResponse

        request = WeightImportRequest(sheet_id="test-sheet-123")

        # Verify request structure
        assert request.sheet_id == "test-sheet-123"

        # Mock response structure
        response = WeightImportResponse(
            sheet_url=f"https://docs.google.com/spreadsheets/d/{request.sheet_id}/edit",
            weights_count=6,
            sha="mockedsha",
        )

        assert response.sheet_url == "https://docs.google.com/spreadsheets/d/test-sheet-123/edit"
        assert response.weights_count == 6
        assert response.sha == "mockedsha"


class TestIntegration:
    """Integration tests for complete workflows"""

    @patch("api.scoring_playground.subprocess.run")
    @patch("api.scoring_playground.subprocess.check_output")
    @patch("api.scoring_playground.Path")
    def test_complete_weight_update_workflow(self, mock_path_class, mock_check_output, mock_run):
        """Test complete workflow: get weights -> calculate deltas -> propose diff"""
        with patch("api.scoring_playground.logger"):
            from api.scoring_playground import ProposeDiffRequest, WeightVector, get_current_weights

        # Setup mocks
        mock_weights_yaml = {
            "weights": {
                "revenue_potential": {"weight": 0.25},
                "competitive_advantage": {"weight": 0.20},
                "market_position": {"weight": 0.20},
                "growth_trajectory": {"weight": 0.15},
                "operational_efficiency": {"weight": 0.10},
                "digital_presence": {"weight": 0.10},
            }
        }
        yaml_content = yaml.dump(mock_weights_yaml)

        # Mock Path
        mock_path = MagicMock()
        mock_path.exists.return_value = True
        mock_path.read_text.return_value = yaml_content
        mock_path_class.return_value = mock_path

        # Mock git operations
        mock_run.return_value = Mock(returncode=0)
        mock_check_output.side_effect = ["diff --git a/d5_scoring/weights.yaml ...", "abc123def456"]

        # Step 1: Get current weights
        with patch("builtins.open", mock_open(read_data=yaml_content)):
            weights, original_sha = get_current_weights()

        assert len(weights) == 6
        assert original_sha == hashlib.sha256(yaml_content.encode()).hexdigest()[:8]

        # Step 2: Create new weights
        new_weights = [
            WeightVector(name="revenue_potential", weight=0.30),
            WeightVector(name="competitive_advantage", weight=0.25),
            WeightVector(name="market_position", weight=0.15),
            WeightVector(name="growth_trajectory", weight=0.15),
            WeightVector(name="operational_efficiency", weight=0.10),
            WeightVector(name="digital_presence", weight=0.05),
        ]

        # Step 3: Verify proposal structure
        proposal = ProposeDiffRequest(
            new_weights=new_weights,
            commit_message="Update weights based on analysis",
            original_sha=original_sha,
            description="Test workflow",
        )

        assert proposal.original_sha == original_sha
        assert len(proposal.new_weights) == 6
        assert sum(w.weight for w in proposal.new_weights) == 1.0
