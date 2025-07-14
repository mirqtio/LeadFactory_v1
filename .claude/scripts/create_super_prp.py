#!/usr/bin/env python3
"""Create a combined super PRP from all individual PRPs."""

from pathlib import Path


def extract_prp_content(prp_path):
    """Extract key content from a PRP, excluding the repetitive context sections."""
    with open(prp_path, "r") as f:
        content = f.read()

    # Find where the Critical Context section starts
    context_start = content.find("## Critical Context")
    if context_start > 0:
        # Keep everything before Critical Context
        content = content[:context_start].strip()

    return content


def create_super_prp():
    """Combine all PRPs into one super document."""
    prp_dir = Path(".claude/PRPs")
    super_prp_path = prp_dir / "SUPER-PRP-ALL-TASKS.md"

    # Read existing header
    with open(super_prp_path, "r") as f:
        header = f.read()

    # Collect all PRPs
    prp_files = sorted([f for f in prp_dir.glob("PRP-P*.md")])

    combined_content = [header]

    # Add each PRP
    for prp_file in prp_files:
        task_id = prp_file.stem.replace("PRP-", "")

        # Extract content without the repetitive context
        prp_content = extract_prp_content(prp_file)

        # Add section divider
        combined_content.append(f"\n---\n\n## {task_id}\n")

        # Remove the redundant title line and adjust headers
        lines = prp_content.split("\n")
        adjusted_lines = []

        for line in lines:
            # Skip the first title line
            if line.startswith("# PRP:"):
                continue
            # Demote headers by one level for better hierarchy
            elif line.startswith("## "):
                adjusted_lines.append("### " + line[3:])
            elif line.startswith("### "):
                adjusted_lines.append("#### " + line[4:])
            elif line.startswith("#### "):
                adjusted_lines.append("##### " + line[5:])
            else:
                adjusted_lines.append(line)

        combined_content.append("\n".join(adjusted_lines))

    # Add shared context sections at the end
    combined_content.append(
        """
---

## Shared Context (Applies to All Tasks)

### Critical Success Factors
1. **Wave Separation**: All P0 tasks must complete before any P1/P2 tasks begin
2. **Coverage Requirements**: Maintain >80% coverage throughout Wave A, target >95% in Wave B
3. **Docker Consistency**: All tests must pass in Docker containers, not just locally
4. **No Scope Creep**: Only modify files within specified integration points
5. **Documentation**: Update README and docs for any behavior changes

### Common Validation Commands
```bash
# Standard validation suite for all tasks
pytest -m "not phase_future and not slow" -q  # KEEP suite
coverage run -m pytest tests/unit              # Coverage check
coverage report --fail-under=80                # Wave A minimum
python -m py_compile $(git ls-files "*.py")   # Syntax check
```

### DO NOT IMPLEMENT (From CURRENT_STATE.md)
- **Yelp Integration**: All Yelp-related code/tests/migrations
- **Mac Mini Deployment**: Use VPS + Docker only
- **Top 10% Filtering**: Analyze 100% of purchased data
- **$199 Pricing**: Use $399 launch price
- **Simple Email Templates**: Use LLM-powered personalization
- **Basic scoring only**: Implement full multi-metric assessment

### Environment Setup (All Tasks)
- Python 3.11.0 (exact version for CI compatibility)
- Docker 20.10+ for containerization
- `USE_STUBS=true` for local development
- Virtual environment activation required
- All sensitive data in `.env` file

---

**Note**: The full CLAUDE.md and CURRENT_STATE.md content has been removed from individual PRPs above to reduce
redundancy. These documents should be reviewed separately and apply to all tasks.
"""
    )

    # Write combined file
    with open(super_prp_path, "w") as f:
        f.write("\n".join(combined_content))

    print(f"✓ Created super PRP with {len(prp_files)} tasks")
    print(f"  Location: {super_prp_path}")

    # Count lines
    with open(super_prp_path, "r") as f:
        line_count = len(f.readlines())
    print(f"  Total lines: {line_count:,}")


if __name__ == "__main__":
    create_super_prp()
