# Account Management Module (P2-000)

Comprehensive user authentication, authorization, and organization management system for LeadFactory.

## Overview

The Account Management module provides:
- User registration and authentication
- JWT-based session management
- Organization and team management
- Role-Based Access Control (RBAC)
- API key management
- Audit logging

## Architecture

### Models

- **Organization**: Company/customer accounts
- **AccountUser**: Individual user accounts
- **Team**: Groups within organizations
- **Role**: Named sets of permissions
- **Permission**: Specific resource:action pairs
- **APIKey**: Long-lived authentication tokens
- **UserSession**: JWT session tracking
- **AccountAuditLog**: Immutable audit trail

### Services

- **AuthService**: Core authentication logic
  - Password hashing (bcrypt)
  - JWT token generation/validation
  - Session management
  - API key generation

### API Endpoints

#### Authentication
- `POST /api/v1/accounts/register` - Create new account
- `POST /api/v1/accounts/login` - Login with email/password
- `POST /api/v1/accounts/refresh` - Refresh access token
- `POST /api/v1/accounts/logout` - End session
- `POST /api/v1/accounts/verify-email` - Verify email address
- `POST /api/v1/accounts/password-reset-request` - Request reset token
- `POST /api/v1/accounts/password-reset` - Reset password

#### User Management
- `GET /api/v1/accounts/me` - Get current user profile
- `PATCH /api/v1/accounts/me` - Update profile
- `POST /api/v1/accounts/me/change-password` - Change password
- `GET /api/v1/accounts/me/sessions` - List active sessions

#### Organization Management
- `GET /api/v1/accounts/organizations/current` - Get user's organization
- `POST /api/v1/accounts/organizations` - Create organization
- `GET /api/v1/accounts/organizations/current/stats` - Get org statistics

#### Team Management
- `GET /api/v1/accounts/teams` - List teams
- `POST /api/v1/accounts/teams` - Create team
- `GET /api/v1/accounts/teams/{id}` - Get team details

#### API Key Management
- `GET /api/v1/accounts/api-keys` - List API keys
- `POST /api/v1/accounts/api-keys` - Create API key
- `DELETE /api/v1/accounts/api-keys/{id}` - Revoke API key

## Authentication

### JWT Tokens
- Access tokens: 30 minute expiry
- Refresh tokens: 30 day expiry
- Tokens contain user ID and email

### API Keys
- Format: `lf_` prefix + 32 random characters
- Stored as SHA256 hash
- Optional expiration date
- Scope-based permissions

### Password Requirements
- Minimum 8 characters
- At least one uppercase letter
- At least one lowercase letter
- At least one digit

## Authorization

### RBAC System
- Resources: lead, report, campaign, assessment, etc.
- Actions: create, read, update, delete, execute
- Roles contain multiple permissions
- Users can have multiple roles

### Middleware
- `require_user` - Require authenticated user
- `require_organization_member` - Require org membership
- `require_permission(resource, action)` - Check specific permission

## Security Features

- Bcrypt password hashing
- Account lockout after 5 failed attempts (1 hour)
- Email verification required
- Password reset tokens expire in 1 hour
- Immutable audit logging
- API key rotation support

## Database Schema

### Organizations Table
```sql
- id (UUID, PK)
- name
- slug (unique)
- stripe_customer_id
- billing_email
- settings (JSON)
- max_users/teams/api_keys
- is_active
- trial_ends_at
- timestamps
```

### Account Users Table
```sql
- id (UUID, PK)
- email (unique)
- username (unique, optional)
- password_hash
- auth_provider
- organization_id (FK)
- status
- email_verified
- mfa_enabled
- security fields
- timestamps
```

### Teams Table
```sql
- id (UUID, PK)
- name
- slug
- organization_id (FK)
- settings (JSON)
- is_default
- timestamps
```

### API Keys Table
```sql
- id (UUID, PK)
- name
- key_hash (unique)
- key_prefix
- user_id (FK)
- organization_id (FK)
- scopes (JSON)
- usage tracking
- timestamps
```

## Usage Examples

### Register New User
```python
POST /api/v1/accounts/register
{
  "email": "user@example.com",
  "password": "SecurePass123!",
  "full_name": "John Doe",
  "organization_name": "Acme Corp"
}
```

### Login
```python
POST /api/v1/accounts/login
{
  "email": "user@example.com",
  "password": "SecurePass123!"
}
```

### Use Access Token
```python
GET /api/v1/accounts/me
Authorization: Bearer <access_token>
```

### Create API Key
```python
POST /api/v1/accounts/api-keys
Authorization: Bearer <access_token>
{
  "name": "Production API Key",
  "scopes": ["read:leads", "write:reports"],
  "expires_in_days": 90
}
```

## Testing

### Unit Tests
- `test_auth_service.py` - Authentication logic
- `test_models.py` - Database models

### Integration Tests
- `test_auth_endpoints.py` - API endpoint testing

### Test Coverage
- Password hashing and verification
- JWT token generation/validation
- Session management
- Account lockout
- Email verification
- Password reset flow
- API key management

## Configuration

Environment variables:
- `SECRET_KEY` - JWT signing key
- `DATABASE_URL` - PostgreSQL connection
- `ENVIRONMENT` - development/production

## Error Handling

### HTTP Status Codes
- 200 - Success
- 201 - Created
- 400 - Bad request (validation errors)
- 401 - Unauthorized (invalid credentials)
- 403 - Forbidden (insufficient permissions)
- 404 - Not found

### Error Response Format
```json
{
  "error": "error_code",
  "message": "Human readable message",
  "details": {}
}
```

## Migration

Run database migration:
```bash
alembic upgrade p2_000_account_management
```

## Performance Considerations

- Passwords hashed with bcrypt (adaptive cost)
- Database indexes on email, username, organization
- Token validation cached in memory
- Audit logs use bulk inserts

## Future Enhancements

- Multi-factor authentication (MFA)
- OAuth2/SAML integration
- Password strength meter
- Session management UI
- IP allowlist/blocklist
- Advanced audit log search
- Webhook notifications
- User impersonation (admin)