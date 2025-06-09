"""
Test Assessment Reports Formatter - Task 038

Comprehensive tests for assessment report formatting functionality.
Tests all acceptance criteria:
- Human-readable summaries
- JSON export works
- Issue prioritization
- Markdown formatting
"""
import pytest
import json
from datetime import datetime, timedelta
from decimal import Decimal
import uuid

import sys
sys.path.insert(0, '/app')  # noqa: E402

from d3_assessment.formatter import (  # noqa: E402
    AssessmentReportFormatter, ReportFormat, IssueSeverity
)
from d3_assessment.coordinator import CoordinatorResult  # noqa: E402
from d3_assessment.models import AssessmentResult  # noqa: E402
from d3_assessment.types import AssessmentType, AssessmentStatus  # noqa: E402


class TestTask038AcceptanceCriteria:
    """Test that Task 038 meets all acceptance criteria"""

    @pytest.fixture
    def formatter(self):
        """Create formatter instance for testing"""
        return AssessmentReportFormatter()

    @pytest.fixture
    def sample_coordinator_result(self):
        """Create sample coordinator result with various assessment types"""
        return CoordinatorResult(
            session_id="sess_test123456",
            business_id="biz_test123",
            total_assessments=3,
            completed_assessments=3,
            failed_assessments=0,
            partial_results={
                AssessmentType.PAGESPEED: AssessmentResult(
                    id=str(uuid.uuid4()),
                    business_id="biz_test123",
                    session_id="sess_test123456",
                    assessment_type=AssessmentType.PAGESPEED,
                    status=AssessmentStatus.COMPLETED,
                    url="https://example-store.com",
                    domain="example-store.com",
                    performance_score=45,  # Poor performance for testing
                    accessibility_score=65,  # Low accessibility
                    seo_score=88,
                    best_practices_score=92,
                    largest_contentful_paint=5500,  # Poor LCP
                    first_input_delay=120,
                    cumulative_layout_shift=0.08,
                    speed_index=4200,
                    time_to_interactive=6000,
                    total_blocking_time=450,
                    pagespeed_data={
                        "lighthouseResult": {
                            "audits": {
                                "unused-css-rules": {
                                    "title": "Remove unused CSS",
                                    "score": 0.3
                                }
                            }
                        }
                    }
                ),
                AssessmentType.TECH_STACK: AssessmentResult(
                    id=str(uuid.uuid4()),
                    business_id="biz_test123",
                    session_id="sess_test123456",
                    assessment_type=AssessmentType.TECH_STACK,
                    status=AssessmentStatus.COMPLETED,
                    url="https://example-store.com",
                    domain="example-store.com",
                    tech_stack_data={
                        "technologies": [
                            {
                                "technology_name": "WordPress",
                                "category": "CMS",
                                "confidence": 0.95,
                                "version": "4.9.8"  # Outdated version
                            },
                            {
                                "technology_name": "WooCommerce",
                                "category": "E-commerce",
                                "confidence": 0.90,
                                "version": "3.5.0"
                            },
                            {
                                "technology_name": "jQuery",
                                "category": "JavaScript Libraries",
                                "confidence": 0.99,
                                "version": "1.12.4"  # Outdated
                            },
                            {
                                "technology_name": "Google Analytics",
                                "category": "Analytics",
                                "confidence": 0.85
                            }
                        ]
                    }
                ),
                AssessmentType.AI_INSIGHTS: AssessmentResult(
                    id=str(uuid.uuid4()),
                    business_id="biz_test123",
                    session_id="sess_test123456",
                    assessment_type=AssessmentType.AI_INSIGHTS,
                    status=AssessmentStatus.COMPLETED,
                    url="https://example-store.com",
                    domain="example-store.com",
                    ai_insights_data={
                        "insights": {
                            "recommendations": [
                                {
                                    "title": "Optimize Image Loading",
                                    "description": "Implement lazy loading and WebP format",
                                    "priority": "High",
                                    "effort": "Medium",
                                    "impact": "Reduce LCP by 30-40%"
                                },
                                {
                                    "title": "Enable Text Compression",
                                    "description": "Enable Gzip or Brotli compression",
                                    "priority": "Medium",
                                    "effort": "Low",
                                    "impact": "Reduce file sizes by 60-80%"
                                },
                                {
                                    "title": "Minimize JavaScript",
                                    "description": "Reduce and defer JavaScript execution",
                                    "priority": "High",
                                    "effort": "High",
                                    "impact": "Improve FID and TTI"
                                }
                            ],
                            "industry_insights": {
                                "industry": "ecommerce",
                                "benchmarks": {
                                    "performance_percentile": "Bottom 25%",
                                    "key_metrics": "Focus on conversion-critical metrics"
                                }
                            },
                            "summary": {
                                "overall_health": "Poor performance affecting user experience",
                                "quick_wins": "Enable compression and optimize images"
                            }
                        },
                        "total_cost_usd": 0.35,
                        "model_version": "gpt-4-0125-preview"
                    },
                    total_cost_usd=Decimal("0.35")
                )
            },
            errors={},
            total_cost_usd=Decimal("0.50"),
            execution_time_ms=150000,
            started_at=datetime.utcnow() - timedelta(minutes=3),
            completed_at=datetime.utcnow()
        )

    @pytest.fixture
    def failed_coordinator_result(self):
        """Create coordinator result with failures"""
        return CoordinatorResult(
            session_id="sess_failed123",
            business_id="biz_test123",
            total_assessments=3,
            completed_assessments=1,
            failed_assessments=2,
            partial_results={
                AssessmentType.PAGESPEED: AssessmentResult(
                    id=str(uuid.uuid4()),
                    business_id="biz_test123",
                    session_id="sess_failed123",
                    assessment_type=AssessmentType.PAGESPEED,
                    status=AssessmentStatus.COMPLETED,
                    url="https://example.com",
                    domain="example.com",
                    performance_score=75,
                    accessibility_score=85,
                    seo_score=90
                )
            },
            errors={
                AssessmentType.TECH_STACK: "Connection timeout",
                AssessmentType.AI_INSIGHTS: "API rate limit exceeded"
            },
            total_cost_usd=Decimal("0.10"),
            execution_time_ms=60000,
            started_at=datetime.utcnow() - timedelta(minutes=1),
            completed_at=datetime.utcnow()
        )

    def test_human_readable_summaries(self, formatter, sample_coordinator_result):
        """
        Test that human-readable summaries are generated correctly
        
        Acceptance Criteria: Human-readable summaries
        """
        text_report = formatter.format_report(sample_coordinator_result, ReportFormat.TEXT)
        
        # Verify report structure
        assert "WEBSITE ASSESSMENT REPORT" in text_report
        assert "Session ID: sess_test123456" in text_report
        assert "Business ID: biz_test123" in text_report
        assert "Total Cost: $0.50" in text_report
        
        # Verify summary section
        assert "SUMMARY" in text_report
        assert "Total Assessments: 3" in text_report
        assert "Completed: 3" in text_report
        assert "Failed: 0" in text_report
        
        # Verify issues section
        assert "PRIORITIZED ISSUES" in text_report
        assert "CRITICAL" in text_report  # Should have critical issues due to poor performance
        assert "Poor Performance Score (45/100)" in text_report
        
        # Verify assessment results
        assert "ASSESSMENT RESULTS" in text_report
        assert "PageSpeed Insights:" in text_report
        assert "Performance Score: 45/100" in text_report
        assert "Accessibility Score: 65/100" in text_report
        assert "LCP: 5500ms" in text_report
        
        # Verify tech stack
        assert "Technology Stack:" in text_report
        assert "WordPress" in text_report
        assert "jQuery" in text_report
        
        # Verify AI recommendations
        assert "AI Recommendations:" in text_report
        assert "Optimize Image Loading" in text_report
        
        print("✓ Human-readable summaries generated correctly")

    def test_json_export_works(self, formatter, sample_coordinator_result):
        """
        Test that JSON export works correctly
        
        Acceptance Criteria: JSON export works
        """
        json_report = formatter.format_report(sample_coordinator_result, ReportFormat.JSON)
        
        # Verify valid JSON
        try:
            data = json.loads(json_report)
        except json.JSONDecodeError:
            pytest.fail("Invalid JSON output")
        
        # Verify JSON structure
        assert "metadata" in data
        assert data["metadata"]["session_id"] == "sess_test123456"
        assert data["metadata"]["business_id"] == "biz_test123"
        assert data["metadata"]["total_cost_usd"] == "0.50"
        
        assert "summary" in data
        assert data["summary"]["total_assessments"] == 3
        assert data["summary"]["completed_assessments"] == 3
        assert data["summary"]["success_rate"] == 1.0
        
        assert "prioritized_issues" in data
        assert isinstance(data["prioritized_issues"], list)
        assert len(data["prioritized_issues"]) > 0
        
        assert "results" in data
        assert "pagespeed" in data["results"]
        assert "tech_stack" in data["results"]
        assert "ai_insights" in data["results"]
        
        # Verify PageSpeed data
        ps_data = data["results"]["pagespeed"]
        assert ps_data["scores"]["performance"] == 45
        assert ps_data["core_web_vitals"]["lcp"] == 5500
        
        # Verify Tech Stack data
        ts_data = data["results"]["tech_stack"]
        assert len(ts_data["technologies"]) == 4
        assert ts_data["technologies"][0]["technology_name"] == "WordPress"
        
        # Verify AI Insights data
        ai_data = data["results"]["ai_insights"]
        assert len(ai_data["insights"]["recommendations"]) == 3
        assert ai_data["cost_usd"] == "0.35"
        
        # Test with raw data included
        json_with_raw = formatter.format_report(
            sample_coordinator_result, ReportFormat.JSON, include_raw_data=True
        )
        data_with_raw = json.loads(json_with_raw)
        assert "raw_data" in data_with_raw["results"]["pagespeed"]
        
        print("✓ JSON export works correctly")

    def test_issue_prioritization(self, formatter, sample_coordinator_result):
        """
        Test that issue prioritization works correctly
        
        Acceptance Criteria: Issue prioritization
        """
        # Extract issues
        issues = formatter._extract_and_prioritize_issues(sample_coordinator_result)
        
        # Verify issues were extracted
        assert len(issues) > 0
        
        # Verify critical performance issue is present
        performance_issues = [i for i in issues if i['category'] == 'performance']
        assert len(performance_issues) > 0
        assert performance_issues[0]['severity'] == IssueSeverity.CRITICAL
        assert "Poor Performance Score" in performance_issues[0]['title']
        
        # Verify LCP issue
        cwv_issues = [i for i in issues if i['category'] == 'core_web_vitals']
        assert len(cwv_issues) > 0
        assert cwv_issues[0]['severity'] == IssueSeverity.HIGH
        assert "Slow Largest Contentful Paint" in cwv_issues[0]['title']
        
        # Verify accessibility issue
        a11y_issues = [i for i in issues if i['category'] == 'accessibility']
        assert len(a11y_issues) > 0
        assert a11y_issues[0]['severity'] == IssueSeverity.HIGH
        
        # Verify outdated technology issues
        security_issues = [i for i in issues if i['category'] == 'security']
        assert len(security_issues) >= 2  # WordPress and jQuery are outdated
        
        # Verify issues are properly prioritized
        # Critical issues should come first
        critical_count = len([i for i in issues[:2] if i['severity'] == IssueSeverity.CRITICAL])
        assert critical_count > 0, "Critical issues should be prioritized first"
        
        # Verify all issues have required fields
        for issue in issues:
            assert 'severity' in issue
            assert 'category' in issue
            assert 'title' in issue
            assert 'description' in issue
            assert 'recommendation' in issue
        
        print("✓ Issue prioritization works correctly")

    def test_markdown_formatting(self, formatter, sample_coordinator_result):
        """
        Test that Markdown formatting works correctly
        
        Acceptance Criteria: Markdown formatting
        """
        markdown_report = formatter.format_report(sample_coordinator_result, ReportFormat.MARKDOWN)
        
        # Verify Markdown structure
        assert "# Website Assessment Report" in markdown_report
        assert "## Report Information" in markdown_report
        assert "## Summary" in markdown_report
        assert "## Prioritized Issues" in markdown_report
        assert "## Assessment Results" in markdown_report
        
        # Verify Markdown formatting elements
        assert "- **Session ID**: `sess_test123456`" in markdown_report
        assert "| Metric | Value |" in markdown_report  # Table header
        assert "|--------|-------|" in markdown_report  # Table separator
        
        # Verify emoji usage
        assert "🔴" in markdown_report  # Critical/Poor emoji
        assert "🟠" in markdown_report  # High/Warning emoji
        
        # Verify PageSpeed section
        assert "### PageSpeed Insights" in markdown_report
        assert "#### Scores" in markdown_report
        assert "| Performance | 45/100 | 🔴 |" in markdown_report
        
        # Verify Core Web Vitals table
        assert "#### Core Web Vitals" in markdown_report
        assert "| LCP | 5500ms | 🔴 Poor |" in markdown_report
        
        # Verify Tech Stack section
        assert "### Technology Stack" in markdown_report
        assert "**CMS**:" in markdown_report
        assert "- WordPress v4.9.8 (95% confidence)" in markdown_report
        
        # Verify AI Insights section
        assert "### AI-Generated Insights" in markdown_report
        assert "#### 1. Optimize Image Loading" in markdown_report
        assert "**Priority**: High" in markdown_report
        assert "**Effort**: Medium" in markdown_report
        
        print("✓ Markdown formatting works correctly")

    def test_failed_assessments_reporting(self, formatter, failed_coordinator_result):
        """Test reporting of failed assessments"""
        # Test text format
        text_report = formatter.format_report(failed_coordinator_result, ReportFormat.TEXT)
        assert "Failed: 2" in text_report
        assert "Failed Assessments:" in text_report
        assert "tech_stack: Connection timeout" in text_report
        assert "ai_insights: API rate limit exceeded" in text_report
        
        # Test JSON format
        json_report = formatter.format_report(failed_coordinator_result, ReportFormat.JSON)
        data = json.loads(json_report)
        assert data["summary"]["failed_assessments"] == 2
        assert data["errors"]["tech_stack"] == "Connection timeout"
        assert data["errors"]["ai_insights"] == "API rate limit exceeded"
        
        # Test Markdown format
        markdown_report = formatter.format_report(failed_coordinator_result, ReportFormat.MARKDOWN)
        assert "| Failed | 2 |" in markdown_report
        
        print("✓ Failed assessments reporting works correctly")

    def test_html_format(self, formatter, sample_coordinator_result):
        """Test HTML report generation"""
        html_report = formatter.format_report(sample_coordinator_result, ReportFormat.HTML)
        
        # Verify HTML structure
        assert "<!DOCTYPE html>" in html_report
        assert "<html>" in html_report
        assert "<title>Assessment Report - sess_test123456</title>" in html_report
        assert "<style>" in html_report
        assert "body { font-family: Arial" in html_report
        
        # Verify CSS classes for severity
        assert ".critical { color: #d32f2f; }" in html_report
        assert ".high { color: #f57c00; }" in html_report
        
        print("✓ HTML format works correctly")

    def test_severity_weighting(self, formatter):
        """Test severity weight system"""
        assert formatter.severity_weights[IssueSeverity.CRITICAL] == 100
        assert formatter.severity_weights[IssueSeverity.HIGH] == 75
        assert formatter.severity_weights[IssueSeverity.MEDIUM] == 50
        assert formatter.severity_weights[IssueSeverity.LOW] == 25
        assert formatter.severity_weights[IssueSeverity.INFO] == 10
        
        print("✓ Severity weighting system works correctly")

    def test_outdated_technology_detection(self, formatter):
        """Test detection of outdated technologies"""
        # Test outdated WordPress
        assert formatter._is_outdated_version({
            'technology_name': 'WordPress',
            'version': '4.9.8'
        }) is True
        
        # Test current WordPress
        assert formatter._is_outdated_version({
            'technology_name': 'WordPress',
            'version': '6.0.0'
        }) is False
        
        # Test outdated jQuery
        assert formatter._is_outdated_version({
            'technology_name': 'jQuery',
            'version': '1.12.4'
        }) is True
        
        # Test current jQuery
        assert formatter._is_outdated_version({
            'technology_name': 'jQuery',
            'version': '3.6.0'
        }) is False
        
        print("✓ Outdated technology detection works correctly")

    def test_summary_report(self, formatter, sample_coordinator_result):
        """Test summary report for multiple assessments"""
        results = [sample_coordinator_result, sample_coordinator_result]
        
        # Test text summary
        text_summary = formatter.create_summary_report(results, ReportFormat.TEXT)
        assert "ASSESSMENT BATCH SUMMARY" in text_summary
        assert "Total Assessments: 2" in text_summary
        assert "Total Cost: $1.00" in text_summary  # 0.50 * 2
        assert "Average Duration: 150.00s" in text_summary
        
        # Test JSON summary
        json_summary = formatter.create_summary_report(results, ReportFormat.JSON)
        data = json.loads(json_summary)
        assert data["total_assessments"] == 2
        assert data["total_cost_usd"] == "1.00"
        assert len(data["assessments"]) == 2
        
        print("✓ Summary report generation works correctly")

    def test_grade_and_status_helpers(self, formatter):
        """Test helper methods for grades and status"""
        # Test grade emoji
        assert formatter._get_grade_emoji(95) == "🟢"
        assert formatter._get_grade_emoji(80) == "🟡"
        assert formatter._get_grade_emoji(60) == "🟠"
        assert formatter._get_grade_emoji(40) == "🔴"
        assert formatter._get_grade_emoji(None) == "❓"
        
        # Test CWV status
        assert formatter._get_cwv_status('lcp', 2000) == "🟢 Good"
        assert formatter._get_cwv_status('lcp', 3000) == "🟡 Needs Improvement"
        assert formatter._get_cwv_status('lcp', 5000) == "🔴 Poor"
        assert formatter._get_cwv_status('lcp', None) == "❓ Unknown"
        
        # Test severity emoji
        assert formatter._get_severity_emoji(IssueSeverity.CRITICAL) == "🔴"
        assert formatter._get_severity_emoji(IssueSeverity.HIGH) == "🟠"
        assert formatter._get_severity_emoji(IssueSeverity.MEDIUM) == "🟡"
        assert formatter._get_severity_emoji(IssueSeverity.LOW) == "🟢"
        assert formatter._get_severity_emoji(IssueSeverity.INFO) == "🔵"
        
        print("✓ Grade and status helpers work correctly")

    def test_comprehensive_formatting_flow(self, formatter, sample_coordinator_result):
        """Test comprehensive formatting workflow"""
        # Test all formats
        formats = [
            (ReportFormat.TEXT, "WEBSITE ASSESSMENT REPORT"),
            (ReportFormat.JSON, '"metadata"'),
            (ReportFormat.MARKDOWN, "# Website Assessment Report"),
            (ReportFormat.HTML, "<!DOCTYPE html>")
        ]
        
        for format_type, expected_content in formats:
            report = formatter.format_report(sample_coordinator_result, format_type)
            assert expected_content in report
            assert len(report) > 100  # Ensure substantial content
        
        # Test issue extraction
        issues = formatter._extract_and_prioritize_issues(sample_coordinator_result)
        assert len(issues) >= 4  # Should have multiple issues
        
        # Test technology grouping
        techs = sample_coordinator_result.partial_results[AssessmentType.TECH_STACK].tech_stack_data["technologies"]
        grouped = formatter._group_technologies_by_category(techs)
        assert "CMS" in grouped
        assert "JavaScript Libraries" in grouped
        assert len(grouped["CMS"]) == 1
        assert grouped["CMS"][0]["technology_name"] == "WordPress"
        
        print("✓ Comprehensive formatting flow works correctly")


# Allow running this test file directly
if __name__ == "__main__":
    import asyncio

    async def run_tests():
        test_instance = TestTask038AcceptanceCriteria()

        print("📝 Running Task 038 Assessment Formatter Tests...")
        print()

        try:
            # Create fixtures manually for direct execution
            formatter = AssessmentReportFormatter()
            
            sample_result = CoordinatorResult(
                session_id="sess_test123456",
                business_id="biz_test123",
                total_assessments=3,
                completed_assessments=3,
                failed_assessments=0,
                partial_results={
                    AssessmentType.PAGESPEED: AssessmentResult(
                        id=str(uuid.uuid4()),
                        business_id="biz_test123",
                        assessment_type=AssessmentType.PAGESPEED,
                        status=AssessmentStatus.COMPLETED,
                        url="https://example.com",
                        domain="example.com",
                        performance_score=45,
                        accessibility_score=65,
                        seo_score=88,
                        largest_contentful_paint=5500
                    )
                },
                errors={},
                total_cost_usd=Decimal("0.50"),
                execution_time_ms=150000,
                started_at=datetime.utcnow() - timedelta(minutes=3),
                completed_at=datetime.utcnow()
            )
            
            failed_result = CoordinatorResult(
                session_id="sess_failed123",
                business_id="biz_test123",
                total_assessments=3,
                completed_assessments=1,
                failed_assessments=2,
                partial_results={},
                errors={
                    AssessmentType.TECH_STACK: "Connection timeout"
                },
                total_cost_usd=Decimal("0.10"),
                execution_time_ms=60000,
                started_at=datetime.utcnow() - timedelta(minutes=1),
                completed_at=datetime.utcnow()
            )

            # Run all acceptance criteria tests
            test_instance.test_human_readable_summaries(formatter, test_instance.sample_coordinator_result())
            test_instance.test_json_export_works(formatter, test_instance.sample_coordinator_result())
            test_instance.test_issue_prioritization(formatter, test_instance.sample_coordinator_result())
            test_instance.test_markdown_formatting(formatter, test_instance.sample_coordinator_result())
            
            # Run additional functionality tests
            test_instance.test_failed_assessments_reporting(formatter, failed_result)
            test_instance.test_html_format(formatter, test_instance.sample_coordinator_result())
            test_instance.test_severity_weighting(formatter)
            test_instance.test_outdated_technology_detection(formatter)
            test_instance.test_summary_report(formatter, test_instance.sample_coordinator_result())
            test_instance.test_grade_and_status_helpers(formatter)
            test_instance.test_comprehensive_formatting_flow(formatter, test_instance.sample_coordinator_result())

            print()
            print("🎉 All Task 038 acceptance criteria tests pass!")
            print("   - Human-readable summaries: ✓")
            print("   - JSON export works: ✓")
            print("   - Issue prioritization: ✓")
            print("   - Markdown formatting: ✓")

        except Exception as e:
            print(f"❌ Test failed: {e}")
            import traceback
            traceback.print_exc()

    # Run async tests
    asyncio.run(run_tests())