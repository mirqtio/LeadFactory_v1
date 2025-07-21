#!/usr/bin/env python3
"""
PRP Migration Validation Script
Validates the stable ID migration completed successfully
"""

import sys
from pathlib import Path

import yaml


def validate_migration():
    """Validate the PRP migration to stable IDs."""

    print("🔍 VALIDATING PRP STABLE ID MIGRATION")
    print("=" * 50)

    yaml_path = Path(".claude/prp_tracking/prp_status.yaml")

    # Load migrated YAML
    with open(yaml_path, "r") as f:
        data = yaml.safe_load(f)

    # Validation checks
    validation_results = {
        "metadata_updated": False,
        "all_prps_have_stable_ids": True,
        "priority_distribution_correct": False,
        "deprecation_marked": False,
        "stats_updated": False,
        "migration_timestamps": True,
    }

    # Check metadata
    metadata = data.get("metadata", {})
    if (
        metadata.get("version") == "2.0"
        and metadata.get("stable_id_system") == True
        and metadata.get("corrected_priorities") == True
    ):
        validation_results["metadata_updated"] = True
        print("✅ Metadata updated to v2.0 with stable ID system")
    else:
        print("❌ Metadata not properly updated")

    # Check all PRPs have stable IDs
    prp_count = 0
    stable_id_count = 0
    priority_counts = {"P0": 0, "P1": 0, "P2": 0, "P3": 0}
    deprecated_count = 0

    for prp_id, prp_data in data["prp_tracking"].items():
        prp_count += 1

        # Check stable ID
        if "stable_id" in prp_data:
            stable_id_count += 1
        else:
            print(f"❌ Missing stable_id for {prp_id}")
            validation_results["all_prps_have_stable_ids"] = False

        # Check migration timestamp
        if "migrated_at" not in prp_data:
            print(f"❌ Missing migration timestamp for {prp_id}")
            validation_results["migration_timestamps"] = False

        # Count priorities (only active PRPs)
        if not prp_data.get("deprecated", False):
            corrected_priority = prp_data.get("corrected_priority", "unknown")
            if corrected_priority in priority_counts:
                priority_counts[corrected_priority] += 1
        else:
            deprecated_count += 1

    if stable_id_count == prp_count:
        print(f"✅ All {prp_count} PRPs have stable IDs")
    else:
        print(f"❌ Only {stable_id_count}/{prp_count} PRPs have stable IDs")

    # Check priority distribution
    expected_distribution = {"P0": 28, "P1": 14, "P2": 10, "P3": 3}
    if priority_counts == expected_distribution:
        validation_results["priority_distribution_correct"] = True
        print(f"✅ Priority distribution correct: {priority_counts}")
    else:
        print(f"❌ Priority distribution incorrect: {priority_counts}")
        print(f"   Expected: {expected_distribution}")

    # Check deprecation
    if deprecated_count == 2:
        validation_results["deprecation_marked"] = True
        print(f"✅ {deprecated_count} PRPs correctly marked as deprecated")
    else:
        print(f"❌ Expected 2 deprecated PRPs, found {deprecated_count}")

    # Check stats
    stats = data.get("stats", {})
    if stats.get("total_prps") == 57 and stats.get("active_prps") == 55 and stats.get("deprecated_prps") == 2:
        validation_results["stats_updated"] = True
        print("✅ Stats section properly updated")
    else:
        print("❌ Stats section not properly updated")
        print(
            f"   Found: total={stats.get('total_prps')}, active={stats.get('active_prps')}, deprecated={stats.get('deprecated_prps')}"
        )

    # Overall validation
    all_passed = all(validation_results.values())

    print("\n" + "=" * 50)
    print("📊 VALIDATION SUMMARY")
    print("=" * 50)

    for check, passed in validation_results.items():
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"{status} {check.replace('_', ' ').title()}")

    print(f"\n🎯 Overall Migration Status: {'✅ SUCCESS' if all_passed else '❌ FAILED'}")

    if all_passed:
        print("\n🚀 Migration completed successfully!")
        print("   - 57 PRPs migrated to stable ID system")
        print("   - Priority distribution corrected using MoSCoW framework")
        print("   - 2 duplicate PRPs properly deprecated")
        print("   - All tracking systems synchronized")
        return True
    else:
        print("\n⚠️  Migration validation failed - manual review required")
        return False


def validate_stable_id_references():
    """Validate stable ID references in documentation."""

    print("\n🔍 VALIDATING DOCUMENTATION REFERENCES")
    print("=" * 50)

    # Check key documentation files exist
    docs_to_check = [
        "COMPLETED_STABLE_IDS.md",
        "INITIAL_STABLE_IDS.md",
        ".claude/STABLE_ID_MAPPING.md",
        ".claude/TRANSITION_PLAN.md",
    ]

    all_exist = True
    for doc in docs_to_check:
        doc_path = Path(doc)
        if doc_path.exists():
            print(f"✅ {doc} exists")
        else:
            print(f"❌ {doc} missing")
            all_exist = False

    return all_exist


if __name__ == "__main__":
    print("Starting PRP Stable ID Migration Validation...")
    print()

    # Validate migration
    migration_valid = validate_migration()

    # Validate documentation
    docs_valid = validate_stable_id_references()

    # Final result
    if migration_valid and docs_valid:
        print("\n🎉 COMPLETE SUCCESS: Migration validation passed all checks!")
        sys.exit(0)
    else:
        print("\n🚨 VALIDATION FAILED: Manual review required")
        sys.exit(1)
