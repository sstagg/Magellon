"""Dispatch 10 CTF test tasks to ctf_tasks_queue via RabbitMQ.

Publishes TaskDto-shaped JSON messages that the CTF plugin's
rabbitmq_consumer_engine will pick up and process. Each task
references an MRC file at /gpfs/ctf_test/<name>.mrc (the container
mount point).

Usage:
    python scripts/dispatch_ctf_test.py
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
QUEUE = "ctf_tasks_queue"

MRC_DIR = "/gpfs/ctf_test"

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

JOB_ID = str(uuid.uuid4())


def make_task(mrc_name: str) -> dict:
    task_id = str(uuid.uuid4())
    stem = os.path.splitext(mrc_name)[0]
    input_path = f"{MRC_DIR}/{mrc_name}"
    output_file = f"{stem}_ctf_output.mrc"

    return {
        "id": task_id,
        "job_id": JOB_ID,
        "session_id": None,
        "session_name": "ctf_ground_test",
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


def main():
    creds = pika.PlainCredentials(RMQ_USER, RMQ_PASS)
    params = pika.ConnectionParameters(host=RMQ_HOST, port=RMQ_PORT, credentials=creds)
    connection = pika.BlockingConnection(params)
    channel = connection.channel()
    channel.queue_declare(queue=QUEUE, durable=True)

    print(f"Job ID: {JOB_ID}")
    print(f"Dispatching {len(MRC_FILES)} CTF tasks to {QUEUE}...")

    for mrc_name in MRC_FILES:
        task = make_task(mrc_name)
        body = json.dumps(task)
        channel.basic_publish(
            exchange="",
            routing_key=QUEUE,
            body=body,
            properties=pika.BasicProperties(delivery_mode=2),
        )
        print(f"  [{task['id'][:8]}] {mrc_name}")

    connection.close()
    print(f"\nDone. {len(MRC_FILES)} tasks published.")
    print(f"Monitor with: docker logs -f magellon-ctf-test")


if __name__ == "__main__":
    main()
