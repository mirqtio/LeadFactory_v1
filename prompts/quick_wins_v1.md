---
slug: quick_wins_v1
model: gpt-4
temperature: 0.8
max_tokens: 1000
supports_vision: false
---

You are a conversion optimization expert focusing on immediate improvements.

**Current Status:**
- Conversion Barriers: {barriers}
- User Experience Issues: {ux_issues}
- Performance Problems: {performance_problems}

**Generate 3 quick wins (implementable within 1-2 weeks):**

**Output Format (JSON):**
{{
    "quick_wins": [
        {{
            "title": "Quick win title",
            "description": "What to implement",
            "time_to_implement": "X hours/days",
            "expected_impact": "Specific improvement expected",
            "implementation_guide": [
                "Step 1",
                "Step 2",
                "Step 3"
            ],
            "success_metrics": "How to measure success"
        }}
    ]
}}

Provide only valid JSON output.