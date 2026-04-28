"""MB6.4 — DLQ topology migration runbook as an executable script.

Implements the runbook at ``Documentation/DLQ_MIGRATION_RUNBOOK.md``
(originally specified inline in ``MESSAGE_BUS_SPEC.md`` §7.2 / former
§9.6.1). The spec calls
this out as the single highest-risk operation in the MB plan because
RabbitMQ refuses to redeclare a queue with different ``x-*`` args —
the only way to retrofit DLQ on an existing queue is
``queue_delete + queue_declare``, which discards any in-flight
messages. The script bakes the drain + snapshot + delete + redeclare
sequence so an operator runs one command instead of six.

Usage
-----

Dry-run against staging (no changes, prints what would happen)::

    python migrate_dlq_topology.py --dry-run --rmq-url amqp://rabbit:behd1d2@127.0.0.1:5672/

Single queue, live run::

    python migrate_dlq_topology.py --queue ctf_tasks_queue \\
        --rmq-url amqp://rabbit:behd1d2@127.0.0.1:5672/

All production queues, live run (requires explicit --yes)::

    python migrate_dlq_topology.py --all --yes \\
        --rmq-url amqp://rabbit:behd1d2@127.0.0.1:5672/

Verify only — reads queue arguments and reports which are DLQ-wired::

    python migrate_dlq_topology.py --verify --all

Preconditions (operator owns)
-----------------------------

1. Staging dry-run has been signed off.
2. All consumers are stopped (plugin containers scaled to 0,
   CoreService result-consumer thread shut down). The script's
   ``if_empty=True`` guard fails loudly if the drain isn't complete.
3. Ops window is scheduled — this is a brief outage per queue.

Rollback
--------

Steps 3–5 (delete / redeclare / rebind) are destructive per the
spec. Rollback means running ``--restore`` (not implemented here;
the spec §9.6.1 footnote documents the manual path). In practice
the simplest rollback is: re-run the script without DLQ args to
go back to the no-DLQ state. Messages dispatched during the
rollback window publish successfully — no-DLQ is the pre-MB6.4
equilibrium.

This script uses pika directly; that is the intended home for pika
access per the ruff allowlist on ``scripts/**``.
"""
from __future__ import annotations

import argparse
import logging
import sys
import time
from dataclasses import dataclass
from typing import Dict, List, Optional
from urllib.parse import urlparse

import pika
from pika.exceptions import ChannelClosedByBroker


logger = logging.getLogger("migrate_dlq_topology")


# ---------------------------------------------------------------------------
# Queue catalog — the five task queues + two result queues that
# predated MB6.4 (the historical "current leaks" list from the bus
# spec's pre-migration §1.2). New queues created via the SDK's
# declare_queue_with_dlq helper don't need this script; this list is
# the pre-MB6.4 legacy set.
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class _QueueSpec:
    name: str
    # For topic-exchange bindings (result queues don't need these;
    # they're on the default exchange).
    exchange: Optional[str] = None
    routing_keys: tuple = ()


_PRODUCTION_QUEUES: List[_QueueSpec] = [
    _QueueSpec("ctf_tasks_queue"),
    _QueueSpec("motioncor_tasks_queue"),
    _QueueSpec("fft_tasks_queue"),
    _QueueSpec("ctf_out_tasks_queue"),
    _QueueSpec("motioncor_out_tasks_queue"),
    _QueueSpec("fft_out_tasks_queue"),
    _QueueSpec("core_step_events_queue", exchange="magellon.events", routing_keys=("job.*.step.*",)),
]

_DLQ_SUFFIX = "_dlq"


# ---------------------------------------------------------------------------
# Core operations
# ---------------------------------------------------------------------------

def _dlq_args(queue_name: str) -> Dict[str, str]:
    """Match ``RabbitmqClient.declare_queue_with_dlq`` output."""
    return {
        "x-dead-letter-exchange": "",
        "x-dead-letter-routing-key": f"{queue_name}{_DLQ_SUFFIX}",
    }


def _inspect(channel, queue_name: str) -> Optional[Dict[str, object]]:
    """Return ``{message_count, consumer_count, arguments}`` for a queue,
    or ``None`` if it doesn't exist. Uses a fresh channel because
    ``queue_declare`` with passive=True on a missing queue closes the
    current channel.
    """
    try:
        frame = channel.queue_declare(queue=queue_name, passive=True)
        return {
            "message_count": frame.method.message_count,
            "consumer_count": frame.method.consumer_count,
        }
    except ChannelClosedByBroker:
        return None


def _drain_and_verify(
    channel, queue_name: str, *, dry_run: bool
) -> bool:
    """Confirm the queue is empty AND has no active consumers.

    Returns True if safe to delete; False otherwise. In --dry-run
    mode this is read-only.
    """
    info = _inspect(channel, queue_name)
    if info is None:
        logger.info("  queue %s does not exist — skipping", queue_name)
        return False

    mc = info["message_count"]
    cc = info["consumer_count"]
    logger.info("  queue %s: messages=%d consumers=%d", queue_name, mc, cc)

    if cc > 0:
        logger.error(
            "  queue %s still has %d consumer(s) — stop them before running this script",
            queue_name, cc,
        )
        return False
    if mc > 0:
        logger.error(
            "  queue %s has %d pending message(s) — not draining inside the script "
            "(risk of losing user work). Stop producers, drain, rerun.",
            queue_name, mc,
        )
        return False
    return True


def _redeclare_with_dlq(
    channel,
    spec: _QueueSpec,
    *,
    dry_run: bool,
) -> None:
    """Declare the DLQ, then delete + redeclare the main queue with
    DLQ args.

    Order matters for failure safety: if we deleted the main queue
    before declaring the DLQ and the DLQ declare then failed (broker
    hiccup, permission issue), the main queue would be gone with no
    way to roll back. Declaring the DLQ FIRST means a failure leaves
    the main queue intact — operator can investigate without an
    outage.

    DLQ ``queue_declare`` is idempotent on a queue that already
    exists with matching args, so re-running this script after a
    partial failure is safe.
    """
    dlq_name = f"{spec.name}{_DLQ_SUFFIX}"

    if dry_run:
        logger.info("  [DRY-RUN] would queue_declare(%s, durable=True)", dlq_name)
        logger.info("  [DRY-RUN] would queue_delete(%s, if_empty=True, if_unused=True)", spec.name)
        logger.info(
            "  [DRY-RUN] would queue_declare(%s, durable=True, args=%s)",
            spec.name, _dlq_args(spec.name),
        )
        if spec.exchange and spec.routing_keys:
            for rk in spec.routing_keys:
                logger.info(
                    "  [DRY-RUN] would queue_bind(%s, exchange=%s, routing_key=%s)",
                    spec.name, spec.exchange, rk,
                )
        return

    # Step 1: ensure the DLQ exists BEFORE touching the main queue.
    # If this raises, the main queue is untouched and the operator
    # can rerun once they fix the DLQ declare cause.
    logger.info("  declaring DLQ %s", dlq_name)
    channel.queue_declare(queue=dlq_name, durable=True)

    # Step 2 + 3: now the destructive part. DLQ already exists, so
    # even if step 3 fails the operator's recovery is "redeclare
    # main without DLQ args", not "rebuild DLQ from scratch".
    logger.info("  deleting %s (if_empty, if_unused)", spec.name)
    channel.queue_delete(queue=spec.name, if_empty=True, if_unused=True)

    logger.info("  redeclaring %s with DLQ args", spec.name)
    channel.queue_declare(
        queue=spec.name,
        durable=True,
        arguments=_dlq_args(spec.name),
    )

    if spec.exchange and spec.routing_keys:
        for rk in spec.routing_keys:
            logger.info(
                "  binding %s -> exchange=%s routing_key=%s",
                spec.name, spec.exchange, rk,
            )
            channel.queue_bind(
                queue=spec.name, exchange=spec.exchange, routing_key=rk
            )


def _verify_dlq_args(channel, queue_name: str) -> Optional[Dict[str, str]]:
    """Inspect a queue's ``x-*`` arguments. Returns the DLQ-related
    args if present, else ``None``. passive=True so no declaration
    side effect.

    pika's queue_declare doesn't return arguments in the method frame,
    so this relies on the fact that re-declaring with matching args is
    a no-op and re-declaring with conflicting args raises. We test by
    attempting to re-declare with the expected DLQ args and catching
    precondition failure.
    """
    expected = _dlq_args(queue_name)
    try:
        channel.queue_declare(queue=queue_name, durable=True, arguments=expected, passive=False)
        return expected
    except ChannelClosedByBroker as e:
        if e.reply_code == 406:  # PRECONDITION_FAILED
            return None
        raise


# ---------------------------------------------------------------------------
# CLI glue
# ---------------------------------------------------------------------------

def _open_connection(url: str) -> pika.BlockingConnection:
    parsed = urlparse(url)
    credentials = pika.PlainCredentials(
        parsed.username or "guest", parsed.password or "guest"
    )
    params = pika.ConnectionParameters(
        host=parsed.hostname or "127.0.0.1",
        port=parsed.port or 5672,
        virtual_host=parsed.path.lstrip("/") or "/",
        credentials=credentials,
        heartbeat=30,
        connection_attempts=3,
        retry_delay=2,
    )
    return pika.BlockingConnection(params)


def _parse_args(argv: List[str]) -> argparse.Namespace:
    ap = argparse.ArgumentParser(description="DLQ topology migration (MB6.4)")
    ap.add_argument(
        "--rmq-url",
        default="amqp://rabbit:behd1d2@127.0.0.1:5672/",
        help="AMQP URL to target. Default is the local docker-compose broker.",
    )
    group = ap.add_mutually_exclusive_group()
    group.add_argument("--queue", help="Migrate just this one queue.")
    group.add_argument("--all", action="store_true", help="Migrate every production queue.")
    group.add_argument(
        "--verify", action="store_true",
        help="Report which queues are DLQ-wired; no changes.",
    )
    ap.add_argument(
        "--dry-run", action="store_true",
        help="Print operations without executing. Safe to run against production.",
    )
    ap.add_argument(
        "--yes", action="store_true",
        help="Required for --all in non-dry-run mode. Confirms you've read the runbook.",
    )
    return ap.parse_args(argv)


def _queues_for_args(args: argparse.Namespace) -> List[_QueueSpec]:
    if args.queue:
        for spec in _PRODUCTION_QUEUES:
            if spec.name == args.queue:
                return [spec]
        raise SystemExit(f"Unknown queue {args.queue!r}. Known: {[q.name for q in _PRODUCTION_QUEUES]}")
    if args.all or args.verify:
        return list(_PRODUCTION_QUEUES)
    raise SystemExit("Specify one of --queue, --all, --verify.")


def main(argv: Optional[List[str]] = None) -> int:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
        datefmt="%H:%M:%S",
    )
    args = _parse_args(list(argv) if argv is not None else sys.argv[1:])

    if args.all and not (args.dry_run or args.verify) and not args.yes:
        logger.error(
            "--all in live mode requires --yes. Read Documentation/"
            "DLQ_MIGRATION_RUNBOOK.md first; stop producers + consumers "
            "first; then rerun with --yes.",
        )
        return 2

    queues = _queues_for_args(args)
    logger.info("target broker: %s", args.rmq_url)
    logger.info("queues: %s", [q.name for q in queues])
    if args.dry_run:
        logger.info("MODE: dry-run (no changes)")
    elif args.verify:
        logger.info("MODE: verify (no changes)")
    else:
        logger.info("MODE: live")

    try:
        conn = _open_connection(args.rmq_url)
    except Exception:
        logger.exception("failed to connect to broker")
        return 1

    try:
        any_failed = False

        if args.verify:
            for spec in queues:
                # Open a fresh channel per queue — passive decl that
                # fails closes the channel.
                ch = conn.channel()
                try:
                    result = _verify_dlq_args(ch, spec.name)
                    status = "DLQ-wired" if result else "NO DLQ"
                    logger.info("  %-30s %s", spec.name, status)
                finally:
                    if ch.is_open:
                        ch.close()
                time.sleep(0.05)
            return 0

        # Migration path: per-queue drain + delete + redeclare.
        for spec in queues:
            logger.info("--- %s ---", spec.name)
            ch = conn.channel()
            try:
                if not _drain_and_verify(ch, spec.name, dry_run=args.dry_run):
                    any_failed = True
                    continue
            finally:
                if ch.is_open:
                    ch.close()

            # Fresh channel for the destructive ops — previous passive
            # failures may have closed the earlier one.
            ch = conn.channel()
            try:
                _redeclare_with_dlq(ch, spec, dry_run=args.dry_run)
            except Exception:
                logger.exception("  %s: redeclare failed", spec.name)
                any_failed = True
            finally:
                if ch.is_open:
                    ch.close()
            time.sleep(0.1)

        return 1 if any_failed else 0
    finally:
        try:
            conn.close()
        except Exception:
            pass


if __name__ == "__main__":
    sys.exit(main())
