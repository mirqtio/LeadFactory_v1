"""
D8 Personalization Spam Score Checker - Task 063

Rule-based spam score checker with configurable rules and score reduction logic
for email deliverability optimization.

Acceptance Criteria:
- Basic spam scoring ✓
- Rule-based checks ✓
- Score reduction logic ✓
- Common patterns caught ✓
"""

import json
import os
import re
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple


class SpamRiskLevel(str, Enum):
    """Spam risk levels"""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class SpamRuleType(str, Enum):
    """Types of spam rules"""

    KEYWORD = "keyword"
    PATTERN = "pattern"
    LENGTH = "length"
    FREQUENCY = "frequency"
    FORMATTING = "formatting"
    STRUCTURE = "structure"


@dataclass
class SpamRule:
    """Individual spam rule configuration"""

    rule_id: str
    rule_type: SpamRuleType
    description: str
    pattern: str
    weight: float
    threshold: Optional[float] = None
    enabled: bool = True
    category: str = "general"


@dataclass
class SpamCheckResult:
    """Result of spam check analysis"""

    overall_score: float
    risk_level: SpamRiskLevel
    triggered_rules: List[Dict[str, Any]]
    suggestions: List[str]
    category_scores: Dict[str, float]
    analysis_details: Dict[str, Any]


class SpamScoreChecker:
    """Main spam score checker with rule-based analysis - Acceptance Criteria"""

    def __init__(self, rules_file: Optional[str] = None):
        """Initialize spam checker with rules"""
        self.rules_file = rules_file or self._get_default_rules_path()
        self.rules = self._load_spam_rules()
        self.max_score = 100.0

    def _get_default_rules_path(self) -> str:
        """Get default path to spam rules JSON"""
        current_dir = os.path.dirname(__file__)
        return os.path.join(current_dir, "spam_rules.json")

    def _load_spam_rules(self) -> List[SpamRule]:
        """Load spam rules from JSON file"""
        try:
            with open(self.rules_file, "r") as file:
                rules_data = json.load(file)

            rules = []
            for rule_data in rules_data.get("rules", []):
                rule = SpamRule(
                    rule_id=rule_data["rule_id"],
                    rule_type=SpamRuleType(rule_data["rule_type"]),
                    description=rule_data["description"],
                    pattern=rule_data["pattern"],
                    weight=rule_data["weight"],
                    threshold=rule_data.get("threshold"),
                    enabled=rule_data.get("enabled", True),
                    category=rule_data.get("category", "general"),
                )
                rules.append(rule)

            return rules

        except (FileNotFoundError, json.JSONDecodeError, KeyError):
            # Fallback to default rules
            return self._get_fallback_rules()

    def _get_fallback_rules(self) -> List[SpamRule]:
        """Fallback spam rules when JSON file not available"""
        return [
            SpamRule(
                "word_free",
                SpamRuleType.KEYWORD,
                "Word: FREE",
                r"\bfree\b",
                15.0,
                category="keywords",
            ),
            SpamRule(
                "word_urgent",
                SpamRuleType.KEYWORD,
                "Word: URGENT",
                r"\burgent\b",
                12.0,
                category="keywords",
            ),
            SpamRule(
                "all_caps",
                SpamRuleType.PATTERN,
                "All caps words",
                r"\b[A-Z]{4,}\b",
                8.0,
                category="formatting",
            ),
            SpamRule(
                "multiple_exclamation",
                SpamRuleType.PATTERN,
                "Multiple exclamations",
                r"!{2,}",
                10.0,
                category="formatting",
            ),
            SpamRule(
                "subject_too_long",
                SpamRuleType.LENGTH,
                "Subject line too long",
                "",
                5.0,
                threshold=60.0,
                category="structure",
            ),
        ]

    def check_spam_score(self, subject_line: str, email_content: str, content_type: str = "html") -> SpamCheckResult:
        """Check spam score for email content - Acceptance Criteria"""

        # Clean content for analysis
        clean_content = self._clean_content(email_content, content_type)
        full_text = f"{subject_line} {clean_content}"

        # Initialize scoring
        total_score = 0.0
        triggered_rules = []
        category_scores = {}
        analysis_details = {
            "subject_length": len(subject_line),
            "content_length": len(clean_content),
            "word_count": len(clean_content.split()),
            "analysis_timestamp": datetime.utcnow().isoformat(),
        }

        # Apply each enabled rule
        for rule in self.rules:
            if not rule.enabled:
                continue

            rule_score, rule_matches = self._apply_rule(rule, subject_line, clean_content, full_text)

            if rule_score > 0:
                total_score += rule_score
                triggered_rules.append(
                    {
                        "rule_id": rule.rule_id,
                        "description": rule.description,
                        "score": rule_score,
                        "matches": rule_matches,
                        "category": rule.category,
                    }
                )

                # Update category scores
                if rule.category not in category_scores:
                    category_scores[rule.category] = 0.0
                category_scores[rule.category] += rule_score

        # Normalize score to 0-100 scale
        final_score = min(total_score, self.max_score)

        # Determine risk level
        risk_level = self._calculate_risk_level(final_score)

        # Generate improvement suggestions
        suggestions = self._generate_suggestions(triggered_rules, analysis_details)

        return SpamCheckResult(
            overall_score=final_score,
            risk_level=risk_level,
            triggered_rules=triggered_rules,
            suggestions=suggestions,
            category_scores=category_scores,
            analysis_details=analysis_details,
        )

    def _apply_rule(self, rule: SpamRule, subject: str, content: str, full_text: str) -> Tuple[float, List[str]]:
        """Apply individual spam rule - Rule-based checks"""

        matches = []
        score = 0.0

        if rule.rule_type == SpamRuleType.KEYWORD:
            matches = self._check_keyword_rule(rule, full_text)
            score = len(matches) * rule.weight

        elif rule.rule_type == SpamRuleType.PATTERN:
            matches = self._check_pattern_rule(rule, full_text)
            score = len(matches) * rule.weight

        elif rule.rule_type == SpamRuleType.LENGTH:
            score = self._check_length_rule(rule, subject, content)
            if score > 0:
                matches = ["Length violation"]

        elif rule.rule_type == SpamRuleType.FREQUENCY:
            score, matches = self._check_frequency_rule(rule, full_text)

        elif rule.rule_type == SpamRuleType.FORMATTING:
            score, matches = self._check_formatting_rule(rule, full_text)

        elif rule.rule_type == SpamRuleType.STRUCTURE:
            score, matches = self._check_structure_rule(rule, subject, content)

        return score, matches

    def _check_keyword_rule(self, rule: SpamRule, text: str) -> List[str]:
        """Check for keyword-based spam patterns - Common patterns caught"""
        matches = re.findall(rule.pattern, text, re.IGNORECASE)
        return matches

    def _check_pattern_rule(self, rule: SpamRule, text: str) -> List[str]:
        """Check for pattern-based spam indicators - Common patterns caught"""
        matches = re.findall(rule.pattern, text)
        return matches

    def _check_length_rule(self, rule: SpamRule, subject: str, content: str) -> float:
        """Check length-based rules"""
        if "subject" in rule.rule_id.lower():
            length = len(subject)
        else:
            length = len(content)

        if rule.threshold and length > rule.threshold:
            return rule.weight

        return 0.0

    def _check_frequency_rule(self, rule: SpamRule, text: str) -> Tuple[float, List[str]]:
        """Check frequency-based rules"""
        matches = re.findall(rule.pattern, text, re.IGNORECASE)
        frequency = len(matches)

        if rule.threshold and frequency > rule.threshold:
            return rule.weight * (frequency - rule.threshold), [f"{frequency} occurrences"]

        return 0.0, []

    def _check_formatting_rule(self, rule: SpamRule, text: str) -> Tuple[float, List[str]]:
        """Check formatting-based rules"""
        matches = re.findall(rule.pattern, text)

        if matches:
            return rule.weight * len(matches), matches

        return 0.0, []

    def _check_structure_rule(self, rule: SpamRule, subject: str, content: str) -> Tuple[float, List[str]]:
        """Check structural rules"""
        score = 0.0
        issues = []

        if "empty" in rule.rule_id.lower():
            if len(content.strip()) == 0:
                score = rule.weight
                issues.append("Empty content")

        elif "ratio" in rule.rule_id.lower():
            # Check text to HTML ratio for HTML content
            if "<" in content:  # HTML content
                text_content = re.sub(r"<[^>]+>", "", content)
                html_ratio = len(content) / max(len(text_content), 1)
                if html_ratio > (rule.threshold or 3.0):
                    score = rule.weight
                    issues.append(f"High HTML ratio: {html_ratio:.1f}")

        return score, issues

    def _clean_content(self, content: str, content_type: str) -> str:
        """Clean content for analysis"""
        if content_type.lower() == "html":
            # Remove HTML tags but keep text
            clean = re.sub(r"<[^>]+>", " ", content)
            # Remove multiple whitespaces
            clean = re.sub(r"\s+", " ", clean)
            return clean.strip()
        return content.strip()

    def _calculate_risk_level(self, score: float) -> SpamRiskLevel:
        """Calculate risk level from spam score"""
        if score < 25:
            return SpamRiskLevel.LOW
        elif score < 50:
            return SpamRiskLevel.MEDIUM
        elif score < 75:
            return SpamRiskLevel.HIGH
        else:
            return SpamRiskLevel.CRITICAL

    def _generate_suggestions(
        self, triggered_rules: List[Dict[str, Any]], analysis_details: Dict[str, Any]
    ) -> List[str]:
        """Generate improvement suggestions - Score reduction logic"""
        suggestions = []

        # Group rules by category for targeted suggestions
        categories = {}
        for rule in triggered_rules:
            category = rule["category"]
            if category not in categories:
                categories[category] = []
            categories[category].append(rule)

        # Generate category-specific suggestions
        if "keywords" in categories:
            suggestions.append("Remove or replace spam trigger words (FREE, URGENT, etc.)")

        if "formatting" in categories:
            formatting_issues = categories["formatting"]
            caps_issues = [r for r in formatting_issues if "caps" in r["rule_id"]]
            if caps_issues:
                suggestions.append("Reduce use of ALL CAPS words")

            exclamation_issues = [r for r in formatting_issues if "exclamation" in r["rule_id"]]
            if exclamation_issues:
                suggestions.append("Limit exclamation marks to one per email")

        if "structure" in categories:
            suggestions.append("Improve email structure and content balance")

        # Length-based suggestions
        if analysis_details.get("subject_length", 0) > 60:
            suggestions.append("Shorten subject line to under 60 characters")

        if analysis_details.get("content_length", 0) < 50:
            suggestions.append("Add more meaningful content to email body")

        # General suggestions if score is high
        overall_score = sum(rule["score"] for rule in triggered_rules)
        if overall_score > 50:
            suggestions.append("Consider complete email rewrite for better deliverability")
        elif overall_score > 25:
            suggestions.append("Review and optimize email content for spam filters")

        return suggestions[:5]  # Limit to top 5 suggestions

    def reduce_spam_score(self, original_content: str, suggestions: List[str]) -> Dict[str, str]:
        """Apply automatic score reduction improvements - Score reduction logic"""

        improved_content = original_content
        applied_fixes = []

        # Apply common fixes
        if "Remove or replace spam trigger words" in " ".join(suggestions):
            # Replace common spam words
            spam_replacements = {
                r"\bFREE\b": "Complimentary",
                r"\bURGENT\b": "Important",
                r"\bACT NOW\b": "Take action",
                r"\bLIMITED TIME\b": "Time-sensitive",
                r"\bCLICK HERE\b": "Learn more",
            }

            for pattern, replacement in spam_replacements.items():
                if re.search(pattern, improved_content, re.IGNORECASE):
                    improved_content = re.sub(pattern, replacement, improved_content, flags=re.IGNORECASE)
                    applied_fixes.append(f"Replaced spam word with '{replacement}'")

        if "Reduce use of ALL CAPS words" in " ".join(suggestions):
            # Convert excessive caps to normal case
            def normalize_caps(match):
                word = match.group(0)
                if len(word) > 3:  # Only normalize long caps words
                    return word.capitalize()
                return word

            improved_content = re.sub(r"\b[A-Z]{4,}\b", normalize_caps, improved_content)
            applied_fixes.append("Normalized excessive capital letters")

        if "Limit exclamation marks" in " ".join(suggestions):
            # Reduce multiple exclamation marks
            improved_content = re.sub(r"!{2,}", "!", improved_content)
            applied_fixes.append("Reduced excessive exclamation marks")

        return {
            "improved_content": improved_content,
            "applied_fixes": applied_fixes,
            "original_length": len(original_content),
            "improved_length": len(improved_content),
        }

    def batch_check_emails(self, emails: List[Dict[str, str]]) -> List[SpamCheckResult]:
        """Check multiple emails for spam scores"""
        results = []

        for email in emails:
            subject = email.get("subject", "")
            content = email.get("content", "")
            content_type = email.get("content_type", "html")

            result = self.check_spam_score(subject, content, content_type)
            results.append(result)

        return results

    def get_rule_statistics(self) -> Dict[str, Any]:
        """Get statistics about loaded rules"""
        enabled_rules = [r for r in self.rules if r.enabled]

        stats = {
            "total_rules": len(self.rules),
            "enabled_rules": len(enabled_rules),
            "disabled_rules": len(self.rules) - len(enabled_rules),
            "rules_by_type": {},
            "rules_by_category": {},
            "average_weight": 0.0,
        }

        # Count by type
        for rule in enabled_rules:
            rule_type = rule.rule_type.value
            if rule_type not in stats["rules_by_type"]:
                stats["rules_by_type"][rule_type] = 0
            stats["rules_by_type"][rule_type] += 1

            # Count by category
            category = rule.category
            if category not in stats["rules_by_category"]:
                stats["rules_by_category"][category] = 0
            stats["rules_by_category"][category] += 1

        # Calculate average weight
        if enabled_rules:
            stats["average_weight"] = sum(r.weight for r in enabled_rules) / len(enabled_rules)

        return stats


# Utility functions for spam checking
def quick_spam_check(subject: str, content: str) -> float:
    """Quick spam score check with default rules"""
    checker = SpamScoreChecker()
    result = checker.check_spam_score(subject, content)
    return result.overall_score


def is_likely_spam(subject: str, content: str, threshold: float = 50.0) -> bool:
    """Quick check if content is likely spam"""
    score = quick_spam_check(subject, content)
    return score >= threshold


def improve_email_deliverability(subject: str, content: str) -> Dict[str, Any]:
    """Get suggestions to improve email deliverability"""
    checker = SpamScoreChecker()
    result = checker.check_spam_score(subject, content)

    if result.overall_score > 25:
        improvements = checker.reduce_spam_score(content, result.suggestions)
        return {
            "original_score": result.overall_score,
            "suggestions": result.suggestions,
            "improvements": improvements,
            "risk_level": result.risk_level.value,
        }

    return {
        "original_score": result.overall_score,
        "suggestions": ["Content appears to be spam-filter friendly"],
        "risk_level": result.risk_level.value,
    }


# Constants for spam checking
DEFAULT_SPAM_THRESHOLD = 50.0
MAX_SUBJECT_LENGTH = 60
MIN_CONTENT_LENGTH = 50
MAX_EXCLAMATION_MARKS = 1
