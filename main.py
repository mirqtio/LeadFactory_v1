"""
Main FastAPI application entry point
"""
# Initialize Sentry before anything else
import core.observability  # noqa: F401  (must be first import)

import time

import uvicorn
from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from core.config import settings
from core.exceptions import LeadFactoryError
from core.logging import get_logger
from core.metrics import get_metrics_response, metrics

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
    logger.error(
        f"LeadFactory error - error_code: {exc.error_code}, details: {exc.details}, path: {request.url.path}"
    )
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


# Import and register routers
from d1_targeting.api import router as targeting_router
from d3_assessment.api import router as assessment_router
from d7_storefront.api import router as storefront_router
from d10_analytics.api import router as analytics_router
from d11_orchestration.api import router as orchestration_router
from api.lineage import router as lineage_router
from api.health import router as health_router
from lead_explorer.api import router as lead_explorer_router
from lead_explorer.api import limiter
from batch_runner.api import router as batch_runner_router

# Add limiter to app state
app.state.limiter = limiter

# Register health router (no prefix needed as it defines its own paths)
app.include_router(health_router, tags=["health"])

# Register domain routers
app.include_router(targeting_router, prefix="/api/v1/targeting", tags=["targeting"])
# Note: d3_assessment already includes prefix in router definition
app.include_router(assessment_router)
# Note: d7_storefront already includes prefix in router definition
app.include_router(storefront_router)
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

# Template Studio (P0-024)
if settings.enable_template_studio:
    from api.template_studio import router as template_studio_router
    app.include_router(template_studio_router)
    # Mount static files for Template Studio UI
    app.mount("/static/template_studio", StaticFiles(directory="static/template_studio"), name="template_studio")

# Scoring Playground (P0-025)
if settings.enable_scoring_playground:
    from api.scoring_playground import router as scoring_playground_router
    app.include_router(scoring_playground_router)
    # Mount static files for Scoring Playground UI
    app.mount("/static/scoring-playground", StaticFiles(directory="static/scoring-playground"), name="scoring_playground")

# Governance (P0-026)
if settings.enable_governance:
    from api.governance import router as governance_router
    from api.audit_middleware import AuditLoggingMiddleware
    
    # Add audit logging middleware
    app.add_middleware(AuditLoggingMiddleware)
    
    # Add governance router
    app.include_router(governance_router)
    
    # Mount static files for Governance UI
    app.mount("/static/governance", StaticFiles(directory="static/governance"), name="governance")


if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.is_development,
        log_level=settings.log_level.lower(),
    )
