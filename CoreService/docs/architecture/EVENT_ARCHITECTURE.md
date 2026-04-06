# Event Architecture & CloudEvents Evaluation

**Version:** 1.0
**Last Updated:** 2025-12-09
**Status:** Evaluation Complete

---

## Table of Contents

1. [Current Event System](#current-event-system)
2. [CloudEvents Evaluation](#cloudevents-evaluation)
3. [Event Replay & Sourcing](#event-replay--sourcing)
4. [Recommendation](#recommendation)

---

## Current Event System

Magellon uses NATS for event broadcasting with a simple JSON format:

### Event Format

```json
{
  "event_type": "job.progress",
  "job_id": "uuid",
  "data": {
    "step": "MotionCor",
    "progress": 50
  },
  "timestamp": "2025-12-09T10:00:00Z"
}
```

### Event Types

| Event | Channel | Purpose |
|-------|---------|---------|
| Job Started | `job.started` | Job begins processing |
| Job Progress | `job.progress` | Progress updates |
| Job Completed | `job.completed` | Job finished successfully |
| Job Failed | `job.failed` | Job encountered error |
| Job Cancelled | `job.cancelled` | Job was cancelled |
| Step Started | `step.started` | Processing step begins |
| Step Completed | `step.completed` | Processing step finished |

---

## CloudEvents Evaluation

### What is CloudEvents?

CloudEvents is a CNCF-graduated specification for describing event data in a vendor-neutral format.

### CloudEvents Format

```json
{
  "specversion": "1.0",
  "type": "com.magellon.job.progress",
  "source": "/jobs/uuid-123",
  "id": "event-uuid",
  "time": "2025-12-09T10:00:00Z",
  "datacontenttype": "application/json",
  "data": {
    "step": "MotionCor",
    "progress": 50
  }
}
```

### Assessment for Magellon

| Aspect | Rating | Notes |
|--------|--------|-------|
| Standards Compliance | 5/5 | CNCF graduated, industry-standard |
| Interoperability | 5/5 | Excellent for multi-system integration |
| Implementation Effort | 3/5 | Moderate refactoring required |
| Performance Impact | 4/5 | Minimal overhead |
| Future-Proofing | 5/5 | Excellent long-term maintainability |
| **Relevance to Use Case** | **3/5** | **Internal system, not multi-cloud** |

### Recommendation

**CONDITIONALLY RECOMMENDED**

CloudEvents is a good practice but offers **moderate value** for Magellon's current architecture because:

1. **Internal System** - Events are consumed internally, not by external systems
2. **Single Platform** - Not running multi-cloud or multi-platform
3. **Simple Needs** - Current JSON format meets all requirements

**When to Adopt CloudEvents:**
- Planning external integrations
- Multi-platform deployment
- Third-party event consumers

---

## Event Replay & Sourcing

### Event Sourcing Options Evaluated

| Framework | Type | Pros | Cons |
|-----------|------|------|------|
| **EventStoreDB** | Dedicated | Purpose-built, powerful | New infrastructure |
| **Kafka** | Stream | High throughput, retention | Complex setup |
| **NATS JetStream** | Stream | Already using NATS | Good fit |
| **Custom** | Database | Simple, no new deps | Manual implementation |

### Recommendation: NATS JetStream

Since Magellon already uses NATS for events, upgrading to JetStream provides:

- **Event Persistence** - Events stored durably
- **Replay Capability** - Replay from any point
- **No New Infrastructure** - Uses existing NATS

### JetStream Configuration

```python
# Enable JetStream for event persistence
import nats
from nats.js.api import StreamConfig

async def setup_jetstream():
    nc = await nats.connect("nats://localhost:4222")
    js = nc.jetstream()

    # Create stream for job events
    await js.add_stream(
        StreamConfig(
            name="JOBS",
            subjects=["job.*", "step.*"],
            retention="limits",
            max_age=86400 * 30,  # 30 days
            storage="file"
        )
    )
```

### Event Replay

```python
async def replay_events(job_id: str, from_time: datetime):
    """Replay events for a specific job"""
    js = nc.jetstream()

    # Subscribe with replay from time
    sub = await js.subscribe(
        f"job.{job_id}.*",
        deliver_policy="by_start_time",
        opt_start_time=from_time
    )

    async for msg in sub.messages:
        event = json.loads(msg.data)
        yield event
```

---

## Recommendation Summary

| Decision | Recommendation | Rationale |
|----------|----------------|-----------|
| Event Format | Keep current JSON | Simple, meets needs |
| CloudEvents | Defer adoption | Limited benefit for internal system |
| Event Persistence | Use NATS JetStream | No new infrastructure |
| Event Replay | Implement with JetStream | Built-in capability |

---

## Related Documentation

- **Workflow Architecture:** `docs/architecture/WORKFLOW_ARCHITECTURE.md`
- **Event Publisher:** `services/event_publisher.py`
- **Event Logging:** `services/event_logging_service.py`

---

**Consolidated from:** CLOUDEVENTS_EVALUATION.md, EVENT_DRIVEN_ARCHITECTURE_APPROACHES.md, EVENT_REPLAY_FRAMEWORKS.md
**Last Updated:** 2025-12-09
