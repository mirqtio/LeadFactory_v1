#!/bin/bash
# Standard validation for Wave A tasks (80% coverage target)

set -e

echo "Running Wave A validation suite..."

# Run KEEP test suite
echo "→ Running KEEP tests..."
pytest -m "not phase_future and not slow" -q

# Check coverage meets Wave A requirement (80%)
echo "→ Checking coverage (80% required)..."
coverage run -m pytest tests/unit
coverage report --fail-under=80

# Lint-level compile check
echo "→ Checking Python syntax..."
python -m py_compile $(git ls-files "*.py")

# Optional: Run in Docker if requested
if [[ "$1" == "--docker" ]]; then
    echo "→ Running Docker validation..."
    make docker-test
fi

echo "✓ Wave A validation complete!"