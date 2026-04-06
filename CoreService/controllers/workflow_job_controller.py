"""
Workflow Job Controller

FastAPI endpoints for job management with Temporal workflow orchestration.

Endpoints:
- POST /api/jobs - Create and execute workflow job
- GET /api/jobs/{job_id} - Get job status and progress
- GET /api/jobs - List jobs
- DELETE /api/jobs/{job_id} - Cancel job
- WS /ws/jobs/{job_id} - WebSocket for real-time job progress updates
"""

import json
import asyncio
import logging
from typing import Optional, List
from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect, Query
from pydantic import BaseModel, Field

from services.temporal_job_manager import get_temporal_job_manager
from services.event_publisher import get_event_publisher
from workflows.image_processing_workflow import ImageProcessingWorkflow

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["Workflow Jobs"])


# ========== Request/Response Models ==========

class CreateJobRequest(BaseModel):
    """Request model for creating a workflow job"""
    job_type: str = Field(..., description="Type of job (e.g., 'image_processing')")
    name: str = Field(..., description="Human-readable job name")
    description: Optional[str] = Field(None, description="Job description")
    workflow_type: str = Field("image_processing", description="Type of workflow to execute")
    workflow_params: dict = Field(..., description="Parameters for the workflow")
    metadata: Optional[dict] = Field(None, description="Additional metadata")

    class Config:
        json_schema_extra = {
            "example": {
                "job_type": "image_processing",
                "name": "Process Image 12345",
                "description": "Process microscopy image with MotionCor, CTF, and Thumbnail",
                "workflow_type": "image_processing",
                "workflow_params": {
                    "image_id": "12345",
                    "input_path": "/gpfs/images/12345.tiff"
                },
                "metadata": {
                    "session_id": "session_001",
                    "user_id": "user_123"
                }
            }
        }


class JobResponse(BaseModel):
    """Response model for job information"""
    job_id: str
    job_type: str
    name: str
    description: str
    status: str
    progress: int
    current_task: Optional[str]
    created_at: str
    updated_at: str
    completed_at: Optional[str]
    metadata: dict
    error: Optional[str]


class JobListResponse(BaseModel):
    """Response model for job list"""
    jobs: List[JobResponse]
    total: int
    limit: int
    offset: int


class WorkflowProgressResponse(BaseModel):
    """Response model for detailed workflow progress"""
    job_id: str
    overall_progress_percent: int
    total_steps: int
    completed_steps: int
    current_step_name: str
    current_step_index: int
    status: str
    steps: List[dict]


# ========== Endpoints ==========

@router.post("/jobs", response_model=JobResponse, status_code=201)
async def create_job(request: CreateJobRequest):
    """
    Create and execute a workflow job

    Creates a new job and starts the corresponding Temporal workflow.
    The workflow executes asynchronously, and progress can be monitored
    via GET /api/jobs/{job_id} or WebSocket connection.

    Returns:
        Job information including job_id for tracking
    """
    try:
        job_manager = await get_temporal_job_manager()

        # Map workflow type to workflow class
        workflow_classes = {
            "image_processing": ImageProcessingWorkflow,
            # Add more workflow types here as needed
        }

        workflow_class = workflow_classes.get(request.workflow_type)
        if not workflow_class:
            raise HTTPException(
                status_code=400,
                detail=f"Unknown workflow type: {request.workflow_type}"
            )

        # Extract workflow arguments from params
        # For ImageProcessingWorkflow: (job_id, image_id, input_path)
        if request.workflow_type == "image_processing":
            image_id = request.workflow_params.get("image_id")
            input_path = request.workflow_params.get("input_path")

            if not image_id or not input_path:
                raise HTTPException(
                    status_code=400,
                    detail="image_id and input_path are required for image_processing workflow"
                )

            workflow_args = [image_id, input_path]
        else:
            workflow_args = []

        # Create and execute workflow
        job = await job_manager.create_and_execute_workflow(
            job_type=request.job_type,
            name=request.name,
            workflow_class=workflow_class,
            workflow_args=workflow_args,
            description=request.description,
            metadata=request.metadata
        )

        return JobResponse(
            job_id=job.job_id,
            job_type=job.job_type,
            name=job.name,
            description=job.description,
            status=job.status,
            progress=job.progress,
            current_task=job.current_task,
            created_at=job.created_at,
            updated_at=job.updated_at,
            completed_at=job.completed_at,
            metadata=job.metadata,
            error=job.error
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to create job: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/jobs/{job_id}", response_model=JobResponse)
async def get_job(job_id: str):
    """
    Get job status and progress

    Returns:
        Current job information including progress percentage
    """
    try:
        job_manager = await get_temporal_job_manager()
        job = await job_manager.get_job(job_id)

        if not job:
            raise HTTPException(status_code=404, detail=f"Job {job_id} not found")

        return JobResponse(
            job_id=job.job_id,
            job_type=job.job_type,
            name=job.name,
            description=job.description,
            status=job.status,
            progress=job.progress,
            current_task=job.current_task,
            created_at=job.created_at,
            updated_at=job.updated_at,
            completed_at=job.completed_at,
            metadata=job.metadata,
            error=job.error
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get job {job_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/jobs/{job_id}/progress", response_model=WorkflowProgressResponse)
async def get_job_progress(job_id: str):
    """
    Get detailed workflow progress

    Queries the Temporal workflow directly for real-time progress information
    including individual step statuses.

    Returns:
        Detailed progress information with step-by-step breakdown
    """
    try:
        job_manager = await get_temporal_job_manager()

        # Get job
        job = await job_manager.get_job(job_id)
        if not job:
            raise HTTPException(status_code=404, detail=f"Job {job_id} not found")

        # Query workflow for detailed progress
        workflow_progress = await job_manager.get_workflow_progress(job_id)

        if workflow_progress:
            # Convert workflow progress to response model
            return WorkflowProgressResponse(
                job_id=workflow_progress.get("job_id", job_id),
                overall_progress_percent=workflow_progress.get("overall_progress_percent", job.progress),
                total_steps=workflow_progress.get("total_steps", 0),
                completed_steps=workflow_progress.get("completed_steps", 0),
                current_step_name=workflow_progress.get("current_step_name", job.current_task or ""),
                current_step_index=workflow_progress.get("current_step_index", -1),
                status=workflow_progress.get("status", job.status),
                steps=[
                    {
                        "step_name": step.step_name,
                        "status": step.status,
                        "progress": step.progress,
                        "message": step.message,
                        "error": step.error
                    }
                    for step in workflow_progress.get("steps", [])
                ]
            )
        else:
            # Workflow progress not available, return basic job info
            return WorkflowProgressResponse(
                job_id=job_id,
                overall_progress_percent=job.progress,
                total_steps=0,
                completed_steps=0,
                current_step_name=job.current_task or "",
                current_step_index=-1,
                status=job.status,
                steps=[]
            )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get progress for job {job_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/jobs", response_model=JobListResponse)
async def list_jobs(
    status: Optional[str] = Query(None, description="Filter by status"),
    job_type: Optional[str] = Query(None, description="Filter by job type"),
    limit: int = Query(100, ge=1, le=500, description="Maximum number of jobs to return"),
    offset: int = Query(0, ge=0, description="Number of jobs to skip")
):
    """
    List jobs with optional filtering

    Returns:
        List of jobs matching the filter criteria
    """
    try:
        job_manager = await get_temporal_job_manager()

        jobs = await job_manager.list_jobs(
            status=status,
            job_type=job_type,
            limit=limit,
            offset=offset
        )

        # Convert to response model
        job_responses = [
            JobResponse(
                job_id=job.job_id,
                job_type=job.job_type,
                name=job.name,
                description=job.description,
                status=job.status,
                progress=job.progress,
                current_task=job.current_task,
                created_at=job.created_at,
                updated_at=job.updated_at,
                completed_at=job.completed_at,
                metadata=job.metadata,
                error=job.error
            )
            for job in jobs
        ]

        return JobListResponse(
            jobs=job_responses,
            total=len(job_responses),
            limit=limit,
            offset=offset
        )

    except Exception as e:
        logger.error(f"Failed to list jobs: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/jobs/{job_id}")
async def cancel_job(job_id: str):
    """
    Cancel a running job

    Cancels the job and its associated Temporal workflow.
    Already completed or failed jobs cannot be cancelled.

    Returns:
        Cancellation status
    """
    try:
        job_manager = await get_temporal_job_manager()

        cancelled = await job_manager.cancel_job(job_id)

        if not cancelled:
            raise HTTPException(
                status_code=400,
                detail=f"Job {job_id} cannot be cancelled (not found or already in terminal state)"
            )

        return {
            "status": "cancelled",
            "job_id": job_id,
            "message": "Job cancellation requested successfully"
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to cancel job {job_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ========== WebSocket Endpoint ==========

@router.websocket("/ws/jobs/{job_id}")
async def websocket_job_progress(websocket: WebSocket, job_id: str):
    """
    WebSocket endpoint for real-time job progress updates

    Connects to NATS event stream and forwards job-related events to the client.
    Client receives real-time updates about job progress, step completion, etc.

    Events:
    - job.progress: Progress updates
    - job.completed: Job completion
    - job.failed: Job failure
    - job.cancelled: Job cancellation
    - step.started: Workflow step started
    - step.progress: Step progress update
    - step.completed: Step completion
    - step.failed: Step failure
    """
    await websocket.accept()
    logger.info(f"WebSocket connection established for job {job_id}")

    # Import NATS client
    from nats.aio.client import Client as NATS

    nc = NATS()
    subscriptions = []

    try:
        # Connect to NATS
        await nc.connect("nats://localhost:4222")

        # Define message handler
        async def message_handler(msg):
            try:
                # Parse message data
                data = json.loads(msg.data.decode())

                # Check if this event is for our job
                event_job_id = data.get("job_id")
                if event_job_id == job_id:
                    # Forward event to WebSocket client
                    await websocket.send_json({
                        "event_type": msg.subject,
                        "data": data
                    })
                    logger.debug(f"Sent event '{msg.subject}' to WebSocket for job {job_id}")

            except Exception as e:
                logger.error(f"Error handling NATS message: {e}")

        # Subscribe to job events
        job_sub = await nc.subscribe("job.*", cb=message_handler)
        subscriptions.append(job_sub)

        # Subscribe to step events
        step_sub = await nc.subscribe("step.*", cb=message_handler)
        subscriptions.append(step_sub)

        logger.info(f"Subscribed to NATS events for job {job_id}")

        # Send initial job status
        job_manager = await get_temporal_job_manager()
        job = await job_manager.get_job(job_id)

        if job:
            await websocket.send_json({
                "event_type": "connection.established",
                "data": {
                    "job_id": job_id,
                    "status": job.status,
                    "progress": job.progress,
                    "current_task": job.current_task
                }
            })

        # Keep connection alive and wait for messages
        while True:
            # Receive messages from client (for keep-alive or commands)
            try:
                data = await asyncio.wait_for(websocket.receive_text(), timeout=30.0)
                # Echo back (keep-alive)
                await websocket.send_json({"event_type": "pong"})
            except asyncio.TimeoutError:
                # Send periodic heartbeat
                await websocket.send_json({"event_type": "heartbeat"})
            except WebSocketDisconnect:
                logger.info(f"WebSocket disconnected for job {job_id}")
                break

    except WebSocketDisconnect:
        logger.info(f"WebSocket disconnected for job {job_id}")

    except Exception as e:
        logger.error(f"WebSocket error for job {job_id}: {e}")

    finally:
        # Cleanup: Unsubscribe and close NATS connection
        for sub in subscriptions:
            try:
                await sub.unsubscribe()
            except Exception as e:
                logger.error(f"Error unsubscribing: {e}")

        if nc.is_connected:
            await nc.close()

        logger.info(f"WebSocket cleanup completed for job {job_id}")
