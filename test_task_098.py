#!/usr/bin/env python3
"""
Simple test for Task 098 - Configure A/B experiments
"""

import os
import subprocess
import sys
from pathlib import Path

import yaml


def test_ab_experiments():
    """Test that A/B experiments are configured correctly"""
    print("Testing Task 098: Configure A/B experiments")

    project_root = Path(__file__).parent
    experiments_dir = project_root / "experiments"
    scripts_dir = project_root / "scripts"

    # Test file existence
    config_file = experiments_dir / "initial.yaml"
    loader_script = scripts_dir / "load_experiments.py"

    assert config_file.exists(), f"Missing experiment config: {config_file}"
    assert loader_script.exists(), f"Missing loader script: {loader_script}"

    print(f"✅ Found experiment configuration: {config_file}")
    print(f"✅ Found loader script: {loader_script}")

    # Load and validate YAML
    with open(config_file, "r") as f:
        config = yaml.safe_load(f)

    print("✅ YAML configuration loaded successfully")

    # Test acceptance criteria
    experiments = config.get("experiments", {})

    # Acceptance Criteria 1: Subject line test configured
    subject_line_test = None
    for exp_id, exp_config in experiments.items():
        if (
            "subject" in exp_id.lower()
            or "subject" in exp_config.get("name", "").lower()
        ):
            subject_line_test = exp_config
            break

    assert subject_line_test is not None, "Subject line test not configured"
    print("✅ Subject line test configured")

    # Acceptance Criteria 2: Price point test configured
    price_point_test = None
    for exp_id, exp_config in experiments.items():
        if "price" in exp_id.lower() or "pricing" in exp_config.get("name", "").lower():
            price_point_test = exp_config
            break

    assert price_point_test is not None, "Price point test not configured"
    print("✅ Price point test configured")

    # Acceptance Criteria 3: 50/50 split configured
    def check_50_50_split(exp_config):
        variants = exp_config.get("variants", {})
        if len(variants) != 2:
            return False
        allocations = [v.get("allocation", 0.0) for v in variants.values()]
        return all(abs(alloc - 0.5) < 0.001 for alloc in allocations)

    assert check_50_50_split(subject_line_test), "Subject line test not 50/50 split"
    assert check_50_50_split(price_point_test), "Price point test not 50/50 split"
    print("✅ 50/50 split configured for both experiments")

    # Acceptance Criteria 4: Tracking enabled
    global_tracking = (
        config.get("global_settings", {}).get("tracking", {}).get("enabled", False)
    )
    monitoring_enabled = (
        config.get("monitoring", {}).get("realtime_tracking", {}).get("enabled", False)
    )

    assert global_tracking or monitoring_enabled, "Tracking not enabled"
    print("✅ Tracking enabled")

    # Test loader script execution
    result = subprocess.run(
        [sys.executable, str(loader_script), "--dry-run"],
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, f"Loader script failed: {result.stderr}"
    print("✅ Loader script executed successfully")

    # Verify output contains success indicators
    assert (
        "EXPERIMENT LOADING: SUCCESS" in result.stdout
    ), "Loader script did not report success"
    assert (
        "Subject Line Test Configured" in result.stdout
    ), "Subject line test not detected by loader"
    assert (
        "Price Point Test Configured" in result.stdout
    ), "Price point test not detected by loader"
    assert (
        "50 50 Split Configured" in result.stdout
    ), "50/50 split not detected by loader"
    assert "Tracking Enabled" in result.stdout, "Tracking not detected by loader"

    print("✅ Loader script output validation passed")

    # Validate experiment structure
    for exp_id, exp_config in experiments.items():
        # Check required fields
        required_fields = ["id", "name", "variants", "primary_metric"]
        for field in required_fields:
            assert field in exp_config, f"Experiment {exp_id} missing field: {field}"

        # Check variants have allocations
        variants = exp_config.get("variants", {})
        assert len(variants) > 0, f"Experiment {exp_id} has no variants"

        for variant_id, variant_config in variants.items():
            assert (
                "allocation" in variant_config
            ), f"Variant {variant_id} missing allocation"
            allocation = variant_config["allocation"]
            assert (
                0.0 <= allocation <= 1.0
            ), f"Invalid allocation for {variant_id}: {allocation}"

    print("✅ Experiment structure validation passed")

    print("\n✅ All acceptance criteria met:")
    print("   - Subject line test configured ✓")
    print("   - Price point test configured ✓")
    print("   - 50/50 split configured ✓")
    print("   - Tracking enabled ✓")

    return True


if __name__ == "__main__":
    try:
        result = test_ab_experiments()
        print("🎉 Task 098 test passed!" if result else "❌ Task 098 test failed!")
        sys.exit(0 if result else 1)
    except Exception as e:
        print(f"❌ Task 098 test failed: {e}")
        sys.exit(1)
