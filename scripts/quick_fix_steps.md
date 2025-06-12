# Quick Fix Steps - LeadFactory

## 🚀 Immediate Actions (5 minutes)

### 1. Run the automated fix script:
```bash
./scripts/fix_immediate_issues.sh
```

This will:
- ✅ Add missing POSTGRES_PASSWORD to .env
- ✅ Add DATADOG_APP_KEY to .env  
- ✅ Create .env.production with correct credentials
- ✅ Restart containers with proper configuration
- ✅ Create database tables
- ✅ Run basic smoke test

### 2. Validate environment:
```bash
python3 scripts/validate_environment.py
```

### 3. Run comprehensive smoke test:
```bash
export DATADOG_API_KEY=$(grep DATADOG_API_KEY .env | cut -d'=' -f2)
export DATADOG_APP_KEY=$(grep DATADOG_APP_KEY .env | cut -d'=' -f2)
python3 tests/smoke_prod/realistic_smoke.py
```

## 🔧 Manual Fixes (if automated script fails)

### Fix Database Password:
```bash
# 1. Add to .env
echo "POSTGRES_PASSWORD=leadfactory_prod_2024" >> .env

# 2. Restart postgres
docker compose -f docker-compose.production.yml stop postgres
docker compose -f docker-compose.production.yml rm -f postgres
POSTGRES_PASSWORD=leadfactory_prod_2024 docker compose -f docker-compose.production.yml up -d postgres

# 3. Update DATABASE_URL in running container
docker exec leadfactory-api bash -c 'export DATABASE_URL="postgresql://leadfactory:leadfactory_prod_2024@leadfactory-postgres:5432/leadfactory"'
```

### Create Database Tables:
```bash
docker exec leadfactory-api python3 -c "
from sqlalchemy import create_engine
from database.models import Base
engine = create_engine('postgresql://leadfactory:leadfactory_prod_2024@leadfactory-postgres:5432/leadfactory')
Base.metadata.create_all(engine)
print('Tables created!')
"
```

### Verify External APIs:
```bash
# Check if real API keys are loaded
docker exec leadfactory-api env | grep -E "(YELP|OPENAI|STRIPE)_API_KEY" | head -5
```

## 📊 Verify Success

### 1. Check Database:
```bash
docker exec leadfactory-postgres psql -U leadfactory -d leadfactory -c "\dt" | head -10
```

### 2. Check Datadog:
```bash
# Should see "API Connection: ✓"
python3 tests/smoke_prod/realistic_smoke.py | grep Datadog -A3
```

### 3. Check API Health:
```bash
curl -s http://localhost:8000/health | jq .
curl -s http://localhost:8000/metrics | grep leadfactory | head -5
```

## 🎯 Expected Results

After running fixes, you should see:
- ✅ Database tables created (businesses, assessments, etc.)
- ✅ All health endpoints return 200
- ✅ Prometheus metrics show activity
- ✅ Datadog API connection works
- ✅ Smoke tests pass with >75% success rate

## 🚨 If Issues Persist

1. Check logs:
```bash
docker logs leadfactory-api --tail 50
docker logs leadfactory-postgres --tail 50
```

2. Restart everything:
```bash
docker compose -f docker-compose.production.yml down
docker compose -f docker-compose.production.yml up -d
```

3. Run validation:
```bash
python3 scripts/validate_environment.py
```

## 📝 Next Steps

Once immediate issues are fixed:
1. Implement missing API endpoints (see ISSUE_RESOLUTION_PLAN.md)
2. Run full test suite
3. Configure Datadog dashboards
4. Set up monitoring alerts
5. Deploy to production