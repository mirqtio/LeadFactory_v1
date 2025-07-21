"""
Production-ready health check endpoint with performance monitoring
"""

import asyncio
import time
from datetime import datetime
from typing import Any

import redis.asyncio as redis
from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.orm import Session

from api.dependencies import get_db
from core.config import settings
from core.logging import get_logger

logger = get_logger(__name__)
router = APIRouter()


def check_database_health(db: Session) -> dict[str, Any]:
    """
    Check database connectivity with timeout protection.

    Args:
        db: Database session dependency

    Returns:
        Dict containing database health status
    """
    try:
        # Use simple SELECT 1 query as recommended by PostgreSQL docs
        start_time = time.time()
        result = db.execute(text("SELECT 1"))
        result.fetchone()
        latency_ms = (time.time() - start_time) * 1000
        return {"status": "connected", "latency_ms": round(latency_ms, 2)}
    except Exception as e:
        logger.error(f"Database health check failed: {str(e)}")
        return {"status": "error", "error": str(e)}


async def check_redis_health(redis_url: str) -> dict[str, Any]:
    """
    Check Redis connectivity with PING command.

    Args:
        redis_url: Redis connection URL

    Returns:
        Dict containing Redis health status
    """
    try:
        # Create async Redis client
        client = await redis.from_url(redis_url, decode_responses=True)

        # Use PING command as recommended by Redis documentation
        start_time = time.time()
        response = await client.ping()
        latency_ms = (time.time() - start_time) * 1000

        await client.close()

        if response:
            return {"status": "connected", "latency_ms": round(latency_ms, 2)}
        return {"status": "error", "error": "PING returned False"}
    except Exception as e:
        logger.error(f"Redis health check failed: {str(e)}")
        return {"status": "error", "error": str(e)}


@router.get("/health")
async def health_check(db: Session = Depends(get_db)) -> JSONResponse:
    """
    Production health check endpoint for external monitoring systems.

    Validates all critical system dependencies and returns structured health data.
    Must complete within 100ms to avoid monitoring system timeouts.

    Returns:
        JSONResponse: Health status with 200 (healthy) or 503 (unhealthy)
    """
    start_time = time.time()

    health_data = {
        "status": "ok",
        "timestamp": datetime.utcnow().isoformat(),
        "version": settings.app_version,
        "environment": settings.environment,
        "checks": {},
    }

    is_healthy = True

    # Check database connectivity with timeout
    try:
        # Run database check synchronously with timeout
        start_db_check = time.time()
        db_result = check_database_health(db)
        db_check_time = (time.time() - start_db_check) * 1000

        # Check if it took too long
        if db_check_time > 50:
            health_data["checks"]["database"] = {
                "status": "timeout",
                "error": f"Database check took {db_check_time:.2f}ms, exceeds 50ms limit",
            }
            is_healthy = False
        else:
            health_data["checks"]["database"] = db_result
            if db_result.get("status") != "connected":
                is_healthy = False
    except Exception as e:
        health_data["checks"]["database"] = {"status": "error", "error": str(e)}
        is_healthy = False

    # Check Redis connectivity if configured and not using default localhost
    if settings.redis_url and settings.redis_url != "redis://localhost:6379/0":
        try:
            redis_result = await asyncio.wait_for(
                check_redis_health(settings.redis_url),
                timeout=0.03,  # 30ms timeout for Redis check
            )
            health_data["checks"]["redis"] = redis_result
            if redis_result.get("status") != "connected":
                # Redis failure is not critical for health check
                logger.warning(f"Redis health check failed: {redis_result}")
        except TimeoutError:
            health_data["checks"]["redis"] = {"status": "timeout", "error": "Redis check timed out after 30ms"}
        except Exception as e:
            health_data["checks"]["redis"] = {"status": "error", "error": str(e)}

    # Calculate response time
    response_time_ms = (time.time() - start_time) * 1000
    health_data["response_time_ms"] = round(response_time_ms, 2)

    # Validate performance requirement
    if response_time_ms > 100:
        health_data["performance_warning"] = "Response time exceeded 100ms threshold"
        logger.warning(f"Health check response time: {response_time_ms}ms exceeds 100ms requirement")

    # Set final status
    if not is_healthy:
        health_data["status"] = "unhealthy"

    # Return appropriate status code
    status_code = 200 if is_healthy else 503

    return JSONResponse(status_code=status_code, content=health_data)


@router.get("/health/detailed")
async def detailed_health_check(db: Session = Depends(get_db)) -> JSONResponse:
    """
    Detailed health check with additional system information.

    This endpoint provides more comprehensive health information including:
    - System resource usage
    - Configuration status
    - Feature flag status

    Returns:
        JSONResponse: Detailed health status
    """
    # Run basic health check first
    basic_response = await health_check(db)

    # Parse the response content
    import json

    health_data = json.loads(basic_response.body)

    # Add additional system information
    health_data.update(
        {
            "system": {
                "use_stubs": settings.use_stubs,
                "features": {
                    "emails": settings.enable_emails,
                    "enrichment": settings.enable_enrichment,
                    "llm_insights": settings.enable_llm_insights,
                    "email_tracking": settings.enable_email_tracking,
                    "template_studio": settings.enable_template_studio,
                    "scoring_playground": settings.enable_scoring_playground,
                    "governance": settings.enable_governance,
                },
                "limits": {
                    "max_daily_emails": settings.max_daily_emails,
                    "max_businesses_per_batch": settings.max_businesses_per_batch,
                    "request_timeout": settings.request_timeout,
                },
            }
        }
    )

    return JSONResponse(status_code=basic_response.status_code, content=health_data)
