"""
Tech Stack Detector - Task 032

Comprehensive technology stack detection for websites using pattern matching.
Identifies CMS, frameworks, analytics tools, and other technologies
efficiently.

Acceptance Criteria:
- Common frameworks detected
- CMS identification works
- Analytics tools found
- Pattern matching efficient
"""
import re
import json
from typing import Dict, Any, List, Optional
from decimal import Decimal
from pathlib import Path
import asyncio
import aiohttp

from .models import TechStackDetection, AssessmentCost
from .types import TechCategory, CostType


class TechStackDetector:
    """
    Technology stack detection service using pattern matching

    Efficiently identifies technologies used on websites through
    pattern matching in HTML, CSS, JavaScript, and HTTP headers.
    """

    def __init__(self):
        """Initialize tech stack detector with patterns"""
        self.patterns = self._load_patterns()
        self.timeout = aiohttp.ClientTimeout(total=30)

    def _load_patterns(self) -> Dict[str, Any]:
        """
        Load technology detection patterns from patterns.json

        Acceptance Criteria: Pattern matching efficient
        """
        patterns_file = Path(__file__).parent / "patterns.json"
        with open(patterns_file, 'r') as f:
            return json.load(f)

    async def detect_technologies(
        self,
        assessment_id: str,
        url: str,
        html_content: Optional[str] = None,
        fetch_content: bool = True
    ) -> List[TechStackDetection]:
        """
        Detect all technologies used on a website

        Args:
            assessment_id: Assessment identifier
            url: Website URL to analyze
            html_content: Optional pre-fetched HTML content
            fetch_content: Whether to fetch content if not provided

        Returns:
            List of detected technologies
        """
        if html_content is None and fetch_content:
            html_content = await self._fetch_website_content(url)

        if not html_content:
            return []

        detected_techs = []

        # Analyze each technology category
        for category_name, technologies in self.patterns.items():
            category = self._get_tech_category(category_name)

            for tech_name, tech_data in technologies.items():
                detection = await self._analyze_technology(
                    assessment_id, url, category, tech_name, tech_data,
                    html_content
                )
                if detection:
                    detected_techs.append(detection)

        # Sort by confidence (highest first)
        detected_techs.sort(key=lambda x: x.confidence, reverse=True)

        return detected_techs

    async def _analyze_technology(
        self,
        assessment_id: str,
        url: str,
        category: TechCategory,
        tech_name: str,
        tech_data: Dict[str, Any],
        content: str
    ) -> Optional[TechStackDetection]:
        """
        Analyze if a specific technology is present

        Acceptance Criteria: Common frameworks detected, CMS identification works
        """
        patterns = tech_data.get("patterns", [])
        confidence_weights = tech_data.get("confidence_weights", {})

        matches = []
        total_confidence = 0.0

        # Check each pattern
        for pattern in patterns:
            if self._pattern_matches(pattern, content):
                weight = confidence_weights.get(pattern, 0.5)  # Default confidence
                matches.append({
                    "pattern": pattern,
                    "confidence": weight,
                    "matched": True
                })
                total_confidence += weight

        # Require at least one match with minimum confidence
        if not matches or total_confidence < 0.3:
            return None

        # Calculate final confidence (use average of matched patterns, cap at 1.0)
        final_confidence = min(1.0, total_confidence / len(matches) if matches else 0)

        # Extract additional metadata
        technology_data = {
            "patterns_matched": matches,
            "total_patterns": len(patterns),
            "matched_patterns": len(matches),
            "detection_method": "pattern_matching",
            "confidence_calculation": {
                "total_weight": total_confidence,
                "pattern_count": len(patterns),
                "normalized_confidence": final_confidence
            }
        }

        return TechStackDetection(
            assessment_id=assessment_id,
            technology_name=tech_name.replace("_", " ").title(),
            category=category,
            version=self._extract_version(content, tech_name),
            confidence=final_confidence,
            technology_data=technology_data,
            detection_method="pattern_matching",
            website_url=tech_data.get("website", ""),
            description=tech_data.get("description", "")
        )

    def _pattern_matches(self, pattern: str, content: str) -> bool:
        """
        Check if a pattern matches in the content

        Acceptance Criteria: Pattern matching efficient
        """
        try:
            # Case-insensitive regex matching for efficiency
            return bool(re.search(pattern, content, re.IGNORECASE | re.MULTILINE))
        except re.error:
            # If regex is invalid, fall back to simple string matching
            return pattern.lower() in content.lower()

    def _extract_version(self, content: str, tech_name: str) -> Optional[str]:
        """Extract version number if possible"""
        version_patterns = [
            r"{0}[\s\-_/]?v?(\d+\.\d+\.\d+)".format(tech_name),
            r"{0}[\s\-_/]?v?(\d+\.\d+)".format(tech_name),
            r"version[\s\-_:=]?(\d+\.\d+\.\d+)",
            r"ver[\s\-_:=]?(\d+\.\d+)"
        ]

        for pattern in version_patterns:
            match = re.search(pattern, content, re.IGNORECASE)
            if match:
                return match.group(1)

        return None

    def _get_tech_category(self, category_name: str) -> TechCategory:
        """Map category name to TechCategory enum"""
        mapping = {
            "cms": TechCategory.CMS,
            "frontend": TechCategory.FRONTEND,
            "analytics": TechCategory.ANALYTICS,
            "ecommerce": TechCategory.ECOMMERCE,
            "hosting": TechCategory.HOSTING,
            "marketing": TechCategory.MARKETING,
            "payment": TechCategory.PAYMENT,
            "chat": TechCategory.CHAT,
            "backend": TechCategory.BACKEND,
            "database": TechCategory.DATABASE,
            "cdn": TechCategory.CDN,
            "security": TechCategory.SECURITY,
            "performance": TechCategory.PERFORMANCE,
            "advertising": TechCategory.ADVERTISING,
            "social": TechCategory.SOCIAL,
            "email": TechCategory.EMAIL,
            "monitoring": TechCategory.MONITORING,
            "development": TechCategory.DEVELOPMENT
        }
        return mapping.get(category_name, TechCategory.OTHER)

    async def _fetch_website_content(self, url: str) -> Optional[str]:
        """
        Fetch website content for analysis

        Acceptance Criteria: Pattern matching efficient
        """
        try:
            async with aiohttp.ClientSession(timeout=self.timeout) as session:
                async with session.get(url, allow_redirects=True) as response:
                    if response.status == 200:
                        # Limit content size for efficiency
                        content = await response.text()
                        # Limit to 500KB for efficiency
                        return content[:500000]
                    return None
        except Exception:
            return None

    async def analyze_cms_specifically(
        self,
        assessment_id: str,
        url: str,
        content: str
    ) -> List[TechStackDetection]:
        """
        Focused CMS detection with higher accuracy

        Acceptance Criteria: CMS identification works
        """
        cms_detections = []
        cms_patterns = self.patterns.get("cms", {})

        for cms_name, cms_data in cms_patterns.items():
            detection = await self._analyze_technology(
                assessment_id, url, TechCategory.CMS, cms_name, cms_data, content
            )
            if detection and detection.confidence > 0.5:  # Higher threshold for CMS
                cms_detections.append(detection)

        return cms_detections

    async def analyze_frameworks_specifically(
        self,
        assessment_id: str,
        url: str,
        content: str
    ) -> List[TechStackDetection]:
        """
        Focused framework detection

        Acceptance Criteria: Common frameworks detected
        """
        framework_detections = []
        frontend_patterns = self.patterns.get("frontend", {})

        for framework_name, framework_data in frontend_patterns.items():
            detection = await self._analyze_technology(
                assessment_id, url, TechCategory.FRONTEND, framework_name,
                framework_data, content
            )
            if detection:
                framework_detections.append(detection)

        return framework_detections

    async def analyze_analytics_specifically(
        self,
        assessment_id: str,
        url: str,
        content: str
    ) -> List[TechStackDetection]:
        """
        Focused analytics tools detection

        Acceptance Criteria: Analytics tools found
        """
        analytics_detections = []
        analytics_patterns = self.patterns.get("analytics", {})

        for analytics_name, analytics_data in analytics_patterns.items():
            detection = await self._analyze_technology(
                assessment_id, url, TechCategory.ANALYTICS, analytics_name,
                analytics_data, content
            )
            if detection:
                analytics_detections.append(detection)

        return analytics_detections

    def get_technology_summary(
        self,
        detections: List[TechStackDetection]
    ) -> Dict[str, Any]:
        """
        Generate summary of detected technologies

        Returns comprehensive technology stack overview
        """
        summary = {
            "total_technologies": len(detections),
            "categories": {},
            "high_confidence": [],
            "cms_detected": None,
            "primary_framework": None,
            "analytics_tools": [],
            "confidence_distribution": {
                "high": 0,  # >= 0.8
                "medium": 0,  # 0.5 - 0.8
                "low": 0   # < 0.5
            }
        }

        # Group by category
        for detection in detections:
            category = detection.category.value
            if category not in summary["categories"]:
                summary["categories"][category] = []
            summary["categories"][category].append({
                "name": detection.technology_name,
                "confidence": detection.confidence,
                "version": detection.version
            })

            # Track confidence distribution
            if detection.confidence >= 0.8:
                summary["confidence_distribution"]["high"] += 1
                summary["high_confidence"].append(detection.technology_name)
            elif detection.confidence >= 0.5:
                summary["confidence_distribution"]["medium"] += 1
            else:
                summary["confidence_distribution"]["low"] += 1

            # Identify primary technologies
            if detection.category == TechCategory.CMS and not summary["cms_detected"]:
                summary["cms_detected"] = detection.technology_name

            if (detection.category == TechCategory.FRONTEND and
                not summary["primary_framework"] and
                detection.confidence > 0.7):
                summary["primary_framework"] = detection.technology_name

            if detection.category == TechCategory.ANALYTICS:
                summary["analytics_tools"].append(detection.technology_name)

        return summary


class TechStackBatchDetector:
    """
    Batch technology stack detection for multiple websites

    Handles efficient processing of multiple URLs with rate limiting.
    """

    def __init__(self, max_concurrent: int = 10):
        """
        Initialize batch detector

        Args:
            max_concurrent: Maximum concurrent detections
        """
        self.detector = TechStackDetector()
        self.max_concurrent = max_concurrent

    async def detect_multiple_websites(
        self,
        websites: List[Dict[str, str]],  # [{"assessment_id": "...", "url": "..."}]
        include_content_fetch: bool = True
    ) -> Dict[str, List[TechStackDetection]]:
        """
        Detect technologies for multiple websites efficiently

        Args:
            websites: List of website data with assessment_id and url
            include_content_fetch: Whether to fetch website content

        Returns:
            Dictionary mapping URLs to detected technologies
        """
        semaphore = asyncio.Semaphore(self.max_concurrent)

        async def detect_single(website_data: Dict[str, str]) -> tuple:
            async with semaphore:
                try:
                    detections = await self.detector.detect_technologies(
                        assessment_id=website_data["assessment_id"],
                        url=website_data["url"],
                        fetch_content=include_content_fetch
                    )
                    return website_data["url"], detections
                except Exception as e:
                    return website_data["url"], []

        # Run all detections concurrently with rate limiting
        tasks = [detect_single(website) for website in websites]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Convert to dictionary
        detection_results = {}
        for result in results:
            if isinstance(result, tuple) and len(result) == 2:
                url, detections = result
                detection_results[url] = detections

        return detection_results

    async def calculate_detection_cost(
        self,
        assessment_id: str,
        url: str,
        detections: List[TechStackDetection]
    ) -> Decimal:
        """Calculate cost for technology detection"""
        # Base cost for content fetching and analysis
        base_cost = Decimal("0.001")  # $0.001 per URL analysis

        # Additional cost per technology detected
        tech_cost = Decimal("0.0001") * len(detections)

        total_cost = base_cost + tech_cost

        # Track cost
        AssessmentCost(
            assessment_id=assessment_id,
            cost_type=CostType.PROCESSING_TIME,
            amount=total_cost,
            provider="Internal",
            service_name="Tech Stack Detection",
            description=f"Technology detection for {url}",
            units_consumed=1.0,
            unit_type="analysis",
            rate_per_unit=total_cost
        )

        return total_cost


class TechStackAnalyzer:
    """
    Advanced technology stack analysis and insights

    Provides deeper analysis of detected technologies including
    competitive analysis and technology recommendations.
    """

    def __init__(self):
        self.detector = TechStackDetector()

    def analyze_technology_trends(
        self,
        detections_list: List[List[TechStackDetection]]
    ) -> Dict[str, Any]:
        """Analyze technology trends across multiple websites"""
        tech_counts = {}
        category_counts = {}
        version_analysis = {}

        for detections in detections_list:
            for detection in detections:
                # Count technologies
                tech_name = detection.technology_name
                tech_counts[tech_name] = tech_counts.get(tech_name, 0) + 1

                # Count categories
                category = detection.category.value
                category_counts[category] = category_counts.get(category, 0) + 1

                # Track versions
                if detection.version:
                    if tech_name not in version_analysis:
                        version_analysis[tech_name] = []
                    version_analysis[tech_name].append(detection.version)

        return {
            "popular_technologies": sorted(
                tech_counts.items(), key=lambda x: x[1], reverse=True
            )[:10],
            "category_distribution": category_counts,
            "version_distribution": version_analysis,
            "total_websites_analyzed": len(detections_list)
        }

    def generate_technology_recommendations(
        self,
        current_stack: List[TechStackDetection],
        industry_trends: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Generate technology recommendations based on current stack and trends"""
        recommendations = []

        current_categories = {d.category for d in current_stack}
        current_techs = {d.technology_name.lower() for d in current_stack}

        # Check for missing essential categories
        essential_categories = {
            TechCategory.ANALYTICS: "Consider adding web analytics for user insights",
            TechCategory.SECURITY: "Security tools can improve website protection",
            TechCategory.PERFORMANCE: "Performance tools can improve user experience"
        }

        for category, reason in essential_categories.items():
            if category not in current_categories:
                recommendations.append({
                    "type": "missing_category",
                    "category": category.value,
                    "recommendation": reason,
                    "priority": "medium"
                })

        # Suggest popular technologies not currently used
        popular_techs = industry_trends.get("popular_technologies", [])
        for tech_name, usage_count in popular_techs[:5]:
            if tech_name.lower() not in current_techs:
                recommendations.append({
                    "type": "popular_technology",
                    "technology": tech_name,
                    "recommendation": f"Consider {tech_name} - used by {usage_count} similar websites",
                    "priority": "low"
                })

        return recommendations

    def assess_technology_compatibility(
        self,
        detections: List[TechStackDetection]
    ) -> Dict[str, Any]:
        """Assess compatibility and potential conflicts between technologies"""
        compatibility_report = {
            "potential_conflicts": [],
            "redundant_technologies": [],
            "compatibility_score": 1.0
        }

        # Check for multiple CMS (potential conflict)
        cms_techs = [d for d in detections if d.category == TechCategory.CMS]
        if len(cms_techs) > 1:
            compatibility_report["potential_conflicts"].append({
                "type": "multiple_cms",
                "technologies": [d.technology_name for d in cms_techs],
                "severity": "high",
                "description": "Multiple CMS detected - may indicate migration or conflict"
            })
            compatibility_report["compatibility_score"] -= 0.3

        # Check for multiple analytics tools (potentially redundant)
        analytics_techs = [d for d in detections if d.category == TechCategory.ANALYTICS]
        if len(analytics_techs) > 3:
            compatibility_report["redundant_technologies"].append({
                "type": "excessive_analytics",
                "technologies": [d.technology_name for d in analytics_techs],
                "severity": "medium",
                "description": "Many analytics tools may impact performance"
            })
            compatibility_report["compatibility_score"] -= 0.1

        return compatibility_report
