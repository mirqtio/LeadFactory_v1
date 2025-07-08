"""
Internal API routes for administrative functions.

These endpoints should be protected and not exposed publicly.
"""
import time
from typing import Dict, Any
import logging

from fastapi import APIRouter, HTTPException, Depends, Header
from fastapi.responses import JSONResponse
from prometheus_client import Counter, Histogram

from core.logging import get_logger
from core.auth import verify_internal_token
from d5_scoring.engine import ConfigurableScoringEngine
from d5_scoring.rules_schema import validate_rules

logger = get_logger(__name__)
router = APIRouter(prefix="/internal", tags=["internal"])

# Metrics
reload_requests = Counter(
    'internal_reload_requests_total',
    'Total number of internal reload requests',
    ['endpoint', 'status']
)

reload_duration = Histogram(
    'internal_reload_duration_seconds',
    'Time spent processing reload requests'
)


def get_internal_auth(x_internal_token: str = Header(...)) -> bool:
    """Verify internal authentication token."""
    if not verify_internal_token(x_internal_token):
        raise HTTPException(
            status_code=403,
            detail="Invalid internal token"
        )
    return True


@router.post("/reload_rules")
@reload_duration.time()
async def reload_scoring_rules(
    auth: bool = Depends(get_internal_auth)
) -> Dict[str, Any]:
    """
    Reload scoring rules from YAML configuration.
    
    This endpoint allows hot-reloading of scoring configuration
    without restarting the service.
    
    Returns:
        JSON with reload status and details
    """
    start_time = time.time()
    
    try:
        # Get the scoring engine instance
        # In production, this would be injected via dependency
        from d5_scoring import get_scoring_engine
        engine = get_scoring_engine()
        
        if not isinstance(engine, ConfigurableScoringEngine):
            raise HTTPException(
                status_code=501,
                detail="Scoring engine does not support hot reload"
            )
        
        # Get current configuration info
        old_version = engine.rules_parser.schema.version if engine.rules_parser.schema else "unknown"
        old_file = engine.rules_parser.rules_file
        
        # Validate new configuration first
        try:
            new_schema = validate_rules(old_file)
            new_version = new_schema.version
        except Exception as e:
            reload_requests.labels(endpoint='reload_rules', status='validation_failed').inc()
            logger.error(
                f"Configuration validation failed: {e}",
                extra={
                    "event": "rules_reload",
                    "status": "failure",
                    "msg": f"Validation failed: {str(e)}",
                    "sha": _get_git_sha(),
                    "timestamp": time.time()
                }
            )
            raise HTTPException(
                status_code=400,
                detail=f"Configuration validation failed: {str(e)}"
            )
        
        # Perform reload
        engine.reload_rules()
        
        # Calculate reload time
        reload_time = time.time() - start_time
        
        reload_requests.labels(endpoint='reload_rules', status='success').inc()
        logger.info(
            f"Scoring rules reloaded successfully in {reload_time:.3f}s",
            extra={
                "event": "rules_reload",
                "status": "success",
                "old_version": old_version,
                "new_version": new_version,
                "reload_time_seconds": reload_time
            }
        )
        
        return {
            "status": "success",
            "message": "Scoring rules reloaded successfully",
            "details": {
                "old_version": old_version,
                "new_version": new_version,
                "config_file": str(old_file),
                "reload_time_seconds": reload_time,
                "timestamp": time.time()
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        reload_requests.labels(endpoint='reload_rules', status='error').inc()
        logger.error(
            f"Failed to reload scoring rules: {e}",
            extra={
                "event": "rules_reload",
                "status": "failure",
                "msg": str(e),
                "sha": _get_git_sha(),
                "timestamp": time.time()
            },
            exc_info=True
        )
        raise HTTPException(
            status_code=500,
            detail=f"Failed to reload scoring rules: {str(e)}"
        )


@router.get("/health/scoring")
async def scoring_health_check(
    auth: bool = Depends(get_internal_auth)
) -> Dict[str, Any]:
    """
    Check health of scoring system.
    
    Returns:
        JSON with scoring system health status
    """
    try:
        from d5_scoring import get_scoring_engine
        engine = get_scoring_engine()
        
        # Check if engine has valid configuration
        has_config = False
        config_version = "unknown"
        
        if hasattr(engine, 'rules_parser') and engine.rules_parser.schema:
            has_config = True
            config_version = engine.rules_parser.schema.version
        
        # Try a test score calculation
        test_data = {
            'company_info': {'name_quality': True},
            'online_presence': {'website_quality': True}
        }
        
        can_score = False
        try:
            result = engine.calculate_score(test_data)
            can_score = 'total_score' in result
        except:
            pass
        
        return {
            "status": "healthy" if has_config and can_score else "unhealthy",
            "details": {
                "has_configuration": has_config,
                "configuration_version": config_version,
                "can_calculate_scores": can_score,
                "engine_type": engine.__class__.__name__
            }
        }
        
    except Exception as e:
        logger.error(f"Health check failed: {e}", exc_info=True)
        return {
            "status": "unhealthy",
            "error": str(e)
        }


def _get_git_sha() -> str:
    """Get current git SHA if available."""
    try:
        import subprocess
        result = subprocess.run(
            ['git', 'rev-parse', 'HEAD'],
            capture_output=True,
            text=True,
            check=True
        )
        return result.stdout.strip()[:8]
    except:
        return "unknown"