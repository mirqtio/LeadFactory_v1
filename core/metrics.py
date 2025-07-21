"""
Core metrics collection for LeadFactory using Prometheus
"""
import asyncio
import time
from functools import wraps

from prometheus_client import CONTENT_TYPE_LATEST, CollectorRegistry, Counter, Gauge, Histogram, Info, generate_latest

from core.logging import get_logger

# Create a global registry for the application
REGISTRY = CollectorRegistry()

# Application info
app_info = Info("leadfactory_app", "LeadFactory application information", registry=REGISTRY)

# Request metrics
request_count = Counter(
    "leadfactory_http_requests_total",
    "Total HTTP requests",
    ["method", "endpoint", "status"],
    registry=REGISTRY,
)

request_duration = Histogram(
    "leadfactory_http_request_duration_seconds",
    "HTTP request duration in seconds",
    ["method", "endpoint"],
    buckets=(0.01, 0.05, 0.1, 0.5, 1.0, 2.5, 5.0, 10.0),
    registry=REGISTRY,
)

# Business processing metrics
businesses_processed = Counter(
    "leadfactory_businesses_processed_total",
    "Total number of businesses processed",
    ["source", "status"],
    registry=REGISTRY,
)

assessments_created = Counter(
    "leadfactory_assessments_created_total",
    "Total number of assessments created",
    ["assessment_type", "status"],
    registry=REGISTRY,
)

emails_sent = Counter(
    "leadfactory_emails_sent_total",
    "Total number of emails sent",
    ["campaign", "status"],
    registry=REGISTRY,
)

purchases_completed = Counter(
    "leadfactory_purchases_completed_total",
    "Total number of purchases completed",
    ["product_type", "experiment"],
    registry=REGISTRY,
)

# Performance metrics
assessment_duration = Histogram(
    "leadfactory_assessment_duration_seconds",
    "Time taken to complete an assessment",
    ["assessment_type"],
    buckets=(0.5, 1.0, 2.0, 5.0, 10.0, 30.0, 60.0),
    registry=REGISTRY,
)

# Resource metrics
active_campaigns = Gauge("leadfactory_active_campaigns", "Number of active campaigns", registry=REGISTRY)

daily_quota_usage = Gauge(
    "leadfactory_daily_quota_usage",
    "Current daily quota usage",
    ["provider"],
    registry=REGISTRY,
)

# Error metrics
error_count = Counter(
    "leadfactory_errors_total",
    "Total number of errors",
    ["error_type", "domain"],
    registry=REGISTRY,
)

# Revenue metrics
revenue_total = Counter(
    "leadfactory_revenue_usd_total",
    "Total revenue in USD",
    ["product_type"],
    registry=REGISTRY,
)

conversion_rate = Gauge(
    "leadfactory_conversion_rate",
    "Current conversion rate",
    ["experiment", "variant"],
    registry=REGISTRY,
)

# Database metrics
db_connections_active = Gauge(
    "leadfactory_database_connections_active",
    "Number of active database connections",
    registry=REGISTRY,
)

db_query_duration = Histogram(
    "leadfactory_database_query_duration_seconds",
    "Database query duration",
    ["operation", "table"],
    buckets=(0.001, 0.005, 0.01, 0.05, 0.1, 0.5, 1.0),
    registry=REGISTRY,
)

# Cache metrics
cache_hits = Counter(
    "leadfactory_cache_hits_total",
    "Total cache hits",
    ["cache_type"],
    registry=REGISTRY,
)

cache_misses = Counter(
    "leadfactory_cache_misses_total",
    "Total cache misses",
    ["cache_type"],
    registry=REGISTRY,
)

# Pipeline metrics
pipeline_runs = Counter(
    "leadfactory_pipeline_runs_total",
    "Total pipeline runs",
    ["pipeline_name", "status"],
    registry=REGISTRY,
)

pipeline_duration = Histogram(
    "leadfactory_pipeline_duration_seconds",
    "Pipeline execution duration",
    ["pipeline_name"],
    buckets=(1.0, 5.0, 10.0, 30.0, 60.0, 180.0, 300.0, 600.0),
    registry=REGISTRY,
)

# Humanloop/Prompt metrics
prompt_requests = Counter(
    "leadfactory_prompt_requests_total",
    "Total prompt/LLM requests",
    ["prompt_slug", "model", "status"],
    registry=REGISTRY,
)

prompt_duration = Histogram(
    "leadfactory_prompt_duration_seconds",
    "Prompt execution duration",
    ["prompt_slug", "model"],
    buckets=(0.1, 0.5, 1.0, 2.0, 5.0, 10.0, 30.0),
    registry=REGISTRY,
)

prompt_tokens_used = Counter(
    "leadfactory_prompt_tokens_total",
    "Total tokens used by prompts",
    ["prompt_slug", "model", "token_type"],
    registry=REGISTRY,
)

prompt_cost_usd = Counter(
    "leadfactory_prompt_cost_usd_total",
    "Total cost of prompt executions in USD",
    ["prompt_slug", "model"],
    registry=REGISTRY,
)

config_reload_total = Counter(
    "leadfactory_config_reload_total",
    "Total configuration reloads",
    ["config_type", "status"],
    registry=REGISTRY,
)

config_reload_duration = Histogram(
    "leadfactory_config_reload_duration_seconds",
    "Configuration reload duration",
    ["config_type"],
    buckets=(0.001, 0.01, 0.05, 0.1, 0.5, 1.0),
    registry=REGISTRY,
)


class MetricsCollector:
    """Helper class for collecting metrics"""

    def __init__(self):
        self.logger = get_logger("metrics")

        # Set application info
        app_info.info({"version": "1.0.0", "environment": "production"})

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

    def track_prompt_request(
        self,
        prompt_slug: str,
        model: str,
        duration: float,
        tokens_input: int,
        tokens_output: int,
        cost: float,
        status: str = "success",
    ):
        """Track Humanloop prompt request metrics"""
        # Track request count
        prompt_requests.labels(prompt_slug=prompt_slug, model=model, status=status).inc()

        # Track duration
        prompt_duration.labels(prompt_slug=prompt_slug, model=model).observe(duration)

        # Track token usage
        prompt_tokens_used.labels(prompt_slug=prompt_slug, model=model, token_type="input").inc(tokens_input)
        prompt_tokens_used.labels(prompt_slug=prompt_slug, model=model, token_type="output").inc(tokens_output)

        # Track cost
        prompt_cost_usd.labels(prompt_slug=prompt_slug, model=model).inc(cost)

    def track_config_reload(self, config_type: str, duration: float, status: str = "success"):
        """Track configuration reload metrics"""
        config_reload_total.labels(config_type=config_type, status=status).inc()
        config_reload_duration.labels(config_type=config_type).observe(duration)

    def increment_counter(self, metric_name: str, amount: int = 1):
        """Generic method to increment counters by metric name"""
        # Map metric names to specific counter metrics
        if metric_name == "targeting_universes_created":
            businesses_processed.labels(source="targeting", status="universe_created").inc(amount)
        elif metric_name == "targeting_universes_updated":
            businesses_processed.labels(source="targeting", status="universe_updated").inc(amount)
        elif metric_name == "targeting_universes_deleted":
            businesses_processed.labels(source="targeting", status="universe_deleted").inc(amount)
        elif metric_name == "targeting_campaigns_created":
            businesses_processed.labels(source="targeting", status="campaign_created").inc(amount)
        elif metric_name == "targeting_campaigns_updated":
            businesses_processed.labels(source="targeting", status="campaign_updated").inc(amount)
        elif metric_name == "targeting_batches_created":
            businesses_processed.labels(source="targeting", status="batch_created").inc(amount)
        elif metric_name == "targeting_batches_updated":
            businesses_processed.labels(source="targeting", status="batch_updated").inc(amount)
        elif metric_name == "targeting_boundaries_created":
            businesses_processed.labels(source="targeting", status="boundary_created").inc(amount)
        else:
            # Default to generic business processing metric
            businesses_processed.labels(source="generic", status=metric_name).inc(amount)

    async def record_pipeline_event(self, pipeline_name: str, event_type: str, run_id: str = None, **kwargs):
        """Record pipeline event for metrics"""
        # Track pipeline run status changes
        if event_type in ["started", "completed", "failed"]:
            pipeline_runs.labels(pipeline_name=pipeline_name, status=event_type).inc()

        # Track duration for completed runs
        if event_type == "completed" and "duration" in kwargs:
            pipeline_duration.labels(pipeline_name=pipeline_name).observe(kwargs["duration"])

        self.logger.info(
            f"Pipeline event recorded: {pipeline_name} - {event_type}",
            extra={
                "pipeline_name": pipeline_name,
                "event_type": event_type,
                "run_id": run_id,
                **kwargs,
            },
        )

    async def record_task_execution(self, task_name: str, status: str, duration: float = None, **kwargs):
        """Record task execution metrics"""
        # Track task execution
        businesses_processed.labels(source=task_name, status=status).inc()

        # Track duration if provided
        if duration:
            assessment_duration.labels(assessment_type=task_name).observe(duration)

        self.logger.info(
            f"Task execution recorded: {task_name} - {status}",
            extra={
                "task_name": task_name,
                "status": status,
                "duration": duration,
                **kwargs,
            },
        )

    def get_metrics(self) -> bytes:
        """Get current metrics in Prometheus format"""
        return generate_latest(REGISTRY)


# Global metrics collector instance
metrics = MetricsCollector()


def get_metrics_collector() -> MetricsCollector:
    """Get the global metrics collector instance"""
    return metrics


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
