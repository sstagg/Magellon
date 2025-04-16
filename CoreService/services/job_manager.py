import json
import time
import uuid
from typing import Dict, Any, Optional, List
from datetime import datetime
import redis
import logging

logger = logging.getLogger(__name__)

class JobStatus:
    """Job status constants"""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"

class JobManager:
    """
    Manages job status, progress, and cancellation using Redis.
    Provides synchronous interface for easy integration with existing code.
    """

    def __init__(self, redis_url="redis://localhost:6379/0"):
        """Initialize with Redis connection"""
        self.redis = redis.Redis.from_url(redis_url, decode_responses=True)
        self.prefix = "magellon:job:"

    def create_job(self, job_type: str, name: str, description: Optional[str] = None) -> str:
        """
        Create a new job

        Args:
            job_type: Type of job (e.g., "magellon_import")
            name: Job name
            description: Optional description

        Returns:
            job_id: Unique job identifier
        """
        job_id = str(uuid.uuid4())

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
            "cancel_requested": False,
            "current_task": None,
            "error": None
        }

        # Store in Redis
        self.redis.set(f"{self.prefix}{job_id}", json.dumps(job_data))

        # Add to job list
        self.redis.zadd("magellon:jobs", {job_id: time.time()})

        return job_id

    def update_job(self, job_id: str, updates: Dict[str, Any]) -> bool:
        """
        Update job data

        Args:
            job_id: Job identifier
            updates: Dictionary of fields to update

        Returns:
            success: True if updated, False if job not found
        """
        job_data = self.get_job(job_id)

        if not job_data:
            return False

        # Apply updates
        job_data.update(updates)
        job_data["updated_at"] = datetime.now().isoformat()

        # Set completed_at if status changed to terminal state
        if "status" in updates:
            if updates["status"] in [JobStatus.COMPLETED, JobStatus.FAILED, JobStatus.CANCELLED]:
                job_data["completed_at"] = datetime.now().isoformat()

        # Store back to Redis
        self.redis.set(f"{self.prefix}{job_id}", json.dumps(job_data))

        # Publish update event
        self.redis.publish("magellon:job_events", json.dumps({
            "type": "job_updated",
            "job_id": job_id
        }))

        return True

    def get_job(self, job_id: str) -> Optional[Dict[str, Any]]:
        """
        Get job data

        Args:
            job_id: Job identifier

        Returns:
            job_data: Job data or None if not found
        """
        job_json = self.redis.get(f"{self.prefix}{job_id}")

        if not job_json:
            return None

        return json.loads(job_json)

    def request_cancellation(self, job_id: str) -> bool:
        """
        Request cancellation of a job

        Args:
            job_id: Job identifier

        Returns:
            success: True if cancellation requested, False if job not found or already in terminal state
        """
        job_data = self.get_job(job_id)

        if not job_data:
            return False

        # Skip if already in terminal state
        if job_data["status"] in [JobStatus.COMPLETED, JobStatus.FAILED, JobStatus.CANCELLED]:
            return False

        # Update cancel flag
        updates = {"cancel_requested": True}

        # If job is still pending, mark as cancelled immediately
        if job_data["status"] == JobStatus.PENDING:
            updates["status"] = JobStatus.CANCELLED

        return self.update_job(job_id, updates)

    def is_cancellation_requested(self, job_id: str) -> bool:
        """
        Check if cancellation was requested

        Args:
            job_id: Job identifier

        Returns:
            requested: True if cancellation requested, False otherwise
        """
        job_data = self.get_job(job_id)

        if not job_data:
            return False

        return job_data.get("cancel_requested", False)

    def update_progress(self, job_id: str, progress: int, current_task: Optional[str] = None) -> bool:
        """
        Update job progress

        Args:
            job_id: Job identifier
            progress: Progress percentage (0-100)
            current_task: Description of current task

        Returns:
            success: True if updated, False if job not found
        """
        updates = {"progress": min(max(progress, 0), 100)}

        if current_task is not None:
            updates["current_task"] = current_task

        return self.update_job(job_id, updates)

    def list_jobs(self, limit: int = 20, offset: int = 0, status: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        List jobs with optional filtering

        Args:
            limit: Maximum number of jobs to return
            offset: Offset for pagination
            status: Filter by status

        Returns:
            jobs: List of job data dictionaries
        """
        # Get job IDs from sorted set
        job_ids = self.redis.zrevrange("magellon:jobs", offset, offset + limit - 1)

        jobs = []
        for job_id in job_ids:
            job_data = self.get_job(job_id)
            if job_data:
                # Apply status filter if specified
                if status and job_data["status"] != status:
                    continue

                jobs.append(job_data)

        return jobs