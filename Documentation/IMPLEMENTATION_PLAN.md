# Magellon — Implementation Plan

**Status:** Revised 2026-04-14; **partially superseded 2026-04-15** by the
plugin-platform refactor (P1–P9, see §"Plugin platform refactor" below).
Original revision superseded the Temporal-centric plan — Phases 0–1 landed,
Phase 2 reverted in commit `86fe9cc`.

> **⚠ Direction change vs. this plan as written.** Guiding rule #5 said
> "RabbitMQ goes" and Phase A.4/A.5 described retiring the RMQ dispatch
> helpers and dropping RMQ from compose. **That direction was reversed.**
> RabbitMQ is now load-bearing for *more* than tasks: discovery (P6),
> dynamic config (P7), and cancellation (P9) all ride a `magellon.plugins`
> topic exchange. Consul was deleted instead (P8). The remainder of this
> plan still applies for Phases B / D / E / F.
>
> **Governing docs (2026-04-21).** `ARCHITECTURE_PRINCIPLES.md` is the
> canonical rule-set every PR in this plan is reviewed against.
> `DATA_PLANE.md` closes the "artifact transport" open question by
> committing to a shared POSIX filesystem; object-storage-only
> deployments are an explicit non-goal. The currently active work is
> under "Active tracks — 2026-04-21" below.

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
| A.6 | Finalize the Phase 0 dead-code audit sweep | Walk `Documentation/PHASE_0_DEAD_CODE_AUDIT.md`, execute the "SAFE TO DELETE" rows that are still safe, re-verify each before removal. |

**Exit criterion:** `grep -ri "temporal\|rabbitmq"` returns hits only in history,
docs, or settings-file examples. One `JobService`. One dispatch path.

**Rollback:** per-PR `git revert`.

---

## Phase B — Plugin execution taxonomy

**Goal:** Make the "plugins without containers" story first-class and
documented. Today it is implicit — `template_picker` is in-process; CTF and
MotionCor run in dedicated containers — but the developer guide doesn't
spell out the choice. New plugin authors should pick the right mode on day
one, not after their first refactor.

| PR  | Title | DoD |
|-----|-------|-----|
| B.1 | Taxonomy in the developer guide | `plugin-developer-guide.md` gets a new top section: **Deployment modes**. Three rows — in-process (default), subprocess (local binary wrapper), containerized (separate image + HTTP). Decision matrix: "when to pick each". |
| B.2 | FFT as the canonical simple-plugin exemplar | The empty `plugins/fft/` stub becomes a complete working plugin: `algorithm.py` (numpy FFT), `service.py` (PluginBase), `models.py` (Pydantic I/O with full `ui_*` metadata), `controller.py` route, full test suite. Target under 200 LOC total. This is the template for FFT-grade plugins. |
| B.3 | Audit current CTF / MotionCor deployment | One-page report: are they truly containerized (HTTP-over-network), or packaged containers that call in-process? What would it take to run CTF in-process on a host that has `ctffind4` installed? Informs B.4. |
| B.4 | `SubprocessExecutor` in the SDK (*if earned*) | Only land if B.3 shows it is worthwhile. Wraps a local binary from a PluginBase — same plugin contract, different runtime. Implements the Executor Protocol stub. |
| B.5 | `HttpContainerExecutor` doc-only (*if earned*) | Document the existing CTF/MotionCor container pattern as a third deployment mode. Probably no new code; just formalize the pattern they already follow. |

**Exit criterion:** A new plugin author reading the guide can answer "do I need
a container?" in under 2 minutes. FFT is merged and shipping.

**Rollback:** PR B.2 is additive (new plugin); others are docs or optional
extension points.

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

Follows `MESSAGE_BUS_EXECUTION_PLAN.md` with this PR ordering. PR IDs
use the `MB` prefix to match the execution plan and to avoid colliding
with Phase-A PR numbering.

| PR   | Title | DoD |
|------|-------|-----|
| MB4.A | Delete plugin RMQ shims | `plugins/magellon_ctf_plugin/core/rabbitmq_client.py`, `plugins/magellon_motioncor_plugin/core/rabbitmq_client.py`, `plugins/magellon_result_processor/core/rabbitmq_client.py` removed. Each plugin's `main.py` unchanged externally. Per-plugin smoke test green against docker-compose. |
| MB4.B | Relocate `result_consumer.py` to SDK | `CoreService/core/result_consumer.py` → `magellon_sdk/bus/binders/rmq/result_consumer.py`. CoreService imports via `from magellon_sdk.bus.services import ...`. `tests/integration/test_e2e_seam.py` green. |
| MB4.C | Stop the result-processor double-consume | Blank `OUT_QUEUES: []` in `plugins/magellon_result_processor/configs/settings_dev.yml` and `settings_prod.yml`. Plugin container then subscribes to nothing and logs `result_processor: OUT_QUEUES empty — staying dormant.` CoreService's in-process consumer becomes the sole writer. Lower-churn alternative to removing the container from `docker-compose.yml`; that can follow once the plugin is confirmed unused for one release cycle. Surfaced in `CURRENT_ARCHITECTURE.md` §8 #19. |
| MB5.1 | Discovery uses `bus.events` | `magellon_sdk/discovery.py::DiscoveryPublisher` routed through `bus.events.publish(AnnounceRoute(...), env)` and `HeartbeatRoute(...)`. Direct RMQ calls deleted. Discovery smoke test green. |
| MB5.2 | Config broker uses `bus.events` | `magellon_sdk/config_broker.py` publishes and subscribes via `bus.events`. Dynamic-config round-trip test green. |
| MB5.3 | Step events absorbed into RMQ binder | `magellon_sdk/transport/rabbitmq_events.py::RabbitmqEventPublisher` collapsed; `StepEventPublisher` redirects to `bus.events.publish(StepEventRoute(...), env)`. `test_transport_rabbitmq_events.py` rewritten against the bus. |
| MB5.4 | Relocate forwarders to SDK | `CoreService/core/plugin_liveness_registry.py` → `magellon_sdk/bus/services/liveness_registry.py`; `CoreService/core/rmq_step_event_forwarder.py` → `magellon_sdk/bus/services/step_event_forwarder.py`; `CoreService/services/plugin_config_publisher.py` → `magellon_sdk/bus/services/config_publisher.py`. CoreService keeps thin FastAPI wrappers. All tests green. |
| MB6.1 | Cancellation uses `bus.tasks.purge` | `CoreService/services/cancellation_service.py::purge_queue` delegates to `magellon_sdk/bus/operator/cancellation.py`. `POST /cancellation/queues/purge` returns identical shape. |
| MB6.2 | Collapse `transport/rabbitmq.py` into the binder | `magellon_sdk/transport/rabbitmq.py` contents moved to private modules under `bus/binders/rmq/`. No external module imports `RabbitmqClient`. |
| MB6.3 | Lint rule | ruff config (or `scripts/lint_no_pika.py` in CI) rejects `pika` / `aio_pika` imports outside `magellon_sdk/bus/binders/rmq/**`. Same rule covers `RabbitmqClient` imports. Per `ARCHITECTURE_PRINCIPLES.md` §3. |
| MB6.4 | DLQ topology migration | `scripts/migrate_dlq_topology.py` runs the §9.6.1 runbook. Scheduled after MB6.3 has soaked ≥ 1 week in production. Post-verify: deliberate-poison message routes to DLQ on CTF + MotionCor queues. |

**Parallelism.** MB5.1 / MB5.2 / MB5.3 touch independent subsystems — merge in any order. MB5.4 depends on MB5.1 / MB5.2 / MB5.3 completion. MB6.2 depends on MB4.A through MB6.1.

**Exit gate.** `rg '^import pika|^from pika' -g '!magellon_sdk/bus/binders/rmq/**'` returns zero, CI-enforced by MB6.3.

**Rollback.** Per-PR `git revert` except MB6.4 (destructive), which has its own runbook rollback in `MESSAGE_BUS_SPEC_AND_PLAN.md` §9.6.1.

### Track B — Close product-visible gaps

**Goal.** Address four product gaps surfaced in the 2026-04-21
architect's review: cooperative cancel for external plugins (R4),
missing plugin-container contract tests (R5), fragmented config
surface (R7), synchronous import handler (R8). Independent of Track A;
each PR can be picked up individually.

PR IDs use the `G` prefix (Gap closure) to avoid colliding with
Phase-B PR numbering.

| PR  | Title | DoD |
|-----|-------|-----|
| G.1 | Cooperative cancel for external plugins | New event `magellon.plugins.cancel.<job_id>` published on operator-initiated cancel. `PluginBrokerRunner` subscribes and sets a flag; plugin checks it at the next `reporter.report(...)` and raises `JobCancelledError` — same contract in-process plugins already honour. Integration test: mid-flight cancel on CTF plugin aborts cleanly within one progress tick. |
| G.2 | Contract test per plugin container | `pytest` fixture in `CoreService/tests/contracts/` boots each plugin image via docker-compose, publishes a canned envelope through the bus, asserts reply shape + provenance stamping. Lands one plugin per PR: CTF first, MotionCor second, FFT third. Closes the gap called out in `CURRENT_ARCHITECTURE.md` §9. |
| G.3 | Unified `PluginConfigResolver` | New SDK class layers YAML → env vars → bus-pushed dynamic config with documented precedence. Replaces the current four-way split (static `settings_dev.yml`, env vars like `MAGELLON_STEP_EVENTS_ENABLED`, `magellon.plugins.config.*` topic, hardcoded `CategoryContract` defaults). Plugins call `resolver.get(key)`; resolution order is one function with a docstring. |
| G.4 | Background the import handler | `controllers/import_controller.py:68` returns `job_id` immediately; `MagellonImporter.process()` runs in FastAPI `BackgroundTasks` (or a dedicated threadpool if CPU-bound work is spotted). Progress already flows over Socket.IO. Smoke test: 1000-image synthetic session completes without tying up an HTTP worker. |

**Ordering.** G.4 is the cheapest (half a day) and the most immediately user-visible — recommend as the first Track B PR. G.1 uses the bus via Track A's MB5.1 path; it can land earlier by targeting the RMQ binder directly and being retargeted trivially.

**Rollback.** Per-PR `git revert`; none of these touch the bus abstraction boundary.

### Cross-track: documentation (E)

Landed 2026-04-21:

- `ARCHITECTURE_PRINCIPLES.md` (new) — canonical rule-set.
- `DATA_PLANE.md` (new) — shared-filesystem decision + deployment matrix.
- `CURRENT_ARCHITECTURE.md` §4.1, §8 #12, §11 — corrected and reframed.
- `TARGET_ARCHITECTURE_AND_PLAN.md` — superseded-banner now points at the new canon.
- `CoreService/docs/plugin-developer-guide.md` — new "Data Plane" section.

These are governance; they gate the review of every PR in Track A and Track B.

### First move

If starting tomorrow: **MB4.A + G.4 as independent PRs**. MB4.A unblocks
the Track A chain; G.4 is the highest-leverage user-visible improvement
at lowest cost. Each is small enough to review in half a day.
