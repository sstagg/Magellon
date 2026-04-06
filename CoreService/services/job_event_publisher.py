"""
Event publishing facade for job and task events.

Wraps MagellonEventService with convenient methods for publishing
job lifecycle, task lifecycle, file, directory, and processing events.
"""

import logging
from typing import Dict, Any, Optional

from event_types import EventType
from magellon_event_service import MagellonEventService

logger = logging.getLogger(__name__)


class JobEventPublisher:
    """Facade over MagellonEventService for job/task event publishing."""

    def __init__(self, event_service: MagellonEventService):
        """
        Initialize the event publisher.

        Args:
            event_service: The underlying MagellonEventService instance.
        """
        self.event_service = event_service

    async def publish_job_event(self, event_type: EventType, job) -> str:
        """
        Publish a job-related event.

        Args:
            event_type: Event type from EventType enum
            job: Job object (must have to_dict() and job_id)

        Returns:
            Event ID
        """
        return await self.event_service.publish_event(
            event_type,
            job.to_dict(),
            job.job_id
        )

    async def publish_task_event(self, event_type: EventType, task) -> str:
        """
        Publish a task-related event.

        Args:
            event_type: Event type from EventType enum
            task: Task object (must have to_dict(), task_id, job_id)

        Returns:
            Event ID
        """
        return await self.event_service.publish_task_event(
            event_type,
            task.task_id,
            task.job_id,
            task.to_dict()
        )

    async def publish_file_event(
            self,
            event_type: EventType,
            file_path: str,
            file_data: Dict[str, Any],
            job_id: Optional[str] = None
    ) -> str:
        """
        Publish a file-related event.

        Args:
            event_type: Event type from EventType enum
            file_path: Path to the file
            file_data: Additional file data
            job_id: Optional job ID for context

        Returns:
            Event ID
        """
        data = {**file_data, "file_path": file_path}
        return await self.event_service.publish_file_event(
            event_type,
            file_path,
            data,
            job_id
        )

    async def publish_directory_event(
            self,
            event_type: EventType,
            dir_path: str,
            dir_data: Dict[str, Any],
            job_id: Optional[str] = None
    ) -> str:
        """
        Publish a directory-related event.

        Args:
            event_type: Event type from EventType enum
            dir_path: Path to the directory
            dir_data: Additional directory data
            job_id: Optional job ID for context

        Returns:
            Event ID
        """
        data = {**dir_data, "directory_path": dir_path}
        return await self.event_service.publish_directory_event(
            event_type,
            dir_path,
            data,
            job_id
        )

    async def publish_processing_event(
            self,
            event_type: EventType,
            process_data: Dict[str, Any],
            job_id: Optional[str] = None,
            task_id: Optional[str] = None
    ) -> str:
        """
        Publish a processing-related event.

        Args:
            event_type: Event type from EventType enum
            process_data: Processing data
            job_id: Optional job ID for context
            task_id: Optional task ID for context

        Returns:
            Event ID
        """
        return await self.event_service.publish_processing_event(
            event_type,
            process_data,
            job_id,
            task_id
        )
