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
- `TARGET_ARCHITECTURE_AND_PLAN.md` — superseded-banner now points at the new canon.
- `CoreService/docs/plugin-developer-guide.md` — new "Data Plane" section.

These are governance; they gate the review of every PR in Track A and Track B.

### First move

If starting tomorrow: **MB4.A + G.4 as independent PRs**. MB4.A unblocks
the Track A chain; G.4 is the highest-leverage user-visible improvement
at lowest cost. Each is small enough to review in half a day.
