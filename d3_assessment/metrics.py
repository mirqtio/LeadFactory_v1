"""
Assessment Metrics - Task 037

Implements metrics collection for assessment functionality using Prometheus.
Tracks assessment counts, duration histograms, cost tracking, and success/failure rates.

Acceptance Criteria:
- Assessment counts tracked
- Duration histograms
- Cost tracking accurate
- Success/failure rates
"""
import time
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta
from decimal import Decimal
from contextlib import contextmanager
from functools import wraps
import logging

from prometheus_client import Counter, Histogram, Gauge, Summary, Info

from .types import AssessmentType, AssessmentStatus

# Setup logging
logger = logging.getLogger(__name__)

# Assessment count metrics
assessment_total = Counter(
    'assessment_total',
    'Total number of assessments triggered',
    ['business_id', 'assessment_type', 'industry']
)

assessment_completed = Counter(
    'assessment_completed',
    'Total number of assessments completed successfully',
    ['business_id', 'assessment_type', 'industry']
)

assessment_failed = Counter(
    'assessment_failed',
    'Total number of failed assessments',
    ['business_id', 'assessment_type', 'industry', 'error_type']
)

# Duration metrics
assessment_duration = Histogram(
    'assessment_duration_seconds',
    'Assessment duration in seconds',
    ['assessment_type', 'industry'],
    buckets=(0.5, 1.0, 2.5, 5.0, 10.0, 30.0, 60.0, 120.0, 300.0, float("inf"))
)

assessment_processing_time = Summary(
    'assessment_processing_time_seconds',
    'Detailed processing time for assessments',
    ['assessment_type', 'step']
)

# Cost metrics
assessment_cost_total = Counter(
    'assessment_cost_usd_total',
    'Total cost of assessments in USD',
    ['assessment_type', 'cost_category']
)

assessment_cost_per_request = Histogram(
    'assessment_cost_usd_per_request',
    'Cost per assessment request in USD',
    ['assessment_type'],
    buckets=(0.01, 0.05, 0.10, 0.25, 0.50, 1.00, 2.50, 5.00, 10.00, float("inf"))
)

# Success/failure rate metrics
assessment_success_rate = Gauge(
    'assessment_success_rate',
    'Current success rate of assessments (rolling window)',
    ['assessment_type', 'window']
)

assessment_error_rate = Gauge(
    'assessment_error_rate',
    'Current error rate of assessments (rolling window)',
    ['assessment_type', 'window']
)

# Active assessment metrics
active_assessments = Gauge(
    'assessment_active',
    'Number of currently active assessments',
    ['assessment_type']
)

assessment_queue_size = Gauge(
    'assessment_queue_size',
    'Number of assessments in queue',
    ['priority']
)

# Resource usage metrics
assessment_memory_usage = Gauge(
    'assessment_memory_usage_bytes',
    'Memory usage by assessment processes',
    ['assessment_type']
)

assessment_api_calls = Counter(
    'assessment_api_calls_total',
    'Total API calls made during assessments',
    ['assessment_type', 'api_provider', 'status_code']
)

# Cache metrics
assessment_cache_hits = Counter(
    'assessment_cache_hits_total',
    'Total cache hits for assessments',
    ['assessment_type']
)

assessment_cache_misses = Counter(
    'assessment_cache_misses_total',
    'Total cache misses for assessments',
    ['assessment_type']
)

# Business metrics
assessment_by_industry = Counter(
    'assessment_by_industry_total',
    'Assessments grouped by industry',
    ['industry', 'assessment_type']
)

assessment_by_hour = Counter(
    'assessment_by_hour_total',
    'Assessments grouped by hour of day',
    ['hour', 'assessment_type']
)

# System info
assessment_system_info = Info(
    'assessment_system',
    'Assessment system information'
)
assessment_system_info.info({
    'version': '1.0.0',
    'environment': 'production'
})


class AssessmentMetrics:
    """
    Assessment metrics collector
    
    Acceptance Criteria: Assessment counts tracked, Duration histograms,
    Cost tracking accurate, Success/failure rates
    """
    
    def __init__(self):
        """Initialize metrics collector"""
        self._start_time = time.time()
        self._success_window: List[Dict[str, Any]] = []
        self._error_window: List[Dict[str, Any]] = []
        self._window_duration = timedelta(minutes=15)  # 15-minute rolling window
        
    def track_assessment_start(
        self,
        business_id: str,
        assessment_type: AssessmentType,
        industry: str = "unknown"
    ) -> str:
        """
        Track assessment start
        
        Acceptance Criteria: Assessment counts tracked
        """
        # Increment total assessments
        assessment_total.labels(
            business_id=business_id,
            assessment_type=assessment_type.value,
            industry=industry
        ).inc()
        
        # Increment active assessments
        active_assessments.labels(assessment_type=assessment_type.value).inc()
        
        # Track by industry and hour
        current_hour = datetime.utcnow().hour
        assessment_by_industry.labels(
            industry=industry,
            assessment_type=assessment_type.value
        ).inc()
        assessment_by_hour.labels(
            hour=str(current_hour),
            assessment_type=assessment_type.value
        ).inc()
        
        # Generate tracking ID
        tracking_id = f"track_{int(time.time() * 1000)}_{assessment_type.value}"
        
        logger.debug(f"Started tracking assessment {tracking_id}")
        return tracking_id
        
    def track_assessment_complete(
        self,
        tracking_id: str,
        business_id: str,
        assessment_type: AssessmentType,
        industry: str = "unknown",
        duration_seconds: float = None,
        cost_usd: Decimal = Decimal("0"),
        status: AssessmentStatus = AssessmentStatus.COMPLETED
    ):
        """
        Track assessment completion
        
        Acceptance Criteria: Assessment counts tracked, Success/failure rates
        """
        # Decrement active assessments
        active_assessments.labels(assessment_type=assessment_type.value).dec()
        
        if status == AssessmentStatus.COMPLETED:
            # Increment completed count
            assessment_completed.labels(
                business_id=business_id,
                assessment_type=assessment_type.value,
                industry=industry
            ).inc()
            
            # Add to success window
            self._add_to_success_window(assessment_type)
            
        elif status in [AssessmentStatus.FAILED, AssessmentStatus.ERROR]:
            # Increment failed count
            assessment_failed.labels(
                business_id=business_id,
                assessment_type=assessment_type.value,
                industry=industry,
                error_type="assessment_failed"
            ).inc()
            
            # Add to error window
            self._add_to_error_window(assessment_type)
        
        # Track duration if provided
        if duration_seconds is not None:
            self.track_duration(assessment_type, industry, duration_seconds)
        
        # Track cost if provided
        if cost_usd > 0:
            self.track_cost(assessment_type, cost_usd)
        
        # Update success/failure rates
        self._update_success_failure_rates()
        
        logger.debug(f"Completed tracking assessment {tracking_id} with status {status}")
        
    def track_duration(
        self,
        assessment_type: AssessmentType,
        industry: str,
        duration_seconds: float
    ):
        """
        Track assessment duration
        
        Acceptance Criteria: Duration histograms
        """
        assessment_duration.labels(
            assessment_type=assessment_type.value,
            industry=industry
        ).observe(duration_seconds)
        
        logger.debug(f"Tracked duration {duration_seconds}s for {assessment_type.value}")
        
    def track_processing_step(
        self,
        assessment_type: AssessmentType,
        step: str,
        duration_seconds: float
    ):
        """Track duration of specific processing step"""
        assessment_processing_time.labels(
            assessment_type=assessment_type.value,
            step=step
        ).observe(duration_seconds)
        
    def track_cost(
        self,
        assessment_type: AssessmentType,
        cost_usd: Decimal,
        cost_category: str = "api_call"
    ):
        """
        Track assessment cost
        
        Acceptance Criteria: Cost tracking accurate
        """
        cost_float = float(cost_usd)
        
        # Track total cost
        assessment_cost_total.labels(
            assessment_type=assessment_type.value,
            cost_category=cost_category
        ).inc(cost_float)
        
        # Track cost per request
        assessment_cost_per_request.labels(
            assessment_type=assessment_type.value
        ).observe(cost_float)
        
        logger.debug(f"Tracked cost ${cost_float} for {assessment_type.value}")
        
    def track_api_call(
        self,
        assessment_type: AssessmentType,
        api_provider: str,
        status_code: int
    ):
        """Track API call made during assessment"""
        assessment_api_calls.labels(
            assessment_type=assessment_type.value,
            api_provider=api_provider,
            status_code=str(status_code)
        ).inc()
        
    def track_cache_hit(self, assessment_type: AssessmentType):
        """Track cache hit"""
        assessment_cache_hits.labels(
            assessment_type=assessment_type.value
        ).inc()
        
    def track_cache_miss(self, assessment_type: AssessmentType):
        """Track cache miss"""
        assessment_cache_misses.labels(
            assessment_type=assessment_type.value
        ).inc()
        
    def update_queue_size(self, priority: str, size: int):
        """Update assessment queue size"""
        assessment_queue_size.labels(priority=priority).set(size)
        
    def update_memory_usage(self, assessment_type: AssessmentType, bytes_used: int):
        """Update memory usage metric"""
        assessment_memory_usage.labels(
            assessment_type=assessment_type.value
        ).set(bytes_used)
        
    def _add_to_success_window(self, assessment_type: AssessmentType):
        """Add successful assessment to rolling window"""
        self._success_window.append({
            "timestamp": datetime.utcnow(),
            "assessment_type": assessment_type
        })
        self._cleanup_windows()
        
    def _add_to_error_window(self, assessment_type: AssessmentType):
        """Add failed assessment to rolling window"""
        self._error_window.append({
            "timestamp": datetime.utcnow(),
            "assessment_type": assessment_type
        })
        self._cleanup_windows()
        
    def _cleanup_windows(self):
        """Remove old entries from rolling windows"""
        cutoff_time = datetime.utcnow() - self._window_duration
        
        self._success_window = [
            entry for entry in self._success_window
            if entry["timestamp"] > cutoff_time
        ]
        
        self._error_window = [
            entry for entry in self._error_window
            if entry["timestamp"] > cutoff_time
        ]
        
    def _update_success_failure_rates(self):
        """
        Update success/failure rate gauges
        
        Acceptance Criteria: Success/failure rates
        """
        # Calculate rates by assessment type
        assessment_types = set(
            [e["assessment_type"] for e in self._success_window] +
            [e["assessment_type"] for e in self._error_window]
        )
        
        for assessment_type in assessment_types:
            success_count = len([
                e for e in self._success_window
                if e["assessment_type"] == assessment_type
            ])
            
            error_count = len([
                e for e in self._error_window
                if e["assessment_type"] == assessment_type
            ])
            
            total_count = success_count + error_count
            
            if total_count > 0:
                success_rate = success_count / total_count
                error_rate = error_count / total_count
                
                assessment_success_rate.labels(
                    assessment_type=assessment_type.value,
                    window="15m"
                ).set(success_rate)
                
                assessment_error_rate.labels(
                    assessment_type=assessment_type.value,
                    window="15m"
                ).set(error_rate)
        
    def get_metrics_summary(self) -> Dict[str, Any]:
        """Get summary of current metrics"""
        self._cleanup_windows()
        
        total_success = len(self._success_window)
        total_errors = len(self._error_window)
        total_assessments = total_success + total_errors
        
        return {
            "uptime_seconds": time.time() - self._start_time,
            "window_duration_minutes": self._window_duration.total_seconds() / 60,
            "total_in_window": total_assessments,
            "success_in_window": total_success,
            "errors_in_window": total_errors,
            "overall_success_rate": (
                total_success / total_assessments if total_assessments > 0 else 0
            ),
            "assessment_types": {
                atype.value: {
                    "success": len([
                        e for e in self._success_window
                        if e["assessment_type"] == atype
                    ]),
                    "errors": len([
                        e for e in self._error_window
                        if e["assessment_type"] == atype
                    ])
                }
                for atype in AssessmentType
            }
        }


# Global metrics instance
metrics = AssessmentMetrics()


# Context managers and decorators
@contextmanager
def track_assessment_duration(assessment_type: AssessmentType, industry: str = "unknown"):
    """
    Context manager to track assessment duration
    
    Usage:
        with track_assessment_duration(AssessmentType.PAGESPEED, "ecommerce"):
            # Perform assessment
            pass
    """
    start_time = time.time()
    try:
        yield
    finally:
        duration = time.time() - start_time
        metrics.track_duration(assessment_type, industry, duration)


@contextmanager
def track_processing_step(assessment_type: AssessmentType, step: str):
    """
    Context manager to track processing step duration
    
    Usage:
        with track_processing_step(AssessmentType.PAGESPEED, "fetch_html"):
            # Fetch HTML content
            pass
    """
    start_time = time.time()
    try:
        yield
    finally:
        duration = time.time() - start_time
        metrics.track_processing_step(assessment_type, step, duration)


def track_assessment(assessment_type: AssessmentType, industry: str = "unknown"):
    """
    Decorator to track assessment execution
    
    Usage:
        @track_assessment(AssessmentType.PAGESPEED, "ecommerce")
        async def assess_website(business_id, url):
            # Assessment logic
            return result
    """
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Extract business_id if available
            business_id = kwargs.get("business_id", "unknown")
            if not business_id and args:
                business_id = args[0] if isinstance(args[0], str) else "unknown"
            
            # Start tracking
            tracking_id = metrics.track_assessment_start(
                business_id, assessment_type, industry
            )
            
            start_time = time.time()
            try:
                # Execute assessment
                result = await func(*args, **kwargs)
                
                # Track completion
                duration = time.time() - start_time
                cost = getattr(result, "total_cost_usd", Decimal("0")) if result else Decimal("0")
                
                metrics.track_assessment_complete(
                    tracking_id=tracking_id,
                    business_id=business_id,
                    assessment_type=assessment_type,
                    industry=industry,
                    duration_seconds=duration,
                    cost_usd=cost,
                    status=AssessmentStatus.COMPLETED
                )
                
                return result
                
            except Exception as e:
                # Track failure
                duration = time.time() - start_time
                
                metrics.track_assessment_complete(
                    tracking_id=tracking_id,
                    business_id=business_id,
                    assessment_type=assessment_type,
                    industry=industry,
                    duration_seconds=duration,
                    cost_usd=Decimal("0"),
                    status=AssessmentStatus.FAILED
                )
                
                raise
        
        return wrapper
    return decorator


class AssessmentMetricsCollector:
    """
    Collector for exporting assessment metrics to monitoring systems
    """
    
    def __init__(self, metrics_instance: AssessmentMetrics = None):
        """Initialize collector with metrics instance"""
        self.metrics = metrics_instance or metrics
        
    def collect_prometheus_metrics(self) -> List[Dict[str, Any]]:
        """Collect metrics in Prometheus format"""
        # This would be used by Prometheus client to scrape metrics
        # The actual metrics are already exposed via prometheus_client
        return []
        
    def export_to_json(self) -> Dict[str, Any]:
        """Export metrics summary as JSON"""
        summary = self.metrics.get_metrics_summary()
        
        return {
            "timestamp": datetime.utcnow().isoformat(),
            "metrics": summary,
            "system": {
                "version": "1.0.0",
                "uptime_seconds": summary["uptime_seconds"]
            }
        }