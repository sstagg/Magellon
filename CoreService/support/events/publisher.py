# publisher/main.py
from fastapi import FastAPI, Depends
from cloudevents.http import CloudEvent
import nats
import uuid
import datetime
import uvicorn
import json
import asyncio
from typing import Optional

app = FastAPI(title="CloudEvents Publisher")

# Setup publisher context for NATS JetStream
class PublisherContext:
    def __init__(self, broker_url: str):
        self.broker_url = broker_url
        self.nc = None
        self.js = None

    async def connect(self):
        if not self.nc:
            self.nc = await nats.connect(self.broker_url)
            self.js = self.nc.jetstream()

            # Create a stream if it doesn't exist
            try:
                await self.js.add_stream(
                    name="EVENTS",
                    subjects=["message-topic"],
                )
                print("Stream created successfully")
            except nats.errors.Error as e:
                if "stream name already in use" in str(e):
                    print("Stream already exists")
                else:
                    raise e

    async def close(self):
        if self.nc:
            await self.nc.close()
            self.nc = None
            self.js = None

async def get_publisher():
    context = PublisherContext(broker_url="nats://localhost:4222")
    await context.connect()
    return context

@app.on_event("startup")
async def startup():
    # Initialize publisher context
    context = await get_publisher()
    app.state.publisher_context = context

@app.on_event("shutdown")
async def shutdown():
    # Clean up publisher context
    if hasattr(app.state, "publisher_context"):
        await app.state.publisher_context.close()

@app.post("/publish")
async def publish_event(message: str):
    # Create CloudEvent using the current API pattern
    # The CloudEvent attributes dictionary
    attributes = {
        "id": str(uuid.uuid4()),
        "source": "publisher-app",
        "type": "com.example.message",
        "time": datetime.datetime.now().isoformat()
    }

    # The data payload
    data = {"message": message}

    # Create the CloudEvent with attributes and data
    event = CloudEvent(attributes, data)

    # Convert CloudEvent to JSON for NATS
    event_json = {
        "id": event["id"],
        "source": event["source"],
        "type": event["type"],
        "time": event["time"],
        "specversion": event["specversion"],
        "data": event.data
    }

    # Publish event to NATS JetStream
    ack = await app.state.publisher_context.js.publish(
        "message-topic",
        json.dumps(event_json).encode(),
        headers={
            "ce-specversion": event["specversion"],
            "ce-id": event["id"],
            "ce-source": event["source"],
            "ce-type": event["type"],
            "content-type": "application/json"
        }
    )

    return {
        "status": "Event published",
        "message": message,
        "event_id": event["id"],
        "stream": ack.stream,
        "sequence": ack.seq
    }

@app.get("/health")
async def health_check():
    return {"status": "healthy"}

# if __name__ == "__main__":
#     uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)