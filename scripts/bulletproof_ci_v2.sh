#!/bin/bash
# Bulletproof CI v2 - Catches issues BEFORE GitHub CI
set -euo pipefail

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo "🚀 Bulletproof CI v2 - Complete Pre-Push Validation"
echo "=================================================="

# Track failures
FAILURES=0
FAILURE_LOG=""

log_failure() {
    FAILURES=$((FAILURES + 1))
    FAILURE_LOG="${FAILURE_LOG}\n❌ $1"
    echo -e "${RED}❌ FAILED: $1${NC}"
}

log_success() {
    echo -e "${GREEN}✅ PASSED: $1${NC}"
}

log_warning() {
    echo -e "${YELLOW}⚠️  WARNING: $1${NC}"
}

# 1. Environment Detection
echo -e "\n📋 Phase 1: Environment Detection"
echo "================================="
if [ -f "/.dockerenv" ] || [ -n "${DOCKER_ENV:-}" ]; then
    echo "Environment: Docker Container"
    STUB_URL="http://stub-server:5010"
else
    echo "Environment: Local Development"
    STUB_URL="http://localhost:5010"
fi
echo "Expected stub URL: $STUB_URL"

# 2. Python Import Validation
echo -e "\n📋 Phase 2: Python Import Validation"
echo "===================================="
echo "Testing critical imports..."
if python -c "
import sys
failed = []
modules = [
    'core.config',
    'core.utils',
    'database.session',
    'd9_delivery.webhook_handler',
    'lead_explorer.repository',
    'api.lineage.routes',
    'd10_analytics.models',
    'd0_gateway.metrics',
    'd1_targeting.geo_validator',
    'd8_personalization.personalizer',
    'd11_orchestration.pipeline'
]
for module in modules:
    try:
        __import__(module)
        print(f'✓ {module}')
    except Exception as e:
        print(f'✗ {module}: {str(e)[:50]}...')
        failed.append(module)
if failed:
    sys.exit(1)
" 2>&1; then
    log_success "All critical imports successful"
else
    log_failure "Import validation - some modules failed to import"
fi

# 2.5. Missing Class/Method Validation
echo -e "\n📋 Phase 2.5: Missing Class/Method Validation"
echo "============================================="
echo "Testing critical classes and methods..."
if python -c "
import sys
failed = []

# Test critical classes and methods
test_cases = [
    ('d8_personalization.personalizer', 'Personalizer'),
    ('d11_orchestration.pipeline', 'Pipeline'),
    ('d11_orchestration.pipeline', 'PipelineStage'),
    ('d0_gateway.metrics', 'GatewayMetrics'),
    ('d1_targeting.geo_validator', 'GeoValidator'),
    ('core.utils', 'slugify'),
    ('core.utils', 'truncate'),
    ('core.utils', 'validate_email'),
    ('core.utils', 'retry_with_backoff'),
]

for module_name, class_or_func in test_cases:
    try:
        module = __import__(module_name, fromlist=[class_or_func])
        obj = getattr(module, class_or_func)
        print(f'✓ {module_name}.{class_or_func}')
    except Exception as e:
        print(f'✗ {module_name}.{class_or_func}: {str(e)[:50]}...')
        failed.append(f'{module_name}.{class_or_func}')

# Test specific methods on classes
method_tests = [
    ('d0_gateway.metrics', 'GatewayMetrics', 'record_request'),
    ('d1_targeting.geo_validator', 'GeoValidator', 'validate_location'),
]

for module_name, class_name, method_name in method_tests:
    try:
        module = __import__(module_name, fromlist=[class_name])
        cls = getattr(module, class_name)
        instance = cls()
        method = getattr(instance, method_name)
        print(f'✓ {module_name}.{class_name}.{method_name}')
    except Exception as e:
        print(f'✗ {module_name}.{class_name}.{method_name}: {str(e)[:50]}...')
        failed.append(f'{module_name}.{class_name}.{method_name}')

if failed:
    sys.exit(1)
" 2>&1; then
    log_success "All critical classes and methods found"
else
    log_failure "Missing class/method validation - some critical components missing"
fi

# 3. Database Model Validation
echo -e "\n📋 Phase 3: Database Model Validation"
echo "====================================="
if python -c "
from database.base import Base
from sqlalchemy import create_engine, inspect
import sys

# Import all models to ensure they're registered
try:
    from d10_analytics import models as analytics_models
    from d9_delivery import models as delivery_models
    from lead_explorer import models as explorer_models
    from d6_reports.lineage import models as lineage_models
    print('✓ All models imported successfully')
except Exception as e:
    print(f'✗ Model import failed: {e}')
    sys.exit(1)

# Create test database
engine = create_engine('sqlite:///:memory:')
try:
    Base.metadata.create_all(bind=engine)
    print('✓ All database tables created successfully')
    
    # Check for critical tables that were missing in migrations
    inspector = inspect(engine)
    tables = inspector.get_table_names()
    
    required_tables = [
        'funnel_events',
        'time_series_data', 
        'metrics_aggregations',
        'businesses',
        'leads',
        'report_lineage'
    ]
    
    missing_tables = [table for table in required_tables if table not in tables]
    if missing_tables:
        print(f'✗ Missing required tables: {missing_tables}')
        sys.exit(1)
    else:
        print('✓ All required tables are present')
        
except Exception as e:
    print(f'✗ Table creation failed: {e}')
    sys.exit(1)
" 2>&1; then
    log_success "Database model validation"
else
    log_failure "Database model validation - models or tables failed"
fi

# 4. Linting with Syntax Errors
echo -e "\n📋 Phase 4: Linting and Syntax Validation"
echo "========================================"
if flake8 . --count --select=E9,F63,F7,F82 --show-source --statistics 2>&1; then
    log_success "No critical syntax errors"
else
    log_failure "Critical syntax errors found"
fi

# Full linting
if flake8 . --max-line-length=120 --extend-ignore=E203,W503 2>&1 | grep -E "^[^:]+:[0-9]+:[0-9]+: [EFW]" | head -20; then
    log_warning "Linting issues found (showing first 20)"
else
    log_success "Full linting check"
fi

# 5. Test Infrastructure Check
echo -e "\n📋 Phase 5: Test Infrastructure Validation"
echo "========================================="
# Check if pytest can collect tests without errors
if pytest --collect-only -q 2>&1 | grep -E "ERROR|ERRORS|FAILED|ImportError|SyntaxError" > /dev/null; then
    log_failure "Test collection errors - some tests have import/syntax issues"
    pytest --collect-only 2>&1 | grep -E "ERROR|ERRORS|FAILED|ImportError|SyntaxError" | head -10
else
    TOTAL_TESTS=$(pytest --collect-only -q 2>&1 | grep -E "\.py::" | wc -l)
    log_success "Test collection - $TOTAL_TESTS tests found"
fi

# 6. Critical Test Suites
echo -e "\n📋 Phase 6: Critical Test Suite Execution"
echo "========================================"

# Run specific test files that were problematic
CRITICAL_TESTS=(
    "tests/unit/d9_delivery/test_webhook_handler.py"
    "tests/unit/lead_explorer/test_repository.py"
    "tests/unit/lineage/test_api.py"
    "tests/unit/lineage/test_api_v2.py"
    "tests/unit/core/test_config.py"
)

for test_file in "${CRITICAL_TESTS[@]}"; do
    if [ -f "$test_file" ]; then
        echo -e "\nTesting: $test_file"
        if pytest "$test_file" -v --tb=short -x 2>&1 | tail -20; then
            log_success "$(basename $test_file)"
        else
            log_failure "$(basename $test_file)"
        fi
    fi
done

# 7. Docker Environment Test
echo -e "\n📋 Phase 7: Docker Environment Simulation"
echo "========================================"
# Test with Docker-like environment variables
export DOCKER_ENV=true
export STUB_BASE_URL="http://stub-server:5010"
export USE_STUBS=true
export ENVIRONMENT=test

if python -c "
from core.config import get_settings
settings = get_settings()
expected = 'http://stub-server:5010'
if settings.stub_base_url != expected:
    print(f'✗ Expected {expected}, got {settings.stub_base_url}')
    exit(1)
print('✓ Docker environment configuration correct')
" 2>&1; then
    log_success "Docker environment simulation"
else
    log_failure "Docker environment simulation"
fi

unset DOCKER_ENV
unset STUB_BASE_URL

# 8. Database Session Test
echo -e "\n📋 Phase 8: Database Session Management"
echo "======================================"
if python -c "
from database.session import SessionLocal
from sqlalchemy.orm import Session

# Test session creation
try:
    db = SessionLocal()
    assert isinstance(db, Session)
    db.close()
    print('✓ Database session creation successful')
except Exception as e:
    print(f'✗ Session creation failed: {e}')
    exit(1)
" 2>&1; then
    log_success "Database session management"
else
    log_failure "Database session management"
fi

# 9. API Endpoint Validation
echo -e "\n📋 Phase 9: API Endpoint Validation"
echo "==================================="
if python -c "
from fastapi.testclient import TestClient
from main import app
import sys

client = TestClient(app)
endpoints = ['/health', '/api/lineage', '/api/v1/leads']
failed = []

for endpoint in endpoints:
    try:
        # Just check if endpoint base path is registered, not if it works
        routes = [route.path for route in app.routes]
        if any(route.startswith(endpoint) for route in routes):
            print(f'✓ {endpoint} routes registered')
        else:
            raise ValueError(f'{endpoint} not found')
    except:
        print(f'✗ {endpoint} routes not found')
        failed.append(endpoint)

if failed:
    sys.exit(1)
" 2>&1; then
    log_success "API endpoint validation"
else
    log_failure "API endpoint validation"
fi

# 9.5. Configuration Validation
echo -e "\n📋 Phase 9.5: Configuration Validation"
echo "======================================"
if python -c "
from core.config import get_settings
from pydantic import ValidationError
import sys

try:
    # Test basic settings creation
    settings = get_settings()
    print('✓ Settings created successfully')
    
    # Test SecretStr handling
    if hasattr(settings, 'google_api_key') and settings.google_api_key:
        secret_value = settings.google_api_key.get_secret_value()
        print('✓ SecretStr handling works')
    
    # Test stub configuration
    if settings.use_stubs:
        api_key = settings.get_api_key('google')
        if api_key.startswith('stub-'):
            print('✓ Stub API key configuration works')
        else:
            print('✗ Stub API key configuration failed')
            sys.exit(1)
    
    # Test environment validation
    if settings.environment == 'production' and settings.use_stubs:
        print('✗ Production environment should not allow stubs')
        sys.exit(1)
    else:
        print('✓ Environment validation works')
        
except ValidationError as e:
    print(f'✗ Configuration validation error: {e}')
    sys.exit(1)
except Exception as e:
    print(f'✗ Configuration error: {e}')
    sys.exit(1)
" 2>&1; then
    log_success "Configuration validation"
else
    log_failure "Configuration validation"
fi

# 10. Database Migration Validation
echo -e "\n📋 Phase 10: Database Migration Validation"
echo "========================================="
if python -c "
from sqlalchemy import create_engine, inspect, text
from alembic import command
from alembic.config import Config
import sys

try:
    # Check if funnel_events table has campaign_id column
    engine = create_engine('sqlite:///:memory:')
    
    # First create the database schema
    from database.base import Base
    Base.metadata.create_all(bind=engine)
    
    # Check table structure
    inspector = inspect(engine)
    if 'funnel_events' in inspector.get_table_names():
        columns = [col['name'] for col in inspector.get_columns('funnel_events')]
        if 'campaign_id' not in columns:
            print('✗ funnel_events table missing campaign_id column')
            sys.exit(1)
        else:
            print('✓ funnel_events table has campaign_id column')
    else:
        print('⚠️  funnel_events table not found - may be created by migrations')
    
    print('✓ Database migration structure validated')
except Exception as e:
    print(f'✗ Migration validation failed: {e}')
    sys.exit(1)
" 2>&1; then
    log_success "Database migration validation"
else
    log_failure "Database migration validation"
fi

# 11. Docker Build Test
echo -e "\n📋 Phase 11: Docker Build Validation"
echo "===================================="
if command -v docker &> /dev/null; then
    echo "Testing Docker build (this may take a minute)..."
    if docker build -f Dockerfile.test -t leadfactory-test-validation . > /tmp/docker-build.log 2>&1; then
        log_success "Docker test image build"
    else
        log_failure "Docker test image build"
        tail -20 /tmp/docker-build.log
    fi
else
    log_warning "Docker not available - skipping Docker build test"
fi

# Summary
echo -e "\n📊 BPCI v2 Summary"
echo "=================="
if [ $FAILURES -eq 0 ]; then
    echo -e "${GREEN}✅ ALL CHECKS PASSED! Safe to push to GitHub.${NC}"
    exit 0
else
    echo -e "${RED}❌ $FAILURES CHECKS FAILED:${NC}"
    echo -e "$FAILURE_LOG"
    echo -e "\n${YELLOW}Fix these issues before pushing to avoid CI failures.${NC}"
    exit 1
fi