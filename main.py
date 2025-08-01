"""
Main FastAPI application entry point
"""

import time

import uvicorn
from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

# Initialize Sentry before anything else
import core.observability  # noqa: F401  (must be first import)

# Import all routers at top level
from account_management.api import router as account_router
from account_management.preference_api import router as preferences_router
from api.analytics import router as analytics_router
from api.health import router as health_router
from api.lineage import router as lineage_router
from batch_runner.api import router as batch_runner_router
from core.config import settings
from core.exceptions import LeadFactoryError
from core.logging import get_logger
from core.metrics import get_metrics_response, metrics
from d0_gateway.api import router as gateway_router
from d1_targeting.api import router as targeting_router
from d1_targeting.collaboration_api import router as collaboration_router  # P2-010
from d3_assessment.api import router as assessment_router
from d6_reports.api import router as reports_router
from d7_storefront.api import router as storefront_router
from d8_personalization.api import router as personalization_router
from d11_orchestration.api import router as orchestration_router
from lead_explorer.api import limiter
from lead_explorer.api import router as lead_explorer_router
from orchestrator.budget_alert_api import router as budget_alert_router

# Conditional imports for features
try:
    from api.template_studio import router as template_studio_router
except ImportError:
    template_studio_router = None

try:
    from api.scoring_playground import router as scoring_playground_router
except ImportError:
    scoring_playground_router = None

try:
    from api.audit_middleware import AuditLoggingMiddleware
    from api.governance import router as governance_router
except ImportError:
    AuditLoggingMiddleware = None
    governance_router = None

logger = get_logger(__name__)

# Create FastAPI app
app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    docs_url="/docs",
    redoc_url="/redoc",
)

# Add rate limiting error handler
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"] if settings.is_development else ["https://leadfactory.com"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Request tracking middleware
@app.middleware("http")
async def track_requests(request: Request, call_next):
    """Track all HTTP requests for metrics"""
    start_time = time.time()

    # Skip metrics endpoint to avoid recursion
    if request.url.path == "/metrics":
        return await call_next(request)

    response = await call_next(request)

    # Track request metrics
    duration = time.time() - start_time
    metrics.track_request(
        method=request.method,
        endpoint=request.url.path,
        status=response.status_code,
        duration=duration,
    )

    return response


# Exception handlers
@app.exception_handler(LeadFactoryError)
async def leadfactory_error_handler(request: Request, exc: LeadFactoryError):
    """Handle custom LeadFactory errors"""
    logger.error(f"LeadFactory error - error_code: {exc.error_code}, details: {exc.details}, path: {request.url.path}")
    return JSONResponse(status_code=exc.status_code, content=exc.to_dict())


@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    """Handle unexpected errors"""
    logger.exception(f"Unexpected error - path: {request.url.path}", exc_info=exc)
    return JSONResponse(
        status_code=500,
        content={"error": "INTERNAL_ERROR", "message": "An unexpected error occurred"},
    )


# Health check is now handled by the dedicated health router


# Custom metrics endpoint
@app.get("/metrics", include_in_schema=False)
async def prometheus_metrics():
    """Expose metrics for Prometheus scraping"""
    if not settings.prometheus_enabled:
        return JSONResponse(status_code=404, content={"error": "Metrics not enabled"})

    metrics_data, content_type = get_metrics_response()
    return Response(content=metrics_data, media_type=content_type)


# Startup event
@app.on_event("startup")
async def startup_event():
    """Initialize application on startup"""
    logger.info(
        f"Starting LeadFactory version={settings.app_version} environment={settings.environment} use_stubs={settings.use_stubs}"
    )


# Shutdown event
@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on shutdown"""
    logger.info("Shutting down LeadFactory")


# All routers now imported at top of file

# Add limiter to app state
app.state.limiter = limiter

# Register health router (no prefix needed as it defines its own paths)
app.include_router(health_router, tags=["health"])

# Register account management router (P2-000)
app.include_router(account_router, tags=["accounts"])

# Register user preferences router (P2-020)
app.include_router(preferences_router, tags=["user-preferences"])

# Register domain routers
app.include_router(gateway_router, tags=["gateway"])
app.include_router(targeting_router, prefix="/api/v1/targeting", tags=["targeting"])
# P2-010: Collaborative Buckets
app.include_router(collaboration_router, tags=["collaborative-buckets"])
# Note: d3_assessment already includes prefix in router definition
app.include_router(assessment_router)
# Register d6_reports router
app.include_router(reports_router, prefix="/api/v1/reports", tags=["reports"])
# Note: d7_storefront already includes prefix in router definition
app.include_router(storefront_router)
# Register d8_personalization router
app.include_router(personalization_router, prefix="/api/v1/personalization", tags=["personalization"])
# Note: d10_analytics already includes prefix in router definition
app.include_router(analytics_router)
# Note: d11_orchestration already includes prefix in router definition
app.include_router(orchestration_router)
# Note: lineage router already includes prefix in router definition
app.include_router(lineage_router)
# Lead Explorer router
app.include_router(lead_explorer_router, prefix="/api/v1", tags=["lead_explorer"])
# Batch Runner router
app.include_router(batch_runner_router, prefix="/api", tags=["batch_runner"])
# P2-040 Unified Budget Monitoring System (PM-1 + PM-2 Integration)
app.include_router(budget_alert_router, tags=["budget_monitoring"])

# Template Studio (P0-024)
if settings.enable_template_studio and template_studio_router is not None:
    app.include_router(template_studio_router)
    # Mount static files for Template Studio UI
    app.mount("/static/template_studio", StaticFiles(directory="static/template_studio"), name="template_studio")

# Scoring Playground (P0-025)
if settings.enable_scoring_playground and scoring_playground_router is not None:
    app.include_router(scoring_playground_router)
    # Mount static files for Scoring Playground UI
    app.mount(
        "/static/scoring-playground", StaticFiles(directory="static/scoring-playground"), name="scoring_playground"
    )

# Governance (P0-026)
if settings.enable_governance and governance_router is not None and AuditLoggingMiddleware is not None:
    # Add audit logging middleware
    app.add_middleware(AuditLoggingMiddleware)

    # Add governance router
    app.include_router(governance_router)

    # Mount static files for Governance UI
    app.mount("/static/governance", StaticFiles(directory="static/governance"), name="governance")

# Design System (P0-028)
# Mount design system CSS file
app.mount("/static/design_system", StaticFiles(directory="static/design_system"), name="design_system")

# Global Navigation Shell (P0-027)
# Mount static files for all UI components
app.mount("/static/global_navigation", StaticFiles(directory="static/global_navigation"), name="global_navigation")
app.mount("/static/lead_explorer", StaticFiles(directory="static/lead_explorer"), name="lead_explorer")
app.mount("/static/batch_runner", StaticFiles(directory="static/batch_runner"), name="batch_runner")
app.mount("/static/lineage", StaticFiles(directory="static/lineage"), name="lineage")


# Root navigation routes (P0-027)
@app.get("/")
async def root():
    """Redirect root to global navigation shell"""
    return RedirectResponse(url="/static/global_navigation/index.html")


@app.get("/lead-explorer")
async def lead_explorer():
    """Redirect to global navigation shell with lead explorer"""
    return RedirectResponse(url="/static/global_navigation/index.html")


@app.get("/batch-runner")
async def batch_runner():
    """Redirect to global navigation shell with batch runner"""
    return RedirectResponse(url="/static/global_navigation/index.html")


@app.get("/template-studio")
async def template_studio():
    """Redirect to global navigation shell with template studio"""
    return RedirectResponse(url="/static/global_navigation/index.html")


@app.get("/scoring-playground")
async def scoring_playground():
    """Redirect to global navigation shell with scoring playground"""
    return RedirectResponse(url="/static/global_navigation/index.html")


@app.get("/lineage")
async def lineage():
    """Redirect to global navigation shell with lineage"""
    return RedirectResponse(url="/static/global_navigation/index.html")


@app.get("/governance")
async def governance():
    """Redirect to global navigation shell with governance"""
    return RedirectResponse(url="/static/global_navigation/index.html")


if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.is_development,
        log_level=settings.log_level.lower(),
    )
