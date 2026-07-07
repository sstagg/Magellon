"""Task-category → RMQ queue-name mapping.

Split out of ``core.helper`` (2026-07-06); import from here in new code,
``core.helper`` re-exports for existing call sites.
"""
from config import app_settings
from magellon_sdk.models import TaskCategory


def get_queue_name_by_task_type(task_type: TaskCategory, is_result: bool = False) -> str:
    """
    Get the appropriate queue name based on task type and whether it's for results

    Args:
        task_type (str): Type of the task (e.g., MOTIONCOR_TASK, CTF_TASK)
        is_result (bool): If True, returns result queue name, else task queue name

    Returns:
        str: Queue name from app settings
    """
    queue_mapping = {
        5: {  # MOTIONCOR_TASK.code
            'task': app_settings.rabbitmq_settings.MOTIONCOR_QUEUE_NAME,
            'result': app_settings.rabbitmq_settings.MOTIONCOR_OUT_QUEUE_NAME
        },
        2: {  # CTF_TASK.code
            'task': app_settings.rabbitmq_settings.CTF_QUEUE_NAME,
            'result': app_settings.rabbitmq_settings.CTF_OUT_QUEUE_NAME
        },
        1: {  # FFT_TASK.code
            'task': app_settings.rabbitmq_settings.FFT_QUEUE_NAME,
            'result': app_settings.rabbitmq_settings.FFT_OUT_QUEUE_NAME
        },
        6: {  # SQUARE_DETECTION.code
            'task': app_settings.rabbitmq_settings.SQUARE_DETECTION_QUEUE_NAME,
            'result': app_settings.rabbitmq_settings.SQUARE_DETECTION_OUT_QUEUE_NAME
        },
        7: {  # HOLE_DETECTION.code
            'task': app_settings.rabbitmq_settings.HOLE_DETECTION_QUEUE_NAME,
            'result': app_settings.rabbitmq_settings.HOLE_DETECTION_OUT_QUEUE_NAME
        },
        8: {  # TOPAZ_PARTICLE_PICKING.code
            'task': app_settings.rabbitmq_settings.TOPAZ_PICK_QUEUE_NAME,
            'result': app_settings.rabbitmq_settings.TOPAZ_PICK_OUT_QUEUE_NAME
        },
        3: {  # PARTICLE_PICKING.code
            'task': getattr(app_settings.rabbitmq_settings, 'PARTICLE_PICKING_QUEUE_NAME', 'particle_picking_tasks_queue'),
            'result': getattr(app_settings.rabbitmq_settings, 'PARTICLE_PICKING_OUT_QUEUE_NAME', 'particle_picking_out_tasks_queue'),
        },
        9: {  # MICROGRAPH_DENOISING.code
            'task': app_settings.rabbitmq_settings.MICROGRAPH_DENOISE_QUEUE_NAME,
            'result': app_settings.rabbitmq_settings.MICROGRAPH_DENOISE_OUT_QUEUE_NAME
        },
    }

    if task_type.code not in queue_mapping:
        return None

    return queue_mapping[task_type.code]['result' if is_result else 'task']
