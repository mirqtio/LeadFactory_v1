#!/bin/bash
# Deploy secrets to VPS
# This script should be run locally, NOT committed with actual secrets

set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Configuration
SSH_HOST="${SSH_HOST:-96.30.197.121}"
SSH_PORT="${SSH_PORT:-22}"
SSH_USER="${SSH_USER:-deploy}"
SSH_KEY="${SSH_KEY:-$HOME/.ssh/leadfactory_deploy}"

echo -e "${GREEN}🔐 LeadFactory VPS Secret Deployment${NC}"
echo "================================================"

# Check if .env.production exists
if [ ! -f ".env.production" ]; then
    echo -e "${RED}❌ Error: .env.production file not found${NC}"
    echo "Please create .env.production with your production secrets"
    echo "You can use .env.example as a template"
    exit 1
fi

# Validate SSH key exists
if [ ! -f "$SSH_KEY" ]; then
    echo -e "${RED}❌ Error: SSH key not found at $SSH_KEY${NC}"
    exit 1
fi

echo -e "${YELLOW}📋 Checking current deployment status...${NC}"

# Test SSH connection
if ! ssh -i "$SSH_KEY" -p "$SSH_PORT" -o ConnectTimeout=5 "$SSH_USER@$SSH_HOST" "echo 'SSH connection successful'" >/dev/null 2>&1; then
    echo -e "${RED}❌ Error: Cannot connect to VPS${NC}"
    echo "Please check your SSH configuration"
    exit 1
fi

echo -e "${GREEN}✅ SSH connection successful${NC}"

# Create backup of existing .env if it exists
echo -e "${YELLOW}📦 Creating backup of existing secrets...${NC}"
ssh -i "$SSH_KEY" -p "$SSH_PORT" "$SSH_USER@$SSH_HOST" << 'EOF'
    if [ -f /srv/leadfactory/.env ]; then
        backup_name="/srv/leadfactory/.env.backup.$(date +%Y%m%d_%H%M%S)"
        cp /srv/leadfactory/.env "$backup_name"
        echo "Backup created: $backup_name"
    else
        echo "No existing .env file found"
    fi
EOF

# Upload new .env file
echo -e "${YELLOW}📤 Uploading production secrets...${NC}"
scp -i "$SSH_KEY" -P "$SSH_PORT" .env.production "$SSH_USER@$SSH_HOST:/tmp/.env.new"

# Move to correct location and set permissions
echo -e "${YELLOW}🔧 Setting up environment file...${NC}"
ssh -i "$SSH_KEY" -p "$SSH_PORT" "$SSH_USER@$SSH_HOST" << 'EOF'
    set -e
    
    # Ensure directory exists
    if [ ! -d /srv/leadfactory ]; then
        sudo mkdir -p /srv/leadfactory
        sudo chown $USER:$USER /srv/leadfactory
    fi
    
    # Move and secure the file
    mv /tmp/.env.new /srv/leadfactory/.env
    chmod 600 /srv/leadfactory/.env
    
    echo "Environment file deployed successfully"
EOF

# Restart services
echo -e "${YELLOW}🔄 Restarting services with new configuration...${NC}"
ssh -i "$SSH_KEY" -p "$SSH_PORT" "$SSH_USER@$SSH_HOST" << 'EOF'
    cd /srv/leadfactory
    
    # Stop existing containers
    docker compose -f docker-compose.prod.yml down || true
    
    # Start with new environment
    docker compose -f docker-compose.prod.yml up -d
    
    # Wait for services to start
    echo "Waiting for services to start..."
    sleep 10
    
    # Check status
    docker compose -f docker-compose.prod.yml ps
    
    # Run migrations
    echo "Running database migrations..."
    docker compose -f docker-compose.prod.yml run --rm -T web alembic upgrade head
    
    # Health check
    echo "Performing health check..."
    if curl -f http://localhost:8000/health; then
        echo -e "\n✅ Application is healthy"
    else
        echo -e "\n❌ Health check failed"
        docker compose -f docker-compose.prod.yml logs --tail=50
    fi
EOF

echo -e "${GREEN}✅ Secret deployment complete!${NC}"
echo "================================================"
echo "Next steps:"
echo "1. Verify the application is running: http://$SSH_HOST:8000"
echo "2. Check logs if needed: ssh -i $SSH_KEY -p $SSH_PORT $SSH_USER@$SSH_HOST 'cd /srv/leadfactory && docker compose -f docker-compose.prod.yml logs'"