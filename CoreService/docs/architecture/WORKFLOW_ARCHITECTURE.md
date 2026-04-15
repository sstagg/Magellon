# Magellon Distributed Workflow Architecture

**Version:** 1.0
**Last Updated:** 2025-12-09
**Status:** Superseded 2026-04-14 — Temporal integration was reverted in `86fe9cc`. See `Documentation/IMPLEMENTATION_PLAN.md` for the current direction. File paths referenced below (`services/temporal_job_manager.py`, `controllers/workflow_job_controller.py`) no longer exist.

---

## Table of Contents

1. [Overview](#overview)
2. [Architecture Diagram](#architecture-diagram)
3. [Components](#components)
4. [Quick Start](#quick-start)
5. [Implementation Details](#implementation-details)
6. [API Reference](#api-reference)
7. [Deployment](#deployment)
8. [Troubleshooting](#troubleshooting)

---

## Overview

Magellon uses a distributed workflow architecture combining:

| Component | Purpose | Technology |
|-----------|---------|------------|
| **Job Manager** | Business logic, job lifecycle | Python/FastAPI |
| **Temporal** | Workflow orchestration, fault tolerance | Temporal.io |
| **NATS** | Real-time event broadcasting | NATS.io |
| **Workers** | Distributed processing (GPU/CPU) | Python |

### Key Benefits

- **Fault Tolerance** - Automatic retries, state persistence
- **Scalability** - Distribute work across multiple machines
- **Real-time Updates** - WebSocket progress notifications
- **Cancellation** - Stop running workflows anytime
- **Audit Trail** - Complete event logging

---

## Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                     React Application                            │
│  - Start workflows                                               │
│  - Real-time progress (via NATS WebSocket)                       │
│  - Cancel workflows                                              │
└─────────────────────────────────────────────────────────────────┘
                          ↓ HTTP/WebSocket
┌─────────────────────────────────────────────────────────────────┐
│                  FastAPI + Job Manager                           │
│  - Create jobs                                                   │
│  - Start Temporal workflows                                      │
│  - Cancel workflows                                              │
│  - Subscribe to NATS for progress updates                        │
└─────────────────────────────────────────────────────────────────┘
         ↓ gRPC                                    ↓ Subscribe
┌──────────────────┐                    ┌──────────────────────┐
│ Temporal Server  │                    │    NATS Server       │
│ (Orchestration)  │                    │  (Event Broker)      │
│                  │                    │                      │
│ - Coordinate     │                    │ Channels:            │
│ - Route tasks    │                    │ - job.progress       │
│ - Track state    │                    │ - job.completed      │
│ - Handle cancel  │                    │ - job.failed         │
└──────────────────┘                    │ - step.started       │
         ↓                              │ - step.completed     │
         ↓ Tasks                        └──────────────────────┘
         ↓                                     ↑ Publish events
    ┌────────────┐  ┌────────────┐  ┌─────────────┐
    │Computer A  │  │Computer B  │  │Computer C   │
    │(GPU)       │  │(CPU)       │  │(Web Server) │
    │            │  │            │  │             │
    │MotionCor   │  │   CTF      │  │ Thumbnail   │
    │Worker      │  │  Worker    │  │   Worker    │
    └────────────┘  └────────────┘  └─────────────┘
```

---

## Components

### Job Manager (`services/temporal_job_manager.py`)

High-level business logic layer that:
- Creates and tracks jobs in database
- Starts Temporal workflows
- Monitors workflow progress
- Handles cancellation requests

```python
from services.temporal_job_manager import get_temporal_job_manager

job_manager = await get_temporal_job_manager()

# Start a job
job_id = await job_manager.start_image_processing_job(
    session_id="session-123",
    image_ids=["img-1", "img-2"],
    pipeline_config=config
)

# Cancel a job
await job_manager.cancel_job(job_id)
```

### Event Publisher (`services/event_publisher.py`)

Centralized NATS event publishing:

```python
from services.event_publisher import get_event_publisher

publisher = await get_event_publisher()

# Publish progress
await publisher.publish_job_started(job_id, workflow_id)
await publisher.publish_step_progress(job_id, "MotionCor", 50)
await publisher.publish_job_completed(job_id)
```

### Workflows (`workflows/image_processing_workflow.py`)

Temporal workflow definitions:

```python
@workflow.defn
class ImageProcessingWorkflow:
    @workflow.run
    async def run(self, params: WorkflowParams) -> WorkflowResult:
        # Step 1: Motion Correction
        await workflow.execute_activity(
            motion_correction,
            params.image_ids,
            start_to_close_timeout=timedelta(hours=1)
        )

        # Step 2: CTF Estimation
        await workflow.execute_activity(
            ctf_estimation,
            params.image_ids,
            start_to_close_timeout=timedelta(minutes=30)
        )

        return WorkflowResult(status="completed")
```

### Activities (`activities/image_processing_activities.py`)

Individual processing tasks:

```python
@activity.defn
async def motion_correction(image_ids: List[str]) -> dict:
    """Run MotionCor2/3 on images"""
    publisher = await get_event_publisher()

    for i, image_id in enumerate(image_ids):
        # Process image
        result = run_motioncor(image_id)

        # Publish progress
        progress = int((i + 1) / len(image_ids) * 100)
        await publisher.publish_step_progress(
            activity.info().workflow_id,
            "MotionCor",
            progress
        )

    return {"processed": len(image_ids)}
```

### Workers

Specialized workers for different processing tasks:

| Worker | File | Purpose | Requirements |
|--------|------|---------|--------------|
| All-in-one | `worker_all.py` | All activities | Development |
| MotionCor | `worker_motioncor.py` | Motion correction | GPU |
| CTF | `worker_ctf.py` | CTF estimation | CPU |
| Thumbnail | `worker_thumbnail.py` | Image thumbnails | CPU |

---

## Quick Start

### 1. Install Dependencies

```bash
pip install temporalio nats-py
```

### 2. Start Infrastructure

```bash
# Start Temporal Server
docker run -d --name temporal \
  -p 7233:7233 \
  -p 8233:8233 \
  temporalio/auto-setup:latest

# Start NATS Server
docker run -d --name nats \
  -p 4222:4222 \
  -p 8222:8222 \
  nats:latest
```

### 3. Start Workers

```bash
# Terminal 1: Start worker
python worker_all.py

# Terminal 2: Start FastAPI
python -m uvicorn main:app --reload
```

### 4. Test Workflow

```bash
# Start a job via API
curl -X POST http://localhost:8000/api/jobs \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "session_id": "session-123",
    "image_ids": ["img-1", "img-2"],
    "pipeline": "standard"
  }'
```

---

## Implementation Details

### Event Channels (NATS)

| Channel | Event Data | When Published |
|---------|-----------|----------------|
| `job.started` | `{job_id, workflow_id, timestamp}` | Job begins |
| `job.progress` | `{job_id, step, progress, timestamp}` | Progress update |
| `job.completed` | `{job_id, result, timestamp}` | Job finishes |
| `job.failed` | `{job_id, error, timestamp}` | Job fails |
| `job.cancelled` | `{job_id, timestamp}` | Job cancelled |
| `step.started` | `{job_id, step_name, timestamp}` | Step begins |
| `step.completed` | `{job_id, step_name, result, timestamp}` | Step finishes |

### Workflow States

```
PENDING → RUNNING → COMPLETED
              ↓
           FAILED
              ↓
         CANCELLED
```

### Retry Policy

```python
# Default retry policy for activities
retry_policy = RetryPolicy(
    initial_interval=timedelta(seconds=1),
    maximum_interval=timedelta(minutes=10),
    backoff_coefficient=2.0,
    maximum_attempts=3
)
```

---

## API Reference

### Endpoints

#### Start Job
```
POST /api/jobs
Authorization: Bearer <token>

{
  "session_id": "uuid",
  "image_ids": ["uuid1", "uuid2"],
  "pipeline": "standard|custom",
  "config": {}
}

Response:
{
  "job_id": "uuid",
  "workflow_id": "workflow-uuid",
  "status": "started"
}
```

#### Get Job Status
```
GET /api/jobs/{job_id}
Authorization: Bearer <token>

Response:
{
  "job_id": "uuid",
  "status": "running",
  "progress": 45,
  "current_step": "MotionCor",
  "started_at": "2025-12-09T10:00:00Z"
}
```

#### Cancel Job
```
POST /api/jobs/{job_id}/cancel
Authorization: Bearer <token>

Response:
{
  "job_id": "uuid",
  "status": "cancelled"
}
```

#### WebSocket Progress
```
WS /ws/jobs/{job_id}/progress

Messages:
{"type": "progress", "step": "MotionCor", "progress": 50}
{"type": "completed", "result": {...}}
{"type": "failed", "error": "..."}
```

---

## Deployment

### Production Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    Load Balancer (Nginx)                         │
└─────────────────────────────────────────────────────────────────┘
                              ↓
        ┌─────────────────────┼─────────────────────┐
        ↓                     ↓                     ↓
┌───────────────┐    ┌───────────────┐    ┌───────────────┐
│ FastAPI Pod 1 │    │ FastAPI Pod 2 │    │ FastAPI Pod 3 │
└───────────────┘    └───────────────┘    └───────────────┘
        │                     │                     │
        └─────────────────────┼─────────────────────┘
                              ↓
┌───────────────────────────────────────────────────────────────┐
│                     Temporal Cluster                           │
│  ┌─────────┐  ┌─────────┐  ┌─────────┐  ┌───────────────┐   │
│  │Frontend │  │History  │  │Matching │  │ PostgreSQL    │   │
│  │Service  │  │Service  │  │Service  │  │ (Persistence) │   │
│  └─────────┘  └─────────┘  └─────────┘  └───────────────┘   │
└───────────────────────────────────────────────────────────────┘
                              ↓
┌───────────────────────────────────────────────────────────────┐
│                     NATS Cluster                               │
│  ┌─────────┐  ┌─────────┐  ┌─────────┐                       │
│  │ Node 1  │  │ Node 2  │  │ Node 3  │                       │
│  └─────────┘  └─────────┘  └─────────┘                       │
└───────────────────────────────────────────────────────────────┘
                              ↓
┌───────────────────────────────────────────────────────────────┐
│                    Worker Nodes                                │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐          │
│  │ GPU Node 1  │  │ GPU Node 2  │  │ CPU Node 1  │          │
│  │ MotionCor   │  │ MotionCor   │  │ CTF/Thumb   │          │
│  └─────────────┘  └─────────────┘  └─────────────┘          │
└───────────────────────────────────────────────────────────────┘
```

### Docker Compose

```yaml
version: '3.8'
services:
  temporal:
    image: temporalio/auto-setup:latest
    ports:
      - "7233:7233"
      - "8233:8233"
    environment:
      - DB=postgresql
      - DB_PORT=5432
      - POSTGRES_USER=temporal
      - POSTGRES_PWD=temporal
      - POSTGRES_SEEDS=postgres
    depends_on:
      - postgres

  nats:
    image: nats:latest
    ports:
      - "4222:4222"
      - "8222:8222"
    command: ["--cluster", "nats://0.0.0.0:6222"]

  postgres:
    image: postgres:13
    environment:
      - POSTGRES_USER=temporal
      - POSTGRES_PASSWORD=temporal

  worker-motioncor:
    build: .
    command: python worker_motioncor.py
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              count: 1
              capabilities: [gpu]

  worker-ctf:
    build: .
    command: python worker_ctf.py
    deploy:
      replicas: 3
```

---

## Troubleshooting

### Common Issues

#### Temporal Connection Failed
```
Error: Failed to connect to Temporal at localhost:7233
```
**Solution:** Ensure Temporal server is running:
```bash
docker ps | grep temporal
docker start temporal
```

#### NATS Connection Failed
```
Error: Could not connect to NATS at localhost:4222
```
**Solution:** Ensure NATS server is running:
```bash
docker ps | grep nats
docker start nats
```

#### Worker Not Processing Tasks
```
Symptom: Jobs stuck in "pending" state
```
**Solution:** Check worker is running and registered:
```bash
# Check worker logs
python worker_all.py

# Verify in Temporal UI: http://localhost:8233
```

#### Workflow Timeout
```
Error: Activity timed out after 1h
```
**Solution:** Increase timeout or check processing:
```python
await workflow.execute_activity(
    motion_correction,
    params,
    start_to_close_timeout=timedelta(hours=4)  # Increase
)
```

### Monitoring

- **Temporal UI:** http://localhost:8233
- **NATS Monitoring:** http://localhost:8222

---

## Related Documentation

- **Security:** `docs/security/SECURITY_ARCHITECTURE.md`
- **API Reference:** `/docs` (Swagger UI)
- **Database Schema:** `docs/magellon_schemal.sql`

---

**Document Version:** 1.0
**Consolidated from:** COMPLETE_ARCHITECTURE.md, QUICKSTART_TEMPORAL_NATS.md, DISTRIBUTED_WORKFLOW_SOLUTION.md, IMPLEMENTATION_SUMMARY.md, DISTRIBUTED_WORKERS_DEPLOYMENT.md, WORKFLOW_ORCHESTRATION_GUIDE.md, JOB_MANAGER_VS_WORKFLOW_ORCHESTRATION.md, PROGRESS_REPORTING_IMPLEMENTATION.md
**Last Updated:** 2025-12-09
