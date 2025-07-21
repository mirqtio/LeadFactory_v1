"""
Test D4 Enrichment Coordinator Simple Coverage Expansion

Simple tests focusing only on uncovered property methods to improve coverage.
"""

import pytest

from d4_enrichment.coordinator import EnrichmentProgress

# Mark entire module as unit test
pytestmark = pytest.mark.unit


class TestEnrichmentProgressEdgeCases:
    """Test EnrichmentProgress property methods for edge cases that improve coverage"""

    def test_completion_percentage_zero_total_businesses(self):
        """Test completion_percentage property when total_businesses is 0 (line 61)"""
        progress = EnrichmentProgress(request_id="test-zero-total", total_businesses=0, processed_businesses=5)

        # Should return 0.0 to avoid division by zero - this hits line 61
        assert progress.completion_percentage == 0.0

    def test_success_rate_zero_processed_businesses(self):
        """Test success_rate property when processed_businesses is 0 (lines 67-69)"""
        progress = EnrichmentProgress(
            request_id="test-zero-processed", total_businesses=10, processed_businesses=0, enriched_businesses=5
        )

        # Should return 0.0 to avoid division by zero - this hits lines 67-69
        assert progress.success_rate == 0.0
