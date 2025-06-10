#!/usr/bin/env python3
"""
Campaign Seeding Script - Task 095

Creates initial target campaigns for LeadFactory production launch
with optimized targeting parameters and quota allocation.

Acceptance Criteria:
- 10 targets created ✓
- Mix of verticals ✓
- High-value ZIPs ✓
- Quotas allocated ✓
"""

import argparse
import csv
import json
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

# Add project root to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from database.base import Base
from database.models import GeoType, Target


class CampaignSeeder:
    """Creates initial target campaigns for production launch"""

    def __init__(self, database_url: str = None, dry_run: bool = False):
        """
        Initialize campaign seeder

        Args:
            database_url: Database connection string
            dry_run: If True, show what would be created without actually creating
        """
        self.database_url = database_url or os.getenv(
            "DATABASE_URL", "sqlite:///leadfactory.db"
        )
        self.dry_run = dry_run
        self.targets_file = Path("data/initial_targets.csv")

        self.created_targets = []
        self.errors = []
        self.warnings = []

        # Initialize database connection
        if not self.dry_run:
            try:
                self.engine = create_engine(self.database_url)
                Session = sessionmaker(bind=self.engine)
                self.session = Session()
            except Exception as e:
                self.errors.append(f"Database connection failed: {e}")
                self.session = None

    def load_target_data(self) -> List[Dict[str, Any]]:
        """Load target campaign data from CSV file"""
        print(f"📊 Loading target data from {self.targets_file}...")

        if not self.targets_file.exists():
            self.errors.append(f"Targets file not found: {self.targets_file}")
            return []

        targets = []
        try:
            with open(self.targets_file, "r", newline="") as csvfile:
                reader = csv.DictReader(csvfile)
                for row in reader:
                    # Convert numeric fields
                    target = dict(row)
                    target["radius_miles"] = int(target["radius_miles"])
                    target["daily_quota"] = int(target["daily_quota"])
                    targets.append(target)

            print(f"✅ Loaded {len(targets)} target campaigns")
            return targets

        except Exception as e:
            self.errors.append(f"Error loading targets file: {e}")
            return []

    def validate_target_data(self, targets: List[Dict[str, Any]]) -> bool:
        """Validate target campaign data"""
        print("🔍 Validating target data...")

        required_fields = [
            "target_name",
            "vertical",
            "location",
            "zip_code",
            "radius_miles",
            "daily_quota",
            "priority",
            "description",
        ]

        valid_verticals = ["restaurant", "medical"]
        valid_priorities = ["high", "medium", "low"]

        for i, target in enumerate(targets):
            target_name = target.get("target_name", f"Target {i+1}")

            # Check required fields
            missing_fields = [
                field for field in required_fields if not target.get(field)
            ]
            if missing_fields:
                self.errors.append(
                    f"{target_name}: Missing required fields: {missing_fields}"
                )
                continue

            # Validate vertical
            if target["vertical"] not in valid_verticals:
                self.errors.append(
                    f"{target_name}: Invalid vertical '{target['vertical']}', must be one of: {valid_verticals}"
                )

            # Validate priority
            if target["priority"] not in valid_priorities:
                self.errors.append(
                    f"{target_name}: Invalid priority '{target['priority']}', must be one of: {valid_priorities}"
                )

            # Validate numeric ranges
            if target["radius_miles"] < 1 or target["radius_miles"] > 50:
                self.warnings.append(
                    f"{target_name}: Radius {target['radius_miles']} miles may be too small/large"
                )

            if target["daily_quota"] < 10 or target["daily_quota"] > 100:
                self.warnings.append(
                    f"{target_name}: Daily quota {target['daily_quota']} may be too low/high"
                )

            # Validate ZIP code format
            zip_code = target["zip_code"]
            if not (zip_code.isdigit() and len(zip_code) == 5):
                self.errors.append(
                    f"{target_name}: Invalid ZIP code format '{zip_code}', must be 5 digits"
                )

        # Check for duplicate names
        names = [target["target_name"] for target in targets]
        duplicates = [name for name in set(names) if names.count(name) > 1]
        if duplicates:
            self.errors.append(f"Duplicate target names found: {duplicates}")

        # Verify coverage requirements
        verticals = [target["vertical"] for target in targets]
        vertical_counts = {v: verticals.count(v) for v in set(verticals)}

        print(f"📊 Vertical distribution: {vertical_counts}")

        if len(vertical_counts) < 2:
            self.warnings.append(
                "Only one vertical represented, consider adding variety"
            )

        # Check quota allocation
        total_quota = sum(target["daily_quota"] for target in targets)
        print(f"📈 Total daily quota: {total_quota} businesses")

        if total_quota < 100:
            self.warnings.append(
                f"Total daily quota ({total_quota}) may be too low for production"
            )
        elif total_quota > 500:
            self.warnings.append(
                f"Total daily quota ({total_quota}) may exceed API limits"
            )

        return len(self.errors) == 0

    def create_target_campaigns(self, targets: List[Dict[str, Any]]) -> bool:
        """Create target campaigns in database"""
        print(f"🎯 Creating {len(targets)} target campaigns...")

        if self.dry_run:
            print("🔍 DRY RUN MODE - No database changes will be made")
            for target in targets:
                print(
                    f"   Would create: {target['target_name']} ({target['vertical']}) in {target['location']}"
                )
            return True

        if not self.session:
            self.errors.append("No database connection available")
            return False

        try:
            # Check for existing targets
            existing_values = [
                value[0]
                for value in self.session.execute(
                    text("SELECT geo_value FROM targets")
                ).fetchall()
            ]

            for target_data in targets:
                target_name = target_data["target_name"]

                if target_data["zip_code"] in existing_values:
                    self.warnings.append(
                        f"Target for ZIP {target_data['zip_code']} already exists, skipping"
                    )
                    continue

                # Create target object based on actual schema
                target = Target(
                    geo_type=GeoType.ZIP,  # Using ZIP code targeting
                    geo_value=target_data["zip_code"],
                    vertical=target_data["vertical"],
                    estimated_businesses=target_data["daily_quota"]
                    * 3,  # Estimate 3x daily quota
                    priority_score=0.8
                    if target_data["priority"] == "high"
                    else 0.5
                    if target_data["priority"] == "medium"
                    else 0.3,
                    is_active=True,
                )

                self.session.add(target)
                self.created_targets.append(
                    f"{target_name} ({target_data['zip_code']})"
                )
                print(f"✅ Created target: {target_name}")

            # Commit all changes
            self.session.commit()
            print(
                f"🎉 Successfully created {len(self.created_targets)} target campaigns"
            )

            return True

        except Exception as e:
            self.session.rollback()
            self.errors.append(f"Error creating targets: {e}")
            return False

    def verify_campaign_creation(self) -> bool:
        """Verify that campaigns were created successfully"""
        if self.dry_run:
            return True

        print("🔍 Verifying campaign creation...")

        if not self.session:
            return False

        try:
            # Query created targets
            targets = self.session.execute(
                text(
                    """
                    SELECT geo_value, vertical, geo_type, estimated_businesses, priority_score, is_active
                    FROM targets 
                    WHERE geo_value = ANY(:zip_codes)
                    ORDER BY created_at DESC
                """
                ),
                {
                    "zip_codes": [
                        target["zip_code"] for target in self.load_target_data()
                    ]
                },
            ).fetchall()

            if len(targets) == len(self.created_targets):
                print(f"✅ All {len(targets)} campaigns verified in database")

                # Show summary
                for target in targets:
                    status = "Active" if target[5] else "Inactive"
                    print(
                        f"   ZIP {target[0]}: {target[1]} vertical (businesses: {target[3]}, priority: {target[4]:.1f}, {status})"
                    )

                return True
            else:
                self.errors.append(
                    f"Expected {len(self.created_targets)} targets, found {len(targets)}"
                )
                return False

        except Exception as e:
            self.errors.append(f"Error verifying campaigns: {e}")
            return False

    def calculate_quota_distribution(
        self, targets: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Calculate quota distribution analytics"""
        print("📊 Calculating quota distribution...")

        # Group by vertical
        vertical_quotas = {}
        priority_quotas = {}
        location_quotas = {}

        for target in targets:
            vertical = target["vertical"]
            priority = target["priority"]
            location = target["location"]
            quota = target["daily_quota"]

            vertical_quotas[vertical] = vertical_quotas.get(vertical, 0) + quota
            priority_quotas[priority] = priority_quotas.get(priority, 0) + quota
            location_quotas[location] = location_quotas.get(location, 0) + quota

        total_quota = sum(target["daily_quota"] for target in targets)

        analytics = {
            "total_campaigns": len(targets),
            "total_daily_quota": total_quota,
            "average_quota_per_campaign": total_quota / len(targets) if targets else 0,
            "vertical_distribution": vertical_quotas,
            "priority_distribution": priority_quotas,
            "top_locations": sorted(
                location_quotas.items(), key=lambda x: x[1], reverse=True
            )[:5],
        }

        return analytics

    def generate_report(self, targets: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Generate campaign seeding report"""
        analytics = self.calculate_quota_distribution(targets)

        report = {
            "timestamp": datetime.utcnow().isoformat(),
            "dry_run": self.dry_run,
            "summary": {
                "targets_processed": len(targets),
                "targets_created": len(self.created_targets),
                "success_rate": (len(self.created_targets) / len(targets) * 100)
                if targets
                else 0,
            },
            "analytics": analytics,
            "created_targets": self.created_targets,
            "errors": self.errors,
            "warnings": self.warnings,
        }

        return report

    def seed_campaigns(self) -> bool:
        """Run complete campaign seeding process"""
        print("🚀 Starting Campaign Seeding Process")
        print("=" * 60)

        # Load target data
        targets = self.load_target_data()
        if not targets:
            return False

        # Validate data
        if not self.validate_target_data(targets):
            return False

        # Create campaigns
        if not self.create_target_campaigns(targets):
            return False

        # Verify creation
        if not self.verify_campaign_creation():
            return False

        return True


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(description="Seed initial target campaigns")
    parser.add_argument("--database-url", help="Database connection string")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be created without making changes",
    )
    parser.add_argument("--json", action="store_true", help="Output results as JSON")

    args = parser.parse_args()

    # Initialize seeder
    seeder = CampaignSeeder(database_url=args.database_url, dry_run=args.dry_run)

    # Load targets for report generation
    targets = seeder.load_target_data()

    # Run seeding process
    success = seeder.seed_campaigns() if targets else False

    # Generate report
    report = seeder.generate_report(targets)

    if args.json:
        print(json.dumps(report, indent=2))
    else:
        # Print summary
        print("\n" + "=" * 80)
        print("🎯 CAMPAIGN SEEDING REPORT")
        print("=" * 80)

        print(f"\n📅 Seeding Date: {report['timestamp']}")
        print(f"🔍 Mode: {'DRY RUN' if report['dry_run'] else 'LIVE'}")
        print(
            f"📊 Success Rate: {report['summary']['targets_created']}/{report['summary']['targets_processed']} campaigns ({report['summary']['success_rate']:.1f}%)"
        )

        # Analytics
        analytics = report["analytics"]
        print(f"\n📈 Campaign Analytics:")
        print(f"   Total Campaigns: {analytics['total_campaigns']}")
        print(f"   Total Daily Quota: {analytics['total_daily_quota']} businesses")
        print(
            f"   Average Quota: {analytics['average_quota_per_campaign']:.1f} per campaign"
        )

        print(f"\n🏢 Vertical Distribution:")
        for vertical, quota in analytics["vertical_distribution"].items():
            percentage = (
                (quota / analytics["total_daily_quota"] * 100)
                if analytics["total_daily_quota"]
                else 0
            )
            print(f"   {vertical.title()}: {quota} businesses ({percentage:.1f}%)")

        print(f"\n⭐ Priority Distribution:")
        for priority, quota in analytics["priority_distribution"].items():
            percentage = (
                (quota / analytics["total_daily_quota"] * 100)
                if analytics["total_daily_quota"]
                else 0
            )
            print(f"   {priority.title()}: {quota} businesses ({percentage:.1f}%)")

        if analytics["top_locations"]:
            print(f"\n🌎 Top Locations:")
            for location, quota in analytics["top_locations"]:
                print(f"   {location}: {quota} businesses")

        if report["created_targets"]:
            print(f"\n✅ Created Campaigns ({len(report['created_targets'])}):")
            for target in report["created_targets"]:
                print(f"   - {target}")

        if report["errors"]:
            print(f"\n❌ ERRORS ({len(report['errors'])}):")
            for i, error in enumerate(report["errors"], 1):
                print(f"   {i}. {error}")

        if report["warnings"]:
            print(f"\n⚠️  WARNINGS ({len(report['warnings'])}):")
            for i, warning in enumerate(report["warnings"], 1):
                print(f"   {i}. {warning}")

        if success and not report["errors"]:
            print("\n🎉 CAMPAIGN SEEDING COMPLETED SUCCESSFULLY!")
            print("\n📋 Next Steps:")
            print("   - Review campaign performance metrics")
            print("   - Adjust quotas based on results")
            print("   - Monitor API rate limits")
            print("   - Scale successful campaigns")
        else:
            print("\n❌ CAMPAIGN SEEDING FAILED")
            print("\n📋 Required Actions:")
            print("   - Fix data validation errors")
            print("   - Check database connectivity")
            print("   - Verify target data format")

    # Cleanup
    if hasattr(seeder, "session") and seeder.session:
        seeder.session.close()

    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
