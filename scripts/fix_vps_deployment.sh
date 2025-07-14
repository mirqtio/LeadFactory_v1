#!/bin/bash
# Fix VPS deployment issues

set -euo pipefail

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

# Configuration
SSH_HOST="${SSH_HOST:-96.30.197.121}"
SSH_PORT="${SSH_PORT:-22}"
SSH_USER="${SSH_USER:-deploy}"
SSH_KEY="${SSH_KEY:-$HOME/.ssh/leadfactory_deploy}"

echo -e "${GREEN}🔧 Fixing VPS Deployment${NC}"
echo "================================================"

# Clean up and restart with fresh database
echo -e "${YELLOW}🧹 Cleaning up existing deployment...${NC}"
ssh -i "$SSH_KEY" -p "$SSH_PORT" "$SSH_USER@$SSH_HOST" << 'EOF'
    cd /srv/leadfactory
    
    # Stop and remove all containers and volumes
    docker compose -f docker-compose.prod.yml down -v
    
    # Remove any existing postgres data
    docker volume rm leadfactory_postgres_data || true
    docker volume rm leadfactory_redis_data || true
    
    echo "Cleanup complete"
EOF

# Upload the env file again
echo -e "${YELLOW}📤 Re-uploading environment file...${NC}"
scp -i "$SSH_KEY" -P "$SSH_PORT" .env.production "$SSH_USER@$SSH_HOST:/tmp/.env.new"

ssh -i "$SSH_KEY" -p "$SSH_PORT" "$SSH_USER@$SSH_HOST" << 'EOF'
    # Move to correct location
    mv /tmp/.env.new /srv/leadfactory/.env
    chmod 600 /srv/leadfactory/.env
    
    # Show what we're using (without exposing secrets)
    echo "Environment file has $(wc -l < /srv/leadfactory/.env) lines"
EOF

# Start fresh deployment
echo -e "${YELLOW}🚀 Starting fresh deployment...${NC}"
ssh -i "$SSH_KEY" -p "$SSH_PORT" "$SSH_USER@$SSH_HOST" << 'EOF'
    cd /srv/leadfactory
    
    # Pull latest code
    git pull origin main
    
    # Start services
    docker compose -f docker-compose.prod.yml up -d
    
    # Wait for database to be ready
    echo "Waiting for database to initialize..."
    sleep 15
    
    # Check container status
    docker compose -f docker-compose.prod.yml ps
    
    # Initialize database
    echo "Initializing database schema..."
    docker compose -f docker-compose.prod.yml exec -T web alembic stamp base || true
    docker compose -f docker-compose.prod.yml exec -T web alembic upgrade head
    
    # Check logs
    echo -e "\n=== Web Container Logs ==="
    docker compose -f docker-compose.prod.yml logs web --tail=20
    
    # Health check
    echo -e "\n=== Health Check ==="
    sleep 5
    if curl -f http://localhost:8000/health; then
        echo -e "\n✅ Application is healthy!"
    else
        echo -e "\n❌ Health check failed"
        echo "Checking container status..."
        docker compose -f docker-compose.prod.yml ps
    fi
EOF

echo -e "\n${GREEN}✅ Deployment fix complete!${NC}"
echo "================================================"
echo "Check the application at: http://$SSH_HOST:8000"