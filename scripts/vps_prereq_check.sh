#!/bin/bash
# VPS Prerequisites Check for LeadFactory Deployment

echo "🔍 VPS Prerequisites Check"
echo "========================="
echo ""

# Check user
echo "1. Current user: $(whoami)"
echo ""

# Check sudo access
echo "2. Sudo access:"
if sudo -n true 2>/dev/null; then
    echo "✅ Passwordless sudo is configured"
else
    echo "❌ Passwordless sudo NOT configured"
    echo "   Fix: Add to sudoers with: echo '$USER ALL=(ALL) NOPASSWD:ALL' | sudo tee /etc/sudoers.d/$USER"
fi
echo ""

# Check Docker
echo "3. Docker installation:"
if command -v docker &> /dev/null; then
    echo "✅ Docker is installed: $(docker --version)"
    if docker ps &> /dev/null; then
        echo "✅ User has Docker permissions"
    else
        echo "❌ User needs Docker permissions"
        echo "   Fix: sudo usermod -aG docker $USER && newgrp docker"
    fi
else
    echo "❌ Docker is NOT installed"
    echo "   Fix: curl -fsSL https://get.docker.com | sh"
fi
echo ""

# Check Docker Compose
echo "4. Docker Compose:"
if docker compose version &> /dev/null; then
    echo "✅ Docker Compose is installed: $(docker compose version)"
else
    echo "❌ Docker Compose is NOT installed"
    echo "   Fix: sudo apt-get update && sudo apt-get install docker-compose-plugin"
fi
echo ""

# Check Git
echo "5. Git installation:"
if command -v git &> /dev/null; then
    echo "✅ Git is installed: $(git --version)"
else
    echo "❌ Git is NOT installed"
    echo "   Fix: sudo apt-get update && sudo apt-get install git"
fi
echo ""

# Check GitHub SSH access
echo "6. GitHub SSH access:"
if ssh -T git@github.com 2>&1 | grep -q "successfully authenticated"; then
    echo "✅ GitHub SSH access is configured"
else
    echo "❌ GitHub SSH access NOT configured"
    echo "   Fix: Generate key with: ssh-keygen -t ed25519 -C 'vps-deploy'"
    echo "        Add public key to GitHub deploy keys"
    if [ -f ~/.ssh/id_ed25519.pub ]; then
        echo "   Your public key:"
        cat ~/.ssh/id_ed25519.pub
    fi
fi
echo ""

# Check directory permissions
echo "7. Directory permissions:"
if [ -d /srv ]; then
    echo "✅ /srv directory exists"
    if [ -w /srv ]; then
        echo "✅ User can write to /srv"
    else
        echo "❌ User cannot write to /srv"
        echo "   Fix: sudo chown $USER:$USER /srv"
    fi
else
    echo "❌ /srv directory does not exist"
    echo "   Fix: sudo mkdir -p /srv && sudo chown $USER:$USER /srv"
fi
echo ""

# Summary
echo "Summary:"
echo "--------"
echo "Run this script as the 'deploy' user on your VPS"
echo "Fix any ❌ items before running deployment"