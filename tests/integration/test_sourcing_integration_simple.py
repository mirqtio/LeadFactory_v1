"""
Integration tests for sourcing pipeline with Gateway refactoring
"""
import pytest
import asyncio
from unittest.mock import Mock, patch, AsyncMock
from datetime import datetime
import uuid

from d2_sourcing import (
    YelpScraper, ScrapingResult, ScrapingStatus,
    SourcingCoordinator, BatchStatus
)
from database.session import SessionLocal
from database.models import Business
from d2_sourcing.models import YelpMetadata


class TestSourcingWithGateway:
    """Test sourcing functionality with Gateway pattern"""

    @pytest.fixture
    def integration_session(self):
        """Create a test database session"""
        session = SessionLocal()
        yield session
        # Cleanup
        try:
            test_businesses = session.query(Business).filter(
                Business.name.like("TEST_%")
            ).all()
            for business in test_businesses:
                session.delete(business)
            session.commit()
        except Exception:
            session.rollback()
        finally:
            session.close()

    @pytest.fixture
    def sample_businesses(self):
        """Sample business data"""
        return [
            {
                "id": "test_biz_1",
                "name": "TEST_Pizza Place",
                "phone": "+14155551234",
                "location": {
                    "address1": "123 Main St",
                    "city": "San Francisco",
                    "state": "CA",
                    "zip_code": "94105",
                    "display_address": ["123 Main St", "San Francisco, CA 94105"]
                },
                "coordinates": {"latitude": 37.7749, "longitude": -122.4194},
                "rating": 4.5,
                "review_count": 100
            }
        ]

    @pytest.mark.asyncio
    async def test_scraper_uses_gateway(self, integration_session, sample_businesses):
        """Test that YelpScraper uses Gateway facade instead of direct HTTP calls"""
        
        # Mock the gateway facade
        with patch("d2_sourcing.yelp_scraper.get_gateway_facade") as mock_get_facade:
            mock_facade = Mock()
            mock_get_facade.return_value = mock_facade
            
            # Mock the search_businesses method
            mock_facade.search_businesses = AsyncMock(return_value={
                "businesses": sample_businesses,
                "total": len(sample_businesses)
            })
            
            # Create scraper
            scraper = YelpScraper(session=integration_session)
            
            # Verify gateway was initialized
            mock_get_facade.assert_called_once()
            
            # Test search
            result = await scraper.search_businesses(
                location="San Francisco, CA",
                max_results=10
            )
            
            # Verify gateway method was called
            mock_facade.search_businesses.assert_called()
            
            # Verify result
            assert result.status == ScrapingStatus.COMPLETED
            assert result.fetched_count == len(sample_businesses)
            assert len(result.businesses) == len(sample_businesses)

    @pytest.mark.asyncio
    async def test_get_business_details_uses_gateway(self, integration_session):
        """Test that get_business_details uses Gateway facade"""
        
        with patch("d2_sourcing.yelp_scraper.get_gateway_facade") as mock_get_facade:
            mock_facade = Mock()
            mock_get_facade.return_value = mock_facade
            
            # Mock the get_business_details method
            business_data = {
                "id": "test_biz_1",
                "name": "TEST_Business",
                "phone": "+14155551234"
            }
            mock_facade.get_business_details = AsyncMock(return_value=business_data)
            
            # Create scraper
            scraper = YelpScraper(session=integration_session)
            
            # Test get details
            result = await scraper.get_business_details("test_biz_1")
            
            # Verify gateway method was called
            mock_facade.get_business_details.assert_called_once_with("test_biz_1")
            
            # Verify result
            assert result["id"] == "test_biz_1"
            assert result["name"] == "TEST_Business"

    @pytest.mark.asyncio
    async def test_no_direct_http_calls(self, integration_session):
        """Verify that YelpScraper doesn't make direct HTTP calls"""
        
        # Patch aiohttp to ensure it's not used
        with patch("aiohttp.ClientSession") as mock_aiohttp:
            # This should not be called
            mock_aiohttp.side_effect = AssertionError("Direct HTTP call detected\!")
            
            with patch("d2_sourcing.yelp_scraper.get_gateway_facade") as mock_get_facade:
                mock_facade = Mock()
                mock_get_facade.return_value = mock_facade
                
                # Mock gateway response
                mock_facade.search_businesses = AsyncMock(return_value={
                    "businesses": [],
                    "total": 0
                })
                
                # Create scraper - should not trigger aiohttp
                scraper = YelpScraper(session=integration_session)
                
                # Search should use gateway, not aiohttp
                result = await scraper.search_businesses(
                    location="San Francisco, CA",
                    max_results=10
                )
                
                # Verify no direct HTTP calls
                mock_aiohttp.assert_not_called()
                
                # Verify gateway was used
                mock_facade.search_businesses.assert_called()

    @pytest.mark.asyncio 
    async def test_coordinator_with_gateway(self, integration_session, sample_businesses):
        """Test that SourcingCoordinator works with Gateway-based scraper"""
        
        with patch("d2_sourcing.yelp_scraper.get_gateway_facade") as mock_get_facade:
            mock_facade = Mock()
            mock_get_facade.return_value = mock_facade
            
            # Mock gateway response
            mock_facade.search_businesses = AsyncMock(return_value={
                "businesses": sample_businesses,
                "total": len(sample_businesses)
            })
            
            # Create coordinator
            coordinator = SourcingCoordinator(session=integration_session)
            await coordinator.initialize()
            
            try:
                # Mock save_business_data
                with patch.object(coordinator.scraper, "save_business_data") as mock_save:
                    mock_save.return_value = str(uuid.uuid4())
                    
                    # Create and process batch
                    batch_id = coordinator.create_batch(
                        location="San Francisco, CA",
                        max_results=10
                    )
                    
                    batch = await coordinator.process_batch(batch_id)
                    
                    # Verify batch completed
                    assert batch.status == BatchStatus.COMPLETED
                    assert batch.scraped_count == len(sample_businesses)
                    
                    # Verify gateway was used
                    mock_facade.search_businesses.assert_called()
                    
            finally:
                await coordinator.shutdown()


if __name__ == "__main__":
    asyncio.run(pytest.main([__file__, "-v"]))
