#!/usr/bin/env python3
"""
Generate HTML reports from assessment JSON results
"""

import json
import os
import sys
from datetime import datetime
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from d6_reports.generator import GenerationOptions, ReportGenerator
from d6_reports.template_engine import TemplateData


def load_assessment_results(json_file):
    """Load assessment results from JSON file"""
    with open(json_file) as f:
        data = json.load(f)
    return data


def generate_report_for_assessment(json_file, output_dir="reports"):
    """Generate HTML report for an assessment result"""
    print(f"\n📄 Processing {json_file}...")

    # Load data
    data = load_assessment_results(json_file)
    results = data["results"]
    business = data["business"]

    # Create output directory
    output_path = Path(output_dir)
    output_path.mkdir(exist_ok=True)

    # Prepare template data
    pagespeed_results = results.get("pagespeed_results") or {}
    performance_score = pagespeed_results.get("performance_score", 0) if pagespeed_results else 0

    template_data = TemplateData(
        business_name=business["business_name"],
        business_url=business["url"],
        assessment_date=datetime.fromisoformat(results["completed_at"].replace("Z", "+00:00")),
        overall_score=performance_score,
        findings=[],  # Would need to extract from results
        recommendations=[],  # Would need to extract from results
        tech_stack=results.get("tech_stack_results", []),
        pagespeed_data=pagespeed_results,
        industry=business.get("vertical", "general"),
        location=business.get("location", "Unknown"),
    )

    # Generate report
    generator = ReportGenerator()
    options = GenerationOptions(
        include_pdf=False,
        include_tech_details=True,
        include_recommendations=True,  # Just HTML for now
    )

    try:
        result = generator.generate_report(template_data=template_data, output_dir=output_path, options=options)

        print("✅ Report generated:")
        print(f"   HTML: {result.html_path}")
        if result.pdf_path:
            print(f"   PDF: {result.pdf_path}")
        print(f"   Generation time: {result.generation_time_ms}ms")

        return result.html_path

    except Exception as e:
        print(f"❌ Error generating report: {e}")
        import traceback

        traceback.print_exc()
        return None


def main():
    """Generate reports for all assessment JSON files"""
    print("🚀 Starting HTML Report Generation")

    # Find all assessment JSON files
    json_files = list(Path().glob("assessment_test_*.json"))

    if not json_files:
        print("❌ No assessment JSON files found")
        print("   Run 'python scripts/run_test_urls.py' first to generate assessments")
        return

    print(f"📊 Found {len(json_files)} assessment files")

    # Create reports directory
    reports_dir = Path("reports_output")
    reports_dir.mkdir(exist_ok=True)

    # Generate reports
    generated_reports = []
    for json_file in json_files:
        report_path = generate_report_for_assessment(json_file, reports_dir)
        if report_path:
            generated_reports.append(report_path)

    print(f"\n✅ Generated {len(generated_reports)} reports")
    print(f"📁 Reports saved in: {reports_dir.absolute()}")

    # Show the generated files
    if generated_reports:
        print("\n📋 Generated reports:")
        for report in generated_reports:
            print(f"   - {report}")


if __name__ == "__main__":
    main()
