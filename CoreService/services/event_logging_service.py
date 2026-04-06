"""
Event Logging Service

Subscribes to NATS events and logs all workflow and job activity.

This service:
- Subscribes to all job.* and step.* events
- Logs events to file and/or database
- Provides audit trail for all workflow executions
- Can be used for monitoring and debugging

Features:
- Real-time event logging
- Structured log format (JSON)
- Separate log files per job (optional)
- Database logging (optional)
- Event replay from logs

Usage:
    python -m services.event_logging_service
"""

import asyncio
import json
import logging
import os
from datetime import datetime
from typing import Optional
from pathlib import Path
from nats.aio.client import Client as NATS

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class EventLoggingService:
    """
    NATS event subscriber that logs all workflow events.

    Subscribes to:
    - job.* events (created, started, progress, completed, failed, cancelled)
    - step.* events (started, progress, completed, failed)
    - worker.* events (registered, heartbeat)
    """

    def __init__(
        self,
        nats_url: str = "nats://localhost:4222",
        log_dir: str = "logs/events",
        log_to_file: bool = True,
        log_to_console: bool = True,
        separate_job_logs: bool = True
    ):
        """
        Initialize Event Logging Service

        Args:
            nats_url: NATS server URL
            log_dir: Directory to store event logs
            log_to_file: Whether to log events to file
            log_to_console: Whether to log events to console
            separate_job_logs: Create separate log file per job
        """
        self.nats_url = nats_url
        self.log_dir = Path(log_dir)
        self.log_to_file = log_to_file
        self.log_to_console = log_to_console
        self.separate_job_logs = separate_job_logs

        self.nc: Optional[NATS] = None
        self._connected = False
        self._subscriptions = []

        # Create log directory
        if self.log_to_file:
            self.log_dir.mkdir(parents=True, exist_ok=True)
            logger.info(f"Event logs will be stored in: {self.log_dir}")

        # Main event log file
        self.main_log_file = self.log_dir / "events.jsonl" if self.log_to_file else None

        # Job-specific log files
        self.job_log_files = {}  # job_id -> file handle

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
        if not self._connected:
            return

        # Unsubscribe from all subscriptions
        for sub in self._subscriptions:
            try:
                await sub.unsubscribe()
            except Exception as e:
                logger.error(f"Error unsubscribing: {e}")

        # Close NATS connection
        if self.nc:
            await self.nc.close()
            self._connected = False

        # Close all job log files
        for log_file in self.job_log_files.values():
            try:
                log_file.close()
            except Exception as e:
                logger.error(f"Error closing log file: {e}")

        logger.info("Disconnected from NATS server")

    async def _log_event(self, subject: str, data: dict):
        """
        Log event to file and/or console

        Args:
            subject: NATS subject (event type)
            data: Event data
        """
        # Create log entry
        log_entry = {
            "timestamp": datetime.utcnow().isoformat(),
            "event_type": subject,
            "data": data
        }

        # Log to console
        if self.log_to_console:
            job_id = data.get("job_id", "unknown")
            logger.info(f"[{subject}] Job {job_id}: {json.dumps(data, indent=2)}")

        # Log to main file
        if self.log_to_file and self.main_log_file:
            try:
                with open(self.main_log_file, 'a') as f:
                    f.write(json.dumps(log_entry) + '\n')
            except Exception as e:
                logger.error(f"Failed to write to main log file: {e}")

        # Log to job-specific file
        if self.log_to_file and self.separate_job_logs:
            job_id = data.get("job_id")
            if job_id:
                try:
                    # Get or create job log file
                    if job_id not in self.job_log_files:
                        job_log_path = self.log_dir / f"job_{job_id}.jsonl"
                        self.job_log_files[job_id] = open(job_log_path, 'a')

                    # Write to job log
                    job_log_file = self.job_log_files[job_id]
                    job_log_file.write(json.dumps(log_entry) + '\n')
                    job_log_file.flush()  # Ensure it's written immediately

                except Exception as e:
                    logger.error(f"Failed to write to job log file for {job_id}: {e}")

    async def _job_event_handler(self, msg):
        """Handle job.* events"""
        try:
            data = json.loads(msg.data.decode())
            await self._log_event(msg.subject, data)

            # Special handling for specific event types
            if msg.subject == "job.created":
                logger.info(f"NEW JOB: {data.get('name')} (ID: {data.get('job_id')})")

            elif msg.subject == "job.started":
                logger.info(f"JOB STARTED: {data.get('job_id')} (Workflow: {data.get('workflow_id')})")

            elif msg.subject == "job.completed":
                logger.info(f"JOB COMPLETED: {data.get('job_id')}")
                # Close job log file if separate logs enabled
                if self.separate_job_logs:
                    job_id = data.get('job_id')
                    if job_id in self.job_log_files:
                        self.job_log_files[job_id].close()
                        del self.job_log_files[job_id]

            elif msg.subject == "job.failed":
                logger.error(f"JOB FAILED: {data.get('job_id')} - {data.get('error')}")

            elif msg.subject == "job.cancelled":
                logger.warning(f"JOB CANCELLED: {data.get('job_id')} - {data.get('reason')}")

        except Exception as e:
            logger.error(f"Error handling job event: {e}")

    async def _step_event_handler(self, msg):
        """Handle step.* events"""
        try:
            data = json.loads(msg.data.decode())
            await self._log_event(msg.subject, data)

            # Special handling for specific event types
            if msg.subject == "step.started":
                logger.info(f"STEP STARTED: {data.get('step_name')} (Job: {data.get('job_id')})")

            elif msg.subject == "step.completed":
                logger.info(f"STEP COMPLETED: {data.get('step_name')} (Job: {data.get('job_id')})")

            elif msg.subject == "step.failed":
                logger.error(f"STEP FAILED: {data.get('step_name')} (Job: {data.get('job_id')}) - {data.get('error')}")

        except Exception as e:
            logger.error(f"Error handling step event: {e}")

    async def _worker_event_handler(self, msg):
        """Handle worker.* events"""
        try:
            data = json.loads(msg.data.decode())
            await self._log_event(msg.subject, data)

            # Special handling for specific event types
            if msg.subject == "worker.registered":
                logger.info(f"WORKER REGISTERED: {data.get('worker_id')} (Type: {data.get('worker_type')})")

            # Don't log heartbeats to console (too verbose)
            # They're still logged to file

        except Exception as e:
            logger.error(f"Error handling worker event: {e}")

    async def start(self):
        """Start the event logging service"""
        if not self._connected:
            await self.connect()

        logger.info("=" * 60)
        logger.info("Event Logging Service")
        logger.info("=" * 60)
        logger.info(f"NATS Server: {self.nats_url}")
        logger.info(f"Log Directory: {self.log_dir}")
        logger.info(f"Log to File: {self.log_to_file}")
        logger.info(f"Log to Console: {self.log_to_console}")
        logger.info(f"Separate Job Logs: {self.separate_job_logs}")
        logger.info("=" * 60)

        # Subscribe to job events
        job_sub = await self.nc.subscribe("job.*", cb=self._job_event_handler)
        self._subscriptions.append(job_sub)
        logger.info("Subscribed to: job.*")

        # Subscribe to step events
        step_sub = await self.nc.subscribe("step.*", cb=self._step_event_handler)
        self._subscriptions.append(step_sub)
        logger.info("Subscribed to: step.*")

        # Subscribe to worker events
        worker_sub = await self.nc.subscribe("worker.*", cb=self._worker_event_handler)
        self._subscriptions.append(worker_sub)
        logger.info("Subscribed to: worker.*")

        logger.info("=" * 60)
        logger.info("Event Logging Service started successfully!")
        logger.info("Listening for events...")
        logger.info("(Press Ctrl+C to stop)")
        logger.info("=" * 60)

    def read_job_events(self, job_id: str) -> list:
        """
        Read all events for a specific job from log file

        Args:
            job_id: Job identifier

        Returns:
            List of event dictionaries in chronological order
        """
        if not self.log_to_file or not self.separate_job_logs:
            logger.warning("Job logs are not enabled")
            return []

        job_log_path = self.log_dir / f"job_{job_id}.jsonl"

        if not job_log_path.exists():
            logger.warning(f"No log file found for job {job_id}")
            return []

        events = []
        try:
            with open(job_log_path, 'r') as f:
                for line in f:
                    event = json.loads(line.strip())
                    events.append(event)

            logger.info(f"Read {len(events)} events for job {job_id}")
            return events

        except Exception as e:
            logger.error(f"Error reading job log file: {e}")
            return []


async def main():
    """Main function to run the event logging service"""

    # Configuration
    nats_url = os.getenv("NATS_URL", "nats://localhost:4222")
    log_dir = os.getenv("EVENT_LOG_DIR", "logs/events")

    # Create service
    service = EventLoggingService(
        nats_url=nats_url,
        log_dir=log_dir,
        log_to_file=True,
        log_to_console=True,
        separate_job_logs=True
    )

    try:
        # Start service
        await service.start()

        # Keep running
        while True:
            await asyncio.sleep(1)

    except KeyboardInterrupt:
        logger.info("\nShutting down event logging service...")

    finally:
        await service.disconnect()
        logger.info("Event logging service stopped")


if __name__ == "__main__":
    asyncio.run(main())
