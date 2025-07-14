"""
D2 Sourcing - Business data acquisition with deduplication

Handles business data sourcing with intelligent deduplication,
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
)
from .models import SourcedLocation

# from .yelp_scraper import (
#     ScrapingResult,
#     ScrapingStatus,
#     YelpScraper,
#     scrape_businesses_by_location,
#     scrape_businesses_by_term,
# )  # Yelp removed per P0-009

__all__ = [
    # Models
    "Business",
    "SourcedLocation",
    # Scraper - removed per P0-009
    # "YelpScraper",
    # "ScrapingResult",
    # "ScrapingStatus",
    # "scrape_businesses_by_location",
    # "scrape_businesses_by_term",
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
    "BatchQuotaException",
    "PaginationException",
    "ErrorRecoveryException",
    "DeduplicationException",
]
