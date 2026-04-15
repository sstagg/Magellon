# Magellon — Target Architecture and Migration Plan

**Status:** Proposal. Not merged. Discuss before acting on phase boundaries.
**Audience:** Core maintainers, plugin developers, operators.
**Companion:** `CURRENT_ARCHITECTURE.md` (the as-is state this plan migrates away from).

---

## 0. Reading guide

This document is opinionated where the evidence supports one answer, and
explicitly labels the places where **either of two choices would work**. The
user asked for "whatever you see fits" and "both works, it is better to be if
there is ambiguity". Follow the bold **Ambiguity** call-outs for those
decisions and revisit them when you have usage data.

The plan assumes the reader has read `CURRENT_ARCHITECTURE.md` and accepts
its critique of the three-job-manager / two-plugin-architecture split.

---

## 1. Design principles

1. **One job has one row of truth.** Three job managers collapse into one.
2. **A plugin is a plugin, not a deployment style.** The same Python contract
   runs in-process, in a local container, or on a cloud GPU — the caller
   doesn't care.
3. **Don't reinvent the wheel.** Temporal for orchestration, NATS JetStream
   for events, CloudEvents for envelope, RunPod (or equivalent) for cloud
   GPU. All already deployed or adoptable with minimal drag.
4. **The user must *see* their job.** Mid-flight progress is a product
   requirement, not a nice-to-have. It is the feature that prompted this
   refactor.
5. **Versioned contracts only.** Plugin I/O, events, and envelopes carry
   explicit schema versions. Silent schema drift is the class of bug that
   has hurt us the most.
6. **Reversible migrations.** Every phase ships behind a feature flag or a
   parallel deploy. No phase is allowed to land without a rollback path.
7. **Small, complete vertical slices.** One plugin, end-to-end, on the new
   stack before the second plugin starts moving.

---

## 2. Target picture in one diagram

```
  ┌─────────────┐      REST + WS         ┌──────────────────────┐
  │  React app  │◄────────────────────► │     CoreService      │
  └─────────────┘                        │  (FastAPI + Socket.  │
                                         │   IO + REST)         │
                                         └────────┬─────────────┘
                                                  │
                            start_workflow / query │        publish event
                                                  ▼               ▼
                                         ┌──────────────┐ ┌────────────────┐
                                         │  Temporal    │ │ NATS JetStream │
                                         │  (server +   │ │  job.*, step.*,│
                                         │   workers)   │ │  worker.*      │
                                         └──────┬───────┘ └───────┬────────┘
                                                │                 │
                          activity = plugin.run │                 │ subscribers:
                                                ▼                 ▼  UI gateway,
                                         ┌──────────────┐  audit log, metrics
                                         │  Executor    │
                                         │  abstraction │
                                         ├──────────────┤
                                         │ Local proc.  │
                                         │ Local docker │
                                         │ Kubernetes   │
                                         │ RunPod GPU   │
                                         │ SLURM        │
                                         └──────┬───────┘
                                                │ runs
                                                ▼
                                         ┌──────────────┐
                                         │ PluginBase   │
                                         │   (SDK)      │
                                         └──────────────┘
```

Five moving parts: **CoreService**, **Temporal**, **NATS JetStream**, the
**Executor abstraction**, and the **Plugin SDK**. Each is discussed below.

---

## 3. CoreService: one JobManager, everything else reactive

This is the actor / message-pump pattern, using Temporal + NATS JetStream as
the transport. Restated in those terms:

- **One authority per job.** A single `JobManager` owns the row in MySQL,
  starts the Temporal workflow (workflow ID *is* the job ID), and publishes
  lifecycle events (`magellon.job.*`) to JetStream. Nobody else writes the
  job row.
- **Everyone else is a reactive consumer.** Workers (Temporal activities
  running plugin code), the UI gateway, the audit log, and the metrics
  collector all *subscribe* to subjects. They never poll the authority.
- **Workers publish back.** While a plugin runs, its `ProgressReporter`
  emits `magellon.step.progress` events onto JetStream. A small projector
  folds those into the job row (so the API surface stays query-able) and
  the UI gateway forwards them to Socket.IO per-`sid`.
- **Envelope stays packet + data.** The same mental model already in
  `TaskBase` + `data: Dict[str, Any]` — wrapped in the CloudEvents frame so
  it's a published standard and carries `dataschema` for schema pinning.

This is the classic "actor with mailbox" / Win32 message-pump pattern:

| Classic concept                      | Target implementation                     |
|--------------------------------------|-------------------------------------------|
| Actor / window                       | Temporal worker, keyed per plugin         |
| Mailbox / message queue              | Temporal task queue *+* NATS subject      |
| `receive` loop / `GetMessage`        | Worker poll + NATS subscriber             |
| Message                              | CloudEvents envelope (`type` + `data`)    |
| Address (`HWND`, actor ref)          | `subject: magellon.job.<id>.step.<step>`  |
| Supervision / "let it crash"         | Temporal retry + timeout policies         |

Two properties this variant buys you that raw actors or Win32 queues don't:

1. **Durable orchestration.** Temporal persists workflow history, so the
   orchestrator can crash mid-pipeline and resume on the same inputs.
2. **Event replay.** JetStream retains events, so late subscribers (a new UI
   tab, an audit rebuild) catch up cleanly. Win32 queues are ephemeral; Akka
   mailboxes are in-memory by default.

Trade-off: slightly higher latency than direct actor refs, because events go
through a broker. In exchange, every message is observable on the bus and
new consumers attach without producers knowing.

### 3.1 What collapses

- **Live `services/job_service.py` (MySQL)** is the base that survives. It
  grows an internal `EventPublisher` handle so every mutation emits onto
  JetStream.
- **`services/job_manager.py` (Dragonfly side path)** is retired in Phase 5
  after `controllers/import_controller.py` is updated to use the unified
  service. Dragonfly stays in the stack for narrower use (idempotency
  tokens, rate limits, cache) — it stops being a state-of-record duplicate.
- **`services/magellon_job_manager.py` + `services/temporal_job_manager.py`
  (scaffolding)** fold into the unified service as its Temporal-driver and
  NATS-publisher internals. The standalone classes disappear.

State-of-record stays in **MySQL**. Everything else is cache or event
stream.

**Ambiguity — MySQL vs Postgres.** MySQL is current. Postgres would give
cleaner JSON operators and `LISTEN/NOTIFY` as a fallback if NATS is down. The
migration cost is not zero but not huge (SQLAlchemy abstracts most of it).
Recommend: **stay on MySQL** unless an independent reason to switch appears.
Don't couple this migration to a DB swap.

---

## 4. The plugin SDK (`MagellonSdk/`)

Today `MagellonSdk/` is a scaffold. Target:

```
MagellonSdk/src/magellon_sdk/
├── __init__.py
├── base.py             # PluginBase (moved out of CoreService)
├── progress.py         # ProgressReporter Protocol, NullReporter
├── envelope.py         # CloudEvents-shaped TaskEnvelope + versioning helpers
├── executor/
│   ├── __init__.py
│   ├── local.py        # in-process
│   ├── docker.py       # local container via docker SDK
│   ├── runpod.py       # POST /run + webhook
│   ├── kubernetes.py   # Job object
│   └── slurm.py        # sbatch
├── worker.py           # Temporal worker scaffold — one call to run a plugin
├── testing.py          # fakes: InMemoryJobService, FakeReporter, etc.
└── cli.py              # magellon-plugin new / test / package
```

The SDK is versioned with semver. A plugin pins `magellon_sdk>=X.Y,<X+1`. Any
breaking change to `PluginBase` or the envelope bumps the major version.

**Plugin author's hello-world:**

```python
from magellon_sdk import PluginBase, PluginInfo, TaskCategory
from pydantic import BaseModel

class MyInput(BaseModel):
    mrc_path: str
    pixel_size: float

class MyOutput(BaseModel):
    defocus: float
    num_items: int

class MyPlugin(PluginBase[MyInput, MyOutput]):
    task_category = TaskCategory(code=101, name="my-ctf", description="...")

    def get_info(self):
        return PluginInfo(name="my-ctf", version="0.1.0", schema_version="1",
                         developer="me", description="...")

    @classmethod
    def input_schema(cls): return MyInput
    @classmethod
    def output_schema(cls): return MyOutput

    def execute(self, data, *, reporter):
        reporter.report(10, "reading mrc")
        # ... compute ...
        reporter.report(90, "writing output")
        return MyOutput(defocus=1.5, num_items=1234)
```

The plugin developer writes **one file**. They do not touch RabbitMQ,
Temporal, NATS, Docker, or MySQL. The same class deploys:

- **In-process** (imported by the registry), if the category allows it.
- **As a Temporal worker** (`magellon-plugin worker --plugin my-ctf`) for
  heavy work.
- **As a RunPod handler** (`magellon-plugin runpod-image` builds the image
  with a one-line handler wrapping `MyPlugin().run(event["input"])`).

---

## 5. The executor abstraction

`Executor` is a small interface the SDK implements per-deployment:

```python
class Executor(Protocol):
    async def submit(self, *, plugin_id: str, payload: dict,
                     job_id: str, reporter: ProgressReporter) -> dict: ...
    async def cancel(self, job_id: str) -> None: ...
```

Executors:

| Executor      | When                                    | How                                                   |
|---------------|-----------------------------------------|-------------------------------------------------------|
| `LocalProcess`| CPU plugins in CoreService's loop       | `loop.run_in_executor`, same path as today            |
| `LocalDocker` | GPU plugin, single-node dev             | Spawn container with `docker-py`, stream stdout       |
| `Kubernetes`  | On-prem cluster                         | `kubernetes.client` creates a `Job`; stream logs      |
| `RunPod`      | Cloud GPU, pay-per-second               | `POST /v2/{endpoint}/run`; progress via webhook       |
| `SLURM`       | HPC partners                            | `sbatch` submit; poll via `sacct`                     |

The **Temporal activity** picks the executor from per-plugin config. This is
where cloud GPU stops being the customer's problem: they set
`executor: runpod` and an API key in config, and the same CTF or MotionCor
workflow runs unchanged.

**Ambiguity — Kubernetes Job vs a persistent worker pool.** For
low-frequency, long-running plugins (MotionCor on a big movie), a one-shot
`Job` is cleaner. For high-throughput CTF on many images, a warm worker pool
amortises startup. Recommend: **start with one-shot Jobs**, add a pool if
profiling shows startup dominates.

---

## 6. Workflows = pipelines of plugins

This is the "gstreamer pipeline / Temporal workflow" vision formalised.

```python
@workflow.defn
class LeginonImportWorkflow:
    @workflow.run
    async def run(self, inputs: LeginonImportInput) -> LeginonImportOutput:
        images = await workflow.execute_activity(
            "file_scan", inputs.source, start_to_close_timeout=...)

        # Fan out per image.
        async with workflow.new_cancel_scope():
            fft_results = await asyncio.gather(*[
                workflow.execute_activity("fft", img, ...) for img in images
            ])
            ctf_results = await asyncio.gather(*[
                workflow.execute_activity("ctffind", img, ...) for img in images
            ])
            mc_results = await asyncio.gather(*[
                workflow.execute_activity("motioncor2", img, ...) for img in images
            ])

        return LeginonImportOutput(ctf=ctf_results, mc=mc_results)
```

Properties this buys you for free:

- **Durable execution.** CoreService can crash mid-pipeline and resume.
- **Retries, timeouts, and backoff** declared per activity.
- **Cancellation** via `workflow_handle.cancel()`, propagated as
  `JobCancelledError` inside the plugin (already in `plugins/progress.py`).
- **Queries.** The existing `workflow_handle.query("get_progress")` pattern
  in `services/temporal_job_manager.py:239` keeps working.
- **Web UI.** Temporal's own UI is a free operator surface.

A "pipeline" is just a workflow. Users can compose their own in Python; a
small DSL can come later if there is demand.

**Ambiguity — Temporal vs NATS-JetStream-as-orchestrator vs Prefect.**
Temporal is the most mature and already 90% wired. JetStream can carry
messages but does not give you durable workflow state or queries — you'd
rebuild them. Prefect is another option but introduces a second
orchestrator. Recommend: **Temporal**. Keep JetStream as the *event bus*,
not the orchestrator.

---

## 7. Event taxonomy (CloudEvents + NATS)

Every event on the bus uses the CloudEvents envelope:

```json
{
  "specversion": "1.0",
  "id": "01HXXXXXXXXX",
  "source": "magellon/core",
  "type": "magellon.job.progress.v1",
  "subject": "job/<job_id>",
  "time": "2026-04-14T12:34:56.789Z",
  "datacontenttype": "application/json",
  "dataschema": "magellon://schemas/step.progress/v1",
  "data": {
    "job_id": "…", "step_id": "…", "plugin_id": "ctf/ctffind",
    "percent": 42, "message": "fitting"
  }
}
```

NATS subjects (keep the names already in `services/event_publisher.py`):

```
magellon.job.created       magellon.job.started       magellon.job.progress
magellon.job.completed     magellon.job.failed        magellon.job.cancelled
magellon.step.started      magellon.step.progress     magellon.step.completed
magellon.step.failed       magellon.worker.registered magellon.worker.heartbeat
```

Prefix with `magellon.` so other tenants on the same NATS cluster can't
collide. Each subject has a pinned JSON schema in `schemas/` in this repo.

**One Socket.IO gateway** subscribes to `magellon.>` on behalf of the
browser. Browser-side code stops caring whether a job ran in-process or on
RunPod — same event stream, same frames.

---

## 8. Phased migration plan

Each phase ends with: green CI, a rollback switch, and an updated section in
`CURRENT_ARCHITECTURE.md` describing the new reality.

### Phase 0 — Safety net (no behaviour change)

- **Characterization tests** on every current envelope and every queue name.
  These tests *codify the bug-for-bug current shape* so the refactor can't
  drift silently.
- **End-to-end smoke test:** submit one Leginon import, assert
  `ctf_tasks_queue` and `motioncor_tasks_queue` see the exact payload shape
  they see today.
- **Contract test** per external plugin: `pytest` boots plugin image, sends
  canned message, asserts canned response.
- **Golden-file tests** on `TaskBase.model_dump()` for CTF and MotionCor
  envelopes.
- Deploy Temporal server in `docker-compose.yml` as an additional service
  (no workers yet, no workflow starts from prod paths).

**Exit criterion:** CI catches any change to envelope bytes-on-the-wire.

### Phase 1 — Extract the SDK

- Move `CoreService/plugins/base.py` and `plugins/progress.py` into
  `MagellonSdk/src/magellon_sdk/`.
- CoreService re-exports from the SDK so existing imports keep working.
- Publish `magellon-sdk` to a private index at `0.1.0`.
- Add CloudEvents envelope helpers and `TaskEnvelope` (Pydantic) to the SDK.
- *No plugin changes yet.*

**Exit criterion:** `pip install magellon-sdk` gives you `PluginBase`. All
existing tests pass with the new import path.

### Phase 2 — First plugin end-to-end on the new stack (the vertical slice)

Pick **CTF** as the pilot because it has no GPU dependency and its
plugin is already fairly small.

- Write a Temporal worker inside the CTF plugin container that runs
  `Ctffind().run(payload)`.
- Write a one-activity workflow `CtfWorkflow` whose single activity calls
  the CTF plugin.
- Add a feature flag `CTF_VIA_TEMPORAL` in CoreService. When on, dispatch
  goes through `TemporalJobManager.start_workflow`; when off, through the
  existing RabbitMQ path.
- UI gateway subscribes to `magellon.step.progress` and forwards to Socket.IO.

**Exit criterion:** In staging, a Leginon import runs CTF through Temporal
and every other step through the legacy path. Progress frames render in the
UI. Rollback = flip the flag.

### Phase 3 — Executor abstraction

- Land `LocalProcess` and `LocalDocker` executors in the SDK.
- Land the `RunPod` executor. Include a sample RunPod handler in the docs.
- Migrate CTF to use the executor abstraction (no behaviour change for the
  default `LocalProcess` path).
- Add a per-plugin config key `executor:` (default `localprocess`).

**Exit criterion:** One customer can flip their CTF plugin to
`executor: runpod` in YAML and have the same workflow run on cloud GPU.

### Phase 4 — Second and third plugin migrations

- MotionCor: same pattern as CTF, plus validation of the RunPod executor on
  a GPU workload.
- Result processor: rewrite as a Temporal workflow step that consumes the
  activity's direct return value. `ctf_out_tasks_queue` and
  `motioncor_out_tasks_queue` disappear because Temporal carries the
  result.
- Particle picker (`pp/template-picker`): already in-process; wrap in a
  workflow to unify UI behaviour.

**Exit criterion:** Every plugin that currently uses RabbitMQ can be
switched to Temporal with a flag. Rollback still works.

### Phase 5 — Retire legacy

- Delete `core/helper.py:get_queue_name_by_task_type` and the
  `dispatch_*_task` functions.
- Delete `core/rabbitmq_client.py`.
- Drop RabbitMQ from `docker-compose.yml` (after a staging soak).
- Collapse the three job managers. `services/job_manager.py` (Dragonfly) and
  the NATS `services/magellon_job_manager.py` merge into the MySQL-backed
  `JobService`. Dragonfly remains for cache/idempotency.
- Remove the per-plugin duplicated `core/` subpackages.
- Delete the on-disk message audit (`/magellon/messages/...`) in favour of
  JetStream retention.

**Exit criterion:** Repo grep for "rabbitmq" returns only archaeology in
docs. One `JobService`. One plugin SDK. One event path.

---

## 9. Test strategy per phase

| Layer               | Tool                         | Owned by     | Runs when           |
|---------------------|------------------------------|--------------|---------------------|
| Plugin unit tests   | `pytest` on `Plugin().run()` | Plugin dev   | Plugin CI           |
| Envelope golden     | `pytest` + JSON golden files | Core         | Core CI             |
| Contract tests      | `pytest` + plugin container  | Core         | Core CI nightly     |
| Workflow tests      | `temporalio.testing`         | Core         | Core CI             |
| Event schema tests  | JSON Schema + `pytest`       | Core         | Core CI             |
| End-to-end staging  | Playwright + real services   | Core         | Pre-release         |
| Load / backpressure | Locust + NATS traffic shaping| Core         | Pre-release         |

**Key rule:** no plugin ships without a contract test pinning its input and
output schemas, and the envelope it produces.

---

## 10. Risks and rollbacks

| Risk                                                        | Mitigation                                                        | Rollback                          |
|-------------------------------------------------------------|-------------------------------------------------------------------|-----------------------------------|
| Temporal server becomes a new single point of failure       | HA deploy (three nodes) in Phase 2+ staging; document DR          | Feature flag to RabbitMQ path     |
| NATS JetStream stream fills up                              | Size streams; alert on consumer lag; use max-age retention        | Smaller retention; flush streams  |
| RunPod latency spikes or outage                             | Executor health-check; fallback executor per plugin               | `executor: localdocker` fallback  |
| CloudEvents adoption breaks a legacy consumer               | Keep bug-for-bug envelope on RabbitMQ until Phase 5               | No code change needed             |
| Plugin authors resist SDK semver discipline                 | Public CHANGELOG; linter in the SDK; deprecation window of 2 versions | N/A                               |
| Three-manager collapse corrupts a job row                   | Characterization tests; dual-write during Phase 5; backup before  | Restore from backup, flip flag    |

Every phase is a feature flag or a parallel deploy. There is no big-bang
cutover.

---

## 11. Non-goals

These are things this plan does **not** try to solve, on purpose:

- Replacing MySQL with Postgres (see §3 ambiguity).
- Replacing Dragonfly with plain Redis (no win, added migration).
- Introducing Akka or any actor framework. "Plugin as actor" is expressed as
  "plugin as Temporal activity" — same mental model, less new infrastructure.
- Splitting CoreService into multiple services. Monolith first; split only
  if hot paths demand it.
- Authoring a DSL for pipelines. Temporal workflow code in Python *is* the
  DSL until a domain need proves otherwise.

---

## 12. Open questions to resolve before Phase 2

1. **Where does Temporal live in staging?** Single-node or three-node from
   day one? (Recommend single-node for staging, three-node for prod.)
2. **Who owns plugin images?** The SDK CLI should build them; but do we
   publish to a central registry, or does each customer build their own? (Recommend
   central registry for core plugins; customers can override.)
3. **RunPod accounts: per-tenant or shared?** Has compliance implications.
   Defer until Phase 3 but start the conversation now.
4. **UI gateway: standalone service or part of CoreService?** Recommend
   starting as a submodule of CoreService; split out if it grows.

These are the decisions that would most benefit from a short design doc
before code starts moving.

---

## 13. What this plan leaves *alone*

It leaves working code working. CTF and MotionCor on RabbitMQ keep running
through Phase 4. The particle picker keeps running in-process. The
React app's current Socket.IO contract survives. The 27 routers are not
touched. No data migration is required — MySQL stays authoritative through
every phase.

The migration is **additive**. Every phase adds the new path alongside the
old one, proves it, and only then removes the old one. That is the whole
safety model.
