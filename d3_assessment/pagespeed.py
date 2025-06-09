"""
PageSpeed Assessor - Task 031

Comprehensive PageSpeed assessment using Google PageSpeed Insights API.
Extracts Core Web Vitals, scores, and performance issues with mobile-first approach.

Acceptance Criteria:
- Core Web Vitals extracted
- All scores captured  
- Issue extraction works
- Mobile-first approach
"""
import uuid
from typing import Dict, Any, Optional, List
from decimal import Decimal
from datetime import datetime
import asyncio

from d0_gateway.providers.pagespeed import PageSpeedClient
from .models import (
    AssessmentResult, PageSpeedAssessment, AssessmentSession, AssessmentCost
)
from .types import (
    AssessmentStatus, AssessmentType, PageSpeedMetric, CostType
)


class PageSpeedAssessor:
    """
    PageSpeed assessment service with mobile-first approach
    
    Handles comprehensive website performance analysis using Google PageSpeed Insights,
    extracting Core Web Vitals, performance scores, and optimization opportunities.
    """
    
    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize PageSpeed assessor
        
        Args:
            api_key: Google PageSpeed API key (optional, will use environment)
        """
        self.client = PageSpeedClient(api_key=api_key)
        self.mobile_first = True  # Mobile-first approach per acceptance criteria
        
    async def assess_website(
        self,
        business_id: str,
        url: str,
        session_id: Optional[str] = None,
        include_desktop: bool = True
    ) -> AssessmentResult:
        """
        Perform comprehensive PageSpeed assessment
        
        Args:
            business_id: Business identifier
            url: Website URL to assess
            session_id: Optional assessment session ID
            include_desktop: Whether to include desktop analysis
            
        Returns:
            AssessmentResult with comprehensive PageSpeed data
        """
        assessment_id = str(uuid.uuid4())
        started_at = datetime.utcnow()
        
        try:
            # Create assessment record
            assessment = AssessmentResult(
                id=assessment_id,
                business_id=business_id,
                session_id=session_id,
                assessment_type=AssessmentType.PAGESPEED,
                status=AssessmentStatus.RUNNING,
                url=url,
                domain=self._extract_domain(url),
                started_at=started_at
            )
            
            # Mobile-first approach - always start with mobile
            mobile_result = await self._analyze_mobile(assessment_id, url)
            desktop_result = None
            
            if include_desktop:
                desktop_result = await self._analyze_desktop(assessment_id, url)
            
            # Extract and populate core metrics
            self._populate_core_metrics(assessment, mobile_result, desktop_result)
            
            # Extract Core Web Vitals
            self._extract_core_web_vitals(assessment, mobile_result)
            
            # Extract performance issues and opportunities
            issues = self._extract_issues(mobile_result, desktop_result)
            
            # Store comprehensive data in JSONB fields
            assessment.pagespeed_data = {
                "mobile": mobile_result,
                "desktop": desktop_result,
                "analysis_timestamp": started_at.isoformat(),
                "mobile_first": self.mobile_first
            }
            
            # Calculate total cost
            total_cost = await self._calculate_assessment_cost(
                assessment_id, session_id, mobile_result, desktop_result
            )
            assessment.total_cost_usd = total_cost
            
            # Mark as completed
            assessment.status = AssessmentStatus.COMPLETED
            assessment.completed_at = datetime.utcnow()
            processing_seconds = (assessment.completed_at - started_at).total_seconds()
            assessment.processing_time_ms = max(1, int(processing_seconds * 1000))  # At least 1ms
            
            return assessment
            
        except Exception as e:
            # Mark as failed with error details
            assessment.status = AssessmentStatus.FAILED
            assessment.error_message = str(e)
            assessment.completed_at = datetime.utcnow()
            raise
    
    async def _analyze_mobile(self, assessment_id: str, url: str) -> Dict[str, Any]:
        """Analyze website on mobile device (mobile-first approach)"""
        try:
            result = await self.client.analyze_url(
                url=url,
                strategy="mobile",
                categories=["performance", "accessibility", "best-practices", "seo"]
            )
            
            # Store detailed mobile assessment
            mobile_assessment = PageSpeedAssessment(
                assessment_id=assessment_id,
                is_mobile=True,
                lighthouse_data=result.get("lighthouseResult", {}),
                lighthouse_version=result.get("lighthouseResult", {}).get("lighthouseVersion"),
                user_agent=result.get("lighthouseResult", {}).get("userAgent"),
                fetch_time=datetime.utcnow()
            )
            
            # Extract scores for quick access
            self._extract_lighthouse_scores(mobile_assessment, result)
            
            # Extract Core Web Vitals details
            self._extract_detailed_cwv(mobile_assessment, result)
            
            # Extract opportunities and diagnostics
            mobile_assessment.opportunities = self._extract_opportunities(result)
            mobile_assessment.diagnostics = self._extract_diagnostics(result)
            
            return result
            
        except Exception as e:
            raise Exception(f"Mobile analysis failed: {str(e)}")
    
    async def _analyze_desktop(self, assessment_id: str, url: str) -> Dict[str, Any]:
        """Analyze website on desktop device"""
        try:
            result = await self.client.analyze_url(
                url=url,
                strategy="desktop",
                categories=["performance", "accessibility", "best-practices", "seo"]
            )
            
            # Store detailed desktop assessment
            desktop_assessment = PageSpeedAssessment(
                assessment_id=assessment_id,
                is_mobile=False,
                lighthouse_data=result.get("lighthouseResult", {}),
                lighthouse_version=result.get("lighthouseResult", {}).get("lighthouseVersion"),
                user_agent=result.get("lighthouseResult", {}).get("userAgent"),
                fetch_time=datetime.utcnow()
            )
            
            # Extract scores for quick access
            self._extract_lighthouse_scores(desktop_assessment, result)
            
            # Extract Core Web Vitals details
            self._extract_detailed_cwv(desktop_assessment, result)
            
            # Extract opportunities and diagnostics
            desktop_assessment.opportunities = self._extract_opportunities(result)
            desktop_assessment.diagnostics = self._extract_diagnostics(result)
            
            return result
            
        except Exception as e:
            raise Exception(f"Desktop analysis failed: {str(e)}")
    
    def _populate_core_metrics(
        self, 
        assessment: AssessmentResult, 
        mobile_result: Dict[str, Any],
        desktop_result: Optional[Dict[str, Any]] = None
    ):
        """
        Populate core metrics in assessment (mobile-first approach)
        
        Acceptance Criteria: All scores captured
        """
        # Use mobile scores as primary (mobile-first approach)
        mobile_categories = mobile_result.get("lighthouseResult", {}).get("categories", {})
        
        # Performance scores (0-100)
        if "performance" in mobile_categories:
            assessment.performance_score = int(mobile_categories["performance"].get("score", 0) * 100)
        
        if "accessibility" in mobile_categories:
            assessment.accessibility_score = int(mobile_categories["accessibility"].get("score", 0) * 100)
            
        if "best-practices" in mobile_categories:
            assessment.best_practices_score = int(mobile_categories["best-practices"].get("score", 0) * 100)
            
        if "seo" in mobile_categories:
            assessment.seo_score = int(mobile_categories["seo"].get("score", 0) * 100)
            
        if "pwa" in mobile_categories:
            assessment.pwa_score = int(mobile_categories["pwa"].get("score", 0) * 100)
    
    def _extract_core_web_vitals(
        self, 
        assessment: AssessmentResult, 
        mobile_result: Dict[str, Any]
    ):
        """
        Extract Core Web Vitals from mobile result (mobile-first)
        
        Acceptance Criteria: Core Web Vitals extracted
        """
        audits = mobile_result.get("lighthouseResult", {}).get("audits", {})
        
        # Largest Contentful Paint (LCP)
        if "largest-contentful-paint" in audits:
            lcp = audits["largest-contentful-paint"]
            assessment.largest_contentful_paint = lcp.get("numericValue")
        
        # First Input Delay (FID) - using max-potential-fid as proxy
        if "max-potential-fid" in audits:
            fid = audits["max-potential-fid"]
            assessment.first_input_delay = fid.get("numericValue")
        
        # Cumulative Layout Shift (CLS)
        if "cumulative-layout-shift" in audits:
            cls = audits["cumulative-layout-shift"]
            assessment.cumulative_layout_shift = cls.get("numericValue")
        
        # First Contentful Paint (FCP)
        if "first-contentful-paint" in audits:
            fcp = audits["first-contentful-paint"]
            assessment.first_contentful_paint = fcp.get("numericValue")
        
        # Speed Index
        if "speed-index" in audits:
            si = audits["speed-index"]
            assessment.speed_index = si.get("numericValue")
        
        # Time to Interactive
        if "interactive" in audits:
            tti = audits["interactive"]
            assessment.time_to_interactive = tti.get("numericValue")
        
        # Total Blocking Time
        if "total-blocking-time" in audits:
            tbt = audits["total-blocking-time"]
            assessment.total_blocking_time = tbt.get("numericValue")
    
    def _extract_lighthouse_scores(
        self, 
        pagespeed_assessment: PageSpeedAssessment, 
        result: Dict[str, Any]
    ):
        """Extract Lighthouse scores for PageSpeedAssessment"""
        categories = result.get("lighthouseResult", {}).get("categories", {})
        
        if "performance" in categories:
            pagespeed_assessment.performance_score = int(categories["performance"].get("score", 0) * 100)
        if "accessibility" in categories:
            pagespeed_assessment.accessibility_score = int(categories["accessibility"].get("score", 0) * 100)
        if "best-practices" in categories:
            pagespeed_assessment.best_practices_score = int(categories["best-practices"].get("score", 0) * 100)
        if "seo" in categories:
            pagespeed_assessment.seo_score = int(categories["seo"].get("score", 0) * 100)
        if "pwa" in categories:
            pagespeed_assessment.pwa_score = int(categories["pwa"].get("score", 0) * 100)
    
    def _extract_detailed_cwv(
        self, 
        pagespeed_assessment: PageSpeedAssessment, 
        result: Dict[str, Any]
    ):
        """Extract detailed Core Web Vitals for PageSpeedAssessment"""
        audits = result.get("lighthouseResult", {}).get("audits", {})
        
        core_web_vitals = {}
        
        # LCP
        if "largest-contentful-paint" in audits:
            lcp = audits["largest-contentful-paint"]
            core_web_vitals["LCP"] = {
                "score": lcp.get("score"),
                "numericValue": lcp.get("numericValue"),
                "displayValue": lcp.get("displayValue"),
                "description": lcp.get("description")
            }
        
        # FID (using max-potential-fid)
        if "max-potential-fid" in audits:
            fid = audits["max-potential-fid"]
            core_web_vitals["FID"] = {
                "score": fid.get("score"),
                "numericValue": fid.get("numericValue"),
                "displayValue": fid.get("displayValue"),
                "description": fid.get("description")
            }
        
        # CLS
        if "cumulative-layout-shift" in audits:
            cls = audits["cumulative-layout-shift"]
            core_web_vitals["CLS"] = {
                "score": cls.get("score"),
                "numericValue": cls.get("numericValue"),
                "displayValue": cls.get("displayValue"),
                "description": cls.get("description")
            }
        
        pagespeed_assessment.core_web_vitals = core_web_vitals
    
    def _extract_opportunities(self, result: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Extract optimization opportunities
        
        Acceptance Criteria: Issue extraction works
        """
        opportunities = []
        audits = result.get("lighthouseResult", {}).get("audits", {})
        
        # Look for audits with savings potential
        for audit_id, audit in audits.items():
            if (audit.get("score", 1) < 1 and  # Failed or could be improved
                "details" in audit and
                audit.get("details", {}).get("overallSavingsMs", 0) > 0):
                
                opportunities.append({
                    "id": audit_id,
                    "title": audit.get("title", ""),
                    "description": audit.get("description", ""),
                    "score": audit.get("score", 0),
                    "savings_ms": audit["details"].get("overallSavingsMs", 0),
                    "impact": self._categorize_impact(audit["details"].get("overallSavingsMs", 0)),
                    "details": audit.get("details", {})
                })
        
        # Sort by potential savings (highest first)
        opportunities.sort(key=lambda x: x["savings_ms"], reverse=True)
        return opportunities
    
    def _extract_diagnostics(self, result: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Extract diagnostic information and issues"""
        diagnostics = []
        audits = result.get("lighthouseResult", {}).get("audits", {})
        
        # Core Web Vitals and performance metrics are not diagnostics
        core_metrics = {
            "largest-contentful-paint", "max-potential-fid", "cumulative-layout-shift",
            "first-contentful-paint", "speed-index", "interactive", "total-blocking-time"
        }
        
        # Look for failed audits without savings (diagnostic issues)
        for audit_id, audit in audits.items():
            if (audit_id not in core_metrics and  # Skip core metrics
                audit.get("score", 1) < 1 and  # Failed
                not audit.get("details", {}).get("overallSavingsMs", 0) and  # No savings
                audit.get("title")):  # Has title (is an actual audit)
                
                diagnostics.append({
                    "id": audit_id,
                    "title": audit.get("title", ""),
                    "description": audit.get("description", ""),
                    "score": audit.get("score", 0),
                    "impact": "informational",
                    "details": audit.get("details", {})
                })
        
        return diagnostics
    
    def _extract_issues(
        self, 
        mobile_result: Dict[str, Any], 
        desktop_result: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """
        Extract comprehensive performance issues
        
        Acceptance Criteria: Issue extraction works
        """
        issues = []
        
        # Extract mobile issues (primary due to mobile-first approach)
        mobile_opportunities = self._extract_opportunities(mobile_result)
        mobile_diagnostics = self._extract_diagnostics(mobile_result)
        
        issues.extend([{**issue, "device": "mobile", "type": "opportunity"} for issue in mobile_opportunities])
        issues.extend([{**issue, "device": "mobile", "type": "diagnostic"} for issue in mobile_diagnostics])
        
        # Extract desktop issues if available
        if desktop_result:
            desktop_opportunities = self._extract_opportunities(desktop_result)
            desktop_diagnostics = self._extract_diagnostics(desktop_result)
            
            issues.extend([{**issue, "device": "desktop", "type": "opportunity"} for issue in desktop_opportunities])
            issues.extend([{**issue, "device": "desktop", "type": "diagnostic"} for issue in desktop_diagnostics])
        
        return issues
    
    def _categorize_impact(self, savings_ms: float) -> str:
        """Categorize performance impact level"""
        if savings_ms >= 1000:  # 1+ seconds
            return "high"
        elif savings_ms >= 500:  # 0.5+ seconds  
            return "medium"
        else:
            return "low"
    
    def _extract_domain(self, url: str) -> str:
        """Extract domain from URL"""
        from urllib.parse import urlparse
        return urlparse(url).netloc.replace("www.", "")
    
    async def _calculate_assessment_cost(
        self,
        assessment_id: str,
        session_id: Optional[str],
        mobile_result: Dict[str, Any],
        desktop_result: Optional[Dict[str, Any]] = None
    ) -> Decimal:
        """
        Calculate and track assessment costs
        
        Returns total cost in USD
        """
        total_cost = Decimal("0.00")
        
        # Cost for mobile analysis
        mobile_cost = await self.client.calculate_cost("GET:/pagespeedonline/v5/runPagespeed")
        total_cost += mobile_cost
        
        # Track mobile API cost
        AssessmentCost(
            assessment_id=assessment_id,
            session_id=session_id,
            cost_type=CostType.API_CALL,
            amount=mobile_cost,
            provider="Google PageSpeed",
            service_name="PageSpeed Insights API",
            description="Mobile PageSpeed analysis",
            units_consumed=1.0,
            unit_type="requests",
            rate_per_unit=mobile_cost
        )
        
        # Cost for desktop analysis if performed
        if desktop_result:
            desktop_cost = await self.client.calculate_cost("GET:/pagespeedonline/v5/runPagespeed")
            total_cost += desktop_cost
            
            # Track desktop API cost
            AssessmentCost(
                assessment_id=assessment_id,
                session_id=session_id,
                cost_type=CostType.API_CALL,
                amount=desktop_cost,
                provider="Google PageSpeed",
                service_name="PageSpeed Insights API",
                description="Desktop PageSpeed analysis",
                units_consumed=1.0,
                unit_type="requests",
                rate_per_unit=desktop_cost
            )
        
        return total_cost


class PageSpeedBatchAssessor:
    """
    Batch PageSpeed assessment for multiple websites
    
    Handles efficient processing of multiple URLs with rate limiting and error handling.
    """
    
    def __init__(self, api_key: Optional[str] = None, max_concurrent: int = 5):
        """
        Initialize batch assessor
        
        Args:
            api_key: Google PageSpeed API key
            max_concurrent: Maximum concurrent assessments
        """
        self.assessor = PageSpeedAssessor(api_key=api_key)
        self.max_concurrent = max_concurrent
        
    async def assess_multiple_websites(
        self,
        websites: List[Dict[str, str]],  # [{"business_id": "...", "url": "..."}]
        session_id: Optional[str] = None,
        include_desktop: bool = True
    ) -> List[AssessmentResult]:
        """
        Assess multiple websites efficiently
        
        Args:
            websites: List of website dictionaries with business_id and url
            session_id: Optional session ID for tracking
            include_desktop: Whether to include desktop analysis
            
        Returns:
            List of assessment results
        """
        semaphore = asyncio.Semaphore(self.max_concurrent)
        
        async def assess_single(website_data: Dict[str, str]) -> AssessmentResult:
            async with semaphore:
                try:
                    return await self.assessor.assess_website(
                        business_id=website_data["business_id"],
                        url=website_data["url"],
                        session_id=session_id,
                        include_desktop=include_desktop
                    )
                except Exception as e:
                    # Return failed assessment
                    return AssessmentResult(
                        business_id=website_data["business_id"],
                        url=website_data["url"],
                        assessment_type=AssessmentType.PAGESPEED,
                        status=AssessmentStatus.FAILED,
                        error_message=str(e),
                        domain=self.assessor._extract_domain(website_data["url"])
                    )
        
        # Run all assessments concurrently with rate limiting
        tasks = [assess_single(website) for website in websites]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Filter out exceptions and return valid results
        return [result for result in results if isinstance(result, AssessmentResult)]