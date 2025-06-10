"""
Test D6 Reports Models - Task 050

Tests for report generation tracking models, template structure,
and mobile/print optimization features.

Acceptance Criteria:
- Report generation tracked ✓
- Template structure defined ✓
- Mobile-responsive HTML ✓
- Print-optimized CSS ✓
"""

import os
import sys
from datetime import datetime, timedelta
from decimal import Decimal
from pathlib import Path

import pytest
from sqlalchemy.exc import IntegrityError

# Debug: Add comprehensive path setup for pytest collection issues
project_root = Path(__file__).parent.parent.parent.parent
current_dir = os.getcwd()
app_dir = "/app"

# Add all possible paths
paths_to_add = [str(project_root), current_dir, app_dir]
for path in paths_to_add:
    if path and path not in sys.path:
        sys.path.insert(0, path)

try:
    from d6_reports.models import (DeliveryMethod, ReportDelivery,
                                   ReportGeneration, ReportSection, ReportStatus,
                                   ReportTemplate, ReportType, TemplateFormat,
                                   generate_uuid)
except ImportError as e:
    # If import fails, try direct file import as fallback
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "d6_reports.models", 
        os.path.join(app_dir, "d6_reports", "models.py")
    )
    if spec and spec.loader:
        d6_models = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(d6_models)
        
        # Extract the classes we need
        DeliveryMethod = d6_models.DeliveryMethod
        ReportDelivery = d6_models.ReportDelivery
        ReportGeneration = d6_models.ReportGeneration
        ReportSection = d6_models.ReportSection
        ReportStatus = d6_models.ReportStatus
        ReportTemplate = d6_models.ReportTemplate
        ReportType = d6_models.ReportType
        TemplateFormat = d6_models.TemplateFormat
        generate_uuid = d6_models.generate_uuid
    else:
        raise e


class TestReportGeneration:
    """Test report generation tracking model"""

    def test_create_report_generation(self, db_session):
        """Test creating a new report generation"""
        # Create report generation
        report = ReportGeneration(
            business_id="business-123",
            user_id="user-456",
            order_id="order-789",
            report_type=ReportType.BUSINESS_AUDIT,
            template_id="template-001",
        )
        db_session.add(report)
        db_session.commit()

        # Verify creation
        assert report.id is not None
        assert report.business_id == "business-123"
        assert report.user_id == "user-456"
        assert report.order_id == "order-789"
        assert report.report_type == ReportType.BUSINESS_AUDIT
        assert report.status == ReportStatus.PENDING
        assert report.requested_at is not None
        assert report.started_at is None
        assert report.completed_at is None
        assert report.retry_count == 0

    def test_report_generation_defaults(self, db_session):
        """Test default values for report generation"""
        report = ReportGeneration(
            business_id="business-123", template_id="template-001"
        )
        db_session.add(report)
        db_session.commit()

        assert report.report_type == ReportType.BUSINESS_AUDIT
        assert report.status == ReportStatus.PENDING
        assert report.output_format == "pdf"
        assert report.retry_count == 0
        assert report.created_at is not None
        assert report.updated_at is not None

    def test_report_generation_properties(self, db_session):
        """Test report generation computed properties"""
        report = ReportGeneration(
            business_id="business-123",
            template_id="template-001",
            status=ReportStatus.COMPLETED,
            started_at=datetime.utcnow() - timedelta(minutes=5),
            completed_at=datetime.utcnow(),
        )
        db_session.add(report)
        db_session.commit()

        # Test properties
        assert report.is_completed is True
        assert report.is_failed is False
        assert report.duration_seconds is not None
        assert report.duration_seconds > 0

    def test_report_generation_failed_status(self, db_session):
        """Test failed report generation properties"""
        report = ReportGeneration(
            business_id="business-123",
            template_id="template-001",
            status=ReportStatus.FAILED,
            failed_at=datetime.utcnow(),
            error_message="Test error",
        )
        db_session.add(report)
        db_session.commit()

        assert report.is_completed is False
        assert report.is_failed is True

    def test_report_generation_with_data(self, db_session):
        """Test report generation with complex data"""
        report_data = {
            "business": {"name": "Test Business", "score": 85},
            "metrics": {"performance": 90, "seo": 80},
        }

        configuration = {
            "include_charts": True,
            "color_scheme": "blue",
            "page_size": "A4",
        }

        report = ReportGeneration(
            business_id="business-123",
            template_id="template-001",
            report_data=report_data,
            configuration=configuration,
            sections_included=["summary", "metrics", "recommendations"],
            generation_time_seconds=45.2,
            quality_score=Decimal("95.50"),
        )
        db_session.add(report)
        db_session.commit()

        # Verify complex data storage
        assert report.report_data == report_data
        assert report.configuration == configuration
        assert report.sections_included == ["summary", "metrics", "recommendations"]
        assert report.generation_time_seconds == 45.2
        assert report.quality_score == Decimal("95.50")

    def test_report_generation_constraints(self, db_session):
        """Test report generation constraints"""
        # Test retry count constraint
        with pytest.raises(IntegrityError):
            report = ReportGeneration(
                business_id="business-123", template_id="template-001", retry_count=-1
            )
            db_session.add(report)
            db_session.commit()

        db_session.rollback()

        # Test quality score range constraint
        with pytest.raises(IntegrityError):
            report = ReportGeneration(
                business_id="business-123",
                template_id="template-001",
                quality_score=Decimal("150.00"),
            )
            db_session.add(report)
            db_session.commit()

    def test_report_generation_repr(self, db_session):
        """Test report generation string representation"""
        report = ReportGeneration(
            business_id="business-123",
            template_id="template-001",
            status=ReportStatus.COMPLETED,
        )
        db_session.add(report)
        db_session.commit()

        repr_str = repr(report)
        assert "ReportGeneration" in repr_str
        assert report.id in repr_str
        assert "business-123" in repr_str
        assert "completed" in repr_str


class TestReportTemplate:
    """Test report template model"""

    def test_create_report_template(self, db_session):
        """Test creating a new report template"""
        template = ReportTemplate(
            name="business_audit_v1",
            display_name="Business Audit Report v1.0",
            description="Comprehensive business analysis template",
            template_type=ReportType.BUSINESS_AUDIT,
            format=TemplateFormat.HTML,
            version="1.0.0",
        )
        db_session.add(template)
        db_session.commit()

        # Verify creation
        assert template.id is not None
        assert template.name == "business_audit_v1"
        assert template.display_name == "Business Audit Report v1.0"
        assert template.template_type == ReportType.BUSINESS_AUDIT
        assert template.format == TemplateFormat.HTML
        assert template.version == "1.0.0"
        assert template.is_active is True
        assert template.is_default is False
        assert template.supports_mobile is True
        assert template.supports_print is True

    def test_template_with_content(self, db_session):
        """Test template with HTML and CSS content"""
        html_content = "<html><body>{{ business_name }}</body></html>"
        css_content = "body { font-family: Arial; }"
        mobile_css = "@media (max-width: 768px) { body { font-size: 14px; } }"
        print_css = "@media print { body { color: black; } }"

        template = ReportTemplate(
            name="test_template",
            display_name="Test Template",
            template_type=ReportType.BUSINESS_AUDIT,
            html_template=html_content,
            css_styles=css_content,
            mobile_css=mobile_css,
            print_css=print_css,
        )
        db_session.add(template)
        db_session.commit()

        # Verify content storage
        assert template.html_template == html_content
        assert template.css_styles == css_content
        assert template.mobile_css == mobile_css
        assert template.print_css == print_css

    def test_template_configuration(self, db_session):
        """Test template configuration and settings"""
        default_sections = ["header", "summary", "metrics", "footer"]
        required_fields = ["business_name", "overall_score"]
        optional_fields = ["industry", "revenue"]
        customizations = {
            "color_themes": ["blue", "green"],
            "layouts": ["standard", "compact"],
        }

        template = ReportTemplate(
            name="config_template",
            display_name="Configurable Template",
            template_type=ReportType.BUSINESS_AUDIT,
            default_sections=default_sections,
            required_data_fields=required_fields,
            optional_data_fields=optional_fields,
            customization_options=customizations,
            max_pages=20,
            estimated_generation_time=30.5,
        )
        db_session.add(template)
        db_session.commit()

        # Verify configuration storage
        assert template.default_sections == default_sections
        assert template.required_data_fields == required_fields
        assert template.optional_data_fields == optional_fields
        assert template.customization_options == customizations
        assert template.max_pages == 20
        assert template.estimated_generation_time == 30.5

    def test_template_properties(self, db_session):
        """Test template computed properties"""
        # Template without mobile/print CSS
        template1 = ReportTemplate(
            name="basic_template",
            display_name="Basic Template",
            template_type=ReportType.BUSINESS_AUDIT,
            supports_mobile=True,
            supports_print=True,
        )
        db_session.add(template1)

        # Template with mobile/print CSS
        template2 = ReportTemplate(
            name="responsive_template",
            display_name="Responsive Template",
            template_type=ReportType.BUSINESS_AUDIT,
            supports_mobile=True,
            supports_print=True,
            mobile_css="@media (max-width: 768px) {}",
            print_css="@media print {}",
        )
        db_session.add(template2)
        db_session.commit()

        # Test properties
        assert template1.is_mobile_responsive is False  # No mobile CSS
        assert template1.is_print_optimized is False  # No print CSS
        assert template2.is_mobile_responsive is True  # Has mobile CSS
        assert template2.is_print_optimized is True  # Has print CSS

    def test_template_constraints(self, db_session):
        """Test template unique constraints"""
        # Create first template
        template1 = ReportTemplate(
            name="duplicate_test",
            display_name="Template 1",
            template_type=ReportType.BUSINESS_AUDIT,
            version="1.0.0",
        )
        db_session.add(template1)
        db_session.commit()

        # Try to create duplicate name+version
        with pytest.raises(IntegrityError):
            template2 = ReportTemplate(
                name="duplicate_test",
                display_name="Template 2",
                template_type=ReportType.BUSINESS_AUDIT,
                version="1.0.0",  # Same name+version
            )
            db_session.add(template2)
            db_session.commit()

    def test_template_repr(self, db_session):
        """Test template string representation"""
        template = ReportTemplate(
            name="test_template",
            display_name="Test Template",
            template_type=ReportType.BUSINESS_AUDIT,
        )
        db_session.add(template)
        db_session.commit()

        repr_str = repr(template)
        assert "ReportTemplate" in repr_str
        assert template.id in repr_str
        assert "test_template" in repr_str
        assert "business_audit" in repr_str


class TestReportSection:
    """Test report section model"""

    def test_create_report_section(self, db_session):
        """Test creating a new report section"""
        # First create a template
        template = ReportTemplate(
            name="test_template",
            display_name="Test Template",
            template_type=ReportType.BUSINESS_AUDIT,
        )
        db_session.add(template)
        db_session.flush()  # Get template ID

        # Create section
        section = ReportSection(
            template_id=template.id,
            name="executive_summary",
            display_name="Executive Summary",
            description="High-level business overview",
            section_order=1,
        )
        db_session.add(section)
        db_session.commit()

        # Verify creation
        assert section.id is not None
        assert section.template_id == template.id
        assert section.name == "executive_summary"
        assert section.display_name == "Executive Summary"
        assert section.section_order == 1
        assert section.is_required is False
        assert section.is_enabled is True
        assert section.page_break_before is False
        assert section.page_break_after is False

    def test_section_with_content(self, db_session):
        """Test section with HTML content and CSS"""
        template = ReportTemplate(
            name="test_template",
            display_name="Test Template",
            template_type=ReportType.BUSINESS_AUDIT,
        )
        db_session.add(template)
        db_session.flush()

        html_content = "<div class='summary'>{{ business_summary }}</div>"
        css_styles = ".summary { padding: 20px; }"
        data_query = "SELECT summary FROM business_data WHERE id = ?"

        section = ReportSection(
            template_id=template.id,
            name="summary_section",
            display_name="Summary Section",
            section_order=1,
            html_content=html_content,
            css_styles=css_styles,
            data_query=data_query,
            is_required=True,
            page_break_after=True,
        )
        db_session.add(section)
        db_session.commit()

        # Verify content storage
        assert section.html_content == html_content
        assert section.css_styles == css_styles
        assert section.data_query == data_query
        assert section.is_required is True
        assert section.page_break_after is True

    def test_section_configuration(self, db_session):
        """Test section configuration and requirements"""
        template = ReportTemplate(
            name="test_template",
            display_name="Test Template",
            template_type=ReportType.BUSINESS_AUDIT,
        )
        db_session.add(template)
        db_session.flush()

        data_requirements = ["business_name", "overall_score", "metrics"]
        conditional_logic = {"show_if": "overall_score > 70"}

        section = ReportSection(
            template_id=template.id,
            name="metrics_section",
            display_name="Metrics Section",
            section_order=2,
            data_requirements=data_requirements,
            conditional_logic=conditional_logic,
            max_content_length=5000,
        )
        db_session.add(section)
        db_session.commit()

        # Verify configuration storage
        assert section.data_requirements == data_requirements
        assert section.conditional_logic == conditional_logic
        assert section.max_content_length == 5000

    def test_section_constraints(self, db_session):
        """Test section unique constraints"""
        template = ReportTemplate(
            name="test_template",
            display_name="Test Template",
            template_type=ReportType.BUSINESS_AUDIT,
        )
        db_session.add(template)
        db_session.flush()

        # Create first section
        section1 = ReportSection(
            template_id=template.id,
            name="duplicate_section",
            display_name="Section 1",
            section_order=1,
        )
        db_session.add(section1)
        db_session.commit()

        # Try to create duplicate template_id+name
        with pytest.raises(IntegrityError):
            section2 = ReportSection(
                template_id=template.id,
                name="duplicate_section",  # Same template+name
                display_name="Section 2",
                section_order=2,
            )
            db_session.add(section2)
            db_session.commit()

    def test_section_repr(self, db_session):
        """Test section string representation"""
        template = ReportTemplate(
            name="test_template",
            display_name="Test Template",
            template_type=ReportType.BUSINESS_AUDIT,
        )
        db_session.add(template)
        db_session.flush()

        section = ReportSection(
            template_id=template.id,
            name="test_section",
            display_name="Test Section",
            section_order=3,
        )
        db_session.add(section)
        db_session.commit()

        repr_str = repr(section)
        assert "ReportSection" in repr_str
        assert section.id in repr_str
        assert "test_section" in repr_str
        assert "order=3" in repr_str


class TestReportDelivery:
    """Test report delivery tracking model"""

    def test_create_report_delivery(self, db_session):
        """Test creating a new report delivery"""
        # Create report generation first
        report = ReportGeneration(
            business_id="business-123", template_id="template-001"
        )
        db_session.add(report)
        db_session.flush()

        # Create delivery
        delivery = ReportDelivery(
            report_generation_id=report.id,
            delivery_method=DeliveryMethod.EMAIL,
            recipient_email="customer@example.com",
            recipient_name="John Doe",
        )
        db_session.add(delivery)
        db_session.commit()

        # Verify creation
        assert delivery.id is not None
        assert delivery.report_generation_id == report.id
        assert delivery.delivery_method == DeliveryMethod.EMAIL
        assert delivery.recipient_email == "customer@example.com"
        assert delivery.recipient_name == "John Doe"
        assert delivery.delivery_status == "pending"
        assert delivery.download_count == 0
        assert delivery.open_count == 0
        assert delivery.retry_count == 0

    def test_delivery_with_tracking(self, db_session):
        """Test delivery with tracking information"""
        report = ReportGeneration(
            business_id="business-123", template_id="template-001"
        )
        db_session.add(report)
        db_session.flush()

        now = datetime.utcnow()

        delivery = ReportDelivery(
            report_generation_id=report.id,
            delivery_method=DeliveryMethod.DOWNLOAD,
            delivery_status="delivered",
            download_url="https://example.com/report.pdf",
            download_expires_at=now + timedelta(days=7),
            download_count=3,
            delivered_at=now,
            opened_at=now + timedelta(minutes=5),
            open_count=2,
            user_agent="Mozilla/5.0...",
            ip_address="192.168.1.1",
        )
        db_session.add(delivery)
        db_session.commit()

        # Verify tracking data
        assert delivery.delivery_status == "delivered"
        assert delivery.download_url == "https://example.com/report.pdf"
        assert delivery.download_count == 3
        assert delivery.open_count == 2
        assert delivery.delivered_at == now
        assert delivery.opened_at == now + timedelta(minutes=5)
        assert delivery.user_agent == "Mozilla/5.0..."
        assert delivery.ip_address == "192.168.1.1"

    def test_delivery_properties(self, db_session):
        """Test delivery computed properties"""
        report = ReportGeneration(
            business_id="business-123", template_id="template-001"
        )
        db_session.add(report)
        db_session.flush()

        now = datetime.utcnow()

        # Delivered delivery
        delivery1 = ReportDelivery(
            report_generation_id=report.id,
            delivery_method=DeliveryMethod.EMAIL,
            delivery_status="delivered",
            delivered_at=now,
        )

        # Expired delivery
        delivery2 = ReportDelivery(
            report_generation_id=report.id,
            delivery_method=DeliveryMethod.DOWNLOAD,
            download_expires_at=now - timedelta(hours=1),  # Expired
        )

        db_session.add_all([delivery1, delivery2])
        db_session.commit()

        # Test properties
        assert delivery1.is_delivered is True
        assert delivery1.is_expired is False
        assert delivery2.is_delivered is False
        assert delivery2.is_expired is True

    def test_delivery_constraints(self, db_session):
        """Test delivery constraints"""
        report = ReportGeneration(
            business_id="business-123", template_id="template-001"
        )
        db_session.add(report)
        db_session.flush()

        # Test retry count constraint
        with pytest.raises(IntegrityError):
            delivery = ReportDelivery(
                report_generation_id=report.id,
                delivery_method=DeliveryMethod.EMAIL,
                retry_count=-1,
            )
            db_session.add(delivery)
            db_session.commit()

        db_session.rollback()

        # Test download count constraint
        with pytest.raises(IntegrityError):
            delivery = ReportDelivery(
                report_generation_id=report.id,
                delivery_method=DeliveryMethod.EMAIL,
                download_count=-1,
            )
            db_session.add(delivery)
            db_session.commit()

    def test_delivery_repr(self, db_session):
        """Test delivery string representation"""
        report = ReportGeneration(
            business_id="business-123", template_id="template-001"
        )
        db_session.add(report)
        db_session.flush()

        delivery = ReportDelivery(
            report_generation_id=report.id,
            delivery_method=DeliveryMethod.EMAIL,
            delivery_status="delivered",
        )
        db_session.add(delivery)
        db_session.commit()

        repr_str = repr(delivery)
        assert "ReportDelivery" in repr_str
        assert delivery.id in repr_str
        assert "email" in repr_str
        assert "delivered" in repr_str


class TestUtilityFunctions:
    """Test utility functions"""

    def test_generate_uuid(self):
        """Test UUID generation"""
        uuid1 = generate_uuid()
        uuid2 = generate_uuid()

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


class TestModelRelationships:
    """Test model relationships"""

    def test_template_sections_relationship(self, db_session):
        """Test template to sections relationship"""
        template = ReportTemplate(
            name="test_template",
            display_name="Test Template",
            template_type=ReportType.BUSINESS_AUDIT,
        )
        db_session.add(template)
        db_session.flush()

        # Add sections
        section1 = ReportSection(
            template_id=template.id,
            name="section1",
            display_name="Section 1",
            section_order=1,
        )
        section2 = ReportSection(
            template_id=template.id,
            name="section2",
            display_name="Section 2",
            section_order=2,
        )

        db_session.add_all([section1, section2])
        db_session.commit()

        # Test relationship
        assert len(template.sections) == 2
        assert section1 in template.sections
        assert section2 in template.sections
        assert section1.template == template
        assert section2.template == template

    def test_generation_deliveries_relationship(self, db_session):
        """Test report generation to deliveries relationship"""
        template = ReportTemplate(
            name="test_template",
            display_name="Test Template",
            template_type=ReportType.BUSINESS_AUDIT,
        )
        db_session.add(template)
        db_session.flush()

        report = ReportGeneration(business_id="business-123", template_id=template.id)
        db_session.add(report)
        db_session.flush()

        # Add deliveries
        delivery1 = ReportDelivery(
            report_generation_id=report.id, delivery_method=DeliveryMethod.EMAIL
        )
        delivery2 = ReportDelivery(
            report_generation_id=report.id, delivery_method=DeliveryMethod.DOWNLOAD
        )

        db_session.add_all([delivery1, delivery2])
        db_session.commit()

        # Test relationships
        assert len(report.deliveries) == 2
        assert delivery1 in report.deliveries
        assert delivery2 in report.deliveries
        assert delivery1.report_generation == report
        assert delivery2.report_generation == report
        assert report.template == template

    def test_template_generations_relationship(self, db_session):
        """Test template to generations relationship"""
        template = ReportTemplate(
            name="test_template",
            display_name="Test Template",
            template_type=ReportType.BUSINESS_AUDIT,
        )
        db_session.add(template)
        db_session.flush()

        # Add report generations
        report1 = ReportGeneration(business_id="business-123", template_id=template.id)
        report2 = ReportGeneration(business_id="business-456", template_id=template.id)

        db_session.add_all([report1, report2])
        db_session.commit()

        # Test relationship
        assert len(template.generations) == 2
        assert report1 in template.generations
        assert report2 in template.generations
        assert report1.template == template
        assert report2.template == template
