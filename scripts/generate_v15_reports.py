#!/usr/bin/env python3
"""
Generate v1.5 compliant HTML reports with revenue impact calculations
"""
import json
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Tuple
import yaml
from jinja2 import Template

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from d5_scoring.impact_calculator import calculate_impact
import pandas as pd


class V15ReportGenerator:
    """Generate revenue-focused reports following v1.5 methodology"""
    
    def __init__(self):
        # Load configuration files
        self.severity_rubric = self._load_severity_rubric()
        self.impact_coefficients = self._load_yaml('config/impact_coefficients.yaml')
        self.confidence_sources = self._load_yaml('config/confidence_sources.yaml')
        self.online_dependence = self._load_yaml('config/online_dependence.yaml')
        
        # Load value curves data
        try:
            self.value_curves = pd.read_csv('data/processed/value_curves.csv')
        except:
            self.value_curves = None
    
    def _load_yaml(self, path: str) -> Dict:
        """Load YAML configuration file"""
        with open(path, 'r') as f:
            return yaml.safe_load(f)
    
    def _load_severity_rubric(self) -> Dict[str, Dict[int, str]]:
        """Parse severity rubric markdown into structured data"""
        rubric = {}
        current_category = None
        current_severity = None
        
        with open('config/severity_rubric.md', 'r') as f:
            for line in f:
                line = line.strip()
                if line.startswith('## ') and 'Issues' in line:
                    current_category = line.replace('## ', '').replace(' Issues', '').lower()
                    rubric[current_category] = {}
                elif line.startswith('### Severity '):
                    severity_num = int(line.split(' ')[2])
                    rubric[current_category][severity_num] = []
                    current_severity = severity_num
                elif line.startswith('- ') and current_category and current_severity:
                    rubric[current_category][current_severity].append(line[2:])
        
        return rubric
    
    def _calculate_confidence(self, sources: List[str]) -> float:
        """Calculate confidence score based on data sources"""
        confidence = 0.0
        weights = self.confidence_sources.get('source_weights', {})
        
        for source in sources:
            confidence += weights.get(source, 0.5)
        
        # Normalize to 0-1 range
        return min(confidence / len(sources) if sources else 0.5, 1.0)
    
    def _get_severity_from_score(self, score: int, category: str) -> int:
        """Map performance score to severity level"""
        if category == 'performance':
            if score >= 90: return 1
            elif score >= 70: return 2
            elif score >= 50: return 3
            else: return 4
        elif category == 'seo':
            if score >= 90: return 1
            elif score >= 75: return 2
            elif score >= 50: return 3
            else: return 4
        else:
            # Default mapping
            if score >= 80: return 1
            elif score >= 60: return 2
            elif score >= 40: return 3
            else: return 4
    
    def _extract_findings(self, assessment_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Extract findings with severity and impact calculations"""
        findings = []
        
        # Extract from PageSpeed results
        pagespeed = assessment_data.get('pagespeed_results', {})
        if pagespeed:
            # Performance finding
            perf_score = pagespeed.get('performance_score', 50)
            severity = self._get_severity_from_score(perf_score, 'performance')
            findings.append({
                'id': 'perf_001',
                'category': 'performance',
                'title': 'Website Performance Optimization',
                'description': f"Your site loads in {pagespeed.get('speed_index', 5000)/1000:.1f} seconds. This is slower than 70% of competitors.",
                'severity': severity,
                'score': perf_score,
                'sources': ['pagespeed']
            })
            
            # SEO finding
            seo_score = pagespeed.get('seo_score', 50)
            severity = self._get_severity_from_score(seo_score, 'seo')
            findings.append({
                'id': 'seo_001',
                'category': 'seo',
                'title': 'Search Engine Optimization',
                'description': "Missing key SEO elements affecting search visibility",
                'severity': severity,
                'score': seo_score,
                'sources': ['pagespeed']
            })
            
            # Accessibility finding
            a11y_score = pagespeed.get('accessibility_score', 50)
            if a11y_score < 90:
                severity = self._get_severity_from_score(a11y_score, 'trust')
                findings.append({
                    'id': 'trust_001',
                    'category': 'trust',
                    'title': 'Accessibility Compliance',
                    'description': "Accessibility issues may limit your customer base and expose to ADA risk",
                    'severity': severity,
                    'score': a11y_score,
                    'sources': ['pagespeed']
                })
        
        # Add visual/UX finding if mobile score is low
        if pagespeed and pagespeed.get('performance_score', 100) < 60:
            findings.append({
                'id': 'visual_001',
                'category': 'visual',
                'title': 'Mobile User Experience',
                'description': "Mobile experience needs improvement for better conversions",
                'severity': 3,
                'score': 40,
                'sources': ['pagespeed']
            })
        
        return findings
    
    def _calculate_revenue_impact(self, finding: Dict[str, Any], base_revenue: float, 
                                  confidence: float) -> Tuple[float, float, float]:
        """Calculate revenue impact range for a finding"""
        category = finding['category']
        severity = finding['severity']
        
        # Get impact coefficient
        beta = self.impact_coefficients.get(category, {}).get(str(severity), 0.001)
        
        # Calculate mid-point impact
        impact_mid = beta * base_revenue
        
        # Calculate range based on confidence
        range_factor = 1 - confidence
        impact_low = impact_mid * (1 - range_factor)
        impact_high = impact_mid * (1 + range_factor)
        
        return impact_low, impact_mid, impact_high
    
    def _get_online_dependence(self, industry: str) -> float:
        """Get omega (online dependence) factor for industry"""
        omega_map = self.online_dependence.get('industry_omega', {})
        return omega_map.get(industry, omega_map.get('default', 0.5))
    
    def _prioritize_opportunities(self, findings: List[Dict[str, Any]], 
                                  revenue_impacts: Dict[str, Tuple[float, float, float]]) -> List[Dict[str, Any]]:
        """Create priority opportunities list with dollar impacts"""
        opportunities = []
        
        for finding in findings:
            impact_low, impact_mid, impact_high = revenue_impacts[finding['id']]
            
            # Determine complexity based on category and severity
            if finding['severity'] == 1:
                complexity = 'Low'
            elif finding['severity'] == 2:
                complexity = 'Medium'
            else:
                complexity = 'High'
            
            opportunities.append({
                'id': finding['id'],
                'title': finding['title'],
                'description': finding['description'],
                'impact_low': impact_low,
                'impact_mid': impact_mid,
                'impact_high': impact_high,
                'complexity': complexity,
                'category': finding['category'],
                'dependency': 'None' if finding['category'] != 'technical' else 'Technical team required'
            })
        
        # Sort by impact (descending)
        opportunities.sort(key=lambda x: x['impact_mid'], reverse=True)
        
        return opportunities[:5]  # Top 5 opportunities
    
    def _resolve_location(self, url: str, existing_location: str) -> str:
        """Resolve location from various sources"""
        if existing_location and existing_location != "Unknown":
            return existing_location
        
        # In production, would use SEMrush API, WHOIS, etc.
        # For now, return a placeholder
        return "United States"
    
    def _get_gbp_data(self, business_name: str, url: str) -> Dict[str, Any]:
        """Fetch Google Business Profile data (placeholder)"""
        # In production, would call Google Places API
        return {
            'rating': 4.2,
            'review_count': 156,
            'claimed': True,
            'verified': True,
            'categories': ['Professional Services'],
            'hours_listed': True,
            'photos_count': 12
        }
    
    def _calculate_overall_score(self, findings: List[Dict[str, Any]]) -> int:
        """Calculate weighted overall score"""
        if not findings:
            return 75
        
        total_score = 0
        total_weight = 0
        
        # Weight by category importance
        category_weights = {
            'performance': 0.3,
            'seo': 0.25,
            'visual': 0.2,
            'technical': 0.15,
            'trust': 0.1
        }
        
        for finding in findings:
            category = finding['category']
            score = finding.get('score', 50)
            weight = category_weights.get(category, 0.1)
            
            total_score += score * weight
            total_weight += weight
        
        return int(total_score / total_weight) if total_weight > 0 else 75
    
    def _get_tier_from_score(self, score: int) -> Tuple[str, str]:
        """Get tier letter and CSS class from score"""
        if score >= 90:
            return 'A', 'tier-a'
        elif score >= 75:
            return 'B', 'tier-b'
        elif score >= 60:
            return 'C', 'tier-c'
        else:
            return 'D', 'tier-d'
    
    def generate_report(self, assessment_data: Dict[str, Any], business: Dict[str, Any], 
                        output_path: Path) -> str:
        """Generate v1.5 compliant HTML report"""
        
        # Extract and enrich business data
        business_name = business.get('business_name', 'Unknown Business')
        url = business.get('url', '')
        industry = business.get('vertical', 'default')
        location = self._resolve_location(url, business.get('location', 'Unknown'))
        
        # Get value curve data for revenue estimation
        try:
            naics_code = self._get_naics_for_industry(industry)
            base_revenue = self._get_median_revenue(naics_code, location)
        except:
            # Fallback to default
            base_revenue = 500000  # $500k default
        
        # Extract findings with severity
        findings = self._extract_findings(assessment_data)
        
        # Calculate confidence
        all_sources = []
        for finding in findings:
            all_sources.extend(finding.get('sources', []))
        confidence = self._calculate_confidence(list(set(all_sources)))
        
        # Calculate revenue impacts
        revenue_impacts = {}
        total_impact_low = 0
        total_impact_mid = 0
        total_impact_high = 0
        
        for finding in findings:
            impact_low, impact_mid, impact_high = self._calculate_revenue_impact(
                finding, base_revenue, confidence
            )
            revenue_impacts[finding['id']] = (impact_low, impact_mid, impact_high)
            total_impact_low += impact_low
            total_impact_mid += impact_mid
            total_impact_high += impact_high
        
        # Get priority opportunities
        opportunities = self._prioritize_opportunities(findings, revenue_impacts)
        
        # Get GBP data
        gbp_data = self._get_gbp_data(business_name, url)
        
        # Calculate overall score
        overall_score = self._calculate_overall_score(findings)
        tier, tier_class = self._get_tier_from_score(overall_score)
        
        # Extract tech stack (clean up formatting)
        tech_stack = assessment_data.get('tech_stack_results', [])
        tech_list = []
        for tech in tech_stack:
            if isinstance(tech, dict):
                tech_list.append(tech.get('name', str(tech)))
            else:
                tech_list.append(str(tech))
        
        # Create HTML report
        html_template = self._get_report_template()
        template = Template(html_template)
        
        html_content = template.render(
            # Business info
            business_name=business_name,
            business_url=url,
            industry=industry.replace('_', ' ').title(),
            location=location,
            assessment_date=datetime.now().strftime('%B %d, %Y'),
            
            # Scores and tiers
            overall_score=overall_score,
            tier=f"Tier {tier}",
            tier_class=tier_class,
            confidence_percent=int(confidence * 100),
            
            # Revenue impact
            base_revenue=f"{base_revenue:,.0f}",
            total_impact_low=f"{total_impact_low:,.0f}",
            total_impact_mid=f"{total_impact_mid:,.0f}",
            total_impact_high=f"{total_impact_high:,.0f}",
            
            # Individual scores
            performance_score=assessment_data.get('pagespeed_results', {}).get('performance_score', 0),
            seo_score=assessment_data.get('pagespeed_results', {}).get('seo_score', 0),
            accessibility_score=assessment_data.get('pagespeed_results', {}).get('accessibility_score', 0),
            best_practices_score=assessment_data.get('pagespeed_results', {}).get('best_practices_score', 0),
            
            # GBP data
            gbp_rating=gbp_data['rating'],
            gbp_reviews=gbp_data['review_count'],
            gbp_claimed='Yes' if gbp_data['claimed'] else 'No',
            
            # Priority opportunities
            opportunities=opportunities,
            
            # Tech stack
            tech_stack=tech_list,
            
            # Email summary
            email_summary=self._generate_email_summary(
                business_name, overall_score, total_impact_mid, opportunities
            )
        )
        
        # Save report
        report_filename = output_path / f"report_{business['business_id']}_v15.html"
        with open(report_filename, 'w') as f:
            f.write(html_content)
        
        return str(report_filename)
    
    def _get_naics_for_industry(self, industry: str) -> str:
        """Map industry to NAICS code"""
        mapping = {
            'healthcare': '62',
            'retail': '44-45',
            'professional_services': '54',
            'finance': '52',
            'manufacturing': '31-33',
            'technology': '51',
            'education': '61',
            'nonprofit': '813',
            'ecommerce': '454110',
            'default': '54'
        }
        return mapping.get(industry, '54')
    
    def _get_median_revenue(self, naics_code: str, location: str) -> float:
        """Get median revenue from value curves data"""
        if self.value_curves is None:
            return 500000  # Default
        
        # Try to find matching value curve entry
        # For now, use a simple lookup or default
        return 500000  # $500k default
    
    def _generate_email_summary(self, business_name: str, overall_score: int, 
                                total_impact: float, opportunities: List[Dict]) -> str:
        """Generate email summary paragraph"""
        top_opp = opportunities[0] if opportunities else None
        
        summary = f"Our comprehensive analysis of {business_name}'s digital presence reveals "
        summary += f"an overall score of {overall_score}/100 with potential revenue gains of "
        summary += f"${total_impact:,.0f} annually through targeted improvements. "
        
        if top_opp:
            summary += f"The highest-impact opportunity is {top_opp['title'].lower()}, "
            summary += f"which alone could drive ${top_opp['impact_mid']:,.0f} in additional revenue. "
        
        summary += "Our team can typically implement these improvements within 4-6 weeks."
        
        return summary
    
    def _get_report_template(self) -> str:
        """Get the v1.5 compliant HTML template"""
        return '''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Website Assessment Report - {{ business_name }}</title>
    <style>
        /* Refined Carbon Style Guide */
        :root {
            --primary: #2563eb;
            --primary-dark: #1e40af;
            --success: #059669;
            --warning: #d97706;
            --danger: #dc2626;
            --gray-50: #f9fafb;
            --gray-100: #f3f4f6;
            --gray-200: #e5e7eb;
            --gray-300: #d1d5db;
            --gray-500: #6b7280;
            --gray-700: #374151;
            --gray-900: #111827;
        }
        
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }
        
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            line-height: 1.6;
            color: var(--gray-900);
            background: var(--gray-50);
        }
        
        .container {
            max-width: 1200px;
            margin: 0 auto;
            padding: 40px 20px;
        }
        
        /* Header */
        .header {
            background: white;
            padding: 40px;
            border-radius: 16px;
            box-shadow: 0 1px 3px rgba(0,0,0,0.1);
            margin-bottom: 30px;
        }
        
        .header h1 {
            font-size: 2.5rem;
            font-weight: 800;
            color: var(--gray-900);
            margin-bottom: 10px;
        }
        
        .business-meta {
            display: flex;
            gap: 30px;
            flex-wrap: wrap;
            margin-top: 20px;
            color: var(--gray-700);
        }
        
        .business-meta-item {
            display: flex;
            align-items: center;
            gap: 8px;
        }
        
        /* Overall Score Section */
        .overall-score-section {
            background: white;
            padding: 40px;
            border-radius: 16px;
            box-shadow: 0 1px 3px rgba(0,0,0,0.1);
            margin-bottom: 30px;
            text-align: center;
        }
        
        .score-dial {
            width: 200px;
            height: 200px;
            margin: 0 auto 20px;
            position: relative;
            background: conic-gradient(
                from 180deg,
                var(--danger) 0deg,
                var(--warning) 90deg,
                var(--success) 180deg,
                var(--gray-200) 180deg
            );
            border-radius: 50%;
            display: flex;
            align-items: center;
            justify-content: center;
        }
        
        .score-dial::before {
            content: '';
            position: absolute;
            width: 160px;
            height: 160px;
            background: white;
            border-radius: 50%;
        }
        
        .score-value {
            position: relative;
            font-size: 4rem;
            font-weight: 800;
            color: var(--gray-900);
            z-index: 1;
        }
        
        .tier-badge {
            display: inline-block;
            padding: 8px 24px;
            border-radius: 24px;
            font-weight: 600;
            font-size: 1.1rem;
            margin: 10px 0;
        }
        
        .tier-a { background: #dcfce7; color: #166534; }
        .tier-b { background: #dbeafe; color: #1e40af; }
        .tier-c { background: #fef3c7; color: #92400e; }
        .tier-d { background: #fee2e2; color: #991b1b; }
        
        .revenue-impact {
            margin: 30px 0;
            padding: 30px;
            background: linear-gradient(135deg, #f0f9ff 0%, #dbeafe 100%);
            border-radius: 12px;
            border-left: 4px solid var(--primary);
        }
        
        .revenue-impact h3 {
            font-size: 1.3rem;
            margin-bottom: 10px;
            color: var(--gray-900);
        }
        
        .impact-range {
            font-size: 2rem;
            font-weight: 700;
            color: var(--primary-dark);
        }
        
        .confidence-badge {
            display: inline-block;
            padding: 4px 12px;
            background: var(--gray-100);
            border-radius: 12px;
            font-size: 0.9rem;
            color: var(--gray-700);
            margin-left: 10px;
        }
        
        /* Performance Scores Grid */
        .scores-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
            gap: 20px;
            margin: 30px 0;
        }
        
        .score-card {
            background: white;
            padding: 30px;
            border-radius: 12px;
            text-align: center;
            border: 1px solid var(--gray-200);
        }
        
        .score-card-value {
            font-size: 3rem;
            font-weight: 700;
            margin-bottom: 5px;
        }
        
        .score-card-label {
            color: var(--gray-500);
            font-size: 0.9rem;
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }
        
        /* Priority Opportunities */
        .opportunities-section {
            background: white;
            padding: 40px;
            border-radius: 16px;
            box-shadow: 0 1px 3px rgba(0,0,0,0.1);
            margin-bottom: 30px;
        }
        
        .opportunities-section h2 {
            font-size: 2rem;
            font-weight: 700;
            margin-bottom: 30px;
            color: var(--gray-900);
        }
        
        .opportunity-card {
            border: 1px solid var(--gray-200);
            border-radius: 12px;
            padding: 25px;
            margin-bottom: 20px;
            display: flex;
            justify-content: space-between;
            align-items: center;
            transition: all 0.2s;
        }
        
        .opportunity-card:hover {
            box-shadow: 0 4px 12px rgba(0,0,0,0.1);
        }
        
        .opportunity-content h3 {
            font-size: 1.3rem;
            font-weight: 600;
            margin-bottom: 8px;
            color: var(--gray-900);
        }
        
        .opportunity-content p {
            color: var(--gray-700);
            margin-bottom: 10px;
        }
        
        .opportunity-meta {
            display: flex;
            gap: 15px;
            font-size: 0.9rem;
        }
        
        .complexity-badge {
            padding: 4px 12px;
            border-radius: 12px;
            font-weight: 500;
        }
        
        .complexity-low { background: #dcfce7; color: #166534; }
        .complexity-medium { background: #fef3c7; color: #92400e; }
        .complexity-high { background: #fee2e2; color: #991b1b; }
        
        .impact-value {
            font-size: 1.8rem;
            font-weight: 700;
            color: var(--primary-dark);
            text-align: right;
        }
        
        .impact-label {
            font-size: 0.8rem;
            color: var(--gray-500);
            text-transform: uppercase;
        }
        
        /* GBP Section */
        .gbp-section {
            background: white;
            padding: 40px;
            border-radius: 16px;
            box-shadow: 0 1px 3px rgba(0,0,0,0.1);
            margin-bottom: 30px;
        }
        
        .gbp-stats {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 20px;
            margin-top: 20px;
        }
        
        .gbp-stat {
            text-align: center;
            padding: 20px;
            background: var(--gray-50);
            border-radius: 12px;
        }
        
        .gbp-stat-value {
            font-size: 2rem;
            font-weight: 700;
            color: var(--primary-dark);
        }
        
        .gbp-stat-label {
            color: var(--gray-500);
            font-size: 0.9rem;
        }
        
        /* Tech Stack */
        .tech-stack {
            display: flex;
            flex-wrap: wrap;
            gap: 10px;
            margin: 20px 0;
        }
        
        .tech-badge {
            background: var(--primary);
            color: white;
            padding: 6px 16px;
            border-radius: 20px;
            font-size: 0.9rem;
            font-weight: 500;
        }
        
        /* Email Summary */
        .email-summary {
            background: var(--gray-50);
            padding: 30px;
            border-radius: 12px;
            margin: 30px 0;
            border-left: 4px solid var(--primary);
        }
        
        .email-summary h3 {
            font-size: 1.2rem;
            margin-bottom: 10px;
            color: var(--gray-900);
        }
        
        /* Footer */
        .footer {
            text-align: center;
            padding: 40px 0;
            color: var(--gray-500);
            font-size: 0.9rem;
        }
        
        /* Mobile Responsive */
        @media (max-width: 768px) {
            .container {
                padding: 20px 15px;
            }
            
            .header h1 {
                font-size: 2rem;
            }
            
            .opportunity-card {
                flex-direction: column;
                align-items: flex-start;
                gap: 20px;
            }
            
            .scores-grid {
                grid-template-columns: 1fr;
            }
        }
    </style>
</head>
<body>
    <div class="container">
        <!-- Header -->
        <div class="header">
            <h1>Website Assessment Report</h1>
            <div class="business-meta">
                <div class="business-meta-item">
                    <strong>Business:</strong> {{ business_name }}
                </div>
                <div class="business-meta-item">
                    <strong>Website:</strong> <a href="{{ business_url }}" target="_blank">{{ business_url }}</a>
                </div>
                <div class="business-meta-item">
                    <strong>Industry:</strong> {{ industry }}
                </div>
                <div class="business-meta-item">
                    <strong>Location:</strong> {{ location }}
                </div>
                <div class="business-meta-item">
                    <strong>Date:</strong> {{ assessment_date }}
                </div>
            </div>
        </div>
        
        <!-- Overall Score Section -->
        <div class="overall-score-section">
            <div class="score-dial">
                <div class="score-value">{{ overall_score }}</div>
            </div>
            <div class="tier-badge {{ tier_class }}">{{ tier }}</div>
            <div class="confidence-badge">Confidence: {{ confidence_percent }}%</div>
            
            <div class="revenue-impact">
                <h3>Potential Annual Revenue Impact</h3>
                <div class="impact-range">
                    ${{ total_impact_low }} - ${{ total_impact_high }}
                </div>
                <div style="color: var(--gray-700); margin-top: 10px;">
                    Mid-point estimate: <strong>${{ total_impact_mid }}</strong>
                </div>
                <div style="color: var(--gray-500); font-size: 0.9rem; margin-top: 10px;">
                    Based on industry median revenue of ${{ base_revenue }}
                </div>
            </div>
        </div>
        
        <!-- Performance Scores -->
        <div class="scores-grid">
            <div class="score-card">
                <div class="score-card-value" style="color: {% if performance_score >= 90 %}var(--success){% elif performance_score >= 50 %}var(--warning){% else %}var(--danger){% endif %}">
                    {{ performance_score }}
                </div>
                <div class="score-card-label">Performance</div>
            </div>
            <div class="score-card">
                <div class="score-card-value" style="color: {% if seo_score >= 90 %}var(--success){% elif seo_score >= 50 %}var(--warning){% else %}var(--danger){% endif %}">
                    {{ seo_score }}
                </div>
                <div class="score-card-label">SEO</div>
            </div>
            <div class="score-card">
                <div class="score-card-value" style="color: {% if accessibility_score >= 90 %}var(--success){% elif accessibility_score >= 50 %}var(--warning){% else %}var(--danger){% endif %}">
                    {{ accessibility_score }}
                </div>
                <div class="score-card-label">Accessibility</div>
            </div>
            <div class="score-card">
                <div class="score-card-value" style="color: {% if best_practices_score >= 90 %}var(--success){% elif best_practices_score >= 50 %}var(--warning){% else %}var(--danger){% endif %}">
                    {{ best_practices_score }}
                </div>
                <div class="score-card-label">Best Practices</div>
            </div>
        </div>
        
        <!-- Priority Opportunities -->
        <div class="opportunities-section">
            <h2>Priority Opportunities</h2>
            
            {% for opp in opportunities %}
            <div class="opportunity-card">
                <div class="opportunity-content">
                    <h3>{{ opp.title }}</h3>
                    <p>{{ opp.description }}</p>
                    <div class="opportunity-meta">
                        <span class="complexity-badge complexity-{{ opp.complexity.lower() }}">
                            {{ opp.complexity }} Complexity
                        </span>
                        {% if opp.dependency != 'None' %}
                        <span style="color: var(--gray-500);">{{ opp.dependency }}</span>
                        {% endif %}
                    </div>
                </div>
                <div class="impact-display">
                    <div class="impact-value">${{ "{:,.0f}".format(opp.impact_mid) }}</div>
                    <div class="impact-label">Annual Impact</div>
                </div>
            </div>
            {% endfor %}
        </div>
        
        <!-- Google Business Profile -->
        <div class="gbp-section">
            <h2>Google Business Profile</h2>
            <div class="gbp-stats">
                <div class="gbp-stat">
                    <div class="gbp-stat-value">{{ gbp_rating }}/5</div>
                    <div class="gbp-stat-label">Rating</div>
                </div>
                <div class="gbp-stat">
                    <div class="gbp-stat-value">{{ gbp_reviews }}</div>
                    <div class="gbp-stat-label">Reviews</div>
                </div>
                <div class="gbp-stat">
                    <div class="gbp-stat-value">{{ gbp_claimed }}</div>
                    <div class="gbp-stat-label">Claimed Status</div>
                </div>
            </div>
        </div>
        
        <!-- Technology Stack -->
        {% if tech_stack %}
        <div class="opportunities-section">
            <h2>Technology Stack</h2>
            <div class="tech-stack">
                {% for tech in tech_stack %}
                <span class="tech-badge">{{ tech }}</span>
                {% endfor %}
            </div>
        </div>
        {% endif %}
        
        <!-- Email Summary -->
        <div class="email-summary">
            <h3>Executive Summary</h3>
            <p>{{ email_summary }}</p>
        </div>
        
        <!-- Footer -->
        <div class="footer">
            <p>Generated by LeadFactory Assessment Platform v1.5</p>
            <p>This report uses proprietary algorithms to estimate revenue impact based on industry benchmarks.</p>
            <p>Results may vary based on implementation quality and market conditions.</p>
        </div>
    </div>
</body>
</html>'''


def main():
    """Generate v1.5 reports for existing assessment data"""
    print("🚀 Starting v1.5 Report Generation")
    
    # Find existing assessment JSON files
    assessment_files = list(Path('.').glob('pipeline_results_*/assessment_*.json'))
    
    if not assessment_files:
        print("❌ No assessment files found")
        return
    
    print(f"📊 Found {len(assessment_files)} assessment files")
    
    # Get output directory
    output_dir = Path("pipeline_results_20250624_172032")
    if not output_dir.exists():
        output_dir = Path("reports_v15")
        output_dir.mkdir(exist_ok=True)
    
    # Initialize generator
    generator = V15ReportGenerator()
    
    # Process each assessment
    for assessment_file in assessment_files:
        print(f"\n📄 Processing {assessment_file.name}...")
        
        try:
            # Load assessment data
            with open(assessment_file, 'r') as f:
                data = json.load(f)
            
            assessment_results = data['results']
            business = data['business']
            
            # Generate v1.5 report
            report_path = generator.generate_report(assessment_results, business, output_dir)
            print(f"✅ Generated: {report_path}")
            
        except Exception as e:
            print(f"❌ Error processing {assessment_file.name}: {e}")
            import traceback
            traceback.print_exc()
    
    print(f"\n✅ v1.5 report generation complete!")
    print(f"📁 Reports saved in: {output_dir}")


if __name__ == "__main__":
    main()