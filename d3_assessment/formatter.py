"""
Assessment Reports Formatter - Task 038

Formats assessment results into human-readable reports with various output
formats including JSON, Markdown, and text summaries. Implements issue
prioritization to help users focus on the most important problems.

Acceptance Criteria:
- Human-readable summaries
- JSON export works
- Issue prioritization
- Markdown formatting
"""
import json
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime
from decimal import Decimal
from enum import Enum
import textwrap

from .types import AssessmentType, AssessmentStatus
from .coordinator import CoordinatorResult
from .models import AssessmentResult


class ReportFormat(Enum):
    """Available report formats"""
    TEXT = "text"
    JSON = "json"
    MARKDOWN = "markdown"
    HTML = "html"


class IssueSeverity(Enum):
    """Issue severity levels for prioritization"""
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"


class AssessmentReportFormatter:
    """
    Formats assessment results into various report formats
    
    Acceptance Criteria: Human-readable summaries, JSON export works,
    Issue prioritization, Markdown formatting
    """
    
    def __init__(self):
        """Initialize report formatter"""
        self.severity_weights = {
            IssueSeverity.CRITICAL: 100,
            IssueSeverity.HIGH: 75,
            IssueSeverity.MEDIUM: 50,
            IssueSeverity.LOW: 25,
            IssueSeverity.INFO: 10
        }
    
    def format_report(
        self,
        result: CoordinatorResult,
        format_type: ReportFormat = ReportFormat.TEXT,
        include_raw_data: bool = False
    ) -> str:
        """
        Format assessment results into specified format
        
        Args:
            result: Coordinator result to format
            format_type: Output format type
            include_raw_data: Include raw assessment data
            
        Returns:
            Formatted report string
        """
        if format_type == ReportFormat.JSON:
            return self._format_json(result, include_raw_data)
        elif format_type == ReportFormat.MARKDOWN:
            return self._format_markdown(result)
        elif format_type == ReportFormat.HTML:
            return self._format_html(result)
        else:  # TEXT
            return self._format_text(result)
    
    def _format_text(self, result: CoordinatorResult) -> str:
        """
        Format as human-readable text summary
        
        Acceptance Criteria: Human-readable summaries
        """
        lines = []
        
        # Header
        lines.append("=" * 80)
        lines.append("WEBSITE ASSESSMENT REPORT")
        lines.append("=" * 80)
        lines.append(f"Session ID: {result.session_id}")
        lines.append(f"Business ID: {result.business_id}")
        lines.append(f"Assessment Date: {result.completed_at.strftime('%Y-%m-%d %H:%M:%S UTC')}")
        lines.append(f"Duration: {result.execution_time_ms / 1000:.2f} seconds")
        lines.append(f"Total Cost: ${result.total_cost_usd}")
        lines.append("")
        
        # Summary
        lines.append("SUMMARY")
        lines.append("-" * 40)
        lines.append(f"Total Assessments: {result.total_assessments}")
        lines.append(f"Completed: {result.completed_assessments}")
        lines.append(f"Failed: {result.failed_assessments}")
        
        if result.failed_assessments > 0:
            lines.append("\nFailed Assessments:")
            for atype, error in result.errors.items():
                lines.append(f"  - {atype.value}: {error}")
        
        lines.append("")
        
        # Prioritized issues
        issues = self._extract_and_prioritize_issues(result)
        if issues:
            lines.append("PRIORITIZED ISSUES")
            lines.append("-" * 40)
            
            for severity in IssueSeverity:
                severity_issues = [i for i in issues if i['severity'] == severity]
                if severity_issues:
                    lines.append(f"\n{severity.value.upper()} ({len(severity_issues)} issues):")
                    for issue in severity_issues[:5]:  # Show top 5 per severity
                        lines.append(f"  • {issue['title']}")
                        wrapped_desc = textwrap.wrap(issue['description'], width=76)
                        for line in wrapped_desc:
                            lines.append(f"    {line}")
                        if issue.get('recommendation'):
                            lines.append(f"    → {issue['recommendation']}")
                        lines.append("")
        
        # Assessment Results
        lines.append("\nASSESSMENT RESULTS")
        lines.append("-" * 40)
        
        # PageSpeed Results
        if AssessmentType.PAGESPEED in result.partial_results:
            ps_result = result.partial_results[AssessmentType.PAGESPEED]
            if ps_result and ps_result.status == AssessmentStatus.COMPLETED:
                lines.append("\nPageSpeed Insights:")
                lines.append(f"  Performance Score: {ps_result.performance_score}/100")
                lines.append(f"  Accessibility Score: {ps_result.accessibility_score}/100")
                lines.append(f"  SEO Score: {ps_result.seo_score}/100")
                lines.append(f"  Best Practices: {ps_result.best_practices_score}/100")
                
                lines.append("\n  Core Web Vitals:")
                lines.append(f"    LCP: {ps_result.largest_contentful_paint}ms")
                lines.append(f"    FID: {ps_result.first_input_delay}ms")
                lines.append(f"    CLS: {ps_result.cumulative_layout_shift}")
        
        # Tech Stack Results
        if AssessmentType.TECH_STACK in result.partial_results:
            ts_result = result.partial_results[AssessmentType.TECH_STACK]
            if ts_result and ts_result.tech_stack_data:
                lines.append("\nTechnology Stack:")
                tech_by_category = self._group_technologies_by_category(
                    ts_result.tech_stack_data.get("technologies", [])
                )
                for category, techs in tech_by_category.items():
                    tech_names = [t['technology_name'] for t in techs[:3]]
                    lines.append(f"  {category}: {', '.join(tech_names)}")
        
        # AI Insights Results
        if AssessmentType.AI_INSIGHTS in result.partial_results:
            ai_result = result.partial_results[AssessmentType.AI_INSIGHTS]
            if ai_result and ai_result.ai_insights_data:
                insights = ai_result.ai_insights_data.get("insights", {})
                if insights.get("recommendations"):
                    lines.append("\nAI Recommendations:")
                    for i, rec in enumerate(insights["recommendations"][:3], 1):
                        lines.append(f"  {i}. {rec.get('title', 'Recommendation')}")
                        if rec.get('impact'):
                            lines.append(f"     Impact: {rec['impact']}")
        
        lines.append("\n" + "=" * 80)
        return "\n".join(lines)
    
    def _format_json(self, result: CoordinatorResult, include_raw: bool = False) -> str:
        """
        Format as JSON export
        
        Acceptance Criteria: JSON export works
        """
        report_data = {
            "metadata": {
                "session_id": result.session_id,
                "business_id": result.business_id,
                "generated_at": datetime.utcnow().isoformat(),
                "assessment_date": result.completed_at.isoformat(),
                "duration_seconds": result.execution_time_ms / 1000,
                "total_cost_usd": str(result.total_cost_usd)
            },
            "summary": {
                "total_assessments": result.total_assessments,
                "completed_assessments": result.completed_assessments,
                "failed_assessments": result.failed_assessments,
                "success_rate": (
                    result.completed_assessments / result.total_assessments
                    if result.total_assessments > 0 else 0
                )
            },
            "errors": {atype.value: error for atype, error in result.errors.items()},
            "prioritized_issues": self._extract_and_prioritize_issues(result),
            "results": {}
        }
        
        # Add assessment results
        for atype, assessment in result.partial_results.items():
            if assessment and assessment.status == AssessmentStatus.COMPLETED:
                report_data["results"][atype.value] = self._serialize_assessment_result(
                    assessment, include_raw
                )
        
        return json.dumps(report_data, indent=2, default=str)
    
    def _format_markdown(self, result: CoordinatorResult) -> str:
        """
        Format as Markdown report
        
        Acceptance Criteria: Markdown formatting
        """
        lines = []
        
        # Header
        lines.append("# Website Assessment Report")
        lines.append("")
        lines.append("## Report Information")
        lines.append(f"- **Session ID**: `{result.session_id}`")
        lines.append(f"- **Business ID**: `{result.business_id}`")
        lines.append(f"- **Date**: {result.completed_at.strftime('%Y-%m-%d %H:%M:%S UTC')}")
        lines.append(f"- **Duration**: {result.execution_time_ms / 1000:.2f} seconds")
        lines.append(f"- **Total Cost**: ${result.total_cost_usd}")
        lines.append("")
        
        # Summary
        lines.append("## Summary")
        lines.append("")
        lines.append("| Metric | Value |")
        lines.append("|--------|-------|")
        lines.append(f"| Total Assessments | {result.total_assessments} |")
        lines.append(f"| Completed | {result.completed_assessments} |")
        lines.append(f"| Failed | {result.failed_assessments} |")
        lines.append(f"| Success Rate | {(result.completed_assessments/result.total_assessments*100):.1f}% |")
        lines.append("")
        
        # Prioritized Issues
        issues = self._extract_and_prioritize_issues(result)
        if issues:
            lines.append("## Prioritized Issues")
            lines.append("")
            
            for severity in IssueSeverity:
                severity_issues = [i for i in issues if i['severity'] == severity]
                if severity_issues:
                    emoji = self._get_severity_emoji(severity)
                    lines.append(f"### {emoji} {severity.value.title()} Priority")
                    lines.append("")
                    
                    for issue in severity_issues[:5]:
                        lines.append(f"**{issue['title']}**")
                        lines.append(f"- {issue['description']}")
                        if issue.get('recommendation'):
                            lines.append(f"- 💡 **Recommendation**: {issue['recommendation']}")
                        lines.append("")
        
        # Assessment Results
        lines.append("## Assessment Results")
        lines.append("")
        
        # PageSpeed Results
        if AssessmentType.PAGESPEED in result.partial_results:
            ps_result = result.partial_results[AssessmentType.PAGESPEED]
            if ps_result and ps_result.status == AssessmentStatus.COMPLETED:
                lines.append("### PageSpeed Insights")
                lines.append("")
                
                # Scores table
                lines.append("#### Scores")
                lines.append("| Category | Score | Grade |")
                lines.append("|----------|-------|-------|")
                lines.append(f"| Performance | {ps_result.performance_score}/100 | {self._get_grade_emoji(ps_result.performance_score)} |")
                lines.append(f"| Accessibility | {ps_result.accessibility_score}/100 | {self._get_grade_emoji(ps_result.accessibility_score)} |")
                lines.append(f"| SEO | {ps_result.seo_score}/100 | {self._get_grade_emoji(ps_result.seo_score)} |")
                lines.append(f"| Best Practices | {ps_result.best_practices_score}/100 | {self._get_grade_emoji(ps_result.best_practices_score)} |")
                lines.append("")
                
                # Core Web Vitals
                lines.append("#### Core Web Vitals")
                lines.append("| Metric | Value | Status |")
                lines.append("|--------|-------|--------|")
                lines.append(f"| LCP | {ps_result.largest_contentful_paint}ms | {self._get_cwv_status('lcp', ps_result.largest_contentful_paint)} |")
                lines.append(f"| FID | {ps_result.first_input_delay}ms | {self._get_cwv_status('fid', ps_result.first_input_delay)} |")
                lines.append(f"| CLS | {ps_result.cumulative_layout_shift} | {self._get_cwv_status('cls', ps_result.cumulative_layout_shift)} |")
                lines.append("")
        
        # Tech Stack Results
        if AssessmentType.TECH_STACK in result.partial_results:
            ts_result = result.partial_results[AssessmentType.TECH_STACK]
            if ts_result and ts_result.tech_stack_data:
                lines.append("### Technology Stack")
                lines.append("")
                
                tech_by_category = self._group_technologies_by_category(
                    ts_result.tech_stack_data.get("technologies", [])
                )
                
                for category, techs in tech_by_category.items():
                    lines.append(f"**{category}**:")
                    for tech in techs[:5]:
                        confidence = tech.get('confidence', 0) * 100
                        version = f" v{tech['version']}" if tech.get('version') else ""
                        lines.append(f"- {tech['technology_name']}{version} ({confidence:.0f}% confidence)")
                    lines.append("")
        
        # AI Insights
        if AssessmentType.AI_INSIGHTS in result.partial_results:
            ai_result = result.partial_results[AssessmentType.AI_INSIGHTS]
            if ai_result and ai_result.ai_insights_data:
                insights = ai_result.ai_insights_data.get("insights", {})
                if insights.get("recommendations"):
                    lines.append("### AI-Generated Insights")
                    lines.append("")
                    
                    for i, rec in enumerate(insights["recommendations"][:5], 1):
                        lines.append(f"#### {i}. {rec.get('title', 'Recommendation')}")
                        lines.append(f"**Priority**: {rec.get('priority', 'Medium')}")
                        lines.append(f"**Effort**: {rec.get('effort', 'Medium')}")
                        lines.append(f"**Impact**: {rec.get('impact', 'Not specified')}")
                        lines.append("")
                        lines.append(rec.get('description', ''))
                        lines.append("")
        
        lines.append("---")
        lines.append(f"*Report generated on {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')}*")
        
        return "\n".join(lines)
    
    def _format_html(self, result: CoordinatorResult) -> str:
        """Format as HTML report (basic version)"""
        # Convert markdown to HTML-like format
        markdown_content = self._format_markdown(result)
        
        html = f"""<!DOCTYPE html>
<html>
<head>
    <title>Assessment Report - {result.session_id}</title>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 40px; }}
        h1, h2, h3 {{ color: #333; }}
        table {{ border-collapse: collapse; width: 100%; margin: 20px 0; }}
        th, td {{ border: 1px solid #ddd; padding: 8px; text-align: left; }}
        th {{ background-color: #f2f2f2; }}
        .critical {{ color: #d32f2f; }}
        .high {{ color: #f57c00; }}
        .medium {{ color: #fbc02d; }}
        .low {{ color: #689f38; }}
        .info {{ color: #1976d2; }}
    </style>
</head>
<body>
    <pre>{markdown_content}</pre>
</body>
</html>"""
        return html
    
    def _extract_and_prioritize_issues(self, result: CoordinatorResult) -> List[Dict[str, Any]]:
        """
        Extract and prioritize issues from assessment results
        
        Acceptance Criteria: Issue prioritization
        """
        issues = []
        
        # Extract PageSpeed issues
        if AssessmentType.PAGESPEED in result.partial_results:
            ps_result = result.partial_results[AssessmentType.PAGESPEED]
            if ps_result and ps_result.status == AssessmentStatus.COMPLETED:
                # Performance issues
                if ps_result.performance_score < 50:
                    severity = IssueSeverity.CRITICAL
                elif ps_result.performance_score < 75:
                    severity = IssueSeverity.HIGH
                elif ps_result.performance_score < 90:
                    severity = IssueSeverity.MEDIUM
                else:
                    severity = None
                
                if severity:
                    issues.append({
                        'severity': severity,
                        'category': 'performance',
                        'title': f'Poor Performance Score ({ps_result.performance_score}/100)',
                        'description': 'Website performance is below acceptable thresholds',
                        'recommendation': 'Focus on optimizing largest contentful paint and reducing JavaScript execution time',
                        'score': self.severity_weights[severity] + (100 - ps_result.performance_score)
                    })
                
                # Core Web Vitals issues
                if ps_result.largest_contentful_paint and ps_result.largest_contentful_paint > 4000:
                    issues.append({
                        'severity': IssueSeverity.HIGH,
                        'category': 'core_web_vitals',
                        'title': f'Slow Largest Contentful Paint ({ps_result.largest_contentful_paint}ms)',
                        'description': 'LCP is above 4s threshold, impacting user experience',
                        'recommendation': 'Optimize images, improve server response times, and use CDN',
                        'score': self.severity_weights[IssueSeverity.HIGH] + (ps_result.largest_contentful_paint / 100)
                    })
                
                # Accessibility issues
                if ps_result.accessibility_score < 70:
                    issues.append({
                        'severity': IssueSeverity.HIGH,
                        'category': 'accessibility',
                        'title': f'Accessibility Issues ({ps_result.accessibility_score}/100)',
                        'description': 'Website has significant accessibility problems',
                        'recommendation': 'Add alt text to images, ensure proper heading structure, and improve color contrast',
                        'score': self.severity_weights[IssueSeverity.HIGH] + (100 - ps_result.accessibility_score)
                    })
        
        # Extract tech stack issues
        if AssessmentType.TECH_STACK in result.partial_results:
            ts_result = result.partial_results[AssessmentType.TECH_STACK]
            if ts_result and ts_result.tech_stack_data:
                techs = ts_result.tech_stack_data.get("technologies", [])
                
                # Check for outdated technologies
                for tech in techs:
                    if tech.get('version') and self._is_outdated_version(tech):
                        issues.append({
                            'severity': IssueSeverity.MEDIUM,
                            'category': 'security',
                            'title': f'Outdated {tech["technology_name"]} version',
                            'description': f'{tech["technology_name"]} {tech.get("version", "")} may have security vulnerabilities',
                            'recommendation': f'Update {tech["technology_name"]} to the latest stable version',
                            'score': self.severity_weights[IssueSeverity.MEDIUM]
                        })
        
        # Sort by score (higher score = higher priority)
        issues.sort(key=lambda x: x['score'], reverse=True)
        
        # Remove score from final output
        for issue in issues:
            issue.pop('score', None)
        
        return issues
    
    def _group_technologies_by_category(self, technologies: List[Dict]) -> Dict[str, List[Dict]]:
        """Group technologies by category"""
        grouped = {}
        for tech in technologies:
            category = tech.get('category', 'Other')
            if category not in grouped:
                grouped[category] = []
            grouped[category].append(tech)
        
        # Sort categories and limit technologies per category
        return {k: sorted(v, key=lambda x: x.get('confidence', 0), reverse=True) 
                for k, v in sorted(grouped.items())}
    
    def _serialize_assessment_result(self, assessment: AssessmentResult, include_raw: bool) -> Dict[str, Any]:
        """Serialize assessment result for JSON export"""
        data = {
            "status": assessment.status.value,
            "url": assessment.url,
            "domain": assessment.domain
        }
        
        if assessment.assessment_type == AssessmentType.PAGESPEED:
            data.update({
                "scores": {
                    "performance": assessment.performance_score,
                    "accessibility": assessment.accessibility_score,
                    "seo": assessment.seo_score,
                    "best_practices": assessment.best_practices_score
                },
                "core_web_vitals": {
                    "lcp": assessment.largest_contentful_paint,
                    "fid": assessment.first_input_delay,
                    "cls": assessment.cumulative_layout_shift
                }
            })
            if include_raw and assessment.pagespeed_data:
                data["raw_data"] = assessment.pagespeed_data
                
        elif assessment.assessment_type == AssessmentType.TECH_STACK:
            if assessment.tech_stack_data:
                data["technologies"] = assessment.tech_stack_data.get("technologies", [])
                
        elif assessment.assessment_type == AssessmentType.AI_INSIGHTS:
            if assessment.ai_insights_data:
                data["insights"] = assessment.ai_insights_data.get("insights", {})
                data["cost_usd"] = str(assessment.ai_insights_data.get("total_cost_usd", 0))
        
        return data
    
    def _get_severity_emoji(self, severity: IssueSeverity) -> str:
        """Get emoji for severity level"""
        emojis = {
            IssueSeverity.CRITICAL: "🔴",
            IssueSeverity.HIGH: "🟠",
            IssueSeverity.MEDIUM: "🟡",
            IssueSeverity.LOW: "🟢",
            IssueSeverity.INFO: "🔵"
        }
        return emojis.get(severity, "⚪")
    
    def _get_grade_emoji(self, score: Optional[int]) -> str:
        """Get grade emoji based on score"""
        if score is None:
            return "❓"
        elif score >= 90:
            return "🟢"
        elif score >= 75:
            return "🟡"
        elif score >= 50:
            return "🟠"
        else:
            return "🔴"
    
    def _get_cwv_status(self, metric: str, value: Optional[float]) -> str:
        """Get Core Web Vitals status"""
        if value is None:
            return "❓ Unknown"
        
        thresholds = {
            'lcp': {'good': 2500, 'needs_improvement': 4000},
            'fid': {'good': 100, 'needs_improvement': 300},
            'cls': {'good': 0.1, 'needs_improvement': 0.25}
        }
        
        if metric in thresholds:
            t = thresholds[metric]
            if value <= t['good']:
                return "🟢 Good"
            elif value <= t['needs_improvement']:
                return "🟡 Needs Improvement"
            else:
                return "🔴 Poor"
        
        return "❓ Unknown"
    
    def _is_outdated_version(self, tech: Dict[str, Any]) -> bool:
        """Check if technology version is outdated (simplified)"""
        # This would need a real version database in production
        outdated_patterns = {
            'WordPress': ['4.', '3.'],
            'jQuery': ['1.', '2.0', '2.1'],
            'PHP': ['5.', '7.0', '7.1', '7.2'],
            'Angular': ['1.', '2.', '3.', '4.', '5.', '6.', '7.', '8.']
        }
        
        tech_name = tech.get('technology_name', '')
        version = tech.get('version', '')
        
        if tech_name in outdated_patterns and version:
            for pattern in outdated_patterns[tech_name]:
                if version.startswith(pattern):
                    return True
        
        return False
    
    def create_summary_report(
        self,
        results: List[CoordinatorResult],
        format_type: ReportFormat = ReportFormat.TEXT
    ) -> str:
        """Create summary report for multiple assessments"""
        if format_type == ReportFormat.JSON:
            summary_data = {
                "total_assessments": len(results),
                "total_cost_usd": str(sum(r.total_cost_usd for r in results)),
                "average_duration_seconds": sum(r.execution_time_ms for r in results) / len(results) / 1000,
                "assessments": [
                    {
                        "session_id": r.session_id,
                        "business_id": r.business_id,
                        "success_rate": r.completed_assessments / r.total_assessments if r.total_assessments > 0 else 0,
                        "cost_usd": str(r.total_cost_usd)
                    }
                    for r in results
                ]
            }
            return json.dumps(summary_data, indent=2)
        else:
            # Simple text summary
            lines = [
                "ASSESSMENT BATCH SUMMARY",
                "=" * 40,
                f"Total Assessments: {len(results)}",
                f"Total Cost: ${sum(r.total_cost_usd for r in results)}",
                f"Average Duration: {sum(r.execution_time_ms for r in results) / len(results) / 1000:.2f}s",
                "",
                "Individual Results:"
            ]
            
            for r in results:
                success_rate = r.completed_assessments / r.total_assessments if r.total_assessments > 0 else 0
                lines.append(f"  - {r.session_id}: {success_rate*100:.0f}% success (${r.total_cost_usd})")
            
            return "\n".join(lines)