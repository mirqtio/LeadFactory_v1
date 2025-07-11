#!/usr/bin/env python3
"""
Run full pipeline with assessments and direct report generation for test URLs
"""
import asyncio
import json
import os
import sys
from datetime import datetime
from pathlib import Path
import httpx
from typing import Dict, Any

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Test URLs provided by user
TEST_URLS = [
    {
        "business_id": "arctic_air",
        "business_name": "Arctic Air CT",
        "url": "http://arcticairct.com/",
        "vertical": "professional_services",
        "location": "Connecticut"
    },
    {
        "business_id": "aloha_snacks",
        "business_name": "Aloha Snacks VB",
        "url": "https://alohasnacksvb.com/",
        "vertical": "retail",
        "location": "Virginia Beach, VA"
    },
    {
        "business_id": "vision21",
        "business_name": "Vision 21",
        "url": "https://vision21.com/",
        "vertical": "healthcare",
        "location": "Unknown"
    },
    {
        "business_id": "life_in_motion",
        "business_name": "Life in Motion Physical Therapy",
        "url": "https://www.lifeinmotionphysicaltherapy.org/",
        "vertical": "healthcare",
        "location": "Unknown"
    },
    {
        "business_id": "power_design",
        "business_name": "Power Design CT",
        "url": "https://www.powerdesignct.com",
        "vertical": "professional_services",
        "location": "Connecticut"
    },
    {
        "business_id": "mandala_vet",
        "business_name": "Mandala Veterinary",
        "url": "https://mandalaveterinary.com/",
        "vertical": "healthcare",
        "location": "Unknown"
    },
    {
        "business_id": "invest_yakima",
        "business_name": "Invest in Yakima",
        "url": "https://www.investinyakima.com/",
        "vertical": "government",
        "location": "Yakima, WA"
    },
    {
        "business_id": "afc_mortgage",
        "business_name": "AFC Mortgage Group",
        "url": "https://www.afcmortgagegroup.net",
        "vertical": "financial_services",
        "location": "Unknown"
    },
    {
        "business_id": "bethel_it",
        "business_name": "Bethel IT Services",
        "url": "https://bethelitservices.com/",
        "vertical": "professional_services",
        "location": "Unknown"
    }
]

# API configuration
API_BASE_URL = "http://localhost:8000"
ASSESSMENT_ENDPOINT = f"{API_BASE_URL}/api/v1/assessments/trigger"
STATUS_ENDPOINT = f"{API_BASE_URL}/api/v1/assessments"


async def trigger_assessment(client: httpx.AsyncClient, business: Dict[str, Any]) -> str:
    """Trigger assessment for a business URL"""
    print(f"\n📊 Triggering assessment for {business['business_name']}...")
    
    payload = {
        "business_id": business["business_id"],
        "url": business["url"],
        "assessment_types": ["pagespeed", "tech_stack", "ai_insights"],
        "industry": business["vertical"],
        "session_config": {
            "business_name": business["business_name"],
            "location": business["location"]
        }
    }
    
    response = await client.post(ASSESSMENT_ENDPOINT, json=payload)
    if response.status_code != 200:
        print(f"❌ Failed to trigger assessment: {response.text}")
        return None
        
    data = response.json()
    session_id = data["session_id"]
    print(f"✅ Assessment started with session ID: {session_id}")
    return session_id


async def check_assessment_status(client: httpx.AsyncClient, session_id: str) -> Dict[str, Any]:
    """Check assessment status"""
    url = f"{STATUS_ENDPOINT}/{session_id}/status"
    response = await client.get(url)
    return response.json()


async def get_assessment_results(client: httpx.AsyncClient, session_id: str) -> Dict[str, Any]:
    """Get assessment results"""
    url = f"{STATUS_ENDPOINT}/{session_id}/results"
    response = await client.get(url)
    return response.json()


async def wait_for_completion(client: httpx.AsyncClient, session_id: str, business_name: str) -> bool:
    """Wait for assessment to complete"""
    print(f"⏳ Waiting for {business_name} assessment to complete...")
    
    max_attempts = 60  # 5 minutes max
    for attempt in range(max_attempts):
        status = await check_assessment_status(client, session_id)
        
        if status["status"] in ["completed", "failed", "partial"]:
            print(f"✅ Assessment {status['status']} for {business_name}")
            return True
            
        print(f"   Progress: {status.get('progress', 'Processing...')} ({attempt+1}/{max_attempts})") 
        await asyncio.sleep(5)  # Check every 5 seconds
    
    print(f"❌ Assessment timed out for {business_name}")
    return False


def generate_html_report(business: Dict[str, Any], assessment_results: Dict[str, Any], output_dir: Path):
    """Generate a simple HTML report from assessment results"""
    print(f"\n📝 Generating HTML report for {business['business_name']}...")
    
    # Extract key data
    pagespeed = assessment_results.get("pagespeed_results", {})
    tech_stack = assessment_results.get("tech_stack_results", [])
    ai_insights = assessment_results.get("ai_insights_results", {})
    
    # Create simple HTML report
    html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Website Assessment Report - {business['business_name']}</title>
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, sans-serif;
            line-height: 1.6;
            color: #333;
            max-width: 900px;
            margin: 0 auto;
            padding: 20px;
            background: #f5f5f5;
        }}
        .container {{
            background: white;
            padding: 40px;
            border-radius: 10px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
        }}
        h1 {{
            color: #2c3e50;
            border-bottom: 3px solid #3498db;
            padding-bottom: 10px;
        }}
        h2 {{
            color: #34495e;
            margin-top: 30px;
        }}
        .score-section {{
            display: flex;
            gap: 20px;
            margin: 20px 0;
            flex-wrap: wrap;
        }}
        .score-card {{
            flex: 1;
            min-width: 200px;
            background: #f8f9fa;
            padding: 20px;
            border-radius: 8px;
            text-align: center;
            border: 2px solid #e9ecef;
        }}
        .score-value {{
            font-size: 48px;
            font-weight: bold;
            color: #3498db;
        }}
        .score-label {{
            color: #7f8c8d;
            font-size: 14px;
            text-transform: uppercase;
            letter-spacing: 1px;
        }}
        .tech-stack {{
            display: flex;
            flex-wrap: wrap;
            gap: 10px;
            margin: 20px 0;
        }}
        .tech-item {{
            background: #3498db;
            color: white;
            padding: 5px 15px;
            border-radius: 20px;
            font-size: 14px;
        }}
        .recommendation {{
            background: #ecf0f1;
            padding: 15px;
            border-left: 4px solid #3498db;
            margin: 10px 0;
        }}
        .recommendation h3 {{
            margin: 0 0 10px 0;
            color: #2c3e50;
        }}
        .info-section {{
            background: #f8f9fa;
            padding: 20px;
            border-radius: 8px;
            margin: 20px 0;
        }}
        .footer {{
            margin-top: 40px;
            padding-top: 20px;
            border-top: 1px solid #e9ecef;
            text-align: center;
            color: #7f8c8d;
            font-size: 14px;
        }}
    </style>
</head>
<body>
    <div class="container">
        <h1>Website Assessment Report</h1>
        
        <div class="info-section">
            <h2>Business Information</h2>
            <p><strong>Name:</strong> {business['business_name']}</p>
            <p><strong>Website:</strong> <a href="{business['url']}" target="_blank">{business['url']}</a></p>
            <p><strong>Industry:</strong> {business['vertical'].replace('_', ' ').title()}</p>
            <p><strong>Location:</strong> {business['location']}</p>
            <p><strong>Assessment Date:</strong> {datetime.now().strftime('%B %d, %Y')}</p>
        </div>
"""
    
    # Add PageSpeed scores if available
    if pagespeed:
        html_content += """
        <h2>Performance Scores</h2>
        <div class="score-section">
"""
        if pagespeed.get('performance_score') is not None:
            html_content += f"""
            <div class="score-card">
                <div class="score-value">{pagespeed.get('performance_score', 0)}</div>
                <div class="score-label">Performance</div>
            </div>
"""
        if pagespeed.get('accessibility_score') is not None:
            html_content += f"""
            <div class="score-card">
                <div class="score-value">{pagespeed.get('accessibility_score', 0)}</div>
                <div class="score-label">Accessibility</div>
            </div>
"""
        if pagespeed.get('seo_score') is not None:
            html_content += f"""
            <div class="score-card">
                <div class="score-value">{pagespeed.get('seo_score', 0)}</div>
                <div class="score-label">SEO</div>
            </div>
"""
        if pagespeed.get('best_practices_score') is not None:
            html_content += f"""
            <div class="score-card">
                <div class="score-value">{pagespeed.get('best_practices_score', 0)}</div>
                <div class="score-label">Best Practices</div>
            </div>
"""
        html_content += "</div>"
        
        # Add opportunities
        opportunities = pagespeed.get('opportunities', [])
        if opportunities:
            html_content += """
        <h2>Performance Opportunities</h2>
"""
            for opp in opportunities[:5]:  # Show top 5
                html_content += f"""
        <div class="recommendation">
            <h3>{opp.get('title', 'Improvement Opportunity')}</h3>
            <p>{opp.get('description', '')}</p>
            {f"<p><strong>Potential Impact:</strong> {opp.get('displayValue', '')}</p>" if opp.get('displayValue') else ''}
        </div>
"""
    
    # Add tech stack
    if tech_stack:
        html_content += """
        <h2>Technology Stack</h2>
        <div class="tech-stack">
"""
        for tech in tech_stack:
            tech_name = tech.get('name', tech) if isinstance(tech, dict) else str(tech)
            html_content += f'            <div class="tech-item">{tech_name}</div>\n'
        html_content += "        </div>"
    
    # Add AI insights
    if ai_insights and ai_insights.get('recommendations'):
        html_content += """
        <h2>AI-Powered Recommendations</h2>
"""
        for rec in ai_insights['recommendations'][:5]:  # Show top 5
            html_content += f"""
        <div class="recommendation">
            <h3>{rec.get('title', 'Recommendation')}</h3>
            <p>{rec.get('description', rec.get('recommendation', ''))}</p>
            {f"<p><strong>Priority:</strong> {rec.get('priority', 'Medium')}</p>" if rec.get('priority') else ''}
        </div>
"""
    
    # Close HTML
    html_content += """
        <div class="footer">
            <p>Generated by LeadFactory Assessment Platform</p>
            <p>© 2025 LeadFactory. All rights reserved.</p>
        </div>
    </div>
</body>
</html>"""
    
    # Save HTML file
    html_filename = output_dir / f"report_{business['business_id']}.html"
    with open(html_filename, 'w') as f:
        f.write(html_content)
    print(f"✅ HTML report saved: {html_filename}")


async def save_assessment_data(session_id: str, business: Dict[str, Any], results: Dict[str, Any], output_dir: Path):
    """Save assessment results to JSON file"""
    filename = output_dir / f"assessment_{business['business_id']}_{session_id}.json"
    
    output = {
        "session_id": session_id,
        "business": business,
        "results": results,
        "generated_at": datetime.utcnow().isoformat()
    }
    
    with open(filename, 'w') as f:
        json.dump(output, f, indent=2, default=str)
    
    print(f"💾 Assessment data saved to {filename}")


async def run_pipeline_for_business(client: httpx.AsyncClient, business: Dict[str, Any], output_dir: Path):
    """Run complete pipeline for a single business"""
    print(f"\n{'='*60}")
    print(f"🏢 Processing: {business['business_name']}")
    print(f"🌐 URL: {business['url']}")
    print(f"📊 Industry: {business['vertical']}")
    print(f"{'='*60}")
    
    # Step 1: Trigger assessment
    session_id = await trigger_assessment(client, business)
    if not session_id:
        return
    
    # Step 2: Wait for completion
    if not await wait_for_completion(client, session_id, business["business_name"]):
        return
    
    # Step 3: Get results
    try:
        results = await get_assessment_results(client, session_id)
        
        # Step 4: Save assessment data
        await save_assessment_data(session_id, business, results, output_dir)
        
        # Step 5: Generate HTML report
        generate_html_report(business, results, output_dir)
        
        # Print summary
        print(f"\n📊 Summary for {business['business_name']}:")
        if results.get("pagespeed_results"):
            ps = results["pagespeed_results"]
            print(f"   Performance Score: {ps.get('performance_score', 'N/A')}/100")
            print(f"   SEO Score: {ps.get('seo_score', 'N/A')}/100")
            print(f"   Accessibility Score: {ps.get('accessibility_score', 'N/A')}/100")
        
        if results.get("tech_stack_results"):
            print(f"   Technologies Found: {len(results['tech_stack_results'])}")
        
        if results.get("ai_insights_results"):
            ai = results["ai_insights_results"]
            recs = ai.get("recommendations", [])
            print(f"   AI Recommendations: {len(recs)}")
            
    except Exception as e:
        print(f"❌ Pipeline failed for {business['business_name']}: {e}")
        import traceback
        traceback.print_exc()


async def main():
    """Run full pipeline for all test URLs"""
    print("🚀 Starting LeadFactory Full Pipeline")
    print(f"📍 API URL: {API_BASE_URL}")
    print(f"🔗 Processing {len(TEST_URLS)} URLs")
    
    # Create output directory with timestamp
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_dir = Path(f"pipeline_results_{timestamp}")
    output_dir.mkdir(exist_ok=True)
    print(f"📁 Output directory: {output_dir}")
    
    async with httpx.AsyncClient(timeout=300.0) as client:
        # First check if API is available
        try:
            response = await client.get(f"{API_BASE_URL}/health")
            if response.status_code != 200:
                print("❌ API is not healthy. Please start the server first.")
                return
            print("✅ API is healthy")
        except Exception as e:
            print(f"❌ Cannot connect to API: {e}")
            print("Please run: python -m uvicorn main:app --reload")
            return
        
        # Process each business sequentially to avoid overwhelming the API
        for business in TEST_URLS:
            await run_pipeline_for_business(client, business, output_dir)
            
            # Small delay between businesses
            await asyncio.sleep(2)
    
    print(f"\n{'='*60}")
    print("✅ Full pipeline completed!")
    print(f"📁 All results saved in: {output_dir.absolute()}")
    print(f"{'='*60}")
    
    # List generated files
    print("\n📋 Generated files:")
    for file in sorted(output_dir.iterdir()):
        print(f"   - {file.name}")


if __name__ == "__main__":
    asyncio.run(main())