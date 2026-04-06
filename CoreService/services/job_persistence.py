"""
Persistence logic for job and task data.

Handles loading and saving jobs/tasks to JSON files on disk.
"""

import json
import logging
import os
from typing import Dict, Tuple

from services.job_models import Job, Task

logger = logging.getLogger(__name__)


class JobPersistence:
    """Handles JSON file-based persistence for jobs and tasks."""

    def __init__(self, data_dir: str = None):
        """
        Initialize persistence layer.

        Args:
            data_dir: Directory for storing JSON files.
                      Defaults to a 'job_data' subdirectory next to this file.
        """
        if data_dir is None:
            data_dir = os.path.join(os.path.dirname(__file__), "job_data")

        self._data_dir = data_dir
        self._jobs_file = os.path.join(self._data_dir, "jobs.json")
        self._tasks_file = os.path.join(self._data_dir, "tasks.json")

        # Ensure data directory exists
        os.makedirs(self._data_dir, exist_ok=True)

    async def load(self) -> Tuple[Dict[str, Dict], Dict[str, Dict]]:
        """
        Load jobs and tasks data from JSON files.

        Returns:
            Tuple of (jobs_data dict, tasks_data dict) where each maps
            ID -> serialized dict. Returns empty dicts if files don't exist.
        """
        jobs_data: Dict[str, Dict] = {}
        tasks_data: Dict[str, Dict] = {}

        try:
            if os.path.exists(self._jobs_file) and os.path.exists(self._tasks_file):
                with open(self._jobs_file, 'r') as f:
                    jobs_data = json.load(f)

                with open(self._tasks_file, 'r') as f:
                    tasks_data = json.load(f)

            logger.info(f"Loaded {len(jobs_data)} jobs and {len(tasks_data)} tasks from persistence")

        except Exception as e:
            logger.error(f"Error loading from persistence: {str(e)}")

        return jobs_data, tasks_data

    async def save(self, jobs: Dict[str, 'Job'], tasks: Dict[str, 'Task']) -> None:
        """
        Save jobs and tasks to JSON files.

        Args:
            jobs: Dictionary mapping job_id -> Job object
            tasks: Dictionary mapping task_id -> Task object
        """
        try:
            jobs_data = {job_id: job.to_dict() for job_id, job in jobs.items()}
            tasks_data = {task_id: task.to_dict() for task_id, task in tasks.items()}

            with open(self._jobs_file, 'w') as f:
                json.dump(jobs_data, f, indent=2)

            with open(self._tasks_file, 'w') as f:
                json.dump(tasks_data, f, indent=2)

            logger.info(f"Saved {len(jobs)} jobs and {len(tasks)} tasks to persistence")

        except Exception as e:
            logger.error(f"Error saving to persistence: {str(e)}")
