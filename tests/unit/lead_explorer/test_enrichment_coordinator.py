"""
Test Lead Explorer enrichment coordinator
"""

from datetime import datetime
from unittest.mock import AsyncMock, Mock, patch

from database.models import EnrichmentStatus
from lead_explorer.enrichment_coordinator import EnrichmentCoordinator, get_enrichment_coordinator, quick_add_enrichment


class TestEnrichmentCoordinator:
    """Test EnrichmentCoordinator functionality"""

    def test_init(self):
        """Test coordinator initialization"""
        coordinator = EnrichmentCoordinator()

        assert coordinator.email_enricher is not None
        assert coordinator._active_tasks == {}

    @patch("lead_explorer.enrichment_coordinator.SessionLocal")
    @patch("lead_explorer.enrichment_coordinator.LeadRepository")
    async def test_start_enrichment(self, mock_repo_class, mock_session_class, created_lead):
        """Test starting enrichment process"""
        # Setup mocks
        mock_session = Mock()
        mock_session_class.return_value.__enter__.return_value = mock_session

        mock_repo = Mock()
        mock_repo_class.return_value = mock_repo

        coordinator = EnrichmentCoordinator()

        lead_data = {
            "id": created_lead.id,
            "email": created_lead.email,
            "domain": created_lead.domain,
            "company_name": created_lead.company_name,
        }

        with patch.object(coordinator, "_enrich_lead_async", new_callable=AsyncMock):
            task_id = await coordinator.start_enrichment(created_lead.id, lead_data)

        # Should return a task ID
        assert task_id is not None
        assert len(task_id) > 0

        # Should update lead status to IN_PROGRESS
        mock_repo.update_enrichment_status.assert_called_once()

    def test_prepare_business_data(self):
        """Test converting lead data to business data format"""
        coordinator = EnrichmentCoordinator()

        lead_data = {
            "id": "lead-123",
            "email": "test@example.com",
            "domain": "example.com",
            "company_name": "Test Corp",
        }

        business_data = coordinator._prepare_business_data(lead_data)

        assert business_data["email"] == "test@example.com"
        assert business_data["domain"] == "example.com"
        assert business_data["website"] == "https://example.com"
        assert business_data["name"] == "Test Corp"
        assert business_data["lead_id"] == "lead-123"

    def test_prepare_business_data_minimal(self):
        """Test converting minimal lead data"""
        coordinator = EnrichmentCoordinator()

        lead_data = {"id": "lead-123", "domain": "example.com"}

        business_data = coordinator._prepare_business_data(lead_data)

        assert business_data["domain"] == "example.com"
        assert business_data["website"] == "https://example.com"
        assert business_data["lead_id"] == "lead-123"
        assert "email" not in business_data
        assert "name" not in business_data

    @patch("lead_explorer.enrichment_coordinator.SessionLocal")
    @patch("lead_explorer.enrichment_coordinator.LeadRepository")
    def test_update_lead_status(self, mock_repo_class, mock_session_class):
        """Test updating lead enrichment status"""
        # Setup mocks
        mock_session = Mock()
        mock_session_class.return_value.__enter__.return_value = mock_session

        mock_repo = Mock()
        mock_repo_class.return_value = mock_repo

        coordinator = EnrichmentCoordinator()

        coordinator._update_lead_status(lead_id="test-lead", status=EnrichmentStatus.COMPLETED, task_id="task-123")

        mock_repo.update_enrichment_status.assert_called_once_with(
            lead_id="test-lead", status=EnrichmentStatus.COMPLETED, task_id="task-123", error=None
        )

    @patch("lead_explorer.enrichment_coordinator.SessionLocal")
    @patch("lead_explorer.enrichment_coordinator.LeadRepository")
    def test_update_lead_status_with_error(self, mock_repo_class, mock_session_class):
        """Test updating lead status with error"""
        # Setup mocks
        mock_session = Mock()
        mock_session_class.return_value.__enter__.return_value = mock_session

        mock_repo = Mock()
        mock_repo_class.return_value = mock_repo

        coordinator = EnrichmentCoordinator()

        coordinator._update_lead_status(
            lead_id="test-lead", status=EnrichmentStatus.FAILED, task_id="task-123", error="Test error"
        )

        mock_repo.update_enrichment_status.assert_called_once_with(
            lead_id="test-lead", status=EnrichmentStatus.FAILED, task_id="task-123", error="Test error"
        )

    @patch("lead_explorer.enrichment_coordinator.SessionLocal")
    @patch("lead_explorer.enrichment_coordinator.LeadRepository")
    def test_update_lead_with_enrichment(self, mock_repo_class, mock_session_class):
        """Test updating lead with enriched data"""
        # Setup mocks
        mock_session = Mock()
        mock_session_class.return_value.__enter__.return_value = mock_session

        mock_repo = Mock()
        mock_lead = Mock()
        mock_lead.email = None  # Lead doesn't have email
        mock_repo.get_lead_by_id.return_value = mock_lead
        mock_repo_class.return_value = mock_repo

        coordinator = EnrichmentCoordinator()

        coordinator._update_lead_with_enrichment(
            lead_id="test-lead", enriched_email="enriched@example.com", email_source="hunter"
        )

        # Should update the lead with enriched email
        mock_repo.update_lead.assert_called_once_with("test-lead", {"email": "enriched@example.com"})

    @patch("lead_explorer.enrichment_coordinator.SessionLocal")
    @patch("lead_explorer.enrichment_coordinator.LeadRepository")
    def test_update_lead_with_enrichment_existing_email(self, mock_repo_class, mock_session_class):
        """Test that enriched email doesn't overwrite existing email"""
        # Setup mocks
        mock_session = Mock()
        mock_session_class.return_value.__enter__.return_value = mock_session

        mock_repo = Mock()
        mock_lead = Mock()
        mock_lead.email = "existing@example.com"  # Lead already has email
        mock_repo.get_lead_by_id.return_value = mock_lead
        mock_repo_class.return_value = mock_repo

        coordinator = EnrichmentCoordinator()

        coordinator._update_lead_with_enrichment(
            lead_id="test-lead", enriched_email="enriched@example.com", email_source="hunter"
        )

        # Should not update the lead since it already has an email
        mock_repo.update_lead.assert_not_called()

    async def test_enrich_lead_async_success(self):
        """Test successful async enrichment"""
        coordinator = EnrichmentCoordinator()

        # Mock email enricher
        coordinator.email_enricher = AsyncMock()
        coordinator.email_enricher.enrich_email.return_value = ("enriched@example.com", "hunter")

        # Mock other methods
        coordinator._update_lead_status = Mock()
        coordinator._update_lead_with_enrichment = Mock()

        lead_data = {"id": "test-lead", "email": "test@example.com", "domain": "example.com"}

        await coordinator._enrich_lead_async("test-lead", lead_data, "task-123")

        # Should update status to COMPLETED (IN_PROGRESS is set in start_enrichment, not _enrich_lead_async)
        assert coordinator._update_lead_status.call_count == 1
        coordinator._update_lead_status.assert_called_with("test-lead", EnrichmentStatus.COMPLETED, "task-123")

        # Should call email enrichment
        coordinator.email_enricher.enrich_email.assert_called_once()

        # Should update lead with enriched data
        coordinator._update_lead_with_enrichment.assert_called_once_with(
            "test-lead", enriched_email="enriched@example.com", email_source="hunter"
        )

        # Should track task
        assert "task-123" in coordinator._active_tasks
        assert coordinator._active_tasks["task-123"]["status"] == "completed"

    async def test_enrich_lead_async_failure(self):
        """Test async enrichment failure"""
        coordinator = EnrichmentCoordinator()

        # Mock email enricher to raise exception
        coordinator.email_enricher = AsyncMock()
        coordinator.email_enricher.enrich_email.side_effect = Exception("Enrichment failed")

        # Mock other methods
        coordinator._update_lead_status = Mock()
        coordinator._update_lead_with_enrichment = Mock()

        lead_data = {"id": "test-lead", "email": "test@example.com", "domain": "example.com"}

        await coordinator._enrich_lead_async("test-lead", lead_data, "task-123")

        # Should update status to FAILED
        coordinator._update_lead_status.assert_called_with(
            "test-lead", EnrichmentStatus.FAILED, "task-123", "Enrichment failed: Enrichment failed"
        )

        # Should track failed task
        assert coordinator._active_tasks["task-123"]["status"] == "failed"
        assert "error" in coordinator._active_tasks["task-123"]

    def test_get_task_status(self):
        """Test getting task status"""
        coordinator = EnrichmentCoordinator()

        # Add a task to tracking
        task_info = {"lead_id": "test-lead", "status": "completed", "started_at": datetime.utcnow()}
        coordinator._active_tasks["task-123"] = task_info

        status = coordinator.get_task_status("task-123")

        assert status == task_info

    def test_get_task_status_not_found(self):
        """Test getting status for non-existent task"""
        coordinator = EnrichmentCoordinator()

        status = coordinator.get_task_status("non-existent")

        assert status is None

    @patch("lead_explorer.enrichment_coordinator.SessionLocal")
    @patch("lead_explorer.enrichment_coordinator.LeadRepository")
    def test_get_lead_enrichment_status(self, mock_repo_class, mock_session_class):
        """Test getting lead enrichment status"""
        # Setup mocks
        mock_session = Mock()
        mock_session_class.return_value.__enter__.return_value = mock_session

        mock_repo = Mock()
        mock_lead = Mock()
        mock_lead.id = "test-lead"
        mock_lead.enrichment_status = EnrichmentStatus.COMPLETED
        mock_lead.enrichment_task_id = "task-123"
        mock_lead.enrichment_error = None
        mock_lead.email = "test@example.com"
        mock_lead.domain = "example.com"
        mock_lead.updated_at = datetime.utcnow()
        mock_repo.get_lead_by_id.return_value = mock_lead
        mock_repo_class.return_value = mock_repo

        coordinator = EnrichmentCoordinator()

        status = coordinator.get_lead_enrichment_status("test-lead")

        assert status["lead_id"] == "test-lead"
        assert status["enrichment_status"] == "completed"
        assert status["enrichment_task_id"] == "task-123"
        assert status["email"] == "test@example.com"

    @patch("lead_explorer.enrichment_coordinator.SessionLocal")
    @patch("lead_explorer.enrichment_coordinator.LeadRepository")
    def test_get_lead_enrichment_status_not_found(self, mock_repo_class, mock_session_class):
        """Test getting status for non-existent lead"""
        # Setup mocks
        mock_session = Mock()
        mock_session_class.return_value.__enter__.return_value = mock_session

        mock_repo = Mock()
        mock_repo.get_lead_by_id.return_value = None
        mock_repo_class.return_value = mock_repo

        coordinator = EnrichmentCoordinator()

        status = coordinator.get_lead_enrichment_status("non-existent")

        assert status is None

    @patch("lead_explorer.enrichment_coordinator.SessionLocal")
    @patch("lead_explorer.enrichment_coordinator.LeadRepository")
    async def test_trigger_batch_enrichment(self, mock_repo_class, mock_session_class):
        """Test triggering batch enrichment"""
        # Setup mocks
        mock_session = Mock()
        mock_session_class.return_value.__enter__.return_value = mock_session

        mock_repo = Mock()

        # Create mock leads
        lead1 = Mock()
        lead1.id = "lead-1"
        lead1.email = "test1@example.com"
        lead1.domain = "example.com"
        lead1.company_name = "Test Corp 1"
        lead1.enrichment_status = EnrichmentStatus.PENDING

        lead2 = Mock()
        lead2.id = "lead-2"
        lead2.email = "test2@example.com"
        lead2.domain = "example2.com"
        lead2.company_name = "Test Corp 2"
        lead2.enrichment_status = EnrichmentStatus.PENDING

        mock_repo.get_lead_by_id.side_effect = [lead1, lead2]
        mock_repo_class.return_value = mock_repo

        coordinator = EnrichmentCoordinator()

        # Mock start_enrichment to avoid actually starting async tasks
        with patch.object(coordinator, "start_enrichment", new_callable=AsyncMock) as mock_start:
            mock_start.side_effect = ["task-1", "task-2"]

            task_ids = await coordinator.trigger_batch_enrichment(["lead-1", "lead-2"])

        assert task_ids == {"lead-1": "task-1", "lead-2": "task-2"}
        assert mock_start.call_count == 2

    def test_cleanup_completed_tasks(self):
        """Test cleaning up old completed tasks"""
        coordinator = EnrichmentCoordinator()

        # Add tasks with different completion times
        old_time = datetime(2023, 1, 1)
        recent_time = datetime.utcnow()

        coordinator._active_tasks = {
            "old-task": {"status": "completed", "completed_at": old_time},
            "recent-task": {"status": "completed", "completed_at": recent_time},
            "running-task": {"status": "running"},
        }

        coordinator.cleanup_completed_tasks(max_age_hours=1)

        # Should remove old completed task but keep recent and running tasks
        assert "old-task" not in coordinator._active_tasks
        assert "recent-task" in coordinator._active_tasks
        assert "running-task" in coordinator._active_tasks


class TestGetEnrichmentCoordinator:
    """Test get_enrichment_coordinator singleton function"""

    def test_get_enrichment_coordinator_singleton(self):
        """Test that function returns same instance"""
        coordinator1 = get_enrichment_coordinator()
        coordinator2 = get_enrichment_coordinator()

        assert coordinator1 is coordinator2
        assert isinstance(coordinator1, EnrichmentCoordinator)


class TestQuickAddEnrichment:
    """Test quick_add_enrichment convenience function"""

    @patch("lead_explorer.enrichment_coordinator.get_enrichment_coordinator")
    async def test_quick_add_enrichment(self, mock_get_coordinator):
        """Test quick add enrichment function"""
        mock_coordinator = AsyncMock()
        mock_coordinator.start_enrichment.return_value = "task-123"
        mock_get_coordinator.return_value = mock_coordinator

        task_id = await quick_add_enrichment(
            lead_id="test-lead", email="test@example.com", domain="example.com", company_name="Test Corp"
        )

        assert task_id == "task-123"

        # Verify coordinator was called with correct data
        mock_coordinator.start_enrichment.assert_called_once_with(
            "test-lead",
            {"id": "test-lead", "email": "test@example.com", "domain": "example.com", "company_name": "Test Corp"},
        )

    @patch("lead_explorer.enrichment_coordinator.get_enrichment_coordinator")
    async def test_quick_add_enrichment_minimal(self, mock_get_coordinator):
        """Test quick add enrichment with minimal data"""
        mock_coordinator = AsyncMock()
        mock_coordinator.start_enrichment.return_value = "task-456"
        mock_get_coordinator.return_value = mock_coordinator

        task_id = await quick_add_enrichment(lead_id="test-lead", domain="example.com")

        assert task_id == "task-456"

        # Verify coordinator was called with minimal data
        mock_coordinator.start_enrichment.assert_called_once_with(
            "test-lead", {"id": "test-lead", "email": None, "domain": "example.com", "company_name": None}
        )
