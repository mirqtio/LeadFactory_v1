"""
Google Business Profile assessor
PRD v1.2 - Extract GBP data with focus on missing hours

Timeout: 5s
Cost: $0.002 per assessment
Output: gbp_profile_json column
"""
from typing import Dict, Any, Optional, List
from datetime import datetime

from d3_assessment.assessors.base import BaseAssessor, AssessmentResult
from d3_assessment.models import AssessmentType
from d3_assessment.exceptions import AssessmentError
from d0_gateway.providers.google_places import GooglePlacesClient
from d0_gateway.factory import create_client
from core.logging import get_logger
from core.config import settings

logger = get_logger(__name__, domain="d3")


class GBPProfileAssessor(BaseAssessor):
    """Extract Google Business Profile data"""
    
    def __init__(self):
        super().__init__()
        self.timeout = 5  # 5 second timeout as per PRD
        self._client = None
        
    @property
    def assessment_type(self) -> AssessmentType:
        return AssessmentType.BUSINESS_INFO
        
    def _get_client(self) -> GooglePlacesClient:
        """Get or create Google Places client"""
        if not self._client:
            self._client = create_client("google_places")
        return self._client
        
    async def assess(self, url: str, business_data: Dict[str, Any]) -> AssessmentResult:
        """
        Get Google Business Profile data
        
        Args:
            url: Website URL (not used directly)
            business_data: Business information with place_id or search params
            
        Returns:
            AssessmentResult with gbp_profile_json data
        """
        try:
            # Get Google Places client
            client = self._get_client()
            
            # Check if we already have a place_id
            place_id = business_data.get('place_id')
            
            if not place_id:
                # Try to find the place
                search_result = await self._find_place(client, business_data)
                if search_result:
                    place_id = search_result.get('place_id')
            
            if not place_id:
                return AssessmentResult(
                    assessment_type=self.assessment_type,
                    status="completed",
                    data={
                        'gbp_profile_json': {
                            'found': False,
                            'hours_missing': True,
                            'error': 'No Google Business Profile found'
                        }
                    }
                )
            
            # Get place details
            place_details = await client.get_place_details(
                place_id=place_id,
                fields=[
                    'name', 'formatted_address', 'formatted_phone_number',
                    'website', 'rating', 'user_ratings_total', 'price_level',
                    'opening_hours', 'business_status', 'types',
                    'photos', 'reviews', 'url', 'utc_offset'
                ]
            )
            
            if not place_details:
                return AssessmentResult(
                    assessment_type=self.assessment_type,
                    status="completed",
                    data={
                        'gbp_profile_json': {
                            'place_id': place_id,
                            'found': False,
                            'hours_missing': True
                        }
                    }
                )
            
            # Process the data
            gbp_data = self._process_place_details(place_details)
            gbp_data['place_id'] = place_id
            
            # Check for missing hours (key for PRD v1.2 scoring)
            hours_missing = not gbp_data.get('has_hours', False)
            
            return AssessmentResult(
                assessment_type=self.assessment_type,
                status="completed",
                data={
                    'gbp_profile_json': gbp_data,
                    'hours_missing': hours_missing,  # For easy access in scoring
                    'place_id': place_id
                },
                metrics={
                    'has_gbp': True,
                    'has_hours': gbp_data.get('has_hours', False),
                    'review_count': gbp_data.get('user_ratings_total', 0),
                    'rating': gbp_data.get('rating', 0),
                    'api_cost_usd': 0.002
                },
                cost=0.002  # $0.002 per assessment
            )
            
        except Exception as e:
            logger.error(f"GBP assessment failed: {e}")
            
            return AssessmentResult(
                assessment_type=self.assessment_type,
                status="completed",
                data={
                    'gbp_profile_json': {
                        'error': str(e),
                        'found': False,
                        'hours_missing': True
                    }
                },
                error_message=f"GBP API error: {str(e)}"
            )
    
    async def _find_place(
        self,
        client: GooglePlacesClient,
        business_data: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """Find place using business data"""
        # Build search query
        name = business_data.get('name', '')
        address = business_data.get('address', '')
        city = business_data.get('city', '')
        state = business_data.get('state', '')
        
        query = f"{name} {address} {city} {state}".strip()
        
        if not query:
            return None
        
        try:
            results = await client.find_place(
                query=query,
                fields=['place_id', 'name', 'formatted_address']
            )
            
            if results and len(results) > 0:
                return results[0]
                
        except Exception as e:
            logger.error(f"Place search failed: {e}")
            
        return None
    
    def _process_place_details(self, details: Dict[str, Any]) -> Dict[str, Any]:
        """Process place details into structured format"""
        # Extract opening hours
        opening_hours = details.get('opening_hours', {})
        hours_data = {}
        has_hours = False
        
        if opening_hours:
            hours_data = {
                'open_now': opening_hours.get('open_now'),
                'periods': opening_hours.get('periods', []),
                'weekday_text': opening_hours.get('weekday_text', [])
            }
            has_hours = bool(opening_hours.get('periods'))
        
        # Extract reviews summary
        reviews = details.get('reviews', [])
        review_summary = []
        
        for review in reviews[:3]:  # Top 3 reviews
            review_summary.append({
                'rating': review.get('rating'),
                'time': review.get('time'),
                'text': review.get('text', '')[:200]  # Truncate long reviews
            })
        
        # Extract photo URLs
        photos = details.get('photos', [])
        photo_urls = []
        
        for photo in photos[:5]:  # Limit to 5 photos
            if 'photo_reference' in photo:
                # Would construct photo URL here
                photo_urls.append(f"photo_ref:{photo['photo_reference']}")
        
        return {
            'name': details.get('name'),
            'formatted_address': details.get('formatted_address'),
            'formatted_phone_number': details.get('formatted_phone_number'),
            'website': details.get('website'),
            'rating': details.get('rating'),
            'user_ratings_total': details.get('user_ratings_total', 0),
            'price_level': details.get('price_level'),
            'business_status': details.get('business_status'),
            'types': details.get('types', []),
            'has_hours': has_hours,
            'hours_missing': not has_hours,
            'opening_hours': hours_data,
            'reviews_summary': review_summary,
            'photo_urls': photo_urls,
            'maps_url': details.get('url'),
            'found': True
        }
    
    def calculate_cost(self) -> float:
        """GBP costs $0.002 per place details call"""
        return 0.002
    
    def is_available(self) -> bool:
        """Check if Google Places is available"""
        return bool(settings.google_api_key) or settings.use_stubs