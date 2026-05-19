"""Re-dispatch MotionCor tasks for a job directly via pika.

Two modes of operation:

  --frames-dir  Scan a host-side directory for .tif/.mrc/.eer frame files
                and dispatch each one, inserting a fresh ImageJobTask row
                per frame so the result-processor can track completion.

  (default)     Query the DB for existing motioncor tasks (stage=1) that
                are not completed and re-queue them with their stored paths.

Bypasses the MessageBus so it works standalone — same pika transport as
dispatch_motioncor_test.py.

Usage:
    python scripts/redispatch_motioncor_job.py --dry-run
    python scripts/redispatch_motioncor_job.py
    python scripts/redispatch_motioncor_job.py \\
        --job-id  5be55963-cd46-4bf5-bfe3-cc7bafa91fc8 \\
        --frames-dir C:/magellon/gpfs/24dec03a/home/frames \\
        --gain    C:/magellon/gpfs/24dec03a/home/gains/20241202_53597_gain_multi_ref.tif

Environment overrides:
    RMQ_HOST RMQ_PORT RMQ_USER RMQ_PASS
    DB_HOST  DB_PORT  DB_NAME  DB_USER  DB_PASS
"""
import argparse
import json
import os
import sys
import uuid
from datetime import datetime, timezone

import pika
import pymysql

# ---------------------------------------------------------------------------
# Config defaults
# ---------------------------------------------------------------------------
RMQ_HOST = os.environ.get("RMQ_HOST", "127.0.0.1")
RMQ_PORT = int(os.environ.get("RMQ_PORT", "5672"))
RMQ_USER = os.environ.get("RMQ_USER", "rabbit")
RMQ_PASS = os.environ.get("RMQ_PASS", "behd1d2")
QUEUE    = "motioncor_tasks_queue"

DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_PORT = int(os.environ.get("DB_PORT", "3306"))
DB_NAME = os.environ.get("DB_NAME", "magellon01")
DB_USER = os.environ.get("DB_USER", "root")
DB_PASS = os.environ.get("DB_PASS", "behd1d2")

DEFAULT_JOB_ID    = "5be55963-cd46-4bf5-bfe3-cc7bafa91fc8"
DEFAULT_FRAMES_DIR = "C:/magellon/gpfs/24dec03a/home/frames"
DEFAULT_GAIN       = "C:/magellon/gpfs/24dec03a/home/gains/20241202_53597_gain_multi_ref.tif"
GPFS_HOST_PATH     = "C:/magellon/gpfs"

MOTIONCOR_SETTINGS = {
    "PatchesX": 7,
    "PatchesY": 7,
    "FmDose":   1.0,
    "Group":    4,
}

FRAME_EXTENSIONS = (".tif", ".tiff", ".mrc", ".eer")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def to_canonical(path: str) -> str:
    """Translate a Windows host path under GPFS_HOST_PATH to /gpfs/... form."""
    if not path:
        return path
    p = path.replace("\\", "/")
    norm_gpfs = GPFS_HOST_PATH.replace("\\", "/")
    if p.startswith(norm_gpfs):
        return "/gpfs" + p[len(norm_gpfs):]
    return p


def uuid_bytes(u: str) -> bytes:
    return uuid.UUID(u).bytes


def connect_db():
    return pymysql.connect(
        host=DB_HOST, port=DB_PORT, db=DB_NAME,
        user=DB_USER, password=DB_PASS,
        charset="utf8mb4",
    )


# ---------------------------------------------------------------------------
# Discover frame files from a directory
# ---------------------------------------------------------------------------

def discover_frames(frames_dir: str) -> list[str]:
    """Return sorted list of absolute frame file paths."""
    if not os.path.isdir(frames_dir):
        print(f"FAIL: frames directory not found: {frames_dir}", file=sys.stderr)
        sys.exit(1)
    files = sorted(
        os.path.join(frames_dir, f)
        for f in os.listdir(frames_dir)
        if f.lower().endswith(FRAME_EXTENSIONS)
    )
    return files


# ---------------------------------------------------------------------------
# DB helpers
# ---------------------------------------------------------------------------

def query_stuck_tasks(conn, job_id: str) -> list[dict]:
    """Return existing motioncor tasks for the job that haven't completed."""
    jb = uuid_bytes(job_id)
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT t.oid, t.job_id, t.image_id, t.status_id,
                   t.image_name, t.image_path, t.frame_name, t.frame_path,
                   i.pixel_size, i.acceleration_voltage
            FROM image_job_task t
            LEFT JOIN image i ON i.oid = t.image_id
            WHERE t.job_id = %s AND t.stage = 1 AND t.status_id NOT IN (2, 4)
            ORDER BY t.image_name
            """,
            (jb,),
        )
        cols = [d[0] for d in cur.description]
        rows = []
        for row in cur.fetchall():
            d = dict(zip(cols, row))
            for f in ("oid", "job_id", "image_id"):
                if isinstance(d.get(f), (bytes, bytearray)):
                    d[f] = str(uuid.UUID(bytes=bytes(d[f])))
            rows.append(d)
        return rows


def insert_task_rows(conn, job_id: str, frame_paths: list[str]) -> list[dict]:
    """Insert fresh ImageJobTask rows for each frame, return list of dicts
    with task_id and path info ready for dispatch."""
    jb = uuid_bytes(job_id)
    records = []
    with conn.cursor() as cur:
        for frame_path in frame_paths:
            task_id    = uuid.uuid4()
            image_name = os.path.splitext(os.path.basename(frame_path))[0]
            # Strip double extension (.mrc.tif → base name without both exts)
            if image_name.endswith(".mrc"):
                image_name = image_name[:-4]
            canonical_path = to_canonical(frame_path)
            cur.execute(
                """
                INSERT INTO image_job_task
                    (oid, job_id, status_id, stage, image_name, image_path,
                     frame_name, frame_path, subject_kind)
                VALUES (%s, %s, 1, 1, %s, %s, %s, %s, 'image')
                """,
                (
                    task_id.bytes,
                    jb,
                    image_name,
                    canonical_path,
                    os.path.basename(frame_path),
                    canonical_path,
                ),
            )
            records.append({
                "task_id":    str(task_id),
                "job_id":     job_id,
                "image_name": image_name,
                "frame_path": canonical_path,
            })
    conn.commit()
    return records


# ---------------------------------------------------------------------------
# Build RabbitMQ payload
# ---------------------------------------------------------------------------

def make_payload(
    task_id: str,
    job_id: str,
    image_name: str,
    frame_path: str,    # canonical /gpfs/... path
    gain_path: str,     # canonical /gpfs/... path
    pixel_size: float = 1.0,
    kv: float = 300.0,
) -> dict:
    session_name = image_name.split("_")[0] if image_name else "unknown"
    return {
        "id":                 task_id,
        "job_id":             job_id,
        "session_id":         None,
        "session_name":       session_name,
        "worker_instance_id": str(uuid.uuid4()),
        "data": {
            "image_id":   str(uuid.uuid4()),
            "image_name": image_name,
            "image_path": frame_path,
            "inputFile":  frame_path,
            "OutMrc":     f"{image_name}_aligned.mrc",
            "Gain":       gain_path,
            "kV":         kv,
            "PixSize":    pixel_size,
            **MOTIONCOR_SETTINGS,
        },
        "status":       {"code": 0, "name": "pending", "description": "Task is pending"},
        "type":         {"code": 3, "name": "MOTIONCOR", "description": "Motion Correction"},
        "created_date": datetime.now(timezone.utc).isoformat(),
        "start_on":     None,
        "end_on":       None,
        "result":       None,
    }


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--job-id",     default=DEFAULT_JOB_ID)
    parser.add_argument("--frames-dir", default=DEFAULT_FRAMES_DIR,
                        help="Directory of raw frame TIF/MRC/EER files")
    parser.add_argument("--gain",       default=DEFAULT_GAIN,
                        help="Host path to the gain reference file")
    parser.add_argument("--pixel-size", type=float, default=None)
    parser.add_argument("--kv",         type=float, default=300.0)
    parser.add_argument("--dry-run",    action="store_true")
    args = parser.parse_args()

    gain_canonical = to_canonical(args.gain)
    print(f"Job ID    : {args.job_id}")
    print(f"Frames dir: {args.frames_dir}")
    print(f"Gain      : {gain_canonical}")

    conn = connect_db()

    # ------------------------------------------------------------------
    # First try: existing stuck tasks in DB
    # ------------------------------------------------------------------
    stuck = query_stuck_tasks(conn, args.job_id)
    if stuck:
        print(f"\nFound {len(stuck)} existing stuck task(s) in DB — will re-queue them.")
        payloads = []
        for row in stuck:
            raw_path = row.get("frame_path") or row.get("image_path") or ""
            frame_canonical = to_canonical(raw_path)
            if not frame_canonical.lower().endswith(".tif"):
                frame_canonical += ".tif"
            pix = float(row["pixel_size"]) if row.get("pixel_size") else (args.pixel_size or 1.0)
            kv  = float(row["acceleration_voltage"]) if row.get("acceleration_voltage") else args.kv
            payloads.append(make_payload(
                task_id=row["oid"],
                job_id=args.job_id,
                image_name=row.get("image_name") or "",
                frame_path=frame_canonical,
                gain_path=gain_canonical,
                pixel_size=pix,
                kv=kv,
            ))
    else:
        # ------------------------------------------------------------------
        # Fallback: scan the frames directory and insert fresh task rows
        # ------------------------------------------------------------------
        print(f"\nNo existing stuck tasks — scanning {args.frames_dir} for frame files ...")
        frame_files = discover_frames(args.frames_dir)
        print(f"Found {len(frame_files)} frame file(s).")

        if args.dry_run:
            print("\n--- DRY RUN ---")
            for f in frame_files:
                print(f"  {to_canonical(f)}")
            conn.close()
            return

        print(f"Inserting {len(frame_files)} ImageJobTask row(s) into DB ...")
        records = insert_task_rows(conn, args.job_id, frame_files)

        payloads = [
            make_payload(
                task_id=r["task_id"],
                job_id=r["job_id"],
                image_name=r["image_name"],
                frame_path=r["frame_path"],
                gain_path=gain_canonical,
                pixel_size=args.pixel_size or 1.0,
                kv=args.kv,
            )
            for r in records
        ]

    if args.dry_run:
        print("\n--- DRY RUN ---")
        for p in payloads:
            print(f"  [{p['id'][:8]}] {p['data']['image_path'][-70:]}")
        conn.close()
        return

    # ------------------------------------------------------------------
    # Publish
    # ------------------------------------------------------------------
    print(f"\nConnecting to RabbitMQ {RMQ_HOST}:{RMQ_PORT} ...")
    creds  = pika.PlainCredentials(RMQ_USER, RMQ_PASS)
    params = pika.ConnectionParameters(host=RMQ_HOST, port=RMQ_PORT, credentials=creds, heartbeat=60)
    rmq    = pika.BlockingConnection(params)
    ch     = rmq.channel()
    ch.queue_declare(queue=QUEUE, durable=True)

    print(f"Publishing {len(payloads)} task(s) to {QUEUE} ...")
    for p in payloads:
        ch.basic_publish(
            exchange="",
            routing_key=QUEUE,
            body=json.dumps(p),
            properties=pika.BasicProperties(delivery_mode=2),
        )
        print(f"  [{p['id'][:8]}] {p['data']['image_name']}")

    rmq.close()
    conn.close()
    print(f"\nDone. {len(payloads)} task(s) published to {QUEUE}.")
    print("Monitor: docker logs -f magellon-motioncor-1")


if __name__ == "__main__":
    main()
