"""
D2 Sourcing - Yelp data acquisition with deduplication

Handles business data sourcing from Yelp API with intelligent deduplication,
data normalization, and quality scoring.
"""

from database.models import Business
from .models import YelpMetadata, SourcedLocation
from .yelp_scraper import YelpScraper, ScrapingResult, ScrapingStatus, scrape_businesses_by_location, scrape_businesses_by_term
from .exceptions import (
    SourcingException,
    YelpAPIException, 
    YelpRateLimitException,
    YelpQuotaExceededException,
    BatchQuotaException,
    PaginationException,
    ErrorRecoveryException
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
    # Exceptions
    'SourcingException',
    'YelpAPIException',
    'YelpRateLimitException', 
    'YelpQuotaExceededException',
    'BatchQuotaException',
    'PaginationException',
    'ErrorRecoveryException'
]