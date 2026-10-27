"""
Result processor for single-file test tasks (Run Processing Jobs page).

Listens to the MotionCor and CTF test output queues and broadcasts each
result to the WebSocket clients waiting on that task. Nothing is stored in
the database: the outputs stay in the task's scratch folder under /jobs.
"""
import asyncio
import json
import logging
import threading
from datetime import datetime

from config import app_settings
from magellon_sdk.bus.binders.rmq._client import RabbitmqClient
from services.motioncor_test_service import broadcast_to_task_connections

logger = logging.getLogger(__name__)

# The web server's event loop; the WebSockets belong to it, so results are
# sent from there (set by result_consumer_engine at startup).
_web_loop = None


def _broadcast(task_id, message) -> None:
    coro = broadcast_to_task_connections(task_id, message)
    if _web_loop is not None and _web_loop.is_running():
        asyncio.run_coroutine_threadsafe(coro, _web_loop).result(timeout=30)
    else:
        asyncio.run(coro)


def process_result_message(ch, method, properties, body):
    """Broadcast one test result to the task's WebSocket clients, then ack."""
    try:
        result_dict = json.loads(body.decode("utf-8"))
        # TaskResultMessage carries task_id; fall back to id.
        task_id = str(result_dict.get("task_id") or result_dict.get("id"))
        output_files = result_dict.get("output_files", [])
        logger.info("Test result for task %s: %d output file(s)", task_id, len(output_files))
        _broadcast(task_id, {
            "type": "result",
            "task_id": task_id,
            "status": "completed" if (result_dict.get("code") or 200) < 400 else "failed",
            "data": result_dict,
            "timestamp": datetime.now().isoformat(),
        })
        ch.basic_ack(delivery_tag=method.delivery_tag)
    except json.JSONDecodeError as e:
        logger.error(f"Error decoding JSON result: {e}")
        ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False)
    except Exception as e:
        logger.error(f"Error processing test result message: {e}")
        ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False)


def _consume(queue_name: str) -> None:
    rabbitmq_client = RabbitmqClient(app_settings.rabbitmq_settings)
    try:
        rabbitmq_client.connect()
        rabbitmq_client.declare_queue(queue_name)
        rabbitmq_client.consume(queue_name, process_result_message)
        logger.info(f"Test result processor consuming {queue_name}")
        rabbitmq_client.start_consuming()
    except Exception as e:
        logger.error(f"Test result processor for {queue_name} stopped: {e}")
    finally:
        rabbitmq_client.close_connection()


def result_consumer_engine(web_loop=None):
    """Consume the MotionCor and CTF test output queues (one thread each)."""
    global _web_loop
    _web_loop = web_loop
    settings = app_settings.rabbitmq_settings
    queues = [getattr(settings, "MOTIONCOR_TEST_OUT_QUEUE_NAME", None) or "motioncor_test_outqueue",
              getattr(settings, "CTF_TEST_OUT_QUEUE_NAME", None) or "ctf_test_outqueue"]
    threads = [threading.Thread(target=_consume, args=(q,), name=f"test-results-{q}", daemon=True)
               for q in queues]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
