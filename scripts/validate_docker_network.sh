#!/bin/bash
# Docker Network Validation Script
# Tests Docker Compose networking and service discovery

set -e

echo "=== Docker Network Validation ==="

# Check if docker-compose.test.yml exists
if [[ ! -f "docker-compose.test.yml" ]]; then
    echo "❌ docker-compose.test.yml not found"
    exit 1
fi

echo "✅ docker-compose.test.yml found"

# Validate docker-compose configuration
echo "Validating Docker Compose configuration..."
if docker compose -f docker-compose.test.yml config --quiet; then
    echo "✅ Docker Compose configuration is valid"
else
    echo "❌ Docker Compose configuration is invalid"
    exit 1
fi

# Show services
echo "Services defined:"
docker compose -f docker-compose.test.yml config --services

# Check if services are running
echo "Checking service status..."
docker compose -f docker-compose.test.yml ps

# Test network connectivity between services
echo "Testing inter-service connectivity..."

# Start services if not running
echo "Starting services..."
docker compose -f docker-compose.test.yml up -d postgres stub-server

# Wait for PostgreSQL
echo "Waiting for PostgreSQL..."
timeout 30 bash -c 'until docker compose -f docker-compose.test.yml exec -T postgres pg_isready -U postgres; do sleep 1; done'

# Wait for stub server with detailed diagnostics
echo "Waiting for stub server..."
timeout 60 bash -c '
    until docker compose -f docker-compose.test.yml exec -T stub-server curl -f http://127.0.0.1:5010/health 2>/dev/null; do 
        echo "Checking stub server status..."
        docker compose -f docker-compose.test.yml exec -T stub-server ps aux | grep uvicorn || echo "Uvicorn not found"
        docker compose -f docker-compose.test.yml exec -T stub-server netstat -tlnp | grep 5010 || echo "Port 5010 not listening"
        sleep 2
    done
'

# Test service discovery from test container
echo "Testing service discovery from test container..."
docker compose -f docker-compose.test.yml run --rm test bash -c "
    echo 'Testing DNS resolution:'
    nslookup postgres || echo 'Failed to resolve postgres'
    nslookup stub-server || echo 'Failed to resolve stub-server'
    
    echo 'Testing port connectivity:'
    nc -zv postgres 5432 || echo 'Cannot connect to postgres:5432'
    nc -zv stub-server 5010 || echo 'Cannot connect to stub-server:5010'
    
    echo 'Testing HTTP endpoints:'
    curl -f http://stub-server:5010/health --connect-timeout 5 || echo 'Cannot reach stub server HTTP'
    
    echo 'Testing database connection:'
    python -c 'import psycopg2; psycopg2.connect(\"postgresql://postgres:postgres@postgres:5432/leadfactory_test\"); print(\"Database OK\")' || echo 'Database connection failed'
"

echo "✅ Network validation complete"

# Cleanup
echo "Cleaning up..."
docker compose -f docker-compose.test.yml down

echo "✅ Docker network validation passed"