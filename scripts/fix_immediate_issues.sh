#!/bin/bash
# Fix immediate issues for LeadFactory
# This script resolves critical infrastructure problems

set -e  # Exit on error

echo "🔧 LeadFactory Immediate Issue Resolution"
echo "========================================"
echo ""

# Step 1: Check if .env exists
if [ ! -f .env ]; then
    echo "❌ .env file not found. Please create it first."
    exit 1
fi

# Step 2: Add missing environment variables
echo "📝 Checking and adding missing environment variables..."

# Add POSTGRES_PASSWORD if missing
if ! grep -q "POSTGRES_PASSWORD=" .env; then
    echo "POSTGRES_PASSWORD=leadfactory_prod_2024" >> .env
    echo "✅ Added POSTGRES_PASSWORD to .env"
fi

# Add DATADOG_APP_KEY if missing (already provided by user)
if ! grep -q "DATADOG_APP_KEY=" .env; then
    echo "DATADOG_APP_KEY=312d99d050dc20f5b542dc8a526be4f05392c377" >> .env
    echo "✅ Added DATADOG_APP_KEY to .env"
fi

# Step 3: Create .env.production for production deployments
echo ""
echo "📝 Creating .env.production..."
cp .env .env.production

# Update DATABASE_URL to use password
sed -i.bak 's|postgresql://leadfactory:leadfactory_dev@|postgresql://leadfactory:leadfactory_prod_2024@|g' .env.production
sed -i.bak 's|postgresql://leadfactory@|postgresql://leadfactory:leadfactory_prod_2024@|g' .env.production

echo "✅ Created .env.production with proper database credentials"

# Step 4: Stop existing containers
echo ""
echo "🛑 Stopping existing containers..."
docker compose -f docker-compose.production.yml down

# Step 5: Start PostgreSQL with correct password
echo ""
echo "🚀 Starting PostgreSQL with correct configuration..."
POSTGRES_PASSWORD=leadfactory_prod_2024 docker compose -f docker-compose.production.yml up -d postgres

# Wait for PostgreSQL to be ready
echo "⏳ Waiting for PostgreSQL to be ready..."
sleep 10

# Test connection
echo "🔍 Testing database connection..."
if docker exec leadfactory-postgres psql -U leadfactory -d leadfactory -c "SELECT 1;" > /dev/null 2>&1; then
    echo "✅ Database connection successful"
else
    echo "❌ Database connection failed"
    exit 1
fi

# Step 6: Start other services with proper environment
echo ""
echo "🚀 Starting all services with correct configuration..."
docker compose -f docker-compose.production.yml --env-file .env.production up -d

# Wait for services to be healthy
echo "⏳ Waiting for services to be healthy..."
sleep 20

# Step 7: Run database setup
echo ""
echo "🗄️ Setting up database schema..."
docker exec leadfactory-api python3 -c "
from sqlalchemy import create_engine, text
from database.models import Base

# Create engine with correct credentials
engine = create_engine('postgresql://leadfactory:leadfactory_prod_2024@leadfactory-postgres:5432/leadfactory')

# Create all tables
Base.metadata.create_all(engine)

# Verify tables created
with engine.connect() as conn:
    result = conn.execute(text(\"SELECT tablename FROM pg_tables WHERE schemaname='public'\"))
    tables = [row[0] for row in result]
    print(f'✅ Created {len(tables)} tables: {tables[:5]}...')
"

# Step 8: Run smoke test to verify
echo ""
echo "🧪 Running smoke test to verify fixes..."
export DATADOG_API_KEY=$(grep DATADOG_API_KEY .env | cut -d'=' -f2)
export DATADOG_APP_KEY=$(grep DATADOG_APP_KEY .env | cut -d'=' -f2)
python3 tests/smoke_prod/simple_runner.py

# Step 9: Check container logs for errors
echo ""
echo "📋 Checking container logs for errors..."
echo "API logs:"
docker logs leadfactory-api --tail 20 2>&1 | grep -E "(ERROR|WARNING|Failed)" || echo "No errors found"

echo ""
echo "✅ Immediate issues resolved!"
echo ""
echo "Next steps:"
echo "1. Run comprehensive smoke test: python3 tests/smoke_prod/realistic_smoke.py"
echo "2. Check Datadog metrics: https://app.datadoghq.com/"
echo "3. Implement missing API endpoints as per ISSUE_RESOLUTION_PLAN.md"