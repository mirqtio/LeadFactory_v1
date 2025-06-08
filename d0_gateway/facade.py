"""
D0 Gateway facade - unified interface for all external APIs
"""
from typing import Dict, Any, Optional, List
from decimal import Decimal
import asyncio

from core.logging import get_logger
from .factory import GatewayClientFactory, get_gateway_factory
from .metrics import GatewayMetrics


class GatewayFacade:
    """
    Unified facade for all external API operations.
    Provides a single entry point for Yelp, PageSpeed, and OpenAI APIs.
    """
    
    def __init__(self, factory: Optional[GatewayClientFactory] = None):
        """
        Initialize the gateway facade
        
        Args:
            factory: Optional factory instance (uses global if None)
        """
        self.logger = get_logger("gateway.facade", domain="d0")
        self.factory = factory or get_gateway_factory()
        self.metrics = GatewayMetrics()
        
        self.logger.info("Gateway facade initialized")
    
    # Yelp API Methods
    async def search_businesses(
        self,
        term: str,
        location: str,
        categories: Optional[str] = None,
        limit: int = 20,
        offset: int = 0,
        sort_by: str = "best_match",
        price: Optional[str] = None,
        open_now: Optional[bool] = None,
        attributes: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Search for businesses using Yelp API
        
        Args:
            term: Search term (e.g., "restaurants", "coffee")
            location: Location (e.g., "San Francisco, CA", "10001")
            categories: Business categories (e.g., "restaurants,bars")
            limit: Number of results to return (max 50)
            offset: Offset for pagination
            sort_by: Sort order (best_match, rating, review_count, distance)
            price: Price filter (1, 2, 3, 4 representing $, $$, $$$, $$$$)
            open_now: Filter for businesses open now
            attributes: Additional attributes filter
            
        Returns:
            Yelp search results
        """
        try:
            client = self.factory.create_client('yelp')
            result = await client.search_businesses(
                location=location,
                categories=categories,
                term=term,
                limit=limit,
                offset=offset,
                sort_by=sort_by,
                price=price,
                open_now=open_now
                # Note: 'attributes' is not supported by YelpClient
            )
            
            self.logger.info(f"Yelp search completed: {term} in {location}")
            return result
            
        except Exception as e:
            self.logger.error(f"Yelp search failed: {e}")
            raise
    
    async def get_business_details(self, business_id: str) -> Dict[str, Any]:
        """
        Get detailed information about a specific business
        
        Args:
            business_id: Yelp business ID
            
        Returns:
            Business details
        """
        try:
            client = self.factory.create_client('yelp')
            result = await client.get_business_details(business_id)
            
            self.logger.info(f"Yelp business details retrieved: {business_id}")
            return result
            
        except Exception as e:
            self.logger.error(f"Failed to get business details: {e}")
            raise
    
    # PageSpeed API Methods
    async def analyze_website(
        self,
        url: str,
        strategy: str = "mobile",
        categories: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        Analyze website performance using PageSpeed Insights
        
        Args:
            url: Website URL to analyze
            strategy: Analysis strategy ('mobile' or 'desktop')
            categories: Categories to analyze (performance, accessibility, etc.)
            
        Returns:
            PageSpeed analysis results
        """
        try:
            client = self.factory.create_client('pagespeed')
            result = await client.analyze_url(
                url=url,
                strategy=strategy,
                categories=categories
            )
            
            self.logger.info(f"PageSpeed analysis completed: {url} ({strategy})")
            return result
            
        except Exception as e:
            self.logger.error(f"PageSpeed analysis failed: {e}")
            raise
    
    async def get_core_web_vitals(
        self,
        url: str,
        strategy: str = "mobile"
    ) -> Dict[str, Any]:
        """
        Get Core Web Vitals for a website
        
        Args:
            url: Website URL to analyze
            strategy: Analysis strategy ('mobile' or 'desktop')
            
        Returns:
            Core Web Vitals data
        """
        try:
            client = self.factory.create_client('pagespeed')
            result = await client.get_core_web_vitals(url, strategy)
            
            self.logger.info(f"Core Web Vitals retrieved: {url}")
            return result
            
        except Exception as e:
            self.logger.error(f"Failed to get Core Web Vitals: {e}")
            raise
    
    async def analyze_multiple_websites(
        self,
        urls: List[str],
        strategy: str = "mobile"
    ) -> Dict[str, Any]:
        """
        Analyze multiple websites in parallel
        
        Args:
            urls: List of URLs to analyze
            strategy: Analysis strategy
            
        Returns:
            Results for all URLs
        """
        try:
            client = self.factory.create_client('pagespeed')
            result = await client.batch_analyze_urls(urls, strategy)
            
            self.logger.info(f"Batch analysis completed: {len(urls)} URLs")
            return result
            
        except Exception as e:
            self.logger.error(f"Batch analysis failed: {e}")
            raise
    
    # OpenAI API Methods
    async def generate_website_insights(
        self,
        pagespeed_data: Dict[str, Any],
        business_context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Generate AI-powered website insights from PageSpeed data
        
        Args:
            pagespeed_data: PageSpeed Insights results
            business_context: Additional business context
            
        Returns:
            AI-generated insights and recommendations
        """
        try:
            client = self.factory.create_client('openai')
            result = await client.analyze_website_performance(
                pagespeed_data=pagespeed_data,
                business_context=business_context
            )
            
            self.logger.info("Website insights generated")
            return result
            
        except Exception as e:
            self.logger.error(f"Failed to generate website insights: {e}")
            raise
    
    async def generate_personalized_email(
        self,
        business_name: str,
        website_issues: List[Dict[str, Any]],
        recipient_name: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Generate personalized email content for outreach
        
        Args:
            business_name: Name of the business
            website_issues: List of identified website issues
            recipient_name: Name of the recipient (if known)
            
        Returns:
            Generated email content
        """
        try:
            client = self.factory.create_client('openai')
            result = await client.generate_email_content(
                business_name=business_name,
                website_issues=website_issues,
                recipient_name=recipient_name
            )
            
            self.logger.info(f"Email content generated for {business_name}")
            return result
            
        except Exception as e:
            self.logger.error(f"Failed to generate email content: {e}")
            raise
    
    # Combined Workflow Methods
    async def complete_business_analysis(
        self,
        business_id: str,
        business_url: Optional[str] = None,
        include_email_generation: bool = False
    ) -> Dict[str, Any]:
        """
        Complete analysis workflow: Yelp → PageSpeed → AI insights
        
        Args:
            business_id: Yelp business ID
            business_url: Business website URL (if not in Yelp data)
            include_email_generation: Whether to generate email content
            
        Returns:
            Complete analysis results
        """
        analysis_results = {
            'business_id': business_id,
            'business_data': None,
            'website_analysis': None,
            'ai_insights': None,
            'email_content': None,
            'errors': []
        }
        
        try:
            # Step 1: Get business details from Yelp
            business_data = await self.get_business_details(business_id)
            analysis_results['business_data'] = business_data
            
            # Extract website URL
            website_url = business_url or business_data.get('url')
            if not website_url:
                analysis_results['errors'].append("No website URL found")
                return analysis_results
            
            # Step 2: Analyze website with PageSpeed
            try:
                website_analysis = await self.analyze_website(website_url)
                analysis_results['website_analysis'] = website_analysis
                
                # Step 3: Generate AI insights
                try:
                    business_context = {
                        'name': business_data.get('name'),
                        'categories': business_data.get('categories', []),
                        'location': business_data.get('location', {})
                    }
                    
                    ai_insights = await self.generate_website_insights(
                        website_analysis, business_context
                    )
                    analysis_results['ai_insights'] = ai_insights
                    
                    # Step 4: Generate email content if requested
                    if include_email_generation and ai_insights.get('ai_recommendations'):
                        try:
                            email_content = await self.generate_personalized_email(
                                business_name=business_data.get('name', 'Business'),
                                website_issues=ai_insights['ai_recommendations'],
                                recipient_name=None
                            )
                            analysis_results['email_content'] = email_content
                            
                        except Exception as e:
                            analysis_results['errors'].append(f"Email generation failed: {e}")
                    
                except Exception as e:
                    analysis_results['errors'].append(f"AI insights failed: {e}")
                
            except Exception as e:
                analysis_results['errors'].append(f"Website analysis failed: {e}")
            
        except Exception as e:
            analysis_results['errors'].append(f"Business lookup failed: {e}")
        
        self.logger.info(f"Complete analysis finished for {business_id}")
        return analysis_results
    
    # Gateway Management Methods
    def get_gateway_status(self) -> Dict[str, Any]:
        """
        Get comprehensive gateway status
        
        Returns:
            Gateway status information
        """
        try:
            # Get factory status
            factory_status = self.factory.get_client_status()
            
            # Get health check
            health_status = self.factory.health_check()
            
            # Get metrics summary
            metrics_summary = self.metrics.get_metrics_summary()
            
            return {
                'status': 'operational',
                'factory': factory_status,
                'health': health_status,
                'metrics': metrics_summary,
                'facade_version': '1.0.0'
            }
            
        except Exception as e:
            self.logger.error(f"Failed to get gateway status: {e}")
            return {
                'status': 'error',
                'error': str(e)
            }
    
    async def get_all_rate_limits(self) -> Dict[str, Any]:
        """
        Get rate limit status for all providers
        
        Returns:
            Rate limit information for all providers
        """
        rate_limits = {}
        
        for provider in self.factory.get_provider_names():
            try:
                client = self.factory.create_client(provider)
                rate_limits[provider] = client.get_rate_limit()
            except Exception as e:
                rate_limits[provider] = {'error': str(e)}
        
        return rate_limits
    
    async def calculate_total_costs(self) -> Dict[str, Decimal]:
        """
        Calculate total costs across all providers
        
        Returns:
            Cost breakdown by provider
        """
        costs = {}
        
        for provider in self.factory.get_provider_names():
            try:
                client = self.factory.create_client(provider)
                # This would typically query metrics for actual costs
                # For now, return estimated costs
                costs[provider] = Decimal('0.00')
            except Exception as e:
                self.logger.error(f"Failed to get costs for {provider}: {e}")
                costs[provider] = Decimal('0.00')
        
        return costs
    
    def invalidate_all_caches(self) -> None:
        """Invalidate all cached clients and responses"""
        self.factory.invalidate_cache()
        self.logger.info("All caches invalidated")


# Global facade instance
_facade_instance = None


def get_gateway_facade() -> GatewayFacade:
    """
    Get the global gateway facade instance
    
    Returns:
        GatewayFacade instance
    """
    global _facade_instance
    if _facade_instance is None:
        _facade_instance = GatewayFacade()
    return _facade_instance