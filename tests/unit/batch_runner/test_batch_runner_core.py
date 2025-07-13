"""
Core unit tests for Batch Runner module focusing on high coverage
"""
import pytest
from unittest.mock import patch
from datetime import datetime

from batch_runner import models, schemas


class TestBatchRunnerCore:
    """Core tests for batch runner functionality"""

    def test_batch_status_enum(self):
        """Test BatchStatus enum"""
        assert models.BatchStatus.PENDING.value == "pending"
        assert models.BatchStatus.RUNNING.value == "running"
        assert models.BatchStatus.COMPLETED.value == "completed"
        assert models.BatchStatus.FAILED.value == "failed"
        assert models.BatchStatus.CANCELLED.value == "cancelled"

    def test_lead_processing_status_enum(self):
        """Test LeadProcessingStatus enum"""
        assert models.LeadProcessingStatus.PENDING.value == "pending"
        assert models.LeadProcessingStatus.PROCESSING.value == "processing"
        assert models.LeadProcessingStatus.COMPLETED.value == "completed"
        assert models.LeadProcessingStatus.FAILED.value == "failed"
        assert models.LeadProcessingStatus.SKIPPED.value == "skipped"

    def test_create_batch_schema(self):
        """Test CreateBatchSchema validation"""
        # Valid schema
        schema = schemas.CreateBatchSchema(
            lead_ids=["lead-1", "lead-2", "lead-3"],
            template_version="v1"
        )
        assert len(schema.lead_ids) == 3
        assert schema.template_version == "v1"

        # Test validation
        with pytest.raises(Exception):
            schemas.CreateBatchSchema(
                lead_ids=[],  # Empty list should fail
                template_version="v1"
            )

    def test_start_batch_schema(self):
        """Test StartBatchSchema with defaults"""
        schema = schemas.StartBatchSchema(
            name="Test Batch",
            lead_ids=["lead-1"],
            template_version="v1",
            estimated_cost_usd=1.00,
            cost_approved=True,
            created_by="test-user"
        )

        assert schema.name == "Test Batch"
        assert schema.max_concurrent == 5  # default
        assert schema.retry_count == 3  # default
        assert schema.cost_approved is True

    def test_batch_preview_schema(self):
        """Test BatchPreviewSchema"""
        schema = schemas.BatchPreviewSchema(
            lead_count=10,
            valid_lead_ids=["lead-1", "lead-2"],
            template_version="v1",
            estimated_cost_usd=5.00,
            cost_breakdown={"total_cost": 5.00},
            provider_breakdown={},
            estimated_duration_minutes=2.5,
            cost_per_lead=0.50,
            is_within_budget=True,
            budget_warning=None,
            accuracy_note="Estimate accurate within ±5%"
        )

        assert schema.lead_count == 10
        assert schema.estimated_cost_usd == 5.00
        assert schema.is_within_budget is True

    def test_batch_response_schema(self):
        """Test BatchResponseSchema"""
        schema = schemas.BatchResponseSchema(
            id="batch-123",
            name="Test Batch",
            status="running",
            total_leads=10,
            processed_leads=5,
            successful_leads=4,
            failed_leads=1,
            progress_percentage=50.0,
            template_version="v1",
            created_at=datetime.utcnow()
        )

        assert schema.id == "batch-123"
        assert schema.status == "running"
        assert schema.progress_percentage == 50.0

    def test_pagination_schema(self):
        """Test PaginationSchema"""
        # Test defaults
        schema = schemas.PaginationSchema()
        assert schema.skip == 0
        assert schema.limit == 20

        # Test custom values
        schema2 = schemas.PaginationSchema(skip=40, limit=100)
        assert schema2.skip == 40
        assert schema2.limit == 100

    def test_websocket_message_schema(self):
        """Test WebSocketMessageSchema"""
        schema = schemas.WebSocketMessageSchema(
            type="progress",
            batch_id="batch-123",
            data={
                "processed": 50,
                "total": 100,
                "percentage": 50.0
            }
        )

        assert schema.type == "progress"
        assert schema.batch_id == "batch-123"
        assert schema.data["percentage"] == 50.0

    def test_batch_model_creation(self):
        """Test BatchReport model"""
        batch = models.BatchReport(
            name="Test Batch",
            template_version="v1",
            total_leads=100,
            created_by="user-123"
        )

        assert batch.name == "Test Batch"
        assert batch.total_leads == 100
        assert batch.created_by == "user-123"

    def test_batch_lead_model(self):
        """Test BatchReportLead model"""
        lead = models.BatchReportLead(
            batch_id="batch-123",
            lead_id="lead-456",
            order_index=0
        )

        assert lead.batch_id == "batch-123"
        assert lead.lead_id == "lead-456"
        assert lead.order_index == 0

    @patch('batch_runner.cost_calculator.CostRates.get_rates')
    def test_cost_calculator_basic(self, mock_get_rates):
        """Test basic cost calculation"""
        from batch_runner.cost_calculator import CostCalculator

        mock_get_rates.return_value = {
            "report_generation": {
                "base_cost": 0.10,
                "complexity_multiplier": {
                    "v1": 1.0,
                    "standard": 1.0
                }
            },
            "providers": {},
            "discounts": {
                "volume_tiers": [
                    {"min_leads": 0, "max_leads": 100, "discount_percent": 0}
                ]
            }
        }

        calculator = CostCalculator()
        assert calculator.rates is not None

        # Test budget validation
        result = calculator.validate_budget(100.00)
        assert "is_within_budget" in result

    def test_connection_manager_basic(self):
        """Test ConnectionManager initialization"""
        from batch_runner.websocket_manager import ConnectionManager

        manager = ConnectionManager()
        assert hasattr(manager, 'active_connections')
        assert hasattr(manager, 'throttles')
        assert isinstance(manager.active_connections, dict)

    @patch('batch_runner.processor.get_settings')
    @patch('batch_runner.processor.get_connection_manager')
    @patch('batch_runner.processor.get_cost_calculator')
    @patch('batch_runner.processor.ThreadPoolExecutor')
    def test_batch_processor_init(self, mock_thread, mock_cost, mock_conn, mock_settings):
        """Test BatchProcessor initialization"""
        from batch_runner.processor import BatchProcessor

        processor = BatchProcessor()
        assert hasattr(processor, 'settings')
        assert hasattr(processor, 'connection_manager')
        assert hasattr(processor, 'cost_calculator')

    def test_schema_serialization(self):
        """Test schema JSON serialization"""
        schema = schemas.BatchResponseSchema(
            id="batch-123",
            name="Test",
            status="completed",
            total_leads=10,
            processed_leads=10,
            successful_leads=10,
            failed_leads=0,
            progress_percentage=100.0,
            template_version="v1",
            created_at=datetime(2024, 1, 1, 10, 0, 0)
        )

        # Should be JSON serializable
        json_data = schema.model_dump()
        assert json_data["id"] == "batch-123"
        assert json_data["progress_percentage"] == 100.0
        assert isinstance(json_data["created_at"], datetime)
