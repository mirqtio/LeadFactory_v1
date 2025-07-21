"""
Queue Monitoring and Health Metrics System.

Provides real-time health visibility, performance metrics, alerting thresholds,
queue health dashboards, and integration with existing core/metrics.py and
d0_gateway/alerts.py systems for comprehensive monitoring.
"""

import asyncio
import time
from datetime import datetime, timedelta
from typing import Any

from pydantic import BaseModel, Field

from core.logging import get_logger
from core.metrics import get_metrics_collector
from infra.redis_queue import QueueStats, RedisQueueBroker


class QueueHealthStatus(BaseModel):
    """Queue health status with thresholds"""

    queue_name: str
    status: str  # 'healthy', 'warning', 'critical', 'unknown'
    pending_count: int
    inflight_count: int
    dlq_count: int
    processing_rate: float  # messages per minute
    avg_processing_time: float  # seconds
    error_rate: float  # percentage
    last_activity: datetime | None = None
    health_score: float = Field(ge=0.0, le=1.0)  # 0.0 = critical, 1.0 = perfect


class QueueAlertThresholds(BaseModel):
    """Configurable alert thresholds for queue monitoring"""

    queue_name: str

    # Queue depth thresholds
    pending_warning_threshold: int = Field(default=100)
    pending_critical_threshold: int = Field(default=500)

    # Processing rate thresholds (messages per minute)
    min_processing_rate_warning: float = Field(default=10.0)
    min_processing_rate_critical: float = Field(default=1.0)

    # Error rate thresholds (percentage)
    error_rate_warning: float = Field(default=5.0)
    error_rate_critical: float = Field(default=15.0)

    # Processing time thresholds (seconds)
    avg_processing_time_warning: float = Field(default=30.0)
    avg_processing_time_critical: float = Field(default=120.0)

    # DLQ thresholds
    dlq_warning_threshold: int = Field(default=10)
    dlq_critical_threshold: int = Field(default=50)

    # Activity timeout (minutes)
    activity_timeout_warning: int = Field(default=10)
    activity_timeout_critical: int = Field(default=30)


class QueueMetrics(BaseModel):
    """Detailed queue metrics for analysis"""

    queue_name: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)

    # Current state
    pending_count: int
    inflight_count: int
    dlq_count: int

    # Performance metrics
    enqueued_total: int
    processed_total: int
    failed_total: int
    processing_rate_1min: float
    processing_rate_5min: float
    processing_rate_15min: float

    # Timing metrics
    avg_processing_time: float
    min_processing_time: float
    max_processing_time: float
    p95_processing_time: float

    # Error metrics
    error_rate: float
    timeout_count: int
    retry_count: int


class QueueMonitor:
    """
    Queue monitoring system with health tracking and alerting.

    Features:
    - Real-time queue health monitoring
    - Configurable alert thresholds
    - Performance metrics collection
    - Integration with core metrics and alerts
    - Health dashboards and reporting
    """

    def __init__(self, broker: RedisQueueBroker):
        """
        Initialize queue monitor.

        Args:
            broker: Redis queue broker instance
        """
        self.broker = broker
        self.logger = get_logger("queue_monitor", domain="infra")

        # Metrics integration
        self.metrics_collector = get_metrics_collector()

        # Alert thresholds by queue
        self.alert_thresholds: dict[str, QueueAlertThresholds] = {}

        # Historical metrics storage (in-memory for now, could be moved to Redis)
        self.metrics_history: dict[str, list[QueueMetrics]] = {}
        self.max_history_size = 1440  # 24 hours at 1-minute intervals

        # Processing time tracking
        self.processing_times: dict[str, list[float]] = {}
        self.max_processing_times = 100  # Keep last 100 processing times

        self.logger.info("Queue monitor initialized")

    def set_alert_thresholds(self, queue_name: str, thresholds: QueueAlertThresholds):
        """Set alert thresholds for a queue"""
        self.alert_thresholds[queue_name] = thresholds
        self.logger.info(f"Set alert thresholds for queue {queue_name}")

    def get_alert_thresholds(self, queue_name: str) -> QueueAlertThresholds:
        """Get alert thresholds for a queue (with defaults)"""
        return self.alert_thresholds.get(queue_name, QueueAlertThresholds(queue_name=queue_name))

    async def collect_queue_metrics(self, queue_name: str) -> QueueMetrics:
        """Collect comprehensive metrics for a queue"""
        try:
            # Get basic queue stats
            stats = self.broker.get_queue_stats(queue_name)

            # Calculate processing rates
            processing_rates = await self._calculate_processing_rates(queue_name)

            # Calculate timing metrics
            timing_metrics = self._calculate_timing_metrics(queue_name)

            # Calculate error rate
            error_rate = self._calculate_error_rate(stats)

            # Get additional counts
            timeout_count = await self._get_timeout_count(queue_name)
            retry_count = await self._get_retry_count(queue_name)

            metrics = QueueMetrics(
                queue_name=queue_name,
                pending_count=stats.pending_count,
                inflight_count=stats.inflight_count,
                dlq_count=stats.dlq_count,
                enqueued_total=await self._get_total_enqueued(queue_name),
                processed_total=stats.processed_total,
                failed_total=stats.failed_total,
                processing_rate_1min=processing_rates["1min"],
                processing_rate_5min=processing_rates["5min"],
                processing_rate_15min=processing_rates["15min"],
                avg_processing_time=timing_metrics["avg"],
                min_processing_time=timing_metrics["min"],
                max_processing_time=timing_metrics["max"],
                p95_processing_time=timing_metrics["p95"],
                error_rate=error_rate,
                timeout_count=timeout_count,
                retry_count=retry_count,
            )

            # Store in history
            self._store_metrics_history(queue_name, metrics)

            # Send metrics to core metrics system
            await self._send_metrics_to_core(metrics)

            return metrics

        except Exception as e:
            self.logger.error(f"Failed to collect metrics for queue {queue_name}: {e}")
            raise

    async def _calculate_processing_rates(self, queue_name: str) -> dict[str, float]:
        """Calculate processing rates for different time windows"""
        current_time = time.time()
        rates = {"1min": 0.0, "5min": 0.0, "15min": 0.0}

        # Get processing timestamps from Redis
        processing_key = f"queue_processing_times:{queue_name}"

        try:
            # Get recent processing timestamps
            timestamps = await self.broker.redis.zrangebyscore(
                processing_key,
                current_time - 900,
                current_time,  # Last 15 minutes
            )

            if timestamps:
                timestamps = [float(ts) for ts in timestamps]

                # Calculate rates for different windows
                rates["1min"] = len([ts for ts in timestamps if ts > current_time - 60])
                rates["5min"] = len([ts for ts in timestamps if ts > current_time - 300]) / 5
                rates["15min"] = len([ts for ts in timestamps if ts > current_time - 900]) / 15

        except Exception as e:
            self.logger.error(f"Error calculating processing rates: {e}")

        return rates

    def _calculate_timing_metrics(self, queue_name: str) -> dict[str, float]:
        """Calculate timing metrics from recent processing times"""
        processing_times = self.processing_times.get(queue_name, [])

        if not processing_times:
            return {"avg": 0.0, "min": 0.0, "max": 0.0, "p95": 0.0}

        sorted_times = sorted(processing_times)

        return {
            "avg": sum(sorted_times) / len(sorted_times),
            "min": sorted_times[0],
            "max": sorted_times[-1],
            "p95": sorted_times[int(len(sorted_times) * 0.95)] if len(sorted_times) > 0 else 0.0,
        }

    def _calculate_error_rate(self, stats: QueueStats) -> float:
        """Calculate error rate as percentage"""
        total_processed = stats.processed_total + stats.failed_total

        if total_processed == 0:
            return 0.0

        return (stats.failed_total / total_processed) * 100.0

    async def _get_timeout_count(self, queue_name: str) -> int:
        """Get timeout count from DLQ statistics"""
        try:
            timeout_key = f"dlq_stats:{queue_name}:timeout"
            count = await self.broker.redis.get(timeout_key)
            return int(count) if count else 0
        except Exception:
            return 0

    async def _get_retry_count(self, queue_name: str) -> int:
        """Get retry count from statistics"""
        try:
            retry_key = f"queue_stats:{queue_name}:retried"
            count = await self.broker.redis.get(retry_key)
            return int(count) if count else 0
        except Exception:
            return 0

    async def _get_total_enqueued(self, queue_name: str) -> int:
        """Get total enqueued count"""
        try:
            enqueued_key = f"queue_stats:{queue_name}:enqueued"
            count = await self.broker.redis.get(enqueued_key)
            return int(count) if count else 0
        except Exception:
            return 0

    def _store_metrics_history(self, queue_name: str, metrics: QueueMetrics):
        """Store metrics in history for trend analysis"""
        if queue_name not in self.metrics_history:
            self.metrics_history[queue_name] = []

        history = self.metrics_history[queue_name]
        history.append(metrics)

        # Trim history to max size
        if len(history) > self.max_history_size:
            history.pop(0)

    async def _send_metrics_to_core(self, metrics: QueueMetrics):
        """Send metrics to core metrics system"""
        try:
            # Send queue depth metrics
            self.metrics_collector.gauge(
                "queue_pending_count", metrics.pending_count, tags={"queue": metrics.queue_name}
            )

            self.metrics_collector.gauge(
                "queue_inflight_count", metrics.inflight_count, tags={"queue": metrics.queue_name}
            )

            self.metrics_collector.gauge("queue_dlq_count", metrics.dlq_count, tags={"queue": metrics.queue_name})

            # Send processing metrics
            self.metrics_collector.gauge(
                "queue_processing_rate_1min", metrics.processing_rate_1min, tags={"queue": metrics.queue_name}
            )

            self.metrics_collector.gauge(
                "queue_avg_processing_time", metrics.avg_processing_time, tags={"queue": metrics.queue_name}
            )

            # Send error metrics
            self.metrics_collector.gauge("queue_error_rate", metrics.error_rate, tags={"queue": metrics.queue_name})

        except Exception as e:
            self.logger.error(f"Failed to send metrics to core system: {e}")

    async def assess_queue_health(self, queue_name: str) -> QueueHealthStatus:
        """Assess overall health of a queue"""
        try:
            metrics = await self.collect_queue_metrics(queue_name)
            thresholds = self.get_alert_thresholds(queue_name)

            # Calculate health score and status
            health_score, status = self._calculate_health_score(metrics, thresholds)

            # Check last activity
            last_activity = await self._get_last_activity(queue_name)

            health_status = QueueHealthStatus(
                queue_name=queue_name,
                status=status,
                pending_count=metrics.pending_count,
                inflight_count=metrics.inflight_count,
                dlq_count=metrics.dlq_count,
                processing_rate=metrics.processing_rate_1min,
                avg_processing_time=metrics.avg_processing_time,
                error_rate=metrics.error_rate,
                last_activity=last_activity,
                health_score=health_score,
            )

            # Send alerts if necessary
            await self._check_and_send_alerts(health_status, thresholds)

            return health_status

        except Exception as e:
            self.logger.error(f"Failed to assess health for queue {queue_name}: {e}")

            return QueueHealthStatus(
                queue_name=queue_name,
                status="unknown",
                pending_count=0,
                inflight_count=0,
                dlq_count=0,
                processing_rate=0.0,
                avg_processing_time=0.0,
                error_rate=0.0,
                health_score=0.0,
            )

    def _calculate_health_score(self, metrics: QueueMetrics, thresholds: QueueAlertThresholds) -> tuple[float, str]:
        """Calculate health score and status"""
        score = 1.0  # Start with perfect score
        status = "healthy"

        # Pending count impact
        if metrics.pending_count > thresholds.pending_critical_threshold:
            score *= 0.3
            status = "critical"
        elif metrics.pending_count > thresholds.pending_warning_threshold:
            score *= 0.7
            if status == "healthy":
                status = "warning"

        # Processing rate impact
        if metrics.processing_rate_1min < thresholds.min_processing_rate_critical:
            score *= 0.4
            status = "critical"
        elif metrics.processing_rate_1min < thresholds.min_processing_rate_warning:
            score *= 0.8
            if status == "healthy":
                status = "warning"

        # Error rate impact
        if metrics.error_rate > thresholds.error_rate_critical:
            score *= 0.2
            status = "critical"
        elif metrics.error_rate > thresholds.error_rate_warning:
            score *= 0.6
            if status == "healthy":
                status = "warning"

        # Processing time impact
        if metrics.avg_processing_time > thresholds.avg_processing_time_critical:
            score *= 0.5
            status = "critical"
        elif metrics.avg_processing_time > thresholds.avg_processing_time_warning:
            score *= 0.8
            if status == "healthy":
                status = "warning"

        # DLQ impact
        if metrics.dlq_count > thresholds.dlq_critical_threshold:
            score *= 0.4
            status = "critical"
        elif metrics.dlq_count > thresholds.dlq_warning_threshold:
            score *= 0.7
            if status == "healthy":
                status = "warning"

        return max(0.0, score), status

    async def _get_last_activity(self, queue_name: str) -> datetime | None:
        """Get last activity timestamp for queue"""
        try:
            activity_key = f"queue_stats:{queue_name}:last_activity"
            timestamp_str = await self.broker.redis.get(activity_key)

            if timestamp_str:
                return datetime.fromisoformat(timestamp_str)
            return None

        except Exception:
            return None

    async def _check_and_send_alerts(self, health_status: QueueHealthStatus, thresholds: QueueAlertThresholds):
        """Check health status and send alerts if needed"""
        try:
            if health_status.status in ["warning", "critical"]:
                # Import alerts system

                # Create alert data
                alert_data = {
                    "queue_name": health_status.queue_name,
                    "status": health_status.status,
                    "health_score": health_status.health_score,
                    "pending_count": health_status.pending_count,
                    "error_rate": health_status.error_rate,
                    "processing_rate": health_status.processing_rate,
                    "timestamp": datetime.utcnow().isoformat(),
                }

                # Send alert (adapt to existing alert system)
                self.logger.warning(f"Queue health alert: {health_status.queue_name} is {health_status.status}")

                # TODO: Integrate with existing alert system once structure is clarified

        except Exception as e:
            self.logger.error(f"Failed to send queue health alert: {e}")

    def record_processing_time(self, queue_name: str, processing_time: float):
        """Record processing time for a message"""
        if queue_name not in self.processing_times:
            self.processing_times[queue_name] = []

        times = self.processing_times[queue_name]
        times.append(processing_time)

        # Trim to max size
        if len(times) > self.max_processing_times:
            times.pop(0)

        # Also record timestamp for rate calculation
        asyncio.create_task(self._record_processing_timestamp(queue_name))

    async def _record_processing_timestamp(self, queue_name: str):
        """Record processing timestamp for rate calculation"""
        try:
            processing_key = f"queue_processing_times:{queue_name}"
            current_time = time.time()

            # Add current timestamp
            await self.broker.redis.zadd(processing_key, {str(current_time): current_time})

            # Clean up old timestamps (older than 15 minutes)
            await self.broker.redis.zremrangebyscore(processing_key, "-inf", current_time - 900)

        except Exception as e:
            self.logger.error(f"Failed to record processing timestamp: {e}")

    async def get_queue_dashboard_data(self, queue_names: list[str]) -> dict[str, Any]:
        """Get dashboard data for multiple queues"""
        dashboard_data = {
            "timestamp": datetime.utcnow().isoformat(),
            "queues": {},
            "overall_health": "healthy",
            "total_pending": 0,
            "total_inflight": 0,
            "total_dlq": 0,
        }

        critical_count = 0
        warning_count = 0

        for queue_name in queue_names:
            try:
                health_status = await self.assess_queue_health(queue_name)

                dashboard_data["queues"][queue_name] = {
                    "status": health_status.status,
                    "health_score": health_status.health_score,
                    "pending_count": health_status.pending_count,
                    "inflight_count": health_status.inflight_count,
                    "dlq_count": health_status.dlq_count,
                    "processing_rate": health_status.processing_rate,
                    "error_rate": health_status.error_rate,
                    "avg_processing_time": health_status.avg_processing_time,
                }

                # Aggregate totals
                dashboard_data["total_pending"] += health_status.pending_count
                dashboard_data["total_inflight"] += health_status.inflight_count
                dashboard_data["total_dlq"] += health_status.dlq_count

                # Track status distribution
                if health_status.status == "critical":
                    critical_count += 1
                elif health_status.status == "warning":
                    warning_count += 1

            except Exception as e:
                self.logger.error(f"Failed to get dashboard data for queue {queue_name}: {e}")
                dashboard_data["queues"][queue_name] = {"status": "unknown"}

        # Determine overall health
        if critical_count > 0:
            dashboard_data["overall_health"] = "critical"
        elif warning_count > 0:
            dashboard_data["overall_health"] = "warning"

        dashboard_data["status_summary"] = {
            "critical": critical_count,
            "warning": warning_count,
            "healthy": len(queue_names) - critical_count - warning_count,
        }

        return dashboard_data

    async def get_queue_trends(self, queue_name: str, hours: int = 24) -> dict[str, list[tuple[datetime, float]]]:
        """Get trend data for a queue over specified time period"""
        trends = {"pending_count": [], "processing_rate": [], "error_rate": [], "health_score": []}

        history = self.metrics_history.get(queue_name, [])
        cutoff_time = datetime.utcnow() - timedelta(hours=hours)

        for metrics in history:
            if metrics.timestamp >= cutoff_time:
                trends["pending_count"].append((metrics.timestamp, metrics.pending_count))
                trends["processing_rate"].append((metrics.timestamp, metrics.processing_rate_1min))
                trends["error_rate"].append((metrics.timestamp, metrics.error_rate))

                # Calculate health score for this point
                thresholds = self.get_alert_thresholds(queue_name)
                health_score, _ = self._calculate_health_score(metrics, thresholds)
                trends["health_score"].append((metrics.timestamp, health_score))

        return trends


# Global monitor instance (lazy initialization)
_monitor_instance: QueueMonitor | None = None


def get_queue_monitor(broker: RedisQueueBroker | None = None) -> QueueMonitor:
    """Get global queue monitor instance"""
    global _monitor_instance
    if _monitor_instance is None:
        from infra.redis_queue import get_queue_broker

        _monitor_instance = QueueMonitor(broker or get_queue_broker())
    return _monitor_instance


def reset_queue_monitor():
    """Reset global monitor instance (mainly for testing)"""
    global _monitor_instance
    _monitor_instance = None
