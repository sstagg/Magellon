# Magellon messages and events — catalogue

This document enumerates every message shape that crosses a process or
network boundary in Magellon today, along with which transport carries
it and where the schema is defined. Keep this in sync with the code —
when a new queue, subject, or Socket.IO event is added, append it here.

## Transports at a glance

| Transport | Direction | Purpose |
|-----------|-----------|---------|
| **RabbitMQ** (pika BlockingConnection) | CoreService ↔ external plugins | Task dispatch + task-result pipeline. Per-plugin in/out queues. |
| **NATS JetStream** (`nats-py`) | CoreService ↔ any service | CloudEvents-wrapped inter-service events. One shared stream today (`EVENTS`) — this will fan out in Phase 4. |
| **Socket.IO** (python-socketio AsyncServer) | CoreService → browser | Real-time job progress + log feed for the React UI. |
| **HTTP/REST** (FastAPI) | Clients → CoreService, plugins → CoreService | Control plane (job create/cancel/list). Out of scope for this doc unless the payload is reused on another transport. |

---

## 1. RabbitMQ: task dispatch / task results

The live, production path. CoreService publishes `TaskDto` bodies onto
a per-plugin **task** queue; each plugin publishes `TaskResultDto`
bodies onto a per-plugin **result** queue that CoreService consumes
(`result_processor` plugin).

### 1.1 Queues

| Queue name (default) | Direction | Carries | Consumer |
|----------------------|-----------|---------|----------|
| `ctf_tasks_queue`         | CoreService → CTF plugin         | `TaskDto[CtfTaskData]`              | `magellon_ctf_plugin` |
| `ctf_out_tasks_queue`     | CTF plugin → CoreService          | `TaskResultDto`                      | `magellon_result_processor` |
| `motioncor_tasks_queue`   | CoreService → MotionCor plugin    | `TaskDto[CryoEmMotionCorTaskData]`   | `magellon_motioncor_plugin` |
| `motioncor_out_tasks_queue` | MotionCor plugin → CoreService  | `TaskResultDto`                      | `magellon_result_processor` |
| `motioncor_test_inqueue`  | (dev) CoreService → MotionCor      | `TaskDto`                            | test harness only |
| `motioncor_test_outqueue` | (dev) MotionCor → CoreService      | `TaskResultDto`                      | test harness only |

Queue names come from `RabbitMQSettings` (`models/pydantic_models_settings.py`)
and are mapped from task-type code in `core/helper.py::get_queue_name_by_task_type`.

> **Task-type → queue** mapping is hardcoded by integer code (2 = CTF,
> 5 = MotionCor). Adding a new plugin requires editing that function
> plus the settings schema. Phase 6's `TaskDispatcher` Protocol will
> remove this switch.

### 1.2 Envelope: `TaskDto`

Schema: `magellon_sdk.models.tasks.TaskDto` (Pydantic v2). Serialized as
JSON with `model_dump_json()`.

```python
class TaskBase(BaseModel):
    id: Optional[UUID] = None
    sesson_id: Optional[UUID] = None                # note: historical typo
    sesson_name: Optional[str] = None
    worker_instance_id: Optional[UUID] = None
    data: Dict[str, Any]                            # plugin-specific task data
    status: Optional[TaskStatus] = None             # code/name/description
    type: Optional[TaskCategory] = None             # code/name/description
    created_date: Optional[datetime] = default UTC now
    start_on: Optional[datetime] = None
    end_on: Optional[datetime] = None
    result: Optional[TaskOutcome] = None

class TaskDto(TaskBase):
    job_id: Optional[UUID] = default uuid4()
```

**Per-plugin `data` shapes** (also in `magellon_sdk.models.tasks`):

- `CtfTaskData` — `inputFile`, `outputFile`, `pixelSize`, `accelerationVoltage`, `sphericalAberration`, `amplitudeContrast`, `sizeOfAmplitudeSpectrum`, `minimumResolution`, `maximumResolution`, `minimumDefocus`, `maximumDefocus`, `defocusSearchStep`, `binning_x`
- `CryoEmMotionCorTaskData` — MotionCor2 CLI flags (`InMrc`/`InTiff`/`InEer`, `Gain`, `Dark`, `PatchesX/Y`, `Iter`, `Bft`, `FtBin`, `PixSize`, `kV`, …). Full list: see source.

**Task-type constants** (`TaskCategory(code, name, description)`):

| Code | Constant              | Name                |
|------|-----------------------|---------------------|
| 1    | `FFT_TASK`             | FFT                 |
| 2    | `CTF_TASK`             | CTF                 |
| 3    | `PARTICLE_PICKING`     | Particle Picking    |
| 4    | `TWO_D_CLASSIFICATION` | 2D Classification   |
| 5    | `MOTIONCOR`            | MotionCor           |

**Task-status constants** (`TaskStatus(code, name, description)`):

| Code | Constant       | Name          |
|------|----------------|---------------|
| 0    | `PENDING`      | pending       |
| 1    | `IN_PROGRESS`  | in_progress   |
| 2    | `COMPLETED`    | completed     |
| 3    | `FAILED`       | failed        |

### 1.3 Envelope: `TaskResultDto`

Schema: `magellon_sdk.models.tasks.TaskResultDto`. Serialized JSON.

```python
class TaskResultDto(BaseModel):
    worker_instance_id: Optional[UUID] = None
    job_id: Optional[UUID] = None
    task_id: Optional[UUID] = None
    image_id: Optional[UUID] = None
    image_path: Optional[str] = None
    session_id: Optional[UUID] = None
    session_name: Optional[str] = None
    code: Optional[int] = None                      # TaskStatus code
    message: Optional[str] = None
    description: Optional[str] = None
    status: Optional[TaskStatus] = None
    type: Optional[TaskCategory] = None
    created_date: Optional[datetime] = default UTC now
    started_on: Optional[datetime] = None
    ended_on: Optional[datetime] = None
    output_data: Dict[str, Any] = {}
    meta_data: Optional[List[ImageMetaData]] = None
    output_files: List[OutputFile] = []
```

`ImageMetaData` — `{key, value, is_persistent?, image_id?}`.
`OutputFile` — `{name?, path?, required}`.

### 1.4 Publisher/consumer code paths

| Direction | Publisher | Consumer |
|-----------|-----------|----------|
| Task dispatch | `core/helper.py::publish_message_to_queue` via `TaskDto.model_dump_json()` | plugin's `core/rabbitmq_consumer_engine.py` |
| Task result | plugin's `core/result_publisher.py` | `magellon_result_processor/services/task_output_processor.py` |

---

## 2. NATS JetStream: CloudEvents inter-service events

The future-facing event bus. Today it is only used by the `support/events`
publisher/subscriber demo pair; Phase 4 will route plugin-progress and
job-lifecycle events through it.

### 2.1 Stream configuration

| Stream   | Subjects (today) | Durability          | Defined in |
|----------|------------------|---------------------|------------|
| `EVENTS` | `message-topic`  | JetStream file (dev: in-memory container) | `CoreService/support/events/publisher.py` |

Phase 2 extraction (`magellon_sdk.transport.nats.NatsPublisher` /
`NatsConsumer`) removes the hardcoding — stream name, subjects, and
durable consumer names are constructor args.

### 2.2 Envelope: CloudEvents 1.0

Schema: `magellon_sdk.envelope.Envelope[DataT]` (Pydantic v2 generic).

Wire format: JSON body + NATS headers.

```json
{
  "specversion": "1.0",
  "id":          "<uuid>",
  "source":      "magellon/plugins/ctf",
  "type":        "magellon.step.completed",
  "subject":     "magellon.job.abc123.step.ctf",
  "time":        "2026-04-15T12:00:00+00:00",
  "datacontenttype": "application/json",
  "data":        { /* DataT-specific payload */ }
}
```

NATS headers set by `NatsPublisher.publish`:

| Header             | Source                          |
|--------------------|---------------------------------|
| `ce-specversion`   | `envelope.specversion` (`"1.0"`) |
| `ce-id`            | `envelope.id`                    |
| `ce-source`        | `envelope.source`                |
| `ce-type`          | `envelope.type`                  |
| `ce-subject`       | `envelope.subject` (if set)      |
| `content-type`     | `envelope.datacontenttype`       |

### 2.3 Event types (current + planned)

| `type`                              | `source`                    | `data` schema        | Phase | Notes |
|-------------------------------------|-----------------------------|----------------------|-------|-------|
| `com.example.message`               | `publisher-app`             | `{message: str}`     | live (demo) | Scaffolding in `support/events/publisher.py`; to be replaced by real event types below. |
| `magellon.job.started`              | `magellon/coreservice`      | `{job_id, session_id?}` | Phase 4 | Emitted by `JobManager.mark_running`. |
| `magellon.job.progress`             | `magellon/coreservice`      | `{job_id, percent, message?}` | Phase 4 | Re-broadcast by Socket.IO emitter. |
| `magellon.job.completed`            | `magellon/coreservice`      | `{job_id, outcome}`  | Phase 4 | Emitted by `JobManager.complete_job`. |
| `magellon.job.failed`               | `magellon/coreservice`      | `{job_id, error}`    | Phase 4 | Emitted by `JobManager.fail_job`. |
| `magellon.step.started`             | `magellon/plugins/<name>`   | `{job_id, task_id, step}` | Phase 4 | Plugin task-start notification. |
| `magellon.step.progress`            | `magellon/plugins/<name>`   | `{job_id, task_id, step, percent, message?}` | Phase 4 | Plugin in-task progress. |
| `magellon.step.completed`           | `magellon/plugins/<name>`   | `{job_id, task_id, step, output_files?}` | Phase 4 | Plugin task-done notification. |
| `magellon.step.failed`              | `magellon/plugins/<name>`   | `{job_id, task_id, step, error}` | Phase 4 | Plugin task failure. |

> **Subject convention** (Phase 4+): `magellon.job.<job_id>.step.<step>`
> — enables per-job NATS wildcards and per-step filtering without body
> inspection.

---

## 3. Socket.IO: browser job updates + logs

CoreService's in-process Socket.IO server (python-socketio `AsyncServer`,
mounted by `core/socketio_server.py`) broadcasts job progress + logs to
the React UI.

| Event name       | Payload shape                              | Emitter |
|------------------|--------------------------------------------|---------|
| `server_message` | `{message: str}`                           | connect handler |
| `pong`           | `{echo: any, from: "server"}`              | ping handler |
| `server_broadcast` | `{from_sid: str, message: str}`          | `/broadcast` REST endpoint |
| `log_entry`      | `{level, source, message, ts}`             | `emit_log()` — called from `JobReporter.log` and plugin-in-process code paths |
| `job_progress`   | `{job_id, percent, message, ts}`           | `JobReporter.progress` (in-process plugins) |
| `job_update`     | Full `JobDto`-like dict (status, progress, …) | `JobManager.*` via `emit_job_update()` |

**Rooms:** all events are either broadcast (no `room`) or addressed to
a specific `sid`. No per-job rooms yet — Phase 4 should introduce
`room=job:<job_id>` so the UI can subscribe to one job without decoding
every update.

**In-process vs. external plugins:** Today `JobReporter` (see
`plugins/progress.py`) writes directly to `JobManager` and forwards to
Socket.IO via `asyncio.run_coroutine_threadsafe`. External plugins
(dispatched via RabbitMQ) do **not** reach this emitter — their
progress is invisible to the UI until a final `TaskResultDto` lands.
Closing this gap is Phase 4.

---

## 4. Known gaps + pending changes

| Gap | Phase | Notes |
|-----|-------|-------|
| Hardcoded task-type → queue switch | 6 | `TaskDispatcher` Protocol in SDK; `RabbitmqTaskDispatcher` + `InProcessTaskDispatcher` impls. |
| External plugin progress invisible to UI | 4 | Route plugin progress through NATS → CoreService → Socket.IO. |
| `TaskOutputProcessor` never advances `ImageJobTask.status_id/stage` | 4 | Single writer path is `JobManager`; result processor currently bypasses it. |
| `support/events/publisher.py` + `subscriber.py` still importable as FastAPI apps | 2 | Keep as thin shims around `magellon_sdk.transport.nats` — migration in this phase. |
| No DLQ on task queues | 3 | `RabbitmqClient.publish_message` has no reject/retry policy. Still open. |
| ~~`asyncio.run()` inside pika blocking callback~~ | 3 (done) | Fixed in all 4 plugin consumer engines: one daemon-thread event loop per process, callbacks use `run_coroutine_threadsafe(...).result()`. |
| ~~`RabbitmqClient.connect()` swallowed `AMQPConnectionError`~~ | 3 (done) | Now raises so helpers report `False` instead of silent-dropping a message as success. |

---

## 5. Updating this document

When you add or change a message shape:

1. Update the schema in `magellon_sdk.models` (or wherever it lives).
2. Bump the relevant row in section 1 / 2 / 3 above.
3. If it is a new event `type`, append a row to §2.3 with `source`,
   `data` shape, and the phase it belongs to.
4. If it crosses a new transport, add it to the top-level table in §1.
