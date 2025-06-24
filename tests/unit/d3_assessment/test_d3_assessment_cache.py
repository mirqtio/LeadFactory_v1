"""
Test Assessment Caching Layer - Task 036

Comprehensive tests for assessment caching functionality.
Tests all acceptance criteria:
- Recent assessments cached
- TTL configuration works
- Cache invalidation logic
- Hit rate tracking
"""
import asyncio
import sys
import uuid
from datetime import datetime, timedelta
from decimal import Decimal
from unittest.mock import AsyncMock, patch

import pytest

sys.path.insert(0, "/app")  # noqa: E402

from d3_assessment.cache import CacheEntry  # noqa: E402
from d3_assessment.cache import (
    AssessmentCache,
    CacheManager,
    CacheStats,
    CacheStrategy,
    cached_assessment,
)
from d3_assessment.coordinator import CoordinatorResult  # noqa: E402
from d3_assessment.models import AssessmentResult  # noqa: E402
from d3_assessment.types import AssessmentStatus, AssessmentType  # noqa: E402


class TestTask036AcceptanceCriteria:
    """Test that Task 036 meets all acceptance criteria"""

    def setup_method(self):
        """Setup for each test"""
        # Reset singleton
        CacheManager._instance = None

    @pytest.fixture
    def cache(self):
        """Create cache instance for testing"""
        return AssessmentCache(
            max_entries=10,
            default_ttl_seconds=300,  # 5 minutes
            max_size_mb=1,
            strategy=CacheStrategy.LRU,
            cleanup_interval_seconds=60,
        )

    @pytest.fixture
    def sample_coordinator_result(self):
        """Sample coordinator result for testing"""
        return CoordinatorResult(
            session_id="sess_test123",
            business_id="biz_test123",
            total_assessments=2,
            completed_assessments=2,
            failed_assessments=0,
            partial_results={
                AssessmentType.PAGESPEED: AssessmentResult(
                    id=str(uuid.uuid4()),
                    business_id="biz_test123",
                    assessment_type=AssessmentType.PAGESPEED,
                    status=AssessmentStatus.COMPLETED,
                    url="https://example.com",
                    domain="example.com",
                    performance_score=85,
                ),
                AssessmentType.TECH_STACK: AssessmentResult(
                    id=str(uuid.uuid4()),
                    business_id="biz_test123",
                    assessment_type=AssessmentType.TECH_STACK,
                    status=AssessmentStatus.COMPLETED,
                    url="https://example.com",
                    domain="example.com",
                    tech_stack_data={"technologies": []},
                ),
            },
            errors={},
            total_cost_usd=Decimal("0.25"),
            execution_time_ms=120000,
            started_at=datetime.utcnow() - timedelta(minutes=2),
            completed_at=datetime.utcnow(),
        )

    @pytest.mark.asyncio
    async def test_recent_assessments_cached(self, cache, sample_coordinator_result):
        """
        Test that recent assessments are cached correctly

        Acceptance Criteria: Recent assessments cached
        """
        business_id = "biz_test123"
        url = "https://example.com"
        assessment_types = [AssessmentType.PAGESPEED, AssessmentType.TECH_STACK]
        industry = "ecommerce"

        # Initially no cached result
        cached_result = await cache.get(business_id, url, assessment_types, industry)
        assert cached_result is None

        # Store result in cache
        cache_key = await cache.put(
            business_id, url, assessment_types, sample_coordinator_result, industry
        )
        assert cache_key.startswith("assessment:")
        assert len(cache_key) == 27  # "assessment:" + 16 hex chars

        # Retrieve cached result
        cached_result = await cache.get(business_id, url, assessment_types, industry)
        assert cached_result is not None
        assert cached_result.session_id == sample_coordinator_result.session_id
        assert cached_result.business_id == sample_coordinator_result.business_id
        assert (
            cached_result.total_assessments
            == sample_coordinator_result.total_assessments
        )

        # Verify cache stats
        stats = cache.get_stats()
        assert stats.hits == 1
        assert stats.misses == 1
        assert stats.entry_count == 1
        assert stats.hit_rate == 0.5

        print("✓ Recent assessments cached correctly")

    @pytest.mark.asyncio
    async def test_ttl_configuration_works(self, cache, sample_coordinator_result):
        """
        Test that TTL configuration works correctly

        Acceptance Criteria: TTL configuration works
        """
        business_id = "biz_test123"
        url = "https://example.com"
        assessment_types = [AssessmentType.PAGESPEED]

        # Test default TTL configuration
        ttl = cache._get_ttl_for_assessment(assessment_types)
        assert ttl == 1800  # PageSpeed default is 30 minutes

        # Test custom TTL configuration
        cache.configure_ttl(AssessmentType.PAGESPEED, 600)  # 10 minutes
        ttl = cache._get_ttl_for_assessment(assessment_types)
        assert ttl == 600

        # Store with custom TTL override
        await cache.put(
            business_id,
            url,
            assessment_types,
            sample_coordinator_result,
            ttl_override=120,  # 2 minutes
        )

        # Check entry TTL
        cache_key = cache._generate_cache_key(business_id, url, assessment_types)
        entry = cache._cache[cache_key]
        assert entry.ttl_seconds == 120

        # Test TTL expiration
        entry.created_at = datetime.utcnow() - timedelta(seconds=121)  # Make it expired
        assert entry.is_expired is True

        # Expired entry should not be returned
        cached_result = await cache.get(business_id, url, assessment_types)
        assert cached_result is None

        # Stats should show expired removal
        stats = cache.get_stats()
        assert stats.expired_removals == 1

        print("✓ TTL configuration works correctly")

    @pytest.mark.asyncio
    async def test_cache_invalidation_logic(self, cache, sample_coordinator_result):
        """
        Test that cache invalidation logic works correctly

        Acceptance Criteria: Cache invalidation logic
        """
        business_id = "biz_test123"
        url1 = "https://example.com"
        url2 = "https://test.com"
        assessment_types = [AssessmentType.PAGESPEED]

        # Create a second coordinator result with the correct domain for test.com
        test_com_result = CoordinatorResult(
            session_id="sess_test456",
            business_id="biz_test123",
            total_assessments=1,
            completed_assessments=1,
            failed_assessments=0,
            partial_results={
                AssessmentType.PAGESPEED: AssessmentResult(
                    id=str(uuid.uuid4()),
                    business_id="biz_test123",
                    assessment_type=AssessmentType.PAGESPEED,
                    status=AssessmentStatus.COMPLETED,
                    url="https://test.com",
                    domain="test.com",  # Correct domain for test.com
                    performance_score=75,
                )
            },
            errors={},
            total_cost_usd=Decimal("0.15"),
            execution_time_ms=90000,
            started_at=datetime.utcnow() - timedelta(minutes=1),
            completed_at=datetime.utcnow(),
        )

        # Store multiple entries
        await cache.put(business_id, url1, assessment_types, sample_coordinator_result)
        await cache.put(business_id, url2, assessment_types, test_com_result)

        # Store entry with tags
        await cache.put(
            business_id,
            url1,
            [AssessmentType.TECH_STACK],
            sample_coordinator_result,
            tags={"test", "api"},
        )

        assert cache.get_stats().entry_count == 3

        # Test specific invalidation
        removed_count = await cache.invalidate(
            business_id=business_id, url=url1, assessment_types=assessment_types
        )
        assert removed_count == 1
        assert cache.get_stats().entry_count == 2

        # Test tag-based invalidation
        removed_count = await cache.invalidate(tags={"test"})
        assert removed_count == 1
        assert cache.get_stats().entry_count == 1

        # Test domain invalidation
        removed_count = await cache.invalidate_by_domain("test.com")
        assert removed_count == 1
        assert cache.get_stats().entry_count == 0

        print("✓ Cache invalidation logic works correctly")

    @pytest.mark.asyncio
    async def test_hit_rate_tracking(self, cache, sample_coordinator_result):
        """
        Test that hit rate tracking works correctly

        Acceptance Criteria: Hit rate tracking
        """
        business_id = "biz_test123"
        url = "https://example.com"
        assessment_types = [AssessmentType.PAGESPEED]

        # Initial stats
        stats = cache.get_stats()
        assert stats.hits == 0
        assert stats.misses == 0
        assert stats.hit_rate == 0.0
        assert stats.miss_rate == 1.0

        # First access - miss
        result = await cache.get(business_id, url, assessment_types)
        assert result is None

        stats = cache.get_stats()
        assert stats.hits == 0
        assert stats.misses == 1
        assert stats.hit_rate == 0.0
        assert stats.miss_rate == 1.0

        # Store result
        await cache.put(business_id, url, assessment_types, sample_coordinator_result)

        # Second access - hit
        result = await cache.get(business_id, url, assessment_types)
        assert result is not None

        stats = cache.get_stats()
        assert stats.hits == 1
        assert stats.misses == 1
        assert stats.hit_rate == 0.5
        assert stats.miss_rate == 0.5

        # Third access - another hit
        result = await cache.get(business_id, url, assessment_types)
        assert result is not None

        stats = cache.get_stats()
        assert stats.hits == 2
        assert stats.misses == 1
        assert abs(stats.hit_rate - 2 / 3) < 1e-10
        assert abs(stats.miss_rate - 1 / 3) < 1e-10

        # Access count tracking
        cache_key = cache._generate_cache_key(business_id, url, assessment_types)
        entry = cache._cache[cache_key]
        assert entry.access_count == 3  # 1 put + 2 gets

        print("✓ Hit rate tracking works correctly")

    @pytest.mark.asyncio
    async def test_cache_eviction_strategies(self, sample_coordinator_result):
        """Test different cache eviction strategies"""
        # Test LRU eviction
        lru_cache = AssessmentCache(max_entries=3, strategy=CacheStrategy.LRU)

        # Fill cache
        for i in range(4):
            await lru_cache.put(
                f"biz_{i}",
                f"https://site{i}.com",
                [AssessmentType.PAGESPEED],
                sample_coordinator_result,
            )

        # Should have evicted oldest accessed entry
        stats = lru_cache.get_stats()
        assert stats.entry_count == 3
        assert stats.evictions == 1

        # Test LFU eviction
        lfu_cache = AssessmentCache(max_entries=3, strategy=CacheStrategy.LFU)

        # Add entries with different access patterns
        await lfu_cache.put(
            "biz_1",
            "https://site1.com",
            [AssessmentType.PAGESPEED],
            sample_coordinator_result,
        )
        await lfu_cache.put(
            "biz_2",
            "https://site2.com",
            [AssessmentType.PAGESPEED],
            sample_coordinator_result,
        )
        await lfu_cache.put(
            "biz_3",
            "https://site3.com",
            [AssessmentType.PAGESPEED],
            sample_coordinator_result,
        )

        # Access entry 1 multiple times
        await lfu_cache.get("biz_1", "https://site1.com", [AssessmentType.PAGESPEED])
        await lfu_cache.get("biz_1", "https://site1.com", [AssessmentType.PAGESPEED])

        # Add new entry to trigger eviction
        await lfu_cache.put(
            "biz_4",
            "https://site4.com",
            [AssessmentType.PAGESPEED],
            sample_coordinator_result,
        )

        # Entry 1 should still be in cache (most frequently used)
        cached = await lfu_cache.get(
            "biz_1", "https://site1.com", [AssessmentType.PAGESPEED]
        )
        assert cached is not None

        await lru_cache.close()
        await lfu_cache.close()

        print("✓ Cache eviction strategies work correctly")

    @pytest.mark.asyncio
    async def test_cache_size_limits(self, sample_coordinator_result):
        """Test cache size limits and eviction"""
        # Create cache with very small size limit
        size_cache = AssessmentCache(
            max_entries=100, max_size_mb=0.001, strategy=CacheStrategy.LRU  # 1KB limit
        )

        # Add large entries to trigger size-based eviction
        large_result = CoordinatorResult(
            session_id="sess_large",
            business_id="biz_large",
            total_assessments=1,
            completed_assessments=1,
            failed_assessments=0,
            partial_results={},
            errors={},
            total_cost_usd=Decimal("0"),
            execution_time_ms=0,
            started_at=datetime.utcnow(),
            completed_at=datetime.utcnow(),
        )

        # Add entries until size limit triggers eviction
        for i in range(10):
            await size_cache.put(
                f"biz_large_{i}",
                f"https://large{i}.com",
                [AssessmentType.PAGESPEED],
                large_result,
            )

        stats = size_cache.get_stats()
        # Should have triggered evictions due to size limit
        assert stats.evictions > 0 or stats.entry_count < 10

        await size_cache.close()

        print("✓ Cache size limits work correctly")

    @pytest.mark.asyncio
    async def test_cache_key_generation(self, cache):
        """Test cache key generation consistency"""
        business_id = "biz_test123"
        url1 = "https://example.com"
        url2 = "https://example.com/"  # With trailing slash
        url3 = "HTTPS://EXAMPLE.COM"  # Different case
        assessment_types = [AssessmentType.PAGESPEED, AssessmentType.TECH_STACK]

        # URLs should normalize to same key
        key1 = cache._generate_cache_key(business_id, url1, assessment_types)
        key2 = cache._generate_cache_key(business_id, url2, assessment_types)
        key3 = cache._generate_cache_key(business_id, url3, assessment_types)

        assert key1 == key2 == key3

        # Different order of assessment types should produce same key
        key4 = cache._generate_cache_key(
            business_id, url1, [AssessmentType.TECH_STACK, AssessmentType.PAGESPEED]
        )
        assert key1 == key4

        # Different parameters should produce different keys
        key5 = cache._generate_cache_key(business_id, url1, [AssessmentType.PAGESPEED])
        assert key1 != key5

        print("✓ Cache key generation works correctly")

    @pytest.mark.asyncio
    async def test_cache_cleanup_and_expiration(self, sample_coordinator_result):
        """Test background cleanup and expiration handling"""
        # Create cache with short cleanup interval
        cleanup_cache = AssessmentCache(
            max_entries=10,
            default_ttl_seconds=1,  # 1 second TTL
            cleanup_interval_seconds=2,  # 2 second cleanup
        )

        # Add entry that will expire
        await cleanup_cache.put(
            "biz_expire",
            "https://expire.com",
            [AssessmentType.PAGESPEED],
            sample_coordinator_result,
            ttl_override=1,  # Force 1 second TTL
        )

        assert cleanup_cache.get_stats().entry_count == 1

        # Wait for expiration (increase time to ensure expiry)
        await asyncio.sleep(2.1)

        # Check if entry is expired before cleanup
        cache_entries = list(cleanup_cache._cache.values())
        if cache_entries:
            entry = cache_entries[0]
            assert (
                entry.is_expired
            ), f"Entry should be expired: age={entry.age_seconds}s, ttl={entry.ttl_seconds}s"

        # Manual cleanup check
        await cleanup_cache._cleanup_expired()

        stats = cleanup_cache.get_stats()
        assert stats.entry_count == 0
        assert stats.expired_removals == 1

        await cleanup_cache.close()

        print("✓ Cache cleanup and expiration work correctly")

    @pytest.mark.asyncio
    async def test_cache_manager_singleton(self):
        """Test cache manager singleton pattern"""
        # Get first instance
        cache1 = await CacheManager.get_cache(max_entries=50)

        # Get second instance - should be same
        cache2 = await CacheManager.get_cache(
            max_entries=100
        )  # Different config ignored

        assert cache1 is cache2
        assert cache1.max_entries == 50  # Original config preserved

        # Close and get new instance
        await CacheManager.close_cache()
        cache3 = await CacheManager.get_cache(max_entries=75)

        assert cache3 is not cache1
        assert cache3.max_entries == 75

        await CacheManager.close_cache()

        print("✓ Cache manager singleton works correctly")

    @pytest.mark.asyncio
    async def test_cached_assessment_decorator(self, sample_coordinator_result):
        """Test cached assessment decorator"""
        call_count = 0

        @cached_assessment(ttl_seconds=300, tags={"decorator_test"})
        async def mock_assessment(
            business_id, url, assessment_types, industry="default"
        ):
            nonlocal call_count
            call_count += 1
            return sample_coordinator_result

        # First call - should execute function
        result1 = await mock_assessment(
            "biz_test", "https://test.com", [AssessmentType.PAGESPEED]
        )
        assert result1 == sample_coordinator_result
        assert call_count == 1

        # Second call - should use cache
        result2 = await mock_assessment(
            "biz_test", "https://test.com", [AssessmentType.PAGESPEED]
        )
        assert result2 == sample_coordinator_result
        assert call_count == 1  # Function not called again

        # Different parameters - should execute function again
        result3 = await mock_assessment(
            "biz_test", "https://other.com", [AssessmentType.PAGESPEED]
        )
        assert result3 == sample_coordinator_result
        assert call_count == 2

        await CacheManager.close_cache()

        print("✓ Cached assessment decorator works correctly")

    @pytest.mark.asyncio
    async def test_cache_info_and_debugging(self, cache, sample_coordinator_result):
        """Test cache information and debugging features"""
        # Add some entries
        await cache.put(
            "biz_1",
            "https://site1.com",
            [AssessmentType.PAGESPEED],
            sample_coordinator_result,
        )
        await cache.put(
            "biz_2",
            "https://site2.com",
            [AssessmentType.TECH_STACK],
            sample_coordinator_result,
        )

        # Get cache info
        cache_info = cache.get_cache_info()

        # Verify cache info structure
        assert "stats" in cache_info
        assert "configuration" in cache_info
        assert "metrics" in cache_info
        assert "ttl_configuration" in cache_info

        # Check stats
        assert cache_info["stats"]["entry_count"] == 2
        assert cache_info["stats"]["total_size_bytes"] > 0

        # Check configuration
        assert cache_info["configuration"]["max_entries"] == 10
        assert cache_info["configuration"]["strategy"] == "lru"

        # Check metrics
        assert "hit_rate_percentage" in cache_info["metrics"]
        assert "cache_utilization_percentage" in cache_info["metrics"]

        # Test list entries
        entries = cache.list_entries()
        assert len(entries) == 2
        assert all("key" in entry for entry in entries)
        assert all("business_id" in entry for entry in entries)

        print("✓ Cache info and debugging features work correctly")

    @pytest.mark.asyncio
    async def test_cache_clear_functionality(self, cache, sample_coordinator_result):
        """Test cache clear functionality"""
        # Add entries
        await cache.put(
            "biz_1",
            "https://site1.com",
            [AssessmentType.PAGESPEED],
            sample_coordinator_result,
        )
        await cache.put(
            "biz_2",
            "https://site2.com",
            [AssessmentType.TECH_STACK],
            sample_coordinator_result,
        )

        assert cache.get_stats().entry_count == 2

        # Clear cache
        cleared_count = await cache.clear()

        assert cleared_count == 2
        assert cache.get_stats().entry_count == 0
        assert cache.get_stats().total_size_bytes == 0

        # Stats should be reset
        stats = cache.get_stats()
        assert stats.hits == 0
        assert stats.misses == 0
        assert stats.evictions == 0

        print("✓ Cache clear functionality works correctly")

    @pytest.mark.asyncio
    async def test_comprehensive_cache_flow(self, cache, sample_coordinator_result):
        """Test comprehensive cache workflow"""
        business_id = "biz_comprehensive"
        url = "https://comprehensive-test.com"
        assessment_types = [
            AssessmentType.PAGESPEED,
            AssessmentType.TECH_STACK,
            AssessmentType.AI_INSIGHTS,
        ]
        industry = "technology"

        # Create comprehensive coordinator result with correct business_id
        comprehensive_result = CoordinatorResult(
            session_id="sess_comprehensive",
            business_id=business_id,  # Use the correct business_id
            total_assessments=3,
            completed_assessments=3,
            failed_assessments=0,
            partial_results={
                AssessmentType.PAGESPEED: AssessmentResult(
                    id=str(uuid.uuid4()),
                    business_id=business_id,
                    assessment_type=AssessmentType.PAGESPEED,
                    status=AssessmentStatus.COMPLETED,
                    url=url,
                    domain="comprehensive-test.com",
                    performance_score=88,
                ),
                AssessmentType.TECH_STACK: AssessmentResult(
                    id=str(uuid.uuid4()),
                    business_id=business_id,
                    assessment_type=AssessmentType.TECH_STACK,
                    status=AssessmentStatus.COMPLETED,
                    url=url,
                    domain="comprehensive-test.com",
                    tech_stack_data={"technologies": []},
                ),
                AssessmentType.AI_INSIGHTS: AssessmentResult(
                    id=str(uuid.uuid4()),
                    business_id=business_id,
                    assessment_type=AssessmentType.AI_INSIGHTS,
                    status=AssessmentStatus.COMPLETED,
                    url=url,
                    domain="comprehensive-test.com",
                    ai_insights_data={"insights": {}},
                ),
            },
            errors={},
            total_cost_usd=Decimal("0.50"),
            execution_time_ms=180000,
            started_at=datetime.utcnow() - timedelta(minutes=3),
            completed_at=datetime.utcnow(),
        )

        # 1. Initial miss
        result = await cache.get(business_id, url, assessment_types, industry)
        assert result is None

        # 2. Store result
        cache_key = await cache.put(
            business_id, url, assessment_types, comprehensive_result, industry
        )
        assert cache_key is not None

        # 3. Cache hit
        result = await cache.get(business_id, url, assessment_types, industry)
        assert result is not None
        assert result.business_id == business_id

        # 4. Test different industry (should miss)
        result = await cache.get(business_id, url, assessment_types, "healthcare")
        assert result is None

        # 5. Test invalidation
        removed = await cache.invalidate(
            business_id=business_id,
            url=url,
            assessment_types=assessment_types,
            industry=industry,
        )
        assert removed == 1

        # 6. Verify invalidation
        result = await cache.get(business_id, url, assessment_types, industry)
        assert result is None

        # 7. Check final stats
        stats = cache.get_stats()
        assert stats.hits == 1
        assert stats.misses == 3
        assert stats.hit_rate == 0.25

        print("✓ Comprehensive cache flow works correctly")


# Allow running this test file directly
if __name__ == "__main__":
    import asyncio

    async def run_tests():
        test_instance = TestTask036AcceptanceCriteria()

        print("🗄️ Running Task 036 Assessment Cache Tests...")
        print()

        try:
            # Setup
            test_instance.setup_method()

            # Create fixtures manually for direct execution
            cache = AssessmentCache(
                max_entries=10,
                default_ttl_seconds=300,
                max_size_mb=1,
                strategy=CacheStrategy.LRU,
                cleanup_interval_seconds=60,
            )

            sample_coordinator_result = CoordinatorResult(
                session_id="sess_test123",
                business_id="biz_test123",
                total_assessments=2,
                completed_assessments=2,
                failed_assessments=0,
                partial_results={
                    AssessmentType.PAGESPEED: AssessmentResult(
                        id=str(uuid.uuid4()),
                        business_id="biz_test123",
                        assessment_type=AssessmentType.PAGESPEED,
                        status=AssessmentStatus.COMPLETED,
                        url="https://example.com",
                        domain="example.com",
                        performance_score=85,
                    )
                },
                errors={},
                total_cost_usd=Decimal("0.25"),
                execution_time_ms=120000,
                started_at=datetime.utcnow() - timedelta(minutes=2),
                completed_at=datetime.utcnow(),
            )

            # Run all acceptance criteria tests
            await test_instance.test_recent_assessments_cached(
                cache, sample_coordinator_result
            )
            await test_instance.test_ttl_configuration_works(
                cache, sample_coordinator_result
            )
            await test_instance.test_cache_invalidation_logic(
                cache, sample_coordinator_result
            )
            await test_instance.test_hit_rate_tracking(cache, sample_coordinator_result)

            # Run additional functionality tests
            await test_instance.test_cache_eviction_strategies(
                sample_coordinator_result
            )
            await test_instance.test_cache_size_limits(sample_coordinator_result)
            await test_instance.test_cache_key_generation(cache)
            await test_instance.test_cache_cleanup_and_expiration(
                sample_coordinator_result
            )
            await test_instance.test_cache_manager_singleton()
            await test_instance.test_cached_assessment_decorator(
                sample_coordinator_result
            )
            await test_instance.test_cache_info_and_debugging(
                cache, sample_coordinator_result
            )
            await test_instance.test_cache_clear_functionality(
                cache, sample_coordinator_result
            )
            await test_instance.test_comprehensive_cache_flow(
                cache, sample_coordinator_result
            )

            print()
            print("🎉 All Task 036 acceptance criteria tests pass!")
            print("   - Recent assessments cached: ✓")
            print("   - TTL configuration works: ✓")
            print("   - Cache invalidation logic: ✓")
            print("   - Hit rate tracking: ✓")

            # Cleanup
            await cache.close()

        except Exception as e:
            print(f"❌ Test failed: {e}")
            import traceback

            traceback.print_exc()

    # Run async tests
    asyncio.run(run_tests())
