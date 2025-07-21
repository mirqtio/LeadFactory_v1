"""
Cost ledger utilities for tracking and aggregating API costs
P1-050: Gateway Cost Ledger implementation
"""

from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Any

from sqlalchemy import and_, func

from core.config import get_settings
from core.logging import get_logger
from database.models import APICost, DailyCostAggregate
from database.session import get_db_sync

logger = get_logger("gateway.cost_ledger", domain="d0")


class CostLedger:
    """
    Centralized cost tracking and aggregation for all gateway API calls
    """

    def __init__(self):
        self.logger = logger
        self.settings = get_settings()

    def record_cost(
        self,
        provider: str,
        operation: str,
        cost_usd: Decimal,
        lead_id: int | None = None,
        campaign_id: int | None = None,
        request_id: str | None = None,
        metadata: dict | None = None,
    ) -> APICost | None:
        """
        Record a single API cost entry

        Args:
            provider: API provider name (e.g., 'dataaxle', 'hunter')
            operation: Operation performed (e.g., 'match_business', 'find_email')
            cost_usd: Cost in USD
            lead_id: Associated lead ID if applicable
            campaign_id: Associated campaign ID if applicable
            request_id: Provider's request ID for correlation
            metadata: Additional context data

        Returns:
            Created APICost record
        """
        # Check if cost tracking is enabled
        if not self.settings.enable_cost_tracking:
            self.logger.debug("Cost tracking disabled, skipping cost recording")
            return None

        with get_db_sync() as db:
            cost_record = APICost(
                provider=provider,
                operation=operation,
                cost_usd=cost_usd,
                lead_id=lead_id,
                campaign_id=campaign_id,
                request_id=request_id,
                meta_data=metadata or {},
            )
            db.add(cost_record)
            db.commit()
            db.refresh(cost_record)

            self.logger.info(
                f"Cost recorded: ${cost_usd:.4f} for {provider}/{operation} "
                f"(lead_id={lead_id}, campaign_id={campaign_id})"
            )

            return cost_record

    def get_provider_costs(
        self,
        provider: str,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
    ) -> dict[str, Any]:
        """
        Get aggregated costs for a specific provider

        Args:
            provider: Provider name
            start_date: Start of date range (default: 30 days ago)
            end_date: End of date range (default: now)

        Returns:
            Dict with total_cost, request_count, and breakdown by operation
        """
        if not start_date:
            start_date = datetime.now() - timedelta(days=30)
        if not end_date:
            end_date = datetime.now()

        with get_db_sync() as db:
            # Get total costs and counts
            results = (
                db.query(
                    APICost.operation,
                    func.sum(APICost.cost_usd).label("total_cost"),
                    func.count(APICost.id).label("request_count"),
                )
                .filter(
                    and_(
                        APICost.provider == provider,
                        APICost.timestamp >= start_date,
                        APICost.timestamp <= end_date,
                    )
                )
                .group_by(APICost.operation)
                .all()
            )

            # Calculate totals
            total_cost = Decimal("0.00")
            total_requests = 0
            operations = {}

            for operation, cost, count in results:
                total_cost += cost or Decimal("0.00")
                total_requests += count
                operations[operation] = {
                    "cost": float(cost or 0),
                    "count": count,
                    "avg_cost": float((cost or 0) / count) if count > 0 else 0,
                }

            return {
                "provider": provider,
                "period": {
                    "start": start_date.isoformat(),
                    "end": end_date.isoformat(),
                },
                "total_cost": float(total_cost),
                "total_requests": total_requests,
                "operations": operations,
            }

    def get_campaign_costs(self, campaign_id: int) -> dict[str, Any]:
        """
        Get total costs for a specific campaign

        Args:
            campaign_id: Campaign ID

        Returns:
            Dict with cost breakdown by provider and operation
        """
        with get_db_sync() as db:
            results = (
                db.query(
                    APICost.provider,
                    APICost.operation,
                    func.sum(APICost.cost_usd).label("total_cost"),
                    func.count(APICost.id).label("request_count"),
                )
                .filter(APICost.campaign_id == campaign_id)
                .group_by(APICost.provider, APICost.operation)
                .all()
            )

            # Organize by provider
            providers = {}
            total_cost = Decimal("0.00")

            for provider, operation, cost, count in results:
                if provider not in providers:
                    providers[provider] = {
                        "total_cost": 0.0,
                        "operations": {},
                    }

                providers[provider]["operations"][operation] = {
                    "cost": float(cost or 0),
                    "count": count,
                }
                providers[provider]["total_cost"] += float(cost or 0)
                total_cost += cost or Decimal("0.00")

            return {
                "campaign_id": campaign_id,
                "total_cost": float(total_cost),
                "providers": providers,
            }

    def aggregate_daily_costs(self, target_date: date | None = None) -> list[DailyCostAggregate]:
        """
        Aggregate costs for a specific day into DailyCostAggregate records

        Args:
            target_date: Date to aggregate (default: yesterday)

        Returns:
            List of created DailyCostAggregate records
        """
        if not target_date:
            target_date = (datetime.now() - timedelta(days=1)).date()

        start_time = datetime.combine(target_date, datetime.min.time())
        end_time = datetime.combine(target_date, datetime.max.time())

        with get_db_sync() as db:
            # Get aggregated data
            results = (
                db.query(
                    APICost.provider,
                    APICost.operation,
                    APICost.campaign_id,
                    func.sum(APICost.cost_usd).label("total_cost"),
                    func.count(APICost.id).label("request_count"),
                )
                .filter(
                    and_(
                        APICost.timestamp >= start_time,
                        APICost.timestamp <= end_time,
                    )
                )
                .group_by(APICost.provider, APICost.operation, APICost.campaign_id)
                .all()
            )

            # Create or update aggregate records
            aggregates = []
            for provider, operation, campaign_id, total_cost, request_count in results:
                # Check if aggregate already exists
                existing = (
                    db.query(DailyCostAggregate)
                    .filter(
                        and_(
                            DailyCostAggregate.date == target_date,
                            DailyCostAggregate.provider == provider,
                            DailyCostAggregate.operation == operation,
                            DailyCostAggregate.campaign_id == campaign_id,
                        )
                    )
                    .first()
                )

                if existing:
                    # Update existing record
                    existing.total_cost_usd = total_cost
                    existing.request_count = request_count
                    existing.updated_at = datetime.now()
                    aggregates.append(existing)
                else:
                    # Create new record
                    aggregate = DailyCostAggregate(
                        date=target_date,
                        provider=provider,
                        operation=operation,
                        campaign_id=campaign_id,
                        total_cost_usd=total_cost,
                        request_count=request_count,
                    )
                    db.add(aggregate)
                    aggregates.append(aggregate)

            db.commit()

            self.logger.info(f"Aggregated {len(aggregates)} cost records for {target_date}")

            return aggregates

    def get_daily_costs(
        self,
        start_date: date,
        end_date: date | None = None,
        provider: str | None = None,
        campaign_id: int | None = None,
    ) -> list[dict]:
        """
        Get daily cost aggregates with optional filtering

        Args:
            start_date: Start date
            end_date: End date (default: today)
            provider: Filter by provider
            campaign_id: Filter by campaign

        Returns:
            List of daily cost records
        """
        if not end_date:
            end_date = date.today()

        with get_db_sync() as db:
            query = db.query(DailyCostAggregate).filter(
                and_(
                    DailyCostAggregate.date >= start_date,
                    DailyCostAggregate.date <= end_date,
                )
            )

            if provider:
                query = query.filter(DailyCostAggregate.provider == provider)
            if campaign_id:
                query = query.filter(DailyCostAggregate.campaign_id == campaign_id)

            results = query.order_by(DailyCostAggregate.date.desc()).all()

            return [
                {
                    "date": r.date.isoformat(),
                    "provider": r.provider,
                    "operation": r.operation,
                    "campaign_id": r.campaign_id,
                    "total_cost": float(r.total_cost_usd),
                    "request_count": r.request_count,
                    "avg_cost": float(r.total_cost_usd / r.request_count) if r.request_count > 0 else 0,
                }
                for r in results
            ]

    def cleanup_old_records(self, days_to_keep: int = 90) -> int:
        """
        Clean up old API cost records (keep aggregates)

        Args:
            days_to_keep: Number of days of records to keep

        Returns:
            Number of records deleted
        """
        cutoff_date = datetime.now() - timedelta(days=days_to_keep)

        with get_db_sync() as db:
            # Count records to delete
            count = db.query(APICost).filter(APICost.timestamp < cutoff_date).count()

            # Delete old records
            if count > 0:
                db.query(APICost).filter(APICost.timestamp < cutoff_date).delete()
                db.commit()

                self.logger.info(f"Cleaned up {count} old cost records")

            return count


# Singleton instance
cost_ledger = CostLedger()


# Convenience functions
def record_api_cost(provider: str, operation: str, cost_usd: float, **kwargs) -> APICost:
    """
    Record an API cost entry

    Args:
        provider: API provider name
        operation: Operation performed
        cost_usd: Cost in USD
        **kwargs: Additional fields (lead_id, campaign_id, etc.)

    Returns:
        Created APICost record
    """
    return cost_ledger.record_cost(provider=provider, operation=operation, cost_usd=Decimal(str(cost_usd)), **kwargs)


def get_provider_costs(provider: str, days: int = 30) -> dict:
    """
    Get cost summary for a provider over the last N days

    Args:
        provider: Provider name
        days: Number of days to look back

    Returns:
        Cost summary dict
    """
    start_date = datetime.now() - timedelta(days=days)
    return cost_ledger.get_provider_costs(provider, start_date=start_date)


def get_campaign_costs(campaign_id: int) -> dict:
    """
    Get total costs for a campaign

    Args:
        campaign_id: Campaign ID

    Returns:
        Cost breakdown dict
    """
    return cost_ledger.get_campaign_costs(campaign_id)
