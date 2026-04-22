# Magellon — MessageBus Specification and Phased Migration Plan (v2.1)

**Status:** Proposal, v2.1 (2026-04-16). Incorporates external review of v2.
**Supersedes:** v1 and v2 (same filename). Earlier revisions preserved in git history.
**Audience:** Platform maintainers, plugin authors, reviewers.
**Companion docs:** `CURRENT_ARCHITECTURE.md` §4/§6/§8, `MESSAGES_AND_EVENTS.md`, `IMPLEMENTATION_PLAN.md`.

---

## 0. What changed

**From v1 → v2:** introduced the four-layer architecture with an explicit Binder SPI (Spring Cloud Stream pattern), tied routes to `CategoryContract` instead of duplicating, kept `PluginBrokerRunner` as composition, and preserved producer-side audit logging.

**From v2 → v2.1 (this revision):** resolves review feedback.

1. **Factory-only bus accessor.** `MessageBus.default()` import-time singleton removed; `get_bus()` is the single entrypoint. Enables test-time injection before decorator registration runs.
2. **Audit is binder config, not middleware.** v2 introduced `@audit_publish` as a hook on `bus.tasks.send`, which contradicted §4.5's "no middleware chains" rule. Audit moves into the RMQ binder as a declarative `AuditLogConfig(...)` setting.
3. **MB6 DLQ topology migration gets a proper runbook.** v2 said "delete-and-redeclare with DLQ args (idempotent, safe on empty queues)" in one line. This is the single highest-risk step in the plan — RabbitMQ returns PRECONDITION_FAILED (code 406) when you try to redeclare with different `x-*` args, and `queue_delete` drops any in-flight messages. §9.6.1 now carries the drain / snapshot / delete / redeclare / rebind runbook.
4. Method count corrected (five, not seven). OpenTelemetry descoped from MB5 to a one-liner. MB0 self-timeboxing dropped. File count in §1.2 pinned via `grep`.

**Consumer API addition (from user feedback):** `bus.tasks.consumer` and `bus.events.subscribe` support **both** decorator and imperative registration — one underlying registration, two ergonomic entrypoints. The decorator form suits module-level plain functions; the imperative form is required for class-based services (bound methods) like `StepEventForwarder` and `LivenessRegistry`.

---

## 1. Context — what's actually in the code today

P1–P9 (2026-04-15) consolidated the broker-based plugin platform but stopped short of abstracting the broker itself. RabbitMQ (`pika`) or `RabbitmqClient` leaks into **16 production files** (non-test, non-sandbox) across CoreService, magellon-sdk, and every external plugin.

### 1.1 Two structurally different usage shapes

Any abstraction has to respect this split — folding them into one API leaks either durability or fanout semantics.

| Shape | Used for | Required primitives |
|---|---|---|
| **Work queue** (commands) | Task dispatch, result fan-in | Durable queue, point-to-point, manual ack/nack, DLQ, queue purge |
| **Event topic** (pub-sub) | Discovery, heartbeat, config broadcast, step events | Topic exchange, routing-key patterns, N subscribers, fire-and-forget |

Matches **Dapr / CloudEvents** ("commands go on queues, events go on pub-sub") and **Cosmic Python**'s command-bus / event-bus separation.

### 1.2 Current leaks (verified file:line, 2026-04-16)

**Work-queue producers:**
- `magellon-sdk/src/magellon_sdk/dispatcher.py:67` — `RabbitmqTaskDispatcher`
- `magellon-sdk/src/magellon_sdk/messaging.py:71` — `publish_message_to_queue`
- `magellon-sdk/src/magellon_sdk/runner.py:65` — `PluginBrokerRunner` (publishes results)
- `CoreService/core/dispatcher_registry.py:22` — three RMQ dispatchers

**Work-queue consumers:**
- `plugins/magellon_ctf_plugin/core/rabbitmq_consumer_engine.py`
- `plugins/magellon_motioncor_plugin/core/rabbitmq_consumer_engine.py`
- `plugins/magellon_result_processor/core/rabbitmq_consumer_engine.py`
- `CoreService/core/result_consumer.py`

**Topic pub-sub:**
- `magellon-sdk/src/magellon_sdk/discovery.py` — announce + heartbeat
- `magellon-sdk/src/magellon_sdk/config_broker.py` — config push / subscribe
- `magellon-sdk/src/magellon_sdk/transport/rabbitmq_events.py` — step events
- `CoreService/core/plugin_liveness_registry.py` — heartbeat subscriber
- `CoreService/core/rmq_step_event_forwarder.py` — step-event forwarder
- `CoreService/services/plugin_config_publisher.py` — config push

**Operator + audit:**
- `CoreService/services/cancellation_service.py` — `purge_queue`
- `CoreService/core/helper.py:76–109,160–181` — audit log writer `/magellon/messages/<queue>/messages.json`, publish-time

**Transport module (the only place that stays):**
- `magellon-sdk/src/magellon_sdk/transport/rabbitmq.py` — `RabbitmqClient`. Becomes the RMQ binder's private module in MB6.

### 1.3 What's already broker-neutral and is an asset

`magellon_sdk/categories/contract.py` owns transport-neutral subject naming:

```python
task_subject(cat)      -> "magellon.tasks.ctf"
result_subject(cat)    -> "magellon.tasks.ctf.result"
heartbeat_subject(c,p) -> "magellon.plugins.heartbeat.ctf.ctffind4"
announce_subject(c,p)  -> "magellon.plugins.announce.ctf.ctffind4"
config_subject(cat)    -> "magellon.plugins.config.ctf"
```

Dots work as NATS subjects and RMQ routing keys. Match CloudEvents envelope `subject` field. This is **one source of truth** — the bus's route value objects delegate here, never duplicate.

### 1.4 Why abstract now

Pitch is **call-site consolidation**, not future-proofing. Even without a second backend, collapsing 16 call sites to one module + one binder is a maintainability win. This matches `feedback_yagni_orchestration`: justified by present-day cleanup, not speculative portability.

---

## 2. Design principles — from prior art, adapted for Python

**1. Two surfaces, not one (Cosmic Python, Dapr).** Commands and events are semantically different. `bus.tasks` and `bus.events` are siblings.

**2. Envelope-first, not raw payloads (CloudEvents 1.0).** FastStream leaks pika kwargs (`correlation_id`, `headers`, `priority`, `app_id`) through publish signatures. Portability trap. The bus accepts/emits `magellon_sdk.envelope.Envelope` only.

**3. Binder SPI between bus and transport (Spring Cloud Stream).** A **binder** (SCS's word) / **connector** (Quarkus') / **carrier** (plain English) is a plug-in module that moves envelopes over one transport. The bus Protocol is the caller-facing surface; the binder interface is the transport-facing surface.

**4. Dual consumer API — decorator and imperative (Quarkus SmallRye + Spring Cloud Stream).** `@bus.tasks.consumer(route)` for module-level plain functions; `bus.tasks.consumer(route, handler)` for bound methods on class-based services. One underlying registration, two ergonomic entrypoints. Return → ack, raise → classified nack via existing `classify_exception`. Handlers never call `msg.ack()`.

**5. Routes read from `CategoryContract`, don't duplicate it.** `TaskRoute.for_category(CTF)` delegates to `CTF.task_subject`. Type safety, not new topology.

**6. No user-extensible middleware (FastStream issue #1646 lesson).** A **fixed, named set** of built-in binder features (audit log, trace context) ships in the binder config. Users cannot compose new middleware chains. This is not a contradiction with §4.5 below — it's the distinction between "framework-extensible hooks" and "binder-built-in features."

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
│     RmqBinder — the only binder for MB1–MB6.                    │
│     Owns: pika connection (long-lived), channel pool,           │
│            topology (exchanges, queues, DLQs), reconnect,       │
│            AMQP properties, AuditLogConfig (publish-time file)  │
│     NatsBinder lives in bus/binders/nats/ — deferred to MB7+.   │
└─────────────────────────────────────────────────────────────────┘
```

**Invariants.**

- L1 never imports anything below L2. Lint rule enforces (MB6).
- L2 never imports anything below L3. L2 has zero transport code.
- L3 is a Protocol + small helpers; no `pika`, no `nats-py`.
- L4 is where `pika` lives. Exactly one directory.

---

## 4. Bus API (L2) — what callers see

### 4.1 Module shape

```python
# magellon_sdk/bus/__init__.py
from magellon_sdk.bus import get_bus, MessageBus
```

**`get_bus()` is the only entrypoint.** There is no module-level singleton. First call lazily constructs the bus from config; subsequent calls return the same instance; tests inject via `get_bus.override(...)` / fixture reset.

Rationale: a module-level `bus = MessageBus.default()` would resolve at import time, which binds the decorator form `@bus.tasks.consumer(...)` to the production bus before any test fixture can swap it. `get_bus()` defers resolution to first call — test code calls `get_bus.override(mock_bus)` in a fixture, and plugin code later calls `get_bus()` inside its constructor and sees the mock.

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

`PublishReceipt` carries `ok: bool`, `message_id: str`, `error: Optional[str]`. Fire-and-forget `bus.events.publish` returns a receipt but callers usually discard it — observability without blocking.

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
def handle_ctf(envelope: Envelope[CtfTaskData]) -> TaskResultDto:
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

Imperative is required whenever the handler is a bound method, a lambda, a dynamically-created function, or when registration order depends on runtime state. Every relocated CoreService service (§8) uses imperative. Plugin `main.py` typically uses decorator.

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

Identical pattern for `TaskResultRoute`, `StepEventRoute`, `HeartbeatRoute`, `AnnounceRoute`, `ConfigRoute`. Each delegates to the matching `CategoryContract` accessor. Patterns (`HeartbeatRoute.all()`) return `EventPattern(subject_glob="magellon.plugins.heartbeat.*")`; the binder translates glob to RMQ `#` or NATS `>`.

Test queues like `motioncor_test_inqueue` use `TaskRoute.named(...)` — explicit, not a contract route.

### 4.4 Envelope

`magellon_sdk.envelope.Envelope` unchanged. CloudEvents 1.0 compliant. `bus.tasks.send` wraps raw payloads if passed a non-`Envelope`, but the typed API accepts `Envelope[T]`.

### 4.5 Out of scope — deliberately

- **User-extensible middleware chains.** A fixed set of named binder features (audit log, trace context) is allowed and configured declaratively. Users cannot register custom pre/post hooks — no way to insert code between bus and binder at runtime.
- **Request/reply (`bus.request(...)`).** No caller needs RPC.
- **Streaming / batch subscribers.** No use case.
- **Broker-specific escape hatches** (RMQ priority, NATS KV). Stay in binder config, never in call-site API.
- **Socket.IO.** Separate transport (browser-facing); outside the bus.
- **Connection pooling as caller concern.** One long-lived connection per binder instance, channel per operation. Caller never touches.

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

**Binder lifecycle.** `start()` establishes the long-lived connection, declares exchanges and durable queues, installs DLQ policy, and turns on binder-level features (audit log, tracing). `close()` drains in-flight consumers and shuts the connection. Reconnect is **internal** to the binder — callers get a working binder or `BinderDown` exception; never retry loops.

**Topology ownership.** The binder owns exchange names (`magellon.plugins`, `magellon.events`, `""` default), queue binding patterns, DLQ routing keys. Caller code never names an exchange. `declare_queue_with_dlq` (capability landed but never called from user code today) becomes a binder `start()`-time operation.

**One binder per process.** `get_bus()` constructs one `Binder` from config, holds it for process lifetime. Not per-call.

---

## 6. `PluginBrokerRunner` — composes over the bus

The runner is **not** deleted. It composes over L2.

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

`DiscoveryService`, `ConfigSubscriberService` move into `magellon_sdk/bus/services/`. Provenance stamping, redelivery handling (via `x-magellon-redelivery` header — binder-tracked, honest integer not boolean), and config-drain-between-deliveries stay in the runner.

---

## 7. Audit, observability, DLQ

### 7.1 Audit log — binder config, publish-time

Today's behavior: `publish_message_to_queue` writes `/magellon/messages/<queue>/messages.json` **before** calling RabbitMQ. A task published-but-never-consumed still appears in the audit log.

v2.1 preserves this by making audit a **binder-level declarative feature**, not a user-composable middleware hook:

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

Binder implementation: `publish_task` appends to `<root>/<subject>/messages.json` before the pika `basic_publish`. Identical to today's behavior, same trigger point, same file layout. No decorator, no middleware abstraction at the bus level.

`AuditLogConfig.enabled` defaults to **False**; CoreService boot turns it on for the routes it audits today. Plugins keep it off by default (they only produce results, not originate tasks).

### 7.2 DLQ

Binder declares DLQ topology at `start()`. `TaskConsumerPolicy(dlq_enabled=True)` is the opt-in. `classify_exception` routes poison messages there. Existing queues lack DLQ args — they need a one-shot topology migration, detailed in §9.6.1 (the highest-risk step in the plan).

### 7.3 Redelivery count

v1 passed `int(method.redelivered)` — boolean masquerading as count. v2.1: binder tracks per-message redelivery in a pika header (`x-magellon-redelivery`) and increments on each nack-requeue. `classify_exception(exc, redelivery_count=N)` gets an honest integer.

### 7.4 OpenTelemetry

Trace context rides envelope `traceparent` extension (CloudEvents standard). Binder-level spans land whenever OTel is wired into the process — not scoped to any specific MB phase.

---

## 8. Code relocation — most goes to `magellon-sdk`

CoreService consumes the bus; it does not co-implement broker logic.

| Moves to | From | Why |
|---|---|---|
| `magellon_sdk/bus/binders/rmq/result_consumer.py` | `CoreService/core/result_consumer.py` | It's a bus subscriber, not a CoreService-specific thing |
| `magellon_sdk/bus/services/liveness_registry.py` | `CoreService/core/plugin_liveness_registry.py` | Heartbeat subscription is generic; CoreService keeps a thin FastAPI wrapper |
| `magellon_sdk/bus/services/config_publisher.py` | `CoreService/services/plugin_config_publisher.py` | Operator primitive — HTTP endpoint stays, publish logic moves |
| `magellon_sdk/bus/services/step_event_forwarder.py` | `CoreService/core/rmq_step_event_forwarder.py` | Subscriber that forwards to Socket.IO — callback injected |
| `magellon_sdk/bus/operator/cancellation.py` | `CoreService/services/cancellation_service.py` (partial) | Broker operations move; FastAPI endpoint stays |
| Collapses into binder | 3× `plugins/*/core/rabbitmq_consumer_engine.py` | Duplicated code; binder is the only consumer harness |
| Collapses into binder | `magellon_sdk/messaging.py::publish_message_to_queue` | Replaced by `bus.tasks.send` with `AuditLogConfig` |
| Collapses into binder | `magellon_sdk/dispatcher.py::RabbitmqTaskDispatcher` | Replaced by `bus.tasks.send`; the Protocol survives for in-process dispatch |

**After migration, CoreService touches the bus in exactly these files:**

- `main.py` / startup: `get_bus().start()`, registers Socket.IO forwarder callback.
- Importers + `core/helper.py`: `bus.tasks.send(...)` at dispatch points.
- `controllers/cancellation_controller.py`: calls `bus.tasks.purge` via operator module.
- `controllers/plugin_config_controller.py`: calls `bus.events.publish` via config publisher service.

Zero `pika` imports outside `magellon_sdk/bus/binders/rmq/`. Lint-enforced (MB6).

---

## 9. Phased plan — MB0–MB6 in scope, MB7 deferred

**Guiding constraint (MB0–MB5): no behavior change.** Reshuffling call-site boundaries. Behavior changes (prefetch enforcement, DLQ cutover, second backend) are explicit and opt-in at their own phase.

Every phase ends with a green test suite on `main`; no phase requires the next.

### MB0 — Pre-extraction: decompose `PluginBrokerRunner`

**Goal:** Make the runner's composition shape visible before the bus lands.

- Split `magellon_sdk/runner.py` into `magellon_sdk/runner/plugin_runner.py` + `magellon_sdk/runner/lifecycle.py` (discovery start, config subscriber start — thin wrappers over existing classes).
- No API change. `PluginBrokerRunner` constructor signature preserved.

**Acceptance:** All existing plugin smoke tests + SDK tests pass. No caller imports change.

### MB1 — Bus Protocol + routes (code lands, nothing uses it)

**Goal:** Specification becomes code.

- `magellon_sdk/bus/__init__.py` — `get_bus()`, `MessageBus` facade.
- `bus/interfaces.py` — `TasksBus`, `EventsBus`, `Binder` Protocols.
- `bus/routes/` — `TaskRoute`, `TaskResultRoute`, `StepEventRoute`, `HeartbeatRoute`, `AnnounceRoute`, `ConfigRoute` + patterns. All delegate to `CategoryContract`.
- `bus/policy.py` — `TaskConsumerPolicy`, `AuditLogConfig`, `PublishReceipt`, `ConsumerHandle`, `SubscriptionHandle`.
- `bus/binders/mock.py` — in-memory binder for unit tests only.
- Unit tests: route → subject translation; envelope round-trip through mock binder; decorator vs imperative registration both work; handler return/raise → classification.

**Acceptance:** `from magellon_sdk.bus import get_bus` works. Mock binder round-trips envelopes. No production code imports `bus` yet.

### MB2 — RMQ binder implementation

**Goal:** One binder, feature-parity with current RMQ code, behind the bus Protocol.

- `magellon_sdk/bus/binders/rmq/` — `binder.py`, `connection.py` (long-lived), `topology.py` (exchanges/queues/DLQ declare), `publish.py`, `consume.py`, `subscribe.py`, `audit.py`.
- Re-uses `magellon_sdk.transport.rabbitmq.RabbitmqClient` internally during transition; collapses in MB6.
- Integration tests against a real RMQ container: publish/consume round-trip, pattern subscribe, purge, DLQ routing, reconnect, audit file writes.

**Acceptance:** New binder-level integration suite green. Still no production caller.

### MB3 — Migrate producers (smallest blast radius)

**Goal:** Every task-dispatch call site moves to `bus.tasks.send`.

- `CoreService/core/dispatcher_registry.py` — `RabbitmqTaskDispatcher` becomes `bus.tasks.send(TaskRoute.for_category(...), env)`.
- `CoreService/core/helper.py::push_task_to_task_queue` — delegates to bus.
- `CoreService/core/helper.py::publish_message_to_queue` — deleted; audit behavior preserved via `AuditLogConfig` on the RMQ binder.
- Importers (`services/importers/*`) unchanged externally; helpers re-routed internally.

**Deletes:** `magellon_sdk/dispatcher.py::RabbitmqTaskDispatcher`, `magellon_sdk/messaging.py::publish_message_to_queue`. Protocols (`TaskDispatcher`) stay for in-process dispatch.

**Acceptance:** All existing integration tests pass. Audit log files continue to appear at the same paths with the same content.

### MB4 — Migrate consumers + relocate to SDK

**Goal:** Consumer side moves behind the bus; most code moves from CoreService to SDK.

- `PluginBrokerRunner._handle_task` wraps `bus.tasks.consumer` registration. Inner plugin.run() + provenance + redelivery-count tracking unchanged behaviorally; redelivery becomes honest integer via `x-magellon-redelivery` header.
- 3× `plugins/*/core/rabbitmq_consumer_engine.py` — deleted.
- `CoreService/core/result_consumer.py` → `magellon_sdk/bus/binders/rmq/result_consumer.py` (a `bus.tasks.consumer` registration for `TaskResultRoute.all()`).
- Each plugin's `main.py` still constructs `PluginBrokerRunner` — external API unchanged.

**Deletes:** 3 consumer-engine files; `CoreService/core/result_consumer.py`.

**Acceptance:** `pytest CoreService/tests/integration/test_e2e_seam.py` green. All 4 plugin smoke tests green against docker-compose.

### MB5 — Migrate topic pub-sub + relocate to SDK

**Goal:** Discovery, heartbeat, config, step events move behind the bus.

- `magellon_sdk/discovery.py` → uses `bus.events.publish` internally.
- `magellon_sdk/config_broker.py` → uses `bus.events.publish` + `bus.events.subscribe`.
- `magellon_sdk/transport/rabbitmq_events.py::RabbitmqEventPublisher` → collapsed into RMQ binder.
- `CoreService/core/rmq_step_event_forwarder.py` → `magellon_sdk/bus/services/step_event_forwarder.py` (Socket.IO emit injected as callback).
- `CoreService/core/plugin_liveness_registry.py` → `magellon_sdk/bus/services/liveness_registry.py`; CoreService keeps a thin FastAPI wrapper.
- `CoreService/services/plugin_config_publisher.py` → `magellon_sdk/bus/services/config_publisher.py`; HTTP endpoint unchanged.

**Acceptance:** `test_step_events_smoke.py`, `test_discovery_smoke.py`, dynamic-config round-trip — all green.

### MB6 — Operator primitives, lint rule, DLQ topology migration

**Goal:** Close out the migration. No `pika` outside the binder. Every production queue has a DLQ.

- `CoreService/services/cancellation_service.py::purge_queue` → calls `bus.tasks.purge` via `magellon_sdk/bus/operator/cancellation.py`.
- Lint rule (ruff + CI check): `pika` and `aio_pika` imports forbidden outside `magellon_sdk/bus/binders/rmq/`.
- `magellon_sdk/transport/rabbitmq.py` collapses into the binder's private modules.
- **DLQ topology migration** — see §9.6.1 runbook.

**Acceptance:** `rg '^import pika|^from pika' -g '!magellon_sdk/bus/binders/rmq/**'` returns zero. DLQ routing verified on CTF and MotionCor queues via a deliberate-poison smoke test in staging. All production queues listed in §1.2 are DLQ-wired.

#### 9.6.1 DLQ topology migration runbook

**Risk:** This is the single highest-risk operation in the plan. RabbitMQ returns `PRECONDITION_FAILED` (code 406) if you try to redeclare a queue with different `x-dead-letter-exchange` / `x-dead-letter-routing-key` args than it was created with. The only way to add DLQ args to an existing queue is `queue.delete` followed by `queue.declare` — and `queue.delete` **discards any messages currently in the queue**, whether ack'd-in-flight or unacked.

**Preconditions:**
- A staging replica of the docker-compose stack is up and healthy.
- The runbook has been dry-run end-to-end against staging and signed off.
- An ops window is scheduled: no imports in flight, no plugins actively consuming.

**Per-queue procedure** (applied to each queue in §1.2 — 5 task queues + 2 result queues):

1. **Drain.** Stop all consumers: scale plugin containers to 0 (CTF, MotionCor, result processor) and shut down CoreService's in-process consumers (`result_consumer.py`). Wait for `messages_ready + messages_unacknowledged == 0` on `rabbitmqctl list_queues name messages_ready messages_unacknowledged`.
2. **Snapshot.** Verify count is zero. If non-zero (should not happen after drain), dump remaining messages to a file via `rabbitmqadmin get queue=<name> count=N requeue=false ackmode=ack_requeue_false` — this is lossy recovery, intentional; operator reviews and decides.
3. **Delete.** `channel.queue_delete(queue_name, if_unused=True, if_empty=True)`. `if_empty=True` fails if drain was incomplete — deliberate safety.
4. **Redeclare.** `channel.queue_declare(queue_name, durable=True, arguments={"x-dead-letter-exchange": "", "x-dead-letter-routing-key": f"{queue_name}_dlq"})`. Also declare the DLQ itself (`{queue_name}_dlq`, durable, no further DLQ).
5. **Rebind.** For topic-bound queues (heartbeat, config, step-event subscribers), re-apply the exchange bindings with the original routing keys.
6. **Restart consumers.** Scale plugin containers back up; CoreService consumers reconnect.
7. **Verify.** Publish a deliberately-malformed test message that triggers `classify_exception → DLQ`. Confirm it lands in `<queue>_dlq` via `rabbitmqctl list_queues`.

**Automation.** MB6 ships `scripts/migrate_dlq_topology.py` that runs 1–5 idempotently with `--dry-run` and `--queue <name>` flags. Step 6 (consumer restart) and step 7 (verify) are operator-run.

**Rollback.** Steps 1–3 are destructive; step 4 onward is reversible by deleting the new queue and redeclaring without DLQ args. If verify (step 7) fails, rollback to no-DLQ is one command per queue. Messages dispatched during a rollback window publish successfully (no-DLQ is the pre-MB6 state).

**Why not "create a new queue, drain-migrate in parallel":** That's a cleaner pattern in principle (RabbitMQ shovel or a consumer-republisher). Ruled out because it needs CoreService + every plugin aware of two queue names during migration. The ops-window delete-and-redeclare trades a scheduled outage for simpler code and is acceptable given that queues drain fast (< 60s after producers stop).

### MB7 — (deferred) second binder

**Goal:** Not committed to in advance. A checkpoint.

If NATS becomes operationally justified (step events want JetStream replay, or compose wants to drop RMQ), implement `NatsBinder` using existing `magellon_sdk/transport/nats.py`. Config flag `MAGELLON_BUS_BACKEND=rmq|nats`. Recommended first cutover: step events (smallest blast radius, already NATS-shaped).

If SQS becomes justified (AWS-only deployment), implement `SqsBinder` + `SnsBinder` — SQS for work, SNS for fanout. Expect 1.5–2× NATS effort: SNS filter policies replace routing-key patterns, 256 KB payload cap, redrive policies replace DLQ exchanges, no native ack/nack semantics (visibility timeout + redrive).

---

## 10. Non-goals

- **Fixing the "two plugin architectures" split** (external RMQ vs in-process `PluginBase`). Orthogonal; both converge through the bus.
- **Replacing Socket.IO.** Different semantics (browser-facing, per-session auth).
- **Workflow engine.** Temporal was reverted for a reason.
- **Changing the envelope format.** CloudEvents 1.0 stays.
- **Adding `bus.request(...)` RPC.** Async dispatch + separate result consume is the model.
- **User-extensible middleware.** Only a fixed, named set of binder features.

---

## 11. Risks

| Risk | Mitigation |
|---|---|
| MB4 touches every plugin — big-bang risk | Each plugin migrates in its own PR; runner API stays backwards-compatible during transition; merge order CTF → MotionCor → result processor. |
| Pika features leak through | Lint rule in MB6. Any new `pika` import outside the binder fails CI. |
| DLQ topology migration data loss | §9.6.1 runbook: drain → snapshot → delete → redeclare → rebind → restart → verify. Dry-run on staging first. `if_empty=True` on delete as a safety net. Rollback path documented. Automation script with `--dry-run`. |
| Prefetch default (`None` = unlimited) hides a future problem | Documented explicitly; plugins opt into `prefetch=1` when they need backpressure. A separate phase can flip the default later based on evidence. |
| Spec flaw only surfaces in MB7 | MB7 is opt-in; fixing one Protocol is cheaper than fixing 16 call sites. |
| Relocation from CoreService → SDK churns imports | Each relocation is a single PR: move file, update imports, no logic changes. Logic changes land in the subsequent phase. |
| Singleton vs factory confusion at MB1 | `get_bus()` is the only entrypoint; no `bus` module attribute. Documented in §4.1. Enforced by absence (the import just isn't there). |

---

## 12. What to read next

- `CURRENT_ARCHITECTURE.md` §4.1, §6, §8 — the RMQ-welded state this plan unwinds.
- `magellon_sdk/categories/contract.py` — the subject-naming source of truth the bus delegates to.
- `magellon_sdk/envelope.py` — the bus's wire type.
- `magellon_sdk/runner.py` — the composition the bus slots under.
- `CoreService/core/dispatcher_registry.py` — smallest migration target (MB3).

---

## 13. References

**Frameworks studied:**

- [Spring Cloud Stream — Binder SPI](https://docs.spring.io/spring-cloud-stream/reference/spring-cloud-stream/binders.html) — the layering v2 adopts: L2/L3/L4 = Bindings / Binder / Broker.
- [Quarkus SmallRye Reactive Messaging — Connectors](https://quarkus.io/guides/messaging) — `@Incoming`/`@Outgoing` decorator model that inspired `@bus.tasks.consumer`.
- [Dapr — Pub/Sub with CloudEvents](https://docs.dapr.io/developing-applications/building-blocks/pubsub/pubsub-cloudevents/) — commands-on-queues vs events-on-pubsub split.
- [Cosmic Python — Chapter 8 (Event Bus) / Chapter 10 (Command Bus)](https://www.cosmicpython.com/book/) — the two-surface split this spec codifies.
- [CloudEvents 1.0](https://github.com/cloudevents/spec/blob/v1.0/spec.md) — envelope format already in use.

**Negative examples (what we deliberately avoid):**

- [FastStream issue #1646](https://github.com/ag2ai/faststream/issues/1646) — middleware unification rabbit hole; why §4.5 excludes user-extensible middleware chains.
- FastStream publish signature (pika kwargs leaking through) — why §2 insists on envelope-first.

**Internal prior art:**

- `magellon_sdk/dispatcher.py` — existing `TaskDispatcher` Protocol. Survives as the in-process dispatch path; bus is the out-of-process path.
- `magellon_sdk/transport/nats.py` — existing NATS transport; blueprint for MB7's `NatsBinder`.

---

**End of v2.1 spec.**

Open questions before MB0:

1. Keep `PluginBrokerRunner` name, or rename to `PluginHarness`? (Cosmetic.)
2. `AuditLogConfig` default-on for CoreService-originated routes, or explicit opt-in per route? (Ops decision — affects disk usage and operator surprise.)
3. MB0 ships as its own PR, or folded into MB1? (PR hygiene; standalone reads cleaner.)
