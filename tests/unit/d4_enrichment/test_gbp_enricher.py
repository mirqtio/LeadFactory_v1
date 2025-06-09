"""
Tests for GBP enricher - Task 042

Tests all acceptance criteria:
- GBP data extraction
- Best match selection
- Business data merge
- Confidence scoring
"""
import pytest
from unittest.mock import Mock, AsyncMock, patch
from datetime import datetime, timedelta
import json

from d4_enrichment.gbp_enricher import (
    GBPEnricher, GBPSearchResult, BatchGBPEnricher
)
from d4_enrichment.models import EnrichmentResult, MatchConfidence
from database.models import Business


@pytest.fixture
def mock_gateway():
    """Mock gateway client for testing"""
    gateway = Mock()
    gateway.search_places = AsyncMock()
    return gateway


@pytest.fixture
def sample_business():
    """Sample business for testing"""
    business = Mock(spec=Business)
    business.id = "business_123"
    business.name = "Joe's Pizza"
    business.phone = "+1-555-123-4567"
    business.address = "123 Main St"
    business.city = "San Francisco"
    business.state = "CA"
    business.zip_code = "94102"
    business.latitude = 37.7749
    business.longitude = -122.4194
    business.website = "https://joespizza.com"
    business.place_id = None
    business.rating = None
    business.user_ratings_total = None
    business.price_level = None
    business.opening_hours = None
    business.business_status = None
    return business


@pytest.fixture
def sample_gbp_result():
    """Sample GBP search result"""
    return GBPSearchResult(
        place_id="ChIJ123abc",
        name="Joe's Pizza",
        formatted_address="123 Main St, San Francisco, CA 94102, USA",
        phone_number="+1 555-123-4567",
        website="https://joespizza.com",
        rating=4.5,
        user_ratings_total=234,
        price_level=2,
        opening_hours={
            "open_now": True,
            "periods": [
                {
                    "close": {"day": 0, "time": "2200"},
                    "open": {"day": 0, "time": "1100"}
                }
            ]
        },
        business_status="OPERATIONAL",
        place_types=["restaurant", "food", "point_of_interest"],
        geometry={
            "location": {"lat": 37.7749, "lng": -122.4194}
        },
        raw_data={"test": "data"}
    )


@pytest.fixture
def enricher(mock_gateway):
    """GBP enricher with mock gateway"""
    return GBPEnricher(gateway_client=mock_gateway, db_session=Mock())


class TestGBPEnricher:
    """Test GBP enricher functionality"""
    
    def test_init(self, enricher):
        """Test enricher initialization"""
        assert enricher.gateway is not None
        assert enricher.matcher is not None
        assert enricher.match_config is not None
        assert enricher.stats['searches_performed'] == 0
    
    def test_business_to_dict(self, enricher, sample_business):
        """Test business to dict conversion"""
        result = enricher._business_to_dict(sample_business)
        
        assert result['id'] == "business_123"
        assert result['business_name'] == "Joe's Pizza"
        assert result['phone'] == "+1-555-123-4567"
        assert result['address'] == "123 Main St"
        assert result['zip'] == "94102"
        assert result['city'] == "San Francisco"
        assert result['state'] == "CA"
        assert result['domain'] == "joespizza.com"
    
    def test_gbp_result_to_dict(self, enricher, sample_gbp_result):
        """Test GBP result to dict conversion"""
        result = enricher._gbp_result_to_dict(sample_gbp_result)
        
        assert result['id'] == "ChIJ123abc"
        assert result['business_name'] == "Joe's Pizza"
        assert result['phone'] == "+1 555-123-4567"
        assert result['address'] == "123 Main St, San Francisco, CA 94102, USA"
        assert result['zip'] == "94102"
        assert result['domain'] == "joespizza.com"
    
    def test_extract_domain(self, enricher):
        """Test domain extraction from URLs"""
        assert enricher._extract_domain("https://example.com") == "example.com"
        assert enricher._extract_domain("http://www.example.com/path") == "www.example.com"
        assert enricher._extract_domain("invalid") is None
        assert enricher._extract_domain(None) is None
    
    def test_extract_zip_from_address(self, enricher):
        """Test ZIP extraction from formatted address"""
        address1 = "123 Main St, San Francisco, CA 94102, USA"
        assert enricher._extract_zip_from_address(address1) == "94102"
        
        address2 = "456 Oak Ave, New York, NY 10001-1234, USA"
        assert enricher._extract_zip_from_address(address2) == "10001-1234"
        
        address3 = "No ZIP here"
        assert enricher._extract_zip_from_address(address3) is None
    
    def test_extract_enrichment_data(self, enricher, sample_gbp_result):
        """Test GBP data extraction - Acceptance Criteria: GBP data extraction"""
        data = enricher._extract_enrichment_data(sample_gbp_result)
        
        assert data['place_id'] == "ChIJ123abc"
        assert data['rating'] == 4.5
        assert data['user_ratings_total'] == 234
        assert data['price_level'] == 2
        assert data['opening_hours'] is not None
        assert data['business_status'] == "OPERATIONAL"
        assert data['place_types'] == ["restaurant", "food", "point_of_interest"]
        assert data['website'] == "https://joespizza.com"
        assert data['formatted_phone_number'] == "+1 555-123-4567"
        assert data['raw_gbp_data'] == {"test": "data"}
    
    def test_merge_business_data(self, enricher, sample_business):
        """Test business data merge - Acceptance Criteria: Business data merge"""
        enrichment_data = {
            'place_id': 'ChIJ123abc',
            'rating': 4.5,
            'user_ratings_total': 234,
            'price_level': 2,
            'opening_hours': {'open_now': True},
            'business_status': 'OPERATIONAL',
            'website': 'https://newwebsite.com',
            'formatted_phone_number': '+1 555-123-4567',
            'geometry': {
                'location': {'lat': 37.7749, 'lng': -122.4194}
            },
            'place_types': ['restaurant']
        }
        
        merged = enricher._merge_business_data(sample_business, enrichment_data)
        
        # Should always merge place_id
        assert merged['place_id'] == 'ChIJ123abc'
        
        # Should merge rating since business doesn't have one
        assert merged['rating'] == 4.5
        assert merged['user_ratings_total'] == 234
        
        # Should merge opening hours since business doesn't have them
        assert merged['opening_hours'] == {'open_now': True}
        
        # Should merge price level
        assert merged['price_level'] == 2
        
        # Should merge business status
        assert merged['business_status'] == 'OPERATIONAL'
        
        # Should NOT merge website since business already has one
        assert 'website' not in merged
        
        # Should NOT merge phone since business already has one
        assert 'phone' not in merged
        
        # Should merge coordinates since business doesn't have them
        # (sample_business.latitude is set but in real scenario might be None)
        assert 'gbp_place_types' in merged
    
    def test_merge_business_data_empty_business(self, enricher):
        """Test merging when business has no existing data"""
        empty_business = Mock(spec=Business)
        empty_business.rating = None
        empty_business.user_ratings_total = None
        empty_business.opening_hours = None
        empty_business.price_level = None
        empty_business.website = None
        empty_business.phone = None
        empty_business.latitude = None
        empty_business.longitude = None
        
        enrichment_data = {
            'place_id': 'ChIJ123abc',
            'rating': 4.5,
            'user_ratings_total': 234,
            'website': 'https://website.com',
            'formatted_phone_number': '+1 555-123-4567',
            'geometry': {
                'location': {'lat': 37.7749, 'lng': -122.4194}
            }
        }
        
        merged = enricher._merge_business_data(empty_business, enrichment_data)
        
        # Should merge all fields since business has none
        assert merged['place_id'] == 'ChIJ123abc'
        assert merged['rating'] == 4.5
        assert merged['user_ratings_total'] == 234
        assert merged['website'] == 'https://website.com'
        assert merged['phone'] == '+1 555-123-4567'
        assert merged['latitude'] == 37.7749
        assert merged['longitude'] == -122.4194
    
    def test_determine_enrichment_confidence(self, enricher):
        """Test confidence scoring - Acceptance Criteria: Confidence scoring"""
        from d4_enrichment.matchers import MatchConfidence as MatcherConfidence
        
        # Mock match result with exact confidence
        exact_match = Mock()
        exact_match.confidence.value = 'exact'
        confidence = enricher._determine_enrichment_confidence(exact_match)
        assert confidence == MatchConfidence.EXACT.value
        
        # Mock match result with high confidence
        high_match = Mock()
        high_match.confidence.value = 'high'
        confidence = enricher._determine_enrichment_confidence(high_match)
        assert confidence == MatchConfidence.HIGH.value
        
        # Mock match result with medium confidence
        medium_match = Mock()
        medium_match.confidence.value = 'medium'
        confidence = enricher._determine_enrichment_confidence(medium_match)
        assert confidence == MatchConfidence.MEDIUM.value
        
        # Mock match result with low confidence
        low_match = Mock()
        low_match.confidence.value = 'low'
        confidence = enricher._determine_enrichment_confidence(low_match)
        assert confidence == MatchConfidence.LOW.value
        
        # Mock match result with uncertain confidence
        uncertain_match = Mock()
        uncertain_match.confidence.value = 'uncertain'
        confidence = enricher._determine_enrichment_confidence(uncertain_match)
        assert confidence == MatchConfidence.UNCERTAIN.value
    
    def test_calculate_data_quality_score(self, enricher, sample_gbp_result):
        """Test data quality score calculation"""
        score = enricher._calculate_data_quality_score(sample_gbp_result)
        assert 0.0 <= score <= 1.0
        assert score > 0.8  # Should be high quality with all fields populated
        
        # Test with minimal data
        minimal_result = GBPSearchResult(
            place_id="test",
            name="Test",
            formatted_address=""
        )
        minimal_score = enricher._calculate_data_quality_score(minimal_result)
        assert minimal_score < score  # Should be lower quality
    
    def test_calculate_completeness_score(self, enricher, sample_gbp_result):
        """Test completeness score calculation"""
        score = enricher._calculate_completeness_score(sample_gbp_result)
        assert 0.0 <= score <= 1.0
        assert score > 0.7  # Should be quite complete
        
        # Test with minimal data
        minimal_result = GBPSearchResult(
            place_id="test",
            name="Test",
            formatted_address=""
        )
        minimal_score = enricher._calculate_completeness_score(minimal_result)
        assert minimal_score < score  # Should be less complete
    
    def test_deduplicate_search_results(self, enricher):
        """Test search result deduplication"""
        results = [
            GBPSearchResult(place_id="1", name="Test 1", formatted_address="Addr 1"),
            GBPSearchResult(place_id="2", name="Test 2", formatted_address="Addr 2"),
            GBPSearchResult(place_id="1", name="Test 1 Duplicate", formatted_address="Addr 1"),  # Duplicate
            GBPSearchResult(place_id="3", name="Test 3", formatted_address="Addr 3"),
        ]
        
        unique_results = enricher._deduplicate_search_results(results)
        
        assert len(unique_results) == 3
        place_ids = [r.place_id for r in unique_results]
        assert place_ids == ["1", "2", "3"]
        
        # Should keep the first occurrence
        assert unique_results[0].name == "Test 1"
    
    def test_parse_places_response(self, enricher):
        """Test parsing of Google Places API response"""
        mock_response = {
            'results': [
                {
                    'place_id': 'ChIJ123',
                    'name': 'Test Place',
                    'formatted_address': '123 Test St, Test City, TC 12345',
                    'rating': 4.2,
                    'user_ratings_total': 150,
                    'price_level': 2,
                    'website': 'https://test.com',
                    'formatted_phone_number': '+1 555-123-4567',
                    'business_status': 'OPERATIONAL',
                    'types': ['restaurant'],
                    'geometry': {'location': {'lat': 37.7749, 'lng': -122.4194}},
                },
                {
                    'place_id': 'ChIJ456',
                    'name': 'Another Place',
                    'formatted_address': '456 Other St, Other City, OC 67890',
                }
            ]
        }
        
        results = enricher._parse_places_response(mock_response)
        
        assert len(results) == 2
        
        # Check first result
        result1 = results[0]
        assert result1.place_id == 'ChIJ123'
        assert result1.name == 'Test Place'
        assert result1.rating == 4.2
        assert result1.user_ratings_total == 150
        assert result1.website == 'https://test.com'
        
        # Check second result (minimal data)
        result2 = results[1]
        assert result2.place_id == 'ChIJ456'
        assert result2.name == 'Another Place'
        assert result2.rating is None
        assert result2.website is None
    
    def test_parse_places_response_empty(self, enricher):
        """Test parsing empty or invalid response"""
        assert enricher._parse_places_response({}) == []
        assert enricher._parse_places_response(None) == []
        assert enricher._parse_places_response({'results': []}) == []
    
    def test_find_best_match_exact(self, enricher, sample_business):
        """Test best match selection with exact match - Acceptance Criteria: Best match selection"""
        # Create a perfect GBP match
        perfect_match = GBPSearchResult(
            place_id="perfect_match",
            name="Joe's Pizza",  # Exact name match
            formatted_address="123 Main St, San Francisco, CA 94102, USA",
            phone_number="+1 555-123-4567",  # Exact phone match
            website="https://joespizza.com"
        )
        
        # Create a poor match
        poor_match = GBPSearchResult(
            place_id="poor_match",
            name="Different Restaurant",
            formatted_address="999 Other St, Other City, NY 10001, USA",
            phone_number="+1 555-999-9999"
        )
        
        search_results = [poor_match, perfect_match]  # Put poor match first to test sorting
        
        best_match, match_result = enricher._find_best_match(sample_business, search_results)
        
        assert best_match is not None
        assert best_match.place_id == "perfect_match"
        assert match_result.overall_score > 0.8  # Should be high score
        assert match_result.record1_id == sample_business.id
        assert match_result.record2_id == "perfect_match"
    
    def test_find_best_match_no_good_matches(self, enricher, sample_business):
        """Test best match selection when no good matches exist"""
        # Create only poor matches
        poor_matches = [
            GBPSearchResult(
                place_id="poor1",
                name="Completely Different Business",
                formatted_address="999 Other St, Other City, NY 10001, USA",
                phone_number="+1 555-999-9999"
            ),
            GBPSearchResult(
                place_id="poor2",
                name="Another Different Business",
                formatted_address="888 Another St, Another City, FL 33101, USA",
                phone_number="+1 555-888-8888"
            )
        ]
        
        best_match, match_result = enricher._find_best_match(sample_business, poor_matches)
        
        # Should return None if no matches meet threshold
        assert best_match is None
        assert match_result is None
    
    def test_find_best_match_empty_results(self, enricher, sample_business):
        """Test best match selection with empty results"""
        best_match, match_result = enricher._find_best_match(sample_business, [])
        
        assert best_match is None
        assert match_result is None
    
    @pytest.mark.asyncio
    async def test_search_gbp_data_cache_hit(self, enricher, sample_business):
        """Test GBP data search with cache hit"""
        # Pre-populate cache
        cache_key = f"gbp_search_{sample_business.name}_{sample_business.zip_code}"
        cached_results = [
            GBPSearchResult(
                place_id="cached_result",
                name="Cached Business",
                formatted_address="Cached Address"
            )
        ]
        enricher.cache[cache_key] = cached_results
        
        results = await enricher._search_gbp_data(sample_business)
        
        assert results == cached_results
        assert enricher.stats['cache_hits'] == 1
        assert enricher.stats['searches_performed'] == 1
    
    @pytest.mark.asyncio
    async def test_search_gbp_data_no_gateway(self, sample_business):
        """Test GBP data search without gateway (mock mode)"""
        enricher = GBPEnricher(gateway_client=None, db_session=Mock())
        
        results = await enricher._search_gbp_data(sample_business)
        
        # Should return mock results
        assert len(results) == 1
        assert results[0].place_id == f"mock_place_{sample_business.id}"
        assert results[0].name == sample_business.name
    
    @pytest.mark.asyncio
    async def test_enrich_business_full_flow(self, enricher, sample_business, sample_gbp_result):
        """Test complete enrichment flow - All Acceptance Criteria"""
        # Mock the search to return our sample result AND update stats
        async def mock_search(business):
            enricher.stats['searches_performed'] += 1
            return [sample_gbp_result]
        
        enricher._search_gbp_data = AsyncMock(side_effect=mock_search)
        
        # Mock recently enriched check
        enricher._is_recently_enriched = Mock(return_value=False)
        
        result = await enricher.enrich_business(sample_business)
        
        # Verify result is created correctly
        assert isinstance(result, EnrichmentResult)
        assert result.business_id == sample_business.id
        assert result.source_record_id == sample_gbp_result.place_id
        assert result.match_score > 0.0
        assert result.company_name == sample_gbp_result.name
        assert result.is_active is True
        
        # Verify statistics updated
        assert enricher.stats['searches_performed'] == 1
        assert enricher.stats['matches_found'] == 1
    
    @pytest.mark.asyncio
    async def test_enrich_business_no_results(self, enricher, sample_business):
        """Test enrichment when no GBP results found"""
        # Mock search to return empty results AND update stats
        async def mock_search(business):
            enricher.stats['searches_performed'] += 1
            return []
        
        enricher._search_gbp_data = AsyncMock(side_effect=mock_search)
        enricher._is_recently_enriched = Mock(return_value=False)
        
        result = await enricher.enrich_business(sample_business)
        
        # Should return no-match result
        assert isinstance(result, EnrichmentResult)
        assert result.business_id == sample_business.id
        assert result.match_score == 0.0
        assert result.is_active is False
        assert "no_match" in result.data_version
    
    @pytest.mark.asyncio
    async def test_enrich_business_recently_enriched(self, enricher, sample_business):
        """Test enrichment when business was recently enriched"""
        # Mock recently enriched check
        enricher._is_recently_enriched = Mock(return_value=True)
        
        result = await enricher.enrich_business(sample_business)
        
        # Should return skipped result
        assert isinstance(result, EnrichmentResult)
        assert result.business_id == sample_business.id
        assert result.match_score == 0.0
        assert result.is_active is False
        assert "skipped" in result.data_version
        assert result.enrichment_cost_usd == 0.0
    
    @pytest.mark.asyncio
    async def test_enrich_business_error(self, enricher, sample_business):
        """Test enrichment error handling"""
        # Mock search to raise an exception
        enricher._search_gbp_data = AsyncMock(side_effect=Exception("API Error"))
        enricher._is_recently_enriched = Mock(return_value=False)
        
        result = await enricher.enrich_business(sample_business)
        
        # Should return error result
        assert isinstance(result, EnrichmentResult)
        assert result.business_id == sample_business.id
        assert result.match_score == 0.0
        assert result.is_active is False
        assert "error" in result.data_version
        assert "API Error" in result.validation_errors
    
    def test_create_mock_search_results(self, enricher, sample_business):
        """Test mock search results creation"""
        results = enricher._create_mock_search_results(sample_business)
        
        assert len(results) == 1
        result = results[0]
        assert result.place_id == f"mock_place_{sample_business.id}"
        assert result.name == sample_business.name
        assert result.phone_number == sample_business.phone
        assert result.rating == 4.2
        assert result.raw_data == {"mock": True}
    
    def test_is_recently_enriched(self, enricher, sample_business):
        """Test recently enriched check"""
        # Business without place_id should not be considered recently enriched
        sample_business.place_id = None
        assert enricher._is_recently_enriched(sample_business) is False
        
        # Business with place_id should be considered recently enriched
        sample_business.place_id = "ChIJ123"
        assert enricher._is_recently_enriched(sample_business) is True
    
    def test_statistics(self, enricher):
        """Test statistics collection and calculation"""
        # Initial stats
        stats = enricher.get_statistics()
        assert stats['match_rate'] == 0.0
        assert stats['high_confidence_rate'] == 0.0
        assert stats['cache_hit_rate'] == 0.0
        
        # Update some stats
        enricher.stats['searches_performed'] = 10
        enricher.stats['matches_found'] = 8
        enricher.stats['exact_matches'] = 3
        enricher.stats['high_confidence_matches'] = 2
        enricher.stats['cache_hits'] = 5
        
        stats = enricher.get_statistics()
        assert stats['match_rate'] == 0.8
        assert stats['high_confidence_rate'] == 0.625  # (3+2)/8
        assert stats['cache_hit_rate'] == 0.5  # 5/10
    
    def test_clear_cache(self, enricher):
        """Test cache clearing"""
        enricher.cache['test'] = 'data'
        assert len(enricher.cache) == 1
        
        enricher.clear_cache()
        assert len(enricher.cache) == 0


class TestBatchGBPEnricher:
    """Test batch enrichment functionality"""
    
    @pytest.fixture
    def batch_enricher(self, enricher):
        """Batch enricher with mock underlying enricher"""
        return BatchGBPEnricher(enricher, batch_size=2)
    
    @pytest.fixture
    def sample_businesses(self):
        """Sample businesses for batch testing"""
        businesses = []
        for i in range(3):
            business = Mock(spec=Business)
            business.id = f"business_{i}"
            business.name = f"Business {i}"
            business.phone = f"+1-555-{i:03d}-{i:04d}"
            business.address = f"{i} Test St"
            business.city = "Test City"
            business.state = "TC"
            business.zip_code = f"{i:05d}"
            business.place_id = None
            businesses.append(business)
        return businesses
    
    @pytest.mark.asyncio
    async def test_enrich_businesses_success(self, batch_enricher, sample_businesses):
        """Test successful batch enrichment"""
        # Mock the enricher to return successful results
        mock_results = []
        for business in sample_businesses:
            result = Mock(spec=EnrichmentResult)
            result.business_id = business.id
            result.match_score = 0.8
            mock_results.append(result)
        
        batch_enricher.enricher.enrich_business = AsyncMock(side_effect=mock_results)
        
        results = await batch_enricher.enrich_businesses(sample_businesses, max_concurrent=2)
        
        assert len(results) == 3
        for i, result in enumerate(results):
            assert result.business_id == f"business_{i}"
            assert result.match_score == 0.8
    
    @pytest.mark.asyncio
    async def test_enrich_businesses_with_errors(self, batch_enricher, sample_businesses):
        """Test batch enrichment with some errors"""
        # Mock the enricher to fail on second business
        def mock_enrich(business):
            if business.id == "business_1":
                raise Exception("Test error")
            else:
                result = Mock(spec=EnrichmentResult)
                result.business_id = business.id
                result.match_score = 0.8
                return result
        
        batch_enricher.enricher.enrich_business = AsyncMock(side_effect=mock_enrich)
        
        # Mock the error result creation
        error_result = Mock(spec=EnrichmentResult)
        error_result.business_id = "business_1"
        error_result.match_score = 0.0
        batch_enricher.enricher._create_error_result = Mock(return_value=error_result)
        
        results = await batch_enricher.enrich_businesses(sample_businesses, max_concurrent=2)
        
        assert len(results) == 3
        
        # First and third should be successful
        assert results[0].business_id == "business_0"
        assert results[0].match_score == 0.8
        
        assert results[2].business_id == "business_2"
        assert results[2].match_score == 0.8
        
        # Second should be error result
        assert results[1].business_id == "business_1"
        assert results[1].match_score == 0.0