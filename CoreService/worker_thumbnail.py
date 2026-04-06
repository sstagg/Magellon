"""
Temporal Worker - Thumbnail

Specialized worker for thumbnail generation.
Deploy this on web server or any computer (lightweight processing).

This worker ONLY handles:
- Thumbnail generation activities
- Workflows (for coordination)
- Event publishing

Usage:
    # On web server or any computer
    python worker_thumbnail.py
"""

import asyncio
import logging
import os
from temporalio.client import Client
from temporalio.worker import Worker

from workflows.image_processing_workflow import ImageProcessingWorkflow
from activities.image_processing_activities import (
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
    temporal_url = os.getenv("TEMPORAL_SERVER", "localhost:7233")
    task_queue = "magellon-tasks"

    # Worker identification
    worker_id = f"thumbnail-worker-{os.getpid()}"

    logger.info("=" * 60)
    logger.info("Magellon Temporal Worker - Thumbnail")
    logger.info("=" * 60)
    logger.info(f"Worker ID: {worker_id}")
    logger.info(f"Temporal Server: {temporal_url}")
    logger.info(f"Task Queue: {task_queue}")
    logger.info("=" * 60)

    # Connect to Temporal server
    try:
        client = await Client.connect(temporal_url)
        logger.info(f"✓ Connected to Temporal server at {temporal_url}")
    except Exception as e:
        logger.error(f"✗ Failed to connect to Temporal server: {e}")
        logger.error("Make sure Temporal server is running and accessible.")
        return

    # Create worker with thumbnail activity only
    worker = Worker(
        client,
        task_queue=task_queue,
        workflows=[ImageProcessingWorkflow],
        activities=[
            generate_thumbnail,  # ONLY Thumbnail activity
            publish_event        # Event publishing
        ]
    )

    logger.info("=" * 60)
    logger.info("Worker Configuration:")
    logger.info("  Computer Role: Thumbnail Generation")
    logger.info("  Workflows:")
    logger.info("    - ImageProcessingWorkflow (coordination)")
    logger.info("  Activities:")
    logger.info("    - generate_thumbnail (lightweight)")
    logger.info("    - publish_event (NATS event publishing)")
    logger.info("=" * 60)
    logger.info("Requirements:")
    logger.info("  - Python with mrcfile and PIL/Pillow")
    logger.info("  - No GPU required (CPU only)")
    logger.info("=" * 60)

    # Publish worker registration event
    try:
        from services.event_publisher import get_event_publisher
        event_publisher = await get_event_publisher()
        await event_publisher.publish_worker_registered(
            worker_id=worker_id,
            worker_type="thumbnail",
            capabilities=["thumbnail", "workflows"]
        )
        logger.info("✓ Registered worker with event system")
    except Exception as e:
        logger.warning(f"Could not register worker with event system: {e}")

    logger.info("Worker started successfully!")
    logger.info("Waiting for thumbnail generation tasks...")
    logger.info("(Press Ctrl+C to stop)")

    # Start heartbeat task
    async def send_heartbeats():
        """Send periodic heartbeats"""
        while True:
            try:
                await asyncio.sleep(30)
                event_publisher = await get_event_publisher()
                await event_publisher.publish_worker_heartbeat(
                    worker_id=worker_id,
                    status="running"
                )
            except Exception as e:
                logger.debug(f"Heartbeat error: {e}")

    heartbeat_task = asyncio.create_task(send_heartbeats())

    # Run worker
    try:
        await worker.run()
    except KeyboardInterrupt:
        logger.info("\nShutting down worker...")
        heartbeat_task.cancel()
    except Exception as e:
        logger.error(f"Worker error: {e}")
        heartbeat_task.cancel()


if __name__ == "__main__":
    asyncio.run(main())
