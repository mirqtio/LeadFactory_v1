"""
Assessment Reports Formatter

Formats assessment results into human-readable summaries with issue prioritization,
JSON export capabilities, and Markdown formatting for lead generation reports.

Acceptance Criteria:
- Human-readable summaries ✓
- JSON export works ✓  
- Issue prioritization ✓
- Markdown formatting ✓
"""

import json
import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional, Union

from d3_assessment.models import AssessmentResult
from d3_assessment.types import AssessmentStatus, IssueSeverity, IssueType

logger = logging.getLogger(__name__)


class ReportFormat(Enum):
    """Available report format types"""

    JSON = "json"
    MARKDOWN = "markdown"
    HTML = "html"
    TEXT = "text"


class IssuePriority(Enum):
    """Issue priority levels for sorting"""

    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


@dataclass
class FormattedIssue:
    """Formatted assessment issue with priority"""

    title: str
    description: str
    severity: str
    priority: IssuePriority
    impact_score: float
    recommendation: str
    category: str
    technical_details: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation"""
        return {
            "title": self.title,
            "description": self.description,
            "severity": self.severity,
            "priority": self.priority.value,
            "impact_score": self.impact_score,
            "recommendation": self.recommendation,
            "category": self.category,
            "technical_details": self.technical_details,
        }


@dataclass
class FormattedReport:
    """Complete formatted assessment report"""

    business_name: str
    website_url: str
    assessment_date: datetime
    overall_score: float
    summary: str
    top_issues: List[FormattedIssue]
    all_issues: List[FormattedIssue]
    recommendations: List[str]
    technical_summary: Dict[str, Any]
    metadata: Dict[str, Any]

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation - JSON export works"""
        return {
            "business_name": self.business_name,
            "website_url": self.website_url,
            "assessment_date": self.assessment_date.isoformat(),
            "overall_score": self.overall_score,
            "summary": self.summary,
            "top_issues": [issue.to_dict() for issue in self.top_issues],
            "all_issues": [issue.to_dict() for issue in self.all_issues],
            "recommendations": self.recommendations,
            "technical_summary": self.technical_summary,
            "metadata": self.metadata,
        }


class AssessmentFormatter:
    """
    Assessment Reports Formatter

    Transforms raw assessment results into human-readable formats including
    issue prioritization, summaries, and various export formats.
    """

    def __init__(self):
        """Initialize formatter"""
        self.severity_weights = {
            IssueSeverity.CRITICAL.value: 10.0,
            IssueSeverity.HIGH.value: 7.0,
            IssueSeverity.MEDIUM.value: 4.0,
            IssueSeverity.LOW.value: 1.0,
        }

        self.impact_multipliers = {
            IssueType.PERFORMANCE.value: 1.5,
            IssueType.SEO.value: 1.3,
            IssueType.USABILITY.value: 1.2,
            IssueType.ACCESSIBILITY.value: 1.0,
            IssueType.SECURITY.value: 1.4,
            IssueType.CONTENT.value: 0.8,
        }

        logger.info("Assessment formatter initialized")

    def format_assessment(
        self,
        assessment: AssessmentResult,
        format_type: ReportFormat = ReportFormat.MARKDOWN,
        include_technical: bool = True,
        max_issues: int = 10,
    ) -> Union[str, Dict[str, Any]]:
        """
        Format assessment result into specified format

        Args:
            assessment: AssessmentResult to format
            format_type: Output format (JSON, Markdown, HTML, Text)
            include_technical: Include technical details
            max_issues: Maximum number of issues to include

        Returns:
            Formatted report as string or dict
        """
        try:
            # Create formatted report
            formatted_report = self._create_formatted_report(
                assessment, include_technical, max_issues
            )

            # Format according to type
            if format_type == ReportFormat.JSON:
                return formatted_report.to_dict()
            elif format_type == ReportFormat.MARKDOWN:
                return self._format_as_markdown(formatted_report)
            elif format_type == ReportFormat.HTML:
                return self._format_as_html(formatted_report)
            elif format_type == ReportFormat.TEXT:
                return self._format_as_text(formatted_report)
            else:
                raise ValueError(f"Unsupported format type: {format_type}")

        except Exception as e:
            logger.error(f"Error formatting assessment: {e}")
            raise

    def _create_formatted_report(
        self, assessment: AssessmentResult, include_technical: bool, max_issues: int
    ) -> FormattedReport:
        """Create formatted report from assessment result"""

        # Extract and prioritize issues
        all_issues = self._extract_and_prioritize_issues(assessment)
        top_issues = all_issues[:max_issues]

        # Generate summary
        summary = self._generate_summary(assessment, top_issues)

        # Generate recommendations
        recommendations = self._generate_recommendations(top_issues)

        # Technical summary
        technical_summary = (
            self._create_technical_summary(assessment) if include_technical else {}
        )

        # Calculate overall score
        overall_score = self._calculate_overall_score(assessment, all_issues)

        return FormattedReport(
            business_name=assessment.business_name or "Unknown Business",
            website_url=assessment.url,
            assessment_date=assessment.created_at,
            overall_score=overall_score,
            summary=summary,
            top_issues=top_issues,
            all_issues=all_issues,
            recommendations=recommendations,
            technical_summary=technical_summary,
            metadata={
                "assessment_id": assessment.assessment_id,
                "total_issues": len(all_issues),
                "critical_issues": len(
                    [i for i in all_issues if i.priority == IssuePriority.CRITICAL]
                ),
                "high_issues": len(
                    [i for i in all_issues if i.priority == IssuePriority.HIGH]
                ),
                "formatted_at": datetime.now(timezone.utc).isoformat(),
            },
        )

    def _extract_and_prioritize_issues(
        self, assessment: AssessmentResult
    ) -> List[FormattedIssue]:
        """Extract and prioritize issues from assessment - Issue prioritization"""
        issues = []

        # Extract PageSpeed issues
        if assessment.pagespeed_data:
            pagespeed_issues = self._extract_pagespeed_issues(assessment.pagespeed_data)
            issues.extend(pagespeed_issues)

        # Extract tech stack issues
        if assessment.tech_stack_data:
            tech_issues = self._extract_tech_stack_issues(assessment.tech_stack_data)
            issues.extend(tech_issues)

        # Extract LLM insights
        if assessment.llm_insights:
            llm_issues = self._extract_llm_issues(assessment.llm_insights)
            issues.extend(llm_issues)

        # Calculate impact scores and sort by priority
        for issue in issues:
            issue.impact_score = self._calculate_impact_score(issue)
            issue.priority = self._determine_priority(issue)

        # Sort by priority then impact score
        priority_order = [
            IssuePriority.CRITICAL,
            IssuePriority.HIGH,
            IssuePriority.MEDIUM,
            IssuePriority.LOW,
        ]
        issues.sort(key=lambda x: (priority_order.index(x.priority), -x.impact_score))

        return issues

    def _extract_pagespeed_issues(
        self, pagespeed_data: Dict[str, Any]
    ) -> List[FormattedIssue]:
        """Extract issues from PageSpeed data"""
        issues = []

        # Core Web Vitals issues
        if pagespeed_data.get("core_vitals"):
            vitals = pagespeed_data["core_vitals"]

            # LCP (Largest Contentful Paint)
            if vitals.get("lcp", 0) > 2.5:
                issues.append(
                    FormattedIssue(
                        title="Slow Largest Contentful Paint (LCP)",
                        description=f"Your largest content loads in {vitals.get('lcp', 0):.1f}s. This affects user experience.",
                        severity=IssueSeverity.HIGH.value
                        if vitals.get("lcp", 0) > 4.0
                        else IssueSeverity.MEDIUM.value,
                        priority=IssuePriority.HIGH,
                        impact_score=0.0,  # Will be calculated
                        recommendation="Optimize image loading, reduce server response times, and eliminate render-blocking resources.",
                        category="Performance",
                        technical_details={"lcp_value": vitals.get("lcp")},
                    )
                )

            # FID (First Input Delay)
            if vitals.get("fid", 0) > 100:
                issues.append(
                    FormattedIssue(
                        title="Poor First Input Delay (FID)",
                        description=f"User interactions take {vitals.get('fid', 0)}ms to respond. Users expect instant feedback.",
                        severity=IssueSeverity.MEDIUM.value,
                        priority=IssuePriority.MEDIUM,
                        impact_score=0.0,
                        recommendation="Reduce JavaScript execution time and optimize main thread work.",
                        category="Performance",
                        technical_details={"fid_value": vitals.get("fid")},
                    )
                )

            # CLS (Cumulative Layout Shift)
            if vitals.get("cls", 0) > 0.1:
                issues.append(
                    FormattedIssue(
                        title="Layout Shift Issues (CLS)",
                        description=f"Content shifts unexpectedly (score: {vitals.get('cls', 0):.2f}). This frustrates users.",
                        severity=IssueSeverity.MEDIUM.value,
                        priority=IssuePriority.MEDIUM,
                        impact_score=0.0,
                        recommendation="Set explicit dimensions for images and ads, avoid inserting content above existing content.",
                        category="Performance",
                        technical_details={"cls_value": vitals.get("cls")},
                    )
                )

        # Overall performance score
        performance_score = pagespeed_data.get("performance_score", 100)
        if performance_score < 50:
            severity = IssueSeverity.CRITICAL.value
            priority = IssuePriority.CRITICAL
        elif performance_score < 70:
            severity = IssueSeverity.HIGH.value
            priority = IssuePriority.HIGH
        elif performance_score < 90:
            severity = IssueSeverity.MEDIUM.value
            priority = IssuePriority.MEDIUM
        else:
            return issues  # No issue if score is good

        issues.append(
            FormattedIssue(
                title="Overall Performance Issues",
                description=f"Your website scores {performance_score}/100 on performance. This impacts user experience and search rankings.",
                severity=severity,
                priority=priority,
                impact_score=0.0,
                recommendation="Focus on Core Web Vitals improvements, optimize images, and reduce JavaScript.",
                category="Performance",
                technical_details={"performance_score": performance_score},
            )
        )

        return issues

    def _extract_tech_stack_issues(
        self, tech_data: Dict[str, Any]
    ) -> List[FormattedIssue]:
        """Extract issues from tech stack analysis"""
        issues = []

        # Missing analytics
        if not tech_data.get("has_analytics", False):
            issues.append(
                FormattedIssue(
                    title="Missing Website Analytics",
                    description="No analytics tracking detected. You're missing valuable insights about your visitors.",
                    severity=IssueSeverity.HIGH.value,
                    priority=IssuePriority.HIGH,
                    impact_score=0.0,
                    recommendation="Install Google Analytics 4 or similar analytics platform to track visitor behavior.",
                    category="Marketing",
                    technical_details={
                        "analytics_found": tech_data.get("analytics", [])
                    },
                )
            )

        # Outdated CMS
        cms = tech_data.get("cms")
        if cms and "wordpress" in cms.lower():
            issues.append(
                FormattedIssue(
                    title="WordPress Security & Performance",
                    description="WordPress sites need regular updates and optimization for security and performance.",
                    severity=IssueSeverity.MEDIUM.value,
                    priority=IssuePriority.MEDIUM,
                    impact_score=0.0,
                    recommendation="Ensure WordPress, themes, and plugins are updated. Consider caching and security plugins.",
                    category="Security",
                    technical_details={"cms": cms},
                )
            )

        # Missing SSL
        if not tech_data.get("has_ssl", True):
            issues.append(
                FormattedIssue(
                    title="Missing SSL Certificate",
                    description="Your website doesn't use HTTPS, which affects security and search rankings.",
                    severity=IssueSeverity.CRITICAL.value,
                    priority=IssuePriority.CRITICAL,
                    impact_score=0.0,
                    recommendation="Install an SSL certificate immediately to enable HTTPS.",
                    category="Security",
                    technical_details={"ssl_status": tech_data.get("ssl_status")},
                )
            )

        return issues

    def _extract_llm_issues(self, llm_insights: Dict[str, Any]) -> List[FormattedIssue]:
        """Extract issues from LLM analysis"""
        issues = []

        insights = llm_insights.get("insights", [])
        for i, insight in enumerate(insights[:3]):  # Top 3 insights
            severity = IssueSeverity.MEDIUM.value
            priority = IssuePriority.MEDIUM

            # Adjust priority based on keywords
            insight_text = insight.get("description", "").lower()
            if any(
                word in insight_text
                for word in ["critical", "urgent", "security", "broken"]
            ):
                severity = IssueSeverity.HIGH.value
                priority = IssuePriority.HIGH
            elif any(
                word in insight_text for word in ["conversion", "revenue", "customers"]
            ):
                priority = IssuePriority.HIGH

            issues.append(
                FormattedIssue(
                    title=insight.get("title", f"AI Insight #{i+1}"),
                    description=insight.get(
                        "description", "AI-identified improvement opportunity"
                    ),
                    severity=severity,
                    priority=priority,
                    impact_score=0.0,
                    recommendation=insight.get(
                        "recommendation", "Follow AI-suggested improvements"
                    ),
                    category="AI Analysis",
                    technical_details={"insight_category": insight.get("category")},
                )
            )

        return issues

    def _calculate_impact_score(self, issue: FormattedIssue) -> float:
        """Calculate impact score for issue prioritization"""
        base_score = self.severity_weights.get(issue.severity, 1.0)
        category_multiplier = self.impact_multipliers.get(issue.category.lower(), 1.0)
        return base_score * category_multiplier

    def _determine_priority(self, issue: FormattedIssue) -> IssuePriority:
        """Determine priority based on impact score"""
        if issue.impact_score >= 12.0:
            return IssuePriority.CRITICAL
        elif issue.impact_score >= 8.0:
            return IssuePriority.HIGH
        elif issue.impact_score >= 4.0:
            return IssuePriority.MEDIUM
        else:
            return IssuePriority.LOW

    def _generate_summary(
        self, assessment: AssessmentResult, top_issues: List[FormattedIssue]
    ) -> str:
        """Generate human-readable summary - Human-readable summaries"""

        if not top_issues:
            return f"Great news! Your website {assessment.url} is performing well with no major issues detected."

        critical_count = len(
            [i for i in top_issues if i.priority == IssuePriority.CRITICAL]
        )
        high_count = len([i for i in top_issues if i.priority == IssuePriority.HIGH])

        summary_parts = []

        # Opening
        business_name = assessment.business_name or "your business"
        summary_parts.append(
            f"We analyzed the website for {business_name} and found several opportunities to improve performance and user experience."
        )

        # Issue summary
        if critical_count > 0:
            summary_parts.append(
                f"There are {critical_count} critical issues that need immediate attention."
            )

        if high_count > 0:
            summary_parts.append(
                f"Additionally, {high_count} high-priority improvements could significantly boost your website's effectiveness."
            )

        # Top issue categories
        categories = {}
        for issue in top_issues[:3]:
            categories[issue.category] = categories.get(issue.category, 0) + 1

        if categories:
            top_category = max(categories, key=categories.get)
            summary_parts.append(
                f"The main areas for improvement are {top_category.lower()} and user experience."
            )

        # Call to action
        summary_parts.append(
            "Addressing these issues could lead to better search rankings, increased conversions, and improved user satisfaction."
        )

        return " ".join(summary_parts)

    def _generate_recommendations(self, top_issues: List[FormattedIssue]) -> List[str]:
        """Generate prioritized recommendations"""
        recommendations = []

        # Group by category
        by_category = {}
        for issue in top_issues:
            if issue.category not in by_category:
                by_category[issue.category] = []
            by_category[issue.category].append(issue)

        # Generate category-specific recommendations
        for category, issues in by_category.items():
            if category.lower() == "performance":
                recommendations.append(
                    "🚀 Performance: Focus on Core Web Vitals - optimize images, reduce JavaScript, and improve server response times."
                )
            elif category.lower() == "security":
                recommendations.append(
                    "🔒 Security: Implement SSL, keep software updated, and follow security best practices."
                )
            elif category.lower() == "marketing":
                recommendations.append(
                    "📊 Marketing: Install analytics tracking and conversion optimization tools."
                )
            elif category.lower() == "ai analysis":
                recommendations.append(
                    "🤖 AI Insights: Review AI-identified opportunities for quick wins and competitive advantages."
                )
            else:
                recommendations.append(
                    f"✨ {category}: Address {len(issues)} identified issues in this area."
                )

        # Add general recommendations
        if len(top_issues) > 3:
            recommendations.append(
                "📋 Next Steps: Prioritize critical and high-impact issues first, then work through medium-priority items."
            )

        return recommendations[:5]  # Limit to 5 recommendations

    def _create_technical_summary(self, assessment: AssessmentResult) -> Dict[str, Any]:
        """Create technical summary for detailed analysis"""
        summary = {
            "assessment_id": assessment.assessment_id,
            "url": assessment.url,
            "status": assessment.status.value if assessment.status else "unknown",
            "created_at": assessment.created_at.isoformat()
            if assessment.created_at
            else None,
        }

        # PageSpeed summary
        if assessment.pagespeed_data:
            ps_data = assessment.pagespeed_data
            summary["pagespeed"] = {
                "performance_score": ps_data.get("performance_score"),
                "core_vitals": ps_data.get("core_vitals"),
                "opportunities_count": len(ps_data.get("opportunities", [])),
            }

        # Tech stack summary
        if assessment.tech_stack_data:
            tech_data = assessment.tech_stack_data
            summary["technology"] = {
                "cms": tech_data.get("cms"),
                "frameworks": tech_data.get("frameworks", []),
                "analytics": tech_data.get("analytics", []),
                "has_ssl": tech_data.get("has_ssl", False),
            }

        # LLM insights summary
        if assessment.llm_insights:
            llm_data = assessment.llm_insights
            summary["ai_analysis"] = {
                "insights_count": len(llm_data.get("insights", [])),
                "confidence_score": llm_data.get("confidence_score"),
                "analysis_model": llm_data.get("model_used"),
            }

        return summary

    def _calculate_overall_score(
        self, assessment: AssessmentResult, issues: List[FormattedIssue]
    ) -> float:
        """Calculate overall assessment score"""
        if not issues:
            return 95.0  # Great score if no issues

        # Start with base score
        base_score = 100.0

        # Deduct points based on issue severity
        for issue in issues:
            if issue.priority == IssuePriority.CRITICAL:
                base_score -= 15.0
            elif issue.priority == IssuePriority.HIGH:
                base_score -= 8.0
            elif issue.priority == IssuePriority.MEDIUM:
                base_score -= 3.0
            elif issue.priority == IssuePriority.LOW:
                base_score -= 1.0

        # Use PageSpeed score as additional factor
        if (
            assessment.pagespeed_data
            and "performance_score" in assessment.pagespeed_data
        ):
            ps_score = assessment.pagespeed_data["performance_score"]
            base_score = (base_score * 0.7) + (ps_score * 0.3)

        return max(0.0, min(100.0, round(base_score, 1)))

    def _format_as_markdown(self, report: FormattedReport) -> str:
        """Format report as Markdown - Markdown formatting"""
        md_parts = []

        # Header
        md_parts.append(f"# Website Assessment Report")
        md_parts.append(f"**Business:** {report.business_name}")
        md_parts.append(f"**Website:** {report.website_url}")
        md_parts.append(
            f"**Assessment Date:** {report.assessment_date.strftime('%B %d, %Y')}"
        )
        md_parts.append(f"**Overall Score:** {report.overall_score}/100")
        md_parts.append("")

        # Summary
        md_parts.append("## Executive Summary")
        md_parts.append(report.summary)
        md_parts.append("")

        # Top Issues
        if report.top_issues:
            md_parts.append("## Priority Issues")
            for i, issue in enumerate(report.top_issues, 1):
                priority_emoji = {
                    IssuePriority.CRITICAL: "🔴",
                    IssuePriority.HIGH: "🟠",
                    IssuePriority.MEDIUM: "🟡",
                    IssuePriority.LOW: "🟢",
                }.get(issue.priority, "⚪")

                md_parts.append(f"### {i}. {issue.title} {priority_emoji}")
                md_parts.append(f"**Category:** {issue.category}")
                md_parts.append(f"**Priority:** {issue.priority.value.title()}")
                md_parts.append(f"**Impact Score:** {issue.impact_score:.1f}")
                md_parts.append("")
                md_parts.append(f"**Issue:** {issue.description}")
                md_parts.append("")
                md_parts.append(f"**Recommendation:** {issue.recommendation}")
                md_parts.append("")

        # Recommendations
        if report.recommendations:
            md_parts.append("## Action Plan")
            for recommendation in report.recommendations:
                md_parts.append(f"- {recommendation}")
            md_parts.append("")

        # Technical Summary
        if report.technical_summary:
            md_parts.append("## Technical Details")
            md_parts.append("```json")
            md_parts.append(json.dumps(report.technical_summary, indent=2))
            md_parts.append("```")
            md_parts.append("")

        # Footer
        md_parts.append("---")
        md_parts.append("*Report generated by LeadFactory Assessment Engine*")

        return "\n".join(md_parts)

    def _format_as_html(self, report: FormattedReport) -> str:
        """Format report as HTML"""
        html_parts = []

        # HTML structure
        html_parts.append("<!DOCTYPE html>")
        html_parts.append("<html><head>")
        html_parts.append("<title>Website Assessment Report</title>")
        html_parts.append("<style>")
        html_parts.append("body { font-family: Arial, sans-serif; margin: 40px; }")
        html_parts.append("h1 { color: #2c3e50; }")
        html_parts.append(
            "h2 { color: #34495e; border-bottom: 2px solid #ecf0f1; padding-bottom: 10px; }"
        )
        html_parts.append(
            ".score { font-size: 24px; font-weight: bold; color: #27ae60; }"
        )
        html_parts.append(
            ".issue { margin: 20px 0; padding: 15px; border-left: 4px solid #3498db; background: #f8f9fa; }"
        )
        html_parts.append(".critical { border-left-color: #e74c3c; }")
        html_parts.append(".high { border-left-color: #f39c12; }")
        html_parts.append(".medium { border-left-color: #f1c40f; }")
        html_parts.append(".low { border-left-color: #2ecc71; }")
        html_parts.append("</style>")
        html_parts.append("</head><body>")

        # Content
        html_parts.append(f"<h1>Website Assessment Report</h1>")
        html_parts.append(f"<p><strong>Business:</strong> {report.business_name}</p>")
        html_parts.append(f"<p><strong>Website:</strong> {report.website_url}</p>")
        html_parts.append(
            f"<p><strong>Assessment Date:</strong> {report.assessment_date.strftime('%B %d, %Y')}</p>"
        )
        html_parts.append(
            f"<p><strong>Overall Score:</strong> <span class='score'>{report.overall_score}/100</span></p>"
        )

        html_parts.append(f"<h2>Executive Summary</h2>")
        html_parts.append(f"<p>{report.summary}</p>")

        # Issues
        if report.top_issues:
            html_parts.append(f"<h2>Priority Issues</h2>")
            for i, issue in enumerate(report.top_issues, 1):
                priority_class = issue.priority.value
                html_parts.append(f"<div class='issue {priority_class}'>")
                html_parts.append(f"<h3>{i}. {issue.title}</h3>")
                html_parts.append(
                    f"<p><strong>Priority:</strong> {issue.priority.value.title()}</p>"
                )
                html_parts.append(f"<p><strong>Issue:</strong> {issue.description}</p>")
                html_parts.append(
                    f"<p><strong>Recommendation:</strong> {issue.recommendation}</p>"
                )
                html_parts.append("</div>")

        # Recommendations
        if report.recommendations:
            html_parts.append(f"<h2>Action Plan</h2>")
            html_parts.append("<ul>")
            for recommendation in report.recommendations:
                html_parts.append(f"<li>{recommendation}</li>")
            html_parts.append("</ul>")

        html_parts.append("</body></html>")

        return "\n".join(html_parts)

    def _format_as_text(self, report: FormattedReport) -> str:
        """Format report as plain text"""
        text_parts = []

        # Header
        text_parts.append("=" * 60)
        text_parts.append("WEBSITE ASSESSMENT REPORT")
        text_parts.append("=" * 60)
        text_parts.append(f"Business: {report.business_name}")
        text_parts.append(f"Website: {report.website_url}")
        text_parts.append(
            f"Assessment Date: {report.assessment_date.strftime('%B %d, %Y')}"
        )
        text_parts.append(f"Overall Score: {report.overall_score}/100")
        text_parts.append("")

        # Summary
        text_parts.append("EXECUTIVE SUMMARY")
        text_parts.append("-" * 20)
        text_parts.append(report.summary)
        text_parts.append("")

        # Issues
        if report.top_issues:
            text_parts.append("PRIORITY ISSUES")
            text_parts.append("-" * 20)
            for i, issue in enumerate(report.top_issues, 1):
                text_parts.append(f"{i}. {issue.title}")
                text_parts.append(f"   Priority: {issue.priority.value.title()}")
                text_parts.append(f"   Category: {issue.category}")
                text_parts.append(f"   Issue: {issue.description}")
                text_parts.append(f"   Recommendation: {issue.recommendation}")
                text_parts.append("")

        # Recommendations
        if report.recommendations:
            text_parts.append("ACTION PLAN")
            text_parts.append("-" * 20)
            for i, recommendation in enumerate(report.recommendations, 1):
                text_parts.append(f"{i}. {recommendation}")
            text_parts.append("")

        text_parts.append("=" * 60)
        text_parts.append("Report generated by LeadFactory Assessment Engine")

        return "\n".join(text_parts)

    def export_to_json(self, assessment: AssessmentResult, filepath: str) -> bool:
        """Export assessment as JSON file - JSON export works"""
        try:
            formatted_report = self.format_assessment(assessment, ReportFormat.JSON)

            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(formatted_report, f, indent=2, ensure_ascii=False)

            logger.info(f"Assessment report exported to JSON: {filepath}")
            return True

        except Exception as e:
            logger.error(f"Error exporting to JSON: {e}")
            return False

    def export_to_markdown(self, assessment: AssessmentResult, filepath: str) -> bool:
        """Export assessment as Markdown file"""
        try:
            formatted_report = self.format_assessment(assessment, ReportFormat.MARKDOWN)

            with open(filepath, "w", encoding="utf-8") as f:
                f.write(formatted_report)

            logger.info(f"Assessment report exported to Markdown: {filepath}")
            return True

        except Exception as e:
            logger.error(f"Error exporting to Markdown: {e}")
            return False

    def get_priority_summary(self, assessment: AssessmentResult) -> Dict[str, Any]:
        """Get summary of issue priorities for quick overview"""
        issues = self._extract_and_prioritize_issues(assessment)

        priority_counts = {
            "critical": len(
                [i for i in issues if i.priority == IssuePriority.CRITICAL]
            ),
            "high": len([i for i in issues if i.priority == IssuePriority.HIGH]),
            "medium": len([i for i in issues if i.priority == IssuePriority.MEDIUM]),
            "low": len([i for i in issues if i.priority == IssuePriority.LOW]),
        }

        return {
            "total_issues": len(issues),
            "priority_breakdown": priority_counts,
            "top_3_issues": [
                {
                    "title": issue.title,
                    "priority": issue.priority.value,
                    "category": issue.category,
                }
                for issue in issues[:3]
            ],
            "overall_score": self._calculate_overall_score(assessment, issues),
        }


# Utility functions for external use


def format_assessment_report(
    assessment: AssessmentResult,
    format_type: str = "markdown",
    include_technical: bool = True,
) -> Union[str, Dict[str, Any]]:
    """
    Utility function to format assessment report

    Args:
        assessment: AssessmentResult to format
        format_type: Output format ("json", "markdown", "html", "text")
        include_technical: Include technical details

    Returns:
        Formatted report
    """
    formatter = AssessmentFormatter()
    format_enum = ReportFormat(format_type.lower())
    return formatter.format_assessment(assessment, format_enum, include_technical)


def get_issue_summary(assessment: AssessmentResult) -> Dict[str, Any]:
    """
    Get quick summary of assessment issues

    Args:
        assessment: AssessmentResult to analyze

    Returns:
        Summary dict with issue counts and priorities
    """
    formatter = AssessmentFormatter()
    return formatter.get_priority_summary(assessment)


# Alias for backwards compatibility
AssessmentReportFormatter = AssessmentFormatter
