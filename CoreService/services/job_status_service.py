import json
import time
import uuid
import asyncio
from typing import Dict, Any, Optional, List, Union
import redis.asyncio as redis
from fastapi import BackgroundTasks, Depends
import logging

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

# Job status constants
class JobStatus:
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


# Redis dependency
async def get_redis() -> redis.Redis:
    """Get Redis connection from pool."""
    client = redis.Redis(connection_pool=redis_pool)
    try:
        yield client
    finally:
        await client.close()


def get_redis_sync() -> redis.Redis:
    """Get synchronous Redis connection from pool for non-async contexts."""
    return redis.Redis(connection_pool=redis_pool)


# Helper function to get a prefixed Redis key
def get_job_key(job_id: str) -> str:
    """Get a Redis key with the Magellon job prefix."""
    return f"{REDIS_PREFIX}{job_id}"


class JobStatusService:
    """Service for tracking job status using Redis."""

    @staticmethod
    async def create_job(
        redis_client: redis.Redis,
        job_id: str,
        job_type: str,
        name: str,
        description: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Create a new job in Redis.
        
        Args:
            redis_client: Redis client
            job_id: Unique job identifier
            job_type: Type of job (e.g., "magellon_import", "epu_import")
            name: Job name
            description: Job description
            metadata: Additional metadata
            
        Returns:
            Job data dictionary
        """
        job_data = {
            "job_id": job_id,
            "job_type": job_type,
            "name": name,
            "description": description,
            "status": JobStatus.PENDING,
            "progress": 0,
            "result": None,
            "error": None,
            "created_at": time.time(),
            "updated_at": time.time(),
            "completed_at": None,
            "metadata": metadata or {},
            "tasks_total": 0,
            "tasks_completed": 0,
            "tasks_failed": 0,
            "current_task": None,
            "cancel_requested": False
        }

        # Store job data as JSON string in Redis
        job_key = get_job_key(job_id)
        await redis_client.set(job_key, json.dumps(job_data))

        # Add to a sorted set for easier listing (sorted by creation time)
        await redis_client.zadd("magellon:jobs", {job_id: time.time()})

        # Publish a message to the job events channel
        await redis_client.publish("magellon:job_events", json.dumps({
            "job_id": job_id,
            "event": "created",
            "data": job_data
        }))

        return job_data

    @staticmethod
    async def update_job(
        redis_client: redis.Redis,
        job_id: str,
        updates: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Update an existing job in Redis.
        
        Args:
            redis_client: Redis client
            job_id: Job identifier
            updates: Dictionary of fields to update
            
        Returns:
            Updated job data
        """
        # Get current job data
        job_key = get_job_key(job_id)
        job_json = await redis_client.get(job_key)
        
        if not job_json:
            raise ValueError(f"Job {job_id} not found")

        job_data = json.loads(job_json)

        # Update with new values
        job_data.update(updates)
        job_data["updated_at"] = time.time()
        
        # Handle status transitions
        if "status" in updates:
            if updates["status"] == JobStatus.COMPLETED:
                job_data["completed_at"] = time.time()
                job_data["progress"] = 100
            elif updates["status"] == JobStatus.FAILED:
                job_data["completed_at"] = time.time()

        # Store updated data back to Redis
        await redis_client.set(job_key, json.dumps(job_data))

        # Publish update to channel
        await redis_client.publish("magellon:job_events", json.dumps({
            "job_id": job_id,
            "event": "updated",
            "data": updates
        }))

        return job_data

    @staticmethod
    async def get_job(redis_client: redis.Redis, job_id: str) -> Optional[Dict[str, Any]]:
        """
        Get job data from Redis.
        
        Args:
            redis_client: Redis client
            job_id: Job identifier
            
        Returns:
            Job data or None if not found
        """
        job_key = get_job_key(job_id)
        job_json = await redis_client.get(job_key)
        
        if not job_json:
            return None

        return json.loads(job_json)

    @staticmethod
    async def request_job_cancellation(redis_client: redis.Redis, job_id: str) -> bool:
        """
        Request cancellation of a job.
        
        Args:
            redis_client: Redis client
            job_id: Job identifier
            
        Returns:
            True if cancellation was requested, False if job not found or already completed
        """
        job_data = await JobStatusService.get_job(redis_client, job_id)
        
        if not job_data:
            return False
            
        if job_data["status"] in [JobStatus.COMPLETED, JobStatus.FAILED, JobStatus.CANCELLED]:
            return False
            
        # Set cancel_requested flag
        await JobStatusService.update_job(redis_client, job_id, {
            "cancel_requested": True,
            "status": JobStatus.CANCELLED if job_data["status"] == JobStatus.PENDING else job_data["status"]
        })
        
        # Publish cancellation request
        await redis_client.publish("magellon:job_events", json.dumps({
            "job_id": job_id,
            "event": "cancellation_requested"
        }))
        
        return True

    @staticmethod
    async def is_cancellation_requested(redis_client: redis.Redis, job_id: str) -> bool:
        """
        Check if cancellation was requested for a job.
        
        Args:
            redis_client: Redis client
            job_id: Job identifier
            
        Returns:
            True if cancellation was requested
        """
        job_data = await JobStatusService.get_job(redis_client, job_id)
        
        if not job_data:
            return False
            
        return job_data.get("cancel_requested", False)

    @staticmethod
    async def list_jobs(
        redis_client: redis.Redis,
        limit: int = 20,
        offset: int = 0,
        status: Optional[str] = None,
        job_type: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        List jobs from Redis with optional filtering.
        
        Args:
            redis_client: Redis client
            limit: Maximum number of jobs to return
            offset: Offset for pagination
            status: Filter by status
            job_type: Filter by job type
            
        Returns:
            List of job data dictionaries
        """
        # Get job IDs sorted by creation time (newest first)
        job_ids = await redis_client.zrevrange("magellon:jobs", offset, offset + limit - 1)

        jobs = []
        for job_id in job_ids:
            job_json = await redis_client.get(get_job_key(job_id))
            if job_json:
                job_data = json.loads(job_json)
                
                # Apply filters if specified
                if (status and job_data.get("status") != status) or \
                   (job_type and job_data.get("job_type") != job_type):
                    continue
                    
                jobs.append(job_data)

        return jobs

    @staticmethod
    async def delete_job(redis_client: redis.Redis, job_id: str) -> bool:
        """
        Delete a job from Redis.
        
        Args:
            redis_client: Redis client
            job_id: Job identifier
            
        Returns:
            True if deleted, False if not found
        """
        job_key = get_job_key(job_id)
        if not await redis_client.exists(job_key):
            return False
            
        # Delete job data
        await redis_client.delete(job_key)
        
        # Remove from sorted set
        await redis_client.zrem("magellon:jobs", job_id)
        
        # Publish deletion event
        await redis_client.publish("magellon:job_events", json.dumps({
            "job_id": job_id,
            "event": "deleted"
        }))
        
        return True

    @staticmethod
    async def update_job_progress(
        redis_client: redis.Redis,
        job_id: str,
        progress: int,
        current_task: Optional[str] = None,
        message: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Update job progress.
        
        Args:
            redis_client: Redis client
            job_id: Job identifier
            progress: Progress percentage (0-100)
            current_task: Description of current task
            message: Progress message
            
        Returns:
            Updated job data
        """
        updates = {"progress": min(max(progress, 0), 100)}
        
        if current_task is not None:
            updates["current_task"] = current_task
            
        if message is not None:
            updates["message"] = message
            
        return await JobStatusService.update_job(redis_client, job_id, updates)

    @staticmethod
    async def increment_task_counter(
        redis_client: redis.Redis,
        job_id: str,
        completed: int = 0,
        failed: int = 0,
        total: int = 0
    ) -> Dict[str, Any]:
        """
        Increment task counters for a job.
        
        Args:
            redis_client: Redis client
            job_id: Job identifier
            completed: Number of completed tasks to add
            failed: Number of failed tasks to add
            total: Number of total tasks to add
            
        Returns:
            Updated job data
        """
        job_data = await JobStatusService.get_job(redis_client, job_id)
        
        if not job_data:
            raise ValueError(f"Job {job_id} not found")
            
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
            updates["progress"] = min(int((completed_tasks / total_tasks) * 100), 100)
            
        return await JobStatusService.update_job(redis_client, job_id, updates)

    # Synchronous versions for non-async contexts
    @staticmethod
    def update_job_sync(
        job_id: str,
        updates: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Synchronous version of update_job for non-async contexts."""
        redis_client = get_redis_sync()
        try:
            return asyncio.run(JobStatusService.update_job(redis_client, job_id, updates))
        finally:
            redis_client.close()

    @staticmethod
    def get_job_sync(job_id: str) -> Optional[Dict[str, Any]]:
        """Synchronous version of get_job for non-async contexts."""
        redis_client = get_redis_sync()
        try:
            return asyncio.run(JobStatusService.get_job(redis_client, job_id))
        finally:
            redis_client.close()

    @staticmethod
    def update_job_progress_sync(
        job_id: str,
        progress: int,
        current_task: Optional[str] = None,
        message: Optional[str] = None
    ) -> Dict[str, Any]:
        """Synchronous version of update_job_progress for non-async contexts."""
        redis_client = get_redis_sync()
        try:
            return asyncio.run(JobStatusService.update_job_progress(
                redis_client, job_id, progress, current_task, message))
        finally:
            redis_client.close()

    @staticmethod
    def is_cancellation_requested_sync(job_id: str) -> bool:
        """Synchronous version of is_cancellation_requested for non-async contexts."""
        redis_client = get_redis_sync()
        try:
            return asyncio.run(JobStatusService.is_cancellation_requested(redis_client, job_id))
        finally:
            redis_client.close()

    @staticmethod
    def increment_task_counter_sync(
        job_id: str,
        completed: int = 0,
        failed: int = 0,
        total: int = 0
    ) -> Dict[str, Any]:
        """Synchronous version of increment_task_counter for non-async contexts."""
        redis_client = get_redis_sync()
        try:
            return asyncio.run(JobStatusService.increment_task_counter(
                redis_client, job_id, completed, failed, total))
        finally:
            redis_client.close()
