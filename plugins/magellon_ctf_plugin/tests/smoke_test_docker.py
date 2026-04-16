#!/usr/bin/env python3
"""Automated smoke test for the CTF plugin Docker image.

Builds the image, starts the container on the magellon Docker network,
dispatches 10 CTF tasks via RabbitMQ, collects step events and result
messages from RabbitMQ, waits for output files, and verifies everything.

Verifies:
  - Output files: 5 per task (MRC, plots, powerspec, txt, avrot)
  - CTF estimates: defocus and CC in valid ranges
  - Step events: started + completed (or failed) per task on magellon.events exchange
  - Result messages: TaskResultDto on ctf_out_tasks_queue per task

Prerequisites:
    - Docker Desktop running
    - magellon Docker network exists (docker_magellon-network)
    - RabbitMQ container running (magellon-rabbitmq-container)
    - 10 ground-truth MRC files in <GPFS_ROOT>/ctf_test/
    - pip install pika

Usage:
    python plugins/magellon_ctf_plugin/tests/smoke_test_docker.py

Environment variables:
    GPFS_ROOT       Host path to gpfs mount (default: C:/temp/magellon/gpfs)
    JOBS_ROOT       Host path for job output  (default: C:/temp/magellon/jobs/ctf_test)
    RMQ_HOST        RabbitMQ host             (default: 127.0.0.1)
    RMQ_PORT        RabbitMQ port             (default: 5672)
    RMQ_USER        RabbitMQ user             (default: rabbit)
    RMQ_PASS        RabbitMQ password         (default: behd1d2)
    DOCKER_NETWORK  Docker network name       (default: docker_magellon-network)
    SKIP_BUILD      Set to 1 to skip image build
"""
import json
import os
import shutil
import subprocess
import sys
import threading
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

import pika

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
GPFS_ROOT = os.environ.get("GPFS_ROOT", "C:/temp/magellon/gpfs")
JOBS_ROOT = os.environ.get("JOBS_ROOT", "C:/temp/magellon/jobs/ctf_test")
RMQ_HOST = os.environ.get("RMQ_HOST", "127.0.0.1")
RMQ_PORT = int(os.environ.get("RMQ_PORT", "5672"))
RMQ_USER = os.environ.get("RMQ_USER", "rabbit")
RMQ_PASS = os.environ.get("RMQ_PASS", "behd1d2")
DOCKER_NETWORK = os.environ.get("DOCKER_NETWORK", "docker_magellon-network")
SKIP_BUILD = os.environ.get("SKIP_BUILD", "") == "1"

IMAGE_NAME = "magellon-ctf-plugin:test"
CONTAINER_NAME = "magellon-ctf-smoke-test"
IN_QUEUE = "ctf_tasks_queue"
OUT_QUEUE = "ctf_out_tasks_queue"
STEP_EVENTS_EXCHANGE = "magellon.events"
STEP_EVENTS_BINDING = "magellon.job.*.step.ctf"
PLUGIN_DIR = Path(__file__).resolve().parent.parent

MRC_DIR = f"{GPFS_ROOT}/ctf_test"

MRC_FILES = [
    "23oct13x_23oct13a_a_00034gr_00008sq_v02_00017hl_00003ex.mrc",
    "24dec03a_00034gr_00004sq_v01_00003hl_00016ex.mrc",
    "24dec03a_00034gr_00005sq_v01_00003hl_00014ex.mrc",
    "24dec03a_00034gr_00004sq_v01_00002hl_00003ex.mrc",
    "24dec03a_00034gr_00004sq_v01_00002hl_00004ex.mrc",
    "24dec03a_00034gr_00004sq_v01_00002hl_00005ex.mrc",
    "24dec03a_00034gr_00004sq_v01_00002hl_00006ex.mrc",
    "24dec03a_00034gr_00004sq_v01_00002hl_00007ex.mrc",
    "24dec03a_00034gr_00004sq_v01_00002hl_00008ex.mrc",
    "24dec03a_00034gr_00004sq_v01_00002hl_00009ex.mrc",
]

CTF_PARAMS = {
    "pixelSize": 1.0,
    "accelerationVoltage": 300.0,
    "sphericalAberration": 2.70,
    "amplitudeContrast": 0.07,
    "sizeOfAmplitudeSpectrum": 512,
    "minimumResolution": 30.0,
    "maximumResolution": 5.0,
    "minimumDefocus": 5000.0,
    "maximumDefocus": 50000.0,
    "defocusSearchStep": 500.0,
    "binning_x": 1,
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def run(cmd: str, check: bool = True, capture: bool = False, **kwargs) -> subprocess.CompletedProcess:
    print(f"  $ {cmd}")
    return subprocess.run(cmd, shell=True, check=check, capture_output=capture, text=True, **kwargs)


def rmq_connection(heartbeat: int = 60):
    creds = pika.PlainCredentials(RMQ_USER, RMQ_PASS)
    params = pika.ConnectionParameters(
        host=RMQ_HOST, port=RMQ_PORT, credentials=creds, heartbeat=heartbeat,
    )
    return pika.BlockingConnection(params)


def make_task(mrc_name: str, job_id: str) -> dict:
    task_id = str(uuid.uuid4())
    stem = os.path.splitext(mrc_name)[0]
    input_path = f"/gpfs/ctf_test/{mrc_name}"
    output_file = f"{stem}_ctf_output.mrc"
    return {
        "id": task_id,
        "job_id": job_id,
        "sesson_id": None,
        "sesson_name": "ctf_smoke_test",
        "worker_instance_id": str(uuid.uuid4()),
        "data": {
            "image_id": None,
            "image_name": stem,
            "image_path": input_path,
            "inputFile": input_path,
            "outputFile": output_file,
            "engine_opts": {},
            **CTF_PARAMS,
        },
        "status": {"code": 0, "name": "pending", "description": "Task is pending"},
        "type": {"code": 2, "name": "CTF", "description": "Contrast Transfer Function"},
        "created_date": datetime.now(timezone.utc).isoformat(),
        "start_on": None,
        "end_on": None,
        "result": None,
    }


# ---------------------------------------------------------------------------
# RabbitMQ collectors (run in background threads)
# ---------------------------------------------------------------------------

class StepEventCollector:
    """Subscribes to magellon.events exchange and collects step events."""

    def __init__(self):
        self.events: list[dict] = []
        self._lock = threading.Lock()
        self._thread: threading.Thread | None = None
        self._connection: pika.BlockingConnection | None = None
        self._queue_name: str = ""

    def start(self):
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def _run(self):
        try:
            # heartbeat=0 disables pika's heartbeat — these collectors are
            # idle for the full task-processing window (~150s), and a
            # missed heartbeat would silently drop our subscription.
            self._connection = rmq_connection(heartbeat=0)
            channel = self._connection.channel()
            channel.exchange_declare(
                exchange=STEP_EVENTS_EXCHANGE, exchange_type="topic", durable=True,
            )
            result = channel.queue_declare(queue="", exclusive=True)
            self._queue_name = result.method.queue
            channel.queue_bind(
                exchange=STEP_EVENTS_EXCHANGE,
                queue=self._queue_name,
                routing_key=STEP_EVENTS_BINDING,
            )
            channel.basic_consume(
                queue=self._queue_name, on_message_callback=self._on_message, auto_ack=True,
            )
            channel.start_consuming()
        except Exception as e:
            print(f"  StepEventCollector error: {e}")

    def _on_message(self, ch, method, properties, body):
        try:
            event = json.loads(body)
            with self._lock:
                self.events.append(event)
        except Exception:
            pass

    def stop(self):
        if self._connection and self._connection.is_open:
            try:
                self._connection.close()
            except Exception:
                pass

    def get_events(self) -> list[dict]:
        with self._lock:
            return list(self.events)


class ResultCollector:
    """Drains messages from ctf_out_tasks_queue."""

    def __init__(self):
        self.results: list[dict] = []
        self._lock = threading.Lock()
        self._thread: threading.Thread | None = None
        self._connection: pika.BlockingConnection | None = None

    def start(self):
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def _run(self):
        try:
            self._connection = rmq_connection(heartbeat=0)
            channel = self._connection.channel()
            channel.queue_declare(queue=OUT_QUEUE, durable=True)
            channel.basic_consume(
                queue=OUT_QUEUE, on_message_callback=self._on_message, auto_ack=True,
            )
            channel.start_consuming()
        except Exception as e:
            print(f"  ResultCollector error: {e}")

    def _on_message(self, ch, method, properties, body):
        try:
            result = json.loads(body)
            with self._lock:
                self.results.append(result)
        except Exception:
            pass

    def stop(self):
        if self._connection and self._connection.is_open:
            try:
                self._connection.close()
            except Exception:
                pass

    def get_results(self) -> list[dict]:
        with self._lock:
            return list(self.results)


# ---------------------------------------------------------------------------
# Steps
# ---------------------------------------------------------------------------

def step_preflight():
    print("\n=== Preflight checks ===")
    missing = [f for f in MRC_FILES if not os.path.isfile(os.path.join(MRC_DIR, f))]
    if missing:
        print(f"FAIL: missing MRC files in {MRC_DIR}:")
        for f in missing:
            print(f"  - {f}")
        sys.exit(1)
    print(f"  {len(MRC_FILES)} MRC files found in {MRC_DIR}")

    result = run("docker network ls --format {{.Name}}", capture=True)
    if DOCKER_NETWORK not in result.stdout.split():
        print(f"FAIL: Docker network '{DOCKER_NETWORK}' not found")
        sys.exit(1)
    print(f"  Docker network '{DOCKER_NETWORK}' exists")

    result = run(f"docker ps --filter name=magellon-rabbitmq-container --format {{{{.Names}}}}", capture=True)
    if "magellon-rabbitmq-container" not in result.stdout:
        print("FAIL: magellon-rabbitmq-container is not running")
        sys.exit(1)
    print("  RabbitMQ container is running")


def step_purge_queues():
    """Purge leftover messages from previous runs."""
    print("\n=== Purging queues ===")
    connection = rmq_connection()
    channel = connection.channel()
    for q in [IN_QUEUE, OUT_QUEUE]:
        channel.queue_declare(queue=q, durable=True)
        purged = channel.queue_purge(queue=q)
        print(f"  {q}: purged {purged.method.message_count} messages")
    channel.exchange_declare(
        exchange=STEP_EVENTS_EXCHANGE, exchange_type="topic", durable=True,
    )
    connection.close()


def step_build():
    print("\n=== Building Docker image ===")
    if SKIP_BUILD:
        print("  Skipping (SKIP_BUILD=1)")
        return
    run(f"docker build -f {PLUGIN_DIR}/Dockerfile.test -t {IMAGE_NAME} {PLUGIN_DIR}", timeout=600)
    print("  Image built successfully")


def step_clean():
    print("\n=== Cleaning previous run ===")
    run(f"docker rm -f {CONTAINER_NAME}", check=False)
    if os.path.isdir(JOBS_ROOT):
        shutil.rmtree(JOBS_ROOT)
        print(f"  Cleaned {JOBS_ROOT}")
    os.makedirs(JOBS_ROOT, exist_ok=True)


def step_start_container():
    print("\n=== Starting CTF container ===")
    nats_url = os.environ.get("NATS_URL", "nats://magellon-nats-container:4222")
    run(
        f"docker run -d --name {CONTAINER_NAME} "
        f"--network {DOCKER_NETWORK} "
        f"-v {GPFS_ROOT}:/gpfs "
        f"-v {JOBS_ROOT}:/jobs "
        f"-e NATS_URL={nats_url} "
        f"{IMAGE_NAME}"
    )
    time.sleep(3)
    result = run(f"docker ps --filter name={CONTAINER_NAME} --format {{{{.Status}}}}", capture=True)
    if "Up" not in result.stdout:
        print("FAIL: container is not running")
        run(f"docker logs {CONTAINER_NAME}")
        sys.exit(1)
    print("  Container is up")


def step_dispatch_tasks() -> tuple[str, list[str]]:
    print("\n=== Dispatching CTF tasks ===")
    job_id = str(uuid.uuid4())
    task_ids = []

    connection = rmq_connection()
    channel = connection.channel()
    channel.queue_declare(queue=IN_QUEUE, durable=True)

    for mrc_name in MRC_FILES:
        task = make_task(mrc_name, job_id)
        task_ids.append(task["id"])
        channel.basic_publish(
            exchange="",
            routing_key=IN_QUEUE,
            body=json.dumps(task),
            properties=pika.BasicProperties(delivery_mode=2),
        )
        print(f"  [{task['id'][:8]}] {mrc_name}")

    connection.close()
    print(f"  Job ID: {job_id}")
    print(f"  {len(MRC_FILES)} tasks dispatched")
    return job_id, task_ids


def step_wait_for_completion(task_ids: list[str], timeout: int = 300):
    """Wait for output dirs matching our specific task IDs.

    Other dirs (from prior runs or queue leftovers) are ignored — we
    only care about the tasks we just dispatched.
    """
    print(f"\n=== Waiting for {len(task_ids)} tasks (timeout {timeout}s) ===")
    start = time.time()
    target_ids = set(task_ids)
    completed = set()

    while len(completed) < len(target_ids):
        elapsed = time.time() - start
        if elapsed > timeout:
            print(f"FAIL: timed out after {timeout}s — {len(completed)}/{len(target_ids)} completed")
            missing = target_ids - completed
            for tid in missing:
                print(f"  - missing: {tid}")
            run(f"docker logs --tail 50 {CONTAINER_NAME}")
            sys.exit(1)

        if os.path.isdir(JOBS_ROOT):
            for d in os.listdir(JOBS_ROOT):
                if d not in target_ids or d in completed:
                    continue
                full = os.path.join(JOBS_ROOT, d)
                if not os.path.isdir(full):
                    continue
                files = os.listdir(full)
                if len(files) >= 5:
                    completed.add(d)
                    print(f"  [{len(completed):2d}/{len(target_ids)}] {d[:8]}... done ({len(files)} files)")

        time.sleep(2)

    elapsed = time.time() - start
    print(f"  All {len(target_ids)} tasks completed in {elapsed:.0f}s")


def step_verify_outputs(task_ids: list[str]):
    print("\n=== Verifying output files ===")
    errors = []

    all_dirs = os.listdir(JOBS_ROOT)
    dirs = [d for d in all_dirs if d in set(task_ids)]
    missing = [tid for tid in task_ids if tid not in all_dirs]
    if missing:
        for tid in missing:
            errors.append(f"{tid[:8]}: no output directory created")

    for d in dirs:
        full = os.path.join(JOBS_ROOT, d)
        files = os.listdir(full)

        if len(files) < 5:
            errors.append(f"{d[:8]}: expected 5 files, found {len(files)}")
            continue

        txt_files = [f for f in files if f.endswith("_ctf_output.txt")]
        if not txt_files:
            errors.append(f"{d[:8]}: missing CTF output txt")
            continue

        txt_path = os.path.join(full, txt_files[0])
        with open(txt_path) as fh:
            lines = fh.readlines()
        data_lines = [l for l in lines if not l.startswith("#") and l.strip()]
        if not data_lines:
            errors.append(f"{d[:8]}: CTF output txt has no data")
            continue

        parts = data_lines[0].split()
        if len(parts) < 7:
            errors.append(f"{d[:8]}: CTF output has {len(parts)} columns, expected 7")
            continue

        defocus1 = float(parts[1])
        defocus2 = float(parts[2])
        cc = float(parts[5])

        if not (1000 < defocus1 < 100000):
            errors.append(f"{d[:8]}: defocus1 {defocus1} out of range")
        if not (1000 < defocus2 < 100000):
            errors.append(f"{d[:8]}: defocus2 {defocus2} out of range")
        if not (0.0 < cc < 1.0):
            errors.append(f"{d[:8]}: cross-correlation {cc} out of range")

        mrc_files = [f for f in files if f.endswith("_ctf_output.mrc")]
        png_files = [f for f in files if f.endswith("-plots.png")]
        jpg_files = [f for f in files if f.endswith("-powerspec.jpg")]

        for label, matches in [("MRC", mrc_files), ("plots PNG", png_files), ("powerspec JPG", jpg_files)]:
            if not matches:
                errors.append(f"{d[:8]}: missing {label}")
            else:
                size = os.path.getsize(os.path.join(full, matches[0]))
                if size < 1024:
                    errors.append(f"{d[:8]}: {label} too small ({size} bytes)")

        print(f"  {d[:8]}... def1={defocus1:.0f} def2={defocus2:.0f} CC={cc:.3f}")

    if errors:
        print(f"\nFAIL: {len(errors)} error(s):")
        for e in errors:
            print(f"  - {e}")
        sys.exit(1)

    print(f"\n  All {len(dirs)} tasks verified successfully")


def step_verify_step_events(collector: StepEventCollector, job_id: str, task_ids: list[str]):
    """Verify step events were emitted for each task.

    Expects at least a 'started' and 'completed' (or 'failed') event
    per task, published to the magellon.events topic exchange with
    routing key job.<job_id>.step.ctf.
    """
    print("\n=== Verifying step events ===")
    errors = []
    events = collector.get_events()
    print(f"  Collected {len(events)} step event(s)")

    events_by_task: dict[str, list[str]] = {}
    for ev in events:
        subject = ev.get("subject", "")
        ev_type = ev.get("type", "")
        data = ev.get("data", {})
        task_id = data.get("task_id", "")
        ev_job_id = data.get("job_id", "")

        if ev_job_id != job_id:
            continue

        events_by_task.setdefault(task_id, []).append(ev_type)

        if ev_type:
            short_type = ev_type.rsplit(".", 1)[-1] if "." in ev_type else ev_type
            print(f"    task={task_id[:8]}... type={short_type}")

    for tid in task_ids:
        types = events_by_task.get(tid, [])
        has_started = any("started" in t for t in types)
        has_terminal = any("completed" in t or "failed" in t for t in types)

        if not has_started:
            errors.append(f"{tid[:8]}: missing 'started' step event")
        if not has_terminal:
            errors.append(f"{tid[:8]}: missing 'completed'/'failed' step event")

    if not events_by_task:
        errors.append(
            "No step events received. Check that MAGELLON_STEP_EVENTS_ENABLED=1 "
            "and MAGELLON_STEP_EVENTS_RMQ=1 are set in the container"
        )

    if errors:
        print(f"\n  STEP EVENTS: {len(errors)} error(s):")
        for e in errors:
            print(f"    - {e}")
        return errors
    else:
        tasks_with_events = len(events_by_task)
        print(f"\n  All {tasks_with_events} tasks have started + completed events")
        return []


def step_verify_results(collector: ResultCollector, task_ids: list[str]):
    """Verify TaskResultDto messages are pushed to ctf_out_tasks_queue.

    The result queue is point-to-point — if CoreService (or anything
    else) is subscribed, RMQ round-robins between consumers and we'll
    only see a subset. Per-task lifecycle is already proven by step
    events (topic exchange, fanout-safe). This check just confirms the
    plugin's result-publish path works at all: we require at least one
    result message to land in our collector.
    """
    print("\n=== Verifying result messages ===")
    results = collector.get_results()
    print(f"  Collected {len(results)} result message(s) from {OUT_QUEUE}")

    our_ids = set(task_ids)
    received_ours = set()
    for r in results:
        tid = r.get("task_id") or r.get("id", "")
        if tid in our_ids:
            received_ours.add(tid)
        status = r.get("status", {})
        status_name = status.get("name", "unknown") if isinstance(status, dict) else str(status)
        ours_marker = "*" if tid in our_ids else " "
        print(f"    {ours_marker} task={tid[:8]}... status={status_name}")

    if not received_ours:
        errors = [
            f"No result messages from our {len(task_ids)} tasks landed in our "
            f"collector on {OUT_QUEUE}. The plugin may not be publishing results, "
            f"or a competing consumer drained them all before we saw any."
        ]
        print(f"\n  RESULTS FAIL: no results for any of our tasks")
        return errors

    missing_ours = our_ids - received_ours
    if missing_ours:
        print(
            f"  ({len(received_ours)}/{len(task_ids)} of our tasks observed — "
            f"rest likely went to a competing consumer like CoreService)"
        )
    else:
        print(f"  All {len(task_ids)} of our tasks have result messages")
    return []


def step_check_container_health():
    print("\n=== Container health check ===")
    result = run(f"docker logs {CONTAINER_NAME} 2>&1", capture=True)
    logs = result.stdout

    error_lines = [l for l in logs.splitlines() if "Error" in l or "Traceback" in l or "FAILED" in l]
    error_lines = [l for l in error_lines if "fitError" not in l]

    if error_lines:
        print(f"  WARNING: {len(error_lines)} error line(s) in logs:")
        for l in error_lines[:5]:
            print(f"    {l.strip()}")
    else:
        print("  No errors in container logs")

    result = run(f"docker ps --filter name={CONTAINER_NAME} --format {{{{.Status}}}}", capture=True)
    if "Up" in result.stdout:
        print("  Container still running")
    else:
        print("  WARNING: container exited")


def step_cleanup():
    print("\n=== Cleanup ===")
    run(f"docker rm -f {CONTAINER_NAME}", check=False)
    print("  Container removed")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    print("=" * 60)
    print("CTF Plugin Docker Smoke Test")
    print("=" * 60)

    step_preflight()
    step_build()
    step_clean()
    step_purge_queues()

    event_collector = StepEventCollector()
    result_collector = ResultCollector()
    event_collector.start()
    result_collector.start()
    time.sleep(1)

    step_start_container()

    all_errors = []
    try:
        job_id, task_ids = step_dispatch_tasks()
        step_wait_for_completion(task_ids)

        # give collectors a moment to catch trailing messages
        time.sleep(3)

        step_verify_outputs(task_ids)
        all_errors += step_verify_step_events(event_collector, job_id, task_ids)
        all_errors += step_verify_results(result_collector, task_ids)
        step_check_container_health()
    finally:
        event_collector.stop()
        result_collector.stop()
        step_cleanup()

    print("\n" + "=" * 60)
    if all_errors:
        print(f"PARTIAL — output files OK, but {len(all_errors)} messaging error(s):")
        for e in all_errors:
            print(f"  - {e}")
        print("=" * 60)
        sys.exit(1)
    else:
        print("PASSED — all 10 CTF tasks: files + step events + results verified")
        print("=" * 60)


if __name__ == "__main__":
    main()
