#!/bin/bash
"""
Setup Smoke-Only CI Gates
Implements GPT o3's recommendation for smoke tests as merge gates
"""

echo "🚀 Setting up Smoke-Only CI Gates..."

# Get repository information
REPO=$(gh repo view --json nameWithOwner -q .nameWithOwner)
echo "Repository: $REPO"

# Enable branch protection with Ultra-Fast CI as required check
echo "📋 Configuring branch protection for main branch..."

gh api \
  --method PUT \
  -H "Accept: application/vnd.github+json" \
  "/repos/$REPO/branches/main/protection" \
  --field required_status_checks='{
    "strict": true,
    "contexts": [
      "Ultra-Fast CI Pipeline / ultra-fast-test",
      "Ultra-Fast CI Pipeline / fast-smoke-test"
    ]
  }' \
  --field enforce_admins=false \
  --field required_pull_request_reviews='{
    "required_approving_review_count": 0,
    "dismiss_stale_reviews": false,
    "require_code_owner_reviews": false
  }' \
  --field restrictions=null \
  --field required_linear_history=true \
  --field allow_force_pushes=false \
  --field allow_deletions=false

if [ $? -eq 0 ]; then
    echo "✅ Branch protection configured successfully!"
    echo "   - Ultra-Fast CI Pipeline is now required for merges"
    echo "   - Linear history enforced"
    echo "   - Force pushes disabled"
else
    echo "❌ Failed to configure branch protection"
    echo "   You may need admin permissions or to configure this manually"
fi

echo ""
echo "🔥 Smoke-Only CI Configuration Complete!"
echo ""
echo "**Current Setup:**"
echo "  - Merge Gate: Ultra-Fast CI Pipeline (~3 minutes)"
echo "  - Tests: Core unit tests + import validation"
echo "  - Full Regression: Runs post-merge via test-full.yml"
echo ""
echo "**How it works:**"
echo "  1. Developer pushes to main (or PR)"
echo "  2. Ultra-Fast CI runs in <3 minutes"
echo "  3. If smoke tests pass → merge allowed"
echo "  4. Full test suite runs after merge"
echo "  5. Failures trigger auto-generated fix PRPs"
echo ""
echo "This follows GPT o3's recommendation for fast feedback loops!"