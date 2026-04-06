"""
Slim orchestrator for job and task management.

Coordinates between JobPersistence, JobEventPublisher, and in-memory state
to manage the lifecycle of jobs and their tasks.
"""

import asyncio
import logging
import os
import uuid
from typing import Dict, Any, Optional, List
from datetime import datetime

from event_types import EventType
from magellon_event_service import MagellonEventService
from services.job_models import JobStatus, TaskStatus, Job, Task
from services.job_persistence import JobPersistence
from services.job_event_publisher import JobEventPublisher

# Re-export for backward compatibility
__all__ = ["JobManager", "Job", "Task", "JobStatus", "TaskStatus"]

logger = logging.getLogger(__name__)


class JobManager:
    """
    Manager for jobs and tasks

    Features:
    - Create and manage jobs with 1:N tasks
    - Track job and task status
    - Publish events for state changes
    - Support job cancellation
    - Persistence via JSON files
    """

    _instance = None

    def __new__(cls, *args, **kwargs):
        """Singleton pattern to ensure consistent state"""
        if cls._instance is None:
            cls._instance = super(JobManager, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self, nats_url: str = "nats://localhost:4222", use_persistence: bool = True):
        """Initialize JobManager"""
        if getattr(self, "_initialized", False):
            return

        # Initialize event service and publisher
        self.event_service = MagellonEventService(nats_url)
        self._publisher = JobEventPublisher(self.event_service)
        self.use_persistence = use_persistence

        # Initialize persistence
        self._persistence = JobPersistence()

        # In-memory storage
        self._jobs = {}  # job_id -> Job
        self._tasks = {}  # task_id -> Task
        self._job_tasks = {}  # job_id -> [task_id, task_id, ...]

        # State
        self._initialized = True
        self._is_connected = False

        logger.info("JobManager initialized")

    async def connect(self) -> None:
        """Connect to NATS and initialize"""
        if self._is_connected:
            return

        # Connect event service
        await self.event_service.connect()

        # Load existing jobs and tasks from persistence
        if self.use_persistence:
            await self._load_from_persistence()

        self._is_connected = True
        logger.info("JobManager connected")

    async def disconnect(self) -> None:
        """Disconnect from NATS and clean up"""
        if not self._is_connected:
            return

        # Save state to persistence
        if self.use_persistence:
            await self._save_to_persistence()

        # Disconnect event service
        await self.event_service.disconnect()

        self._is_connected = False
        logger.info("JobManager disconnected")

    async def _load_from_persistence(self) -> None:
        """Load jobs and tasks from persistence"""
        jobs_data, tasks_data = await self._persistence.load()
        self._process_loaded_data(jobs_data, tasks_data)

    def _process_loaded_data(self, jobs_data: Dict[str, Dict], tasks_data: Dict[str, Dict]) -> None:
        """Process loaded job and task data"""
        # First load all tasks
        for task_id, task_data in tasks_data.items():
            task = Task.from_dict(task_data)
            self._tasks[task_id] = task

            # Initialize job_tasks collections
            job_id = task.job_id
            if job_id not in self._job_tasks:
                self._job_tasks[job_id] = []

            self._job_tasks[job_id].append(task_id)

        # Then load all jobs
        for job_id, job_data in jobs_data.items():
            job = Job.from_dict(job_data)
            self._jobs[job_id] = job

            # Attach tasks to job
            if job_id in self._job_tasks:
                for task_id in self._job_tasks[job_id]:
                    if task_id in self._tasks:
                        job.tasks.append(self._tasks[task_id])

    async def _save_to_persistence(self) -> None:
        """Save jobs and tasks to persistence"""
        await self._persistence.save(self._jobs, self._tasks)

    # =============== Job Methods ===============

    async def create_job(
            self,
            job_type: str,
            name: str,
            description: Optional[str] = None,
            metadata: Optional[Dict[str, Any]] = None
    ) -> Job:
        """
        Create a new job

        Args:
            job_type: Type of job (e.g., "epu_import")
            name: Job name
            description: Job description
            metadata: Additional metadata

        Returns:
            Job object
        """
        if not self._is_connected:
            await self.connect()

        # Create job ID
        job_id = str(uuid.uuid4())

        # Create job
        job = Job(
            job_id=job_id,
            job_type=job_type,
            name=name,
            description=description,
            metadata=metadata or {},
            status=JobStatus.PENDING,
            progress=0,
            created_at=datetime.utcnow().isoformat(),
            updated_at=datetime.utcnow().isoformat()
        )

        # Store job
        self._jobs[job_id] = job
        self._job_tasks[job_id] = []

        # Publish job creation event
        await self._publisher.publish_job_event(EventType.JOB_CREATED, job)

        # Persist changes
        if self.use_persistence:
            await self._save_to_persistence()

        logger.info(f"Created job {job_id} of type {job_type}")
        return job

    async def get_job(self, job_id: str) -> Optional[Job]:
        """
        Get job by ID

        Args:
            job_id: Job ID

        Returns:
            Job object or None if not found
        """
        if not self._is_connected:
            await self.connect()

        return self._jobs.get(job_id)

    async def update_job(self, job_id: str, updates: Dict[str, Any]) -> Optional[Job]:
        """
        Update job properties

        Args:
            job_id: Job ID
            updates: Dictionary of properties to update

        Returns:
            Updated Job object or None if not found
        """
        if not self._is_connected:
            await self.connect()

        # Get job
        job = await self.get_job(job_id)
        if not job:
            logger.warning(f"Attempted to update non-existent job {job_id}")
            return None

        # Store original status for event determination
        original_status = job.status

        # Apply updates
        for key, value in updates.items():
            if hasattr(job, key):
                setattr(job, key, value)

        # Update timestamp
        job.updated_at = datetime.utcnow().isoformat()

        # Handle status transitions
        if "status" in updates and updates["status"] != original_status:
            if updates["status"] == JobStatus.RUNNING:
                # If starting, check for cancellation request
                if job.cancel_requested:
                    job.status = JobStatus.CANCELLED
                    job.completed_at = datetime.utcnow().isoformat()
                else:
                    await self._publisher.publish_job_event(EventType.JOB_STARTED, job)

            elif updates["status"] == JobStatus.COMPLETED:
                job.completed_at = datetime.utcnow().isoformat()
                job.progress = 100
                await self._publisher.publish_job_event(EventType.JOB_COMPLETED, job)

            elif updates["status"] == JobStatus.FAILED:
                job.completed_at = datetime.utcnow().isoformat()
                await self._publisher.publish_job_event(EventType.JOB_FAILED, job)

            elif updates["status"] == JobStatus.CANCELLED:
                job.completed_at = datetime.utcnow().isoformat()
                await self._publisher.publish_job_event(EventType.JOB_CANCELLED, job)

        # Publish update event for other changes
        if original_status == job.status and (
                "progress" in updates or "current_task" in updates
        ):
            await self._publisher.publish_job_event(EventType.JOB_UPDATED, job)

        # Persist changes
        if self.use_persistence:
            await self._save_to_persistence()

        logger.info(f"Updated job {job_id}")
        return job

    async def update_job_progress(
            self,
            job_id: str,
            progress: int,
            current_task: Optional[str] = None
    ) -> Optional[Job]:
        """
        Update job progress

        Args:
            job_id: Job ID
            progress: Progress percentage (0-100)
            current_task: Description of current task

        Returns:
            Updated Job object or None if not found
        """
        # Ensure progress is within valid range
        progress = min(max(progress, 0), 100)

        # Prepare updates
        updates = {"progress": progress}
        if current_task is not None:
            updates["current_task"] = current_task

        # Update job
        return await self.update_job(job_id, updates)

    async def request_job_cancellation(self, job_id: str) -> bool:
        """
        Request job cancellation

        Args:
            job_id: Job ID

        Returns:
            True if cancellation was requested, False if job not found
            or already in terminal state
        """
        if not self._is_connected:
            await self.connect()

        # Get job
        job = await self.get_job(job_id)
        if not job:
            logger.warning(f"Attempted to cancel non-existent job {job_id}")
            return False

        # Skip if already in terminal state
        if job.status in [JobStatus.COMPLETED, JobStatus.FAILED, JobStatus.CANCELLED]:
            logger.info(f"Job {job_id} already in terminal state {job.status}")
            return False

        # Set cancellation flag
        job.cancel_requested = True
        job.updated_at = datetime.utcnow().isoformat()

        # If job is pending, mark as cancelled immediately
        if job.status == JobStatus.PENDING:
            job.status = JobStatus.CANCELLED
            job.completed_at = datetime.utcnow().isoformat()
            await self._publisher.publish_job_event(EventType.JOB_CANCELLED, job)
        else:
            await self._publisher.publish_job_event(EventType.JOB_CANCELLATION_REQUESTED, job)

        # Cancel all pending tasks
        for task in job.tasks:
            if task.status == TaskStatus.PENDING:
                await self.update_task(
                    task.task_id,
                    {"status": TaskStatus.CANCELLED, "cancel_requested": True}
                )

        # Persist changes
        if self.use_persistence:
            await self._save_to_persistence()

        logger.info(f"Requested cancellation for job {job_id}")
        return True

    async def is_cancellation_requested(self, job_id: str) -> bool:
        """
        Check if cancellation has been requested for a job

        Args:
            job_id: Job ID

        Returns:
            True if cancellation requested, False otherwise
        """
        if not self._is_connected:
            await self.connect()

        job = await self.get_job(job_id)
        return job is not None and job.cancel_requested

    async def list_jobs(
            self,
            status: Optional[str] = None,
            job_type: Optional[str] = None,
            limit: int = 100,
            offset: int = 0
    ) -> List[Job]:
        """
        List jobs with optional filtering

        Args:
            status: Filter by status
            job_type: Filter by job type
            limit: Maximum number of jobs to return
            offset: Number of jobs to skip

        Returns:
            List of Job objects
        """
        if not self._is_connected:
            await self.connect()

        # Get all jobs
        all_jobs = list(self._jobs.values())

        # Apply filters
        filtered_jobs = all_jobs

        if status:
            filtered_jobs = [job for job in filtered_jobs if job.status == status]

        if job_type:
            filtered_jobs = [job for job in filtered_jobs if job.job_type == job_type]

        # Sort by created_at (newest first)
        sorted_jobs = sorted(
            filtered_jobs,
            key=lambda job: job.created_at,
            reverse=True
        )

        # Apply pagination
        paginated_jobs = sorted_jobs[offset:offset + limit]

        return paginated_jobs

    # =============== Task Methods ===============

    async def create_task(
            self,
            job_id: str,
            task_type: str,
            parameters: Optional[Dict[str, Any]] = None
    ) -> Optional[Task]:
        """
        Create a new task for a job

        Args:
            job_id: Parent job ID
            task_type: Type of task
            parameters: Task parameters

        Returns:
            Task object or None if parent job not found
        """
        if not self._is_connected:
            await self.connect()

        # Get parent job
        job = await self.get_job(job_id)
        if not job:
            logger.warning(f"Attempted to create task for non-existent job {job_id}")
            return None

        # Create task ID
        task_id = str(uuid.uuid4())

        # Create task
        task = Task(
            task_id=task_id,
            job_id=job_id,
            task_type=task_type,
            parameters=parameters or {},
            status=TaskStatus.PENDING,
            progress=0,
            created_at=datetime.utcnow().isoformat(),
            updated_at=datetime.utcnow().isoformat()
        )

        # Store task
        self._tasks[task_id] = task
        self._job_tasks.setdefault(job_id, []).append(task_id)
        job.tasks.append(task)

        # Update job task stats
        job.tasks_total += 1

        # Update job status
        job.update_status_from_tasks()
        job.updated_at = datetime.utcnow().isoformat()

        # Publish task creation event
        await self._publisher.publish_task_event(EventType.TASK_CREATED, task)

        # Publish job update event
        await self._publisher.publish_job_event(EventType.JOB_UPDATED, job)

        # Persist changes
        if self.use_persistence:
            await self._save_to_persistence()

        logger.info(f"Created task {task_id} of type {task_type} for job {job_id}")
        return task

    async def get_task(self, task_id: str) -> Optional[Task]:
        """
        Get task by ID

        Args:
            task_id: Task ID

        Returns:
            Task object or None if not found
        """
        if not self._is_connected:
            await self.connect()

        return self._tasks.get(task_id)

    async def update_task(self, task_id: str, updates: Dict[str, Any]) -> Optional[Task]:
        """
        Update task properties

        Args:
            task_id: Task ID
            updates: Dictionary of properties to update

        Returns:
            Updated Task object or None if not found
        """
        if not self._is_connected:
            await self.connect()

        # Get task
        task = await self.get_task(task_id)
        if not task:
            logger.warning(f"Attempted to update non-existent task {task_id}")
            return None

        # Store original status for event determination
        original_status = task.status

        # Apply updates
        for key, value in updates.items():
            if hasattr(task, key):
                setattr(task, key, value)

        # Update timestamp
        task.updated_at = datetime.utcnow().isoformat()

        # Handle status transitions
        if "status" in updates and updates["status"] != original_status:
            # Get parent job
            job = await self.get_job(task.job_id)

            if updates["status"] == TaskStatus.RUNNING:
                # Check for cancellation request
                if task.cancel_requested or (job and job.cancel_requested):
                    task.status = TaskStatus.CANCELLED
                    task.completed_at = datetime.utcnow().isoformat()
                else:
                    await self._publisher.publish_task_event(EventType.TASK_STARTED, task)

            elif updates["status"] == TaskStatus.COMPLETED:
                task.completed_at = datetime.utcnow().isoformat()
                task.progress = 100

                if job:
                    job.tasks_completed += 1
                    job.update_progress()
                    job.update_status_from_tasks()
                    job.updated_at = datetime.utcnow().isoformat()

                await self._publisher.publish_task_event(EventType.TASK_COMPLETED, task)

                if job:
                    await self._publisher.publish_job_event(EventType.JOB_UPDATED, job)

            elif updates["status"] == TaskStatus.FAILED:
                task.completed_at = datetime.utcnow().isoformat()

                if job:
                    job.tasks_failed += 1
                    job.update_progress()
                    job.update_status_from_tasks()
                    job.updated_at = datetime.utcnow().isoformat()

                await self._publisher.publish_task_event(EventType.TASK_FAILED, task)

                if job:
                    if job.status == JobStatus.FAILED:
                        await self._publisher.publish_job_event(EventType.JOB_FAILED, job)
                    else:
                        await self._publisher.publish_job_event(EventType.JOB_UPDATED, job)

            elif updates["status"] == TaskStatus.CANCELLED:
                task.completed_at = datetime.utcnow().isoformat()

                if job:
                    job.tasks_failed += 1  # Count cancelled as failed
                    job.update_progress()
                    job.update_status_from_tasks()
                    job.updated_at = datetime.utcnow().isoformat()

                await self._publisher.publish_task_event(EventType.TASK_CANCELLED, task)

                if job:
                    if job.status == JobStatus.CANCELLED:
                        await self._publisher.publish_job_event(EventType.JOB_CANCELLED, job)
                    else:
                        await self._publisher.publish_job_event(EventType.JOB_UPDATED, job)

        # Publish update event for progress updates
        elif original_status == task.status and "progress" in updates:
            await self._publisher.publish_task_event(EventType.TASK_UPDATED, task)

        # Persist changes
        if self.use_persistence:
            await self._save_to_persistence()

        logger.info(f"Updated task {task_id}")
        return task

    async def update_task_progress(self, task_id: str, progress: int) -> Optional[Task]:
        """
        Update task progress

        Args:
            task_id: Task ID
            progress: Progress percentage (0-100)

        Returns:
            Updated Task object or None if not found
        """
        # Ensure progress is within valid range
        progress = min(max(progress, 0), 100)

        # Update task
        return await self.update_task(task_id, {"progress": progress})

    async def request_task_cancellation(self, task_id: str) -> bool:
        """
        Request task cancellation

        Args:
            task_id: Task ID

        Returns:
            True if cancellation was requested, False if task not found
            or already in terminal state
        """
        if not self._is_connected:
            await self.connect()

        # Get task
        task = await self.get_task(task_id)
        if not task:
            logger.warning(f"Attempted to cancel non-existent task {task_id}")
            return False

        # Skip if already in terminal state
        if task.status in [TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELLED]:
            logger.info(f"Task {task_id} already in terminal state {task.status}")
            return False

        # Set cancellation flag
        task.cancel_requested = True
        task.updated_at = datetime.utcnow().isoformat()

        # If task is pending, mark as cancelled immediately
        if task.status == TaskStatus.PENDING:
            task.status = TaskStatus.CANCELLED
            task.completed_at = datetime.utcnow().isoformat()

            # Update parent job
            job = await self.get_job(task.job_id)
            if job:
                job.tasks_failed += 1
                job.update_progress()
                job.update_status_from_tasks()
                job.updated_at = datetime.utcnow().isoformat()

            # Publish task cancelled event
            await self._publisher.publish_task_event(EventType.TASK_CANCELLED, task)

            # Publish job update event
            if job:
                await self._publisher.publish_job_event(EventType.JOB_UPDATED, job)
        else:
            # Publish cancellation requested event
            await self.event_service.publish_task_event(
                EventType.TASK_CANCELLATION_REQUESTED,
                task_id,
                task.job_id,
                task.to_dict()
            )

        # Persist changes
        if self.use_persistence:
            await self._save_to_persistence()

        logger.info(f"Requested cancellation for task {task_id}")
        return True

    async def is_task_cancellation_requested(self, task_id: str) -> bool:
        """
        Check if cancellation has been requested for a task

        Args:
            task_id: Task ID

        Returns:
            True if cancellation requested, False otherwise
        """
        if not self._is_connected:
            await self.connect()

        task = await self.get_task(task_id)
        if not task:
            return False

        # Check task cancellation flag or parent job cancellation flag
        job = await self.get_job(task.job_id)
        return task.cancel_requested or (job and job.cancel_requested)

    async def list_tasks_by_job(self, job_id: str) -> List[Task]:
        """
        List all tasks for a job

        Args:
            job_id: Job ID

        Returns:
            List of Task objects
        """
        if not self._is_connected:
            await self.connect()

        job = await self.get_job(job_id)
        if not job:
            logger.warning(f"Attempted to list tasks for non-existent job {job_id}")
            return []

        return job.tasks

    # =============== Importer-specific Methods ===============

    async def publish_file_event(
            self,
            event_type: EventType,
            file_path: str,
            file_data: Dict[str, Any],
            job_id: Optional[str] = None
    ) -> str:
        """
        Publish a file-related event

        Args:
            event_type: Event type from EventType enum
            file_path: Path to the file
            file_data: Additional file data
            job_id: Optional job ID for context

        Returns:
            Event ID
        """
        if not self._is_connected:
            await self.connect()

        return await self._publisher.publish_file_event(
            event_type, file_path, file_data, job_id
        )

    async def publish_directory_event(
            self,
            event_type: EventType,
            dir_path: str,
            dir_data: Dict[str, Any],
            job_id: Optional[str] = None
    ) -> str:
        """
        Publish a directory-related event

        Args:
            event_type: Event type from EventType enum
            dir_path: Path to the directory
            dir_data: Additional directory data
            job_id: Optional job ID for context

        Returns:
            Event ID
        """
        if not self._is_connected:
            await self.connect()

        return await self._publisher.publish_directory_event(
            event_type, dir_path, dir_data, job_id
        )

    async def publish_processing_event(
            self,
            event_type: EventType,
            process_data: Dict[str, Any],
            job_id: Optional[str] = None,
            task_id: Optional[str] = None
    ) -> str:
        """
        Publish a processing-related event

        Args:
            event_type: Event type from EventType enum
            process_data: Processing data
            job_id: Optional job ID for context
            task_id: Optional task ID for context

        Returns:
            Event ID
        """
        if not self._is_connected:
            await self.connect()

        return await self._publisher.publish_processing_event(
            event_type, process_data, job_id, task_id
        )

    # =============== Synchronous API ===============

    def _ensure_loop(self):
        """Ensure there's an event loop for sync methods"""
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            # No running event loop
            return asyncio.new_event_loop()
        return asyncio.get_event_loop()

    def _run_async(self, coro):
        """Run an async coroutine from a sync context"""
        loop = self._ensure_loop()
        if loop.is_running():
            # We're in an async context already, use asyncio.run_coroutine_threadsafe
            import threading
            if threading.current_thread() is threading.main_thread():
                # In main thread with running loop - use create_task
                return asyncio.create_task(coro)
            else:
                # In another thread - use run_coroutine_threadsafe
                future = asyncio.run_coroutine_threadsafe(coro, loop)
                return future.result()
        else:
            # We're in a sync context, use loop.run_until_complete
            return loop.run_until_complete(coro)

    # Sync versions of async methods

    def connect_sync(self) -> None:
        """Connect to NATS synchronously"""
        return self._run_async(self.connect())

    def disconnect_sync(self) -> None:
        """Disconnect from NATS synchronously"""
        return self._run_async(self.disconnect())

    def create_job_sync(
            self,
            job_type: str,
            name: str,
            description: Optional[str] = None,
            metadata: Optional[Dict[str, Any]] = None
    ) -> Job:
        """Create a new job synchronously"""
        return self._run_async(self.create_job(job_type, name, description, metadata))

    def get_job_sync(self, job_id: str) -> Optional[Job]:
        """Get job by ID synchronously"""
        return self._run_async(self.get_job(job_id))

    def update_job_sync(self, job_id: str, updates: Dict[str, Any]) -> Optional[Job]:
        """Update job properties synchronously"""
        return self._run_async(self.update_job(job_id, updates))

    def update_job_progress_sync(
            self,
            job_id: str,
            progress: int,
            current_task: Optional[str] = None
    ) -> Optional[Job]:
        """Update job progress synchronously"""
        return self._run_async(self.update_job_progress(job_id, progress, current_task))

    def request_job_cancellation_sync(self, job_id: str) -> bool:
        """Request job cancellation synchronously"""
        return self._run_async(self.request_job_cancellation(job_id))

    def is_cancellation_requested_sync(self, job_id: str) -> bool:
        """Check if cancellation has been requested for a job synchronously"""
        return self._run_async(self.is_cancellation_requested(job_id))

    def list_jobs_sync(
            self,
            status: Optional[str] = None,
            job_type: Optional[str] = None,
            limit: int = 100,
            offset: int = 0
    ) -> List[Job]:
        """List jobs with optional filtering synchronously"""
        return self._run_async(self.list_jobs(status, job_type, limit, offset))

    def create_task_sync(
            self,
            job_id: str,
            task_type: str,
            parameters: Optional[Dict[str, Any]] = None
    ) -> Optional[Task]:
        """Create a new task for a job synchronously"""
        return self._run_async(self.create_task(job_id, task_type, parameters))

    def get_task_sync(self, task_id: str) -> Optional[Task]:
        """Get task by ID synchronously"""
        return self._run_async(self.get_task(task_id))

    def update_task_sync(self, task_id: str, updates: Dict[str, Any]) -> Optional[Task]:
        """Update task properties synchronously"""
        return self._run_async(self.update_task(task_id, updates))

    def update_task_progress_sync(self, task_id: str, progress: int) -> Optional[Task]:
        """Update task progress synchronously"""
        return self._run_async(self.update_task_progress(task_id, progress))

    def request_task_cancellation_sync(self, task_id: str) -> bool:
        """Request task cancellation synchronously"""
        return self._run_async(self.request_task_cancellation(task_id))

    def is_task_cancellation_requested_sync(self, task_id: str) -> bool:
        """Check if cancellation has been requested for a task synchronously"""
        return self._run_async(self.is_task_cancellation_requested(task_id))

    def list_tasks_by_job_sync(self, job_id: str) -> List[Task]:
        """List all tasks for a job synchronously"""
        return self._run_async(self.list_tasks_by_job(job_id))

    # =============== Context Manager Support ===============

    async def __aenter__(self):
        """Async context manager enter"""
        await self.connect()
        return self

    async def __aexit__(self, exc_type, exc_value, traceback):
        """Async context manager exit"""
        await self.disconnect()

    def __enter__(self):
        """Sync context manager enter"""
        self.connect_sync()
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        """Sync context manager exit"""
        self.disconnect_sync()
