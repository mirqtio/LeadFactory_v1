#!/bin/bash
#
# Setup script for git hooks
# This ensures all developers have the correct hooks installed
#

set -e

echo "🔧 Setting up git hooks..."

# Get the project root directory
PROJECT_ROOT="$(git rev-parse --show-toplevel 2>/dev/null || echo ".")"
HOOKS_DIR="$PROJECT_ROOT/.git/hooks"

# Check if we're in a git repository
if [ ! -d "$HOOKS_DIR" ]; then
    echo "❌ Error: Not in a git repository or .git/hooks directory not found"
    exit 1
fi

# Create pre-commit hook
cat > "$HOOKS_DIR/pre-commit" << 'EOF'
#!/bin/bash
#
# Pre-commit hook that runs quick validation checks
# This prevents basic issues from being committed
#

echo "🚀 Pre-commit validation starting..."

# Check if we're in the correct directory
if [ ! -f "Makefile" ]; then
    echo "❌ Error: Cannot find Makefile. Are you in the project root?"
    exit 1
fi

# Run quick validation checks
if ! make quick-check; then
    echo ""
    echo "❌ Pre-commit validation FAILED!"
    echo ""
    echo "🚨 Commit blocked - please fix issues before committing"
    echo ""
    echo "To fix:"
    echo "  1. Run: make quick-check"
    echo "  2. Fix any issues reported"
    echo "  3. Try committing again"
    echo ""
    echo "To bypass (NOT recommended):"
    echo "  git commit --no-verify"
    echo ""
    exit 1
fi

echo ""
echo "✅ Pre-commit validation PASSED!"
echo ""
echo "=================================================="
echo "📝 REMINDER: Task Completion Requirements"
echo "=================================================="
echo "Before marking ANY task as complete, ensure:"
echo "✓ ALL CI checks are passing GREEN (run: make pre-push)"
echo "✓ Test Suite is passing"
echo "✓ Docker Build is passing"
echo "✓ Linting is passing"
echo "✓ Deploy to VPS is passing"
echo ""
echo "Full validation will run on pre-push using BPCI"
echo "=================================================="
echo ""

exit 0
EOF

# Create pre-push hook
cat > "$HOOKS_DIR/pre-push" << 'EOF'
#!/bin/bash
#
# Pre-push hook that ensures local validation passes before pushing to GitHub
# This prevents CI failures by catching issues locally first
#

echo "🛡️  Pre-push validation starting..."

# Run the comprehensive pre-push validation
if ! make pre-push; then
    echo ""
    echo "❌ Pre-push validation FAILED!"
    echo ""
    echo "🚨 Push blocked to prevent CI failures"
    echo ""
    echo "To fix:"
    echo "  1. Run: make pre-push"
    echo "  2. Fix any issues reported"
    echo "  3. Try pushing again"
    echo ""
    echo "For quick checks during development:"
    echo "  make quick-check"
    echo ""
    exit 1
fi

echo ""
echo "✅ Pre-push validation PASSED!"
echo "🚀 Safe to push - CI should pass"
echo ""

exit 0
EOF

# Make hooks executable
chmod +x "$HOOKS_DIR/pre-commit"
chmod +x "$HOOKS_DIR/pre-push"

echo "✅ Git hooks installed successfully!"
echo ""
echo "Hooks installed:"
echo "  - pre-commit: Runs quick validation (lint + format + core tests)"
echo "  - pre-push: Runs full BPCI validation"
echo ""
echo "To test hooks:"
echo "  - Pre-commit: make a small change and try to commit"
echo "  - Pre-push: try to push after committing"
echo ""
echo "To bypass hooks (not recommended):"
echo "  - git commit --no-verify"
echo "  - git push --no-verify"
echo ""

# Check if pre-commit framework is installed
if command -v pre-commit &> /dev/null; then
    echo "📦 pre-commit framework detected. Installing hooks..."
    pre-commit install
    echo "✅ pre-commit framework hooks installed"
else
    echo "ℹ️  Note: pre-commit framework not installed"
    echo "   To install: pip install pre-commit && pre-commit install"
fi

echo ""
echo "🎉 Setup complete!"