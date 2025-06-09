"""
Simple test to verify D6 Reports models work in Docker
"""
import pytest
import sys
import os
from datetime import datetime
from decimal import Decimal

# Ensure we can import from project root
sys.path.insert(0, '/app')

# Import models via direct file import to avoid module issues
import importlib.util
spec = importlib.util.spec_from_file_location("d6_models", "/app/d6_reports/models.py")
d6_models = importlib.util.module_from_spec(spec)
spec.loader.exec_module(d6_models)

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, scoped_session

# Import database models to create all tables
spec_models = importlib.util.spec_from_file_location("database_models", "/app/database/models.py")
db_models = importlib.util.module_from_spec(spec_models)
spec_models.loader.exec_module(db_models)

# Import database base 
spec_base = importlib.util.spec_from_file_location("database_base", "/app/database/base.py")
db_base = importlib.util.module_from_spec(spec_base)
spec_base.loader.exec_module(db_base)


@pytest.fixture(scope="function")  
def db_session():
    """Create a database session for testing"""
    engine = create_engine("sqlite:///:memory:", echo=False)
    
    # Manually create d6_reports tables since they're not in the main metadata
    d6_models.ReportGeneration.__table__.create(engine, checkfirst=True)
    d6_models.ReportTemplate.__table__.create(engine, checkfirst=True)
    d6_models.ReportSection.__table__.create(engine, checkfirst=True)
    d6_models.ReportDelivery.__table__.create(engine, checkfirst=True)
    
    # Create all standard tables
    db_base.Base.metadata.create_all(engine)
    
    Session = scoped_session(sessionmaker(bind=engine))
    session = Session()
    
    yield session
    
    session.close()
    Session.remove()


def test_report_generation_creation(db_session):
    """Test creating a ReportGeneration model"""
    # Create report generation
    report = d6_models.ReportGeneration(
        business_id="business-123",
        template_id="template-001",
        report_type=d6_models.ReportType.BUSINESS_AUDIT
    )
    db_session.add(report)
    db_session.commit()
    
    # Verify creation
    assert report.id is not None
    assert report.business_id == "business-123"
    assert report.template_id == "template-001"
    assert report.report_type == d6_models.ReportType.BUSINESS_AUDIT
    assert report.status == d6_models.ReportStatus.PENDING


def test_report_template_creation(db_session):
    """Test creating a ReportTemplate model"""
    template = d6_models.ReportTemplate(
        name="business_audit_v1",
        display_name="Business Audit Report",
        template_type=d6_models.ReportType.BUSINESS_AUDIT,
        format=d6_models.TemplateFormat.HTML
    )
    db_session.add(template)
    db_session.commit()
    
    # Verify creation
    assert template.id is not None
    assert template.name == "business_audit_v1"
    assert template.display_name == "Business Audit Report"
    assert template.template_type == d6_models.ReportType.BUSINESS_AUDIT
    assert template.format == d6_models.TemplateFormat.HTML
    assert template.is_active is True
    assert template.supports_mobile is True
    assert template.supports_print is True


def test_report_section_creation(db_session):
    """Test creating a ReportSection model"""
    # Create template first
    template = d6_models.ReportTemplate(
        name="test_template",
        display_name="Test Template",
        template_type=d6_models.ReportType.BUSINESS_AUDIT
    )
    db_session.add(template)
    db_session.flush()
    
    # Create section
    section = d6_models.ReportSection(
        template_id=template.id,
        name="executive_summary",
        display_name="Executive Summary",
        section_order=1
    )
    db_session.add(section)
    db_session.commit()
    
    # Verify creation
    assert section.id is not None
    assert section.template_id == template.id
    assert section.name == "executive_summary"
    assert section.display_name == "Executive Summary"
    assert section.section_order == 1
    assert section.is_enabled is True


def test_report_delivery_creation(db_session):
    """Test creating a ReportDelivery model"""
    # Create report generation first
    report = d6_models.ReportGeneration(
        business_id="business-123",
        template_id="template-001"
    )
    db_session.add(report)
    db_session.flush()
    
    # Create delivery
    delivery = d6_models.ReportDelivery(
        report_generation_id=report.id,
        delivery_method=d6_models.DeliveryMethod.EMAIL,
        recipient_email="test@example.com"
    )
    db_session.add(delivery)
    db_session.commit()
    
    # Verify creation
    assert delivery.id is not None
    assert delivery.report_generation_id == report.id
    assert delivery.delivery_method == d6_models.DeliveryMethod.EMAIL
    assert delivery.recipient_email == "test@example.com"
    assert delivery.delivery_status == "pending"


def test_template_mobile_responsive_property(db_session):
    """Test mobile responsive property"""
    # Template without mobile CSS
    template1 = d6_models.ReportTemplate(
        name="basic_template",
        display_name="Basic Template",
        template_type=d6_models.ReportType.BUSINESS_AUDIT,
        supports_mobile=True
    )
    
    # Template with mobile CSS
    template2 = d6_models.ReportTemplate(
        name="responsive_template",
        display_name="Responsive Template",
        template_type=d6_models.ReportType.BUSINESS_AUDIT,
        supports_mobile=True,
        mobile_css="@media (max-width: 768px) { body { font-size: 14px; } }"
    )
    
    db_session.add_all([template1, template2])
    db_session.commit()
    
    # Test properties
    assert template1.is_mobile_responsive is False  # No mobile CSS
    assert template2.is_mobile_responsive is True   # Has mobile CSS


def test_template_print_optimized_property(db_session):
    """Test print optimized property"""
    # Template without print CSS
    template1 = d6_models.ReportTemplate(
        name="basic_template",
        display_name="Basic Template",
        template_type=d6_models.ReportType.BUSINESS_AUDIT,
        supports_print=True
    )
    
    # Template with print CSS
    template2 = d6_models.ReportTemplate(
        name="print_template",
        display_name="Print Template",
        template_type=d6_models.ReportType.BUSINESS_AUDIT,
        supports_print=True,
        print_css="@media print { body { color: black; } }"
    )
    
    db_session.add_all([template1, template2])
    db_session.commit()
    
    # Test properties
    assert template1.is_print_optimized is False  # No print CSS
    assert template2.is_print_optimized is True   # Has print CSS


def test_uuid_generation():
    """Test UUID generation utility"""
    uuid1 = d6_models.generate_uuid()
    uuid2 = d6_models.generate_uuid()
    
    # Should be strings
    assert isinstance(uuid1, str)
    assert isinstance(uuid2, str)
    
    # Should be different
    assert uuid1 != uuid2
    
    # Should be valid UUID format
    assert len(uuid1) == 36  # Standard UUID string length
    assert len(uuid2) == 36
    assert "-" in uuid1
    assert "-" in uuid2