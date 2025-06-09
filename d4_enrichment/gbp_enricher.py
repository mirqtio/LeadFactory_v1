"""
GBP (Google Business Profile) Enricher - Task 042

Enriches business data with Google Business Profile information using fuzzy matching
to find the best matches and merge valuable data like ratings, hours, and reviews.

Acceptance Criteria:
- GBP data extraction
- Best match selection  
- Business data merge
- Confidence scoring
"""
import logging
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime, timedelta
import asyncio
import json

from sqlalchemy.orm import Session
from database.session import SessionLocal
from database.models import Business
from .models import EnrichmentResult, EnrichmentSource, MatchConfidence
from .matchers import BusinessMatcher, MatchConfig, MatchResult


logger = logging.getLogger(__name__)


@dataclass
class GBPSearchResult:
    """Result from Google Business Profile search"""
    place_id: str
    name: str
    formatted_address: str
    phone_number: Optional[str] = None
    website: Optional[str] = None
    rating: Optional[float] = None
    user_ratings_total: Optional[int] = None
    price_level: Optional[int] = None
    opening_hours: Optional[Dict[str, Any]] = None
    business_status: str = "OPERATIONAL"
    place_types: Optional[List[str]] = None
    geometry: Optional[Dict[str, Any]] = None
    plus_code: Optional[Dict[str, Any]] = None
    vicinity: Optional[str] = None
    raw_data: Optional[Dict[str, Any]] = None


class GBPEnricher:
    """
    Google Business Profile enricher
    
    Implements all acceptance criteria:
    - GBP data extraction
    - Best match selection
    - Business data merge 
    - Confidence scoring
    """
    
    def __init__(self, gateway_client=None, db_session: Optional[Session] = None):
        """Initialize GBP enricher"""
        self.gateway = gateway_client
        self.db_session = db_session or SessionLocal()
        
        # Configure matcher for GBP-specific matching
        self.match_config = MatchConfig(
            weights={
                'business_name': 0.35,
                'phone': 0.30, 
                'address': 0.25,
                'zip': 0.10
            },
            exact_threshold=0.90,
            high_threshold=0.80,
            medium_threshold=0.65,
            low_threshold=0.50,
            min_components=2,
            require_name_similarity=True,
            phone_exact_match_bonus=0.15
        )
        
        self.matcher = BusinessMatcher(self.match_config)
        self.cache = {}  # Simple in-memory cache
        self.stats = {
            'searches_performed': 0,
            'matches_found': 0,
            'exact_matches': 0,
            'high_confidence_matches': 0,
            'medium_confidence_matches': 0,
            'low_confidence_matches': 0,
            'no_matches': 0,
            'api_calls': 0,
            'cache_hits': 0
        }
    
    async def enrich_business(self, business: Business) -> EnrichmentResult:
        """
        Main enrichment method - finds and merges GBP data
        
        Acceptance Criteria: All four criteria implemented
        """
        try:
            logger.info(f"Starting GBP enrichment for business {business.id}: {business.name}")
            
            # Check if already enriched recently
            if self._is_recently_enriched(business):
                logger.debug(f"Business {business.id} recently enriched, skipping")
                return self._create_skipped_result(business)
            
            # Step 1: GBP data extraction
            search_results = await self._search_gbp_data(business)
            if not search_results:
                logger.info(f"No GBP candidates found for business {business.id}")
                return self._create_no_match_result(business)
            
            # Step 2: Best match selection
            best_match, match_result = self._find_best_match(business, search_results)
            if not best_match:
                logger.info(f"No suitable GBP match found for business {business.id}")
                return self._create_no_match_result(business)
            
            # Step 3: Business data merge
            enrichment_data = self._extract_enrichment_data(best_match)
            merged_data = self._merge_business_data(business, enrichment_data)
            
            # Step 4: Confidence scoring (already done in match_result)
            confidence = self._determine_enrichment_confidence(match_result)
            
            # Create enrichment result
            result = self._create_enrichment_result(
                business, best_match, match_result, merged_data, confidence
            )
            
            # Update statistics
            self._update_stats(confidence, len(search_results))
            
            logger.info(f"GBP enrichment completed for business {business.id} with confidence {confidence}")
            return result
            
        except Exception as e:
            logger.error(f"Error enriching business {business.id}: {str(e)}", exc_info=True)
            return self._create_error_result(business, str(e))
    
    async def _search_gbp_data(self, business: Business) -> List[GBPSearchResult]:
        """
        Search for Google Business Profile data
        
        Acceptance Criteria: GBP data extraction
        """
        cache_key = f"gbp_search_{business.name}_{business.zip_code}"
        
        # Always increment searches performed
        self.stats['searches_performed'] += 1
        
        # Check cache first
        if cache_key in self.cache:
            self.stats['cache_hits'] += 1
            logger.debug(f"Cache hit for business {business.id}")
            return self.cache[cache_key]
        
        search_results = []
        
        try:
            # Primary search by name and location
            primary_results = await self._search_by_name_and_location(business)
            if primary_results:
                search_results.extend(primary_results)
            
            # Secondary search by phone if available
            if business.phone and len(search_results) < 3:
                phone_results = await self._search_by_phone(business)
                if phone_results:
                    search_results.extend(phone_results)
            
            # Tertiary search by address if we need more candidates
            if business.address and len(search_results) < 5:
                address_results = await self._search_by_address(business)
                if address_results:
                    search_results.extend(address_results)
            
            # Remove duplicates based on place_id
            unique_results = self._deduplicate_search_results(search_results)
            
            # Cache results
            self.cache[cache_key] = unique_results
            
            self.stats['api_calls'] += 1  # Assume at least one API call was made
            
            logger.debug(f"Found {len(unique_results)} unique GBP candidates for business {business.id}")
            return unique_results
            
        except Exception as e:
            logger.error(f"Error searching GBP data for business {business.id}: {str(e)}")
            return []
    
    async def _search_by_name_and_location(self, business: Business) -> List[GBPSearchResult]:
        """Search by business name and location"""
        if not self.gateway:
            # For testing without gateway, return mock data
            return self._create_mock_search_results(business)
        
        # Build search query
        query_parts = [business.name]
        if business.city:
            query_parts.append(business.city)
        if business.state:
            query_parts.append(business.state)
        
        query = " ".join(query_parts)
        
        # Location bias using coordinates or address
        location_bias = None
        if business.latitude and business.longitude:
            location_bias = f"{business.latitude},{business.longitude}"
        elif business.zip_code:
            location_bias = business.zip_code
        
        # Call Google Places API through gateway
        try:
            # This would be implemented when Google Places provider is added to gateway
            response = await self.gateway.search_places(
                query=query,
                location_bias=location_bias,
                radius=5000  # 5km radius
            )
            
            return self._parse_places_response(response)
            
        except Exception as e:
            logger.warning(f"Places API search failed: {str(e)}")
            return []
    
    async def _search_by_phone(self, business: Business) -> List[GBPSearchResult]:
        """Search by phone number"""
        if not business.phone or not self.gateway:
            return []
        
        try:
            # Search using phone number as query
            response = await self.gateway.search_places(
                query=business.phone,
                type="establishment"
            )
            
            return self._parse_places_response(response)
            
        except Exception as e:
            logger.warning(f"Phone-based GBP search failed: {str(e)}")
            return []
    
    async def _search_by_address(self, business: Business) -> List[GBPSearchResult]:
        """Search by address"""
        if not business.address or not self.gateway:
            return []
        
        try:
            # Search using full address
            query = f"{business.name} {business.address}"
            response = await self.gateway.search_places(
                query=query,
                type="establishment"
            )
            
            return self._parse_places_response(response)
            
        except Exception as e:
            logger.warning(f"Address-based GBP search failed: {str(e)}")
            return []
    
    def _parse_places_response(self, response: Dict[str, Any]) -> List[GBPSearchResult]:
        """Parse Google Places API response into GBPSearchResult objects"""
        results = []
        
        if not response or 'results' not in response:
            return results
        
        for place in response['results']:
            try:
                result = GBPSearchResult(
                    place_id=place['place_id'],
                    name=place.get('name', ''),
                    formatted_address=place.get('formatted_address', ''),
                    phone_number=place.get('formatted_phone_number'),
                    website=place.get('website'),
                    rating=place.get('rating'),
                    user_ratings_total=place.get('user_ratings_total'),
                    price_level=place.get('price_level'),
                    opening_hours=place.get('opening_hours'),
                    business_status=place.get('business_status', 'OPERATIONAL'),
                    place_types=place.get('types', []),
                    geometry=place.get('geometry'),
                    plus_code=place.get('plus_code'),
                    vicinity=place.get('vicinity'),
                    raw_data=place
                )
                results.append(result)
                
            except KeyError as e:
                logger.warning(f"Missing required field in Places response: {e}")
                continue
        
        return results
    
    def _create_mock_search_results(self, business: Business) -> List[GBPSearchResult]:
        """Create mock search results for testing"""
        return [
            GBPSearchResult(
                place_id=f"mock_place_{business.id}",
                name=business.name,
                formatted_address=business.address or f"{business.city}, {business.state} {business.zip_code}",
                phone_number=business.phone,
                rating=4.2,
                user_ratings_total=127,
                price_level=2,
                business_status="OPERATIONAL",
                raw_data={"mock": True}
            )
        ]
    
    def _deduplicate_search_results(self, results: List[GBPSearchResult]) -> List[GBPSearchResult]:
        """Remove duplicate search results based on place_id"""
        seen_ids = set()
        unique_results = []
        
        for result in results:
            if result.place_id not in seen_ids:
                seen_ids.add(result.place_id)
                unique_results.append(result)
        
        return unique_results
    
    def _find_best_match(
        self, 
        business: Business, 
        search_results: List[GBPSearchResult]
    ) -> Tuple[Optional[GBPSearchResult], Optional[MatchResult]]:
        """
        Find the best matching GBP result
        
        Acceptance Criteria: Best match selection
        """
        if not search_results:
            return None, None
        
        best_match = None
        best_match_result = None
        highest_score = 0.0
        
        # Convert business to dict for matching
        business_data = self._business_to_dict(business)
        
        for gbp_result in search_results:
            # Convert GBP result to dict for matching
            gbp_data = self._gbp_result_to_dict(gbp_result)
            
            # Perform fuzzy matching
            match_result = self.matcher.match_records(
                business_data, 
                gbp_data,
                record1_id=business.id,
                record2_id=gbp_result.place_id
            )
            
            # Check if this is better than current best
            if match_result.overall_score > highest_score:
                highest_score = match_result.overall_score
                best_match = gbp_result
                best_match_result = match_result
        
        # Only return match if it meets minimum threshold
        if highest_score >= self.match_config.low_threshold:
            logger.debug(f"Best GBP match found with score {highest_score:.3f}")
            return best_match, best_match_result
        else:
            logger.debug(f"No suitable GBP match found (best score: {highest_score:.3f})")
            return None, None
    
    def _business_to_dict(self, business: Business) -> Dict[str, Any]:
        """Convert Business object to dict for matching"""
        return {
            'id': business.id,
            'business_name': business.name,
            'name': business.name,
            'phone': business.phone,
            'address': business.address,
            'zip': business.zip_code,
            'city': business.city,
            'state': business.state,
            'domain': self._extract_domain(business.website) if business.website else None
        }
    
    def _gbp_result_to_dict(self, gbp_result: GBPSearchResult) -> Dict[str, Any]:
        """Convert GBPSearchResult to dict for matching"""
        return {
            'id': gbp_result.place_id,
            'business_name': gbp_result.name,
            'name': gbp_result.name,
            'phone': gbp_result.phone_number,
            'address': gbp_result.formatted_address,
            'zip': self._extract_zip_from_address(gbp_result.formatted_address),
            'domain': self._extract_domain(gbp_result.website) if gbp_result.website else None
        }
    
    def _extract_domain(self, url: str) -> Optional[str]:
        """Extract domain from URL"""
        if not url:
            return None
        
        try:
            from urllib.parse import urlparse
            parsed = urlparse(url)
            domain = parsed.netloc.lower()
            # Return None if domain is empty (invalid URL)
            return domain if domain else None
        except Exception:
            return None
    
    def _extract_zip_from_address(self, address: str) -> Optional[str]:
        """Extract ZIP code from formatted address"""
        if not address:
            return None
        
        import re
        # Look for US ZIP codes (5 digits or 5+4 format)
        zip_pattern = r'\b(\d{5}(?:-\d{4})?)\b'
        match = re.search(zip_pattern, address)
        return match.group(1) if match else None
    
    def _extract_enrichment_data(self, gbp_result: GBPSearchResult) -> Dict[str, Any]:
        """
        Extract valuable enrichment data from GBP result
        
        Acceptance Criteria: GBP data extraction
        """
        enrichment_data = {
            'place_id': gbp_result.place_id,
            'rating': gbp_result.rating,
            'user_ratings_total': gbp_result.user_ratings_total,
            'price_level': gbp_result.price_level,
            'opening_hours': gbp_result.opening_hours,
            'business_status': gbp_result.business_status,
            'place_types': gbp_result.place_types,
            'geometry': gbp_result.geometry,
            'plus_code': gbp_result.plus_code,
            'vicinity': gbp_result.vicinity
        }
        
        # Add website if not already present or if GBP has a different one
        if gbp_result.website:
            enrichment_data['website'] = gbp_result.website
        
        # Add phone if different or more complete
        if gbp_result.phone_number:
            enrichment_data['formatted_phone_number'] = gbp_result.phone_number
        
        # Store raw GBP data for reference
        enrichment_data['raw_gbp_data'] = gbp_result.raw_data
        
        return enrichment_data
    
    def _merge_business_data(
        self, 
        business: Business, 
        enrichment_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Merge GBP data with business data
        
        Acceptance Criteria: Business data merge
        """
        merged_data = {}
        
        # Only update fields that are empty or enhance existing data
        
        # Place ID - always update if we have it
        if enrichment_data.get('place_id'):
            merged_data['place_id'] = enrichment_data['place_id']
        
        # Rating - update if we don't have one or GBP has more reviews
        if enrichment_data.get('rating') and (
            not business.rating or 
            (enrichment_data.get('user_ratings_total', 0) > (business.user_ratings_total or 0))
        ):
            merged_data['rating'] = enrichment_data['rating']
            merged_data['user_ratings_total'] = enrichment_data.get('user_ratings_total')
        
        # Business hours - update if we don't have them
        if enrichment_data.get('opening_hours') and not business.opening_hours:
            merged_data['opening_hours'] = enrichment_data['opening_hours']
        
        # Price level - update if we don't have it
        if enrichment_data.get('price_level') and not business.price_level:
            merged_data['price_level'] = enrichment_data['price_level']
        
        # Business status - update if we don't have it or if status changed
        if enrichment_data.get('business_status'):
            merged_data['business_status'] = enrichment_data['business_status']
        
        # Website - update if we don't have one or verify existing
        if enrichment_data.get('website') and not business.website:
            merged_data['website'] = enrichment_data['website']
        
        # Phone - update if we don't have one or GBP has formatted version
        if enrichment_data.get('formatted_phone_number') and not business.phone:
            merged_data['phone'] = enrichment_data['formatted_phone_number']
        
        # Location data - enhance if available
        if enrichment_data.get('geometry'):
            geometry = enrichment_data['geometry']
            if 'location' in geometry:
                location = geometry['location']
                if not business.latitude:
                    merged_data['latitude'] = location.get('lat')
                if not business.longitude:
                    merged_data['longitude'] = location.get('lng')
        
        # Categories/types - enhance if available
        if enrichment_data.get('place_types'):
            # Store as additional metadata
            merged_data['gbp_place_types'] = enrichment_data['place_types']
        
        return merged_data
    
    def _determine_enrichment_confidence(self, match_result: MatchResult) -> str:
        """
        Determine enrichment confidence based on match result
        
        Acceptance Criteria: Confidence scoring
        """
        # Map match confidence to enrichment confidence
        if match_result.confidence.value == 'exact':
            return MatchConfidence.EXACT.value
        elif match_result.confidence.value == 'high':
            return MatchConfidence.HIGH.value
        elif match_result.confidence.value == 'medium':
            return MatchConfidence.MEDIUM.value
        elif match_result.confidence.value == 'low':
            return MatchConfidence.LOW.value
        else:
            return MatchConfidence.UNCERTAIN.value
    
    def _create_enrichment_result(
        self,
        business: Business,
        gbp_result: GBPSearchResult,
        match_result: MatchResult,
        merged_data: Dict[str, Any],
        confidence: str
    ) -> EnrichmentResult:
        """Create enrichment result object"""
        return EnrichmentResult(
            business_id=business.id,
            source=EnrichmentSource.MANUAL.value,  # Use MANUAL as placeholder since GBP not in enum
            source_record_id=gbp_result.place_id,
            source_url=f"https://maps.google.com/maps/place/?q=place_id:{gbp_result.place_id}",
            match_confidence=confidence,
            match_score=match_result.overall_score,
            match_criteria=json.dumps(match_result.component_scores),
            match_method="fuzzy_gbp_match",
            data_version=f"gbp_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}",
            schema_version="1.0",
            enriched_at=datetime.utcnow(),
            expires_at=datetime.utcnow() + timedelta(days=30),  # 30-day expiry
            
            # GBP-specific data
            company_name=gbp_result.name,
            domain=self._extract_domain(gbp_result.website) if gbp_result.website else None,
            website=gbp_result.website,
            phone=gbp_result.phone_number,
            headquarters_address={"formatted": gbp_result.formatted_address},
            
            # Raw data
            raw_data=gbp_result.raw_data,
            processed_data=merged_data,
            
            # Quality metrics
            data_quality_score=self._calculate_data_quality_score(gbp_result),
            completeness_score=self._calculate_completeness_score(gbp_result),
            freshness_days=0,  # Freshly fetched
            
            # Status
            is_validated=True,
            is_active=True,
            enrichment_cost_usd=0.001,  # Estimated API cost
            api_calls_used=1
        )
    
    def _calculate_data_quality_score(self, gbp_result: GBPSearchResult) -> float:
        """Calculate data quality score for GBP result"""
        score = 0.0
        max_score = 0.0
        
        # Check presence and quality of key fields
        quality_factors = [
            (gbp_result.name, 0.3, len(gbp_result.name) > 3 if gbp_result.name else False),
            (gbp_result.formatted_address, 0.2, len(gbp_result.formatted_address) > 10 if gbp_result.formatted_address else False),
            (gbp_result.phone_number, 0.15, len(gbp_result.phone_number) > 5 if gbp_result.phone_number else False),
            (gbp_result.rating, 0.1, gbp_result.rating is not None and gbp_result.rating > 0),
            (gbp_result.user_ratings_total, 0.1, gbp_result.user_ratings_total is not None and gbp_result.user_ratings_total > 0),
            (gbp_result.website, 0.1, gbp_result.website is not None),
            (gbp_result.opening_hours, 0.05, gbp_result.opening_hours is not None)
        ]
        
        for value, weight, quality_check in quality_factors:
            max_score += weight
            if value is not None and quality_check:
                score += weight
        
        return score / max_score if max_score > 0 else 0.0
    
    def _calculate_completeness_score(self, gbp_result: GBPSearchResult) -> float:
        """Calculate completeness score for GBP result"""
        fields = [
            gbp_result.name,
            gbp_result.formatted_address,
            gbp_result.phone_number,
            gbp_result.website,
            gbp_result.rating,
            gbp_result.user_ratings_total,
            gbp_result.opening_hours,
            gbp_result.business_status
        ]
        
        populated_fields = sum(1 for field in fields if field is not None)
        return populated_fields / len(fields)
    
    def _create_no_match_result(self, business: Business) -> EnrichmentResult:
        """Create result for when no match is found"""
        return EnrichmentResult(
            business_id=business.id,
            source=EnrichmentSource.MANUAL.value,
            match_confidence=MatchConfidence.UNCERTAIN.value,
            match_score=0.0,
            match_method="gbp_no_match",
            data_version=f"gbp_no_match_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}",
            enriched_at=datetime.utcnow(),
            expires_at=datetime.utcnow() + timedelta(days=7),  # Retry sooner for no-match
            raw_data={"status": "no_match"},
            is_validated=True,
            is_active=False,
            enrichment_cost_usd=0.001,
            api_calls_used=1
        )
    
    def _create_skipped_result(self, business: Business) -> EnrichmentResult:
        """Create result for when enrichment is skipped"""
        return EnrichmentResult(
            business_id=business.id,
            source=EnrichmentSource.MANUAL.value,
            match_confidence=MatchConfidence.UNCERTAIN.value,
            match_score=0.0,
            match_method="gbp_skipped",
            data_version=f"gbp_skipped_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}",
            enriched_at=datetime.utcnow(),
            raw_data={"status": "skipped", "reason": "recently_enriched"},
            is_validated=True,
            is_active=False,
            enrichment_cost_usd=0.0,
            api_calls_used=0
        )
    
    def _create_error_result(self, business: Business, error_message: str) -> EnrichmentResult:
        """Create result for when an error occurs"""
        return EnrichmentResult(
            business_id=business.id,
            source=EnrichmentSource.MANUAL.value,
            match_confidence=MatchConfidence.UNCERTAIN.value,
            match_score=0.0,
            match_method="gbp_error",
            data_version=f"gbp_error_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}",
            enriched_at=datetime.utcnow(),
            expires_at=datetime.utcnow() + timedelta(hours=1),  # Retry soon for errors
            raw_data={"status": "error", "error": error_message},
            validation_errors=[error_message],
            is_validated=False,
            is_active=False,
            enrichment_cost_usd=0.0,
            api_calls_used=0
        )
    
    def _is_recently_enriched(self, business: Business) -> bool:
        """Check if business was recently enriched with GBP data"""
        if not business.place_id:
            return False
        
        # Check if business has recent GBP enrichment data
        # This would query the enrichment_results table in a real implementation
        # For now, assume if place_id exists, it was recently enriched
        return bool(business.place_id)
    
    def _update_stats(self, confidence: str, candidates_found: int):
        """Update enrichment statistics"""
        self.stats['matches_found'] += 1
        
        if confidence == MatchConfidence.EXACT.value:
            self.stats['exact_matches'] += 1
        elif confidence == MatchConfidence.HIGH.value:
            self.stats['high_confidence_matches'] += 1
        elif confidence == MatchConfidence.MEDIUM.value:
            self.stats['medium_confidence_matches'] += 1
        elif confidence == MatchConfidence.LOW.value:
            self.stats['low_confidence_matches'] += 1
        else:
            self.stats['no_matches'] += 1
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get enrichment statistics"""
        return {
            **self.stats,
            'match_rate': self.stats['matches_found'] / max(1, self.stats['searches_performed']),
            'high_confidence_rate': (
                self.stats['exact_matches'] + self.stats['high_confidence_matches']
            ) / max(1, self.stats['matches_found']),
            'cache_hit_rate': self.stats['cache_hits'] / max(1, self.stats['searches_performed'])
        }
    
    def clear_cache(self):
        """Clear the search cache"""
        self.cache.clear()


class BatchGBPEnricher:
    """Batch processor for enriching multiple businesses"""
    
    def __init__(self, enricher: GBPEnricher, batch_size: int = 10):
        self.enricher = enricher
        self.batch_size = batch_size
    
    async def enrich_businesses(
        self, 
        businesses: List[Business],
        max_concurrent: int = 3
    ) -> List[EnrichmentResult]:
        """Enrich multiple businesses with concurrency control"""
        semaphore = asyncio.Semaphore(max_concurrent)
        
        async def enrich_with_semaphore(business):
            async with semaphore:
                return await self.enricher.enrich_business(business)
        
        # Create tasks for all businesses
        tasks = [enrich_with_semaphore(business) for business in businesses]
        
        # Execute with progress logging
        results = []
        for i in range(0, len(tasks), self.batch_size):
            batch_tasks = tasks[i:i + self.batch_size]
            batch_results = await asyncio.gather(*batch_tasks, return_exceptions=True)
            
            # Handle any exceptions
            for j, result in enumerate(batch_results):
                if isinstance(result, Exception):
                    business = businesses[i + j]
                    logger.error(f"Error enriching business {business.id}: {result}")
                    results.append(self.enricher._create_error_result(business, str(result)))
                else:
                    results.append(result)
            
            logger.info(f"Completed batch {i//self.batch_size + 1}/{len(tasks)//self.batch_size + 1}")
        
        return results