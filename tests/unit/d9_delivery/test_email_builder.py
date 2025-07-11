"""Unit tests for email builder."""
import pytest

# Mark entire module as slow for CI optimization
pytestmark = pytest.mark.slow
from d9_delivery.email_builder import (
    select_email_findings,
    prepare_email_context,
    _calculate_revenue_range,
)
from d3_assessment.audit_schema import (
    AuditFinding,
    FindingSeverity,
    FindingCategory,
)


def create_test_finding(
    issue_id: str,
    title: str,
    severity: FindingSeverity,
    category: FindingCategory,
    conversion_impact: float = 0.02,
    effort: str = "moderate",
) -> AuditFinding:
    """Helper to create test findings."""
    return AuditFinding(
        issue_id=issue_id,
        title=title,
        description=f"Description for {title}. [Learn more](https://example.com)",
        severity=severity,
        category=category,
        evidence=[],
        conversion_impact=conversion_impact,
        effort_estimate=effort,
    )


def test_select_email_findings_with_gbp():
    """Test finding selection with GBP issue."""
    findings = [
        create_test_finding(
            "no_gbp_profile",
            "No Google Business Profile Found",
            FindingSeverity.HIGH,
            FindingCategory.TRUST,
            0.035,
        ),
        create_test_finding(
            "slow_page_load",
            "Page Load Time Too Slow",
            FindingSeverity.CRITICAL,
            FindingCategory.PERFORMANCE,
            0.04,
        ),
        create_test_finding(
            "missing_h1",
            "Missing H1 Tag",
            FindingSeverity.MEDIUM,
            FindingCategory.SEO,
            0.01,
        ),
    ]

    result = select_email_findings(findings, has_gbp=False)

    assert result["has_gbp_issue"] is True
    assert result["gbp_issue"].issue_id == "no_gbp_profile"
    assert result["gbp_impact"] == 3  # 0.035 * 100
    assert result["hook_issue"].issue_id == "slow_page_load"
    assert result["additional_issue"] is None  # Only one critical


def test_select_email_findings_no_gbp():
    """Test finding selection without GBP issue."""
    findings = [
        create_test_finding(
            "slow_page_load",
            "Page Load Time Too Slow",
            FindingSeverity.CRITICAL,
            FindingCategory.PERFORMANCE,
            0.04,
        ),
        create_test_finding(
            "cta_below_fold",
            "CTA Below the Fold",
            FindingSeverity.HIGH,
            FindingCategory.VISUAL,
            0.03,
        ),
        create_test_finding(
            "missing_alt_text",
            "Missing Alt Text",
            FindingSeverity.LOW,
            FindingCategory.SEO,
            0.005,
        ),
    ]

    result = select_email_findings(findings, has_gbp=True)

    assert result["has_gbp_issue"] is False
    assert result["hook_issue"].issue_id == "slow_page_load"
    assert result["additional_issue"].issue_id == "cta_below_fold"


def test_revenue_range_calculation():
    """Test revenue range calculation with confidence adjustment."""
    # Visual finding - wider range
    visual_finding = create_test_finding(
        "visual_issue",
        "Visual Issue",
        FindingSeverity.HIGH,
        FindingCategory.VISUAL,
        0.02,
    )

    low, high = _calculate_revenue_range(visual_finding, 1_000_000)

    # 0.02 * 1M = 20k base
    # Visual: 70-130% range
    assert low == 14000  # 20k * 0.7 = 14k
    assert high == 26000  # 20k * 1.3 = 26k

    # Non-visual finding - tighter range
    perf_finding = create_test_finding(
        "perf_issue",
        "Performance Issue",
        FindingSeverity.HIGH,
        FindingCategory.PERFORMANCE,
        0.02,
    )

    low, high = _calculate_revenue_range(perf_finding, 1_000_000)

    # 85-115% range
    assert low == 17000  # 20k * 0.85 = 17k
    assert high == 23000  # 20k * 1.15 = 23k


def test_prepare_email_context():
    """Test complete email context preparation."""
    findings = [
        create_test_finding(
            "no_gbp_profile",
            "No Google Business Profile Found",
            FindingSeverity.HIGH,
            FindingCategory.TRUST,
            0.035,
            "easy",
        ),
        create_test_finding(
            "slow_page_load",
            "Page Load Time Too Slow",
            FindingSeverity.CRITICAL,
            FindingCategory.PERFORMANCE,
            0.04,
            "moderate",
        ),
    ]

    context = prepare_email_context(
        business_name="Test Business",
        overall_score=45,
        findings=findings,
        revenue_estimate=2_000_000,
        contact_name="John Doe",
    )

    # Basic context
    assert context["business_name"] == "Test Business"
    assert context["contact_name"] == "John Doe"
    assert context["overall_score"] == 45
    assert context["score_class"] == "score-low"  # < 50

    # Revenue impact range (total impact: 0.035 + 0.04 = 0.075)
    # 0.075 * 2M = 150k base
    assert context["revenue_impact_low"] == 105000  # 150k * 0.7
    assert context["revenue_impact_high"] == 195000  # 150k * 1.3

    # GBP issue
    assert context["has_gbp_issue"] is True
    assert context["gbp_impact"] == 3

    # Hook issue
    assert context["hook_issue_title"] == "Page Load Time Too Slow"
    assert context["hook_complexity"] == "Medium"  # moderate -> Medium

    # No link in simplified description
    assert "[Learn more]" not in context["hook_issue_description"]


def test_complexity_formatting():
    """Test effort estimate formatting."""
    findings = [
        create_test_finding(
            "test1", "Test 1", FindingSeverity.HIGH, FindingCategory.SEO, 0.01, "easy"
        ),
        create_test_finding(
            "test2", "Test 2", FindingSeverity.HIGH, FindingCategory.SEO, 0.01, "hard"
        ),
    ]

    result = select_email_findings(findings)

    # First finding is hook
    assert result["hook_complexity"] == "Low"  # easy -> Low


def test_jinja_render_compatibility():
    """Test that context works with Jinja2 templates."""
    from jinja2 import Template

    # Minimal test template
    template = Template(
        """
    {% if has_gbp_issue %}
    GBP Issue: {{ gbp_issue_description }} ({{ gbp_impact }}% impact)
    {% endif %}
    Hook: {{ hook_issue_title }} - ${{ hook_impact_low }}-${{ hook_impact_high }}
    """
    )

    findings = [
        create_test_finding(
            "no_gbp_profile",
            "No Google Business Profile Found",
            FindingSeverity.HIGH,
            FindingCategory.TRUST,
            0.035,
        ),
        create_test_finding(
            "slow_page_load",
            "Page Load Time Too Slow",
            FindingSeverity.CRITICAL,
            FindingCategory.PERFORMANCE,
            0.04,
        ),
    ]

    context = prepare_email_context(
        business_name="Test", overall_score=50, findings=findings
    )

    rendered = template.render(**context)

    assert "GBP Issue:" in rendered
    assert "3% impact" in rendered
    assert "Page Load Time Too Slow" in rendered
    assert "$34000-$46000" in rendered  # Approximate values
