"""
Unit tests for Phase 0.5 provider implementations
Task TS-10: Additional unit tests for Data Axle and Hunter clients
"""

import pytest
from unittest.mock import Mock, patch, AsyncMock
import httpx
from decimal import Decimal

from d0_gateway.providers.dataaxle import DataAxleClient
from d0_gateway.providers.hunter import HunterClient
from d0_gateway.exceptions import (
    RateLimitExceededError, AuthenticationError, APIProviderError,
    InvalidResponseError, TimeoutError
)


class TestDataAxleClient:
    """Unit tests for Data Axle client"""
    
    @pytest.fixture
    def client(self):
        """Create test client"""
        return DataAxleClient(
            api_key='test-key',
            base_url='https://api.test.com'
        )
        
    @pytest.fixture
    def sample_business(self):
        """Sample business data"""
        return {
            'name': 'Test Restaurant LLC',
            'address': '123 Main St',
            'city': 'San Francisco',
            'state': 'CA',
            'zip_code': '94105',
            'phone': '415-555-0123'
        }
        
    @pytest.mark.asyncio
    @patch('d0_gateway.providers.dataaxle.DataAxleClient._post')
    async def test_match_business_success(self, mock_post, client, sample_business):
        """Test successful business match"""
        # Mock response (the _post method returns the parsed JSON directly)
        mock_post.return_value = {
            'businesses': [{
                'businessId': 'DA123',
                'name': 'Test Restaurant LLC',
                'primaryAddress': {
                    'street': '123 Main St',
                    'city': 'San Francisco',
                    'state': 'CA',
                    'zip': '94105'
                },
                'employees': 25,
                'revenue': 2500000
            }],
            'totalRecords': 1
        }
        
        # Test
        result = await client.match_business(sample_business)
        
        # Verify
        assert result['matched'] is True
        assert result['dataaxle_id'] == 'DA123'
        assert result['confidence'] > 0.8
        assert result['enriched_data']['employees'] == 25
        assert result['enriched_data']['revenue'] == 2500000
        
    @pytest.mark.asyncio
    @patch('httpx.AsyncClient.post')
    async def test_match_business_no_match(self, mock_post, client, sample_business):
        """Test business match with no results"""
        # Mock response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'businesses': [],
            'totalRecords': 0
        }
        mock_post.return_value = mock_response
        
        # Test
        result = await client.match_business(sample_business)
        
        # Verify
        assert result['matched'] is False
        assert result['dataaxle_id'] is None
        assert result['confidence'] == 0
        assert result['enriched_data'] == {}
        
    @pytest.mark.asyncio
    @patch('httpx.AsyncClient.post')
    async def test_match_business_auth_error(self, mock_post, client, sample_business):
        """Test authentication error"""
        # Mock 401 response
        mock_response = Mock()
        mock_response.status_code = 401
        mock_response.text = 'Unauthorized'
        mock_post.return_value = mock_response
        
        # Test
        with pytest.raises(AuthenticationError):
            await client.match_business(sample_business)
            
    @pytest.mark.asyncio
    @patch('httpx.AsyncClient.post')
    async def test_match_business_rate_limit(self, mock_post, client, sample_business):
        """Test rate limit error"""
        # Mock 429 response
        mock_response = Mock()
        mock_response.status_code = 429
        mock_response.headers = {'Retry-After': '60'}
        mock_post.return_value = mock_response
        
        # Test
        with pytest.raises(RateLimitExceededError) as exc_info:
            await client.match_business(sample_business)
            
        assert exc_info.value.retry_after == 60
        
    def test_calculate_match_confidence(self, client):
        """Test match confidence calculation"""
        # Exact match
        business = {
            'name': 'Test Restaurant',
            'address': '123 Main St',
            'city': 'San Francisco',
            'zip_code': '94105'
        }
        
        match = {
            'name': 'Test Restaurant',
            'primaryAddress': {
                'street': '123 Main St',
                'city': 'San Francisco',
                'zip': '94105'
            }
        }
        
        confidence = client._calculate_match_confidence(business, match)
        assert confidence >= 0.9
        
        # Partial match
        match['name'] = 'Test Restaurant LLC'
        match['primaryAddress']['street'] = '123 Main Street'
        
        confidence = client._calculate_match_confidence(business, match)
        assert 0.7 <= confidence < 0.9
        
        # Poor match
        match['name'] = 'Different Business'
        match['primaryAddress']['city'] = 'Los Angeles'
        
        confidence = client._calculate_match_confidence(business, match)
        assert confidence < 0.5


class TestHunterClient:
    """Unit tests for Hunter client"""
    
    @pytest.fixture
    def client(self):
        """Create test client"""
        return HunterClient(api_key='test-key')
        
    @pytest.fixture
    def sample_company(self):
        """Sample company data"""
        return {
            'name': 'Test Company',
            'website': 'https://testcompany.com'
        }
        
    @pytest.mark.asyncio
    @patch('httpx.AsyncClient.get')
    async def test_find_email_success(self, mock_get, client, sample_company):
        """Test successful email finding"""
        # Mock response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'data': {
                'email': 'john@testcompany.com',
                'first_name': 'John',
                'last_name': 'Doe',
                'position': 'CEO',
                'confidence': 90,
                'sources': [{
                    'domain': 'testcompany.com',
                    'uri': 'https://testcompany.com/about'
                }]
            }
        }
        mock_get.return_value = mock_response
        
        # Test
        result = await client.find_email(sample_company)
        
        # Verify
        assert result['found'] is True
        assert result['email'] == 'john@testcompany.com'
        assert result['confidence'] == 90
        assert result['contact']['first_name'] == 'John'
        assert result['contact']['position'] == 'CEO'
        
    @pytest.mark.asyncio
    @patch('httpx.AsyncClient.get')
    async def test_find_email_not_found(self, mock_get, client, sample_company):
        """Test email not found"""
        # Mock response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'data': {
                'email': None
            }
        }
        mock_get.return_value = mock_response
        
        # Test
        result = await client.find_email(sample_company)
        
        # Verify
        assert result['found'] is False
        assert result['email'] is None
        assert result['confidence'] == 0
        
    @pytest.mark.asyncio
    @patch('httpx.AsyncClient.get')
    async def test_find_email_missing_domain(self, mock_get, client):
        """Test with missing website"""
        company = {'name': 'Test Company'}
        
        result = await client.find_email(company)
        
        assert result['found'] is False
        assert result['email'] is None
        assert not mock_get.called
        
    @pytest.mark.asyncio
    @patch('httpx.AsyncClient.get')
    async def test_find_email_network_error(self, mock_get, client, sample_company):
        """Test network error handling"""
        # Mock network error
        mock_get.side_effect = httpx.NetworkError("Connection failed")
        
        # Test - network errors are handled by base client
        with pytest.raises(Exception):  # Base client will wrap the error
            await client.find_email(sample_company)
            
    def test_extract_domain(self, client):
        """Test domain extraction from URLs"""
        # Various URL formats
        assert client._extract_domain('https://example.com') == 'example.com'
        assert client._extract_domain('http://www.example.com') == 'example.com'
        assert client._extract_domain('https://subdomain.example.com') == 'example.com'
        assert client._extract_domain('example.com') == 'example.com'
        assert client._extract_domain('https://example.com/path') == 'example.com'
        
        # Invalid URLs
        assert client._extract_domain('not-a-url') is None
        assert client._extract_domain('') is None
        assert client._extract_domain(None) is None


class TestCostTracking:
    """Test cost tracking functionality"""
    
    @pytest.mark.asyncio
    @patch('d0_gateway.base.SessionLocal')
    async def test_emit_cost_dataaxle(self, mock_session):
        """Test cost emission for Data Axle"""
        # Mock database session
        mock_db = Mock()
        mock_session.return_value.__enter__.return_value = mock_db
        
        # Create client
        client = DataAxleClient(api_key='test-key')
        
        # Emit cost
        client.emit_cost(
            lead_id=123,
            cost_usd=0.05,
            operation='match_business',
            metadata={'confidence': 0.95}
        )
        
        # Verify database call
        mock_db.add.assert_called_once()
        cost_record = mock_db.add.call_args[0][0]
        assert cost_record.provider == 'dataaxle'
        assert float(cost_record.cost_usd) == 0.05
        assert cost_record.operation == 'match_business'
        
    @pytest.mark.asyncio
    @patch('d0_gateway.base.SessionLocal')
    async def test_emit_cost_hunter(self, mock_session):
        """Test cost emission for Hunter"""
        # Mock database session
        mock_db = Mock()
        mock_session.return_value.__enter__.return_value = mock_db
        
        # Create client
        client = HunterClient(api_key='test-key')
        
        # Emit cost
        client.emit_cost(
            lead_id=456,
            cost_usd=0.01,
            operation='find_email',
            metadata={'domain': 'example.com'}
        )
        
        # Verify database call
        mock_db.add.assert_called_once()
        cost_record = mock_db.add.call_args[0][0]
        assert cost_record.provider == 'hunter'
        assert float(cost_record.cost_usd) == 0.01
        assert cost_record.operation == 'find_email'