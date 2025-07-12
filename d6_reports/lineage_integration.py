"""
Integration module for capturing lineage during report generation
"""

import uuid
from datetime import datetime
from typing import Dict, Any, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from d6_reports.lineage.tracker import LineageData, LineageTracker
from d6_reports.models import ReportGeneration, ReportStatus


class LineageCapture:
    """
    Service to capture lineage data during report generation lifecycle
    """
    
    def __init__(self, session: AsyncSession):
        self.session = session
        self.tracker = LineageTracker(session)
        self._pipeline_context = {}
    
    async def start_pipeline(
        self,
        lead_id: str,
        template_version: str,
        initial_data: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Start a new pipeline run and return pipeline_run_id
        
        Args:
            lead_id: ID of the lead being processed
            template_version: Version of the template being used
            initial_data: Initial data for the pipeline
            
        Returns:
            pipeline_run_id: Unique ID for this pipeline run
        """
        pipeline_run_id = str(uuid.uuid4())
        
        self._pipeline_context[pipeline_run_id] = {
            "lead_id": lead_id,
            "template_version": template_version,
            "start_time": datetime.utcnow(),
            "logs": [],
            "raw_inputs": initial_data or {},
        }
        
        return pipeline_run_id
    
    def log_pipeline_event(
        self,
        pipeline_run_id: str,
        event_type: str,
        message: str,
        data: Optional[Dict[str, Any]] = None
    ):
        """
        Log an event during pipeline execution
        
        Args:
            pipeline_run_id: ID of the pipeline run
            event_type: Type of event (info, warning, error, etc.)
            message: Event message
            data: Optional event data
        """
        if pipeline_run_id not in self._pipeline_context:
            return
        
        event = {
            "timestamp": datetime.utcnow().isoformat(),
            "type": event_type,
            "message": message,
        }
        
        if data:
            event["data"] = data
        
        self._pipeline_context[pipeline_run_id]["logs"].append(event)
    
    def add_raw_input(
        self,
        pipeline_run_id: str,
        input_key: str,
        input_data: Any
    ):
        """
        Add raw input data to the pipeline context
        
        Args:
            pipeline_run_id: ID of the pipeline run
            input_key: Key for the input data
            input_data: The input data to store
        """
        if pipeline_run_id not in self._pipeline_context:
            return
        
        self._pipeline_context[pipeline_run_id]["raw_inputs"][input_key] = input_data
    
    async def capture_on_completion(
        self,
        report_generation_id: str,
        pipeline_run_id: str,
        success: bool = True,
        error_data: Optional[Dict[str, Any]] = None
    ) -> bool:
        """
        Capture lineage when report generation completes
        
        Args:
            report_generation_id: ID of the report generation record
            pipeline_run_id: ID of the pipeline run
            success: Whether the pipeline completed successfully
            error_data: Error information if pipeline failed
            
        Returns:
            bool: True if lineage was captured successfully
        """
        if pipeline_run_id not in self._pipeline_context:
            return False
        
        context = self._pipeline_context[pipeline_run_id]
        end_time = datetime.utcnow()
        
        # Log completion event
        if success:
            self.log_pipeline_event(pipeline_run_id, "info", "Pipeline completed successfully")
        else:
            self.log_pipeline_event(
                pipeline_run_id, 
                "error", 
                "Pipeline failed",
                error_data
            )
        
        # Create lineage data
        lineage_data = LineageData(
            lead_id=context["lead_id"],
            pipeline_run_id=pipeline_run_id,
            template_version_id=context["template_version"],
            pipeline_start_time=context["start_time"],
            pipeline_end_time=end_time,
            pipeline_logs={
                "events": context["logs"],
                "summary": {
                    "total_events": len(context["logs"]),
                    "error_count": len([e for e in context["logs"] if e["type"] == "error"]),
                    "warning_count": len([e for e in context["logs"] if e["type"] == "warning"]),
                    "duration_seconds": (end_time - context["start_time"]).total_seconds(),
                    "success": success,
                }
            },
            raw_inputs=context["raw_inputs"],
        )
        
        # Capture lineage
        lineage = await self.tracker.capture_lineage(
            report_generation_id=report_generation_id,
            lineage_data=lineage_data,
        )
        
        # Clean up context
        del self._pipeline_context[pipeline_run_id]
        
        return lineage is not None


async def create_report_with_lineage(
    session: AsyncSession,
    business_id: str,
    template_id: str,
    template_version: str,
    user_id: Optional[str] = None,
    order_id: Optional[str] = None,
    report_data: Optional[Dict[str, Any]] = None,
) -> tuple[ReportGeneration, str]:
    """
    Create a new report generation with lineage tracking
    
    Args:
        session: Database session
        business_id: ID of the business
        template_id: ID of the template
        template_version: Version of the template
        user_id: Optional user ID
        order_id: Optional order ID
        report_data: Optional report data
        
    Returns:
        Tuple of (ReportGeneration, pipeline_run_id)
    """
    # Create lineage capture service
    lineage_capture = LineageCapture(session)
    
    # Start pipeline
    pipeline_run_id = await lineage_capture.start_pipeline(
        lead_id=business_id,  # Using business_id as lead_id for now
        template_version=template_version,
        initial_data=report_data,
    )
    
    # Create report generation record
    report = ReportGeneration(
        business_id=business_id,
        user_id=user_id,
        order_id=order_id,
        template_id=template_id,
        status=ReportStatus.PENDING,
        report_data=report_data,
        configuration={
            "pipeline_run_id": pipeline_run_id,
            "template_version": template_version,
        },
    )
    
    session.add(report)
    await session.commit()
    
    # Log creation event
    lineage_capture.log_pipeline_event(
        pipeline_run_id,
        "info",
        f"Report generation created with ID: {report.id}",
        {"report_id": report.id, "template_id": template_id},
    )
    
    return report, pipeline_run_id