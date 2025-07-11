#!/bin/bash
# Rollback script for LeadFactory deployments
# Usage: ./scripts/rollback.sh [TASK_ID]

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo "=== LeadFactory Rollback Script ==="

# Load environment
if [ -f .env ]; then
    source .env
fi

# Get task ID from argument or prompt
TASK_ID=${1:-}
if [ -z "$TASK_ID" ]; then
    echo -e "${YELLOW}Enter the task ID to rollback (e.g., P0-001):${NC}"
    read TASK_ID
fi

echo -e "\n${YELLOW}Rolling back task: $TASK_ID${NC}"

# Task-specific rollback procedures
case "$TASK_ID" in
    "P0-000")
        echo "Rolling back Makefile setup..."
        git checkout HEAD -- Makefile
        git checkout HEAD -- setup.py
        ;;
    
    "P0-001")
        echo "Rolling back enrichment.py fix..."
        git checkout HEAD -- src/enrichment.py
        git checkout HEAD -- tests/test_enrichment.py
        ;;
    
    "P0-002")
        echo "Rolling back test configuration..."
        git checkout HEAD -- conftest.py
        git checkout HEAD -- pytest.ini
        git checkout HEAD -- tests/
        ;;
    
    "P0-003")
        echo "Rolling back CI configuration..."
        git checkout HEAD -- .github/workflows/deploy.yml
        git checkout HEAD -- Dockerfile.test
        ;;
    
    "P0-004")
        echo "Rolling back Docker workflow..."
        git checkout HEAD -- .github/workflows/docker.yml
        git checkout HEAD -- docker-compose.ci.yml
        ;;
    
    "P0-005")
        echo "Rolling back factory method..."
        git checkout HEAD -- src/factory.py
        git checkout HEAD -- tests/test_factory.py
        ;;
    
    "P0-006")
        echo "Rolling back stub server..."
        # Stop stub server if running
        docker stop stub-server 2>/dev/null || true
        git checkout HEAD -- stubs/
        git checkout HEAD -- Dockerfile.stub
        ;;
    
    "P0-007")
        echo "Rolling back database migrations..."
        # Rollback last migration
        alembic downgrade -1
        git checkout HEAD -- migrations/
        ;;
    
    "P0-008")
        echo "Rolling back assessment.py..."
        git checkout HEAD -- src/assessment.py
        git checkout HEAD -- tests/test_assessment.py
        ;;
    
    "P0-009")
        echo "Rolling back feature flags..."
        git checkout HEAD -- src/feature_flags.py
        git checkout HEAD -- .env
        ;;
    
    "P0-010")
        echo "Rolling back cost tracking..."
        git checkout HEAD -- src/cost_tracking.py
        git checkout HEAD -- tests/test_cost_tracking.py
        ;;
    
    "P0-011")
        echo "Rolling back VPS deployment..."
        # Restore previous deployment configuration
        git checkout HEAD -- deploy/
        git checkout HEAD -- .github/workflows/deploy.yml
        echo -e "${YELLOW}Note: Manual VPS cleanup may be required${NC}"
        ;;
    
    "P0-012")
        echo "Rolling back Postgres container..."
        # Stop and remove Postgres container
        docker stop leadfactory-postgres 2>/dev/null || true
        docker rm leadfactory-postgres 2>/dev/null || true
        git checkout HEAD -- docker-compose.production.yml
        ;;
    
    "P1-013"|"P1-014"|"P1-015"|"P1-016"|"P1-017"|"P1-018"|"P1-019"|"P1-020"|"P1-021"|"P1-022"|"P1-023"|"P1-024")
        echo "Rolling back Wave B task $TASK_ID..."
        # For Wave B tasks, revert the entire commit
        COMMIT=$(git log --oneline | grep "$TASK_ID" | head -1 | awk '{print $1}')
        if [ -n "$COMMIT" ]; then
            git revert --no-edit $COMMIT
        else
            echo -e "${RED}Could not find commit for $TASK_ID${NC}"
            exit 1
        fi
        ;;
    
    *)
        echo -e "${RED}Unknown task ID: $TASK_ID${NC}"
        echo "Valid task IDs: P0-000 through P0-012, P1-013 through P1-024"
        exit 1
        ;;
esac

# Common rollback steps
echo -e "\n${YELLOW}Performing common rollback steps...${NC}"

# Clear any cached data
echo "→ Clearing cache..."
find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
rm -rf .pytest_cache 2>/dev/null || true

# Restart services if in production
if [ "$ENVIRONMENT" = "production" ]; then
    echo "→ Restarting services..."
    docker-compose restart app 2>/dev/null || true
fi

# Update progress tracking
if [ -f .claude/prp_progress.json ]; then
    echo "→ Updating progress tracking..."
    # Mark task as failed in progress file
    python -c "
import json
with open('.claude/prp_progress.json', 'r') as f:
    progress = json.load(f)
progress['$TASK_ID'] = 'rolled_back'
with open('.claude/prp_progress.json', 'w') as f:
    json.dump(progress, f, indent=2)
"
fi

echo -e "\n${GREEN}✓ Rollback complete for task $TASK_ID${NC}"
echo -e "${YELLOW}Remember to:${NC}"
echo "1. Review the changes with 'git status'"
echo "2. Test the system is working correctly"
echo "3. Update any external dependencies if needed"
echo "4. Notify the team about the rollback"