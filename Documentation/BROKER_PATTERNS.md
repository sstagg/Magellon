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
