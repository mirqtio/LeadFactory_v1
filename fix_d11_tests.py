#!/usr/bin/env python3
"""
Fix D11 orchestration test database setup issues
"""

import os

# Read the test file
test_file = 'tests/unit/d11_orchestration/test_api.py'
with open(test_file, 'r') as f:
    content = f.read()

# Remove all skip decorators
skip_patterns = [
    '@pytest.mark.skip(reason="Complex integration tests requiring proper database setup - these work in production but need SQLite table creation fixes for isolated unit testing")',
    '@pytest.mark.skip(reason="Database table creation issues in test environment - functionality works in production")'
]

for pattern in skip_patterns:
    content = content.replace(pattern + '\n', '')
    content = content.replace('    ' + pattern + '\n', '')

# Fix the test_db fixture to properly create all tables
old_fixture = '''@pytest.fixture
def test_db():
    """Create test database session"""
    engine = create_engine(
        "sqlite:///:memory:", connect_args={"check_same_thread": False}
    )

    # Import all models to ensure tables are created
    from d11_orchestration.models import (Experiment, ExperimentVariant,
                                          PipelineRun, VariantAssignment)
    from database.models import Business  # Import other models as needed'''

new_fixture = '''@pytest.fixture
def test_db():
    """Create test database session"""
    engine = create_engine(
        "sqlite:///:memory:", connect_args={"check_same_thread": False}
    )

    # Import ALL models to ensure all tables are created
    from database.models import (
        Business, Target, EmailDelivery, Purchase, Customer,
        Assessment, Report, Campaign, CampaignTarget
    )
    from d1_targeting.models import BatchJob, SearchCriteria, TargetList
    from d2_sourcing.models import BusinessListing, DataSource
    from d3_assessment.models import AssessmentResult
    from d4_enrichment.models import BusinessProfile, EnrichmentResult
    from d5_scoring.models import ScoringResult
    from d6_reports.models import ReportGeneration
    from d7_storefront.models import D7Purchase, PurchaseItem
    from d8_personalization.models import EmailPersonalization
    from d9_delivery.models import EmailDelivery as D9EmailDelivery, DeliveryEvent
    from d10_analytics.models import AnalyticsEvent, EmailEvent
    from d11_orchestration.models import (
        Experiment, ExperimentVariant, PipelineRun, VariantAssignment
    )'''

content = content.replace(old_fixture, new_fixture)

# Add proper table creation
table_creation = '''
    # Create all tables
    Base.metadata.create_all(bind=engine)'''

# Find where to insert table creation
import_end = content.find('from database.models import Business  # Import other models as needed')
if import_end > 0:
    # Find the next line after imports
    next_line = content.find('\n', import_end) + 1
    # Insert table creation
    content = content[:next_line] + table_creation + content[next_line:]

# Write back
with open(test_file, 'w') as f:
    f.write(content)

print("Fixed D11 test file - removed skip decorators and fixed database setup")