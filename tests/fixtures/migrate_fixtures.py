#!/usr/bin/env python3
"""
Script to migrate existing conftest.py files to use centralized fixtures.

This script will:
1. Identify duplicate fixture definitions
2. Update imports to use centralized fixtures
3. Create backward compatibility aliases
4. Report on changes made
"""
import os
import re
from pathlib import Path
from typing import Dict, List, Tuple


class FixtureMigrator:
    """Migrate test fixtures to use centralized system."""

    # Common fixture patterns to replace
    FIXTURE_PATTERNS = {
        # Database fixtures
        r"@pytest\.fixture.*\ndef\s+(db_session|db|database)\s*\(": ("test_db", "Database session fixture"),
        r"@pytest\.fixture.*\ndef\s+(async_db_session|async_db)\s*\(": (
            "async_test_db",
            "Async database session fixture",
        ),
        # API fixtures
        r"@pytest\.fixture.*\ndef\s+(test_client|client)\s*\(": ("test_client", "FastAPI test client fixture"),
        r"@pytest\.fixture.*\ndef\s+(auth_headers|auth_token)\s*\(": ("auth_headers", "Authentication headers fixture"),
    }

    def __init__(self, dry_run: bool = True):
        self.dry_run = dry_run
        self.changes: List[Dict] = []

    def find_conftest_files(self, root_path: str = "tests") -> List[Path]:
        """Find all conftest.py files in the test directory."""
        conftest_files = []
        for root, dirs, files in os.walk(root_path):
            if "conftest.py" in files:
                conftest_files.append(Path(root) / "conftest.py")
        return conftest_files

    def analyze_fixture(self, content: str) -> Dict[str, List[str]]:
        """Analyze fixtures defined in a conftest file."""
        fixtures = {"database": [], "api": [], "external": [], "other": []}

        # Find all fixture definitions
        fixture_pattern = r"@pytest\.fixture.*?\ndef\s+(\w+)\s*\("
        matches = re.finditer(fixture_pattern, content, re.MULTILINE | re.DOTALL)

        for match in matches:
            fixture_name = match.group(1)

            # Categorize fixtures
            if any(db in fixture_name for db in ["db", "database", "session"]):
                fixtures["database"].append(fixture_name)
            elif any(api in fixture_name for api in ["client", "auth", "api"]):
                fixtures["api"].append(fixture_name)
            elif any(ext in fixture_name for ext in ["mock", "stub", "fake"]):
                fixtures["external"].append(fixture_name)
            else:
                fixtures["other"].append(fixture_name)

        return fixtures

    def generate_migration(self, fixtures: Dict[str, List[str]], file_path: Path) -> str:
        """Generate migrated conftest content."""
        module_name = file_path.parent.name

        lines = [
            '"""',
            f"Shared test configuration for {module_name}",
            "",
            "Uses centralized fixtures from tests.fixtures package.",
            '"""',
            "import pytest",
            "",
        ]

        # Determine which fixtures to import
        imports = []
        aliases = []

        if fixtures["database"]:
            imports.extend(["test_db", "async_test_db", "seeded_db"])
            # Create aliases for backward compatibility
            for fixture in fixtures["database"]:
                if fixture != "test_db":
                    aliases.append(f"{fixture} = test_db")

        if fixtures["api"]:
            imports.extend(["test_client", "authenticated_client", "api_helper"])
            for fixture in fixtures["api"]:
                if fixture == "client":
                    aliases.append("client = test_client")

        if fixtures["external"]:
            imports.extend(["mock_all_external_services"])

        if imports:
            lines.append("# Import centralized fixtures")
            lines.append(f"from tests.fixtures import {', '.join(imports)}  # noqa: F401")
            lines.append("")

        if aliases:
            lines.append("# Aliases for backward compatibility")
            for alias in aliases:
                lines.append(alias)
            lines.append("")

        # Add note about remaining fixtures
        if fixtures["other"]:
            lines.append("# Domain-specific fixtures")
            lines.append("# TODO: Consider moving these to centralized fixtures if reusable")
            lines.append("")

        return "\n".join(lines)

    def migrate_file(self, file_path: Path) -> bool:
        """Migrate a single conftest file."""
        print(f"\nAnalyzing: {file_path}")

        try:
            content = file_path.read_text()
            fixtures = self.analyze_fixture(content)

            # Check if already migrated
            if "from tests.fixtures import" in content:
                print("  ✓ Already migrated")
                return False

            # Check if has fixtures to migrate
            total_fixtures = sum(len(f) for f in fixtures.values())
            if total_fixtures == 0:
                print("  ✓ No fixtures to migrate")
                return False

            # Report findings
            print(f"  Found {total_fixtures} fixtures:")
            for category, fixture_list in fixtures.items():
                if fixture_list:
                    print(f"    - {category}: {', '.join(fixture_list)}")

            # Generate new content
            new_content = self.generate_migration(fixtures, file_path)

            # Keep any custom fixtures
            if fixtures["other"]:
                print("  Preserving custom fixtures:")
                # Extract custom fixture definitions
                for fixture in fixtures["other"]:
                    pattern = rf"(@pytest\.fixture.*?\ndef\s+{fixture}\s*\(.*?\n(?:.*?\n)*?)(?=@pytest\.fixture|\Z)"
                    match = re.search(pattern, content, re.MULTILINE | re.DOTALL)
                    if match:
                        new_content += "\n" + match.group(1)
                        print(f"    - {fixture}")

            if not self.dry_run:
                # Backup original
                backup_path = file_path.with_suffix(".py.bak")
                file_path.rename(backup_path)

                # Write new content
                file_path.write_text(new_content)
                print(f"  ✓ Migrated successfully (backup: {backup_path})")
            else:
                print("  ✓ Would migrate (dry run)")

            self.changes.append({"file": str(file_path), "fixtures": fixtures, "migrated": True})

            return True

        except Exception as e:
            print(f"  ✗ Error: {e}")
            return False

    def run(self, root_path: str = "tests") -> None:
        """Run the migration process."""
        print("Fixture Migration Tool")
        print("=" * 50)
        print(f"Mode: {'DRY RUN' if self.dry_run else 'LIVE'}")
        print(f"Root path: {root_path}")
        print()

        # Find all conftest files
        conftest_files = self.find_conftest_files(root_path)
        print(f"Found {len(conftest_files)} conftest.py files")

        # Migrate each file
        migrated_count = 0
        for file_path in conftest_files:
            if self.migrate_file(file_path):
                migrated_count += 1

        # Summary
        print("\n" + "=" * 50)
        print("Migration Summary:")
        print(f"  - Files analyzed: {len(conftest_files)}")
        print(f"  - Files migrated: {migrated_count}")

        if self.dry_run:
            print("\nThis was a dry run. To apply changes, run with --apply flag")
        else:
            print("\nMigration complete! Original files backed up with .bak extension")

        # Detailed report
        if self.changes:
            print("\nDetailed Report:")
            for change in self.changes:
                print(f"\n  {change['file']}:")
                total = sum(len(f) for f in change["fixtures"].values())
                print(f"    - Total fixtures: {total}")
                for category, fixtures in change["fixtures"].items():
                    if fixtures:
                        print(f"    - {category}: {len(fixtures)}")


def main():
    """Run the migration tool."""
    import argparse

    parser = argparse.ArgumentParser(description="Migrate test fixtures to centralized system")
    parser.add_argument("--apply", action="store_true", help="Apply changes (default is dry run)")
    parser.add_argument("--path", default="tests", help="Root path to search for tests")
    args = parser.parse_args()

    migrator = FixtureMigrator(dry_run=not args.apply)
    migrator.run(args.path)


if __name__ == "__main__":
    main()
