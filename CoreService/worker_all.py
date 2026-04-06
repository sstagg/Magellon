"""
Temporal Worker - All-in-One

Development worker that handles all activities.
Use this for local development and testing.

For production, use specialized workers (worker_motioncor.py, worker_ctf.py, etc.)
that run on different computers with appropriate hardware.

Usage:
    python worker_all.py
"""

import asyncio
import logging
from temporalio.client import Client
from temporalio.worker import Worker

from workflows.image_processing_workflow import ImageProcessingWorkflow
from activities.image_processing_activities import (
    process_motioncor,
    process_ctf,
    generate_thumbnail,
    publish_event
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def main():
    """Main worker function"""

    # Temporal server configuration
    temporal_url = "localhost:7233"
    task_queue = "magellon-tasks"

    logger.info("=" * 60)
    logger.info("Magellon Temporal Worker (All-in-One)")
    logger.info("=" * 60)
    logger.info(f"Temporal Server: {temporal_url}")
    logger.info(f"Task Queue: {task_queue}")
    logger.info("=" * 60)

    # Connect to Temporal server
    try:
        client = await Client.connect(temporal_url)
        logger.info(f"✓ Connected to Temporal server at {temporal_url}")
    except Exception as e:
        logger.error(f"✗ Failed to connect to Temporal server: {e}")
        logger.error("Make sure Temporal server is running:")
        logger.error("  docker run -d --name temporal -p 7233:7233 -p 8233:8233 temporalio/auto-setup:latest")
        return

    # Create worker with ALL workflows and activities
    worker = Worker(
        client,
        task_queue=task_queue,
        workflows=[ImageProcessingWorkflow],
        activities=[
            process_motioncor,
            process_ctf,
            generate_thumbnail,
            publish_event
        ]
    )

    logger.info("=" * 60)
    logger.info("Worker Configuration:")
    logger.info("  Workflows:")
    logger.info("    - ImageProcessingWorkflow")
    logger.info("  Activities:")
    logger.info("    - process_motioncor (MotionCor - requires GPU)")
    logger.info("    - process_ctf (CTF estimation)")
    logger.info("    - generate_thumbnail (Thumbnail generation)")
    logger.info("    - publish_event (NATS event publishing)")
    logger.info("=" * 60)

    logger.info("Worker started successfully!")
    logger.info("Waiting for workflow and activity tasks...")
    logger.info("(Press Ctrl+C to stop)")

    # Run worker (this blocks until interrupted)
    try:
        await worker.run()
    except KeyboardInterrupt:
        logger.info("\nShutting down worker...")
    except Exception as e:
        logger.error(f"Worker error: {e}")


if __name__ == "__main__":
    asyncio.run(main())
