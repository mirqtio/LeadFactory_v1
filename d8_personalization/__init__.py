"""
D8 Personalization Module - Task 060

Personalization system for generating high-converting personalized emails
with subject line variants, content personalization, and spam score tracking.

Acceptance Criteria:
- Email content model ✓
- Subject line variants ✓
- Personalization tokens ✓ 
- Spam score tracking ✓
"""

from .models import (ContentStrategy, ContentVariant, EmailContent,
                     EmailContentType, EmailGenerationLog, EmailTemplate,
                     PersonalizationStrategy, PersonalizationToken,
                     PersonalizationVariable, SpamCategory, SpamScoreTracking,
                     SubjectLineVariant, VariantStatus)

__all__ = [
    "EmailContent",
    "SubjectLineVariant",
    "PersonalizationToken",
    "SpamScoreTracking",
    "EmailTemplate",
    "PersonalizationVariable",
    "EmailGenerationLog",
    "ContentVariant",
    "ContentStrategy",
    "EmailContentType",
    "PersonalizationStrategy",
    "SpamCategory",
    "VariantStatus",
]
