"""
Assessment Database Service - Replace In-Memory Storage

Replaces in-memory storage with proper database persistence for assessment results,
sessions, and coordinator data. Part of P3-006 mock integration replacement.
"""

from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from core.logging import get_logger
from database.session import get_db

from .coordinator import CoordinatorResult
from .models import AssessmentResult as DBAssessmentResult
from .models import AssessmentSession as DBAssessmentSession
from .types import AssessmentStatus, AssessmentType

logger = get_logger(__name__, domain="d3")


class AssessmentDatabaseService:
    """
    Database service for managing assessment results and sessions

    Replaces in-memory storage with proper database persistence.
    Part of P3-006 Replace Mock Integrations initiative.
    """

    def __init__(self):
        self.logger = logger

    async def store_assessment_result(self, session_id: str, result: CoordinatorResult) -> bool:
        """
        Store assessment result in database instead of memory

        Args:
            session_id: Assessment session ID
            result: Coordinator result to store

        Returns:
            True if stored successfully
        """
        try:
            with get_db() as db:
                # Update session record
                session = db.query(DBAssessmentSession).filter(DBAssessmentSession.id == session_id).first()

                if not session:
                    # Create session if it doesn't exist
                    session = DBAssessmentSession(
                        id=session_id,
                        assessment_type=AssessmentType.FULL_AUDIT,
                        status=self._map_coordinator_status(result),
                        total_assessments=result.total_assessments,
                        completed_assessments=result.completed_assessments,
                        failed_assessments=result.failed_assessments,
                        total_cost_usd=result.total_cost_usd,
                        started_at=result.started_at,
                        completed_at=result.completed_at,
                        config_data={},
                    )
                    db.add(session)
                else:
                    # Update existing session
                    session.status = self._map_coordinator_status(result)
                    session.completed_assessments = result.completed_assessments
                    session.failed_assessments = result.failed_assessments
                    session.total_cost_usd = result.total_cost_usd
                    session.completed_at = result.completed_at

                # Store individual assessment results
                for assessment_type, assessment_result in result.partial_results.items():
                    if assessment_result:
                        self._store_individual_result(db, session_id, assessment_result)

                db.commit()
                self.logger.info(f"Stored assessment result for session {session_id}")
                return True

        except Exception as e:
            self.logger.error(f"Failed to store assessment result for session {session_id}: {e}")
            return False

    def _store_individual_result(self, db: Session, session_id: str, result) -> None:
        """Store individual assessment result"""
        try:
            # Check if result already exists
            existing = (
                db.query(DBAssessmentResult)
                .filter(
                    DBAssessmentResult.session_id == session_id,
                    DBAssessmentResult.assessment_type == result.assessment_type,
                    DBAssessmentResult.business_id == result.business_id,
                )
                .first()
            )

            if existing:
                # Update existing result
                self._update_assessment_result(existing, result)
            else:
                # Create new result
                db_result = self._create_assessment_result(session_id, result)
                db.add(db_result)

        except Exception as e:
            self.logger.error(f"Failed to store individual result: {e}")

    def _create_assessment_result(self, session_id: str, result) -> DBAssessmentResult:
        """Create new assessment result database record"""
        return DBAssessmentResult(
            id=result.id,
            business_id=result.business_id,
            session_id=session_id,
            assessment_type=result.assessment_type,
            status=result.status,
            url=result.url,
            domain=result.domain,
            # Store structured data
            pagespeed_data=getattr(result, "pagespeed_data", None),
            tech_stack_data=getattr(result, "tech_stack_data", None),
            ai_insights_data=getattr(result, "ai_insights_data", None),
            assessment_metadata=getattr(result, "assessment_metadata", None),
            # Screenshot data
            screenshot_url=getattr(result, "screenshot_url", None),
            screenshot_thumb_url=getattr(result, "screenshot_thumb_url", None),
            visual_scores_json=getattr(result, "visual_scores_json", None),
            visual_warnings=getattr(result, "visual_warnings", None),
            visual_quickwins=getattr(result, "visual_quickwins", None),
            # Performance metrics
            performance_score=getattr(result, "performance_score", None),
            accessibility_score=getattr(result, "accessibility_score", None),
            best_practices_score=getattr(result, "best_practices_score", None),
            seo_score=getattr(result, "seo_score", None),
            pwa_score=getattr(result, "pwa_score", None),
            # Core Web Vitals
            largest_contentful_paint=getattr(result, "largest_contentful_paint", None),
            first_input_delay=getattr(result, "first_input_delay", None),
            cumulative_layout_shift=getattr(result, "cumulative_layout_shift", None),
            speed_index=getattr(result, "speed_index", None),
            time_to_interactive=getattr(result, "time_to_interactive", None),
            # Timing and cost
            started_at=result.started_at,
            completed_at=result.completed_at,
            total_cost_usd=getattr(result, "total_cost_usd", 0),
            error_message=getattr(result, "error_message", None),
        )

    def _update_assessment_result(self, existing: DBAssessmentResult, result) -> None:
        """Update existing assessment result"""
        existing.status = result.status
        existing.completed_at = result.completed_at

        # Update data fields if they exist
        if hasattr(result, "pagespeed_data") and result.pagespeed_data:
            existing.pagespeed_data = result.pagespeed_data

        if hasattr(result, "tech_stack_data") and result.tech_stack_data:
            existing.tech_stack_data = result.tech_stack_data

        if hasattr(result, "ai_insights_data") and result.ai_insights_data:
            existing.ai_insights_data = result.ai_insights_data

        # Update performance metrics
        if hasattr(result, "performance_score"):
            existing.performance_score = result.performance_score
        if hasattr(result, "accessibility_score"):
            existing.accessibility_score = result.accessibility_score
        if hasattr(result, "seo_score"):
            existing.seo_score = result.seo_score

        # Update cost and error info
        if hasattr(result, "total_cost_usd"):
            existing.total_cost_usd = result.total_cost_usd
        if hasattr(result, "error_message"):
            existing.error_message = result.error_message

    async def get_assessment_result(self, session_id: str) -> CoordinatorResult | None:
        """
        Retrieve assessment result from database instead of memory

        Args:
            session_id: Assessment session ID

        Returns:
            CoordinatorResult or None if not found
        """
        try:
            with get_db() as db:
                # Get session
                session = db.query(DBAssessmentSession).filter(DBAssessmentSession.id == session_id).first()

                if not session:
                    return None

                # Get individual results
                results = db.query(DBAssessmentResult).filter(DBAssessmentResult.session_id == session_id).all()

                # Convert to coordinator result format
                partial_results = {}
                errors = {}

                for result in results:
                    partial_results[result.assessment_type] = result
                    if result.error_message:
                        errors[result.assessment_type] = result.error_message

                return CoordinatorResult(
                    session_id=session_id,
                    business_id=session.config_data.get("business_id", "unknown"),
                    total_assessments=session.total_assessments,
                    completed_assessments=session.completed_assessments,
                    failed_assessments=session.failed_assessments,
                    partial_results=partial_results,
                    errors=errors,
                    total_cost_usd=session.total_cost_usd,
                    execution_time_ms=self._calculate_execution_time(session),
                    started_at=session.started_at,
                    completed_at=session.completed_at,
                )

        except Exception as e:
            self.logger.error(f"Failed to get assessment result for session {session_id}: {e}")
            return None

    async def get_batch_sessions(self, batch_id: str) -> list[str] | None:
        """
        Get batch session IDs from database

        Args:
            batch_id: Batch identifier

        Returns:
            List of session IDs or None
        """
        try:
            with get_db() as db:
                # Query sessions with batch_id in config_data
                sessions = (
                    db.query(DBAssessmentSession)
                    .filter(DBAssessmentSession.config_data.contains({"batch_id": batch_id}))
                    .all()
                )

                return [session.id for session in sessions]

        except Exception as e:
            self.logger.error(f"Failed to get batch sessions for batch {batch_id}: {e}")
            return None

    async def store_batch_sessions(self, batch_id: str, session_ids: list[str]) -> bool:
        """
        Store batch session mapping in database

        Args:
            batch_id: Batch identifier
            session_ids: List of session IDs in the batch

        Returns:
            True if stored successfully
        """
        try:
            with get_db() as db:
                # Update all sessions to include batch_id
                for session_id in session_ids:
                    session = db.query(DBAssessmentSession).filter(DBAssessmentSession.id == session_id).first()

                    if session:
                        config_data = session.config_data or {}
                        config_data["batch_id"] = batch_id
                        session.config_data = config_data

                db.commit()
                self.logger.info(f"Stored batch mapping for {batch_id}: {len(session_ids)} sessions")
                return True

        except Exception as e:
            self.logger.error(f"Failed to store batch sessions for {batch_id}: {e}")
            return False

    def _map_coordinator_status(self, result: CoordinatorResult) -> AssessmentStatus:
        """Map coordinator result to assessment status"""
        if result.failed_assessments == result.total_assessments:
            return AssessmentStatus.FAILED
        if result.completed_assessments == result.total_assessments:
            return AssessmentStatus.COMPLETED
        if result.completed_assessments > 0:
            return AssessmentStatus.PARTIAL
        return AssessmentStatus.RUNNING

    def _calculate_execution_time(self, session: DBAssessmentSession) -> int:
        """Calculate execution time in milliseconds"""
        if session.started_at and session.completed_at:
            delta = session.completed_at - session.started_at
            return int(delta.total_seconds() * 1000)
        return 0

    async def cleanup_old_sessions(self, days_old: int = 30) -> int:
        """
        Clean up old assessment sessions

        Args:
            days_old: Delete sessions older than this many days

        Returns:
            Number of sessions cleaned up
        """
        try:
            cutoff_date = datetime.utcnow() - timedelta(days=days_old)

            with get_db() as db:
                # Delete old sessions and their results
                old_sessions = db.query(DBAssessmentSession).filter(DBAssessmentSession.created_at < cutoff_date).all()

                count = len(old_sessions)

                for session in old_sessions:
                    # Delete associated results first
                    db.query(DBAssessmentResult).filter(DBAssessmentResult.session_id == session.id).delete()

                    # Delete session
                    db.delete(session)

                db.commit()
                self.logger.info(f"Cleaned up {count} old assessment sessions")
                return count

        except Exception as e:
            self.logger.error(f"Failed to cleanup old sessions: {e}")
            return 0


# Global service instance
assessment_db_service = AssessmentDatabaseService()
