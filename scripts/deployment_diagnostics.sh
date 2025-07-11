#!/bin/bash
# Comprehensive deployment diagnostics script
# Run this on your VPS to collect all necessary troubleshooting information

set -e

echo "🔍 LeadFactory Deployment Diagnostics"
echo "===================================="
echo "Generated at: $(date)"
echo ""

# System Information
echo "1. SYSTEM INFORMATION"
echo "-------------------"
echo "OS: $(cat /etc/os-release | grep PRETTY_NAME | cut -d= -f2)"
echo "Kernel: $(uname -r)"
echo "Memory: $(free -h | grep Mem | awk '{print $2}')"
echo "Disk Space:"
df -h / | tail -1
echo ""

# Docker Status
echo "2. DOCKER STATUS"
echo "---------------"
echo "Docker Version:"
docker --version 2>&1 || echo "Docker not installed"
echo "Docker Compose Version:"
docker compose version 2>&1 || echo "Docker Compose not installed"
echo "Docker Service Status:"
systemctl is-active docker 2>&1 || echo "Docker service not running"
echo "Current User Docker Access:"
docker ps >/dev/null 2>&1 && echo "✓ User has Docker access" || echo "✗ User needs Docker permissions"
echo ""

# Repository Status
echo "3. REPOSITORY STATUS"
echo "------------------"
if [ -d /srv/leadfactory ]; then
    echo "✓ Repository directory exists"
    cd /srv/leadfactory
    echo "Git Remote:"
    git remote -v 2>&1 || echo "Not a git repository"
    echo "Current Branch:"
    git branch --show-current 2>&1 || echo "No git branch"
    echo "Last Commit:"
    git log -1 --oneline 2>&1 || echo "No commits"
    echo "Directory Permissions:"
    ls -la /srv/leadfactory | head -5
else
    echo "✗ Repository directory /srv/leadfactory does not exist"
fi
echo ""

# Docker Compose Status
echo "4. DOCKER COMPOSE STATUS"
echo "----------------------"
if [ -f /srv/leadfactory/docker-compose.prod.yml ]; then
    echo "✓ docker-compose.prod.yml exists"
    cd /srv/leadfactory
    echo "Running Containers:"
    docker compose -f docker-compose.prod.yml ps 2>&1 || echo "Failed to list containers"
    echo ""
    echo "Container Logs (last 20 lines each):"
    echo "--- Web Container ---"
    docker compose -f docker-compose.prod.yml logs --tail 20 web 2>&1 || echo "No web logs"
    echo "--- DB Container ---"
    docker compose -f docker-compose.prod.yml logs --tail 20 db 2>&1 || echo "No db logs"
    echo "--- Redis Container ---"
    docker compose -f docker-compose.prod.yml logs --tail 20 redis 2>&1 || echo "No redis logs"
else
    echo "✗ docker-compose.prod.yml not found"
fi
echo ""

# Environment Configuration
echo "5. ENVIRONMENT CONFIGURATION"
echo "--------------------------"
if [ -f /srv/leadfactory/.env ]; then
    echo "✓ .env file exists"
    echo "Environment variables (sanitized):"
    grep -E "^[A-Z_]+=" /srv/leadfactory/.env | sed 's/=.*/=<SET>/'
else
    echo "✗ .env file not found at /srv/leadfactory/.env"
fi
echo ""

# Network Status
echo "6. NETWORK STATUS"
echo "----------------"
echo "Port 8000 Status:"
netstat -tlnp 2>&1 | grep :8000 || echo "Port 8000 not listening"
echo "Port 80 Status:"
netstat -tlnp 2>&1 | grep :80 || echo "Port 80 not listening"
echo ""

# Health Check
echo "7. HEALTH CHECK"
echo "--------------"
if curl -f -s http://localhost:8000/health >/dev/null 2>&1; then
    echo "✓ Health endpoint responding"
    echo "Response:"
    curl -s http://localhost:8000/health | python3 -m json.tool 2>&1 || curl -s http://localhost:8000/health
else
    echo "✗ Health endpoint not responding"
    echo "Curl output:"
    curl -v http://localhost:8000/health 2>&1
fi
echo ""

# GitHub SSH Access
echo "8. GITHUB SSH ACCESS"
echo "-------------------"
echo "SSH Key Status:"
ls -la ~/.ssh/id_* 2>&1 | grep -E "(id_rsa|id_ed25519)" || echo "No SSH keys found"
echo "GitHub SSH Test:"
ssh -T git@github.com 2>&1 || true
echo ""

# Recent System Logs
echo "9. RECENT SYSTEM LOGS"
echo "-------------------"
echo "Docker daemon logs (last 20 lines):"
journalctl -u docker --no-pager -n 20 2>&1 || echo "Cannot access Docker logs"
echo ""

# Recommendations
echo "10. AUTOMATED RECOMMENDATIONS"
echo "----------------------------"

# Check common issues
if ! docker --version >/dev/null 2>&1; then
    echo "⚠️  Install Docker: curl -fsSL https://get.docker.com | sh"
fi

if ! docker compose version >/dev/null 2>&1; then
    echo "⚠️  Install Docker Compose plugin: sudo apt-get install docker-compose-plugin"
fi

if ! docker ps >/dev/null 2>&1; then
    echo "⚠️  Add user to docker group: sudo usermod -aG docker $USER && newgrp docker"
fi

if [ ! -d /srv/leadfactory ]; then
    echo "⚠️  Create directory: sudo mkdir -p /srv/leadfactory && sudo chown $USER:$USER /srv/leadfactory"
fi

if [ ! -f /srv/leadfactory/.env ]; then
    echo "⚠️  Create .env file with required environment variables"
fi

if ! ssh -T git@github.com 2>&1 | grep -q "successfully authenticated"; then
    echo "⚠️  Add SSH key to GitHub: ssh-keygen -t ed25519 && cat ~/.ssh/id_ed25519.pub"
fi

echo ""
echo "Diagnostics complete. Please share this output for troubleshooting."