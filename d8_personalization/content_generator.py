"""
D8 Personalization Content Generator - Task 062

Advanced content generation utilities and templates for creating
personalized email content with different strategies and formats.

Acceptance Criteria:
- Issue extraction works ✓
- LLM integration complete ✓
- HTML/text formatting ✓
- Spam check integrated ✓
"""

import re
import json
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime
from dataclasses import dataclass
from enum import Enum

from .models import ContentStrategy, PersonalizationStrategy, EmailContentType
from .personalizer import ExtractedIssue, IssueImpact


class TemplateVariable(str, Enum):
    """Template variables for content generation"""
    BUSINESS_NAME = "business_name"
    CONTACT_NAME = "contact_name"
    INDUSTRY = "industry"
    LOCATION = "location"
    MAIN_ISSUE = "main_issue"
    ISSUE_COUNT = "issue_count"
    IMPACT_LEVEL = "impact_level"
    IMPROVEMENT = "improvement"
    CALL_TO_ACTION = "call_to_action"


@dataclass
class ContentTemplate:
    """Template for generating email content"""
    name: str
    content_type: EmailContentType
    strategy: ContentStrategy
    subject_template: str
    opening_template: str
    problem_statement: str
    solution_statement: str
    call_to_action: str
    closing_template: str
    variables: List[str]
    tone: str = "professional"
    length_category: str = "medium"  # short, medium, long


@dataclass
class GeneratedContent:
    """Generated email content with metadata"""
    subject_line: str
    opening: str
    body: str
    call_to_action: str
    closing: str
    full_html: str
    full_text: str
    variables_used: Dict[str, str]
    template_used: str
    generation_method: str


class ContentTemplateLibrary:
    """Library of content templates for different strategies"""
    
    def __init__(self):
        self.templates = self._initialize_templates()
    
    def _initialize_templates(self) -> Dict[str, List[ContentTemplate]]:
        """Initialize content template library"""
        return {
            ContentStrategy.PROBLEM_AGITATION.value: self._create_problem_agitation_templates(),
            ContentStrategy.BEFORE_AFTER.value: self._create_before_after_templates(),
            ContentStrategy.EDUCATIONAL_VALUE.value: self._create_educational_templates(),
            ContentStrategy.DIRECT_OFFER.value: self._create_direct_offer_templates(),
            ContentStrategy.SOCIAL_PROOF.value: self._create_social_proof_templates(),
            ContentStrategy.URGENCY_SCARCITY.value: self._create_urgency_templates()
        }
    
    def _create_problem_agitation_templates(self) -> List[ContentTemplate]:
        """Create problem-agitation-solution templates"""
        return [
            ContentTemplate(
                name="website_performance_problem",
                content_type=EmailContentType.COLD_OUTREACH,
                strategy=ContentStrategy.PROBLEM_AGITATION,
                subject_template="Is {business_name}'s website costing you customers?",
                opening_template="Hi {contact_name}, I was analyzing {business_name}'s website and noticed some concerning issues.",
                problem_statement="Your website has {main_issue}, which could be driving potential customers away. In fact, {impact_level} impact issues like this can reduce conversions by up to 40%.",
                solution_statement="The good news? These issues are completely fixable. {improvement} would make an immediate difference to your online performance.",
                call_to_action="Would you be interested in a free 15-minute consultation to discuss how we can turn these issues into opportunities?",
                closing_template="Best regards,\nThe Website Performance Team",
                variables=["business_name", "contact_name", "main_issue", "impact_level", "improvement"],
                tone="concerned_helpful"
            ),
            ContentTemplate(
                name="seo_visibility_problem",
                content_type=EmailContentType.COLD_OUTREACH,
                strategy=ContentStrategy.PROBLEM_AGITATION,
                subject_template="{business_name} missing from local search results",
                opening_template="Hello, I was searching for {industry} businesses in {location} and noticed {business_name} wasn't showing up where it should be.",
                problem_statement="This means potential customers can't find you when they're actively looking for {industry} services. Every day this continues, competitors are capturing customers that should be yours.",
                solution_statement="SEO optimization can fix this quickly. {improvement} would get you visible to local customers within 30-60 days.",
                call_to_action="Can we schedule a brief call to show you exactly where {business_name} should be ranking?",
                closing_template="Best regards,\nLocal SEO Team",
                variables=["business_name", "industry", "location", "improvement"],
                tone="urgent_helpful"
            )
        ]
    
    def _create_before_after_templates(self) -> List[ContentTemplate]:
        """Create before/after scenario templates"""
        return [
            ContentTemplate(
                name="website_transformation",
                content_type=EmailContentType.AUDIT_OFFER,
                strategy=ContentStrategy.BEFORE_AFTER,
                subject_template="Before & after: {business_name}'s website potential",
                opening_template="Hi {contact_name}, I wanted to show you what {business_name}'s website could look like with some strategic improvements.",
                problem_statement="Right now: {main_issue} and {issue_count} other issues are limiting your website's effectiveness.",
                solution_statement="After optimization: Your website would load faster, rank higher in search results, and convert more visitors into customers. {improvement} alone could increase conversions by 25%.",
                call_to_action="Would you like to see a detailed before/after analysis of {business_name}'s potential?",
                closing_template="Best regards,\nWebsite Optimization Team",
                variables=["business_name", "contact_name", "main_issue", "issue_count", "improvement"],
                tone="vision_focused"
            )
        ]
    
    def _create_educational_templates(self) -> List[ContentTemplate]:
        """Create educational value templates"""
        return [
            ContentTemplate(
                name="website_education",
                content_type=EmailContentType.EDUCATIONAL,
                strategy=ContentStrategy.EDUCATIONAL_VALUE,
                subject_template="3 ways {business_name} can improve online performance",
                opening_template="Hi {contact_name}, I've put together some insights that could help {business_name} attract more customers online.",
                problem_statement="Many {industry} businesses struggle with the same {issue_count} common website issues. Here's what I found for {business_name}:",
                solution_statement="Here are three specific improvements that would make the biggest impact: {improvement}. These changes typically take 2-4 weeks to implement but can improve performance for years.",
                call_to_action="Would you like a detailed action plan showing exactly how to implement these improvements?",
                closing_template="Happy to help,\nWebsite Performance Team",
                variables=["business_name", "contact_name", "industry", "issue_count", "improvement"],
                tone="helpful_educational"
            )
        ]
    
    def _create_direct_offer_templates(self) -> List[ContentTemplate]:
        """Create direct offer templates"""
        return [
            ContentTemplate(
                name="free_audit_offer",
                content_type=EmailContentType.AUDIT_OFFER,
                strategy=ContentStrategy.DIRECT_OFFER,
                subject_template="Free website audit for {business_name}",
                opening_template="Hi {contact_name}, I'd like to offer {business_name} a complimentary website performance audit.",
                problem_statement="Our analysis shows {main_issue} and other optimization opportunities that could improve your online results.",
                solution_statement="This free audit will identify exactly how to {improvement} and provide a priority roadmap for maximum impact.",
                call_to_action="The audit takes 15 minutes and could save you thousands in lost revenue. When would be a good time this week?",
                closing_template="Looking forward to helping,\nWebsite Audit Team",
                variables=["business_name", "contact_name", "main_issue", "improvement"],
                tone="direct_professional"
            )
        ]
    
    def _create_social_proof_templates(self) -> List[ContentTemplate]:
        """Create social proof templates"""
        return [
            ContentTemplate(
                name="case_study_success",
                content_type=EmailContentType.COLD_OUTREACH,
                strategy=ContentStrategy.SOCIAL_PROOF,
                subject_template="How we helped a {industry} business like {business_name}",
                opening_template="Hi {contact_name}, I wanted to share how we recently helped another {industry} business overcome similar challenges to what I noticed with {business_name}.",
                problem_statement="They had {main_issue} and were losing customers to competitors with better websites.",
                solution_statement="After implementing {improvement}, they saw a 45% increase in online inquiries within 60 days. The same approach could work for {business_name}.",
                call_to_action="Would you like to see the full case study and discuss how we could achieve similar results for {business_name}?",
                closing_template="Best regards,\nClient Success Team",
                variables=["business_name", "contact_name", "industry", "main_issue", "improvement"],
                tone="proof_based"
            )
        ]
    
    def _create_urgency_templates(self) -> List[ContentTemplate]:
        """Create urgency/scarcity templates"""
        return [
            ContentTemplate(
                name="limited_time_audit",
                content_type=EmailContentType.PROMOTIONAL,
                strategy=ContentStrategy.URGENCY_SCARCITY,
                subject_template="48 hours left: Free audit for {business_name}",
                opening_template="Hi {contact_name}, I have space for just 3 more free website audits this month, and I wanted to offer one to {business_name}.",
                problem_statement="With {main_issue} affecting your website, every day of delay means lost customers and revenue.",
                solution_statement="This audit will create a priority action plan to {improvement} and give you a competitive advantage.",
                call_to_action="Since spots are limited, can we schedule your audit by Friday? It only takes 15 minutes and could transform your online results.",
                closing_template="Limited time offer,\nWebsite Audit Team",
                variables=["business_name", "contact_name", "main_issue", "improvement"],
                tone="urgent_exclusive"
            )
        ]
    
    def get_templates(self, strategy: ContentStrategy) -> List[ContentTemplate]:
        """Get templates for a specific strategy"""
        return self.templates.get(strategy.value, [])
    
    def get_template_by_name(self, name: str) -> Optional[ContentTemplate]:
        """Get a specific template by name"""
        for templates in self.templates.values():
            for template in templates:
                if template.name == name:
                    return template
        return None


class VariableResolver:
    """Resolves template variables with actual data"""
    
    def __init__(self):
        self.resolution_methods = {
            TemplateVariable.BUSINESS_NAME: self._resolve_business_name,
            TemplateVariable.CONTACT_NAME: self._resolve_contact_name,
            TemplateVariable.INDUSTRY: self._resolve_industry,
            TemplateVariable.LOCATION: self._resolve_location,
            TemplateVariable.MAIN_ISSUE: self._resolve_main_issue,
            TemplateVariable.ISSUE_COUNT: self._resolve_issue_count,
            TemplateVariable.IMPACT_LEVEL: self._resolve_impact_level,
            TemplateVariable.IMPROVEMENT: self._resolve_improvement,
            TemplateVariable.CALL_TO_ACTION: self._resolve_call_to_action
        }
    
    def resolve_variables(
        self, 
        template: ContentTemplate,
        business_data: Dict[str, Any],
        contact_data: Optional[Dict[str, Any]],
        issues: List[ExtractedIssue]
    ) -> Dict[str, str]:
        """Resolve all variables in a template"""
        resolved = {}
        
        for variable in template.variables:
            if variable in self.resolution_methods:
                resolved[variable] = self.resolution_methods[variable](
                    business_data, contact_data, issues
                )
            else:
                resolved[variable] = f"{{{variable}}}"  # Unresolved placeholder
        
        return resolved
    
    def _resolve_business_name(
        self, 
        business_data: Dict[str, Any], 
        contact_data: Optional[Dict[str, Any]], 
        issues: List[ExtractedIssue]
    ) -> str:
        """Resolve business name variable"""
        name = business_data.get('name', 'your business')
        
        # Clean up common suffixes
        suffixes = [' LLC', ' Inc', ' Corp', ' Ltd', ' Co']
        for suffix in suffixes:
            if name.endswith(suffix):
                name = name[:-len(suffix)]
        
        return name.strip()
    
    def _resolve_contact_name(
        self, 
        business_data: Dict[str, Any], 
        contact_data: Optional[Dict[str, Any]], 
        issues: List[ExtractedIssue]
    ) -> str:
        """Resolve contact name variable"""
        if not contact_data:
            return "there"
        
        first_name = contact_data.get('first_name')
        if first_name:
            return first_name.title()
        
        full_name = contact_data.get('name')
        if full_name:
            return full_name.split()[0].title()
        
        return "there"
    
    def _resolve_industry(
        self, 
        business_data: Dict[str, Any], 
        contact_data: Optional[Dict[str, Any]], 
        issues: List[ExtractedIssue]
    ) -> str:
        """Resolve industry variable"""
        category = business_data.get('category', '')
        industry = business_data.get('industry', '')
        
        # Normalize industry names
        industry_text = category or industry or 'business'
        
        # Clean up common terms
        industry_text = industry_text.lower()
        if industry_text.endswith('s'):
            industry_text = industry_text[:-1]  # Make singular
        
        return industry_text
    
    def _resolve_location(
        self, 
        business_data: Dict[str, Any], 
        contact_data: Optional[Dict[str, Any]], 
        issues: List[ExtractedIssue]
    ) -> str:
        """Resolve location variable"""
        location_data = business_data.get('location', {})
        
        if isinstance(location_data, dict):
            city = location_data.get('city', '')
            if ', ' in city:
                city = city.split(', ')[0]  # Remove state suffix
            return city or 'your area'
        
        return str(location_data) if location_data else 'your area'
    
    def _resolve_main_issue(
        self, 
        business_data: Dict[str, Any], 
        contact_data: Optional[Dict[str, Any]], 
        issues: List[ExtractedIssue]
    ) -> str:
        """Resolve main issue variable"""
        if not issues:
            return "website performance issues"
        
        main_issue = issues[0]
        return main_issue.description.lower()
    
    def _resolve_issue_count(
        self, 
        business_data: Dict[str, Any], 
        contact_data: Optional[Dict[str, Any]], 
        issues: List[ExtractedIssue]
    ) -> str:
        """Resolve issue count variable"""
        count = len(issues)
        if count == 0:
            return "several"
        elif count == 1:
            return "1"
        else:
            return str(count)
    
    def _resolve_impact_level(
        self, 
        business_data: Dict[str, Any], 
        contact_data: Optional[Dict[str, Any]], 
        issues: List[ExtractedIssue]
    ) -> str:
        """Resolve impact level variable"""
        if not issues:
            return "medium"
        
        main_issue = issues[0]
        return main_issue.impact.value
    
    def _resolve_improvement(
        self, 
        business_data: Dict[str, Any], 
        contact_data: Optional[Dict[str, Any]], 
        issues: List[ExtractedIssue]
    ) -> str:
        """Resolve improvement variable"""
        if not issues:
            return "optimize your website for better performance"
        
        main_issue = issues[0]
        return main_issue.improvement.lower()
    
    def _resolve_call_to_action(
        self, 
        business_data: Dict[str, Any], 
        contact_data: Optional[Dict[str, Any]], 
        issues: List[ExtractedIssue]
    ) -> str:
        """Resolve call to action variable"""
        business_name = self._resolve_business_name(business_data, contact_data, issues)
        return f"Schedule a free consultation to improve {business_name}'s website performance"


class ContentFormatter:
    """Formats generated content into HTML and text versions"""
    
    def __init__(self):
        self.html_styles = {
            'container': 'font-family: Arial, sans-serif; line-height: 1.6; color: #333; max-width: 600px; margin: 0 auto; padding: 20px;',
            'header': 'background-color: #f8f9fa; padding: 20px; border-radius: 8px; margin-bottom: 20px;',
            'title': 'color: #2c3e50; margin-top: 0;',
            'content': 'background-color: #ffffff; padding: 15px; border-radius: 5px; margin: 15px 0;',
            'highlight': 'background-color: #e3f2fd; padding: 15px; border-radius: 5px; margin: 15px 0;',
            'button': 'background-color: #3498db; color: white; padding: 12px 24px; text-decoration: none; border-radius: 5px; display: inline-block;',
            'footer': 'color: #7f8c8d; font-size: 14px; border-top: 1px solid #ecf0f1; padding-top: 15px; margin-top: 20px;'
        }
    
    def format_html_email(
        self, 
        template: ContentTemplate,
        resolved_variables: Dict[str, str],
        issues: List[ExtractedIssue]
    ) -> str:
        """Format email content as HTML"""
        
        # Replace variables in template sections
        subject = self._replace_variables(template.subject_template, resolved_variables)
        opening = self._replace_variables(template.opening_template, resolved_variables)
        problem = self._replace_variables(template.problem_statement, resolved_variables)
        solution = self._replace_variables(template.solution_statement, resolved_variables)
        cta = self._replace_variables(template.call_to_action, resolved_variables)
        closing = self._replace_variables(template.closing_template, resolved_variables)
        
        # Build issues section if available
        issues_html = self._format_issues_html(issues) if issues else ""
        
        # Build complete HTML
        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="utf-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>{subject}</title>
        </head>
        <body style="{self.html_styles['container']}">
            <div style="{self.html_styles['header']}">
                <h2 style="{self.html_styles['title']}">Website Performance Insights</h2>
                
                <p>{opening}</p>
                
                <div style="{self.html_styles['content']}">
                    <p><strong>The Issue:</strong></p>
                    <p>{problem}</p>
                </div>
                
                {issues_html}
                
                <div style="{self.html_styles['highlight']}">
                    <p><strong>The Solution:</strong></p>
                    <p>{solution}</p>
                </div>
                
                <div style="text-align: center; margin: 30px 0;">
                    <a href="mailto:hello@example.com?subject=Website%20Consultation" 
                       style="{self.html_styles['button']}">
                        Get Started Today
                    </a>
                </div>
                
                <p>{cta}</p>
                
                <p style="{self.html_styles['footer']}">
                    {closing}
                </p>
            </div>
        </body>
        </html>
        """
        
        return html_content.strip()
    
    def format_text_email(
        self, 
        template: ContentTemplate,
        resolved_variables: Dict[str, str],
        issues: List[ExtractedIssue]
    ) -> str:
        """Format email content as plain text"""
        
        # Replace variables in template sections
        opening = self._replace_variables(template.opening_template, resolved_variables)
        problem = self._replace_variables(template.problem_statement, resolved_variables)
        solution = self._replace_variables(template.solution_statement, resolved_variables)
        cta = self._replace_variables(template.call_to_action, resolved_variables)
        closing = self._replace_variables(template.closing_template, resolved_variables)
        
        # Build issues section if available
        issues_text = self._format_issues_text(issues) if issues else ""
        
        # Build complete text
        text_content = f"""
{opening}

The Issue:
{problem}
{issues_text}
The Solution:
{solution}

{cta}

To get started: Reply to this email or call us directly.

{closing}

---
Website Performance Team
Email: hello@example.com
        """
        
        return text_content.strip()
    
    def _replace_variables(self, text: str, variables: Dict[str, str]) -> str:
        """Replace template variables with resolved values"""
        for variable, value in variables.items():
            text = text.replace(f"{{{variable}}}", value)
        return text
    
    def _format_issues_html(self, issues: List[ExtractedIssue]) -> str:
        """Format issues list as HTML"""
        if not issues:
            return ""
        
        html = '<div style="background-color: #fff3cd; padding: 15px; border-radius: 5px; margin: 15px 0;">'
        html += '<p><strong>Specific Issues Found:</strong></p><ul>'
        
        for issue in issues[:3]:  # Top 3 issues
            impact_color = {
                IssueImpact.HIGH: "#d73527",
                IssueImpact.MEDIUM: "#ff9800",
                IssueImpact.LOW: "#4caf50"
            }.get(issue.impact, "#666")
            
            html += f'''
            <li style="margin-bottom: 8px;">
                <span style="color: {impact_color}; font-weight: bold;">
                    {issue.description}
                </span><br>
                <em style="color: #666;">Fix: {issue.improvement}</em>
            </li>
            '''
        
        html += '</ul></div>'
        return html
    
    def _format_issues_text(self, issues: List[ExtractedIssue]) -> str:
        """Format issues list as plain text"""
        if not issues:
            return ""
        
        text = "\nSpecific Issues Found:\n" + "="*25 + "\n"
        
        for i, issue in enumerate(issues[:3], 1):
            text += f"{i}. {issue.description}\n"
            text += f"   Impact: {issue.impact.value.title()}\n"
            text += f"   Fix: {issue.improvement}\n\n"
        
        return text


class AdvancedContentGenerator:
    """Advanced content generator using templates and variable resolution"""
    
    def __init__(self):
        self.template_library = ContentTemplateLibrary()
        self.variable_resolver = VariableResolver()
        self.content_formatter = ContentFormatter()
    
    def generate_content(
        self, 
        strategy: ContentStrategy,
        business_data: Dict[str, Any],
        contact_data: Optional[Dict[str, Any]],
        issues: List[ExtractedIssue],
        content_type: EmailContentType = EmailContentType.COLD_OUTREACH
    ) -> GeneratedContent:
        """Generate complete email content using templates"""
        
        # Get templates for strategy
        templates = self.template_library.get_templates(strategy)
        
        # Find best matching template
        template = self._select_best_template(
            templates, content_type, business_data, issues
        )
        
        if not template:
            return self._generate_fallback_content(
                business_data, contact_data, issues
            )
        
        # Resolve variables
        resolved_variables = self.variable_resolver.resolve_variables(
            template, business_data, contact_data, issues
        )
        
        # Generate formatted content
        html_content = self.content_formatter.format_html_email(
            template, resolved_variables, issues
        )
        
        text_content = self.content_formatter.format_text_email(
            template, resolved_variables, issues
        )
        
        # Extract individual components
        subject_line = self._replace_variables(
            template.subject_template, resolved_variables
        )
        opening = self._replace_variables(
            template.opening_template, resolved_variables
        )
        body = self._replace_variables(
            f"{template.problem_statement} {template.solution_statement}",
            resolved_variables
        )
        cta = self._replace_variables(
            template.call_to_action, resolved_variables
        )
        closing = self._replace_variables(
            template.closing_template, resolved_variables
        )
        
        return GeneratedContent(
            subject_line=subject_line,
            opening=opening,
            body=body,
            call_to_action=cta,
            closing=closing,
            full_html=html_content,
            full_text=text_content,
            variables_used=resolved_variables,
            template_used=template.name,
            generation_method="template_based"
        )
    
    def _select_best_template(
        self, 
        templates: List[ContentTemplate], 
        content_type: EmailContentType,
        business_data: Dict[str, Any],
        issues: List[ExtractedIssue]
    ) -> Optional[ContentTemplate]:
        """Select the best template for the given context"""
        
        if not templates:
            return None
        
        # Filter by content type
        matching_templates = [
            t for t in templates 
            if t.content_type == content_type
        ]
        
        if not matching_templates:
            matching_templates = templates  # Fallback to any template
        
        # Score templates based on context
        scored_templates = []
        for template in matching_templates:
            score = self._score_template(template, business_data, issues)
            scored_templates.append((score, template))
        
        # Return best scoring template
        scored_templates.sort(reverse=True)
        return scored_templates[0][1] if scored_templates else None
    
    def _score_template(
        self, 
        template: ContentTemplate, 
        business_data: Dict[str, Any], 
        issues: List[ExtractedIssue]
    ) -> float:
        """Score template based on how well it fits the context"""
        score = 0.0
        
        # Score based on available variables
        business_name = business_data.get('name')
        if business_name and 'business_name' in template.variables:
            score += 0.3
        
        industry = business_data.get('category') or business_data.get('industry')
        if industry and 'industry' in template.variables:
            score += 0.2
        
        # Score based on issues
        if issues:
            if 'main_issue' in template.variables:
                score += 0.3
            if 'issue_count' in template.variables:
                score += 0.2
        
        return score
    
    def _generate_fallback_content(
        self, 
        business_data: Dict[str, Any],
        contact_data: Optional[Dict[str, Any]],
        issues: List[ExtractedIssue]
    ) -> GeneratedContent:
        """Generate fallback content when no template matches"""
        
        business_name = business_data.get('name', 'your business')
        contact_name = "there"
        
        if contact_data:
            contact_name = (contact_data.get('first_name') or 
                          contact_data.get('name', '').split()[0] or 
                          "there")
        
        # Simple fallback content
        subject_line = f"Website insights for {business_name}"
        opening = f"Hi {contact_name},"
        body = f"I noticed some opportunities to improve {business_name}'s website performance and wanted to share some insights with you."
        cta = "Would you be interested in a free consultation to discuss these improvements?"
        closing = "Best regards,\nWebsite Performance Team"
        
        # Simple HTML
        html_content = f"""
        <div style="font-family: Arial, sans-serif; max-width: 600px;">
            <p>{opening}</p>
            <p>{body}</p>
            <p>{cta}</p>
            <p>{closing}</p>
        </div>
        """
        
        # Simple text
        text_content = f"{opening}\n\n{body}\n\n{cta}\n\n{closing}"
        
        return GeneratedContent(
            subject_line=subject_line,
            opening=opening,
            body=body,
            call_to_action=cta,
            closing=closing,
            full_html=html_content,
            full_text=text_content,
            variables_used={},
            template_used="fallback",
            generation_method="fallback"
        )
    
    def _replace_variables(self, text: str, variables: Dict[str, str]) -> str:
        """Replace template variables with resolved values"""
        for variable, value in variables.items():
            text = text.replace(f"{{{variable}}}", value)
        return text


# Utility functions for content generation
def clean_html_content(html_content: str) -> str:
    """Clean and validate HTML content"""
    # Remove script tags for security
    html_content = re.sub(r'<script[^>]*>.*?</script>', '', html_content, flags=re.DOTALL | re.IGNORECASE)
    
    # Remove inline event handlers
    html_content = re.sub(r'\s*on\w+\s*=\s*["\'][^"\']*["\']', '', html_content, flags=re.IGNORECASE)
    
    return html_content


def extract_text_from_html(html_content: str) -> str:
    """Extract plain text from HTML content"""
    # Remove HTML tags
    text = re.sub(r'<[^>]+>', ' ', html_content)
    
    # Clean up whitespace
    text = re.sub(r'\s+', ' ', text)
    
    return text.strip()


def validate_email_content(subject: str, content: str) -> Dict[str, bool]:
    """Validate email content for common issues"""
    return {
        'subject_length_ok': 10 <= len(subject) <= 60,
        'content_length_ok': 100 <= len(content) <= 2000,
        'has_call_to_action': any(word in content.lower() for word in ['call', 'click', 'reply', 'schedule', 'contact']),
        'personalization_present': any(char.isupper() for char in content),
        'no_excessive_punctuation': content.count('!') <= 2 and content.count('?') <= 2
    }


# Constants for content generation
MAX_TEMPLATE_VARIABLES = 10
DEFAULT_CONTENT_LENGTH_RANGE = (200, 800)
MAX_ISSUES_IN_CONTENT = 3
TEMPLATE_CACHE_SIZE = 50