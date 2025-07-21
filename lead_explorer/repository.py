"""
Repository pattern for Lead database operations.

Provides async database operations with proper error handling,
pagination, and filtering capabilities.
"""

from datetime import datetime
from typing import Any

from sqlalchemy import asc, desc, or_
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from core.logging import get_logger
from database.models import (
    AuditAction,
    AuditLogLead,
    Badge,
    BadgeAuditLog,
    BadgeType,
    EnrichmentStatus,
    Lead,
    LeadBadge,
)

logger = get_logger("lead_explorer_repository")


class LeadRepository:
    """Repository for Lead CRUD operations"""

    def __init__(self, db: Session):
        self.db = db

    def create_lead(
        self,
        email: str | None = None,
        domain: str | None = None,
        company_name: str | None = None,
        contact_name: str | None = None,
        is_manual: bool = False,
        source: str | None = None,
        created_by: str | None = None,
    ) -> Lead:
        """Create a new lead"""
        try:
            lead = Lead(
                email=email.lower() if email else None,
                domain=domain.lower() if domain else None,
                company_name=company_name,
                contact_name=contact_name,
                is_manual=is_manual,
                source=source,
                created_by=created_by,
            )

            self.db.add(lead)
            self.db.commit()
            self.db.refresh(lead)

            logger.info(f"Created lead {lead.id} - email: {email}, domain: {domain}, is_manual: {is_manual}")

            return lead

        except IntegrityError as e:
            self.db.rollback()
            logger.error(f"Integrity error creating lead: {e}")
            raise ValueError("Lead with this email or domain already exists")
        except SQLAlchemyError as e:
            self.db.rollback()
            logger.error(f"Database error creating lead: {e}")
            raise

    def get_lead_by_id(self, lead_id: str) -> Lead | None:
        """Get lead by ID"""
        return self.db.query(Lead).filter(Lead.id == lead_id, Lead.is_deleted.is_(False)).first()

    def get_leads_by_ids(self, lead_ids: list[str]) -> list[Lead]:
        """
        Get multiple leads by IDs in a single query (bulk operation)

        Args:
            lead_ids: List of lead IDs to retrieve

        Returns:
            List of Lead objects found (only existing, non-deleted leads)
        """
        if not lead_ids:
            return []

        return self.db.query(Lead).filter(Lead.id.in_(lead_ids), Lead.is_deleted.is_(False)).all()

    def get_lead_by_email(self, email: str) -> Lead | None:
        """Get lead by email"""
        return self.db.query(Lead).filter(Lead.email == email.lower(), Lead.is_deleted.is_(False)).first()

    def get_lead_by_domain(self, domain: str) -> Lead | None:
        """Get lead by domain"""
        return self.db.query(Lead).filter(Lead.domain == domain.lower(), Lead.is_deleted.is_(False)).first()

    def list_leads(
        self,
        skip: int = 0,
        limit: int = 100,
        is_manual: bool | None = None,
        enrichment_status: EnrichmentStatus | None = None,
        search: str | None = None,
        sort_by: str = "created_at",
        sort_order: str = "desc",
        # P0-021: Badge-based filtering parameters
        badge_ids: list[str] | None = None,
        badge_types: list[str] | None = None,
        has_badges: bool | None = None,
        exclude_badge_ids: list[str] | None = None,
    ) -> tuple[list[Lead], int]:
        """List leads with filtering and pagination"""

        query = self.db.query(Lead).filter(Lead.is_deleted.is_(False))

        # Apply filters
        if is_manual is not None:
            query = query.filter(Lead.is_manual == is_manual)

        if enrichment_status is not None:
            query = query.filter(Lead.enrichment_status == enrichment_status)

        if search:
            search_term = f"%{search.lower()}%"
            query = query.filter(
                or_(
                    Lead.email.ilike(search_term),
                    Lead.domain.ilike(search_term),
                    Lead.company_name.ilike(search_term),
                    Lead.contact_name.ilike(search_term),
                )
            )

        # P0-021: Badge-based filtering
        if badge_ids:
            # Filter leads that have any of the specified badges
            query = query.join(LeadBadge).filter(LeadBadge.badge_id.in_(badge_ids), LeadBadge.is_active == True)

        if badge_types:
            # Filter leads that have badges of specified types
            query = (
                query.join(LeadBadge)
                .join(Badge)
                .filter(Badge.badge_type.in_([BadgeType(bt) for bt in badge_types]), LeadBadge.is_active == True)
            )

        if has_badges is not None:
            if has_badges:
                # Filter leads that have at least one active badge
                query = query.join(LeadBadge).filter(LeadBadge.is_active == True)
            else:
                # Filter leads that have no active badges
                subquery = self.db.query(LeadBadge.lead_id).filter(LeadBadge.is_active == True)
                query = query.filter(~Lead.id.in_(subquery))

        if exclude_badge_ids:
            # Exclude leads that have any of the specified badges
            subquery = self.db.query(LeadBadge.lead_id).filter(
                LeadBadge.badge_id.in_(exclude_badge_ids), LeadBadge.is_active == True
            )
            query = query.filter(~Lead.id.in_(subquery))

        # Get total count for pagination
        total_count = query.count()

        # Apply sorting
        sort_column = getattr(Lead, sort_by, Lead.created_at)
        if sort_order.lower() == "desc":
            query = query.order_by(desc(sort_column))
        else:
            query = query.order_by(asc(sort_column))

        # Apply pagination
        leads = query.offset(skip).limit(limit).all()

        return leads, total_count

    def update_lead(self, lead_id: str, updates: dict[str, Any], updated_by: str | None = None) -> Lead | None:
        """Update lead with change tracking"""
        lead = self.get_lead_by_id(lead_id)
        if not lead:
            return None

        try:
            # Store old values for audit
            {column.name: getattr(lead, column.name) for column in Lead.__table__.columns}

            # Apply updates
            for field, value in updates.items():
                if hasattr(lead, field):
                    setattr(lead, field, value)

            if updated_by:
                lead.updated_by = updated_by

            self.db.commit()
            self.db.refresh(lead)

            logger.info(f"Updated lead {lead_id} - fields updated: {list(updates.keys())}")

            return lead

        except SQLAlchemyError as e:
            self.db.rollback()
            logger.error(f"Error updating lead {lead_id}: {e}")
            raise

    def soft_delete_lead(self, lead_id: str, deleted_by: str | None = None) -> bool:
        """Soft delete a lead"""
        lead = self.get_lead_by_id(lead_id)
        if not lead:
            return False

        try:
            lead.is_deleted = True
            lead.deleted_at = datetime.utcnow()
            lead.deleted_by = deleted_by

            self.db.commit()

            logger.info(f"Soft deleted lead {lead_id}")
            return True

        except SQLAlchemyError as e:
            self.db.rollback()
            logger.error(f"Error deleting lead {lead_id}: {e}")
            raise

    def update_enrichment_status(
        self, lead_id: str, status: EnrichmentStatus, task_id: str | None = None, error: str | None = None
    ) -> bool:
        """Update enrichment status and task tracking"""
        lead = self.get_lead_by_id(lead_id)
        if not lead:
            return False

        try:
            lead.enrichment_status = status
            if task_id:
                lead.enrichment_task_id = task_id
            if error:
                lead.enrichment_error = error

            self.db.commit()

            logger.info(f"Updated enrichment status for lead {lead_id} - status: {status.value}, task_id: {task_id}")
            return True

        except SQLAlchemyError as e:
            self.db.rollback()
            logger.error(f"Error updating enrichment status for lead {lead_id}: {e}")
            raise


class AuditRepository:
    """Repository for audit log operations"""

    def __init__(self, db: Session):
        self.db = db

    def create_audit_log(
        self,
        lead_id: str,
        action: AuditAction,
        user_id: str | None = None,
        user_ip: str | None = None,
        user_agent: str | None = None,
        old_values: dict[str, Any] | None = None,
        new_values: dict[str, Any] | None = None,
    ) -> AuditLogLead:
        """Create audit log entry"""
        import hashlib
        import json

        try:
            audit_log = AuditLogLead(
                lead_id=lead_id,
                action=action,
                user_id=user_id,
                user_ip=user_ip,
                user_agent=user_agent,
                old_values=json.dumps(old_values) if old_values else None,
                new_values=json.dumps(new_values) if new_values else None,
            )

            # Calculate checksum for tamper detection
            data = {
                "lead_id": audit_log.lead_id,
                "action": audit_log.action.value,
                "timestamp": audit_log.timestamp.isoformat() if audit_log.timestamp else None,
                "user_id": audit_log.user_id,
                "old_values": audit_log.old_values,
                "new_values": audit_log.new_values,
            }
            content = json.dumps(data, sort_keys=True)
            audit_log.checksum = hashlib.sha256(content.encode()).hexdigest()

            self.db.add(audit_log)
            self.db.commit()
            self.db.refresh(audit_log)

            logger.info(f"Created audit log for lead {lead_id} - action: {action.value}")

            return audit_log

        except SQLAlchemyError as e:
            self.db.rollback()
            logger.error(f"Error creating audit log: {e}")
            raise

    def get_audit_trail(self, lead_id: str, limit: int = 50) -> list[AuditLogLead]:
        """Get audit trail for a lead"""
        return (
            self.db.query(AuditLogLead)
            .filter(AuditLogLead.lead_id == lead_id)
            .order_by(desc(AuditLogLead.timestamp))
            .limit(limit)
            .all()
        )

    def verify_audit_integrity(self, audit_id: str) -> bool:
        """Verify audit log integrity"""
        import hashlib
        import json

        audit_log = self.db.query(AuditLogLead).filter(AuditLogLead.id == audit_id).first()

        if not audit_log:
            return False

        # Recalculate checksum
        data = {
            "lead_id": audit_log.lead_id,
            "action": audit_log.action.value if audit_log.action else None,
            "timestamp": audit_log.timestamp.isoformat() if audit_log.timestamp else None,
            "user_id": audit_log.user_id,
            "old_values": audit_log.old_values,
            "new_values": audit_log.new_values,
        }
        content = json.dumps(data, sort_keys=True)
        expected_checksum = hashlib.sha256(content.encode()).hexdigest()

        return audit_log.checksum == expected_checksum


class BadgeRepository:
    """Repository for Badge CRUD operations and lead badge assignments"""

    def __init__(self, db: Session):
        self.db = db

    def create_badge(
        self,
        name: str,
        description: str | None = None,
        badge_type: str = "custom",
        color: str = "#007bff",
        icon: str | None = None,
        is_system: bool = False,
        is_active: bool = True,
        created_by: str | None = None,
    ) -> Badge:
        """Create a new badge"""
        try:
            badge = Badge(
                name=name,
                description=description,
                badge_type=BadgeType(badge_type),
                color=color,
                icon=icon,
                is_system=is_system,
                is_active=is_active,
                created_by=created_by,
            )

            self.db.add(badge)
            self.db.commit()
            self.db.refresh(badge)

            logger.info(f"Created badge: {badge.id}")
            return badge

        except IntegrityError as e:
            self.db.rollback()
            logger.error(f"Integrity error creating badge: {e}")
            raise
        except SQLAlchemyError as e:
            self.db.rollback()
            logger.error(f"Database error creating badge: {e}")
            raise

    def get_badge_by_id(self, badge_id: str) -> Badge | None:
        """Get a badge by ID"""
        try:
            return self.db.query(Badge).filter(Badge.id == badge_id, Badge.is_active == True).first()
        except SQLAlchemyError as e:
            logger.error(f"Database error getting badge {badge_id}: {e}")
            raise

    def list_badges(
        self,
        skip: int = 0,
        limit: int = 20,
        badge_type: str | None = None,
        is_system: bool | None = None,
        is_active: bool | None = None,
        search: str | None = None,
        sort_by: str = "name",
        sort_order: str = "asc",
    ) -> tuple[list[Badge], int]:
        """List badges with filtering and pagination"""
        try:
            query = self.db.query(Badge)

            # Apply filters
            if badge_type:
                query = query.filter(Badge.badge_type == BadgeType(badge_type))

            if is_system is not None:
                query = query.filter(Badge.is_system == is_system)

            if is_active is not None:
                query = query.filter(Badge.is_active == is_active)
            else:
                # Default to active badges only
                query = query.filter(Badge.is_active == True)

            if search:
                search_term = f"%{search}%"
                query = query.filter(
                    or_(
                        Badge.name.ilike(search_term),
                        Badge.description.ilike(search_term),
                    )
                )

            # Get total count before pagination
            total_count = query.count()

            # Apply sorting
            if sort_by == "name":
                query = query.order_by(asc(Badge.name) if sort_order == "asc" else desc(Badge.name))
            elif sort_by == "created_at":
                query = query.order_by(asc(Badge.created_at) if sort_order == "asc" else desc(Badge.created_at))
            elif sort_by == "badge_type":
                query = query.order_by(asc(Badge.badge_type) if sort_order == "asc" else desc(Badge.badge_type))
            else:
                query = query.order_by(asc(Badge.name))

            # Apply pagination
            badges = query.offset(skip).limit(limit).all()

            return badges, total_count

        except SQLAlchemyError as e:
            logger.error(f"Database error listing badges: {e}")
            raise

    def update_badge(
        self,
        badge_id: str,
        updates: dict[str, Any],
        updated_by: str | None = None,
    ) -> Badge | None:
        """Update a badge"""
        try:
            badge = self.get_badge_by_id(badge_id)
            if not badge:
                return None

            # Apply updates
            for key, value in updates.items():
                if hasattr(badge, key):
                    if key == "badge_type" and value:
                        setattr(badge, key, BadgeType(value))
                    else:
                        setattr(badge, key, value)

            badge.updated_at = datetime.utcnow()

            self.db.commit()
            self.db.refresh(badge)

            logger.info(f"Updated badge: {badge_id}")
            return badge

        except SQLAlchemyError as e:
            self.db.rollback()
            logger.error(f"Database error updating badge {badge_id}: {e}")
            raise

    def delete_badge(self, badge_id: str, deleted_by: str | None = None) -> bool:
        """Soft delete a badge"""
        try:
            badge = self.get_badge_by_id(badge_id)
            if not badge:
                return False

            badge.is_active = False
            badge.updated_at = datetime.utcnow()

            self.db.commit()

            logger.info(f"Deleted badge: {badge_id}")
            return True

        except SQLAlchemyError as e:
            self.db.rollback()
            logger.error(f"Database error deleting badge {badge_id}: {e}")
            raise

    def assign_badge_to_lead(
        self,
        lead_id: str,
        badge_id: str,
        assigned_by: str | None = None,
        notes: str | None = None,
        expires_at: datetime | None = None,
    ) -> LeadBadge:
        """Assign a badge to a lead with audit logging"""
        try:
            # Check if badge assignment already exists
            existing = (
                self.db.query(LeadBadge)
                .filter(LeadBadge.lead_id == lead_id, LeadBadge.badge_id == badge_id, LeadBadge.is_active == True)
                .first()
            )

            if existing:
                # Reactivate if it was previously removed
                existing.is_active = True
                existing.assigned_by = assigned_by
                existing.assigned_at = datetime.utcnow()
                existing.notes = notes
                existing.expires_at = expires_at
                existing.removed_at = None
                existing.removed_by = None
                existing.removal_reason = None

                lead_badge = existing
            else:
                # Create new assignment
                lead_badge = LeadBadge(
                    lead_id=lead_id,
                    badge_id=badge_id,
                    assigned_by=assigned_by,
                    notes=notes,
                    expires_at=expires_at,
                )
                self.db.add(lead_badge)

            self.db.commit()
            self.db.refresh(lead_badge)

            # Create audit log
            self._create_badge_audit_log(
                lead_id=lead_id,
                badge_id=badge_id,
                lead_badge_id=lead_badge.id,
                action="assign",
                user_id=assigned_by,
                new_values={
                    "assigned_by": assigned_by,
                    "notes": notes,
                    "expires_at": expires_at.isoformat() if expires_at else None,
                },
            )

            logger.info(f"Assigned badge {badge_id} to lead {lead_id}")
            return lead_badge

        except SQLAlchemyError as e:
            self.db.rollback()
            logger.error(f"Database error assigning badge {badge_id} to lead {lead_id}: {e}")
            raise

    def remove_badge_from_lead(
        self,
        lead_id: str,
        badge_id: str,
        removed_by: str | None = None,
        removal_reason: str | None = None,
    ) -> LeadBadge | None:
        """Remove a badge from a lead with audit logging"""
        try:
            lead_badge = (
                self.db.query(LeadBadge)
                .filter(LeadBadge.lead_id == lead_id, LeadBadge.badge_id == badge_id, LeadBadge.is_active == True)
                .first()
            )

            if not lead_badge:
                return None

            # Store old values for audit
            old_values = {
                "assigned_by": lead_badge.assigned_by,
                "notes": lead_badge.notes,
                "expires_at": lead_badge.expires_at.isoformat() if lead_badge.expires_at else None,
            }

            # Soft delete
            lead_badge.is_active = False
            lead_badge.removed_at = datetime.utcnow()
            lead_badge.removed_by = removed_by
            lead_badge.removal_reason = removal_reason

            self.db.commit()
            self.db.refresh(lead_badge)

            # Create audit log
            self._create_badge_audit_log(
                lead_id=lead_id,
                badge_id=badge_id,
                lead_badge_id=lead_badge.id,
                action="remove",
                user_id=removed_by,
                old_values=old_values,
                new_values={
                    "removed_by": removed_by,
                    "removal_reason": removal_reason,
                },
            )

            logger.info(f"Removed badge {badge_id} from lead {lead_id}")
            return lead_badge

        except SQLAlchemyError as e:
            self.db.rollback()
            logger.error(f"Database error removing badge {badge_id} from lead {lead_id}: {e}")
            raise

    def get_lead_badges(
        self,
        lead_id: str,
        include_inactive: bool = False,
    ) -> list[LeadBadge]:
        """Get all badges assigned to a lead"""
        try:
            query = self.db.query(LeadBadge).filter(LeadBadge.lead_id == lead_id)

            if not include_inactive:
                query = query.filter(LeadBadge.is_active == True)

            return query.order_by(desc(LeadBadge.assigned_at)).all()

        except SQLAlchemyError as e:
            logger.error(f"Database error getting badges for lead {lead_id}: {e}")
            raise

    def get_badge_audit_trail(
        self,
        lead_id: str,
        limit: int = 50,
    ) -> list[BadgeAuditLog]:
        """Get badge audit trail for a lead"""
        try:
            return (
                self.db.query(BadgeAuditLog)
                .filter(BadgeAuditLog.lead_id == lead_id)
                .order_by(desc(BadgeAuditLog.timestamp))
                .limit(limit)
                .all()
            )

        except SQLAlchemyError as e:
            logger.error(f"Database error getting badge audit trail for lead {lead_id}: {e}")
            raise

    def _create_badge_audit_log(
        self,
        lead_id: str,
        badge_id: str,
        lead_badge_id: str | None,
        action: str,
        user_id: str | None = None,
        old_values: dict | None = None,
        new_values: dict | None = None,
        notes: str | None = None,
    ) -> BadgeAuditLog:
        """Create a badge audit log entry"""
        try:
            audit_log = BadgeAuditLog(
                lead_id=lead_id,
                badge_id=badge_id,
                lead_badge_id=lead_badge_id,
                action=action,
                user_id=user_id,
                old_values=old_values,
                new_values=new_values,
                notes=notes,
            )

            self.db.add(audit_log)
            self.db.commit()
            self.db.refresh(audit_log)

            return audit_log

        except SQLAlchemyError as e:
            self.db.rollback()
            logger.error(f"Database error creating badge audit log: {e}")
            raise
