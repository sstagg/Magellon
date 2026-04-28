# DLQ Topology Migration — Operator Runbook (MB6.4)

**Status:** Ops procedure, 2026-04-21. Paired with
`CoreService/scripts/migrate_dlq_topology.py`.
**Risk:** High. This is the single non-revertible-by-`git revert`
operation in the MessageBus migration plan.
**Companion:** `MESSAGE_BUS_SPEC.md` §7.2 (DLQ design); this runbook
was originally inline in the spec's §9.6.1 and extracted here
2026-04-21 alongside the MB6.4 script.

---

## What this migrates

Seven production RMQ queues that predate MB6.4 have no dead-letter
exchange wired:

| Queue | Exchange | Routing keys |
|---|---|---|
| `ctf_tasks_queue` | default | — |
| `motioncor_tasks_queue` | default | — |
| `fft_tasks_queue` | default | — |
| `ctf_out_tasks_queue` | default | — |
| `motioncor_out_tasks_queue` | default | — |
| `fft_out_tasks_queue` | default | — |
| `core_step_events_queue` | `magellon.events` | `job.*.step.*` |

After the migration each queue is declared with
`x-dead-letter-exchange=""` + `x-dead-letter-routing-key=<queue>_dlq`
and a companion `<queue>_dlq` queue exists to catch poisoned messages.

## Why it cannot be a quiet rolling change

RabbitMQ returns `PRECONDITION_FAILED` (code 406) if you try to
redeclare a queue with different `x-*` args than it was created with.
The only path to retrofit DLQ args is **`queue_delete` + `queue_declare`**
— and `queue_delete` drops any messages in the queue. So a brief
outage window is unavoidable.

## Preconditions

Check all of these before executing in production.

1. **Dry-run on staging is signed off.** Run
   `python scripts/migrate_dlq_topology.py --dry-run --all
   --rmq-url amqp://…@staging-rmq:5672/` against a staging replica of
   production topology. The output should be error-free and match
   the expected queue list.
2. **All producers stopped.** No `bus.tasks.send` / `bus.events.publish`
   call is in flight. In docker-compose this usually means scaling
   CoreService to 0 and keeping the frontend off.
3. **All consumers stopped.** Plugin containers scaled to 0 (CTF,
   MotionCor, FFT, result processor). CoreService's in-process
   result-consumer exits with CoreService shutdown.
4. **Queues are empty.** `rabbitmqctl list_queues name messages_ready
   messages_unacknowledged consumers` returns 0 for all three counters
   on each target queue. The migration script also checks this and
   refuses to proceed otherwise; this is a belt-and-braces step.
5. **Backup.** Not strictly required for queue topology but take one
   anyway: `rabbitmqctl export_definitions /path/to/backup.json`.

## Execution

Run in a scheduled ops window. The window needs to cover:

- ~30 seconds of actual migration (per queue: declare DLQ + delete
  main + redeclare main + rebind, all sub-second; script loops
  sequentially).
- Time to scale consumers/producers back up after verify.

### Per-queue step order (failure-safe)

The script applies operations in this order so a partial failure
leaves the system recoverable:

1. **Declare the DLQ** (`<queue>_dlq`). Idempotent if it already
   exists. If this step fails, the main queue is still untouched —
   operator fixes the cause and reruns.
2. **Delete the main queue** (`if_empty=True, if_unused=True`). Now
   the destructive part begins; the DLQ already exists so the
   recovery surface is "redeclare main", not "rebuild DLQ + main".
3. **Redeclare the main queue with DLQ args**.
4. **Rebind** the main queue to its exchange / routing keys (only
   `core_step_events_queue` has bindings; the task / out queues use
   the default exchange).

Live run for all production queues:

```
cd CoreService
python scripts/migrate_dlq_topology.py \
    --all \
    --yes \
    --rmq-url amqp://rabbit:PASSWORD@PROD-HOST:5672/
```

`--yes` is required for `--all` in live mode. It is the sign-off
that you've read this runbook; the script refuses without it.

For a single queue:

```
python scripts/migrate_dlq_topology.py \
    --queue ctf_tasks_queue \
    --rmq-url amqp://rabbit:PASSWORD@PROD-HOST:5672/
```

## Verify after execution

1. **DLQ wiring visible.** Run the script's verify mode:

    ```
    python scripts/migrate_dlq_topology.py --verify --all \
        --rmq-url amqp://rabbit:PASSWORD@PROD-HOST:5672/
    ```

    Every target queue should report `DLQ-wired`.

2. **Companion DLQs exist.** `rabbitmqctl list_queues name` should
   now show `ctf_tasks_queue_dlq`, `motioncor_tasks_queue_dlq`, etc.

3. **Poison-message smoke test** (on staging replica or the quietest
   prod queue): publish a deliberately-malformed message and confirm
   it routes to the DLQ. Example with `rabbitmqadmin`:

    ```
    rabbitmqadmin publish exchange="" routing_key=ctf_tasks_queue \
        payload='{not-valid-json}'

    # Start a plugin replica pointed at staging; let it reject.
    # Then:
    rabbitmqadmin get queue=ctf_tasks_queue_dlq count=1
    # Should return the malformed payload.
    ```

4. **Start producers + consumers back up.** Scale plugin containers
   to their production replica count; restart CoreService. Confirm
   a normal import flows end-to-end.

## Rollback

The destructive steps (delete + redeclare + rebind) are not
reversible by `git revert`. Rollback options:

1. **Redeclare without DLQ args.** Run the script with a `--no-dlq`
   flag (TODO: add if rollback ever becomes likely — current script
   only has the forward path because rollback during the ops window
   is expected to be rare). Manual equivalent: `queue_delete` each
   migrated queue and `queue_declare` without `x-*` args.
2. **Restore from `export_definitions` backup** taken in the
   preconditions. Broker-wide but clean.

Either way: messages dispatched during the rollback window publish
successfully — the pre-MB6.4 state (no DLQ) is a valid equilibrium.

## Why this script is a one-shot and not ongoing automation

New queues created after MB6.4 land should call
`RabbitmqClient.declare_queue_with_dlq` at construction time
(`magellon_sdk.bus.binders.rmq._client`). The binder already does
this for bus-declared queues via `TaskConsumerPolicy(dlq_enabled=True)`.
This script only exists for the one-time migration of queues that
existed before DLQ wiring was possible. After it runs once cleanly,
the script itself becomes archaeology — safe to delete.
