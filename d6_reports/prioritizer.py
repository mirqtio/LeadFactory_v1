"""
D6 Reports Finding Prioritizer - Task 051

Intelligent prioritization of website assessment findings for conversion-optimized
audit reports. Selects top issues and quick wins for maximum impact.

Acceptance Criteria:
- Impact scoring works ✓
- Top 3 issues selected ✓
- Quick wins identified ✓
- Conversion focus ✓
"""

import logging
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

# Handle imports for different environments
try:
    from .finding_scorer import FindingScore, FindingScorer
except ImportError:
    try:
        from finding_scorer import FindingScore, FindingScorer
    except ImportError:
        import os
        import sys

        sys.path.insert(0, os.path.dirname(__file__))
        from finding_scorer import FindingScore, FindingScorer


logger = logging.getLogger(__name__)


@dataclass
class PrioritizationResult:
    """Result of finding prioritization process"""

    top_issues: List[FindingScore]
    quick_wins: List[FindingScore]
    all_findings: List[FindingScore]
    summary: Dict[str, Any]

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization"""
        return {
            "top_issues": [finding.to_dict() for finding in self.top_issues],
            "quick_wins": [finding.to_dict() for finding in self.quick_wins],
            "all_findings": [finding.to_dict() for finding in self.all_findings],
            "summary": self.summary,
        }


class FindingPrioritizer:
    """
    Prioritizes website assessment findings for conversion-optimized reports

    Acceptance Criteria: Top 3 issues selected, Quick wins identified, Conversion focus
    """

    def __init__(self, top_issues_count: int = 3, max_quick_wins: int = 5):
        """
        Initialize the finding prioritizer

        Args:
            top_issues_count: Number of top issues to select (default: 3)
            max_quick_wins: Maximum number of quick wins to identify
        """
        self.scorer = FindingScorer()
        self.top_issues_count = top_issues_count
        self.max_quick_wins = max_quick_wins

        logger.info(f"Initialized FindingPrioritizer with top_issues_count={top_issues_count}")

    def prioritize_findings(
        self,
        assessment_results: Dict[str, Any],
        business_context: Optional[Dict[str, Any]] = None,
    ) -> PrioritizationResult:
        """
        Prioritize findings from assessment results

        Acceptance Criteria: Impact scoring works, Top 3 issues selected, Quick wins identified

        Args:
            assessment_results: Assessment data with findings
            business_context: Optional business context for customization

        Returns:
            PrioritizationResult: Prioritized findings with top issues and quick wins
        """
        logger.info("Starting finding prioritization process")

        # Extract findings from assessment results
        findings = self._extract_findings(assessment_results)
        logger.info(f"Extracted {len(findings)} findings from assessment results")

        if not findings:
            logger.warning("No findings found in assessment results")
            return self._empty_result()

        # Apply business context if provided
        if business_context:
            findings = self._apply_business_context(findings, business_context)

        # Score all findings
        scored_findings = []
        for finding in findings:
            try:
                scored_finding = self.scorer.score_finding(finding)
                scored_findings.append(scored_finding)
            except Exception as e:
                logger.error(f"Failed to score finding {finding.get('id', 'unknown')}: {e}")
                continue

        logger.info(f"Successfully scored {len(scored_findings)} findings")

        if not scored_findings:
            logger.warning("No findings could be scored")
            return self._empty_result()

        # Sort by priority score (highest first)
        scored_findings.sort(key=lambda x: x.priority_score, reverse=True)

        # Select top issues
        top_issues = self._select_top_issues(scored_findings)

        # Identify quick wins
        quick_wins = self._identify_quick_wins(scored_findings)

        # Generate summary
        summary = self._generate_summary(scored_findings, top_issues, quick_wins)

        result = PrioritizationResult(
            top_issues=top_issues,
            quick_wins=quick_wins,
            all_findings=scored_findings,
            summary=summary,
        )

        logger.info(
            f"Prioritization complete: {len(top_issues)} top issues, " f"{len(quick_wins)} quick wins identified"
        )

        return result

    def _extract_findings(self, assessment_results: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Extract findings from various assessment result formats"""
        findings = []

        # Extract from PageSpeed insights
        pagespeed_data = assessment_results.get("pagespeed_data", {})
        if pagespeed_data:
            findings.extend(self._extract_pagespeed_findings(pagespeed_data))

        # Extract from AI insights
        ai_insights = assessment_results.get("ai_insights_data", {})
        if ai_insights:
            findings.extend(self._extract_ai_insights_findings(ai_insights))

        # Extract from tech stack analysis
        tech_stack = assessment_results.get("tech_stack_data", {})
        if tech_stack:
            findings.extend(self._extract_tech_stack_findings(tech_stack))

        # Extract from custom assessments
        custom_findings = assessment_results.get("findings", [])
        if custom_findings:
            findings.extend(custom_findings)

        return findings

    def _extract_pagespeed_findings(self, pagespeed_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Extract findings from PageSpeed Insights data"""
        findings = []

        lighthouse_result = pagespeed_data.get("lighthouseResult", {})
        audits = lighthouse_result.get("audits", {})

        for audit_id, audit_data in audits.items():
            if audit_data.get("score") is not None and audit_data.get("score") < 0.9:
                # This is a potential issue
                finding = {
                    "id": f"pagespeed_{audit_id}",
                    "title": audit_data.get("title", audit_id),
                    "category": self._categorize_pagespeed_audit(audit_id),
                    "severity": self._pagespeed_score_to_severity(audit_data.get("score", 1.0)),
                    "fix_type": self._pagespeed_audit_to_fix_type(audit_id),
                    "description": audit_data.get("description", ""),
                    "impact_factors": self._get_pagespeed_impact_factors(audit_id, audit_data),
                    "effort_factors": self._get_pagespeed_effort_factors(audit_id, audit_data),
                    "conversion_factors": self._get_pagespeed_conversion_factors(audit_id, audit_data),
                }
                findings.append(finding)

        return findings

    def _extract_ai_insights_findings(self, ai_insights: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Extract findings from AI insights data"""
        findings = []

        insights = ai_insights.get("insights", [])
        for i, insight in enumerate(insights):
            finding = {
                "id": f"ai_insight_{i}",
                "title": insight.get("title", f"AI Insight {i+1}"),
                "category": insight.get("category", "general"),
                "severity": insight.get("severity", "medium"),
                "fix_type": insight.get("fix_type", "css_changes"),
                "description": insight.get("description", ""),
                "impact_factors": insight.get("impact_factors", {}),
                "effort_factors": insight.get("effort_factors", {}),
                "conversion_factors": insight.get("conversion_factors", {}),
            }
            findings.append(finding)

        return findings

    def _extract_tech_stack_findings(self, tech_stack: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Extract findings from tech stack analysis"""
        findings = []

        # Look for missing or outdated technologies
        missing_analytics = tech_stack.get("missing_analytics", [])
        for analytics in missing_analytics:
            finding = {
                "id": f"missing_{analytics}",
                "title": f"Missing {analytics.title()} Analytics",
                "category": "analytics",
                "severity": "medium",
                "fix_type": "third_party_integration",
                "description": f"Website is missing {analytics} tracking",
                "impact_factors": {"affects_conversion_tracking": True},
                "effort_factors": {"requires_third_party": True},
                "conversion_factors": {"affects_lead_generation": True},
            }
            findings.append(finding)

        # Check for outdated technologies
        outdated_tech = tech_stack.get("outdated_technologies", [])
        for tech in outdated_tech:
            finding = {
                "id": f"outdated_{tech['name']}",
                "title": f"Outdated {tech['name']}",
                "category": "security",
                "severity": "high" if tech.get("security_risk", False) else "medium",
                "fix_type": "server_config",
                "description": f"{tech['name']} version is outdated",
                "impact_factors": {"security_risk": tech.get("security_risk", False)},
                "effort_factors": {"requires_developer": True},
                "conversion_factors": {"trust_issue": tech.get("security_risk", False)},
            }
            findings.append(finding)

        return findings

    def _apply_business_context(
        self, findings: List[Dict[str, Any]], business_context: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Apply business context to adjust finding priorities"""
        business_type = business_context.get("business_type", "general")
        industry = business_context.get("industry", "general")

        # Adjust conversion factors based on business type
        for finding in findings:
            conversion_factors = finding.get("conversion_factors", {})

            # E-commerce businesses prioritize checkout and forms
            if business_type == "ecommerce":
                if finding.get("category") in ["checkout", "forms", "payment"]:
                    conversion_factors["blocks_purchase"] = True
                    conversion_factors["critical_for_revenue"] = True

            # Service businesses prioritize lead generation
            elif business_type == "service":
                if finding.get("category") in ["forms", "cta", "contact"]:
                    conversion_factors["affects_lead_generation"] = True
                    conversion_factors["critical_for_leads"] = True

            # SaaS businesses prioritize signup flow
            elif business_type == "saas":
                if finding.get("category") in ["forms", "performance", "mobile"]:
                    conversion_factors["affects_signup_flow"] = True
                    conversion_factors["user_experience_issue"] = True

            finding["conversion_factors"] = conversion_factors

        return findings

    def _select_top_issues(self, scored_findings: List[FindingScore]) -> List[FindingScore]:
        """
        Select top issues based on priority score

        Acceptance Criteria: Top 3 issues selected
        """
        # Filter out quick wins to avoid overlap
        non_quick_win_findings = [f for f in scored_findings if not f.is_quick_win or f.priority_score >= 8.5]

        # Ensure diversity in categories
        top_issues = []
        used_categories = set()

        for finding in non_quick_win_findings:
            if len(top_issues) >= self.top_issues_count:
                break

            # Prefer different categories for better coverage
            if finding.category not in used_categories or len(top_issues) == 0:
                top_issues.append(finding)
                used_categories.add(finding.category)
            elif len(top_issues) < self.top_issues_count:
                # Fill remaining slots even with duplicate categories
                top_issues.append(finding)

        # If we still need more, fill from remaining high-scoring findings
        remaining_needed = self.top_issues_count - len(top_issues)
        if remaining_needed > 0:
            remaining_findings = [f for f in scored_findings if f not in top_issues][:remaining_needed]
            top_issues.extend(remaining_findings)

        return top_issues[: self.top_issues_count]

    def _identify_quick_wins(self, scored_findings: List[FindingScore]) -> List[FindingScore]:
        """
        Identify quick wins based on high impact and low effort

        Acceptance Criteria: Quick wins identified
        """
        quick_wins = [finding for finding in scored_findings if finding.is_quick_win]

        # Sort by quick win score
        quick_wins.sort(key=lambda x: x.quick_win_score, reverse=True)

        return quick_wins[: self.max_quick_wins]

    def _generate_summary(
        self,
        all_findings: List[FindingScore],
        top_issues: List[FindingScore],
        quick_wins: List[FindingScore],
    ) -> Dict[str, Any]:
        """Generate summary statistics"""
        if not all_findings:
            return {"total_findings": 0}

        # Calculate averages
        avg_impact = sum(f.impact_score for f in all_findings) / len(all_findings)
        avg_effort = sum(f.effort_score for f in all_findings) / len(all_findings)
        avg_conversion_impact = sum(f.conversion_impact for f in all_findings) / len(all_findings)

        # Count by category
        category_counts = {}
        for finding in all_findings:
            category_counts[finding.category] = category_counts.get(finding.category, 0) + 1

        # Count by impact level
        impact_levels = {
            "critical": len([f for f in all_findings if f.impact_score >= 8.5]),
            "high": len([f for f in all_findings if 7.0 <= f.impact_score < 8.5]),
            "medium": len([f for f in all_findings if 5.0 <= f.impact_score < 7.0]),
            "low": len([f for f in all_findings if f.impact_score < 5.0]),
        }

        return {
            "total_findings": len(all_findings),
            "top_issues_count": len(top_issues),
            "quick_wins_count": len(quick_wins),
            "average_impact_score": round(avg_impact, 2),
            "average_effort_score": round(avg_effort, 2),
            "average_conversion_impact": round(avg_conversion_impact, 2),
            "findings_by_category": category_counts,
            "findings_by_impact_level": impact_levels,
            "highest_impact_finding": max(all_findings, key=lambda x: x.impact_score).title,
            "easiest_quick_win": min(quick_wins, key=lambda x: x.effort_score).title if quick_wins else None,
        }

    def _empty_result(self) -> PrioritizationResult:
        """Return empty result when no findings are available"""
        return PrioritizationResult(top_issues=[], quick_wins=[], all_findings=[], summary={"total_findings": 0})

    # Helper methods for PageSpeed categorization
    def _categorize_pagespeed_audit(self, audit_id: str) -> str:
        """Categorize PageSpeed audit by ID"""
        performance_audits = [
            "first-contentful-paint",
            "largest-contentful-paint",
            "speed-index",
            "total-blocking-time",
            "cumulative-layout-shift",
            "server-response-time",
        ]
        accessibility_audits = [
            "color-contrast",
            "image-alt",
            "label",
            "link-name",
            "button-name",
        ]
        best_practices_audits = [
            "uses-https",
            "is-on-https",
            "external-anchors-use-rel-noopener",
        ]
        seo_audits = ["document-title", "meta-description", "hreflang", "canonical"]

        if audit_id in performance_audits:
            return "performance"
        elif audit_id in accessibility_audits:
            return "accessibility"
        elif audit_id in best_practices_audits:
            return "best_practices"
        elif audit_id in seo_audits:
            return "seo"
        else:
            return "general"

    def _pagespeed_score_to_severity(self, score: float) -> str:
        """Convert PageSpeed score to severity level"""
        if score < 0.5:
            return "critical"
        elif score < 0.7:
            return "high"
        elif score < 0.9:
            return "medium"
        else:
            return "low"

    def _pagespeed_audit_to_fix_type(self, audit_id: str) -> str:
        """Determine fix type from PageSpeed audit ID"""
        image_audits = ["uses-optimized-images", "uses-webp-images", "offscreen-images"]
        css_audits = ["unused-css-rules", "render-blocking-resources"]
        js_audits = ["unused-javascript", "legacy-javascript"]
        server_audits = ["uses-text-compression", "server-response-time"]

        if audit_id in image_audits:
            return "image_optimization"
        elif audit_id in css_audits:
            return "css_changes"
        elif audit_id in js_audits:
            return "javascript_fixes"
        elif audit_id in server_audits:
            return "server_config"
        else:
            return "html_structure"

    def _get_pagespeed_impact_factors(self, audit_id: str, audit_data: Dict) -> Dict[str, bool]:
        """Get impact factors for PageSpeed audit"""
        core_vitals = [
            "first-contentful-paint",
            "largest-contentful-paint",
            "cumulative-layout-shift",
            "total-blocking-time",
        ]

        return {
            "affects_core_web_vitals": audit_id in core_vitals,
            "above_the_fold": audit_id in ["first-contentful-paint", "largest-contentful-paint"],
            "mobile_specific": False,  # Would need mobile-specific data
            "affects_forms": audit_id in ["color-contrast", "label", "button-name"],
        }

    def _get_pagespeed_effort_factors(self, audit_id: str, audit_data: Dict) -> Dict[str, Any]:
        """Get effort factors for PageSpeed audit"""
        easy_fixes = ["image-alt", "meta-description", "document-title"]
        automated_fixes = ["uses-optimized-images", "uses-webp-images"]

        return {
            "requires_developer": audit_id not in easy_fixes,
            "requires_design": audit_id in ["color-contrast", "font-size"],
            "automated_fix_available": audit_id in automated_fixes,
            "affected_elements": 1,  # Default, would need detailed analysis
            "requires_third_party": False,
        }

    def _get_pagespeed_conversion_factors(self, audit_id: str, audit_data: Dict) -> Dict[str, bool]:
        """Get conversion factors for PageSpeed audit"""
        performance_critical = [
            "first-contentful-paint",
            "largest-contentful-paint",
            "speed-index",
        ]
        trust_related = ["uses-https", "is-on-https"]
        ux_related = ["color-contrast", "tap-targets", "font-size"]

        return {
            "user_experience_issue": audit_id in performance_critical + ux_related,
            "trust_issue": audit_id in trust_related,
            "mobile_conversion_issue": audit_id in ["tap-targets", "font-size"],
            "affects_lead_generation": audit_id in ux_related,
            "blocks_purchase": False,  # Would need e-commerce specific analysis
        }
