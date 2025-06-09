"""
Target Universe Manager for managing CRUD operations, geo conflicts, priority scoring, and freshness tracking
"""
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime, timedelta
from decimal import Decimal
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, func, desc, asc
import uuid

from core.logging import get_logger
from core.config import get_settings
from database.session import SessionLocal
from .models import TargetUniverse, Campaign, CampaignTarget, GeographicBoundary
from .types import (
    VerticalMarket, GeographyLevel, TargetingCriteria,
    GeographicConstraint, TargetMetrics, QualificationRules
)
from .geo_validator import GeoValidator


class TargetUniverseManager:
    """
    Manager for target universe operations with CRUD, geo conflict detection,
    priority scoring, and freshness tracking
    """

    def __init__(self, session: Optional[Session] = None):
        self.logger = get_logger("target_universe", domain="d1")
        self.session = session or SessionLocal()
        self.settings = get_settings()
        self.geo_validator = GeoValidator()

    # CRUD Operations

    def create_universe(
        self,
        name: str,
        description: Optional[str],
        verticals: List[VerticalMarket],
        geography_config: Dict[str, Any],
        qualification_rules: Optional[QualificationRules] = None,
        created_by: Optional[str] = None
    ) -> TargetUniverse:
        """
        Create a new target universe with validation

        Args:
            name: Universe name
            description: Optional description
            verticals: List of target verticals
            geography_config: Geographic constraints
            qualification_rules: Auto-qualification rules
            created_by: Creator identifier

        Returns:
            Created TargetUniverse instance

        Raises:
            ValueError: If validation fails
        """
        try:
            # Validate geography configuration
            geo_conflicts = self.geo_validator.detect_conflicts(geography_config)
            if geo_conflicts:
                self.logger.warning(f"Geography conflicts detected for universe '{name}': {geo_conflicts}")

            # Validate verticals
            validated_verticals = [VerticalMarket(v) for v in verticals]

            # Create universe
            universe = TargetUniverse(
                id=str(uuid.uuid4()),
                name=name,
                description=description,
                verticals=[v.value for v in validated_verticals],
                geography_config=geography_config,
                qualification_rules=qualification_rules.dict() if qualification_rules else None,
                created_by=created_by,
                estimated_size=self._estimate_universe_size(validated_verticals, geography_config)
            )

            self.session.add(universe)
            self.session.commit()

            self.logger.info(f"Created target universe: {universe.id} ({name})")
            return universe

        except Exception as e:
            self.session.rollback()
            self.logger.error(f"Failed to create target universe '{name}': {e}")
            raise

    def get_universe(self, universe_id: str) -> Optional[TargetUniverse]:
        """Get target universe by ID"""
        return self.session.query(TargetUniverse).filter_by(id=universe_id).first()

    def list_universes(
        self,
        active_only: bool = True,
        limit: int = 100,
        offset: int = 0
    ) -> List[TargetUniverse]:
        """
        List target universes with pagination

        Args:
            active_only: Filter to active universes only
            limit: Maximum results to return
            offset: Pagination offset

        Returns:
            List of TargetUniverse instances
        """
        query = self.session.query(TargetUniverse)

        if active_only:
            query = query.filter_by(is_active=True)

        return query.order_by(desc(TargetUniverse.created_at)).offset(offset).limit(limit).all()

    def update_universe(
        self,
        universe_id: str,
        **updates
    ) -> Optional[TargetUniverse]:
        """
        Update target universe with validation

        Args:
            universe_id: Universe ID to update
            **updates: Fields to update

        Returns:
            Updated TargetUniverse instance or None if not found
        """
        try:
            universe = self.get_universe(universe_id)
            if not universe:
                return None

            # Validate geography updates
            if 'geography_config' in updates:
                geo_conflicts = self.geo_validator.detect_conflicts(updates['geography_config'])
                if geo_conflicts:
                    self.logger.warning(f"Geography conflicts in update for {universe_id}: {geo_conflicts}")

            # Update fields
            for field, value in updates.items():
                if hasattr(universe, field):
                    setattr(universe, field, value)

            universe.updated_at = datetime.utcnow()
            self.session.commit()

            self.logger.info(f"Updated target universe: {universe_id}")
            return universe

        except Exception as e:
            self.session.rollback()
            self.logger.error(f"Failed to update universe {universe_id}: {e}")
            raise

    def delete_universe(self, universe_id: str) -> bool:
        """
        Soft delete target universe (mark as inactive)

        Args:
            universe_id: Universe ID to delete

        Returns:
            True if deleted, False if not found
        """
        try:
            universe = self.get_universe(universe_id)
            if not universe:
                return False

            # Check for active campaigns
            active_campaigns = self.session.query(Campaign).filter(
                and_(
                    Campaign.target_universe_id == universe_id,
                    Campaign.status.in_(['scheduled', 'running'])
                )
            ).count()

            if active_campaigns > 0:
                raise ValueError(f"Cannot delete universe with {active_campaigns} active campaigns")

            universe.is_active = False
            universe.updated_at = datetime.utcnow()
            self.session.commit()

            self.logger.info(f"Deleted target universe: {universe_id}")
            return True

        except Exception as e:
            self.session.rollback()
            self.logger.error(f"Failed to delete universe {universe_id}: {e}")
            raise

    # Geo Conflict Detection

    def detect_geo_conflicts(self, geography_config: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Detect geographic conflicts in configuration

        Args:
            geography_config: Geographic constraints to validate

        Returns:
            List of conflict descriptions
        """
        return self.geo_validator.detect_conflicts(geography_config)

    def validate_geo_hierarchy(self, constraints: List[GeographicConstraint]) -> List[str]:
        """
        Validate geographic hierarchy consistency

        Args:
            constraints: List of geographic constraints

        Returns:
            List of validation error messages
        """
        return self.geo_validator.validate_hierarchy(constraints)

    def resolve_geo_overlaps(
        self,
        constraints: List[GeographicConstraint]
    ) -> List[GeographicConstraint]:
        """
        Resolve geographic overlaps by merging or removing redundant constraints

        Args:
            constraints: List of constraints to resolve

        Returns:
            Resolved list of constraints
        """
        return self.geo_validator.resolve_overlaps(constraints)

    # Priority Scoring

    def calculate_universe_priority(self, universe: TargetUniverse) -> float:
        """
        Calculate priority score for target universe based on multiple factors

        Args:
            universe: TargetUniverse to score

        Returns:
            Priority score (0.0 - 1.0, higher is better)
        """
        try:
            score = 0.0

            # Size factor (30% weight) - larger universes get higher priority
            if universe.actual_size > 0:
                size_factor = min(universe.actual_size / 10000, 1.0)  # Cap at 10k targets
                score += size_factor * 0.3

            # Qualification rate (25% weight)
            if universe.actual_size > 0:
                qualification_rate = universe.qualified_count / universe.actual_size
                score += qualification_rate * 0.25

            # Freshness factor (20% weight)
            freshness_score = self._calculate_freshness_score(universe)
            score += freshness_score * 0.2

            # Vertical diversity (15% weight) - more verticals = higher priority
            vertical_count = len(universe.verticals) if universe.verticals else 0
            diversity_factor = min(vertical_count / 5, 1.0)  # Cap at 5 verticals
            score += diversity_factor * 0.15

            # Campaign performance (10% weight)
            campaign_performance = self._calculate_campaign_performance(universe)
            score += campaign_performance * 0.1

            return min(score, 1.0)

        except Exception as e:
            self.logger.error(f"Failed to calculate priority for universe {universe.id}: {e}")
            return 0.0

    def rank_universes_by_priority(
        self,
        universe_ids: Optional[List[str]] = None,
        limit: int = 50
    ) -> List[Tuple[TargetUniverse, float]]:
        """
        Rank target universes by priority score

        Args:
            universe_ids: Optional list to filter by specific universe IDs
            limit: Maximum results to return

        Returns:
            List of (TargetUniverse, priority_score) tuples sorted by priority
        """
        query = self.session.query(TargetUniverse).filter_by(is_active=True)

        if universe_ids:
            query = query.filter(TargetUniverse.id.in_(universe_ids))

        universes = query.limit(limit * 2).all()  # Get more to account for scoring

        # Calculate priorities
        scored_universes = []
        for universe in universes:
            priority = self.calculate_universe_priority(universe)
            scored_universes.append((universe, priority))

        # Sort by priority descending
        scored_universes.sort(key=lambda x: x[1], reverse=True)

        return scored_universes[:limit]

    # Freshness Tracking

    def update_freshness_metrics(self, universe_id: str) -> None:
        """
        Update freshness metrics for a target universe

        Args:
            universe_id: Universe ID to update
        """
        try:
            universe = self.get_universe(universe_id)
            if not universe:
                return

            # Update last refresh timestamp
            universe.last_refresh = datetime.utcnow()

            # Recalculate actual size (would typically query d2_sourcing)
            # For now, we'll simulate this
            universe.actual_size = self._get_current_universe_size(universe)

            self.session.commit()
            self.logger.info(f"Updated freshness metrics for universe {universe_id}")

        except Exception as e:
            self.session.rollback()
            self.logger.error(f"Failed to update freshness for universe {universe_id}: {e}")
            raise

    def get_stale_universes(self, max_age_hours: int = 24) -> List[TargetUniverse]:
        """
        Get universes that need freshness updates

        Args:
            max_age_hours: Maximum age before considering stale

        Returns:
            List of stale TargetUniverse instances
        """
        cutoff_time = datetime.utcnow() - timedelta(hours=max_age_hours)

        return self.session.query(TargetUniverse).filter(
            and_(
                TargetUniverse.is_active == True,
                or_(
                    TargetUniverse.last_refresh.is_(None),
                    TargetUniverse.last_refresh < cutoff_time
                )
            )
        ).all()

    def calculate_freshness_score(self, universe: TargetUniverse) -> float:
        """
        Calculate freshness score for a universe (0.0 - 1.0)

        Args:
            universe: TargetUniverse to score

        Returns:
            Freshness score (1.0 = perfectly fresh, 0.0 = very stale)
        """
        return self._calculate_freshness_score(universe)

    # Metrics and Analytics

    def get_universe_metrics(self, universe_id: str) -> TargetMetrics:
        """
        Get comprehensive metrics for a target universe

        Args:
            universe_id: Universe ID

        Returns:
            TargetMetrics with calculated values
        """
        universe = self.get_universe(universe_id)
        if not universe:
            return TargetMetrics()

        # Query campaign metrics
        campaign_stats = self.session.query(
            func.sum(Campaign.total_targets).label('total'),
            func.sum(Campaign.contacted_targets).label('contacted'),
            func.sum(Campaign.responded_targets).label('responded'),
            func.sum(Campaign.converted_targets).label('converted'),
            func.sum(Campaign.excluded_targets).label('excluded'),
            func.sum(Campaign.total_cost).label('cost')
        ).filter_by(target_universe_id=universe_id).first()

        # Calculate rates
        total = campaign_stats.total or 0
        contacted = campaign_stats.contacted or 0
        responded = campaign_stats.responded or 0
        converted = campaign_stats.converted or 0

        return TargetMetrics(
            total_targets=total,
            qualified_targets=universe.qualified_count,
            contacted_targets=contacted,
            responded_targets=responded,
            converted_targets=converted,
            excluded_targets=campaign_stats.excluded or 0,
            qualification_rate=universe.qualified_count / universe.actual_size if universe.actual_size > 0 else 0.0,
            contact_rate=contacted / total if total > 0 else 0.0,
            response_rate=responded / contacted if contacted > 0 else 0.0,
            conversion_rate=converted / contacted if contacted > 0 else 0.0,
            total_cost=Decimal(str(campaign_stats.cost or 0)),
            cost_per_contact=Decimal(str(campaign_stats.cost or 0)) / contacted if contacted > 0 else Decimal("0.00"),
            cost_per_conversion=Decimal(str(campaign_stats.cost or 0)) / converted if converted > 0 else Decimal("0.00")
        )

    def get_performance_summary(self, days: int = 30) -> Dict[str, Any]:
        """
        Get performance summary across all universes

        Args:
            days: Number of days to include in summary

        Returns:
            Dictionary with performance metrics
        """
        cutoff_date = datetime.utcnow() - timedelta(days=days)

        # Get universe counts
        total_universes = self.session.query(TargetUniverse).filter_by(is_active=True).count()

        # Get fresh vs stale counts
        fresh_universes = self.session.query(TargetUniverse).filter(
            and_(
                TargetUniverse.is_active == True,
                TargetUniverse.last_refresh >= cutoff_date
            )
        ).count()

        # Get campaign metrics
        campaign_metrics = self.session.query(
            func.count(Campaign.id).label('total_campaigns'),
            func.sum(Campaign.total_targets).label('total_targets'),
            func.sum(Campaign.contacted_targets).label('contacted'),
            func.sum(Campaign.converted_targets).label('converted'),
            func.sum(Campaign.total_cost).label('cost')
        ).join(TargetUniverse).filter(
            and_(
                TargetUniverse.is_active == True,
                Campaign.created_at >= cutoff_date
            )
        ).first()

        return {
            'period_days': days,
            'total_universes': total_universes,
            'fresh_universes': fresh_universes,
            'stale_universes': total_universes - fresh_universes,
            'freshness_rate': fresh_universes / total_universes if total_universes > 0 else 0.0,
            'total_campaigns': campaign_metrics.total_campaigns or 0,
            'total_targets': campaign_metrics.total_targets or 0,
            'contacted_targets': campaign_metrics.contacted or 0,
            'converted_targets': campaign_metrics.converted or 0,
            'conversion_rate': (campaign_metrics.converted or 0) / (campaign_metrics.contacted or 1),
            'total_cost': float(campaign_metrics.cost or 0),
            'average_cost_per_conversion': float(campaign_metrics.cost or 0) / (campaign_metrics.converted or 1)
        }

    # Private helper methods

    def _estimate_universe_size(
        self,
        verticals: List[VerticalMarket],
        geography_config: Dict[str, Any]
    ) -> Optional[int]:
        """Estimate universe size based on criteria (placeholder implementation)"""
        # This would typically query historical data or use estimation algorithms
        base_size = len(verticals) * 1000  # 1000 targets per vertical as baseline

        # Adjust for geography scope
        geo_multiplier = self._calculate_geo_multiplier(geography_config)

        return int(base_size * geo_multiplier)

    def _calculate_geo_multiplier(self, geography_config: Dict[str, Any]) -> float:
        """Calculate geographic scope multiplier for size estimation"""
        # Simplified implementation
        if not geography_config:
            return 1.0

        # More specific targeting = smaller multiplier
        constraint_count = len(geography_config.get('constraints', []))
        return max(0.1, 1.0 - (constraint_count * 0.2))

    def _calculate_freshness_score(self, universe: TargetUniverse) -> float:
        """Calculate freshness score based on last refresh time"""
        if not universe.last_refresh:
            return 0.0

        hours_since_refresh = (datetime.utcnow() - universe.last_refresh).total_seconds() / 3600

        # Score decreases over time: 1.0 at 0 hours, 0.5 at 24 hours, 0.0 at 72 hours
        if hours_since_refresh <= 24:
            return 1.0 - (hours_since_refresh / 48)  # Linear decrease
        else:
            return max(0.0, 0.5 - ((hours_since_refresh - 24) / 96))

    def _calculate_campaign_performance(self, universe: TargetUniverse) -> float:
        """Calculate average campaign performance for universe"""
        campaigns = self.session.query(Campaign).filter_by(
            target_universe_id=universe.id
        ).all()

        if not campaigns:
            return 0.5  # Neutral score for new universes

        total_conversion_rate = 0.0
        for campaign in campaigns:
            if campaign.contacted_targets > 0:
                conversion_rate = campaign.converted_targets / campaign.contacted_targets
                total_conversion_rate += conversion_rate

        return total_conversion_rate / len(campaigns) if campaigns else 0.0

    def _get_current_universe_size(self, universe: TargetUniverse) -> int:
        """Get current actual size of universe (placeholder implementation)"""
        # This would typically query the d2_sourcing module to get actual counts
        # For now, return the current value with some simulation
        return universe.actual_size + (universe.actual_size // 10)  # Simulate 10% growth
