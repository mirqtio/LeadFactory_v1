"""
Business Deduplicator - Task 027

Implements intelligent business deduplication with fuzzy matching, merge logic,
and performance optimization for large datasets.

Acceptance Criteria:
- Duplicate detection works
- Merge logic correct
- Update timestamps properly
- Performance optimized
"""
import time
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime
from difflib import SequenceMatcher
from enum import Enum
from typing import Any, Dict, List, Optional, Set

from sqlalchemy import and_, or_
from sqlalchemy.orm import Session

from core.config import get_settings
from core.logging import get_logger
from database.models import Business
from database.session import SessionLocal

from .exceptions import DeduplicationException
from .models import SourcedLocation


class MatchConfidence(Enum):
    """Confidence levels for duplicate matches"""

    EXACT = "exact"  # 100% match
    HIGH = "high"  # 90-99% match
    MEDIUM = "medium"  # 70-89% match
    LOW = "low"  # 50-69% match
    NO_MATCH = "no_match"  # <50% match


class MergeStrategy(Enum):
    """Strategies for merging duplicate businesses"""

    KEEP_NEWEST = "keep_newest"
    KEEP_OLDEST = "keep_oldest"
    KEEP_MOST_COMPLETE = "keep_most_complete"
    KEEP_HIGHEST_RATED = "keep_highest_rated"
    MANUAL_REVIEW = "manual_review"


@dataclass
class DuplicateMatch:
    """Represents a potential duplicate match between two businesses"""

    business_1_id: str
    business_2_id: str
    confidence: MatchConfidence
    confidence_score: float
    match_reasons: List[str]
    distance_meters: Optional[float] = None
    name_similarity: float = 0.0
    phone_similarity: float = 0.0
    address_similarity: float = 0.0
    detected_at: datetime = None

    def __post_init__(self):
        if self.detected_at is None:
            self.detected_at = datetime.utcnow()


@dataclass
class MergeResult:
    """Result of a business merge operation"""

    primary_business_id: str
    merged_business_ids: List[str]
    merge_strategy: MergeStrategy
    merge_timestamp: datetime
    fields_merged: Dict[str, Any]
    conflicts_resolved: List[str]
    metadata_preserved: bool = True

    def __post_init__(self):
        if self.merge_timestamp is None:
            self.merge_timestamp = datetime.utcnow()


class BusinessDeduplicator:
    """
    Intelligent business deduplication system

    Provides fuzzy matching, confidence scoring, and automated/manual merge
    capabilities for business records from multiple sources.
    """

    # Matching thresholds
    EXACT_MATCH_THRESHOLD = 1.0
    HIGH_CONFIDENCE_THRESHOLD = 0.9
    MEDIUM_CONFIDENCE_THRESHOLD = 0.7
    LOW_CONFIDENCE_THRESHOLD = 0.5

    # Performance optimization settings
    BATCH_SIZE = 1000
    MAX_DISTANCE_METERS = 500  # Only compare businesses within 500m

    def __init__(self, session: Optional[Session] = None):
        """Initialize the business deduplicator"""
        self.settings = get_settings()
        self.logger = get_logger("business_deduplicator", domain="d2")
        self.session = session or SessionLocal()

        # Performance tracking
        self.processed_count = 0
        self.duplicates_found = 0
        self.merges_performed = 0
        self.start_time = None

        # Caching for performance
        self._business_cache = {}
        self._similarity_cache = {}

    def find_duplicates(
        self,
        business_ids: Optional[List[str]] = None,
        limit: Optional[int] = None,
        confidence_threshold: float = MEDIUM_CONFIDENCE_THRESHOLD,
    ) -> List[DuplicateMatch]:
        """
        Find potential duplicate businesses

        Acceptance Criteria: Duplicate detection works
        """
        self.start_time = time.time()
        self.logger.info(
            f"Starting duplicate detection with threshold {confidence_threshold}"
        )

        duplicates = []

        try:
            # Get businesses to process
            businesses = self._get_businesses_for_deduplication(business_ids, limit)
            self.logger.info(f"Processing {len(businesses)} businesses for duplicates")

            # Process in batches for performance
            for i in range(0, len(businesses), self.BATCH_SIZE):
                batch = businesses[i : i + self.BATCH_SIZE]
                batch_duplicates = self._find_duplicates_in_batch(
                    batch, confidence_threshold
                )
                duplicates.extend(batch_duplicates)

                self.processed_count += len(batch)
                if self.processed_count % 5000 == 0:
                    self.logger.info(
                        f"Processed {self.processed_count} businesses, found {len(duplicates)} duplicates"
                    )

            # Sort by confidence score (highest first)
            duplicates.sort(key=lambda x: x.confidence_score, reverse=True)

            self.duplicates_found = len(duplicates)
            elapsed = time.time() - self.start_time

            self.logger.info(
                f"Duplicate detection completed: {self.duplicates_found} duplicates found "
                f"in {elapsed:.2f}s ({self.processed_count/elapsed:.1f} businesses/sec)"
            )

            return duplicates

        except Exception as e:
            self.logger.error(f"Error in duplicate detection: {e}")
            raise DeduplicationException(f"Duplicate detection failed: {e}")

    def _get_businesses_for_deduplication(
        self, business_ids: Optional[List[str]] = None, limit: Optional[int] = None
    ) -> List[Business]:
        """Get businesses that need deduplication processing"""
        query = self.session.query(Business)

        if business_ids:
            query = query.filter(Business.id.in_(business_ids))

        # Only process businesses with sufficient data
        query = query.filter(
            and_(
                Business.name.isnot(None),
                or_(Business.address.isnot(None), Business.phone.isnot(None)),
            )
        )

        if limit:
            query = query.limit(limit)

        return query.all()

    def _find_duplicates_in_batch(
        self, businesses: List[Business], confidence_threshold: float
    ) -> List[DuplicateMatch]:
        """Find duplicates within a batch of businesses"""
        duplicates = []

        # Create spatial index for performance optimization
        businesses_by_location = self._group_by_approximate_location(businesses)

        for i, business1 in enumerate(businesses):
            # Only compare with businesses in nearby locations for performance
            nearby_businesses = self._get_nearby_businesses(
                business1, businesses_by_location, businesses[i + 1 :]
            )

            for business2 in nearby_businesses:
                if business1.id >= business2.id:  # Avoid duplicate comparisons
                    continue

                match = self._calculate_match_confidence(business1, business2)

                if match.confidence_score >= confidence_threshold:
                    duplicates.append(match)

        return duplicates

    def _group_by_approximate_location(
        self, businesses: List[Business]
    ) -> Dict[str, List[Business]]:
        """Group businesses by approximate location for spatial optimization"""
        # Acceptance Criteria: Performance optimized
        groups = defaultdict(list)

        for business in businesses:
            if business.latitude and business.longitude:
                # Create spatial grid key (roughly 1km grid cells)
                lat_key = int(business.latitude * 100)  # ~1.1km at equator
                lng_key = int(business.longitude * 100)
                grid_key = f"{lat_key},{lng_key}"
                groups[grid_key].append(business)
            else:
                # Fallback for businesses without coordinates
                groups["no_location"].append(business)

        return groups

    def _get_nearby_businesses(
        self,
        target_business: Business,
        businesses_by_location: Dict[str, List[Business]],
        remaining_businesses: List[Business],
    ) -> List[Business]:
        """Get businesses that are geographically nearby for comparison"""
        if not target_business.latitude or not target_business.longitude:
            # No location data, compare with all remaining businesses
            return remaining_businesses

        nearby = []
        target_lat_key = int(target_business.latitude * 100)
        target_lng_key = int(target_business.longitude * 100)

        # Check current grid cell and adjacent cells
        for lat_offset in [-1, 0, 1]:
            for lng_offset in [-1, 0, 1]:
                grid_key = (
                    f"{target_lat_key + lat_offset},{target_lng_key + lng_offset}"
                )
                if grid_key in businesses_by_location:
                    nearby.extend(businesses_by_location[grid_key])

        # Filter to only businesses in remaining list and within distance threshold
        filtered_nearby = []
        for business in nearby:
            if business in remaining_businesses:
                distance = self._calculate_distance(target_business, business)
                if distance is None or distance <= self.MAX_DISTANCE_METERS:
                    filtered_nearby.append(business)

        return filtered_nearby

    def _calculate_match_confidence(
        self, business1: Business, business2: Business
    ) -> DuplicateMatch:
        """
        Calculate confidence that two businesses are duplicates

        Acceptance Criteria: Duplicate detection works
        """
        # Use cache to avoid recalculating same pairs
        cache_key = (
            f"{min(business1.id, business2.id)}:{max(business1.id, business2.id)}"
        )
        if cache_key in self._similarity_cache:
            return self._similarity_cache[cache_key]

        match_reasons = []
        scores = {}

        # Name similarity (most important factor)
        name_sim = self._calculate_name_similarity(business1.name, business2.name)
        scores["name"] = name_sim
        if name_sim > 0.8:
            match_reasons.append(f"Similar names ({name_sim:.2f})")

        # Phone similarity
        phone_sim = self._calculate_phone_similarity(business1.phone, business2.phone)
        scores["phone"] = phone_sim
        if phone_sim > 0.9:
            match_reasons.append(f"Similar phones ({phone_sim:.2f})")

        # Address similarity
        address_sim = self._calculate_address_similarity(
            business1.address, business2.address
        )
        scores["address"] = address_sim
        if address_sim > 0.7:
            match_reasons.append(f"Similar addresses ({address_sim:.2f})")

        # Geographic distance
        distance = self._calculate_distance(business1, business2)
        if distance is not None and distance < 50:  # Very close
            match_reasons.append(f"Very close distance ({distance:.0f}m)")

        # Website similarity
        website_sim = self._calculate_website_similarity(
            business1.website, business2.website
        )
        if website_sim > 0.9:
            match_reasons.append(f"Similar websites ({website_sim:.2f})")

        # Calculate overall confidence score
        confidence_score = self._calculate_overall_confidence(scores, distance)

        # Determine confidence level
        if confidence_score >= self.EXACT_MATCH_THRESHOLD:
            confidence = MatchConfidence.EXACT
        elif confidence_score >= self.HIGH_CONFIDENCE_THRESHOLD:
            confidence = MatchConfidence.HIGH
        elif confidence_score >= self.MEDIUM_CONFIDENCE_THRESHOLD:
            confidence = MatchConfidence.MEDIUM
        elif confidence_score >= self.LOW_CONFIDENCE_THRESHOLD:
            confidence = MatchConfidence.LOW
        else:
            confidence = MatchConfidence.NO_MATCH

        match = DuplicateMatch(
            business_1_id=business1.id,
            business_2_id=business2.id,
            confidence=confidence,
            confidence_score=confidence_score,
            match_reasons=match_reasons,
            distance_meters=distance,
            name_similarity=name_sim,
            phone_similarity=phone_sim,
            address_similarity=address_sim,
        )

        # Cache the result
        self._similarity_cache[cache_key] = match

        return match

    def _calculate_name_similarity(
        self, name1: Optional[str], name2: Optional[str]
    ) -> float:
        """Calculate similarity between business names"""
        if not name1 or not name2:
            return 0.0

        # Normalize names
        norm1 = self._normalize_business_name(name1)
        norm2 = self._normalize_business_name(name2)

        if norm1 == norm2:
            return 1.0

        # Use sequence matcher for fuzzy matching
        return SequenceMatcher(None, norm1, norm2).ratio()

    def _normalize_business_name(self, name: str) -> str:
        """Normalize business name for comparison"""
        if not name:
            return ""

        # Convert to lowercase and remove common business suffixes/prefixes
        normalized = name.lower().strip()

        # Remove common business entity types
        suffixes = ["llc", "inc", "corp", "ltd", "co", "company", "corporation"]
        for suffix in suffixes:
            if normalized.endswith(f" {suffix}"):
                normalized = normalized[: -len(suffix) - 1].strip()

        # Remove common punctuation and extra spaces
        import re

        normalized = re.sub(r"[^\w\s]", " ", normalized)
        normalized = re.sub(r"\s+", " ", normalized).strip()

        return normalized

    def _calculate_phone_similarity(
        self, phone1: Optional[str], phone2: Optional[str]
    ) -> float:
        """Calculate similarity between phone numbers"""
        if not phone1 or not phone2:
            return 0.0

        # Normalize phone numbers (remove formatting)
        norm1 = "".join(filter(str.isdigit, phone1))
        norm2 = "".join(filter(str.isdigit, phone2))

        if not norm1 or not norm2:
            return 0.0

        if norm1 == norm2:
            return 1.0

        # Check if one is a subset of the other (different formatting)
        if norm1 in norm2 or norm2 in norm1:
            return 0.9

        return 0.0

    def _calculate_address_similarity(
        self, addr1: Optional[str], addr2: Optional[str]
    ) -> float:
        """Calculate similarity between addresses"""
        if not addr1 or not addr2:
            return 0.0

        # Normalize addresses
        norm1 = self._normalize_address(addr1)
        norm2 = self._normalize_address(addr2)

        if norm1 == norm2:
            return 1.0

        return SequenceMatcher(None, norm1, norm2).ratio()

    def _normalize_address(self, address: str) -> str:
        """Normalize address for comparison"""
        if not address:
            return ""

        import re

        normalized = address.lower().strip()

        # Replace common abbreviations
        replacements = {
            r"\bst\b": "street",
            r"\bave\b": "avenue",
            r"\brd\b": "road",
            r"\bdr\b": "drive",
            r"\bblvd\b": "boulevard",
            r"\bln\b": "lane",
            r"\bct\b": "court",
            r"\bpl\b": "place",
            r"\bapt\b": "apartment",
            r"\bste\b": "suite",
            r"\bfl\b": "floor",
        }

        for pattern, replacement in replacements.items():
            normalized = re.sub(pattern, replacement, normalized)

        # Remove punctuation and normalize spaces
        normalized = re.sub(r"[^\w\s]", " ", normalized)
        normalized = re.sub(r"\s+", " ", normalized).strip()

        return normalized

    def _calculate_distance(
        self, business1: Business, business2: Business
    ) -> Optional[float]:
        """Calculate distance between two businesses in meters"""
        if not all(
            [
                business1.latitude,
                business1.longitude,
                business2.latitude,
                business2.longitude,
            ]
        ):
            return None

        # Use Haversine formula for great circle distance
        import math

        lat1, lng1 = math.radians(business1.latitude), math.radians(business1.longitude)
        lat2, lng2 = math.radians(business2.latitude), math.radians(business2.longitude)

        dlat = lat2 - lat1
        dlng = lng2 - lng1

        a = (
            math.sin(dlat / 2) ** 2
            + math.cos(lat1) * math.cos(lat2) * math.sin(dlng / 2) ** 2
        )
        c = 2 * math.asin(math.sqrt(a))

        # Earth's radius in meters
        return 6371000 * c

    def _calculate_website_similarity(
        self, url1: Optional[str], url2: Optional[str]
    ) -> float:
        """Calculate similarity between website URLs"""
        if not url1 or not url2:
            return 0.0

        # Extract domain names
        import re

        domain1 = re.sub(r"^https?://(www\.)?", "", url1.lower().strip()).split("/")[0]
        domain2 = re.sub(r"^https?://(www\.)?", "", url2.lower().strip()).split("/")[0]

        if domain1 == domain2:
            return 1.0

        return SequenceMatcher(None, domain1, domain2).ratio()

    def _calculate_overall_confidence(
        self, scores: Dict[str, float], distance: Optional[float]
    ) -> float:
        """Calculate overall confidence score from individual similarities"""
        # Weighted scoring based on importance
        weights = {
            "name": 0.4,  # Name is most important
            "phone": 0.25,  # Phone is highly reliable
            "address": 0.2,  # Address is important
            "website": 0.15,  # Website is useful but less common
        }

        # Calculate weighted average
        weighted_sum = 0.0
        total_weight = 0.0

        for field, score in scores.items():
            if field in weights and score > 0:
                weighted_sum += score * weights[field]
                total_weight += weights[field]

        if total_weight == 0:
            return 0.0

        base_score = weighted_sum / total_weight

        # Distance bonus for very close businesses
        if distance is not None:
            if distance < 10:  # Same building
                base_score += 0.1
            elif distance < 50:  # Very close
                base_score += 0.05

        return min(1.0, base_score)

    def merge_duplicates(
        self,
        duplicate_matches: List[DuplicateMatch],
        strategy: MergeStrategy = MergeStrategy.KEEP_MOST_COMPLETE,
        auto_merge_threshold: float = HIGH_CONFIDENCE_THRESHOLD,
    ) -> List[MergeResult]:
        """
        Merge duplicate businesses based on specified strategy

        Acceptance Criteria: Merge logic correct, Update timestamps properly
        """
        merge_results = []
        processed_pairs = set()

        self.logger.info(
            f"Starting merge process for {len(duplicate_matches)} duplicates"
        )

        # Group duplicates by business clusters
        business_clusters = self._group_duplicates_into_clusters(duplicate_matches)

        for cluster in business_clusters:
            if len(cluster) < 2:
                continue

            # Skip if any pair already processed
            cluster_key = tuple(sorted(cluster))
            if cluster_key in processed_pairs:
                continue

            try:
                # Determine if auto-merge is appropriate
                cluster_matches = [
                    m
                    for m in duplicate_matches
                    if {m.business_1_id, m.business_2_id}.issubset(cluster)
                ]

                should_auto_merge = all(
                    m.confidence_score >= auto_merge_threshold for m in cluster_matches
                )

                if should_auto_merge:
                    merge_result = self._merge_business_cluster(cluster, strategy)
                    merge_results.append(merge_result)
                    self.merges_performed += 1
                else:
                    # Mark for manual review
                    self.logger.info(f"Cluster {cluster} requires manual review")
                    self._mark_for_manual_review(cluster)

                processed_pairs.add(cluster_key)

            except Exception as e:
                self.logger.error(f"Error merging cluster {cluster}: {e}")
                continue

        self.logger.info(
            f"Merge process completed: {len(merge_results)} merges performed"
        )
        return merge_results

    def _group_duplicates_into_clusters(
        self, matches: List[DuplicateMatch]
    ) -> List[Set[str]]:
        """Group duplicate matches into clusters of related businesses"""
        # Build adjacency graph
        graph = defaultdict(set)
        all_businesses = set()

        for match in matches:
            graph[match.business_1_id].add(match.business_2_id)
            graph[match.business_2_id].add(match.business_1_id)
            all_businesses.add(match.business_1_id)
            all_businesses.add(match.business_2_id)

        # Find connected components (clusters)
        clusters = []
        visited = set()

        for business_id in all_businesses:
            if business_id not in visited:
                cluster = set()
                self._dfs_cluster(business_id, graph, visited, cluster)
                if cluster:
                    clusters.append(cluster)

        return clusters

    def _dfs_cluster(self, business_id: str, graph: Dict, visited: Set, cluster: Set):
        """Depth-first search to find all businesses in a cluster"""
        visited.add(business_id)
        cluster.add(business_id)

        for neighbor in graph[business_id]:
            if neighbor not in visited:
                self._dfs_cluster(neighbor, graph, visited, cluster)

    def _merge_business_cluster(
        self, cluster: Set[str], strategy: MergeStrategy
    ) -> MergeResult:
        """
        Merge a cluster of duplicate businesses

        Acceptance Criteria: Merge logic correct, Update timestamps properly
        """
        businesses = self.session.query(Business).filter(Business.id.in_(cluster)).all()

        # Determine primary business based on strategy
        primary_business = self._select_primary_business(businesses, strategy)
        secondary_businesses = [b for b in businesses if b.id != primary_business.id]

        # Merge data from secondary businesses into primary
        fields_merged = self._merge_business_data(
            primary_business, secondary_businesses
        )

        # Update timestamps properly
        merge_timestamp = datetime.utcnow()
        primary_business.updated_at = merge_timestamp

        # Archive secondary businesses
        conflicts_resolved = []
        for secondary in secondary_businesses:
            secondary.is_active = False
            secondary.merged_into = primary_business.id
            secondary.updated_at = merge_timestamp

            # Check for data conflicts and resolve them
            conflict = self._check_data_conflicts(primary_business, secondary)
            if conflict:
                conflicts_resolved.append(conflict)

        # Update sourced location mappings
        self._update_sourced_locations(
            primary_business.id, [b.id for b in secondary_businesses]
        )

        # Yelp metadata updates removed per P0-009

        self.session.commit()

        return MergeResult(
            primary_business_id=primary_business.id,
            merged_business_ids=[b.id for b in secondary_businesses],
            merge_strategy=strategy,
            merge_timestamp=merge_timestamp,
            fields_merged=fields_merged,
            conflicts_resolved=conflicts_resolved,
        )

    def _select_primary_business(
        self, businesses: List[Business], strategy: MergeStrategy
    ) -> Business:
        """Select which business should be the primary after merge"""
        if strategy == MergeStrategy.KEEP_NEWEST:
            return max(businesses, key=lambda b: b.created_at or datetime.min)
        elif strategy == MergeStrategy.KEEP_OLDEST:
            return min(businesses, key=lambda b: b.created_at or datetime.max)
        elif strategy == MergeStrategy.KEEP_HIGHEST_RATED:
            return max(businesses, key=lambda b: b.rating or 0)
        elif strategy == MergeStrategy.KEEP_MOST_COMPLETE:
            return max(businesses, key=self._calculate_completeness)
        else:
            # Default to most complete
            return max(businesses, key=self._calculate_completeness)

    def _calculate_completeness(self, business: Business) -> float:
        """Calculate how complete a business record is"""
        fields = [
            business.name,
            business.address,
            business.phone,
            business.website,
            business.email,
            business.description,
            business.rating,
            business.latitude,
            business.longitude,
        ]

        filled_fields = sum(1 for field in fields if field is not None)
        return filled_fields / len(fields)

    def _merge_business_data(
        self, primary: Business, secondaries: List[Business]
    ) -> Dict[str, Any]:
        """Merge data from secondary businesses into primary business"""
        fields_merged = {}

        # Merge fields where primary has null/empty values
        merge_fields = [
            "address",
            "phone",
            "website",
            "email",
            "description",
            "latitude",
            "longitude",
            "rating",
            "review_count",
        ]

        for field in merge_fields:
            primary_value = getattr(primary, field, None)

            if not primary_value:  # Primary field is empty/null
                # Find best value from secondaries
                for secondary in secondaries:
                    secondary_value = getattr(secondary, field, None)
                    if secondary_value:
                        setattr(primary, field, secondary_value)
                        fields_merged[field] = secondary_value
                        break

            # For rating, take the average if multiple values exist
            elif field == "rating":
                ratings = [primary.rating] + [s.rating for s in secondaries if s.rating]
                if len(ratings) > 1:
                    avg_rating = sum(ratings) / len(ratings)
                    primary.rating = round(avg_rating, 1)
                    fields_merged[field] = avg_rating

        return fields_merged

    def _check_data_conflicts(
        self, primary: Business, secondary: Business
    ) -> Optional[str]:
        """Check for conflicts between primary and secondary business data"""
        conflicts = []

        # Check for conflicting non-null values
        fields_to_check = ["phone", "website", "email"]

        for field in fields_to_check:
            primary_val = getattr(primary, field, None)
            secondary_val = getattr(secondary, field, None)

            if (
                primary_val
                and secondary_val
                and str(primary_val).lower() != str(secondary_val).lower()
            ):
                conflicts.append(f"{field}: '{primary_val}' vs '{secondary_val}'")

        return "; ".join(conflicts) if conflicts else None

    def _update_sourced_locations(self, primary_id: str, merged_ids: List[str]):
        """Update sourced location mappings after merge"""
        # Acceptance Criteria: Update timestamps properly
        update_time = datetime.utcnow()

        for merged_id in merged_ids:
            self.session.query(SourcedLocation).filter(
                SourcedLocation.business_id == merged_id
            ).update({"business_id": primary_id, "last_updated": update_time})

    # _update_yelp_metadata method removed per P0-009

    def _mark_for_manual_review(self, cluster: Set[str]):
        """Mark a business cluster for manual review"""
        # Update businesses to indicate manual review needed
        self.session.query(Business).filter(Business.id.in_(cluster)).update(
            {"needs_review": True, "updated_at": datetime.utcnow()}
        )

        self.logger.info(f"Marked cluster {cluster} for manual review")

    def get_deduplication_stats(self) -> Dict[str, Any]:
        """Get statistics about the deduplication process"""
        elapsed = (time.time() - self.start_time) if self.start_time else 0

        return {
            "processed_count": self.processed_count,
            "duplicates_found": self.duplicates_found,
            "merges_performed": self.merges_performed,
            "processing_time_seconds": elapsed,
            "businesses_per_second": self.processed_count / elapsed
            if elapsed > 0
            else 0,
            "cache_hit_rate": len(self._similarity_cache)
            / max(1, self.processed_count),
        }


# Convenience functions for common deduplication tasks


def find_and_merge_duplicates(
    business_ids: Optional[List[str]] = None,
    confidence_threshold: float = 0.7,
    merge_strategy: MergeStrategy = MergeStrategy.KEEP_MOST_COMPLETE,
    auto_merge_threshold: float = 0.9,
) -> Dict[str, Any]:
    """
    Convenience function to find and merge duplicates in one operation

    Returns summary statistics of the operation
    """
    deduplicator = BusinessDeduplicator()

    # Find duplicates
    duplicates = deduplicator.find_duplicates(
        business_ids=business_ids, confidence_threshold=confidence_threshold
    )

    # Merge high-confidence duplicates
    merge_results = deduplicator.merge_duplicates(
        duplicates, strategy=merge_strategy, auto_merge_threshold=auto_merge_threshold
    )

    # Get statistics
    stats = deduplicator.get_deduplication_stats()
    stats.update(
        {
            "duplicates_identified": len(duplicates),
            "merges_completed": len(merge_results),
            "merge_strategy": merge_strategy.value,
        }
    )

    return stats


def detect_duplicates_only(
    business_ids: Optional[List[str]] = None, confidence_threshold: float = 0.5
) -> List[DuplicateMatch]:
    """
    Convenience function to only detect duplicates without merging

    Useful for review and analysis
    """
    deduplicator = BusinessDeduplicator()
    return deduplicator.find_duplicates(
        business_ids=business_ids, confidence_threshold=confidence_threshold
    )
