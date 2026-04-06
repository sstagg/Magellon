"""
Event Publisher Service for NATS Integration

Publishes events to NATS message broker for distributed event-driven architecture.
Used by workflows, activities, and job manager to broadcast events.
"""

import json
import asyncio
from datetime import datetime
from typing import Dict, Any, Optional
from nats.aio.client import Client as NATS
from config import settings
import logging

logger = logging.getLogger(__name__)


class EventPublisher:
    """
    Centralized event publisher for NATS message broker.

    Publishes events for:
    - Job lifecycle (created, started, progress, completed, failed, cancelled)
    - Workflow steps (started, progress, completed, failed)
    - System events (worker registered, worker heartbeat)
    """

    def __init__(self, nats_url: str = "nats://localhost:4222"):
        self.nats_url = nats_url
        self.nc: Optional[NATS] = None
        self._connected = False

    async def connect(self):
        """Connect to NATS server"""
        if self._connected:
            return

        try:
            self.nc = NATS()
            await self.nc.connect(self.nats_url)
            self._connected = True
            logger.info(f"Connected to NATS server at {self.nats_url}")
        except Exception as e:
            logger.error(f"Failed to connect to NATS: {e}")
            raise

    async def disconnect(self):
        """Disconnect from NATS server"""
        if self.nc and self._connected:
            await self.nc.close()
            self._connected = False
            logger.info("Disconnected from NATS server")

    async def _publish(self, subject: str, data: Dict[str, Any]):
        """
        Internal method to publish event to NATS

        Args:
            subject: NATS subject (e.g., 'job.created', 'step.progress')
            data: Event data dictionary
        """
        if not self._connected:
            await self.connect()

        try:
            # Add timestamp if not present
            if "timestamp" not in data:
                data["timestamp"] = datetime.utcnow().isoformat()

            # Serialize to JSON
            message = json.dumps(data).encode()

            # Publish to NATS
            await self.nc.publish(subject, message)

            logger.debug(f"Published event to '{subject}': {data}")

        except Exception as e:
            logger.error(f"Failed to publish event to '{subject}': {e}")
            raise

    # ========== Job Events ==========

    async def publish_job_created(self, job_id: str, job_type: str, name: str, metadata: Dict[str, Any] = None):
        """Publish job created event"""
        await self._publish("job.created", {
            "job_id": job_id,
            "job_type": job_type,
            "name": name,
            "metadata": metadata or {},
            "status": "pending"
        })

    async def publish_job_started(self, job_id: str, workflow_id: str):
        """Publish job started event"""
        await self._publish("job.started", {
            "job_id": job_id,
            "workflow_id": workflow_id,
            "status": "running"
        })

    async def publish_job_progress(self, job_id: str, progress: int, current_step: str, step_details: Dict[str, Any] = None):
        """
        Publish job progress event

        Args:
            job_id: Unique job identifier
            progress: Overall progress percentage (0-100)
            current_step: Name of current step being executed
            step_details: Additional details about current step
        """
        await self._publish("job.progress", {
            "job_id": job_id,
            "progress": progress,
            "current_step": current_step,
            "step_details": step_details or {}
        })

    async def publish_job_completed(self, job_id: str, result: Dict[str, Any] = None, duration_seconds: float = None):
        """Publish job completed event"""
        await self._publish("job.completed", {
            "job_id": job_id,
            "status": "completed",
            "result": result or {},
            "duration_seconds": duration_seconds
        })

    async def publish_job_failed(self, job_id: str, error: str, error_details: Dict[str, Any] = None):
        """Publish job failed event"""
        await self._publish("job.failed", {
            "job_id": job_id,
            "status": "failed",
            "error": error,
            "error_details": error_details or {}
        })

    async def publish_job_cancelled(self, job_id: str, reason: str = None):
        """Publish job cancelled event"""
        await self._publish("job.cancelled", {
            "job_id": job_id,
            "status": "cancelled",
            "reason": reason or "User requested cancellation"
        })

    # ========== Step/Activity Events ==========

    async def publish_step_started(self, job_id: str, step_name: str, step_index: int, total_steps: int):
        """Publish workflow step started event"""
        await self._publish("step.started", {
            "job_id": job_id,
            "step_name": step_name,
            "step_index": step_index,
            "total_steps": total_steps,
            "status": "running"
        })

    async def publish_step_progress(self, job_id: str, step_name: str, progress: int, message: str = None):
        """
        Publish step progress event

        Args:
            job_id: Job identifier
            step_name: Name of the step
            progress: Step progress percentage (0-100)
            message: Optional progress message
        """
        await self._publish("step.progress", {
            "job_id": job_id,
            "step_name": step_name,
            "progress": progress,
            "message": message
        })

    async def publish_step_completed(self, job_id: str, step_name: str, result: Dict[str, Any] = None, duration_seconds: float = None):
        """Publish workflow step completed event"""
        await self._publish("step.completed", {
            "job_id": job_id,
            "step_name": step_name,
            "status": "completed",
            "result": result or {},
            "duration_seconds": duration_seconds
        })

    async def publish_step_failed(self, job_id: str, step_name: str, error: str, retry_count: int = 0):
        """Publish workflow step failed event"""
        await self._publish("step.failed", {
            "job_id": job_id,
            "step_name": step_name,
            "status": "failed",
            "error": error,
            "retry_count": retry_count
        })

    # ========== Worker Events ==========

    async def publish_worker_registered(self, worker_id: str, worker_type: str, capabilities: list):
        """Publish worker registered event"""
        await self._publish("worker.registered", {
            "worker_id": worker_id,
            "worker_type": worker_type,
            "capabilities": capabilities
        })

    async def publish_worker_heartbeat(self, worker_id: str, status: str, current_tasks: int = 0):
        """Publish worker heartbeat event"""
        await self._publish("worker.heartbeat", {
            "worker_id": worker_id,
            "status": status,
            "current_tasks": current_tasks
        })


# Global singleton instance
_event_publisher: Optional[EventPublisher] = None


async def get_event_publisher() -> EventPublisher:
    """
    Get or create global event publisher instance.

    Usage in FastAPI:
        from services.event_publisher import get_event_publisher

        event_publisher = await get_event_publisher()
        await event_publisher.publish_job_started(job_id, workflow_id)
    """
    global _event_publisher

    if _event_publisher is None:
        nats_url = getattr(settings, 'nats_url', 'nats://localhost:4222')
        _event_publisher = EventPublisher(nats_url)
        await _event_publisher.connect()

    return _event_publisher
