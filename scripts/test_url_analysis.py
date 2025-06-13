#!/usr/bin/env python3
"""
Test script to analyze an arbitrary URL through the LeadFactory pipeline.
Runs all analysis steps except report generation and email sending.
"""
import os
import sys
import json
import argparse
from datetime import datetime
from decimal import Decimal
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.syntax import Syntax
from rich import print as rprint
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Add src to Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from database import SessionLocal, engine
from database.models import Business, Target, ScoringResult
from d0_gateway.providers.yelp import YelpClient
from d4_enrichment.gbp_enricher import GBPEnricher
from d3_assessment.coordinator import AssessmentCoordinator
from d3_assessment.models import AssessmentResult, PageSpeedAssessment, TechStackDetection, AIInsight
from sqlalchemy.orm import Session
from sqlalchemy import text

console = Console()

def parse_args():
    parser = argparse.ArgumentParser(description='Test URL analysis through LeadFactory pipeline')
    parser.add_argument('url', help='URL to analyze (e.g., https://example.com)')
    parser.add_argument('--search-location', default='United States', help='Location for Yelp search')
    parser.add_argument('--search-radius', type=int, default=40000, help='Search radius in meters (max 40000)')
    parser.add_argument('--verbose', '-v', action='store_true', help='Show detailed output')
    return parser.parse_args()

def create_test_target(session: Session, url: str) -> Target:
    """Create a test target for the URL."""
    target = Target(
        external_id=f"test_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
        batch_id=None,
        search_location="Test Location",
        business_name=f"Test Business for {url}",
        website_url=url,
        status="pending"
    )
    session.add(target)
    session.commit()
    return target

def display_business_info(business: Business):
    """Display business information in a formatted table."""
    table = Table(title="Business Information", show_header=True, header_style="bold magenta")
    table.add_column("Field", style="cyan", width=25)
    table.add_column("Value", style="white")
    
    # Basic info
    table.add_row("ID", str(business.id))
    table.add_row("Name", business.name or "N/A")
    table.add_row("Website", business.website_url or "N/A")
    table.add_row("Phone", business.phone or "N/A")
    table.add_row("Email", business.email or "N/A")
    
    # Location
    table.add_row("Address", business.address_street or "N/A")
    table.add_row("City", business.address_city or "N/A")
    table.add_row("State", business.address_state or "N/A")
    table.add_row("ZIP", business.address_zip or "N/A")
    
    # Yelp data
    if business.yelp_id:
        table.add_row("Yelp ID", business.yelp_id)
        table.add_row("Yelp Rating", f"{business.yelp_rating or 'N/A'}")
        table.add_row("Yelp Reviews", str(business.yelp_review_count or 0))
        table.add_row("Yelp Categories", ", ".join(business.yelp_categories or []))
        table.add_row("Price Level", business.yelp_price_level or "N/A")
    
    # Google data
    if business.google_place_id:
        table.add_row("Google Place ID", business.google_place_id)
        table.add_row("Google Rating", f"{business.google_rating or 'N/A'}")
        table.add_row("Google Reviews", str(business.google_review_count or 0))
    
    console.print(table)

def display_website_analysis(analysis: AssessmentResult):
    """Display website analysis results."""
    if not analysis:
        console.print("[yellow]No website analysis available[/yellow]")
        return
    
    # Overall metrics
    table = Table(title="Website Analysis", show_header=True, header_style="bold blue")
    table.add_column("Metric", style="cyan", width=25)
    table.add_column("Value", style="white")
    
    table.add_row("Analysis Date", analysis.created_at.strftime("%Y-%m-%d %H:%M:%S"))
    table.add_row("Assessment Type", analysis.assessment_type)
    table.add_row("Status", analysis.status)
    table.add_row("Website URL", analysis.website_url or "N/A")
    
    # PageSpeed scores if available
    if analysis.performance_score is not None:
        table.add_row("Performance Score", f"{analysis.performance_score}/100")
    if analysis.accessibility_score is not None:
        table.add_row("Accessibility Score", f"{analysis.accessibility_score}/100")
    if analysis.seo_score is not None:
        table.add_row("SEO Score", f"{analysis.seo_score}/100")
    
    # Core Web Vitals
    if analysis.lcp_ms:
        table.add_row("Largest Contentful Paint", f"{analysis.lcp_ms} ms")
    if analysis.fid_ms:
        table.add_row("First Input Delay", f"{analysis.fid_ms} ms")
    if analysis.cls_score:
        table.add_row("Cumulative Layout Shift", f"{analysis.cls_score}")
    
    console.print(table)
    
    # Technology Stack
    if analysis.tech_stack_data:
        tech_data = analysis.tech_stack_data
        tech_info = []
        
        if analysis.cms_detected:
            tech_info.append(f"CMS: {analysis.cms_detected}")
        if analysis.framework_detected:
            tech_info.append(f"Framework: {analysis.framework_detected}")
        if analysis.hosting_detected:
            tech_info.append(f"Hosting: {analysis.hosting_detected}")
        
        if tech_info:
            console.print(Panel("\n".join(tech_info), title="Technology Stack", style="yellow"))
    
    # AI Insights if available
    if analysis.ai_insights_data:
        insights = analysis.ai_insights_data
        if isinstance(insights, dict) and insights.get('insights'):
            console.print("\n[bold]AI Insights:[/bold]")
            for insight in insights['insights'][:3]:  # Show first 3 insights
                console.print(f"• {insight.get('title', 'N/A')}")
                if insight.get('description'):
                    console.print(f"  [dim]{insight['description']}[/dim]")

def display_scoring_results(scoring: ScoringResult):
    """Display scoring results."""
    if not scoring:
        console.print("[yellow]No scoring results available[/yellow]")
        return
    
    table = Table(title="Lead Scoring", show_header=True, header_style="bold red")
    table.add_column("Score Type", style="cyan", width=25)
    table.add_column("Value", style="white")
    table.add_column("Details", style="dim")
    
    table.add_row("Overall Score", f"{scoring.total_score:.2f}", "Combined score from all factors")
    table.add_row("Business Score", f"{scoring.business_score:.2f}", "Based on reviews, ratings, etc.")
    table.add_row("Website Score", f"{scoring.website_score:.2f}", "Based on website quality")
    table.add_row("Market Score", f"{scoring.market_score:.2f}", "Based on location and industry")
    
    # Score breakdown
    if scoring.score_components:
        console.print("\n[bold]Score Components:[/bold]")
        components = json.dumps(scoring.score_components, indent=2)
        console.print(Syntax(components, "json", theme="monokai"))
    
    console.print(table)

def analyze_url(url: str, location: str, radius: int, verbose: bool):
    """Run the full analysis pipeline on a URL."""
    session = SessionLocal()
    
    try:
        console.print(f"\n[bold cyan]Analyzing URL:[/bold cyan] {url}")
        console.print(f"[bold cyan]Search Location:[/bold cyan] {location}")
        console.print(f"[bold cyan]Search Radius:[/bold cyan] {radius} meters\n")
        
        # Step 1: Search for business on Yelp
        console.print("[yellow]Step 1: Searching for business on Yelp...[/yellow]")
        yelp_client = YelpClient(api_key=os.getenv('YELP_API_KEY'))
        
        # Extract business name from URL for search
        from urllib.parse import urlparse
        domain = urlparse(url).netloc.replace('www.', '')
        business_name = domain.split('.')[0]
        
        # Search Yelp
        yelp_results = yelp_client.search_businesses(
            term=business_name,
            location=location,
            radius=radius
        )
        
        if not yelp_results:
            console.print("[red]No Yelp results found. Creating business from URL only...[/red]")
            # Create business without Yelp data
            business = Business(
                name=business_name.title(),
                website_url=url,
                source="manual_test",
                yelp_match_confidence=0.0
            )
            session.add(business)
            session.commit()
        else:
            # Use the first result
            yelp_data = yelp_results[0]
            console.print(f"[green]Found on Yelp: {yelp_data.get('name')}[/green]")
            
            # Create business with Yelp data
            business = Business(
                name=yelp_data.get('name'),
                website_url=url,
                source="yelp",
                yelp_id=yelp_data.get('id'),
                yelp_categories=[cat['alias'] for cat in yelp_data.get('categories', [])],
                yelp_rating=yelp_data.get('rating'),
                yelp_review_count=yelp_data.get('review_count'),
                yelp_price_level=yelp_data.get('price'),
                yelp_match_confidence=0.95,
                phone=yelp_data.get('phone'),
                address_street=yelp_data.get('location', {}).get('address1'),
                address_city=yelp_data.get('location', {}).get('city'),
                address_state=yelp_data.get('location', {}).get('state'),
                address_zip=yelp_data.get('location', {}).get('zip_code'),
                latitude=yelp_data.get('coordinates', {}).get('latitude'),
                longitude=yelp_data.get('coordinates', {}).get('longitude')
            )
            session.add(business)
            session.commit()
            
            # Get additional Yelp details
            if verbose:
                details = yelp_client.get_business_details(yelp_data.get('id'))
                if details:
                    console.print("[dim]Additional Yelp details retrieved[/dim]")
        
        # Step 2: Google enrichment (if we have location data)
        if business.name and business.address_city:
            console.print("\n[yellow]Step 2: Enriching with Google data...[/yellow]")
            gbp_enricher = GBPEnricher()
            google_data = gbp_enricher.enrich_business(
                name=business.name,
                street=business.address_street,
                city=business.address_city,
                state=business.address_state,
                zip_code=business.address_zip,
                existing_data={}
            )
            
            if google_data and google_data.get('google_place_id'):
                business.google_place_id = google_data.get('google_place_id')
                business.google_rating = google_data.get('google_rating')
                business.google_review_count = google_data.get('google_review_count')
                session.commit()
                console.print("[green]Google data added[/green]")
        else:
            console.print("\n[dim]Step 2: Skipping Google enrichment (no location data)[/dim]")
        
        # Step 3: Website assessment
        console.print("\n[yellow]Step 3: Analyzing website...[/yellow]")
        assessment_coordinator = AssessmentCoordinator(session)
        
        # Run website assessment
        try:
            analysis = assessment_coordinator.assess_business(business.id)
            if analysis:
                console.print("[green]Website analysis complete[/green]")
            else:
                console.print("[red]Website analysis failed[/red]")
        except Exception as e:
            console.print(f"[red]Website analysis error: {str(e)}[/red]")
            analysis = None
        
        # Step 4: Lead scoring
        console.print("\n[yellow]Step 4: Calculating lead score...[/yellow]")
        
        # Calculate scores based on available data
        scoring = ScoringResult(
            business_id=business.id,
            scoring_version="1.0",
            total_score=0.0,
            business_score=0.0,
            website_score=0.0,
            market_score=0.0,
            score_components={}
        )
        
        # Business score (based on Yelp/Google data)
        business_components = {}
        if business.yelp_rating:
            business_components['yelp_rating'] = float(business.yelp_rating) * 20
        if business.yelp_review_count:
            business_components['review_volume'] = min(float(business.yelp_review_count) / 10, 100)
        if business.google_rating:
            business_components['google_rating'] = float(business.google_rating) * 20
        
        scoring.business_score = sum(business_components.values()) / len(business_components) if business_components else 50.0
        scoring.score_components['business'] = business_components
        
        # Website score (based on assessment)
        website_components = {}
        if analysis:
            if analysis.has_contact_form:
                website_components['contact_form'] = 20
            if analysis.has_phone_number:
                website_components['phone_visible'] = 15
            if analysis.has_email:
                website_components['email_visible'] = 15
            if analysis.is_mobile_friendly:
                website_components['mobile_friendly'] = 25
            if analysis.has_ssl:
                website_components['ssl_enabled'] = 25
        
        scoring.website_score = sum(website_components.values()) if website_components else 30.0
        scoring.score_components['website'] = website_components
        
        # Market score (simplified for test)
        scoring.market_score = 60.0  # Default middle score
        scoring.score_components['market'] = {'default': 60.0}
        
        # Total score (weighted average)
        scoring.total_score = (
            scoring.business_score * 0.4 +
            scoring.website_score * 0.4 +
            scoring.market_score * 0.2
        )
        
        session.add(scoring)
        session.commit()
        console.print("[green]Lead scoring complete[/green]")
        
        # Display results
        console.print("\n" + "="*80 + "\n")
        console.print("[bold magenta]ANALYSIS RESULTS[/bold magenta]\n")
        
        display_business_info(business)
        
        if analysis:
            console.print("")
            display_website_analysis(analysis)
        
        console.print("")
        display_scoring_results(scoring)
        
        # Show raw data if verbose
        if verbose:
            console.print("\n[bold]Raw Business Data:[/bold]")
            business_dict = {
                'id': business.id,
                'name': business.name,
                'website_url': business.website_url,
                'yelp_data': {
                    'id': business.yelp_id,
                    'categories': business.yelp_categories,
                    'rating': float(business.yelp_rating) if business.yelp_rating else None,
                    'reviews': business.yelp_review_count,
                    'price': business.yelp_price_level
                },
                'google_data': {
                    'place_id': business.google_place_id,
                    'rating': float(business.google_rating) if business.google_rating else None,
                    'reviews': business.google_review_count
                },
                'location': {
                    'address': business.address_street,
                    'city': business.address_city,
                    'state': business.address_state,
                    'zip': business.address_zip,
                    'lat': float(business.latitude) if business.latitude else None,
                    'lng': float(business.longitude) if business.longitude else None
                }
            }
            console.print(Syntax(json.dumps(business_dict, indent=2, default=str), "json", theme="monokai"))
        
        console.print(f"\n[bold green]Analysis complete! Business ID: {business.id}[/bold green]")
        
        # Provide SQL query to check all related data
        console.print("\n[dim]To see all data in the database, run:[/dim]")
        console.print(f"[dim]SELECT * FROM businesses WHERE id = {business.id};[/dim]")
        console.print(f"[dim]SELECT * FROM assessment_results WHERE business_id = {business.id};[/dim]")
        console.print(f"[dim]SELECT * FROM scoring_results WHERE business_id = {business.id};[/dim]")
        
    except Exception as e:
        console.print(f"[red]Error during analysis: {str(e)}[/red]")
        if verbose:
            import traceback
            console.print(traceback.format_exc())
    finally:
        session.close()

def main():
    args = parse_args()
    
    # Validate URL
    from urllib.parse import urlparse
    parsed = urlparse(args.url)
    if not parsed.scheme:
        args.url = f"https://{args.url}"
    
    analyze_url(args.url, args.search_location, args.search_radius, args.verbose)

if __name__ == "__main__":
    main()