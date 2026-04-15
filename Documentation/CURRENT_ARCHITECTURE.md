# Magellon — Current Architecture (as-is)

**Status:** Reference manual of the system as it exists on `main` (April 2026).
**Audience:** Architects, new plugin developers, reviewers of the target-state proposal.
**Companion:** `TARGET_ARCHITECTURE_AND_PLAN.md` (where we are going and how).

This document describes Magellon **as it actually behaves in the repo**, not as any
single diagram would suggest. Magellon is in mid-migration from a RabbitMQ-based
plugin fleet to an in-process plugin registry plus a Temporal workflow engine,
and *both stacks are live at the same time*. Calling that out explicitly is the
point of this document — the target-state document explains how they converge.

---

## 1. System context

Magellon is an extensible platform for cryo-EM data visualization, management,
and processing (Khoshbin et al., *IUCrJ* 12, 637–646, 2025; bioRxiv
10.1101/2025.06.09.658726). It provides:

- A **CoreService** (FastAPI) that owns the data model, authz, import pipelines,
  and job orchestration.
- A **React frontend** (`magellon-react-app`) that talks to CoreService over REST
  and Socket.IO.
- A fleet of **processing plugins** (CTF estimation, motion correction, particle
  picking, FFT, …). Some run *inside* CoreService; others run *outside* as
  containerised RabbitMQ consumers.
- An infrastructure layer in `Docker/docker-compose.yml`: MySQL, RabbitMQ, NATS
  (JetStream enabled), Dragonfly (Redis-compatible), Consul, Prometheus,
  Grafana.

The repo layout reflects this split:

```
Magellon/
├── CoreService/          # FastAPI, 27 routers, plugin registry, job managers
├── plugins/              # External plugins (RabbitMQ consumers)
│   ├── magellon_ctf_plugin/
│   ├── magellon_motioncor_plugin/
│   └── magellon_result_processor/
├── MagellonSdk/          # Scaffolded SDK — essentially empty today
├── magellon-react-app/   # Frontend
├── Docker/               # docker-compose deployment topology
├── Documentation/        # This file and the target doc
└── infrastructure/       # Ansible/TF (out of scope here)
```

---

## 2. Deployment topology

`Docker/docker-compose.yml` brings up the full stack. Key services and ports:

| Service        | Purpose                                    | Notes                                                       |
|----------------|--------------------------------------------|-------------------------------------------------------------|
| `mysql`        | Primary OLTP store                         | CoreService ORM target                                      |
| `rabbitmq`     | Task broker for external plugins           | Management UI on 15672                                      |
| `nats`         | Event bus (JetStream enabled)              | Already deployed; used by the new `EventPublisher` path     |
| `dragonfly`    | Redis-compatible KV + pub/sub              | Backs the Dragonfly `JobManager` singleton                  |
| `consul`       | Service discovery                          | External plugins register here                              |
| `prometheus`   | Metrics                                    | Scrapes `/metrics`                                          |
| `grafana`      | Dashboards                                 |                                                             |
| `core_service` | FastAPI app                                | Also owns the in-process plugin runtime and Socket.IO       |
| `*_plugin`     | External plugin containers                 | One per processing step (CTF, MotionCor, result processor)  |

Plugin containers declare GPU reservations where needed (MotionCor). The CTF
plugin is CPU-based.

---

## 3. CoreService internals

### 3.1 Web surface

`CoreService/main.py` wires **27 routers** into FastAPI, covering authentication
(Casbin RBAC + row-level security), data browsing (sessions, images,
particles), import pipelines (Leginon, EPU, file-scan), and the newer plugin /
workflow surface. Socket.IO is mounted *inside* FastAPI as of commit `fc0f325`
so that progress frames share the HTTP server/event loop (see
`core/socketio_server.py`).

### 3.2 Domain model

The split between a **job** (user-visible unit of work) and a **task** (single
processing step against one image) is encoded in
`CoreService/models/plugins_models.py`:

- `TaskBase` (`models/plugins_models.py:49`) — the envelope: `id`, `job_id`,
  `worker_instance_id`, `status`, `type` (`TaskCategory`), `created_date`,
  `start_on`, `end_on`, `result`.
- `data: Dict[str, Any]` — the payload, typed per task (`CtfTaskData` at line
  126, `CryoEmMotionCorTaskData` at line 141, …).
- `TaskDto` extends `TaskBase` with a `job_id`.
- `JobDto` extends `TaskBase` with `tasks: List[TaskDto]`.
- `TaskResultDto` (line 312) is the return envelope: output files, meta-data
  rows, status, timestamps.

This envelope/payload split is the *same shape* every plugin sees on the
RabbitMQ path. It is, effectively, a homegrown CloudEvents — with the quirks
that come from not being CloudEvents (no `specversion`, `source`, or
`datacontenttype`).

### 3.3 One live job service, two scaffolded replacements

There are three files in `services/` whose class is named `JobManager` or
`JobService`. Only **one is on the hot path**; the other two are scaffolding
that was committed as preparation for the next architectural step.

| Manager                                        | File                                                                    | Status on `main`                                                                                          |
|------------------------------------------------|-------------------------------------------------------------------------|-----------------------------------------------------------------------------------------------------------|
| MySQL `JobService`                             | `services/job_service.py`                                               | **Live.** Imported by `plugins/controller.py:29`, `plugins/progress.py:19`, `plugins/pp/controller.py:51`.|
| Dragonfly `JobManager`                         | `services/job_manager.py` (936 lines)                                   | **Side path.** Only imported by `controllers/import_controller.py:11`. Predates the plugin controller.    |
| NATS `JobManager` + `TemporalJobManager`       | `services/magellon_job_manager.py` + `services/temporal_job_manager.py` | **Scaffolding.** Referenced from `controllers/workflow_job_controller.py` and `docs/architecture/WORKFLOW_ARCHITECTURE.md` — not from the live plugin or import flows.|

The scaffolded pieces already do useful work:

- `services/event_publisher.py` is a complete NATS publisher with the
  `job.*`, `step.*`, `worker.*` subject taxonomy. Not yet wired to the live
  plugin path.
- `services/temporal_job_manager.py` is a working Temporal client: starts
  workflows, polls `workflow_handle.query("get_progress")` at
  `temporal_job_manager.py:239`, republishes onto NATS. Has no workflows to
  run against — Temporal server and workers are not in
  `docker-compose.yml` yet.

**Implication:** the live path today is MySQL `JobService` + Socket.IO
direct emit from `plugins/progress.py`. The NATS/Temporal stack is ~90%
prepared but not yet load-bearing. The target-state document makes it
load-bearing and retires the Dragonfly side path.

### 3.4 Event publisher

`services/event_publisher.py` (236 lines) is the NATS outbound surface. It
publishes to these subjects:

```
job.created        job.started     job.progress
job.completed      job.failed      job.cancelled
step.started       step.progress   step.completed   step.failed
worker.registered  worker.heartbeat
```

A global singleton is exposed via `get_event_publisher()`. The subject
taxonomy is *already* close to what the target-state document proposes —
it just isn't the sole event path yet.

---

## 4. Two parallel plugin architectures

### 4.1 Architecture A — external RabbitMQ plugins (`Magellon/plugins/`)

Each external plugin is a separate Python project with its own Docker image.
They share a near-identical `core/` subpackage that is **copy-pasted across
repos**: `core/model_dto.py`, `core/rabbitmq_client.py`, `core/settings.py`,
`core/consul.py`, `core/setup_plugin.py`. The duplication has already drifted
between plugins.

**Queue topology** (from `CoreService/core/helper.py`):

| Direction       | Queue                         | Producer         | Consumer                      |
|-----------------|-------------------------------|------------------|-------------------------------|
| Dispatch CTF    | `ctf_tasks_queue`             | CoreService      | `magellon_ctf_plugin`         |
| Dispatch MC     | `motioncor_tasks_queue`       | CoreService      | `magellon_motioncor_plugin`   |
| Results CTF     | `ctf_out_tasks_queue`         | CTF plugin       | `magellon_result_processor`   |
| Results MC      | `motioncor_out_tasks_queue`   | MC plugin        | `magellon_result_processor`   |
| WebSocket bridge| `motioncor_test_inqueue/out`  | Frontend test    | MC plugin / bridge            |

The mapping from `TaskCategory.code` to queue name is hardcoded in
`CoreService/core/helper.py:111` (`get_queue_name_by_task_type`, with `2=CTF`,
`5=MOTIONCOR`). Adding a new task type requires editing this file.

**Dispatch path** (`services/leginon_frame_transfer_job_service.py:411`):
`run_task()` calls `compute_ctf_task` → `dispatch_ctf_task`
(`core/helper.py:183`) or `compute_motioncor_task` → `dispatch_motioncor_task`
(`core/helper.py:349`). Both end at `push_task_to_task_queue`
(`core/helper.py:138`), which uses `RabbitmqClient` (`core/rabbitmq_client.py`)
to publish a durable, persistent message (`delivery_mode=2`, line 54) to the
queue. `publish_message_to_queue` (line 76) additionally writes every outgoing
message to `/magellon/messages/<queue>/messages.json` as an on-disk audit log.

**Consumer pattern** (`plugins/magellon_ctf_plugin/core/rabbitmq_consumer_engine.py`):
each plugin spins a pika `BlockingConnection` and, inside the blocking
callback, calls `asyncio.run(do_execute(the_task))` (line 25). This has two
known problems:
1. It defeats `PREFETCH_COUNT > 1` because the callback is synchronous.
2. `basic_nack(requeue=False)` silently drops poison messages instead of
   routing them to a DLQ.

**Result processing:** the result-processor plugin
(`plugins/magellon_result_processor/core/rabbitmq_consumer_engine.py`) is the
only plugin that consumes from a *list* of queues (`OUT_QUEUES` fan-in). Its
`TaskOutputProcessor` (`services/task_output_processor.py`) moves files into
`MAGELLON_HOME_DIR/<session>/<dir_name>/<image>/` and writes `ImageMetaData`
rows with `category_id` (2=ctf, 3=motioncor).

**Settings drift:** each plugin carries its own `configs/settings_dev.yml` and
they have diverged (different log formats, different broker host fallbacks).

**Client visibility:** there is no mid-flight progress path in this
architecture. The user sees "dispatched" and, eventually, "done" or an error.
If a plugin hangs, the user waits.

### 4.2 Architecture B — in-process `PluginBase` + registry (`CoreService/plugins/`)

The newer architecture runs plugins inside the CoreService process.

- **`plugins/base.py`** — `PluginBase(ABC, Generic[InputT, OutputT])`. Every
  plugin declares typed Pydantic input/output schemas and implements
  `execute()`. The class enforces a lifecycle:
  `DISCOVERED → INSTALLED → CONFIGURED → READY → RUNNING → COMPLETED/ERROR/DISABLED`
  (see the ASCII diagram at the top of the file). `run()` is the non-virtual
  entry point: validate input → `pre_execute` → `execute` → `post_execute` →
  validate output. Plugins expose `task_category: ClassVar[TaskCategory]` for
  routing.
- **`plugins/registry.py`** — `PluginRegistry` walks the `plugins.*` package
  with `pkgutil.walk_packages`, imports any module ending in `.service`,
  instantiates every `PluginBase` subclass it finds, and caches it keyed by
  `{category}/{name}`. Currently discovered: `ctf/ctffind`,
  `motioncor/motioncor2`, `pp/template-picker` (there is also an `fft/`
  folder). Lazy, thread-safe, with a `refresh()` for dev reloads.
- **`plugins/progress.py`** — `ProgressReporter` Protocol plus `NullReporter`
  (for plugins run outside a job context) and `JobReporter` (for live jobs).
  `JobReporter.report()` persists progress via `JobService`, emits
  `emit_job_update` / `emit_log` onto Socket.IO via
  `asyncio.run_coroutine_threadsafe`, deduplicates identical percents, and
  raises `JobCancelledError` at the next checkpoint when the job has been
  marked cancelled. This is the **only** cooperative-cancel path in the repo
  today.
- **`plugins/controller.py`** — generic HTTP router:
  ```
  GET    /plugins/                        list plugins
  GET    /plugins/{id}/info|health|requirements
  GET    /plugins/{id}/schema/input|output
  POST   /plugins/{id}/jobs               submit one
  POST   /plugins/{id}/jobs/batch         fan out over N inputs
  GET    /plugins/jobs                    list (optional filter)
  GET    /plugins/jobs/{job_id}           detail
  DELETE /plugins/jobs/{job_id}           cooperative cancel
  ```
  `_run_generic_job` runs `plugin.run()` in `loop.run_in_executor`, pushes
  progress frames over Socket.IO, and catches `JobCancelledError` to emit a
  cancelled envelope.

**Client visibility:** this path streams progress. The UI already renders it
for particle-picking.

### 4.3 Why both exist

Architecture A predates the decision to put Magellon on a single control plane.
Architecture B is the newer design and is where the next wave of plugins is
landing. Neither is going away *today* because:

- A handles the GPU-heavy steps (MotionCor, eventually Topaz/DeepPicker) where
  out-of-process isolation is still convenient.
- B handles the CPU/IO-bound steps and anything that benefits from being in the
  same process as the ORM and Socket.IO.

The target-state document proposes a single SDK that lets a plugin run in
either location without rewrite.

---

## 5. Message envelope

Both architectures share the same envelope shape in code
(`TaskBase` + `data: Dict[str, Any]`), but it is not versioned and is not a
published standard. Fields vary subtly across consumers. There is no explicit
`source`, `specversion`, or schema-version pin, so schema changes propagate as
silent compatibility bugs.

Plugin schema version *is* tracked at the plugin level:
`PluginInfo.schema_version` (`models/plugins_models.py:240`) is compared by the
frontend against a cached copy to decide whether to re-fetch the input form.
This is a small but real contract surface.

---

## 6. Import pipelines

CoreService ingests external datasets via three routes:

- **Leginon frame transfer** (`services/leginon_frame_transfer_job_service.py`)
  — the canonical example of a complex job. Orchestrates per-image FFT/PNG
  generation (in-process), CTF (RabbitMQ), and MotionCor (RabbitMQ).
- **EPU import** — Thermo Fisher EPU layout walker.
- **File-scan import** — generic filesystem walker.

These pipelines are the main *producers* of jobs today and therefore the most
important callers of the three job managers.

---

## 7. Progress and event surface today

Mid-flight progress exists on three unrelated paths:

1. **Socket.IO `emit_job_update` / `emit_log`** from the in-process plugin
   runtime (`plugins/progress.py` → `core/socketio_server.py`). The React app
   subscribes per-`sid`. **This is the only path the current UI consumes for
   plugin jobs.**
2. **NATS `job.*` / `step.*` subjects** from `services/event_publisher.py`,
   republished by `TemporalJobManager` via `workflow_handle.query`. No UI
   subscriber exists yet.
3. **Dragonfly pub/sub** on channel `magellon:job_events` from
   `services/job_manager.py`. Used by server-internal listeners.

Pick a job and you cannot predict, from the outside, which of these three
paths will carry its progress. This is the concrete developer-experience cost
of the three-manager problem.

---

## 8. Temporal integration (partial)

`services/temporal_job_manager.py` (406 lines) is a working Temporal client.
It:

- Extends the NATS `JobManager`.
- Uses `temporalio.client.Client` to start workflows.
- Monitors workflow progress by calling `workflow_handle.query("get_progress")`
  every 5 seconds and republishing onto NATS (line 239).
- Handles cancellation via `workflow_handle.cancel()`.

What is **not** yet in place:

- A worker that actually runs Temporal *activities*. The plugins are not yet
  activities.
- Workflow definitions that compose plugins as steps (the gstreamer /
  pipeline-of-plugins idea).
- A deployed Temporal cluster in `docker-compose.yml`.

So Temporal is wired client-side but does not have anything to run against in
the default dev stack. ~90% of what the target state needs already exists in
code; the missing piece is the server, the workers, and one workflow
definition.

---

## 9. Known limitations (with evidence)

| # | Problem | Evidence |
|---|---------|----------|
| 1 | One live job service + two scaffolded replacements (not fragmentation, but inventory to converge) | `services/job_service.py` live; `services/job_manager.py` side path; `services/magellon_job_manager.py` + `temporal_job_manager.py` prepared but unwired |
| 2 | Two plugin architectures | `Magellon/plugins/` (RabbitMQ) vs `CoreService/plugins/` (in-process) |
| 3 | SDK scaffolded but empty | `MagellonSdk/README.md` is `# Welome MagellonSdk` |
| 4 | Duplicated `core/` across external plugins | Same files in each of `magellon_ctf_plugin`, `magellon_motioncor_plugin`, `magellon_result_processor`; drift observed |
| 5 | Queue mapping hardcoded | `core/helper.py:111` `get_queue_name_by_task_type` — adding a task type is a source edit |
| 6 | `asyncio.run` inside blocking pika callback | `plugins/magellon_ctf_plugin/core/rabbitmq_consumer_engine.py:25` |
| 7 | Poison messages silently dropped | `basic_nack(requeue=False)` with no DLQ in external plugins |
| 8 | `rabbitmq_client.connect()` swallows errors | `core/rabbitmq_client.py` catches `AMQPConnectionError`, leaves `self.connection=None`, does not re-raise |
| 9 | Path coupling via shared filesystem | `TaskOutputProcessor` assumes `MAGELLON_HOME_DIR` is visible to every container — breaks on cloud executors |
| 10| No CloudEvents / no envelope versioning | `TaskBase` has no `specversion`, `source`, `datacontenttype` |
| 11| No DLQ, no retry policy | External-plugin failures hit `basic_nack(requeue=False)` and disappear |
| 12| Customer GPU/Docker install burden | Out-of-scope of repo but repeatedly reported; motivates the Executor abstraction in the target doc |
| 13| Multiple settings drift | Per-plugin `configs/settings_dev.yml` files have diverged |

---

## 10. Test suite inventory

Roughly 23 pytest files under `CoreService/tests/` and plugin repos. Coverage
is concentrated on:

- ORM round-trips and Casbin policy enforcement.
- Import-pipeline happy paths.
- A handful of plugin-level unit tests (`plugins/<plugin>/tests/`).

Gaps (relevant to the migration plan):

- **No characterization tests** on dispatch paths — the current
  envelope-on-the-wire is not pinned.
- **No end-to-end test** that drives RabbitMQ + MySQL + Socket.IO together.
- **No contract tests** between CoreService and external plugins.
- **No load / backpressure tests** on the queue topology.

The target-state plan's Phase 0 is to add characterization tests for the
exact envelope shape, subject names, and queue names in use today before any
code moves.

---

## 11. What to read next

- `TARGET_ARCHITECTURE_AND_PLAN.md` — the destination and the phased plan.
- `CoreService/plugins/base.py` — the cleanest single file for understanding
  the target plugin contract.
- `CoreService/services/temporal_job_manager.py` — proof that ~90% of the
  target orchestration plumbing already exists.
- `Docker/docker-compose.yml` — what's already deployed (NATS and JetStream
  already there; Temporal server is the one missing piece).
