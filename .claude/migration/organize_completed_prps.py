#!/usr/bin/env python3
"""
Organize Completed PRP Files
Move completed PRP files to PRPs/Completed folder based on stable ID tracking
"""

import shutil
from pathlib import Path

import yaml


def get_completed_prps():
    """Get list of completed PRPs from tracking system."""

    yaml_path = Path(".claude/prp_tracking/prp_status.yaml")
    with open(yaml_path) as f:
        data = yaml.safe_load(f)

    completed_prps = []
    for legacy_id, prp_data in data["prp_tracking"].items():
        if prp_data.get("status") == "complete":
            completed_prps.append(
                {
                    "legacy_id": legacy_id,
                    "stable_id": prp_data.get("stable_id"),
                    "title": prp_data.get("title"),
                    "priority": prp_data.get("corrected_priority"),
                }
            )

    return completed_prps


def find_prp_file(legacy_id, prp_title):
    """Find the PRP file corresponding to a legacy ID."""

    prp_dir = Path(".claude/PRPs")

    # Common patterns for PRP files
    patterns = [
        f"PRP-{legacy_id.lower()}*.md",
        f"PRP-{legacy_id.replace('-', '')}*.md",
        f"{legacy_id.lower()}*.md",
        f"*{legacy_id.lower()}*.md",
    ]

    for pattern in patterns:
        matches = list(prp_dir.glob(pattern))
        if matches:
            return matches[0]

    # Manual search by title keywords
    title_words = prp_title.lower().replace(" ", "-").replace("&", "and")
    for prp_file in prp_dir.glob("*.md"):
        if any(word in prp_file.name.lower() for word in title_words.split("-")[:3]):
            return prp_file

    return None


def organize_completed_prps():
    """Move completed PRP files to Completed folder."""

    print("🗂️  ORGANIZING COMPLETED PRP FILES")
    print("=" * 50)

    completed_dir = Path(".claude/PRPs/Completed")
    completed_dir.mkdir(exist_ok=True)

    completed_prps = get_completed_prps()

    moved_count = 0
    not_found_count = 0

    for prp in completed_prps:
        legacy_id = prp["legacy_id"]
        stable_id = prp["stable_id"]
        title = prp["title"]
        priority = prp["priority"]

        # Find the corresponding file
        prp_file = find_prp_file(legacy_id, title)

        if prp_file and prp_file.exists():
            # Create new filename with stable ID
            new_filename = f"{stable_id}_{legacy_id}_{title.replace(' ', '_').replace('&', 'and')}.md"
            new_path = completed_dir / new_filename

            # Move the file
            shutil.move(str(prp_file), str(new_path))
            print(f"✅ Moved: {prp_file.name} → {new_filename}")
            moved_count += 1

        else:
            print(f"❌ Not found: {legacy_id} - {title}")
            not_found_count += 1

    print("\n📊 ORGANIZATION SUMMARY")
    print("=" * 50)
    print(f"✅ Files moved: {moved_count}")
    print(f"❌ Files not found: {not_found_count}")
    print(f"📁 Total completed PRPs: {len(completed_prps)}")

    if moved_count > 0:
        print("\n📂 Completed PRP files now organized in:")
        print("   .claude/PRPs/Completed/")

    return moved_count, not_found_count


if __name__ == "__main__":
    organize_completed_prps()
