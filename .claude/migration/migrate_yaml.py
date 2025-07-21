#!/usr/bin/env python3
"""
PRP YAML Migration Script
Adds stable IDs and corrected priorities to prp_status.yaml
"""

from datetime import datetime
from pathlib import Path

import yaml

# Stable ID mapping based on STABLE_ID_MAPPING.md
STABLE_ID_MAPPING = {
    # P0 Must-Have Completed (20)
    "P0-001": ("PRP-1001", "P0"),
    "P0-002": ("PRP-1002", "P0"),
    "P0-003": ("PRP-1003", "P0"),
    "P0-004": ("PRP-1004", "P0"),
    "P0-005": ("PRP-1005", "P0"),
    "P0-006": ("PRP-1006", "P0"),
    "P0-007": ("PRP-1007", "P0"),
    "P0-008": ("PRP-1008", "P0"),
    "P0-009": ("PRP-1009", "P0"),
    "P0-010": ("PRP-1010", "P0"),
    "P0-011": ("PRP-1011", "P0"),
    "P0-012": ("PRP-1012", "P0"),
    "P0-016": ("PRP-1013", "P0"),
    "P0-020": ("PRP-1014", "P0"),
    "P0-021": ("PRP-1015", "P0"),
    "P0-022": ("PRP-1016", "P0"),
    "P0-023": ("PRP-1017", "P0"),
    "P0-024": ("PRP-1018", "P0"),
    "P0-025": ("PRP-1019", "P0"),
    "P0-026": ("PRP-1020", "P0"),
    # P1 Should-Have Completed (8)
    "P1-010": ("PRP-1021", "P1"),
    "P1-020": ("PRP-1022", "P1"),
    "P1-030": ("PRP-1023", "P1"),
    "P1-040": ("PRP-1024", "P1"),
    "P1-050": ("PRP-1025", "P1"),
    "P1-060": ("PRP-1026", "P1"),
    "P1-070": ("PRP-1027", "P1"),
    "P1-080": ("PRP-1028", "P1"),
    # P2 Could-Have Completed (3)
    "P2-000": ("PRP-1029", "P2"),
    "P2-010": ("PRP-1030", "P2"),
    "P2-020": ("PRP-1031", "P2"),
    # P3 Won't-Have-Now Completed (1)
    "P3-003": ("PRP-1032", "P3"),
    # P0 Must-Have Remaining (8)
    "P0-000": ("PRP-1033", "P0"),
    "P0-013": ("PRP-1034", "P0"),
    "P0-014": ("PRP-1035", "P0"),
    "P0-015": ("PRP-1036", "P0"),
    "P0-027": ("PRP-1037", "P0"),
    "P0-028": ("PRP-1038", "P0"),
    "P3-001": ("PRP-1039", "P0"),  # Priority corrected to P0 (critical security)
    "P3-007": ("PRP-1040", "P0"),  # Priority corrected to P0 (blocking workflow)
    # P1 Should-Have Remaining (6)
    "P2-030": ("PRP-1041", "P1"),  # Priority corrected to P1 (key revenue driver)
    "P0-029": ("PRP-1042", "P1"),  # Priority corrected to P1 (essential UI)
    "P0-030": ("PRP-1043", "P1"),  # Priority corrected to P1 (important UI)
    "P0-031": ("PRP-1044", "P1"),  # Priority corrected to P1 (critical UI)
    "P3-002": ("PRP-1045", "P1"),  # Priority corrected to P1 (important integration)
    "P3-005": ("PRP-1046", "P1"),  # Priority corrected to P1 (production confidence)
    # P2 Could-Have Remaining (7)
    "P2-040": ("PRP-1047", "P2"),
    "P2-050": ("PRP-1048", "P2"),
    "P2-060": ("PRP-1049", "P2"),
    "P2-070": ("PRP-1050", "P2"),  # Will be marked as deprecated
    "P2-080": ("PRP-1051", "P2"),
    "P2-090": ("PRP-1052", "P2"),
    "P0-032": ("PRP-1053", "P2"),  # Priority corrected to P2 (polish)
    "P0-033": ("PRP-1054", "P2"),  # Priority corrected to P2 (enhancement)
    # P3 Won't-Have-Now Remaining (4)
    "P0-034": ("PRP-1055", "P3"),  # Priority corrected to P3 (lower priority polish)
    "P3-004": ("PRP-1056", "P3"),  # Will be marked as deprecated
    "P3-006": ("PRP-1057", "P3"),
}

# Deprecation mapping
DEPRECATIONS = {
    "P2-070": {
        "deprecated": True,
        "superseded_by": "PRP-1042",
        "reason": "Superseded by P0-029 Lead Explorer UI (Wave D UI Consolidation)",
    },
    "P3-004": {
        "deprecated": True,
        "superseded_by": "PRP-1044",
        "reason": "Superseded by P0-031 Batch Report Runner UI (Wave D UI Consolidation)",
    },
}


def migrate_yaml():
    """Migrate prp_status.yaml to include stable IDs and corrected priorities."""

    yaml_path = Path(".claude/prp_tracking/prp_status.yaml")

    # Load current YAML
    with open(yaml_path) as f:
        data = yaml.safe_load(f)

    # Update metadata
    data["metadata"]["version"] = "2.0"
    data["metadata"]["last_updated"] = datetime.now().isoformat() + "Z"
    data["metadata"]["migration_completed"] = datetime.now().isoformat() + "Z"
    data["metadata"]["stable_id_system"] = True
    data["metadata"]["corrected_priorities"] = True

    # Update each PRP
    updated_count = 0
    for prp_id, prp_data in data["prp_tracking"].items():
        if prp_id in STABLE_ID_MAPPING:
            stable_id, corrected_priority = STABLE_ID_MAPPING[prp_id]

            # Add stable ID and corrected priority
            prp_data["stable_id"] = stable_id
            prp_data["corrected_priority"] = corrected_priority
            prp_data["legacy_id"] = prp_id

            # Add migration timestamp
            prp_data["migrated_at"] = datetime.now().isoformat() + "Z"

            # Handle deprecations
            if prp_id in DEPRECATIONS:
                prp_data.update(DEPRECATIONS[prp_id])

            updated_count += 1

    # Update stats with corrected priorities
    priority_counts = {"P0": 0, "P1": 0, "P2": 0, "P3": 0}
    status_counts = {"complete": 0, "in_progress": 0, "validated": 0, "new": 0}

    for prp_data in data["prp_tracking"].values():
        if not prp_data.get("deprecated", False):
            priority = prp_data.get("corrected_priority", "unknown")
            if priority in priority_counts:
                priority_counts[priority] += 1

            status = prp_data.get("status", "unknown")
            if status in status_counts:
                status_counts[status] += 1

    # Update stats section
    data["stats"] = {
        "total_prps": 57,
        "active_prps": 55,  # After deprecating duplicates
        "deprecated_prps": 2,
        "priority_distribution": priority_counts,
        "status_distribution": status_counts,
        "completion_rate": round(status_counts["complete"] / 55, 3),
        "moscow_distribution": {
            "must_have_p0": f"{priority_counts['P0']} ({round(priority_counts['P0'] / 55 * 100)}%)",
            "should_have_p1": f"{priority_counts['P1']} ({round(priority_counts['P1'] / 55 * 100)}%)",
            "could_have_p2": f"{priority_counts['P2']} ({round(priority_counts['P2'] / 55 * 100)}%)",
            "wont_have_p3": f"{priority_counts['P3']} ({round(priority_counts['P3'] / 55 * 100)}%)",
        },
    }

    # Write updated YAML
    with open(yaml_path, "w") as f:
        yaml.dump(data, f, default_flow_style=False, sort_keys=False, width=120)

    print(f"✅ Updated {updated_count} PRPs with stable IDs and corrected priorities")
    print(
        f"✅ Priority distribution: P0={priority_counts['P0']}, P1={priority_counts['P1']}, P2={priority_counts['P2']}, P3={priority_counts['P3']}"
    )
    print(f"✅ Active PRPs: {55} (after deprecating 2 duplicates)")
    print(f"✅ Completion rate: {round(status_counts['complete'] / 55 * 100, 1)}%")

    return True


if __name__ == "__main__":
    migrate_yaml()
