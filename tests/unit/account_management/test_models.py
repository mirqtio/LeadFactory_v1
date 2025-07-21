"""
Unit tests for account management models
"""

from datetime import UTC, datetime, timedelta, timezone

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from account_management.models import (
    AccountAuditLog,
    AccountUser,
    APIKey,
    AuthProvider,
    EmailVerificationToken,
    Organization,
    PasswordResetToken,
    Permission,
    PermissionAction,
    ResourceType,
    Role,
    Team,
    TeamRole,
    UserSession,
    UserStatus,
    generate_api_key,
    generate_uuid,
)


class TestModelHelpers:
    """Test model helper functions"""

    def test_generate_uuid(self):
        """Test UUID generation"""
        uuid1 = generate_uuid()
        uuid2 = generate_uuid()

        assert isinstance(uuid1, str)
        assert len(uuid1) == 36  # Standard UUID format
        assert uuid1 != uuid2  # Should be unique

    def test_generate_api_key(self):
        """Test API key generation"""
        key1 = generate_api_key()
        key2 = generate_api_key()

        assert isinstance(key1, str)
        assert len(key1) >= 32
        assert key1 != key2  # Should be unique


class TestOrganizationModel:
    """Test Organization model"""

    def test_create_organization(self, db: Session):
        """Test creating organization"""
        org = Organization(
            name="Test Company",
            slug="test-company",
            billing_email="billing@test.com",
            max_users=10,
            max_teams=5,
            max_api_keys=20,
        )

        db.add(org)
        db.commit()

        assert org.id is not None
        assert org.name == "Test Company"
        assert org.slug == "test-company"
        assert org.is_active is True
        assert org.settings == {}
        assert org.created_at is not None
        assert org.updated_at is not None

    def test_organization_unique_slug(self, db: Session):
        """Test organization slug uniqueness"""
        org1 = Organization(name="Company 1", slug="test-slug")
        org2 = Organization(name="Company 2", slug="test-slug")

        db.add(org1)
        db.commit()

        db.add(org2)
        with pytest.raises(IntegrityError):
            db.commit()

    def test_organization_relationships(self, db: Session):
        """Test organization relationships"""
        org = Organization(name="Test Org", slug="test-org")
        db.add(org)
        db.flush()

        # Add user
        user = AccountUser(email="user@test.com", organization_id=org.id, status=UserStatus.ACTIVE)
        db.add(user)

        # Add team
        team = Team(name="Test Team", slug="test-team", organization_id=org.id)
        db.add(team)

        db.commit()
        db.refresh(org)

        assert len(org.users) == 1
        assert org.users[0].email == "user@test.com"
        assert len(org.teams) == 1
        assert org.teams[0].name == "Test Team"


class TestAccountUserModel:
    """Test AccountUser model"""

    def test_create_user(self, db: Session):
        """Test creating user"""
        user = AccountUser(
            email="test@example.com",
            username="testuser",
            password_hash="hashed_password",
            full_name="Test User",
            auth_provider=AuthProvider.LOCAL,
        )

        db.add(user)
        db.commit()

        assert user.id is not None
        assert user.email == "test@example.com"
        assert user.status == UserStatus.ACTIVE
        assert user.email_verified is False
        assert user.mfa_enabled is False
        assert user.failed_login_attempts == 0
        assert user.timezone == "UTC"
        assert user.locale == "en_US"

    def test_user_unique_email(self, db: Session):
        """Test user email uniqueness"""
        user1 = AccountUser(email="test@example.com", status=UserStatus.ACTIVE)
        user2 = AccountUser(email="test@example.com", status=UserStatus.ACTIVE)

        db.add(user1)
        db.commit()

        db.add(user2)
        with pytest.raises(IntegrityError):
            db.commit()

    def test_user_unique_username(self, db: Session):
        """Test user username uniqueness"""
        user1 = AccountUser(email="user1@example.com", username="testuser", status=UserStatus.ACTIVE)
        user2 = AccountUser(email="user2@example.com", username="testuser", status=UserStatus.ACTIVE)

        db.add(user1)
        db.commit()

        db.add(user2)
        with pytest.raises(IntegrityError):
            db.commit()

    def test_user_organization_relationship(self, db: Session):
        """Test user-organization relationship"""
        org = Organization(name="Test Org", slug="test-org")
        db.add(org)
        db.flush()

        user = AccountUser(email="test@example.com", organization_id=org.id, status=UserStatus.ACTIVE)
        db.add(user)
        db.commit()

        db.refresh(user)
        assert user.organization is not None
        assert user.organization.name == "Test Org"


class TestTeamModel:
    """Test Team model"""

    def test_create_team(self, db: Session):
        """Test creating team"""
        org = Organization(name="Test Org", slug="test-org")
        db.add(org)
        db.flush()

        team = Team(name="Engineering", slug="engineering", description="Engineering team", organization_id=org.id)

        db.add(team)
        db.commit()

        assert team.id is not None
        assert team.name == "Engineering"
        assert team.slug == "engineering"
        assert team.is_default is False
        assert team.settings == {}

    def test_team_unique_slug_per_org(self, db: Session):
        """Test team slug uniqueness within organization"""
        org = Organization(name="Test Org", slug="test-org")
        db.add(org)
        db.flush()

        team1 = Team(name="Team 1", slug="test-team", organization_id=org.id)
        team2 = Team(name="Team 2", slug="test-team", organization_id=org.id)

        db.add(team1)
        db.commit()

        db.add(team2)
        with pytest.raises(IntegrityError):
            db.commit()

    def test_team_slug_reusable_across_orgs(self, db: Session):
        """Test team slug can be reused across organizations"""
        org1 = Organization(name="Org 1", slug="org-1")
        org2 = Organization(name="Org 2", slug="org-2")
        db.add_all([org1, org2])
        db.flush()

        team1 = Team(name="Team", slug="engineering", organization_id=org1.id)
        team2 = Team(name="Team", slug="engineering", organization_id=org2.id)

        db.add_all([team1, team2])
        db.commit()  # Should not raise error


class TestRolePermissionModels:
    """Test Role and Permission models"""

    def test_create_permission(self, db: Session):
        """Test creating permission"""
        perm = Permission(resource=ResourceType.LEAD, action=PermissionAction.CREATE, description="Create leads")

        db.add(perm)
        db.commit()

        assert perm.id is not None
        assert perm.resource == ResourceType.LEAD
        assert perm.action == PermissionAction.CREATE

    def test_permission_unique_resource_action(self, db: Session):
        """Test permission resource-action uniqueness"""
        perm1 = Permission(resource=ResourceType.LEAD, action=PermissionAction.CREATE)
        perm2 = Permission(resource=ResourceType.LEAD, action=PermissionAction.CREATE)

        db.add(perm1)
        db.commit()

        db.add(perm2)
        with pytest.raises(IntegrityError):
            db.commit()

    def test_create_role(self, db: Session):
        """Test creating role"""
        role = Role(name="Admin", description="Administrator role", is_system=True)

        db.add(role)
        db.commit()

        assert role.id is not None
        assert role.name == "Admin"
        assert role.is_system is True

    def test_role_permission_relationship(self, db: Session):
        """Test role-permission relationship"""
        # Create permissions
        perm1 = Permission(resource=ResourceType.LEAD, action=PermissionAction.CREATE)
        perm2 = Permission(resource=ResourceType.LEAD, action=PermissionAction.READ)
        db.add_all([perm1, perm2])
        db.flush()

        # Create role with permissions
        role = Role(name="Lead Manager")
        role.permissions = [perm1, perm2]

        db.add(role)
        db.commit()
        db.refresh(role)

        assert len(role.permissions) == 2
        assert perm1 in role.permissions
        assert perm2 in role.permissions


class TestAPIKeyModel:
    """Test APIKey model"""

    def test_create_api_key(self, db: Session):
        """Test creating API key"""
        org = Organization(name="Test Org", slug="test-org")
        db.add(org)
        db.flush()

        user = AccountUser(email="test@example.com", organization_id=org.id, status=UserStatus.ACTIVE)
        db.add(user)
        db.flush()

        api_key = APIKey(
            name="Test API Key",
            key_hash="hash_of_key",
            key_prefix="lf_12345",
            user_id=user.id,
            organization_id=org.id,
            scopes=["read:leads", "write:leads"],
        )

        db.add(api_key)
        db.commit()

        assert api_key.id is not None
        assert api_key.name == "Test API Key"
        assert api_key.is_active is True
        assert api_key.usage_count == 0
        assert api_key.scopes == ["read:leads", "write:leads"]

    def test_api_key_unique_hash(self, db: Session):
        """Test API key hash uniqueness"""
        org = Organization(name="Test Org", slug="test-org")
        user = AccountUser(email="test@example.com", organization_id=org.id, status=UserStatus.ACTIVE)
        db.add_all([org, user])
        db.flush()

        key1 = APIKey(name="Key 1", key_hash="same_hash", key_prefix="lf_1", user_id=user.id, organization_id=org.id)
        key2 = APIKey(name="Key 2", key_hash="same_hash", key_prefix="lf_2", user_id=user.id, organization_id=org.id)

        db.add(key1)
        db.commit()

        db.add(key2)
        with pytest.raises(IntegrityError):
            db.commit()


class TestUserSessionModel:
    """Test UserSession model"""

    def test_create_session(self, db: Session):
        """Test creating user session"""
        user = AccountUser(email="test@example.com", status=UserStatus.ACTIVE)
        db.add(user)
        db.flush()

        session = UserSession(
            user_id=user.id,
            session_token_hash="session_hash",
            refresh_token_hash="refresh_hash",
            ip_address="192.168.1.1",
            user_agent="Mozilla/5.0",
            expires_at=datetime.now(UTC) + timedelta(hours=1),
            refresh_expires_at=datetime.now(UTC) + timedelta(days=30),
        )

        db.add(session)
        db.commit()

        assert session.id is not None
        assert session.is_active is True
        assert session.created_at is not None
        assert session.last_activity_at is not None

    def test_session_unique_tokens(self, db: Session):
        """Test session token uniqueness"""
        user = AccountUser(email="test@example.com", status=UserStatus.ACTIVE)
        db.add(user)
        db.flush()

        session1 = UserSession(
            user_id=user.id, session_token_hash="same_token", expires_at=datetime.now(UTC) + timedelta(hours=1)
        )
        session2 = UserSession(
            user_id=user.id, session_token_hash="same_token", expires_at=datetime.now(UTC) + timedelta(hours=1)
        )

        db.add(session1)
        db.commit()

        db.add(session2)
        with pytest.raises(IntegrityError):
            db.commit()


class TestAuditLogModel:
    """Test AccountAuditLog model"""

    def test_create_audit_log(self, db: Session):
        """Test creating audit log"""
        org = Organization(name="Test Org", slug="test-org")
        user = AccountUser(email="test@example.com", organization_id=org.id, status=UserStatus.ACTIVE)
        db.add_all([org, user])
        db.flush()

        audit = AccountAuditLog(
            user_id=user.id,
            organization_id=org.id,
            action="CREATE",
            resource_type="lead",
            resource_id="lead-123",
            ip_address="192.168.1.1",
            details={"foo": "bar"},
        )

        db.add(audit)
        db.commit()

        assert audit.id is not None
        assert audit.created_at is not None
        assert audit.details == {"foo": "bar"}

    def test_audit_log_nullable_user(self, db: Session):
        """Test audit log with nullable user (for system actions)"""
        org = Organization(name="Test Org", slug="test-org")
        db.add(org)
        db.flush()

        audit = AccountAuditLog(
            user_id=None,  # System action
            organization_id=org.id,
            action="SYSTEM_CLEANUP",
            resource_type="expired_sessions",
        )

        db.add(audit)
        db.commit()

        assert audit.user_id is None


class TestTokenModels:
    """Test token models"""

    def test_create_email_verification_token(self, db: Session):
        """Test creating email verification token"""
        user = AccountUser(email="test@example.com", status=UserStatus.ACTIVE)
        db.add(user)
        db.flush()

        token = EmailVerificationToken(
            user_id=user.id,
            email=user.email,
            token_hash="verification_hash",
            expires_at=datetime.now(UTC) + timedelta(hours=24),
        )

        db.add(token)
        db.commit()

        assert token.id is not None
        assert token.created_at is not None
        assert token.used_at is None

    def test_create_password_reset_token(self, db: Session):
        """Test creating password reset token"""
        user = AccountUser(email="test@example.com", status=UserStatus.ACTIVE)
        db.add(user)
        db.flush()

        token = PasswordResetToken(
            user_id=user.id, token_hash="reset_hash", expires_at=datetime.now(UTC) + timedelta(hours=1)
        )

        db.add(token)
        db.commit()

        assert token.id is not None
        assert token.created_at is not None
        assert token.used_at is None
