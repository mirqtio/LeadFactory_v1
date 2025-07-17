#!/bin/bash
# Standard validation for Wave B tasks (95% coverage target)

set -e

echo "Running Wave B validation suite..."

# Run KEEP test suite
echo "→ Running KEEP tests..."
pytest -m "not phase_future and not slow" -q

# Check coverage meets Wave B requirement (95%)
echo "→ Checking coverage (95% required)..."
coverage run -m pytest tests/unit
coverage report --fail-under=95

# Lint-level compile check
echo "→ Checking Python syntax..."
python -m py_compile $(git ls-files "*.py")

# Always run Docker validation for Wave B
echo "→ Running Docker validation..."
make docker-test

echo "✓ Wave B validation complete!"