"""
D4 Enrichment Domain - Task 040

Data enrichment services for businesses discovered through D2 sourcing.
Adds additional business information from external sources.

Components:
- Models: Data structures for enrichment results
- External APIs: Integration with enrichment services
- Data validation: Quality checks for enriched data
- Source attribution: Track data provenance
"""

from .models import (
    EnrichmentResult,
    EnrichmentRequest,
    EnrichmentSource,
    MatchConfidence,
    DataVersion
)

__all__ = [
    "EnrichmentResult",
    "EnrichmentRequest",
    "EnrichmentSource",
    "MatchConfidence",
    "DataVersion"
]
