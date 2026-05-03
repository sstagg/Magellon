# Magellon — Current Architecture (as-is)

**Status:** Reference manual of the system as it exists on `main` (2026-05-03).
**Audience:** Architects, new plugin developers, reviewers of the v1 plan.
**Companion:** `IMPLEMENTATION_PLAN.md` (where we are going and how).

This document describes Magellon **as it actually behaves in the repo**, not
as any single diagram would suggest. Magellon is in mid-consolidation: a
RabbitMQ-based external plugin fleet coexists with an in-process plugin
registry. A previous direction (Temporal as the workflow engine) was
reverted on 2026-04-14 (`86fe9cc`); residual scaffolding from that era
still exists in the repo and is called out below.

The 2026-05-03 rollout (17 commits, see §12) added two new categories
end-to-end (`PARTICLE_EXTRACTION` + `TWO_D_CLASSIFICATION`), the
**subject axis** that lets non-image-keyed tasks live alongside the
image-keyed ones, the typed **`Artifact`** entity that bridges
producing/consuming jobs, the **`PipelineRun`** rollup, and an
external **template-picker plugin** that coexists with the in-process
one. The architectural decisions behind those additions are ratified
in `memory/project_artifact_bus_invariants.md`.

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

Repo layout (post 2026-05-03 rollout):

```
Magellon/
├── CoreService/                          # FastAPI, routers, plugin registry, job service
├── plugins/                              # External plugins (RabbitMQ consumers)
│   ├── magellon_ctf_plugin/
│   ├── magellon_motioncor_plugin/
│   ├── magellon_fft_plugin/              # reference / blueprint
│   ├── magellon_topaz_plugin/            # picking + denoise
│   ├── magellon_ptolemy_plugin/          # square + hole detection
│   ├── magellon_result_processor/        # legacy result writer (dormant; see §4.1 #19)
│   ├── magellon_stack_maker_plugin/      # NEW (Phase 5): PARTICLE_EXTRACTION
│   ├── magellon_can_classifier_plugin/   # NEW (Phase 7): TWO_D_CLASSIFICATION
│   └── magellon_template_picker_plugin/  # NEW (Phase 6): external PARTICLE_PICKING
├── magellon-sdk/         # magellon-sdk 2.0.0
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
exists in two places. Pre-2026-05-03 every task was image-keyed; the
**subject axis** (Phase 3) generalises that so aggregate-input tasks
(2D classification, future 3D refine) can live alongside.

- **SQLAlchemy (persistent):** `ImageJob`, `ImageJobTask`, plus three
  new tables added 2026-05-03 (alembic migrations 0004 / 0005 / 0006,
  not yet applied at the time of writing — see §11):
  - `image_job_task.subject_kind` (VARCHAR(32) NOT NULL DEFAULT
    `'image'`, per ratified rule 4 — VARCHAR not ENUM since the
    table is tens-of-millions of rows) and `subject_id` (UUID
    nullable). Allowed kinds:
    `image | particle_stack | session | run | artifact`. The
    migration backfills `subject_id = image_id` for every existing
    row, so image-keyed plugins keep working unchanged.
  - `artifact` table — typed bridge between a producing job/task
    and downstream consumers. STI shape: hot columns (`kind`,
    `producing_job_id`, `producing_task_id`, `msession_id`,
    `mrcs_path`, `star_path`, `particle_count`, `apix`, `box_size`)
    + long-tail `data_json`. Per ratified rule 6: immutable
    post-write; only `deleted_at` mutates. Two kinds today:
    `particle_stack` (extractor output) and `class_averages`
    (classifier output).
  - `pipeline_run` table — user-visible rollup over a sequence of
    `ImageJob`s (each algorithm step is its own job; PipelineRun
    groups them). `image_job.parent_run_id` FK is nullable so
    pre-Phase-8 jobs remain valid as standalone runs. Status enum
    mirrors `ImageJob.status_id`.

  Status enum from `controllers/import_controller.py:151`:
  1=pending, 2=running, 3=processing, 4=completed, 5=failed,
  6=cancelled.

- **Pydantic wire shapes:** `TaskBase`, `TaskMessage`, `JobMessage`,
  `TaskResultMessage` in `models/plugins_models.py` (re-exported from
  `magellon_sdk.models`). `data: Dict[str, Any]` is the per-task-type
  payload; concrete shapes are `CtfInput`, `MotionCorInput`, `FftInput`,
  `ParticleExtractionInput`, `TwoDClassificationInput`, etc. (Renamed
  from `*Dto` / `*TaskData` in SDK 2.0; see
  `Documentation/CATEGORIES_AND_BACKENDS.md` §4 and
  `magellon-sdk/CHANGELOG.md`.)

  Both `TaskMessage` and `TaskResultMessage` carry the **subject
  axis** (`subject_kind`, `subject_id`); see Phase 3b SDK round-trip.
  `magellon_sdk.models.artifact.Artifact` mirrors the `artifact`
  table 1:1 for the SDK-side (also Phase 4).

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

**Dead-code island — removed (A.1 follow-up, `7d1f657`).** The Temporal-era
scaffolding (~2K lines: `services/magellon_job_manager.py`,
`services/job_event_publisher.py`, `services/magellon_event_service.py`,
`services/event_logging_service.py`, `services/event_publisher.py`,
`activities/image_processing_activities.py`, `worker_{ctf,motioncor,thumbnail,all}.py`,
and `docs/architecture/{WORKFLOW,EVENT}_ARCHITECTURE.md`) was deleted
alongside the Temporal revert. Any new orchestrator adoption starts from
`magellon_sdk.executor.Executor` (surviving Protocol), not from these.

**Importer path uses `job_service` too** for `ImageJob`/`ImageJobTask` row
creation, and task state writes after dispatch now come back through the
in-process `TaskOutputProcessor` (P3, §4.1) which calls
`_advance_task_state` to update `status_id` + `stage` per result.

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

| Direction       | Queue                                       | Producer     | Consumer                            |
|-----------------|---------------------------------------------|--------------|-------------------------------------|
| Dispatch CTF    | `ctf_tasks_queue`                           | CoreService  | `magellon_ctf_plugin`               |
| Dispatch MC     | `motioncor_tasks_queue`                     | CoreService  | `magellon_motioncor_plugin`         |
| Dispatch FFT    | `fft_tasks_queue`                           | CoreService  | `magellon_fft_plugin`               |
| Dispatch Topaz pick   | `topaz_pick_tasks_queue`              | CoreService  | `magellon_topaz_plugin`             |
| Dispatch denoise      | `micrograph_denoise_tasks_queue`      | CoreService  | `magellon_topaz_plugin`             |
| Dispatch ptolemy      | `square_detection_tasks_queue` / `hole_detection_tasks_queue` | CoreService | `magellon_ptolemy_plugin` |
| **Dispatch extract**  | `particle_extraction_tasks_queue`     | CoreService  | `magellon_stack_maker_plugin` (NEW Phase 5) |
| **Dispatch 2D-class** | `two_d_classification_tasks_queue`    | CoreService  | `magellon_can_classifier_plugin` (NEW Phase 7) |
| **Dispatch picker (external)** | `particle_picking_tasks_queue` | CoreService | `magellon_template_picker_plugin` (NEW Phase 6) |
| Results (all)         | `<category>_out_tasks_queue`          | each plugin  | CoreService in-process consumer (P3) |
| Test bridge           | `motioncor_test_inqueue/out`          | Frontend     | MC plugin (test harness only)       |

Routing is now owned by `core/dispatcher_registry.py::get_task_dispatcher_registry()`
(MB3): `_BusTaskDispatcher` instances keyed by `TaskCategory` wrap each
task in a CloudEvents `Envelope` and send via `bus.tasks.send`. Adding a
task type is one `registry.register(...)` call. The legacy switch in
`get_queue_name_by_task_type` (`core/helper.py:75`) survives only as a
lookup helper for the on-disk audit log.

**Dispatch path.** Importers (`services/importers/{MagellonImporter,EPUImporter,SerialEmImporter,BaseImporter}.py`)
and the Leginon frame-transfer service build a `TaskMessage` and call
`dispatch_ctf_task` / `dispatch_motioncor_task` (`core/helper.py:147`
and `:349`). Both end at `push_task_to_task_queue` (`core/helper.py:106`)
which delegates to `get_task_dispatcher_registry().dispatch(task)`
(`core/dispatcher_registry.py`). The registry wraps the `TaskMessage`
in a CloudEvents `Envelope` and publishes via `bus.tasks.send` on the
RMQ-backed `MessageBus` (installed once at startup by
`install_core_bus()`, called from `main.py:367`). When the message
sets `target_backend`, the dispatcher's `BackendQueueResolver`
(`_live_backend_queue` in production) consults the
`PluginLivenessRegistry` and routes to the named backend's task
queue; missing backend raises `BackendNotLive` rather than falling
back. The on-disk audit log is still written to
`/magellon/messages/<queue>/messages.json` via `_audit_outgoing_message`
(`core/helper.py`), decoupled from the publish path. (Updated 2026-04-27:
X.1 added the backend-pin path. MB3 producer migration landed
2026-04-21; `RabbitmqClient` is no longer on the dispatch path.)

**Consumer pattern** (P5 — `magellon_sdk.runner.plugin_runner.PluginBrokerRunner`):
each plugin's `main.py` installs the RMQ bus (`install_rmq_bus(rmq)`)
and constructs one `PluginBrokerRunner`. The runner registers a
`bus.tasks.consumer` for its category route and hands deliveries to
`plugin.run(...)` on a single dedicated event loop
(`asyncio.run_coroutine_threadsafe`). Exceptions are classified via
`magellon_sdk.errors.classify_exception` into `AckAction.{ACK, NACK_REQUEUE, DLQ}`:
parse and unsupported-input errors route to DLQ, transient infra
errors requeue, plugin-domain errors ack with a failure result. No more
`asyncio.run` per message; no more silent poison-drop.

**Result processing — in-process (P3).** CoreService owns the result
writer: `CoreService/core/result_consumer.py` subscribes to each
category's result route and delegates to
`CoreService/services/task_output_processor.py::TaskOutputProcessor`.
On each result it:

1. Moves output files (CTF star files, MC MRCs) under
   `MAGELLON_HOME_DIR/<session>/<dir_name>/<image>/` (see `DATA_PLANE.md`).
2. Writes `ImageMetaData` rows keyed by `image_id`, with `category_id`
   distinguishing CTF (2) vs MotionCor (3).
3. Calls `_advance_task_state(...)` (P4) to set `ImageJobTask.status_id`
   (COMPLETED=2 / FAILED=3) and `stage` (MotionCor=1, CTF=2, square=3,
   hole=4, topaz=5, denoise=6, **extraction=7, classification=8**,
   unknown=99). Failures route through the same helper inside the
   error handler, so a plugin crash surfaces as `status_id=3` instead
   of a hung row.
4. **Phase 3c (2026-05-03):** `_advance_task_state` also backfills
   `ImageJobTask.subject_kind` / `subject_id` from the result when
   dispatch left them at the DDL default. Authoritative writes still
   come from dispatch — this is the back-compat seam for pre-Phase-3
   importers.
5. **Phase 5b/5c (2026-05-03):** for `PARTICLE_EXTRACTION` (code 10)
   results, `_maybe_write_artifact` writes a new `artifact` row of
   kind `'particle_stack'` and projects its id back into
   `output_data['particle_stack_id']`. For `TWO_D_CLASSIFICATION`
   (code 4) results, same shape with kind `'class_averages'` and
   `output_data['class_averages_id']`. Per ratified rule 6:
   re-runs always create a NEW row (no UPDATE).

The out-of-tree `magellon_result_processor` plugin **is still built
and started by default** (`Docker/docker-compose.yml:167`). Its
`main.py` also registers a `bus.tasks.consumer` per `OUT_QUEUES`
entry — and its `configs/settings_prod.yml:31–39` lists the same
`ctf_out_tasks_queue` + `motioncor_out_tasks_queue` CoreService
subscribes to. RabbitMQ round-robins deliveries between the two
consumers: ~50% of CTF and MotionCor results are projected by
CoreService's newer `TaskOutputProcessor` (with `_advance_task_state`),
~50% by the plugin container's older copy at
`plugins/magellon_result_processor/services/task_output_processor.py`.
FFT is unaffected — only CoreService lists `fft_out_tasks_queue`.
The intent per `CoreService/main.py:417–422` was either/or, not both;
the compose stack and plugin settings were never updated to enforce
that. Tracked as §8 #19 and resolution PR MB4.C in
`IMPLEMENTATION_PLAN.md`.

**Client visibility.** Live. External plugins emit
`magellon.step.*` CloudEvents via
`magellon_sdk.events.StepEventPublisher`; CoreService runs two
forwarders — `core/rmq_step_event_forwarder.py` and
`core/step_event_forwarder.py` (NATS) — which fan into
`JobEventWriter` and re-emit on Socket.IO. The React UI consumes one
Socket.IO stream whether the plugin ran in-process or in a container.

**Settings drift — mostly resolved (P7).** Runtime knobs flow through
`magellon.plugins.config.<category>` / `.broadcast` topic exchanges;
every `PluginBrokerRunner` ships a `ConfigSubscriber` that drains
pending updates between tasks and calls `plugin.configure(...)`.
Static per-plugin `settings_dev.yml` files still exist for boot-time
wiring (broker host, credentials); unification of that layer is
tracked as Track B PR G.3 (`PluginConfigResolver`) in
`IMPLEMENTATION_PLAN.md`.

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
8. The UI sees Socket.IO events for both paths now. External plugins
   emit `magellon.step.*` envelopes via
   `magellon_sdk.events.StepEventPublisher`; CoreService's step-event
   forwarder (`magellon_sdk/bus/services/step_event_forwarder.py`,
   relocated in MB5.4b) consumes them via `bus.events.subscribe` and
   emits `emit_step_event` onto the same Socket.IO channel the
   in-process plugin runtime uses. The React app sees one stream
   regardless of where the plugin ran.

---

## 6. Progress and event surface today

All progress flows converge on one Socket.IO channel. Three producers,
one consumer (the React app):

1. **In-process plugin runtime** — `plugins/progress.py::JobReporter`
   emits `emit_job_update` / `emit_log` via
   `core/socketio_server.py`. The React app subscribes per-`sid`.
   Unchanged since P5.

2. **External RMQ plugins (MB5.3 + MB5.4b)** — plugin's
   `magellon_sdk.events.StepEventPublisher` publishes each
   `magellon.step.*` envelope via `bus.events.publish(StepEventRoute,
   env)`. CoreService's step-event forwarder
   (`magellon_sdk.bus.services.step_event_forwarder`, relocated in
   MB5.4b) subscribes via `bus.events.subscribe(StepEventRoute.all(),
   handler)`. Handler writes a `job_event` row (idempotent on
   `event_id` UNIQUE) and schedules a Socket.IO `emit_step_event`
   via `asyncio.run_coroutine_threadsafe` against the asgi loop.

3. **NATS forwarder (pre-existing)** — when `NATS_STEP_EVENTS_STREAM`
   is configured, plugins fan out to NATS JetStream too; the NATS
   forwarder in CoreService (`core/step_event_forwarder.py`) runs
   the same handler chain. The `job_event.event_id` UNIQUE index
   makes cross-transport re-delivery a no-op, so RMQ + NATS can
   coexist without double-writes.

Pre-MB5.3 this section called out "external plugin progress is
invisible today." That gap is closed.

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

The dead-code island that the original revert left in the tree is
gone — see §3.3 (deleted in the A.1 follow-up, `7d1f657`).

---

## 8. Known limitations (with evidence)

| # | Problem | Evidence |
|---|---------|----------|
| 1 | ~~`ImageJobTask` state not advanced after RMQ task completion~~ | **Resolved (Phase 4).** `task_output_processor._advance_task_state` writes `status_id` + `stage` (MotionCor=1, CTF=2, square=3, hole=4, topaz=5, denoise=6, **extraction=7, classification=8** added 2026-05-03, unknown=99). 24 unit tests. |
| 2 | ~~No failure path from external plugin crashes~~ | **Resolved (P2 + P5).** `magellon_sdk.errors.classify_exception` returns `AckAction.{ACK,NACK_REQUEUE,DLQ}` per a typed taxonomy; `PluginBrokerRunner` honours it (DLQ for poison, requeue for transient, ack-with-failure-result for plugin-domain errors). |
| 3 | ~~No mid-flight progress for external plugins~~ | **Fully resolved (MB5.3 + MB5.4b).** `StepEventPublisher` publishes via `bus.events.publish(StepEventRoute, env)`; `magellon_sdk.bus.services.step_event_forwarder.StepEventForwarder` subscribes via `bus.events.subscribe(StepEventRoute.all(), handler)` and emits `emit_step_event` onto Socket.IO. React app consumes one stream regardless of plugin location. |
| 4 | Two plugin architectures | Same split (`plugins/` RMQ vs `CoreService/plugins/` in-process). The `TaskDispatcher` Protocol is the shared seam, and **`CategoryContract` (P1)** is the canonical input/output schema both halves resolve against — substitutability is now contract-pinned, not convention-pinned. **X.1 (2026-04-27)** added a `backend_id` axis under each category so two plugins serving one category (e.g. ctffind4 + gctf) are individually addressable via `TaskMessage.target_backend`. **2026-05-03 (Phase 6)** ships an external `template-picker` backend alongside the in-process `pp/template_picker`; both register against `PARTICLE_PICKING` and the dispatcher routes via `target_backend`. |
| 5 | ~~Temporal-era dead-code island (~2K lines)~~ | **Resolved (A.1 follow-up, `7d1f657`).** |
| 6 | ~~SDK scaffolded, thin~~ | **Filled in.** `magellon-sdk 2.0.0` (pyproject 1.2.0→2.0.0 fix landed 2026-05-03) ships `PluginBase`, `Envelope`, `Executor` Protocol, `ProgressReporter`, **`TaskDispatcher` + `TaskDispatcherRegistry` (Phase 6)**, **NATS transport** (`NatsPublisher`/`NatsConsumer`), **RMQ transport** (`RabbitmqClient` with `declare_queue_with_dlq`), **`events.StepEventPublisher`**, **per-category backend axis** (`PluginManifest.backend_id`, `TaskMessage.target_backend`, X.1), and (2026-05-03) the **active-task ContextVar + daemon-loop + step-reporter helpers** (`magellon_sdk.runner.active_task`) that every plugin used to hand-roll, plus the **subject axis** (`TaskMessage.subject_kind/subject_id`, `CategoryContract.subject_kind`), the **`Artifact`/`ArtifactKind`** Pydantic models, and the **`PARTICLE_EXTRACTION` + `TWO_D_CLASSIFICATION` contracts**. |
| 7 | ~~Duplicated `core/` across external plugins~~ | **Resolved (Phases B.1/B.2/B.3, `c90eefb`/`eda4933`/`f9a4511`).** |
| 8 | ~~Queue mapping hardcoded~~ | **Resolved (Phase 6 + wiring).** `core.dispatcher_registry.get_task_dispatcher_registry()` owns the `TaskCategory.code` → dispatcher mapping. `push_task_to_task_queue` delegates. `get_queue_name_by_task_type` remains for the audit helper. |
| 9 | ~~`asyncio.run` inside blocking pika callback~~ | **Resolved (Phase 3).** All 4 plugin consumer engines use one daemon-thread event loop + `asyncio.run_coroutine_threadsafe(...).result()`. |
| 10 | ~~Poison messages silently dropped~~ | **Resolved (P2).** `classify_exception` routes parse / validation / unsupported-input errors to DLQ explicitly, transient infra errors to requeue, and plugin-domain failures to an ack-with-failure-result. Existing queues still need the broker-policy migration before DLQ delivery actually fires for them. |
| 11 | ~~`rabbitmq_client.connect()` swallows errors~~ | **Resolved (Phase 3).** `RabbitmqClient.connect()` and `publish_message()` now re-raise `AMQPConnectionError` / `ChannelError`; `publish_message_to_queue` returns `False` instead of silent-dropping. |
| 12 | ~~Path coupling via shared filesystem~~ | **Reframed as architectural choice (2026-04-21).** `TaskOutputProcessor` assumes `MAGELLON_HOME_DIR` is a POSIX-shared namespace visible to CoreService and every plugin worker — this is the data plane and is intentional, not a gap. See `DATA_PLANE.md`. Object-storage-only deployments are an explicit non-goal. |
| 13 | ~~No CloudEvents / no envelope versioning~~ | **Resolved (Phase 2).** `magellon_sdk.envelope.Envelope[DataT]` is CloudEvents 1.0 compliant with `specversion`, `source`, `type`, `subject`, `time`, `datacontenttype`. Used by the NATS transport and the step-event publisher. |
| 14 | ~~No DLQ, no retry policy~~ | **DLQ fully scripted (MB6.4); retry policy still open.** `RabbitmqClient.declare_queue_with_dlq()` wires the args on new queues (2 integration tests). Existing queues are migrated via `CoreService/scripts/migrate_dlq_topology.py` per `Documentation/DLQ_MIGRATION_RUNBOOK.md` — production run is a scheduled ops event post-MB6.3 soak. Retry policy (per-category back-off) is still open. |
| 15 | ~~Settings drift per plugin~~ | **Mostly resolved (P7).** Runtime knobs now flow through `magellon.plugins.config.<category>` / `.broadcast` topic exchange; every `PluginBrokerRunner` ships a `ConfigSubscriber` that drains pending updates between tasks and calls `plugin.configure()`. Static per-plugin `settings_dev.yml` files still exist for boot-time wiring. |
| 16 | No operator hard-stop for runaway plugin work | **Resolved (P9).** `POST /cancellation/queues/purge` drains pending tasks from one or more category queues; `POST /cancellation/containers/{name}/kill` issues `docker kill` on a stuck plugin replica. Cooperative cancel via `JobManager.request_cancel` remains the in-flight path. |
| 17 | Broker-based discovery / liveness (replaces Consul) | **Landed (P6).** Plugins emit one `magellon.plugins.announce.*` on boot and a `magellon.plugins.heartbeat.*` every N seconds via `DiscoveryPublisher` + `HeartbeatLoop`. CoreService listens with `core.plugin_liveness_registry.start_liveness_listener` and exposes the registry to the plugin discovery endpoints. |
| 18 | Provenance on results | **Resolved (P4).** `PluginBrokerRunner` auto-injects plugin manifest (id, name, version, schema_version, container hostname, host) into every `TaskResultDto.provenance` after the result_factory builds the wire shape; CoreService records it for audit. |
| 19 | ~~Result-processor plugin double-consumes with in-process consumer~~ | **Resolved (MB4.C, `5827b8f`).** Blanked `OUT_QUEUES: []` in both plugin YAMLs (`settings_dev.yml` + `settings_prod.yml`). Plugin container now subscribes to nothing (logs `result_processor: OUT_QUEUES empty — staying dormant`); CoreService's in-process consumer is the sole writer. Container deletion and dir removal are deferred follow-ups once the plugin is confirmed unused for a release cycle. |
| 20 | ~~No cooperative cancel for external plugins~~ | **Resolved (G.1, `6663d23`).** New `CancelRoute.for_job(<id>)` + `CancelRegistry` + `start_cancel_listener(bus)` in `magellon_sdk.bus.services.cancel_registry`. `PluginBrokerRunner` subscribes on startup; `BoundStepReporter.started/progress` checks the registry and raises `JobCancelledError`. Runner catches the raise and publishes a FAILED-status result with `output_data["cancelled"]=True`. `JobManager.request_cancel` publishes the cancel event alongside the in-process flag. Plugins that emit step events (all four today) get cooperative cancel with no code change. |
| 21 | ~~No contract test between CoreService and external plugin containers~~ | **Resolved (G.2, `59b420c`).** `CoreService/tests/contracts/` package with per-plugin test modules for CTF, MotionCor, FFT. Each hits the plugin's HTTP `/execute` endpoint with a canned `TaskDto` (missing-file input → clean failure) and asserts `task_id`/`job_id` echo + `TaskResultDto` shape round-trip. Bypasses RMQ to avoid racing CoreService's in-process result consumer. Tests skip cleanly with an actionable message when the plugin container isn't up. Closes the §9 "no contract test" gap. |
| 22 | ~~Fragmented plugin config surface (YAML + env + bus push + CategoryContract defaults)~~ | **Resolved (G.3, `50deb25`).** `magellon_sdk.config.PluginConfigResolver` layers the four surfaces under one `get(key)` API with documented precedence (runtime overrides > env > YAML > defaults). Typed accessors (`get_bool`/`get_int`/`get_float`/`get_str`) log-and-default on garbage. Per-plugin migration to use the resolver is per-plugin follow-up; the class contract is frozen by 26 unit tests. |
| 23 | ~~Synchronous import handler ties up HTTP worker on large sessions~~ | **Resolved (G.4, `2de2449`).** `POST /magellon-import` returns a scheduled `job_id` immediately; `MagellonImporter.process()` runs in FastAPI `BackgroundTasks` with its own DB session. `BaseImporter.pre_assigned_job_id` attribute threads the id so the endpoint's response matches the row the BG task eventually inserts. |
| 24 | ~~ContextVar / daemon-loop / step-reporter helpers duplicated across every external plugin~~ | **Resolved (Phase 1, `c89b1cd` + `8336793` + `611ae98`, 2026-05-03).** Promoted into `magellon_sdk.runner.active_task` (`current_task`, `set_active_task`, `reset_active_task`, `get_step_event_loop`, `emit_step`, `make_step_reporter`). `PluginBrokerRunner` sets the ContextVar in `_handle_task` / `_process` for every plugin. ~280 lines of duplication deleted across FFT/topaz/CTF/MotionCor/ptolemy. Back-compat shims (`<Plugin>BrokerRunner` aliased to `PluginBrokerRunner`, `get_active_task` to `current_task`) preserve old import paths for one release. |
| 25 | ~~Tasks cannot represent aggregate-input work (2D classification, 3D refine)~~ | **Resolved (Phase 3 + 3b + 3c + 3d, 2026-05-03).** Subject axis added end-to-end: `image_job_task.subject_kind` (VARCHAR(32) DEFAULT `'image'`) + `subject_id` (UUID nullable) via alembic 0004; `TaskMessage` + `TaskResultMessage` carry both fields; `PluginBrokerRunner._stamp_subject` echoes them onto results; `TaskOutputProcessor` backfills the row when dispatch left them at the DDL default; `CategoryContract.subject_kind` (default `'image'`, `TWO_D_CLASSIFICATION_CATEGORY` overrides to `'particle_stack'`) provides the declarative seam so pre-Phase-3 dispatchers automatically pick up the right subject. Authoritative writes still come from dispatch — backfill is the back-compat seam. |
| 26 | ~~No typed bridge between producing and consuming jobs~~ | **Resolved (Phase 4 + 5b, 2026-05-03).** New `artifact` table (alembic 0005) with promoted hot columns + `data_json` long-tail. Per ratified rule 6: immutable; only `deleted_at` mutates. SDK ships `Artifact`/`ArtifactKind` Pydantic models. `TaskOutputProcessor._maybe_write_artifact` writes `particle_stack` rows for `PARTICLE_EXTRACTION` results and `class_averages` rows for `TWO_D_CLASSIFICATION` results, projecting the new id back into `output_data` for downstream addressability. 9 unit tests pin the writer + lineage shape. |
| 27 | ~~No user-visible rollup over the picker → extractor → classifier pipeline~~ | **Resolved (Phase 8 + 8b, 2026-05-03).** New `pipeline_run` table (alembic 0006) with `image_job.parent_run_id` FK. Each algorithm step stays its own `ImageJob`; `PipelineRun` groups them. ORM `PipelineRun` class + 10 ORM tests. HTTP CRUD at `/pipelines/runs` (POST create / GET detail / GET list with bulk job-count / DELETE soft-delete) + 11 controller tests. Per rule 6 no PUT — runs are immutable; status flips authoritatively when child jobs transition. |

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

## 12. Extraction + classification rollout (2026-05-03)

17 commits added two new categories end-to-end plus the architectural
plumbing they need (subject axis, Artifact entity, PipelineRun
rollup), absorbed five plugins' duplicated runner glue into the SDK,
and shipped HTTP CRUD for the rollup. ~610 tests passing across
SDK + 8 plugins + CoreService. Each row is one or two commits; full
narrative in `memory/project_extraction_classification_rollout.md`.

| Phase | Commits          | What it delivered                                                                 |
|-------|------------------|-----------------------------------------------------------------------------------|
| 0/1/2 | `c89b1cd`        | SDK 1.2.0 → 2.0.0 pyproject; `PluginBrokerRunner` absorbs ContextVar + daemon-loop + step-reporter; FFT plugin migrated as proof + tidied (lifespan, drop matplotlib, 500-not-400, height in engine_opts). |
| 1b    | `8336793` `611ae98` | Topaz / CTF / MotionCor / ptolemy migrated off per-plugin boilerplate. Lazy compute imports for topaz/motioncor/ptolemy so contract tests run without onnxruntime / cv2. |
| 1c    | `8c1fd66`        | Plugin contract tests for CTF / MotionCor / ptolemy mirroring FFT/topaz pattern. |
| 3     | `5fb2af0`        | Subject axis SDK side: `TaskMessage.subject_kind/subject_id` + alembic 0004 (`image_job_task.subject_kind` VARCHAR(32) DEFAULT `'image'` + `subject_id` UUID, backfill `subject_id = image_id`). |
| 3b    | `99f885c`        | `TaskResultMessage` carries the same fields; `PluginBrokerRunner._stamp_subject` echoes from task to result. |
| 3c    | `cc2631e`        | `TaskOutputProcessor._advance_task_state` backfills the row when dispatch left columns at default. |
| 3d    | `deb0ca8`        | `CategoryContract.subject_kind` (default `'image'`; TWO_D_CLASSIFICATION → `'particle_stack'`); runner falls back to it when neither task nor plugin specified. |
| 4     | `5fb2af0`        | `Artifact` entity SDK side + alembic 0005. STI shape per rule 2.                  |
| 4b/5b | `11f5465`        | `Artifact` ORM class + `TaskOutputProcessor._maybe_write_artifact` for both new categories. |
| 5     | `d07d27c`        | `magellon_stack_maker_plugin` (PARTICLE_EXTRACTION code 10, backend_id `stack-maker`); algorithm vendored from Sandbox with the two RELION integration bugs fixed. |
| 6     | `8513666`        | `magellon_template_picker_plugin` (PARTICLE_PICKING external backend `template-picker`); coexists with the in-process picker. |
| 7     | `d07d27c`        | `magellon_can_classifier_plugin` scaffold (TWO_D_CLASSIFICATION code 4, backend_id `can-classifier`). |
| 7b    | `f8e84fa`        | Vendored 1714-line CAN algorithm into `plugin/algorithm/`; full STAR-aware orchestration in `compute.py`. Lazy torch import keeps contract tests fast. |
| 7c    | `6d50ca6`        | Synthetic-stack e2e test (skipif-torch). 4-particle / 32px box / 2 classes / 1 iter, runs in <30s on CPU torch. |
| 8     | `66e101f`        | `pipeline_run` table (alembic 0006) + ORM `PipelineRun` + `image_job.parent_run_id` FK. |
| 8b    | `c50a3c6`        | HTTP CRUD at `/pipelines/runs`. 11 controller tests with mocked SQLAlchemy session. |
| polish| `9f1ca8b`        | Drop topaz inline picks (rule 1 enforcement); remove stale 1.2.0 wheels + leftover `output_file.json`s; add `.gitignore` to 5 plugins; CHANGELOG entry. |

Net effect for users: the picker → extractor → classifier pipeline
is deployable end-to-end. The frontend caller and the
dispatch-side glue (POST endpoints that target the new categories
and chain them via PipelineRun) are the next deliverables.

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

(see also §12 below — the 2026-05-03 rollout adds three plugins, the
subject axis, Artifact entity, and PipelineRun rollup.)


- **`ARCHITECTURE_PRINCIPLES.md`** — the canonical rule-set every
  non-trivial PR in Magellon is reviewed against. Read this first.
- **`DATA_PLANE.md`** — the shared-filesystem decision, the deployment
  matrix, and what the platform forecloses on (object-storage-only).
- **`CATEGORIES_AND_BACKENDS.md`** — backend layer under every
  `TaskCategory`, the consolidated `GET /plugins/capabilities`
  endpoint, and the `Envelope` / `Message` wire-shape naming rule.
  Track C shipped 2026-04-27. Updated 2026-05-03 with the new
  categories (PARTICLE_EXTRACTION, TWO_D_CLASSIFICATION) and the
  `subject_kind` field.
- **`memory/project_artifact_bus_invariants.md`** — five ratified
  rules + two refinements driving the 2026-05-03 rollout: bus
  carries refs + summaries only; Artifact STI with hot columns;
  artifact lineage is the DAG; VARCHAR not ENUM; immutability;
  per-mic extraction default.
- **`memory/project_extraction_classification_rollout.md`** —
  full 17-commit narrative.
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
