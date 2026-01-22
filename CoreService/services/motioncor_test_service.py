"""
Service for managing Motioncor test tasks and WebSocket connections.
Handles task creation, queue management, and real-time result delivery.
"""

import asyncio
import json
import logging
import uuid
from typing import Dict, List, Optional
from uuid import UUID

from core.rabbitmq_client import RabbitmqClient
from config import app_settings
from models.plugins_models import TaskDto, CryoEmMotionCorTaskData, MOTIONCOR_TASK, PENDING, COMPLETED, FAILED

logger = logging.getLogger(__name__)

# Store active WebSocket connections by task_id
active_connections: Dict[str, List['WebSocketConnection']] = {}


class WebSocketConnection:
    """Manages a single WebSocket connection for a motioncor test task."""
    
    def __init__(self, websocket, task_id: str):
        self.websocket = websocket
        self.task_id = task_id
        self.is_connected = False
    
    async def accept(self):
        await self.websocket.accept()
        self.is_connected = True
    
    async def send_json(self, data: dict):
        if self.is_connected:
            try:
                await self.websocket.send_json(data)
            except Exception as e:
                logger.error(f"Error sending WebSocket message for task {self.task_id}: {e}")
    
    async def send_update(self, status: str, progress: int = 0, message: str = ""):
        """Send a status update to the connected client."""
        await self.send_json({
            "type": "status_update",
            "task_id": self.task_id,
            "status": status,
            "progress": progress,
            "message": message,
            "timestamp": str(uuid.uuid4())
        })
    
    async def send_result(self, result: dict):
        """Send the final result to the connected client."""
        await self.send_json({
            "type": "result",
            "task_id": self.task_id,
            "status": "completed",
            "data": result
        })
    
    async def send_error(self, error: str):
        """Send an error message to the connected client."""
        await self.send_json({
            "type": "error",
            "task_id": self.task_id,
            "status": "failed",
            "error": error
        })


class MotioncorTestTaskManager:
    """Manages motioncor test tasks and their execution."""
    
    @staticmethod
    def create_test_task(
        task_id: UUID,
        image_path: str,
        gain_path: str,
        defects_path: Optional[str],
        session_name: str,
        task_params: dict,
        motioncor_settings: dict
    ) -> TaskDto:
        """
        Create a motioncor test task and prepare it for queueing.
        
        Args:
            task_id: Unique task identifier
            image_path: Path to the image file
            gain_path: Path to the gain reference file
            defects_path: Optional path to defects file
            session_name: Name of the session
            task_params: Additional task parameters
            motioncor_settings: Motioncor-specific settings
        
        Returns:
            TaskDto: The created task object ready for queueing
        """
        try:
            task_data = {
                "image_path": image_path,
                "gain_path": gain_path,
                "defects_path": defects_path,
                "session_name": session_name,
                "task_params": task_params,
                "motioncor_settings": motioncor_settings,
                "is_test": True  # Mark as test task
            }
            
            task = TaskDto(
                id=task_id,
                job_id=uuid.uuid4(),
                worker_instance_id=uuid.uuid4(),
                created_date=__import__('datetime').datetime.now(),
                status=PENDING,
                type=MOTIONCOR_TASK,
                data=task_data,
                sesson_name=session_name
            )
            
            logger.info(f"Created motioncor test task: {task_id}")
            return task
        
        except Exception as e:
            logger.error(f"Error creating motioncor test task: {e}")
            raise
    
    @staticmethod
    def publish_task_to_queue(task: TaskDto) -> bool:
        """
        Publish a task to the motioncor test input queue.
        
        Args:
            task: The task to publish
        
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            settings = app_settings.rabbitmq_settings
            rabbitmq_client = RabbitmqClient(settings)
            rabbitmq_client.connect()
            
            queue_name = settings.MOTIONCOR_TEST_QUEUE_NAME
            message = task.model_dump_json()
            
            rabbitmq_client.publish_message(message, queue_name)
            
            logger.info(f"Published motioncor test task {task.id} to queue {queue_name}")
            return True
        
        except Exception as e:
            logger.error(f"Error publishing task to queue: {e}")
            return False
        finally:
            try:
                rabbitmq_client.close_connection()
            except:
                pass


async def register_websocket_connection(task_id: str, websocket):
    """Register a WebSocket connection for a task (WebSocket must already be accepted)."""
    if task_id not in active_connections:
        active_connections[task_id] = []
    
    connection = WebSocketConnection(websocket, task_id)
    # NOTE: WebSocket should already be accepted by the caller before calling this function
    # DO NOT call await connection.accept() again - it will cause ASGI protocol error
    active_connections[task_id].append(connection)
    
    logger.info(f"WebSocket connected for task {task_id}, total connections: {len(active_connections[task_id])}")
    return connection


async def unregister_websocket_connection(task_id: str, connection: WebSocketConnection):
    """Unregister a WebSocket connection."""
    if task_id in active_connections:
        try:
            active_connections[task_id].remove(connection)
            logger.info(f"WebSocket disconnected for task {task_id}")
            
            # Clean up empty task connection lists
            if not active_connections[task_id]:
                del active_connections[task_id]
        except ValueError:
            pass


async def broadcast_to_task_connections(task_id: str, message: dict):
    """Broadcast a message to all WebSocket connections for a task."""
    logger.debug(f"broadcast_to_task_connections called for task_id: {task_id}")
    logger.debug(f"Active connections keys: {list(active_connections.keys())}")
    
    if task_id not in active_connections:
        logger.warning(f"No active connections found for task_id: {task_id}")
        return
    
    num_connections = len(active_connections[task_id])
    logger.info(f"Broadcasting to {num_connections} connection(s) for task {task_id}")
    
    disconnected = []
    for i, connection in enumerate(active_connections[task_id]):
        try:
            logger.debug(f"Sending message to connection {i+1}/{num_connections}")
            # Send the message directly using send_json method
            await connection.send_json(message)
            logger.debug(f"Successfully sent to connection {i+1}/{num_connections}")
        except Exception as e:
            logger.error(f"Error broadcasting to connection for task {task_id}: {type(e).__name__}: {e}")
            logger.error(f"Message keys: {list(message.keys()) if isinstance(message, dict) else 'not a dict'}")
            disconnected.append(connection)
    
    logger.info(f"Broadcast complete. {len(disconnected)} disconnected connection(s)")
    
    # Remove disconnected connections
    for connection in disconnected:
        try:
            active_connections[task_id].remove(connection)
        except ValueError:
            pass


async def send_status_update(task_id: str, status: str, progress: int = 0, message: str = ""):
    """Send a status update to all connections for a task."""
    update_message = {
        "type": "status_update",
        "task_id": task_id,
        "status": status,
        "progress": progress,
        "message": message,
        "timestamp": str(uuid.uuid4())
    }
    await broadcast_to_task_connections(task_id, update_message)


async def send_result(task_id: str, result: dict):
    """Send final result to all connections for a task."""
    result_message = {
        "type": "result",
        "task_id": task_id,
        "status": "completed",
        "data": result,
        "timestamp": str(uuid.uuid4())
    }
    await broadcast_to_task_connections(task_id, result_message)


async def send_error(task_id: str, error: str):
    """Send error message to all connections for a task."""
    error_message = {
        "type": "error",
        "task_id": task_id,
        "status": "failed",
        "error": error,
        "timestamp": str(uuid.uuid4())
    }
    await broadcast_to_task_connections(task_id, error_message)
