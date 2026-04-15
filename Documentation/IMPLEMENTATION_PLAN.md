# Magellon — Implementation Plan

**Status:** Revised 2026-04-14. Supersedes the Temporal-centric plan that was
partially executed — Phases 0–1 landed, Phase 2 reverted in commit `86fe9cc`.

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
5. **One event path to the UI.** Socket.IO is what the frontend consumes today;
   it is sufficient for one-plugin-one-call. Defer NATS/JetStream until
   fan-out or durability becomes a real need.
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
`../MagellonSdk`. PR 1.6 (publish to an index) deferred pending an infra
decision — folded into Phase E below.

### Phase 2 — Temporal (reverted `86fe9cc`)
Not pursued. The SDK retains `PluginBase`, progress reporter, CloudEvents
envelope, and the `Executor` Protocol — the orchestrator-agnostic contract —
so nothing re-introducing Temporal later has to restart from zero.

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

**Goal:** One event path from plugin → UI. Today Socket.IO works and is
wired; NATS is present but only used by import/domain workflows; RabbitMQ is
dead after Phase A. Fragment count should go to 1.

| PR  | Title | DoD |
|-----|-------|-----|
| C.1 | Socket.IO as the sole UI event path | All plugin-progress emits go through one helper. `JobService.emit(...)` is the single producer. No other module calls `sio.emit` directly. Contract pinned by the existing PR 0.6 tests. |
| C.2 | Decide NATS fate | Audit: what actually subscribes to NATS today? If only import workflows, either (a) move those to Socket.IO too and drop NATS, or (b) keep NATS behind one clear seam (`MagellonEventService`) and document that plugin code never touches it. |
| C.3 | JobService as the single progress seam | Plugin author writes `reporter.report(pct, msg)`; reporter fans out to Socket.IO + DB. No other fan-out paths. Existing `JobReporter` stays host-side; `ProgressReporter` Protocol in SDK. |
| C.4 | PR 0.7 — plugin-container contract test | The Phase 0 test that was deferred: boot a plugin container image in CI, POST a canned input, assert response shape. Validates the containerized-plugin path once rather than per-plugin. |
| C.5 | PR 0.8 — end-to-end smoke test | Also deferred from Phase 0: MySQL + CoreService + one plugin, submit one job, assert progress frames and result row. Runs nightly in CI. |

**Exit criterion:** `grep -r "sio.emit\|nats.publish"` returns a bounded set of
locations (ideally: one helper each). Nightly e2e smoke green.

**Rollback:** per-PR revert; C.2 is the only one that removes a dependency
(NATS), and only if the audit shows it has no live consumer.

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
via path (`-e ../MagellonSdk`). That's fine for in-tree work; it doesn't let
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
  paying customer asks for. Not before.
- **Fan-out event bus (NATS/JetStream).** Add when either (a) multi-tenant
  scale-out requires it, or (b) the import/domain workflows grow a second
  consumer. Until then Socket.IO is enough.
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
| SDK unit tests          | `MagellonSdk/tests/`                      | SDK CI                    |

**Rule:** no PR in Phase A or later merges without the tests that pin the
behaviour it touches. Reviewer rejects otherwise.

---

## Current iteration

Phase A (consolidation) starts next — A.1 and A.2 are pure deletions of dead
code with zero behaviour change, so they can land immediately and in either
order.
