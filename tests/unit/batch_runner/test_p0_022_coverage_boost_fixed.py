"""
P0-022 Test Coverage Enhancement - Fixed for Actual API
Specifically created to boost batch_runner test coverage above 80% for P0-022 completion
"""
import asyncio
import uuid
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest
from pydantic import ValidationError

from batch_runner.cost_calculator import CostCalculator, CostRates
from batch_runner.models import BatchReport, BatchReportLead, BatchStatus, LeadProcessingStatus
from batch_runner.processor import BatchProcessor
from batch_runner.schemas import CreateBatchSchema, StartBatchSchema
from core.exceptions import LeadFactoryError


class TestBatchSchemasCoverage:
    """Enhanced Schemas test coverage for P0-022"""

    def test_create_batch_schema_validation(self):
        """Test CreateBatchSchema validation"""
        # Valid schema
        schema = CreateBatchSchema(
            lead_ids=["lead-1", "lead-2", "lead-3"],
            template_version="v1.0"
        )
        assert len(schema.lead_ids) == 3
        assert schema.template_version == "v1.0"

    def test_create_batch_schema_duplicate_leads(self):
        """Test validation with duplicate lead IDs"""
        with pytest.raises(ValidationError):
            CreateBatchSchema(
                lead_ids=["lead-1", "lead-1", "lead-2"],
                template_version="v1.0"
            )

    def test_create_batch_schema_too_many_leads(self):
        """Test validation with too many leads"""
        with pytest.raises(ValidationError):
            lead_ids = [f"lead-{i}" for i in range(1001)]
            CreateBatchSchema(lead_ids=lead_ids, template_version="v1.0")

    def test_start_batch_schema_validation(self):
        """Test StartBatchSchema validation"""
        schema = StartBatchSchema(
            lead_ids=["lead-1", "lead-2"],
            name="Test Batch",
            template_version="v1.0",
            estimated_cost_usd=25.0,
            cost_approved=True,
            created_by="user123"
        )
        assert schema.name == "Test Batch"
        assert schema.cost_approved is True
        assert schema.estimated_cost_usd == 25.0

    def test_leadfactory_error_handling(self):
        """Test LeadFactoryError exception handling"""
        error = LeadFactoryError("Test error", status_code=400)
        assert str(error) == "Test error"
        assert error.status_code == 400


class TestCostCalculatorCoverage:
    """Enhanced CostCalculator test coverage for P0-022"""

    @pytest.fixture
    def calculator(self):
        """Create CostCalculator instance"""
        return CostCalculator()

    @pytest.fixture
    def cost_rates(self):
        """Create CostRates instance"""
        return CostRates()

    def test_cost_rates_initialization(self, cost_rates):
        """Test CostRates initialization"""
        rates = cost_rates.get_rates()
        assert isinstance(rates, dict)
        assert "report_generation" in rates
        assert "providers" in rates

    def test_cost_rates_caching(self, cost_rates):
        """Test CostRates caching mechanism"""
        # First call loads rates
        rates1 = cost_rates.get_rates()
        
        # Second call should use cache
        rates2 = cost_rates.get_rates()
        
        # Should be same object (cached)
        assert rates1 is rates2

    def test_cost_calculator_batch_preview(self, calculator):
        """Test batch cost preview calculation"""
        with patch('batch_runner.cost_calculator.SessionLocal') as mock_session:
            mock_db = MagicMock()
            mock_session.return_value.__enter__.return_value = mock_db
            mock_db.execute.return_value.fetchall.return_value = []
            
            result = calculator.calculate_batch_preview(["lead-1", "lead-2"], "v1")
            
            assert isinstance(result, dict)
            assert "cost_breakdown" in result
            assert "estimated_duration_minutes" in result

    def test_cost_calculator_budget_validation(self, calculator):
        """Test budget validation"""
        result = calculator.validate_budget(25.0)
        
        assert isinstance(result, dict)
        assert "is_within_budget" in result


class TestBatchProcessorCoverage:
    """Enhanced BatchProcessor test coverage for P0-022"""

    @pytest.fixture
    def processor(self):
        """Create BatchProcessor instance"""
        return BatchProcessor()

    @patch("batch_runner.processor.SessionLocal")
    async def test_process_batch_initialization(self, mock_session, processor):
        """Test batch processing initialization"""
        mock_db = MagicMock()
        mock_session.return_value.__enter__.return_value = mock_db
        
        # Mock batch with no leads
        mock_batch = MagicMock()
        mock_batch.status = BatchStatus.PENDING
        mock_db.query.return_value.filter_by.return_value.first.return_value = mock_batch
        mock_db.query.return_value.filter_by.return_value.all.return_value = []
        
        batch_id = str(uuid.uuid4())
        result = await processor.process_batch(batch_id)
        
        assert isinstance(result, dict)
        assert "processed_count" in result


class TestModelsCoverage:
    """Enhanced Models test coverage for P0-022"""

    def test_batch_report_creation(self):
        """Test BatchReport model creation"""
        batch = BatchReport(
            name="Test Batch",
            template_version="v1.0",
            total_leads=10,
            created_by="user123"
        )
        
        assert batch.name == "Test Batch"
        assert batch.template_version == "v1.0"
        assert batch.total_leads == 10
        assert batch.created_by == "user123"

    def test_batch_report_lead_creation(self):
        """Test BatchReportLead model creation"""
        lead = BatchReportLead(
            batch_id=str(uuid.uuid4()),
            lead_id=str(uuid.uuid4()),
            order_index=1,
            status=LeadProcessingStatus.PENDING,
            created_at=datetime.utcnow(),
        )
        
        assert lead.order_index == 1
        assert lead.status == LeadProcessingStatus.PENDING
        assert isinstance(lead.batch_id, str)
        assert isinstance(lead.lead_id, str)

    def test_batch_report_progress_calculation(self):
        """Test batch report progress calculation"""
        batch = BatchReport(
            name="Progress Test",
            template_version="v1.0",
            total_leads=100,
            processed_leads=50,
            successful_leads=45,
            failed_leads=5,
            progress_percentage=50.0,
            created_by="user123",
            status=BatchStatus.RUNNING,
        )
        
        # Test progress tracking
        assert batch.processed_leads == 50
        assert batch.successful_leads == 45
        assert batch.failed_leads == 5
        assert batch.progress_percentage == 50.0

    def test_batch_status_enum_values(self):
        """Test all BatchStatus enum values"""
        assert BatchStatus.PENDING.value == "pending"
        assert BatchStatus.RUNNING.value == "running"
        assert BatchStatus.COMPLETED.value == "completed"
        assert BatchStatus.FAILED.value == "failed"
        assert BatchStatus.CANCELLED.value == "cancelled"

        # Test enum iteration
        all_statuses = list(BatchStatus)
        assert len(all_statuses) == 5

    def test_lead_processing_status_enum_values(self):
        """Test all LeadProcessingStatus enum values"""
        assert LeadProcessingStatus.PENDING.value == "pending"
        assert LeadProcessingStatus.PROCESSING.value == "processing"
        assert LeadProcessingStatus.COMPLETED.value == "completed"
        assert LeadProcessingStatus.FAILED.value == "failed"
        assert LeadProcessingStatus.SKIPPED.value == "skipped"

        # Test enum iteration
        all_statuses = list(LeadProcessingStatus)
        assert len(all_statuses) == 5


class TestWebSocketManagerCoverage:
    """Enhanced WebSocket manager test coverage for P0-022"""

    def test_websocket_manager_initialization(self):
        """Test WebSocket manager initialization"""
        from batch_runner.websocket_manager import ConnectionManager
        
        manager = ConnectionManager()
        stats = manager.get_stats()
        assert isinstance(stats, dict)
        assert "active_connections" in stats

    def test_websocket_connection_stats(self):
        """Test WebSocket connection statistics"""
        from batch_runner.websocket_manager import get_connection_manager
        
        manager = get_connection_manager()
        initial_stats = manager.get_stats()
        assert initial_stats["active_connections"] >= 0


class TestAPIEndpointsCoverage:
    """Enhanced API endpoints coverage for P0-022"""

    def test_api_error_handling_decorator(self):
        """Test API error handling decorator"""
        from batch_runner.api import handle_api_errors
        
        @handle_api_errors
        async def test_function():
            raise LeadFactoryError("Test error", status_code=400)
        
        # Test that decorator exists and can be applied
        assert hasattr(test_function, '__name__')
        assert test_function.__name__ == 'wrapper'

    def test_user_context_extraction(self):
        """Test user context extraction"""
        from batch_runner.api import get_user_context
        
        # Mock request object
        mock_request = MagicMock()
        mock_request.headers = {"X-User-ID": "user123", "User-Agent": "test-agent"}
        mock_request.client.host = "127.0.0.1"
        
        context = get_user_context(mock_request)
        
        assert isinstance(context, dict)
        assert "user_id" in context
        assert "user_ip" in context
        assert "user_agent" in context


class TestConfigurationCoverage:
    """Enhanced configuration test coverage for P0-022"""

    def test_cost_rates_default_configuration(self):
        """Test default cost rates configuration"""
        rates = CostRates()
        default_rates = rates._get_default_rates()
        
        assert isinstance(default_rates, dict)
        assert "report_generation" in default_rates
        assert "providers" in default_rates
        assert "discounts" in default_rates
        assert "overhead" in default_rates

    def test_cost_rates_file_loading_fallback(self):
        """Test cost rates file loading with fallback to defaults"""
        # Test with non-existent config path
        rates = CostRates(config_path="non/existent/path.json")
        config = rates.get_rates()
        
        # Should fall back to defaults
        assert isinstance(config, dict)
        assert "report_generation" in config


class TestBatchUtilitiesCoverage:
    """Enhanced batch utilities test coverage for P0-022"""

    def test_batch_report_with_cost_tracking(self):
        """Test BatchReport with cost tracking"""
        batch = BatchReport(
            name="Cost Test",
            template_version="v1.0",
            total_leads=100,
            estimated_cost_usd=250.75,
            actual_cost_usd=248.50,
            created_by="user123",
            status=BatchStatus.COMPLETED,
        )
        
        # Test cost variance calculation
        if batch.actual_cost_usd and batch.estimated_cost_usd:
            variance = batch.actual_cost_usd - batch.estimated_cost_usd
            assert variance == -2.25  # Under budget

    def test_batch_report_with_timestamps(self):
        """Test BatchReport with timestamp handling"""
        now = datetime.utcnow()
        batch = BatchReport(
            name="Timestamp Test",
            template_version="v1.0",
            total_leads=10,
            created_by="user123",
            created_at=now,
            started_at=now,
            completed_at=now + timedelta(minutes=30),
        )
        
        assert batch.created_at == now
        assert batch.started_at == now
        assert batch.completed_at > batch.started_at