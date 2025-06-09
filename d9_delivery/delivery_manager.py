"""
Email Delivery Manager

Orchestrates email delivery through SendGrid with compliance,
suppression checking, and delivery recording.

Acceptance Criteria:
- Suppression check works ✓
- Compliance headers added ✓
- Unsubscribe tokens ✓
- Send recording ✓
"""

import logging
import uuid
from typing import Dict, List, Optional, Any, Union
from datetime import datetime, timezone
from dataclasses import dataclass

from sqlalchemy.orm import Session

from core.config import get_settings
from core.exceptions import ValidationError, EmailDeliveryError
from database.session import SessionLocal
from d9_delivery.models import EmailDelivery, DeliveryEvent, DeliveryStatus, EventType
from d9_delivery.sendgrid_client import SendGridClient, EmailData, SendGridResponse
from d9_delivery.email_builder import EmailBuilder, PersonalizationData
from d9_delivery.compliance import ComplianceManager


logger = logging.getLogger(__name__)


@dataclass
class DeliveryRequest:
    """Email delivery request data structure"""
    to_email: str
    template_name: str
    personalization: PersonalizationData
    to_name: Optional[str] = None
    reply_to_email: Optional[str] = None
    list_type: str = "marketing"
    priority: str = "normal"  # normal, high, low
    scheduled_at: Optional[datetime] = None
    custom_args: Optional[Dict[str, Any]] = None


@dataclass
class DeliveryResult:
    """Email delivery result data structure"""
    success: bool
    delivery_id: Optional[str] = None
    message_id: Optional[str] = None
    error_message: Optional[str] = None
    suppressed: bool = False
    compliance_added: bool = False


class DeliveryManager:
    """
    Email Delivery Manager
    
    Orchestrates the complete email delivery process including:
    - Suppression checking
    - Compliance header addition
    - Email building and personalization
    - SendGrid delivery
    - Delivery recording and tracking
    """
    
    def __init__(self, config: Optional[Any] = None):
        """Initialize delivery manager"""
        self.config = config or get_settings()
        self.email_builder = EmailBuilder()
        self.compliance_manager = ComplianceManager(config)
        
        logger.info("Delivery manager initialized")
    
    async def send_email(self, request: DeliveryRequest) -> DeliveryResult:
        """
        Send email with full compliance and tracking
        
        Args:
            request: DeliveryRequest with email details
            
        Returns:
            DeliveryResult with send results
        """
        delivery_id = str(uuid.uuid4())
        
        try:
            # Step 1: Check suppression
            if self.compliance_manager.check_suppression(request.to_email, request.list_type):
                logger.info(f"Email {request.to_email} is suppressed, skipping send")
                
                # Record suppressed delivery
                self._record_delivery(
                    delivery_id=delivery_id,
                    to_email=request.to_email,
                    status=DeliveryStatus.SUPPRESSED
                )
                
                return DeliveryResult(
                    success=False,
                    delivery_id=delivery_id,
                    suppressed=True,
                    error_message="Email address is suppressed"
                )
            
            # Step 2: Build email with personalization
            try:
                email_data = self.email_builder.build_email(
                    template_name=request.template_name,
                    personalization=request.personalization,
                    to_email=request.to_email,
                    to_name=request.to_name,
                    reply_to_email=request.reply_to_email
                )
                
                # Add custom args from request
                if request.custom_args:
                    if not email_data.custom_args:
                        email_data.custom_args = {}
                    email_data.custom_args.update(request.custom_args)
                
                # Add delivery tracking args
                email_data.custom_args.update({
                    'delivery_id': delivery_id,
                    'list_type': request.list_type,
                    'priority': request.priority
                })
                
            except Exception as e:
                logger.error(f"Error building email for {request.to_email}: {e}")
                
                self._record_delivery(
                    delivery_id=delivery_id,
                    to_email=request.to_email,
                    status=DeliveryStatus.FAILED,
                    error_message=f"Email building failed: {str(e)}"
                )
                
                return DeliveryResult(
                    success=False,
                    delivery_id=delivery_id,
                    error_message=f"Email building failed: {str(e)}"
                )
            
            # Step 3: Add compliance headers and unsubscribe links
            try:
                email_data = self.compliance_manager.add_compliance_to_email_data(
                    email_data, 
                    request.list_type
                )
                compliance_added = True
                
            except Exception as e:
                logger.error(f"Error adding compliance to email for {request.to_email}: {e}")
                compliance_added = False
                # Continue with send even if compliance addition fails
            
            # Step 4: Record delivery attempt
            self._record_delivery(
                delivery_id=delivery_id,
                to_email=request.to_email,
                status=DeliveryStatus.PENDING,
                scheduled_at=request.scheduled_at
            )
            
            # Step 5: Send via SendGrid
            try:
                async with SendGridClient() as sendgrid_client:
                    sendgrid_response = await sendgrid_client.send_email(email_data)
                
                if sendgrid_response.success:
                    # Step 6: Record successful send
                    self._update_delivery_status(
                        delivery_id=delivery_id,
                        status=DeliveryStatus.SENT,
                        sendgrid_message_id=sendgrid_response.message_id
                    )
                    
                    # Record send event
                    self._record_delivery_event(
                        delivery_id=delivery_id,
                        event_type=EventType.SENT,
                        sendgrid_message_id=sendgrid_response.message_id
                    )
                    
                    logger.info(f"Email sent successfully to {request.to_email}, delivery_id: {delivery_id}")
                    
                    return DeliveryResult(
                        success=True,
                        delivery_id=delivery_id,
                        message_id=sendgrid_response.message_id,
                        compliance_added=compliance_added
                    )
                
                else:
                    # Step 6: Record failed send
                    self._update_delivery_status(
                        delivery_id=delivery_id,
                        status=DeliveryStatus.FAILED,
                        error_message=sendgrid_response.error_message
                    )
                    
                    # Record failure event
                    self._record_delivery_event(
                        delivery_id=delivery_id,
                        event_type=EventType.FAILED,
                        error_message=sendgrid_response.error_message
                    )
                    
                    logger.error(f"SendGrid send failed for {request.to_email}: {sendgrid_response.error_message}")
                    
                    return DeliveryResult(
                        success=False,
                        delivery_id=delivery_id,
                        error_message=sendgrid_response.error_message,
                        compliance_added=compliance_added
                    )
            
            except Exception as e:
                # Step 6: Record exception
                error_message = f"SendGrid send exception: {str(e)}"
                
                self._update_delivery_status(
                    delivery_id=delivery_id,
                    status=DeliveryStatus.FAILED,
                    error_message=error_message
                )
                
                self._record_delivery_event(
                    delivery_id=delivery_id,
                    event_type=EventType.FAILED,
                    error_message=error_message
                )
                
                logger.error(f"SendGrid send exception for {request.to_email}: {e}")
                
                return DeliveryResult(
                    success=False,
                    delivery_id=delivery_id,
                    error_message=error_message,
                    compliance_added=compliance_added
                )
        
        except Exception as e:
            # Catch-all exception handling
            error_message = f"Delivery manager exception: {str(e)}"
            logger.error(f"Delivery manager exception for {request.to_email}: {e}")
            
            try:
                self._record_delivery(
                    delivery_id=delivery_id,
                    to_email=request.to_email,
                    status=DeliveryStatus.FAILED,
                    error_message=error_message
                )
            except:
                # If even recording fails, just log
                logger.error(f"Failed to record delivery for {request.to_email}")
            
            return DeliveryResult(
                success=False,
                delivery_id=delivery_id,
                error_message=error_message
            )
    
    async def send_batch_emails(self, requests: List[DeliveryRequest]) -> List[DeliveryResult]:
        """
        Send multiple emails in batch
        
        Args:
            requests: List of DeliveryRequest objects
            
        Returns:
            List of DeliveryResult objects
        """
        results = []
        
        logger.info(f"Starting batch send for {len(requests)} emails")
        
        # Process each request individually to ensure proper tracking
        for request in requests:
            try:
                result = await self.send_email(request)
                results.append(result)
                
            except Exception as e:
                logger.error(f"Batch send error for {request.to_email}: {e}")
                results.append(DeliveryResult(
                    success=False,
                    error_message=f"Batch send error: {str(e)}"
                ))
        
        # Log batch summary
        successful = sum(1 for r in results if r.success)
        suppressed = sum(1 for r in results if r.suppressed)
        failed = len(results) - successful - suppressed
        
        logger.info(f"Batch send completed: {successful} sent, {suppressed} suppressed, {failed} failed")
        
        return results
    
    def _record_delivery(
        self, 
        delivery_id: str,
        to_email: str,
        status: DeliveryStatus,
        sendgrid_message_id: Optional[str] = None,
        error_message: Optional[str] = None,
        scheduled_at: Optional[datetime] = None
    ) -> bool:
        """
        Record email delivery to database
        
        Args:
            delivery_id: Unique delivery identifier
            to_email: Recipient email
            status: Delivery status
            sendgrid_message_id: SendGrid message ID
            error_message: Error message if failed
            scheduled_at: When email was scheduled
            
        Returns:
            True if successful, False otherwise
        """
        try:
            with SessionLocal() as session:
                # Create delivery record with required fields
                delivery_data = {
                    "delivery_id": delivery_id,
                    "to_email": to_email,
                    "from_email": "noreply@leadfactory.com",  # Default from email
                    "subject": "LeadFactory Email",  # Default subject
                    "status": status.value
                }
                
                # Add optional fields if provided
                if sendgrid_message_id:
                    delivery_data["sendgrid_message_id"] = sendgrid_message_id
                if error_message:
                    delivery_data["error_message"] = error_message
                
                delivery = EmailDelivery(**delivery_data)
                
                session.add(delivery)
                session.commit()
                
                logger.debug(f"Recorded delivery {delivery_id} for {to_email}")
                return True
                
        except Exception as e:
            logger.error(f"Error recording delivery {delivery_id}: {e}")
            return False
    
    def _update_delivery_status(
        self,
        delivery_id: str,
        status: DeliveryStatus,
        sendgrid_message_id: Optional[str] = None,
        error_message: Optional[str] = None
    ) -> bool:
        """
        Update delivery status in database
        
        Args:
            delivery_id: Delivery ID to update
            status: New status
            sendgrid_message_id: SendGrid message ID
            error_message: Error message if failed
            
        Returns:
            True if successful, False otherwise
        """
        try:
            with SessionLocal() as session:
                delivery = session.query(EmailDelivery).filter(
                    EmailDelivery.delivery_id == delivery_id
                ).first()
                
                if delivery:
                    delivery.status = status.value
                    
                    if sendgrid_message_id:
                        delivery.sendgrid_message_id = sendgrid_message_id
                    
                    if error_message:
                        delivery.error_message = error_message
                    
                    if status == DeliveryStatus.SENT:
                        delivery.sent_at = datetime.now(timezone.utc)
                    elif status == DeliveryStatus.DELIVERED:
                        delivery.delivered_at = datetime.now(timezone.utc)
                    
                    session.commit()
                    logger.debug(f"Updated delivery {delivery_id} status to {status.value}")
                    return True
                else:
                    logger.warning(f"Delivery {delivery_id} not found for status update")
                    return False
                
        except Exception as e:
            logger.error(f"Error updating delivery {delivery_id} status: {e}")
            return False
    
    def _record_delivery_event(
        self,
        delivery_id: str,
        event_type: EventType,
        sendgrid_message_id: Optional[str] = None,
        error_message: Optional[str] = None,
        event_data: Optional[Dict[str, Any]] = None
    ) -> bool:
        """
        Record delivery event to database
        
        Args:
            delivery_id: Delivery ID
            event_type: Type of event
            sendgrid_message_id: SendGrid message ID
            error_message: Error message if applicable
            event_data: Additional event data
            
        Returns:
            True if successful, False otherwise
        """
        try:
            with SessionLocal() as session:
                event = DeliveryEvent(
                    delivery_id=delivery_id,
                    event_type=event_type.value,
                    sendgrid_message_id=sendgrid_message_id,
                    error_message=error_message,
                    event_data=event_data or {}
                )
                
                session.add(event)
                session.commit()
                
                logger.debug(f"Recorded {event_type.value} event for delivery {delivery_id}")
                return True
                
        except Exception as e:
            logger.error(f"Error recording event for delivery {delivery_id}: {e}")
            return False
    
    def get_delivery_status(self, delivery_id: str) -> Optional[Dict[str, Any]]:
        """
        Get delivery status and events
        
        Args:
            delivery_id: Delivery ID to query
            
        Returns:
            Dictionary with delivery status or None if not found
        """
        try:
            with SessionLocal() as session:
                delivery = session.query(EmailDelivery).filter(
                    EmailDelivery.delivery_id == delivery_id
                ).first()
                
                if not delivery:
                    return None
                
                # Get events
                events = session.query(DeliveryEvent).filter(
                    DeliveryEvent.delivery_id == delivery_id
                ).order_by(DeliveryEvent.created_at).all()
                
                return {
                    "delivery_id": delivery.delivery_id,
                    "to_email": delivery.to_email,
                    "from_email": delivery.from_email,
                    "subject": delivery.subject,
                    "status": delivery.status,
                    "sendgrid_message_id": delivery.sendgrid_message_id,
                    "error_message": delivery.error_message,
                    "created_at": delivery.created_at.isoformat() if delivery.created_at else None,
                    "sent_at": delivery.sent_at.isoformat() if delivery.sent_at else None,
                    "delivered_at": delivery.delivered_at.isoformat() if delivery.delivered_at else None,
                    "events": [
                        {
                            "event_type": event.event_type,
                            "created_at": event.created_at.isoformat() if event.created_at else None,
                            "sendgrid_message_id": event.sendgrid_message_id,
                            "error_message": event.error_message,
                            "event_data": event.event_data
                        }
                        for event in events
                    ]
                }
                
        except Exception as e:
            logger.error(f"Error getting delivery status for {delivery_id}: {e}")
            return None
    
    def get_delivery_stats(self, hours: int = 24) -> Dict[str, Any]:
        """
        Get delivery statistics for the last N hours
        
        Args:
            hours: Number of hours to look back
            
        Returns:
            Dictionary with delivery statistics
        """
        try:
            from datetime import timedelta
            
            cutoff_time = datetime.now(timezone.utc) - timedelta(hours=hours)
            
            with get_session() as session:
                # Total deliveries
                total_deliveries = session.query(EmailDelivery).filter(
                    EmailDelivery.created_at >= cutoff_time
                ).count()
                
                # By status
                sent_count = session.query(EmailDelivery).filter(
                    EmailDelivery.created_at >= cutoff_time,
                    EmailDelivery.status == DeliveryStatus.SENT.value
                ).count()
                
                failed_count = session.query(EmailDelivery).filter(
                    EmailDelivery.created_at >= cutoff_time,
                    EmailDelivery.status == DeliveryStatus.FAILED.value
                ).count()
                
                suppressed_count = session.query(EmailDelivery).filter(
                    EmailDelivery.created_at >= cutoff_time,
                    EmailDelivery.status == DeliveryStatus.SUPPRESSED.value
                ).count()
                
                pending_count = session.query(EmailDelivery).filter(
                    EmailDelivery.created_at >= cutoff_time,
                    EmailDelivery.status == DeliveryStatus.PENDING.value
                ).count()
                
                return {
                    "period_hours": hours,
                    "total_deliveries": total_deliveries,
                    "sent_count": sent_count,
                    "failed_count": failed_count,
                    "suppressed_count": suppressed_count,
                    "pending_count": pending_count,
                    "success_rate": round((sent_count / total_deliveries * 100) if total_deliveries > 0 else 0, 2),
                    "suppression_rate": round((suppressed_count / total_deliveries * 100) if total_deliveries > 0 else 0, 2),
                    "last_updated": datetime.now(timezone.utc).isoformat()
                }
                
        except Exception as e:
            logger.error(f"Error getting delivery stats: {e}")
            return {
                "error": str(e),
                "last_updated": datetime.now(timezone.utc).isoformat()
            }


# Utility functions

async def send_audit_email(
    business_name: str,
    to_email: str,
    contact_name: Optional[str] = None,
    issues: Optional[List[Dict[str, str]]] = None,
    score: Optional[float] = None,
    template: str = "cold_outreach",
    list_type: str = "marketing"
) -> DeliveryResult:
    """
    Utility function to send website audit email
    
    Args:
        business_name: Name of the business
        to_email: Recipient email
        contact_name: Contact name
        issues: List of issues found
        score: Assessment score
        template: Email template to use
        list_type: Type of mailing list
        
    Returns:
        DeliveryResult
    """
    from d9_delivery.email_builder import PersonalizationData
    
    personalization = PersonalizationData(
        business_name=business_name,
        contact_name=contact_name,
        issues_found=issues or [],
        assessment_score=score
    )
    
    request = DeliveryRequest(
        to_email=to_email,
        template_name=template,
        personalization=personalization,
        to_name=contact_name,
        list_type=list_type
    )
    
    delivery_manager = DeliveryManager()
    return await delivery_manager.send_email(request)


def create_delivery_request(
    to_email: str,
    template_name: str,
    business_name: str,
    **kwargs
) -> DeliveryRequest:
    """
    Factory function to create DeliveryRequest
    
    Args:
        to_email: Recipient email
        template_name: Email template name
        business_name: Business name for personalization
        **kwargs: Additional personalization and request data
        
    Returns:
        DeliveryRequest object
    """
    from d9_delivery.email_builder import PersonalizationData
    
    # Extract personalization data
    personalization = PersonalizationData(
        business_name=business_name,
        contact_name=kwargs.get('contact_name'),
        contact_first_name=kwargs.get('contact_first_name'),
        business_category=kwargs.get('business_category'),
        business_location=kwargs.get('business_location'),
        issues_found=kwargs.get('issues_found', []),
        assessment_score=kwargs.get('assessment_score'),
        custom_data=kwargs.get('custom_data', {})
    )
    
    return DeliveryRequest(
        to_email=to_email,
        template_name=template_name,
        personalization=personalization,
        to_name=kwargs.get('to_name'),
        reply_to_email=kwargs.get('reply_to_email'),
        list_type=kwargs.get('list_type', 'marketing'),
        priority=kwargs.get('priority', 'normal'),
        scheduled_at=kwargs.get('scheduled_at'),
        custom_args=kwargs.get('custom_args')
    )