#!/usr/bin/env python3
"""Automated smoke test for the CTF plugin Docker image.

Builds the image, starts the container on the magellon Docker network,
dispatches 10 CTF tasks via RabbitMQ, waits for results on the output
queue, and verifies that each task produced the expected output files.

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

EXPECTED_EXTENSIONS = [
    "_ctf_output.mrc",
    "_ctf_output.mrc-plots.png",
    "_ctf_output.mrc-powerspec.jpg",
    "_ctf_output.txt",
    "_ctf_output_avrot.txt",
]

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def run(cmd: str, check: bool = True, capture: bool = False, **kwargs) -> subprocess.CompletedProcess:
    print(f"  $ {cmd}")
    return subprocess.run(cmd, shell=True, check=check, capture_output=capture, text=True, **kwargs)


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
    run(
        f"docker run -d --name {CONTAINER_NAME} "
        f"--network {DOCKER_NETWORK} "
        f"-v {GPFS_ROOT}:/gpfs "
        f"-v {JOBS_ROOT}:/jobs "
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

    creds = pika.PlainCredentials(RMQ_USER, RMQ_PASS)
    params = pika.ConnectionParameters(host=RMQ_HOST, port=RMQ_PORT, credentials=creds)
    connection = pika.BlockingConnection(params)
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


def step_wait_for_completion(task_ids: list[str], timeout: int = 180):
    print(f"\n=== Waiting for {len(task_ids)} tasks (timeout {timeout}s) ===")
    start = time.time()
    completed_dirs = set()

    while len(completed_dirs) < len(task_ids):
        elapsed = time.time() - start
        if elapsed > timeout:
            print(f"FAIL: timed out after {timeout}s — {len(completed_dirs)}/{len(task_ids)} completed")
            run(f"docker logs --tail 50 {CONTAINER_NAME}")
            sys.exit(1)

        if os.path.isdir(JOBS_ROOT):
            for d in os.listdir(JOBS_ROOT):
                full = os.path.join(JOBS_ROOT, d)
                if os.path.isdir(full) and d not in completed_dirs:
                    files = os.listdir(full)
                    if len(files) >= 5:
                        completed_dirs.add(d)
                        print(f"  [{len(completed_dirs):2d}/{len(task_ids)}] {d[:8]}... done ({len(files)} files)")

        time.sleep(2)

    elapsed = time.time() - start
    print(f"  All {len(task_ids)} tasks completed in {elapsed:.0f}s")


def step_verify_outputs(task_ids: list[str]):
    print("\n=== Verifying output files ===")
    errors = []

    dirs = os.listdir(JOBS_ROOT)
    if len(dirs) != len(task_ids):
        errors.append(f"Expected {len(task_ids)} output dirs, found {len(dirs)}")

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
    step_start_container()

    try:
        job_id, task_ids = step_dispatch_tasks()
        step_wait_for_completion(task_ids)
        step_verify_outputs(task_ids)
        step_check_container_health()
    finally:
        step_cleanup()

    print("\n" + "=" * 60)
    print("PASSED — all 10 CTF tasks completed and verified")
    print("=" * 60)


if __name__ == "__main__":
    main()
