"""
Google PageSpeed Insights API v5 client implementation
"""
from typing import Dict, Any, Optional, List
from decimal import Decimal
import urllib.parse

from ..base import BaseAPIClient


class PageSpeedClient(BaseAPIClient):
    """Google PageSpeed Insights API v5 client"""

    def __init__(self, api_key: Optional[str] = None):
        super().__init__(
            provider="pagespeed",
            api_key=api_key
        )

    def _get_base_url(self) -> str:
        """Get PageSpeed API base URL"""
        return "https://www.googleapis.com"

    def _get_headers(self) -> Dict[str, str]:
        """Get PageSpeed API headers"""
        return {
            "Content-Type": "application/json"
        }

    def get_rate_limit(self) -> Dict[str, int]:
        """Get PageSpeed rate limit configuration"""
        return {
            'daily_limit': 25000,
            'daily_used': 0,  # Would be fetched from Redis in real implementation
            'burst_limit': 50,
            'window_seconds': 1
        }

    def calculate_cost(self, operation: str, **kwargs) -> Decimal:
        """
        Calculate cost for PageSpeed API operations

        PageSpeed API is free up to 25,000 queries/day
        Beyond that, $4 per 1,000 queries
        """
        if operation.startswith("GET:/pagespeedonline/v5/runPagespeed"):
            # Free tier up to 25,000/day
            return Decimal('0.000')
        else:
            # Paid tier estimate
            return Decimal('0.004')

    async def analyze_url(
        self,
        url: str,
        strategy: str = "mobile",
        categories: Optional[List[str]] = None,
        locale: Optional[str] = None,
        utm_campaign: Optional[str] = None,
        utm_source: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Analyze a URL with PageSpeed Insights

        Args:
            url: URL to analyze (required)
            strategy: Analysis strategy - 'mobile' or 'desktop'
            categories: List of categories to analyze (performance, accessibility, best-practices, seo, pwa)
            locale: Locale for the analysis (e.g. 'en')
            utm_campaign: UTM campaign parameter
            utm_source: UTM source parameter

        Returns:
            Dict containing PageSpeed analysis results
        """
        params = {
            'url': url,
            'strategy': strategy,
            'key': self.api_key
        }

        # Add optional parameters
        if categories:
            # Join categories with comma
            params['category'] = ','.join(categories)
        else:
            # Default categories for comprehensive analysis
            params['category'] = 'performance,accessibility,best-practices,seo'

        if locale:
            params['locale'] = locale
        if utm_campaign:
            params['utm_campaign'] = utm_campaign
        if utm_source:
            params['utm_source'] = utm_source

        return await self.make_request(
            'GET',
            '/pagespeedonline/v5/runPagespeed',
            params=params
        )

    async def analyze_mobile_and_desktop(self, url: str) -> Dict[str, Any]:
        """
        Analyze URL for both mobile and desktop

        Args:
            url: URL to analyze

        Returns:
            Dict containing both mobile and desktop results
        """
        mobile_result = await self.analyze_url(url, strategy="mobile")
        desktop_result = await self.analyze_url(url, strategy="desktop")

        return {
            'url': url,
            'mobile': mobile_result,
            'desktop': desktop_result,
            'analyzed_at': mobile_result.get('analysisUTCTimestamp')
        }

    async def get_core_web_vitals(self, url: str, strategy: str = "mobile") -> Dict[str, Any]:
        """
        Extract Core Web Vitals from PageSpeed analysis

        Args:
            url: URL to analyze
            strategy: Analysis strategy

        Returns:
            Dict containing Core Web Vitals metrics
        """
        result = await self.analyze_url(url, strategy=strategy)

        lighthouse_result = result.get('lighthouseResult', {})
        audits = lighthouse_result.get('audits', {})

        # Extract Core Web Vitals
        cwv = {
            'url': url,
            'strategy': strategy,
            'largest_contentful_paint': None,
            'first_input_delay': None,
            'cumulative_layout_shift': None,
            'first_contentful_paint': None,
            'speed_index': None,
            'performance_score': None
        }

        # LCP (Largest Contentful Paint)
        if 'largest-contentful-paint' in audits:
            lcp = audits['largest-contentful-paint']
            cwv['largest_contentful_paint'] = {
                'score': lcp.get('score'),
                'numericValue': lcp.get('numericValue'),
                'displayValue': lcp.get('displayValue')
            }

        # FID (First Input Delay) - using max-potential-fid as proxy
        if 'max-potential-fid' in audits:
            fid = audits['max-potential-fid']
            cwv['first_input_delay'] = {
                'score': fid.get('score'),
                'numericValue': fid.get('numericValue'),
                'displayValue': fid.get('displayValue')
            }

        # CLS (Cumulative Layout Shift)
        if 'cumulative-layout-shift' in audits:
            cls = audits['cumulative-layout-shift']
            cwv['cumulative_layout_shift'] = {
                'score': cls.get('score'),
                'numericValue': cls.get('numericValue'),
                'displayValue': cls.get('displayValue')
            }

        # Additional metrics
        if 'first-contentful-paint' in audits:
            fcp = audits['first-contentful-paint']
            cwv['first_contentful_paint'] = {
                'score': fcp.get('score'),
                'numericValue': fcp.get('numericValue'),
                'displayValue': fcp.get('displayValue')
            }

        if 'speed-index' in audits:
            si = audits['speed-index']
            cwv['speed_index'] = {
                'score': si.get('score'),
                'numericValue': si.get('numericValue'),
                'displayValue': si.get('displayValue')
            }

        # Overall performance score
        categories = lighthouse_result.get('categories', {})
        if 'performance' in categories:
            cwv['performance_score'] = categories['performance'].get('score')

        return cwv

    async def batch_analyze_urls(
        self,
        urls: List[str],
        strategy: str = "mobile",
        include_core_web_vitals: bool = True
    ) -> Dict[str, Any]:
        """
        Analyze multiple URLs efficiently

        Args:
            urls: List of URLs to analyze
            strategy: Analysis strategy
            include_core_web_vitals: Whether to extract Core Web Vitals

        Returns:
            Dict containing results for all URLs
        """
        results = {}

        for url in urls:
            try:
                if include_core_web_vitals:
                    result = await self.get_core_web_vitals(url, strategy)
                else:
                    result = await self.analyze_url(url, strategy)

                results[url] = result

            except Exception as e:
                self.logger.error(f"Failed to analyze URL {url}: {e}")
                results[url] = {"error": str(e), "url": url}

        return {
            "urls": results,
            "total_urls": len(urls),
            "successful_urls": len([r for r in results.values() if "error" not in r]),
            "strategy": strategy
        }

    def extract_opportunities(self, pagespeed_result: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Extract optimization opportunities from PageSpeed result

        Args:
            pagespeed_result: Raw PageSpeed API response

        Returns:
            List of optimization opportunities
        """
        lighthouse_result = pagespeed_result.get('lighthouseResult', {})
        audits = lighthouse_result.get('audits', {})

        opportunities = []

        # Look for failed audits that have savings
        for audit_id, audit in audits.items():
            if (audit.get('score', 1) < 1 and  # Failed or partially failed
                'details' in audit and
                audit.get('details', {}).get('overallSavingsMs', 0) > 0):

                opportunities.append({
                    'id': audit_id,
                    'title': audit.get('title', ''),
                    'description': audit.get('description', ''),
                    'savings_ms': audit['details'].get('overallSavingsMs', 0),
                    'score': audit.get('score', 0),
                    'impact': self._categorize_impact(audit['details'].get('overallSavingsMs', 0))
                })

        # Sort by potential savings
        opportunities.sort(key=lambda x: x['savings_ms'], reverse=True)

        return opportunities

    def _categorize_impact(self, savings_ms: float) -> str:
        """Categorize impact level based on potential savings"""
        if savings_ms >= 1000:  # 1+ seconds
            return "high"
        elif savings_ms >= 500:  # 0.5+ seconds
            return "medium"
        else:
            return "low"
