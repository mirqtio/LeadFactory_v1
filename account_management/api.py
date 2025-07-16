"""
Account Management API Endpoints
Authentication, user management, and organization endpoints
"""
from datetime import datetime, timedelta, timezone
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from account_management.auth_service import AuthService
from account_management.models import (
    AccountUser,
    APIKey,
    Organization,
    Team,
    UserStatus,
)
from account_management.schemas import (
    APIKeyCreate,
    APIKeyCreateResponse,
    APIKeyResponse,
    AuditLogResponse,
    AuthTokenResponse,
    EmailVerificationRequest,
    ErrorResponse,
    OrganizationCreate,
    OrganizationResponse,
    OrganizationStatsResponse,
    PasswordChange,
    PasswordReset,
    PasswordResetRequest,
    RefreshTokenRequest,
    SessionResponse,
    TeamCreate,
    TeamDetailResponse,
    TeamMemberAdd,
    TeamResponse,
    TeamUpdate,
    UserLogin,
    UserProfileResponse,
    UserRegister,
    UserResponse,
    UserUpdate,
)
from core.logging import get_logger
from database.base import get_db

logger = get_logger(__name__)

# Create router
router = APIRouter(prefix="/api/v1/accounts", tags=["accounts"])

# Security
security = HTTPBearer()


# Dependencies
async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db)
) -> AccountUser:
    """Get current authenticated user from JWT token"""
    token = credentials.credentials
    
    try:
        payload = AuthService.decode_token(token)
        
        if payload.get("type") != "access":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token type"
            )
        
        user_id = payload.get("sub")
        if not user_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token"
            )
        
        user = db.query(AccountUser).filter(
            AccountUser.id == user_id,
            AccountUser.status == UserStatus.ACTIVE
        ).first()
        
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User not found"
            )
        
        return user
        
    except Exception as e:
        logger.error(f"Token validation error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials"
        )


async def get_current_user_optional(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
    db: Session = Depends(get_db)
) -> Optional[AccountUser]:
    """Get current user if authenticated, None otherwise"""
    if not credentials:
        return None
    
    try:
        return await get_current_user(credentials, db)
    except HTTPException:
        return None


# Auth endpoints
@router.post("/register", response_model=AuthTokenResponse, status_code=status.HTTP_201_CREATED)
async def register(
    request: Request,
    data: UserRegister,
    db: Session = Depends(get_db)
):
    """Register a new user account"""
    # Check if email already exists
    existing_user = db.query(AccountUser).filter(
        AccountUser.email == data.email.lower()
    ).first()
    
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered"
        )
    
    # Check if username is taken
    if data.username:
        existing_username = db.query(AccountUser).filter(
            AccountUser.username == data.username.lower()
        ).first()
        
        if existing_username:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Username already taken"
            )
    
    # Create organization if provided
    organization = None
    if data.organization_name:
        org_slug = data.organization_name.lower().replace(" ", "-")
        organization = Organization(
            name=data.organization_name,
            slug=org_slug,
            billing_email=data.email
        )
        db.add(organization)
        db.flush()
    
    # Create user
    user = AccountUser(
        email=data.email.lower(),
        username=data.username.lower() if data.username else None,
        password_hash=AuthService.hash_password(data.password.get_secret_value()),
        full_name=data.full_name,
        phone=data.phone,
        timezone=data.timezone,
        locale=data.locale,
        organization_id=organization.id if organization else None,
        status=UserStatus.ACTIVE,
        email_verified=False
    )
    
    db.add(user)
    db.commit()
    db.refresh(user)
    
    # Create default team if organization was created
    if organization:
        default_team = Team(
            name="Default Team",
            slug="default",
            organization_id=organization.id,
            is_default=True
        )
        db.add(default_team)
        db.commit()
    
    # Create session
    access_token, refresh_token, session = AuthService.create_session(
        db,
        user,
        ip_address=request.client.host,
        user_agent=request.headers.get("User-Agent")
    )
    
    # Send verification email (TODO: implement email service)
    verification_token = AuthService.create_email_verification_token(db, user)
    logger.info(f"Verification token for {user.email}: {verification_token}")
    
    return AuthTokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        user=UserResponse.model_validate(user)
    )


@router.post("/login", response_model=AuthTokenResponse)
async def login(
    request: Request,
    data: UserLogin,
    db: Session = Depends(get_db)
):
    """Login with email and password"""
    user = AuthService.authenticate_user(
        db,
        data.email,
        data.password.get_secret_value()
    )
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password"
        )
    
    # Create session
    access_token, refresh_token, session = AuthService.create_session(
        db,
        user,
        ip_address=request.client.host,
        user_agent=request.headers.get("User-Agent"),
        device_id=data.device_id
    )
    
    return AuthTokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        user=UserResponse.model_validate(user)
    )


@router.post("/refresh", response_model=AuthTokenResponse)
async def refresh_token(
    request: Request,
    data: RefreshTokenRequest,
    db: Session = Depends(get_db)
):
    """Refresh access token using refresh token"""
    try:
        payload = AuthService.decode_token(data.refresh_token)
        
        if payload.get("type") != "refresh":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token type"
            )
        
        user_id = payload.get("sub")
        user = db.query(AccountUser).filter(
            AccountUser.id == user_id,
            AccountUser.status == UserStatus.ACTIVE
        ).first()
        
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User not found"
            )
        
        # Create new session
        access_token, new_refresh_token, session = AuthService.create_session(
            db,
            user,
            ip_address=request.client.host,
            user_agent=request.headers.get("User-Agent")
        )
        
        return AuthTokenResponse(
            access_token=access_token,
            refresh_token=new_refresh_token,
            user=UserResponse.model_validate(user)
        )
        
    except Exception as e:
        logger.error(f"Refresh token error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token"
        )


@router.post("/logout")
async def logout(
    current_user: AccountUser = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Logout current session"""
    # TODO: Invalidate current session
    return {"message": "Logged out successfully"}


@router.post("/verify-email")
async def verify_email(
    data: EmailVerificationRequest,
    db: Session = Depends(get_db)
):
    """Verify email address"""
    user = AuthService.verify_email_token(db, data.token)
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired verification token"
        )
    
    return {"message": "Email verified successfully"}


@router.post("/password-reset-request")
async def request_password_reset(
    data: PasswordResetRequest,
    db: Session = Depends(get_db)
):
    """Request password reset token"""
    token = AuthService.create_password_reset_token(db, data.email)
    
    if token:
        # TODO: Send reset email
        logger.info(f"Password reset token for {data.email}: {token}")
    
    # Always return success to prevent email enumeration
    return {"message": "If the email exists, a reset link has been sent"}


@router.post("/password-reset")
async def reset_password(
    data: PasswordReset,
    db: Session = Depends(get_db)
):
    """Reset password using token"""
    user = AuthService.reset_password(
        db,
        data.token,
        data.new_password.get_secret_value()
    )
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired reset token"
        )
    
    return {"message": "Password reset successfully"}


# User profile endpoints
@router.get("/me", response_model=UserProfileResponse)
async def get_current_user_profile(
    current_user: AccountUser = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get current user profile"""
    return UserProfileResponse.model_validate(current_user)


@router.patch("/me", response_model=UserResponse)
async def update_profile(
    data: UserUpdate,
    current_user: AccountUser = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Update current user profile"""
    # Check username uniqueness
    if data.username and data.username != current_user.username:
        existing = db.query(AccountUser).filter(
            AccountUser.username == data.username.lower(),
            AccountUser.id != current_user.id
        ).first()
        
        if existing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Username already taken"
            )
    
    # Update fields
    update_data = data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(current_user, field, value)
    
    db.commit()
    db.refresh(current_user)
    
    return UserResponse.model_validate(current_user)


@router.post("/me/change-password")
async def change_password(
    data: PasswordChange,
    current_user: AccountUser = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Change current user password"""
    # Verify current password
    if not AuthService.verify_password(
        data.current_password.get_secret_value(),
        current_user.password_hash
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Current password is incorrect"
        )
    
    # Update password
    current_user.password_hash = AuthService.hash_password(
        data.new_password.get_secret_value()
    )
    db.commit()
    
    return {"message": "Password changed successfully"}


@router.get("/me/sessions", response_model=List[SessionResponse])
async def get_user_sessions(
    current_user: AccountUser = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get user's active sessions"""
    sessions = db.query(UserSession).filter(
        UserSession.user_id == current_user.id,
        UserSession.is_active == True,
        UserSession.expires_at > datetime.now(timezone.utc)
    ).all()
    
    return [SessionResponse.model_validate(s) for s in sessions]


# Organization endpoints
@router.get("/organizations/current", response_model=OrganizationResponse)
async def get_current_organization(
    current_user: AccountUser = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get current user's organization"""
    if not current_user.organization_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User is not part of an organization"
        )
    
    return OrganizationResponse.model_validate(current_user.organization)


@router.post("/organizations", response_model=OrganizationResponse, status_code=status.HTTP_201_CREATED)
async def create_organization(
    data: OrganizationCreate,
    current_user: AccountUser = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Create a new organization"""
    if current_user.organization_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User already belongs to an organization"
        )
    
    # Check slug uniqueness
    existing = db.query(Organization).filter(
        Organization.slug == data.slug
    ).first()
    
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Organization slug already exists"
        )
    
    # Create organization
    org = Organization(**data.model_dump())
    db.add(org)
    db.flush()
    
    # Add user to organization
    current_user.organization_id = org.id
    
    # Create default team
    default_team = Team(
        name="Default Team",
        slug="default",
        organization_id=org.id,
        is_default=True
    )
    db.add(default_team)
    
    db.commit()
    db.refresh(org)
    
    return OrganizationResponse.model_validate(org)


@router.get("/organizations/current/stats", response_model=OrganizationStatsResponse)
async def get_organization_stats(
    current_user: AccountUser = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get organization statistics"""
    if not current_user.organization_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User is not part of an organization"
        )
    
    # Get stats
    total_users = db.query(AccountUser).filter(
        AccountUser.organization_id == current_user.organization_id
    ).count()
    
    active_users = db.query(AccountUser).filter(
        AccountUser.organization_id == current_user.organization_id,
        AccountUser.status == UserStatus.ACTIVE
    ).count()
    
    total_teams = db.query(Team).filter(
        Team.organization_id == current_user.organization_id
    ).count()
    
    total_api_keys = db.query(APIKey).filter(
        APIKey.organization_id == current_user.organization_id
    ).count()
    
    active_api_keys = db.query(APIKey).filter(
        APIKey.organization_id == current_user.organization_id,
        APIKey.is_active == True
    ).count()
    
    return OrganizationStatsResponse(
        total_users=total_users,
        active_users=active_users,
        total_teams=total_teams,
        total_api_keys=total_api_keys,
        active_api_keys=active_api_keys
    )


# Team endpoints
@router.get("/teams", response_model=List[TeamResponse])
async def list_teams(
    current_user: AccountUser = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """List user's teams"""
    if not current_user.organization_id:
        return []
    
    teams = db.query(Team).filter(
        Team.organization_id == current_user.organization_id
    ).all()
    
    return [TeamResponse.model_validate(t) for t in teams]


@router.post("/teams", response_model=TeamResponse, status_code=status.HTTP_201_CREATED)
async def create_team(
    data: TeamCreate,
    current_user: AccountUser = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Create a new team"""
    if not current_user.organization_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User must belong to an organization"
        )
    
    # Check slug uniqueness
    existing = db.query(Team).filter(
        Team.organization_id == current_user.organization_id,
        Team.slug == data.slug
    ).first()
    
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Team slug already exists in organization"
        )
    
    # Create team
    team = Team(
        **data.model_dump(),
        organization_id=current_user.organization_id
    )
    db.add(team)
    db.commit()
    db.refresh(team)
    
    return TeamResponse.model_validate(team)


@router.get("/teams/{team_id}", response_model=TeamDetailResponse)
async def get_team(
    team_id: str,
    current_user: AccountUser = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get team details"""
    team = db.query(Team).filter(
        Team.id == team_id,
        Team.organization_id == current_user.organization_id
    ).first()
    
    if not team:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Team not found"
        )
    
    return TeamDetailResponse.model_validate(team)


# API Key endpoints
@router.get("/api-keys", response_model=List[APIKeyResponse])
async def list_api_keys(
    current_user: AccountUser = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """List user's API keys"""
    keys = db.query(APIKey).filter(
        APIKey.user_id == current_user.id,
        APIKey.is_active == True
    ).all()
    
    return [APIKeyResponse.model_validate(k) for k in keys]


@router.post("/api-keys", response_model=APIKeyCreateResponse, status_code=status.HTTP_201_CREATED)
async def create_api_key(
    data: APIKeyCreate,
    current_user: AccountUser = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Create a new API key"""
    if not current_user.organization_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User must belong to an organization"
        )
    
    # Calculate expiration
    expires_at = None
    if data.expires_in_days:
        expires_at = datetime.now(timezone.utc) + timedelta(days=data.expires_in_days)
    
    # Create API key
    raw_key, api_key = AuthService.create_api_key(
        db,
        current_user,
        data.name,
        data.scopes,
        expires_at
    )
    
    response = APIKeyCreateResponse.model_validate(api_key)
    response.key = raw_key
    
    return response


@router.delete("/api-keys/{key_id}")
async def revoke_api_key(
    key_id: str,
    current_user: AccountUser = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Revoke an API key"""
    api_key = db.query(APIKey).filter(
        APIKey.id == key_id,
        APIKey.user_id == current_user.id
    ).first()
    
    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="API key not found"
        )
    
    api_key.is_active = False
    api_key.revoked_at = datetime.now(timezone.utc)
    db.commit()
    
    return {"message": "API key revoked successfully"}