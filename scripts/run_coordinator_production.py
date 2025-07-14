import asyncio
import json
import logging
import os
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Setup logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

# Ensure the project root is in the Python path
import sys

project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

# Local application imports
from d1_targeting.models import Base, Business
from d3_assessment.coordinator_v3 import AssessmentCoordinatorV3
from d5_scoring.engine import ConfigurableScoringEngine
from d5_scoring.utils import make_serializable
from d6_reports.generator import GenerationOptions, ReportGenerator


# --- Database Setup ---
def init_db():
    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        raise ValueError("DATABASE_URL environment variable not set.")
    engine = create_engine(db_url)
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)


async def main():
    """Main function to run the production assessment pipeline for a single business."""
    print("\n" + "=" * 80)
    print("🚀 STARTING PRODUCTION ASSESSMENT PIPELINE")
    print("=" * 80 + "\n")

    # --- Configuration ---
    output_dir = Path("tmp/production_run")
    output_dir.mkdir(exist_ok=True, parents=True)

    # --- Initialize Services ---
    print("🔧 Initializing services...")
    try:
        SessionLocal = init_db()
        db_session = SessionLocal()

        coordinator = AssessmentCoordinatorV3()
        scorer = ConfigurableScoringEngine(rules_path="d5_scoring/scoring_rules.yml")
        generator = ReportGenerator(template_dir="templates")
        print("   ✔️ Services initialized successfully.")
    except Exception as e:
        logger.error(f"Failed to initialize services: {str(e)}", exc_info=True)
        print(f"\n❌ Critical Error: Failed to initialize services. {str(e)}")
        return

    # --- Pipeline Execution ---
    try:
        # 1. Get Business Data and Run Assessment
        business_data = {
            "business_name": "Aloha Snacks",
            "url": "https://alohasnacks.com/",
            "business_id": "e4d9a4e4-7f2a-4f1e-8c1a-2b9f4e9a0b1a",  # Example UUID
        }

        # Create the business record if it doesn't exist
        business = db_session.query(Business).filter_by(id=business_data["business_id"]).first()
        if not business:
            business = Business(
                id=business_data["business_id"], name=business_data["business_name"], website=business_data["url"]
            )
            db_session.add(business)
            db_session.commit()
            print(f"   -> Created new business record for {business_data['business_name']}.")
        else:
            print(f"   -> Found existing business record for {business_data['business_name']}.")

        print(f"\n🔍 Assessing business: {business_data['business_name']}")
        start_time = asyncio.get_event_loop().time()
        assessment_result = await coordinator.execute_comprehensive_assessment(business_data)
        api_time = asyncio.get_event_loop().time() - start_time

        if not assessment_result or assessment_result.get("status") == "error":
            error_msg = assessment_result.get("error", "Unknown error")
            logger.error(f"Assessment failed for {business_data['business_name']}: {error_msg}")
            print(f"\n❌ Assessment failed: {error_msg}")
            results_file = output_dir / "assessment_failed.json"
            with open(results_file, "w") as f:
                json.dump(make_serializable(assessment_result), f, indent=2)
            print(f"   -> Detailed error info saved to: {results_file}")
            return

        print(f"\n✅ Assessment complete in {api_time:.1f}s. Status: {assessment_result.get('status')}")
        assessment_results_data = assessment_result.get("results", {})

        # 2. Run Scoring
        print("\n📊 Scoring assessment results...")
        scoring_result = scorer.calculate_score(business_data=business_data, assessment_data=assessment_results_data)
        print(f"   ✔️ Final Score: {scoring_result.overall_score}/100")

        # 3. Generate Report
        print("\n📄 Generating production report...")
        report_options = GenerationOptions(include_pdf=False)
        generation_result = await generator.generate_report(
            business_data=business_data,
            assessment_data=assessment_results_data,
            scoring_result=scoring_result.to_dict(),
            options=report_options,
        )

        if not generation_result.success:
            print(f"❌ Report generation failed: {generation_result.error_message}")
            return

        html_content = generation_result.html_content
        html_path = output_dir / "aloha_snacks_production_report.html"
        with open(html_path, "w") as f:
            f.write(html_content)
        print(f"✅ HTML report saved to: {html_path}")

        # Save detailed results
        results_file = output_dir / "assessment_results.json"
        with open(results_file, "w") as f:
            json.dump(make_serializable(assessment_result), f, indent=2)
        print(f"\n📊 Full results saved to: {results_file}")

        print("\n" + "=" * 80)
        print("✅ PRODUCTION ASSESSMENT COMPLETE")
        print("=" * 80)
        print(f"📁 Output directory: {output_dir}/")

    except Exception as e:
        logger.error(f"An unexpected error occurred in the main pipeline: {str(e)}", exc_info=True)
        print(f"\n❌ An unexpected error occurred: {str(e)}")


if __name__ == "__main__":
    init_db()
    asyncio.run(main())
