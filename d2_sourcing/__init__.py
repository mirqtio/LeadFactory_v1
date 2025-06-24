"""
D2 Sourcing - Yelp data acquisition with deduplication

Handles business data sourcing from Yelp API with intelligent deduplication,
data normalization, and quality scoring.
"""

from database.models import Business

from .coordinator import (
    BatchStatus,
    CoordinatorMetrics,
    CoordinatorStatus,
    SourcingBatch,
    SourcingCoordinator,
    process_location_batch,
    process_multiple_locations,
)
from .deduplicator import (
    BusinessDeduplicator,
    DuplicateMatch,
    MatchConfidence,
    MergeResult,
    MergeStrategy,
    detect_duplicates_only,
    find_and_merge_duplicates,
)
from .exceptions import (
    BatchQuotaException,
    DeduplicationException,
    ErrorRecoveryException,
    PaginationException,
    SourcingException,
    YelpAPIException,
    YelpQuotaExceededException,
    YelpRateLimitException,
)
from .models import SourcedLocation, YelpMetadata
from .yelp_scraper import (
    ScrapingResult,
    ScrapingStatus,
    YelpScraper,
    scrape_businesses_by_location,
    scrape_businesses_by_term,
)

__all__ = [
    # Models
    "Business",
    "YelpMetadata",
    "SourcedLocation",
    # Scraper
    "YelpScraper",
    "ScrapingResult",
    "ScrapingStatus",
    "scrape_businesses_by_location",
    "scrape_businesses_by_term",
    # Deduplicator
    "BusinessDeduplicator",
    "DuplicateMatch",
    "MergeResult",
    "MatchConfidence",
    "MergeStrategy",
    "find_and_merge_duplicates",
    "detect_duplicates_only",
    # Coordinator
    "SourcingCoordinator",
    "SourcingBatch",
    "CoordinatorStatus",
    "BatchStatus",
    "CoordinatorMetrics",
    "process_location_batch",
    "process_multiple_locations",
    # Exceptions
    "SourcingException",
    "YelpAPIException",
    "YelpRateLimitException",
    "YelpQuotaExceededException",
    "BatchQuotaException",
    "PaginationException",
    "ErrorRecoveryException",
    "DeduplicationException",
]
