#!/usr/bin/env python3
"""Validate a single PRP through the six-gate validation pipeline."""

import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import List

# Import the validation components from recursive_prp_processor
sys.path.insert(0, str(Path(__file__).parent))
from recursive_prp_processor import PRPGenerator  # noqa: E402


@dataclass
class MockTask:
    """Mock task for single PRP validation."""

    priority: str
    title: str
    dependencies: List[str]
    goal: str
    integration_points: List[str]
    tests_to_pass: List[str]
    acceptance_criteria: List[str]
    wave: str

    @property
    def slug(self):
        return re.sub(r"[^a-z0-9-]+", "-", self.title.lower()).strip("-")

    @property
    def prp_filename(self):
        return f"PRP-{self.priority}-{self.slug}.md"


def extract_task_from_prp(prp_path: str) -> MockTask:
    """Extract task data from a PRP file"""
    with open(prp_path, "r") as f:
        content = f.read()

    # Extract task ID and title from header
    header_match = re.search(r"# PRP-(P\d+-\d{3})\s+(.+)", content)
    if not header_match:
        raise ValueError("Could not extract task ID and title from PRP")

    task_id = header_match.group(1)
    title = header_match.group(2).strip()

    # Extract dependencies
    deps_match = re.search(r"## Dependencies\s*\n(.+?)(?=\n##|\Z)", content, re.DOTALL)
    dependencies = []
    if deps_match:
        deps_text = deps_match.group(1).strip()
        if deps_text and deps_text != "None":
            # Parse dependency list
            dep_lines = deps_text.split("\n")
            for line in dep_lines:
                dep_match = re.search(r"(P\d+-\d{3})", line)
                if dep_match:
                    dependencies.append(dep_match.group(1))

    # Extract goal
    goal_match = re.search(r"## Goal\s*\n(.+?)(?=\n##|\Z)", content, re.DOTALL)
    goal = goal_match.group(1).strip() if goal_match else ""

    # Extract acceptance criteria
    criteria_match = re.search(r"### Success Criteria\s*\n(.+?)(?=\n##|\Z)", content, re.DOTALL)
    acceptance_criteria = []
    if criteria_match:
        criteria_text = criteria_match.group(1)
        for line in criteria_text.split("\n"):
            if line.strip().startswith("- [ ]"):
                acceptance_criteria.append(line.strip()[5:].strip())

    # Extract integration points
    integration_match = re.search(r"### Integration Points\s*\n(.+?)(?=\n###|\Z)", content, re.DOTALL)
    integration_points = []
    if integration_match:
        int_text = integration_match.group(1)
        for line in int_text.split("\n"):
            if line.strip().startswith("-"):
                integration_points.append(line.strip()[1:].strip())

    # Extract validation gates (as tests to pass)
    tests_match = re.search(r"### Executable Tests\s*\n```bash\s*\n(.+?)```", content, re.DOTALL)
    tests_to_pass = []
    if tests_match:
        tests_text = tests_match.group(1)
        for line in tests_text.split("\n"):
            if line.strip() and not line.startswith("#"):
                tests_to_pass.append(line.strip())

    # Determine wave based on task ID
    wave = "A" if task_id.startswith("P0") else "B"

    return MockTask(
        priority=task_id,
        title=title,
        dependencies=dependencies,
        goal=goal,
        integration_points=integration_points,
        tests_to_pass=tests_to_pass,
        acceptance_criteria=acceptance_criteria,
        wave=wave,
    )


def main():
    if len(sys.argv) < 2:
        print("Usage: python validate_single_prp.py <path_to_prp>")
        sys.exit(1)

    prp_path = sys.argv[1]
    if not Path(prp_path).exists():
        print(f"Error: PRP file not found: {prp_path}")
        sys.exit(1)

    print(f"Validating PRP: {prp_path}")
    print("=" * 50)

    try:
        # Extract task data from PRP
        task = extract_task_from_prp(prp_path)
        print(f"Task ID: {task.priority}")
        print(f"Title: {task.title}")
        print(f"Wave: {task.wave}")
        print()

        # Run validation
        generator = PRPGenerator()
        with open(prp_path, "r") as f:
            prp_content = f.read()

        # Run six-gate validation
        success = generator._validate_prp(task, prp_content)

        if success:
            print("\n✅ PRP validation PASSED!")
        else:
            print("\n❌ PRP validation FAILED!")
            sys.exit(1)

    except Exception as e:
        print(f"Error during validation: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
