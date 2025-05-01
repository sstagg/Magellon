import json
import uuid
import asyncio
import logging
from typing import Dict, Any, Optional, List, Callable, Union
from datetime import datetime
import nats
from nats.js.client import JetStreamContext
from cloudevents.http import CloudEvent
import walnats
from walnats import CloudEventEnvelope

from event_types import EventType

logger = logging.getLogger(__name__)

# Default NATS configuration
NATS_CONFIG = {
    "servers": ["nats://localhost:4222"],
    "connection_name": "magellon-event-service",
    "reconnect_time_wait": 2,  # Wait 2 seconds between reconnection attempts
    "max_reconnect_attempts": -1,  # Unlimited reconnection attempts
    "error_cb": lambda conn, err: logger.error(f"NATS connection error: {err}")
}

class MagellonEventService:
    """
    Service for handling CloudEvents over NATS for Magellon using Walnats.

    This service provides:
    - Event publishing with CloudEvents format
    - Event subscription with callback handling
    - JetStream support for persistence
    - Both sync and async APIs
    """
    _instance = None

    def __new__(cls, *args, **kwargs):
        """Implement singleton pattern to ensure consistent connection"""
        if cls._instance is None:
            cls._instance = super(MagellonEventService, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self, config: Dict[str, Any] = None):
        """Initialize the event service"""
        # Skip initialization if already done
        if getattr(self, "_initialized", False):
            return

        self._config = config or NATS_CONFIG
        self._walnats = None
        self._nats_conn = None
        self._js = None
        self._connections_active = 0
        self._is_connected = False
        self._source = "org.magellon"
        self._initialized = True
        self._subscriptions = {}

        # Define streams
        self._streams = [
            {
                "name": "MAGELLON_JOBS",
                "subjects": ["job.*"],
                "description": "Job lifecycle events"
            },
            {
                "name": "MAGELLON_TASKS",
                "subjects": ["task.*"],
                "description": "Task lifecycle events"
            },
            {
                "name": "MAGELLON_DATABASE",
                "subjects": ["db.*"],
                "description": "Database operation events"
            },
            {
                "name": "MAGELLON_FILES",
                "subjects": ["file.*", "directory.*"],
                "description": "File and directory operation events"
            },
            {
                "name": "MAGELLON_PROCESSING",
                "subjects": ["processing.*"],
                "description": "Processing operation events"
            },
            {
                "name": "MAGELLON_IMPORT",
                "subjects": ["import.*"],
                "description": "Importer-specific events"
            },
            {
                "name": "MAGELLON_SYSTEM",
                "subjects": ["system.*"],
                "description": "System events"
            }
        ]

    async def connect_async(self) -> None:
        """Connect to NATS server asynchronously"""
        if self._is_connected:
            return

        try:
            # Initialize Walnats
            self._walnats = walnats.WalNats(self._config["servers"][0], client_name="magellon-event-service")
            await self._walnats.connect()

            # Store raw NATS connection and JetStream context
            self._nats_conn = self._walnats._nc
            self._js = self._nats_conn.jetstream()

            # Ensure required streams exist
            await self._ensure_streams_exist()

            self._is_connected = True
            logger.info("Connected to NATS server")
        except Exception as e:
            logger.error(f"Failed to connect to NATS: {str(e)}")
            raise

    def connect(self) -> None:
        """Connect to NATS server synchronously"""
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(self.connect_async())
        finally:
            loop.close()

    async def _ensure_streams_exist(self) -> None:
        """Ensure required JetStream streams exist"""
        for stream_config in self._streams:
            try:
                # Check if stream exists
                await self._js.stream_info(stream_config["name"])
                logger.debug(f"Stream {stream_config['name']} exists")
            except nats.errors.Error:
                # Create stream if it doesn't exist
                await self._js.add_stream(
                    name=stream_config["name"],
                    subjects=stream_config["subjects"],
                    description=stream_config.get("description", ""),
                    retention="limits",
                    max_age=60 * 60 * 24 * 7,  # 7 days default retention
                    storage="file",
                    num_replicas=1
                )
                logger.info(f"Created stream {stream_config['name']}")

    async def disconnect_async(self) -> None:
        """Disconnect from NATS server asynchronously"""
        if self._walnats and self._is_connected:
            await self._walnats.close()
            self._is_connected = False
            self._walnats = None
            self._nats_conn = None
            self._js = None
            logger.info("Disconnected from NATS server")

    def disconnect(self) -> None:
        """Disconnect from NATS server synchronously"""
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(self.disconnect_async())
        finally:
            loop.close()

    def create_cloud_event(
            self,
            event_type: Union[EventType, str],
            data: Dict[str, Any],
            subject_id: str = None,
            additional_attributes: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """
        Create a CloudEvent with standard attributes

        Args:
            event_type: The event type (from EventType enum or string)
            data: Event payload data
            subject_id: Optional identifier for source (e.g., job_id)
            additional_attributes: Optional additional CloudEvent attributes

        Returns:
            Dict representing a CloudEvent
        """
        event_id = str(uuid.uuid4())
        source = self._source

        if subject_id:
            source = f"{source}/{subject_id}"

        # Convert event_type to string if it's an Enum
        if isinstance(event_type, EventType):
            event_type = event_type.value

        # Create base attributes
        attributes = {
            "specversion": "1.0",
            "id": event_id,
            "source": source,
            "type": event_type,
            "time": datetime.utcnow().isoformat() + "Z",
            "datacontenttype": "application/json"
        }

        # Add additional attributes if provided
        if additional_attributes:
            attributes.update(additional_attributes)

        # Return CloudEvent as a dictionary (compatible with Walnats)
        return {
            "attributes": attributes,
            "data": data
        }

    async def publish_event_async(
            self,
            event_type: Union[EventType, str],
            data: Dict[str, Any],
            subject_id: str = None,
            additional_attributes: Dict[str, Any] = None
    ) -> str:
        """
        Publish a CloudEvent asynchronously

        Args:
            event_type: The event type (from EventType enum or string)
            data: Event payload data
            subject_id: Optional identifier for source (e.g., job_id)
            additional_attributes: Optional additional CloudEvent attributes

        Returns:
            event_id: The CloudEvent ID
        """
        if not self._is_connected:
            await self.connect_async()

        # Convert event_type to string if it's an Enum
        type_str = event_type.value if isinstance(event_type, EventType) else event_type

        # Create CloudEvent
        cloud_event = self.create_cloud_event(type_str, data, subject_id, additional_attributes)
        event_id = cloud_event["attributes"]["id"]

        # Use Walnats to publish
        try:
            # Create Walnats CloudEventEnvelope
            envelope = CloudEventEnvelope(
                attributes=cloud_event["attributes"],
                data=cloud_event["data"]
            )

            # Publish to NATS
            await self._walnats.publish(type_str, envelope)
            logger.debug(f"Published event {event_id} of type {type_str}")

            return event_id
        except Exception as e:
            logger.error(f"Error publishing event {type_str}: {str(e)}")
            raise

    def publish_event(
            self,
            event_type: Union[EventType, str],
            data: Dict[str, Any],
            subject_id: str = None,
            additional_attributes: Dict[str, Any] = None
    ) -> str:
        """
        Publish a CloudEvent synchronously

        Args:
            event_type: The event type (from EventType enum or string)
            data: Event payload data
            subject_id: Optional identifier for source (e.g., job_id)
            additional_attributes: Optional additional CloudEvent attributes

        Returns:
            event_id: The CloudEvent ID
        """
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            return loop.run_until_complete(
                self.publish_event_async(event_type, data, subject_id, additional_attributes)
            )
        finally:
            loop.close()

    # Convenience methods for specific event types
    def publish_job_event(self, event_type: EventType, job_id: str, job_data: Dict[str, Any]) -> str:
        """Publish a job-related event"""
        return self.publish_event(event_type, job_data, job_id)


    def publish_task_event(self, event_type: EventType, task_id: str, job_id: str, task_data: Dict[str, Any]) -> str:
        """Publish a task-related event"""
        # Include job_id in data for easier querying
        if "job_id" not in task_data:
            task_data["job_id"] = job_id

        return self.publish_event(
            event_type,
            task_data,
            f"{job_id}/task/{task_id}"
        )

    def publish_file_event(self, event_type: EventType, file_path: str, file_data: Dict[str, Any], job_id: str = None) -> str:
        """Publish a file-related event"""
        subject_id = job_id if job_id else "file"

        # Include file_path in data
        if "file_path" not in file_data:
            file_data["file_path"] = file_path

        return self.publish_event(event_type, file_data, subject_id)

    def publish_directory_event(self, event_type: EventType, dir_path: str, dir_data: Dict[str, Any], job_id: str = None) -> str:
        """Publish a directory-related event"""
        subject_id = job_id if job_id else "directory"

        # Include dir_path in data
        if "directory_path" not in dir_data:
            dir_data["directory_path"] = dir_path

        return self.publish_event(event_type, dir_data, subject_id)

    def publish_processing_event(self, event_type: EventType, processing_data: Dict[str, Any], job_id: str = None, task_id: str = None) -> str:
        """Publish a processing-related event"""
        subject_id = None
        if job_id and task_id:
            subject_id = f"{job_id}/task/{task_id}"
        elif job_id:
            subject_id = job_id

        return self.publish_event(event_type, processing_data, subject_id)

    def publish_import_event(self, event_type: EventType, import_data: Dict[str, Any], job_id: str) -> str:
        """Publish an import-related event"""
        return self.publish_event(event_type, import_data, job_id)

    def publish_error_event(self, message: str, error: Exception, context: Dict[str, Any] = None) -> str:
        """Publish a system error event"""
        data = {
            "message": message,
            "error": str(error),
            "error_type": error.__class__.__name__,
            "context": context or {}
        }
        return self.publish_event(EventType.SYSTEM_ERROR, data)

    async def subscribe_async(
            self,
            event_type: Union[EventType, str],
            callback: Callable,
            queue_group: str = None,
            durable: str = None
    ) -> str:
        """
        Subscribe to events asynchronously

        Args:
            event_type: Event type to subscribe to (supports wildcards)
            callback: Async callback function that takes a CloudEvent
            queue_group: Optional queue group for load balancing
            durable: Optional durable subscription name

        Returns:
            subscription_id: Unique subscription identifier
        """
        if not self._is_connected:
            await self.connect_async()

        # Convert event_type to string if it's an Enum
        subject = event_type.value if isinstance(event_type, EventType) else event_type

        # Create a unique subscription ID
        sub_id = str(uuid.uuid4())

        try:
            # Setup the callback to convert from Walnats format to our format
            async def wrapped_callback(msg, event_envelope):
                try:
                    # Create a standard dictionary representation
                    cloud_event = {
                        "attributes": event_envelope.attributes,
                        "data": event_envelope.data
                    }

                    # Call the user callback
                    await callback(cloud_event)

                    # Acknowledge the message if using JetStream
                    if hasattr(msg, 'ack'):
                        await msg.ack()
                except Exception as e:
                    logger.error(f"Error in event callback: {str(e)}")
                    # Don't acknowledge to allow redelivery

            # Choose subscription type based on parameters
            if durable:
                # JetStream durable subscription
                consumer_config = {
                    "durable_name": durable,
                    "ack_policy": "explicit",
                    "deliver_policy": "all"
                }

                # Determine which stream to use based on subject pattern
                stream_name = self._get_stream_for_subject(subject)

                # Create the subscription
                subscription = await self._walnats.subscribe_jetstream(
                    subject=subject,
                    stream=stream_name,
                    consumer_config=consumer_config,
                    queue=queue_group,
                    callback=wrapped_callback
                )

                logger.info(f"Created durable subscription '{durable}' for {subject}")
            else:
                # Regular NATS subscription
                subscription = await self._walnats.subscribe(
                    subject=subject,
                    queue=queue_group,
                    callback=wrapped_callback
                )

                logger.info(f"Subscribed to {subject}")

            # Store subscription for cleanup
            self._subscriptions[sub_id] = subscription

            return sub_id

        except Exception as e:
            logger.error(f"Error creating subscription to {subject}: {str(e)}")
            raise

    def _get_stream_for_subject(self, subject: str) -> str:
        """Find the appropriate stream for a given subject pattern"""
        for stream in self._streams:
            for stream_subject in stream["subjects"]:
                # Simple matching - could be enhanced with proper wildcard handling
                if subject.split('.')[0] == stream_subject.split('.')[0]:
                    return stream["name"]

        # Default to MAGELLON_SYSTEM if no match
        return "MAGELLON_SYSTEM"

    def subscribe(
            self,
            event_type: Union[EventType, str],
            callback: Callable,
            queue_group: str = None,
            durable: str = None
    ) -> str:
        """
        Subscribe to events synchronously

        Args:
            event_type: Event type to subscribe to (supports wildcards)
            callback: Callback function that takes a CloudEvent
            queue_group: Optional queue group for load balancing
            durable: Optional durable subscription name

        Returns:
            subscription_id: Unique subscription identifier
        """
        # For synchronous callbacks, wrap the callback to run in the event loop
        async def async_wrapper(event):
            loop = asyncio.get_event_loop()
            return await loop.run_in_executor(None, callback, event)

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            return loop.run_until_complete(
                self.subscribe_async(event_type, async_wrapper, queue_group, durable)
            )
        finally:
            loop.close()

    async def unsubscribe_async(self, subscription_id: str) -> bool:
        """
        Unsubscribe from events asynchronously

        Args:
            subscription_id: The subscription ID to unsubscribe

        Returns:
            success: True if unsubscribed successfully
        """
        if subscription_id not in self._subscriptions:
            return False

        subscription = self._subscriptions[subscription_id]

        try:
            # Unsubscribe
            await subscription.unsubscribe()
            del self._subscriptions[subscription_id]
            logger.info(f"Unsubscribed from subscription {subscription_id}")
            return True
        except Exception as e:
            logger.error(f"Error unsubscribing: {str(e)}")
            return False

    def unsubscribe(self, subscription_id: str) -> bool:
        """
        Unsubscribe from events synchronously

        Args:
            subscription_id: The subscription ID to unsubscribe

        Returns:
            success: True if unsubscribed successfully
        """
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            return loop.run_until_complete(self.unsubscribe_async(subscription_id))
        finally:
            loop.close()

    # Context manager support
    async def __aenter__(self):
        """Async context manager enter"""
        await self.connect_async()
        self._connections_active += 1
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit"""
        self._connections_active -= 1
        if self._connections_active <= 0:
            await self.disconnect_async()
            self._connections_active = 0

    def __enter__(self):
        """Sync context manager enter"""
        self.connect()
        self._connections_active += 1
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Sync context manager exit"""
        self._connections_active -= 1
        if self._connections_active <= 0:
            self.disconnect()
            self._connections_active = 0