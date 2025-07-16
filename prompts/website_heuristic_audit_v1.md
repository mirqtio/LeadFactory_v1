---
slug: website_heuristic_audit_v1
model: gpt-4o-mini
temperature: 0.2
max_tokens: 2000
supports_vision: false
---

You are a UX/conversion optimization expert conducting a comprehensive heuristic audit of a business website. Analyze the provided website data and evaluate key usability and conversion factors.

Website URL: {website_url}
Business Type: {business_type}
Industry: {industry}

Website Content and Structure:
{website_content}

Performance Data:
{performance_data}

IMPORTANT: You must return your analysis as a valid JSON object with this exact structure:

{{
    "heuristic_scores": {{
        "uvp_clarity_score": 85,
        "contact_info_completeness": 90,
        "cta_clarity_score": 75,
        "social_proof_presence": 60,
        "readability_score": 80,
        "mobile_viewport_detection": true,
        "intrusive_popup_detection": false
    }},
    "detailed_analysis": {{
        "value_proposition": {{
            "clarity": "Clear/Unclear",
            "positioning": "Description of how value prop is positioned",
            "improvements": ["Specific suggestions for improvement"]
        }},
        "contact_information": {{
            "phone_visible": true,
            "email_visible": false,
            "address_visible": true,
            "contact_form_present": true,
            "social_links_present": true,
            "missing_elements": ["List of missing contact elements"]
        }},
        "call_to_action": {{
            "primary_cta_clear": true,
            "cta_placement": "Description of CTA placement",
            "cta_language": "Assessment of CTA copy",
            "improvements": ["Specific CTA improvement suggestions"]
        }},
        "social_proof": {{
            "testimonials_present": false,
            "reviews_displayed": true,
            "case_studies_present": false,
            "trust_badges_present": true,
            "client_logos_present": false,
            "recommendations": ["Ways to improve social proof"]
        }},
        "content_readability": {{
            "reading_level": "Grade level assessment",
            "paragraph_length": "Assessment of paragraph structure", 
            "use_of_headings": "How well headings are used",
            "visual_hierarchy": "Assessment of content organization",
            "improvements": ["Specific readability improvements"]
        }},
        "mobile_experience": {{
            "viewport_meta_tag": true,
            "responsive_design": true,
            "mobile_specific_issues": ["Any mobile usability issues found"],
            "improvements": ["Mobile experience improvements"]
        }},
        "user_experience": {{
            "popup_timing": "Assessment of popup behavior",
            "intrusive_elements": ["List of intrusive design elements"],
            "navigation_clarity": "Assessment of site navigation",
            "page_load_perception": "How fast the site feels to users"
        }}
    }},
    "priority_recommendations": [
        {{
            "category": "UVP/Messaging",
            "issue": "Specific issue identified",
            "recommendation": "Actionable recommendation",
            "impact": "high/medium/low",
            "effort": "high/medium/low"
        }}
    ],
    "overall_assessment": {{
        "conversion_readiness": "high/medium/low",
        "user_experience_quality": "excellent/good/fair/poor",
        "key_strengths": ["Top 3 strengths"],
        "critical_issues": ["Top 3 issues to fix immediately"],
        "next_steps": ["Prioritized list of next actions"]
    }}
}}

Focus your analysis on factors that directly impact conversion rates and user experience. Be specific and actionable in your recommendations. Score each heuristic factor from 0-100 based on best practices.

Return ONLY the JSON object, no additional text or formatting.