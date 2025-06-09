"""
Core metrics collection for LeadFactory using Prometheus
"""
from typing import Dict, Any, Optional
from functools import wraps
import time
import asyncio

from prometheus_client import Counter, Histogram, Gauge, Info, Summary
from prometheus_client import CollectorRegistry, generate_latest, CONTENT_TYPE_LATEST

from core.logging import get_logger


# Create a global registry for the application
REGISTRY = CollectorRegistry()

# Application info
app_info = Info(
    'leadfactory_app',
    'LeadFactory application information',
    registry=REGISTRY
)

# Request metrics
request_count = Counter(
    'leadfactory_http_requests_total',
    'Total HTTP requests',
    ['method', 'endpoint', 'status'],
    registry=REGISTRY
)

request_duration = Histogram(
    'leadfactory_http_request_duration_seconds',
    'HTTP request duration in seconds',
    ['method', 'endpoint'],
    buckets=(0.01, 0.05, 0.1, 0.5, 1.0, 2.5, 5.0, 10.0),
    registry=REGISTRY
)

# Business processing metrics
businesses_processed = Counter(
    'leadfactory_businesses_processed_total',
    'Total number of businesses processed',
    ['source', 'status'],
    registry=REGISTRY
)

assessments_created = Counter(
    'leadfactory_assessments_created_total',
    'Total number of assessments created',
    ['assessment_type', 'status'],
    registry=REGISTRY
)

emails_sent = Counter(
    'leadfactory_emails_sent_total',
    'Total number of emails sent',
    ['campaign', 'status'],
    registry=REGISTRY
)

purchases_completed = Counter(
    'leadfactory_purchases_completed_total',
    'Total number of purchases completed',
    ['product_type', 'experiment'],
    registry=REGISTRY
)

# Performance metrics
assessment_duration = Histogram(
    'leadfactory_assessment_duration_seconds',
    'Time taken to complete an assessment',
    ['assessment_type'],
    buckets=(0.5, 1.0, 2.0, 5.0, 10.0, 30.0, 60.0),
    registry=REGISTRY
)

# Resource metrics
active_campaigns = Gauge(
    'leadfactory_active_campaigns',
    'Number of active campaigns',
    registry=REGISTRY
)

daily_quota_usage = Gauge(
    'leadfactory_daily_quota_usage',
    'Current daily quota usage',
    ['provider'],
    registry=REGISTRY
)

# Error metrics
error_count = Counter(
    'leadfactory_errors_total',
    'Total number of errors',
    ['error_type', 'domain'],
    registry=REGISTRY
)

# Revenue metrics
revenue_total = Counter(
    'leadfactory_revenue_usd_total',
    'Total revenue in USD',
    ['product_type'],
    registry=REGISTRY
)

conversion_rate = Gauge(
    'leadfactory_conversion_rate',
    'Current conversion rate',
    ['experiment', 'variant'],
    registry=REGISTRY
)

# Database metrics
db_connections_active = Gauge(
    'leadfactory_database_connections_active',
    'Number of active database connections',
    registry=REGISTRY
)

db_query_duration = Histogram(
    'leadfactory_database_query_duration_seconds',
    'Database query duration',
    ['operation', 'table'],
    buckets=(0.001, 0.005, 0.01, 0.05, 0.1, 0.5, 1.0),
    registry=REGISTRY
)

# Cache metrics
cache_hits = Counter(
    'leadfactory_cache_hits_total',
    'Total cache hits',
    ['cache_type'],
    registry=REGISTRY
)

cache_misses = Counter(
    'leadfactory_cache_misses_total',
    'Total cache misses',
    ['cache_type'],
    registry=REGISTRY
)


class MetricsCollector:
    """Helper class for collecting metrics"""

    def __init__(self):
        self.logger = get_logger("metrics")

        # Set application info
        app_info.info({
            'version': '1.0.0',
            'environment': 'production'
        })

    def track_request(self, method: str, endpoint: str, status: int, duration: float):
        """Track HTTP request metrics"""
        request_count.labels(method=method, endpoint=endpoint, status=str(status)).inc()
        request_duration.labels(method=method, endpoint=endpoint).observe(duration)

    def track_business_processed(self, source: str, status: str = "success"):
        """Track business processing"""
        businesses_processed.labels(source=source, status=status).inc()

    def track_assessment_created(self, assessment_type: str, duration: float, status: str = "success"):
        """Track assessment creation"""
        assessments_created.labels(assessment_type=assessment_type, status=status).inc()
        assessment_duration.labels(assessment_type=assessment_type).observe(duration)

    def track_email_sent(self, campaign: str, status: str = "success"):
        """Track email sending"""
        emails_sent.labels(campaign=campaign, status=status).inc()

    def track_purchase(self, product_type: str, amount: float, experiment: str = "default"):
        """Track purchase completion"""
        purchases_completed.labels(product_type=product_type, experiment=experiment).inc()
        revenue_total.labels(product_type=product_type).inc(amount)

    def track_error(self, error_type: str, domain: str):
        """Track errors"""
        error_count.labels(error_type=error_type, domain=domain).inc()

    def update_active_campaigns(self, count: int):
        """Update active campaigns gauge"""
        active_campaigns.set(count)

    def update_quota_usage(self, provider: str, usage: int):
        """Update quota usage gauge"""
        daily_quota_usage.labels(provider=provider).set(usage)

    def update_conversion_rate(self, rate: float, experiment: str = "default", variant: str = "control"):
        """Update conversion rate gauge"""
        conversion_rate.labels(experiment=experiment, variant=variant).set(rate)

    def track_database_query(self, operation: str, table: str, duration: float):
        """Track database query performance"""
        db_query_duration.labels(operation=operation, table=table).observe(duration)

    def update_db_connections(self, count: int):
        """Update active database connections"""
        db_connections_active.set(count)

    def track_cache_hit(self, cache_type: str = "redis"):
        """Track cache hit"""
        cache_hits.labels(cache_type=cache_type).inc()

    def track_cache_miss(self, cache_type: str = "redis"):
        """Track cache miss"""
        cache_misses.labels(cache_type=cache_type).inc()

    def get_metrics(self) -> bytes:
        """Get current metrics in Prometheus format"""
        return generate_latest(REGISTRY)


# Global metrics collector instance
metrics = MetricsCollector()


def track_time(metric_name: str = None):
    """Decorator to track execution time of functions"""
    def decorator(func):
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            start_time = time.time()
            try:
                result = await func(*args, **kwargs)
                return result
            finally:
                duration = time.time() - start_time
                if metric_name:
                    # Custom metric tracking
                    assessment_duration.labels(assessment_type=metric_name).observe(duration)

        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            start_time = time.time()
            try:
                result = func(*args, **kwargs)
                return result
            finally:
                duration = time.time() - start_time
                if metric_name:
                    # Custom metric tracking
                    assessment_duration.labels(assessment_type=metric_name).observe(duration)

        # Return appropriate wrapper based on function type
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper

    return decorator


def get_metrics_response() -> tuple[bytes, str]:
    """Get metrics response for Prometheus endpoint"""
    return metrics.get_metrics(), CONTENT_TYPE_LATEST


# Convenience functions for common metrics
def track_funnel_step(step: str, success: bool = True):
    """Track funnel progression"""
    status = "success" if success else "dropped"
    businesses_processed.labels(source=step, status=status).inc()


def track_api_call(provider: str, endpoint: str, success: bool = True):
    """Track external API calls"""
    # This is handled by D0 Gateway metrics, but we can aggregate here
    status = "success" if success else "failed"
    request_count.labels(method="API", endpoint=f"{provider}:{endpoint}", status=status).inc()
