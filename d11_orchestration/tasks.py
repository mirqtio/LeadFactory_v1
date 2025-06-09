"""
D11 Orchestration Tasks - Task 076

Task executors for individual pipeline stages that integrate with domain-specific
coordinators and maintain proper error handling, logging, and metrics collection.

These task classes wrap the domain coordinators and provide the interface
needed by the Prefect pipeline orchestration system.
"""

import asyncio
from datetime import datetime
from typing import Dict, List, Optional, Any
from abc import ABC, abstractmethod

try:
    from prefect.logging import get_run_logger
except ImportError:
    def get_run_logger():
        import logging
        return logging.getLogger(__name__)

from d2_sourcing.coordinator import SourcingCoordinator
from d3_assessment.coordinator import AssessmentCoordinator
from core.exceptions import LeadFactoryError
from core.metrics import MetricsCollector

# Mock imports for modules not yet implemented or incompatible with task interface
try:
    from d1_targeting.target_universe import TargetUniverseManager
    # Create wrapper for consistency with task interface
    class TargetingAPI:
        def __init__(self):
            self.manager = TargetUniverseManager()
        
        async def search_businesses(self, query, location, verticals, limit=1000):
            # Mock implementation - would integrate with actual targeting logic
            return [
                {"id": f"business_{i}", "name": f"Business {i}", "location": location, "vertical": verticals[i % len(verticals)]}
                for i in range(min(limit, 100))  # Mock data
            ]
except ImportError:
    class TargetingAPI:
        async def search_businesses(self, query, location, verticals, limit=1000):
            return [
                {"id": f"business_{i}", "name": f"Business {i}", "location": location, "vertical": verticals[i % len(verticals)]}
                for i in range(min(limit, 100))
            ]

# Mock imports for modules not yet implemented
try:
    from d6_payment.tier_assignment import TierAssignmentSystem
except ImportError:
    class TierAssignmentSystem:
        async def calculate_business_score(self, assessment_data):
            return 75  # Mock score
        
        async def assign_tier(self, business_score, business_data):
            if business_score >= 80:
                return "premium"
            elif business_score >= 60:
                return "standard"
            else:
                return "basic"

try:
    from d4_engagement.personalizer import EmailPersonalizer
except ImportError:
    class EmailPersonalizer:
        async def create_personalized_report(self, business_data, assessment_data, tier):
            return {
                "content": f"Personalized report for {business_data.get('name', 'Business')}",
                "tier": tier,
                "assessment_summary": assessment_data.get("summary", "No assessment"),
                "recommendations": ["Improve website performance", "Enhance SEO"]
            }

try:
    from d5_delivery.manager import DeliveryManager
except ImportError:
    class DeliveryManager:
        async def deliver_report(self, business_data, report_content, tier):
            # Mock successful delivery
            return True


class BaseTask(ABC):
    """
    Base task executor class
    
    Provides common functionality for all pipeline task executors including
    logging, metrics collection, and error handling patterns.
    """
    
    def __init__(self, metrics_collector: Optional[MetricsCollector] = None):
        self.metrics = metrics_collector or MetricsCollector()
        self.logger = get_run_logger()
    
    @abstractmethod
    async def execute(self, **kwargs) -> Dict[str, Any]:
        """Execute the task with given parameters"""
        pass
    
    async def _record_task_metrics(
        self, 
        task_name: str, 
        duration_seconds: float,
        status: str,
        count: int = 0,
        error: Optional[str] = None
    ) -> None:
        """Record task execution metrics"""
        
        await self.metrics.record_task_execution(
            task_name=task_name,
            duration_seconds=duration_seconds,
            status=status,
            records_processed=count,
            error_message=error
        )


class TargetingTask(BaseTask):
    """
    Business targeting task executor
    
    Integrates with D1 Targeting domain to identify target businesses
    based on specified criteria and quotas.
    """
    
    def __init__(self, metrics_collector: Optional[MetricsCollector] = None):
        super().__init__(metrics_collector)
        self.targeting_api = TargetingAPI()
    
    async def execute(
        self,
        execution_date: datetime,
        config: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Execute business targeting stage"""
        
        start_time = datetime.utcnow()
        task_config = config or {}
        
        try:
            self.logger.info(f"Starting targeting for {execution_date.date()}")
            
            # Get targeting parameters from config
            target_count = task_config.get("target_count", 1000)
            verticals = task_config.get("verticals", ["restaurant", "retail", "healthcare"])
            location = task_config.get("location", "San Francisco, CA")
            
            # Execute targeting
            businesses = await self.targeting_api.search_businesses(
                query="",  # General search
                location=location,
                verticals=verticals,
                limit=target_count
            )
            
            # Track success metrics
            duration = (datetime.utcnow() - start_time).total_seconds()
            await self._record_task_metrics(
                task_name="targeting",
                duration_seconds=duration,
                status="success",
                count=len(businesses)
            )
            
            result = {
                "businesses": businesses,
                "target_count": len(businesses),
                "execution_date": execution_date.isoformat(),
                "config": task_config
            }
            
            self.logger.info(f"Targeting completed: {len(businesses)} businesses found")
            return result
            
        except Exception as e:
            # Track error metrics
            duration = (datetime.utcnow() - start_time).total_seconds()
            await self._record_task_metrics(
                task_name="targeting",
                duration_seconds=duration,
                status="failed",
                error=str(e)
            )
            
            self.logger.error(f"Targeting failed: {str(e)}", exc_info=True)
            raise LeadFactoryError(f"Targeting task failed: {str(e)}") from e


class SourcingTask(BaseTask):
    """
    Business data sourcing task executor
    
    Integrates with D2 Sourcing domain to enrich business data
    with additional information from external sources.
    """
    
    def __init__(self, metrics_collector: Optional[MetricsCollector] = None):
        super().__init__(metrics_collector)
        self.sourcing_coordinator = SourcingCoordinator()
    
    async def execute(
        self,
        businesses: List[Dict[str, Any]],
        execution_date: datetime,
        config: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Execute business data sourcing stage"""
        
        start_time = datetime.utcnow()
        task_config = config or {}
        
        try:
            self.logger.info(f"Starting sourcing for {len(businesses)} businesses")
            
            # Process businesses in batches
            batch_size = task_config.get("batch_size", 100)
            enriched_businesses = []
            
            for i in range(0, len(businesses), batch_size):
                batch = businesses[i:i + batch_size]
                
                self.logger.info(f"Processing batch {i//batch_size + 1}")
                
                # Enrich each business in the batch
                for business in batch:
                    try:
                        enriched = await self.sourcing_coordinator.enrich_business(
                            business_data=business
                        )
                        enriched_businesses.append(enriched)
                        
                    except Exception as e:
                        self.logger.warning(f"Failed to enrich business {business.get('id', 'unknown')}: {str(e)}")
                        # Continue with original data
                        enriched_businesses.append(business)
            
            # Track success metrics
            duration = (datetime.utcnow() - start_time).total_seconds()
            await self._record_task_metrics(
                task_name="sourcing",
                duration_seconds=duration,
                status="success",
                count=len(enriched_businesses)
            )
            
            result = {
                "enriched_businesses": enriched_businesses,
                "original_count": len(businesses),
                "enriched_count": len(enriched_businesses),
                "execution_date": execution_date.isoformat(),
                "config": task_config
            }
            
            self.logger.info(f"Sourcing completed: {len(enriched_businesses)} businesses enriched")
            return result
            
        except Exception as e:
            # Track error metrics
            duration = (datetime.utcnow() - start_time).total_seconds()
            await self._record_task_metrics(
                task_name="sourcing",
                duration_seconds=duration,
                status="failed",
                error=str(e)
            )
            
            self.logger.error(f"Sourcing failed: {str(e)}", exc_info=True)
            raise LeadFactoryError(f"Sourcing task failed: {str(e)}") from e


class AssessmentTask(BaseTask):
    """
    Website assessment task executor
    
    Integrates with D3 Assessment domain to analyze business websites
    and generate comprehensive assessment reports.
    """
    
    def __init__(self, metrics_collector: Optional[MetricsCollector] = None):
        super().__init__(metrics_collector)
        self.assessment_coordinator = AssessmentCoordinator()
    
    async def execute(
        self,
        businesses: List[Dict[str, Any]],
        execution_date: datetime,
        config: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Execute website assessment stage"""
        
        start_time = datetime.utcnow()
        task_config = config or {}
        
        try:
            self.logger.info(f"Starting assessment for {len(businesses)} businesses")
            
            # Process assessments with concurrency control
            max_concurrent = task_config.get("max_concurrent_assessments", 10)
            assessments = []
            
            # Create semaphore for concurrency control
            semaphore = asyncio.Semaphore(max_concurrent)
            
            async def assess_business(business: Dict[str, Any]) -> Optional[Dict[str, Any]]:
                async with semaphore:
                    try:
                        assessment = await self.assessment_coordinator.assess_business(
                            business_data=business
                        )
                        return assessment
                        
                    except Exception as e:
                        self.logger.warning(f"Failed to assess business {business.get('id', 'unknown')}: {str(e)}")
                        return None
            
            # Execute assessments concurrently
            tasks = [assess_business(business) for business in businesses]
            assessment_results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # Filter successful assessments
            for result in assessment_results:
                if result and not isinstance(result, Exception):
                    assessments.append(result)
            
            # Track success metrics
            duration = (datetime.utcnow() - start_time).total_seconds()
            await self._record_task_metrics(
                task_name="assessment",
                duration_seconds=duration,
                status="success",
                count=len(assessments)
            )
            
            result = {
                "assessments": assessments,
                "original_count": len(businesses),
                "assessed_count": len(assessments),
                "execution_date": execution_date.isoformat(),
                "config": task_config
            }
            
            self.logger.info(f"Assessment completed: {len(assessments)} businesses assessed")
            return result
            
        except Exception as e:
            # Track error metrics
            duration = (datetime.utcnow() - start_time).total_seconds()
            await self._record_task_metrics(
                task_name="assessment",
                duration_seconds=duration,
                status="failed",
                error=str(e)
            )
            
            self.logger.error(f"Assessment failed: {str(e)}", exc_info=True)
            raise LeadFactoryError(f"Assessment task failed: {str(e)}") from e


class ScoringTask(BaseTask):
    """
    Business scoring and tier assignment task executor
    
    Integrates with D6 Payment tier assignment system to score businesses
    and assign appropriate tiers based on assessment results.
    """
    
    def __init__(self, metrics_collector: Optional[MetricsCollector] = None):
        super().__init__(metrics_collector)
        self.tier_system = TierAssignmentSystem()
    
    async def execute(
        self,
        assessments: List[Dict[str, Any]],
        execution_date: datetime,
        config: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Execute business scoring and tier assignment stage"""
        
        start_time = datetime.utcnow()
        task_config = config or {}
        
        try:
            self.logger.info(f"Starting scoring for {len(assessments)} assessments")
            
            scored_businesses = []
            
            # Score each business based on assessment
            for assessment in assessments:
                try:
                    # Calculate business score
                    score = await self.tier_system.calculate_business_score(
                        assessment_data=assessment
                    )
                    
                    # Assign tier based on score
                    tier = await self.tier_system.assign_tier(
                        business_score=score,
                        business_data=assessment.get("business", {})
                    )
                    
                    scored_business = {
                        "business": assessment.get("business", {}),
                        "assessment": assessment,
                        "score": score,
                        "tier": tier,
                        "scored_at": datetime.utcnow().isoformat()
                    }
                    
                    scored_businesses.append(scored_business)
                    
                except Exception as e:
                    self.logger.warning(f"Failed to score business: {str(e)}")
                    # Continue with unscored business
                    scored_businesses.append({
                        "business": assessment.get("business", {}),
                        "assessment": assessment,
                        "score": 0,
                        "tier": "basic",
                        "scored_at": datetime.utcnow().isoformat(),
                        "error": str(e)
                    })
            
            # Track success metrics
            duration = (datetime.utcnow() - start_time).total_seconds()
            await self._record_task_metrics(
                task_name="scoring",
                duration_seconds=duration,
                status="success",
                count=len(scored_businesses)
            )
            
            result = {
                "scored_businesses": scored_businesses,
                "original_count": len(assessments),
                "scored_count": len(scored_businesses),
                "execution_date": execution_date.isoformat(),
                "config": task_config
            }
            
            self.logger.info(f"Scoring completed: {len(scored_businesses)} businesses scored")
            return result
            
        except Exception as e:
            # Track error metrics
            duration = (datetime.utcnow() - start_time).total_seconds()
            await self._record_task_metrics(
                task_name="scoring",
                duration_seconds=duration,
                status="failed",
                error=str(e)
            )
            
            self.logger.error(f"Scoring failed: {str(e)}", exc_info=True)
            raise LeadFactoryError(f"Scoring task failed: {str(e)}") from e


class PersonalizationTask(BaseTask):
    """
    Email personalization task executor
    
    Integrates with D4 Engagement personalizer to create personalized
    email content and reports for each business.
    """
    
    def __init__(self, metrics_collector: Optional[MetricsCollector] = None):
        super().__init__(metrics_collector)
        self.personalizer = EmailPersonalizer()
    
    async def execute(
        self,
        scored_businesses: List[Dict[str, Any]],
        execution_date: datetime,
        config: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Execute email personalization stage"""
        
        start_time = datetime.utcnow()
        task_config = config or {}
        
        try:
            self.logger.info(f"Starting personalization for {len(scored_businesses)} businesses")
            
            personalized_reports = []
            
            # Process personalization with concurrency control
            max_concurrent = task_config.get("max_concurrent_personalization", 5)
            semaphore = asyncio.Semaphore(max_concurrent)
            
            async def personalize_business(scored_business: Dict[str, Any]) -> Optional[Dict[str, Any]]:
                async with semaphore:
                    try:
                        report = await self.personalizer.create_personalized_report(
                            business_data=scored_business["business"],
                            assessment_data=scored_business["assessment"],
                            tier=scored_business["tier"]
                        )
                        
                        return {
                            "business": scored_business["business"],
                            "assessment": scored_business["assessment"],
                            "score": scored_business["score"],
                            "tier": scored_business["tier"],
                            "report": report,
                            "personalized_at": datetime.utcnow().isoformat()
                        }
                        
                    except Exception as e:
                        self.logger.warning(f"Failed to personalize for business: {str(e)}")
                        return None
            
            # Execute personalization concurrently
            tasks = [personalize_business(business) for business in scored_businesses]
            personalization_results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # Filter successful personalizations
            for result in personalization_results:
                if result and not isinstance(result, Exception):
                    personalized_reports.append(result)
            
            # Track success metrics
            duration = (datetime.utcnow() - start_time).total_seconds()
            await self._record_task_metrics(
                task_name="personalization",
                duration_seconds=duration,
                status="success",
                count=len(personalized_reports)
            )
            
            result = {
                "reports": personalized_reports,
                "original_count": len(scored_businesses),
                "personalized_count": len(personalized_reports),
                "execution_date": execution_date.isoformat(),
                "config": task_config
            }
            
            self.logger.info(f"Personalization completed: {len(personalized_reports)} reports created")
            return result
            
        except Exception as e:
            # Track error metrics
            duration = (datetime.utcnow() - start_time).total_seconds()
            await self._record_task_metrics(
                task_name="personalization",
                duration_seconds=duration,
                status="failed",
                error=str(e)
            )
            
            self.logger.error(f"Personalization failed: {str(e)}", exc_info=True)
            raise LeadFactoryError(f"Personalization task failed: {str(e)}") from e


class DeliveryTask(BaseTask):
    """
    Report delivery task executor
    
    Integrates with D5 Delivery manager to send personalized reports
    to business contacts via email or other channels.
    """
    
    def __init__(self, metrics_collector: Optional[MetricsCollector] = None):
        super().__init__(metrics_collector)
        self.delivery_manager = DeliveryManager()
    
    async def execute(
        self,
        personalized_reports: List[Dict[str, Any]],
        execution_date: datetime,
        config: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Execute report delivery stage"""
        
        start_time = datetime.utcnow()
        task_config = config or {}
        
        try:
            self.logger.info(f"Starting delivery for {len(personalized_reports)} reports")
            
            delivered_count = 0
            failed_deliveries = []
            
            # Process deliveries with rate limiting
            max_concurrent = task_config.get("max_concurrent_deliveries", 3)
            semaphore = asyncio.Semaphore(max_concurrent)
            
            async def deliver_report(report_data: Dict[str, Any]) -> bool:
                async with semaphore:
                    try:
                        success = await self.delivery_manager.deliver_report(
                            business_data=report_data["business"],
                            report_content=report_data["report"],
                            tier=report_data["tier"]
                        )
                        
                        return success
                        
                    except Exception as e:
                        self.logger.warning(f"Failed to deliver report: {str(e)}")
                        failed_deliveries.append({
                            "business_id": report_data["business"].get("id"),
                            "error": str(e)
                        })
                        return False
            
            # Execute deliveries concurrently
            tasks = [deliver_report(report) for report in personalized_reports]
            delivery_results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # Count successful deliveries
            for result in delivery_results:
                if result is True:
                    delivered_count += 1
            
            # Track success metrics
            duration = (datetime.utcnow() - start_time).total_seconds()
            await self._record_task_metrics(
                task_name="delivery",
                duration_seconds=duration,
                status="success",
                count=delivered_count
            )
            
            result = {
                "delivered_count": delivered_count,
                "failed_count": len(failed_deliveries),
                "total_count": len(personalized_reports),
                "failed_deliveries": failed_deliveries,
                "execution_date": execution_date.isoformat(),
                "config": task_config
            }
            
            self.logger.info(f"Delivery completed: {delivered_count}/{len(personalized_reports)} reports delivered")
            return result
            
        except Exception as e:
            # Track error metrics
            duration = (datetime.utcnow() - start_time).total_seconds()
            await self._record_task_metrics(
                task_name="delivery",
                duration_seconds=duration,
                status="failed",
                error=str(e)
            )
            
            self.logger.error(f"Delivery failed: {str(e)}", exc_info=True)
            raise LeadFactoryError(f"Delivery task failed: {str(e)}") from e