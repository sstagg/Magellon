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
