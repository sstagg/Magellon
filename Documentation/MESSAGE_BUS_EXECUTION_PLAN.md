# Magellon — MessageBus Execution Plan

**Status:** Proposal (2026-04-16). Companion to `MESSAGE_BUS_SPEC_AND_PLAN.md` v2.1.
**Scope:** How we actually ship MB0 → MB6. The spec owns **what** and **why**; this doc owns **how** and **in what order**.
**Not in scope:** MB7 (second binder). Separate decision after MB6 lands.

---

## 1. How to read this doc

Each phase from the spec breaks into **one or more PRs**. Every PR:

- has a single-sentence goal,
- touches a bounded list of files,
- has explicit acceptance criteria (tests that go from red/skipped → green, or behavior that stays identical),
- has a rollback plan (revert-safe merge, feature flag, or documented ops procedure).

PRs are sized for reviewability: aim < 500 changed lines, hard ceiling 1000. If a PR grows past that, split.

---

## 2. Phase dependency graph

```
MB0 ── MB1 ── MB2 ──┬── MB3 ── MB4 ── MB5 ── MB6
                    │
                    └── (MB5 can start in parallel with MB4
                         because events and tasks are independent channels)
```

**Sequential backbone:** MB0 → MB1 → MB2 → MB3 → (MB4 ∥ MB5) → MB6.

**Parallelizable slots inside phases:**

- MB4.2 / MB4.3 / MB4.4 — per-plugin migrations (CTF, MotionCor, result processor) — independent PRs, merge order chosen for risk.
- MB5.1 / MB5.2 / MB5.3 — discovery, config, step events — independent call sites, independent PRs.

**Hard gates (cannot skip):**

- End of MB2: RMQ binder integration suite passes against a real RMQ container.
- End of MB3: audit log files continue to appear at same paths with byte-level identical content to a pre-MB3 baseline.
- Before MB6.4: DLQ migration runbook dry-run on staging replica, ops sign-off.

---

## 3. PR breakdown

### MB0 — Pre-extraction

| PR | Goal | Files | Acceptance | Rollback |
|---|---|---|---|---|
| **MB0.1** | Split `runner.py` into `runner/plugin_runner.py` + `runner/lifecycle.py` | `magellon_sdk/src/magellon_sdk/runner.py` → `runner/__init__.py`, `runner/plugin_runner.py`, `runner/lifecycle.py`; update imports in `plugins/*/main.py` | All existing plugin smoke tests + `test_runner.py` green. No external import changes: `from magellon_sdk.runner import PluginBrokerRunner` still works. | Single-PR revert. No production behavior change. |

### MB1 — Bus Protocol + routes (code lands, nothing uses it)

| PR | Goal | Files | Acceptance |
|---|---|---|---|
| **MB1.1** | Interfaces and policies | `bus/__init__.py`, `bus/interfaces.py`, `bus/policy.py` | Protocol surface compiles; `mypy` / `ruff` clean; no production caller imports it yet. |
| **MB1.2** | Route value objects (delegate to `CategoryContract`) | `bus/routes/task_route.py`, `event_route.py`, `patterns.py` | Unit tests: `TaskRoute.for_category(CTF).subject == "magellon.tasks.ctf"`; `TaskRoute.named("x").subject == "x"`; subject strings match what `CategoryContract` produces today. |
| **MB1.3** | Mock binder + bus implementation + dual-form consumer test | `bus/binders/mock.py`, `bus/_facade.py`, `tests/bus/test_mock_binder.py`, `tests/bus/test_consumer_forms.py` | Round-trip: `bus.tasks.send(route, env)` → registered handler gets called. Both `@bus.tasks.consumer(route)` and `bus.tasks.consumer(route, fn)` register successfully. `get_bus.override(mock)` works in fixtures. |

Rollback: nothing production imports the bus; any PR is revert-safe.

### MB2 — RMQ binder implementation

| PR | Goal | Files | Acceptance |
|---|---|---|---|
| **MB2.1** | Connection + topology | `bus/binders/rmq/connection.py`, `topology.py` | Long-lived connection test: `binder.start()` opens one connection; reconnect under forced close. Topology declares exchanges (`magellon.plugins`, `magellon.events`) and DLQ-wired queues on `start()`. |
| **MB2.2** | Work queue: publish + consume | `bus/binders/rmq/publish.py`, `consume.py` | Integration test against a real RMQ container: `binder.publish_task(route, env)` → `binder.consume_tasks(route, handler)` round-trip; redelivery counter increments on nack-requeue (header `x-magellon-redelivery`); DLQ routing verified with poison message. |
| **MB2.3** | Topic pub-sub: publish + subscribe | `bus/binders/rmq/subscribe.py` | Integration test: publish to `StepEventRoute(job=42, step="ctf")`, subscriber bound on `StepEventRoute.all()` receives it. Pattern glob → RMQ `#` translation verified. |
| **MB2.4** | Audit log as binder feature | `bus/binders/rmq/audit.py`, extension of `publish.py` | `AuditLogConfig(enabled=True, root="/tmp/test_audit", routes=[ctf_route])` — publishing to ctf route writes `/tmp/test_audit/magellon.tasks.ctf/messages.json` with the envelope JSON. **Byte-level diff** against a pre-MB3 captured baseline from `helper.py::publish_message_to_queue`. |

Rollback: binder isn't wired into production; any PR is revert-safe.

### MB3 — Migrate producers (smallest blast radius)

| PR | Goal | Files | Acceptance |
|---|---|---|---|
| **MB3.1** | `dispatcher_registry.py` uses the bus | `CoreService/core/dispatcher_registry.py`, `CoreService/main.py` (startup: `get_bus().start()`) | Existing integration tests (`test_e2e_seam.py`) green. `RabbitmqTaskDispatcher.dispatch` delegated to `bus.tasks.send` internally — external API unchanged. |
| **MB3.2** | Collapse `publish_message_to_queue` + `helper.py::push_task_to_task_queue` | `CoreService/core/helper.py`, delete `magellon_sdk/dispatcher.py::RabbitmqTaskDispatcher`, delete `magellon_sdk/messaging.py::publish_message_to_queue` | Audit log file parity check: capture a day's messages.json on baseline, replay the same dispatches post-MB3, diff is byte-identical. `TaskDispatcher` Protocol survives (in-process dispatch path). |

Rollback: both PRs are self-contained. MB3.2 is the riskier of the two — if audit parity fails, revert and investigate before re-attempting.

### MB4 — Migrate consumers + relocate

| PR | Goal | Files | Acceptance |
|---|---|---|---|
| **MB4.1** | `PluginBrokerRunner` internally uses `bus.tasks.consumer` | `magellon_sdk/runner/plugin_runner.py` | Existing `PluginBrokerRunner` constructor signature unchanged. Runner's consume loop replaced by `bus.tasks.consumer(route, self._handle_task)`; ack/nack/DLQ goes through binder. All plugin smoke tests green without any plugin code change. |
| **MB4.2** | CTF plugin cutover | `plugins/magellon_ctf_plugin/main.py`, delete `plugins/magellon_ctf_plugin/core/rabbitmq_consumer_engine.py` and `rabbitmq_client.py` | CTF smoke test green against docker-compose. Step events from CTF still reach UI. |
| **MB4.3** | MotionCor plugin cutover | same pattern in `plugins/magellon_motioncor_plugin/` | MotionCor smoke test green. GPU run not required for review; unit + mock integration is enough. |
| **MB4.4** | Result processor cutover | same pattern in `plugins/magellon_result_processor/` | `test_e2e_seam.py` + `test_result_consumer.py` green. |
| **MB4.5** | Relocate `result_consumer.py` to SDK | move `CoreService/core/result_consumer.py` → `magellon_sdk/bus/binders/rmq/result_consumer.py`; CoreService imports via `from magellon_sdk.bus.services import ...` | CoreService `main.py` now registers the result consumer via `bus.tasks.consumer(TaskResultRoute.all(), handler)`. No logic change, just location. |

Rollback: per-plugin rollback is independent — revert MB4.3 without touching CTF. MB4.1 is behind the existing runner API so revert is single-file.

### MB5 — Migrate topic pub-sub + relocate

| PR | Goal | Files | Acceptance |
|---|---|---|---|
| **MB5.1** | Discovery uses `bus.events` | `magellon_sdk/discovery.py` → calls `bus.events.publish` | Heartbeat smoke: a plugin announces and the liveness registry (still in CoreService) sees it. Test `test_discovery.py` green. |
| **MB5.2** | Config push/subscribe uses `bus.events` | `magellon_sdk/config_broker.py` | Dynamic-config round-trip test green: `ConfigPublisher.push` → `ConfigSubscriber.take_pending` via bus. |
| **MB5.3** | Step events collapse into binder | `magellon_sdk/transport/rabbitmq_events.py` → absorbed into `bus/binders/rmq/`; external publisher API redirects to `bus.events.publish(StepEventRoute(...), env)` | `test_transport_rabbitmq_events.py` rewritten to test via bus; step events still reach UI. |
| **MB5.4** | Relocate `step_event_forwarder` + `liveness_registry` | move from `CoreService/core/` → `magellon_sdk/bus/services/`; CoreService keeps thin wrappers | Forwarder's Socket.IO callback still fires; liveness registry HTTP endpoint returns same shape. Imperative `bus.events.subscribe(...)` registration with bound method. |
| **MB5.5** | Relocate `plugin_config_publisher` | `CoreService/services/plugin_config_publisher.py` → `magellon_sdk/bus/services/config_publisher.py`; CoreService HTTP controller unchanged | Admin config-push UI flow works end-to-end. |

MB5.1 / MB5.2 / MB5.3 are parallelizable — different subsystems. MB5.4 / MB5.5 require MB5.1 / MB5.2 / MB5.3 respectively.

Rollback: per-subsystem; discovery rollback doesn't affect step events.

### MB6 — Operator primitives + lint + DLQ migration

| PR | Goal | Files | Acceptance |
|---|---|---|---|
| **MB6.1** | Cancellation → bus | `CoreService/services/cancellation_service.py` → calls `bus.tasks.purge` via `magellon_sdk/bus/operator/cancellation.py` | `POST /cancellation/queues/purge` returns same shape; integration test green. |
| **MB6.2** | Collapse `transport/rabbitmq.py` into binder | `magellon_sdk/transport/rabbitmq.py` → private modules under `bus/binders/rmq/` | No external module imports `RabbitmqClient` anymore. Existing binder tests green (they use the same code, just relocated). |
| **MB6.3** | Lint rule | `pyproject.toml` ruff config OR `scripts/lint_no_pika.py` in CI | `rg '^import pika\|^from pika' -g '!magellon_sdk/bus/binders/rmq/**'` returns zero. CI job enforces on every PR. |
| **MB6.4** | DLQ topology migration — script + staging | `scripts/migrate_dlq_topology.py`, `Documentation/DLQ_MIGRATION_RUNBOOK.md` (extracts §9.6.1 into a standalone ops doc) | `--dry-run` on staging replica prints expected operations per queue; operator executes the real run in a scheduled window; post-verify smoke test confirms DLQ routing on CTF and MotionCor. |

**MB6.4 is the only PR in the whole plan that cannot be rolled back by `git revert`.** Rollback = re-run the migration script in reverse (documented in runbook §9.6.1). Merge MB6.4 **after** MB6.1–MB6.3 are in production for ≥ 1 week.

---

## 4. Risk checkpoints (go/no-go gates)

| After | Checkpoint | Go signal | No-go action |
|---|---|---|---|
| MB1 | Protocol review | Mock binder round-trips envelopes; dual-form consumer works; `get_bus.override()` swaps in test fixtures | Revisit spec §4; a design flaw here is cheap. Do not proceed to MB2. |
| MB2 | Integration parity | Binder integration suite green against real RMQ; audit log byte-diff matches captured baseline | Fix binder before any production call site migrates. |
| MB3 | Audit log parity | One day's `messages.json` byte-identical to pre-MB3 capture | Revert MB3; investigate audit drift; likely a binder bug from MB2 surfacing late. |
| MB4 per plugin | Plugin smoke green | CTF / MotionCor / result-processor docker-compose smoke test passes | Revert that plugin's PR; keep the others. Plugin remains on pre-MB4 code. |
| MB5 per subsystem | Subsystem smoke green | Discovery/config/step-event smoke test passes | Revert that subsystem's PR. |
| Before MB6.4 | DLQ staging dry-run | Runbook dry-run on staging replica completes without error; ops signs off | Do not schedule production window. Iterate on runbook. |

---

## 5. Effort estimate

Rough person-day sizing for a focused single-engineer run. Parallel hands reduce wall-clock but not total effort.

| Phase | Person-days | Notes |
|---|---|---|
| MB0 | 0.5–1 | One file split; tests already cover the shape. |
| MB1 | 2–3 | Bulk is tests. Mock binder is small. |
| MB2 | 4–6 | The heavy phase. Binder is the one piece of real new code. |
| MB3 | 1–2 | Small; audit parity check is the time sink. |
| MB4 | 4–6 | Three plugin cutovers + relocation. Can parallelize to 2–3 wall-clock days if needed. |
| MB5 | 3–4 | Five subsystems, each small. Can parallelize. |
| MB6 | 3–5 | 2 days code + 1–3 days DLQ ops (dry-run, window scheduling, execution). |
| **Total** | **18–27** | ≈ 4–6 focused weeks single-handed. |

---

## 6. Definition of Done (end of MB6)

- `rg '^import pika\|^from pika' -g '!magellon_sdk/bus/binders/rmq/**'` returns zero.
- `rg 'RabbitmqClient' -g '!magellon_sdk/bus/binders/rmq/**' -g '!**/tests/**'` returns zero.
- All 16 call sites listed in spec §1.2 use `bus.tasks.*` or `bus.events.*`.
- CoreService contains no RMQ code beyond (a) calling the bus and (b) thin FastAPI wrappers around relocated SDK services.
- Every production queue is DLQ-wired (verified via `rabbitmqctl list_queues arguments` snapshot).
- CI lint rule blocks any new `pika` import outside the binder.
- `MESSAGE_BUS_SPEC_AND_PLAN.md` v2.1 remains accurate (or is updated once during the run if a spec edit is forced).

---

## 7. What to do first

If starting tomorrow: MB0.1. One PR, half a day, no production risk. It both proves the runner is a composition (not a fused loop) and kicks off the branching structure — every subsequent PR is an increment on a shape that's already been reviewed once.

If the spec hasn't been formally reviewed yet: do that first. The three open questions at the end of the spec (runner name, audit default, MB0 standalone) get answered, and then MB0.1 lands unblocked.

---

## 8. What we are NOT doing in this plan

- **MB7 / second binder (NATS, SQS).** Explicitly deferred. Reassess after MB6 ships and the bus has a quarter of production use. If the abstraction proves out, NATS is a mechanical port using the existing `magellon_sdk/transport/nats.py`. If it doesn't, we've still won on call-site consolidation.
- **Fixing the in-process vs external plugin split.** Orthogonal. Both halves will call `bus.tasks.send` once MB3 is in.
- **Workflow engine reintroduction.** Temporal was reverted for a reason; see `feedback_yagni_orchestration`.
- **Envelope format changes.** CloudEvents 1.0 stays.
- **OpenTelemetry rollout.** Trace context rides the envelope; span instrumentation lands whenever, not on a bus phase.
