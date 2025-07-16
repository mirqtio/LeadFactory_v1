#!/usr/bin/env python
"""
Example script to demonstrate the visual analyzer functionality
"""
import asyncio
import json
import os

from d3_assessment.assessors.visual_analyzer import VisualAnalyzer


async def test_visual_analyzer():
    """Test the visual analyzer with stub data"""
    # Set USE_STUBS to true for this example
    os.environ["USE_STUBS"] = "true"

    # Create visual analyzer instance
    analyzer = VisualAnalyzer()

    print("Visual Analyzer Test")
    print("===================")
    print(f"Assessment Type: {analyzer.assessment_type}")
    print(f"Timeout: {analyzer.get_timeout()}s")
    print(f"Cost: ${analyzer.calculate_cost()}")
    print(f"Available: {analyzer.is_available()}")
    print()

    # Test with a sample URL
    test_url = "https://example.com"
    business_data = {"id": "test-lead-123", "name": "Example Business", "website": test_url}

    print(f"Analyzing: {test_url}")
    print("-" * 50)

    # Run the assessment
    result = await analyzer.assess(test_url, business_data)

    print(f"Status: {result.status}")
    print(f"Cost: ${result.cost}")
    print()

    if result.status == "completed":
        # Show screenshot URLs
        print("Screenshots captured:")
        print(f"  Desktop: {result.data.get('screenshot_url', 'N/A')}")
        print(f"  Thumbnail: {result.data.get('screenshot_thumb_url', 'N/A')}")
        print(f"  Mobile: {result.data.get('mobile_screenshot_url', 'N/A')}")
        print()

        # Show visual scores
        print("Visual Scores (0-100):")
        scores = result.data.get("visual_scores_json", {})
        for dimension, score in scores.items():
            print(f"  {dimension.replace('_', ' ').title()}: {score}")

        avg_score = result.data.get("visual_analysis", {}).get("average_score", 0)
        print(f"\nAverage Score: {avg_score:.1f}")
        print()

        # Show warnings
        warnings = result.data.get("visual_warnings", [])
        if warnings:
            print("Warnings:")
            for i, warning in enumerate(warnings, 1):
                print(f"  {i}. {warning}")
            print()

        # Show quick wins
        quickwins = result.data.get("visual_quickwins", [])
        if quickwins:
            print("Quick Wins:")
            for i, win in enumerate(quickwins, 1):
                print(f"  {i}. {win}")
            print()

        # Show insights
        insights = result.data.get("visual_analysis", {}).get("insights", {})
        if insights:
            print("Insights:")
            for category, items in insights.items():
                if items:
                    print(f"  {category.title()}:")
                    for item in items:
                        print(f"    - {item}")

        # Show metrics
        print("\nMetrics:")
        for key, value in result.metrics.items():
            print(f"  {key}: {value}")
    else:
        print(f"Error: {result.error_message}")

    print("\n" + "=" * 50)
    print("Full result data (JSON):")
    print(json.dumps(result.data, indent=2))


if __name__ == "__main__":
    asyncio.run(test_visual_analyzer())
