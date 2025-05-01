# consumer/main.py
from fastapi import FastAPI
from cloudevents.http import CloudEvent
import nats
import asyncio
import uvicorn
import json
from typing import List, Dict, Any, Optional

app = FastAPI(title="CloudEvents Consumer")

# Message store to keep track of received messages
received_messages = []

# Setup consumer context for NATS JetStream
class ConsumerContext:
    def __init__(self, broker_url: str, stream_name: str, consumer_name: str):
        self.broker_url = broker_url
        self.stream_name = stream_name
        self.consumer_name = consumer_name
        self.nc = None
        self.js = None
        self.sub = None
        self.running = False

    async def connect(self):
        if not self.nc:
            self.nc = await nats.connect(self.broker_url)
            self.js = self.nc.jetstream()

            # Make sure the stream exists before creating a consumer
            try:
                stream_info = await self.js.stream_info(self.stream_name)
                print(f"Connected to stream: {self.stream_name}")
            except nats.errors.Error:
                print(f"Stream '{self.stream_name}' not found - waiting for publisher to create it")
                return False

            # Create a consumer if it doesn't exist
            try:
                # Create a durable consumer for the stream
                await self.js.add_consumer(
                    self.stream_name,
                    durable_name=self.consumer_name,
                    ack_policy="explicit",
                )
                print(f"Consumer '{self.consumer_name}' created or already exists")
                return True
            except nats.errors.Error as e:
                print(f"Error creating consumer: {e}")
                return False

    async def close(self):
        if self.sub:
            await self.sub.unsubscribe()
            self.sub = None

        if self.nc:
            await self.nc.close()
            self.nc = None
            self.js = None
            self.running = False

    async def subscribe(self, process_event_callback):
        if not self.js:
            return

        # Create a pull subscription
        self.sub = await self.js.pull_subscribe(
            "message-topic",
            durable=self.consumer_name
        )
        self.running = True

        # Start a background task to continuously receive messages
        asyncio.create_task(self._process_messages(process_event_callback))

    async def _process_messages(self, callback):
        while self.running:
            try:
                # Fetch messages in batches
                msgs = await self.sub.fetch(batch=10, timeout=1)

                for msg in msgs:
                    # Process the message
                    try:
                        json_data = json.loads(msg.data.decode())

                        # Create a CloudEvent from the received data
                        attributes = {
                            "id": json_data.get("id", ""),
                            "source": json_data.get("source", ""),
                            "type": json_data.get("type", ""),
                            "time": json_data.get("time", ""),
                            "specversion": json_data.get("specversion", "1.0")
                        }

                        data = json_data.get("data", {})

                        # Create CloudEvent with current API pattern
                        event = CloudEvent(attributes, data)

                        # Process the event
                        await callback(event)

                        # Acknowledge the message
                        await msg.ack()
                    except Exception as e:
                        print(f"Error processing message: {e}")
                        # Negative acknowledge to try again later
                        await msg.nak()
            except asyncio.TimeoutError:
                # No messages received, just continue
                await asyncio.sleep(0.1)
            except Exception as e:
                print(f"Error fetching messages: {e}")
                await asyncio.sleep(1)  # Wait before retrying

# Process an incoming event
async def process_event(event: CloudEvent):
    # Extract and process the CloudEvent
    event_data = event.data
    message = event_data.get("message", "No message content")
    print(f"Received message: {message}")

    # Store the message
    received_messages.append({
        "id": event["id"],
        "source": event["source"],
        "type": event["type"],
        "time": event["time"],
        "message": message
    })

@app.on_event("startup")
async def startup():
    # Initialize consumer context
    context = ConsumerContext(
        broker_url="nats://localhost:4222",
        stream_name="EVENTS",
        consumer_name="events-consumer"
    )

    async def connect_with_retry():
        connected = False
        retry_count = 0
        max_retries = 10

        while not connected and retry_count < max_retries:
            connected = await context.connect()
            if connected:
                await context.subscribe(process_event)
                print("Successfully connected and subscribed")
            else:
                retry_count += 1
                wait_time = min(retry_count, 5)
                print(f"Connection attempt {retry_count} failed. Retrying in {wait_time} seconds...")
                await asyncio.sleep(wait_time)

        if not connected:
            print("Failed to connect after multiple attempts")

    # Start connection process in background
    asyncio.create_task(connect_with_retry())

    # Store context in app state
    app.state.consumer_context = context

@app.on_event("shutdown")
async def shutdown():
    # Clean up consumer context
    if hasattr(app.state, "consumer_context"):
        await app.state.consumer_context.close()

@app.get("/messages")
async def get_messages():
    # Return all received messages
    return {"messages": received_messages}

@app.get("/health")
async def health_check():
    if hasattr(app.state, "consumer_context") and app.state.consumer_context.running:
        return {"status": "healthy", "message_count": len(received_messages)}
    return {"status": "initializing", "message_count": len(received_messages)}

# if __name__ == "__main__":
#     uvicorn.run("main:app", host="0.0.0.0", port=8001, reload=True)