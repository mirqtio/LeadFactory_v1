#!/bin/bash
#
# Setup script for bulletproof CI/CD that prevents GitHub failures
# Run this once to setup comprehensive local validation
#

set -e

echo "🛡️  Setting up Bulletproof CI/CD Protection..."
echo ""

# 1. Install and configure pre-commit
echo "1. Setting up enhanced pre-commit hooks..."
pip install pre-commit
pre-commit install
pre-commit install --hook-type pre-push

# 2. Install pre-push hook
echo "2. Installing comprehensive pre-push validation..."
cp .git/hooks/pre-push .git/hooks/pre-push.backup 2>/dev/null || true
cat > .git/hooks/pre-push << 'EOF'
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

chmod +x .git/hooks/pre-push

# 3. Validate the setup
echo "3. Testing the setup..."
if make quick-check; then
    echo "✅ Quick validation passed"
else
    echo "⚠️  Quick validation needs attention"
fi

echo ""
echo "🎉 Bulletproof CI/CD Protection Setup Complete!"
echo ""
echo "Available commands:"
echo "  make quick-check  - Fast validation for frequent commits"
echo "  make pre-push     - Complete CI simulation before push"
echo "  make ci-local     - Full GitHub CI simulation"
echo ""
echo "🛡️  From now on, pushes will be blocked if they would fail CI"
echo "✅ This should eliminate CI failures entirely"
echo ""