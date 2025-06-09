"""
Assessment Caching Layer - Task 036

Implements caching for assessment results to improve performance and reduce
redundant API calls. Provides TTL configuration, cache invalidation logic,
and hit rate tracking.

Acceptance Criteria:
- Recent assessments cached
- TTL configuration works
- Cache invalidation logic
- Hit rate tracking
"""
import asyncio
import hashlib
import json
import time
from typing import Dict, Any, Optional, List, Tuple, Set
from datetime import datetime, timedelta
from decimal import Decimal
from dataclasses import dataclass, asdict
from enum import Enum
import logging

from .types import AssessmentType, AssessmentStatus
from .coordinator import CoordinatorResult

# Setup logging
logger = logging.getLogger(__name__)


class CacheStrategy(Enum):
    """Cache strategy options"""
    LRU = "lru"  # Least Recently Used
    LFU = "lfu"  # Least Frequently Used
    FIFO = "fifo"  # First In, First Out
    TTL_ONLY = "ttl_only"  # Time-based only


@dataclass
class CacheEntry:
    """Cache entry with metadata"""
    key: str
    value: Any
    created_at: datetime
    accessed_at: datetime
    access_count: int
    ttl_seconds: int
    tags: Set[str]
    size_bytes: int

    @property
    def is_expired(self) -> bool:
        """Check if cache entry is expired"""
        if self.ttl_seconds <= 0:
            return False  # No expiration
        return datetime.utcnow() > self.created_at + timedelta(seconds=self.ttl_seconds)

    @property
    def age_seconds(self) -> int:
        """Get age of cache entry in seconds"""
        return int((datetime.utcnow() - self.created_at).total_seconds())

    def touch(self):
        """Update access metadata"""
        self.accessed_at = datetime.utcnow()
        self.access_count += 1


@dataclass
class CacheStats:
    """Cache statistics for monitoring"""
    hits: int = 0
    misses: int = 0
    evictions: int = 0
    expired_removals: int = 0
    total_size_bytes: int = 0
    entry_count: int = 0

    @property
    def hit_rate(self) -> float:
        """Calculate cache hit rate"""
        total = self.hits + self.misses
        return (self.hits / total) if total > 0 else 0.0

    @property
    def miss_rate(self) -> float:
        """Calculate cache miss rate"""
        return 1.0 - self.hit_rate


class AssessmentCache:
    """
    Assessment results caching layer with TTL, invalidation, and hit tracking

    Acceptance Criteria: Recent assessments cached, TTL configuration works,
    Cache invalidation logic, Hit rate tracking
    """

    def __init__(
        self,
        max_entries: int = 1000,
        default_ttl_seconds: int = 3600,  # 1 hour
        max_size_mb: int = 100,
        strategy: CacheStrategy = CacheStrategy.LRU,
        cleanup_interval_seconds: int = 300  # 5 minutes
    ):
        """
        Initialize assessment cache

        Args:
            max_entries: Maximum number of cache entries
            default_ttl_seconds: Default TTL for cache entries
            max_size_mb: Maximum cache size in MB
            strategy: Cache eviction strategy
            cleanup_interval_seconds: Interval for background cleanup
        """
        self.max_entries = max_entries
        self.default_ttl_seconds = default_ttl_seconds
        self.max_size_bytes = max_size_mb * 1024 * 1024
        self.strategy = strategy
        self.cleanup_interval_seconds = cleanup_interval_seconds

        # Cache storage
        self._cache: Dict[str, CacheEntry] = {}
        self._stats = CacheStats()

        # Configuration per assessment type
        self._ttl_config: Dict[AssessmentType, int] = {
            AssessmentType.PAGESPEED: 1800,    # 30 minutes
            AssessmentType.TECH_STACK: 7200,   # 2 hours
            AssessmentType.AI_INSIGHTS: 3600,  # 1 hour
            AssessmentType.FULL_AUDIT: 1800    # 30 minutes
        }

        # Background cleanup task
        self._cleanup_task: Optional[asyncio.Task] = None
        try:
            self._start_background_cleanup()
        except RuntimeError:
            # No event loop running - cleanup will be manual
            logger.debug("No event loop available for background cleanup")

    def _start_background_cleanup(self):
        """Start background cleanup task"""
        async def cleanup_loop():
            while True:
                try:
                    await asyncio.sleep(self.cleanup_interval_seconds)
                    await self._cleanup_expired()
                except asyncio.CancelledError:
                    break
                except Exception as e:
                    logger.error(f"Cache cleanup error: {e}")

        self._cleanup_task = asyncio.create_task(cleanup_loop())

    async def _cleanup_expired(self):
        """Clean up expired cache entries"""
        expired_keys = [
            key for key, entry in self._cache.items()
            if entry.is_expired
        ]

        for key in expired_keys:
            self._remove_entry(key, reason="expired")
            self._stats.expired_removals += 1

        if expired_keys:
            logger.info(f"Cleaned up {len(expired_keys)} expired cache entries")

    def _generate_cache_key(
        self,
        business_id: str,
        url: str,
        assessment_types: List[AssessmentType],
        industry: str = "default",
        **kwargs
    ) -> str:
        """
        Generate cache key for assessment

        Acceptance Criteria: Recent assessments cached
        """
        # Create deterministic key based on assessment parameters
        key_data = {
            "business_id": business_id,
            "url": url.lower().strip("/"),  # Normalize URL
            "assessment_types": sorted([t.value for t in assessment_types]),
            "industry": industry.lower(),
            "extra": kwargs
        }

        # Generate hash of key data
        key_json = json.dumps(key_data, sort_keys=True, default=str)
        key_hash = hashlib.sha256(key_json.encode()).hexdigest()[:16]

        return f"assessment:{key_hash}"

    def _get_ttl_for_assessment(self, assessment_types: List[AssessmentType]) -> int:
        """
        Get TTL for assessment based on types

        Acceptance Criteria: TTL configuration works
        """
        if not assessment_types:
            return self.default_ttl_seconds

        # Use minimum TTL of all assessment types
        ttls = [
            self._ttl_config.get(atype, self.default_ttl_seconds)
            for atype in assessment_types
        ]
        return min(ttls)

    def _calculate_entry_size(self, value: Any) -> int:
        """Calculate approximate size of cache entry in bytes"""
        try:
            # Convert to JSON to estimate size
            json_str = json.dumps(value, default=str, ensure_ascii=False)
            return len(json_str.encode('utf-8'))
        except Exception:
            # Fallback estimation
            return len(str(value).encode('utf-8'))

    def _should_evict(self) -> bool:
        """Check if cache eviction is needed"""
        return (
            len(self._cache) >= self.max_entries or
            self._stats.total_size_bytes >= self.max_size_bytes
        )

    def _evict_entries(self):
        """
        Evict cache entries based on strategy

        Acceptance Criteria: Cache invalidation logic
        """
        if not self._cache:
            return

        # Calculate how many entries to evict (25% of max or 1, whichever is larger)
        evict_count = max(1, self.max_entries // 4)

        if self.strategy == CacheStrategy.LRU:
            # Evict least recently used
            entries_by_access = sorted(
                self._cache.items(),
                key=lambda x: x[1].accessed_at
            )
        elif self.strategy == CacheStrategy.LFU:
            # Evict least frequently used
            entries_by_access = sorted(
                self._cache.items(),
                key=lambda x: (x[1].access_count, x[1].accessed_at)
            )
        elif self.strategy == CacheStrategy.FIFO:
            # Evict oldest entries
            entries_by_access = sorted(
                self._cache.items(),
                key=lambda x: x[1].created_at
            )
        else:  # TTL_ONLY
            # Evict by TTL, then by age
            entries_by_access = sorted(
                self._cache.items(),
                key=lambda x: (x[1].is_expired, x[1].created_at)
            )

        # Evict entries
        for i in range(min(evict_count, len(entries_by_access))):
            key, _ = entries_by_access[i]
            self._remove_entry(key, reason="evicted")
            self._stats.evictions += 1

    def _remove_entry(self, key: str, reason: str = "removed"):
        """Remove entry from cache and update stats"""
        if key in self._cache:
            entry = self._cache[key]
            self._stats.total_size_bytes -= entry.size_bytes
            self._stats.entry_count -= 1
            del self._cache[key]
            logger.debug(f"Cache entry {key} {reason}")

    async def get(
        self,
        business_id: str,
        url: str,
        assessment_types: List[AssessmentType],
        industry: str = "default",
        **kwargs
    ) -> Optional[CoordinatorResult]:
        """
        Get cached assessment result

        Acceptance Criteria: Recent assessments cached, Hit rate tracking
        """
        key = self._generate_cache_key(
            business_id, url, assessment_types, industry, **kwargs
        )

        if key not in self._cache:
            self._stats.misses += 1
            logger.debug(f"Cache miss for key {key}")
            return None

        entry = self._cache[key]

        # Check if expired
        if entry.is_expired:
            self._remove_entry(key, reason="expired")
            self._stats.expired_removals += 1
            self._stats.misses += 1
            logger.debug(f"Cache entry {key} expired")
            return None

        # Update access metadata
        entry.touch()
        self._stats.hits += 1

        logger.debug(f"Cache hit for key {key} (age: {entry.age_seconds}s)")
        return entry.value

    async def put(
        self,
        business_id: str,
        url: str,
        assessment_types: List[AssessmentType],
        result: CoordinatorResult,
        industry: str = "default",
        ttl_override: Optional[int] = None,
        tags: Optional[Set[str]] = None,
        **kwargs
    ) -> str:
        """
        Store assessment result in cache

        Acceptance Criteria: Recent assessments cached, TTL configuration works
        """
        key = self._generate_cache_key(
            business_id, url, assessment_types, industry, **kwargs
        )

        # Determine TTL
        ttl_seconds = ttl_override or self._get_ttl_for_assessment(assessment_types)

        # Calculate entry size
        size_bytes = self._calculate_entry_size(result)

        # Create cache entry
        entry = CacheEntry(
            key=key,
            value=result,
            created_at=datetime.utcnow(),
            accessed_at=datetime.utcnow(),
            access_count=1,
            ttl_seconds=ttl_seconds,
            tags=tags or set(),
            size_bytes=size_bytes
        )

        # Check if eviction is needed
        if self._should_evict():
            self._evict_entries()

        # Store entry
        if key in self._cache:
            # Update existing entry stats
            old_entry = self._cache[key]
            self._stats.total_size_bytes -= old_entry.size_bytes
        else:
            self._stats.entry_count += 1

        self._cache[key] = entry
        self._stats.total_size_bytes += size_bytes

        logger.debug(f"Cached assessment result {key} (TTL: {ttl_seconds}s, Size: {size_bytes}b)")
        return key

    async def invalidate(
        self,
        business_id: Optional[str] = None,
        url: Optional[str] = None,
        assessment_types: Optional[List[AssessmentType]] = None,
        tags: Optional[Set[str]] = None,
        **kwargs
    ) -> int:
        """
        Invalidate cache entries based on criteria

        Acceptance Criteria: Cache invalidation logic
        """
        removed_count = 0
        keys_to_remove = []

        for key, entry in self._cache.items():
            should_remove = False

            # Check tag-based invalidation
            if tags and entry.tags:
                if any(tag in entry.tags for tag in tags):
                    should_remove = True

            # Check parameter-based invalidation
            if business_id or url or assessment_types:
                # Generate key for comparison
                if business_id and url and assessment_types:
                    target_key = self._generate_cache_key(
                        business_id, url, assessment_types, **kwargs
                    )
                    if key == target_key:
                        should_remove = True

            if should_remove:
                keys_to_remove.append(key)

        # Remove identified keys
        for key in keys_to_remove:
            self._remove_entry(key, reason="invalidated")
            removed_count += 1

        if removed_count > 0:
            logger.info(f"Invalidated {removed_count} cache entries")

        return removed_count

    async def invalidate_by_domain(self, domain: str) -> int:
        """Invalidate all cache entries for a specific domain"""
        removed_count = 0
        keys_to_remove = []

        domain_lower = domain.lower()

        for key, entry in self._cache.items():
            # Check if entry's result contains the domain
            if hasattr(entry.value, 'partial_results'):
                for assessment_result in entry.value.partial_results.values():
                    if hasattr(assessment_result, 'domain'):
                        if assessment_result.domain.lower() == domain_lower:
                            keys_to_remove.append(key)
                            break

        # Remove identified keys
        for key in keys_to_remove:
            self._remove_entry(key, reason="domain_invalidated")
            removed_count += 1

        if removed_count > 0:
            logger.info(f"Invalidated {removed_count} cache entries for domain {domain}")

        return removed_count

    def get_stats(self) -> CacheStats:
        """
        Get cache statistics

        Acceptance Criteria: Hit rate tracking
        """
        # Update current stats
        self._stats.entry_count = len(self._cache)
        self._stats.total_size_bytes = sum(entry.size_bytes for entry in self._cache.values())

        return CacheStats(
            hits=self._stats.hits,
            misses=self._stats.misses,
            evictions=self._stats.evictions,
            expired_removals=self._stats.expired_removals,
            total_size_bytes=self._stats.total_size_bytes,
            entry_count=self._stats.entry_count
        )

    def get_cache_info(self) -> Dict[str, Any]:
        """Get detailed cache information"""
        stats = self.get_stats()

        # Calculate additional metrics
        total_requests = stats.hits + stats.misses
        avg_entry_size = stats.total_size_bytes / stats.entry_count if stats.entry_count > 0 else 0

        # Get entry age distribution
        ages = [entry.age_seconds for entry in self._cache.values()]
        avg_age = sum(ages) / len(ages) if ages else 0

        return {
            "stats": asdict(stats),
            "configuration": {
                "max_entries": self.max_entries,
                "max_size_mb": self.max_size_bytes // (1024 * 1024),
                "default_ttl_seconds": self.default_ttl_seconds,
                "strategy": self.strategy.value,
                "cleanup_interval_seconds": self.cleanup_interval_seconds
            },
            "metrics": {
                "hit_rate_percentage": round(stats.hit_rate * 100, 2),
                "total_requests": total_requests,
                "cache_utilization_percentage": round(
                    (stats.entry_count / self.max_entries) * 100, 2
                ),
                "size_utilization_percentage": round(
                    (stats.total_size_bytes / self.max_size_bytes) * 100, 2
                ),
                "average_entry_size_bytes": round(avg_entry_size, 2),
                "average_entry_age_seconds": round(avg_age, 2)
            },
            "ttl_configuration": {
                atype.value: ttl for atype, ttl in self._ttl_config.items()
            }
        }

    async def clear(self) -> int:
        """Clear all cache entries"""
        count = len(self._cache)
        self._cache.clear()
        self._stats = CacheStats()

        logger.info(f"Cleared {count} cache entries")
        return count

    def configure_ttl(self, assessment_type: AssessmentType, ttl_seconds: int):
        """
        Configure TTL for specific assessment type

        Acceptance Criteria: TTL configuration works
        """
        self._ttl_config[assessment_type] = ttl_seconds
        logger.info(f"Configured TTL for {assessment_type.value}: {ttl_seconds}s")

    def list_entries(self, limit: int = 50) -> List[Dict[str, Any]]:
        """List cache entries for debugging"""
        entries = []

        for key, entry in list(self._cache.items())[:limit]:
            entries.append({
                "key": key,
                "created_at": entry.created_at.isoformat(),
                "accessed_at": entry.accessed_at.isoformat(),
                "access_count": entry.access_count,
                "age_seconds": entry.age_seconds,
                "ttl_seconds": entry.ttl_seconds,
                "is_expired": entry.is_expired,
                "size_bytes": entry.size_bytes,
                "tags": list(entry.tags),
                "business_id": getattr(entry.value, 'business_id', 'unknown') if entry.value else 'unknown'
            })

        return entries

    async def close(self):
        """Clean up cache resources"""
        if self._cleanup_task:
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass

        logger.info("Assessment cache closed")


class CacheManager:
    """
    Global cache manager for assessment caching

    Provides singleton access to assessment cache with configuration management
    """

    _instance: Optional[AssessmentCache] = None
    _lock = asyncio.Lock()

    @classmethod
    async def get_cache(
        cls,
        max_entries: int = 1000,
        default_ttl_seconds: int = 3600,
        max_size_mb: int = 100,
        strategy: CacheStrategy = CacheStrategy.LRU
    ) -> AssessmentCache:
        """Get or create singleton cache instance"""
        if cls._instance is None:
            async with cls._lock:
                if cls._instance is None:
                    cls._instance = AssessmentCache(
                        max_entries=max_entries,
                        default_ttl_seconds=default_ttl_seconds,
                        max_size_mb=max_size_mb,
                        strategy=strategy
                    )
                    logger.info("Created assessment cache instance")

        return cls._instance

    @classmethod
    async def close_cache(cls):
        """Close and clean up cache instance"""
        if cls._instance:
            await cls._instance.close()
            cls._instance = None
            logger.info("Closed assessment cache instance")


# Cache decorator for easy use
def cached_assessment(
    ttl_seconds: Optional[int] = None,
    tags: Optional[Set[str]] = None,
    cache_manager: Optional[CacheManager] = None
):
    """
    Decorator for caching assessment results

    Usage:
        @cached_assessment(ttl_seconds=1800, tags={"api", "v1"})
        async def perform_assessment(...):
            ...
    """
    def decorator(func):
        async def wrapper(*args, **kwargs):
            # Extract cache key parameters
            cache = await CacheManager.get_cache()

            # Try to get from cache first
            cached_result = await cache.get(*args, **kwargs)
            if cached_result is not None:
                return cached_result

            # Execute function
            result = await func(*args, **kwargs)

            # Store in cache
            if result is not None:
                await cache.put(
                    *args, result, ttl_override=ttl_seconds, tags=tags, **kwargs
                )

            return result

        return wrapper
    return decorator
