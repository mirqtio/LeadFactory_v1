"""
LLM Prompts for Insight Generation - Task 033

Structured prompts for generating website insights, recommendations,
and industry-specific analysis.

Acceptance Criteria:
- 3 recommendations generated
- Industry-specific insights
- Cost tracking works
- Structured output parsing
"""


class InsightPrompts:
    """Collection of prompts for LLM insight generation"""

    WEBSITE_ANALYSIS_PROMPT = """
You are an expert web analyst providing actionable insights for business websites.

Analyze the following website data and provide exactly 3 specific, actionable recommendations.

**Website Information:**
- URL: {url}
- Industry: {industry}
- Performance Score: {performance_score}/100
- Accessibility Score: {accessibility_score}/100
- SEO Score: {seo_score}/100
- Technologies Detected: {technologies}

**PageSpeed Metrics:**
- Largest Contentful Paint: {lcp}ms
- First Input Delay: {fid}ms
- Cumulative Layout Shift: {cls}
- Speed Index: {speed_index}ms

**Key Issues:**
{top_issues}

**Requirements:**
1. Provide exactly 3 recommendations
2. Focus on {industry} industry best practices
3. Prioritize by business impact
4. Include specific implementation steps
5. Estimate effort level (Low/Medium/High)

**Output Format (JSON):**
{{
    "recommendations": [
        {{
            "title": "Specific recommendation title",
            "description": "Detailed description with industry context",
            "priority": "High|Medium|Low",
            "effort": "Low|Medium|High",
            "impact": "Description of business impact",
            "implementation_steps": [
                "Step 1: Specific action",
                "Step 2: Specific action"
            ],
            "industry_context": "How this applies to {industry} specifically"
        }}
    ],
    "industry_insights": {{
        "industry": "{industry}",
        "benchmarks": {{
            "performance_percentile": "Your site vs {industry} average",
            "key_metrics": "Industry-specific metrics analysis"
        }},
        "competitive_advantage": "How improvements provide edge",
        "compliance_notes": "Industry regulations or standards"
    }},
    "summary": {{
        "overall_health": "Brief assessment",
        "quick_wins": "Top 2 immediate actions",
        "long_term_strategy": "Strategic recommendations"
    }}
}}

Provide only valid JSON output."""

    TECHNICAL_ANALYSIS_PROMPT = """
You are a technical web performance expert analyzing website optimization opportunities.

**Technical Data:**
- Core Web Vitals: LCP {lcp}ms, FID {fid}ms, CLS {cls}
- Performance Issues: {performance_issues}
- Technology Stack: {tech_stack}
- Hosting Platform: {hosting}

**Analysis Focus:**
1. Technical performance optimization
2. Infrastructure recommendations
3. Technology stack improvements

**Required Output (JSON):**
{{
    "technical_recommendations": [
        {{
            "category": "Performance|Infrastructure|Technology",
            "title": "Technical recommendation",
            "description": "Detailed technical explanation",
            "implementation": "How to implement",
            "expected_improvement": "Specific metrics improvement"
        }}
    ],
    "infrastructure_insights": {{
        "current_setup": "Analysis of current stack",
        "optimization_opportunities": "Specific technical improvements",
        "modernization_path": "Technology upgrade recommendations"
    }}
}}

Provide only valid JSON output."""

    INDUSTRY_BENCHMARK_PROMPT = """
You are an industry analyst providing competitive benchmarking insights.

**Website Performance:**
- Overall Score: {overall_score}/100
- Industry: {industry}
- Key Metrics: {metrics}

**Analysis Requirements:**
1. Compare against {industry} industry standards
2. Identify competitive advantages/disadvantages
3. Suggest industry-specific optimizations

**Output Format (JSON):**
{{
    "benchmark_analysis": {{
        "industry": "{industry}",
        "performance_vs_industry": {{
            "percentile": "Top/Middle/Bottom 25%",
            "key_strengths": ["Strength 1", "Strength 2"],
            "improvement_areas": ["Area 1", "Area 2"]
        }},
        "industry_specific_insights": [
            {{
                "insight": "Industry-specific observation",
                "implication": "What this means for business",
                "action": "Recommended action"
            }}
        ],
        "competitive_analysis": {{
            "advantages": "Where site excels vs industry",
            "gaps": "Where competitors likely perform better",
            "differentiation_opportunities": "Unique positioning options"
        }}
    }}
}}

Provide only valid JSON output."""

    QUICK_WINS_PROMPT = """
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

Provide only valid JSON output."""

    @staticmethod
    def get_industry_context(industry: str) -> dict:
        """Get industry-specific context for prompts"""
        industry_contexts = {
            "ecommerce": {
                "key_metrics": ["conversion_rate", "cart_abandonment", "page_load_time"],
                "compliance": ["PCI DSS", "GDPR", "accessibility"],
                "benchmarks": {"performance_score": 85, "lcp": 2500, "cls": 0.1}
            },
            "healthcare": {
                "key_metrics": ["trust_signals", "accessibility", "mobile_performance"],
                "compliance": ["HIPAA", "accessibility", "mobile_first"],
                "benchmarks": {"performance_score": 90, "accessibility_score": 95, "lcp": 2000}
            },
            "finance": {
                "key_metrics": ["security", "trust", "performance", "mobile"],
                "compliance": ["SOX", "PCI DSS", "security_headers", "SSL"],
                "benchmarks": {"performance_score": 92, "security_score": 98, "lcp": 1800}
            },
            "education": {
                "key_metrics": ["accessibility", "mobile_performance", "content_readability"],
                "compliance": ["WCAG 2.1 AA", "FERPA", "accessibility"],
                "benchmarks": {"accessibility_score": 95, "performance_score": 85, "mobile_score": 90}
            },
            "nonprofit": {
                "key_metrics": ["engagement", "mobile_performance", "donation_conversion"],
                "compliance": ["accessibility", "transparency", "donor_privacy"],
                "benchmarks": {"performance_score": 80, "accessibility_score": 90, "seo_score": 85}
            },
            "technology": {
                "key_metrics": ["performance", "innovation", "developer_experience"],
                "compliance": ["technical_standards", "API_performance", "security"],
                "benchmarks": {"performance_score": 95, "lcp": 1500, "technical_score": 92}
            },
            "professional_services": {
                "key_metrics": ["trust_signals", "contact_conversion", "mobile_experience"],
                "compliance": ["professional_standards", "client_confidentiality"],
                "benchmarks": {"seo_score": 88, "performance_score": 85, "trust_score": 90}
            },
            "retail": {
                "key_metrics": ["product_discovery", "checkout_flow", "mobile_commerce"],
                "compliance": ["payment_security", "consumer_protection", "accessibility"],
                "benchmarks": {"performance_score": 87, "mobile_score": 90, "conversion_rate": 2.5}
            },
            "manufacturing": {
                "key_metrics": ["b2b_functionality", "technical_content", "lead_generation"],
                "compliance": ["industry_standards", "technical_compliance"],
                "benchmarks": {"performance_score": 82, "b2b_optimization": 85, "technical_seo": 88}
            },
            "default": {
                "key_metrics": ["performance", "user_experience", "seo"],
                "compliance": ["basic_accessibility", "privacy"],
                "benchmarks": {"performance_score": 85, "accessibility_score": 85, "seo_score": 85}
            }
        }
        
        return industry_contexts.get(industry.lower(), industry_contexts["default"])

    @staticmethod
    def format_technologies(tech_stack: list) -> str:
        """Format technology stack for prompt inclusion"""
        if not tech_stack:
            return "None detected"
        
        tech_by_category = {}
        for tech in tech_stack:
            category = tech.get('category', 'Other')
            if category not in tech_by_category:
                tech_by_category[category] = []
            tech_by_category[category].append(tech.get('technology_name', 'Unknown'))
        
        formatted = []
        for category, technologies in tech_by_category.items():
            tech_list = ', '.join(technologies[:3])  # Limit to first 3 per category
            formatted.append(f"{category}: {tech_list}")
        
        return '; '.join(formatted)

    @staticmethod
    def format_issues(issues: list, limit: int = 5) -> str:
        """Format performance issues for prompt inclusion"""
        if not issues:
            return "No significant issues detected"
        
        formatted_issues = []
        for issue in issues[:limit]:
            impact = issue.get('impact', 'Unknown')
            title = issue.get('title', 'Unknown issue')
            savings = issue.get('savings_ms', 0)
            
            if savings > 0:
                formatted_issues.append(f"• {title} (Impact: {impact}, Saves: {savings}ms)")
            else:
                formatted_issues.append(f"• {title} (Impact: {impact})")
        
        return '\n'.join(formatted_issues)

    @staticmethod
    def get_prompt_variables(assessment_data: dict, industry: str = "default") -> dict:
        """Extract and format variables for prompt templates"""
        tech_stack = assessment_data.get('tech_stack', [])
        performance_issues = assessment_data.get('performance_issues', [])
        
        return {
            'url': assessment_data.get('url', 'Unknown'),
            'industry': industry,
            'performance_score': assessment_data.get('performance_score', 0),
            'accessibility_score': assessment_data.get('accessibility_score', 0),
            'seo_score': assessment_data.get('seo_score', 0),
            'lcp': assessment_data.get('largest_contentful_paint', 0),
            'fid': assessment_data.get('first_input_delay', 0),
            'cls': assessment_data.get('cumulative_layout_shift', 0),
            'speed_index': assessment_data.get('speed_index', 0),
            'technologies': InsightPrompts.format_technologies(tech_stack),
            'top_issues': InsightPrompts.format_issues(performance_issues),
            'tech_stack': InsightPrompts.format_technologies(tech_stack),
            'hosting': InsightPrompts._extract_hosting(tech_stack),
            'overall_score': InsightPrompts._calculate_overall_score(assessment_data),
            'metrics': InsightPrompts._format_key_metrics(assessment_data),
            'barriers': InsightPrompts._identify_conversion_barriers(assessment_data),
            'ux_issues': InsightPrompts._identify_ux_issues(assessment_data),
            'performance_problems': InsightPrompts._format_performance_problems(performance_issues),
            'performance_issues': InsightPrompts.format_issues(performance_issues)
        }

    @staticmethod
    def _extract_hosting(tech_stack: list) -> str:
        """Extract hosting platform from tech stack"""
        hosting_techs = [tech for tech in tech_stack if tech.get('category') == 'hosting']
        if hosting_techs:
            return hosting_techs[0].get('technology_name', 'Unknown')
        return "Not detected"

    @staticmethod
    def _calculate_overall_score(assessment_data: dict) -> int:
        """Calculate overall website score"""
        scores = [
            assessment_data.get('performance_score', 0),
            assessment_data.get('accessibility_score', 0),
            assessment_data.get('seo_score', 0),
            assessment_data.get('best_practices_score', 0)
        ]
        valid_scores = [s for s in scores if s > 0]
        return int(sum(valid_scores) / len(valid_scores)) if valid_scores else 0

    @staticmethod
    def _format_key_metrics(assessment_data: dict) -> str:
        """Format key performance metrics"""
        metrics = []
        if assessment_data.get('largest_contentful_paint'):
            metrics.append(f"LCP: {assessment_data['largest_contentful_paint']}ms")
        if assessment_data.get('first_input_delay'):
            metrics.append(f"FID: {assessment_data['first_input_delay']}ms")
        if assessment_data.get('cumulative_layout_shift'):
            metrics.append(f"CLS: {assessment_data['cumulative_layout_shift']}")
        return ', '.join(metrics) if metrics else "No core metrics available"

    @staticmethod
    def _identify_conversion_barriers(assessment_data: dict) -> str:
        """Identify potential conversion barriers"""
        barriers = []
        
        if assessment_data.get('largest_contentful_paint', 0) > 4000:
            barriers.append("Slow page loading (4+ seconds)")
        
        if assessment_data.get('accessibility_score', 100) < 85:
            barriers.append("Accessibility issues limiting user access")
        
        if assessment_data.get('performance_score', 100) < 75:
            barriers.append("Poor performance impacting user experience")
        
        return '; '.join(barriers) if barriers else "No major barriers identified"

    @staticmethod
    def _identify_ux_issues(assessment_data: dict) -> str:
        """Identify user experience issues"""
        ux_issues = []
        
        if assessment_data.get('cumulative_layout_shift', 0) > 0.25:
            ux_issues.append("Layout instability (high CLS)")
        
        if assessment_data.get('first_input_delay', 0) > 300:
            ux_issues.append("Slow interactivity (high FID)")
        
        mobile_score = assessment_data.get('mobile_performance_score', 100)
        if mobile_score < 80:
            ux_issues.append("Poor mobile experience")
        
        return '; '.join(ux_issues) if ux_issues else "No major UX issues identified"

    @staticmethod
    def _format_performance_problems(issues: list) -> str:
        """Format performance problems for prompts"""
        if not issues:
            return "No significant performance problems"
        
        problems = []
        for issue in issues[:3]:  # Top 3 issues
            title = issue.get('title', 'Unknown')
            impact = issue.get('impact', 'unknown')
            problems.append(f"{title} ({impact} impact)")
        
        return '; '.join(problems)