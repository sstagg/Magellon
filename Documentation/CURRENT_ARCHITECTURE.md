# Magellon — Current Architecture (as-is)

**Status:** Reference manual of the system as it exists on `main` (2026-04-15).
**Audience:** Architects, new plugin developers, reviewers of the v1 plan.
**Companion:** `IMPLEMENTATION_PLAN.md` (where we are going and how).

This document describes Magellon **as it actually behaves in the repo**, not
as any single diagram would suggest. Magellon is in mid-consolidation: a
RabbitMQ-based external plugin fleet coexists with an in-process plugin
registry. A previous direction (Temporal as the workflow engine) was
reverted on 2026-04-14 (`86fe9cc`); residual scaffolding from that era
still exists in the repo and is called out below.

---

## 1. System context

Magellon is an extensible platform for cryo-EM data visualization, management,
and processing (Khoshbin et al., *IUCrJ* 12, 637–646, 2025; bioRxiv
10.1101/2025.06.09.658726). It provides:

- A **CoreService** (FastAPI) that owns the data model, authz, import
  pipelines, and job orchestration.
- A **React frontend** (`magellon-react-app`) that talks to CoreService over
  REST and Socket.IO.
- A fleet of **processing plugins** (CTF estimation, motion correction,
  particle picking, FFT, …). Some run *inside* CoreService; others run
  *outside* as containerised RabbitMQ consumers.
- An infrastructure layer in `Docker/docker-compose.yml`: MySQL, RabbitMQ,
  NATS, Dragonfly (Redis-compatible), Prometheus, Grafana. **Consul was
  removed in P8 (2026-04-15)** — discovery and dynamic configuration both
  ride the RabbitMQ broker now.

Repo layout:

```
Magellon/
├── CoreService/          # FastAPI, routers, plugin registry, job service
├── plugins/              # External plugins (RabbitMQ consumers)
│   ├── magellon_ctf_plugin/
│   ├── magellon_motioncor_plugin/
│   └── magellon_result_processor/
├── magellon-sdk/         # magellon-sdk 0.1.0 — scaffolded, editable install
├── magellon-react-app/   # Frontend
├── Docker/               # docker-compose deployment topology
├── Documentation/        # This file, IMPLEMENTATION_PLAN, etc.
└── infrastructure/       # Ansible/TF (out of scope here)
```

---

## 2. Deployment topology

`Docker/docker-compose.yml` brings up the full stack. Current services:

| Service        | Purpose                                    | Notes                                                       |
|----------------|--------------------------------------------|-------------------------------------------------------------|
| `mysql`        | Primary OLTP store                         | CoreService ORM target                                      |
| `rabbitmq`     | Task broker for external plugins           | Management UI on 15672. Live path for CTF / MotionCor.      |
| `nats`         | Event bus (present, minimally used)        | Deployed in compose. No live publishers today — see §6.     |
| `dragonfly`    | Redis-compatible KV + pub/sub              | Cache. Dragonfly-backed `JobManager` was deleted 2026-04-14.|
| `prometheus`   | Metrics                                    | Scrapes `/metrics`                                          |
| `grafana`      | Dashboards                                 |                                                             |
| `core_service` | FastAPI app                                | Owns in-process plugin runtime and Socket.IO                |
| `*_plugin`     | External plugin containers                 | CTF, MotionCor, result processor                            |

No Temporal server — removed from compose in the 2026-04-14 revert.
No Consul server either — removed in P8 (2026-04-15); the
`magellon.plugins.*` topic exchange handles announce / heartbeat /
config-push that used to flow through Consul KV + service-catalog.

---

## 3. CoreService internals

### 3.1 Web surface

`CoreService/main.py` wires multiple routers into FastAPI, covering
authentication (Casbin RBAC + row-level security), data browsing (sessions,
images, particles), import pipelines (Leginon, EPU, Magellon, SerialEM),
and the newer plugin surface. Socket.IO is mounted *inside* FastAPI as of
commit `fc0f325` so that progress frames share the HTTP server/event loop
(`core/socketio_server.py`).

### 3.2 Domain model

The split between a **job** (user-visible unit of work) and a **task**
(single processing step against one image) exists in two places:

- **SQLAlchemy (persistent):** `ImageJob` at `models/sqlalchemy_models.py:287`
  — columns include `oid`, `name`, `msession_id`, `status_id`, `type_id`,
  `settings` (JSON), `processed_json` (JSON). `ImageJobTask` at
  `sqlalchemy_models.py:520` — `oid`, `job_id` (FK), `image_id` (FK),
  `status_id`, `type_id`, `stage`, `image_path`, `data_json`,
  `processed_json`. Status enum from `controllers/import_controller.py:151`:
  1=pending, 2=running, 3=processing, 4=completed, 5=failed, 6=cancelled.

- **Pydantic DTOs (wire):** `TaskBase`, `TaskDto`, `JobDto`, `TaskResultDto`
  in `models/plugins_models.py` (around line 49–312). `data: Dict[str, Any]`
  is the per-task-type payload; concrete shapes are `CtfTaskData`,
  `CryoEmMotionCorTaskData`, etc. This is the envelope RabbitMQ carries.

The envelope is a homegrown shape — no `specversion`, `source`, or
`datacontenttype` — functionally similar to CloudEvents but not standards-
compliant. Plugin schema version IS tracked via
`PluginInfo.schema_version` (`plugins_models.py:240`) and consumed by the
frontend.

### 3.3 Job state ownership

**One live writer: `services/job_service.py`.** Imported by
`plugins/controller.py`, `plugins/progress.py`, `plugins/pp/controller.py`.
Owns the in-process plugin lifecycle — writes `ImageJob` + `ImageJobTask`
rows atomically on `create_job`, updates on `mark_running`,
`update_progress`, `complete_job`, `fail_job`, `cancel_job`, and emits
Socket.IO events as it goes.

**Dead-code island (Temporal-era, ~2K lines, zero live importers):**

| File                                                 | What it was                            |
|------------------------------------------------------|----------------------------------------|
| `services/magellon_job_manager.py`                   | Domain-style job manager over NATS     |
| `services/job_event_publisher.py`                    | Facade over MagellonEventService       |
| `services/magellon_event_service.py`                 | NATS JetStream + subject taxonomy      |
| `services/event_logging_service.py`                  | Streams NATS events to stdout/log      |
| `services/event_publisher.py`                        | Legacy NATS publisher                  |
| `activities/image_processing_activities.py`          | Temporal activities                    |
| `worker_{ctf,motioncor,thumbnail,all}.py`            | Temporal worker entry points           |
| `docs/architecture/{WORKFLOW,EVENT}_ARCHITECTURE.md` | Temporal-era design docs               |

None are imported by live code. Slated for deletion in an A.1-followup PR.

**Importer path uses `job_service` too** for `ImageJob`/`ImageJobTask` row
creation, but dispatches individual tasks via RabbitMQ (see §4.1). Task
**state writes** after dispatch currently do not come back through
`job_service` — see §4.1's gap note.

### 3.4 Plugin registry (in-process)

`plugins/registry.py` walks `plugins.*`, imports any `.service` module,
instantiates every `PluginBase` subclass, and caches by
`{category}/{name}`. Currently discovered:

- `ctf/ctffind` — stub
- `motioncor/motioncor2` — stub
- `pp/template-picker` — **live** (particle picking by template matching)
- `fft/` — empty directory

The in-process runtime at `plugins/controller.py` exposes the generic
plugin HTTP surface (see §4.2).

---

## 4. Two parallel plugin architectures

### 4.1 Architecture A — external RabbitMQ plugins (`Magellon/plugins/`)

Each external plugin is its own Python project with its own Docker image.
The previously copy-pasted `core/` subpackage has been **consolidated into
`magellon-sdk`** across Phases B.1 / B.2 / B.3 (`c90eefb` / `eda4933` /
`f9a4511`); plugin `core/` shims now re-export from the SDK. The
`core/consul.py` shim was deleted in P8 alongside the broker. Each plugin's
`main.py` collapses to a `PluginBrokerRunner` instance (P5) that does the
RMQ loop, broker-based discovery (P6), dynamic config subscription (P7),
and provenance-stamped result publishing (P4) for free.

**Queue topology** (from `CoreService/core/helper.py` + plugin configs):

| Direction       | Queue                         | Producer     | Consumer                      |
|-----------------|-------------------------------|--------------|-------------------------------|
| Dispatch CTF    | `ctf_tasks_queue`             | CoreService  | `magellon_ctf_plugin`         |
| Dispatch MC     | `motioncor_tasks_queue`       | CoreService  | `magellon_motioncor_plugin`   |
| Results CTF     | `ctf_out_tasks_queue`         | CTF plugin   | `magellon_result_processor`   |
| Results MC      | `motioncor_out_tasks_queue`   | MC plugin    | `magellon_result_processor`   |
| Test bridge     | `motioncor_test_inqueue/out`  | Frontend     | MC plugin (test harness only) |

Queue naming is hardcoded in `core/helper.py:111` (`get_queue_name_by_task_type`)
with `2=CTF`, `5=MOTIONCOR`. Adding a task type is a source edit.

**Dispatch path.** Importers (`services/importers/{MagellonImporter,EPUImporter,SerialEmImporter,BaseImporter}.py`)
and the Leginon frame-transfer service build a `TaskDto` and call
`dispatch_ctf_task` / `dispatch_motioncor_task` (`core/helper.py:147`
and `:349`). Both end at `push_task_to_task_queue` (`core/helper.py:106`)
which delegates to `get_task_dispatcher_registry().dispatch(task)`
(`core/dispatcher_registry.py:124`). The registry wraps the `TaskDto`
in a CloudEvents `Envelope` and publishes via `bus.tasks.send` on the
RMQ-backed `MessageBus` (installed once at startup by
`install_core_bus()`, called from `main.py:367`). The on-disk audit
log is still written to `/magellon/messages/<queue>/messages.json`
via `_audit_outgoing_message` (`core/helper.py:124`), now decoupled
from the publish path. (Updated 2026-04-21: MB3 producer migration
landed; `RabbitmqClient` is no longer on the dispatch path.)

**Consumer pattern** (`plugins/magellon_ctf_plugin/core/rabbitmq_consumer_engine.py`):
each plugin spins a pika `BlockingConnection` and, inside the blocking
callback, calls `asyncio.run(do_execute(the_task))`. This has two known
issues:

1. It defeats `PREFETCH_COUNT > 1` — the callback is synchronous.
2. `basic_nack(requeue=False)` silently drops poison messages; no DLQ.

**Result processing.** `magellon_result_processor` subscribes to a *list*
of out-queues (`OUT_QUEUES` fan-in) and delegates to `TaskOutputProcessor`
at `plugins/magellon_result_processor/services/task_output_processor.py:128`.
On each result it:

1. Moves output files (CTF star files, MC MRCs) to
   `MAGELLON_HOME_DIR/<session>/<dir_name>/<image>/`.
2. Writes `ImageMetaData` rows keyed by `image_id`, with `category_id`
   distinguishing CTF (2) vs MotionCor (3).

**Known gap (`task_output_processor.py`):**
`ImageJobTask.status_id` and `stage` are **never advanced past 1 (pending)**
after a task completes. The lines that would set `db_task.stage = 5`
were removed during a refactor. Consequences:

- UI has no reliable per-task completion signal on the RMQ path.
- There is no failure path either — a plugin crash mid-task is invisible
  to CoreService; the task row stays at `pending` indefinitely.

**Client visibility.** Nothing streams mid-flight progress from external
plugins to the UI today. The user sees "dispatched" and, eventually, the
result appears in `ImageMetaData` — or doesn't.

**Settings drift.** Each plugin has its own `configs/settings_dev.yml` and
they have diverged (different log formats, different broker host
fallbacks).

### 4.2 Architecture B — in-process `PluginBase` + registry (`CoreService/plugins/`)

The newer architecture runs plugins inside the CoreService process.

- **`plugins/base.py`** — `PluginBase(ABC, Generic[InputT, OutputT])`. Every
  plugin declares typed Pydantic input/output schemas and implements
  `execute()`. The class enforces a lifecycle
  `DISCOVERED → INSTALLED → CONFIGURED → READY → RUNNING → COMPLETED/ERROR/DISABLED`.
  `run()` is the non-virtual entry: validate input → `pre_execute` →
  `execute` → `post_execute` → validate output. Plugins expose
  `task_category: ClassVar[TaskCategory]` for routing.
- **`plugins/progress.py`** — `ProgressReporter` Protocol + `NullReporter`
  (out-of-job) and `JobReporter` (in-job). `JobReporter.report()` persists
  progress via `JobService`, emits `emit_job_update` / `emit_log` onto
  Socket.IO via `asyncio.run_coroutine_threadsafe`, deduplicates identical
  percents, and raises `JobCancelledError` at the next checkpoint when the
  job has been marked cancelled. This is the **only** cooperative-cancel
  path in the repo.
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
  progress frames over Socket.IO, and catches `JobCancelledError` to emit
  a cancelled envelope.

**Client visibility.** This path streams progress. The UI renders it for
particle-picking today.

### 4.3 Why both exist

Architecture A predates the decision to put Magellon on a single control
plane. Architecture B is the newer design where the next wave of plugins
will land. Neither is going away today because:

- A handles GPU-heavy steps (MotionCor, eventually Topaz/DeepPicker)
  where out-of-process isolation is convenient.
- B handles CPU/IO-bound steps and anything that benefits from living in
  the same process as the ORM and Socket.IO.

The v1 plan in `IMPLEMENTATION_PLAN.md` introduces a `JobManager` seam
such that both architectures call the same state writer, and a plugin
SDK (`magellon-sdk`) with shared `TaskDispatcher` / `ProgressReporter`
contracts that work in either location.

---

## 5. End-to-end flow: a Magellon import today

For concreteness, the actual sequence a Magellon import runs through:

1. `POST /magellon-import` → `controllers/import_controller.py:68`.
2. `MagellonImporter.setup(request, db_session)` + `.process(db_session)`.
3. `process()` at `services/importers/MagellonImporter.py:44`:
   - Reads `session.json` from source_dir.
   - Creates/upserts `Project` + `Msession` rows.
   - Creates `ImageJob` row at `:79–91` (status_id=1, pending). Commits.
   - Iterates images: creates `Image` + `ImageJobTask` rows
     (`:421–501`). Commits.
   - `run_tasks()` loops tasks synchronously: PNG conversion + FFT are
     **in-process** (no broker); `compute_ctf_task` → `dispatch_ctf_task`
     → **RabbitMQ publish** to `ctf_tasks_queue`; `compute_motioncor_task`
     → `dispatch_motioncor_task` → **RabbitMQ publish** to
     `motioncor_tasks_queue`.
4. The HTTP request **returns** at this point — dispatch is fire-and-forget
   from CoreService's perspective.
5. External CTF plugin container consumes `ctf_tasks_queue`, runs
   `ctffind4`, publishes result on `ctf_out_tasks_queue`.
6. External MotionCor plugin consumes `motioncor_tasks_queue`, runs
   `MotionCor2`, publishes on `motioncor_out_tasks_queue`.
7. `magellon_result_processor` consumes both out-queues, moves output
   files, writes `ImageMetaData`. **`ImageJobTask.stage` is not updated
   (see §4.1 gap).**
8. The UI sees Socket.IO events only for the in-process bits; the external
   plugin portion is silent until results show up in `ImageMetaData`.

---

## 6. Progress and event surface today

Two paths carry mid-flight progress; one is live, one is scaffolded-but-
unused:

1. **Socket.IO `emit_job_update` / `emit_log`** from the in-process plugin
   runtime (`plugins/progress.py` → `core/socketio_server.py`). The React
   app subscribes per-`sid`. **This is the only path the current UI
   consumes for plugin jobs.** External RMQ plugins do **not** emit on
   this path.

2. **NATS** — a broker is deployed in compose but no live publisher
   currently writes to it. `services/event_publisher.py` + the
   `services/magellon_event_service.py` singleton implement a complete
   NATS publisher with a `job.*` / `step.*` / `worker.*` subject
   taxonomy, but their only importers are the Temporal-era workers and
   activities, which are dead code (§3.3). A third path via Dragonfly
   pub/sub existed in the deleted `services/job_manager.py` and is now
   gone.

The concrete developer-experience cost: external plugin progress is
invisible today.

---

## 7. Temporal integration — status

**Reverted 2026-04-14 (`86fe9cc`).** The prior plan put Temporal in the
center of job orchestration. Phase 2 PRs landed worker scaffold,
`CtfWorkflow`, `CTF_VIA_TEMPORAL` feature flag, and the Temporal Docker
stack — then were reverted because the actual current workload ("one
import, thousands of discrete tasks, no multi-step pipelines, no signals
or queries") did not justify what Temporal delivers.

What survived the revert: the orchestrator-agnostic contract — `PluginBase`,
`ProgressReporter`, CloudEvents envelope, `Executor` Protocol — all in
`magellon-sdk`. If a workflow engine becomes justified later (real
multi-step pipelines with retry policy trees or human-in-the-loop),
that's the plug-in point.

What did not survive but is still in the tree: the dead-code island
listed in §3.3.

---

## 8. Known limitations (with evidence)

| # | Problem | Evidence |
|---|---------|----------|
| 1 | ~~`ImageJobTask` state not advanced after RMQ task completion~~ | **Resolved (Phase 4).** `task_output_processor._advance_task_state` writes `status_id` + `stage` (MotionCor=1, CTF=2, unknown=99). 5 unit tests. |
| 2 | ~~No failure path from external plugin crashes~~ | **Resolved (P2 + P5).** `magellon_sdk.errors.classify_exception` returns `AckAction.{ACK,NACK_REQUEUE,DLQ}` per a typed taxonomy; `PluginBrokerRunner` honours it (DLQ for poison, requeue for transient, ack-with-failure-result for plugin-domain errors). |
| 3 | ~~No mid-flight progress for external plugins~~ | **Publisher half resolved (Phase 4.5).** `magellon_sdk.events.StepEventPublisher` emits `magellon.step.*` CloudEvents on NATS. CoreService Socket.IO forwarder is the remaining half. |
| 4 | Two plugin architectures | Same split (`plugins/` RMQ vs `CoreService/plugins/` in-process). The `TaskDispatcher` Protocol is the shared seam, and **`CategoryContract` (P1)** is the canonical input/output schema both halves resolve against — substitutability is now contract-pinned, not convention-pinned. |
| 5 | ~~Temporal-era dead-code island (~2K lines)~~ | **Resolved (A.1 follow-up, `7d1f657`).** |
| 6 | ~~SDK scaffolded, thin~~ | **Filled in.** `magellon-sdk 0.1.0` now ships `PluginBase`, `Envelope`, `Executor` Protocol, `ProgressReporter`, **`TaskDispatcher` + `TaskDispatcherRegistry` (Phase 6)**, **NATS transport** (`NatsPublisher`/`NatsConsumer`), **RMQ transport** (`RabbitmqClient` with `declare_queue_with_dlq`), and **`events.StepEventPublisher`**. |
| 7 | ~~Duplicated `core/` across external plugins~~ | **Resolved (Phases B.1/B.2/B.3, `c90eefb`/`eda4933`/`f9a4511`).** |
| 8 | ~~Queue mapping hardcoded~~ | **Resolved (Phase 6 + wiring).** `core.dispatcher_registry.get_task_dispatcher_registry()` owns the `TaskCategory.code` → dispatcher mapping. `push_task_to_task_queue` delegates. `get_queue_name_by_task_type` remains for the audit helper. |
| 9 | ~~`asyncio.run` inside blocking pika callback~~ | **Resolved (Phase 3).** All 4 plugin consumer engines use one daemon-thread event loop + `asyncio.run_coroutine_threadsafe(...).result()`. |
| 10 | ~~Poison messages silently dropped~~ | **Resolved (P2).** `classify_exception` routes parse / validation / unsupported-input errors to DLQ explicitly, transient infra errors to requeue, and plugin-domain failures to an ack-with-failure-result. Existing queues still need the broker-policy migration before DLQ delivery actually fires for them. |
| 11 | ~~`rabbitmq_client.connect()` swallows errors~~ | **Resolved (Phase 3).** `RabbitmqClient.connect()` and `publish_message()` now re-raise `AMQPConnectionError` / `ChannelError`; `publish_message_to_queue` returns `False` instead of silent-dropping. |
| 12 | ~~Path coupling via shared filesystem~~ | **Reframed as architectural choice (2026-04-21).** `TaskOutputProcessor` assumes `MAGELLON_HOME_DIR` is a POSIX-shared namespace visible to CoreService and every plugin worker — this is the data plane and is intentional, not a gap. See `DATA_PLANE.md`. Object-storage-only deployments are an explicit non-goal. |
| 13 | ~~No CloudEvents / no envelope versioning~~ | **Resolved (Phase 2).** `magellon_sdk.envelope.Envelope[DataT]` is CloudEvents 1.0 compliant with `specversion`, `source`, `type`, `subject`, `time`, `datacontenttype`. Used by the NATS transport and the step-event publisher. |
| 14 | ~~No DLQ, no retry policy~~ | **Capability landed.** `RabbitmqClient.declare_queue_with_dlq()` wires `x-dead-letter-exchange` + routing key on new queues; 2 integration tests. Existing queues need a broker-policy migration (can't re-declare with new `x-*` args). Retry policy is still open. |
| 15 | ~~Settings drift per plugin~~ | **Mostly resolved (P7).** Runtime knobs now flow through `magellon.plugins.config.<category>` / `.broadcast` topic exchange; every `PluginBrokerRunner` ships a `ConfigSubscriber` that drains pending updates between tasks and calls `plugin.configure()`. Static per-plugin `settings_dev.yml` files still exist for boot-time wiring. |
| 16 | No operator hard-stop for runaway plugin work | **Resolved (P9).** `POST /cancellation/queues/purge` drains pending tasks from one or more category queues; `POST /cancellation/containers/{name}/kill` issues `docker kill` on a stuck plugin replica. Cooperative cancel via `JobManager.request_cancel` remains the in-flight path. |
| 17 | Broker-based discovery / liveness (replaces Consul) | **Landed (P6).** Plugins emit one `magellon.plugins.announce.*` on boot and a `magellon.plugins.heartbeat.*` every N seconds via `DiscoveryPublisher` + `HeartbeatLoop`. CoreService listens with `core.plugin_liveness_registry.start_liveness_listener` and exposes the registry to the plugin discovery endpoints. |
| 18 | Provenance on results | **Resolved (P4).** `PluginBrokerRunner` auto-injects plugin manifest (id, name, version, schema_version, container hostname, host) into every `TaskResultDto.provenance` after the result_factory builds the wire shape; CoreService records it for audit. |

---

## 9. Test suite inventory

Pytest files under `CoreService/tests/` and plugin repos. Coverage is
concentrated on:

- ORM round-trips and Casbin policy enforcement.
- Import-pipeline happy paths.
- Plugin-level unit tests under `plugins/<plugin>/tests/`.
- Phase 0 characterization tests: pytest config, envelope goldens, queue
  names, plugin registry, HTTP contract, Socket.IO emit shape
  (`tests/characterization/`).

Gaps (relevant to the v1 plan):

- Seam-level E2E landed at `CoreService/tests/integration/test_e2e_seam.py`
  (Phase 5): publishes a real `TaskDto` via `RabbitmqTaskDispatcher`, a
  stub worker thread round-trips a `TaskResultDto`, and the result is
  driven through `_advance_task_state`. Covers RMQ + dispatcher +
  state-advance seam, but does not include MySQL or Socket.IO yet.
- Full docker-compose smoke runbook: `CoreService/scripts/e2e_smoke.sh`.
  Skipped in CI pending a GPU runner.
- NATS pub/sub integration test: `tests/integration/test_nats_pubsub.py`.
- RMQ integration tests (SDK-level): `magellon-sdk/tests/test_transport_rabbitmq_integration.py`
  including DLQ routing.
- No contract test between CoreService and external plugin containers.
- No load / backpressure tests on the queue topology.

---

## 10. Plugin platform refactor (P1–P9, 2026-04-15)

Nine sequential phases that landed the broker-native plugin platform.
Each row is one commit; tests landed alongside.

| Phase | Commit     | What it delivered                                                                 |
|-------|------------|-----------------------------------------------------------------------------------|
| P1    | `9a39299`  | `CategoryContract` + I/O diversity rules — canonical input/output per category.   |
| P2    | `9078dc6`  | Typed failure taxonomy (`AckAction.{ACK,NACK_REQUEUE,DLQ}` via `classify_exception`). |
| P3    | `ef5fffe`  | Result-processor promoted in-process — `OUT_QUEUES` consumed inside CoreService.  |
| P4    | `3e8af0a`  | Per-task provenance auto-stamped on every `TaskResultDto`.                        |
| P5    | `886f0e9`  | `PluginBrokerRunner` harness — plugins' `main.py` collapses to one constructor.   |
| P6    | `9a73c74`+`96f2908` | Broker-based discovery + heartbeat (replaces Consul); CoreService liveness registry. |
| P7    | `40f9008`+`ba20628` | Broker-based dynamic config — `magellon.plugins.config.<category>` + `.broadcast`. |
| P8    | `2f7aa9c`  | Consul deleted — package, service, models, plugin shims, compose.                 |
| P9    | `7e95930`  | Cancellation primitives — queue purge + container kill, Administrator-gated.      |

Net effect for a plugin author today: a new plugin is `class
MyPlugin(PluginBase): ...` plus a `main.py` that builds a `PluginBrokerRunner`
against a `CategoryContract`. Discovery, heartbeat, dynamic config,
provenance stamping, and typed failure routing are inherited.

---

## 11. What to read next

- **`ARCHITECTURE_PRINCIPLES.md`** — the canonical rule-set every
  non-trivial PR in Magellon is reviewed against. Read this first.
- **`DATA_PLANE.md`** — the shared-filesystem decision, the deployment
  matrix, and what the platform forecloses on (object-storage-only).
- **`IMPLEMENTATION_PLAN.md`** — the v1 / v2 / v3 phasing: hardening the
  RMQ system with a `JobManager` seam + SDK + progress bus, then NATS
  additively, then a data-driven decision.
- **`CoreService/plugins/base.py`** — the cleanest single file for
  understanding the target plugin contract.
- **`CoreService/services/job_service.py`** — the one live job-state
  writer today; the future `JobManager` is likely an expansion of this.
- **`plugins/magellon_ctf_plugin/`** and
  **`plugins/magellon_result_processor/`** — the external plugin
  reference; any new plugin SDK must stay compatible with their wire
  format.
- **`Docker/docker-compose.yml`** — deployed stack. RMQ + NATS both
  present; Temporal removed.
