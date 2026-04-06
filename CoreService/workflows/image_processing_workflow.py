"""
Image Processing Workflow

Orchestrates distributed image processing pipeline:
1. MotionCor (motion correction)
2. CTF (contrast transfer function estimation)
3. Thumbnail generation

Features:
- Multi-level progress tracking (job + step)
- NATS event broadcasting
- Cancellation support
- Retry logic with exponential backoff
- Query methods for real-time progress
"""

from datetime import timedelta
from temporalio import workflow
from temporalio.common import RetryPolicy
from dataclasses import dataclass
from typing import List, Dict, Any
import logging

logger = logging.getLogger(__name__)

# Import activities (will be defined in activities module)
with workflow.unsafe.imports_passed_through():
    from activities.image_processing_activities import (
        process_motioncor,
        process_ctf,
        generate_thumbnail,
        publish_event
    )


@dataclass
class StepProgress:
    """Progress information for a single workflow step"""
    step_name: str
    status: str  # pending, running, completed, failed
    progress: int  # 0-100
    message: str = ""
    error: str = ""
    duration_seconds: float = 0.0
    result: Dict[str, Any] = None

    def __post_init__(self):
        if self.result is None:
            self.result = {}


@dataclass
class WorkflowProgress:
    """Overall workflow progress information"""
    job_id: str
    total_steps: int
    completed_steps: int
    current_step_name: str
    current_step_index: int
    overall_progress_percent: int
    steps: List[StepProgress]
    status: str  # running, completed, failed, cancelled


@workflow.defn
class ImageProcessingWorkflow:
    """
    Temporal workflow for image processing pipeline.

    Orchestrates: MotionCor → CTF → Thumbnail
    Publishes progress events to NATS for real-time monitoring.
    """

    def __init__(self):
        # Step definitions
        self.steps = [
            StepProgress("MotionCor", "pending", 0),
            StepProgress("CTF", "pending", 0),
            StepProgress("Thumbnail", "pending", 0)
        ]
        self.total_steps = len(self.steps)
        self.completed_steps = 0
        self.current_step_index = -1
        self.job_id = None
        self.overall_status = "running"

    @workflow.run
    async def run(self, job_id: str, image_id: str, input_path: str) -> Dict[str, Any]:
        """
        Execute image processing workflow

        Args:
            job_id: Unique job identifier
            image_id: Image identifier
            input_path: Path to input image file

        Returns:
            Dictionary with results from all processing steps
        """
        self.job_id = job_id

        # Retry policy for activities
        retry_policy = RetryPolicy(
            initial_interval=timedelta(seconds=1),
            maximum_interval=timedelta(seconds=10),
            maximum_attempts=3,
            backoff_coefficient=2.0
        )

        results = {}

        try:
            # Publish workflow started event
            await workflow.execute_activity(
                publish_event,
                args=["job.started", {
                    "job_id": job_id,
                    "image_id": image_id,
                    "total_steps": self.total_steps
                }],
                start_to_close_timeout=timedelta(seconds=10),
                retry_policy=retry_policy
            )

            # ========== Step 1: MotionCor ==========
            results["motioncor"] = await self._execute_step(
                step_index=0,
                activity_fn=process_motioncor,
                activity_args=[job_id, image_id, input_path],
                timeout=timedelta(minutes=30)
            )

            # ========== Step 2: CTF ==========
            results["ctf"] = await self._execute_step(
                step_index=1,
                activity_fn=process_ctf,
                activity_args=[job_id, image_id, results["motioncor"]["output_path"]],
                timeout=timedelta(minutes=15)
            )

            # ========== Step 3: Thumbnail ==========
            results["thumbnail"] = await self._execute_step(
                step_index=2,
                activity_fn=generate_thumbnail,
                activity_args=[job_id, image_id, results["motioncor"]["output_path"]],
                timeout=timedelta(minutes=5)
            )

            # All steps completed
            self.overall_status = "completed"
            self.completed_steps = self.total_steps

            # Publish workflow completed event
            await workflow.execute_activity(
                publish_event,
                args=["job.completed", {
                    "job_id": job_id,
                    "image_id": image_id,
                    "results": results
                }],
                start_to_close_timeout=timedelta(seconds=10)
            )

            return {
                "status": "completed",
                "job_id": job_id,
                "image_id": image_id,
                "results": results
            }

        except Exception as e:
            # Workflow failed
            self.overall_status = "failed"

            # Mark current step as failed
            if 0 <= self.current_step_index < self.total_steps:
                self.steps[self.current_step_index].status = "failed"
                self.steps[self.current_step_index].error = str(e)

            # Publish workflow failed event
            await workflow.execute_activity(
                publish_event,
                args=["job.failed", {
                    "job_id": job_id,
                    "image_id": image_id,
                    "error": str(e),
                    "failed_step": self.steps[self.current_step_index].step_name if self.current_step_index >= 0 else "unknown"
                }],
                start_to_close_timeout=timedelta(seconds=10)
            )

            raise

    async def _execute_step(
        self,
        step_index: int,
        activity_fn,
        activity_args: list,
        timeout: timedelta
    ) -> Dict[str, Any]:
        """
        Execute a single workflow step with progress tracking

        Args:
            step_index: Index of the step (0-based)
            activity_fn: Activity function to execute
            activity_args: Arguments to pass to activity
            timeout: Activity timeout

        Returns:
            Result dictionary from activity
        """
        step = self.steps[step_index]
        self.current_step_index = step_index

        # Mark step as running
        step.status = "running"
        step.progress = 0

        # Publish step started event
        await workflow.execute_activity(
            publish_event,
            args=["step.started", {
                "job_id": self.job_id,
                "step_name": step.step_name,
                "step_index": step_index,
                "total_steps": self.total_steps
            }],
            start_to_close_timeout=timedelta(seconds=10)
        )

        # Execute the actual activity
        retry_policy = RetryPolicy(
            initial_interval=timedelta(seconds=1),
            maximum_interval=timedelta(seconds=10),
            maximum_attempts=3,
            backoff_coefficient=2.0
        )

        try:
            result = await workflow.execute_activity(
                activity_fn,
                args=activity_args,
                start_to_close_timeout=timeout,
                retry_policy=retry_policy,
                heartbeat_timeout=timedelta(seconds=30)  # Expect heartbeats every 30s
            )

            # Step completed successfully
            step.status = "completed"
            step.progress = 100
            step.result = result
            self.completed_steps += 1

            # Publish step completed event
            await workflow.execute_activity(
                publish_event,
                args=["step.completed", {
                    "job_id": self.job_id,
                    "step_name": step.step_name,
                    "result": result
                }],
                start_to_close_timeout=timedelta(seconds=10)
            )

            return result

        except Exception as e:
            # Step failed
            step.status = "failed"
            step.error = str(e)

            # Publish step failed event
            await workflow.execute_activity(
                publish_event,
                args=["step.failed", {
                    "job_id": self.job_id,
                    "step_name": step.step_name,
                    "error": str(e)
                }],
                start_to_close_timeout=timedelta(seconds=10)
            )

            raise

    @workflow.query
    def get_progress(self) -> WorkflowProgress:
        """
        Query method to get current workflow progress.

        Can be called from outside the workflow to get real-time progress.

        Returns:
            WorkflowProgress object with current state
        """
        # Calculate overall progress
        overall_progress = 0
        for step in self.steps:
            if step.status == "completed":
                overall_progress += (100 / self.total_steps)
            elif step.status == "running":
                overall_progress += (step.progress / self.total_steps)

        current_step_name = self.steps[self.current_step_index].step_name if 0 <= self.current_step_index < self.total_steps else "Not started"

        return WorkflowProgress(
            job_id=self.job_id or "unknown",
            total_steps=self.total_steps,
            completed_steps=self.completed_steps,
            current_step_name=current_step_name,
            current_step_index=self.current_step_index,
            overall_progress_percent=int(overall_progress),
            steps=self.steps,
            status=self.overall_status
        )

    @workflow.query
    def get_current_step(self) -> StepProgress:
        """
        Query method to get current step information.

        Returns:
            StepProgress object for the currently executing step
        """
        if 0 <= self.current_step_index < self.total_steps:
            return self.steps[self.current_step_index]
        return StepProgress("None", "pending", 0)

    @workflow.signal
    async def update_step_progress(self, step_index: int, progress: int, message: str = ""):
        """
        Signal method to update step progress from activities.

        Activities can send progress updates via this signal.

        Args:
            step_index: Index of the step to update
            progress: Progress percentage (0-100)
            message: Optional progress message
        """
        if 0 <= step_index < self.total_steps:
            self.steps[step_index].progress = progress
            self.steps[step_index].message = message

            # Publish progress event
            await workflow.execute_activity(
                publish_event,
                args=["step.progress", {
                    "job_id": self.job_id,
                    "step_name": self.steps[step_index].step_name,
                    "progress": progress,
                    "message": message
                }],
                start_to_close_timeout=timedelta(seconds=10)
            )
