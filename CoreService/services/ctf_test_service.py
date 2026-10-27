"""
Single-file CTF test tasks (Run Processing Jobs page).

Mirrors services/motioncor_test_service.py: builds the task, publishes it to
the CTF test queue, and shares that module's WebSocket registry, so results
from either test queue reach the browser the same way.
"""
import logging
import uuid
from datetime import datetime
from uuid import UUID

from config import app_settings
from magellon_sdk.bus.binders.rmq._client import RabbitmqClient
from magellon_sdk.models import CTF_TASK, PENDING, TaskMessage
from services.motioncor_test_service import (  # noqa: F401  (re-exported for the WebSocket route)
    register_websocket_connection,
    unregister_websocket_connection,
)

logger = logging.getLogger(__name__)


class CTFTestTaskManager:
    """Creates CTF test tasks and puts them on the CTF test queue."""

    @staticmethod
    def create_test_task(task_id: UUID, image_path: str, session_name: str, ctf_params: dict) -> TaskMessage:
        return TaskMessage(
            id=task_id,
            job_id=uuid.uuid4(),
            worker_instance_id=uuid.uuid4(),
            created_date=datetime.now(),
            status=PENDING,
            type=CTF_TASK,
            # The plugin's test consumer reads image_path + ctf_params.
            data={"image_path": image_path, "ctf_params": ctf_params,
                  "session_name": session_name, "is_test": True},
            session_name=session_name,
        )

    @staticmethod
    def publish_task_to_queue(task: TaskMessage) -> bool:
        settings = app_settings.rabbitmq_settings
        client = RabbitmqClient(settings)
        try:
            client.connect()
            queue_name = getattr(settings, "CTF_TEST_QUEUE_NAME", None) or "ctf_test_inqueue"
            client.publish_message(task.model_dump_json(), queue_name)
            logger.info(f"Published CTF test task {task.id} to queue {queue_name}")
            return True
        except Exception as e:
            logger.error(f"Error publishing CTF test task: {e}")
            return False
        finally:
            try:
                client.close_connection()
            except Exception:
                pass
