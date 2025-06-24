"""
Yelp Scraper with Pagination - Task 026

Handles business data scraping from Yelp API with intelligent pagination,
quota enforcement, error recovery, and result limiting.

Acceptance Criteria:
- Pagination handled correctly
- 1000 result limit respected
- Batch quota enforcement
- Error recovery works
"""
import asyncio
import json
import logging
import time
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, Generator, List, Optional, Tuple

from sqlalchemy.orm import Session

from core.config import get_settings
from core.logging import get_logger
from d0_gateway.facade import get_gateway_facade
from database.session import SessionLocal

from .exceptions import (
    BatchQuotaException,
    ErrorRecoveryException,
    NetworkException,
    PaginationException,
    YelpAPIException,
    YelpAuthenticationException,
    YelpBusinessNotFoundException,
    YelpQuotaExceededException,
    YelpRateLimitException,
)
from .models import SourcedLocation, YelpMetadata


class ScrapingStatus(Enum):
    """Status of scraping operations"""

    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    QUOTA_EXCEEDED = "quota_exceeded"
    RATE_LIMITED = "rate_limited"


@dataclass
class ScrapingResult:
    """Result of a scraping operation"""

    status: ScrapingStatus
    total_results: int
    fetched_count: int
    error_count: int
    quota_used: int
    duration_seconds: float
    error_message: Optional[str] = None
    businesses: List[Dict[str, Any]] = None

    def __post_init__(self):
        if self.businesses is None:
            self.businesses = []


@dataclass
class PaginationState:
    """Track pagination state across requests"""

    offset: int = 0
    limit: int = 50
    total_results: int = 0
    current_page: int = 1
    has_more: bool = True
    last_request_time: Optional[datetime] = None


class YelpScraper:
    """
    Yelp business data scraper with pagination, quota management, and error recovery

    Handles the complexity of Yelp's pagination system while respecting rate limits,
    quota constraints, and implementing robust error recovery mechanisms.
    """

    # Yelp API Constants
    MAX_RESULTS_PER_REQUEST = 50
    YELP_MAX_RESULTS = 1000  # Yelp's hard limit
    MAX_RETRIES = 3
    BACKOFF_MULTIPLIER = 2

    def __init__(self, session: Optional[Session] = None):
        """Initialize the Yelp scraper"""
        self.settings = get_settings()
        self.logger = get_logger("yelp_scraper", domain="d2")
        self.session = session or SessionLocal()

        # Gateway facade for all external API calls
        self.gateway = get_gateway_facade()

        # Quota tracking
        self.daily_quota_limit = self._get_daily_quota_limit()
        self.batch_quota_limit = self._get_batch_quota_limit()
        self.current_quota_usage = 0

        # Error recovery state
        self.consecutive_errors = 0
        self.last_error_time = None

    def _get_daily_quota_limit(self) -> int:
        """Get daily quota limit from configuration"""
        return getattr(self.settings, "YELP_DAILY_QUOTA", 5000)

    def _get_batch_quota_limit(self) -> int:
        """Get per-batch quota limit from configuration"""
        return getattr(self.settings, "YELP_BATCH_QUOTA", 1000)

    def check_quota_availability(self, requested_results: int) -> bool:
        """
        Check if we have enough quota for the requested number of results

        Acceptance Criteria: Batch quota enforcement
        """
        # Check daily quota
        daily_usage = self._get_current_daily_usage()
        if daily_usage + requested_results > self.daily_quota_limit:
            raise YelpQuotaExceededException(
                f"Daily quota would be exceeded: {daily_usage + requested_results} > {self.daily_quota_limit}",
                quota_type="daily",
            )

        # Check batch quota
        if self.current_quota_usage + requested_results > self.batch_quota_limit:
            raise BatchQuotaException(
                f"Batch quota would be exceeded",
                current_usage=self.current_quota_usage,
                limit=self.batch_quota_limit,
            )

        return True

    def _get_current_daily_usage(self) -> int:
        """Get current daily API usage from database"""
        today = datetime.utcnow().date()
        try:
            # Count requests made today
            usage = (
                self.session.query(YelpMetadata)
                .filter(YelpMetadata.response_timestamp >= today)
                .count()
            )
            return usage
        except Exception as e:
            self.logger.warning(f"Could not fetch daily usage: {e}")
            return 0

    async def search_businesses(
        self,
        location: str,
        term: Optional[str] = None,
        categories: Optional[List[str]] = None,
        max_results: int = 1000,
        **search_params,
    ) -> ScrapingResult:
        """
        Search for businesses with pagination handling

        Acceptance Criteria:
        - Pagination handled correctly
        - 1000 result limit respected
        - Batch quota enforcement
        - Error recovery works
        """
        start_time = time.time()

        # Enforce Yelp's 1000 result limit
        max_results = min(max_results, self.YELP_MAX_RESULTS)

        # Check quota before starting
        self.check_quota_availability(max_results)

        self.logger.info(
            f"Starting Yelp search: location='{location}', max_results={max_results}"
        )

        result = ScrapingResult(
            status=ScrapingStatus.IN_PROGRESS,
            total_results=0,
            fetched_count=0,
            error_count=0,
            quota_used=0,
            duration_seconds=0.0,
        )

        try:
            # Initialize pagination state
            pagination = PaginationState(limit=self.MAX_RESULTS_PER_REQUEST)

            # Collect all businesses across pages
            all_businesses = []

            while pagination.has_more and len(all_businesses) < max_results:
                # Calculate remaining results needed
                remaining_needed = max_results - len(all_businesses)
                current_limit = min(pagination.limit, remaining_needed)

                # Perform paginated search
                page_result = await self._search_page(
                    location=location,
                    term=term,
                    categories=categories,
                    offset=pagination.offset,
                    limit=current_limit,
                    **search_params,
                )

                # Update result tracking
                result.quota_used += 1
                self.current_quota_usage += 1

                if page_result.get("error"):
                    result.error_count += 1
                    self.logger.error(f"Page error: {page_result['error']}")

                    # Try error recovery
                    if not await self._handle_error_recovery(page_result["error"]):
                        break
                    continue

                # Process successful page
                businesses = page_result.get("businesses", [])
                total = page_result.get("total", 0)

                # Update pagination state
                pagination.total_results = total
                pagination.offset += len(businesses)
                pagination.has_more = (
                    len(businesses) == current_limit
                    and pagination.offset < total
                    and pagination.offset < self.YELP_MAX_RESULTS
                )

                # Add businesses to results
                all_businesses.extend(businesses)
                result.fetched_count = len(all_businesses)

                self.logger.info(
                    f"Fetched page: offset={pagination.offset - len(businesses)}, "
                    f"count={len(businesses)}, total_so_far={len(all_businesses)}"
                )

                # Respect 1000 result limit
                if len(all_businesses) >= self.YELP_MAX_RESULTS:
                    self.logger.info(f"Reached Yelp's 1000 result limit")
                    break

            # Finalize result
            result.businesses = all_businesses
            result.total_results = pagination.total_results
            result.status = ScrapingStatus.COMPLETED
            result.duration_seconds = time.time() - start_time

            self.logger.info(
                f"Search completed: fetched={result.fetched_count}, "
                f"total_available={result.total_results}, quota_used={result.quota_used}"
            )

            return result

        except YelpQuotaExceededException as e:
            result.status = ScrapingStatus.QUOTA_EXCEEDED
            result.error_message = str(e)
            result.duration_seconds = time.time() - start_time
            self.logger.error(f"Quota exceeded: {e}")
            return result

        except YelpRateLimitException as e:
            result.status = ScrapingStatus.RATE_LIMITED
            result.error_message = str(e)
            result.duration_seconds = time.time() - start_time
            self.logger.error(f"Rate limited: {e}")
            return result

        except Exception as e:
            result.status = ScrapingStatus.FAILED
            result.error_message = str(e)
            result.duration_seconds = time.time() - start_time
            self.logger.error(f"Search failed: {e}")
            return result

    async def _search_page(
        self,
        location: str,
        offset: int,
        limit: int,
        term: Optional[str] = None,
        categories: Optional[List[str]] = None,
        **search_params,
    ) -> Dict[str, Any]:
        """
        Fetch a single page of search results

        Acceptance Criteria: Pagination handled correctly
        """
        # Make API request with retry logic
        for attempt in range(self.MAX_RETRIES):
            try:
                # Use gateway for Yelp API call
                data = await self.gateway.search_businesses(
                    term=term,
                    location=location,
                    categories=",".join(categories) if categories else None,
                    limit=limit,
                    offset=offset,
                    **search_params,
                )

                self.consecutive_errors = 0  # Reset error counter
                return data

            except Exception as e:
                self.consecutive_errors += 1

                # Check for specific error types from gateway
                error_msg = str(e).lower()
                if "rate limit" in error_msg:
                    # Extract retry after if available
                    retry_after = 60  # Default to 60 seconds
                    raise YelpRateLimitException(retry_after=retry_after)
                elif "quota" in error_msg:
                    raise YelpQuotaExceededException()
                elif "authentication" in error_msg or "unauthorized" in error_msg:
                    raise YelpAuthenticationException()
                elif "not found" in error_msg:
                    return {"businesses": [], "total": 0}

                if attempt == self.MAX_RETRIES - 1:
                    raise NetworkException(
                        f"API error after {self.MAX_RETRIES} attempts: {e}"
                    )

                # Exponential backoff
                await asyncio.sleep(self.BACKOFF_MULTIPLIER**attempt)

    async def _handle_error_recovery(self, error: Exception) -> bool:
        """
        Handle error recovery with exponential backoff

        Acceptance Criteria: Error recovery works
        """
        self.consecutive_errors += 1
        self.last_error_time = datetime.utcnow()

        # Determine if we should retry
        if isinstance(error, YelpRateLimitException):
            if hasattr(error, "retry_after") and error.retry_after:
                wait_time = error.retry_after
            else:
                wait_time = min(60, self.BACKOFF_MULTIPLIER**self.consecutive_errors)

            self.logger.info(f"Rate limited, waiting {wait_time} seconds")
            await asyncio.sleep(wait_time)
            return True

        elif isinstance(
            error, (YelpQuotaExceededException, YelpAuthenticationException)
        ):
            # Non-recoverable errors
            return False

        elif isinstance(error, NetworkException):
            if self.consecutive_errors < self.MAX_RETRIES:
                wait_time = self.BACKOFF_MULTIPLIER**self.consecutive_errors
                self.logger.info(
                    f"Network error #{self.consecutive_errors}, retrying in {wait_time}s"
                )
                await asyncio.sleep(wait_time)
                return True
            return False

        elif self.consecutive_errors < self.MAX_RETRIES:
            # Generic retry with backoff
            wait_time = self.BACKOFF_MULTIPLIER**self.consecutive_errors
            self.logger.info(
                f"Error #{self.consecutive_errors}, retrying in {wait_time}s: {error}"
            )
            await asyncio.sleep(wait_time)
            return True

        return False

    async def get_business_details(self, business_id: str) -> Dict[str, Any]:
        """
        Get detailed information for a specific business

        Includes error recovery and quota tracking
        """
        self.check_quota_availability(1)

        for attempt in range(self.MAX_RETRIES):
            try:
                # Use gateway for Yelp API call
                data = await self.gateway.get_business_details(business_id)
                self.current_quota_usage += 1
                return data

            except Exception as e:
                error_msg = str(e).lower()
                if "not found" in error_msg:
                    raise YelpBusinessNotFoundException(business_id)
                elif "rate limit" in error_msg:
                    retry_after = 60  # Default to 60 seconds
                    raise YelpRateLimitException(retry_after=retry_after)
                elif "authentication" in error_msg or "unauthorized" in error_msg:
                    raise YelpAuthenticationException()

                if attempt == self.MAX_RETRIES - 1:
                    raise NetworkException(f"Failed to get business details: {e}")
                await asyncio.sleep(self.BACKOFF_MULTIPLIER**attempt)

    async def save_business_data(self, business_data: Dict[str, Any]) -> str:
        """Save business data to database with metadata tracking"""
        try:
            # Create or update business record
            # This would integrate with the Business model and deduplication logic
            business_id = str(uuid.uuid4())

            # Create Yelp metadata record
            yelp_metadata = YelpMetadata(
                business_id=business_id,
                yelp_url=business_data.get("url"),
                photos=business_data.get("photos", []),
                raw_response=business_data,
                api_version="v3",
                completeness_score=self._calculate_completeness_score(business_data),
                freshness_score=1.0,  # Newly fetched
                accuracy_score=0.95,  # Default high accuracy for Yelp
            )

            self.session.add(yelp_metadata)
            self.session.commit()

            return business_id

        except Exception as e:
            self.session.rollback()
            self.logger.error(f"Failed to save business data: {e}")
            raise

    def _calculate_completeness_score(self, business_data: Dict[str, Any]) -> float:
        """Calculate data completeness score based on available fields"""
        required_fields = ["name", "location", "phone", "categories"]
        optional_fields = ["url", "hours", "price", "rating", "review_count"]

        required_score = sum(
            1 for field in required_fields if business_data.get(field)
        ) / len(required_fields)
        optional_score = sum(
            1 for field in optional_fields if business_data.get(field)
        ) / len(optional_fields)

        # Weight required fields more heavily
        return (required_score * 0.7) + (optional_score * 0.3)

    def get_pagination_generator(
        self, location: str, max_results: int = 1000, **search_params
    ) -> Generator[Tuple[int, List[Dict[str, Any]]], None, None]:
        """
        Generator for paginated results - useful for streaming large datasets

        Yields tuples of (offset, businesses) for each page
        """
        # This would be a sync wrapper around the async pagination
        # For now, providing the interface structure
        offset = 0
        limit = self.MAX_RESULTS_PER_REQUEST

        while offset < max_results and offset < self.YELP_MAX_RESULTS:
            # In a real implementation, this would use asyncio.run()
            # or be called from an async context
            businesses = []  # Placeholder for sync implementation

            if not businesses:
                break

            yield offset, businesses
            offset += len(businesses)

    def get_scraping_stats(self) -> Dict[str, Any]:
        """Get current scraping session statistics"""
        return {
            "quota_used": self.current_quota_usage,
            "daily_quota_limit": self.daily_quota_limit,
            "batch_quota_limit": self.batch_quota_limit,
            "consecutive_errors": self.consecutive_errors,
            "last_error_time": self.last_error_time,
        }


# Convenience functions for common use cases


async def scrape_businesses_by_location(
    location: str, categories: Optional[List[str]] = None, max_results: int = 1000
) -> ScrapingResult:
    """
    Convenience function to scrape businesses by location

    Handles all the setup and teardown automatically
    """
    scraper = YelpScraper()

    return await scraper.search_businesses(
        location=location, categories=categories, max_results=max_results
    )


async def scrape_businesses_by_term(
    term: str, location: str, max_results: int = 1000
) -> ScrapingResult:
    """
    Convenience function to scrape businesses by search term

    Handles all the setup and teardown automatically
    """
    scraper = YelpScraper()

    return await scraper.search_businesses(
        location=location, term=term, max_results=max_results
    )
