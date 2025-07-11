#!/bin/bash
# Setup GitHub deploy key on VPS

echo "🔐 GitHub Deploy Key Setup"
echo "========================="
echo ""
echo "This script will help you set up SSH access from your VPS to GitHub"
echo "so the deployment can clone the repository."
echo ""

# Check if key already exists
if [ -f ~/.ssh/id_ed25519 ]; then
    echo "⚠️  SSH key already exists at ~/.ssh/id_ed25519"
    echo "Current public key:"
    cat ~/.ssh/id_ed25519.pub
    echo ""
    echo "Testing GitHub access..."
    if ssh -T git@github.com 2>&1 | grep -q "successfully authenticated"; then
        echo "✅ GitHub access is already working!"
        exit 0
    else
        echo "❌ Key exists but GitHub access not working"
        echo "You need to add the above public key to your repository"
    fi
else
    echo "Creating new SSH key for GitHub access..."
    ssh-keygen -t ed25519 -C "vps-deploy@$(hostname)" -f ~/.ssh/id_ed25519 -N ""
    echo ""
    echo "✅ Key generated successfully!"
fi

echo ""
echo "📋 Next steps:"
echo "=============="
echo ""
echo "1. Copy this public key:"
echo ""
cat ~/.ssh/id_ed25519.pub
echo ""
echo "2. Add it to your GitHub repository:"
echo "   - Go to: https://github.com/mirqtio/LeadFactory_v1/settings/keys"
echo "   - Click 'New deploy key'"
echo "   - Title: 'VPS Deploy Key'"
echo "   - Key: [paste the public key above]"
echo "   - ✅ Check 'Allow write access' (optional, for pushing tags)"
echo "   - Click 'Add key'"
echo ""
echo "3. Test the connection:"
echo "   ssh -T git@github.com"
echo ""
echo "You should see: 'Hi mirqtio/LeadFactory_v1! You've successfully authenticated...'"