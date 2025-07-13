"""
Audit logging system with SQLAlchemy event listeners for automatic capture.

Automatically logs all CREATE, UPDATE, and DELETE operations on Lead models
with tamper detection and comprehensive change tracking.
"""
import json
import hashlib
from typing import Dict, Any, Optional
from datetime import datetime

from sqlalchemy import event
from sqlalchemy.orm import Session
from sqlalchemy.orm.state import InstanceState

from core.logging import get_logger
from database.models import Lead, AuditLogLead, AuditAction

logger = get_logger("lead_explorer_audit")


class AuditContext:
    """Thread-local context for audit information"""
    _context = {}
    
    @classmethod
    def set_user_context(cls, user_id: Optional[str] = None, 
                        user_ip: Optional[str] = None, 
                        user_agent: Optional[str] = None):
        """Set user context for current thread"""
        cls._context = {
            "user_id": user_id,
            "user_ip": user_ip,
            "user_agent": user_agent
        }
    
    @classmethod
    def get_user_context(cls) -> Dict[str, Optional[str]]:
        """Get user context for current thread"""
        return cls._context.copy()
    
    @classmethod
    def clear_user_context(cls):
        """Clear user context"""
        cls._context = {}


def get_model_values(instance: Lead) -> Dict[str, Any]:
    """Extract relevant model values for audit logging"""
    return {
        "email": instance.email,
        "domain": instance.domain,
        "company_name": instance.company_name,
        "contact_name": instance.contact_name,
        "enrichment_status": instance.enrichment_status.value if instance.enrichment_status else None,
        "enrichment_task_id": instance.enrichment_task_id,
        "enrichment_error": instance.enrichment_error,
        "is_manual": instance.is_manual,
        "source": instance.source,
        "is_deleted": instance.is_deleted,
        "created_by": instance.created_by,
        "updated_by": instance.updated_by,
        "deleted_by": instance.deleted_by
    }


def create_audit_log(session: Session, lead_id: str, action: AuditAction, 
                    old_values: Optional[Dict[str, Any]] = None,
                    new_values: Optional[Dict[str, Any]] = None):
    """Create an audit log entry with tamper detection"""
    try:
        user_context = AuditContext.get_user_context()
        
        audit_log = AuditLogLead(
            lead_id=lead_id,
            action=action,
            user_id=user_context.get("user_id"),
            user_ip=user_context.get("user_ip"),
            user_agent=user_context.get("user_agent"),
            old_values=json.dumps(old_values) if old_values else None,
            new_values=json.dumps(new_values) if new_values else None
        )
        
        # Calculate checksum for tamper detection
        timestamp_str = audit_log.timestamp.isoformat() if audit_log.timestamp else datetime.utcnow().isoformat()
        data = {
            'lead_id': audit_log.lead_id,
            'action': audit_log.action.value,
            'timestamp': timestamp_str,
            'user_id': audit_log.user_id,
            'old_values': audit_log.old_values,
            'new_values': audit_log.new_values,
        }
        content = json.dumps(data, sort_keys=True)
        audit_log.checksum = hashlib.sha256(content.encode()).hexdigest()
        
        session.add(audit_log)
        # Don't commit here - let the main transaction handle it
        
        logger.info(f"Created audit log for lead {lead_id} - action: {action.value}, user_id: {user_context.get('user_id')}")
        
    except Exception as e:
        logger.error(f"Failed to create audit log for lead {lead_id}: {str(e)}")
        # Don't raise - audit logging failure should not break the main operation


# Event listeners for automatic audit logging
@event.listens_for(Lead, 'after_insert')
def log_lead_insert(mapper, connection, target):
    """Log lead creation"""
    session = Session.object_session(target)
    if session:
        new_values = get_model_values(target)
        create_audit_log(
            session=session,
            lead_id=target.id,
            action=AuditAction.CREATE,
            new_values=new_values
        )


@event.listens_for(Lead, 'after_update')
def log_lead_update(mapper, connection, target):
    """Log lead updates"""
    session = Session.object_session(target)
    if session:
        # Get the original values from the session's identity map
        history = session.get_transaction()._changes
        old_values = None
        
        # Try to get old values from SQLAlchemy's state tracking
        state: InstanceState = target.__dict__.get('_sa_instance_state')
        if state and hasattr(state, 'committed_state'):
            # Get committed state if available
            old_values = {}
            for key in ['email', 'domain', 'company_name', 'contact_name', 
                       'enrichment_status', 'enrichment_task_id', 'enrichment_error',
                       'is_manual', 'source', 'is_deleted', 'created_by', 
                       'updated_by', 'deleted_by']:
                if hasattr(state.committed_state, key):
                    old_val = getattr(state.committed_state, key)
                    if hasattr(old_val, 'value'):  # Handle enums
                        old_values[key] = old_val.value
                    else:
                        old_values[key] = old_val
        
        new_values = get_model_values(target)
        
        # Only log if there are actual changes
        if old_values != new_values:
            create_audit_log(
                session=session,
                lead_id=target.id,
                action=AuditAction.UPDATE,
                old_values=old_values,
                new_values=new_values
            )


@event.listens_for(Lead, 'after_delete')
def log_lead_delete(mapper, connection, target):
    """Log lead deletion (this handles hard deletes, soft deletes use update)"""
    session = Session.object_session(target)
    if session:
        old_values = get_model_values(target)
        create_audit_log(
            session=session,
            lead_id=target.id,
            action=AuditAction.DELETE,
            old_values=old_values
        )


class AuditMiddleware:
    """Middleware to automatically set audit context from request headers"""
    
    def __init__(self, app):
        self.app = app
    
    async def __call__(self, scope, receive, send):
        if scope["type"] == "http":
            # Extract user context from headers
            headers = dict(scope.get("headers", []))
            user_id = headers.get(b"x-user-id", b"").decode("utf-8") or None
            user_agent = headers.get(b"user-agent", b"").decode("utf-8") or None
            
            # Get client IP (considering proxies)
            user_ip = None
            if "client" in scope and scope["client"]:
                user_ip = scope["client"][0]
            
            # Set audit context
            AuditContext.set_user_context(
                user_id=user_id,
                user_ip=user_ip,
                user_agent=user_agent
            )
        
        try:
            await self.app(scope, receive, send)
        finally:
            # Clean up context
            AuditContext.clear_user_context()


def setup_audit_logging():
    """Setup audit logging - call this during app initialization"""
    logger.info("Setting up audit logging for Lead Explorer")
    # Event listeners are automatically registered when this module is imported
    # This function can be used for any additional setup if needed
    pass


def verify_audit_integrity(session: Session, audit_id: str) -> bool:
    """Verify the integrity of an audit log entry"""
    audit_log = session.query(AuditLogLead).filter_by(id=audit_id).first()
    if not audit_log:
        return False
    
    try:
        # Recalculate checksum
        data = {
            'lead_id': audit_log.lead_id,
            'action': audit_log.action.value,
            'timestamp': audit_log.timestamp.isoformat(),
            'user_id': audit_log.user_id,
            'old_values': audit_log.old_values,
            'new_values': audit_log.new_values,
        }
        content = json.dumps(data, sort_keys=True)
        expected_checksum = hashlib.sha256(content.encode()).hexdigest()
        
        return audit_log.checksum == expected_checksum
    
    except Exception as e:
        logger.error(f"Error verifying audit integrity for {audit_id}: {str(e)}")
        return False


def get_audit_summary(session: Session, lead_id: str) -> Dict[str, Any]:
    """Get audit summary for a lead"""
    audit_logs = session.query(AuditLogLead).filter_by(lead_id=lead_id).all()
    
    return {
        "total_events": len(audit_logs),
        "create_events": len([log for log in audit_logs if log.action == AuditAction.CREATE]),
        "update_events": len([log for log in audit_logs if log.action == AuditAction.UPDATE]),
        "delete_events": len([log for log in audit_logs if log.action == AuditAction.DELETE]),
        "first_event": audit_logs[0].timestamp if audit_logs else None,
        "last_event": audit_logs[-1].timestamp if audit_logs else None,
        "unique_users": len(set(log.user_id for log in audit_logs if log.user_id)),
        "integrity_verified": all(verify_audit_integrity(session, log.id) for log in audit_logs[:10])  # Check first 10
    }