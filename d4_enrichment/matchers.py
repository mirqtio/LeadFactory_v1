"""
Fuzzy matching system for business data - Task 041

High-level matching system that combines similarity algorithms to match
business records across different data sources with confidence scoring.

Acceptance Criteria:
- Phone matching works
- Name/ZIP matching accurate
- Address similarity scoring
- Weighted combination logic
"""
import logging
from typing import Dict, Any, List, Optional, Tuple, Set
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime
import uuid

from .similarity import (
    SimilarityResult, SimilarityAlgorithm, WeightedSimilarity,
    PhoneSimilarity, NameSimilarity, AddressSimilarity, ZipSimilarity
)


logger = logging.getLogger(__name__)


class MatchConfidence(Enum):
    """Match confidence levels"""
    EXACT = "exact"          # 0.95-1.0
    HIGH = "high"            # 0.85-0.94
    MEDIUM = "medium"        # 0.70-0.84
    LOW = "low"             # 0.50-0.69
    UNCERTAIN = "uncertain"  # 0.0-0.49


class MatchType(Enum):
    """Types of matches found"""
    EXACT_MATCH = "exact_match"
    FUZZY_MATCH = "fuzzy_match"
    PARTIAL_MATCH = "partial_match"
    POTENTIAL_MATCH = "potential_match"
    NO_MATCH = "no_match"


@dataclass
class MatchResult:
    """Result of a matching operation"""
    record1_id: str
    record2_id: str
    overall_score: float
    confidence: MatchConfidence
    match_type: MatchType
    component_scores: Dict[str, float]
    similarity_details: Dict[str, SimilarityResult]
    metadata: Dict[str, Any] = field(default_factory=dict)
    match_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    matched_at: datetime = field(default_factory=datetime.utcnow)


@dataclass
class MatchConfig:
    """Configuration for matching behavior"""
    # Weights for different components
    weights: Dict[str, float] = field(default_factory=lambda: {
        'business_name': 0.40,
        'phone': 0.25,
        'address': 0.20,
        'zip': 0.10,
        'domain': 0.05
    })

    # Thresholds for confidence levels
    exact_threshold: float = 0.95
    high_threshold: float = 0.85
    medium_threshold: float = 0.70
    low_threshold: float = 0.50

    # Minimum required components for a valid match
    min_components: int = 2

    # Component-specific requirements
    require_name_similarity: bool = True
    require_location_match: bool = False  # Either address or ZIP
    phone_exact_match_bonus: float = 0.1  # Bonus for exact phone match

    # Performance settings
    max_candidates: int = 1000
    early_exit_threshold: float = 0.99


class BusinessMatcher:
    """
    Main fuzzy matching system for business records

    Implements all acceptance criteria:
    - Phone matching works
    - Name/ZIP matching accurate
    - Address similarity scoring
    - Weighted combination logic
    """

    def __init__(self, config: Optional[MatchConfig] = None):
        """Initialize matcher with configuration"""
        self.config = config or MatchConfig()
        self.match_cache: Dict[str, MatchResult] = {}
        self.stats = {
            'total_matches': 0,
            'exact_matches': 0,
            'high_matches': 0,
            'medium_matches': 0,
            'low_matches': 0,
            'no_matches': 0
        }

    def match_records(
        self,
        record1: Dict[str, Any],
        record2: Dict[str, Any],
        record1_id: Optional[str] = None,
        record2_id: Optional[str] = None
    ) -> MatchResult:
        """
        Match two business records

        Implements all acceptance criteria through weighted combination
        """
        # Generate IDs if not provided
        if record1_id is None:
            record1_id = record1.get('id', str(uuid.uuid4()))
        if record2_id is None:
            record2_id = record2.get('id', str(uuid.uuid4()))

        # Check cache first
        cache_key = f"{record1_id}:{record2_id}"
        if cache_key in self.match_cache:
            return self.match_cache[cache_key]

        # Calculate weighted similarity
        similarity_result = WeightedSimilarity.calculate_combined_similarity(
            record1, record2, self.config.weights
        )

        # Extract component scores from similarity details
        component_scores = {}
        similarity_details = {}

        if 'component_details' in similarity_result.metadata:
            for component, result in similarity_result.metadata['component_details'].items():
                component_scores[component] = result.score
                similarity_details[component] = result

        # Apply bonuses and adjustments
        adjusted_score = self._apply_scoring_adjustments(
            similarity_result.score, component_scores, record1, record2
        )

        # Determine confidence and match type
        confidence = self._determine_confidence(adjusted_score)
        match_type = self._determine_match_type(adjusted_score, component_scores)

        # Validate match requirements
        if not self._validate_match_requirements(component_scores):
            confidence = MatchConfidence.UNCERTAIN
            match_type = MatchType.NO_MATCH
            adjusted_score = min(adjusted_score, 0.49)

        # Create match result
        result = MatchResult(
            record1_id=record1_id,
            record2_id=record2_id,
            overall_score=adjusted_score,
            confidence=confidence,
            match_type=match_type,
            component_scores=component_scores,
            similarity_details=similarity_details,
            metadata={
                'original_score': similarity_result.score,
                'adjustments_applied': adjusted_score != similarity_result.score,
                'weights_used': self.config.weights,
                'record1_snippet': self._create_record_snippet(record1),
                'record2_snippet': self._create_record_snippet(record2)
            }
        )

        # Cache result
        self.match_cache[cache_key] = result

        # Update statistics
        self._update_stats(confidence)

        logger.debug(f"Matched {record1_id} vs {record2_id}: {confidence.value} ({adjusted_score:.3f})")

        return result

    def find_best_matches(
        self,
        target_record: Dict[str, Any],
        candidate_records: List[Dict[str, Any]],
        target_id: Optional[str] = None,
        min_score: float = 0.5,
        max_results: int = 10
    ) -> List[MatchResult]:
        """
        Find best matching records from a list of candidates

        Acceptance Criteria: Implements efficient matching with scoring
        """
        if target_id is None:
            target_id = target_record.get('id', str(uuid.uuid4()))

        matches = []

        # Limit candidates for performance
        candidates_to_check = candidate_records[:self.config.max_candidates]

        for i, candidate in enumerate(candidates_to_check):
            candidate_id = candidate.get('id', f"candidate_{i}")

            match_result = self.match_records(
                target_record, candidate, target_id, candidate_id
            )

            if match_result.overall_score >= min_score:
                matches.append(match_result)

                # Early exit for perfect matches
                if match_result.overall_score >= self.config.early_exit_threshold:
                    logger.debug(f"Early exit on near-perfect match: {match_result.overall_score}")
                    break

        # Sort by score descending
        matches.sort(key=lambda x: x.overall_score, reverse=True)

        return matches[:max_results]

    def match_phone_numbers(self, phone1: str, phone2: str) -> MatchResult:
        """
        Dedicated phone number matching

        Acceptance Criteria: Phone matching works
        """
        result = PhoneSimilarity.calculate_similarity(phone1, phone2)

        confidence = self._determine_confidence(result.score)
        match_type = MatchType.EXACT_MATCH if result.score == 1.0 else MatchType.FUZZY_MATCH

        return MatchResult(
            record1_id="phone1",
            record2_id="phone2",
            overall_score=result.score,
            confidence=confidence,
            match_type=match_type,
            component_scores={'phone': result.score},
            similarity_details={'phone': result},
            metadata={
                'match_type': 'phone_only',
                'phone1': phone1,
                'phone2': phone2,
                'normalized1': result.normalized_input,
                'normalized2': result.normalized_target
            }
        )

    def match_names_and_zips(
        self,
        name1: str, zip1: str,
        name2: str, zip2: str
    ) -> MatchResult:
        """
        Dedicated name and ZIP matching

        Acceptance Criteria: Name/ZIP matching accurate
        """
        name_result = NameSimilarity.calculate_similarity(name1, name2)
        zip_result = ZipSimilarity.calculate_similarity(zip1, zip2)

        # Weighted combination (names more important than ZIP)
        weights = {'name': 0.7, 'zip': 0.3}
        combined_score = (
            name_result.score * weights['name'] +
            zip_result.score * weights['zip']
        )

        confidence = self._determine_confidence(combined_score)

        # Determine match type based on component scores
        if name_result.score >= 0.9 and zip_result.score >= 0.9:
            match_type = MatchType.EXACT_MATCH
        elif name_result.score >= 0.7 and zip_result.score >= 0.7:
            match_type = MatchType.FUZZY_MATCH
        elif name_result.score >= 0.5 or zip_result.score >= 0.7:
            match_type = MatchType.PARTIAL_MATCH
        else:
            match_type = MatchType.NO_MATCH

        return MatchResult(
            record1_id="name_zip1",
            record2_id="name_zip2",
            overall_score=combined_score,
            confidence=confidence,
            match_type=match_type,
            component_scores={
                'name': name_result.score,
                'zip': zip_result.score
            },
            similarity_details={
                'name': name_result,
                'zip': zip_result
            },
            metadata={
                'match_type': 'name_zip',
                'weights': weights,
                'name1': name1,
                'name2': name2,
                'zip1': zip1,
                'zip2': zip2
            }
        )

    def match_addresses(self, address1: str, address2: str) -> MatchResult:
        """
        Dedicated address matching

        Acceptance Criteria: Address similarity scoring
        """
        result = AddressSimilarity.calculate_similarity(address1, address2)

        confidence = self._determine_confidence(result.score)

        if result.score >= 0.9:
            match_type = MatchType.EXACT_MATCH
        elif result.score >= 0.7:
            match_type = MatchType.FUZZY_MATCH
        elif result.score >= 0.5:
            match_type = MatchType.PARTIAL_MATCH
        else:
            match_type = MatchType.NO_MATCH

        return MatchResult(
            record1_id="address1",
            record2_id="address2",
            overall_score=result.score,
            confidence=confidence,
            match_type=match_type,
            component_scores={'address': result.score},
            similarity_details={'address': result},
            metadata={
                'match_type': 'address_only',
                'address1': address1,
                'address2': address2
            }
        )

    def _apply_scoring_adjustments(
        self,
        base_score: float,
        component_scores: Dict[str, float],
        record1: Dict[str, Any],
        record2: Dict[str, Any]
    ) -> float:
        """Apply bonuses and penalties to base score"""
        adjusted_score = base_score

        # Phone exact match bonus
        if 'phone' in component_scores and component_scores['phone'] == 1.0:
            adjusted_score += self.config.phone_exact_match_bonus

        # Penalty for very different business types (if available)
        type1 = record1.get('business_type', '').lower()
        type2 = record2.get('business_type', '').lower()
        if type1 and type2 and type1 != type2:
            # Small penalty for different business types
            adjusted_score *= 0.95

        # Ensure score stays within bounds
        return min(1.0, max(0.0, adjusted_score))

    def _determine_confidence(self, score: float) -> MatchConfidence:
        """Determine confidence level from score"""
        if score >= self.config.exact_threshold:
            return MatchConfidence.EXACT
        elif score >= self.config.high_threshold:
            return MatchConfidence.HIGH
        elif score >= self.config.medium_threshold:
            return MatchConfidence.MEDIUM
        elif score >= self.config.low_threshold:
            return MatchConfidence.LOW
        else:
            return MatchConfidence.UNCERTAIN

    def _determine_match_type(
        self,
        overall_score: float,
        component_scores: Dict[str, float]
    ) -> MatchType:
        """Determine match type from scores"""
        if overall_score >= self.config.exact_threshold:
            return MatchType.EXACT_MATCH
        elif overall_score >= self.config.medium_threshold:
            # Check if it's a fuzzy match or partial match
            high_components = sum(1 for score in component_scores.values() if score >= 0.8)
            if high_components >= 2:
                return MatchType.FUZZY_MATCH
            else:
                return MatchType.PARTIAL_MATCH
        elif overall_score >= self.config.low_threshold:
            return MatchType.POTENTIAL_MATCH
        else:
            return MatchType.NO_MATCH

    def _validate_match_requirements(self, component_scores: Dict[str, float]) -> bool:
        """Validate that match meets minimum requirements"""
        # Check minimum number of components
        valid_components = sum(1 for score in component_scores.values() if score > 0)
        if valid_components < self.config.min_components:
            return False

        # Check name similarity requirement
        if self.config.require_name_similarity:
            name_score = component_scores.get('business_name', 0)
            if name_score < 0.3:  # Very low name similarity
                return False

        # Check location match requirement
        if self.config.require_location_match:
            address_score = component_scores.get('address', 0)
            zip_score = component_scores.get('zip', 0)
            if address_score < 0.5 and zip_score < 0.5:
                return False

        return True

    def _create_record_snippet(self, record: Dict[str, Any]) -> Dict[str, str]:
        """Create a snippet of record for debugging"""
        snippet = {}
        fields_to_include = ['business_name', 'name', 'phone', 'address', 'zip', 'domain']

        for field in fields_to_include:
            if field in record and record[field]:
                snippet[field] = str(record[field])[:100]  # Truncate long values

        return snippet

    def _update_stats(self, confidence: MatchConfidence):
        """Update matching statistics"""
        self.stats['total_matches'] += 1

        if confidence == MatchConfidence.EXACT:
            self.stats['exact_matches'] += 1
        elif confidence == MatchConfidence.HIGH:
            self.stats['high_matches'] += 1
        elif confidence == MatchConfidence.MEDIUM:
            self.stats['medium_matches'] += 1
        elif confidence == MatchConfidence.LOW:
            self.stats['low_matches'] += 1
        else:
            self.stats['no_matches'] += 1

    def get_statistics(self) -> Dict[str, Any]:
        """Get matching statistics"""
        total = self.stats['total_matches']
        if total == 0:
            return self.stats.copy()

        return {
            **self.stats,
            'success_rate': (total - self.stats['no_matches']) / total,
            'high_confidence_rate': (
                self.stats['exact_matches'] + self.stats['high_matches']
            ) / total,
            'cache_size': len(self.match_cache)
        }

    def clear_cache(self):
        """Clear the match cache"""
        self.match_cache.clear()

    def configure_weights(self, weights: Dict[str, float]):
        """Update component weights"""
        self.config.weights.update(weights)

    def configure_thresholds(
        self,
        exact: Optional[float] = None,
        high: Optional[float] = None,
        medium: Optional[float] = None,
        low: Optional[float] = None
    ):
        """Update confidence thresholds"""
        if exact is not None:
            self.config.exact_threshold = exact
        if high is not None:
            self.config.high_threshold = high
        if medium is not None:
            self.config.medium_threshold = medium
        if low is not None:
            self.config.low_threshold = low


class BatchMatcher:
    """Batch matching for processing multiple records efficiently"""

    def __init__(self, matcher: BusinessMatcher):
        self.matcher = matcher

    def match_datasets(
        self,
        dataset1: List[Dict[str, Any]],
        dataset2: List[Dict[str, Any]],
        min_score: float = 0.7
    ) -> List[MatchResult]:
        """Match all records in dataset1 against dataset2"""
        all_matches = []

        for i, record1 in enumerate(dataset1):
            record1_id = record1.get('id', f"dataset1_{i}")

            matches = self.matcher.find_best_matches(
                record1, dataset2, record1_id, min_score, max_results=5
            )

            all_matches.extend(matches)

        return all_matches

    def deduplicate_dataset(
        self,
        dataset: List[Dict[str, Any]],
        min_score: float = 0.8
    ) -> Tuple[List[Dict[str, Any]], List[MatchResult]]:
        """Find and remove duplicates within a dataset"""
        unique_records = []
        duplicates = []
        processed_ids = set()

        for i, record in enumerate(dataset):
            record_id = record.get('id', f"record_{i}")

            if record_id in processed_ids:
                continue

            # Find matches for this record in remaining records
            remaining_records = dataset[i+1:]
            matches = self.matcher.find_best_matches(
                record, remaining_records, record_id, min_score
            )

            # Add record to unique list
            unique_records.append(record)
            processed_ids.add(record_id)

            # Mark duplicates as processed
            for match in matches:
                duplicates.append(match)
                processed_ids.add(match.record2_id)

        return unique_records, duplicates
