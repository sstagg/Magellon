"""End-to-end MotionCor plugin smoke test.

Submits N real .tif movies from C:\\temp\\motioncor\\Magellon-test\\example*
to the plugin via its normal input queue, then listens on the out-queue
for TaskResultDto messages and prints a summary.

Does NOT execute MC2 locally — it just exercises the Core→RabbitMQ→plugin
dispatch path against whatever consumer is running (Docker container,
WSL, or native Linux plugin).

Usage:
    python test_batch_publish.py                    # 2 tasks, 10-min timeout
    python test_batch_publish.py --count 3          # 3 tasks
    python test_batch_publish.py --count 1 --timeout 120

Environment overrides (for targeting a remote host):
    RABBIT_HOST       — override RabbitMQ hostname (default: from config)
    REMOTE_DATA_ROOT  — remap input file paths (e.g., /data)
    GAIN_PATH         — override gain file path (default: DUMMY_GAIN)
"""
import argparse
import json
import logging
import os
import sys
import time
import uuid
from pathlib import Path

import pika

from core.helper import push_task_to_task_queue
from core.model_dto import CryoEmMotionCorTaskData, MOTIONCOR, PENDING
from core.settings import AppSettingsSingleton
from core.task_factory import MotioncorTaskFactory

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("batch-publish-test")

TEST_ROOT = Path(r"C:\temp\motioncor\Magellon-test")
# Placeholder gain — these example movies were captured without gain correction
# (see Magellon-test/script.sh which runs MC2 without -Gain). The model marks
# Gain as required (str, non-optional), so we satisfy the schema with this
# path. If the plugin's is_mrc_file() check rejects it, the task will fail
# downstream, which the test reports — that's still a valid signal.
DUMMY_GAIN = os.environ.get("GAIN_PATH", str(TEST_ROOT / "no_gain.gain.eer"))


def find_example_tifs(count: int):
    """Pick first `count` example folders that actually contain a .tif."""
    picks = []
    for i in range(1, 11):
        folder = TEST_ROOT / f"example{i}"
        if not folder.is_dir():
            continue
        tifs = list(folder.glob("*.tif"))
        if not tifs:
            continue
        picks.append((folder.name, tifs[0]))
        if len(picks) >= count:
            break
    if len(picks) < count:
        logger.warning("Only found %d .tif files, requested %d", len(picks), count)
    return picks


def build_task(folder_name: str, tif: Path):
    """Construct a MotioncorTask for one .tif input."""
    input_path = remap_path(tif, folder_name)
    gain_path = DUMMY_GAIN
    remote_root = os.environ.get("REMOTE_DATA_ROOT")
    if remote_root:
        gain_path = f"{remote_root}/gain_ones.mrc"
    data = CryoEmMotionCorTaskData(
        image_id=uuid.uuid4(),
        image_name=tif.name,
        image_path=input_path,
        inputFile=input_path,
        outputFile=f"{folder_name}_output.mrc",
        OutMrc=f"{folder_name}_output.mrc",
        Gain=gain_path,
        PatchesX=5,
        PatchesY=5,
        Iter=10,
        Tol=0.5,
        FtBin=1,
        kV=300,
        FmDose=0.75,
        PixSize=0.705,
        Group=3,
    )
    task = MotioncorTaskFactory.create_task(
        pid=str(uuid.uuid4()),
        instance_id=uuid.uuid4(),
        job_id=uuid.uuid4(),
        data=data.model_dump(),
        ptype=MOTIONCOR,
        pstatus=PENDING,
    )
    task.sesson_name = f"smoketest-{folder_name}"
    return task


def connect_rmq():
    s = AppSettingsSingleton.get_instance().rabbitmq_settings
    creds = pika.PlainCredentials(s.USER_NAME, s.PASSWORD)
    params = pika.ConnectionParameters(
        host=s.HOST_NAME,
        port=s.PORT,
        virtual_host=s.VIRTUAL_HOST,
        credentials=creds,
        connection_attempts=3,
        socket_timeout=10,
    )
    return pika.BlockingConnection(params)


def remap_path(local_path: Path, folder_name: str) -> str:
    """Translate a local Windows path to a remote Linux path when REMOTE_DATA_ROOT is set."""
    remote_root = os.environ.get("REMOTE_DATA_ROOT")
    if remote_root:
        return f"{remote_root}/{folder_name}/{local_path.name}"
    return str(local_path)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--count", type=int, default=2, help="Number of tasks to submit")
    ap.add_argument("--timeout", type=int, default=600, help="Seconds to wait for results")
    args = ap.parse_args()

    # Apply env-var overrides for remote testing
    s = AppSettingsSingleton.get_instance().rabbitmq_settings
    if os.environ.get("RABBIT_HOST"):
        s.HOST_NAME = os.environ["RABBIT_HOST"]
        logger.info("RABBIT_HOST override → %s", s.HOST_NAME)

    if not TEST_ROOT.is_dir():
        logger.error("Test data dir not found: %s", TEST_ROOT)
        sys.exit(2)

    picks = find_example_tifs(args.count)
    if not picks:
        logger.error("No .tif files found under %s", TEST_ROOT)
        sys.exit(2)
    in_queue = s.QUEUE_NAME           # motioncor_tasks_queue
    out_queue = s.OUT_QUEUE_NAME      # motioncor_out_tasks_queue
    logger.info("RabbitMQ %s:%s  in=%s  out=%s", s.HOST_NAME, s.PORT, in_queue, out_queue)

    # --- Publish ---
    pending = {}   # job_id -> {folder, tif, t0}
    for folder_name, tif in picks:
        task = build_task(folder_name, tif)
        job_id = str(task.job_id)
        ok = push_task_to_task_queue(task)
        if not ok:
            logger.error("Publish FAILED for %s", folder_name)
            continue
        pending[job_id] = {"folder": folder_name, "tif": tif, "t0": time.time()}
        logger.info("Published %s  job_id=%s  tif=%s (%.1f MB)",
                    folder_name, job_id, tif.name, tif.stat().st_size / 1e6)

    if not pending:
        logger.error("No tasks published; aborting wait.")
        sys.exit(1)

    # --- Consume results ---
    conn = connect_rmq()
    ch = conn.channel()
    ch.queue_declare(queue=out_queue, durable=True)

    results = {}  # job_id -> result dict
    deadline = time.time() + args.timeout

    logger.info("Waiting up to %ds for %d results on %s...",
                args.timeout, len(pending), out_queue)

    def handler(channel, method, properties, body):
        try:
            msg = json.loads(body)
        except Exception as e:
            logger.warning("non-JSON message on %s: %s", out_queue, e)
            channel.basic_ack(delivery_tag=method.delivery_tag)
            return

        job_id = str(msg.get("job_id", ""))
        if job_id in pending and job_id not in results:
            elapsed = time.time() - pending[job_id]["t0"]
            results[job_id] = {
                "code": msg.get("code"),
                "message": msg.get("message"),
                "description": (msg.get("description") or "")[:200],
                "output_files": msg.get("output_files") or msg.get("outputs") or [],
                "elapsed": elapsed,
            }
            logger.info("RESULT %s  folder=%s  code=%s  elapsed=%.1fs",
                        job_id, pending[job_id]["folder"],
                        results[job_id]["code"], elapsed)
            channel.basic_ack(delivery_tag=method.delivery_tag)
        else:
            # Not ours — requeue so other consumers / future runs can see it
            channel.basic_nack(delivery_tag=method.delivery_tag, requeue=True)

        if len(results) >= len(pending):
            channel.stop_consuming()

    ch.basic_qos(prefetch_count=1)
    ch.basic_consume(queue=out_queue, on_message_callback=handler)

    # Poll with timeout using process_data_events
    try:
        while time.time() < deadline and len(results) < len(pending):
            conn.process_data_events(time_limit=5)
    finally:
        try:
            ch.close()
            conn.close()
        except Exception:
            pass

    # --- Report ---
    print("\n" + "=" * 72)
    print(f"Summary — {len(results)}/{len(pending)} results within {args.timeout}s")
    print("=" * 72)
    for job_id, meta in pending.items():
        r = results.get(job_id)
        if r is None:
            print(f"  TIMEOUT  {meta['folder']:<10}  job_id={job_id}")
        else:
            status = "OK " if r["code"] in (0, 200) else f"ERR({r['code']})"
            print(f"  {status:<8} {meta['folder']:<10}  {r['elapsed']:>6.1f}s  "
                  f"msg={r['message']!r}")
            if r["output_files"]:
                for f in r["output_files"]:
                    print(f"           out: {f}")
            if r["description"]:
                print(f"           desc: {r['description']}")
    print("=" * 72)

    missing = len(pending) - len(results)
    errored = sum(1 for r in results.values() if r["code"] not in (0, 200))
    sys.exit(0 if missing == 0 and errored == 0 else 1)


if __name__ == "__main__":
    main()
