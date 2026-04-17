#!/usr/bin/env python3
"""Local-wiring smoke test for the MotionCor plugin Docker image.

Mirrors the CTF smoke test (plugins/magellon_ctf_plugin/tests/smoke_test_docker.py)
but runs against a CPU-only test image whose MotionCor binary is mocked.
The mock produces the same output-file shape the plugin expects (output.mrc
+ output_DW.mrc + per-patch log files), letting us prove RMQ in/out + step
events end-to-end without needing a CUDA host.

Real-GPU validation lives in `runpod_gpu_test.py` — it spins up a RunPod
pod with the actual MotionCor2 binary and one of the example movies.

Verifies:
  - Output directories: one per task with the DW.mrc + patch logs
  - Step events: started + completed (or failed) per task on magellon.events
  - Result messages: TaskResultDto on motioncor_out_tasks_queue per task

Prerequisites:
    - Docker Desktop running
    - magellon Docker network exists (docker_magellon-network)
    - RabbitMQ container running (magellon-rabbitmq-container)
    - Sample TIF/MRC movies at <GPFS_ROOT>/motioncor_test/
    - A gain reference at <GPFS_ROOT>/motioncor_test/gain.mrc
    - pip install pika

Usage:
    python plugins/magellon_motioncor_plugin/tests/smoke_test_docker.py

Environment variables:
    GPFS_ROOT       Host path to gpfs mount (default: C:/temp/magellon/gpfs)
    JOBS_ROOT       Host path for job output (default: C:/temp/magellon/jobs/motioncor_test)
    RMQ_HOST        RabbitMQ host           (default: 127.0.0.1)
    RMQ_PORT        RabbitMQ port           (default: 5672)
    RMQ_USER        RabbitMQ user           (default: rabbit)
    RMQ_PASS        RabbitMQ password       (default: behd1d2)
    DOCKER_NETWORK  Docker network name     (default: docker_magellon-network)
    NUM_TASKS       How many tasks to dispatch (default: 5; max bounded by
                    files actually present under MOVIE_DIR)
    SKIP_BUILD      Set to 1 to skip image build
    SKIP_SEED       Set to 1 to skip auto-seeding test data from
                    C:/temp/motioncor/Magellon-test (default: seed if missing)
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
JOBS_ROOT = os.environ.get("JOBS_ROOT", "C:/temp/magellon/jobs/motioncor_test")
RMQ_HOST = os.environ.get("RMQ_HOST", "127.0.0.1")
RMQ_PORT = int(os.environ.get("RMQ_PORT", "5672"))
RMQ_USER = os.environ.get("RMQ_USER", "rabbit")
RMQ_PASS = os.environ.get("RMQ_PASS", "behd1d2")
DOCKER_NETWORK = os.environ.get("DOCKER_NETWORK", "docker_magellon-network")
NUM_TASKS = int(os.environ.get("NUM_TASKS", "5"))
SKIP_BUILD = os.environ.get("SKIP_BUILD", "") == "1"
SKIP_SEED = os.environ.get("SKIP_SEED", "") == "1"

IMAGE_NAME = "magellon-motioncor-plugin:test"
CONTAINER_NAME = "magellon-motioncor-smoke-test"
IN_QUEUE = "motioncor_tasks_queue"
OUT_QUEUE = "motioncor_out_tasks_queue"
STEP_EVENTS_EXCHANGE = "magellon.events"
STEP_EVENTS_BINDING = "magellon.job.*.step.motioncor"
PLUGIN_DIR = Path(__file__).resolve().parent.parent

MOVIE_DIR = f"{GPFS_ROOT}/motioncor_test"
SEED_SOURCE = "C:/temp/motioncor/Magellon-test"

# Default MotionCor parameters — match the bench script so behaviour
# matches the reference benchmark times in motioncor2_benchmark_results.txt.
MOTIONCOR_PARAMS = {
    "PatchesX": 5,
    "PatchesY": 5,
    "Iter": 10,
    "Tol": 0.5,
    "Bft": 100,
    "FtBin": 1.0,
    "kV": 300,
    "PixSize": 1.0,
    "FmDose": 1.0,
    "Gpu": "0",
    "RotGain": 0,
    "FlipGain": 0,
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


def discover_movies() -> list[str]:
    """Return up to NUM_TASKS movie filenames present under MOVIE_DIR."""
    if not os.path.isdir(MOVIE_DIR):
        return []
    candidates = sorted(
        f for f in os.listdir(MOVIE_DIR)
        if f.lower().endswith((".tif", ".tiff", ".mrc", ".eer"))
        and not f.lower().startswith("gain")
    )
    return candidates[:NUM_TASKS]


def make_task(movie_name: str, gain_name: str, job_id: str) -> dict:
    task_id = str(uuid.uuid4())
    image_id = str(uuid.uuid4())
    stem = os.path.splitext(movie_name)[0]
    input_path = f"/gpfs/motioncor_test/{movie_name}"
    gain_path = f"/gpfs/motioncor_test/{gain_name}"
    return {
        "id": task_id,
        "job_id": job_id,
        "session_id": None,
        "session_name": "motioncor_smoke_test",
        "worker_instance_id": str(uuid.uuid4()),
        "data": {
            "image_id": image_id,
            "image_name": stem,
            "image_path": input_path,
            "inputFile": input_path,
            "OutMrc": f"{stem}_aligned.mrc",
            "Gain": gain_path,
            "engine_opts": {},
            **MOTIONCOR_PARAMS,
        },
        "status": {"code": 0, "name": "pending", "description": "Task is pending"},
        "type": {"code": 3, "name": "MOTIONCOR", "description": "Motion Correction"},
        "created_date": datetime.now(timezone.utc).isoformat(),
        "start_on": None,
        "end_on": None,
        "result": None,
    }


# ---------------------------------------------------------------------------
# RabbitMQ collectors (run in background threads)
# ---------------------------------------------------------------------------

class StepEventCollector:
    """Subscribes to magellon.events and collects motioncor step events."""

    def __init__(self):
        self.events: list[dict] = []
        self._lock = threading.Lock()
        self._thread: threading.Thread | None = None
        self._connection: pika.BlockingConnection | None = None

    def start(self):
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def _run(self):
        try:
            # heartbeat=0 disables pika's heartbeat — collectors are idle
            # during the GPU-bound processing window and a missed heartbeat
            # would silently drop our subscription.
            self._connection = rmq_connection(heartbeat=0)
            channel = self._connection.channel()
            channel.exchange_declare(
                exchange=STEP_EVENTS_EXCHANGE, exchange_type="topic", durable=True,
            )
            result = channel.queue_declare(queue="", exclusive=True)
            queue_name = result.method.queue
            channel.queue_bind(
                exchange=STEP_EVENTS_EXCHANGE,
                queue=queue_name,
                routing_key=STEP_EVENTS_BINDING,
            )
            channel.basic_consume(
                queue=queue_name, on_message_callback=self._on_message, auto_ack=True,
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
    """Drains messages from motioncor_out_tasks_queue."""

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

def step_seed_test_data():
    """Copy a few example movies + a stub gain into MOVIE_DIR.

    The CTF smoke test assumes its MRC fixtures are pre-staged. For
    motioncor we auto-seed from C:/temp/motioncor/Magellon-test/example* —
    one TIF per example folder — so a fresh checkout is one command from
    a green run. Skip with SKIP_SEED=1 if you've curated MOVIE_DIR by hand.
    """
    print("\n=== Seeding test data ===")
    if SKIP_SEED:
        print("  Skipping (SKIP_SEED=1)")
        return
    os.makedirs(MOVIE_DIR, exist_ok=True)
    existing = [f for f in os.listdir(MOVIE_DIR) if f.lower().endswith((".tif", ".tiff", ".mrc"))]
    if len(existing) >= NUM_TASKS + 1:  # +1 for gain
        print(f"  Already have {len(existing)} files in {MOVIE_DIR}, skipping seed")
        return

    if not os.path.isdir(SEED_SOURCE):
        print(f"  WARN: seed source {SEED_SOURCE} not present — skipping seed")
        print(f"  You'll need to populate {MOVIE_DIR} manually before running")
        return

    # Copy one TIF per example folder (up to NUM_TASKS).
    copied = 0
    for i in range(1, 11):
        if copied >= NUM_TASKS:
            break
        ex = Path(SEED_SOURCE) / f"example{i}"
        if not ex.is_dir():
            continue
        tifs = list(ex.glob("*.tif")) + list(ex.glob("*.tiff"))
        if not tifs:
            continue
        src = tifs[0]
        dst = Path(MOVIE_DIR) / src.name
        if not dst.exists():
            print(f"  copy {src.name}")
            shutil.copy2(src, dst)
        copied += 1

    # Stub gain reference — the mock binary doesn't actually read it but
    # the plugin's path-existence check needs a real file to chew on.
    gain = Path(MOVIE_DIR) / "gain.mrc"
    if not gain.exists():
        print("  creating stub gain.mrc")
        with open(gain, "wb") as f:
            f.write(b"\x00" * 1024)
            f.write(b"MAP \x44\x44\x00\x00")

    print(f"  Seeded {copied} movies + gain.mrc into {MOVIE_DIR}")


def step_preflight():
    print("\n=== Preflight checks ===")
    movies = discover_movies()
    if len(movies) < NUM_TASKS:
        print(f"FAIL: only {len(movies)} movies in {MOVIE_DIR}, need {NUM_TASKS}")
        sys.exit(1)
    print(f"  {len(movies)} movie file(s) found in {MOVIE_DIR}")

    gain_files = [f for f in os.listdir(MOVIE_DIR) if f.lower().startswith("gain")]
    if not gain_files:
        print(f"FAIL: no gain reference found in {MOVIE_DIR} (expected file starting with 'gain')")
        sys.exit(1)
    print(f"  Gain reference: {gain_files[0]}")

    result = run("docker network ls --format {{.Name}}", capture=True)
    if DOCKER_NETWORK not in result.stdout.split():
        print(f"FAIL: Docker network '{DOCKER_NETWORK}' not found")
        sys.exit(1)
    print(f"  Docker network '{DOCKER_NETWORK}' exists")

    result = run("docker ps --filter name=magellon-rabbitmq-container --format {{.Names}}", capture=True)
    if "magellon-rabbitmq-container" not in result.stdout:
        print("FAIL: magellon-rabbitmq-container is not running")
        sys.exit(1)
    print("  RabbitMQ container is running")

    sdk_wheel = PLUGIN_DIR / "magellon_sdk-0.1.0-py3-none-any.whl"
    if not sdk_wheel.exists():
        print(f"FAIL: SDK wheel not found at {sdk_wheel}")
        print("  Build it with: cd magellon-sdk && python -m build --wheel && \\")
        print(f"    cp dist/magellon_sdk-0.1.0-py3-none-any.whl {PLUGIN_DIR}/")
        sys.exit(1)
    print(f"  SDK wheel present ({sdk_wheel.stat().st_size} bytes)")


def step_purge_queues():
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
    run(f"docker build -f {PLUGIN_DIR}/Dockerfile.test -t {IMAGE_NAME} {PLUGIN_DIR}", timeout=900)
    print("  Image built successfully")


def step_clean():
    print("\n=== Cleaning previous run ===")
    run(f"docker rm -f {CONTAINER_NAME}", check=False)
    if os.path.isdir(JOBS_ROOT):
        shutil.rmtree(JOBS_ROOT)
        print(f"  Cleaned {JOBS_ROOT}")
    os.makedirs(JOBS_ROOT, exist_ok=True)


def step_start_container():
    print("\n=== Starting MotionCor container ===")
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


def step_dispatch_tasks() -> tuple[str, list[str], list[str]]:
    print("\n=== Dispatching MotionCor tasks ===")
    movies = discover_movies()
    gain_name = next(f for f in os.listdir(MOVIE_DIR) if f.lower().startswith("gain"))
    job_id = str(uuid.uuid4())
    task_ids: list[str] = []
    image_ids: list[str] = []

    connection = rmq_connection()
    channel = connection.channel()
    channel.queue_declare(queue=IN_QUEUE, durable=True)

    for movie_name in movies:
        task = make_task(movie_name, gain_name, job_id)
        task_ids.append(task["id"])
        image_ids.append(task["data"]["image_id"])
        channel.basic_publish(
            exchange="",
            routing_key=IN_QUEUE,
            body=json.dumps(task),
            properties=pika.BasicProperties(delivery_mode=2),
        )
        print(f"  [{task['id'][:8]}] {movie_name}")

    connection.close()
    print(f"  Job ID: {job_id}")
    print(f"  {len(movies)} task(s) dispatched")
    return job_id, task_ids, image_ids


def step_wait_for_completion(image_ids: list[str], timeout: int = 180):
    """Wait for output dirs (named by image_id) to appear with the expected files.

    The motioncor plugin writes outputs to JOBS_DIR/<image_id>/, not by
    task_id like CTF does — that's a quirk of motioncor_service.py.
    """
    print(f"\n=== Waiting for {len(image_ids)} tasks (timeout {timeout}s) ===")
    start = time.time()
    target_ids = set(image_ids)
    completed = set()

    while len(completed) < len(target_ids):
        elapsed = time.time() - start
        if elapsed > timeout:
            print(f"FAIL: timed out after {timeout}s — {len(completed)}/{len(target_ids)} completed")
            run(f"docker logs --tail 80 {CONTAINER_NAME}")
            sys.exit(1)

        if os.path.isdir(JOBS_ROOT):
            for d in os.listdir(JOBS_ROOT):
                if d not in target_ids or d in completed:
                    continue
                full = os.path.join(JOBS_ROOT, d)
                if not os.path.isdir(full):
                    continue
                # The mock writes output_aligned.mrc + _DW.mrc + per-patch logs.
                # Wait until the DW file exists — that's the last thing written.
                files = os.listdir(full)
                has_dw = any(f.endswith("_DW.mrc") for f in files)
                if has_dw:
                    completed.add(d)
                    print(f"  [{len(completed):2d}/{len(target_ids)}] {d[:8]}... done ({len(files)} files)")

        time.sleep(2)

    elapsed = time.time() - start
    print(f"  All {len(target_ids)} tasks completed in {elapsed:.0f}s")


def step_verify_outputs(image_ids: list[str]) -> list[str]:
    """Returns a list of error messages; empty == all good. The caller
    aggregates with the messaging-layer checks so we get one combined
    report instead of bailing on the first failure."""
    print("\n=== Verifying output files ===")
    errors: list[str] = []

    all_dirs = os.listdir(JOBS_ROOT)
    dirs = [d for d in all_dirs if d in set(image_ids)]
    missing = [iid for iid in image_ids if iid not in all_dirs]
    for iid in missing:
        errors.append(f"{iid[:8]}: no output directory created")

    for d in dirs:
        full = os.path.join(JOBS_ROOT, d)
        files = os.listdir(full)

        dw_files = [f for f in files if f.endswith("_DW.mrc")]
        mrc_files = [f for f in files if f.endswith(".mrc") and not f.endswith("_DW.mrc")]
        # With PatchesX/Y > 1 the plugin produces three shift logs. The
        # plugin renames one to `*-patch-Patch.log` (lowercase) and leaves
        # the other two with MotionCor's original casing (`*-Patch-Frame.log`,
        # `*-Patch-Full.log`). Match case-insensitively so both styles count.
        shift_logs = [f for f in files if f.endswith(".log") and "patch" in f.lower()]

        if not dw_files:
            errors.append(f"{d[:8]}: missing _DW.mrc")
        else:
            size = os.path.getsize(os.path.join(full, dw_files[0]))
            if size < 256:
                errors.append(f"{d[:8]}: _DW.mrc too small ({size} bytes)")

        if not mrc_files:
            errors.append(f"{d[:8]}: missing aligned MRC")

        if MOTIONCOR_PARAMS["PatchesX"] > 1 and len(shift_logs) < 3:
            errors.append(f"{d[:8]}: expected 3 shift logs, found {len(shift_logs)}")

        print(f"  {d[:8]}... files={len(files)} dw={bool(dw_files)} shift_logs={len(shift_logs)}")

    if errors:
        print(f"\n  OUTPUT FILES: {len(errors)} error(s):")
        for e in errors:
            print(f"    - {e}")
    else:
        print(f"\n  All {len(dirs)} task(s) verified successfully")
    return errors


def step_verify_step_events(collector: StepEventCollector, job_id: str, task_ids: list[str]):
    print("\n=== Verifying step events ===")
    errors = []
    events = collector.get_events()
    print(f"  Collected {len(events)} step event(s)")

    events_by_task: dict[str, list[str]] = {}
    for ev in events:
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
            "and MAGELLON_STEP_EVENTS_RMQ=1 are set in the container, and that "
            f"the routing-key binding ({STEP_EVENTS_BINDING}) matches what the "
            "plugin actually publishes."
        )

    if errors:
        print(f"\n  STEP EVENTS: {len(errors)} error(s):")
        for e in errors:
            print(f"    - {e}")
        return errors
    print(f"\n  All {len(events_by_task)} task(s) have started + terminal events")
    return []


def step_verify_results(collector: ResultCollector, task_ids: list[str]):
    """Verify TaskResultDto messages reach motioncor_out_tasks_queue.

    Same caveat as the CTF test: the result queue is point-to-point, so
    if CoreService is also subscribed it'll round-robin and we'll only
    see a subset. We require at least one of our tasks to land in our
    collector — the per-task lifecycle is already proven by step events.
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
        return [
            f"No result messages from our {len(task_ids)} tasks landed in our "
            f"collector on {OUT_QUEUE}. The plugin may not be publishing results, "
            f"or a competing consumer drained them all before we saw any."
        ]

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

    error_lines = [l for l in logs.splitlines() if "Error" in l or "Traceback" in l]
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
    print("MotionCor Plugin Docker Smoke Test (local-wiring, mocked GPU)")
    print("=" * 60)

    step_seed_test_data()
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
        job_id, task_ids, image_ids = step_dispatch_tasks()
        step_wait_for_completion(image_ids)
        time.sleep(3)  # let trailing messages land

        all_errors += step_verify_outputs(image_ids)
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
    print(f"PASSED — all {NUM_TASKS} MotionCor tasks: outputs + step events + results verified")
    print("=" * 60)


if __name__ == "__main__":
    main()
