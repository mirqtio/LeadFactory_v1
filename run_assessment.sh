#!/bin/bash
# Run full assessment for a business
# Usage: ./run_assessment.sh <business_id> [--type full_audit|pagespeed|tech_stack|ai_insights]

if [ -z "$1" ]; then
    echo "Usage: $0 <business_id> [--type assessment_type]"
    echo ""
    echo "Assessment types:"
    echo "  full_audit  - Complete assessment (default)"
    echo "  pagespeed   - PageSpeed Insights only"
    echo "  tech_stack  - Technology detection only"
    echo "  ai_insights - AI insights only"
    echo ""
    echo "Recent businesses:"
    docker exec anthrasite_leadfactory_v1-db-1 psql -U leadfactory -d leadfactory_dev -c "
    SELECT id, name, website FROM businesses ORDER BY created_at DESC LIMIT 5"
    exit 1
fi

# Run the assessment in Docker
docker exec anthrasite_leadfactory_v1-app-1 python scripts/run_full_assessment.py "$@"