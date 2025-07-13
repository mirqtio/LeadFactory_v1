"""
Repository pattern for Lead database operations.

Provides async database operations with proper error handling,
pagination, and filtering capabilities.
"""
from typing import List, Optional, Dict, Any, Tuple
from datetime import datetime

from sqlalchemy import or_, desc, asc
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from database.models import Lead, AuditLogLead, EnrichmentStatus, AuditAction
from core.logging import get_logger

logger = get_logger("lead_explorer_repository")


class LeadRepository:
    """Repository for Lead CRUD operations"""

    def __init__(self, db: Session):
        self.db = db

    def create_lead(
        self, 
        email: Optional[str] = None,
        domain: Optional[str] = None,
        company_name: Optional[str] = None,
        contact_name: Optional[str] = None,
        is_manual: bool = False,
        source: Optional[str] = None,
        created_by: Optional[str] = None
    ) -> Lead:
        """Create a new lead"""
        try:
            lead = Lead(
                email=email,
                domain=domain, 
                company_name=company_name,
                contact_name=contact_name,
                is_manual=is_manual,
                source=source,
                created_by=created_by
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

    def get_lead_by_id(self, lead_id: str) -> Optional[Lead]:
        """Get lead by ID"""
        return (
            self.db.query(Lead)
            .filter(Lead.id == lead_id, Lead.is_deleted == False)
            .first()
        )

    def get_lead_by_email(self, email: str) -> Optional[Lead]:
        """Get lead by email"""
        return (
            self.db.query(Lead)
            .filter(Lead.email == email.lower(), Lead.is_deleted == False)
            .first()
        )

    def get_lead_by_domain(self, domain: str) -> Optional[Lead]:
        """Get lead by domain"""
        return (
            self.db.query(Lead)
            .filter(Lead.domain == domain.lower(), Lead.is_deleted == False)
            .first()
        )

    def list_leads(
        self,
        skip: int = 0,
        limit: int = 100,
        is_manual: Optional[bool] = None,
        enrichment_status: Optional[EnrichmentStatus] = None,
        search: Optional[str] = None,
        sort_by: str = "created_at",
        sort_order: str = "desc"
    ) -> Tuple[List[Lead], int]:
        """List leads with filtering and pagination"""
        
        query = self.db.query(Lead).filter(Lead.is_deleted == False)
        
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
                    Lead.contact_name.ilike(search_term)
                )
            )
        
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

    def update_lead(
        self,
        lead_id: str,
        updates: Dict[str, Any],
        updated_by: Optional[str] = None
    ) -> Optional[Lead]:
        """Update lead with change tracking"""
        lead = self.get_lead_by_id(lead_id)
        if not lead:
            return None
            
        try:
            # Store old values for audit
            old_values = {
                column.name: getattr(lead, column.name)
                for column in Lead.__table__.columns
            }
            
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

    def soft_delete_lead(
        self,
        lead_id: str,
        deleted_by: Optional[str] = None
    ) -> bool:
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
        self,
        lead_id: str,
        status: EnrichmentStatus,
        task_id: Optional[str] = None,
        error: Optional[str] = None
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
        user_id: Optional[str] = None,
        user_ip: Optional[str] = None,
        user_agent: Optional[str] = None,
        old_values: Optional[Dict[str, Any]] = None,
        new_values: Optional[Dict[str, Any]] = None
    ) -> AuditLogLead:
        """Create audit log entry"""
        import json
        import hashlib
        
        try:
            audit_log = AuditLogLead(
                lead_id=lead_id,
                action=action,
                user_id=user_id,
                user_ip=user_ip,
                user_agent=user_agent,
                old_values=json.dumps(old_values) if old_values else None,
                new_values=json.dumps(new_values) if new_values else None
            )
            
            # Calculate checksum for tamper detection
            data = {
                'lead_id': audit_log.lead_id,
                'action': audit_log.action.value,
                'timestamp': audit_log.timestamp.isoformat() if audit_log.timestamp else None,
                'user_id': audit_log.user_id,
                'old_values': audit_log.old_values,
                'new_values': audit_log.new_values,
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

    def get_audit_trail(
        self,
        lead_id: str,
        limit: int = 50
    ) -> List[AuditLogLead]:
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
        audit_log = (
            self.db.query(AuditLogLead)
            .filter(AuditLogLead.id == audit_id)
            .first()
        )
        
        if not audit_log:
            return False
            
        return audit_log.verify_checksum()