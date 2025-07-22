#!/usr/bin/env python3
"""
PRP Organization Tool - Moves completed PRPs to Completed folder and updates INITIAL.md

This tool helps keep the PRP tracking organized by:
1. Moving completed PRP files from .claude/PRPs/ to .claude/PRPs/Completed/
2. Removing their stubs from INITIAL.md to keep the active list clean
3. Optionally updating status tracking files
"""

import os
import re
import shutil
import subprocess
from datetime import datetime
from pathlib import Path
from typing import List, Set, Tuple


def find_completed_prps(prp_dir: Path) -> List[Path]:
    """
    Find PRP files that are marked as completed.

    Args:
        prp_dir: Directory containing PRP files

    Returns:
        List of completed PRP file paths
    """
    completed_prps = []

    for prp_file in prp_dir.glob("*.md"):
        if prp_file.name.startswith("PRP-") and "Completed" not in str(prp_file):
            try:
                content = prp_file.read_text()

                # Check for completion indicators in the file
                # Look for actual PRP status completion, not code snippets
                completion_indicators = [
                    r"^\*\*Status\*\*.*[Cc]ompleted",  # **Status**: Completed
                    r"^Status:.*[Cc]ompleted",  # Status: Completed
                    r'EVIDENCE_COMPLETE.*"success".*true',  # Evidence footer with success
                    r"^\*\*Priority.*Status.*[Cc]ompleted",  # Priority/Status line
                    r"## COMPLETED.*✅",  # Section header with completed
                    r"# .*COMPLETED.*✅",  # Title with completed
                ]

                for indicator in completion_indicators:
                    if re.search(indicator, content, re.IGNORECASE | re.MULTILINE):
                        completed_prps.append(prp_file)
                        break

            except Exception as e:
                print(f"⚠️ Could not read {prp_file.name}: {e}")

    return completed_prps


def extract_prp_id_from_filename(filename: str) -> str:
    """Extract PRP ID from filename (e.g., 'PRP-1033-prerequisites.md' -> 'PRP-1033')"""
    match = re.match(r"([A-Z]+-[0-9A-Z]+)", filename)
    return match.group(1) if match else filename.replace(".md", "")


def extract_prp_info_from_initial(initial_content: str, prp_id: str) -> Tuple[str, int, int]:
    """
    Extract PRP information from INITIAL.md content.

    Returns:
        Tuple of (title, start_line, end_line) or ("", -1, -1) if not found
    """
    lines = initial_content.split("\n")

    # Look for the PRP entry
    for i, line in enumerate(lines):
        if prp_id in line and ("🔄" in line or "#### " in line):
            # Find the title
            title_match = re.search(r"#### 🔄 (.*?):", line)
            title = title_match.group(1) if title_match else prp_id

            # Find the end of this PRP entry (next PRP or section)
            end_line = len(lines)
            for j in range(i + 1, len(lines)):
                if re.match(r"^#### [🔄🚨❌]", lines[j]) or re.match(r"^## ", lines[j]):
                    end_line = j
                    break

            return title, i, end_line

    return "", -1, -1


def move_completed_prps(prp_dir: Path, completed_dir: Path, dry_run: bool = False) -> List[Tuple[str, str]]:
    """
    Move completed PRP files to the Completed directory.

    Args:
        prp_dir: Source directory containing PRP files
        completed_dir: Destination Completed directory
        dry_run: If True, only show what would be moved

    Returns:
        List of (source, destination) tuples for moved files
    """
    completed_prps = find_completed_prps(prp_dir)
    moved_files = []

    if not completed_prps:
        print("📝 No completed PRPs found to move")
        return moved_files

    # Ensure completed directory exists
    if not dry_run:
        completed_dir.mkdir(exist_ok=True)

    print(f"📦 Found {len(completed_prps)} completed PRPs to organize:")

    for prp_file in completed_prps:
        dest_file = completed_dir / prp_file.name

        if dry_run:
            print(f"   📁 WOULD MOVE: {prp_file.name} → Completed/")
            # Add to moved_files for dry-run processing
            moved_files.append((str(prp_file), str(dest_file)))
        else:
            if dest_file.exists():
                print(f"   ⚠️ SKIP: {prp_file.name} (already exists in Completed/)")
                continue

            try:
                shutil.move(str(prp_file), str(dest_file))
                print(f"   ✅ MOVED: {prp_file.name} → Completed/")
                moved_files.append((str(prp_file), str(dest_file)))
            except Exception as e:
                print(f"   ❌ FAILED to move {prp_file.name}: {e}")

    return moved_files


def update_initial_md(initial_file: Path, moved_files: List[Tuple[str, str]], dry_run: bool = False) -> int:
    """
    Remove completed PRP stubs from INITIAL.md.

    Args:
        initial_file: Path to INITIAL.md file
        moved_files: List of moved files to remove from INITIAL.md
        dry_run: If True, only show what would be removed

    Returns:
        Number of PRPs removed from INITIAL.md
    """
    if not moved_files:
        print("📝 No moved files to remove from INITIAL.md")
        return 0

    if not initial_file.exists():
        print("⚠️ INITIAL.md not found")
        return 0

    try:
        content = initial_file.read_text()
        original_content = content
        lines = content.split("\n")
        removed_count = 0

        print(f"\n📝 Updating INITIAL.md...")

        # Extract PRP IDs from moved files
        moved_prp_ids = set()
        for source, dest in moved_files:
            filename = Path(source).name
            prp_id = extract_prp_id_from_filename(filename)
            moved_prp_ids.add(prp_id)
            if dry_run:
                print(f"   🔍 Extracted PRP ID '{prp_id}' from '{filename}'")

        # Remove PRP sections from INITIAL.md
        new_lines = []
        skip_lines = False
        current_prp_id = None

        for i, line in enumerate(lines):
            # Check if this is a PRP header line
            prp_match = re.search(r"#### 🔄 ([A-Z]+-[0-9A-Z-]+)", line)
            if prp_match:
                current_prp_id = prp_match.group(1)
                skip_lines = current_prp_id in moved_prp_ids

                if skip_lines:
                    removed_count += 1
                    if not dry_run:
                        print(f"   🗑️ REMOVING: {current_prp_id} section")
                    else:
                        print(f"   🗑️ WOULD REMOVE: {current_prp_id} section")

            # Check if we've reached the next section/PRP
            elif re.match(r"^#### [🔄🚨❌]", line) or re.match(r"^## ", line):
                skip_lines = False
                current_prp_id = None

            # Add line if we're not skipping
            if not skip_lines:
                new_lines.append(line)

        # Update remaining count in header
        new_content = "\n".join(new_lines)
        if not dry_run and removed_count > 0:
            # Update the remaining work count
            remaining_pattern = r"(\*\*Remaining Work\*\*): (\d+) active PRPs"

            def update_remaining(match):
                current_count = int(match.group(2))
                new_count = max(0, current_count - removed_count)
                return f"{match.group(1)}: {new_count} active PRPs"

            new_content = re.sub(remaining_pattern, update_remaining, new_content)

            # Add update timestamp
            timestamp = datetime.now().strftime("%Y-%m-%d")
            new_content = re.sub(r"(\*\*Last Updated\*\*): \d{4}-\d{2}-\d{2}", f"\\1: {timestamp}", new_content)

        if not dry_run and new_content != original_content:
            initial_file.write_text(new_content)
            print(f"   ✅ Updated INITIAL.md (removed {removed_count} completed PRPs)")
        elif dry_run:
            print(f"   📝 WOULD UPDATE INITIAL.md (remove {removed_count} completed PRPs)")

        return removed_count

    except Exception as e:
        print(f"❌ Error updating INITIAL.md: {e}")
        return 0


def git_add_changes(files_to_add: List[str], dry_run: bool = False) -> bool:
    """
    Add the organized files to git staging.

    Args:
        files_to_add: List of files to add to git
        dry_run: If True, only show what would be added

    Returns:
        True if successful, False otherwise
    """
    if not files_to_add:
        return True

    try:
        if dry_run:
            print(f"\n🔧 WOULD ADD to git: {len(files_to_add)} files")
            for file_path in files_to_add:
                print(f"   📁 {file_path}")
        else:
            # Add files to git
            cmd = ["git", "add"] + files_to_add
            result = subprocess.run(cmd, capture_output=True, text=True, cwd=Path.cwd())

            if result.returncode == 0:
                print(f"✅ Added {len(files_to_add)} files to git staging")
                return True
            else:
                print(f"⚠️ Git add warning: {result.stderr}")
                return False

    except Exception as e:
        print(f"❌ Error adding files to git: {e}")
        return False


def main():
    """Main organizer function"""
    import argparse

    parser = argparse.ArgumentParser(description="Organize completed PRPs")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be done without making changes")
    parser.add_argument("--no-git", action="store_true", help="Skip git operations")

    args = parser.parse_args()

    print("🗂️ PRP Organization Tool")
    print("=" * 50)

    # Define paths
    project_root = Path(__file__).parent
    prp_dir = project_root / ".claude" / "PRPs"
    completed_dir = prp_dir / "Completed"
    initial_file = project_root / "INITIAL.md"

    if not prp_dir.exists():
        print("❌ .claude/PRPs directory not found")
        return 1

    if args.dry_run:
        print("🔍 DRY RUN MODE - No changes will be made")
        print()

    # Step 1: Move completed PRP files
    moved_files = move_completed_prps(prp_dir, completed_dir, dry_run=args.dry_run)

    # Step 2: Update INITIAL.md
    removed_count = update_initial_md(initial_file, moved_files, dry_run=args.dry_run)

    # Step 3: Git operations (if requested and not dry run)
    if not args.no_git and not args.dry_run and (moved_files or removed_count > 0):
        files_to_add = []

        # Add moved files in their new location
        for source, dest in moved_files:
            files_to_add.append(dest)

        # Add updated INITIAL.md
        if removed_count > 0:
            files_to_add.append(str(initial_file))

        git_add_changes(files_to_add, dry_run=args.dry_run)

    # Summary
    print("\n" + "=" * 50)
    if args.dry_run:
        print("🔍 DRY RUN COMPLETE - No changes made")
        print(f"📊 Would organize {len(moved_files)} PRPs")
        print(f"📝 Would remove {removed_count} stubs from INITIAL.md")
    else:
        print("✅ ORGANIZATION COMPLETE")
        print(f"📦 Moved {len(moved_files)} PRP files to Completed/")
        print(f"📝 Removed {removed_count} stubs from INITIAL.md")

        if moved_files:
            print("\n🎉 Completed PRPs organized successfully!")
            print("💡 Run 'git status' to see the staged changes")
        else:
            print("\n📝 No completed PRPs found to organize")

    return 0


if __name__ == "__main__":
    exit(main())
