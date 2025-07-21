"""
Assessment Test Data Generator - Task 088

Generates realistic assessment test data for various testing scenarios.
Supports deterministic generation and performance datasets.

Acceptance Criteria:
- Realistic test data ✓
- Various scenarios covered ✓
- Deterministic generation ✓
- Performance data sets ✓
"""

import random
import uuid
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

from d3_assessment.models import AssessmentResult, AssessmentStatus, AssessmentType
from database.models import Business


class AssessmentScenario(Enum):
    """Assessment generation scenarios for different testing contexts"""

    HIGH_PERFORMANCE = "high_performance"
    POOR_PERFORMANCE = "poor_performance"
    MIXED_RESULTS = "mixed_results"
    MOBILE_OPTIMIZED = "mobile_optimized"
    DESKTOP_ONLY = "desktop_only"
    ECOMMERCE_FOCUSED = "ecommerce_focused"
    LOCAL_BUSINESS = "local_business"
    ENTERPRISE_SITE = "enterprise_site"
    BLOG_CONTENT = "blog_content"
    PORTFOLIO_SITE = "portfolio_site"


@dataclass
class AssessmentProfile:
    """Profile defining assessment characteristics for generation"""

    scenario: str
    performance_range: tuple[int, int]
    accessibility_range: tuple[int, int]
    best_practices_range: tuple[int, int]
    seo_range: tuple[int, int]
    mobile_score_range: tuple[int, int]
    desktop_score_range: tuple[int, int]
    common_technologies: list[str]
    typical_issues: list[str]
    load_time_range: tuple[float, float]
    page_size_range: tuple[int, int]  # KB
    status_weights: dict[str, float]


class AssessmentGenerator:
    """
    Generates realistic assessment test data with various scenarios and deterministic output.

    Features:
    - Realistic assessment scores and metrics
    - Technology stack detection simulation
    - Performance data patterns
    - Deterministic generation for reproducible tests
    - Large dataset generation for performance testing
    """

    def __init__(self, seed: int = 42):
        """Initialize generator with optional seed for deterministic output"""
        self.seed = seed
        self.random = random.Random(seed)
        self._setup_profiles()
        self._setup_technology_data()
        self._setup_insights_data()

    def _setup_profiles(self):
        """Setup assessment profiles for different scenarios"""
        self.profiles = {
            AssessmentScenario.HIGH_PERFORMANCE: AssessmentProfile(
                scenario="high_performance",
                performance_range=(85, 98),
                accessibility_range=(90, 100),
                best_practices_range=(88, 96),
                seo_range=(85, 95),
                mobile_score_range=(85, 98),
                desktop_score_range=(90, 100),
                common_technologies=["React", "Next.js", "Cloudflare", "WebP", "CDN"],
                typical_issues=[
                    "Minor unused CSS",
                    "Small image optimization opportunity",
                ],
                load_time_range=(0.8, 2.1),
                page_size_range=(500, 1200),
                status_weights={"COMPLETED": 0.95, "FAILED": 0.03, "PENDING": 0.02},
            ),
            AssessmentScenario.POOR_PERFORMANCE: AssessmentProfile(
                scenario="poor_performance",
                performance_range=(15, 45),
                accessibility_range=(30, 60),
                best_practices_range=(25, 55),
                seo_range=(20, 50),
                mobile_score_range=(10, 40),
                desktop_score_range=(20, 50),
                common_technologies=["jQuery", "Legacy CMS", "Unoptimized images"],
                typical_issues=[
                    "Large images",
                    "Render blocking resources",
                    "No HTTPS",
                    "Missing meta tags",
                ],
                load_time_range=(5.2, 12.8),
                page_size_range=(3000, 8000),
                status_weights={"COMPLETED": 0.85, "FAILED": 0.10, "PENDING": 0.05},
            ),
            AssessmentScenario.MIXED_RESULTS: AssessmentProfile(
                scenario="mixed_results",
                performance_range=(50, 80),
                accessibility_range=(60, 85),
                best_practices_range=(55, 78),
                seo_range=(45, 75),
                mobile_score_range=(45, 75),
                desktop_score_range=(60, 85),
                common_technologies=[
                    "WordPress",
                    "Bootstrap",
                    "Google Analytics",
                    "jQuery",
                ],
                typical_issues=[
                    "Some accessibility issues",
                    "Image optimization needed",
                    "SEO improvements possible",
                ],
                load_time_range=(2.5, 4.8),
                page_size_range=(1500, 3000),
                status_weights={"COMPLETED": 0.90, "FAILED": 0.06, "PENDING": 0.04},
            ),
            AssessmentScenario.MOBILE_OPTIMIZED: AssessmentProfile(
                scenario="mobile_optimized",
                performance_range=(75, 90),
                accessibility_range=(80, 95),
                best_practices_range=(75, 88),
                seo_range=(80, 92),
                mobile_score_range=(85, 98),
                desktop_score_range=(70, 85),
                common_technologies=[
                    "Progressive Web App",
                    "AMP",
                    "Responsive Design",
                    "Touch Optimization",
                ],
                typical_issues=[
                    "Desktop experience could be enhanced",
                    "Minor desktop layout issues",
                ],
                load_time_range=(1.2, 2.8),
                page_size_range=(600, 1500),
                status_weights={"COMPLETED": 0.92, "FAILED": 0.05, "PENDING": 0.03},
            ),
            AssessmentScenario.ECOMMERCE_FOCUSED: AssessmentProfile(
                scenario="ecommerce_focused",
                performance_range=(60, 85),
                accessibility_range=(70, 88),
                best_practices_range=(75, 90),
                seo_range=(75, 90),
                mobile_score_range=(65, 85),
                desktop_score_range=(70, 90),
                common_technologies=[
                    "Shopify",
                    "WooCommerce",
                    "SSL",
                    "Payment Gateway",
                    "Analytics",
                ],
                typical_issues=[
                    "Complex checkout flow",
                    "Product image optimization",
                    "Category page speed",
                ],
                load_time_range=(2.0, 4.5),
                page_size_range=(2000, 4000),
                status_weights={"COMPLETED": 0.88, "FAILED": 0.08, "PENDING": 0.04},
            ),
            AssessmentScenario.DESKTOP_ONLY: AssessmentProfile(
                scenario="desktop_only",
                performance_range=(70, 90),
                accessibility_range=(65, 85),
                best_practices_range=(70, 85),
                seo_range=(70, 85),
                mobile_score_range=(30, 60),
                desktop_score_range=(80, 95),
                common_technologies=[
                    "Legacy JavaScript",
                    "Flash",
                    "Desktop CSS",
                    "Fixed Width",
                ],
                typical_issues=[
                    "Poor mobile experience",
                    "Not responsive",
                    "Mobile usability issues",
                ],
                load_time_range=(1.5, 3.5),
                page_size_range=(1000, 2500),
                status_weights={"COMPLETED": 0.90, "FAILED": 0.06, "PENDING": 0.04},
            ),
            AssessmentScenario.LOCAL_BUSINESS: AssessmentProfile(
                scenario="local_business",
                performance_range=(45, 75),
                accessibility_range=(50, 80),
                best_practices_range=(55, 75),
                seo_range=(60, 85),
                mobile_score_range=(50, 80),
                desktop_score_range=(55, 80),
                common_technologies=[
                    "WordPress",
                    "Google Maps",
                    "Local SEO",
                    "Contact Forms",
                ],
                typical_issues=[
                    "Local SEO optimization needed",
                    "Contact information clarity",
                    "Mobile directions",
                ],
                load_time_range=(2.5, 5.0),
                page_size_range=(1200, 3000),
                status_weights={"COMPLETED": 0.88, "FAILED": 0.08, "PENDING": 0.04},
            ),
            AssessmentScenario.ENTERPRISE_SITE: AssessmentProfile(
                scenario="enterprise_site",
                performance_range=(70, 90),
                accessibility_range=(80, 95),
                best_practices_range=(80, 95),
                seo_range=(75, 90),
                mobile_score_range=(75, 90),
                desktop_score_range=(80, 95),
                common_technologies=[
                    "Enterprise CMS",
                    "CDN",
                    "Security Headers",
                    "Analytics Suite",
                ],
                typical_issues=[
                    "Complex navigation",
                    "Heavy resources",
                    "Corporate compliance",
                ],
                load_time_range=(1.5, 3.0),
                page_size_range=(2000, 5000),
                status_weights={"COMPLETED": 0.92, "FAILED": 0.05, "PENDING": 0.03},
            ),
            AssessmentScenario.BLOG_CONTENT: AssessmentProfile(
                scenario="blog_content",
                performance_range=(65, 85),
                accessibility_range=(70, 90),
                best_practices_range=(65, 85),
                seo_range=(75, 95),
                mobile_score_range=(70, 90),
                desktop_score_range=(70, 90),
                common_technologies=[
                    "WordPress",
                    "Content Management",
                    "Social Sharing",
                    "Comments System",
                ],
                typical_issues=[
                    "Image optimization",
                    "Content structure",
                    "Loading speed",
                ],
                load_time_range=(2.0, 4.0),
                page_size_range=(800, 2000),
                status_weights={"COMPLETED": 0.90, "FAILED": 0.06, "PENDING": 0.04},
            ),
            AssessmentScenario.PORTFOLIO_SITE: AssessmentProfile(
                scenario="portfolio_site",
                performance_range=(60, 85),
                accessibility_range=(65, 85),
                best_practices_range=(70, 90),
                seo_range=(55, 80),
                mobile_score_range=(70, 90),
                desktop_score_range=(75, 95),
                common_technologies=[
                    "Static Site Generator",
                    "Image Gallery",
                    "Contact Forms",
                    "Responsive Design",
                ],
                typical_issues=[
                    "Large image files",
                    "Gallery optimization",
                    "Portfolio organization",
                ],
                load_time_range=(1.8, 4.2),
                page_size_range=(1500, 4000),
                status_weights={"COMPLETED": 0.90, "FAILED": 0.06, "PENDING": 0.04},
            ),
        }

    def _setup_technology_data(self):
        """Setup technology detection data"""
        self.technologies = {
            "cms": {
                "WordPress": {
                    "market_share": 0.35,
                    "indicators": ["wp-content", "wp-includes"],
                },
                "Shopify": {
                    "market_share": 0.15,
                    "indicators": ["shopify", "cdn.shopify.com"],
                },
                "Squarespace": {"market_share": 0.08, "indicators": ["squarespace"]},
                "Wix": {
                    "market_share": 0.06,
                    "indicators": ["wix.com", "static.wix.com"],
                },
                "Custom": {"market_share": 0.20, "indicators": []},
                "Unknown": {"market_share": 0.16, "indicators": []},
            },
            "javascript_frameworks": {
                "React": {"popularity": 0.25, "performance_impact": "medium"},
                "Vue.js": {"popularity": 0.12, "performance_impact": "low"},
                "Angular": {"popularity": 0.10, "performance_impact": "high"},
                "jQuery": {"popularity": 0.35, "performance_impact": "low"},
                "Vanilla JS": {"popularity": 0.18, "performance_impact": "minimal"},
            },
            "css_frameworks": {
                "Bootstrap": {"usage": 0.30},
                "Tailwind CSS": {"usage": 0.15},
                "Material UI": {"usage": 0.08},
                "Foundation": {"usage": 0.05},
                "Custom CSS": {"usage": 0.42},
            },
            "analytics": {
                "Google Analytics": {"adoption": 0.70},
                "Facebook Pixel": {"adoption": 0.25},
                "Hotjar": {"adoption": 0.08},
                "Adobe Analytics": {"adoption": 0.03},
                "None": {"adoption": 0.15},
            },
        }

    def _setup_insights_data(self):
        """Setup AI insights generation data"""
        self.insights_templates = {
            "performance_strengths": [
                "Website loads quickly with optimized images and efficient caching",
                "Mobile performance is excellent with responsive design",
                "Server response times are optimal",
                "Content delivery network implementation is effective",
                "Core Web Vitals meet Google's standards",
            ],
            "performance_issues": [
                "Large images are slowing down page load times",
                "Render-blocking JavaScript is delaying content display",
                "Server response times could be improved",
                "Multiple HTTP requests are impacting performance",
                "Unoptimized CSS is affecting load speed",
            ],
            "accessibility_strengths": [
                "Good color contrast ratios throughout the site",
                "Proper heading hierarchy is implemented",
                "Images have appropriate alt text",
                "Keyboard navigation is functional",
                "ARIA labels are properly used",
            ],
            "accessibility_issues": [
                "Some images are missing alt text",
                "Color contrast ratios need improvement",
                "Heading hierarchy could be better structured",
                "Form labels are not properly associated",
                "Keyboard navigation has some barriers",
            ],
            "seo_strengths": [
                "Meta titles and descriptions are well optimized",
                "URL structure is clean and descriptive",
                "Site has proper schema markup",
                "Internal linking strategy is effective",
                "Content is well structured with proper headings",
            ],
            "seo_issues": [
                "Meta descriptions are missing or too short",
                "Title tags could be more descriptive",
                "Missing schema markup opportunities",
                "Internal linking could be improved",
                "Some pages lack proper heading structure",
            ],
            "recommendations": [
                "Optimize images using WebP format and compression",
                "Implement lazy loading for below-the-fold content",
                "Minimize and combine CSS and JavaScript files",
                "Add proper alt text to all images",
                "Improve meta descriptions for better search visibility",
                "Implement structured data markup",
                "Enhance mobile responsiveness",
                "Improve page load speed through caching",
                "Add SSL certificate for security",
                "Optimize for Core Web Vitals",
            ],
        }

    def generate_scores(self, scenario: AssessmentScenario) -> dict[str, int]:
        """Generate realistic assessment scores for given scenario"""
        profile = self.profiles[scenario]

        # Generate scores within realistic ranges
        performance = self.random.randint(*profile.performance_range)
        accessibility = self.random.randint(*profile.accessibility_range)
        best_practices = self.random.randint(*profile.best_practices_range)
        seo = self.random.randint(*profile.seo_range)

        # Mobile and desktop scores (with some correlation to overall performance)
        mobile_base = self.random.randint(*profile.mobile_score_range)
        desktop_base = self.random.randint(*profile.desktop_score_range)

        # Add some correlation between mobile/desktop and overall performance
        performance_factor = (performance - 50) / 50  # -1 to 1 scale
        mobile_score = max(0, min(100, mobile_base + int(performance_factor * 10)))
        desktop_score = max(0, min(100, desktop_base + int(performance_factor * 10)))

        return {
            "performance_score": performance,
            "accessibility_score": accessibility,
            "best_practices_score": best_practices,
            "seo_score": seo,
            "mobile_score": mobile_score,
            "desktop_score": desktop_score,
        }

    def generate_pagespeed_data(self, scenario: AssessmentScenario, scores: dict[str, int]) -> dict[str, Any]:
        """Generate realistic PageSpeed Insights data"""
        profile = self.profiles[scenario]

        # Generate load times and page size
        load_time = round(self.random.uniform(*profile.load_time_range), 2)
        page_size = self.random.randint(*profile.page_size_range)

        # Core Web Vitals (correlated with performance score)
        performance_factor = scores["performance_score"] / 100

        # First Contentful Paint (0.9s to 4.0s)
        fcp = round(1.8 + (1.0 - performance_factor) * 2.2, 2)

        # Largest Contentful Paint (1.2s to 6.0s)
        lcp = round(2.5 + (1.0 - performance_factor) * 3.5, 2)

        # Cumulative Layout Shift (0.0 to 0.25)
        cls = round((1.0 - performance_factor) * 0.25, 3)

        # First Input Delay (10ms to 300ms)
        fid = round(50 + (1.0 - performance_factor) * 250)

        pagespeed_data = {
            "performance_score": scores["performance_score"],
            "accessibility_score": scores["accessibility_score"],
            "best_practices_score": scores["best_practices_score"],
            "seo_score": scores["seo_score"],
            "load_time": load_time,
            "page_size_kb": page_size,
            "core_web_vitals": {
                "first_contentful_paint": fcp,
                "largest_contentful_paint": lcp,
                "cumulative_layout_shift": cls,
                "first_input_delay": fid,
            },
            "mobile_score": scores["mobile_score"],
            "desktop_score": scores["desktop_score"],
            "assessment_date": datetime.utcnow().isoformat(),
            "scenario": scenario.value,
        }

        return pagespeed_data

    def generate_tech_stack_data(self, scenario: AssessmentScenario) -> dict[str, Any]:
        """Generate realistic technology stack detection data"""
        profile = self.profiles[scenario]

        detected_technologies = []

        # Add scenario-specific technologies
        for tech in profile.common_technologies:
            detected_technologies.append(
                {
                    "name": tech,
                    "confidence": self.random.uniform(0.7, 1.0),
                    "version": self.generate_version(),
                    "category": self.categorize_technology(tech),
                }
            )

        # Add some random common technologies
        all_techs = []
        for category, techs in self.technologies.items():
            for tech_name, tech_data in techs.items():
                if tech_name != "Unknown" and tech_name not in profile.common_technologies:
                    weight = tech_data.get(
                        "market_share",
                        tech_data.get(
                            "popularity",
                            tech_data.get("usage", tech_data.get("adoption", 0.1)),
                        ),
                    )
                    if self.random.random() < weight * 0.3:  # Reduce probability for variety
                        all_techs.append(tech_name)

        # Add 2-4 additional technologies
        additional_count = self.random.randint(2, 4)
        additional_techs = self.random.sample(all_techs, min(additional_count, len(all_techs)))

        for tech in additional_techs:
            detected_technologies.append(
                {
                    "name": tech,
                    "confidence": self.random.uniform(0.5, 0.9),
                    "version": self.generate_version(),
                    "category": self.categorize_technology(tech),
                }
            )

        tech_stack_data = {
            "detected_technologies": detected_technologies,
            "cms_detected": self.detect_cms(),
            "javascript_framework": self.detect_js_framework(),
            "css_framework": self.detect_css_framework(),
            "analytics_tools": self.detect_analytics(),
            "security_features": self.generate_security_features(),
            "hosting_info": self.generate_hosting_info(),
        }

        return tech_stack_data

    def generate_ai_insights_data(self, scenario: AssessmentScenario, scores: dict[str, int]) -> dict[str, Any]:
        """Generate realistic AI insights data"""
        profile = self.profiles[scenario]

        # Select insights based on scores and scenario
        strengths = []
        issues = []
        recommendations = []

        # Performance insights
        if scores["performance_score"] >= 80:
            strengths.extend(
                self.random.sample(
                    self.insights_templates["performance_strengths"],
                    k=self.random.randint(1, 2),
                )
            )
        else:
            issues.extend(
                self.random.sample(
                    self.insights_templates["performance_issues"],
                    k=self.random.randint(1, 3),
                )
            )

        # Accessibility insights
        if scores["accessibility_score"] >= 80:
            strengths.extend(
                self.random.sample(
                    self.insights_templates["accessibility_strengths"],
                    k=self.random.randint(1, 2),
                )
            )
        else:
            issues.extend(
                self.random.sample(
                    self.insights_templates["accessibility_issues"],
                    k=self.random.randint(1, 2),
                )
            )

        # SEO insights
        if scores["seo_score"] >= 75:
            strengths.extend(
                self.random.sample(
                    self.insights_templates["seo_strengths"],
                    k=self.random.randint(1, 2),
                )
            )
        else:
            issues.extend(self.random.sample(self.insights_templates["seo_issues"], k=self.random.randint(1, 2)))

        # Add scenario-specific issues
        issues.extend(self.random.sample(profile.typical_issues, k=min(2, len(profile.typical_issues))))

        # Generate recommendations
        rec_count = max(3, len(issues))
        recommendations = self.random.sample(
            self.insights_templates["recommendations"],
            k=min(rec_count, len(self.insights_templates["recommendations"])),
        )

        # Generate priority scores for recommendations
        prioritized_recommendations = []
        for rec in recommendations:
            priority = self.random.choice(["high", "medium", "low"])
            impact = self.random.choice(["high", "medium", "low"])
            effort = self.random.choice(["low", "medium", "high"])

            prioritized_recommendations.append(
                {
                    "recommendation": rec,
                    "priority": priority,
                    "estimated_impact": impact,
                    "implementation_effort": effort,
                    "category": self.categorize_recommendation(rec),
                }
            )

        ai_insights_data = {
            "overall_score": round(
                (
                    scores["performance_score"]
                    + scores["accessibility_score"]
                    + scores["best_practices_score"]
                    + scores["seo_score"]
                )
                / 4
            ),
            "strengths": strengths,
            "issues": issues,
            "recommendations": prioritized_recommendations,
            "competitor_analysis": self.generate_competitor_analysis(),
            "industry_benchmarks": self.generate_industry_benchmarks(scores),
            "improvement_potential": self.calculate_improvement_potential(scores),
            "analysis_confidence": self.random.uniform(0.75, 0.95),
        }

        return ai_insights_data

    def generate_assessment(
        self,
        business: Business,
        scenario: AssessmentScenario,
        assessment_id: str | None = None,
    ) -> AssessmentResult:
        """Generate a complete realistic assessment for given business and scenario"""
        profile = self.profiles[scenario]

        # Generate assessment scores
        scores = self.generate_scores(scenario)

        # Generate assessment data
        pagespeed_data = self.generate_pagespeed_data(scenario, scores)
        tech_stack_data = self.generate_tech_stack_data(scenario)
        ai_insights_data = self.generate_ai_insights_data(scenario, scores)

        # Determine assessment status
        status_weights = profile.status_weights
        status = self.random.choices(list(status_weights.keys()), weights=list(status_weights.values()))[0]

        # Determine assessment type based on scenario
        assessment_type = AssessmentType.FULL_AUDIT
        if scenario in [AssessmentScenario.MOBILE_OPTIMIZED] or scenario in [
            AssessmentScenario.HIGH_PERFORMANCE,
            AssessmentScenario.POOR_PERFORMANCE,
        ]:
            assessment_type = AssessmentType.PAGESPEED

        # Create assessment result
        assessment = AssessmentResult(
            id=assessment_id or str(uuid.uuid4()),
            business_id=business.id,
            assessment_type=assessment_type,
            status=AssessmentStatus[status],
            priority=self.random.randint(1, 10),
            # Website info
            url=business.website or f"https://{business.name.lower().replace(' ', '')}.com",
            domain=business.website.replace("https://", "").replace("http://", "").split("/")[0]
            if business.website
            else f"{business.name.lower().replace(' ', '')}.com",
            is_mobile=scenario == AssessmentScenario.MOBILE_OPTIMIZED,
            user_agent="Mozilla/5.0 (compatible; LeadFactory Assessment Bot)",
            # Scores
            performance_score=scores["performance_score"],
            accessibility_score=scores["accessibility_score"],
            best_practices_score=scores["best_practices_score"],
            seo_score=scores["seo_score"],
            # Assessment data
            pagespeed_data=pagespeed_data,
            tech_stack_data=tech_stack_data,
            ai_insights_data=ai_insights_data,
            assessment_metadata={
                "generated_scenario": scenario.value,
                "generation_seed": self.seed,
                "generated_at": datetime.utcnow().isoformat(),
                "mobile_score": scores["mobile_score"],
                "desktop_score": scores["desktop_score"],
            },
            # Timestamps
            created_at=datetime.utcnow(),
            completed_at=datetime.utcnow() if status == "COMPLETED" else None,
        )

        return assessment

    def generate_assessments(
        self,
        businesses: list[Business],
        scenarios: list[AssessmentScenario] | None = None,
    ) -> list[AssessmentResult]:
        """Generate assessments for multiple businesses"""
        if scenarios is None:
            scenarios = list(AssessmentScenario)

        assessments = []
        for business in businesses:
            scenario = self.random.choice(scenarios)
            assessment = self.generate_assessment(business, scenario)
            assessments.append(assessment)

        return assessments

    def generate_performance_dataset(self, businesses: list[Business], size: str = "small") -> list[AssessmentResult]:
        """Generate large assessment datasets for performance testing"""
        sizes = {
            "small": len(businesses),
            "medium": len(businesses) * 2,  # Multiple assessments per business
            "large": len(businesses) * 3,
            "xlarge": len(businesses) * 5,
        }

        target_count = sizes.get(size, len(businesses))
        assessments = []

        for i in range(target_count):
            business = businesses[i % len(businesses)]
            scenario = self.random.choice(list(AssessmentScenario))
            assessment = self.generate_assessment(business, scenario)
            assessments.append(assessment)

        return assessments

    # Helper methods
    def generate_version(self) -> str:
        """Generate realistic version numbers"""
        major = self.random.randint(1, 15)
        minor = self.random.randint(0, 20)
        patch = self.random.randint(0, 50)
        return f"{major}.{minor}.{patch}"

    def categorize_technology(self, tech: str) -> str:
        """Categorize technology by type"""
        categories = {
            "React": "JavaScript Framework",
            "Vue.js": "JavaScript Framework",
            "Angular": "JavaScript Framework",
            "jQuery": "JavaScript Library",
            "Bootstrap": "CSS Framework",
            "WordPress": "CMS",
            "Shopify": "E-commerce Platform",
            "Google Analytics": "Analytics",
            "Cloudflare": "CDN",
            "SSL": "Security",
        }
        return categories.get(tech, "Other")

    def detect_cms(self) -> str | None:
        """Detect CMS with weighted probability"""
        cms_options = list(self.technologies["cms"].keys())
        weights = [self.technologies["cms"][cms]["market_share"] for cms in cms_options]
        return self.random.choices(cms_options, weights=weights)[0]

    def detect_js_framework(self) -> str | None:
        """Detect JavaScript framework"""
        js_options = list(self.technologies["javascript_frameworks"].keys())
        weights = [self.technologies["javascript_frameworks"][js]["popularity"] for js in js_options]
        return self.random.choices(js_options, weights=weights)[0]

    def detect_css_framework(self) -> str | None:
        """Detect CSS framework"""
        css_options = list(self.technologies["css_frameworks"].keys())
        weights = [self.technologies["css_frameworks"][css]["usage"] for css in css_options]
        return self.random.choices(css_options, weights=weights)[0]

    def detect_analytics(self) -> list[str]:
        """Detect analytics tools"""
        tools = []
        for tool, data in self.technologies["analytics"].items():
            if tool != "None" and self.random.random() < data["adoption"]:
                tools.append(tool)
        return tools if tools else ["None"]

    def generate_security_features(self) -> dict[str, bool]:
        """Generate security feature detection"""
        return {
            "https": self.random.random() > 0.2,  # 80% have HTTPS
            "security_headers": self.random.random() > 0.4,  # 60% have security headers
            "ssl_certificate": self.random.random() > 0.15,  # 85% have SSL
            "content_security_policy": self.random.random() > 0.7,  # 30% have CSP
        }

    def generate_hosting_info(self) -> dict[str, str]:
        """Generate hosting information"""
        providers = [
            "AWS",
            "Google Cloud",
            "Azure",
            "Cloudflare",
            "DigitalOcean",
            "Shared Hosting",
            "Unknown",
        ]
        return {
            "provider": self.random.choice(providers),
            "cdn": "Cloudflare" if self.random.random() > 0.6 else "None",
            "server_location": self.random.choice(["US", "EU", "Asia", "Multiple"]),
        }

    def categorize_recommendation(self, rec: str) -> str:
        """Categorize recommendation by type"""
        if "image" in rec.lower():
            return "Images"
        if "seo" in rec.lower() or "meta" in rec.lower():
            return "SEO"
        if "accessibility" in rec.lower() or "alt" in rec.lower():
            return "Accessibility"
        if "performance" in rec.lower() or "speed" in rec.lower():
            return "Performance"
        return "General"

    def generate_competitor_analysis(self) -> dict[str, Any]:
        """Generate competitor analysis data"""
        return {
            "average_performance": self.random.randint(60, 80),
            "industry_leaders": [
                {"name": "Industry Leader 1", "score": self.random.randint(85, 95)},
                {"name": "Industry Leader 2", "score": self.random.randint(80, 90)},
            ],
            "market_position": self.random.choice(["above_average", "average", "below_average"]),
        }

    def generate_industry_benchmarks(self, scores: dict[str, int]) -> dict[str, Any]:
        """Generate industry benchmark data"""
        return {
            "industry_average_performance": self.random.randint(55, 75),
            "industry_average_accessibility": self.random.randint(60, 80),
            "industry_average_seo": self.random.randint(50, 70),
            "percentile_ranking": {
                "performance": min(95, max(5, int((scores["performance_score"] / 100) * 100))),
                "accessibility": min(95, max(5, int((scores["accessibility_score"] / 100) * 100))),
                "seo": min(95, max(5, int((scores["seo_score"] / 100) * 100))),
            },
        }

    def calculate_improvement_potential(self, scores: dict[str, int]) -> dict[str, Any]:
        """Calculate improvement potential"""
        avg_score = sum(scores.values()) / len(scores)
        potential = max(0, 90 - avg_score)  # Potential improvement to reach 90

        return {
            "overall_potential": round(potential),
            "quick_wins": self.random.randint(5, 15),
            "estimated_time_to_implement": f"{self.random.randint(2, 8)} weeks",
            "roi_estimate": self.random.choice(["high", "medium", "low"]),
        }

    def reset_seed(self, seed: int):
        """Reset generator seed for deterministic reproduction"""
        self.seed = seed
        self.random = random.Random(seed)
