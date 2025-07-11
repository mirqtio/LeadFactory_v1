#!/bin/bash
# Enhanced PRP Pipeline Runner with Validation Gates

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

echo "🚀 LeadFactory PRP Pipeline with Gold-Standard Validation"
echo "========================================================="
echo

# Check dependencies
echo "📋 Checking dependencies..."

# Check for Python
if ! command -v python3 &> /dev/null; then
    echo "❌ Python 3 not found"
    exit 1
fi

# Check for pydantic
if ! python3 -c "import pydantic" 2>/dev/null; then
    echo "⚠️  Installing pydantic..."
    pip install pydantic
fi

# Check for ruff (optional)
if command -v ruff &> /dev/null; then
    echo "✅ Ruff linter found"
else
    echo "⚠️  Ruff not found (lint checks will be skipped)"
    echo "   Install with: pip install ruff"
fi

echo

# Change to project root
cd "$PROJECT_ROOT"

# Run the command
if [ $# -eq 0 ]; then
    echo "Usage: $0 [generate|execute|status|test]"
    exit 1
fi

case "$1" in
    generate)
        echo "🔨 Generating PRPs with validation gates..."
        python3 "$SCRIPT_DIR/recursive_prp_processor.py" generate
        ;;
    execute)
        echo "🚀 Executing PRPs with CRITIC + Judge loops..."
        python3 "$SCRIPT_DIR/recursive_prp_processor.py" execute
        ;;
    status)
        echo "📊 Checking PRP execution status..."
        python3 "$SCRIPT_DIR/recursive_prp_processor.py" status
        ;;
    test)
        echo "🧪 Running validation tests..."
        python3 "$SCRIPT_DIR/test_validation.py"
        ;;
    *)
        echo "Unknown command: $1"
        echo "Usage: $0 [generate|execute|status|test]"
        exit 1
        ;;
esac

echo
echo "✨ Pipeline complete!"