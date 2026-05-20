# Magellon — Architecture Reference

**Status:** Consolidated reference manual. Merged from nine source documents on 2026-05-13.
**Audience:** Architects, plugin developers, reviewers, operators wanting the full picture.
**Companion:** `PLUGINS.md` (plugin model), `SECURITY.md` (authz / RLS), `OPERATIONS.md` (runbooks).

This is the single source of truth for how Magellon works today. It carries
the canonical principles, the as-is architecture, the data + control plane
contracts, the messaging conventions, the category + backend model, the
cryo-EM workflow narrative, and the in-flight roadmap. Every word is
verbatim from its origin doc; section provenance is noted at the top of
each block.

## Contents

1. [Architecture Principles](#1-architecture-principles)
2. [Current Architecture (as-is)](#2-current-architecture-as-is)
3. [Data Plane — Shared Filesystem](#3-data-plane--shared-filesystem)
4. [Message Bus — Specification](#4-message-bus--specification)
5. [Broker Patterns](#5-broker-patterns)
6. [Messages and Events](#6-messages-and-events)
7. [Categories and Backends](#7-categories-and-backends)
8. [CryoEM Pipeline Walk-through](#8-cryoem-pipeline-walk-through)
9. [Roadmap — Implementation Plan](#9-roadmap--implementation-plan)
10. [Roadmap — Unified Platform Plan](#10-roadmap--unified-platform-plan)
11. [Roadmap — Pipeline Ergonomics Plan](#11-roadmap--pipeline-ergonomics-plan)
12. [Roadmap — Pipeline Ergonomics First Slice](#12-roadmap--pipeline-ergonomics-first-slice)

---

<!--
  Section: 1. Architecture Principles
  Originated from: Documentation/ARCHITECTURE_PRINCIPLES.md
  Merged into this consolidated reference 2026-05-13.
-->

# Magellon — Architectural Principles

**Status:** Canonical as of 2026-04-21.
**Audience:** Reviewers, architects, plugin developers.
**Companion docs:** `CURRENT_ARCHITECTURE.md`, `DATA_PLANE.md`, `IMPLEMENTATION_PLAN.md`.

This document is the short list of principles every non-trivial PR is
reviewed against. It is deliberately terse — if a principle needs a page
of nuance, it belongs in its own doc (like `DATA_PLANE.md`), not here.

The principles are derived from operational experience of the P1–P9
plugin platform refactor (2026-04-15) and the MessageBus migration
specified in `MESSAGE_BUS_SPEC.md` (Track A, shipped 2026-04-21).
Each rule below names a live call site or a past incident that
motivated it.

---

## 1. Two planes, clearly separated

**Rule.** Metadata flows on the bus (control plane). Bytes flow on the
shared filesystem (data plane). The bus carries path references to
files the data plane makes real.

**Why.** Cryo-EM payloads are GB-scale. Routing micrographs through
a broker would blow past envelope limits, defeat broker durability,
and double the I/O cost. Every mature platform in this domain
(CryoSPARC, Relion, Scipion) assumes a shared filesystem.

**How to apply.** Any PR that proposes serializing image data through
the bus (`TaskDto.data`, `TaskResultDto`, event payload) is rejected;
carry a path reference instead. Any PR that proposes reading or
writing image data from somewhere other than `MAGELLON_HOME_DIR`
needs a design doc. See `DATA_PLANE.md`.

---

## 2. One logical owner per concept

**Rule.** One row of truth per job (`services/job_service.py`). One
bus API (`magellon_sdk.bus`). One envelope (`Envelope[T]`). One
progress seam (`ProgressReporter`). No shadow implementations.

**Why.** The three-job-manager split (Dragonfly `job_manager.py`,
Temporal `temporal_job_manager.py`, live `job_service.py`) was the
single worst class of bug Magellon has shipped: races between
writers, conflicting status enums, lost progress. The platform
refactor collapsed it to one live path; the dead managers were
deleted in A.1 (`7d1f657`).

**How to apply.** Before introducing a new class, check whether an
existing one owns the concept. If two classes exist and you can't
name which is authoritative, that's the PR to open — collapse them —
not the PR you're writing.

---

## 3. Layer boundaries are lint-enforced, not guideline-enforced

**Rule.** When you declare an abstraction layer, ship a linter rule
that fails CI on a violation. Guidelines alone decay.

**Why.** The MB plan's L1 → L2 → L3 → L4 layering is worth what the
lint rule enforces and nothing more. MB6.3's rule (`pika` imports
forbidden outside `bus/binders/rmq/`) is the enforceable version.
Without it, one careless PR re-couples the call-site code to the
transport and the abstraction silently regresses.

**How to apply.** Same pattern for the two planes: once an artifact
resolver exists, forbid direct `MAGELLON_HOME_DIR` / `shutil.move`
calls outside it. Same for Socket.IO: once Phase C.1 lands, forbid
`sio.emit` outside `JobService`. Write the ruff or grep rule in the
same PR as the abstraction; don't defer.

---

## 4. Every abstraction pays its way today

**Rule.** Abstractions are justified by present-day call-site
consolidation, not by hypothetical future flexibility.

**Why.** The Temporal revert (`86fe9cc`, 2026-04-14) is the
cautionary tale: an orchestrator adopted for a workflow story that
had no concrete consumer. The MessageBus spec, by contrast, is
justified on the 16 present-day call sites it collapses (spec §1.2)
— not on the hypothetical NATS / SQS binder (MB7, explicitly
deferred).

**How to apply.** A PR proposing a Protocol, SPI, or plugin point
must name the call sites that collapse onto it today. "So we can
swap X later" without a named customer is not sufficient
justification.

---

## 5. Contracts are versioned and tested

**Rule.** Every wire contract (envelope, plugin I/O, event schema)
carries an explicit schema version and has a golden test pinning its
bytes-on-the-wire shape.

**Why.** Silent schema drift is the bug class that motivated the
Phase 0 characterization tests. CloudEvents `specversion`,
`PluginInfo.schema_version`, and `CategoryContract` are the three
layers of versioning the platform already enforces. Golden tests
under `CoreService/tests/characterization/` keep them honest.

**How to apply.** A PR that changes a Pydantic model on the wire, a
bus route subject, or a plugin's `schema_version` must update the
golden test in the same PR. Reviewer rejects if the golden file is
untouched.

---

## 6. Additive first, subtractive second

**Rule.** The add-new-path PR and the delete-old-path PR are always
separate. Every phase ships reversible-by-`git revert` until the
legacy path is empirically safe to remove.

**Why.** The MessageBus plan's MB3 → MB6 ordering is the template:
producers migrate first (smallest blast radius), consumers next,
operator primitives last, DLQ topology migration only after the rest
has soaked in production for a week. Every step is `git revert`-safe
except the DLQ migration, and that one has a runbook.

**How to apply.** A PR titled "refactor X, remove Y" is split into
two. The first lands and soaks; the second follows. Reviewer rejects
dual-purpose PRs. Exception: pure renames with no semantic change
can land atomically.

---

## 7. Operator surface is first-class

**Rule.** Every subsystem ships with documented answers to: how do I
observe it, how do I drain it, how do I recover it?

**Why.** P9 (queue purge + container kill) and the DLQ migration
runbook (`DLQ_MIGRATION_RUNBOOK.md`) set the bar.
Subsystems without this surface are the ones that page operators at
3 AM with no tools.

**How to apply.** A PR introducing a new subsystem (a new consumer,
a new event stream, a new integration) must include: (a) a
healthcheck or status endpoint, (b) a documented way to drain or
purge its queue / stream, (c) a runbook entry or log keywords that
point an operator at the problem.

---

## Meta: when to update this document

Update this file when:

- A new principle survives three PR reviews (you found yourself
  writing the same comment three times — that's a principle).
- A principle turns out wrong in practice. Delete it, don't soften
  it — a principle that's sometimes-true is just noise.
- A principle's motivating evidence is superseded (e.g., the MB
  work lands and the "two planes" principle inherits new examples).

Do *not* add principles here speculatively. Every rule is justified
by a concrete incident, commit, or named call site.


---

<!--
  Section: 2. Current Architecture (as-is)
  Originated from: Documentation/CURRENT_ARCHITECTURE.md
  Merged into this consolidated reference 2026-05-13.
-->

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
│   ├── magellon_boxnet_plugin/           # BoxNet particle picking
│   ├── magellon_stack_maker_plugin/      # Phase 5: PARTICLE_EXTRACTION
│   ├── magellon_can_classifier_plugin/   # Phase 7: TWO_D_CLASSIFICATION
│   └── magellon_template_picker_plugin/  # Phase 6: external PARTICLE_PICKING
│   # magellon_result_processor was deleted (A.4); CoreService's
│   # in-process TaskOutputProcessor is the sole result writer.
├── magellon-sdk/         # magellon-sdk 2.4.0 (subject-tag dispatch gate, PE1-B, 2026-05-11)
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

### 3.4 Plugin metadata surface

The in-process plugin **registry** (`plugins/registry.py`, walked
`plugins.*` and instantiated `PluginBase` subclasses) was deleted
2026-05-04 with the rest of Architecture B (see §4.2). Plugins no
longer live inside CoreService.

CoreService now surfaces plugin metadata through two complementary
read endpoints, both served by `plugins/controller.py`:

- `GET /plugins/` (`controller.py:329`) — live announce/heartbeat
  view, populated by `core/plugin_liveness_registry.py` from
  `magellon.plugins.announce.*` + `heartbeat.*`. Empty when nothing
  is currently running.
- `GET /plugins/db` (`controller.py:381`) — DB-cataloged view of
  every plugin ever installed/discovered, including offline ones.
  This is what the **React plugins page** reads first
  (`InstalledPluginsView`); the live view is layered on top via
  per-plugin `GET /plugins/{id}/status` polls.

The consolidated catalog (`GET /plugins/capabilities`,
`controller.py:217`) joins the two and adds per-category input/output
JSON schemas + the operator-pinned default. See §4 for the full
HTTP surface.

**Dual `plugin_id` axes.** The system keys plugin records on two
distinct identifier spaces and the React UI threads both:

- `plugin_id` — the announce-derived runtime identifier. Comes from
  `magellon.plugins.announce.*` envelopes; rotates per replica scale
  event. The bus dispatcher / liveness registry / `/plugins/*`
  HTTP surface key on this. Format: free-form, plugin's choice.
- `manifest_plugin_id` — the install-time identifier from
  `manifest.yaml`. The install pipeline (`/admin/plugins/*`),
  `install_state.json`, and the upgrade/uninstall flow key on this.
  Format: manifest-validated slug `[a-z0-9._-]+`.

Most operator actions (Start / Stop / Restart / Pause / Scale /
Uninstall / Upgrade) flow through admin endpoints and need
`manifest_plugin_id`; the live status chip cluster reads the bus
view and needs `plugin_id`. The React `InstalledPluginsView` row
carries both fields and dispatches to each endpoint with the
matching key — never assume they're the same string.

**Schema flow — three tiers, ordered (PE2-UI + 2026-05-13).** The
runner page reads each plugin's input/output JSON schema via
`GET /plugins/{id}/schema/input` (and `/output`). The endpoint
resolves through three tiers in order:

1. **Live registry** — when the plugin is currently announcing,
   `Announce.input_schema` carries the dict produced by
   `cls.input_schema().model_json_schema()` (SDK side, in
   `magellon_sdk/runner/lifecycle.py`). The in-memory
   `PluginLivenessEntry.input_schema` is the source of truth while
   the plugin's heartbeat is fresh.
2. **DB row** — `record_announce` mirrors the announced schema
   into `Plugin.manifest_json["input_schema"]` /
   `["output_schema"]`. Survives a CoreService restart and the
   gap before the next plugin announce (plugins announce
   once-per-container-boot, not per-CoreService-boot — so without
   this tier, every CoreService restart blanks every plugin's
   schema until each plugin container is also bounced).
3. **Category contract fallback** — `contract.input_model`'s
   `model_json_schema()`. This is the minimum every backend in
   the category satisfies (e.g. `CryoEmImageInput` for image-keyed
   categories). Used when no plugin has ever announced for this
   plugin_id — typically a first-deploy or a plugin that predates
   PE2-UI.

Pre-PE2-UI plugins (announce envelopes without the schema field)
land on tier 3 and stay there forever, by design. Post-PE2-UI
plugins update tier 2 the first time they announce, so subsequent
CoreService restarts read straight from the DB until the next
announce comes in to refresh.

---

## 4. Plugin architecture

**2026-05-04 update (PI-5/PI-6 + PT-1..PT-6).** Architecture B (in-process
`PluginBase` + registry inside CoreService) is **retired**. Every plugin
in the system is now an external broker plugin under `Magellon/plugins/`,
running as its own FastAPI host with a `PluginBrokerRunner` consuming
from RMQ. Each plugin can opt into a sync HTTP surface via
**capabilities**:

- `Capability.SYNC` — plugin exposes `POST /execute` (the SDK's
  `make_sync_router(plugin)` mounts it from the same FastAPI app
  that hosts the bus consumer).
- `Capability.PREVIEW` — plugin exposes `POST /preview`,
  `POST /preview/{id}/retune`, `DELETE /preview/{id}` for the
  interactive preview-and-retune loop. Useful when a UI feature
  needs sub-second response (the picker's threshold slider) and
  RMQ round-trip is too expensive.

CoreService routes sync calls via `services/sync_dispatcher.py`.
Resolution priority (mirrors the bus dispatcher):

1. `instance_id` pin — sticky preview routing (R1 #1, R2 #3 fix).
   `POST /preview` remembers which replica answered; subsequent
   `retune`/`delete` for the same `preview_id` go to the same
   replica because the score-map cache lives there. With one
   replica everything works; with N replicas, this prevents
   slider ticks from 404-ing on cache miss.
2. `target_backend` pin (caller asked for a specific backend).
3. Operator-pinned per-category default (`PluginCategoryDefault`
   from PM1) — *iff* the default advertises the capability AND
   is enabled. Fall through to step 4 otherwise. (R1 #2 fix:
   pre-fix this was a hard return that raised
   `CapabilityMissing` on a default-with-SYNC-but-not-PREVIEW
   instead of trying a sibling backend.)
4. First live, **enabled** plugin advertising the capability.
   Disabled plugins (operator hit `/disable`) are skipped — same
   behaviour the bus dispatcher has long had; the sync path used
   to silently route to them. (R2 #1 fix.)

Connection management (R1 #3): a module-level pooled `httpx.Client`
with `max_keepalive_connections=20` keeps TCP connections warm
across calls. Per-call timeouts via `request(timeout=...)`:
retune ≤5s, preview ≤30s, run ≤60s.

Two HTTP surfaces consume the dispatcher:

- **Feature-named** routes for categories that need CoreService-side
  orchestration (DB persistence, batch loops, COCO export):
  `/particle-picking/preview`, `/particle-picking/run-and-save`, etc.
  Particle picking is the canonical example.
- **Generic** `/dispatch/{category}/...`. Two flavours:
  - `/dispatch/{category}/run` accepts `Dict[str, Any]` — works
    for any category, including ones that haven't pinned a
    Pydantic input model yet.
  - `/dispatch/v1/{category_slug}/run` is per-CategoryContract,
    typed by the category's `input_model` so OpenAPI / `/docs`
    shows real schemas. Registered at app import by walking
    `CATEGORIES`.

`GET /dispatch/capabilities` returns a per-category map of
`{supports_sync, supports_preview, live_plugin_id, http_endpoint,
enabled}` so the React UI can show/hide controls without
round-tripping. `supports_*` flips False when the default plugin
is disabled even if it's live + capable + has an endpoint.

The plugin's announce envelope carries an `http_endpoint`
(`AnyHttpUrl`-validated, R1 minor 2). The install pipeline
allocates the port at install time (R2 #4):

- Range defaults to `[18000, 18999]`; override via
  `MAGELLON_PLUGIN_PORT_MIN/MAX` env.
- Persistent assignment file at
  `<plugins_dir>/.port_assignments.json` survives CoreService
  restarts. The plugin's URL is stable across the lifetime of
  the install.
- `UvInstaller` writes `MAGELLON_PLUGIN_HTTP_ENDPOINT/_HOST/_PORT`
  into `runtime.env` (loaded by the systemd unit's
  `EnvironmentFile=`).
- `DockerInstaller` passes `-p <host_port>:<container_port>`
  plus the matching `-e` env vars.
- Both installers release the port on uninstall.

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

The out-of-tree `magellon_result_processor` plugin **has been
deleted** (A.4). MB4.C first made it dormant by blanking its
`OUT_QUEUES`, leaving the plugin built-but-idle; A.4 then removed the
plugin directory and its `docker-compose.yml` service outright.
CoreService's in-process `TaskOutputProcessor` is the sole result
writer for every category — there is no longer a second consumer to
race on `ctf_out_tasks_queue` / `motioncor_out_tasks_queue`.

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

### 4.2 ~~Architecture B — in-process `PluginBase` + registry~~ — RETIRED

**Removed 2026-05-04 (PI-5/PI-6 + PI-6.1).** The in-process plugin
runtime that lived under `CoreService/plugins/` (PluginBase, the
filesystem walk that auto-discovered service.py files, the
`/plugins/{id}/jobs` HTTP surface that ran `plugin.run()` in an
executor) is gone. The last in-process plugin
(`pp/template-picker`) became a plain particle-picking feature
controller that delegates compute to the external
`magellon_template_picker_plugin` over the sync transport. See
the rollout narrative in
`memory/project_extraction_classification_rollout.md` and the
PI-* / PT-* commits 2026-05-03..05-04.

What survived from the old `plugins/` namespace:
- `plugins/progress.py` — `JobReporter` + `JobCancelledError` are
  used by the particle-picking controller and any future feature
  controller for the Socket.IO progress path. Not plugin-runtime
  code anymore; just CoreService progress utilities that happen
  to live there.
- `plugins/controller.py` — the plugin-manager HTTP surface
  (`/plugins/`, `/plugins/db`, `/plugins/{id}/status`, etc.).
  The `/plugins/{id}/jobs` route now dispatches purely via the
  bus (no in-process branch).

### 4.3 Capability layer (PT-1..PT-6)

The single architecture is **Architecture A** with a capability-
based opt-in for sync HTTP. CoreService's `services/sync_dispatcher.py`
routes calls to a plugin's `http_endpoint` based on what the plugin
declared. Because the SDK's `make_sync_router` / `make_preview_router`
helpers wire the contract endpoints, the plugin author writes
`execute_sync()` / `preview()` / `retune()` once and gets the right
URLs for free.

Categories that need richer feature controllers (DB persistence,
batch loops, etc.) keep their feature-named URLs
(`/particle-picking/*`); the rest reach the generic
`/dispatch/{category}/*`. Both share one dispatcher.

The bus path (RMQ for batch / async / step-event-emitting work)
stays the canonical transport. Sync is purely additive — a plugin
can serve both transports from one FastAPI app.

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
7. CoreService's in-process `TaskOutputProcessor` consumes both
   out-queues, moves output files, writes `ImageMetaData`, and advances
   `ImageJobTask.status_id` + `stage` via `_advance_task_state`.
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
| 6 | ~~SDK scaffolded, thin~~ | **Filled in.** `magellon-sdk 2.4.0` (2.0.0 baseline 2026-05-03 → 2.2.0 capability layer 2026-05-04 → 2.3.0 → 2.4.0 subject-tag dispatch gate 2026-05-11) ships `PluginBase`, `Envelope`, `Executor` Protocol, `ProgressReporter`, **`TaskDispatcher` + `TaskDispatcherRegistry` (Phase 6)**, **NATS transport** (`NatsPublisher`/`NatsConsumer`), **RMQ transport** (`RabbitmqClient` with `declare_queue_with_dlq`), **`events.StepEventPublisher`**, **per-category backend axis** (`PluginManifest.backend_id`, `TaskMessage.target_backend`, X.1), and (2026-05-03) the **active-task ContextVar + daemon-loop + step-reporter helpers** (`magellon_sdk.runner.active_task`) that every plugin used to hand-roll, plus the **subject axis** (`TaskMessage.subject_kind/subject_id`, `CategoryContract.subject_kind`), the **`Artifact`/`ArtifactKind`** Pydantic models, and the **`PARTICLE_EXTRACTION` + `TWO_D_CLASSIFICATION` contracts**. |
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
| 19 | ~~Result-processor plugin double-consumes with in-process consumer~~ | **Resolved (MB4.C `5827b8f`; plugin deleted A.4).** MB4.C blanked `OUT_QUEUES: []` in both plugin YAMLs so the container stayed dormant; A.4 then deleted the `magellon_result_processor` plugin directory and its `docker-compose.yml` service entirely. CoreService's in-process `TaskOutputProcessor` is the sole result writer — no second consumer exists. |
| 20 | ~~No cooperative cancel for external plugins~~ | **Resolved (G.1, `6663d23`).** New `CancelRoute.for_job(<id>)` + `CancelRegistry` + `start_cancel_listener(bus)` in `magellon_sdk.bus.services.cancel_registry`. `PluginBrokerRunner` subscribes on startup; `BoundStepReporter.started/progress` checks the registry and raises `JobCancelledError`. Runner catches the raise and publishes a FAILED-status result with `output_data["cancelled"]=True`. `JobManager.request_cancel` publishes the cancel event alongside the in-process flag. Plugins that emit step events (all four today) get cooperative cancel with no code change. |
| 21 | ~~No contract test between CoreService and external plugin containers~~ | **Resolved (G.2, `59b420c`).** `CoreService/tests/contracts/` package with per-plugin test modules for CTF, MotionCor, FFT. Each hits the plugin's HTTP `/execute` endpoint with a canned `TaskDto` (missing-file input → clean failure) and asserts `task_id`/`job_id` echo + `TaskResultDto` shape round-trip. Bypasses RMQ to avoid racing CoreService's in-process result consumer. Tests skip cleanly with an actionable message when the plugin container isn't up. Closes the §9 "no contract test" gap. |
| 22 | ~~Fragmented plugin config surface (YAML + env + bus push + CategoryContract defaults)~~ | **Resolved (G.3, `50deb25`).** `magellon_sdk.config.PluginConfigResolver` layers the four surfaces under one `get(key)` API with documented precedence (runtime overrides > env > YAML > defaults). Typed accessors (`get_bool`/`get_int`/`get_float`/`get_str`) log-and-default on garbage. Per-plugin migration to use the resolver is per-plugin follow-up; the class contract is frozen by 26 unit tests. |
| 23 | ~~Synchronous import handler ties up HTTP worker on large sessions~~ | **Resolved (G.4, `2de2449`).** `POST /magellon-import` returns a scheduled `job_id` immediately; `MagellonImporter.process()` runs in FastAPI `BackgroundTasks` with its own DB session. `BaseImporter.pre_assigned_job_id` attribute threads the id so the endpoint's response matches the row the BG task eventually inserts. |
| 24 | ~~ContextVar / daemon-loop / step-reporter helpers duplicated across every external plugin~~ | **Resolved (Phase 1, `c89b1cd` + `8336793` + `611ae98`, 2026-05-03).** Promoted into `magellon_sdk.runner.active_task` (`current_task`, `set_active_task`, `reset_active_task`, `get_step_event_loop`, `emit_step`, `make_step_reporter`). `PluginBrokerRunner` sets the ContextVar in `_handle_task` / `_process` for every plugin. ~280 lines of duplication deleted across FFT/topaz/CTF/MotionCor/ptolemy. Back-compat shims (`<Plugin>BrokerRunner` aliased to `PluginBrokerRunner`, `get_active_task` to `current_task`) preserve old import paths for one release. |
| 25 | ~~Tasks cannot represent aggregate-input work (2D classification, 3D refine)~~ | **Resolved (Phase 3 + 3b + 3c + 3d, 2026-05-03).** Subject axis added end-to-end: `image_job_task.subject_kind` (VARCHAR(32) DEFAULT `'image'`) + `subject_id` (UUID nullable) via alembic 0004; `TaskMessage` + `TaskResultMessage` carry both fields; `PluginBrokerRunner._stamp_subject` echoes them onto results; `TaskOutputProcessor` backfills the row when dispatch left them at the DDL default; `CategoryContract.subject_kind` (default `'image'`, `TWO_D_CLASSIFICATION_CATEGORY` overrides to `'particle_stack'`) provides the declarative seam so pre-Phase-3 dispatchers automatically pick up the right subject. Authoritative writes still come from dispatch — backfill is the back-compat seam. |
| 26 | ~~No typed bridge between producing and consuming jobs~~ | **Resolved (Phase 4 + 5b, 2026-05-03).** New `artifact` table (alembic 0005) with promoted hot columns + `data_json` long-tail. Per ratified rule 6: immutable; only `deleted_at` mutates. SDK ships `Artifact`/`ArtifactKind` Pydantic models. `TaskOutputProcessor._maybe_write_artifact` writes `particle_stack` rows for `PARTICLE_EXTRACTION` results and `class_averages` rows for `TWO_D_CLASSIFICATION` results, projecting the new id back into `output_data` for downstream addressability. 9 unit tests pin the writer + lineage shape. |
| 27 | ~~No user-visible rollup over the picker → extractor → classifier pipeline~~ | **Resolved (Phase 8 + 8b, 2026-05-03; rollup wired A.1).** New `pipeline_run` table (alembic 0006) with `image_job.parent_run_id` FK. Each algorithm step stays its own `ImageJob`; `PipelineRun` groups them. ORM `PipelineRun` class + 10 ORM tests. HTTP CRUD at `/pipelines/runs` (POST create / GET detail / GET list with bulk job-count / DELETE soft-delete) + 11 controller tests. Per rule 6 no PUT — runs are immutable. A.1 closed the deferred rollup: `JobManager._rollup_parent_run` recomputes the parent's `status_id` + `started`/`ended` dates on every child `mark_running`/`complete`/`fail`/`cancel`, mapping the `ImageJob` 0-4 enum onto `PipelineRun`'s 1/2/4/5/6 enum. |
| 28 | ~~Subject-typed inputs not validated at dispatch (silent hung jobs on wrong subject kind)~~ | **Resolved (PE1-A `db09ce4` + PE1-B `38c7f2f`, 2026-05-10/11; SDK 2.4.0).** Dispatch gate in `plugins/controller.py` rejects pre-publish: `_reject_if_subject_missing` (`:838`) for aggregate categories whose `CategoryContract.subject_kind != 'image'`; `_reject_if_subject_tag_mismatch` (`:876`) walks `CategoryContract.input_subjects` and verifies every UUID-typed field references an `Artifact` of the declared kind. Returns 4xx instead of publishing a doomed task. Field-level subject tags live on `CategoryContract.input_subjects` / `output_subjects` (e.g. `TWO_D_CLASSIFICATION.input_subjects = {'particle_stack_id': 'particle_stack', 'image_id': 'image'}`). |
| 29 | ~~Plugin schemas lost on CoreService restart~~ | **Resolved (`31845f1`, 2026-05-13).** Announced schemas used to live only in the in-memory liveness registry; a CoreService restart cleared them and the next announce was indefinite (plugins announce once per container boot, not per CoreService boot). `record_announce` now mirrors `msg.input_schema` / `output_schema` into `Plugin.manifest_json`; `_live_schema_for_plugin` reads three tiers (live → DB row → category contract). See §3.4 *Schema flow*. |
| 30 | Docker layer-cache traps stale SDK in plugin images | **Open.** `docker build` of `plugins/<id>/Dockerfile` uses build cache on `COPY wheels ./wheels`. When `scripts/rebuild-sdk-wheels.sh` produces a byte-identical wheel (no SDK source change), the layer cache reuses the prior `pip install` layer and ships an older SDK than the developer expects. Surfaced 2026-05-13 — the symptom was every plugin's input_schema flowing as None despite the SDK source clearly producing a schema. Manual workarounds: `docker image rm <plugin-image>` before reinstall, or modify any byte of the wheel content (e.g. touch a comment). Cleaner fix would hash the wheel into the image tag or pass `--no-cache` from `DockerInstaller`. |

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
- Plugin contract tests at `CoreService/tests/contracts/` (G.2, `59b420c`) —
  per-plugin module for CTF, MotionCor, FFT, hitting each plugin's
  `/execute` over HTTP with a canned `TaskMessage` and asserting the
  `TaskResultMessage` round-trip. Skip cleanly when the container isn't up.
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
  **`plugins/magellon_fft_plugin/`** (the reference / blueprint) —
  the external plugin reference; any new plugin SDK must stay
  compatible with their wire format.
- **`Docker/docker-compose.yml`** — deployed stack. RMQ + NATS both
  present; Temporal removed.


---

<!--
  Section: 3. Data Plane — Shared Filesystem
  Originated from: Documentation/DATA_PLANE.md
  Merged into this consolidated reference 2026-05-13.
-->

# Magellon — Data Plane: Shared Filesystem

**Status:** Canonical architectural decision as of 2026-04-21.
**Audience:** Operators, plugin developers, deployment engineers.
**Companion docs:** `ARCHITECTURE_PRINCIPLES.md` §1, `CURRENT_ARCHITECTURE.md`, `MESSAGE_BUS_SPEC.md`.

---

## 1. The decision

Magellon has two transport planes:

- **Control plane — the MessageBus** (`magellon_sdk.bus`). Carries
  task dispatch, results metadata, events, discovery, configuration,
  cancellation. Small payloads (≤ 10 KB per envelope, typically much
  less). Durable, versioned, observable.
- **Data plane — a shared POSIX filesystem** mounted at
  `MAGELLON_HOME_DIR` on CoreService and every plugin worker.
  Carries raw and derived image data: MRC files, motion-corrected
  outputs, CTF star files, thumbnails, FFTs. Large payloads
  (MB per micrograph, GB per movie, TB per session).

Metadata flows on the bus. Bytes flow on the filesystem. The bus
carries path references to files the data plane makes real.

---

## 2. Why this split

**Cryo-EM payload sizes forbid the alternative.** A single K3
micrograph is 10–20 MB. A raw movie is 1–10 GB. A typical session
produces thousands of these. Routing them through the bus would:

- Blow past CloudEvents envelope guidance (≤ 256 KB) and every
  broker's practical message-size limit.
- Defeat broker durability — JetStream retention walls, RMQ lazy-
  queue memory pressure — long before a session finishes.
- Double the I/O: every byte would be written to disk by the
  plugin, serialized, published, received, deserialized, and
  written *again* by CoreService.

**The domain already assumes it.** CryoSPARC, Relion, and Scipion
all assume a shared scratch filesystem visible to every worker.
HPC clusters run cryo-EM on GPFS, Lustre, BeeGFS, or CephFS as a
matter of course. Fighting this pattern would buy nothing and
cost deployment compatibility.

**The bus stays small and fast.** Keeping large binary data off
the bus means the bus stays durable, low-latency, and cheaply
instrumented. The control plane serves its actual purpose.

---

## 3. What flows on each plane

### Control plane (bus)

| Carried | Example | Typical size |
|---|---|---|
| Task dispatch | `TaskDto` with `image_path: str` | 1–4 KB |
| Task result | `TaskResultDto` with output paths + metadata | 1–8 KB |
| Step events | `magellon.step.progress` envelopes | < 1 KB |
| Discovery | Announce / heartbeat | < 1 KB |
| Config push | `magellon.plugins.config.<cat>` updates | 1–4 KB |
| Cancellation | Operator intents | < 1 KB |

### Data plane (filesystem)

| Carried | Example path | Typical size |
|---|---|---|
| Raw frames | `$MAGELLON_HOME_DIR/<session>/frames/<image>.mrc` | 10 MB – 10 GB |
| Motion-corrected | `$MAGELLON_HOME_DIR/<session>/motioncor/<image>_aligned.mrc` | 10–100 MB |
| CTF outputs | `$MAGELLON_HOME_DIR/<session>/ctf/<image>.star` | < 1 MB (many files) |
| Thumbnails / PNGs | `$MAGELLON_HOME_DIR/<session>/thumbnails/<image>.png` | 100 KB – 1 MB |
| FFTs | `$MAGELLON_HOME_DIR/<session>/fft/<image>_fft.png` | 100 KB – 1 MB |

The `<session>/<category>/<image>` layout convention is enforced
by `CoreService/services/task_output_processor.py::_get_destination_dir`.
Plugins that deviate break the projection.

---

## 4. Mount requirement

**Single namespace, visible to all.** CoreService and every plugin
worker — in-process, subprocess, or containerized — must see the
same path resolve to the same file. If plugin A writes
`$MAGELLON_HOME_DIR/<session>/foo.mrc` and plugin B cannot read
that path, the deployment is broken.

This is a deployment prerequisite, not a Magellon bug. Operators
own provisioning the shared filesystem; the platform assumes it.

---

## 5. Acceptable implementations

| Deployment | Backing | Notes |
|---|---|---|
| HPC / on-prem cluster | GPFS, Lustre, BeeGFS, CephFS | Recommended — designed for exactly this workload. |
| On-prem Kubernetes | CephFS, NFS with RWX PV | PV `accessModes` must include `ReadWriteMany`. |
| Single-node `docker-compose` | Docker bind mount | Dev default; every service mounts the same host dir. |
| AWS | EFS | `ReadWriteMany`; provisioned throughput sized per session. |
| GCP | Filestore | Basic for dev, HDD for small sessions, SSD for prod. |
| Azure | Azure Files (NFS protocol) | SMB works but POSIX semantics are cleaner. |

**Smaller scales.** A single NFS export between two hosts is a
valid entry point. Not recommended past ~2 plugin replicas — NFSv3
locking behaviour and `rename` atomicity become fragile under
concurrent writes.

---

## 6. Plugin obligations

Plugins using the data plane must:

1. **Read and write only under `$MAGELLON_HOME_DIR`.** Never use
   `/tmp` for cross-plugin artifacts — it's not shared.
2. **Write to session-scoped subdirectories.**
   `<session>/<category>/<image>` is the layout the result
   projector assumes.
3. **Return file paths, not bytes, in `TaskResultDto`.** The
   result processor moves files based on the paths the plugin
   reports.
4. **Handle partial writes atomically.** Write to a temp name
   under the session dir, then `os.rename` to the final name —
   `rename` within one filesystem is atomic on POSIX.
5. **Tolerate eventual consistency on some backends.** EFS metadata
   ops are strongly consistent; NFSv3 `readdir` after `rename`
   may lag. If a plugin needs to see another plugin's output,
   sequence that dependency via the bus, not via filesystem
   polling.

---

## 7. What this forecloses on

Deliberately out of scope:

- **Object-storage-only deployments** (S3, GCS, Azure Blob without
  a filesystem gateway). A Magellon plugin cannot assume S3
  semantics — no `rename`, no atomic listings, eventual consistency
  on reads after writes. If an S3-only target becomes a product
  requirement, it's a separate architectural track, not a quick
  adapter.
- **Serverless cloud GPU** (RunPod, Lambda, Cloud Run Jobs)
  *without* a persistent attached filesystem volume. These
  platforms work only if they can mount the shared filesystem.
  Otherwise the plugin has no way to produce output CoreService
  can see.
- **Byte-addressable data on the bus.** A future "small images fit
  in the envelope" optimisation is not supported. Keep the plane
  separation strict.

These are not regrets. They are the cost of a simple, fast, domain-
appropriate architecture. Operators needing one of the above should
treat Magellon's deployment requirements as a selection criterion.

---

## 8. Operator surface

Per `ARCHITECTURE_PRINCIPLES.md` §7, the data plane answers three
questions:

- **Observe.** `df -h $MAGELLON_HOME_DIR` gives capacity; Prometheus
  node_exporter's filesystem collector tracks free bytes, inode
  usage, and write latency.
- **Drain.** Session cleanup is currently manual
  (`rm -r $MAGELLON_HOME_DIR/<session>`). A retention policy per
  session is open work, tracked under Track B if it graduates.
- **Recover.** A full data plane is recoverable from the raw-frame
  backup (customer-owned). CoreService's MySQL state lets the
  platform re-run any step whose inputs survive.

---

## 9. Open questions

Deferred until evidence justifies them:

1. **Per-session quotas.** One rogue session can fill the plane for
   everyone. GPFS and Lustre support per-fileset quotas; NFS via
   `xfs_quota`. Do we want this platform-enforced? Not yet — no
   incident has forced it.
2. **Archival tier.** Sessions older than N days could move to
   cheaper storage. Design space is large (HSM, S3 IA, glacier);
   no customer has asked.
3. **Checksums on result files.** A corrupted output propagates
   silently today. A hash in `TaskResultDto` is cheap; worth doing
   if plugin crashes ever produce half-written MRCs — no evidence
   yet.

---

## 9.5. Path-translation invariants

The bind-mount story works because four invariants hold across the
codebase. Violations are the most common source of "plugin can't
open the file" bugs in mixed-OS deployments.

1. **Wire paths are canonical `/gpfs/...`** — every value that
   crosses a process boundary (RMQ envelope, sync HTTP body, NATS
   event) is in canonical form. CoreService translates host →
   canonical at every dispatch boundary; plugins translate canonical
   → local at every I/O boundary.

2. **One source of truth for the translation helpers** —
   `magellon_sdk.paths.to_canonical_gpfs_path` /
   `from_canonical_gpfs_path` are the canonical implementation.
   CoreService's `core/helper.py` wraps these (post-2.1
   consolidation, 2026-05-12); plugins import from the SDK directly.
   If both ends drift, mixed-deployment data-plane access breaks
   asymmetrically — symptom is "Linux works, Windows direct-run
   doesn't."

3. **Canonicalization happens once per boundary** —
   `canonicalize_paths_in_payload` walks RMQ payloads at dispatch
   time (`core/helper.py`); `services/sync_dispatcher.py` walks
   HTTP bodies at sync-send time. Plugins don't re-canonicalize on
   receive; they `from_canonical_gpfs_path` at the I/O call site.

4. **The translation helpers are deliberately naive about
   `..`** — they only do prefix substitution. `..` segments pass
   through. Defense-in-depth (`is_under_gpfs_root` in
   `core/helper.py`) is the check that catches path-escape
   attempts at the I/O boundary. Don't try to teach the helpers
   security; keep them small and predictable.

These invariants are tested by:

- `CoreService/tests/test_canonical_gpfs_path.py` + `_edges.py` —
  CoreService side, prefix-overlap and trailing-slash boundary
  cases.
- `magellon-sdk/tests/test_paths.py` + `_edges.py` — SDK side,
  same edge cases for symmetry.
- `CoreService/tests/test_canonicalize_property.py` — randomized
  property tests for the payload walker (idempotency, type
  preservation, no false positives on prose).

If you're touching path translation, add a test in each suite.

---

## 10. What to read next

- `ARCHITECTURE_PRINCIPLES.md` — the canonical rule-set this doc
  implements for the data plane.
- `CoreService/services/task_output_processor.py` — the live code
  that reads and moves files under `MAGELLON_HOME_DIR`.
- `Docker/docker-compose.yml` — the reference bind-mount layout
  for dev; every plugin service gets `/magellon:/magellon:rw`.


---

<!--
  Section: 4. Message Bus — Specification
  Originated from: Documentation/MESSAGE_BUS_SPEC.md
  Merged into this consolidated reference 2026-05-13.
-->

# Magellon — MessageBus Specification

**Status:** Canonical, 2026-04-28. Migration to this spec completed
2026-04-21 (Track A: MB0–MB6, see `IMPLEMENTATION_PLAN.md`).
**Audience:** Platform maintainers, plugin authors, reviewers.
**Companion docs:** `CURRENT_ARCHITECTURE.md` §4/§6, `MESSAGES_AND_EVENTS.md`,
`BROKER_PATTERNS.md`, `DLQ_MIGRATION_RUNBOOK.md`.

This document specifies the `magellon_sdk.bus` abstraction. Earlier
revisions (v1, v2, v2.1) and the original migration plan (MB0–MB6 PR
sequencing) are preserved in git history.

---

## 1. Why this exists

Magellon's plugin platform uses messaging in two structurally different
shapes. Any abstraction has to respect the split — folding them into one
API leaks either durability or fanout semantics.

| Shape | Used for | Required primitives |
|---|---|---|
| **Work queue** (commands) | Task dispatch, result fan-in | Durable queue, point-to-point, manual ack/nack, DLQ, queue purge |
| **Event topic** (pub-sub) | Discovery, heartbeat, config broadcast, step events | Topic exchange, routing-key patterns, N subscribers, fire-and-forget |

This matches **Dapr / CloudEvents** ("commands go on queues, events go on
pub-sub") and **Cosmic Python**'s command-bus / event-bus separation.

`magellon_sdk/categories/contract.py` already owns transport-neutral
subject naming:

```python
task_subject(cat)      -> "magellon.tasks.ctf"
result_subject(cat)    -> "magellon.tasks.ctf.result"
heartbeat_subject(c,p) -> "magellon.plugins.heartbeat.ctf.ctffind4"
announce_subject(c,p)  -> "magellon.plugins.announce.ctf.ctffind4"
config_subject(cat)    -> "magellon.plugins.config.ctf"
```

Dots work as NATS subjects and RMQ routing keys. Match CloudEvents
envelope `subject` field. This is **one source of truth** — the bus's
route value objects delegate here, never duplicate.

For the broker patterns these subjects implement (work queue, topic
fanout × 4, DLX), see `BROKER_PATTERNS.md`.

---

## 2. Design principles

**1. Two surfaces, not one (Cosmic Python, Dapr).** Commands and events
are semantically different. `bus.tasks` and `bus.events` are siblings.

**2. Envelope-first, not raw payloads (CloudEvents 1.0).** FastStream
leaks pika kwargs (`correlation_id`, `headers`, `priority`, `app_id`)
through publish signatures — a portability trap. The bus accepts and
emits `magellon_sdk.envelope.Envelope` only.

**3. Binder SPI between bus and transport (Spring Cloud Stream).** A
**binder** (SCS's word) / **connector** (Quarkus') / **carrier** (plain
English) is a plug-in module that moves envelopes over one transport.
The bus Protocol is the caller-facing surface; the binder interface is
the transport-facing surface.

**4. Dual consumer API — decorator and imperative.**
`@bus.tasks.consumer(route)` for module-level plain functions;
`bus.tasks.consumer(route, handler)` for bound methods on class-based
services. One underlying registration, two ergonomic entrypoints. Return
→ ack, raise → classified nack via existing `classify_exception`.
Handlers never call `msg.ack()`.

**5. Routes read from `CategoryContract`, don't duplicate it.**
`TaskRoute.for_category(CTF)` delegates to `CTF.task_subject`. Type
safety, not new topology.

**6. No user-extensible middleware (FastStream issue #1646 lesson).** A
**fixed, named set** of built-in binder features (audit log, trace
context) ships in the binder config. Users cannot compose new middleware
chains.

---

## 3. Architecture — four layers

```
┌─────────────────────────────────────────────────────────────────┐
│ L1: Caller code (CoreService, plugins, runner)                  │
│     imports: magellon_sdk.bus                                   │
│     touches: get_bus(), bus.tasks.send, bus.events.publish,     │
│              @bus.tasks.consumer, bus.events.subscribe(...),    │
│              Envelope, Route value objects                      │
├─────────────────────────────────────────────────────────────────┤
│ L2: Bus API (magellon-sdk/src/magellon_sdk/bus/)                │
│     MessageBus facade + TasksBus + EventsBus Protocols          │
│     Route value objects, TaskConsumerPolicy                     │
│     get_bus() factory — NOT a module-level singleton            │
├─────────────────────────────────────────────────────────────────┤
│ L3: Binder SPI (magellon-sdk/src/magellon_sdk/bus/binder.py)    │
│     Binder Protocol: start, close, publish_task, consume_tasks, │
│                      publish_event, subscribe_events,           │
│                      purge_tasks                                │
│     One binder instance per transport per process               │
├─────────────────────────────────────────────────────────────────┤
│ L4: Binder implementations (magellon-sdk/src/magellon_sdk/      │
│                              bus/binders/rmq/)                  │
│     RmqBinder — the only production binder today.               │
│     Owns: pika connection (long-lived), channel pool,           │
│            topology (exchanges, queues, DLQs), reconnect,       │
│            AMQP properties, AuditLogConfig (publish-time file)  │
│     NatsBinder, MockBinder, InMemoryBinder also live here.      │
└─────────────────────────────────────────────────────────────────┘
```

**Invariants** — lint-enforced by the ruff banned-api rule (MB6.3,
`.github/workflows/lint.yml`):

- L1 never imports anything below L2.
- L2 never imports anything below L3. L2 has zero transport code.
- L3 is a Protocol + small helpers; no `pika`, no `nats-py`.
- L4 is where `pika` lives. Exactly one directory.

`rg '^import pika|^from pika' -g '!magellon_sdk/bus/binders/rmq/**' -g '!**/tests/**'`
returns zero on `main`.

---

## 4. Bus API (L2) — what callers see

### 4.1 Module shape

```python
# magellon_sdk/bus/__init__.py
from magellon_sdk.bus import get_bus, MessageBus
```

**`get_bus()` is the only entrypoint.** There is no module-level
singleton. First call lazily constructs the bus from config; subsequent
calls return the same instance; tests inject via `get_bus.override(...)`
/ fixture reset.

Rationale: a module-level `bus = MessageBus.default()` would resolve at
import time, which binds the decorator form `@bus.tasks.consumer(...)`
to the production bus before any test fixture can swap it. `get_bus()`
defers resolution to first call — test code calls
`get_bus.override(mock_bus)` in a fixture, and plugin code later calls
`get_bus()` inside its constructor and sees the mock.

```python
# Two sibling modules with distinct semantics

# Work (commands) — durable, ack-required, DLQ-capable
bus.tasks.send(route: TaskRoute, envelope: Envelope[T]) -> PublishReceipt
bus.tasks.consumer(route, handler=None, *, policy=TaskConsumerPolicy())
    # handler=None → decorator form
    # handler=fn   → imperative registration, returns ConsumerHandle
bus.tasks.purge(route: TaskRoute) -> int

# Events (pub-sub) — fanout, fire-and-forget
bus.events.publish(route: EventRoute, envelope: Envelope[T]) -> PublishReceipt
bus.events.subscribe(pattern: EventPattern, handler=None)
    # handler=None → decorator form
    # handler=fn   → imperative, returns SubscriptionHandle
```

**Five methods, two modules, one envelope type.**

`PublishReceipt` carries `ok: bool`, `message_id: str`, `error: Optional[str]`.
Fire-and-forget `bus.events.publish` returns a receipt but callers
usually discard it — observability without blocking.

### 4.2 Consumer API — dual form

Underlying implementation:

```python
def consumer(self, route, handler=None, *, policy=TaskConsumerPolicy()):
    def _register(fn):
        return self._binder.consume_tasks(route, fn, policy)
    return _register if handler is None else _register(handler)
```

**Decorator form** — plugin `main.py`, module-level plain functions:

```python
bus = get_bus()

@bus.tasks.consumer(TaskRoute.for_category(CTF), policy=TaskConsumerPolicy(max_retries=3))
def handle_ctf(envelope: Envelope[CtfInput]) -> TaskResultMessage:
    # return → ack
    # raise BadInputError → DLQ (classify_exception: ACK→DLQ)
    # raise ConnectionError → requeue (classify_exception: NACK_REQUEUE)
    # raise PluginExecutionError → ack-with-failure (classify_exception: ACK)
    ...
```

**Imperative form** — class-based services with bound methods:

```python
class StepEventForwarder:
    """Forwards step events to Socket.IO. Bound method handler."""

    def __init__(self, bus: MessageBus, socketio):
        self.socketio = socketio
        self._handle = bus.events.subscribe(StepEventRoute.all(), self._forward)

    def _forward(self, envelope: Envelope) -> None:
        self.socketio.emit("step_event", envelope.model_dump())

    def stop(self) -> None:
        self._handle.close()
```

Imperative is required whenever the handler is a bound method, a lambda,
a dynamically-created function, or when registration order depends on
runtime state. Every relocated CoreService service uses imperative.
Plugin `main.py` typically uses decorator.

### 4.3 Route value objects (read from `CategoryContract`)

```python
# magellon_sdk/bus/routes/task_route.py
@dataclass(frozen=True)
class TaskRoute:
    subject: str            # the subject string is the source of truth

    @classmethod
    def for_category(cls, c: CategoryContract) -> "TaskRoute":
        return cls(subject=c.task_subject)

    @classmethod
    def named(cls, subject: str) -> "TaskRoute":
        """Escape hatch for non-contract routes (e.g. test queues)."""
        return cls(subject=subject)
```

Identical pattern for `TaskResultRoute`, `StepEventRoute`,
`HeartbeatRoute`, `AnnounceRoute`, `ConfigRoute`, `CancelRoute`. Each
delegates to the matching `CategoryContract` accessor. Patterns
(`HeartbeatRoute.all()`) return
`EventPattern(subject_glob="magellon.plugins.heartbeat.*")`; the binder
translates glob to RMQ `#` or NATS `>`.

Test queues like `motioncor_test_inqueue` use `TaskRoute.named(...)` —
explicit, not a contract route.

### 4.4 Envelope

`magellon_sdk.envelope.Envelope` is CloudEvents 1.0 compliant.
`bus.tasks.send` wraps raw payloads if passed a non-`Envelope`, but the
typed API accepts `Envelope[T]`.

### 4.5 Out of scope — deliberately

- **User-extensible middleware chains.** A fixed set of named binder
  features (audit log, trace context) is allowed and configured
  declaratively. Users cannot register custom pre/post hooks.
- **Request/reply (`bus.request(...)`).** No caller needs RPC.
- **Streaming / batch subscribers.** No use case.
- **Broker-specific escape hatches** (RMQ priority, NATS KV). Stay in
  binder config, never in call-site API.
- **Socket.IO.** Separate transport (browser-facing); outside the bus.
- **Connection pooling as caller concern.** One long-lived connection
  per binder instance, channel per operation. Caller never touches.

---

## 5. Binder SPI (L3)

```python
# magellon_sdk/bus/binder.py
class Binder(Protocol):
    name: str                                # "rmq", "nats", "sqs"

    def start(self) -> None: ...             # connect, declare topology, install audit
    def close(self) -> None: ...

    # Work queue
    def publish_task(self, route: TaskRoute, env: Envelope) -> PublishReceipt: ...
    def consume_tasks(
        self, route: TaskRoute, handler: TaskHandler, policy: TaskConsumerPolicy,
    ) -> ConsumerHandle: ...
    def purge_tasks(self, route: TaskRoute) -> int: ...

    # Events
    def publish_event(self, route: EventRoute, env: Envelope) -> PublishReceipt: ...
    def subscribe_events(
        self, pattern: EventPattern, handler: EventHandler,
    ) -> SubscriptionHandle: ...
```

**Binder lifecycle.** `start()` establishes the long-lived connection,
declares exchanges and durable queues, installs DLQ policy, and turns
on binder-level features (audit log, tracing). `close()` drains
in-flight consumers and shuts the connection. Reconnect is **internal**
to the binder — callers get a working binder or `BinderDown` exception;
never retry loops.

**Topology ownership.** The binder owns exchange names
(`magellon.plugins`, `magellon.events`, `""` default), queue binding
patterns, DLQ routing keys. Caller code never names an exchange.
`declare_queue_with_dlq` is a binder `start()`-time operation (see
`magellon-sdk/src/magellon_sdk/bus/binders/rmq/_client.py`).

**One binder per process.** `get_bus()` constructs one `Binder` from
config, holds it for process lifetime. Not per-call.

---

## 6. `PluginBrokerRunner` — composes over the bus

The runner is **not** a separate transport layer — it composes over L2.

```python
class PluginBrokerRunner:
    """Wires one PluginBase to the bus, adds lifecycle services."""

    def __init__(self, *, plugin, bus, contract, heartbeat_interval=15.0): ...

    def start_blocking(self) -> None:
        # 1. register task consumer via bus (imperative — bound method)
        self._task_handle = self.bus.tasks.consumer(
            TaskRoute.for_category(self.contract),
            self._handle_task,
            policy=self._policy,
        )

        # 2. discovery: publish announce + heartbeat via bus.events
        self._discovery = DiscoveryService(
            bus=self.bus, contract=self.contract, interval=self.heartbeat_interval,
        )
        self._discovery.start()

        # 3. config subscriber via bus.events
        self._config = ConfigSubscriberService(bus=self.bus, contract=self.contract)
        self._config.start()

        # 4. run the consumer until stopped
        self._task_handle.run_until_shutdown()

    def _handle_task(self, env: Envelope) -> Envelope:
        # Drain pending config between deliveries (never during execute)
        self._config.apply_pending(self.plugin)

        # Validate, run, stamp provenance
        validated = self.contract.validate_input(env.data)
        result = self.plugin.run(validated)
        result_dto = self._build_result(env, result)
        self._stamp_provenance(result_dto)
        return Envelope.wrap(...)  # binder publishes to TaskResultRoute
```

`DiscoveryService`, `ConfigSubscriberService` live under
`magellon_sdk/bus/services/`. Provenance stamping, redelivery handling
(via `x-magellon-redelivery` header — binder-tracked, honest integer not
boolean), and config-drain-between-deliveries stay in the runner.

---

## 7. Audit, observability, DLQ

### 7.1 Audit log — binder config, publish-time

`publish_message_to_queue` historically wrote
`/magellon/messages/<queue>/messages.json` **before** calling RabbitMQ.
A task published-but-never-consumed appeared in the audit log. That
behavior is preserved as a **binder-level declarative feature**, not a
user-composable middleware hook:

```python
# When constructing the RMQ binder (called inside get_bus() from config)
RmqBinder(
    settings=rabbitmq_settings,
    audit=AuditLogConfig(
        enabled=True,
        root="/magellon/messages",
        routes=[TaskRoute.for_category(CTF), TaskRoute.for_category(MOTIONCOR)],
    ),
)
```

Binder implementation: `publish_task` appends to
`<root>/<subject>/messages.json` before the pika `basic_publish`. Same
trigger point as the old code, same file layout. No decorator, no
middleware abstraction at the bus level.

`AuditLogConfig.enabled` defaults to **False**; CoreService boot turns
it on for the routes it audits. Plugins keep it off by default (they
only produce results, not originate tasks).

### 7.2 DLQ

Binder declares DLQ topology at `start()`.
`TaskConsumerPolicy(dlq_enabled=True)` is the opt-in.
`classify_exception` (in `magellon_sdk/errors.py`) routes poison
messages to DLQ. The DLQ topology migration for queues that predated
DLQ args is documented in `DLQ_MIGRATION_RUNBOOK.md`.

### 7.3 Redelivery count

Binder tracks per-message redelivery in a pika header
(`x-magellon-redelivery`) and increments on each nack-requeue.
`classify_exception(exc, redelivery_count=N)` gets an honest integer
rather than the misleading boolean `int(method.redelivered)`.

### 7.4 OpenTelemetry

Trace context rides envelope `traceparent` extension (CloudEvents
standard). Binder-level spans land whenever OTel is wired into the
process.

---

## 8. Non-goals

- **Fixing the "two plugin architectures" split** (external RMQ vs
  in-process `PluginBase`). Tracked separately in
  `UNIFIED_PLATFORM_PLAN.md`; both converge through the bus.
- **Replacing Socket.IO.** Different semantics (browser-facing,
  per-session auth).
- **Workflow engine.** Temporal was reverted for a reason.
- **Changing the envelope format.** CloudEvents 1.0 stays.
- **Adding `bus.request(...)` RPC.** Async dispatch + separate result
  consume is the model.
- **User-extensible middleware.** Only a fixed, named set of binder
  features.

---

## 9. Adding a new binder

If a second backend becomes operationally justified (NATS for
JetStream replay, SQS for AWS-only deployment), implement a new
`Binder` next to `bus/binders/rmq/`. Config flag
`MAGELLON_BUS_BACKEND=rmq|nats|sqs`. Recommended first cutover for any
new binder: step events (smallest blast radius, naturally pub-sub).

For SQS specifically, expect 1.5–2× NATS effort: SNS filter policies
replace routing-key patterns, 256 KB payload cap, redrive policies
replace DLQ exchanges, no native ack/nack semantics (visibility timeout
+ redrive).

For the comparison of how each candidate transport implements the six
broker patterns Magellon uses, see `BROKER_PATTERNS.md` §8.

---

## 10. References

**Frameworks studied:**

- [Spring Cloud Stream — Binder SPI](https://docs.spring.io/spring-cloud-stream/reference/spring-cloud-stream/binders.html)
  — the layering this spec adopts: L2/L3/L4 = Bindings / Binder /
  Broker.
- [Quarkus SmallRye Reactive Messaging — Connectors](https://quarkus.io/guides/messaging)
  — `@Incoming`/`@Outgoing` decorator model that inspired
  `@bus.tasks.consumer`.
- [Dapr — Pub/Sub with CloudEvents](https://docs.dapr.io/developing-applications/building-blocks/pubsub/pubsub-cloudevents/)
  — commands-on-queues vs events-on-pubsub split.
- [Cosmic Python — Chapter 8 (Event Bus) / Chapter 10 (Command Bus)](https://www.cosmicpython.com/book/)
  — the two-surface split this spec codifies.
- [CloudEvents 1.0](https://github.com/cloudevents/spec/blob/v1.0/spec.md)
  — envelope format already in use.

**Negative examples (what we deliberately avoid):**

- [FastStream issue #1646](https://github.com/ag2ai/faststream/issues/1646)
  — middleware unification rabbit hole; why §4.5 excludes
  user-extensible middleware chains.
- FastStream publish signature (pika kwargs leaking through) — why §2
  insists on envelope-first.

**Internal prior art:**

- `magellon_sdk/dispatcher.py` — `TaskDispatcher` Protocol. Survives as
  the in-process dispatch path; bus is the out-of-process path.
- `magellon_sdk/bus/binders/rmq/_client.py` — the RMQ implementation
  details (what was once `transport/rabbitmq.py`).


---

<!--
  Section: 5. Broker Patterns
  Originated from: Documentation/BROKER_PATTERNS.md
  Merged into this consolidated reference 2026-05-13.
-->

# Magellon — Broker Patterns Tutorial

**Status:** Reference / pedagogical. Describes the six messaging patterns
Magellon uses on top of RabbitMQ as of 2026-04-28.
**Audience:** New plugin authors, reviewers trying to understand why a
particular feature uses a queue vs. a topic exchange, and anyone
evaluating an alternate transport (NATS, Durable Objects, …).
**Companions:**
- `CURRENT_ARCHITECTURE.md` — the system as it actually runs.
- `MESSAGE_BUS_SPEC.md` — the transport-neutral abstraction.
- `MESSAGES_AND_EVENTS.md` — wire shapes (`Envelope`, routing keys).
- `DLQ_MIGRATION_RUNBOOK.md` — the operational side of pattern #6.

This document explains the **patterns**, not the wire format. It assumes
you've at least skimmed `MESSAGES_AND_EVENTS.md` for the envelope shape.

---

## 0. Vocabulary

Everything below uses three RMQ primitives. They're worth pinning down
before the tour, because four of the six patterns are the same shape with
different parameters.

- **Queue** — a buffer messages sit in until a consumer pulls one. Many
  producers can push; many consumers can pull, but each message is
  delivered to **exactly one** consumer. RMQ load-balances across
  consumers on the same queue.
- **Exchange** — the post-office in front of queues. A producer publishes
  to an exchange + a *routing key*; the exchange decides which queue(s)
  receive a copy. Three flavours matter to us:
  - `direct` — exact routing-key match.
  - `topic` — wildcard match (`a.*.c`, `a.#`).
  - `fanout` — every bound queue gets a copy.
- **Binding** — the rule "this queue wants messages whose routing key
  matches `X`" attached to an exchange.

Magellon hides all of this behind `MessageBus`
(`magellon-sdk/src/magellon_sdk/bus/interfaces.py`). Plugin code says
`bus.tasks.send(env)` or `bus.events.subscribe(route, handler)` and never
touches an exchange directly. But the patterns are still RMQ underneath,
so understanding them helps when reading logs, debugging missing
deliveries, or reasoning about an alternate transport.

---

## 1. Work queues — "give the next free chef the next ticket"

**Picture.** A diner has one ticket spike and five chefs. A waiter clips
a ticket onto the spike. Whichever chef finishes first grabs it. Each
ticket is cooked exactly once. If a chef burns out mid-cook, the ticket
goes back on the spike for someone else.

**Why Magellon needs it.** A 5,000-image import produces 5,000 CTF tasks.
Whichever CTF plugin replica is free should pick up the next one. Tasks
must not be processed twice; tasks must not be dropped if a worker
crashes mid-cook.

**RMQ primitive.** A *durable queue* per category — `ctf_tasks_queue`,
`motioncor_tasks_queue`, `fft_tasks_queue`, etc. Each plugin replica is
a consumer with `prefetch_count=1` (don't grab a second ticket until you
ack the first). Worker crashes mid-task → RMQ re-queues the un-acked
message and another consumer picks it up.

**Where in the code:**
- Producer: `CoreService/core/dispatcher_registry.py` — wraps a
  `TaskMessage` in a CloudEvents `Envelope` and calls
  `bus.tasks.send(env)`.
- Consumer: each plugin's `main.py` (e.g.
  `plugins/magellon_ctf_plugin/main.py:109`) constructs a
  `PluginBrokerRunner`, which registers a `bus.tasks.consumer` for its
  category route in `magellon-sdk/src/magellon_sdk/runner/plugin_runner.py`.
- RMQ wiring: `magellon-sdk/src/magellon_sdk/bus/binders/rmq/binder.py`.

---

## 2. Step-event fanout — "the kitchen radio"

**Picture.** The chef calls "fries down!" on the kitchen radio. Anyone
listening — the expediter, the waiter, the manager checking timing —
hears it. The chef doesn't know who is listening. Multiple listeners
each get their own copy of every shout.

**Why Magellon needs it.** When MotionCor finishes alignment, the React
UI wants a progress bar update; the audit log wants a row; possibly
Grafana wants a counter. The plugin shouldn't have to know who cares.

**RMQ primitive.** A *topic exchange* (`magellon.events`) with routing
keys like `magellon.step.ctf.started`, `magellon.step.motioncor.progress`.
Each subscriber declares **its own** queue and binds it to a wildcard
pattern (`magellon.step.*` or `magellon.step.ctf.*`). Every event lands
in every bound queue — that's the fanout.

This is the key difference from pattern #1: in #1, N consumers share
**one** queue; here, N consumers each have **their own** queue, all fed
from one exchange.

**Where in the code:**
- Publisher: `magellon-sdk/src/magellon_sdk/events.py` —
  `StepEventPublisher`.
- Route definition: `magellon-sdk/src/magellon_sdk/bus/routes/event_route.py`
  — `StepEventRoute`.
- Forwarder (CoreService side):
  `magellon-sdk/src/magellon_sdk/bus/services/step_event_forwarder.py` —
  subscribes via `bus.events.subscribe(StepEventRoute.all(), handler)`,
  writes a `job_event` row (idempotent on `event_id` UNIQUE), re-emits
  over Socket.IO.

NATS does the same job for the same events with subjects
(`magellon.step.>`) — that's why the message-bus spec was designed
transport-neutral.

---

## 3. Discovery & heartbeat — "everyone shouts their name when they walk in, then taps the bar every 10 seconds"

**Picture.** New chef walks in. Shouts "Mario, motioncor station, on
shift." Every 10 seconds taps the bar — *still here*. Manager keeps a
clipboard. Chef stops tapping for 30s → manager crosses them off.

**Why Magellon needs it.** Phase P8 deleted Consul. CoreService still
needs to know which plugin replicas are alive so the dispatcher can pin
to a specific backend (X.1's `target_backend`). With no central
registry, plugins announce themselves on the bus.

**RMQ primitive.** Same topic-exchange fanout as pattern #2, different
routing keys: `magellon.plugins.announce.<category>.<backend>` on boot,
`magellon.plugins.heartbeat.<category>.<backend>` every N seconds.
CoreService binds **one** queue to `magellon.plugins.#` and updates an
in-memory registry as messages flow.

A tuning detail: heartbeat-side queues are usually declared
**non-durable + auto-delete**. If CoreService restarts, there's no point
queuing up old heartbeats — the next round arrives in 10s anyway.

**Where in the code:**
- Plugin side: `magellon-sdk/src/magellon_sdk/discovery.py` —
  `DiscoveryPublisher`, `HeartbeatLoop`.
- CoreService side:
  `magellon-sdk/src/magellon_sdk/bus/services/liveness_registry.py` —
  subscribes, maintains the in-memory map, ages out stale entries.

---

## 4. Dynamic config push — "a memo to all CTF stations" + "a memo to everyone"

**Picture.** Manager wants every CTF chef to switch knife brands. Sticks
one memo on the CTF-only board (everyone at that station reads it). Or,
for "no peanuts in any dish today," sticks one memo on the all-stations
board (everyone everywhere reads it).

**Why Magellon needs it.** An operator changes "max defocus" for CTF
without redeploying. Or flips `STEP_EVENTS_ENABLED=false` system-wide.
Each running plugin needs to apply the change between tasks, no restart.

**RMQ primitive.** Topic exchange again, with two routing-key
conventions:

- `magellon.plugins.config.<category>` — only plugins of that category
  bind to it.
- `magellon.plugins.config.broadcast` — every plugin binds to it.

Each plugin replica draws an *exclusive auto-delete* queue (its own
mailbox, deleted when the replica dies) and binds it to both keys. The
runner's `ConfigSubscriber` drains it between tasks and calls
`plugin.configure(...)`.

**Where in the code:**
- Publisher (CoreService):
  `magellon-sdk/src/magellon_sdk/bus/services/config_publisher.py`.
- Subscriber (plugin): `magellon-sdk/src/magellon_sdk/config_broker.py`
  — `ConfigSubscriber`. Wired into `PluginBrokerRunner`.

The pattern repeats on purpose. Once you understand "topic exchange +
per-subscriber queue + wildcard binding," patterns #2/#3/#4 are the
same shape with different routing keys.

---

## 5. Cooperative cancel — "table 7 walked out, drop their order"

**Picture.** Customer leaves before food's up. Manager shouts "table 7
cancelled!" Anyone holding a table-7 ticket bins it; everyone else
ignores. Importantly: this **doesn't yank a knife out of mid-chop** —
the chef finishes the current cut, then checks the cancellation board
before starting the next step.

**Why Magellon needs it.** User clicks "Cancel job 1234" in the UI.
CoreService has dispatched 200 tasks for that job; some are running,
most are queued. We can't kill mid-MotionCor — that's the P9 hard-stop
(`docker kill`). We *can* tell every plugin "if you're about to start a
task whose `job_id` matches 1234, fail it instead."

**RMQ primitive.** Topic-exchange fanout again. Routing key
`magellon.cancel.<job_id>`. Each plugin replica binds an exclusive
queue to `magellon.cancel.*`. `CancelRegistry` keeps a local `set` of
cancelled job_ids. The progress reporter checks this set at every
`started/progress` checkpoint and raises `JobCancelledError`.

The cancel signal is *advisory*: it sits in a registry, and cooperative
code paths consult it. The runner catches the raise and emits a FAILED
result with `output_data["cancelled"]=True`.

**Where in the code:**
- Both sides:
  `magellon-sdk/src/magellon_sdk/bus/services/cancel_registry.py` —
  `CancelRoute.for_job(<id>)`, `CancelRegistry`,
  `start_cancel_listener(bus)`.
- Hook point: `BoundStepReporter.started/progress` in the SDK reporter
  — the `if job_id in cancel_registry: raise` check lives there.

---

## 6. Poison routing (DLX / DLQ) — "tickets that nobody can cook go in the manager's drawer"

**Picture.** Ticket says "boil a watch." No chef can cook that. Instead
of throwing it in the bin (lost forever) or putting it back on the spike
(it'll just come around again), they slide it into the manager's drawer
for review. Manager opens the drawer Monday, decides what to do.

**Why Magellon needs it.** A `TaskMessage` arrives with a malformed
envelope, a missing input file, or a category the plugin doesn't
support. Re-queueing creates an infinite redelivery loop. Dropping it
loses the evidence. We need a parking lot.

**RMQ primitive.** Two paired pieces:

1. **DLX (Dead-Letter Exchange).** Each main queue is declared with
   `x-dead-letter-exchange = magellon.dlx`. When a consumer NACKs a
   message with `requeue=False`, RMQ routes it through the DLX into a
   paired `<queue>.dlq`. Operator inspects later.
2. **The classifier deciding which fate to pick.**
   `magellon-sdk/src/magellon_sdk/errors.py::classify_exception`
   returns one of:
   - `AckAction.ACK` — plugin domain failure (ctffind crashed on this
     image): ack with a failure result, no re-queue, no DLQ.
   - `AckAction.NACK_REQUEUE` — transient infra (RMQ lost connection
     mid-task): re-queue, somebody else will get it.
   - `AckAction.DLQ` — poison (parse error, unknown category): NACK
     with `requeue=False` → DLX → `<queue>.dlq`.

The runner enforces the action in
`magellon-sdk/src/magellon_sdk/runner/plugin_runner.py`.

**Where in the code:**
- Topology:
  `magellon-sdk/src/magellon_sdk/bus/binders/rmq/_client.py::declare_queue_with_dlq`
  — the one place that knows how to declare a queue + its DLQ pair
  correctly.
- Classifier: `magellon-sdk/src/magellon_sdk/errors.py`.
- Existing-queue migration (queues declared before DLQ existed):
  `CoreService/scripts/migrate_dlq_topology.py` per
  `Documentation/DLQ_MIGRATION_RUNBOOK.md`.

---

## 7. The patterns, compressed

Reading all six in a row makes them feel distinct. Reading them by RMQ
shape collapses them to three:

| Shape                                         | Patterns                                          | Why                                                              |
|-----------------------------------------------|---------------------------------------------------|------------------------------------------------------------------|
| **Direct queue, many consumers, one wins**    | #1 work queues                                    | Tasks must be processed exactly once, fairly distributed         |
| **Topic exchange, many subscribers, all win** | #2 step events, #3 discovery/heartbeat, #4 config push, #5 cancel | Broadcasts where every interested party needs its own copy       |
| **DLX sidecar on every queue**                | #6 poison routing                                 | Parking lot for messages no consumer can handle                  |

Patterns 2–5 are *the same RMQ pattern* with different routing-key
namespaces. Once you've internalised topic + own-queue + wildcard
binding, you have four of the six.

---

## 8. Pattern internals — who actually decides what?

A common misconception: "RabbitMQ knows about my jobs / poison
messages / config." It doesn't. RabbitMQ moves opaque byte-blobs along
queues per the topology you declared. Every interesting decision in
the six patterns above is made by Python code in `magellon-sdk` that
*uses* RMQ as plumbing.

This section walks the three patterns where the dumb-broker /
smart-worker split most often confuses readers.

### 8.1 DLQ — the worker classifies poison; RMQ just routes

Two layers, often conflated:

| Layer | Owns | Where it lives |
|---|---|---|
| **Plumbing** — "if this message is nack'd-without-requeue, route it to *this* DLQ" | RabbitMQ | Queue declaration arguments: `x-dead-letter-exchange` + `x-dead-letter-routing-key` |
| **Decision** — "this exception means poison, not transient failure" | Python (the worker) | `magellon_sdk/errors.py::classify_exception` |

Per-message flow:

1. Binder hands the envelope to `PluginBrokerRunner._handle_task`
   (`runner/plugin_runner.py:142`).
2. Plugin's `execute()` runs. Returns → ack. Raises → propagates back
   to the binder.
3. Binder calls `classify_exception(exc, redelivery_count=N)`. Returns
   one of `ACK` / `REQUEUE` / `DLQ`. Rules in priority order:
   - `PermanentError` → `DLQ` immediately.
   - `RetryableError` → `REQUEUE` (with the plugin's optional
     `retry_after_seconds` hint).
   - Untyped exception → `REQUEUE` until `redelivery_count >= 3`,
     then `DLQ`. Tracked via the `x-magellon-redelivery` header the
     binder increments per nack-requeue.
4. Binder translates the action: `ACK` → `basic_ack`; `REQUEUE` →
   `basic_nack(requeue=True)`; `DLQ` → `basic_nack(requeue=False)`.

The fourth step is where RMQ's DLX involvement begins and ends. It
sees `requeue=False`, looks at the queue's `x-dead-letter-exchange`
arg, routes the bytes accordingly. RMQ at no point inspected the
exception, the message body, or the redelivery count.

A plugin opts into fast DLQ routing by raising `PermanentError`
explicitly. Otherwise the runner gives it three retries before giving
up — protects against poison loops when a plugin raises an untyped
exception.

### 8.2 Cancellation — RMQ doesn't know what a job is

A queue is an opaque list of byte-blobs. RMQ has no knowledge that
delivery #1 and delivery #5 both belong to "job 1234". It can't
filter "drop everything for job 1234" because it never parsed your
envelope. So you need code that *does* understand the envelope.

Magellon has two mechanisms, both Python:

**Mechanism A — cooperative cancel (G.1, default).** Operator clicks
"Cancel" → CoreService publishes `CancelMessage(job_id=1234)` on
`magellon.plugins.cancel.1234` → every plugin replica's bus
subscription catches it (`bus/services/cancel_registry.py:153`) and
adds `"1234"` to a `Set[str]` in process memory. When a replica next
pulls a task from `ctf_tasks_queue` whose `job_id` is 1234, the first
`reporter.started()` checkpoint inside `plugin.run()` looks at the
registry and raises `JobCancelledError`. The runner catches the
raise (`runner/plugin_runner.py:168`), publishes a FAILED-with-
`output_data["cancelled"]=True` result, and acks. The task drains in
milliseconds.

The queued tasks for job 1234 are **not** removed from the queue.
They get delivered normally, and each replica short-circuits on
arrival. No queue mutation needed.

**Mechanism B — queue purge (P9, hard-stop).**
`POST /cancellation/queues/purge` calls
`bus.tasks.purge(TaskRoute.named(...))`, which is the one place RMQ
*does* drop messages — `channel.queue_purge(queue_name)`. But this is
category-wide ("drop ALL pending CTF work"), not per-job. Use it for
runaway plugins or queues full of stale work, not for normal
cancellation.

So "RMQ should handle it, right?" — no, by design. Per-job filtering
needs envelope inspection, which is a Python concern.

### 8.3 Dynamic config — broker is the delivery mechanism, not the store

A `ConfigUpdate` push is just an `Envelope` published on
`magellon.plugins.config.<category>` (or `.broadcast`). Each plugin
replica subscribes to `magellon.plugins.config.>` and filters by
`update.target` in Python (`config_broker.py:278`). Filtering on the
client side — RMQ doesn't know which `target` field this replica
cares about; it just delivers every wildcard-matching message and
lets Python decide.

The non-obvious part is **when** the config is applied:

```python
# config_broker.py:259
def deliver(self, message: ConfigUpdate) -> None:
    with self._lock:
        # version check, then:
        self._pending.update(message.settings)   # buffer only
```

```python
# runner/plugin_runner.py:303
def _apply_pending_config(self) -> None:
    pending = self._config_subscriber.take_pending()  # atomic drain
    if pending:
        self.plugin.configure(pending)
```

`_apply_pending_config()` runs at the **start of each task** delivery
(`_handle_task:161`), never during one. A config update arriving
mid-execute lands in the buffer immediately, but the plugin doesn't
see it until the current task finishes. Trade: one task's worth of
latency on a config rollout in exchange for never racing a running
`execute()`. Worth it.

**Persistence — the `persistent` flag.** A push marked
`ConfigUpdate.persistent=True` is also written to a per-replica local
file by the subscriber (when constructed with a `persisted_path`).
On boot the subscriber loads the file and primes its buffer, so the
first `configure()` call after restart sees the operator's last
persistent push. Non-persistent pushes (the default) stay in-memory
only — same as before. This solves the "operator pushed
`max_defocus=5.0` last week, plugin restarted, lost it" gap.

**What it does NOT solve — cross-replica consistency.** Each replica
writes its own local file. A replica that was offline during the
push has stale state; a new replica added later starts empty. The
production-grade fix is a centralized store fronting the bus
(Spring Cloud Config / Consul KV pattern): CoreService persists
config in MySQL, plugins fetch on boot, the bus message becomes a
"refetch" notification rather than carrying the value itself.
Tracked as a Phase 2 follow-up.

**What belongs where.** Credentials and infrastructure config (broker
host, DB URL) belong in env vars and YAML — managed by the deploy
system. Operator-tuned runtime values (algorithm knobs, log levels)
belong in the bus push path. The `persistent` flag is the marker
that says "this is the kind of value that should survive restart."

### The thread

> RMQ moves bytes; Python interprets them.

Every "smart" feature in the patterns above lives in `magellon-sdk`,
not in the broker. That's why the same patterns transfer to NATS or
the in-memory binder — the decision-making code doesn't change, only
the transport plumbing underneath does.

---

## 9. Implications for alternate transports

This is the lens the message-bus abstraction was designed for. Mapping
the three shapes onto candidate transports:

| Transport                     | Shape #1 (work queue)                       | Shape #2 (topic fanout)                              | Shape #3 (DLX/DLQ)                                |
|-------------------------------|---------------------------------------------|------------------------------------------------------|---------------------------------------------------|
| **RabbitMQ** (today)          | Native — durable queue + prefetch + ack     | Native — topic exchange + per-consumer queue         | Native — `x-dead-letter-exchange` arg             |
| **NATS JetStream** (in tree)  | Native — pull consumer on a stream          | Native — subjects with `>` wildcards                 | Native — max-deliver + DLQ stream                 |
| **Redis Streams**             | Consumer groups (`XREADGROUP`)              | Pub/sub or per-stream fanout (more wiring)           | Hand-rolled — write a "dead" stream on max retry  |
| **Cloudflare Durable Objects**| One DO per queue holding a list + alarm     | One DO per topic holding subscriber WS connections   | Hand-rolled — store failed messages in DO storage |
| **Cloudflare Queues**         | Native — push to Worker consumer            | **Missing** — no fanout / no topics                  | Native — DLQ binding                              |
| **Upstash QStash**            | Push to HTTPS endpoint                      | **Missing** — single-target webhook only             | Native — retry + DLQ to a different URL           |

The cells that read "missing" are why CF Queues and QStash aren't
drop-in replacements for Magellon's RMQ — patterns #2/#3/#4/#5 (four
of the six) all need shape #2, which neither provides.

DO is the most interesting outlier: every cell is achievable, but
several say "hand-rolled." That's the right summary — DO is a building
block, RMQ is a finished product.

---

## 10. Where to read next

- **`MESSAGE_BUS_SPEC.md`** — the abstraction that lets us swap
  transports without rewriting plugins.
- **`MESSAGES_AND_EVENTS.md`** — the envelope on the wire that travels
  through any of these patterns.
- **`CURRENT_ARCHITECTURE.md` §4.1 + §6** — how the patterns above
  compose into the actual end-to-end flow today.
- **`DLQ_MIGRATION_RUNBOOK.md`** — operational side of pattern #6 for
  queues declared before DLQ existed.


---

<!--
  Section: 6. Messages and Events
  Originated from: Documentation/MESSAGES_AND_EVENTS.md
  Merged into this consolidated reference 2026-05-13.
-->

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

The live, production path. CoreService publishes `TaskMessage` bodies onto
a per-plugin **task** queue; each plugin publishes `TaskResultMessage`
bodies onto a per-plugin **result** queue that CoreService consumes via
its in-process `TaskOutputProcessor`.

### 1.1 Queues

| Queue name (default) | Direction | Carries | Consumer |
|----------------------|-----------|---------|----------|
| `ctf_tasks_queue`         | CoreService → CTF plugin         | `TaskMessage[CtfInput]`              | `magellon_ctf_plugin` |
| `ctf_out_tasks_queue`     | CTF plugin → CoreService          | `TaskResultMessage`                      | CoreService in-process `TaskOutputProcessor` |
| `motioncor_tasks_queue`   | CoreService → MotionCor plugin    | `TaskMessage[MotionCorInput]`   | `magellon_motioncor_plugin` |
| `motioncor_out_tasks_queue` | MotionCor plugin → CoreService  | `TaskResultMessage`                      | CoreService in-process `TaskOutputProcessor` |
| `motioncor_test_inqueue`  | (dev) CoreService → MotionCor      | `TaskMessage`                            | test harness only |
| `motioncor_test_outqueue` | (dev) MotionCor → CoreService      | `TaskResultMessage`                      | test harness only |

Queue names come from `RabbitMQSettings` (`models/pydantic_models_settings.py`)
and are mapped from task-type code in `core/helper.py::get_queue_name_by_task_type`.

> **Task-type → queue** mapping was hardcoded by integer code (2 = CTF,
> 5 = MotionCor). `magellon_sdk.dispatcher.TaskDispatcherRegistry` now
> owns this mapping — each plugin registers its own dispatcher (RMQ or
> in-process) and routes by `TaskCategory.code`. `get_queue_name_by_task_type`
> remains for now; call-site migration is a follow-up.

### 1.2 Envelope: `TaskMessage`

Schema: `magellon_sdk.models.tasks.TaskMessage` (Pydantic v2). Serialized as
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

class TaskMessage(TaskBase):
    job_id: Optional[UUID] = default uuid4()
```

**Per-plugin `data` shapes** (also in `magellon_sdk.models.tasks`):

- `CtfInput` — `inputFile`, `outputFile`, `pixelSize`, `accelerationVoltage`, `sphericalAberration`, `amplitudeContrast`, `sizeOfAmplitudeSpectrum`, `minimumResolution`, `maximumResolution`, `minimumDefocus`, `maximumDefocus`, `defocusSearchStep`, `binning_x`
- `MotionCorInput` — MotionCor2 CLI flags (`InMrc`/`InTiff`/`InEer`, `Gain`, `Dark`, `PatchesX/Y`, `Iter`, `Bft`, `FtBin`, `PixSize`, `kV`, …). Full list: see source.

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

### 1.3 Envelope: `TaskResultMessage`

Schema: `magellon_sdk.models.tasks.TaskResultMessage`. Serialized JSON.

```python
class TaskResultMessage(BaseModel):
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
| Task dispatch | `core/helper.py::publish_message_to_queue` via `TaskMessage.model_dump_json()` | plugin's `core/rabbitmq_consumer_engine.py` |
| Task result | plugin's `core/result_publisher.py` | CoreService `services/task_output_processor.py` (in-process) |

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
| `job_update`     | Full `JobMessage`-like dict (status, progress, …) | `JobManager.*` via `emit_job_update()` |

**Rooms:** all events are either broadcast (no `room`) or addressed to
a specific `sid`. No per-job rooms yet — Phase 4 should introduce
`room=job:<job_id>` so the UI can subscribe to one job without decoding
every update.

**In-process vs. external plugins:** Today `JobReporter` (see
`plugins/progress.py`) writes directly to `JobManager` and forwards to
Socket.IO via `asyncio.run_coroutine_threadsafe`. External plugins
(dispatched via RabbitMQ) do **not** reach this emitter — their
progress is invisible to the UI until a final `TaskResultMessage` lands.
Closing this gap is Phase 4.

---

## 4. Known gaps + pending changes

| Gap | Phase | Notes |
|-----|-------|-------|
| ~~Hardcoded task-type → queue switch~~ | 6 (done) | `magellon_sdk.dispatcher` ships `TaskDispatcher` Protocol + `RabbitmqTaskDispatcher` + `InProcessTaskDispatcher` + `TaskDispatcherRegistry`. 11 unit tests. CoreService migration of `get_queue_name_by_task_type` call sites is a follow-up. |
| External plugin progress invisible to UI | 4 (partial) | Plumbing deferred — see Phase 4.5 below. Today's step: at least final state lands in DB so UI moves past "pending". |
| ~~`TaskOutputProcessor` never advances `ImageJobTask.status_id/stage`~~ | 4 (done) | Result processor now writes `status_id` (COMPLETED / FAILED) and `stage` (MotionCor=1, CTF=2, unknown=99) on the `image_job_task` row keyed by `task_result.task_id`. 5 mocked-DB unit tests. |
| Plugin-progress pipe to UI | 4.5 (publisher half done) | SDK ships `magellon_sdk.events.StepEventPublisher` + `StepStartedMessage`/`StepProgressMessage`/`StepCompletedMessage`/`StepFailedMessage` payloads + subject helper. Plugins can now emit `magellon.step.*` CloudEvents. CoreService Socket.IO forwarder is still TODO. |
| `support/events/publisher.py` + `subscriber.py` still importable as FastAPI apps | 2 | Keep as thin shims around `magellon_sdk.transport.nats` — migration in this phase. |
| DLQ on task queues | 3 (capability landed) | `RabbitmqClient.declare_queue_with_dlq(name)` now declares a queue + matching `<name>_dlq` with `x-dead-letter-exchange`/`x-dead-letter-routing-key` set. Rejected/expired messages land on the DLQ instead of the floor. New plugin queues should opt in; existing queues (`ctf_tasks_queue`, `motioncor_tasks_queue`) need a broker-policy migration because re-declaring them with new `x-*` args is a `PRECONDITION_FAILED`. |
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


---

<!--
  Section: 7. Categories and Backends
  Originated from: Documentation/CATEGORIES_AND_BACKENDS.md
  Merged into this consolidated reference 2026-05-13.
-->

# Magellon — Categories, Backends, and Wire-Shape Naming

**Status:** Canonical. Track C shipped 2026-04-27 (X.1 `0a3f216`,
X.2 `581518f`, X.3 `4639990`). SDK 1.2 → 1.3 → 2.0. Updated
2026-05-03 with the new aggregate-category seam (subject_kind on
CategoryContract + TaskMessage) and the two new categories
`PARTICLE_EXTRACTION` (code 10) + `TWO_D_CLASSIFICATION` (code 4)
landed end-to-end. See `IMPLEMENTATION_PLAN.md` "Track C" + the
2026-05-03 rollout in `CURRENT_ARCHITECTURE.md` §12.
**Audience:** Architects, plugin developers adding a second backend
under an existing category, callers using `target_backend`.
**Companion:** `ARCHITECTURE_PRINCIPLES.md`, `CURRENT_ARCHITECTURE.md`,
`MESSAGE_BUS_SPEC.md`,
`memory/project_artifact_bus_invariants.md` (the five ratified
rules driving the new aggregate-category work).

This doc proposes three additions on top of the live plugin platform:

1. A **backend** layer — a named, second axis underneath every category.
2. A **capabilities endpoint** — one URL the dispatcher and the UI both
   read for "what categories exist, what backends serve each one,
   which is the default."
3. A **wire-shape naming rule** — every class that crosses the bus ends
   in either `Envelope` or `Message`. Static metadata classes do not.

It does not change the data plane, the bus binders, or job-row
ownership. It is additive (principle 6) and reversible until the final
rename PR.

---

## 1. Why a backend layer

A `TaskCategory` answers *"what kind of work is this?"* — `CTF`,
`MOTIONCOR`, `TOPAZ_PARTICLE_PICKING`. Today, when several plugins
implement the same category, RabbitMQ round-robins between them and
CoreService picks one default per category via
`POST /plugins/categories/{category}/default`
(`plugins/controller.py:691`).

That mechanism works, but the second axis is unnamed in the wire
contract. A caller has no clean way to say *"run this CTF on ctffind4
specifically, not on whatever happens to be the current default."*
Operators who run two CTF engines side-by-side (one CPU, one GPU) for
A/B comparison have no place to record that intent on the task itself.
Logs and provenance say `plugin_id="CTF Plugin"` — uninformative when
two plugins share a category.

The fix is to give that second axis a first-class name and let it ride
on the message.

### Vocabulary: backend, not engine or impl

We use **backend**. Reasons:

- "engine" already means the algorithm itself in cryo-EM literature
  (CTF *engine* = ctffind4 vs gctf as code). Keeping it for the
  algorithm and using "backend" for the platform's substitutable slot
  avoids overloading the word.
- "impl" is the term used inside `_resolve_dispatch_target`. It is
  internal-shorthand, not user-facing. A UI label saying "Default
  impl: ctffind4" reads worse than "Default backend: ctffind4".
- RabbitMQ literature uses `provider`/`variant` interchangeably; we
  pick one term and stick with it.

**Web research confirms** the topic-exchange pattern of
`<category>.<variant>.<...>` is the canonical RabbitMQ approach for a
hierarchical second axis. See sources at the bottom of this doc.

### Backend identity

A backend is identified by a short `backend_id` — lowercase,
alphanumeric, dot-free:

```
ctffind4
gctf
gocsf
motioncor2
motioncor3
topaz
template-picker
```

One plugin = one backend. One backend can be live in multiple replicas
(scale-out); they all share the `backend_id` and the round-robin
behaviour stays. The combination
`(category, backend_id)` is the routable identity.

---

## 2. How backend rides the wire

### 2.1 PluginManifest carries `backend_id`

```python
class PluginManifest(BaseModel):
    info: PluginInfo
    backend_id: str          # NEW — required as of SDK 1.2
    capabilities: list[Capability] = []
    ...
```

Plugin authors set it once; everything else (announce subject, default
queue name, provenance stamp on `TaskResultMessage`) derives from it.

### 2.2 CategoryContract enumerates backends at registry time

```python
class CategoryContract(BaseModel):
    category: TaskCategory
    input_model: Type[BaseModel]
    output_model: Type[CategoryOutput]

    # 2026-05-03 (Phase 3d): the kind of entity tasks of this
    # category operate on. Default 'image'; aggregate categories
    # override (TWO_D_CLASSIFICATION_CATEGORY → 'particle_stack').
    # PluginBrokerRunner._stamp_subject falls back to this when
    # neither dispatch nor plugin set TaskMessage.subject_kind.
    subject_kind: str = "image"

    # NEW — populated by the liveness registry, not hand-coded.
    @property
    def known_backends(self) -> list[str]: ...

    # NEW — the operator-pinned default; falls back to first-seen
    # when unset. Same data the H1 default-impl selector already
    # tracks, just exposed under the "backend" name.
    @property
    def default_backend(self) -> str | None: ...
```

The contract object stays immutable; the live `known_backends` /
`default_backend` views read from `PluginLivenessRegistry` and
`PluginStateStore`. The contract is still the single source of truth
for I/O shape.

### 2.2a Subject axis (Phase 3, 2026-05-03)

Pre-Phase-3 every task was image-keyed: `image_job_task.image_id`
FK + `CryoEmImageInput.image_id` field. The CAN classifier doesn't
fit — its input is a particle stack drawn from M micrographs, not
a single image. The subject axis generalises the model:

| Surface | Field added | Notes |
|---|---|---|
| `TaskMessage` / `TaskResultMessage` | `subject_kind: Optional[str]` + `subject_id: Optional[UUID]` | None defaults; pre-Phase-3 callers unchanged. |
| `image_job_task` (alembic 0004) | `subject_kind` VARCHAR(32) NOT NULL DEFAULT `'image'` + `subject_id` UUID nullable | Per ratified rule 4: VARCHAR + app validation, never MySQL ENUM (the table is tens-of-millions of rows; ENUM ALTER is a multi-hour migration). Migration backfills `subject_id = image_id`. |
| `CategoryContract` | `subject_kind: str = "image"` | Declarative seam — `TWO_D_CLASSIFICATION_CATEGORY` overrides to `'particle_stack'`. |

Allowed values: `image | particle_stack | session | run | artifact`.
The runner's `_stamp_subject` precedence is **plugin-set on result >
task-set on dispatch > contract default**. Authoritative writes
still come from dispatch; the projector backfills only when dispatch
left columns at their DDL default (back-compat seam).

### 2.3 TaskMessage gains `target_backend`

```python
class TaskMessage(BaseModel):           # was TaskDto
    id: UUID
    job_id: UUID
    type: TaskCategory
    target_backend: Optional[str] = None  # NEW
    data: Dict[str, Any]
    ...
```

- `target_backend = None` → category-wide round-robin (today's
  behaviour, unchanged).
- `target_backend = "ctffind4"` → dispatch only to a backend whose
  manifest declares that id. If none is live, dispatch fails with a
  503 (same shape as `_resolve_dispatch_target` returns today).

### 2.4 Bus subjects get an optional fourth segment

Subjects today:

```
magellon.tasks.<category>             # task dispatch (broadcast)
magellon.tasks.<category>.result      # results
```

Subjects after this PR:

```
magellon.tasks.<category>                       # category-wide
magellon.tasks.<category>.<backend>             # backend-pinned (NEW)
magellon.tasks.<category>.result                # results
magellon.tasks.<category>.result.<backend>      # backend-stamped result (NEW)
```

RabbitMQ topic exchanges natively support this (sources below):
plugin queues bind on `magellon.tasks.<category>.*` so they receive
both shapes. The fourth segment is information for the dispatcher,
not a separate routing path.

The category-wide subject stays the default. **A backend-pinned
subject is only used when `target_backend` is set on the message.**
Operators flipping the per-category default does not change the
message shape — it changes which backend wins the round-robin on the
category-wide subject.

### 2.5 Routing rule (one paragraph)

`_BusTaskDispatcher.dispatch(task)`:

1. If `task.target_backend` is set, validate that backend is live for
   `task.type`. If yes, publish to
   `magellon.tasks.<category>.<backend>`. If no, raise — do not
   silently fall back to the default.
2. Else publish to `magellon.tasks.<category>` (today's path).

This satisfies principle 4: it pays its way today on two named
call sites — the operator A/B comparison case, and the importer
that already knows it wants MotionCor3 over MotionCor2 for tilt
series.

---

## 3. The capabilities endpoint

### 3.1 Why one consolidated endpoint

Today the discovery surface is split across:

- `GET /plugins/` — every plugin instance, with manifest excerpts
- `GET /plugins/categories/defaults` — the per-category default-impl
  map
- `GET /plugins/{id}/manifest` — full manifest per plugin

A UI wanting to render a "pick a backend" widget calls all three and
joins them in JS. The dispatcher reads the same data from
`get_liveness_registry()` and `get_state_store()`. Two readers, three
URLs, one shape that should be canonical.

The new endpoint collapses them:

```
GET /plugins/capabilities
```

returns one object that the UI renders directly and the dispatcher
can consume in tests:

```jsonc
{
  "categories": [
    {
      "code": 2,
      "name": "CTF",
      "description": "Contrast Transfer Function",
      "input_schema": { ... },          // CategoryContract.input_model JSON Schema
      "output_schema": { ... },
      "default_backend": "ctffind4",
      "backends": [
        {
          "backend_id": "ctffind4",
          "plugin_id": "ctf/CTF Plugin",
          "version": "0.4.1",
          "schema_version": "1",
          "capabilities": ["cpu_intensive", "idempotent"],
          "isolation": "container",
          "transport": "rmq",
          "live_replicas": 2,
          "enabled": true,
          "is_default_for_category": true,
          "task_queue": "ctf_tasks_queue"
        },
        {
          "backend_id": "gctf",
          "plugin_id": "ctf/gCTF",
          "version": "0.2.0",
          "capabilities": ["gpu_required", "idempotent"],
          ...
        }
      ]
    },
    { "code": 5, "name": "MotionCor", ... }
  ],
  "sdk_version": "0.1.0"
}
```

One read, one snapshot, every consumer aligned. Existing endpoints
stay (principle 6: additive first); they will only be removed if the
follow-up demonstrates they have no callers.

### 3.2 Dispatcher uses the same store, not the endpoint

The dispatcher stays a process-local registry — it reads
`PluginLivenessRegistry` directly, not its own HTTP endpoint. The
capabilities endpoint *projects* that store; the dispatcher
*queries* it. That keeps dispatch off the network and keeps the
"one logical owner per concept" principle (#2) intact: the registry
is the single source of backend availability.

### 3.3 Backend-pin-on-dispatch HTTP shape

The submit endpoints need an optional knob to surface backend pinning:

```
POST /plugins/{plugin_id}/jobs
{
  "input": { ... },
  "target_backend": "gctf"      // NEW — optional
}

POST /tasks/dispatch
{
  "category": "CTF",
  "data": { ... },
  "target_backend": "gctf"      // NEW — optional
}
```

The existing `plugin_id`-based form is preserved; specifying the full
`<category>/<plugin_id>` already pinned a backend in practice. The
new field is the clean way to do it for category-scoped callers.

---

## 4. Wire-shape naming rule

### 4.1 The rule

Every class that **crosses the bus or HTTP wire** ends in:

| Suffix     | Use                                                                                              |
|------------|--------------------------------------------------------------------------------------------------|
| `Envelope` | The CloudEvents 1.0 wrapper (`Envelope[DataT]` in `magellon_sdk.envelope`). One class only.      |
| `Message`  | Any payload that goes inside `Envelope.data`, OR is itself the body of a request/response/event. |

Static metadata, contracts, and value objects do **not** carry these
suffixes. They are nested or referenced — they don't travel
standalone.

### 4.2 Worked classification

| Current name              | Wire shape? | Final name                  | Notes |
|---------------------------|-------------|-----------------------------|-------|
| `Envelope[DataT]`         | yes (outer) | `Envelope[DataT]`           | unchanged |
| `TaskDto`                 | yes         | `TaskMessage`               | what we put inside `Envelope.data` for `magellon.tasks.*` |
| `TaskBase`                | —           | *deleted*                   | only `TaskDto` and `JobDto` extended it; collapse |
| `JobDto`                  | yes         | `JobMessage`                | bundle of tasks; rare on the wire today but kept symmetric |
| `TaskResultDto`           | yes         | `TaskResultMessage`         | `magellon.tasks.*.result` body |
| `TaskOutcome`             | nested      | `TaskOutcome`               | embedded inside TaskMessage; not a message itself |
| `TaskStatus`              | nested      | `TaskStatus`                | value object |
| `TaskCategory`            | nested      | `TaskCategory`              | value object |
| `CancelMessage`           | yes         | `CancelMessage`             | already correct |
| `StepStarted`             | yes (data)  | `StepStartedMessage`        | inside `Envelope[StepStartedMessage]` |
| `StepProgress`            | yes (data)  | `StepProgressMessage`       | same |
| `StepCompleted`           | yes (data)  | `StepCompletedMessage`      | same |
| `StepFailed`              | yes (data)  | `StepFailedMessage`         | same |
| `CryoEmImageTaskData`     | nested      | `CryoEmImageInput`          | inside `TaskMessage.data`; symmetric with `*Output` |
| `CtfTaskData`             | nested      | `CtfInput`                  | symmetric with `CtfOutput` |
| `FftTaskData`             | nested      | `FftInput`                  | symmetric with `FftOutput` |
| `CryoEmMotionCorTaskData` | nested      | `MotionCorInput`            | symmetric with `MotionCorOutput` |
| `MicrographDenoiseTaskData` | nested    | `MicrographDenoiseInput`    | etc. |
| `TopazPickTaskData`       | nested      | `TopazPickInput`            | etc. |
| `PtolemyTaskData`         | nested      | `PtolemyInput`              | etc. |
| `MrcToPngTaskData`        | nested      | `MrcToPngInput`             | etc. |
| `*Output` (CtfOutput, …)  | nested      | unchanged                   | already symmetric, no suffix |
| `CategoryContract`        | metadata    | unchanged                   | not a wire shape |
| `PluginInfo`, `PluginManifest`, `PluginStatus`, `Capability`, `Transport`, `IsolationLevel`, `ResourceHints`, `RequirementResult`, `CheckRequirementsResult` | metadata | unchanged | descriptive, not transmitted as standalone messages |
| `ImageMetaData`, `OutputFile`, `Detection`, `Particle`, `DebugInfo` | nested | unchanged | embedded sub-types |
| `PluginArchiveManifest`   | metadata    | unchanged                   | install-time descriptor |

Concrete-task subclasses (`FftTask`, `CtfTask`, `MotioncorTask`)
collapse out — once `*TaskData` becomes `*Input` and `TaskMessage`
generalises, the typed `TaskMessage[CtfInput]` form replaces them.

### 4.3 Why this rule and not "just rename Dto"

The existing `*Dto` set is mixed: `TaskDto` and `TaskResultDto` are
true wire envelopes; `*TaskData` is *not* — it's a nested input.
Picking `Message` as the suffix only for actual wire envelopes
preserves the boundary the codebase already drew. Using `*Input` /
`*Output` for nested shapes mirrors the symmetry already present in
`categories/outputs.py`.

---

## 5. Phasing

Three PR sequence, every step `git revert`-safe (principle 6).

### Phase X.1 — Add backend layer + capabilities endpoint (additive)

- Add `backend_id: str` to `PluginManifest`. Default to
  `info.name.lower().replace(" ", "-")` for one release so existing
  plugins don't break; deprecation-warn at startup.
- Add `target_backend: Optional[str]` to `TaskMessage` (today's
  `TaskDto`). Default `None`.
- Wire `_BusTaskDispatcher` to honour `target_backend` per §2.5.
- Add `GET /plugins/capabilities`.
- Bind plugin queues to `magellon.tasks.<category>.*` in addition to
  `magellon.tasks.<category>` (one extra binding per queue, RMQ
  topic exchange is fine with both).
- Tests: contract tests (`tests/contracts/`) gain a backend-pin case.
  `_resolve_dispatch_target` gets two new cases: pin matches, pin
  misses (503).

**No renames yet.** Today's call sites keep working unchanged.

### Phase X.2 — Wire-shape rename (alias + migrate)

- Add new names as aliases:
  ```python
  TaskMessage = TaskDto
  TaskResultMessage = TaskResultDto
  JobMessage = JobDto
  CtfInput = CtfTaskData
  ...
  StepStartedMessage = StepStarted
  ...
  ```
- Migrate call sites to import the new names. CoreService first,
  plugins second, tests third.
- Update characterization goldens in
  `CoreService/tests/characterization/`.
- Documentation walk-through (this file, `CURRENT_ARCHITECTURE.md`,
  `MESSAGES_AND_EVENTS.md`).

### Phase X.3 — Drop the aliases

- Remove `TaskDto = TaskMessage` shims and the legacy class names.
- Delete `models/plugins_models.py`'s shim if every CoreService call
  site is on the new names.
- Bump `magellon_sdk` to 0.2.0; bump `PluginInfo.schema_version`.

Plugins that haven't migrated still get a deprecation warning at
import for one release before the rename hits.

---

## 6. Risks and how to read them

- **Backend pinning over-used.** If callers reflexively set
  `target_backend`, we lose the round-robin. Mitigation:
  category-wide is the default in every importer code path; the
  field is opt-in.
- **Plugin authors hand-pick a `backend_id` that collides.** Two
  plugins claim `backend_id="ctffind4"` and the dispatcher can't
  tell them apart. Mitigation: the liveness registry rejects a
  second announce with the same `(category, backend_id)` and a
  different `plugin.version` — one of them has to rename. CoreService
  logs a `DUP_BACKEND_ID` warning to make the conflict visible.
- **Rename churn.** Phase X.2 touches every plugin. Mitigation: the
  alias landing is mechanical (one PR, one search-and-replace per
  caller); the alias-removal PR can wait a release behind it
  (principle 6).

---

## 7. What this document does not change

- **Two planes** (principle 1). Backends are control-plane only;
  bytes still flow on the data plane.
- **One job-row writer** (principle 2). `JobService` /
  `JobManager` still own the job lifecycle.
- **Existing CategoryContract I/O shapes.** `input_model` and
  `output_model` are unchanged; `*Input` / `*Output` rename is a
  type rename, not a schema change.
- **NATS / RMQ binder split.** Bus binders are unaffected.

---

## 7a. Live category catalogue (2026-05-03)

| Category | Code | Subject kind | Input model | Output model | Live backends (`backend_id`) |
|---|---|---|---|---|---|
| `FFT` | 1 | `image` | `FftInput` | `FftOutput` | `fft` (magellon_fft_plugin) |
| `CTF` | 2 | `image` | `CtfInput` | `CtfOutput` | `ctf` (magellon_ctf_plugin) |
| `PARTICLE_PICKING` | 3 | `image` | `CryoEmImageInput` (no canonical input model yet) | `ParticlePickingOutput` | `pp/template-picker` (in-process) + `template-picker` (external, Phase 6 / 2026-05-03) |
| `TWO_D_CLASSIFICATION` | 4 | **`particle_stack`** | `TwoDClassificationInput` | `TwoDClassificationOutput` | `can-classifier` (Phase 7 / 2026-05-03) |
| `MOTIONCOR` | 5 | `image` | `MotionCorInput` | `MotionCorOutput` | `motioncor` (magellon_motioncor_plugin) |
| `SQUARE_DETECTION` | 6 | `image` | `PtolemyInput` | `SquareDetectionOutput` | `ptolemy/square` (magellon_ptolemy_plugin) |
| `HOLE_DETECTION` | 7 | `image` | `PtolemyInput` | `HoleDetectionOutput` | `ptolemy/hole` (magellon_ptolemy_plugin) |
| `TOPAZ_PARTICLE_PICKING` | 8 | `image` | `TopazPickInput` | `ParticlePickingOutput` | `topaz` (magellon_topaz_plugin) |
| `MICROGRAPH_DENOISING` | 9 | `image` | `MicrographDenoiseInput` | `MicrographDenoisingOutput` | `topaz-denoise` (magellon_topaz_plugin) |
| `PARTICLE_EXTRACTION` | 10 | `image` | `ParticleExtractionInput` | `ParticleExtractionOutput` | `stack-maker` (Phase 5 / 2026-05-03) |

Subject-kind column distinguishes the only aggregate-input category
(`TWO_D_CLASSIFICATION`) from the rest. Per ratified rule 7
(extraction is per-mic, not session-merged), `PARTICLE_EXTRACTION`
stays image-keyed even though its OUTPUT is a `particle_stack`
artifact.

---

## 8. Open questions

1. **`target_backend` placement.** Inline on `TaskMessage` (chosen
   above) vs as a CloudEvents extension on `Envelope`
   (`ce_target_backend`). Inline is simpler for today; the extension
   form would survive an envelope-reshape. Decision: inline for now,
   re-evaluate when MB7 (NATS binder) lands.
2. **Per-backend DLQ.** Does a poison message on the
   `<category>.<backend>` subject route to a backend-scoped DLQ, or
   the category DLQ? Today's DLQ topology is per-queue, so the
   answer is "category DLQ" until X.1 ships and the operational
   experience says otherwise.
3. **Health vs `live_replicas`.** The capabilities endpoint exposes
   `live_replicas` as a count. Operators have asked for per-replica
   health. Out of scope for this doc; tracked separately.

---

## 9. Sources

- [RabbitMQ topic exchanges and hierarchical routing keys](https://www.rabbitmq.com/tutorials/tutorial-five-python)
- [RabbitMQ topic exchanges (CloudAMQP)](https://www.cloudamqp.com/blog/rabbitmq-topic-exchange-explained.html)
- [Celery routing — separate queues vs headers](https://docs.celeryq.dev/en/stable/userguide/routing.html)
- [CloudEvents Java SDK + Spring `Message` mapping](https://cloudevents.github.io/sdk-java/spring.html)
- [MassTransit CloudEvents discussion (envelope vs `Message`)](https://github.com/MassTransit/MassTransit/discussions/2539)
- [Knative Eventing CloudEvents `type` convention](https://knative.dev/docs/eventing/event-registry/)
- [Kubernetes aggregated discovery endpoint pattern (`/api`, `/apis`, `/openapi/v3`)](https://kubernetes.io/docs/concepts/overview/kubernetes-api/)


---

<!--
  Section: 8. CryoEM Pipeline Walk-through
  Originated from: CoreService/docs/cryo-em-pipeline.md
  Merged into this consolidated reference 2026-05-13.
-->

# Cryo-EM pipeline tutorial — for the dev team

A walk-through of the full single-particle cryo-EM workflow, from a
microscope session to a published 3D structure. Aimed at developers
who haven't seen it before — explains *what* each step is, *why* it
matters, *which* RELION binary runs it, and *where* Magellon plugs in.

If you only know microscopy at the "it makes a picture of small
things" level, start here. If you've used RELION's GUI and just need
to know the CLI shape, skip to the [pipeline table](#the-pipeline-at-a-glance).

## Why this document exists

The cryo-EM workflow has ~12 distinct stages, each producing inputs
for the next. Some stages cost minutes, others cost a day on 8 GPUs.
Magellon orchestrates them as queue tasks; to plug a new tool in
correctly you need to know what each stage actually does to the
data. The vocabulary is dense (defocus astigmatism, gold-standard FSC,
Bayesian polishing) but the underlying ideas are not.

## The 30-second mental model

> A cryo-EM dataset is a few thousand to a few million 2D images of
> the same molecule frozen at random orientations. Each image is one
> projection of the 3D molecular density. The job of the pipeline is
> to figure out which orientation each image came from, then back-
> project all the images into one 3D density map.

Everything else is making that work in the presence of noise, motion,
imaging artefacts, and conformational heterogeneity.

## What a microscope session produces

A modern cryo-EM session on a 300 kV Krios with a Falcon 4i or K3
detector takes 12–48 hours and produces:

| Item | Typical size | What it is |
|---|---|---|
| **Movies** | 50–500 frames each, ~50 MB to several GB per micrograph | Each "image" is actually a movie — the detector records ~50 frames during one exposure so we can correct beam-induced motion. Stored as `.tif` (16-bit) or `.eer` (Falcon event format). |
| **Total micrographs per session** | 1k–10k | Each micrograph captures ~100–1000 particles. |
| **Pixel size** | 0.6–1.5 Å | Set by magnification × detector pixel size. |
| **Defocus range** | 0.5–3.0 µm | Deliberately spread to cover all spatial frequencies. |
| **Gain reference** | 1 file per session | Per-pixel sensitivity correction. |

Output: a **session directory** with raw movies, gain ref, and a
metadata STAR file that maps movies to acquisition parameters
(defocus, magnification, dose, etc.).

In Magellon: this is the data already on `/gpfs/<session>/rawdata/`.
The bus picks up new movies as they land.

## The pipeline at a glance

| # | Step | RELION binary | What it produces | Typical wall-clock | Magellon plugin |
|---|---|---|---|---|---|
| 1 | **Beam-induced motion correction** | `relion_run_motioncorr_mpi` (wraps MotionCor2/3) | Aligned, dose-weighted micrographs (`.mrc`) | 10–30 min for 1k movies on 4 GPUs | `magellon_motioncor_plugin` ✅ |
| 2 | **CTF estimation** | `relion_run_ctffind_mpi` (wraps CTFFIND4) | Per-micrograph defocus, astigmatism, CTF goodness | 5–10 min for 1k micrographs on 4 CPUs | `magellon_ctf_plugin` ✅ |
| 3 | **Particle picking** | `relion_autopick_mpi` (LoG / template / Topaz) | `.star` file of particle (x, y) coords per micrograph | 10–30 min | `magellon_topaz_plugin` ✅ |
| 4 | **Particle extraction** | `relion_preprocess_mpi --extract` | Particle stack (`.mrcs`) — boxes cut around each coord, normalised | 5–15 min | not yet — would be a thin plugin |
| 5 | **2D classification** | `relion_refine_mpi --K 50 ...` (no `--auto_refine`) | 50 representative 2D class averages + per-particle class assignment | 1–4 hours on 4 GPUs | not yet |
| 6 | **2D selection** | `relion_class_ranker` or manual | Cleaned `particles.star` (junk classes removed) | 5–15 min interactive | not yet |
| 7 | **Initial model** | `relion_refine_mpi --denovo_3dref` (VDAM) | A first 3D template (~10–20 Å resolution) | 30–60 min on 4 GPUs | not yet |
| 8 | **3D classification** | `relion_refine_mpi --K 4 --ref initial.mrc` | K separate 3D maps + per-particle class assignment | 4–24 hours | not yet |
| 9 | **3D refinement (gold-standard)** | `mpirun -np 3 relion_refine_mpi --auto_refine --split_random_halves` | Final 3D map + two half-maps (for FSC) | 4–24 hours | not yet |
| 10 | **CTF refinement** | `relion_ctf_refine_mpi` | Per-particle defocus + per-optics-group beam tilt + Zernike aberrations | 30–90 min | not yet |
| 11 | **Bayesian polishing** | `relion_motion_refine_mpi` | Per-particle motion correction using the 3D model as prior | 1–4 hours | not yet |
| 12 | **Refine again** | step 9 with the polished particles | Higher-resolution 3D map | 4–12 hours | not yet |
| 13 | **Postprocess** | `relion_postprocess` | Sharpened final map + FSC + resolution number | < 1 min | could fold into a plugin |
| 14 | **Local resolution** | `relion_postprocess --local_resolution` | Per-voxel resolution map | 5–15 min | not yet |
| 15 | **Atomic model building** | ModelAngelo (separate) | PDB / mmCIF | 1–6 hours | out of scope today |

A full "raw movies → publishable structure" pipeline is **typically 1–3 days** of compute on a multi-GPU workstation.

## Each step in detail

### 1. Motion correction

**Why**: each movie's frames suffer from beam-induced specimen motion
(specimen drifts ~5–50 Å during the exposure). If you sum the frames
naively you blur the image. Aligning the frames before summation
sharpens the resulting micrograph by ~2× resolution.

**What it does**: subdivides the frame into ~5×5 patches, finds
patch-wise translations between consecutive frames, fits a B-spline
to the translation field, sums dose-weighted aligned frames.

**Inputs**: movie stack + gain ref.
**Outputs**: one `.mrc` micrograph per movie + a `_PS.mrc` power-spectrum visualisation.
**Magellon today**: `magellon_motioncor_plugin` wraps MotionCor3 and is validated to 0.043 px mean error vs reference.

### 2. CTF estimation

**Why**: the microscope's lenses defocus the image to enhance contrast,
but defocus introduces a sinusoidal modulation in Fourier space (the
"Contrast Transfer Function") with spatial-frequency-dependent zeros
where signal is destroyed. To recover the signal, every later step
needs to know the CTF for each micrograph.

**What it does**: fits the CTF model `CTF(k) = sin(γ(k))` (where γ
encodes defocus, spherical aberration, voltage, amplitude contrast)
to the observed Thon rings in the micrograph's power spectrum.
Reports defocus_U, defocus_V, defocus_angle, and a goodness-of-fit.

**Inputs**: aligned micrograph.
**Outputs**: STAR row per micrograph with the CTF parameters + a diagnostic plot.
**Magellon today**: `magellon_ctf_plugin` wraps CTFFIND4 (4 backends inside the plugin: ctffind4_native reference, ctffind4_fast production, gctffind GPU, ctffind4_external).

### 3. Particle picking

**Why**: each micrograph contains 100–1000 particles in random
positions. We need to find them.

**What it does**: classical (Laplacian-of-Gaussian template
correlation, Class2D-template matching) or learned (Topaz CNN, crYOLO)
methods scan the micrograph for blob-like signals matching expected
particle size. Output: a list of (x, y) coordinates per micrograph.

**Inputs**: aligned micrograph + particle diameter (estimated from
the molecule).
**Outputs**: `coords.star` with one row per picked particle.
**Magellon today**: `magellon_topaz_plugin` provides Topaz-CNN picking; classical template-matching also exists in `magellon-rust-mrc/algorithms/particle_picker/`.

### 4. Particle extraction

**Why**: subsequent steps work on individual particle "boxes", not
whole micrographs. Cutting and normalising the boxes is its own step
because the box size and normalisation method affect resolution.

**What it does**: cuts a square region (e.g. 256×256 px) around each
coord. Normalises by subtracting the edge-ring mean and dividing by
the edge-ring stdev (the "white-edges" convention) — gives every
particle ~zero mean and unit noise stdev, which the E-M optimiser
expects. Optionally inverts contrast (cryo-EM is "dark protein on
bright background"; reconstruction expects the opposite).

**Inputs**: micrographs + coords + particle diameter.
**Outputs**: a single `.mrcs` stack (all particles concatenated) + a
`particles.star` with one row per particle and a pointer to its slice.
**Magellon today**: implemented in `magellon-rust-mrc/algorithms/spa/particle.rs`. Not yet wrapped as a CoreService plugin — would be ~1 day of work.

### 5. 2D classification — *why this matters more than it looks*

**Why**: picked particles include junk (ice contamination, broken
particles, neighbouring molecules incidentally cropped). 2D
classification clusters particles into K groups by appearance; bad
groups (blobs, ice, edge artefacts) are dropped, leaving a clean
particle set. Typical retention: 30–70% of picks.

**What it does**: Bayesian E-M with K independent 2D references.
Each particle is assigned a posterior over (class, in-plane angle,
shift). After convergence: each class average is the *de-noised*
sum of all particles assigned to it.

**Inputs**: `particles.star` (raw extracted boxes).
**Outputs**: `run_it025_classes.mrcs` (the K class averages) +
`run_it025_data.star` (per-particle class + pose posteriors).
**Magellon today**: not in shell-out path; partial in `magellon-rust-mrc` (CAN+MRA-based, not RELION's Bayesian approach).

### 6. 2D class selection

**Why**: 50 classes is more than a human can manually curate per
particle. RELION 5 has a CNN class-ranker that scores classes by
"likely-good vs likely-junk".

**What it does**: ResNet-18-class classifier outputs a score per class.
Above-threshold classes are kept.

**Inputs**: `run_it025_classes.mrcs`.
**Outputs**: `selected_particles.star` (subset of the input).
**Magellon today**: not exposed; could be wrapped as a Topaz-style ONNX plugin.

### 7. Initial model (3D template)

**Why**: 3D refinement needs a starting model. A bad starting model
gives a bad refinement (the optimisation is non-convex). For new
molecules without an existing PDB structure, we generate one from
the cleaned 2D particles using a stochastic gradient method (VDAM).

**What it does**: variational adaptive momentum gradient descent in
real space, randomly initialised. ~50 iterations. Converges to a
~10–20 Å low-resolution shape with the correct topology.

**Inputs**: cleaned 2D particles.
**Outputs**: a single low-res `.mrc` map.
**Magellon today**: not implemented anywhere.

### 8. 3D classification — heterogeneity removal

**Why**: even after 2D cleanup, particles may represent multiple
conformations of the molecule (open/closed, with/without ligand).
3D classification clusters particles by 3D shape so each conformation
gets its own reconstruction.

**What it does**: same Bayesian E-M as 2D classification but with K
*3D* references that are projected at every orientation per particle.

**Inputs**: 2D-cleaned particles + initial 3D model.
**Outputs**: K 3D maps + per-particle class assignment.
**Magellon today**: not in shell-out path.

### 9. 3D refinement (gold-standard) — the headline

**Why**: take the cleanest particle subset and refine it to highest
possible resolution. Gold-standard means we split the dataset into
two halves at the start and refine each *independently* — at the end
we compute FSC between the two reconstructions to get an unbiased
resolution estimate (without independent halves we'd be measuring
how well the same data agrees with itself, which is meaningless).

**What it does**: same Bayesian E-M but `--auto_refine` mode adapts
the angular sampling (HEALPix order) per iteration based on the
estimated angular accuracy. Refines until the FSC stops improving.
Runs in MPI: 1 master + 2 workers (one per half-set).

**Inputs**: cleaned particles (one or two STAR files for the two halves) + initial 3D model.
**Outputs**: `run_class001.mrc` (the final unmasked sum), `run_half1_class001_unfil.mrc` and `run_half2_class001_unfil.mrc` (the two unfiltered half-maps), full refined particle metadata.
**Magellon today**: not in shell-out path. The Rust port has every component (`magellon-rust-mrc/algorithms/spa/refinement/run_one_iteration`) but lacks the gold-standard wrapper (~2–4 weeks of work).

### 10. CTF refinement — getting the last 0.5 Å

**Why**: per-micrograph CTF estimation (step 2) is approximate.
After we have a high-resolution reference, we can re-estimate the
CTF *per particle* (defocus changes by ~50 nm across one micrograph)
and *per optics group* (beam tilt, magnification anisotropy, higher-
order Zernike aberrations). Tightens resolution by 0.2–0.5 Å.

**What it does**: holds the 3D map fixed, optimises CTF parameters
to maximise the per-particle log-likelihood.

**Inputs**: refined particles + refined map.
**Outputs**: particle STAR with corrected CTF columns.
**Magellon today**: not implemented.

### 11. Bayesian polishing — re-run motion correction with prior

**Why**: step 1 (motion correction) only knows about the micrograph's
own data. Once we have a high-res reference, we can re-do the per-frame
alignment using the model as a prior — for each particle, find the
frame-by-frame translations that maximise its likelihood under the
3D model. Tightens resolution by another 0.2–0.5 Å.

**What it does**: per-particle, per-frame alignment optimisation
with a smoothness prior across frames.

**Inputs**: refined particles + refined map + original movies.
**Outputs**: re-extracted particle STAR with polished motion.
**Magellon today**: not implemented; the standard 3D motion module
in `magellon-rust-mrc/algorithms/motion/` is the per-micrograph
version, not the per-particle-Bayesian one.

### 12. Refine again

After CTF refinement and polishing, re-run `Refine3D` with the
improved particles. Resolution improves further.

### 13. Postprocess — sharpening

**Why**: the refined map's high-frequency components are attenuated
by the imaging process (sample heterogeneity, residual motion). We
estimate the attenuation curve from a Guinier plot and apply the
inverse — "sharpening" — boosting high frequencies back up.

**What it does**:
1. Apply a soft-edge solvent mask to both half-maps to focus on the
   protein density.
2. Compute FSC between the two masked half-maps.
3. The FSC = 0.143 crossing gives the **resolution** number.
4. Fit `ln(power) ∝ -B·s²/2` in shells where signal dominates noise.
   The slope gives B (typical -50 to -200 Å²; negative is expected).
5. Apply `exp(+|B|·s²/4)` per Fourier shell, weight by the Heymann
   masked-FSC factor `√(2·FSC/(1+FSC))`, low-pass at the resolution
   cutoff.
6. Inverse FFT → final real-space sharpened map.

**Inputs**: two unfiltered half-maps + a solvent mask.
**Outputs**: sharpened final `.mrc` + FSC curve as ASCII + Guinier plot.
**Magellon today**: implemented in `magellon-rust-mrc/algorithms/spa/postprocess.rs` — works on real data; could replace `relion_postprocess` for plugin work *now* if we wire it into the bus.

### 14. Local resolution

**Why**: the global resolution number from FSC is a single value,
but real maps have *spatially varying* resolution — the molecule's
core might be at 2.0 Å while the flexible loops are at 4.0 Å. A local
resolution map shows this directly.

**What it does**: sliding-window FSC over local cubes of the volume.
**Magellon today**: not implemented; `magellon-rust-mrc/algorithms/spa/fsc.rs` does global FSC; local would extend it.

### 15. Atomic model building

The final 3D map is a density. To get a *protein structure* (PDB
file with atomic coordinates), you fit chains of amino acids into
the density. ModelAngelo (a transformer-based model) does this
automatically given the map + sequence; Coot is the manual-curation
tool. This step is downstream of everything in this doc.

## Where Magellon plugs into all of this

```
        ┌─────────────────┐
        │  microscope     │
        │  (movies, gain) │
        └────────┬────────┘
                 │ (filesystem watcher)
                 ▼
   ┌──────────────────────────────┐    Magellon orchestration
   │  CoreService task bus        │    (FastAPI, RabbitMQ tasks,
   │  ──────────────────────────  │     plugin containers)
   │  motioncor_tasks_queue       │
   │  ctf_tasks_queue             │
   │  particle_picking_q          │
   │  ...                         │
   │  (RELION jobs as new queues) │
   └──┬─────────┬─────────┬──────┬┘
      │         │         │      │
      ▼         ▼         ▼      ▼
   MotionCor  CTFFind  Topaz   (RELION-as-plugin)
   plugin     plugin   plugin   ← new

```

The architecture is already designed for this: `magellon_*_plugin/`
containers each consume one queue, do their thing, write outputs to
`/gpfs/jobs/<task-id>/`, post a result to the `*_out_tasks_queue`.
Adding RELION = new container + new queue, no platform changes.

## What Magellon-rust-mrc adds *beyond* what RELION provides

The native Rust port (`C:\projects\magellon-rust-mrc`) is at "everything
works for one E-M iteration". Its value over RELION-as-plugin:

1. **Sub-second latency** for "classify this one particle" (RELION's
   subprocess startup is 100–500 ms before any work).
2. **Streaming** — accumulate particles into the reconstruction *as
   they're picked*, no STAR-file marshalling between batches.
3. **In-process embedding** — the TUI viewer can compute Class2D in
   the same process; web/WASM/mobile too.
4. **CI-friendly** — no GPU + CUDA + drivers needed for tests.
5. **Multi-GPU-vendor** — cubecl targets CUDA + HIP (AMD) + SYCL
   (Intel) from one codebase.

For most production use the Rust port is **not on the critical path**:
shell out RELION for everything that runs once-per-dataset, and
reserve the Rust port for the interactive / streaming / embedded
features that are Magellon-distinct.

See [`magellon-rust-mrc/docs/relion-port-status.md`](../../magellon-rust-mrc/docs/relion-port-status.md)
for what's implemented in Rust and what's still RELION-only.


---

<!--
  Section: 9. Roadmap — Implementation Plan
  Originated from: Documentation/IMPLEMENTATION_PLAN.md
  Merged into this consolidated reference 2026-05-13.
-->

# Magellon — Implementation Plan

**Status:** Living document. Revised 2026-04-14, refreshed 2026-04-28.
Tracks A (MB4–MB6), B (G.1–G.4), C (X.1–X.3) all shipped 2026-04-21 /
2026-04-27. Phase A largely done (A.1–A.5 landed or cancelled).
Phases B / C / D / E / F retained for partially-open work; see status
notes per phase.

> **Historical note.** The original Phase A plan (rule #5: "RabbitMQ
> goes"; A.4/A.5: retire RMQ helpers, drop RMQ from compose) was
> reversed by the P1–P9 plugin-platform refactor (2026-04-15). RMQ is
> now load-bearing for tasks, discovery (P6), dynamic config (P7), and
> cancellation (P9) — all riding the `magellon.plugins` topic exchange.
> Consul was deleted instead (P8). Phases B / D / E / F still apply.
>
> **Governing docs (2026-04-21).** `ARCHITECTURE_PRINCIPLES.md` is the
> canonical rule-set every PR in this plan is reviewed against.
> `DATA_PLANE.md` closes the "artifact transport" question by
> committing to a shared POSIX filesystem; object-storage-only
> deployments are an explicit non-goal.

**Context:** The earlier plan assumed Temporal would become the workflow engine
and NATS the event backbone. The actual workload is **one plugin, one call,
one reply** (see `CoreService/docs/plugin-developer-guide.md`). Temporal's value
(durable history, multi-step signals, cross-restart retries) had no concrete
consumer, so we reverted. The extension point — `magellon_sdk.executor.Executor`
Protocol — survived the revert so a workflow engine can plug back in when
pipelines become a real requirement.

---

## Guiding rules

1. **Default to in-process.** A plugin is a Python module under `CoreService/plugins/`
   that subclasses `PluginBase[In, Out]` and gets mounted on a FastAPI router.
   Containers and remote executors are *deployment modes*, not new plugin models.
2. **Simple plugins stay simple.** FFT-grade plugins should be a single Python
   file, no Docker required. If a plugin needs a heavy binary (ctffind4,
   MotionCor2), it is allowed — but allowed, not mandatory.
3. **YAGNI on orchestration.** No workflow engine until multi-step pipelines
   become a real workload. When they do, the Executor Protocol is the
   integration point — do not re-scaffold.
4. **One job, one truth.** Collapse `job_service`, `magellon_job_manager`,
   and the dead `job_manager` / `temporal_job_manager` into one path.
5. **Two layers, not three.** Socket.IO for CoreService ↔ UI (real-time
   browser pushes). NATS for CoreService ↔ containerized plugins (async
   request + progress + reply, long jobs without holding an HTTP
   connection). In-process plugins don't need either — direct function
   call with a `ProgressReporter` that fans out to Socket.IO.
   **RabbitMQ goes.**
6. **Additive, then subtractive.** Build the new path alongside the old,
   prove it in CI, then delete.
7. **Reversible PRs.** Each PR in this plan stands alone; `git revert` restores
   green.

---

## Completed phases

### Phase 0 — Safety net (complete)
PRs 0.1–0.6 (`9c37b07`, `5d426f4`) characterization tests: pytest.ini,
envelope goldens, queue names, plugin registry, HTTP contract, Socket.IO
emit shape. PR 0.10 (`1c17ede`) dead-code audit. PR 0.11 (`9609240`) typo fix.
PR 0.9 (Temporal infra) — reverted in `86fe9cc`. PRs 0.7–0.8 (live-docker
contract + full e2e smoke) never landed; deferred to Phase C.

### Phase 1 — SDK extract (complete minus publish)
PRs 1.1–1.5, 1.7 all landed (`a4d1e10`, `5d14b06`, `b90ffe2`, `eb00daa`,
`f10456f`). `magellon-sdk 0.1.0` is installable as an editable dep from
`../magellon-sdk`. PR 1.6 (publish to an index) deferred pending an infra
decision — folded into Phase E below.

### Phase 2 — Temporal (reverted `86fe9cc`)
Not pursued. The SDK retains `PluginBase`, progress reporter, CloudEvents
envelope, and the `Executor` Protocol — the orchestrator-agnostic contract —
so nothing re-introducing Temporal later has to restart from zero.

### Plugin platform refactor (P1–P9, complete 2026-04-15)
Nine sequential phases that turned plugins into broker-native, single-purpose
category workers. This was *not* in the plan above — it was the realization
during Phase B work that the duplicated `core/` consolidation alone wasn't
enough; the broker needed to own discovery and config too, which then made
Consul redundant.

| Phase | Commit     | Delivered                                                                                       |
|-------|------------|-------------------------------------------------------------------------------------------------|
| P1    | `9a39299`  | `CategoryContract` + I/O diversity rules.                                                        |
| P2    | `9078dc6`  | Typed failure taxonomy (`AckAction.{ACK,NACK_REQUEUE,DLQ}`).                                     |
| P3    | `ef5fffe`  | Result-processor promoted in-process (`OUT_QUEUES` consumed in CoreService).                     |
| P4    | `3e8af0a`  | Per-task provenance auto-stamped on `TaskResultDto`.                                             |
| P5    | `886f0e9`  | `PluginBrokerRunner` harness — plugin `main.py` collapses to one constructor.                    |
| P6    | `9a73c74` + `96f2908` | Broker-based discovery + heartbeat (replaces Consul); CoreService liveness registry. |
| P7    | `40f9008` + `ba20628` | Broker-based dynamic config (`magellon.plugins.config.<category>` + `.broadcast`).   |
| P8    | `2f7aa9c`  | Consul deleted — package, models, plugin shims, compose service.                                  |
| P9    | `7e95930`  | Cancellation primitives — `POST /cancellation/queues/purge`, `/containers/{name}/kill`.           |

**Direct implication for Phase A:** A.4 ("Retire RabbitMQ dispatch helpers")
and A.5 ("Drop RabbitMQ from docker-compose.yml") will not be pursued — the
broker is now the integration point for *all* plugin lifecycle traffic, not
just task dispatch. A.1/A.2/A.3 already landed (`a989d6f` / `3066a64` / `5f3922e`).

### Phase A — Consolidate (status)
A.1 / A.2 / A.3 done as above. A.4 / A.5 cancelled per the platform refactor.
A.6 (Phase 0 dead-code sweep) ongoing as part of regular cleanup.

---

## Phase A — Consolidate (cleanup we owe)

**Goal:** Pay the debt the prior phases exposed — three job managers, dead
Temporal/RabbitMQ scaffolding, orphaned controllers — before building anything
new.

| PR  | Title | DoD |
|-----|-------|-----|
| A.1 | Delete orphaned Temporal scaffolding | `controllers/workflow_job_controller.py` (472 lines, no mounted routes) and `services/temporal_job_manager.py` (406 lines, only caller was the orphan controller) removed. Any incidental imports fixed. |
| A.2 | Delete Dragonfly `services/job_manager.py` | 670-line unused singleton flagged by the Phase 0 audit. Confirm zero live callers via grep, then delete. Dragonfly stays as a cache. |
| A.3 | Pick ONE job manager as canonical | Decide: is `job_service.py` (the live plugin dispatch) or `magellon_job_manager.py` (domain/import) the survivor? Merge the other into it. One lifecycle, one state store, one progress path. |
| A.4 | Retire the RabbitMQ dispatch helpers | `core/helper.py` — `publish_message_to_queue`, `get_queue_name_by_task_type`, `push_task_to_task_queue`, `dispatch_ctf_task`, `dispatch_motioncor_task` — all dead now that plugins dispatch in-process. Delete along with `core/rabbitmq_client.py`. |
| A.5 | Drop RabbitMQ from `docker-compose.yml` | Remove the service and its volume. If any importer still writes to `/magellon/messages/*/messages.json` as an audit trail, replace with structured log lines. |
| A.6 | Finalize the Phase 0 dead-code audit sweep | Walk the original audit (retired from `Documentation/`; see git log for `PHASE_0_DEAD_CODE_AUDIT.md`), execute remaining "SAFE TO DELETE" rows, re-verify each before removal. |

**Exit criterion:** `grep -ri "temporal\|rabbitmq"` returns hits only in history,
docs, or settings-file examples. One `JobService`. One dispatch path.

**Rollback:** per-PR `git revert`.

---

## Phase B — Plugin execution taxonomy ~~(planned)~~ — SUPERSEDED by PI/PT

**Status (2026-05-04):** This phase planned three deployment modes
(in-process / subprocess / containerized) and an `HttpContainerExecutor`.
PI-5/PI-6 + PT-1..PT-6 collapsed the taxonomy: there is now one
deployment mode (external broker plugin = standalone FastAPI host)
with an opt-in **capability layer** that supports sync HTTP for
sub-second interactive flows.

What replaced this phase:

- **In-process plugins gone.** Architecture B (`PluginBase` registry
  walk inside CoreService) was retired in PI-5/PI-6.1. The last
  in-process plugin (`pp/template-picker`) became a feature
  controller that delegates compute to the external
  `magellon_template_picker_plugin` over the sync transport.
- **Container vs subprocess** is now an *install method* concern,
  not a runtime concern. The install pipeline picks
  `UvInstaller` (uv venv + systemd unit) or `DockerInstaller`
  (image + container) per the manifest's `install:` list. Both
  produce a plugin process that talks RMQ. Operators don't need
  to read a deployment-mode taxonomy to choose; the manifest's
  predicates pick.
- **Sync transport** is opt-in via capabilities. A plugin
  declares `Capability.SYNC` and/or `Capability.PREVIEW`; the SDK
  mounts the contract endpoints via `make_sync_router(plugin)` /
  `make_preview_router(plugin)`; CoreService routes via
  `services/sync_dispatcher.py`. See
  `CURRENT_ARCHITECTURE.md` §4.

The developer guide that B.1 would have written exists in essence
in `plugin-developer-guide.md` plus the SDK's
`magellon_sdk/capabilities/__init__.py` docstring; a future PR can
consolidate.

---

## Phase C — Event & dispatch consolidation

**Goal:** Two event seams, each with one producer and one consumer shape:
Socket.IO for CoreService → UI, NATS for CoreService ↔ containerized
plugins. Today both exist; both have fragmented callers; neither has a
single owning module. Cut the fragments, keep the layering. RabbitMQ is
already gone after Phase A.

| PR  | Title | DoD |
|-----|-------|-----|
| C.1 | Socket.IO — single producer for UI events | All UI-facing `emit` calls funnel through `JobService.emit(...)`. No other module calls `sio.emit` directly. Contract pinned by the existing PR 0.6 tests. |
| C.2 | NATS — single seam for container-plugin transport | Consolidate NATS publish/subscribe behind `services/event_service.py` (the `MagellonEventService` is already close to this). Subjects documented: `magellon.plugin.<id>.request`, `.progress`, `.reply`. Plugin authors use a helper, not `nats.connect(...)` directly. |
| C.3 | `ProgressReporter` fans out to the right seam | Plugin author always writes `reporter.report(pct, msg)`. In-process plugins: reporter pushes Socket.IO. Container plugins: reporter publishes NATS, gateway in CoreService forwards to Socket.IO. Plugin code stays transport-agnostic. |
| C.4 | Document the plugin transport protocol | Short `Documentation/PLUGIN_TRANSPORT.md`: NATS subject naming, request/progress/reply payload shape (reuse the CloudEvents envelope already in SDK), timeout / retry expectations. One page. |
| C.5 | PR 0.7 — plugin-container contract test | The Phase 0 test that was deferred: boot a plugin container image in CI, publish a canned request on NATS, assert progress frames + reply shape. Validates the containerized-plugin transport once rather than per-plugin. |
| C.6 | PR 0.8 — end-to-end smoke test | Also deferred from Phase 0: MySQL + NATS + CoreService + one container plugin, submit one job, assert progress frames arrive on Socket.IO and result row persists. Runs nightly in CI. |

**Exit criterion:** Each bus has exactly one owning module (`JobService` for
Socket.IO, `MagellonEventService` for NATS). Plugin code never imports
`socketio` or `nats` directly. Nightly e2e smoke green.

**Rollback:** per-PR revert.

---

## Phase D — Frontend consolidation

**Goal:** Finish the FSD migration that's been in progress, pick one HTTP
client, retire legacy folders. Scoped narrowly — this is cleanup, not a
rewrite.

| PR  | Title | DoD |
|-----|-------|-----|
| D.1 | FSD migration — finish the job | Move remaining `src/pages/*` and top-level `src/components/*` into `src/features/` or `src/shared/`. Old folders deleted. |
| D.2 | HTTP client standardization | Pick Axios or `fetch` (Axios recommended — existing JobsPanel uses it, interceptors already exist). Remove the other. One `api/` client module. |
| D.3 | Socket.IO subscription consistency | Centralize subscription lifecycle. Today only JobsPanel subscribes; other real-time panels fall back to polling. One `useJobEvents(jobId)` hook used everywhere. |

**Exit criterion:** `src/pages/` and legacy `src/components/` empty or
removed. `grep "from 'axios'\|from \"axios\"" | wc -l` equals
`grep "fetch(" | wc -l` in app code only at the boundary file.

**Rollback:** per-PR revert; none touch backend contracts.

---

## Phase E — SDK publish path

**Goal:** Unblock external plugin authors. Today `magellon-sdk` installs only
via path (`-e ../magellon-sdk`). That's fine for in-tree work; it doesn't let
a third party `pip install magellon-sdk`.

| PR  | Title | DoD |
|-----|-------|-----|
| E.1 | Decide publish target | Document the decision in `Documentation/`: private PyPI (self-hosted), GitHub Packages, or public PyPI. Includes auth/CI implications. This is a *decision*, not code. |
| E.2 | CI publish-on-tag | GitHub Action builds the wheel, publishes on `v*` tags. Secrets provisioned. Smoke-install in a clean venv on publish. |
| E.3 | `magellon-sdk 0.2.0` — first published version | Bump from 0.1.0 (scaffold) to 0.2.0 (first external release). Changelog, pinned deps. CoreService switches from editable install to a version pin. |
| E.4 | SDK versioning strategy | Short `Documentation/SDK_VERSIONING.md`: semver rules, deprecation window, breaking-change communication. |

**Exit criterion:** A plugin repo outside `C:\projects\Magellon` can
`pip install magellon-sdk` and author a working plugin without touching
Magellon source.

**Rollback:** CoreService can revert to editable install at any time.

---

## Phase F — Plugin Hub (optional, deferred)

**Goal (if pursued):** publish/discover/install flow for third-party plugins.

Defer until: an external author actually needs it, or the in-tree plugin
count grows past ~10. Today CTF, MotionCor, template_picker + an FFT stub
fit comfortably in-tree. PRs 6.1–6.5 in the prior plan stand as a reference;
re-plan them when the need is real.

---

## Deferred indefinitely

Each of these remains valuable *as an option* if the workload changes. None
are being built on spec.

- **Workflow orchestration** (Temporal, Airflow, Prefect). Add when
  multi-step pipelines that need retries/signals/history become a real
  workload. Plug in via `magellon_sdk.executor.Executor`.
- **`LocalDocker` / `RunPod` / `Kubernetes` executors.** Add the first one a
  paying customer asks for. Not before. Note: any cloud-GPU executor
  must include a mounted shared filesystem per `DATA_PLANE.md` — the
  platform assumes path-addressed image data. RunPod-style serverless
  with no attached FS volume is not a Magellon target.
- **JetStream durability / replay.** NATS core (non-persistent pub/sub) is
  enough for today's request → progress → reply pattern. Turn on JetStream
  when either (a) plugin outputs need to survive a CoreService restart
  mid-job, or (b) a second consumer wants to replay event history.
- **On-disk message audit**. The `/magellon/messages/*/messages.json`
  writes went away with RabbitMQ; replace with structured logs if audit is
  ever required again.

---

## Test discipline (unchanged from prior plan)

A test lives at the layer that enforces the contract it pins:

| Layer                   | Lives in                                  | Runs when                 |
|-------------------------|-------------------------------------------|---------------------------|
| Plugin unit test        | The plugin's own directory                | CoreService CI            |
| Envelope / schema golden| `CoreService/tests/characterization/`     | CoreService CI            |
| HTTP contract           | `CoreService/tests/characterization/`     | CoreService CI            |
| Socket.IO emit shape    | `CoreService/tests/characterization/`     | CoreService CI            |
| Container contract      | `CoreService/tests/contracts/` (Phase C.4)| CoreService CI (dockered) |
| E2E smoke               | `CoreService/tests/e2e/` (Phase C.5)      | CI nightly + pre-release  |
| SDK unit tests          | `magellon-sdk/tests/`                     | SDK CI                    |

**Rule:** no PR in Phase A or later merges without the tests that pin the
behaviour it touches. Reviewer rejects otherwise.

---

## Active tracks — 2026-04-21

Two parallel tracks are the current work, following adoption of
`ARCHITECTURE_PRINCIPLES.md` and `DATA_PLANE.md`. The previously open
"artifact transport" question is **closed** per `DATA_PLANE.md` — the
platform commits to a shared POSIX filesystem as the data plane; that
removes what would otherwise have been Track D (artifact transport
abstraction) from the roadmap.

Tracks A and B run in parallel. Track A is paced by one reviewer-cadence
chain; Track B PRs are independent and can be picked up one at a time.

### Track A — Finish the MessageBus migration

**Goal.** Close out MB4–MB6 so the bus abstraction is complete, no
`pika` imports leak outside the binder, and every production queue is
DLQ-wired. Half-migrated is the worst state to sit in — new call sites
drift onto whichever pattern the author copied from. Non-negotiable.

PR IDs use the `MB` prefix to avoid colliding with Phase-A PR
numbering. The original execution plan (PR-by-PR ordering, file lists,
acceptance criteria) lived in `Documentation/MESSAGE_BUS_EXECUTION_PLAN.md`,
retired from the directory now that all 13 PRs shipped — see git log.
Architecture details remain in `MESSAGE_BUS_SPEC.md`.

**Track A status (2026-04-21, end of day).** All 13 Track A PRs
shipped in one session. Exit gate met: `rg '^import pika|^from pika'`
outside `magellon_sdk/bus/binders/rmq/` returns empty on production
code, and the MB6.3 ruff lint rule enforces this on every push/PR.
The only remaining operational step is the MB6.4 **production run**
in a scheduled ops window, after MB6.3 soaks for a week.

| PR   | Title | Status |
|------|-------|--------|
| ~~MB4.A~~ | Delete plugin RMQ shims | **Done (`ca85bad`).** |
| ~~MB4.B~~ | Relocate `result_consumer.py` to SDK | **Done (`af4e019`).** New `magellon_sdk/bus/services/result_consumer.py`; CoreService keeps a thin wrapper. 4 new SDK tests + 5 CoreService tests green. |
| ~~MB4.C~~ | Stop the result-processor double-consume | **Done (`5827b8f`).** Blanked `OUT_QUEUES: []` in both plugin YAMLs. Plugin container now dormant by default; CoreService sole writer. |
| ~~MB5.1~~ | Discovery on `bus.events` | **Done (`d334f01`).** `DiscoveryPublisher.announce`/`heartbeat` delegate to `bus.events.publish(AnnounceRoute/HeartbeatRoute, env)`. Wire body unchanged (CloudEvents binary content mode). 9/9 tests green. |
| ~~MB5.2~~ | Config broker on `bus.events` | **Done (`2419c4d`).** `ConfigPublisher` via `bus.events.publish`; `ConfigSubscriber.start` via `bus.events.subscribe(ConfigRoute.all(), handler)` with target-filter in Python. 10/10 tests green. |
| ~~MB5.3~~ | Step events into RMQ binder | **Done (`3ada760`).** `_RmqAsyncAdapter` → `_BusRmqAdapter`; `make_step_publisher` routes through `get_bus()` for the RMQ mirror. 20/20 tests green (events + legacy transport). |
| ~~MB5.4a~~ | Relocate liveness registry | **Done (`434303c`).** `PluginLivenessRegistry`, singleton, `start_liveness_listener` moved to `magellon_sdk/bus/services/liveness_registry.py`; CoreService is a thin re-export. Two explicit `bus.events.subscribe` calls (announce + heartbeat) replace the `#` wildcard bind. 6/6 tests green. |
| ~~MB5.4b~~ | Relocate step-event forwarder | **Done (`4e5d6a8`).** `StepEventForwarder` in SDK; `BusStepEventConsumer` adapts `bus.events.subscribe(StepEventRoute.all(), ...)`. CoreService subclass injects `JobEventWriter`. Tests unchanged. 8/8 green. |
| ~~MB5.4c~~ | Relocate config-publisher singleton | **Done (`2fdcc72`).** Singleton lifecycle in SDK; push helpers stay in CoreService for patch-compatibility with existing tests. 4/4 green. |
| ~~MB6.1~~ | Cancellation via `bus.tasks.purge` | **Done (`0fa5e04`).** `cancellation_service.purge_queue` delegates to `get_bus().tasks.purge(TaskRoute.named(...))`. 9/9 service + 7/7 controller tests green. |
| ~~MB6.2~~ | Collapse `transport/rabbitmq.py` into binder-private | **Done (`c0059f2`).** `transport/rabbitmq.py` → `bus/binders/rmq/_client.py`. `transport/rabbitmq_events.py` + its tests deleted. `CoreService/core/rabbitmq_client.py` shim deleted. `messaging.publish_message_to_queue` migrated to `bus.tasks.send`. Seam test installs bus. 276/276 SDK tests green. |
| ~~MB6.3~~ | Ruff banned-api rule + CI workflow | **Done (`efa7af3`).** `[tool.ruff.lint.flake8-tidy-imports.banned-api]` in both pyproject.toml files banning `pika`, `aio_pika`, and the legacy transport paths. `.github/workflows/lint.yml` runs on push + PR. Clean on both packages. |
| ~~MB6.4~~ | DLQ topology migration | **Script + runbook done (`629a526`).** `CoreService/scripts/migrate_dlq_topology.py` implements §9.6.1 with `--dry-run`, `--queue`, `--all`, `--verify`, `--yes`. `Documentation/DLQ_MIGRATION_RUNBOOK.md` extracted. **Production run is a separate ops event** — schedule after MB6.3 soaks ≥ 1 week. |

**Exit gate status (2026-04-21).** `rg '^import pika|^from pika' -g '!magellon_sdk/bus/binders/rmq/**' -g '!**/tests/**' -g '!**/scripts/**'` returns **zero** on `main`. CI-enforced by MB6.3's ruff banned-api rule with the `.github/workflows/lint.yml` workflow.

**Rollback.** Per-PR `git revert` except MB6.4, which has its own runbook rollback in `DLQ_MIGRATION_RUNBOOK.md`.

### Track B — Close product-visible gaps

**Track B status (2026-04-21, end of day).** All 4 PRs shipped.

PR IDs use the `G` prefix (Gap closure) to avoid colliding with
Phase-B PR numbering.

| PR  | Title | Status |
|-----|-------|--------|
| ~~G.1~~ | Cooperative cancel for external plugins | **Done (`6663d23`).** New `CancelRoute` + `CancelRegistry` + bus listener. `BoundStepReporter.started/progress` check the registry and raise `JobCancelledError` so plugins abort at their next progress checkpoint. `PluginBrokerRunner._handle_task` catches the raise and publishes a FAILED-status result with `output_data["cancelled"]=True`. `JobManager.request_cancel` publishes the bus cancel event alongside the in-process flag. 5 new SDK tests; ruff clean. |
| ~~G.2~~ | Contract test per plugin container | **Done (`59b420c`).** `CoreService/tests/contracts/` framework + one test module per plugin (CTF, MotionCor, FFT). Each hits the plugin's HTTP `/execute` endpoint with a canned TaskDto (missing-file input → clean failure), asserts `task_id`/`job_id` echo + TaskResultDto shape. Bypasses RMQ to avoid racing CoreService's in-process result consumer. Skips cleanly with an actionable message when the plugin container isn't up. |
| ~~G.3~~ | Unified `PluginConfigResolver` | **Done (`50deb25`).** `magellon_sdk/config/resolver.py` layers runtime overrides > env vars > YAML > defaults with lock-protected `apply_overrides`. Typed accessors (`get_bool/get_int/get_float/get_str`) that log-and-default on garbage so plugin hot loops don't crash on typo'd values. `snapshot()` for diagnostics. 26 tests pinning precedence + merge semantics. Per-plugin migration to use the resolver is per-plugin follow-up; the class contract is frozen. |
| ~~G.4~~ | Background the import handler | **Done (`2de2449`, earlier session).** `/magellon-import` returns a scheduled `job_id` immediately; `MagellonImporter.process()` runs in FastAPI `BackgroundTasks` with its own DB session. `BaseImporter.pre_assigned_job_id` attribute threads the id. |

**Ordering.** G.4 is the cheapest (half a day) and the most immediately user-visible — recommend as the first Track B PR. G.1 uses the bus via Track A's MB5.1 path; it can land earlier by targeting the RMQ binder directly and being retargeted trivially.

**Rollback.** Per-PR `git revert`; none of these touch the bus abstraction boundary.

### Track C — Backends + wire-shape naming (shipped 2026-04-27)

**Goal.** Give the second axis under each `TaskCategory` a first-class
name (`backend`), one consolidated capabilities endpoint that the UI
and the dispatcher both read, and a uniform `Envelope` / `Message`
suffix on every wire-shape class. Detailed design in
`Documentation/CATEGORIES_AND_BACKENDS.md`.

**Track C status (2026-04-27, end of day).** All three PRs landed in
one session. SDK 1.2.0 → 1.3.0 (additive) → 2.0.0 (alias drop). 76
files migrated mechanically; zero new test failures across 326
SDK + 326 CoreService tests vs the pre-X.1 baseline.

PR IDs use the `X` prefix to avoid colliding with Phase-A and Track A/B
numbering.

| PR  | Title | Status |
|-----|-------|--------|
| ~~X.1~~ | Backend layer + capabilities endpoint | **Done (`0a3f216`).** Adds `backend_id` to `PluginManifest`, `target_backend` to `TaskMessage`, `_BusTaskDispatcher` honors backend pin via `BackendQueueResolver` (raises `BackendNotLive` on miss), `PluginLivenessRegistry` indexes by `(category, backend_id)` with `DUP_BACKEND_ID` collision warning, `GET /plugins/capabilities` returns one consolidated catalog. 18 SDK + 6 dispatcher + 4 capabilities tests. Envelope golden regenerated for the new `target_backend` field. |
| ~~X.2~~ | Wire-shape rename — alias + migrate | **Done (`581518f`).** `TaskDto`→`TaskMessage`, `TaskResultDto`→`TaskResultMessage`, `JobDto`→`JobMessage`, `*TaskData`→`*Input`, `Step{Started,Progress,Completed,Failed}`→`*Message`. 76 files / 481 occurrences migrated via word-boundary regex. Old names kept as literal aliases — `isinstance` works against either name. SDK bumped 1.2.0 → 1.3.0. |
| ~~X.3~~ | Drop legacy aliases | **Done (`4639990`).** Removed legacy aliases from SDK and CoreService shim. SDK bumped 1.3.0 → 2.0.0; `PluginInfo.schema_version` default `"1"` → `"2"` so frontends re-fetch plugin form schemas. CHANGELOG entries for both 1.3.0 and 2.0.0 with full migration table. |

**Rollback.** Per-PR `git revert`. X.3 is the only one that breaks
out-of-tree plugins that haven't migrated. Revert order if rolling
back: X.3 → X.2 → X.1.

**Operational follow-ups.** End-to-end smoke against a real RMQ broker
(target_backend path is unit-tested but not yet exercised against
pika). Frontend re-fetch of plugin form schemas after the
schema_version bump (manual click-through pending).

### Cross-track: documentation (E)

Landed 2026-04-21:

- `ARCHITECTURE_PRINCIPLES.md` (new) — canonical rule-set.
- `DATA_PLANE.md` (new) — shared-filesystem decision + deployment matrix.
- `CURRENT_ARCHITECTURE.md` §4.1, §8 #12, §11 — corrected and reframed.
- `CoreService/docs/plugin-developer-guide.md` — new "Data Plane" section.
- `TARGET_ARCHITECTURE_AND_PLAN.md` was superseded and retired from `Documentation/` 2026-04-28; see git log.

These are governance; they gate the review of every PR in Track A and Track B.

### First move

If starting tomorrow: **MB4.A + G.4 as independent PRs**. MB4.A unblocks
the Track A chain; G.4 is the highest-leverage user-visible improvement
at lowest cost. Each is small enough to review in half a day.


---

<!--
  Section: 10. Roadmap — Unified Platform Plan
  Originated from: Documentation/UNIFIED_PLATFORM_PLAN.md
  Merged into this consolidated reference 2026-05-13.
-->

# Magellon — Unified Platform Plan

**Status:** Proposal, 2026-04-17. Companion to `MESSAGE_BUS_SPEC.md` (the bus foundations the unified architecture composes over).
**Scope:** Retire the dual plugin architecture, then build toward a plugin hub on top of one coherent contract.
**Not in scope:** MB7 (second binder), orchestration engines, UI redesigns outside the plugins page.

---

## 1. Why

Magellon currently has two plugin architectures living side-by-side:

- **In-process plugins** live under `CoreService/plugins/<category>/<name>/service.py` as `PluginBase` subclasses. They're discovered by a filesystem walk at startup (`plugins/registry.py`) and invoked via `POST /plugins/{id}/jobs`, which calls `plugin.run(input)` directly in the CoreService process.
- **Broker plugins** live in their own repos / Docker images (`plugins/magellon_*_plugin/`). They announce themselves on `magellon.plugins.liveness`, consume from RMQ category queues via `PluginBrokerRunner`, and publish results back to the bus. Dispatch flows through `bus.tasks.send`.

The two paths diverged out of migration order — MB0–MB6 introduced the bus and moved external plugins to it; in-process plugins haven't moved yet. Every divergence is a tax:

- Two discovery mechanisms (filesystem walk vs liveness heartbeat) → `/plugins/` page missed FFT until 2026-04-17.
- Two dispatch code paths (`plugin.run()` vs `bus.tasks.send`) → every new dispatch feature has to be implemented twice or gets skipped on one side.
- Two status sources, two failure modes (Python exception vs envelope-with-error), two result projections.
- No clean story for "swap the default FFT with a user-supplied one" — the in-process version can't be replaced at runtime without a CoreService restart.

One architecture, multiple deployment topologies, multiple invocation modes (see §3) is the target shape. This doc sequences the migration.

---

## 2. Target architecture

### 2.1 One plugin contract

Every plugin is a `PluginBase[InputT, OutputT]` subclass. `execute(input_data) -> output` is the only business-logic surface a plugin author writes. No branches on topology.

### 2.2 One discovery path

Every plugin announces itself on `magellon.plugins.liveness` (announce on boot, heartbeat every 15s). `CoreService.core.plugin_liveness_registry` is the single source of truth. The filesystem walk in `plugins/registry.py` goes away.

**In-process plugins announce too.** They run a `PluginBrokerRunner` inside the CoreService Python process; it calls `install_rmq_bus(settings)` at startup and announces via the same discovery code external plugins use. The fact that the consumer lives in-process is a *deployment topology*, not a different path.

### 2.3 One invocation path

All dispatch goes through `bus.tasks.send(route, envelope)`. The HTTP endpoints (`POST /plugins/{id}/jobs`, `/image/fft/dispatch`, etc.) become thin shims that wrap input + publish. They don't know (or care) whether the receiver is in-process, in a container, or remote.

### 2.4 Deployment topologies (orthogonal to contract)

- **in-process** — `PluginBrokerRunner` spawned inside CoreService on startup. Same queue a container would consume. Good for dev, plugins that need DB access, zero-Docker deployments.
- **container** — Docker image running `PluginBrokerRunner`. Same queue. Good for GPU, isolation, heterogeneous hosts, horizontal scale.
- **subprocess** — spawn per-task, consume one and exit. For legacy binaries and strict quarantine.
- **remote-host** — future; no contract change.

Multiple instances of the same implementation compete naturally on the same queue — RMQ round-robins deliveries. `2 bare-metal + 6 containers = 8 instances` works out of the box.

### 2.5 Invocation modes (orthogonal to topology)

- **async bus** — default. Publish → fire-and-forget. Result comes back as a result envelope + step-event stream.
- **sync bus (request/reply)** — future SDK primitive for UI blocking on human input (e.g. plugin-runner "Run" button). Correlation-ID over the bus. Works with any topology.
- **preview** — explicit `Capability.PREVIEW` opt-out. Sync HTTP to the plugin's own `/preview` endpoint for interactive UX (`pp/template-picker` today). Bypasses the bus. Documented as an exception, not a general path.

**No direct in-process call escape hatch.** Tests don't use one; they use the in-memory or mock binder (see §2.6).

### 2.6 Test strategy — bind, don't bypass

We already shipped three binders (MB1–MB2). They are the test strategy:

| Binder | `install_*_bus()` | Use case | Sync? |
|---|---|---|---|
| **RMQ** | `install_rmq_bus` | Production, local dev with `docker compose`. | No |
| **In-memory** | `install_inmemory_bus` | Integration tests, local dev without RMQ. Broker-shaped semantics, real threads. | No |
| **Mock** | `install_mock_bus` | Unit tests, asserting on published envelopes without threads. | **Yes** |

**Rule:** no test uses RabbitMQ. Plugin-layer unit tests use mock. Integration tests use in-memory. Docker-level smoke tests use RMQ against a container. Any test reaching for `install_rmq_bus` needs justification in review.

---

## 3. Hub vision (outcome of the whole program)

Long-term target: `/en/panel/plugins` is a marketplace. Users browse available implementations, compare popularity, install, enable/disable. The platform supports multiple implementations of the same capability coexisting or replacing each other.

Mechanics enabled by the unified architecture:

- A plugin is a Docker image / pip package that declares: which capability it provides (`fft`, `ctf`, `motioncor`, custom), SDK version it was built against, resource hints, input/output JSON schemas.
- A user uploads a plugin archive or provides a URL → review workflow → if approved, the plugin becomes installable from the plugins page.
- Capability routing lets operators choose which implementation handles which jobs.
- Reproducibility: every `image_job` row carries `plugin_id + version` of the implementation that ran it.

What prevents this today:

- Contract isn't SemVer-stable. Field-default shifts (e.g. `outputFile` typo fix) ripple through third-party plugins.
- No capability routing — multiple implementations on the same queue just compete at RMQ round-robin.
- No install flow, no archive format, no review workflow, no central registry.
- No two-tier trust (verified vs community) — real concern for scientific compute where a malicious or buggy plugin's output looks plausible.

---

## 4. Phase sequence

### U — Unify architecture

| Phase | Goal | Est |
|---|---|---|
| **U1** | Retire the dual plugin architecture. `/plugins/` backed by liveness registry only. In-process plugins run `PluginBrokerRunner`. Dispatch always via bus. Tests migrate to mock/in-memory binders. | 1–2 sessions |
| **U2** | SDK SemVer hardening. Freeze `magellon_sdk.models.*` public shapes behind major-version bumps. Document contract surface. Plugins pin `magellon-sdk>=1.0,<2.0`. | 1 session |

### H — Hub foundations

| Phase | Goal | Est |
|---|---|---|
| **H1** | Per-plugin enable/disable toggles in `/plugins` UI. Per-implementation queues (route `magellon.tasks.fft.<impl-id>`) so installing a replacement doesn't just load-balance with the default. | 2–3 sessions |
| **H2** | Install-from-URL / Install-from-image flow on the plugins page. `POST /plugins/install` accepts a Docker image ref or Git URL, CoreService spawns a managed subprocess/container that runs the plugin, announces on the bus, shows up in the UI. No central registry yet. | 1–2 sessions |
| **H3a** | Plugin archive format spec (manifest.yaml + Dockerfile or source + dependencies). Author tooling (`magellon-sdk plugin init`, `magellon-sdk plugin pack`). | 1–2 sessions |
| **H3b** | Upload-and-review workflow. Author submits archive → automated checks (contract pinning, SDK version, manifest validity, schema emit) → human review for verified tier. | 3+ sessions |
| **H3c** | Central registry service. Search, popularity metrics, install-by-id. Two-tier trust (verified / community). | 5+ sessions |

### S — Small enablers (can slot in anywhere)

| Item | Rationale | Est |
|---|---|---|
| **Input/output JSON schemas in manifest** | Plugins already have `input_schema()` / `output_schema()` Pydantic classes. Emitting `model_json_schema()` in `PluginManifest` unlocks form rendering, upload validation, cross-version compatibility checks. | 30 min |
| **Reproducibility audit** | Every `image_job` row should show `plugin_id + plugin_version`. Most infrastructure is there via `TaskResultDto.plugin_id/plugin_version`; just surface it in the UI. | 1 session |
| **Plugin lifecycle API** | `/admin/plugins/{id}/stop`, `/start`, `/restart` — needed before H1 is usable. | 1 session |

---

## 5. Hard parts (up front, not surfacing mid-phase)

### 5.1 `pp/template-picker` preview

Sub-100ms interactive UX. The bus roundtrip — even in-memory — is the wrong tool. Keep `Capability.PREVIEW` as the explicit opt-out. Document it as the one exception to "everything through the bus."

### 5.2 In-process plugins sharing CoreService's DB session

In-process `TaskOutputProcessor` writes DB rows. Post-MB4.5 this logic lives in CoreService's in-process result consumer; plugins just publish results. The split is clean: **plugins compute, CoreService owns state.** In-process plugins don't get DB access just because they're in-process — they publish results and CoreService's result consumer writes DB rows, same path containers use.

### 5.3 Discovery timing

External plugins announce asynchronously. Dispatch-before-announce races: publish a task before any consumer exists. RMQ queues the task until a consumer attaches — fine for short delays. For long ones (no consumer ever attaches), need a timeout → fail job policy. Already partially addressed by existing binder reconnect logic; formalize in H1.

### 5.4 Scientific reproducibility

A misbehaving plugin that returns plausible-looking wrong defocus values is hard to detect. Mitigations across the program:

- **U2**: SemVer contract hardening means which fields mean what is stable across versions.
- **H3b**: automated contract-validation checks before a plugin enters the hub.
- **Two-tier trust** in the hub (verified vs community).
- **Reproducibility audit** (S-tier): every result carries plugin_id + version; operators can cross-check.

This is fundamentally a *community + review* problem, not just a technical one. Don't hand-wave.

### 5.5 Versioning and upgrade pain

If CoreService upgrades its SDK to 2.0 while the user has a community plugin pinned to 1.x, the plugin breaks. Policies to decide:

- Does CoreService refuse to dispatch to a plugin with incompatible SDK version? (Yes — fail-fast is better than silent data corruption.)
- Does the UI warn before upgrading?
- How long do we support each major?

This is a U2 deliverable.

---

## 6. Definition of Done

End of U1:
- `GET /plugins/` returns only liveness-registry entries. `plugins/registry.py` deleted.
- `POST /plugins/{id}/jobs` publishes via `bus.tasks.send`, not `plugin.run()`.
- `CoreService/plugins/*/service.py` files deleted (their broker-side equivalents already exist).
- All tests use `install_mock_bus` or `install_inmemory_bus`; no test imports pika or starts an RMQ container.
- Docker-level smoke tests use real RMQ in their container.

End of U2:
- `magellon-sdk` ships v1.0 with a frozen `magellon_sdk.models.*` public surface.
- Deprecation policy documented.
- All shipping plugins pin `magellon-sdk>=1.0,<2.0`.

End of H1:
- Plugin Browser has per-plugin enable/disable toggles.
- Installing a second FFT implementation doesn't auto-load-balance with the default; operator chooses.

End of H3c:
- Third-party plugin authors can submit archives, get reviewed, and users can install their plugins from the UI without code changes to CoreService.

---

## 7. What we are NOT doing in this plan

- **Workflow engine reintroduction.** Temporal was reverted for a reason. See `feedback_yagni_orchestration`.
- **Envelope format changes.** CloudEvents 1.0 stays.
- **Multi-language plugins.** Python-only for now. The contract is JSON-serializable so cross-language is possible in principle, but adding it pre-hub is premature abstraction.
- **Distributed tracing / OpenTelemetry.** Orthogonal. Rides the envelope when it lands; not a phase.
- **Plugin runtime sandboxing (cgroups, seccomp).** Container isolation is enough for V1. Real sandboxing is a hub-tier item for community plugins, not a foundation.


---

<!--
  Section: 11. Roadmap — Pipeline Ergonomics Plan
  Originated from: Documentation/PIPELINE_ERGONOMICS_PLAN.md
  Merged into this consolidated reference 2026-05-13.
-->

# Pipeline Ergonomics — Plan

**Status:** Proposal, 2026-05-10.
**Audience:** Plugin authors, dispatcher / job-service maintainers, frontend (plugin catalog).
**Scope:** OSS Magellon. The visual workflow / pipeline builder is explicitly out of scope (reserved for Magellon Pro).
**Companion docs:**
- `ARCHITECTURE_PRINCIPLES.md` — especially #4 (abstractions pay their way today), #6 (additive first), and the immutability rule.
- `PLUGIN_MANAGER_PLAN.md` — runtime/operational plane for plugins; the registry UX phase below complements PM6/PM7.
- `MAGELLON_HUB_SPEC.md` — distribution registry; the registry-discovery work consumes Hub.
- `PLUGIN_INSTALL_PLAN.md` — authoring + install pipeline; the install-from-Hub flow is the existing P9.
- `CATEGORIES_AND_BACKENDS.md` §2.2a — the existing subject axis the typed-socket tags extend.
- `CURRENT_ARCHITECTURE.md` §8 — the gap list; this plan closes three of those gaps.

This plan groups four ergonomics improvements adapted from ComfyUI's design that fit the current Magellon contracts with no new infrastructure — additive metadata, one dispatcher-side optimization, and a UX-only layer on top of the existing Hub. Each is independently shippable.

The four tracks:

| Track | What | Why ship it |
|---|---|---|
| **PE1** | Typed-socket subject tags | Wire-shape validation in the schema endpoints + a catalog filter — no more "plugin runs, then fails because the input was wrong shape" |
| **PE2** | Lineage-keyed dispatch cache | Parameter sweeps and re-renders cost zero plugin runs |
| **PE3** | Workflow-as-JSON in exports | Offline reproducibility; users can share runs without DB access |
| **PE4** | Registry-UX layer on the Hub | Discovery / version-pin / "updates available" — completes the OSS plugin marketplace story |

---

## PE1. Typed-socket subject tags

**Status (2026-05-11):** PE1-A (category-level `produces_subject_kind`) and
PE1-B (field-level `input_subjects` / `output_subjects` + dispatch gate)
both shipped. PE1-B uses the existing `subject_kind` / `Artifact.kind`
vocabulary rather than the new richer vocabulary the plan example
sketched — pragmatic choice given that only `particle_stack_id` is an
artifact-OID input today; rich-vocab extension is deferred until more
inputs migrate from paths to artifact OIDs. Frontend catalog filter
(below) is the remaining PE1 deliverable.

### Goal

Make it impossible to dispatch a plugin against an input whose subject type doesn't match what it accepts. Today the schema endpoints (`GET /plugins/{id}/schema/{input,output}`, shipped in Track C) carry field types but not semantic input subjects, so the only validation is "did the dispatcher pass the right number of artifact ids."

### Contract change (additive)

Plugin authors add `accepts:` to input schema fields and `produces:` to output schema fields. Both are lists of subject-axis tags drawn from the same vocabulary `CATEGORIES_AND_BACKENDS.md` §2.2a already uses for the `subject` axis on plugin manifests.

Example (manifest fragment):

```yaml
# manifest.yaml — additive fields only
inputs:
  micrograph:
    type: file
    accepts: ["Micrograph"]
  particle_stack:
    type: file
    accepts: ["ParticleStack"]
    optional: true

outputs:
  picks:
    type: file
    produces: "PickList"
  ctf_estimate:
    type: file
    produces: "CTFEstimate"
```

Type-tag grammar (intentionally minimal):

```
Subject              exact subject match
Subject<sub_tag>     subject with a refinement (reserved; not used in PE1)
*                    any subject (escape hatch; discouraged)
```

We do **not** introduce a richer type system in PE1 — multi-tag (`Layer<Raster:ice_thickness>`) is a Pro-only generalization. Keep OSS narrow.

### Validation seam

`/plugins/capabilities` (Track C) is the dispatch-side authority. Extend it to return the per-field `accepts:` / `produces:` for each plugin. Validation lives in **one** place — `services/dispatch_service.py` (or current owner) — at the moment an artifact-id set is bound to a plugin invocation. Reject with `400 SUBJECT_TAG_MISMATCH` and the exact field + offered subject vs declared subject. Plugin-side validation stays advisory; the gate is server-side.

### Frontend payoff

The plugin catalog grows a "consumes" / "produces" filter that operates entirely on capability metadata. Same surface that already powers the Track-C backend axis filter — additive UI, no new endpoint.

### Migration

- **Manifests without `accepts:` / `produces:`.** Treat as legacy: implicit `accepts: ["*"]`, `produces: "*"`. Log a deprecation warning at announce time. Lint rule (per principle #3): new plugins must declare both. Existing plugins given a deadline before the dispatcher rejects.
- **Alembic.** None — the metadata lives in plugin schemas, not the DB.
- **SDK bump.** Minor (e.g. 2.2 → 2.3); manifest validator gains the optional fields.

### Acceptance

1. A plugin declaring `accepts: ["Micrograph"]` rejects an invocation with a `ParticleStack` input, at the dispatcher, before any worker is woken.
2. The catalog's "what consumes `Micrograph`?" query returns ≥1 result and is computed from `/plugins/capabilities` alone.

---

## PE2. Lineage-keyed dispatch cache

### Goal

The five Artifact invariants (memory: `project_artifact_bus_invariants.md`) — immutability, deterministic params hash, lineage as DAG — already give us everything to deduplicate dispatch. Concretely: if the same plugin at the same version is asked to run with the same input artifact set and the same parameters, return the existing output artifact without re-running the worker.

This is the biggest cost lever for users doing parameter sweeps, picker re-runs after a setting tweak, or re-export operations.

### Cache key

```
cache_key = SHA-256 of (
    plugin_id,
    plugin_version,
    sorted(input_artifact_oids),         # one entry per declared input field
    canonicalized_params_json,           # already computed for params_hash
    category,                            # disambiguate when one plugin serves N categories
)
```

`plugin_version` includes both the package version and the manifest content hash, so a re-installed plugin with edited code produces a different key even at the same SemVer.

### Storage

Two options; recommend **(a)**:

**(a) Reuse the Artifact table.** Add a covering index `(producer_plugin_id, producer_plugin_version, params_hash, input_set_hash)` on `Artifact`. `input_set_hash` is a new hot column on Artifact (cheap; consistent with the existing hot-column policy). Pre-dispatch the controller does a single point lookup against this index. If hit → return the existing artifact's `oid`. No new table.

**(b) Sibling `dispatch_cache` table.** Cleaner separation, but a second source of truth for "what runs have happened" — violates principle #2 (one logical owner). Reject.

### Dispatcher seam

`services/dispatch_service.py` (or current owner) gains one method:

```python
def lookup_cached_output(
    plugin_id: UUID, plugin_version: str,
    category: Category, input_oids: list[UUID], params: dict
) -> UUID | None:
    """Return existing artifact oid if a prior run produced it; else None."""
```

Called right after subject-tag validation (PE1), before the bus publish. On hit, the controller emits the standard `task.completed` event with the cached `oid` so downstream consumers see no difference from a real run — they only notice the latency.

### Cache invalidation

Three cases, in order of frequency:

1. **Plugin version bump.** Key changes naturally; old hits stay valid for re-export but new runs go through.
2. **Input artifact superseded.** Lineage already marks superseded artifacts. The cache lookup filters: if any `input_oid` is superseded, skip the cache (fall through to a real run). This is the correct conservative default.
3. **Manual invalidation.** Admin endpoint (`POST /admin/dispatch-cache/invalidate`) with filters. Rare; expected only after a known-bad plugin run gets identified.

### Acceptance

1. A picker re-run with identical params returns in < 50 ms (cache hit) instead of seconds (worker dispatch).
2. A 5-value colormap sweep against the same upstream artifact set fires exactly 1 plugin run + 4 cache hits.
3. Cache hits are observable in `bus.events` audit (so ops can measure hit rate).
4. Cold-cache behavior is unchanged from today (no regression risk on the slow path).

### Risks

- **False hits from non-determinism.** If a plugin's output depends on wall clock, RNG without seed, or floating-point non-determinism, two runs at the same key are not identical. PE2 is not at fault — those plugins are buggy. Document the contract explicitly: plugins MUST be deterministic given (input artifacts, params). Lint via the existing manifest declaration `deterministic: true` (default true; opt-out plugins skip the cache).
- **Index cost.** One additional index on `Artifact`. Measured cost is bounded by Artifact row count, which is already the system's scale ceiling.

---

## PE3. Workflow-as-JSON in exports

### Goal

When a user exports a result (a stack, a particle list, a CTF estimate), embed enough metadata so they can later answer "how did this come to exist?" without DB access — the same trick ComfyUI plays with PNG metadata. Server-side we already have full lineage in the DAG; the work is **serializing** the relevant subgraph and **embedding** it in exports.

### Wire shape

A compact JSON object describing the lineage subgraph that produced an artifact:

```json
{
  "magellon_workflow_version": 1,
  "exported_at": "2026-05-10T19:00:00Z",
  "root_artifact": {
    "oid": "…",
    "subject": "ParticleStack",
    "producer": {"plugin_id": "…", "version": "1.4.2", "params_hash": "sha256:…"}
  },
  "nodes": [
    {"oid": "…", "subject": "Micrograph",     "source": "imported", "import_uri": "…"},
    {"oid": "…", "subject": "CTFEstimate",    "producer": {…}, "params": {…}},
    {"oid": "…", "subject": "PickList",       "producer": {…}, "params": {…}},
    {"oid": "…", "subject": "ParticleStack",  "producer": {…}, "params": {…}}
  ],
  "edges": [
    {"from": "<oid>", "to": "<oid>", "kind": "input"}
  ]
}
```

Keys:

- `nodes` is the transitive lineage closure of the root, capped (see §3.1).
- Each node carries enough to **re-create** the run if all referenced plugins/versions are installed locally — `params` (full, not hashed), `producer.{plugin_id, version}`, `subject`, and either an `import_uri` (root data sources) or upstream edges.
- No artifact bytes embedded. Refs only.

### Where it goes

| Export type | Embed location | Reader |
|---|---|---|
| Plugin-emitted file (e.g. `.mrcs`) | Sidecar `<filename>.magellon-workflow.json` | Any CLI tool / Magellon importer |
| Star file (`.star`) | Header comment block prefixed `# magellon-workflow:` | Magellon importer; ignored by Relion |
| PNG / WebP thumbnails | `tEXt` / `EXIF` block (key: `magellon:workflow`) | Magellon UI drag-and-drop |
| Bulk export (zip / tar) | Top-level `magellon-workflow.json` | Magellon importer |

### Producing it

One service endpoint:

```
GET /artifacts/{oid}/workflow.json
```

Returns the JSON above. Existing lineage queries already traverse the DAG; this is a serializer on top.

### Sub-questions

- **§3.1 Lineage closure cap.** Practical exports want bounded JSON. Cap at N=200 nodes by default; truncate with a `"truncated_at_depth": K` marker. Full closure available behind a flag.
- **§3.2 Plugin params confidentiality.** Some plugins accept secrets (API keys, paths to private datasets). Manifest extension `params.<key>.export: false` redacts the value in workflow.json. Reuse the existing secret-handling vocabulary (or introduce it here if absent).

### Acceptance

1. A user drags an exported `.png` of a 2D class average back into the Magellon UI and sees the full lineage from import → CTF → pick → extract → class2d.
2. The JSON, fed to a `magellon workflow replay` CLI command on a second deployment with the same plugins installed, produces an identical artifact (same `params_hash`, same `content_hash`).
3. Truncated exports remain valid JSON and are flagged as truncated.

### Out of scope

- The CLI replay tool is a follow-on (own plan).
- Visual rendering of the workflow inside the UI is the Pro workflow-builder's job; OSS keeps a plain JSON view + a tree of artifact cards.

---

## PE4. Registry-UX layer on the Hub

### Goal

Plugin discovery, install, version-pin, and "updates available" in the Magellon UI. This is the missing operational UX on top of the already-shipped Hub spec and install pipeline.

### What already exists

- **MAGELLON_HUB_SPEC.md** — distribution registry server (H1–H3 in progress).
- **PLUGIN_INSTALL_PLAN.md** — P1–P8 shipped; P9 (hub-fetch) deferred.
- **PLUGIN_MANAGER_PLAN.md** — runtime / operational verbs (pause, resume, disable, health). PM6/PM7 sketch updates-badge plumbing.

### What PE4 adds (UX only, no new contract)

A new frontend route `/plugins/registry` with three panes:

1. **Browse.** Search / filter Hub plugins by category, backend, subject-tag (PE1), and capability flag. Lists install state (`installed` / `update available` / `not installed`).
2. **Pinned versions.** For each installed plugin, current version + pin / unpin toggle + history.
3. **Update inbox.** Aggregated "updates available" — one click → diff (manifest + changelog) → confirm → triggers the install pipeline at P9 (hub-fetch).

All three are thin views over existing endpoints + the Hub. The one new endpoint:

```
GET /plugins/registry/index            # local merged view: Hub catalog + local install state
```

Internal-only; the merge logic lives server-side so the frontend never holds Hub credentials.

### Dependencies

- P9 (hub-fetch install) needs to land first or in parallel; PE4 is the UX cap on it.
- PM6 (updates badge) is the per-plugin scalar version; PE4 is the cross-plugin aggregate.

### Acceptance

1. A new operator with an empty install browses the registry, installs three plugins, and sees them announce themselves within the configured liveness window — all from the UI, no CLI.
2. After a Hub publish of plugin X v1.5, an existing X@1.4 install shows the update badge within the existing PM6 refresh cadence.
3. Version pin survives a CoreService restart (lives in DB, not in-process state).

### Out of scope

- Hub submission UX for plugin authors (separate; lives in `MAGELLON_HUB_SPEC.md`).
- Permission model for who can install vs who can browse — assumes the same admin gate as PLUGIN_MANAGER_PLAN PM4.
- Per-tenant catalogs / private registries — Pro-only.

---

## PE2 — Dispatch cache (shipped 2026-05-12)

Lineage-keyed cache as described above. What landed:

- **Alembic 0010** adds four columns + the covering index
  ``ix_artifact_dispatch_cache`` to ``artifact``:
  ``producer_plugin_id``, ``producer_plugin_version``, ``params_hash``,
  ``input_set_hash``. All nullable so pre-PE2 rows survive untouched.
- **SDK** ships ``magellon_sdk.cache`` with three pure functions —
  ``compute_input_set_hash``, ``compute_params_hash``,
  ``compute_cache_key``. Canonical JSON + sorted-OID hashing so the
  same inputs in different order produce the same key.
- **Writer** (``TaskOutputProcessor._maybe_write_artifact``) populates
  the four columns on every new Artifact row by joining to the
  originating ``ImageJobTask`` for plugin id, version, and the input
  params dict.
- **Dispatcher hook** in ``plugins/controller.py`` —
  ``_try_dispatch_cache_hit`` runs before bus publish. On hit, the
  controller returns the prior producing job's envelope with
  ``cached: True`` and ``cached_artifact_id`` so callers see the
  same job_id reference they'd see from a real run. Only categories
  that transform subjects (``produces_subject_kind != None``) cache —
  in-place categories like CTF / MotionCor are unaffected.
- **Supersession filter** in ``services/dispatch_cache.py``: walks
  ``source_artifact_id`` ancestors and refuses a hit when any
  ancestor has been soft-deleted (rule #2 from the plan).
- **Admin invalidate endpoint** at
  ``POST /admin/dispatch-cache/invalidate`` (rule #3, manual). At
  least one filter required — refuses the no-filter case as a
  safety check.

Tests: 17 cache-behavior cases (hit, miss, version bump, params
change, input-set change, soft-delete, superseded ancestor,
invalidate by id/version/oid).

---

## PE4 — Registry UX layer (shipped 2026-05-12)

Three-pane registry view on the React side, one merge endpoint on
the backend.

- **``GET /plugins/registry/index``** fetches the hub's
  ``/v1/index.json`` and joins with local install state. The merge
  shape: per plugin, latest hub version + installed version +
  ``update_available`` flag + ``install_method`` chip + source
  classification (``"hub"`` vs ``"local-only"``). Hub failures
  degrade gracefully — ``hub_status`` reports ``"unreachable"`` or
  ``"http_<code>"`` and the response still carries the local-only
  list so air-gapped deployments aren't blocked by a slow hub.
- **``/panel/plugins/registry``** React page reads the merge and
  splits into three tabs: Browse (hub plugins), Update inbox
  (anything with ``update_available``), Local-only (installed but
  absent from the hub catalog). Search box filters across all three.
- **Pinning persistence is deferred.** Per the plan PE4 acceptance
  #3, "version pin survives CoreService restart" needs a new
  pin-state table. The merge endpoint and the UI tabs are
  independently useful without pinning; a follow-up PR can add the
  pin column + chip without touching the existing routes.

Tests: 12 backend cases (merge happy-path, hub degradation, version
comparison parametrized, hub URL override) + 5 frontend cases
(tab routing, hub-unreachable alert, loading state).

---

## PE6 — UI consumers (shipped 2026-05-12)

Four React additions that close the loop on PE1/PE3/PE5 endpoints
already on the wire:

- **Try-example chip row** in `PluginTestPanel` — consumes
  `capabilities.examples`. Clicking a chip merges the example values
  on top of schema defaults, so any fields the example omits keep
  their declared default. Empty when a category hasn't authored
  examples yet (no chrome eaten).
- **Subject-tag catalog filter** on `InstalledPluginsView` — closes
  PE1 acceptance #2. Filter chips read `subject_kind` /
  `produces_subject_kind` / `input_subjects` / `output_subjects` from
  the capabilities response. Two chips per known subject:
  `consumes <subject>` and `produces <subject>`. Click toggles;
  matched-count is shown next to the registered count.
- **Workflow lineage viewer page** at `/panel/artifacts/:oid` —
  consumes the existing `GET /artifacts/{oid}/workflow.json`. Renders
  the root + ancestors as a vertical stack of cards with plugin id +
  version + collapsible params block + Re-run button.
- **Re-run with same params button** on each non-imported workflow
  node — re-submits the producing plugin through the existing
  `POST /plugins/{plugin_id}/jobs` endpoint with the recorded params.
  Confirms first when any param value is the redacted-secret
  sentinel so the operator doesn't accidentally fire a literal
  `"<redacted>"` string at the plugin. No new backend endpoint
  needed — the workflow JSON already contains everything.

Cribbed from: Gradio (examples gallery), VS Code marketplace tag
filters (subject-tag chips), CryoSPARC's "Clone with inputs" (re-run
button), Dagster's asset materialization view (the lineage cards).
13 vitest cases pin the filter logic + viewer behaviour.

---

## PE5 — Examples gallery + decorated SDK inputs (shipped 2026-05-12)

Cribbed from Gradio / HF Spaces: every plugin should be runnable from
the test panel in one click without the operator inventing values for
microscope parameters they haven't internalised yet. Two additive
changes, no infra:

- **`CategoryContract.examples: list[CategoryExample]`** in
  `magellon-sdk`. Each entry is `{name, description, values}`. Surfaced
  on `GET /plugins/capabilities` so the React side renders one chip per
  example next to the SchemaForm; clicking a chip pre-fills the form
  values. Validated against the category's `input_model` at registry
  load so a typo fails at SDK import, not at operator click time.
- **`ui_widget` / `ui_group` / `ui_marks` / `ui_unit` / `ui_tunable`
  decorations on every SDK plugin input** (CtfInput, MotionCorInput,
  FftInput, TopazPickInput, MicrographDenoiseInput, PtolemyInput,
  ParticleExtractionInput, TwoDClassificationInput). Pre-this-change
  the existing SchemaForm fallback rendered bare numeric fields with
  no groups / units / help. Post-change every plugin renders like the
  template-picker: grouped accordions, slider marks, unit suffixes,
  advanced collapsed by default.

The React side already supports both — `SchemaForm` reads `ui_*`,
`ParticleSettingsDrawer` already debounces tunable changes for live
retune. The decorations unlock that UX for every plugin, not just
the template-picker. Catalog filter (PE1 acceptance #2) and a
React "Try example" dropdown remain open.

---

## Cross-cutting non-goals

- **Visual workflow / pipeline builder.** Pro.
- **Layered images.** Pro (see `magellon-rust-mrc/docs/image-layers-architecture.md`).
- **Cross-plugin scheduling primitives.** YAGNI (memory: `feedback_yagni_orchestration.md`). The four tracks here add value without orchestration.

---

## Sequencing recommendation

PE1 first — it unblocks the cache-key precision in PE2 (subject-aware caching is sharper than blind-input caching) and the registry filter in PE4. PE2 and PE3 can land in parallel after PE1. PE4 waits on P9.

```
PE1 ─┬─→ PE2 ─┐
     ├─→ PE3 ─┤
     └─→ PE4  ┘   (also waits on P9)
```

No track requires a feature flag — all four are additive, off-by-default-friendly, and revertable by reverting the metadata.


---

<!--
  Section: 12. Roadmap — Pipeline Ergonomics First Slice
  Originated from: Documentation/PIPELINE_ERGONOMICS_FIRST_SLICE.md
  Merged into this consolidated reference 2026-05-13.
-->

# Pipeline Ergonomics — First Slice (Cheap Cut)

**Status:** Shipped 2026-05-10 — see commit log around `b747f8c`. PE1-A and PE3-lite both landed; PE2 + PE3-full + PE4 + multi-input lineage remain deferred per the table at the bottom. This doc is retained as the implementation reference; once any of the deferred tracks ship, expand or supersede.
**Audience:** Implementer of the slice, reviewer.
**Companion docs:** `PIPELINE_ERGONOMICS_PLAN.md` (four-track roadmap), `ARCHITECTURE_PRINCIPLES.md`.

This doc names the two tracks worth landing now and the two worth deferring. Each change is grounded in a current file path and existing seam — no new infrastructure, no DB migrations, no breaking contract changes.

---

## Scope

**In — land in this slice:**

- **PE1-A — Subject-tag socket validation (lite).** Surface the existing `CategoryContract.subject_kind` on the capabilities endpoint, add `produces_subject_kind` for outputs, and add an explicit dispatch-side rejection for subject-kind mismatches.
- **PE3-lite — Workflow-as-JSON endpoint.** One new endpoint `GET /artifacts/{oid}/workflow.json` that serializes the existing single-parent ancestor chain + producer plugin metadata. No file-format embedding (PNG `tEXt`, star comments, zip top-level) in this slice.

**Deferred — flagged at end:**

- **PE2 — Dispatch cache.** Requires a new hot column + index on `Artifact` + Alembic migration. Worth doing, but not this slice.
- **PE3 full — Format embedding.** PNG `tEXt`, `.star` header comments, zip top-level. Per-format work; ship the endpoint first, let it bake.
- **PE4 — Registry UX.** Depends on `PLUGIN_INSTALL_PLAN` P9 (hub-fetch install, currently deferred). Blocked.

**Out — not this plan:**

- Multi-input lineage. `Artifact.source_artifact_id` is a single-parent FK (`models/sqlalchemy_models.py:718`). True DAG lineage is a separate effort; PE3-lite serializes what's representable today.
- Visual workflow / pipeline builder (Pro).

---

## Current state (grounded, 2026-05-10)

Each track's "what's missing" depends on what's already there. The relevant seams:

| Concept | Lives at | Shape today |
|---|---|---|
| Category contract | `magellon-sdk/src/magellon_sdk/categories/contract.py:136` | `CategoryContract(BaseModel)` with `subject_kind: str = "image"` (line 158) and `input_model` / `output_model` (Pydantic) |
| Subject-kind on dispatch | `CoreService/plugins/controller.py:816` | `_derive_subject(contract, validated)` already threads `(subject_kind, subject_id)` into the bus task |
| Capabilities endpoint | `CoreService/plugins/controller.py:194` | `GET /capabilities` returns `_CategoryCapabilities` with `input_schema` / `output_schema` but **no `subject_kind`** field |
| Schema endpoints | `CoreService/plugins/controller.py:572, 590` | `GET /plugins/{id}/schema/{input,output}` returns `contract.{input,output}_model.model_json_schema()` |
| Artifact + lineage | `CoreService/models/sqlalchemy_models.py:691` | Single parent via `source_artifact_id` (self-FK). `producing_task_id` carries plugin reference. `data_json` for cold metadata. |
| Lineage walk | `CoreService/controllers/artifacts_controller.py:148` | `GET /artifacts/{oid}/lineage` already walks ancestors (bounded depth 20) + direct descendants |

What's missing for the slice:

- `CategoryContract.produces_subject_kind` (none today; output subject is implicit).
- Subject-kind exposure on `_CategoryCapabilities` (the schema is there; the tag isn't).
- An explicit "your input doesn't match this plugin's subject" rejection at dispatch.
- A `/artifacts/{oid}/workflow.json` serializer.

---

## PE1-A — Subject-tag socket validation (lite)

### Changes, file by file

**1. `magellon-sdk/src/magellon_sdk/categories/contract.py`** — add one field.

```python
class CategoryContract(BaseModel):
    # existing fields...
    subject_kind: str = "image"               # already present
    produces_subject_kind: str | None = None  # NEW — None means "same as subject_kind"
```

`None` default keeps every existing contract valid. For categories that transform subjects (e.g. `PARTICLE_EXTRACTION`: image → particle_stack), the call site in `categories/__init__.py` sets it explicitly. SDK minor bump (2.2 → 2.3).

**2. `CoreService/plugins/controller.py`** — extend the capability response shape.

```python
class _CategoryCapabilities(BaseModel):
    # existing fields...
    input_schema: Optional[Dict[str, Any]] = None
    output_schema: Optional[Dict[str, Any]] = None
    subject_kind: str = "image"               # NEW
    produces_subject_kind: str | None = None  # NEW
```

Populate in `list_capabilities()` (line 199) from the contract — three new lines next to the existing `input_schema` block (line 273).

**3. `CoreService/plugins/controller.py`** — add the dispatch gate.

The current dispatch path (`submit_job` line 602 → `_submit_broker_job` → `_derive_subject`) currently accepts whatever the request carries. Add **one validation call** between request parse and `_derive_subject`:

```python
def _reject_if_subject_mismatch(
    contract: CategoryContract,
    validated: BaseModel,
    request: JobSubmitRequest,
) -> None:
    """Reject 422 if the caller's input subject doesn't match
    contract.subject_kind. Idempotent — silent on match."""
    # Aggregate categories (subject == particle_stack etc.) require
    # subject_id on the request; image categories use request.image_id.
    expected = contract.subject_kind
    if expected == "particle_stack" and request.particle_stack_id is None:
        raise HTTPException(422, f"Category requires particle_stack_id (subject={expected})")
    if expected == "image" and request.image_id is None and request.subject_id is None:
        raise HTTPException(422, f"Category requires image_id (subject={expected})")
```

Hooked into `_submit_broker_job` and `_submit_broker_batch`. The existing `_derive_subject` already handles the happy path, so this is the explicit rejection seam the plan called for.

**4. Tests.** Add to `tests/characterization/test_plugin_controller_http.py`:

- Capabilities response includes `subject_kind` per category.
- Submitting a `PARTICLE_EXTRACTION` job with only `image_id` (no `particle_stack_id`) returns 422.
- Submitting a `CTF` job with `image_id` succeeds (regression check on the happy path).

### Acceptance

1. `GET /plugins/capabilities` includes `subject_kind` and (where set) `produces_subject_kind` per category.
2. Dispatching a particle-stack-keyed plugin without `particle_stack_id` returns 422 at the controller, before any bus publish.
3. No existing characterization test fails.

### Cost estimate

≈ 1–2 days. SDK field + capability shape + dispatch gate + tests + manifest doc note. No migration, no breaking API change (additive only).

---

## PE3-lite — Workflow-as-JSON endpoint

### Goal

Ship `GET /artifacts/{oid}/workflow.json` as a serializer over the existing single-parent ancestor walk. No format embedding yet. The endpoint is the reusable primitive; embed-in-PNG / embed-in-star can follow when there's demand.

### Wire shape

Re-using the structure from `PIPELINE_ERGONOMICS_PLAN.md` §PE3, scoped to single-parent lineage:

```json
{
  "magellon_workflow_version": 1,
  "exported_at": "2026-05-10T19:00:00Z",
  "lineage_shape": "single_parent_chain",
  "root_artifact": {
    "oid": "…",
    "kind": "particle_stack",
    "producer": {
      "plugin_id": "…",
      "plugin_version": "1.4.2",
      "category": "PARTICLE_EXTRACTION",
      "params": { … }
    }
  },
  "ancestors": [
    {"oid": "…", "kind": "image",        "producer": null,  "source": "imported"},
    {"oid": "…", "kind": "ctf_estimate", "producer": { … }},
    {"oid": "…", "kind": "pick_list",    "producer": { … }}
  ],
  "truncated_at_depth": null
}
```

`lineage_shape` is literal `"single_parent_chain"` — honest about the current schema. When multi-input DAG lineage lands, the value becomes `"dag"` and `ancestors` grows edges.

### Changes, file by file

**1. `CoreService/controllers/artifacts_controller.py`** — one new endpoint next to the existing `/lineage` route (line 148).

```python
@artifacts_router.get("/{oid}/workflow.json", response_model=WorkflowExport)
def get_artifact_workflow(
    oid: UUID,
    db: Session = Depends(get_db),
    user_id: UUID = Depends(get_current_user_id),
):
    """Serialize the single-parent ancestor chain + producer plugin
    metadata. Stable JSON for offline reproducibility / sharing.
    """
    root = db.query(Artifact).filter(Artifact.oid == oid).first()
    if root is None or root.deleted_at is not None:
        raise HTTPException(404, "Artifact not found")

    chain = _walk_ancestors(db, root, max_depth=200)
    return WorkflowExport(
        magellon_workflow_version=1,
        exported_at=datetime.utcnow(),
        lineage_shape="single_parent_chain",
        root_artifact=_artifact_to_workflow_node(db, root),
        ancestors=[_artifact_to_workflow_node(db, a) for a in chain],
        truncated_at_depth=200 if len(chain) >= 200 else None,
    )
```

The existing `/lineage` walk (line 167–178) uses depth 20 — re-use the same pattern, raised to 200 per the plan. Factor the walk into `_walk_ancestors(db, artifact, max_depth)` and call it from both endpoints. This is a tiny refactor; reject it if it bloats the diff.

**2. Producer extraction.** `_artifact_to_workflow_node` joins `artifact → producing_task → plugin` to recover `plugin_id`, `plugin_version`, `category`, `params`. The join already exists implicitly via `producing_task_id` (line 711). New helper, ~15 lines.

**3. Pydantic response models.** Two small classes (`WorkflowProducer`, `WorkflowNode`, `WorkflowExport`) in `models/pydantic_models.py` next to the existing `ArtifactView` / `ArtifactLineageView`.

**4. Secret redaction.** Producer `params` may contain secrets. Two options:

  - **Cheap (this slice):** Redact any param whose **key** matches `re.compile(r"(secret|password|token|api[_-]?key)", re.I)` — replace value with `"<redacted>"`. Documented behavior.
  - **Robust (later):** Manifest declares `params.<key>.export: false`. Out of scope here.

Pick (a) for now and call it out in the docstring.

**5. Tests.** Add to `tests/controllers/test_artifacts_controller.py`:

- Workflow JSON for a leaf artifact returns the full chain back to an imported root.
- Producer block populated for non-imported artifacts; `null` for the imported root.
- Param key `"api_key"` is redacted to `"<redacted>"`.
- Truncation flag set when chain exceeds depth 200.

### Acceptance

1. `GET /artifacts/{oid}/workflow.json` returns a JSON document parseable by `pydantic.BaseModel.model_validate`.
2. Output matches the existing `/lineage` ancestor list (same artifacts, same order).
3. Secret-keyed params are redacted.
4. A CLI smoke command (`curl … | jq .root_artifact.producer.plugin_id`) prints the producing plugin id without errors.

### Cost estimate

≈ 1 day. One endpoint, three Pydantic models, ≈ 50 lines of serialization, four tests.

---

## Sequencing — as shipped

Landed in four commits on `main` on 2026-05-10:

| Commit | Track | Scope |
|---|---|---|
| `e6e70e6` | docs | `PIPELINE_ERGONOMICS_PLAN.md` + this doc + README index |
| `35e7b65` | sdk | `CategoryContract.produces_subject_kind`; bump 2.2.0 → 2.3.0 + CHANGELOG entry |
| `3d5cb46` | core PE1-A | `subject_kind`/`produces_subject_kind` on `/plugins/capabilities`; `_reject_if_subject_missing` gate in `_submit_broker_job`/`_submit_broker_batch`; 3 characterization tests |
| `b747f8c` | core PE3-lite | `GET /artifacts/{oid}/workflow.json` + Pydantic models + secret redaction + 9 tests (7 happy path + 2 truncation boundary) |

Original sequencing rationale (PE1-A before PE3-lite because the SDK change is a release artifact) held.

---

## Deferred — what's worth doing next

| Track | Trigger to start | Cost when picked up |
|---|---|---|
| **PE2 dispatch cache** | After PE1-A — subject-kind-aware cache key is sharper | Migration + index + dispatcher pre-check + audit event. ≈ 1 sprint. |
| **PE3 full** — format embedding | When a real user case lands (e.g. "I exported a star file and want to re-import its lineage") | Per-format adapters; PNG `tEXt` first (drop-in zone). ≈ 3 days per format. |
| **PE4 registry UX** | After `PLUGIN_INSTALL_PLAN` P9 (hub-fetch install) | UX layer only — depends on Hub MVP. ≈ 1 sprint. |
| **Multi-input DAG lineage** | When a plugin needs to record ≥ 2 input parents (e.g. CTF + Micrograph → ParticleStack) | New `artifact_input_edge` table + migration + lineage walk update + PE3 `lineage_shape: "dag"`. ≈ 1 sprint. |

---

## Non-goals

- Backwards-incompatible changes to `CategoryContract` or `_CategoryCapabilities`. All additions are optional fields with safe defaults.
- New DB tables or migrations in this slice.
- Visual rendering of `workflow.json` in the UI. Pro workflow builder territory; OSS users get the JSON.
- Replacing the existing `/lineage` endpoint. `workflow.json` is a sibling, not a successor.

