#!/usr/bin/env python3
"""
Simplified test script to analyze a URL through the LeadFactory pipeline.
Uses direct database queries and API calls without the async complexity.
"""
import os
import sys
import json
import requests
import argparse
from datetime import datetime
from decimal import Decimal
from urllib.parse import urlparse
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.syntax import Syntax
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Add src to Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from database import SessionLocal
from database.models import Business, ScoringResult
from d3_assessment.models import AssessmentResult, AssessmentType, AssessmentStatus
from sqlalchemy.orm import Session

console = Console()

def parse_args():
    parser = argparse.ArgumentParser(description='Test URL analysis through LeadFactory pipeline')
    parser.add_argument('url', help='URL to analyze (e.g., https://example.com)')
    parser.add_argument('--search-location', default='United States', help='Location for Yelp search')
    parser.add_argument('--verbose', '-v', action='store_true', help='Show detailed output')
    return parser.parse_args()

def search_yelp_direct(term, location):
    """Direct Yelp API call without async complexity."""
    api_key = os.getenv('YELP_API_KEY')
    if not api_key:
        console.print("[red]No Yelp API key found in environment[/red]")
        return None
    
    headers = {
        'Authorization': f'Bearer {api_key}',
        'Accept': 'application/json'
    }
    
    params = {
        'term': term,
        'location': location,
        'limit': 5,
        'sort_by': 'best_match'
    }
    
    try:
        response = requests.get(
            'https://api.yelp.com/v3/businesses/search',
            headers=headers,
            params=params,
            timeout=10
        )
        response.raise_for_status()
        data = response.json()
        return data.get('businesses', [])
    except Exception as e:
        console.print(f"[red]Yelp API error: {str(e)}[/red]")
        return None

def analyze_website_simple(url):
    """Simple website analysis using PageSpeed API."""
    api_key = os.getenv('GOOGLE_API_KEY')  # PageSpeed uses the main Google API key
    if not api_key:
        console.print("[yellow]No Google API key, skipping website analysis[/yellow]")
        return None
    
    params = {
        'url': url,
        'key': api_key,
        'category': ['performance', 'accessibility', 'seo']
    }
    
    try:
        response = requests.get(
            'https://www.googleapis.com/pagespeedonline/v5/runPagespeed',
            params=params,
            timeout=60  # Increased timeout for complex sites
        )
        response.raise_for_status()
        data = response.json()
        
        # Check if there's an error in the response
        if 'error' in data:
            console.print(f"[red]PageSpeed API error: {data['error'].get('message', 'Unknown error')}[/red]")
            return None
            
        return data
    except requests.exceptions.Timeout:
        console.print("[yellow]PageSpeed API timed out (site may be too complex)[/yellow]")
        return None
    except requests.exceptions.HTTPError as e:
        console.print(f"[red]PageSpeed HTTP error: {e.response.status_code} - {e.response.text[:200]}[/red]")
        return None
    except Exception as e:
        console.print(f"[red]PageSpeed API error: {str(e)}[/red]")
        return None

def display_business_info(business):
    """Display business information in a formatted table."""
    table = Table(title="Business Information", show_header=True, header_style="bold magenta")
    table.add_column("Field", style="cyan", width=25)
    table.add_column("Value", style="white")
    
    table.add_row("ID", str(business.id))
    table.add_row("Name", business.name or "N/A")
    table.add_row("Website", business.website or "N/A")
    table.add_row("Phone", business.phone or "N/A")
    
    if business.yelp_id and not business.yelp_id.startswith('manual_'):
        table.add_row("Yelp ID", business.yelp_id)
        table.add_row("Rating", f"{business.rating or 'N/A'}")
        table.add_row("Reviews", str(business.user_ratings_total or 0))
        if business.categories:
            table.add_row("Categories", ", ".join(business.categories[:3]))
    
    if business.address:
        table.add_row("Address", f"{business.address}, {business.city}, {business.state} {business.zip_code}")
    
    console.print(table)

def display_pagespeed_results(data):
    """Display PageSpeed analysis results."""
    if not data:
        return
    
    table = Table(title="PageSpeed Analysis", show_header=True, header_style="bold blue")
    table.add_column("Metric", style="cyan", width=30)
    table.add_column("Score", style="white")
    
    # Lighthouse scores
    categories = data.get('lighthouseResult', {}).get('categories', {})
    
    if 'performance' in categories:
        score = int(categories['performance']['score'] * 100)
        table.add_row("Performance Score", f"{score}/100")
    
    if 'accessibility' in categories:
        score = int(categories['accessibility']['score'] * 100)
        table.add_row("Accessibility Score", f"{score}/100")
    
    if 'seo' in categories:
        score = int(categories['seo']['score'] * 100)
        table.add_row("SEO Score", f"{score}/100")
    
    # Core Web Vitals
    audits = data.get('lighthouseResult', {}).get('audits', {})
    
    if 'largest-contentful-paint' in audits:
        lcp = audits['largest-contentful-paint']['displayValue']
        table.add_row("Largest Contentful Paint", lcp)
    
    if 'cumulative-layout-shift' in audits:
        cls = audits['cumulative-layout-shift']['displayValue']
        table.add_row("Cumulative Layout Shift", cls)
    
    if 'total-blocking-time' in audits:
        tbt = audits['total-blocking-time']['displayValue']
        table.add_row("Total Blocking Time", tbt)
    
    console.print(table)

def main():
    args = parse_args()
    
    # Validate URL
    parsed = urlparse(args.url)
    if not parsed.scheme:
        args.url = f"https://{args.url}"
    
    console.print(f"\n[bold cyan]Analyzing URL:[/bold cyan] {args.url}")
    console.print(f"[bold cyan]Search Location:[/bold cyan] {args.search_location}\n")
    
    session = SessionLocal()
    
    try:
        # Extract business name from URL
        domain = urlparse(args.url).netloc.replace('www.', '')
        business_name = domain.split('.')[0]
        
        # Step 1: Search Yelp
        console.print("[yellow]Step 1: Searching for business on Yelp...[/yellow]")
        yelp_results = search_yelp_direct(business_name, args.search_location)
        
        if not yelp_results:
            # Create business without Yelp data
            business = Business(
                yelp_id=f"manual_{business_name}_{datetime.now().strftime('%Y%m%d%H%M%S')}",
                name=business_name.title(),
                website=args.url
            )
        else:
            # Use first result
            yelp_data = yelp_results[0]
            console.print(f"[green]Found on Yelp: {yelp_data['name']}[/green]")
            
            business = Business(
                yelp_id=yelp_data.get('id'),
                name=yelp_data['name'],
                website=args.url,
                url=yelp_data.get('url'),
                categories=[cat['alias'] for cat in yelp_data.get('categories', [])],
                rating=Decimal(str(yelp_data.get('rating', 0))),
                user_ratings_total=yelp_data.get('review_count'),
                price_level=len(yelp_data.get('price', '')) if yelp_data.get('price') else None,
                phone=yelp_data.get('phone'),
                address=yelp_data.get('location', {}).get('address1'),
                city=yelp_data.get('location', {}).get('city'),
                state=yelp_data.get('location', {}).get('state'),
                zip_code=yelp_data.get('location', {}).get('zip_code'),
                latitude=yelp_data.get('coordinates', {}).get('latitude'),
                longitude=yelp_data.get('coordinates', {}).get('longitude')
            )
        
        # Check if business already exists
        existing = session.query(Business).filter_by(yelp_id=business.yelp_id).first()
        if existing:
            console.print(f"[yellow]Business already exists in database (ID: {existing.id}), updating...[/yellow]")
            # Update existing business
            for key, value in {
                'name': business.name,
                'website': business.website,
                'url': business.url,
                'phone': business.phone,
                'address': business.address,
                'city': business.city,
                'state': business.state,
                'zip_code': business.zip_code,
                'latitude': business.latitude,
                'longitude': business.longitude,
                'categories': business.categories,
                'rating': business.rating,
                'user_ratings_total': business.user_ratings_total,
                'price_level': business.price_level
            }.items():
                if value is not None:
                    setattr(existing, key, value)
            business = existing
            session.commit()
        else:
            session.add(business)
            session.commit()
        
        # Step 2: Website Analysis
        console.print("\n[yellow]Step 2: Analyzing website...[/yellow]")
        pagespeed_data = analyze_website_simple(args.url)
        if pagespeed_data:
            console.print("[green]Website analysis complete[/green]")
            
            # Save assessment result
            lighthouse = pagespeed_data.get('lighthouseResult', {})
            categories = lighthouse.get('categories', {})
            audits = lighthouse.get('audits', {})
            
            assessment = AssessmentResult(
                business_id=business.id,
                assessment_type=AssessmentType.pagespeed.value,
                status=AssessmentStatus.completed.value,
                website_url=args.url,
                website_domain=urlparse(args.url).netloc,
                is_mobile=False,  # Desktop analysis
                
                # Scores
                performance_score=int(categories.get('performance', {}).get('score', 0) * 100),
                accessibility_score=int(categories.get('accessibility', {}).get('score', 0) * 100),
                seo_score=int(categories.get('seo', {}).get('score', 0) * 100),
                best_practices_score=int(categories.get('best-practices', {}).get('score', 0) * 100),
                
                # Core Web Vitals
                lcp_ms=int(float(audits.get('largest-contentful-paint', {}).get('numericValue', 0))),
                fid_ms=int(float(audits.get('max-potential-fid', {}).get('numericValue', 0))),
                cls_score=float(audits.get('cumulative-layout-shift', {}).get('numericValue', 0)),
                
                # Store raw data
                pagespeed_data=pagespeed_data,
                
                # Set to completed
                completed_at=datetime.now()
            )
            session.add(assessment)
            session.commit()
            console.print("[dim]Assessment result saved to database[/dim]")
        
        # Step 3: Simple scoring
        console.print("\n[yellow]Step 3: Calculating lead score...[/yellow]")
        
        # Calculate simple scores
        business_score = 50.0  # Base score
        if business.rating:
            business_score = float(business.rating) * 20
        
        website_score = 50.0  # Base score
        if pagespeed_data:
            categories = pagespeed_data.get('lighthouseResult', {}).get('categories', {})
            if 'performance' in categories:
                website_score = categories['performance']['score'] * 100
        
        total_score = (business_score + website_score) / 2
        
        scoring = ScoringResult(
            business_id=business.id,
            scoring_version=1,
            score_raw=Decimal(str(total_score / 100)),  # Convert to 0-1 scale
            score_pct=int(total_score),
            tier='A' if total_score >= 80 else 'B' if total_score >= 60 else 'C' if total_score >= 40 else 'D',
            confidence=Decimal('0.85'),
            score_breakdown={
                'business': {'yelp_rating': business_score},
                'website': {'pagespeed_performance': website_score},
                'market': {'default': 50.0}
            },
            passed_gate=total_score >= 50
        )
        session.add(scoring)
        session.commit()
        
        # Display results
        console.print("\n" + "="*80 + "\n")
        console.print("[bold magenta]ANALYSIS RESULTS[/bold magenta]\n")
        
        display_business_info(business)
        
        if pagespeed_data:
            console.print("")
            display_pagespeed_results(pagespeed_data)
        
        console.print(f"\n[bold]Lead Score: {total_score:.1f}/100 (Tier {scoring.tier})[/bold]")
        console.print(f"  • Business Score: {business_score:.1f}")
        console.print(f"  • Website Score: {website_score:.1f}")
        console.print(f"  • Confidence: {float(scoring.confidence) * 100:.0f}%")
        console.print(f"  • Pass Gate: {'Yes' if scoring.passed_gate else 'No'}")
        
        console.print(f"\n[bold green]Analysis complete! Business ID: {business.id}[/bold green]")
        
        # SQL queries for verification
        console.print("\n[dim]To see all data in the database:[/dim]")
        console.print(f"[dim]docker exec anthrasite_leadfactory_v1-db-1 psql -U leadfactory -d leadfactory_dev -c \"SELECT * FROM businesses WHERE id = {business.id}\"[/dim]")
        
        if args.verbose and yelp_results:
            console.print("\n[bold]All Yelp Results:[/bold]")
            for idx, result in enumerate(yelp_results[:3]):
                console.print(f"\n{idx+1}. {result['name']}")
                console.print(f"   Rating: {result.get('rating', 'N/A')} ({result.get('review_count', 0)} reviews)")
                console.print(f"   Categories: {', '.join([c['title'] for c in result.get('categories', [])])}")
                console.print(f"   Address: {result.get('location', {}).get('address1', 'N/A')}")
        
    except Exception as e:
        console.print(f"[red]Error: {str(e)}[/red]")
        if args.verbose:
            import traceback
            console.print(traceback.format_exc())
    finally:
        session.close()

if __name__ == "__main__":
    main()