"""SEMrush adapter for traffic and keyword enrichment."""
import os
import logging
import redis
from datetime import datetime, timedelta
from functools import lru_cache
from typing import Dict, Optional

from d0_gateway.providers.semrush import SEMrushClient
from core.config import settings

logger = logging.getLogger(__name__)

# Redis client for monthly quota tracking
_redis_client = None


def _get_redis_client():
    """Get or create Redis client."""
    global _redis_client
    if _redis_client is None:
        _redis_client = redis.Redis(
            host=settings.redis_host, port=settings.redis_port, decode_responses=True
        )
    return _redis_client


class SEMrushAdapter:
    """
    SEMrush adapter for domain traffic and keyword analysis.

    Implements:
    - Monthly quota tracking via Redis
    - 30-day caching
    - Traffic and keyword intent extraction
    """

    def __init__(self, api_key: Optional[str] = None):
        """Initialize SEMrush adapter."""
        self.api_key = api_key or os.getenv("SEMRUSH_API_KEY")
        if not self.api_key:
            raise ValueError("SEMrush API key not configured")

        self.client = SEMrushClient(api_key=self.api_key)
        self.monthly_cap = int(os.getenv("MONTHLY_SEMRUSH_CAP", "10000"))
        self._cache = {}  # Simple in-memory cache

    def _get_month_key(self) -> str:
        """Get Redis key for current month's quota."""
        now = datetime.now()
        return f"semrush:quota:{now.year}:{now.month}"

    def _check_monthly_quota(self) -> bool:
        """Check if monthly quota allows another request."""
        try:
            redis = _get_redis_client()
            key = self._get_month_key()

            # Get current count
            current = redis.get(key)
            if current is None:
                current = 0
            else:
                current = int(current)

            return current < self.monthly_cap
        except Exception as e:
            logger.error(f"Redis quota check failed: {e}")
            # Fail open - allow request if Redis is down
            return True

    def _increment_monthly_quota(self):
        """Increment monthly quota counter."""
        try:
            redis = _get_redis_client()
            key = self._get_month_key()

            # Increment with expiry at end of month
            pipeline = redis.pipeline()
            pipeline.incr(key)

            # Set expiry to end of current month
            now = datetime.now()
            if now.month == 12:
                next_month = datetime(now.year + 1, 1, 1)
            else:
                next_month = datetime(now.year, now.month + 1, 1)
            seconds_until_next_month = int((next_month - now).total_seconds())
            pipeline.expire(key, seconds_until_next_month)

            pipeline.execute()
        except Exception as e:
            logger.error(f"Redis quota increment failed: {e}")

    @lru_cache(maxsize=1000)
    def _get_cached(self, domain: str) -> Optional[Dict]:
        """Get cached result for domain (30-day cache)."""
        cache_key = f"semrush:{domain}"

        if cache_key in self._cache:
            cached_data, cached_time = self._cache[cache_key]
            # Check if cache is still valid (30 days)
            if datetime.now() - cached_time < timedelta(days=30):
                return cached_data

        return None

    def _set_cached(self, domain: str, data: Dict):
        """Cache result for domain."""
        cache_key = f"semrush:{domain}"
        self._cache[cache_key] = (data, datetime.now())

    async def fetch_overview(self, domain: str) -> Optional[Dict]:
        """
        Fetch domain overview with traffic and keyword data.

        Args:
            domain: Domain to analyze

        Returns:
            Dict with:
            - visits: Estimated monthly visits
            - organic_keywords: Number of organic keywords
            - commercial_kw_pct: Percentage of commercial intent keywords
            - paid_keywords: Number of paid keywords

        Respects MONTHLY_SEMRUSH_CAP and caches for 30 days.
        """
        # Check cache first
        cached = self._get_cached(domain)
        if cached is not None:
            logger.info(f"Using cached SEMrush data for {domain}")
            return cached

        # Check monthly quota
        if not self._check_monthly_quota():
            logger.warning(f"SEMrush monthly quota exceeded ({self.monthly_cap})")
            return None

        try:
            # Fetch from API
            result = await self.client.get_domain_overview(domain)

            if not result:
                return None

            # Extract and transform data
            data = {
                "visits": result.get("organic_traffic", 0),
                "organic_keywords": result.get("organic_keywords", 0),
                "paid_keywords": result.get("paid_keywords", 0),
                # Estimate commercial intent based on paid/organic ratio
                "commercial_kw_pct": self._estimate_commercial_intent(result),
            }

            # Cache result
            self._set_cached(domain, data)

            # Increment quota
            self._increment_monthly_quota()

            logger.info(
                f"SEMrush data for {domain}: "
                f"visits={data['visits']}, "
                f"organic_kw={data['organic_keywords']}, "
                f"commercial_pct={data['commercial_kw_pct']}%"
            )

            return data

        except Exception as e:
            logger.error(f"SEMrush fetch failed for {domain}: {e}")
            return None

    def _estimate_commercial_intent(self, semrush_data: Dict) -> int:
        """
        Estimate commercial keyword percentage from SEMrush data.

        Uses ratio of paid to organic keywords as a proxy for commercial intent.
        """
        organic = semrush_data.get("organic_keywords", 0)
        paid = semrush_data.get("paid_keywords", 0)

        if organic == 0:
            return 50  # Default if no organic keywords

        # Higher paid/organic ratio suggests more commercial intent
        ratio = paid / (organic + paid) if (organic + paid) > 0 else 0

        # Map ratio to percentage (0-100)
        # 0% paid = 20% commercial (some natural commercial intent)
        # 50% paid = 70% commercial
        # 80%+ paid = 90% commercial
        if ratio < 0.1:
            return 20
        elif ratio < 0.3:
            return 40
        elif ratio < 0.5:
            return 60
        elif ratio < 0.8:
            return 70
        else:
            return 90

    def get_visits_per_mil(self, visits: int, annual_revenue: float) -> int:
        """
        Calculate visits per million in revenue.

        Args:
            visits: Monthly visits
            annual_revenue: Annual revenue in dollars

        Returns:
            Monthly visits per $1M revenue
        """
        if annual_revenue <= 0:
            return 5000  # Default

        revenue_in_millions = annual_revenue / 1_000_000
        return int(visits / revenue_in_millions) if revenue_in_millions > 0 else 5000
