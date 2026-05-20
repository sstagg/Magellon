"""
Drain motioncor_tasks_queue and save messages to a JSON file.

Since the local motioncor plugin has no GPU, tasks dispatched during import
accumulate in the queue. This script drains them so they can be replayed
on AWS via replay_plugin_stack.py.

Usage:
    python sandbox/aws/record_tasks.py --session 24dec03a
    python sandbox/aws/record_tasks.py --session 24dec03a --out /tmp/tasks.json
    python sandbox/aws/record_tasks.py --peek   # read without consuming (requires mgmt API)

Output:
    sandbox/aws/motioncor_tasks_{session}.json  (or --out path)

Env overrides:
    RMQ_HOST  RMQ_PORT  RMQ_USER  RMQ_PASS
    RMQ_MGMT_PORT  (default 15672, used by --peek)
"""

import argparse
import json
import os
import sys

import pika

RMQ_HOST      = os.environ.get("RMQ_HOST",  "127.0.0.1")
RMQ_PORT      = int(os.environ.get("RMQ_PORT",  "5672"))
RMQ_USER      = os.environ.get("RMQ_USER",  "rabbit")
RMQ_PASS      = os.environ.get("RMQ_PASS",  "behd1d2")
RMQ_MGMT_PORT = int(os.environ.get("RMQ_MGMT_PORT", "15672"))

QUEUE = "motioncor_tasks_queue"

HERE = os.path.dirname(os.path.abspath(__file__))


def _default_output(session: str) -> str:
    return os.path.join(HERE, f"motioncor_tasks_{session}.json")


def drain_queue(dry_run: bool = False) -> list:
    """
    Consume all pending messages from motioncor_tasks_queue and return them.
    Messages are acknowledged (removed from queue) unless dry_run=True.

    With dry_run=True, messages are nack'd + requeued so the queue is
    unchanged; this requires basic_get without auto_ack followed by nack.
    """
    params = pika.ConnectionParameters(
        host=RMQ_HOST, port=RMQ_PORT,
        credentials=pika.PlainCredentials(RMQ_USER, RMQ_PASS),
        connection_attempts=3, retry_delay=2,
        heartbeat=60,
    )
    conn = pika.BlockingConnection(params)
    ch   = conn.channel()
    ch.queue_declare(queue=QUEUE, durable=True, passive=False)

    messages  = []
    nack_tags = []

    while True:
        method, props, body = ch.basic_get(queue=QUEUE, auto_ack=False)
        if method is None:
            break
        try:
            payload = json.loads(body)
        except json.JSONDecodeError:
            payload = {"_raw": body.decode("utf-8", errors="replace")}
        messages.append(payload)

        if dry_run:
            nack_tags.append(method.delivery_tag)
        else:
            ch.basic_ack(method.delivery_tag)

    if dry_run:
        for tag in nack_tags:
            ch.basic_nack(tag, requeue=True)

    conn.close()
    return messages


def peek_via_mgmt(count: int = 1000) -> list:
    """
    Use the RabbitMQ Management HTTP API to peek at messages without
    consuming them.  Requires the management plugin to be enabled.
    """
    import urllib.request
    import urllib.error
    import base64

    url = (
        f"http://{RMQ_HOST}:{RMQ_MGMT_PORT}"
        f"/api/queues/%2F/{QUEUE}/get"
    )
    body = json.dumps({
        "count": count,
        "ackmode": "ack_requeue_true",   # peek, keep messages
        "encoding": "auto",
        "truncate": 50000,
    }).encode()

    creds = base64.b64encode(f"{RMQ_USER}:{RMQ_PASS}".encode()).decode()
    req = urllib.request.Request(
        url, data=body, method="POST",
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Basic {creds}",
        },
    )
    try:
        with urllib.request.urlopen(req) as resp:
            raw = json.loads(resp.read())
    except urllib.error.HTTPError as exc:
        print(f"Management API error: {exc.code} {exc.reason}", file=sys.stderr)
        raise

    return [json.loads(item["payload"]) if item.get("payload_encoding") == "string"
            else item for item in raw]


def main():
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--session", default="",
                        help="session name, used only for the default output filename")
    parser.add_argument("--out", default=None,
                        help="output JSON file path (default: motioncor_tasks_{session}.json)")
    parser.add_argument("--peek", action="store_true",
                        help="use Management API to peek without consuming (leaves queue intact)")
    parser.add_argument("--dry-run", action="store_true",
                        help="drain and then requeue (queue unchanged, but momentarily empty)")
    args = parser.parse_args()

    out_path = args.out or _default_output(args.session or "unknown")

    if args.peek:
        print(f"Peeking via Management API ({RMQ_HOST}:{RMQ_MGMT_PORT})...")
        messages = peek_via_mgmt()
    elif args.dry_run:
        print(f"Dry-run drain (messages will be requeued)...")
        messages = drain_queue(dry_run=True)
    else:
        print(f"Draining {QUEUE} on {RMQ_HOST}:{RMQ_PORT}...")
        messages = drain_queue(dry_run=False)

    print(f"Found {len(messages)} message(s).")

    if not messages:
        print("Queue is empty — nothing to record.")
        sys.exit(0)

    os.makedirs(os.path.dirname(os.path.abspath(out_path)), exist_ok=True)
    with open(out_path, "w") as fh:
        json.dump(messages, fh, indent=2, default=str)
    print(f"Saved to: {out_path}")

    # Print a brief summary of what was recorded
    ids = [m.get("id", "?") for m in messages[:5]]
    print(f"First task IDs: {ids}" + (" ..." if len(messages) > 5 else ""))

    image_paths = [m.get("data", {}).get("inputFile") or m.get("data", {}).get("image_path")
                   for m in messages if m.get("data")]
    image_paths = [p for p in image_paths if p]
    if image_paths:
        print(f"Example input file: {image_paths[0]}")


if __name__ == "__main__":
    main()
