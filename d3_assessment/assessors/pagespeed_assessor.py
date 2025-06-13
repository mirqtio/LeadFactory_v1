"""
PageSpeed assessor using Google PageSpeed Insights API
PRD v1.2 - Website performance analysis

Timeout: 30s per device
Cost: $0.00 (free API)
Output: pagespeed_json column
"""
import asyncio
from typing import Dict, Any, Optional

from d3_assessment.assessors.base import BaseAssessor, AssessmentResult
from d3_assessment.models import AssessmentType
from d3_assessment.exceptions import AssessmentError, AssessmentTimeoutError
from d0_gateway.providers.pagespeed import PageSpeedClient
from core.logging import get_logger

logger = get_logger(__name__, domain="d3")


class PageSpeedAssessor(BaseAssessor):
    """Assess website performance using Google PageSpeed Insights"""
    
    def __init__(self):
        super().__init__()
        self.timeout = 30  # 30 seconds per device
        self._client = None
        
    @property
    def assessment_type(self) -> AssessmentType:
        return AssessmentType.PAGESPEED
        
    async def _get_client(self) -> PageSpeedClient:
        """Get or create PageSpeed client"""
        if not self._client:
            self._client = PageSpeedClient()
        return self._client
        
    async def assess(self, url: str, business_data: Dict[str, Any]) -> AssessmentResult:
        """
        Assess website performance using PageSpeed Insights
        
        Args:
            url: Website URL to assess
            business_data: Business information (not used for PageSpeed)
            
        Returns:
            AssessmentResult with PageSpeed data
        """
        try:
            client = await self._get_client()
            
            # Run mobile analysis (PRD v1.2 focuses on mobile)
            try:
                mobile_result = await asyncio.wait_for(
                    client.analyze_url(
                        url=url,
                        strategy="mobile",
                        categories=["performance", "accessibility", "best-practices", "seo"]
                    ),
                    timeout=self.timeout
                )
            except asyncio.TimeoutError:
                raise AssessmentTimeoutError(f"PageSpeed mobile analysis timed out after {self.timeout}s")
            
            # Extract key metrics
            lighthouse = mobile_result.get('lighthouseResult', {})
            categories = lighthouse.get('categories', {})
            audits = lighthouse.get('audits', {})
            
            # Extract scores
            scores = {}
            for category in ['performance', 'accessibility', 'best-practices', 'seo']:
                if category in categories:
                    scores[category] = int(categories[category].get('score', 0) * 100)
            
            # Extract Core Web Vitals
            cwv = {}
            if 'largest-contentful-paint' in audits:
                cwv['lcp'] = audits['largest-contentful-paint'].get('numericValue')
            if 'cumulative-layout-shift' in audits:
                cwv['cls'] = audits['cumulative-layout-shift'].get('numericValue')
            if 'max-potential-fid' in audits:
                cwv['fid'] = audits['max-potential-fid'].get('numericValue')
            
            # Extract opportunities
            opportunities = []
            for audit_id, audit in audits.items():
                if (audit.get('score', 1) < 1 and 
                    'details' in audit and 
                    audit.get('details', {}).get('overallSavingsMs', 0) > 0):
                    opportunities.append({
                        'id': audit_id,
                        'title': audit.get('title', ''),
                        'savings_ms': audit['details'].get('overallSavingsMs', 0)
                    })
            
            # Sort by savings
            opportunities.sort(key=lambda x: x['savings_ms'], reverse=True)
            
            # Build PageSpeed data
            pagespeed_data = {
                'scores': scores,
                'core_web_vitals': cwv,
                'opportunities': opportunities[:5],  # Top 5 opportunities
                'fetch_time': lighthouse.get('fetchTime'),
                'user_agent': lighthouse.get('userAgent'),
                'environment': lighthouse.get('environment', {}),
                'config_settings': lighthouse.get('configSettings', {})
            }
            
            return AssessmentResult(
                assessment_type=self.assessment_type,
                status="completed",
                data={
                    'pagespeed_json': pagespeed_data
                },
                metrics={
                    'performance_score': scores.get('performance', 0),
                    'mobile_friendly': scores.get('performance', 0) >= 50,
                    'lcp_ms': cwv.get('lcp'),
                    'cls_score': cwv.get('cls'),
                    'fid_ms': cwv.get('fid'),
                    'opportunities_count': len(opportunities)
                },
                cost=0.0  # PageSpeed API is free
            )
            
        except AssessmentTimeoutError:
            raise
        except Exception as e:
            logger.error(f"PageSpeed assessment failed for {url}: {e}")
            
            # Return minimal result with error
            return AssessmentResult(
                assessment_type=self.assessment_type,
                status="failed",
                data={'pagespeed_json': {}},
                error_message=f"PageSpeed API error: {str(e)}"
            )
    
    def calculate_cost(self) -> float:
        """PageSpeed API is free"""
        return 0.0
    
    def is_available(self) -> bool:
        """PageSpeed is always available (no API key required)"""
        return True