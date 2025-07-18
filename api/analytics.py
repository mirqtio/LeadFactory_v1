"""
Analytics API Bridge for P2-010 Unit Economics Views

This module provides a bridge/facade to the analytics API endpoints
required by P2-010. The actual implementation is in d10_analytics/api.py
following the domain-specific pattern, while this module satisfies the
PRP requirement for api/analytics.py.

Integration Points:
- Re-exports the analytics router from d10_analytics
- Maintains compatibility with existing integration tests
- Preserves all existing endpoint functionality

Endpoints Available:
- GET /api/v1/analytics/unit_econ - Unit economics metrics
- GET /api/v1/analytics/unit_econ/pdf - PDF reports
- POST /api/v1/analytics/metrics - Analytics metrics
- POST /api/v1/analytics/funnel - Funnel analysis
- POST /api/v1/analytics/cohort - Cohort analysis
- POST /api/v1/analytics/export - Data export
- GET /api/v1/analytics/health - Health check
"""

# Import the complete analytics router from domain-specific implementation
from d10_analytics.api import router

# Re-export the router to satisfy P2-010 requirements
__all__ = ["router"]

# The router includes:
# - All unit economics endpoints for P2-010
# - Proper authentication and authorization
# - Caching (24-hour for unit economics)
# - CSV/JSON/PDF export capabilities
# - Error handling and validation
# - Integration with materialized views

# This bridge ensures that:
# 1. P2-010 requirement for "api/analytics.py" is satisfied
# 2. Domain-specific implementation in d10_analytics/ is preserved
# 3. All existing tests continue to work
# 4. Integration points in main.py remain unchanged
