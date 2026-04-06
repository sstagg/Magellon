"""
Temporal-Integrated Job Manager

Enhanced job manager that integrates with Temporal for workflow orchestration.

Architecture:
- Job Manager: Business logic, job lifecycle, status tracking
- Temporal: Workflow orchestration, distributed execution, fault tolerance
- NATS: Event broadcasting for real-time updates and logging

Features:
- Creates jobs and starts Temporal workflows
- Monitors workflow progress via polling
- Publishes progress events to NATS
- Supports workflow cancellation
- Compatible with existing JobManager interface
"""

import asyncio
import uuid
import logging
from datetime import datetime
from typing import Dict, Any, Optional, Type
from temporalio.client import Client as TemporalClient, WorkflowHandle
from temporalio import workflow

from services.magellon_job_manager import JobManager, Job, JobStatus
from services.event_publisher import get_event_publisher

logger = logging.getLogger(__name__)


class TemporalJobManager(JobManager):
    """
    Enhanced JobManager with Temporal workflow orchestration integration.

    Extends the base JobManager to delegate workflow execution to Temporal
    while maintaining high-level job management and status tracking.
    """

    def __init__(
        self,
        nats_url: str = "nats://localhost:4222",
        temporal_url: str = "localhost:7233",
        use_persistence: bool = True
    ):
        """
        Initialize Temporal Job Manager

        Args:
            nats_url: NATS server URL for event broadcasting
            temporal_url: Temporal server URL for workflow orchestration
            use_persistence: Whether to persist jobs to disk
        """
        super().__init__(nats_url, use_persistence)

        self.temporal_url = temporal_url
        self.temporal_client: Optional[TemporalClient] = None

        # Track workflow handles for each job
        self._workflow_handles: Dict[str, WorkflowHandle] = {}

        # Track monitoring tasks
        self._monitoring_tasks: Dict[str, asyncio.Task] = {}

        logger.info(f"TemporalJobManager initialized with Temporal URL: {temporal_url}")

    async def connect(self) -> None:
        """Connect to NATS and Temporal"""
        # Connect to NATS (parent class)
        await super().connect()

        # Connect to Temporal
        if not self.temporal_client:
            try:
                self.temporal_client = await TemporalClient.connect(self.temporal_url)
                logger.info(f"Connected to Temporal server at {self.temporal_url}")
            except Exception as e:
                logger.error(f"Failed to connect to Temporal: {e}")
                raise

    async def disconnect(self) -> None:
        """Disconnect from NATS and Temporal"""
        # Cancel all monitoring tasks
        for task in self._monitoring_tasks.values():
            task.cancel()

        # Wait for tasks to complete
        if self._monitoring_tasks:
            await asyncio.gather(*self._monitoring_tasks.values(), return_exceptions=True)

        # Disconnect from NATS (parent class)
        await super().disconnect()

        # Close Temporal client
        if self.temporal_client:
            await self.temporal_client.close()
            logger.info("Disconnected from Temporal server")

    async def create_and_execute_workflow(
        self,
        job_type: str,
        name: str,
        workflow_class: Type,
        workflow_args: list,
        task_queue: str = "magellon-tasks",
        metadata: Optional[Dict[str, Any]] = None,
        description: Optional[str] = None
    ) -> Job:
        """
        Create job and start Temporal workflow

        This is the main method for executing distributed workflows.

        Args:
            job_type: Type of job (e.g., "image_processing")
            name: Human-readable job name
            workflow_class: Temporal workflow class to execute
            workflow_args: Arguments to pass to workflow
            task_queue: Temporal task queue name
            metadata: Additional job metadata
            description: Job description

        Returns:
            Job object with workflow_id in metadata

        Example:
            job = await job_manager.create_and_execute_workflow(
                job_type="image_processing",
                name="Process Image 12345",
                workflow_class=ImageProcessingWorkflow,
                workflow_args=["image_12345", "/gpfs/images/12345.tiff"],
                metadata={"image_id": "12345"}
            )
        """
        if not self._is_connected:
            await self.connect()

        # 1. Create job using parent class method
        job = await self.create_job(
            job_type=job_type,
            name=name,
            description=description,
            metadata=metadata or {}
        )

        job_id = job.job_id

        # 2. Start Temporal workflow
        try:
            # Update job status to running
            job.status = JobStatus.RUNNING
            job.updated_at = datetime.utcnow().isoformat()

            # Prepend job_id to workflow args
            full_workflow_args = [job_id, *workflow_args]

            # Start workflow
            workflow_handle = await self.temporal_client.start_workflow(
                workflow_class.run,
                args=full_workflow_args,
                id=f"workflow-{job_id}",
                task_queue=task_queue
            )

            # Store workflow handle
            self._workflow_handles[job_id] = workflow_handle

            # Store workflow ID in job metadata
            job.metadata["workflow_id"] = workflow_handle.id
            job.metadata["task_queue"] = task_queue

            logger.info(f"Started Temporal workflow {workflow_handle.id} for job {job_id}")

            # 3. Publish job started event via NATS
            event_publisher = await get_event_publisher()
            await event_publisher.publish_job_started(
                job_id=job_id,
                workflow_id=workflow_handle.id
            )

            # 4. Start background task to monitor workflow progress
            monitoring_task = asyncio.create_task(
                self._monitor_workflow(job_id, workflow_handle)
            )
            self._monitoring_tasks[job_id] = monitoring_task

            logger.info(f"Started monitoring for job {job_id}")

        except Exception as e:
            # Workflow start failed
            job.status = JobStatus.FAILED
            job.error = f"Failed to start workflow: {str(e)}"
            job.completed_at = datetime.utcnow().isoformat()

            logger.error(f"Failed to start workflow for job {job_id}: {e}")

            # Publish job failed event
            event_publisher = await get_event_publisher()
            await event_publisher.publish_job_failed(
                job_id=job_id,
                error=str(e)
            )

        return job

    async def _monitor_workflow(self, job_id: str, workflow_handle: WorkflowHandle):
        """
        Monitor Temporal workflow and update job status

        This method:
        1. Polls workflow for progress updates
        2. Updates job object with current progress
        3. Publishes progress events to NATS
        4. Handles completion and failure

        Args:
            job_id: Job identifier
            workflow_handle: Temporal workflow handle
        """
        job = self._jobs.get(job_id)
        if not job:
            logger.error(f"Job {job_id} not found for monitoring")
            return

        event_publisher = await get_event_publisher()

        try:
            # Poll for progress periodically
            while True:
                # Check if job cancellation was requested
                if job.cancel_requested:
                    logger.info(f"Cancellation requested for job {job_id}, cancelling workflow")
                    await workflow_handle.cancel()
                    break

                # Query workflow progress
                try:
                    progress = await workflow_handle.query("get_progress")

                    # Update job with progress info
                    job.progress = progress.get("overall_progress_percent", 0)
                    job.current_task = progress.get("current_step_name", "Processing")
                    job.updated_at = datetime.utcnow().isoformat()

                    # Publish progress event to NATS
                    await event_publisher.publish_job_progress(
                        job_id=job_id,
                        progress=job.progress,
                        current_step=job.current_task,
                        step_details=progress
                    )

                    # Check if completed
                    if progress.get("overall_progress_percent", 0) >= 100:
                        logger.info(f"Workflow for job {job_id} is complete (100% progress)")
                        break

                except Exception as e:
                    # Query failed (workflow might not have started yet, or query not available)
                    logger.debug(f"Failed to query workflow progress for job {job_id}: {e}")

                # Wait before next poll
                await asyncio.sleep(5)

            # Wait for final result
            try:
                result = await workflow_handle.result()

                # Workflow completed successfully
                job.status = JobStatus.COMPLETED
                job.progress = 100
                job.completed_at = datetime.utcnow().isoformat()
                job.updated_at = datetime.utcnow().isoformat()
                job.metadata["workflow_result"] = result

                # Publish job completed event
                await event_publisher.publish_job_completed(
                    job_id=job_id,
                    result=result
                )

                logger.info(f"Job {job_id} completed successfully")

            except Exception as e:
                # Workflow failed or was cancelled
                if job.cancel_requested:
                    job.status = JobStatus.CANCELLED
                    job.completed_at = datetime.utcnow().isoformat()
                    job.updated_at = datetime.utcnow().isoformat()

                    await event_publisher.publish_job_cancelled(
                        job_id=job_id,
                        reason="User requested cancellation"
                    )

                    logger.info(f"Job {job_id} was cancelled")
                else:
                    job.status = JobStatus.FAILED
                    job.error = str(e)
                    job.completed_at = datetime.utcnow().isoformat()
                    job.updated_at = datetime.utcnow().isoformat()

                    await event_publisher.publish_job_failed(
                        job_id=job_id,
                        error=str(e)
                    )

                    logger.error(f"Job {job_id} failed: {e}")

        except Exception as e:
            logger.error(f"Error monitoring workflow for job {job_id}: {e}")

            job.status = JobStatus.FAILED
            job.error = f"Monitoring error: {str(e)}"
            job.updated_at = datetime.utcnow().isoformat()

        finally:
            # Clean up
            if job_id in self._monitoring_tasks:
                del self._monitoring_tasks[job_id]

            # Persist final state
            if self.use_persistence:
                await self._save_to_persistence()

    async def cancel_job(self, job_id: str) -> bool:
        """
        Cancel a running job and its Temporal workflow

        Args:
            job_id: Job identifier

        Returns:
            True if cancellation was initiated, False otherwise
        """
        # Use parent class cancellation logic
        cancelled = await self.request_job_cancellation(job_id)

        if cancelled:
            # If we have a workflow handle, cancel the Temporal workflow
            workflow_handle = self._workflow_handles.get(job_id)
            if workflow_handle:
                try:
                    await workflow_handle.cancel()
                    logger.info(f"Cancelled Temporal workflow for job {job_id}")
                except Exception as e:
                    logger.error(f"Failed to cancel Temporal workflow for job {job_id}: {e}")

        return cancelled

    async def get_workflow_progress(self, job_id: str) -> Optional[Dict[str, Any]]:
        """
        Get real-time workflow progress by querying Temporal

        Args:
            job_id: Job identifier

        Returns:
            Progress dictionary from workflow query, or None if not available
        """
        workflow_handle = self._workflow_handles.get(job_id)
        if not workflow_handle:
            logger.warning(f"No workflow handle found for job {job_id}")
            return None

        try:
            progress = await workflow_handle.query("get_progress")
            return progress
        except Exception as e:
            logger.error(f"Failed to query workflow progress for job {job_id}: {e}")
            return None


# Global singleton instance
_temporal_job_manager: Optional[TemporalJobManager] = None


async def get_temporal_job_manager(
    nats_url: str = "nats://localhost:4222",
    temporal_url: str = "localhost:7233"
) -> TemporalJobManager:
    """
    Get or create global Temporal Job Manager instance

    Usage in FastAPI:
        from services.temporal_job_manager import get_temporal_job_manager
        from workflows.image_processing_workflow import ImageProcessingWorkflow

        job_manager = await get_temporal_job_manager()

        job = await job_manager.create_and_execute_workflow(
            job_type="image_processing",
            name="Process Image",
            workflow_class=ImageProcessingWorkflow,
            workflow_args=["image_id", "/path/to/image.tiff"]
        )
    """
    global _temporal_job_manager

    if _temporal_job_manager is None:
        _temporal_job_manager = TemporalJobManager(nats_url, temporal_url)
        await _temporal_job_manager.connect()

    return _temporal_job_manager
