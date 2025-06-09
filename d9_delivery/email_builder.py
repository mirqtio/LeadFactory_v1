"""
Email Builder

Builds properly formatted emails for SendGrid delivery with templates,
personalization, and compliance features.

Acceptance Criteria:
- Email building works ✓
- Categories added ✓
- Custom args included ✓
"""

import os
import re
import logging
import uuid
from typing import Dict, List, Any, Optional, Union
from datetime import datetime, timezone
from dataclasses import dataclass, field
from jinja2 import Template, Environment, BaseLoader
import html

from .sendgrid_client import EmailData


logger = logging.getLogger(__name__)


@dataclass
class EmailTemplate:
    """Email template data structure"""
    name: str
    subject_template: str
    html_template: str
    text_template: Optional[str] = None
    default_categories: List[str] = field(default_factory=list)
    default_custom_args: Dict[str, Any] = field(default_factory=dict)


@dataclass
class PersonalizationData:
    """Personalization data for email templates"""
    business_name: str
    contact_name: Optional[str] = None
    contact_first_name: Optional[str] = None
    business_category: Optional[str] = None
    business_location: Optional[str] = None
    issues_found: List[str] = field(default_factory=list)
    assessment_score: Optional[float] = None
    custom_data: Dict[str, Any] = field(default_factory=dict)


class EmailBuilder:
    """
    Email builder for creating formatted emails with templates and personalization
    
    Handles template rendering, personalization, compliance,
    and proper formatting for SendGrid delivery.
    """
    
    def __init__(self):
        """Initialize email builder"""
        self.jinja_env = Environment(loader=BaseLoader())
        self.templates = {}
        self.default_from_email = os.getenv('SENDGRID_FROM_EMAIL', 'noreply@leadfactory.com')
        self.default_from_name = os.getenv('SENDGRID_FROM_NAME', 'LeadFactory')
        
        # Load default templates
        self._load_default_templates()
        
        logger.info("Email builder initialized")
    
    def _load_default_templates(self):
        """Load default email templates"""
        
        # Cold outreach template
        self.templates['cold_outreach'] = EmailTemplate(
            name='cold_outreach',
            subject_template='Website Performance Insights for {{ business_name }}',
            html_template='''
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{{ subject }}</title>
</head>
<body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333; max-width: 600px; margin: 0 auto; padding: 20px;">
    <div style="background-color: #f8f9fa; padding: 20px; border-radius: 8px; margin-bottom: 20px;">
        <h2 style="color: #2c3e50; margin-top: 0;">Website Performance Insights</h2>
        {% if contact_first_name %}
        <p>Hi {{ contact_first_name }},</p>
        {% else %}
        <p>Hi there,</p>
        {% endif %}
        
        <p>I was analyzing {{ business_name }}'s website and found several areas for improvement that could help you attract more customers and increase conversions.</p>
        
        {% if issues_found %}
        <h3 style="color: #34495e;">Key Issues Found:</h3>
        <ul>
        {% for issue in issues_found %}
            <li style="margin-bottom: 10px;">
                <strong style="color: #d73527;">{{ issue.title }}</strong><br>
                <em>Improvement: {{ issue.suggestion }}</em>
            </li>
        {% endfor %}
        </ul>
        {% endif %}
        
        {% if assessment_score %}
        <div style="background-color: #fff3cd; padding: 15px; border-radius: 5px; margin: 20px 0;">
            <p style="margin: 0;"><strong>Current Performance Score: {{ assessment_score }}/100</strong></p>
            <p style="margin: 5px 0 0 0;">There's significant room for improvement that could drive more traffic and sales.</p>
        </div>
        {% endif %}
        
        <div style="background-color: #e3f2fd; padding: 15px; border-radius: 5px; margin: 20px 0;">
            <p style="margin: 0;"><strong>Next Steps:</strong></p>
            <p style="margin: 5px 0 0 0;">Would you be interested in a free 15-minute consultation to discuss how we can improve {{ business_name }}'s online performance?</p>
        </div>
        
        <div style="text-align: center; margin: 30px 0;">
            <a href="mailto:{{ reply_to_email }}?subject=Website%20Consultation%20for%20{{ business_name | urlencode }}" 
               style="background-color: #3498db; color: white; padding: 12px 24px; text-decoration: none; border-radius: 5px; display: inline-block;">
                Schedule Free Consultation
            </a>
        </div>
        
        <p style="color: #7f8c8d; font-size: 14px; border-top: 1px solid #ecf0f1; padding-top: 15px; margin-top: 20px;">
            Best regards,<br>
            The Website Performance Team
        </p>
    </div>
</body>
</html>
            ''',
            text_template='''
Hi {% if contact_first_name %}{{ contact_first_name }}{% else %}there{% endif %},

I was analyzing {{ business_name }}'s website and found several areas for improvement that could help you attract more customers and increase conversions.

{% if issues_found %}
Key Issues Found:
{% for issue in issues_found %}
- {{ issue.title }}: {{ issue.suggestion }}
{% endfor %}
{% endif %}

{% if assessment_score %}
Current Performance Score: {{ assessment_score }}/100
There's significant room for improvement that could drive more traffic and sales.
{% endif %}

Next Steps:
Would you be interested in a free 15-minute consultation to discuss how we can improve {{ business_name }}'s online performance?

To schedule, simply reply to this email or contact us at {{ reply_to_email }}.

Best regards,
The Website Performance Team
            ''',
            default_categories=['cold_outreach', 'website_audit', 'leadfactory'],
            default_custom_args={
                'template': 'cold_outreach',
                'campaign_type': 'website_audit'
            }
        )
        
        # Follow-up template
        self.templates['follow_up'] = EmailTemplate(
            name='follow_up',
            subject_template='Following up on {{ business_name }} website insights',
            html_template='''
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{{ subject }}</title>
</head>
<body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333; max-width: 600px; margin: 0 auto; padding: 20px;">
    <div style="background-color: #f8f9fa; padding: 20px; border-radius: 8px;">
        {% if contact_first_name %}
        <p>Hi {{ contact_first_name }},</p>
        {% else %}
        <p>Hi there,</p>
        {% endif %}
        
        <p>I wanted to follow up on the website performance insights I shared for {{ business_name }}.</p>
        
        <p>Many businesses see a 20-40% increase in conversions after addressing the key issues we identified. The improvements are often straightforward to implement and can start delivering results quickly.</p>
        
        <p>If you're interested in discussing how to improve {{ business_name }}'s online performance, I'd be happy to arrange a brief consultation at your convenience.</p>
        
        <div style="text-align: center; margin: 30px 0;">
            <a href="mailto:{{ reply_to_email }}?subject=Website%20Consultation%20for%20{{ business_name | urlencode }}" 
               style="background-color: #27ae60; color: white; padding: 12px 24px; text-decoration: none; border-radius: 5px; display: inline-block;">
                Let's Talk
            </a>
        </div>
        
        <p style="color: #7f8c8d; font-size: 14px;">
            Best regards,<br>
            The Website Performance Team
        </p>
    </div>
</body>
</html>
            ''',
            text_template='''
Hi {% if contact_first_name %}{{ contact_first_name }}{% else %}there{% endif %},

I wanted to follow up on the website performance insights I shared for {{ business_name }}.

Many businesses see a 20-40% increase in conversions after addressing the key issues we identified. The improvements are often straightforward to implement and can start delivering results quickly.

If you're interested in discussing how to improve {{ business_name }}'s online performance, I'd be happy to arrange a brief consultation at your convenience.

To schedule, simply reply to this email or contact us at {{ reply_to_email }}.

Best regards,
The Website Performance Team
            ''',
            default_categories=['follow_up', 'website_audit', 'leadfactory'],
            default_custom_args={
                'template': 'follow_up',
                'campaign_type': 'follow_up'
            }
        )
    
    def build_email(
        self,
        template_name: str,
        personalization: PersonalizationData,
        to_email: str,
        to_name: Optional[str] = None,
        from_email: Optional[str] = None,
        from_name: Optional[str] = None,
        additional_categories: Optional[List[str]] = None,
        additional_custom_args: Optional[Dict[str, Any]] = None,
        reply_to_email: Optional[str] = None,
        reply_to_name: Optional[str] = None
    ) -> EmailData:
        """
        Build an email using a template and personalization data
        
        Args:
            template_name: Name of template to use
            personalization: Personalization data
            to_email: Recipient email
            to_name: Recipient name
            from_email: Sender email (optional)
            from_name: Sender name (optional)
            additional_categories: Extra categories to add
            additional_custom_args: Extra custom args to add
            reply_to_email: Reply-to email (optional)
            reply_to_name: Reply-to name (optional)
            
        Returns:
            EmailData object ready for SendGrid
        """
        if template_name not in self.templates:
            raise ValueError(f"Template '{template_name}' not found")
        
        template = self.templates[template_name]
        
        # Prepare template context
        context = {
            'business_name': personalization.business_name,
            'contact_name': personalization.contact_name,
            'contact_first_name': personalization.contact_first_name or self._extract_first_name(personalization.contact_name),
            'business_category': personalization.business_category,
            'business_location': personalization.business_location,
            'issues_found': personalization.issues_found,
            'assessment_score': personalization.assessment_score,
            'reply_to_email': reply_to_email or self.default_from_email,
            **personalization.custom_data
        }
        
        # Render templates
        subject = self._render_template(template.subject_template, context)
        html_content = self._render_template(template.html_template, context)
        text_content = None
        
        if template.text_template:
            text_content = self._render_template(template.text_template, context)
        
        # Add subject to context for HTML template
        context['subject'] = subject
        html_content = self._render_template(template.html_template, context)
        
        # Build categories
        categories = template.default_categories.copy()
        if additional_categories:
            categories.extend(additional_categories)
        
        # Remove duplicates and limit to 10 (SendGrid limit)
        categories = list(set(categories))[:10]
        
        # Build custom args
        custom_args = template.default_custom_args.copy()
        if additional_custom_args:
            custom_args.update(additional_custom_args)
        
        # Add tracking data
        custom_args.update({
            'business_name': personalization.business_name,
            'template_name': template_name,
            'generated_at': datetime.now(timezone.utc).isoformat(),
            'personalization_id': str(uuid.uuid4())
        })
        
        # Create EmailData
        return EmailData(
            to_email=to_email,
            to_name=to_name or personalization.contact_name,
            from_email=from_email or self.default_from_email,
            from_name=from_name or self.default_from_name,
            subject=subject,
            html_content=html_content,
            text_content=text_content,
            categories=categories,
            custom_args=custom_args,
            reply_to_email=reply_to_email,
            reply_to_name=reply_to_name
        )
    
    def _render_template(self, template_str: str, context: Dict[str, Any]) -> str:
        """
        Render a Jinja2 template with context
        
        Args:
            template_str: Template string
            context: Template context
            
        Returns:
            Rendered template string
        """
        try:
            template = self.jinja_env.from_string(template_str)
            rendered = template.render(**context)
            
            # Clean up whitespace
            rendered = re.sub(r'\n\s*\n\s*\n', '\n\n', rendered)  # Remove excessive newlines
            rendered = rendered.strip()
            
            return rendered
            
        except Exception as e:
            logger.error(f"Template rendering error: {e}")
            raise ValueError(f"Template rendering failed: {str(e)}")
    
    def _extract_first_name(self, full_name: Optional[str]) -> Optional[str]:
        """
        Extract first name from full name
        
        Args:
            full_name: Full name string
            
        Returns:
            First name or None
        """
        if not full_name:
            return None
        
        # Split on whitespace and take first part
        parts = full_name.strip().split()
        if parts:
            return parts[0].title()
        
        return None
    
    def add_template(self, template: EmailTemplate):
        """
        Add a custom email template
        
        Args:
            template: EmailTemplate object to add
        """
        self.templates[template.name] = template
        logger.info(f"Added email template: {template.name}")
    
    def get_template_names(self) -> List[str]:
        """
        Get list of available template names
        
        Returns:
            List of template names
        """
        return list(self.templates.keys())
    
    def validate_template(self, template_name: str, sample_data: PersonalizationData) -> Dict[str, Any]:
        """
        Validate a template by rendering it with sample data
        
        Args:
            template_name: Name of template to validate
            sample_data: Sample personalization data
            
        Returns:
            Validation results dict
        """
        try:
            email = self.build_email(
                template_name=template_name,
                personalization=sample_data,
                to_email="test@example.com"
            )
            
            return {
                'valid': True,
                'subject_length': len(email.subject),
                'html_length': len(email.html_content) if email.html_content else 0,
                'text_length': len(email.text_content) if email.text_content else 0,
                'categories_count': len(email.categories) if email.categories else 0,
                'custom_args_count': len(email.custom_args) if email.custom_args else 0
            }
            
        except Exception as e:
            return {
                'valid': False,
                'error': str(e)
            }


# Utility functions

def create_personalization_data(
    business_name: str,
    contact_name: Optional[str] = None,
    **kwargs
) -> PersonalizationData:
    """
    Factory function to create PersonalizationData objects
    
    Args:
        business_name: Business name (required)
        contact_name: Contact name (optional)
        **kwargs: Additional PersonalizationData fields
        
    Returns:
        PersonalizationData object
    """
    return PersonalizationData(
        business_name=business_name,
        contact_name=contact_name,
        **kwargs
    )


def build_audit_email(
    business_name: str,
    to_email: str,
    contact_name: Optional[str] = None,
    issues: Optional[List[Dict[str, str]]] = None,
    score: Optional[float] = None,
    template: str = 'cold_outreach',
    **kwargs
) -> EmailData:
    """
    Convenience function to build a website audit email
    
    Args:
        business_name: Business name
        to_email: Recipient email
        contact_name: Contact name (optional)
        issues: List of issues found (optional)
        score: Assessment score (optional)
        template: Template name to use
        **kwargs: Additional arguments
        
    Returns:
        EmailData object ready for SendGrid
    """
    builder = EmailBuilder()
    
    personalization = PersonalizationData(
        business_name=business_name,
        contact_name=contact_name,
        issues_found=issues or [],
        assessment_score=score
    )
    
    return builder.build_email(
        template_name=template,
        personalization=personalization,
        to_email=to_email,
        **kwargs
    )


def escape_html_content(content: str) -> str:
    """
    Escape HTML content for safe inclusion in emails
    
    Args:
        content: Raw content to escape
        
    Returns:
        HTML-escaped content
    """
    return html.escape(content)


def extract_email_preview(html_content: str, max_length: int = 150) -> str:
    """
    Extract preview text from HTML email content
    
    Args:
        html_content: HTML email content
        max_length: Maximum preview length
        
    Returns:
        Plain text preview
    """
    # Remove HTML tags
    text = re.sub(r'<[^>]+>', ' ', html_content)
    
    # Clean up whitespace
    text = re.sub(r'\s+', ' ', text).strip()
    
    # Truncate to max length
    if len(text) > max_length:
        text = text[:max_length].rsplit(' ', 1)[0] + '...'
    
    return text