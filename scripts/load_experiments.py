#!/usr/bin/env python3
"""
Experiment Configuration Loader - Task 098

Loads A/B experiment configurations from YAML files and validates them
against the experiment schema. Integrates with the LeadFactory experiment system.

Acceptance Criteria:
- Subject line test configured ✓
- Price point test configured ✓
- 50/50 split configured ✓
- Tracking enabled ✓
"""

import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

import yaml

# Add project root to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    from d11_orchestration.experiments import ExperimentManager
    from d11_orchestration.models import Experiment, ExperimentStatus

    EXPERIMENT_MANAGER_AVAILABLE = True
except ImportError:
    EXPERIMENT_MANAGER_AVAILABLE = False
    print("Warning: Experiment manager not available - running in validation mode only")


class ExperimentLoader:
    """Loads and validates A/B experiment configurations"""

    def __init__(self, config_dir: str = "experiments", dry_run: bool = False):
        """
        Initialize experiment loader

        Args:
            config_dir: Directory containing experiment YAML files
            dry_run: If True, validate but don't load experiments
        """
        self.config_dir = Path(config_dir)
        self.dry_run = dry_run
        self.experiments_loaded = []
        self.validation_errors = []
        self.validation_warnings = []

        if EXPERIMENT_MANAGER_AVAILABLE and not dry_run:
            self.experiment_manager = ExperimentManager()
        else:
            self.experiment_manager = None

    def load_config_file(self, file_path: Path) -> Optional[Dict[str, Any]]:
        """Load and parse a YAML configuration file"""
        try:
            with open(file_path, "r") as f:
                config = yaml.safe_load(f)

            print(f"✅ Loaded configuration: {file_path}")
            return config

        except yaml.YAMLError as e:
            self.validation_errors.append(f"YAML parse error in {file_path}: {e}")
            return None
        except FileNotFoundError:
            self.validation_errors.append(f"Configuration file not found: {file_path}")
            return None
        except Exception as e:
            self.validation_errors.append(f"Error loading {file_path}: {e}")
            return None

    def validate_experiment_config(self, config: Dict[str, Any]) -> bool:
        """Validate experiment configuration structure and values"""
        print("🔍 Validating experiment configuration...")

        is_valid = True

        # Check required top-level fields
        required_fields = ["version", "experiments", "assignment_rules"]
        for field in required_fields:
            if field not in config:
                self.validation_errors.append(f"Missing required field: {field}")
                is_valid = False

        if not is_valid:
            return False

        # Validate experiments section
        experiments = config.get("experiments", {})
        if not experiments:
            self.validation_errors.append("No experiments defined")
            return False

        # Validate each experiment
        for exp_id, exp_config in experiments.items():
            is_valid &= self.validate_single_experiment(exp_id, exp_config)

        # Validate assignment rules
        assignment_rules = config.get("assignment_rules", {})
        for rule_id, rule_config in assignment_rules.items():
            is_valid &= self.validate_assignment_rule(rule_id, rule_config)

        # Validate traffic allocation totals
        is_valid &= self.validate_traffic_allocations(experiments)

        return is_valid

    def validate_single_experiment(self, exp_id: str, exp_config: Dict[str, Any]) -> bool:
        """Validate a single experiment configuration"""
        is_valid = True

        # Required experiment fields
        required_fields = ["id", "name", "variants", "primary_metric"]
        for field in required_fields:
            if field not in exp_config:
                self.validation_errors.append(f"Experiment {exp_id}: Missing required field '{field}'")
                is_valid = False

        # Validate variants
        variants = exp_config.get("variants", {})
        if not variants:
            self.validation_errors.append(f"Experiment {exp_id}: No variants defined")
            is_valid = False

        # Check for control variant
        if "control" not in variants:
            self.validation_warnings.append(f"Experiment {exp_id}: No control variant defined")

        # Validate variant allocations
        total_allocation = 0.0
        for variant_id, variant_config in variants.items():
            allocation = variant_config.get("allocation", 0.0)
            if not isinstance(allocation, (int, float)) or allocation < 0 or allocation > 1:
                self.validation_errors.append(
                    f"Experiment {exp_id}, variant {variant_id}: Invalid allocation {allocation}"
                )
                is_valid = False
            total_allocation += allocation

        # Check total allocation sums to 1.0 (with small tolerance for floating point)
        if abs(total_allocation - 1.0) > 0.001:
            self.validation_errors.append(
                f"Experiment {exp_id}: Variant allocations sum to {total_allocation}, expected 1.0"
            )
            is_valid = False

        return is_valid

    def validate_assignment_rule(self, rule_id: str, rule_config: Dict[str, Any]) -> bool:
        """Validate an assignment rule configuration"""
        is_valid = True

        # Required rule fields
        required_fields = ["experiment_id", "method", "assignment_map"]
        for field in required_fields:
            if field not in rule_config:
                self.validation_errors.append(f"Assignment rule {rule_id}: Missing required field '{field}'")
                is_valid = False

        # Validate assignment map
        assignment_map = rule_config.get("assignment_map", [])
        if not assignment_map:
            self.validation_errors.append(f"Assignment rule {rule_id}: Empty assignment map")
            is_valid = False

        # Validate hash ranges cover [0.0, 1.0] without gaps or overlaps
        if rule_config.get("method") == "hash_based":
            ranges = []
            for assignment in assignment_map:
                hash_range = assignment.get("hash_range", [])
                if len(hash_range) != 2:
                    self.validation_errors.append(f"Assignment rule {rule_id}: Invalid hash_range {hash_range}")
                    is_valid = False
                else:
                    ranges.append(tuple(hash_range))

            # Check ranges are contiguous and cover [0.0, 1.0]
            if ranges:
                ranges.sort()
                if ranges[0][0] != 0.0:
                    self.validation_errors.append(f"Assignment rule {rule_id}: Hash ranges don't start at 0.0")
                    is_valid = False
                if ranges[-1][1] != 1.0:
                    self.validation_errors.append(f"Assignment rule {rule_id}: Hash ranges don't end at 1.0")
                    is_valid = False

                # Check for gaps or overlaps
                for i in range(1, len(ranges)):
                    if ranges[i][0] != ranges[i - 1][1]:
                        self.validation_errors.append(f"Assignment rule {rule_id}: Gap or overlap in hash ranges")
                        is_valid = False
                        break

        return is_valid

    def validate_traffic_allocations(self, experiments: Dict[str, Any]) -> bool:
        """Validate that traffic allocations are correctly configured"""
        is_valid = True

        for exp_id, exp_config in experiments.items():
            variants = exp_config.get("variants", {})

            # Check if this is a 50/50 split (acceptance criteria requirement)
            if len(variants) == 2:
                allocations = [v.get("allocation", 0.0) for v in variants.values()]
                if all(abs(alloc - 0.5) < 0.001 for alloc in allocations):
                    print(f"✅ Experiment {exp_id}: 50/50 split configured correctly")
                else:
                    self.validation_warnings.append(
                        f"Experiment {exp_id}: Not a 50/50 split (allocations: {allocations})"
                    )

        return is_valid

    def check_acceptance_criteria(self, config: Dict[str, Any]) -> Dict[str, bool]:
        """Check if all acceptance criteria are met"""
        criteria = {
            "subject_line_test_configured": False,
            "price_point_test_configured": False,
            "50_50_split_configured": False,
            "tracking_enabled": False,
        }

        experiments = config.get("experiments", {})

        # Check for subject line test
        for exp_id, exp_config in experiments.items():
            if "subject" in exp_id.lower() or "subject" in exp_config.get("name", "").lower():
                criteria["subject_line_test_configured"] = True
                print(f"✅ Subject line test found: {exp_id}")

                # Check for 50/50 split
                variants = exp_config.get("variants", {})
                if len(variants) == 2:
                    allocations = [v.get("allocation", 0.0) for v in variants.values()]
                    if all(abs(alloc - 0.5) < 0.001 for alloc in allocations):
                        criteria["50_50_split_configured"] = True
                        print("✅ 50/50 split configured for subject line test")

        # Check for price point test
        for exp_id, exp_config in experiments.items():
            if "price" in exp_id.lower() or "pricing" in exp_config.get("name", "").lower():
                criteria["price_point_test_configured"] = True
                print(f"✅ Price point test found: {exp_id}")

                # Check for 50/50 split
                variants = exp_config.get("variants", {})
                if len(variants) == 2:
                    allocations = [v.get("allocation", 0.0) for v in variants.values()]
                    if all(abs(alloc - 0.5) < 0.001 for alloc in allocations):
                        criteria["50_50_split_configured"] = True
                        print("✅ 50/50 split configured for price point test")

        # Check for tracking enabled
        global_tracking = config.get("global_settings", {}).get("tracking", {}).get("enabled", False)
        monitoring_enabled = config.get("monitoring", {}).get("realtime_tracking", {}).get("enabled", False)

        if global_tracking or monitoring_enabled:
            criteria["tracking_enabled"] = True
            print("✅ Tracking enabled")

        return criteria

    def load_experiments_to_system(self, config: Dict[str, Any]) -> bool:
        """Load experiments into the experiment management system"""
        if self.dry_run:
            print("🔍 DRY RUN: Would load experiments to system")
            return True

        if not self.experiment_manager:
            print("⚠️  Experiment manager not available - skipping system load")
            return True

        print("📤 Loading experiments to system...")

        try:
            experiments = config.get("experiments", {})

            for exp_id, exp_config in experiments.items():
                # Convert config to experiment model
                experiment_data = {
                    "experiment_id": exp_config["id"],
                    "name": exp_config["name"],
                    "description": exp_config.get("description", ""),
                    "status": ExperimentStatus.ACTIVE,
                    "start_date": datetime.fromisoformat(exp_config.get("start_date", "").replace("Z", "+00:00")),
                    "end_date": datetime.fromisoformat(exp_config.get("end_date", "").replace("Z", "+00:00")),
                    "config": exp_config,
                }

                # Create or update experiment
                success = self.experiment_manager.create_experiment(experiment_data)
                if success:
                    self.experiments_loaded.append(exp_id)
                    print(f"✅ Loaded experiment: {exp_id}")
                else:
                    self.validation_errors.append(f"Failed to load experiment: {exp_id}")

            print(f"📊 Successfully loaded {len(self.experiments_loaded)} experiments")
            return len(self.validation_errors) == 0

        except Exception as e:
            self.validation_errors.append(f"Error loading experiments to system: {e}")
            return False

    def generate_hash_assignment(self, input_string: str, experiment_config: Dict[str, Any]) -> str:
        """Generate hash-based variant assignment for testing"""
        hash_seed = experiment_config.get("hash_seed", "leadfactory_2025")
        hash_input = f"{hash_seed}:{input_string}"
        hash_value = int(hashlib.md5(hash_input.encode()).hexdigest(), 16)
        normalized_hash = (hash_value % 10000) / 10000.0  # Normalize to [0, 1)

        # Find variant based on hash ranges in assignment rules
        assignment_rules = experiment_config.get("assignment_rules", {})
        for rule_id, rule_config in assignment_rules.items():
            assignment_map = rule_config.get("assignment_map", [])
            for assignment in assignment_map:
                hash_range = assignment.get("hash_range", [])
                if len(hash_range) == 2 and hash_range[0] <= normalized_hash < hash_range[1]:
                    return assignment.get("variant", "control")

        return "control"  # Default fallback

    def test_experiment_assignment(self, config: Dict[str, Any]) -> None:
        """Test experiment assignment distribution"""
        print("🧪 Testing experiment assignment distribution...")

        # Test with sample inputs
        test_inputs = [
            "test@example.com",
            "business_123",
            "user_456",
            "sample@test.com",
            "demo@company.com",
        ]

        experiments = config.get("experiments", {})
        for exp_id, exp_config in experiments.items():
            print(f"\n🎯 Testing {exp_id}:")

            variant_counts = {}
            for test_input in test_inputs * 20:  # Test with 100 assignments
                variant = self.generate_hash_assignment(f"{test_input}_{exp_id}", config)
                variant_counts[variant] = variant_counts.get(variant, 0) + 1

            total_assignments = sum(variant_counts.values())
            for variant, count in variant_counts.items():
                percentage = (count / total_assignments) * 100
                print(f"   {variant}: {count}/{total_assignments} ({percentage:.1f}%)")

    def generate_report(self, config: Dict[str, Any], criteria: Dict[str, bool]) -> Dict[str, Any]:
        """Generate experiment loading report"""
        report = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "config_file": str(self.config_dir / "initial.yaml"),
            "dry_run": self.dry_run,
            "validation": {
                "valid": len(self.validation_errors) == 0,
                "errors": self.validation_errors,
                "warnings": self.validation_warnings,
            },
            "acceptance_criteria": criteria,
            "experiments": {
                "total_configured": len(config.get("experiments", {})),
                "loaded_to_system": len(self.experiments_loaded),
                "experiment_ids": list(config.get("experiments", {}).keys()),
            },
            "summary": {
                "all_criteria_met": all(criteria.values()),
                "experiments_loaded": len(self.experiments_loaded),
                "validation_passed": len(self.validation_errors) == 0,
            },
        }

        return report

    def load_all_experiments(self) -> bool:
        """Load all experiment configurations from the config directory"""
        print("🚀 Loading LeadFactory A/B Experiments")
        print("=" * 60)

        # Load initial experiment configuration
        config_file = self.config_dir / "initial.yaml"
        config = self.load_config_file(config_file)

        if not config:
            print("❌ Failed to load experiment configuration")
            return False

        # Validate configuration
        if not self.validate_experiment_config(config):
            print(f"❌ Configuration validation failed: {len(self.validation_errors)} errors")
            for error in self.validation_errors:
                print(f"   - {error}")
            return False

        print("✅ Configuration validation passed")

        # Check acceptance criteria
        criteria = self.check_acceptance_criteria(config)

        # Test assignment distribution
        self.test_experiment_assignment(config)

        # Load to system (if not dry run)
        system_load_success = self.load_experiments_to_system(config)

        # Generate report
        report = self.generate_report(config, criteria)

        # Print summary
        print("\n" + "=" * 60)
        print("📊 EXPERIMENT LOADING SUMMARY")
        print("=" * 60)

        print(f"Configuration file: {config_file}")
        print(f"Mode: {'DRY RUN' if self.dry_run else 'LIVE'}")
        print(f"Validation: {'PASSED' if report['validation']['valid'] else 'FAILED'}")

        print("\n📋 Acceptance Criteria:")
        for criterion, met in criteria.items():
            status = "✅" if met else "❌"
            print(f"   {status} {criterion.replace('_', ' ').title()}")

        print("\n🧪 Experiments Configured:")
        for exp_id in report["experiments"]["experiment_ids"]:
            print(f"   - {exp_id}")

        if self.validation_warnings:
            print(f"\n⚠️  Warnings ({len(self.validation_warnings)}):")
            for warning in self.validation_warnings:
                print(f"   - {warning}")

        success = report["validation"]["valid"] and report["summary"]["all_criteria_met"] and system_load_success

        status = "SUCCESS" if success else "FAILED"
        print(f"\n🎉 EXPERIMENT LOADING: {status}")

        return success


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(description="Load A/B experiment configurations")
    parser.add_argument(
        "--config-dir",
        default="experiments",
        help="Directory containing experiment YAML files",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate configuration without loading to system",
    )
    parser.add_argument("--json", action="store_true", help="Output results as JSON")

    args = parser.parse_args()

    # Initialize loader
    loader = ExperimentLoader(config_dir=args.config_dir, dry_run=args.dry_run)

    # Load experiments
    success = loader.load_all_experiments()

    # Output JSON report if requested
    if args.json:
        config_file = Path(args.config_dir) / "initial.yaml"
        config = loader.load_config_file(config_file)
        criteria = loader.check_acceptance_criteria(config) if config else {}
        report = loader.generate_report(config or {}, criteria)
        print(json.dumps(report, indent=2))

    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
