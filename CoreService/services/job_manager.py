import json
import time
import uuid
import asyncio
from typing import Dict, Any, Optional, List, Union
import redis.asyncio as redis
from contextlib import asynccontextmanager
import logging
from datetime import datetime
from fastapi import Depends

logger = logging.getLogger(__name__)

# Redis configuration
REDIS_HOST = "localhost"  # Use environment variable in production
REDIS_PORT = 6379
REDIS_DB = 0
REDIS_PASSWORD = None  # Use environment variable in production
REDIS_PREFIX = "magellon:job:"

# Redis connection pool
redis_pool = redis.ConnectionPool(
    host=REDIS_HOST,
    port=REDIS_PORT,
    db=REDIS_DB,
    password=REDIS_PASSWORD,
    decode_responses=True,
)

class JobStatus:
    """Job status constants"""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"

# Redis dependency for FastAPI
async def get_redis() -> redis.Redis:
    """Get Redis connection from pool for use with FastAPI dependency injection."""
    client = redis.Redis(connection_pool=redis_pool)
    try:
        yield client
    finally:
        await client.close()

# Context manager for async operations
@asynccontextmanager
async def get_redis_async():
    """Context manager for async Redis operations."""
    client = redis.Redis(connection_pool=redis_pool)
    try:
        yield client
    finally:
        await client.close()

# Function to get Redis connection for sync operations
def get_redis_sync() -> redis.Redis:
    """Get synchronous Redis connection from pool for non-async contexts."""
    return redis.Redis(connection_pool=redis_pool)

def get_job_key(job_id: str) -> str:
    """Get a Redis key with the Magellon job prefix."""
    return f"{REDIS_PREFIX}{job_id}"

class JobManager:
    """
    Comprehensive job management service with Redis backend.
    Provides both synchronous and asynchronous interfaces.
    Implements singleton pattern for consistent access.
    """
    _instance = None

    def __new__(cls):
        """Singleton pattern to ensure consistent state across the application."""
        if cls._instance is None:
            cls._instance = super(JobManager, cls).__new__(cls)
        return cls._instance

    # =============== Asynchronous API ===============

    async def create_job_async(
            self,
            job_type: str,
            name: str,
            description: Optional[str] = None,
            metadata: Optional[Dict[str, Any]] = None,
            redis_client: Optional[redis.Redis] = None
    ) -> str:
        """
        Create a new job asynchronously.

        Args:
            job_type: Type of job (e.g., "magellon_import")
            name: Job name
            description: Job description
            metadata: Additional metadata
            redis_client: Optional Redis client (if None, a new connection is created)

        Returns:
            job_id: Unique job identifier
        """
        job_id = str(uuid.uuid4())

        # Create job data
        job_data = {
            "job_id": job_id,
            "job_type": job_type,
            "name": name,
            "description": description or f"{job_type} job",
            "status": JobStatus.PENDING,
            "progress": 0,
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat(),
            "completed_at": None,
            "metadata": metadata or {},
            "tasks_total": 0,
            "tasks_completed": 0,
            "tasks_failed": 0,
            "current_task": None,
            "cancel_requested": False,
            "error": None
        }

        # Use provided Redis client or create a new one
        close_client = False
        if redis_client is None:
            redis_client = redis.Redis(connection_pool=redis_pool)
            close_client = True

        try:
            # Store job data
            await redis_client.set(get_job_key(job_id), json.dumps(job_data))

            # Add to sorted set for listing
            await redis_client.zadd("magellon:jobs", {job_id: time.time()})

            # Publish creation event
            await redis_client.publish("magellon:job_events", json.dumps({
                "type": "job_created",
                "job_id": job_id,
                "data": job_data
            }))

            logger.info(f"Created job {job_id} of type {job_type}")
            return job_id
        finally:
            if close_client:
                await redis_client.close()

    async def get_job_async(
            self,
            job_id: str,
            redis_client: Optional[redis.Redis] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Get job data asynchronously.

        Args:
            job_id: Job identifier
            redis_client: Optional Redis client

        Returns:
            job_data: Job data or None if not found
        """
        close_client = False
        if redis_client is None:
            redis_client = redis.Redis(connection_pool=redis_pool)
            close_client = True

        try:
            job_json = await redis_client.get(get_job_key(job_id))

            if not job_json:
                return None

            return json.loads(job_json)
        finally:
            if close_client:
                await redis_client.close()

    async def update_job_async(
            self,
            job_id: str,
            updates: Dict[str, Any],
            redis_client: Optional[redis.Redis] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Update job data asynchronously.

        Args:
            job_id: Job identifier
            updates: Dictionary of fields to update
            redis_client: Optional Redis client

        Returns:
            updated_job_data: Updated job data or None if job not found
        """
        close_client = False
        if redis_client is None:
            redis_client = redis.Redis(connection_pool=redis_pool)
            close_client = True

        try:
            # Get current job data
            job_data = await self.get_job_async(job_id, redis_client)

            if not job_data:
                logger.warning(f"Attempted to update non-existent job {job_id}")
                return None

            # Apply updates
            job_data.update(updates)
            job_data["updated_at"] = datetime.now().isoformat()

            # Handle status transitions
            if "status" in updates:
                # Set completed_at timestamp for terminal states
                if updates["status"] in [JobStatus.COMPLETED, JobStatus.FAILED, JobStatus.CANCELLED]:
                    job_data["completed_at"] = datetime.now().isoformat()

                    # Set progress to 100% for completed jobs
                    if updates["status"] == JobStatus.COMPLETED and "progress" not in updates:
                        job_data["progress"] = 100

                # If status changes to RUNNING, make sure cancel_requested flag is respected
                if updates["status"] == JobStatus.RUNNING and job_data.get("cancel_requested", False):
                    job_data["status"] = JobStatus.CANCELLED
                    job_data["completed_at"] = datetime.now().isoformat()

            # Save updated job data
            await redis_client.set(get_job_key(job_id), json.dumps(job_data))

            # Publish update event
            await redis_client.publish("magellon:job_events", json.dumps({
                "type": "job_updated",
                "job_id": job_id,
                "updates": updates
            }))

            logger.debug(f"Updated job {job_id} with {updates}")
            return job_data
        finally:
            if close_client:
                await redis_client.close()

    async def update_progress_async(
            self,
            job_id: str,
            progress: int,
            current_task: Optional[str] = None,
            redis_client: Optional[redis.Redis] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Update job progress asynchronously.

        Args:
            job_id: Job identifier
            progress: Progress percentage (0-100)
            current_task: Description of current task
            redis_client: Optional Redis client

        Returns:
            updated_job_data: Updated job data or None if job not found
        """
        # Ensure progress is within valid range
        progress = min(max(progress, 0), 100)

        # Create updates dictionary
        updates = {"progress": progress}
        if current_task is not None:
            updates["current_task"] = current_task

        # Update job with progress and current task
        return await self.update_job_async(job_id, updates, redis_client)

    async def request_cancellation_async(
            self,
            job_id: str,
            redis_client: Optional[redis.Redis] = None
    ) -> bool:
        """
        Request job cancellation asynchronously.

        Args:
            job_id: Job identifier
            redis_client: Optional Redis client

        Returns:
            success: True if cancellation requested, False if job not found or already in terminal state
        """
        close_client = False
        if redis_client is None:
            redis_client = redis.Redis(connection_pool=redis_pool)
            close_client = True

        try:
            # Get current job data
            job_data = await self.get_job_async(job_id, redis_client)

            if not job_data:
                logger.warning(f"Attempted to cancel non-existent job {job_id}")
                return False

            # Skip if already in terminal state
            if job_data["status"] in [JobStatus.COMPLETED, JobStatus.FAILED, JobStatus.CANCELLED]:
                logger.warning(f"Attempted to cancel job {job_id} in terminal state {job_data['status']}")
                return False

            # Prepare updates based on current status
            updates = {"cancel_requested": True}

            # If job is still pending, mark as cancelled immediately
            if job_data["status"] == JobStatus.PENDING:
                updates["status"] = JobStatus.CANCELLED
                updates["completed_at"] = datetime.now().isoformat()

            # Update job data
            await self.update_job_async(job_id, updates, redis_client)

            # Publish cancellation event
            await redis_client.publish("magellon:job_events", json.dumps({
                "type": "job_cancelled",
                "job_id": job_id
            }))

            logger.info(f"Cancellation requested for job {job_id}")
            return True
        finally:
            if close_client:
                await redis_client.close()

    async def is_cancellation_requested_async(
            self,
            job_id: str,
            redis_client: Optional[redis.Redis] = None
    ) -> bool:
        """
        Check if cancellation was requested asynchronously.

        Args:
            job_id: Job identifier
            redis_client: Optional Redis client

        Returns:
            requested: True if cancellation requested, False otherwise
        """
        job_data = await self.get_job_async(job_id, redis_client)

        if not job_data:
            return False

        return job_data.get("cancel_requested", False)

    async def increment_task_counter_async(
            self,
            job_id: str,
            completed: int = 0,
            failed: int = 0,
            total: int = 0,
            redis_client: Optional[redis.Redis] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Increment task counters asynchronously.

        Args:
            job_id: Job identifier
            completed: Number of completed tasks to add
            failed: Number of failed tasks to add
            total: Number of total tasks to add
            redis_client: Optional Redis client

        Returns:
            updated_job_data: Updated job data or None if job not found
        """
        close_client = False
        if redis_client is None:
            redis_client = redis.Redis(connection_pool=redis_pool)
            close_client = True

        try:
            # Get current job data
            job_data = await self.get_job_async(job_id, redis_client)

            if not job_data:
                logger.warning(f"Attempted to update task counters for non-existent job {job_id}")
                return None

            # Prepare updates
            updates = {}

            if completed:
                updates["tasks_completed"] = job_data.get("tasks_completed", 0) + completed

            if failed:
                updates["tasks_failed"] = job_data.get("tasks_failed", 0) + failed

            if total:
                updates["tasks_total"] = job_data.get("tasks_total", 0) + total

            # Calculate progress based on completed/total tasks if available
            if "tasks_completed" in updates and job_data.get("tasks_total", 0) > 0:
                total_tasks = job_data.get("tasks_total", 0)
                completed_tasks = updates.get("tasks_completed", job_data.get("tasks_completed", 0))
                failed_tasks = updates.get("tasks_failed", job_data.get("tasks_failed", 0))

                # Only count tasks as done if they are completed or failed
                done_tasks = completed_tasks + failed_tasks

                # Calculate progress percentage (0-100)
                updates["progress"] = min(int((done_tasks / total_tasks) * 100), 100)

                # If all tasks are done, update job status
                if done_tasks >= total_tasks:
                    if failed_tasks > 0:
                        updates["status"] = JobStatus.FAILED
                        updates["error"] = f"{failed_tasks} tasks failed"
                    else:
                        updates["status"] = JobStatus.COMPLETED

                    updates["completed_at"] = datetime.now().isoformat()

            # Update job data
            return await self.update_job_async(job_id, updates, redis_client)
        finally:
            if close_client:
                await redis_client.close()

    async def list_jobs_async(
            self,
            limit: int = 20,
            offset: int = 0,
            status: Optional[str] = None,
            job_type: Optional[str] = None,
            redis_client: Optional[redis.Redis] = None
    ) -> List[Dict[str, Any]]:
        """
        List jobs asynchronously with optional filtering.

        Args:
            limit: Maximum number of jobs to return
            offset: Offset for pagination
            status: Filter by status
            job_type: Filter by job type
            redis_client: Optional Redis client

        Returns:
            jobs: List of job data dictionaries
        """
        close_client = False
        if redis_client is None:
            redis_client = redis.Redis(connection_pool=redis_pool)
            close_client = True

        try:
            # Get job IDs sorted by creation time (newest first)
            job_ids = await redis_client.zrevrange("magellon:jobs", offset, offset + limit - 1)

            jobs = []
            for job_id in job_ids:
                job_data = await self.get_job_async(job_id, redis_client)

                if job_data:
                    # Apply filters if specified
                    if status and job_data.get("status") != status:
                        continue
                    if job_type and job_data.get("job_type") != job_type:
                        continue

                    jobs.append(job_data)

            return jobs
        finally:
            if close_client:
                await redis_client.close()

    async def delete_job_async(
            self,
            job_id: str,
            redis_client: Optional[redis.Redis] = None
    ) -> bool:
        """
        Delete a job asynchronously.

        Args:
            job_id: Job identifier
            redis_client: Optional Redis client

        Returns:
            success: True if deleted, False if not found
        """
        close_client = False
        if redis_client is None:
            redis_client = redis.Redis(connection_pool=redis_pool)
            close_client = True

        try:
            # Check if job exists
            job_key = get_job_key(job_id)
            if not await redis_client.exists(job_key):
                return False

            # Delete job data
            await redis_client.delete(job_key)

            # Remove from sorted set
            await redis_client.zrem("magellon:jobs", job_id)

            # Publish deletion event
            await redis_client.publish("magellon:job_events", json.dumps({
                "type": "job_deleted",
                "job_id": job_id
            }))

            logger.info(f"Deleted job {job_id}")
            return True
        finally:
            if close_client:
                await redis_client.close()

    # =============== Synchronous API ===============

    def create_job(
            self,
            job_type: str,
            name: str,
            description: Optional[str] = None,
            metadata: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Create a new job synchronously.

        Args:
            job_type: Type of job (e.g., "magellon_import")
            name: Job name
            description: Job description
            metadata: Additional metadata

        Returns:
            job_id: Unique job identifier
        """
        return asyncio.run(self.create_job_async(job_type, name, description, metadata))

    def get_job(self, job_id: str) -> Optional[Dict[str, Any]]:
        """
        Get job data synchronously.

        Args:
            job_id: Job identifier

        Returns:
            job_data: Job data or None if not found
        """
        return asyncio.run(self.get_job_async(job_id))

    def update_job(self, job_id: str, updates: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Update job data synchronously.

        Args:
            job_id: Job identifier
            updates: Dictionary of fields to update

        Returns:
            updated_job_data: Updated job data or None if job not found
        """
        return asyncio.run(self.update_job_async(job_id, updates))

    def update_progress(
            self,
            job_id: str,
            progress: int,
            current_task: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Update job progress synchronously.

        Args:
            job_id: Job identifier
            progress: Progress percentage (0-100)
            current_task: Description of current task

        Returns:
            updated_job_data: Updated job data or None if job not found
        """
        return asyncio.run(self.update_progress_async(job_id, progress, current_task))

    def request_cancellation(self, job_id: str) -> bool:
        """
        Request job cancellation synchronously.

        Args:
            job_id: Job identifier

        Returns:
            success: True if cancellation requested, False if job not found or already in terminal state
        """
        return asyncio.run(self.request_cancellation_async(job_id))

    def is_cancellation_requested(self, job_id: str) -> bool:
        """
        Check if cancellation was requested synchronously.

        Args:
            job_id: Job identifier

        Returns:
            requested: True if cancellation requested, False otherwise
        """
        return asyncio.run(self.is_cancellation_requested_async(job_id))

    def increment_task_counter(
            self,
            job_id: str,
            completed: int = 0,
            failed: int = 0,
            total: int = 0
    ) -> Optional[Dict[str, Any]]:
        """
        Increment task counters synchronously.

        Args:
            job_id: Job identifier
            completed: Number of completed tasks to add
            failed: Number of failed tasks to add
            total: Number of total tasks to add

        Returns:
            updated_job_data: Updated job data or None if job not found
        """
        return asyncio.run(self.increment_task_counter_async(
            job_id, completed, failed, total
        ))

    def list_jobs(
            self,
            limit: int = 20,
            offset: int = 0,
            status: Optional[str] = None,
            job_type: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        List jobs synchronously with optional filtering.

        Args:
            limit: Maximum number of jobs to return
            offset: Offset for pagination
            status: Filter by status
            job_type: Filter by job type

        Returns:
            jobs: List of job data dictionaries
        """
        return asyncio.run(self.list_jobs_async(limit, offset, status, job_type))

    def delete_job(self, job_id: str) -> bool:
        """
        Delete a job synchronously.

        Args:
            job_id: Job identifier

        Returns:
            success: True if deleted, False if not found
        """
        return asyncio.run(self.delete_job_async(job_id))