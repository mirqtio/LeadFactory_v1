"""Email builder for audit report teasers."""
from typing import Dict, List, Optional, Tuple
from d3_assessment.audit_schema import AuditFinding, FindingSeverity, FindingCategory


def select_email_findings(
    findings: List[AuditFinding], has_gbp: bool = True
) -> Dict[str, any]:
    """
    Select findings for email teaser based on strategy.

    Strategy:
    1. If GBP issue exists (missing/weak), show as free quick win
    2. Select highest impact finding as hook
    3. Optionally show one more critical finding

    Args:
        findings: List of audit findings
        has_gbp: Whether business has Google Business Profile

    Returns:
        Dict with selected findings and metadata
    """

    # Sort findings by impact (conversion_impact * severity)
    def impact_score(f: AuditFinding) -> float:
        severity_weight = {
            FindingSeverity.CRITICAL: 4,
            FindingSeverity.HIGH: 3,
            FindingSeverity.MEDIUM: 2,
            FindingSeverity.LOW: 1,
        }
        return f.conversion_impact * severity_weight.get(f.severity, 1)

    sorted_findings = sorted(findings, key=impact_score, reverse=True)

    result = {
        "has_gbp_issue": False,
        "gbp_issue": None,
        "hook_issue": None,
        "additional_issue": None,
        "total_issues": len(findings),
    }

    # Check for GBP issues
    gbp_findings = [
        f
        for f in findings
        if f.category == FindingCategory.TRUST
        and ("gbp" in f.issue_id.lower() or "google" in f.title.lower())
    ]

    if gbp_findings and not has_gbp:
        result["has_gbp_issue"] = True
        result["gbp_issue"] = gbp_findings[0]
        result["gbp_issue_description"] = _simplify_description(
            gbp_findings[0].description
        )
        result["gbp_impact"] = int(gbp_findings[0].conversion_impact * 100)

        # Remove GBP from main findings list for hook selection
        sorted_findings = [f for f in sorted_findings if f not in gbp_findings]

    # Select hook issue (highest impact non-GBP)
    if sorted_findings:
        hook = sorted_findings[0]
        result["hook_issue"] = hook
        result["hook_issue_title"] = hook.title
        result["hook_issue_description"] = _simplify_description(hook.description)
        result["hook_complexity"] = _format_complexity(hook.effort_estimate)

        # Calculate revenue range
        low, high = _calculate_revenue_range(hook)
        result["hook_impact_low"] = low
        result["hook_impact_high"] = high

    # Select additional issue if high severity
    remaining = sorted_findings[1:] if len(sorted_findings) > 1 else []
    critical_remaining = [
        f
        for f in remaining
        if f.severity in [FindingSeverity.CRITICAL, FindingSeverity.HIGH]
    ]

    if critical_remaining:
        result["additional_issue"] = critical_remaining[0]
        result["additional_issue_title"] = critical_remaining[0].title
        result["additional_issue_description"] = _simplify_description(
            critical_remaining[0].description
        )

    return result


def _simplify_description(description: str) -> str:
    """Simplify technical descriptions for email."""
    # Remove technical jargon and links
    simplified = description.replace("[Learn more]", "")
    simplified = simplified.replace("(https://", "(")

    # Truncate at first period if too long
    if len(simplified) > 150 and "." in simplified:
        simplified = simplified.split(".")[0] + "."

    return simplified.strip()


def _format_complexity(effort: str) -> str:
    """Format effort estimate as complexity label."""
    mapping = {
        "easy": "Low",
        "moderate": "Medium",
        "hard": "High",
        "very_hard": "Very High",
    }
    return mapping.get(effort.lower(), "Medium")


def _calculate_revenue_range(
    finding: AuditFinding, base_revenue: float = 1_000_000
) -> Tuple[int, int]:
    """
    Calculate revenue impact range based on finding.

    Returns low and high estimates.
    """
    base_impact = finding.conversion_impact * base_revenue

    # Wider range for lower confidence findings
    if finding.category == FindingCategory.VISUAL:
        low = int(base_impact * 0.7)
        high = int(base_impact * 1.3)
    else:
        low = int(base_impact * 0.85)
        high = int(base_impact * 1.15)

    # Round to nearest $500
    low = (low // 500) * 500
    high = ((high + 499) // 500) * 500

    return (low, high)


def prepare_email_context(
    business_name: str,
    overall_score: int,
    findings: List[AuditFinding],
    revenue_estimate: float = 1_000_000,
    contact_name: Optional[str] = None,
) -> Dict[str, any]:
    """
    Prepare complete context for email template.

    Args:
        business_name: Name of the business
        overall_score: Overall performance score (0-100)
        findings: List of audit findings
        revenue_estimate: Estimated annual revenue
        contact_name: Contact person's name (optional)

    Returns:
        Dict with all template variables
    """
    # Check if business has GBP based on findings
    has_gbp = not any(
        f.category == FindingCategory.TRUST
        and ("gbp" in f.issue_id.lower() or "google" in f.title.lower())
        for f in findings
    )

    # Select findings
    selected = select_email_findings(findings, has_gbp=has_gbp)

    # Calculate total revenue impact range
    total_impact = sum(f.conversion_impact for f in findings)
    total_low = int(total_impact * revenue_estimate * 0.7)
    total_high = int(total_impact * revenue_estimate * 1.3)

    # Round to nearest $1000
    total_low = (total_low // 1000) * 1000
    total_high = ((total_high + 999) // 1000) * 1000

    # Determine score class
    if overall_score >= 80:
        score_class = "score-high"
    elif overall_score >= 50:
        score_class = "score-medium"
    else:
        score_class = "score-low"

    context = {
        "business_name": business_name,
        "contact_name": contact_name,
        "overall_score": overall_score,
        "score_class": score_class,
        "revenue_impact_low": total_low,
        "revenue_impact_high": total_high,
        "total_issues": selected["total_issues"],
        "report_price": 97,  # Can be dynamic based on tier
        "support_phone": "1-800-LEADFAC",
        "company_name": "LeadFactory",
        "current_year": 2024,
        # Finding-specific
        "has_gbp_issue": selected["has_gbp_issue"],
    }

    # Add GBP issue details if present
    if selected["has_gbp_issue"]:
        context.update(
            {
                "gbp_issue_description": selected["gbp_issue_description"],
                "gbp_impact": selected["gbp_impact"],
            }
        )

    # Add hook issue details
    if selected["hook_issue"]:
        context.update(
            {
                "hook_issue_title": selected["hook_issue_title"],
                "hook_issue_description": selected["hook_issue_description"],
                "hook_impact_low": selected["hook_impact_low"],
                "hook_impact_high": selected["hook_impact_high"],
                "hook_complexity": selected["hook_complexity"],
            }
        )

    # Add additional issue if present
    if selected["additional_issue"]:
        context.update(
            {
                "additional_issue": True,
                "additional_issue_title": selected["additional_issue_title"],
                "additional_issue_description": selected[
                    "additional_issue_description"
                ],
            }
        )

    return context
