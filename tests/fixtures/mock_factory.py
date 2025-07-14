"""
Mock Factory Framework for Test Coverage Enhancement

Provides a standardized approach to creating mock responses for external services.
Based on P0-015 triangulation feedback for fast, deterministic tests.
"""
from typing import Any, Dict, Optional, Type, TypeVar
from abc import ABC, abstractmethod
import json
from unittest.mock import Mock, MagicMock
from requests.exceptions import Timeout, ConnectionError as RequestsConnectionError

T = TypeVar('T', bound='MockFactory')


class MockFactory(ABC):
    """
    Base class for provider mock factories.
    
    Provides standard patterns for:
    - Success responses
    - Error responses  
    - Timeout scenarios
    - Rate limiting
    - Circuit breaker states
    """
    
    @classmethod
    @abstractmethod
    def create_success_response(cls, **overrides) -> Dict[str, Any]:
        """Create standard success response with optional overrides."""
        pass
    
    @classmethod
    @abstractmethod
    def create_error_response(cls, error_type: str, **overrides) -> Dict[str, Any]:
        """Create standard error response for given error type."""
        pass
    
    @classmethod
    def create_timeout_scenario(cls) -> Mock:
        """Create a mock that raises Timeout exception."""
        mock = Mock()
        mock.side_effect = Timeout("Connection timed out")
        return mock
    
    @classmethod
    def create_connection_error_scenario(cls) -> Mock:
        """Create a mock that raises ConnectionError."""
        mock = Mock()
        mock.side_effect = RequestsConnectionError("Failed to establish connection")
        return mock
    
    @classmethod
    def create_rate_limit_response(cls, retry_after: int = 60) -> Dict[str, Any]:
        """Create standard rate limit response."""
        return {
            "error": "rate_limit_exceeded",
            "message": "API rate limit exceeded",
            "retry_after": retry_after,
            "status_code": 429
        }
    
    @classmethod
    def create_paginated_response(cls, items: list, page: int = 1, 
                                per_page: int = 20, total: Optional[int] = None) -> Dict[str, Any]:
        """Create standard paginated response."""
        if total is None:
            total = len(items)
        
        return {
            "items": items[per_page * (page - 1):per_page * page],
            "page": page,
            "per_page": per_page,
            "total": total,
            "pages": (total + per_page - 1) // per_page
        }
    
    @classmethod
    def create_mock_session(cls, responses: Dict[str, Any]) -> Mock:
        """
        Create a mock session with predefined responses.
        
        Args:
            responses: Dict mapping URLs to response data
            
        Returns:
            Mock session object with get/post methods configured
        """
        session = Mock()
        
        def mock_request(method: str, url: str, **kwargs):
            response = Mock()
            response.status_code = 200
            response.headers = {"content-type": "application/json"}
            
            if url in responses:
                data = responses[url]
                if isinstance(data, Exception):
                    raise data
                response.json.return_value = data
                response.text = json.dumps(data)
            else:
                response.status_code = 404
                response.json.return_value = {"error": "not_found"}
                
            return response
        
        session.get.side_effect = lambda url, **kwargs: mock_request("GET", url, **kwargs)
        session.post.side_effect = lambda url, **kwargs: mock_request("POST", url, **kwargs)
        
        return session
    
    @classmethod
    def create_async_mock(cls, return_value: Any) -> MagicMock:
        """Create an async mock that returns the given value."""
        mock = MagicMock()
        mock.__aenter__.return_value = mock
        mock.__aexit__.return_value = None
        mock.return_value = return_value
        return mock


class ResponseBuilder:
    """
    Fluent builder for creating mock responses.
    
    Example:
        response = (ResponseBuilder()
                   .with_status(200)
                   .with_data({"id": 123})
                   .with_headers({"X-RateLimit-Remaining": "50"})
                   .build())
    """
    
    def __init__(self):
        self.status_code = 200
        self.data = {}
        self.headers = {}
        self.error = None
        
    def with_status(self, status_code: int) -> 'ResponseBuilder':
        """Set the status code."""
        self.status_code = status_code
        return self
        
    def with_data(self, data: Dict[str, Any]) -> 'ResponseBuilder':
        """Set the response data."""
        self.data = data
        return self
        
    def with_headers(self, headers: Dict[str, str]) -> 'ResponseBuilder':
        """Set response headers."""
        self.headers.update(headers)
        return self
        
    def with_error(self, error: Exception) -> 'ResponseBuilder':
        """Set an error to be raised."""
        self.error = error
        return self
        
    def build(self) -> Mock:
        """Build the mock response object."""
        if self.error:
            mock = Mock()
            mock.side_effect = self.error
            return mock
            
        response = Mock()
        response.status_code = self.status_code
        response.headers = self.headers
        response.json.return_value = self.data
        response.text = json.dumps(self.data)
        return response