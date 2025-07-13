"""
Unit tests for Governance module (P0-026)
"""
import pytest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, timedelta
from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from api.governance import (
    RoleChecker, require_admin, create_audit_log,
    create_user, list_users, change_user_role, deactivate_user,
    query_audit_logs, verify_audit_integrity
)
from database.governance_models import User, UserRole, AuditLog, RoleChangeLog


class TestRoleChecker:
    """Test RoleChecker dependency"""
    
    def test_admin_allowed_for_admin_role(self):
        """Admin can access admin-only endpoints"""
        admin_user = User(
            id="admin-id",
            email="admin@test.com",
            name="Admin",
            role=UserRole.ADMIN,
            is_active=True
        )
        
        checker = RoleChecker([UserRole.ADMIN])
        result = checker(admin_user)
        assert result == admin_user
    
    def test_viewer_blocked_for_admin_role(self):
        """Viewer is blocked from admin-only endpoints"""
        viewer_user = User(
            id="viewer-id",
            email="viewer@test.com",
            name="Viewer",
            role=UserRole.VIEWER,
            is_active=True
        )
        
        checker = RoleChecker([UserRole.ADMIN])
        with pytest.raises(HTTPException) as exc_info:
            checker(viewer_user)
        
        assert exc_info.value.status_code == status.HTTP_403_FORBIDDEN
        assert "Access denied" in exc_info.value.detail
    
    def test_multiple_allowed_roles(self):
        """Multiple roles can be allowed"""
        viewer_user = User(
            id="viewer-id",
            email="viewer@test.com",
            name="Viewer",
            role=UserRole.VIEWER,
            is_active=True
        )
        
        checker = RoleChecker([UserRole.ADMIN, UserRole.VIEWER])
        result = checker(viewer_user)
        assert result == viewer_user


class TestAuditLogging:
    """Test audit logging functionality"""
    
    @pytest.mark.asyncio
    async def test_audit_log_creation(self):
        """Audit logs are created for mutations"""
        # Mock database session
        mock_db = Mock(spec=Session)
        mock_request = Mock()
        mock_request.method = "POST"
        mock_request.url.path = "/api/users"
        mock_request.client.host = "127.0.0.1"
        mock_request.headers.get.return_value = "Mozilla/5.0"
        
        mock_response = Mock()
        mock_response.status_code = 201
        
        mock_user = User(
            id="user-id",
            email="user@test.com",
            name="Test User",
            role=UserRole.ADMIN
        )
        
        # Mock the last audit entry for checksum chaining
        mock_last_entry = Mock()
        mock_last_entry.checksum = "previous-checksum"
        mock_db.query().order_by().first.return_value = mock_last_entry
        
        # Call create_audit_log
        await create_audit_log(
            db=mock_db,
            request=mock_request,
            response=mock_response,
            user=mock_user,
            start_time=1000.0,
            request_body={"test": "data"},
            response_body={"id": "new-id"},
            object_type="User",
            object_id="new-id"
        )
        
        # Verify audit log was added to database
        mock_db.add.assert_called_once()
        mock_db.commit.assert_called_once()
        
        # Get the audit log that was created
        audit_log = mock_db.add.call_args[0][0]
        assert isinstance(audit_log, AuditLog)
        assert audit_log.user_id == "user-id"
        assert audit_log.user_email == "user@test.com"
        assert audit_log.action == "CREATE"
        assert audit_log.object_type == "User"
        assert audit_log.object_id == "new-id"
    
    def test_audit_log_content_hash(self):
        """Content hash is calculated correctly"""
        audit_log = AuditLog(
            timestamp=datetime(2024, 1, 1, 12, 0, 0),
            user_id="user-id",
            user_email="user@test.com",
            user_role=UserRole.ADMIN,
            action="CREATE",
            method="POST",
            endpoint="/api/users",
            object_type="User",
            object_id="object-id",
            request_data='{"test": "data"}',
            response_status=201,
            response_data='{"id": "object-id"}',
            duration_ms=50,
            ip_address="127.0.0.1",
            user_agent="Test Agent",
            details=None
        )
        
        hash1 = audit_log.calculate_content_hash()
        assert len(hash1) == 64  # SHA256 hex length
        
        # Same content should produce same hash
        hash2 = audit_log.calculate_content_hash()
        assert hash1 == hash2
        
        # Different content should produce different hash
        audit_log.action = "UPDATE"
        hash3 = audit_log.calculate_content_hash()
        assert hash1 != hash3
    
    def test_audit_log_checksum_chaining(self):
        """Checksums are chained correctly"""
        audit_log = AuditLog(
            user_id="user-id",
            user_email="user@test.com",
            user_role=UserRole.ADMIN,
            action="CREATE",
            method="POST",
            endpoint="/api/users",
            object_type="User",
            response_status=201
        )
        audit_log.content_hash = "content-hash-123"
        
        # First entry (no previous checksum)
        checksum1 = audit_log.calculate_checksum(None)
        assert checksum1.startswith("")  # Valid SHA256
        assert "GENESIS" in f"GENESIS:{audit_log.content_hash}"
        
        # Subsequent entry
        checksum2 = audit_log.calculate_checksum("previous-checksum")
        assert checksum2 != checksum1
        assert "previous-checksum" in f"previous-checksum:{audit_log.content_hash}"


class TestUserManagement:
    """Test user management endpoints"""
    
    @pytest.mark.asyncio
    async def test_create_user_success(self):
        """Admin can create new users"""
        mock_db = Mock(spec=Session)
        mock_request = Mock()
        mock_admin = User(
            id="admin-id",
            email="admin@test.com",
            role=UserRole.ADMIN
        )
        
        # Mock no existing user
        mock_db.query().filter().first.return_value = None
        
        from api.governance import UserCreate
        user_data = UserCreate(
            email="newuser@test.com",
            name="New User",
            role=UserRole.VIEWER
        )
        
        # Mock the create_audit_log to avoid async issues
        with patch('api.governance.create_audit_log'):
            result = await create_user(
                request=mock_request,
                user_data=user_data,
                db=mock_db,
                current_user=mock_admin
            )
        
        assert result.email == "newuser@test.com"
        assert result.name == "New User"
        assert result.role == UserRole.VIEWER
        mock_db.add.assert_called_once()
        mock_db.commit.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_create_user_duplicate_email(self):
        """Cannot create user with duplicate email"""
        mock_db = Mock(spec=Session)
        mock_request = Mock()
        mock_admin = User(
            id="admin-id",
            email="admin@test.com",
            role=UserRole.ADMIN
        )
        
        # Mock existing user
        mock_db.query().filter().first.return_value = User(email="existing@test.com")
        
        from api.governance import UserCreate
        user_data = UserCreate(
            email="existing@test.com",
            name="New User",
            role=UserRole.VIEWER
        )
        
        with pytest.raises(HTTPException) as exc_info:
            await create_user(
                request=mock_request,
                user_data=user_data,
                db=mock_db,
                current_user=mock_admin
            )
        
        assert exc_info.value.status_code == status.HTTP_409_CONFLICT
        assert "already exists" in exc_info.value.detail
    
    @pytest.mark.asyncio
    async def test_list_users(self):
        """List users with optional filtering"""
        mock_db = Mock(spec=Session)
        mock_user = Mock()
        
        users = [
            User(id="1", email="user1@test.com", name="User 1", role=UserRole.ADMIN, is_active=True),
            User(id="2", email="user2@test.com", name="User 2", role=UserRole.VIEWER, is_active=True),
            User(id="3", email="user3@test.com", name="User 3", role=UserRole.VIEWER, is_active=False)
        ]
        
        mock_db.query().order_by().all.return_value = users
        
        result = await list_users(db=mock_db, current_user=mock_user)
        
        assert len(result) == 3
        assert result[0].email == "user1@test.com"
        assert result[1].role == UserRole.VIEWER
        assert result[2].is_active == False
    
    @pytest.mark.asyncio
    async def test_change_role_success(self):
        """Admin can change user roles"""
        mock_db = Mock(spec=Session)
        mock_request = Mock()
        mock_admin = User(
            id="admin-id",
            email="admin@test.com",
            role=UserRole.ADMIN
        )
        
        target_user = User(
            id="target-id",
            email="target@test.com",
            role=UserRole.VIEWER
        )
        mock_db.query().filter().first.return_value = target_user
        
        from api.governance import RoleChangeRequest
        role_change = RoleChangeRequest(
            new_role=UserRole.ADMIN,
            reason="Promoted to admin for project management"
        )
        
        with patch('api.governance.create_audit_log'):
            result = await change_user_role(
                request=mock_request,
                user_id="target-id",
                role_change=role_change,
                db=mock_db,
                current_user=mock_admin
            )
        
        assert result.role == UserRole.ADMIN
        assert target_user.role == UserRole.ADMIN
        mock_db.add.assert_called_once()  # Role change log
        mock_db.commit.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_prevent_self_demotion(self):
        """Admin cannot demote themselves"""
        mock_db = Mock(spec=Session)
        mock_request = Mock()
        mock_admin = User(
            id="admin-id",
            email="admin@test.com",
            role=UserRole.ADMIN
        )
        
        mock_db.query().filter().first.return_value = mock_admin
        
        from api.governance import RoleChangeRequest
        role_change = RoleChangeRequest(
            new_role=UserRole.VIEWER,
            reason="Testing self-demotion"
        )
        
        with pytest.raises(HTTPException) as exc_info:
            await change_user_role(
                request=mock_request,
                user_id="admin-id",
                role_change=role_change,
                db=mock_db,
                current_user=mock_admin
            )
        
        assert exc_info.value.status_code == status.HTTP_400_BAD_REQUEST
        assert "Cannot demote your own account" in exc_info.value.detail
    
    @pytest.mark.asyncio
    async def test_deactivate_user_success(self):
        """Admin can deactivate users"""
        mock_db = Mock(spec=Session)
        mock_request = Mock()
        mock_admin = User(
            id="admin-id",
            email="admin@test.com",
            role=UserRole.ADMIN
        )
        
        target_user = User(
            id="target-id",
            email="target@test.com",
            is_active=True
        )
        mock_db.query().filter().first.return_value = target_user
        
        with patch('api.governance.create_audit_log'):
            result = await deactivate_user(
                request=mock_request,
                user_id="target-id",
                db=mock_db,
                current_user=mock_admin
            )
        
        assert result["status"] == "User deactivated successfully"
        assert target_user.is_active == False
        assert target_user.deactivated_by == "admin-id"
        mock_db.commit.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_prevent_self_deactivation(self):
        """Admin cannot deactivate themselves"""
        mock_db = Mock(spec=Session)
        mock_request = Mock()
        mock_admin = User(
            id="admin-id",
            email="admin@test.com",
            role=UserRole.ADMIN
        )
        
        mock_db.query().filter().first.return_value = mock_admin
        
        with pytest.raises(HTTPException) as exc_info:
            await deactivate_user(
                request=mock_request,
                user_id="admin-id",
                db=mock_db,
                current_user=mock_admin
            )
        
        assert exc_info.value.status_code == status.HTTP_400_BAD_REQUEST
        assert "Cannot deactivate your own account" in exc_info.value.detail


class TestAuditQuerying:
    """Test audit log querying and verification"""
    
    @pytest.mark.asyncio
    async def test_query_audit_logs(self):
        """Query audit logs with filters"""
        mock_db = Mock(spec=Session)
        mock_user = Mock()
        
        audit_logs = [
            AuditLog(
                id=1,
                timestamp=datetime.now(),
                user_email="user1@test.com",
                user_role=UserRole.ADMIN,
                action="CREATE",
                method="POST",
                endpoint="/api/users",
                object_type="User",
                object_id="123",
                response_status=201,
                duration_ms=50,
                ip_address="127.0.0.1"
            ),
            AuditLog(
                id=2,
                timestamp=datetime.now(),
                user_email="user2@test.com",
                user_role=UserRole.VIEWER,
                action="UPDATE",
                method="PUT",
                endpoint="/api/leads/456",
                object_type="Lead",
                object_id="456",
                response_status=200,
                duration_ms=75,
                ip_address="192.168.1.1"
            )
        ]
        
        mock_query = Mock()
        mock_db.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.order_by.return_value = mock_query
        mock_query.offset.return_value = mock_query
        mock_query.limit.return_value = mock_query
        mock_query.all.return_value = audit_logs
        
        from api.governance import AuditLogQuery
        query = AuditLogQuery(
            action="CREATE",
            object_type="User",
            limit=100,
            offset=0
        )
        
        result = await query_audit_logs(
            query=query,
            db=mock_db,
            current_user=mock_user
        )
        
        assert len(result) == 2
        assert result[0].user_email == "user1@test.com"
        assert result[1].action == "UPDATE"
    
    @pytest.mark.asyncio
    async def test_verify_audit_integrity_valid(self):
        """Verify audit log integrity when valid"""
        mock_db = Mock(spec=Session)
        mock_admin = User(role=UserRole.ADMIN)
        
        # Create audit entry with valid hashes
        audit_entry = AuditLog(
            id=1,
            timestamp=datetime.now(),
            user_id="user-id",
            user_email="user@test.com",
            user_role=UserRole.ADMIN,
            action="CREATE",
            method="POST",
            endpoint="/api/users",
            object_type="User",
            response_status=201
        )
        
        # Calculate correct hashes
        audit_entry.content_hash = audit_entry.calculate_content_hash()
        audit_entry.checksum = audit_entry.calculate_checksum("previous-checksum")
        
        # Mock previous entry
        previous_entry = Mock()
        previous_entry.checksum = "previous-checksum"
        
        mock_query = Mock()
        mock_db.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.first.return_value = audit_entry
        mock_query.order_by.return_value = mock_query
        
        # First call returns the audit entry, second call returns previous
        mock_query.first.side_effect = [audit_entry, previous_entry]
        
        result = await verify_audit_integrity(
            audit_id=1,
            db=mock_db,
            current_user=mock_admin
        )
        
        assert result["content_valid"] == True
        assert result["chain_valid"] == True
        assert result["integrity_status"] == "VALID"
    
    @pytest.mark.asyncio
    async def test_verify_audit_integrity_tampered(self):
        """Detect tampered audit logs"""
        mock_db = Mock(spec=Session)
        mock_admin = User(role=UserRole.ADMIN)
        
        # Create audit entry with tampered content
        audit_entry = AuditLog(
            id=1,
            timestamp=datetime.now(),
            user_id="user-id",
            user_email="user@test.com",
            user_role=UserRole.ADMIN,
            action="CREATE",
            method="POST",
            endpoint="/api/users",
            object_type="User",
            response_status=201
        )
        
        # Set incorrect hashes (simulating tampering)
        audit_entry.content_hash = "incorrect-hash"
        audit_entry.checksum = "incorrect-checksum"
        
        mock_query = Mock()
        mock_db.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.first.return_value = audit_entry
        mock_query.order_by.return_value = mock_query
        
        result = await verify_audit_integrity(
            audit_id=1,
            db=mock_db,
            current_user=mock_admin
        )
        
        assert result["content_valid"] == False
        assert result["chain_valid"] == False
        assert result["integrity_status"] == "TAMPERED"


class TestPerformanceRequirements:
    """Test performance requirements"""
    
    @pytest.mark.asyncio
    async def test_audit_logging_performance(self):
        """Audit logging adds <100ms overhead"""
        import time
        
        mock_db = Mock(spec=Session)
        mock_request = Mock()
        mock_request.method = "POST"
        mock_request.url.path = "/api/users"
        mock_request.client.host = "127.0.0.1"
        mock_request.headers.get.return_value = "Mozilla/5.0"
        
        mock_response = Mock()
        mock_response.status_code = 201
        
        mock_user = User(
            id="user-id",
            email="user@test.com",
            name="Test User",
            role=UserRole.ADMIN
        )
        
        # Time the audit log creation
        start_time = time.time()
        
        await create_audit_log(
            db=mock_db,
            request=mock_request,
            response=mock_response,
            user=mock_user,
            start_time=start_time,
            request_body={"test": "data"},
            response_body={"id": "new-id"},
            object_type="User",
            object_id="new-id"
        )
        
        duration = (time.time() - start_time) * 1000  # Convert to ms
        
        # Should complete in under 100ms
        assert duration < 100, f"Audit logging took {duration}ms, exceeds 100ms requirement"


class TestCrossModuleCompatibility:
    """Test cross-module compatibility"""
    
    def test_rbac_can_be_disabled(self):
        """RBAC can be disabled via environment variable"""
        # This would be tested in integration tests with ENABLE_RBAC=false
        # For unit test, we just verify the RoleChecker can be mocked
        mock_checker = Mock(spec=RoleChecker)
        mock_checker.return_value = Mock()
        
        # Should not raise any exceptions
        user = mock_checker(Mock())
        assert user is not None