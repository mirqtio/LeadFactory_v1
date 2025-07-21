"""
Audit logging system with SQLAlchemy event listeners for automatic capture.

Automatically logs all CREATE, UPDATE, and DELETE operations on Lead models
with tamper detection and comprehensive change tracking.
"""

import hashlib
import json
import os
from datetime import datetime
from typing import Any

from sqlalchemy import event
from sqlalchemy.orm import Session

from core.logging import get_logger
from database.models import AuditAction, AuditLogLead, Lead

logger = get_logger("lead_explorer_audit")


class AuditContext:
    """Thread-local context for audit information"""

    _context = {}

    @classmethod
    def set_user_context(cls, user_id: str | None = None, user_ip: str | None = None, user_agent: str | None = None):
        """Set user context for current thread"""
        cls._context = {"user_id": user_id, "user_ip": user_ip, "user_agent": user_agent}

    @classmethod
    def get_user_context(cls) -> dict[str, str | None]:
        """Get user context for current thread"""
        return cls._context.copy()

    @classmethod
    def clear_user_context(cls):
        """Clear user context"""
        cls._context = {}


def get_model_values(instance: Lead) -> dict[str, Any]:
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
        "deleted_by": instance.deleted_by,
    }


def create_audit_log(
    session: Session,
    lead_id: str,
    action: AuditAction,
    old_values: dict[str, Any] | None = None,
    new_values: dict[str, Any] | None = None,
):
    """Create an audit log entry with tamper detection"""
    # Skip audit logging if disabled by feature flag
    if not ENABLE_AUDIT_LOGGING:
        return

    try:
        user_context = AuditContext.get_user_context()

        audit_log = AuditLogLead(
            lead_id=lead_id,
            action=action,
            user_id=user_context.get("user_id"),
            user_ip=user_context.get("user_ip"),
            user_agent=user_context.get("user_agent"),
            old_values=json.dumps(old_values) if old_values else None,
            new_values=json.dumps(new_values) if new_values else None,
        )

        # Calculate checksum for tamper detection
        timestamp_str = audit_log.timestamp.isoformat() if audit_log.timestamp else datetime.utcnow().isoformat()
        data = {
            "lead_id": audit_log.lead_id,
            "action": audit_log.action.value,
            "timestamp": timestamp_str,
            "user_id": audit_log.user_id,
            "old_values": audit_log.old_values,
            "new_values": audit_log.new_values,
        }
        content = json.dumps(data, sort_keys=True)
        audit_log.checksum = hashlib.sha256(content.encode()).hexdigest()

        session.add(audit_log)
        # Don't commit here - let the main transaction handle it

        logger.info(
            f"Created audit log for lead {lead_id} - action: {action.value}, user_id: {user_context.get('user_id')}"
        )

    except Exception as e:
        logger.error(f"Failed to create audit log for lead {lead_id}: {str(e)}")
        # Don't raise - audit logging failure should not break the main operation


# Session-level event listeners for reliable audit logging

# Enable audit logging with feature flag (default: True)
ENABLE_AUDIT_LOGGING = os.getenv("ENABLE_AUDIT_LOGGING", "true").lower() == "true"

if ENABLE_AUDIT_LOGGING:

    @event.listens_for(Session, "after_commit")
    def log_session_changes(session):
        """Log all Lead changes after successful commit - ensures all data is persisted"""
        # Check if audit logging is enabled at runtime
        if os.getenv("ENABLE_AUDIT_LOGGING", "true").lower() != "true":
            return

        try:
            # We need to track changes during the transaction, but create audit logs after commit
            # Use a thread-local storage to track what needs to be audited
            if not hasattr(session, "_audit_changes"):
                return

            # Create audit logs using the same engine as the original session
            # This ensures we use the correct database (test vs production)
            audit_session = Session(bind=session.get_bind())
            try:
                # Process stored audit changes
                for change in session._audit_changes:
                    create_audit_log(
                        session=audit_session,
                        lead_id=change["lead_id"],
                        action=change["action"],
                        old_values=change.get("old_values"),
                        new_values=change.get("new_values"),
                    )

                audit_session.commit()
            finally:
                audit_session.close()

            # Clear the changes after processing
            delattr(session, "_audit_changes")

        except Exception as e:
            logger.error(f"Failed to create audit logs after commit: {str(e)}")
            # Don't raise - audit logging failure should not break the main operation

    @event.listens_for(Session, "before_flush")
    def collect_session_changes(session, flush_context, instances):
        """Collect Lead changes before flush to track for audit logging"""
        # Check if audit logging is enabled at runtime
        if os.getenv("ENABLE_AUDIT_LOGGING", "true").lower() != "true":
            return

        try:
            if not hasattr(session, "_audit_changes"):
                session._audit_changes = []

            # Track all Lead model changes in this session
            for instance in session.new:
                if isinstance(instance, Lead):
                    new_values = get_model_values(instance)
                    session._audit_changes.append(
                        {
                            "lead_id": instance.id,  # Will be set after flush
                            "action": AuditAction.CREATE,
                            "new_values": new_values,
                            "instance": instance,  # Keep reference to get ID after flush
                        }
                    )

            for instance in session.dirty:
                if isinstance(instance, Lead):
                    # Get old values from attribute history
                    old_values = {}
                    from sqlalchemy import inspect

                    state = inspect(instance)
                    for key in [
                        "email",
                        "domain",
                        "company_name",
                        "contact_name",
                        "enrichment_status",
                        "enrichment_task_id",
                        "enrichment_error",
                        "is_manual",
                        "source",
                        "is_deleted",
                        "created_by",
                        "updated_by",
                        "deleted_by",
                    ]:
                        if hasattr(state.attrs, key):
                            attr = getattr(state.attrs, key)
                            if attr.history.has_changes() and attr.history.deleted:
                                old_val = attr.history.deleted[0]
                                old_values[key] = old_val.value if hasattr(old_val, "value") else old_val

                    new_values = get_model_values(instance)

                    # Only log if there are actual changes
                    if old_values and old_values != new_values:
                        # Check if this is a soft delete (is_deleted flag change)
                        if old_values.get("is_deleted") is False and new_values.get("is_deleted") is True:
                            # Soft delete - log as UPDATE but note the deletion context
                            new_values["_soft_delete"] = True

                        session._audit_changes.append(
                            {
                                "lead_id": instance.id,
                                "action": AuditAction.UPDATE,
                                "old_values": old_values,
                                "new_values": new_values,
                                "instance": instance,
                            }
                        )

            for instance in session.deleted:
                if isinstance(instance, Lead):
                    old_values = get_model_values(instance)
                    session._audit_changes.append(
                        {
                            "lead_id": instance.id,
                            "action": AuditAction.DELETE,
                            "old_values": old_values,
                            "instance": instance,
                        }
                    )

        except Exception as e:
            logger.error(f"Failed to collect changes for audit logging: {str(e)}")
            # Don't raise - audit logging failure should not break the main operation

    @event.listens_for(Session, "after_flush")
    def update_audit_change_ids(session, flush_context):
        """Update audit changes with proper IDs after flush"""
        # Check if audit logging is enabled at runtime
        if os.getenv("ENABLE_AUDIT_LOGGING", "true").lower() != "true":
            return

        try:
            if hasattr(session, "_audit_changes"):
                for change in session._audit_changes:
                    if "instance" in change and change["instance"].id:
                        change["lead_id"] = change["instance"].id
                    # Remove instance reference to avoid memory issues
                    change.pop("instance", None)
        except Exception as e:
            logger.error(f"Failed to update audit change IDs: {str(e)}")


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
            AuditContext.set_user_context(user_id=user_id, user_ip=user_ip, user_agent=user_agent)

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


def verify_audit_integrity(session: Session, audit_id: str) -> bool:
    """Verify the integrity of an audit log entry"""
    try:
        audit_log = session.query(AuditLogLead).filter_by(id=audit_id).first()
        if not audit_log:
            return False

        # Recalculate checksum
        data = {
            "lead_id": audit_log.lead_id,
            "action": audit_log.action.value,
            "timestamp": audit_log.timestamp.isoformat(),
            "user_id": audit_log.user_id,
            "old_values": audit_log.old_values,
            "new_values": audit_log.new_values,
        }
        content = json.dumps(data, sort_keys=True)
        expected_checksum = hashlib.sha256(content.encode()).hexdigest()

        return audit_log.checksum == expected_checksum

    except Exception as e:
        logger.error(f"Error verifying audit integrity for {audit_id}: {str(e)}")
        return False


def get_audit_summary(session: Session, lead_id: str) -> dict[str, Any]:
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
        "integrity_verified": all(verify_audit_integrity(session, log.id) for log in audit_logs[:10]),  # Check first 10
    }
