#!/usr/bin/env python3
"""
Run full assessment pipeline for a business ID.
This runs the complete D3 assessment including PageSpeed, tech stack detection, and AI insights.
"""
import os
import sys
import asyncio
import argparse
from datetime import datetime
from rich.console import Console
from rich.table import Table
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Add src to Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from database import SessionLocal
from database.models import Business
from d3_assessment.coordinator import AssessmentCoordinator
from d3_assessment.models import AssessmentResult, AssessmentType

console = Console()

def parse_args():
    parser = argparse.ArgumentParser(description='Run full assessment for a business')
    parser.add_argument('business_id', help='Business ID to assess')
    parser.add_argument('--type', choices=['full_audit', 'pagespeed', 'tech_stack', 'ai_insights'], 
                       default='full_audit', help='Assessment type')
    return parser.parse_args()

async def run_assessment(business_id: str, assessment_type: str):
    """Run the assessment asynchronously."""
    session = SessionLocal()
    
    try:
        # Check if business exists
        business = session.query(Business).filter_by(id=business_id).first()
        if not business:
            console.print(f"[red]Business not found: {business_id}[/red]")
            return None
            
        console.print(f"[cyan]Running {assessment_type} assessment for: {business.name}[/cyan]")
        console.print(f"Website: {business.website}")
        
        # Create coordinator
        coordinator = AssessmentCoordinator()
        
        # Run assessment
        console.print("\n[yellow]Starting assessment...[/yellow]")
        result = await coordinator.execute_comprehensive_assessment(
            business_id=business_id,
            url=business.website,
            assessment_types=[AssessmentType(assessment_type)] if assessment_type != 'full_audit' else None,
            industry=business.categories[0] if business.categories else None,
            session_config=None
        )
        
        if result and result.partial_results:
            console.print(f"[green]Assessment completed! {result.completed_assessments}/{result.total_assessments} assessments successful[/green]")
            if result.failed_assessments > 0:
                console.print(f"[yellow]Failed assessments: {result.failed_assessments}[/yellow]")
            # Return the first assessment result for display
            return list(result.partial_results.values())[0] if result.partial_results else None
        else:
            console.print("[red]Assessment failed or no results[/red]")
            if result and result.errors:
                for assessment_type, error in result.errors.items():
                    console.print(f"[red]  {assessment_type}: {error}[/red]")
            return None
            
    except Exception as e:
        console.print(f"[red]Error: {str(e)}[/red]")
        import traceback
        console.print(traceback.format_exc())
        return None
    finally:
        session.close()

def display_assessment_results(assessment: AssessmentResult):
    """Display detailed assessment results."""
    if not assessment:
        return
        
    # Main assessment info
    table = Table(title="Assessment Summary", show_header=True, header_style="bold magenta")
    table.add_column("Field", style="cyan")
    table.add_column("Value", style="white")
    
    table.add_row("Assessment ID", str(assessment.id))
    table.add_row("Type", str(assessment.assessment_type))
    table.add_row("Status", assessment.status)
    table.add_row("Created", assessment.created_at.strftime("%Y-%m-%d %H:%M:%S"))
    
    if assessment.performance_score is not None:
        table.add_row("Performance Score", f"{assessment.performance_score}/100")
    if assessment.accessibility_score is not None:
        table.add_row("Accessibility Score", f"{assessment.accessibility_score}/100")
    if assessment.seo_score is not None:
        table.add_row("SEO Score", f"{assessment.seo_score}/100")
    if assessment.best_practices_score is not None:
        table.add_row("Best Practices Score", f"{assessment.best_practices_score}/100")
        
    console.print(table)
    
    # Core Web Vitals
    if any([assessment.lcp_ms, assessment.fid_ms, assessment.cls_score]):
        vitals_table = Table(title="Core Web Vitals", show_header=True, header_style="bold blue")
        vitals_table.add_column("Metric", style="cyan")
        vitals_table.add_column("Value", style="white")
        vitals_table.add_column("Rating", style="yellow")
        
        if assessment.lcp_ms:
            lcp_rating = "Good" if assessment.lcp_ms < 2500 else "Needs Improvement" if assessment.lcp_ms < 4000 else "Poor"
            vitals_table.add_row("Largest Contentful Paint", f"{assessment.lcp_ms}ms", lcp_rating)
            
        if assessment.fid_ms:
            fid_rating = "Good" if assessment.fid_ms < 100 else "Needs Improvement" if assessment.fid_ms < 300 else "Poor"
            vitals_table.add_row("First Input Delay", f"{assessment.fid_ms}ms", fid_rating)
            
        if assessment.cls_score:
            cls_rating = "Good" if assessment.cls_score < 0.1 else "Needs Improvement" if assessment.cls_score < 0.25 else "Poor"
            vitals_table.add_row("Cumulative Layout Shift", f"{assessment.cls_score}", cls_rating)
            
        console.print(vitals_table)
    
    # Technology detected
    if any([assessment.cms_detected, assessment.framework_detected, assessment.hosting_detected]):
        tech_table = Table(title="Technology Stack", show_header=True, header_style="bold green")
        tech_table.add_column("Category", style="cyan")
        tech_table.add_column("Detected", style="white")
        
        if assessment.cms_detected:
            tech_table.add_row("CMS", assessment.cms_detected)
        if assessment.framework_detected:
            tech_table.add_row("Framework", assessment.framework_detected)
        if assessment.hosting_detected:
            tech_table.add_row("Hosting", assessment.hosting_detected)
            
        console.print(tech_table)
    
    # AI Insights
    if assessment.ai_insights_data:
        console.print("\n[bold yellow]AI-Generated Insights:[/bold yellow]")
        insights = assessment.ai_insights_data.get('insights', [])
        for i, insight in enumerate(insights[:5], 1):
            console.print(f"\n{i}. [bold]{insight.get('title', 'N/A')}[/bold]")
            console.print(f"   Category: {insight.get('category', 'N/A')}")
            console.print(f"   Impact: {insight.get('impact', 'N/A')} | Effort: {insight.get('effort', 'N/A')}")
            console.print(f"   {insight.get('description', 'N/A')}")
            
    # Cost breakdown
    if assessment.total_cost_usd:
        console.print(f"\n[dim]Total assessment cost: ${assessment.total_cost_usd:.4f}[/dim]")

def main():
    args = parse_args()
    
    # Run the async assessment
    assessment = asyncio.run(run_assessment(args.business_id, args.type))
    
    if assessment:
        console.print("")
        display_assessment_results(assessment)
        
        console.print(f"\n[bold green]Assessment complete![/bold green]")
        console.print(f"To see raw data: ./show_business.sh {args.business_id}")

if __name__ == "__main__":
    main()