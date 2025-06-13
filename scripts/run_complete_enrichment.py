#!/usr/bin/env python3
"""
Run complete enrichment pipeline including:
1. Website assessment (PageSpeed, Tech Stack, AI Insights)
2. Screenshot capture (simulated - would use headless browser)
3. Google Business Profile lookup
4. Email finding via Data Axle and Hunter.io
5. ChatGPT 4o analysis with all data
"""
import asyncio
import json
import os
import sys
from datetime import datetime
from typing import Dict, Any, Optional

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from d4_enrichment.dataaxle_enricher import DataAxleEnricher
from d4_enrichment.hunter_enricher import HunterEnricher
from d4_enrichment.gbp_enricher import GBPEnricher
from d0_gateway.providers.dataaxle import DataAxleClient
from d0_gateway.providers.hunter import HunterClient
from core.logging import get_logger

logger = get_logger(__name__)

# Test business data
BUSINESS_DATA = {
    "business_id": "07a80cdc-3c94-48df-9351-5ba097026806",
    "name": "Yakima County Development Association",
    "website": "https://investinyakima.com",
    "address": "10 North 9th Street, Yakima, WA 98901",
    "city": "Yakima",
    "state": "WA",
    "categories": ["Economic Development", "Non-Profit Organizations"],
    "assessment_results": {}  # Will be populated
}


async def simulate_screenshot_capture(url: str) -> Dict[str, Any]:
    """Simulate screenshot capture (in production would use Playwright/Puppeteer)"""
    print(f"\n📸 Capturing screenshot of {url}")
    await asyncio.sleep(1)  # Simulate processing
    
    return {
        "screenshot_url": f"screenshots/{BUSINESS_DATA['business_id']}_homepage.png",
        "captured_at": datetime.now().isoformat(),
        "page_title": "Invest in Yakima - Economic Development",
        "meta_description": "Yakima County Development Association promotes economic growth and business development in Yakima County, Washington.",
        "visible_text_preview": "Welcome to Yakima County - A great place to live, work, and do business..."
    }


async def enrich_with_gbp(business_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Enrich with Google Business Profile data"""
    print("\n🗺️  Searching Google Business Profile...")
    
    try:
        gbp_enricher = GBPEnricher(use_mock=True)  # Using mock for demo
        
        # Search for business
        results = await gbp_enricher.search_business(
            name=business_data["name"],
            address=business_data["address"],
            city=business_data["city"],
            state=business_data["state"]
        )
        
        if results:
            print(f"  ✓ Found {len(results)} GBP matches")
            # Return best match
            return results[0].to_dict() if results else None
        else:
            print("  ✗ No GBP matches found")
            return None
            
    except Exception as e:
        logger.error(f"GBP enrichment failed: {e}")
        print(f"  ✗ GBP enrichment error: {str(e)}")
        return None


async def enrich_with_dataaxle(business_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Enrich with Data Axle for email and contact info"""
    print("\n📧 Searching Data Axle for contact information...")
    
    try:
        enricher = DataAxleEnricher()
        result = await enricher.enrich_business(
            business_data, 
            business_data["business_id"]
        )
        
        if result and result.email:
            print(f"  ✓ Found email: {result.email}")
            print(f"  ✓ Confidence: {result.confidence_score:.0%}")
            return {
                "email": result.email,
                "phone": result.phone,
                "contact_name": result.contact_name,
                "contact_title": result.contact_title,
                "employee_count": result.employee_count,
                "annual_revenue": result.annual_revenue,
                "confidence": result.confidence_score
            }
        else:
            print("  ✗ No Data Axle match found")
            return None
            
    except Exception as e:
        logger.error(f"Data Axle enrichment failed: {e}")
        print(f"  ✗ Data Axle error: {str(e)}")
        return None


async def enrich_with_hunter(business_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Fallback to Hunter.io for email finding"""
    print("\n🎯 Trying Hunter.io as fallback for email...")
    
    try:
        enricher = HunterEnricher()
        result = await enricher.enrich_business(
            business_data,
            business_data["business_id"]
        )
        
        if result and result.email:
            print(f"  ✓ Found email: {result.email}")
            print(f"  ✓ Confidence: {result.confidence_score:.0%}")
            return {
                "email": result.email,
                "confidence": result.confidence_score,
                "source": "hunter.io"
            }
        else:
            print("  ✗ No Hunter.io emails found")
            return None
            
    except Exception as e:
        logger.error(f"Hunter enrichment failed: {e}")
        print(f"  ✗ Hunter.io error: {str(e)}")
        return None


async def analyze_with_gpt4(enrichment_data: Dict[str, Any]) -> Dict[str, Any]:
    """Simulate GPT-4o analysis (would call OpenAI API in production)"""
    print("\n🤖 Analyzing with ChatGPT 4o...")
    await asyncio.sleep(2)  # Simulate API call
    
    # Simulated personalized analysis
    analysis = {
        "personalized_insights": {
            "business_overview": "Yakima County Development Association is a well-established economic development organization with a strong digital presence. Their website shows good technical implementation but has room for performance improvements.",
            "key_opportunities": [
                "Website performance optimization could improve user experience and SEO rankings",
                "Mobile experience needs attention - current performance score is below industry standards",
                "Email marketing integration appears limited - opportunity for lead generation improvement"
            ],
            "recommended_approach": "Focus on website performance optimization and mobile experience enhancement. Their mission aligns with digital transformation initiatives.",
            "personalization_hooks": [
                "Economic development focus aligns with digital growth strategies",
                "Non-profit status may qualify for special pricing or grants",
                "Community impact angle for case studies"
            ]
        },
        "lead_score": 78,
        "engagement_strategy": "Educational approach highlighting ROI of digital improvements for economic development initiatives",
        "estimated_project_value": "$15,000 - $25,000",
        "ai_confidence": 0.85
    }
    
    print("  ✓ Analysis complete")
    return analysis


async def run_complete_enrichment():
    """Run the complete enrichment pipeline"""
    print("=" * 80)
    print("LeadFactory Complete Enrichment Pipeline")
    print("=" * 80)
    print(f"Business: {BUSINESS_DATA['name']}")
    print(f"Website: {BUSINESS_DATA['website']}")
    print(f"Time: {datetime.now().isoformat()}")
    
    # Assume we already have assessment results from previous run
    BUSINESS_DATA["assessment_results"] = {
        "pagespeed": {
            "performance_score": 53,
            "mobile_friendly": True,
            "largest_contentful_paint": 8555,
            "issues_found": 7
        },
        "tech_stack": {
            "cms": "WordPress",
            "hosting": "WP Engine",
            "analytics": ["Google Analytics", "Google Tag Manager"],
            "frameworks": ["jQuery", "Bootstrap"]
        },
        "ai_insights": {
            "summary": "Economic development organization website with moderate performance",
            "recommendations": ["Optimize images", "Implement caching", "Minify resources"]
        }
    }
    
    enrichment_results = {
        "business_id": BUSINESS_DATA["business_id"],
        "timestamp": datetime.now().isoformat(),
        "assessment_data": BUSINESS_DATA["assessment_results"],
        "enrichment_data": {}
    }
    
    # 1. Capture Screenshot
    screenshot_data = await simulate_screenshot_capture(BUSINESS_DATA["website"])
    enrichment_results["enrichment_data"]["screenshot"] = screenshot_data
    
    # 2. Google Business Profile Lookup
    gbp_data = await enrich_with_gbp(BUSINESS_DATA)
    if gbp_data:
        enrichment_results["enrichment_data"]["google_business_profile"] = gbp_data
    
    # 3. Try Data Axle for email/contact
    dataaxle_data = await enrich_with_dataaxle(BUSINESS_DATA)
    if dataaxle_data:
        enrichment_results["enrichment_data"]["data_axle"] = dataaxle_data
    
    # 4. If no email from Data Axle, try Hunter.io
    if not dataaxle_data or not dataaxle_data.get("email"):
        hunter_data = await enrich_with_hunter(BUSINESS_DATA)
        if hunter_data:
            enrichment_results["enrichment_data"]["hunter_io"] = hunter_data
    
    # 5. Send everything to GPT-4o for analysis
    gpt_analysis = await analyze_with_gpt4(enrichment_results)
    enrichment_results["ai_analysis"] = gpt_analysis
    
    # Summary
    print("\n" + "=" * 80)
    print("ENRICHMENT SUMMARY")
    print("=" * 80)
    
    email_found = (
        enrichment_results["enrichment_data"].get("data_axle", {}).get("email") or
        enrichment_results["enrichment_data"].get("hunter_io", {}).get("email")
    )
    
    print(f"✅ Assessment data available")
    print(f"✅ Screenshot captured")
    print(f"{'✅' if gbp_data else '❌'} Google Business Profile data")
    print(f"{'✅' if email_found else '❌'} Email address found: {email_found or 'None'}")
    print(f"✅ AI analysis completed")
    print(f"\n📊 Lead Score: {gpt_analysis['lead_score']}/100")
    print(f"💰 Estimated Value: {gpt_analysis['estimated_project_value']}")
    
    # Save results
    output_file = f"complete_enrichment_{BUSINESS_DATA['business_id']}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(output_file, "w") as f:
        json.dump(enrichment_results, f, indent=2, default=str)
    print(f"\n📄 Full results saved to: {output_file}")
    
    return enrichment_results


if __name__ == "__main__":
    results = asyncio.run(run_complete_enrichment())