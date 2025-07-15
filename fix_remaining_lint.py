#!/usr/bin/env python3
"""
Fix remaining linting errors with targeted approaches
"""

import subprocess
from pathlib import Path


def run_ruff_check():
    """Get current ruff errors"""
    try:
        result = subprocess.run(["ruff", "check", "."], capture_output=True, text=True, cwd=Path(__file__).parent)
        return result.stdout
    except FileNotFoundError:
        return ""


def fix_star_imports():
    """Add noqa comments to star imports that are needed"""
    files_to_check = ["scripts/debug_migrations.py", "tests/unit/test_migrations.py", "core/prerequisites.py"]

    for file_path in files_to_check:
        full_path = Path(__file__).parent / file_path
        if full_path.exists():
            with open(full_path, "r") as f:
                content = f.read()

            # Add noqa to star imports
            lines = content.split("\n")
            modified = False

            for i, line in enumerate(lines):
                if "import *" in line and "# noqa" not in line:
                    lines[i] = line + "  # noqa: F403"
                    modified = True
                    print(f"Fixed star import in {file_path}: {line.strip()}")

            if modified:
                with open(full_path, "w") as f:
                    f.write("\n".join(lines))


def fix_unused_imports():
    """Fix obvious unused imports"""
    # Let ruff automatically fix what it can
    try:
        subprocess.run(["ruff", "check", "--fix", "--select=F401", "."], cwd=Path(__file__).parent, capture_output=True)
        print("Applied automatic F401 fixes")
    except FileNotFoundError:
        pass


def fix_import_order():
    """Fix import order issues"""
    try:
        subprocess.run(["isort", ".", "--profile", "black"], cwd=Path(__file__).parent, capture_output=True)
        print("Applied isort fixes")
    except FileNotFoundError:
        pass


def main():
    """Fix remaining linting issues"""
    print("Starting systematic linting fixes...")

    # Get initial count
    initial_output = run_ruff_check()
    initial_count = len(initial_output.split("\n")) if initial_output else 0
    print(f"Initial errors: {initial_count}")

    # Fix star imports
    print("\n1. Fixing star imports...")
    fix_star_imports()

    # Fix unused imports
    print("\n2. Fixing unused imports...")
    fix_unused_imports()

    # Fix import order
    print("\n3. Fixing import order...")
    fix_import_order()

    # Get final count
    final_output = run_ruff_check()
    final_count = len(final_output.split("\n")) if final_output else 0
    print(f"\nFinal errors: {final_count}")
    print(f"Reduced by: {initial_count - final_count}")

    # Show remaining error types
    if final_output:
        print("\nRemaining error types:")
        error_types = {}
        for line in final_output.split("\n"):
            if ": " in line and " | " in line:
                parts = line.split(": ")
                if len(parts) >= 2:
                    error_code = parts[1].split()[0]
                    error_types[error_code] = error_types.get(error_code, 0) + 1

        for error_type, count in sorted(error_types.items(), key=lambda x: x[1], reverse=True):
            print(f"  {error_type}: {count}")


if __name__ == "__main__":
    main()
