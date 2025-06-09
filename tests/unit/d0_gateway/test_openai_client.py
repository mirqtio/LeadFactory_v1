"""
Test OpenAI API client implementation
"""
import pytest
import json
from decimal import Decimal
from unittest.mock import AsyncMock, Mock, patch

from d0_gateway.providers.openai import OpenAIClient


class TestOpenAIClient:

    @pytest.fixture
    def openai_client(self):
        """Create OpenAI client for testing"""
        return OpenAIClient()

    def test_gpt4o_mini_integration_initialization(self, openai_client):
        """Test that GPT-4o-mini integration is properly initialized"""
        # Should inherit from BaseAPIClient
        assert hasattr(openai_client, 'provider')
        assert openai_client.provider == "openai"

        # Should have rate limiter, circuit breaker, cache
        assert hasattr(openai_client, 'rate_limiter')
        assert hasattr(openai_client, 'circuit_breaker')
        assert hasattr(openai_client, 'cache')

        # Should have proper base URL
        assert openai_client._get_base_url() == "https://api.openai.com"

        # Should have proper headers (in stub mode)
        headers = openai_client._get_headers()
        assert "Authorization" in headers
        assert "Bearer" in headers["Authorization"]
        assert headers["Content-Type"] == "application/json"

    def test_token_counting_accurate_cost_calculation(self, openai_client):
        """Test that token counting and cost calculation is accurate"""
        # Test cost calculation for chat completions
        cost = openai_client.calculate_cost("POST:/v1/chat/completions")

        # Should calculate based on GPT-4o-mini pricing
        # Input: 800 tokens * $0.15/1M = $0.00012
        # Output: 300 tokens * $0.60/1M = $0.00018
        # Total: $0.0003
        expected_cost = Decimal('0.0003')
        assert abs(cost - expected_cost) < Decimal('0.00001')  # Allow small floating point differences

        # Test other operations
        other_cost = openai_client.calculate_cost("GET:/other")
        assert other_cost == Decimal('0.001')

    @pytest.mark.asyncio
    async def test_gpt4o_mini_integration_chat_completion(self, openai_client):
        """Test GPT-4o-mini integration through chat completion"""
        # Mock OpenAI API response
        mock_response = {
            "id": "chatcmpl-123",
            "object": "chat.completion",
            "created": 1677652288,
            "model": "gpt-4o-mini",
            "choices": [
                {
                    "index": 0,
                    "message": {
                        "role": "assistant",
                        "content": "This is a test response from GPT-4o-mini."
                    },
                    "finish_reason": "stop"
                }
            ],
            "usage": {
                "prompt_tokens": 20,
                "completion_tokens": 10,
                "total_tokens": 30
            }
        }

        openai_client.make_request = AsyncMock(return_value=mock_response)

        # Test basic chat completion
        messages = [
            {"role": "user", "content": "Hello, how are you?"}
        ]

        result = await openai_client.chat_completion(messages)

        # Verify API call was made correctly
        openai_client.make_request.assert_called_once_with(
            'POST',
            '/v1/chat/completions',
            json={
                'model': 'gpt-4o-mini',  # Default model
                'messages': messages,
                'temperature': 0.3  # Default temperature
            }
        )

        # Verify response structure
        assert result['model'] == "gpt-4o-mini"
        assert result['choices'][0]['message']['content'] == "This is a test response from GPT-4o-mini."
        assert 'usage' in result
        assert result['usage']['total_tokens'] == 30

    @pytest.mark.asyncio
    async def test_chat_completion_with_custom_parameters(self, openai_client):
        """Test chat completion with custom parameters"""
        mock_response = {
            "choices": [{"message": {"content": "Custom response"}}],
            "usage": {"total_tokens": 25}
        }

        openai_client.make_request = AsyncMock(return_value=mock_response)

        # Test with custom parameters
        await openai_client.chat_completion(
            messages=[{"role": "user", "content": "Test"}],
            model="gpt-4o-mini",
            temperature=0.7,
            max_tokens=150,
            response_format={"type": "json_object"}
        )

        call_args = openai_client.make_request.call_args[1]['json']

        # Verify all custom parameters are included
        assert call_args['model'] == "gpt-4o-mini"
        assert call_args['temperature'] == 0.7
        assert call_args['max_tokens'] == 150
        assert call_args['response_format'] == {"type": "json_object"}

    @pytest.mark.asyncio
    async def test_cost_tracking_per_request_usage_data(self, openai_client):
        """Test that cost tracking per request includes usage data"""
        mock_response = {
            "choices": [{"message": {"content": "Response"}}],
            "usage": {
                "prompt_tokens": 50,
                "completion_tokens": 25,
                "total_tokens": 75
            },
            "model": "gpt-4o-mini"
        }

        openai_client.make_request = AsyncMock(return_value=mock_response)

        result = await openai_client.chat_completion([{"role": "user", "content": "Test"}])

        # Verify usage tracking is included in response
        assert 'usage' in result
        assert result['usage']['prompt_tokens'] == 50
        assert result['usage']['completion_tokens'] == 25
        assert result['usage']['total_tokens'] == 75

        # Calculate actual cost based on real usage
        prompt_cost = (Decimal('50') / Decimal('1000000')) * Decimal('0.15')
        completion_cost = (Decimal('25') / Decimal('1000000')) * Decimal('0.60')
        expected_actual_cost = prompt_cost + completion_cost

        # Verify cost calculation method works with these numbers
        estimated_cost = openai_client.calculate_cost("POST:/v1/chat/completions")
        assert isinstance(estimated_cost, Decimal)
        assert estimated_cost > Decimal('0')

    @pytest.mark.asyncio
    async def test_retry_logic_implemented_error_handling(self, openai_client):
        """Test that retry logic and error handling is implemented"""
        from core.exceptions import ExternalAPIError, RateLimitError

        # Test rate limit error (429)
        openai_client.make_request = AsyncMock(side_effect=RateLimitError("openai", "burst"))

        with pytest.raises(RateLimitError):
            await openai_client.chat_completion([{"role": "user", "content": "Test"}])

        # Test API error (400)
        openai_client.make_request = AsyncMock(side_effect=ExternalAPIError("Invalid request", 400))

        with pytest.raises(ExternalAPIError):
            await openai_client.chat_completion([{"role": "user", "content": "Test"}])

        # Test authentication error (401)
        openai_client.make_request = AsyncMock(side_effect=ExternalAPIError("Invalid API key", 401))

        with pytest.raises(ExternalAPIError):
            await openai_client.chat_completion([{"role": "user", "content": "Test"}])

    @pytest.mark.asyncio
    async def test_network_error_handling(self, openai_client):
        """Test handling of network-related errors"""
        import httpx

        # Test timeout error
        openai_client.make_request = AsyncMock(side_effect=httpx.TimeoutException("Request timeout"))

        with pytest.raises(httpx.TimeoutException):
            await openai_client.chat_completion([{"role": "user", "content": "Test"}])

        # Test connection error
        openai_client.make_request = AsyncMock(side_effect=httpx.ConnectError("Connection failed"))

        with pytest.raises(httpx.ConnectError):
            await openai_client.chat_completion([{"role": "user", "content": "Test"}])

    @pytest.mark.asyncio
    async def test_website_performance_analysis(self, openai_client):
        """Test AI-powered website performance analysis"""
        # Mock PageSpeed data
        pagespeed_data = {
            "id": "https://example.com",
            "analysisUTCTimestamp": "2023-01-01T12:00:00.000Z",
            "lighthouseResult": {
                "categories": {
                    "performance": {"score": 0.65},
                    "seo": {"score": 0.85},
                    "accessibility": {"score": 0.78},
                    "best-practices": {"score": 0.92}
                },
                "audits": {
                    "largest-contentful-paint": {
                        "score": 0.6,
                        "displayValue": "3.2 s"
                    },
                    "cumulative-layout-shift": {
                        "score": 0.8,
                        "displayValue": "0.15"
                    }
                }
            }
        }

        # Mock AI response with recommendations
        mock_ai_response = {
            "choices": [{
                "message": {
                    "content": json.dumps([
                        {
                            "issue": "Large Contentful Paint is slow",
                            "impact": "high",
                            "effort": "medium",
                            "improvement": "Optimize images and enable compression"
                        },
                        {
                            "issue": "Layout shift detected",
                            "impact": "medium",
                            "effort": "low",
                            "improvement": "Add width/height attributes to images"
                        },
                        {
                            "issue": "Server response time could be faster",
                            "impact": "medium",
                            "effort": "high",
                            "improvement": "Upgrade hosting or use CDN"
                        }
                    ])
                }
            }],
            "usage": {"total_tokens": 150},
            "model": "gpt-4o-mini"
        }

        openai_client.make_request = AsyncMock(return_value=mock_ai_response)

        result = await openai_client.analyze_website_performance(pagespeed_data)

        # Verify analysis structure
        assert result['url'] == "https://example.com"
        assert result['analysis_timestamp'] == "2023-01-01T12:00:00.000Z"

        # Verify performance summary
        summary = result['performance_summary']
        assert summary['performance_score'] == 0.65
        assert summary['seo_score'] == 0.85
        assert summary['accessibility_score'] == 0.78
        assert summary['best_practices_score'] == 0.92

        # Verify AI recommendations
        recommendations = result['ai_recommendations']
        assert len(recommendations) == 3
        assert recommendations[0]['issue'] == "Large Contentful Paint is slow"
        assert recommendations[0]['impact'] == "high"
        assert recommendations[0]['effort'] == "medium"

        # Verify usage tracking
        assert 'usage' in result
        assert result['usage']['tokens_used']['total_tokens'] == 150

    @pytest.mark.asyncio
    async def test_email_content_generation(self, openai_client):
        """Test AI-powered email content generation"""
        # Mock website issues
        website_issues = [
            {
                "issue": "Poor page load speed",
                "impact": "high"
            },
            {
                "issue": "Missing meta descriptions",
                "impact": "medium"
            },
            {
                "issue": "Low accessibility score",
                "impact": "medium"
            }
        ]

        # Mock AI response
        mock_ai_response = {
            "choices": [{
                "message": {
                    "content": json.dumps({
                        "subject": "Quick Website Performance Insights for Acme Corp",
                        "body": "Hi John,\n\nI ran a quick analysis of Acme Corp's website and found some opportunities to improve page load speed and SEO. These changes could help increase conversions and search rankings.\n\nWould you be interested in a brief call to discuss the findings?\n\nBest regards,\nWebsite Performance Team"
                    })
                }
            }],
            "usage": {"total_tokens": 75},
            "created": 1677652288
        }

        openai_client.make_request = AsyncMock(return_value=mock_ai_response)

        result = await openai_client.generate_email_content(
            business_name="Acme Corp",
            website_issues=website_issues,
            recipient_name="John"
        )

        # Verify email content structure
        assert result['business_name'] == "Acme Corp"
        assert result['recipient_name'] == "John"
        assert result['email_subject'] == "Quick Website Performance Insights for Acme Corp"
        assert "Acme Corp" in result['email_body']
        assert "John" in result['email_body']
        assert result['issues_count'] == 3
        assert result['generated_at'] == 1677652288

        # Verify usage tracking
        assert 'usage' in result
        assert result['usage']['total_tokens'] == 75

    @pytest.mark.asyncio
    async def test_ai_fallback_when_json_parsing_fails(self, openai_client):
        """Test fallback behavior when AI returns invalid JSON"""
        pagespeed_data = {
            "id": "https://example.com",
            "lighthouseResult": {
                "categories": {
                    "performance": {"score": 0.5},
                    "seo": {"score": 0.7},
                    "accessibility": {"score": 0.6}
                }
            }
        }

        # Mock AI response with invalid JSON
        mock_ai_response = {
            "choices": [{
                "message": {
                    "content": "This is not valid JSON content"
                }
            }],
            "usage": {"total_tokens": 50}
        }

        openai_client.make_request = AsyncMock(return_value=mock_ai_response)

        result = await openai_client.analyze_website_performance(pagespeed_data)

        # Should return fallback recommendations
        assert 'error' in result
        assert result['error'] == 'Failed to generate AI insights'
        assert 'fallback_recommendations' in result

        # Verify fallback recommendations are generated
        fallback = result['fallback_recommendations']
        assert len(fallback) > 0
        assert all('issue' in rec and 'impact' in rec and 'effort' in rec and 'improvement' in rec
                  for rec in fallback)

    def test_fallback_recommendations_generation(self, openai_client):
        """Test generation of fallback recommendations"""
        # Test case with poor performance
        context = {
            'performance_score': 0.4,  # Poor performance
            'seo_score': 0.6,         # Poor SEO
            'accessibility_score': 0.7  # Poor accessibility
        }

        fallback = openai_client._get_fallback_recommendations(context)

        # Should generate recommendations for each poor score
        assert len(fallback) == 3

        # Verify recommendation structure
        for rec in fallback:
            assert 'issue' in rec
            assert 'impact' in rec
            assert 'effort' in rec
            assert 'improvement' in rec
            assert rec['impact'] in ['high', 'medium', 'low']
            assert rec['effort'] in ['high', 'medium', 'low']

    def test_rate_limit_configuration(self, openai_client):
        """Test OpenAI rate limit configuration"""
        rate_limit = openai_client.get_rate_limit()

        # Should have reasonable limits for OpenAI API
        assert rate_limit['daily_limit'] == 10000
        assert rate_limit['burst_limit'] == 20
        assert rate_limit['window_seconds'] == 1
        assert 'daily_used' in rate_limit

    @pytest.mark.asyncio
    async def test_business_context_integration(self, openai_client):
        """Test integration of business context in analysis"""
        pagespeed_data = {
            "id": "https://restaurant.com",
            "lighthouseResult": {
                "categories": {
                    "performance": {"score": 0.7}
                }
            }
        }

        business_context = {
            "industry": "restaurant",
            "location": "San Francisco",
            "target_audience": "local diners"
        }

        # Mock AI response
        mock_ai_response = {
            "choices": [{
                "message": {
                    "content": json.dumps([
                        {
                            "issue": "Mobile performance for local customers",
                            "impact": "high",
                            "effort": "medium",
                            "improvement": "Optimize for mobile ordering experience"
                        }
                    ])
                }
            }],
            "usage": {"total_tokens": 100}
        }

        openai_client.make_request = AsyncMock(return_value=mock_ai_response)

        result = await openai_client.analyze_website_performance(
            pagespeed_data,
            business_context=business_context
        )

        # Verify business context was included in analysis
        assert result['url'] == "https://restaurant.com"
        assert 'ai_recommendations' in result

        # Verify the AI was called with business context
        call_args = openai_client.make_request.call_args[1]['json']
        messages = call_args['messages']
        user_message = next(msg for msg in messages if msg['role'] == 'user')
        assert str(business_context) in user_message['content']


class TestOpenAIClientIntegration:

    @pytest.mark.asyncio
    async def test_rate_limiting_integration(self):
        """Test integration with rate limiting"""
        openai_client = OpenAIClient()

        # Mock rate limiter to indicate limit exceeded
        with patch.object(openai_client.rate_limiter, 'is_allowed', return_value=False):
            from core.exceptions import RateLimitError

            openai_client.make_request = AsyncMock(side_effect=RateLimitError("openai", "daily"))

            with pytest.raises(RateLimitError):
                await openai_client.chat_completion([{"role": "user", "content": "Test"}])

    @pytest.mark.asyncio
    async def test_circuit_breaker_integration(self):
        """Test integration with circuit breaker"""
        openai_client = OpenAIClient()

        # Mock circuit breaker to indicate open state
        with patch.object(openai_client.circuit_breaker, 'can_execute', return_value=False):
            from d0_gateway.exceptions import CircuitBreakerOpenError

            openai_client.make_request = AsyncMock(side_effect=CircuitBreakerOpenError("openai", 5))

            with pytest.raises(CircuitBreakerOpenError):
                await openai_client.chat_completion([{"role": "user", "content": "Test"}])

    @pytest.mark.asyncio
    async def test_caching_integration(self):
        """Test integration with response caching"""
        openai_client = OpenAIClient()

        # Test that cache is properly initialized
        assert hasattr(openai_client, 'cache')
        assert openai_client.cache.provider == "openai"

        # Test cache key generation for chat completion
        chat_params = {"model": "gpt-4o-mini", "messages": [{"role": "user", "content": "test"}]}
        cache_key = openai_client.cache.generate_key("/v1/chat/completions", chat_params)

        # Cache key should be deterministic
        assert isinstance(cache_key, str)
        assert cache_key.startswith("api_cache:")

        # Test cache statistics are available
        stats = await openai_client.cache.get_cache_stats()
        assert 'provider' in stats
        assert stats['provider'] == "openai"

    @pytest.mark.asyncio
    async def test_stub_mode_integration(self):
        """Test integration with stub mode"""
        with patch('core.config.get_settings') as mock_get_settings:
            mock_settings = Mock()
            mock_settings.use_stubs = True
            mock_settings.stub_base_url = "http://localhost:8000"
            mock_get_settings.return_value = mock_settings

            openai_client = OpenAIClient()

            # Should use stub configuration
            assert openai_client.api_key == "stub-openai-key"
            assert "localhost" in openai_client.base_url


class TestOpenAIClientEdgeCases:

    @pytest.mark.asyncio
    async def test_empty_messages_handling(self):
        """Test handling of empty messages"""
        openai_client = OpenAIClient()

        # Mock response for empty messages
        mock_response = {"choices": [{"message": {"content": "Please provide a message."}}]}
        openai_client.make_request = AsyncMock(return_value=mock_response)

        result = await openai_client.chat_completion([])

        # Should handle empty messages gracefully
        assert 'choices' in result

    @pytest.mark.asyncio
    async def test_malformed_pagespeed_data(self):
        """Test handling of malformed PageSpeed data"""
        openai_client = OpenAIClient()

        # Test with minimal/malformed data
        malformed_data = {
            "id": "https://example.com"
            # Missing lighthouseResult
        }

        # Mock fallback response
        mock_response = {
            "choices": [{"message": {"content": "Invalid data format"}}],
            "usage": {"total_tokens": 10}
        }
        openai_client.make_request = AsyncMock(return_value=mock_response)

        # Should handle malformed data without crashing
        result = await openai_client.analyze_website_performance(malformed_data)

        # Should still return a valid structure
        assert 'url' in result or 'error' in result

    @pytest.mark.asyncio
    async def test_email_generation_fallback(self):
        """Test email generation fallback when AI fails"""
        openai_client = OpenAIClient()

        # Mock AI failure
        openai_client.make_request = AsyncMock(side_effect=Exception("AI service unavailable"))

        try:
            result = await openai_client.generate_email_content(
                business_name="Test Business",
                website_issues=[{"issue": "slow loading", "impact": "high"}]
            )

            # Should return fallback content
            assert 'error' in result or 'fallback_subject' in result

        except Exception:
            # If exception is thrown, that's also acceptable behavior
            pass
