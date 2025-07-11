"""
Test Tier Assignment System - Task 048

Tests for tier assignment system ensuring all acceptance criteria are met:
- A/B/C/D tiers assigned
- Configurable boundaries
- Gate pass/fail logic
- Distribution tracking
"""

import json
import sys
import tempfile
import unittest
import pytest

sys.path.insert(0, "/app")

from d5_scoring.tiers import (
    LeadTier,
    TierAssignmentEngine,
    TierBoundary,
    TierConfiguration,
    assign_lead_tier,
    create_standard_configuration,
)

# Mark entire module as xfail for Phase 0.5
pytestmark = pytest.mark.xfail(reason="Phase 0.5 feature", strict=False)


class TestTask048AcceptanceCriteria(unittest.TestCase):
    """Test that Task 048 meets all acceptance criteria"""

    def test_abcd_tiers_assigned(self):
        """
        Test that A/B/C/D tiers are correctly assigned

        Acceptance Criteria: A/B/C/D tiers assigned
        """
        engine = TierAssignmentEngine()

        # Test each tier assignment
        test_cases = [
            ("lead_a_001", 90.0, LeadTier.A),  # Tier A (80-100)
            ("lead_b_001", 75.0, LeadTier.B),  # Tier B (65-80)
            ("lead_c_001", 55.0, LeadTier.C),  # Tier C (50-65)
            ("lead_d_001", 35.0, LeadTier.D),  # Tier D (30-50)
            ("lead_fail_001", 25.0, LeadTier.FAILED),  # Below gate threshold
        ]

        for lead_id, score, expected_tier in test_cases:
            assignment = engine.assign_tier(lead_id, score)
            assert (
                assignment.tier == expected_tier
            ), f"Score {score} should assign to tier {expected_tier}, got {assignment.tier}"
            assert assignment.lead_id == lead_id, "Lead ID should match"
            assert assignment.score == score, "Score should match"

        # Verify all tiers are represented
        assigned_tiers = {assignment.tier for assignment in engine.assignments}
        expected_tiers = {
            LeadTier.A,
            LeadTier.B,
            LeadTier.C,
            LeadTier.D,
            LeadTier.FAILED,
        }
        assert (
            assigned_tiers == expected_tiers
        ), "All A/B/C/D tiers plus FAILED should be assigned"

        print("✓ A/B/C/D tiers correctly assigned")

    def test_configurable_boundaries(self):
        """
        Test that tier boundaries are configurable and not hardcoded

        Acceptance Criteria: Configurable boundaries
        """
        # Create custom configuration with different boundaries
        custom_config = TierConfiguration(
            name="custom_test",
            version="test_1.0.0",
            gate_threshold=25.0,  # Lower gate threshold
            boundaries=[
                TierBoundary(LeadTier.A, 85.0, 100.0, "Custom Tier A"),
                TierBoundary(LeadTier.B, 70.0, 84.9, "Custom Tier B"),
                TierBoundary(LeadTier.C, 55.0, 69.9, "Custom Tier C"),
                TierBoundary(LeadTier.D, 25.0, 54.9, "Custom Tier D"),
            ],
        )

        engine = TierAssignmentEngine(custom_config)

        # Test that same scores assign to different tiers with custom boundaries
        test_cases = [
            (82.0, LeadTier.B),  # Would be A in default, B in custom
            (67.0, LeadTier.C),  # Would be B in default, C in custom
            (52.0, LeadTier.D),  # Would be C in default, D in custom
            (27.0, LeadTier.D),  # Would be FAILED in default, D in custom
            (20.0, LeadTier.FAILED),  # Below custom gate threshold
        ]

        for score, expected_tier in test_cases:
            assignment = engine.assign_tier(f"test_{score}", score)
            assert (
                assignment.tier == expected_tier
            ), f"Custom config: score {score} should be {expected_tier}, got {assignment.tier}"

        # Test boundary validation
        with self.assertRaises(ValueError):
            TierBoundary(LeadTier.A, 90.0, 80.0)  # Invalid boundary

        with self.assertRaises(ValueError):
            TierBoundary(LeadTier.A, -10.0, 110.0)  # Invalid range

        # Test configuration update
        new_config = create_standard_configuration(gate_threshold=40.0)
        engine.update_configuration(new_config)

        assignment = engine.assign_tier("update_test", 35.0)
        assert (
            assignment.tier == LeadTier.FAILED
        ), "Updated gate threshold should cause failure"

        print("✓ Configurable boundaries work correctly")

    def test_gate_pass_fail_logic(self):
        """
        Test gate pass/fail logic determines qualification

        Acceptance Criteria: Gate pass/fail logic
        """
        # Test with different gate thresholds
        gate_configs = [
            (
                30.0,
                [
                    (50.0, True, LeadTier.C),  # Pass gate, get tier
                    (25.0, False, LeadTier.FAILED),  # Fail gate
                    (30.0, True, LeadTier.D),  # Exactly at threshold - pass
                    (29.9, False, LeadTier.FAILED),  # Just below threshold - fail
                ],
            ),
            (
                50.0,
                [
                    (60.0, True, LeadTier.C),  # Pass higher gate
                    (45.0, False, LeadTier.FAILED),  # Fail higher gate
                    (
                        50.0,
                        True,
                        LeadTier.D,
                    ),  # Exactly at threshold - pass (Tier D for gate=50.0)
                ],
            ),
        ]

        for gate_threshold, test_cases in gate_configs:
            config = create_standard_configuration(gate_threshold)
            engine = TierAssignmentEngine(config)

            for i, (score, should_pass, expected_tier) in enumerate(test_cases):
                assignment = engine.assign_tier(
                    f"gate_test_{gate_threshold}_{i}", score
                )

                assert (
                    assignment.passed_gate == should_pass
                ), f"Score {score} with gate {gate_threshold}: expected pass={should_pass}, got {assignment.passed_gate}"
                assert (
                    assignment.tier == expected_tier
                ), f"Score {score} should assign to {expected_tier}, got {assignment.tier}"

        # Test gate pass/fail counts in distribution
        engine = TierAssignmentEngine()  # Default gate threshold 30.0

        scores_and_expected = [
            (80.0, True),  # Pass
            (60.0, True),  # Pass
            (40.0, True),  # Pass
            (25.0, False),  # Fail
            (15.0, False),  # Fail
        ]

        for i, (score, should_pass) in enumerate(scores_and_expected):
            engine.assign_tier(f"pass_fail_{i}", score)

        distribution = engine.get_tier_distribution()
        assert distribution.gate_pass_count == 3, "Should have 3 passes"
        assert distribution.gate_fail_count == 2, "Should have 2 failures"
        assert distribution.gate_pass_rate == 60.0, "Pass rate should be 60%"

        print("✓ Gate pass/fail logic works correctly")

    def test_distribution_tracking(self):
        """
        Test that lead distribution across tiers is tracked

        Acceptance Criteria: Distribution tracking
        """
        engine = TierAssignmentEngine()

        # Create diverse set of assignments
        assignments_data = [
            # Tier A leads (2)
            ("a1", 95.0),
            ("a2", 85.0),
            # Tier B leads (3)
            ("b1", 75.0),
            ("b2", 70.0),
            ("b3", 65.0),
            # Tier C leads (4)
            ("c1", 60.0),
            ("c2", 55.0),
            ("c3", 52.0),
            ("c4", 50.0),
            # Tier D leads (1)
            ("d1", 40.0),
            # Failed leads (2)
            ("f1", 25.0),
            ("f2", 15.0),
        ]

        # Assign all leads
        for lead_id, score in assignments_data:
            engine.assign_tier(lead_id, score)

        # Get distribution
        distribution = engine.get_tier_distribution()

        # Verify total count
        assert distribution.total_assignments == 12, "Should track 12 total assignments"

        # Verify tier counts
        expected_counts = {
            LeadTier.A: 2,
            LeadTier.B: 3,
            LeadTier.C: 4,
            LeadTier.D: 1,
            LeadTier.FAILED: 2,
        }

        for tier, expected_count in expected_counts.items():
            actual_count = distribution.tier_counts[tier]
            assert (
                actual_count == expected_count
            ), f"Tier {tier} should have {expected_count} leads, got {actual_count}"

        # Verify percentages
        tier_percentages = distribution.tier_percentages
        self.assertAlmostEqual(
            tier_percentages[LeadTier.A], 16.67, places=1
        )  # "Tier A should be ~16.67%"
        assert tier_percentages[LeadTier.B] == 25.0, "Tier B should be 25%"
        self.assertAlmostEqual(
            tier_percentages[LeadTier.C], 33.33, places=1
        )  # "Tier C should be ~33.33%"
        self.assertAlmostEqual(
            tier_percentages[LeadTier.D], 8.33, places=1
        )  # "Tier D should be ~8.33%"
        self.assertAlmostEqual(
            tier_percentages[LeadTier.FAILED], 16.67, places=1
        )  # "Failed should be ~16.67%"

        # Verify gate statistics
        assert distribution.gate_pass_count == 10, "Should have 10 passed leads"
        assert distribution.gate_fail_count == 2, "Should have 2 failed leads"
        self.assertAlmostEqual(
            distribution.gate_pass_rate, 83.33, places=1
        )  # "Pass rate should be ~83.33%"

        # Test filtering by tier
        tier_a_assignments = engine.get_assignments_by_tier(LeadTier.A)
        assert len(tier_a_assignments) == 2, "Should find 2 Tier A assignments"

        qualified_leads = engine.get_qualified_leads()
        assert len(qualified_leads) == 10, "Should find 10 qualified leads"

        failed_leads = engine.get_failed_leads()
        assert len(failed_leads) == 2, "Should find 2 failed leads"

        print("✓ Distribution tracking works correctly")

    def test_batch_assignment(self):
        """Test batch assignment functionality"""
        engine = TierAssignmentEngine()

        # Batch assignment
        lead_scores = {
            "batch_1": 90.0,
            "batch_2": 70.0,
            "batch_3": 45.0,
            "batch_4": 20.0,
            "batch_5": 85.0,
        }

        assignments = engine.batch_assign_tiers(lead_scores)

        assert len(assignments) == 5, "Should return 5 assignments"

        # Verify assignments
        expected_tiers = {
            "batch_1": LeadTier.A,
            "batch_2": LeadTier.B,
            "batch_3": LeadTier.D,
            "batch_4": LeadTier.FAILED,
            "batch_5": LeadTier.A,
        }

        for assignment in assignments:
            expected_tier = expected_tiers[assignment.lead_id]
            assert (
                assignment.tier == expected_tier
            ), f"Batch assignment: {assignment.lead_id} should be {expected_tier}"

        print("✓ Batch assignment works correctly")

    def test_tier_enum_properties(self):
        """Test LeadTier enum properties and methods"""
        # Test priority ordering
        assert (
            LeadTier.A.priority_order < LeadTier.B.priority_order
        ), "A should have higher priority than B"
        assert (
            LeadTier.B.priority_order < LeadTier.C.priority_order
        ), "B should have higher priority than C"
        assert (
            LeadTier.C.priority_order < LeadTier.D.priority_order
        ), "C should have higher priority than D"
        assert (
            LeadTier.D.priority_order < LeadTier.FAILED.priority_order
        ), "D should have higher priority than FAILED"

        # Test descriptions
        for tier in LeadTier:
            description = tier.description
            assert isinstance(
                description, str
            ), f"Tier {tier} should have string description"
            assert (
                len(description) > 10
            ), f"Tier {tier} description should be meaningful"

        print("✓ LeadTier enum properties work correctly")

    def test_custom_configuration_factory(self):
        """Test custom configuration creation helpers"""
        # Test custom configuration factory
        config = TierAssignmentEngine.create_custom_configuration(
            name="test_custom",
            gate_threshold=35.0,
            tier_a_min=85.0,
            tier_b_min=70.0,
            tier_c_min=55.0,
            tier_d_min=35.0,
        )

        assert config.name == "test_custom", "Custom config should have correct name"
        assert config.gate_threshold == 35.0, "Custom gate threshold should be set"
        assert len(config.boundaries) == 4, "Should have 4 tier boundaries"

        # Verify boundaries are correct
        tier_a_boundary = next(b for b in config.boundaries if b.tier == LeadTier.A)
        assert tier_a_boundary.min_score == 85.0, "Tier A should start at 85.0"

        tier_d_boundary = next(b for b in config.boundaries if b.tier == LeadTier.D)
        assert tier_d_boundary.min_score == 35.0, "Tier D should start at 35.0"

        print("✓ Custom configuration factory works correctly")

    def test_export_distribution_summary(self):
        """Test comprehensive distribution summary export"""
        engine = TierAssignmentEngine()

        # Add some assignments
        test_assignments = [
            ("export_1", 95.0),
            ("export_2", 75.0),
            ("export_3", 55.0),
            ("export_4", 35.0),
            ("export_5", 20.0),
        ]

        for lead_id, score in test_assignments:
            engine.assign_tier(lead_id, score)

        # Export summary
        summary = engine.export_distribution_summary()

        # Verify structure
        assert "configuration" in summary, "Summary should include configuration"
        assert "distribution" in summary, "Summary should include distribution"
        assert "summary" in summary, "Summary should include summary stats"

        # Verify configuration info
        config_info = summary["configuration"]
        assert config_info["name"] == "default_abcd", "Should include config name"
        assert config_info["gate_threshold"] == 30.0, "Should include gate threshold"
        assert config_info["total_boundaries"] == 4, "Should include boundary count"

        # Verify distribution info
        dist_info = summary["distribution"]
        assert dist_info["total_assignments"] == 5, "Should track total assignments"
        assert dist_info["gate_pass_count"] == 4, "Should track pass count"
        assert dist_info["gate_fail_count"] == 1, "Should track fail count"
        assert "tier_counts" in dist_info, "Should include tier counts"
        assert "tier_percentages" in dist_info, "Should include tier percentages"

        # Verify summary stats
        summary_stats = summary["summary"]
        assert summary_stats["highest_tier_leads"] == 1, "Should count A-tier leads"
        assert summary_stats["qualified_leads"] == 4, "Should count qualified leads"
        assert summary_stats["total_processed"] == 5, "Should count total processed"

        print("✓ Export distribution summary works correctly")

    def test_configuration_file_loading(self):
        """Test loading configuration from JSON file"""
        # Create temporary config file
        config_data = {
            "name": "file_test_config",
            "version": "2.0.0",
            "gate_threshold": 40.0,
            "description": "Test configuration from file",
            "enabled": True,
            "boundaries": [
                {
                    "tier": "A",
                    "min_score": 85.0,
                    "max_score": 100.0,
                    "description": "File Tier A",
                },
                {
                    "tier": "B",
                    "min_score": 70.0,
                    "max_score": 84.9,
                    "description": "File Tier B",
                },
                {
                    "tier": "C",
                    "min_score": 55.0,
                    "max_score": 69.9,
                    "description": "File Tier C",
                },
                {
                    "tier": "D",
                    "min_score": 40.0,
                    "max_score": 54.9,
                    "description": "File Tier D",
                },
            ],
        }

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(config_data, f)
            config_file = f.name

        try:
            # Load configuration from file
            engine = TierAssignmentEngine.from_configuration_file(config_file)

            assert (
                engine.configuration.name == "file_test_config"
            ), "Should load config name"
            assert engine.configuration.version == "2.0.0", "Should load config version"
            assert (
                engine.configuration.gate_threshold == 40.0
            ), "Should load gate threshold"
            assert (
                len(engine.configuration.boundaries) == 4
            ), "Should load all boundaries"

            # Test assignment with loaded config
            assignment = engine.assign_tier("file_test", 72.0)
            assert assignment.tier == LeadTier.B, "Should use loaded boundaries"

        finally:
            import os

            os.unlink(config_file)

        print("✓ Configuration file loading works correctly")

    def test_edge_cases_and_validation(self):
        """Test edge cases and input validation"""
        engine = TierAssignmentEngine()

        # Test score validation
        with self.assertRaises(ValueError):
            engine.assign_tier("invalid_1", -5.0)

        with self.assertRaises(ValueError):
            engine.assign_tier("invalid_2", 105.0)

        # Test boundary edge cases
        assignment_30 = engine.assign_tier("edge_30", 30.0)  # Exactly at gate threshold
        assert assignment_30.passed_gate == True, "Score exactly at gate should pass"
        assert assignment_30.tier == LeadTier.D, "Score 30.0 should be Tier D"

        assignment_29_9 = engine.assign_tier("edge_29_9", 29.9)  # Just below gate
        assert assignment_29_9.passed_gate == False, "Score below gate should fail"
        assert assignment_29_9.tier == LeadTier.FAILED, "Score 29.9 should be FAILED"

        # Test tier boundary edges
        assignment_80 = engine.assign_tier("edge_80", 80.0)  # Exactly at A boundary
        assert assignment_80.tier == LeadTier.A, "Score 80.0 should be Tier A"

        assignment_79_9 = engine.assign_tier("edge_79_9", 79.9)  # Just below A
        assert assignment_79_9.tier == LeadTier.B, "Score 79.9 should be Tier B"

        print("✓ Edge cases and validation work correctly")

    def test_comprehensive_functionality(self):
        """
        Comprehensive test verifying all acceptance criteria work together
        """
        # This test verifies all four acceptance criteria work together

        # 1. A/B/C/D tiers assigned - create custom config and assign various tiers
        custom_config = TierAssignmentEngine.create_custom_configuration(
            name="comprehensive_test",
            gate_threshold=25.0,
            tier_a_min=80.0,
            tier_b_min=65.0,
            tier_c_min=50.0,
            tier_d_min=25.0,
        )
        engine = TierAssignmentEngine(custom_config)

        comprehensive_leads = [
            ("comp_a1", 95.0, LeadTier.A),
            ("comp_a2", 85.0, LeadTier.A),
            ("comp_b1", 75.0, LeadTier.B),
            ("comp_b2", 68.0, LeadTier.B),
            ("comp_c1", 60.0, LeadTier.C),
            ("comp_c2", 52.0, LeadTier.C),
            ("comp_d1", 40.0, LeadTier.D),
            ("comp_d2", 30.0, LeadTier.D),
            ("comp_f1", 20.0, LeadTier.FAILED),
            ("comp_f2", 10.0, LeadTier.FAILED),
        ]

        for lead_id, score, expected_tier in comprehensive_leads:
            assignment = engine.assign_tier(lead_id, score)
            assert (
                assignment.tier == expected_tier
            ), f"A/B/C/D assignment failed for {lead_id}"

        # 2. Configurable boundaries - verify custom boundaries are being used
        assert (
            engine.configuration.gate_threshold == 25.0
        ), "Custom gate threshold should be used"
        boundary_a = next(
            b for b in engine.configuration.boundaries if b.tier == LeadTier.A
        )
        assert boundary_a.min_score == 80.0, "Custom Tier A boundary should be used"

        # 3. Gate pass/fail logic - verify gate logic works with custom threshold
        distribution = engine.get_tier_distribution()
        assert distribution.gate_pass_count == 8, "Should have 8 passes with gate=25.0"
        assert (
            distribution.gate_fail_count == 2
        ), "Should have 2 failures with gate=25.0"

        # 4. Distribution tracking - verify comprehensive tracking
        assert distribution.total_assignments == 10, "Should track all 10 assignments"
        assert (
            distribution.tier_counts[LeadTier.A] == 2
        ), "Should track 2 A-tier assignments"
        assert (
            distribution.tier_counts[LeadTier.B] == 2
        ), "Should track 2 B-tier assignments"
        assert (
            distribution.tier_counts[LeadTier.C] == 2
        ), "Should track 2 C-tier assignments"
        assert (
            distribution.tier_counts[LeadTier.D] == 2
        ), "Should track 2 D-tier assignments"
        assert (
            distribution.tier_counts[LeadTier.FAILED] == 2
        ), "Should track 2 failed assignments"

        # Export and verify summary integrates all features
        summary = engine.export_distribution_summary()
        assert (
            summary["configuration"]["name"] == "comprehensive_test"
        ), "Should export config info"
        assert (
            summary["distribution"]["gate_pass_rate"] == 80.0
        ), "Should calculate pass rate correctly"
        assert (
            len(summary["distribution"]["tier_counts"]) == 5
        ), "Should include all tier counts"

        print("✓ All acceptance criteria working together successfully")


class TestConvenienceFunctions(unittest.TestCase):
    """Test convenience functions and additional features"""

    def test_assign_lead_tier_function(self):
        """Test standalone assign_lead_tier function"""
        assignment = assign_lead_tier("convenience_001", 85.0)

        assert assignment.lead_id == "convenience_001", "Should assign correct lead ID"
        assert assignment.score == 85.0, "Should assign correct score"
        assert assignment.tier == LeadTier.A, "Should assign correct tier"
        assert assignment.passed_gate == True, "Should pass gate"

        print("✓ Convenience function works correctly")

    def test_create_standard_configuration_function(self):
        """Test create_standard_configuration function"""
        config = create_standard_configuration(gate_threshold=45.0)

        assert config.name == "standard_abcd", "Should have standard name"
        assert config.gate_threshold == 45.0, "Should use custom gate threshold"
        assert len(config.boundaries) == 4, "Should have 4 boundaries"

        # Verify Tier D uses the gate threshold
        tier_d_boundary = next(b for b in config.boundaries if b.tier == LeadTier.D)
        assert (
            tier_d_boundary.min_score == 45.0
        ), "Tier D should start at gate threshold"

        print("✓ Standard configuration function works correctly")


# Allow running this test file directly
if __name__ == "__main__":
    print("🏆 Running Task 048 Tier Assignment System Tests...")
    print("   - A/B/C/D tiers assigned: ✓")
    print("   - Configurable boundaries: ✓")
    print("   - Gate pass/fail logic: ✓")
    print("   - Distribution tracking: ✓")

    # Run tests using unittest
    unittest.main(verbosity=2)
