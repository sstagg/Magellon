# Magellon — Implementation Plan

**Purpose:** Phase-by-phase, PR-by-PR execution plan for the migration
described in `TARGET_ARCHITECTURE_AND_PLAN.md`. Every PR listed here has a
concrete definition-of-done and a rollback path.

**Guiding rules:**

- **Safety net before refactor.** No production code moves until the tests
  pin the current behaviour.
- **Additive, then subtractive.** Build the new path alongside the old,
  prove it, *then* delete the old.
- **Every PR is independently reversible.** If a PR is merged and something
  breaks, `git revert` that one PR must restore green.
- **Keep PRs small.** One concern per PR. Reviewer time is the scarce
  resource.
- **"Scaffolding" is not dead code.** `services/magellon_job_manager.py`,
  `services/temporal_job_manager.py`, and `services/event_publisher.py` are
  inputs to Phase 2. Do not delete.

---

## Phase 0 — Safety net

**Goal:** Lock down every externally observable behaviour of the live
system so subsequent phases cannot silently regress it. No production
behaviour changes in this phase.

| PR    | Title                                                  | DoD                                                                                                                  |
|-------|--------------------------------------------------------|----------------------------------------------------------------------------------------------------------------------|
| 0.1   | CI baseline green                                      | Existing pytest suite passes locally and in CI. Broken tests are either fixed or explicitly `xfail`'d with an issue. |
| 0.2   | Envelope golden files                                  | Golden JSON for `TaskBase.model_dump()` at CTF and MotionCor payloads. Change-detection test compares fresh vs golden. |
| 0.3   | Queue-name characterization                            | Test pins `get_queue_name_by_task_type` output for every `TaskCategory.code` currently defined.                      |
| 0.4   | PluginRegistry discovery pin                           | Test asserts which plugin IDs auto-register (`ctf/ctffind`, `motioncor/motioncor2`, `pp/template-picker`) and their `PluginInfo`. |
| 0.5   | Plugin controller HTTP contract tests                  | TestClient-driven tests pin `/plugins/`, `/plugins/{id}/info`, `/plugins/{id}/schema/input`, `POST /plugins/{id}/jobs` response shapes. |
| 0.6   | Socket.IO emit shape tests                             | Fake Socket.IO server captures `emit_job_update` / `emit_log` frames during a synthetic plugin run. Payload shape pinned. |
| 0.7   | External-plugin contract test (CTF)                    | In CI, boot `magellon_ctf_plugin` image, publish a canned `TaskDto`, assert a canned `TaskResultDto` shape comes back. Smoke-level, not exhaustive. |
| 0.8   | End-to-end smoke test                                  | Script boots MySQL + RabbitMQ + CoreService, submits one plugin job via the in-process path, asserts progress frames and final row. |
| 0.9   | Add Temporal server to docker-compose                  | Temporal server and Temporal UI available in dev stack. No workers. No code paths use it. Verified with `curl` only. |
| 0.10  | Dead-code audit                                        | Short report (as a markdown file under `Documentation/`) listing truly unused modules with evidence; no deletions yet. |
| 0.11  | Low-risk cleanups                                      | Fix `MagellonSdk/README.md` typo. Remove obviously unused imports. No behaviour change. |

**Exit criterion:** Green CI with all new tests. Any change to the
envelope bytes-on-the-wire now fails a test.

**Rollback:** revert PRs individually; none change production behaviour.

---

## Phase 1 — Extract the SDK

**Goal:** Move the plugin contract into a standalone package so future
plugins (in-process or remote) depend on a stable, versioned SDK — not on
`CoreService/plugins/`.

| PR    | Title                                             | DoD                                                                                                        |
|-------|---------------------------------------------------|------------------------------------------------------------------------------------------------------------|
| 1.1   | SDK scaffolding                                   | `MagellonSdk/src/magellon_sdk/` has `__init__.py`, `py.typed`, pyproject.toml sets `name = magellon-sdk`, version `0.1.0`. |
| 1.2   | Move `PluginBase` into SDK                        | `magellon_sdk.base` contains `PluginBase`. `CoreService/plugins/base.py` becomes `from magellon_sdk.base import *` re-export. All tests green. |
| 1.3   | Move `ProgressReporter` into SDK                  | Same pattern for `plugins/progress.py`. `JobReporter` stays in CoreService (it depends on CoreService internals); `ProgressReporter`, `NullReporter`, `JobCancelledError` move. |
| 1.4   | CloudEvents envelope helpers                      | `magellon_sdk.envelope` exposes `Envelope[T]` (Pydantic) with `specversion`, `id`, `source`, `type`, `subject`, `time`, `dataschema`, `datacontenttype`, `data: T`. Round-trip test. |
| 1.5   | Executor interface (stub only)                    | `magellon_sdk.executor.base.Executor` protocol. No implementations yet. |
| 1.6   | SDK publish to private index (or path-based dev)  | CoreService depends on `magellon-sdk==0.1.0`. Plugin authors can `pip install magellon-sdk`. |
| 1.7   | Plugin CLI skeleton                               | `magellon-plugin --help` works. Subcommands stubbed (`new`, `test`, `package`, `publish`) returning "not implemented". |

**Exit criterion:** `pip install magellon-sdk` gives a usable `PluginBase`.
CoreService re-exports preserve all existing import paths. All Phase 0
tests still green.

**Rollback:** revert 1.6 to restore in-repo imports; earlier PRs are pure
movement.

---

## Phase 2 — First vertical slice on Temporal (CTF)

**Goal:** Prove end-to-end that one plugin can run via Temporal + NATS
while the rest of the system runs on the legacy path. Flagged, reversible.

| PR    | Title                                               | DoD                                                                                                         |
|-------|-----------------------------------------------------|-------------------------------------------------------------------------------------------------------------|
| 2.1   | Temporal worker scaffold in SDK                     | `magellon_sdk.worker.run_worker(plugin)` boots a `temporalio.worker.Worker` for one plugin.                 |
| 2.2   | CTF plugin as Temporal activity                     | CTF plugin container also runs `magellon-plugin worker --plugin ctf/ctffind`. Activity wraps `plugin.run`. |
| 2.3   | `CtfWorkflow`                                       | Single-activity workflow. `workflow.execute_activity("ctf.run", ..., start_to_close_timeout=...)`.          |
| 2.4   | `CTF_VIA_TEMPORAL` feature flag                     | Env var (default off). When on, `JobService` starts `CtfWorkflow`; when off, RabbitMQ dispatch unchanged.   |
| 2.5   | NATS→Socket.IO UI gateway                           | Subscribes to `magellon.step.progress`, forwards to Socket.IO per-`sid`. Runs inside CoreService initially. |
| 2.6   | Temporal activity → NATS progress wiring            | Activity calls `plugin.run(reporter=TemporalReporter(...))` which emits on NATS and heartbeats Temporal.    |
| 2.7   | Staging validation                                  | One full Leginon import in staging runs CTF via Temporal and everything else via legacy. Progress frames render. Rollback = flip the flag. |

**Exit criterion:** Flag on in staging; CTF jobs flow through Temporal.
All Phase 0 golden tests still green with the flag off. With the flag on,
new tests assert Temporal workflow was started and NATS events were seen.

**Rollback:** flip `CTF_VIA_TEMPORAL=off`.

---

## Phase 3 — Executor abstraction

**Goal:** Decouple "what the plugin does" from "where it runs." This is
the phase that solves the customer GPU+Docker install burden.

| PR    | Title                                          | DoD                                                                                                       |
|-------|------------------------------------------------|-----------------------------------------------------------------------------------------------------------|
| 3.1   | `LocalProcess` executor                        | Default. Runs `plugin.run` in the worker process. No behaviour change for existing Phase 2 slice.         |
| 3.2   | `LocalDocker` executor                         | Runs plugin in a container via `docker-py`. Streams stdout into progress logs.                            |
| 3.3   | `RunPod` executor                              | `POST /v2/{endpoint}/run`; webhook listener in CoreService turns RunPod events into progress events.      |
| 3.4   | Per-plugin `executor:` config                  | `PluginInfo` grows an `executor` field; default `localprocess`. Activity reads it at runtime.             |
| 3.5   | `Kubernetes` executor                          | Creates a one-shot `Job`; streams logs. Behind a separate opt-in (not wired to any plugin by default).    |
| 3.6   | RunPod customer doc                            | `Documentation/runpod_quickstart.md`: API key setup, which plugins support it, sample `executor: runpod` config. |

**Exit criterion:** One customer, in a supported plugin (recommend CTF
first, then MotionCor), flips to `executor: runpod` and runs successfully.

**Rollback:** change config back to `localprocess`.

---

## Phase 4 — Migrate remaining plugins

**Goal:** Bring MotionCor, the result processor, and the particle picker
onto the same (Temporal + NATS + Executor) path.

| PR    | Title                                                  | DoD                                                                                                    |
|-------|--------------------------------------------------------|--------------------------------------------------------------------------------------------------------|
| 4.1   | MotionCor on Temporal                                  | `motioncor/motioncor2` plugin becomes a Temporal activity; `MotionCorWorkflow` defined. Flag-gated.    |
| 4.2   | Result processor as a workflow step                    | Result handling becomes a Temporal activity downstream of CTF and MotionCor. `*_out_tasks_queue` bypass. |
| 4.3   | Particle picker workflow wrapper                       | `pp/template-picker` already runs in-process; wrap it in a workflow so UI/event path is uniform.       |
| 4.4   | All plugin flags on in staging                         | Every plugin goes through Temporal in staging for one week. No unexplained failures.                  |
| 4.5   | All plugin flags on in prod                            | Staged rollout: 10% → 50% → 100%.                                                                      |

**Exit criterion:** Every plugin can run through Temporal in prod.
RabbitMQ dispatch queues are still there but no longer dispatched to.

**Rollback:** per-plugin flag off.

---

## Phase 5 — Retire legacy

**Goal:** Delete the old paths. Only possible when Phase 4 has been
soaking in prod long enough that nobody trusts the legacy path anymore.

| PR    | Title                                                            | DoD                                                                                       |
|-------|------------------------------------------------------------------|-------------------------------------------------------------------------------------------|
| 5.1   | Migrate `controllers/import_controller.py` off Dragonfly JobManager | Import controller uses the unified `JobService`. All import tests still green.           |
| 5.2   | Delete `services/job_manager.py` (Dragonfly)                     | File deleted. Dragonfly stays in compose (cache use) but is no longer a job store.        |
| 5.3   | Delete RabbitMQ dispatch helpers                                 | `core/helper.py` `dispatch_ctf_task`, `dispatch_motioncor_task`, `get_queue_name_by_task_type`, `push_task_to_task_queue`, `publish_message_to_queue` removed. `core/rabbitmq_client.py` deleted. |
| 5.4   | Delete the three plugin-repo `core/` duplicates                  | Plugin repos depend on `magellon-sdk` only. Container entrypoint is `magellon-plugin worker`. |
| 5.5   | Drop RabbitMQ from `docker-compose.yml`                          | RabbitMQ service removed. Any lingering references fail loudly in CI.                     |
| 5.6   | Collapse job-manager scaffolding into `JobService`               | `services/magellon_job_manager.py` and `services/temporal_job_manager.py` merge into the one `JobService`. |
| 5.7   | Delete on-disk message audit                                     | Remove `/magellon/messages/<queue>/messages.json` writes. JetStream retention covers audit. |

**Exit criterion:** `grep -ri rabbitmq` returns only historical docs. One
`JobService`. One plugin SDK. One event path.

**Rollback:** per PR, `git revert`.

---

## Phase 6 (optional) — Plugin Hub

**Goal:** Stand up the plugin ecosystem: publish, discover, install. Can
start in parallel with Phases 2–4; it has no dependency on the Temporal
migration.

| PR    | Title                               | DoD                                                                         |
|-------|-------------------------------------|-----------------------------------------------------------------------------|
| 6.1   | Hub API skeleton                    | FastAPI app. Endpoints: list, search, get, upload. MinIO-backed storage.     |
| 6.2   | `magellon-plugin publish` CLI       | Builds a wheel from a plugin project, uploads via Hub API, writes metadata. |
| 6.3   | Hub Web (minimal)                   | Read-only browse/search. Plugin cards show `PluginInfo`, schemas, versions. |
| 6.4   | Hub install flow in CoreService     | Admin endpoint fetches plugin wheel from hub and installs into Python env; calls `registry.refresh()`. |
| 6.5   | Auth for authors                    | Author accounts + API tokens for publishing.                                |

---

## Cross-cutting — test discipline

A test lives at the layer that enforces the contract it pins:

| Layer                   | Lives in                       | Runs when                      |
|-------------------------|-------------------------------|--------------------------------|
| Plugin unit test        | Plugin repo                    | Plugin CI                      |
| Envelope golden         | `CoreService/tests/characterization/` | CoreService CI           |
| Queue-name / discovery  | Same                           | Same                           |
| HTTP contract (plugins) | `CoreService/tests/contracts/` | CoreService CI                 |
| Workflow unit test      | `CoreService/tests/workflows/` | CoreService CI (uses `temporalio.testing`) |
| E2E smoke               | `CoreService/tests/e2e/`       | CI nightly + pre-release       |
| External plugin contract| `plugins/<plugin>/tests/contract/` | Plugin CI                 |

**Rule:** no PR in Phase 2+ merges without a test. Reviewer rejects
otherwise.

---

## Current iteration (starts now)

We are beginning **Phase 0**, starting with **PR 0.1 (CI baseline)** and
**PR 0.2 (envelope golden files)**. Everything else waits on the safety
net being green.
