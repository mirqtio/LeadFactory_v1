"""
D2 Sourcing - Yelp data acquisition with deduplication

Handles business data sourcing from Yelp API with intelligent deduplication,
data normalization, and quality scoring.
"""

from database.models import Business
from .models import YelpMetadata, SourcedLocation
from .yelp_scraper import YelpScraper, ScrapingResult, ScrapingStatus, scrape_businesses_by_location, scrape_businesses_by_term
from .deduplicator import BusinessDeduplicator, DuplicateMatch, MergeResult, MatchConfidence, MergeStrategy, find_and_merge_duplicates, detect_duplicates_only
from .exceptions import (
    SourcingException,
    YelpAPIException, 
    YelpRateLimitException,
    YelpQuotaExceededException,
    BatchQuotaException,
    PaginationException,
    ErrorRecoveryException,
    DeduplicationException
)

__all__ = [
    # Models
    'Business',
    'YelpMetadata', 
    'SourcedLocation',
    # Scraper
    'YelpScraper',
    'ScrapingResult',
    'ScrapingStatus',
    'scrape_businesses_by_location',
    'scrape_businesses_by_term',
    # Deduplicator
    'BusinessDeduplicator',
    'DuplicateMatch',
    'MergeResult',
    'MatchConfidence',
    'MergeStrategy',
    'find_and_merge_duplicates',
    'detect_duplicates_only',
    # Exceptions
    'SourcingException',
    'YelpAPIException',
    'YelpRateLimitException', 
    'YelpQuotaExceededException',
    'BatchQuotaException',
    'PaginationException',
    'ErrorRecoveryException',
    'DeduplicationException'
]