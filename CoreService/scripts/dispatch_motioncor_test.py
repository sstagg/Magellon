"""Dispatch MotionCor test tasks to motioncor_tasks_queue via RabbitMQ.

Sibling of dispatch_ctf_test.py. Publishes TaskDto-shaped messages that the
MotionCor plugin's rabbitmq_consumer_engine will pick up. By default it
discovers TIF/MRC movies under /gpfs/motioncor_test (the container mount
point) and references the gain at /gpfs/motioncor_test/<gain>.

Usage:
    python scripts/dispatch_motioncor_test.py
    NUM_TASKS=3 python scripts/dispatch_motioncor_test.py

Environment overrides:
    RMQ_HOST, RMQ_PORT, RMQ_USER, RMQ_PASS  RabbitMQ connection
    MOVIE_HOST_DIR    Host-side dir to enumerate (default: C:/temp/magellon/gpfs/motioncor_test)
    MOVIE_DIR         Container-side path used in the published task
                      (default: /gpfs/motioncor_test)
    NUM_TASKS         How many movies to dispatch (default: 5)
"""
import json
import os
import sys
import uuid
from datetime import datetime, timezone

import pika

RMQ_HOST = os.environ.get("RMQ_HOST", "127.0.0.1")
RMQ_PORT = int(os.environ.get("RMQ_PORT", "5672"))
RMQ_USER = os.environ.get("RMQ_USER", "rabbit")
RMQ_PASS = os.environ.get("RMQ_PASS", "behd1d2")
QUEUE = "motioncor_tasks_queue"

MOVIE_HOST_DIR = os.environ.get("MOVIE_HOST_DIR", "C:/temp/magellon/gpfs/motioncor_test")
MOVIE_DIR = os.environ.get("MOVIE_DIR", "/gpfs/motioncor_test")
NUM_TASKS = int(os.environ.get("NUM_TASKS", "5"))

# Match the bench script (motioncor2_benchmark_results.txt) so timing has
# something to compare against.
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

JOB_ID = str(uuid.uuid4())


def discover_movies() -> list[str]:
    if not os.path.isdir(MOVIE_HOST_DIR):
        print(f"FAIL: {MOVIE_HOST_DIR} does not exist", file=sys.stderr)
        sys.exit(1)
    files = sorted(
        f for f in os.listdir(MOVIE_HOST_DIR)
        if f.lower().endswith((".tif", ".tiff", ".mrc", ".eer"))
        and not f.lower().startswith("gain")
    )
    if not files:
        print(f"FAIL: no movie files under {MOVIE_HOST_DIR}", file=sys.stderr)
        sys.exit(1)
    return files[:NUM_TASKS]


def discover_gain() -> str:
    gains = [f for f in os.listdir(MOVIE_HOST_DIR) if f.lower().startswith("gain")]
    if not gains:
        print(f"FAIL: no gain reference under {MOVIE_HOST_DIR}", file=sys.stderr)
        sys.exit(1)
    return gains[0]


def make_task(movie_name: str, gain_name: str) -> dict:
    task_id = str(uuid.uuid4())
    image_id = str(uuid.uuid4())
    stem = os.path.splitext(movie_name)[0]
    input_path = f"{MOVIE_DIR}/{movie_name}"
    gain_path = f"{MOVIE_DIR}/{gain_name}"
    return {
        "id": task_id,
        "job_id": JOB_ID,
        "sesson_id": None,
        "sesson_name": "motioncor_manual_test",
        "worker_instance_id": str(uuid.uuid4()),
        "data": {
            "image_id": image_id,
            "image_name": stem,
            "image_path": input_path,
            "inputFile": input_path,
            "outputFile": f"{stem}_aligned.mrc",
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


def main():
    movies = discover_movies()
    gain = discover_gain()

    creds = pika.PlainCredentials(RMQ_USER, RMQ_PASS)
    params = pika.ConnectionParameters(host=RMQ_HOST, port=RMQ_PORT, credentials=creds)
    connection = pika.BlockingConnection(params)
    channel = connection.channel()
    channel.queue_declare(queue=QUEUE, durable=True)

    print(f"Job ID: {JOB_ID}")
    print(f"Gain  : {gain}")
    print(f"Dispatching {len(movies)} MotionCor tasks to {QUEUE}...")

    for movie_name in movies:
        task = make_task(movie_name, gain)
        body = json.dumps(task)
        channel.basic_publish(
            exchange="",
            routing_key=QUEUE,
            body=body,
            properties=pika.BasicProperties(delivery_mode=2),
        )
        print(f"  [{task['id'][:8]}] image_id={task['data']['image_id'][:8]} {movie_name}")

    connection.close()
    print(f"\nDone. {len(movies)} tasks published.")
    print("Monitor with: docker logs -f magellon-motioncor-smoke-test")


if __name__ == "__main__":
    main()
