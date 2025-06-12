#!/usr/bin/env python3
"""
Schedule production tests in Prefect

Sets up:
- Daily smoke tests at 20:30 UTC
- Heartbeat checks every 2 hours
- Cleanup jobs
"""
import asyncio
import sys
from pathlib import Path
from datetime import time

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from prefect import serve
from prefect.deployments import Deployment
from prefect.server.schemas.schedules import CronSchedule, IntervalSchedule

from tests.e2e.test_production_smoke import daily_smoke_flow
from tests.e2e.test_heartbeat import heartbeat_flow
from core.logging import get_logger

logger = get_logger(__name__)


async def create_deployments():
    """Create Prefect deployments for scheduled tests"""
    
    # Daily smoke test deployment
    smoke_deployment = await Deployment.build_from_flow(
        flow=daily_smoke_flow,
        name="daily-smoke-test",
        description="Full pipeline smoke test - runs daily at 20:30 UTC",
        schedule=CronSchedule(cron="30 20 * * *", timezone="UTC"),
        tags=["production", "smoke-test", "daily"],
        parameters={},
        work_queue_name="leadfactory"
    )
    
    smoke_id = await smoke_deployment.apply()
    logger.info(f"Created daily smoke test deployment: {smoke_id}")
    
    # Heartbeat deployment (every 2 hours)
    heartbeat_deployment = await Deployment.build_from_flow(
        flow=heartbeat_flow,
        name="heartbeat-check",
        description="Service health checks - runs every 2 hours",
        schedule=IntervalSchedule(interval=7200),  # 2 hours in seconds
        tags=["production", "heartbeat", "monitoring"],
        parameters={},
        work_queue_name="leadfactory"
    )
    
    heartbeat_id = await heartbeat_deployment.apply()
    logger.info(f"Created heartbeat deployment: {heartbeat_id}")
    
    # Also create a cleanup flow
    from d11_orchestration.tasks import cleanup_old_data
    
    @flow(name="daily-cleanup")
    async def cleanup_flow():
        """Clean up old test and temporary data"""
        logger.info("Running daily cleanup")
        
        # Clean up old smoke test data
        deleted_smoke = await cleanup_old_data(
            table="businesses",
            where_clause="id LIKE 'smoke_%' AND created_at < NOW() - INTERVAL '7 days'"
        )
        
        # Clean up old heartbeat data
        deleted_heartbeat = await cleanup_old_data(
            table="businesses",
            where_clause="id LIKE 'heartbeat_%' AND created_at < NOW() - INTERVAL '1 day'"
        )
        
        # Clean up orphaned records
        deleted_orphans = await cleanup_old_data(
            table="emails",
            where_clause="""
                business_id NOT IN (SELECT id FROM businesses)
                AND created_at < NOW() - INTERVAL '30 days'
            """
        )
        
        logger.info(
            f"Cleanup complete: "
            f"smoke={deleted_smoke}, "
            f"heartbeat={deleted_heartbeat}, "
            f"orphans={deleted_orphans}"
        )
        
        return {
            "deleted_smoke": deleted_smoke,
            "deleted_heartbeat": deleted_heartbeat,
            "deleted_orphans": deleted_orphans
        }
    
    cleanup_deployment = await Deployment.build_from_flow(
        flow=cleanup_flow,
        name="daily-cleanup",
        description="Clean up old test data - runs daily at 03:00 UTC",
        schedule=CronSchedule(cron="0 3 * * *", timezone="UTC"),
        tags=["production", "cleanup", "daily"],
        parameters={},
        work_queue_name="leadfactory"
    )
    
    cleanup_id = await cleanup_deployment.apply()
    logger.info(f"Created cleanup deployment: {cleanup_id}")
    
    return {
        "smoke": smoke_id,
        "heartbeat": heartbeat_id,
        "cleanup": cleanup_id
    }


async def main():
    """Create and start scheduled test deployments"""
    logger.info("Setting up Prefect scheduled tests...")
    
    # Create deployments
    deployment_ids = await create_deployments()
    
    logger.info("\nDeployments created successfully!")
    logger.info("\nSchedule Summary:")
    logger.info("- Daily Smoke Test: 20:30 UTC (30 min before nightly batch)")
    logger.info("- Heartbeat Checks: Every 2 hours (00:00, 02:00, 04:00...)")
    logger.info("- Cleanup Job: Daily at 03:00 UTC")
    
    logger.info("\nTo start the Prefect agent:")
    logger.info("  prefect agent start -q leadfactory")
    
    logger.info("\nTo view deployments:")
    logger.info("  prefect deployment ls")
    
    logger.info("\nTo run a deployment manually:")
    logger.info("  prefect deployment run 'daily-smoke-flow/daily-smoke-test'")
    
    # Optionally start serving flows
    if "--serve" in sys.argv:
        logger.info("\nStarting flow server...")
        await serve(
            daily_smoke_flow.to_deployment(
                name="daily-smoke-test",
                cron="30 20 * * *"
            ),
            heartbeat_flow.to_deployment(
                name="heartbeat-check",
                interval=7200
            ),
            cleanup_flow.to_deployment(
                name="daily-cleanup",
                cron="0 3 * * *"
            )
        )


if __name__ == "__main__":
    asyncio.run(main())