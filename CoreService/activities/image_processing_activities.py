"""
Image Processing Activities

Temporal activities for distributed image processing tasks.
These activities are executed by workers and can be distributed across different computers.

Activities:
- process_motioncor: Motion correction (requires GPU)
- process_ctf: CTF estimation
- generate_thumbnail: Thumbnail generation
- publish_event: Publish events to NATS
"""

import time
import subprocess
import asyncio
from datetime import datetime
from typing import Dict, Any
from temporalio import activity
from services.event_publisher import get_event_publisher
import logging

logger = logging.getLogger(__name__)


@activity.defn
async def publish_event(subject: str, data: Dict[str, Any]) -> None:
    """
    Publish event to NATS message broker

    Args:
        subject: NATS subject (e.g., 'job.started', 'step.progress')
        data: Event data dictionary
    """
    try:
        event_publisher = await get_event_publisher()

        # Use the centralized event publisher
        await event_publisher._publish(subject, data)

        activity.logger.info(f"Published event to '{subject}': {data}")

    except Exception as e:
        activity.logger.error(f"Failed to publish event: {e}")
        # Don't fail the workflow if event publishing fails
        # Just log the error


@activity.defn
async def process_motioncor(job_id: str, image_id: str, input_path: str) -> Dict[str, Any]:
    """
    Motion correction activity (runs on GPU-enabled worker)

    This activity:
    1. Runs MotionCor2/3 for motion correction
    2. Reports progress via heartbeats
    3. Publishes progress events to NATS
    4. Returns output path and quality metrics

    Args:
        job_id: Job identifier
        image_id: Image identifier
        input_path: Path to input movie file

    Returns:
        Dictionary with:
        - output_path: Path to motion-corrected image
        - quality_score: Quality metric
        - metadata: Additional metadata
    """
    activity.logger.info(f"[Job {job_id}] Starting MotionCor for image {image_id}")

    event_publisher = await get_event_publisher()
    start_time = time.time()

    try:
        # Publish step started event
        await event_publisher.publish_step_started(
            job_id=job_id,
            step_name="MotionCor",
            step_index=0,
            total_steps=3
        )

        # Output path
        output_path = input_path.replace(".tiff", "_motioncor.mrc").replace(".tif", "_motioncor.mrc")

        # Simulate or execute MotionCor processing
        # In production, this would call your actual MotionCor service

        # Example: subprocess call to MotionCor2
        # subprocess.run([
        #     "MotionCor2",
        #     "-InTiff", input_path,
        #     "-OutMrc", output_path,
        #     "-Gpu", "0",
        #     "-Patch", "5", "5",
        #     "-Iter", "10"
        # ], check=True)

        # For now, simulate processing with progress updates
        for progress in [0, 25, 50, 75, 100]:
            # Send heartbeat to Temporal (prevents timeout)
            activity.heartbeat(progress)

            # Publish progress event to NATS
            await event_publisher.publish_step_progress(
                job_id=job_id,
                step_name="MotionCor",
                progress=progress,
                message=f"Motion correction {progress}% complete"
            )

            # Simulate processing time
            await asyncio.sleep(2)

        # Calculate duration
        duration = time.time() - start_time

        # Result
        result = {
            "output_path": output_path,
            "quality_score": 0.85,
            "metadata": {
                "drift_x": 2.3,
                "drift_y": 1.8,
                "frames_processed": 40
            }
        }

        # Publish step completed event
        await event_publisher.publish_step_completed(
            job_id=job_id,
            step_name="MotionCor",
            result=result,
            duration_seconds=duration
        )

        activity.logger.info(f"[Job {job_id}] MotionCor completed in {duration:.2f}s")

        return result

    except Exception as e:
        # Publish step failed event
        await event_publisher.publish_step_failed(
            job_id=job_id,
            step_name="MotionCor",
            error=str(e)
        )

        activity.logger.error(f"[Job {job_id}] MotionCor failed: {e}")
        raise


@activity.defn
async def process_ctf(job_id: str, image_id: str, input_path: str) -> Dict[str, Any]:
    """
    CTF estimation activity (can run on CPU or GPU worker)

    This activity:
    1. Runs CTFFind4 for CTF estimation
    2. Reports progress via heartbeats
    3. Publishes progress events to NATS
    4. Returns CTF parameters

    Args:
        job_id: Job identifier
        image_id: Image identifier
        input_path: Path to motion-corrected image

    Returns:
        Dictionary with:
        - defocus: Defocus value in microns
        - astigmatism: Astigmatism value
        - resolution: Estimated resolution
        - confidence: Confidence score
    """
    activity.logger.info(f"[Job {job_id}] Starting CTF estimation for image {image_id}")

    event_publisher = await get_event_publisher()
    start_time = time.time()

    try:
        # Publish step started event
        await event_publisher.publish_step_started(
            job_id=job_id,
            step_name="CTF",
            step_index=1,
            total_steps=3
        )

        # Example: subprocess call to CTFFind4
        # subprocess.run([
        #     "ctffind",
        #     input_path,
        #     # ... other parameters
        # ], check=True)

        # Simulate processing with progress updates
        for progress in [0, 33, 66, 100]:
            # Send heartbeat
            activity.heartbeat(progress)

            # Publish progress event
            await event_publisher.publish_step_progress(
                job_id=job_id,
                step_name="CTF",
                progress=progress,
                message=f"CTF estimation {progress}% complete"
            )

            await asyncio.sleep(1.5)

        duration = time.time() - start_time

        # Result
        result = {
            "defocus": 2.5,
            "astigmatism": 0.15,
            "resolution": 3.2,
            "confidence": 0.92,
            "metadata": {
                "phase_shift": 0.0,
                "cross_correlation": 0.88
            }
        }

        # Publish step completed event
        await event_publisher.publish_step_completed(
            job_id=job_id,
            step_name="CTF",
            result=result,
            duration_seconds=duration
        )

        activity.logger.info(f"[Job {job_id}] CTF estimation completed in {duration:.2f}s")

        return result

    except Exception as e:
        await event_publisher.publish_step_failed(
            job_id=job_id,
            step_name="CTF",
            error=str(e)
        )

        activity.logger.error(f"[Job {job_id}] CTF estimation failed: {e}")
        raise


@activity.defn
async def generate_thumbnail(job_id: str, image_id: str, input_path: str) -> Dict[str, Any]:
    """
    Thumbnail generation activity (lightweight, can run anywhere)

    This activity:
    1. Generates thumbnail image
    2. Reports progress via heartbeats
    3. Publishes progress events to NATS
    4. Returns thumbnail path

    Args:
        job_id: Job identifier
        image_id: Image identifier
        input_path: Path to motion-corrected image

    Returns:
        Dictionary with:
        - thumbnail_path: Path to generated thumbnail
        - size: Thumbnail dimensions
    """
    activity.logger.info(f"[Job {job_id}] Generating thumbnail for image {image_id}")

    event_publisher = await get_event_publisher()
    start_time = time.time()

    try:
        # Publish step started event
        await event_publisher.publish_step_started(
            job_id=job_id,
            step_name="Thumbnail",
            step_index=2,
            total_steps=3
        )

        # Output path
        thumbnail_path = input_path.replace(".mrc", "_thumb.png")

        # Example: Use mrcfile and PIL to generate thumbnail
        # import mrcfile
        # from PIL import Image
        # with mrcfile.open(input_path) as mrc:
        #     data = mrc.data
        #     # ... process and save thumbnail

        # Simulate processing
        for progress in [0, 50, 100]:
            activity.heartbeat(progress)

            await event_publisher.publish_step_progress(
                job_id=job_id,
                step_name="Thumbnail",
                progress=progress,
                message=f"Thumbnail generation {progress}% complete"
            )

            await asyncio.sleep(0.5)

        duration = time.time() - start_time

        # Result
        result = {
            "thumbnail_path": thumbnail_path,
            "size": "256x256",
            "format": "PNG"
        }

        # Publish step completed event
        await event_publisher.publish_step_completed(
            job_id=job_id,
            step_name="Thumbnail",
            result=result,
            duration_seconds=duration
        )

        activity.logger.info(f"[Job {job_id}] Thumbnail generation completed in {duration:.2f}s")

        return result

    except Exception as e:
        await event_publisher.publish_step_failed(
            job_id=job_id,
            step_name="Thumbnail",
            error=str(e)
        )

        activity.logger.error(f"[Job {job_id}] Thumbnail generation failed: {e}")
        raise
