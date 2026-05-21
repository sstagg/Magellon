"""
Demo Data Reset
===============
Wipes session/image/metadata/job rows so the database is ready for a fresh
demo import (see https://www.magellon.org/post/magellon-demo). Keeps all
security tables, lookup tables, projects, plugins, and pipelines intact.

Usage:
    python scripts/reset_demo_data.py          # preview only
    python scripts/reset_demo_data.py --yes    # actually truncate

Reads DB settings from config (app_settings_dev.yaml by default).
"""

import argparse
import os
import shutil
import sys
import time
import uuid

import yaml
from sqlalchemy import create_engine, text

try:
    import pika  # optional; skip queue purge if not installed
    _HAS_PIKA = True
except ImportError:
    _HAS_PIKA = False

PURGE_QUEUES = [
    "ctf_tasks_queue", "ctf_out_tasks_queue",
    "motioncor_tasks_queue", "motioncor_out_tasks_queue",
    "hole_detection_tasks_queue", "hole_detection_out_tasks_queue",
    "square_detection_tasks_queue", "square_detection_out_tasks_queue",
]

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_CONFIG = os.path.join(ROOT, "configs", "app_settings_dev.yaml")


# Order matters: children before parents.
CLEAR_TABLES = [
    "artifact",        # FK: producing_job_id → image_job, producing_task_id → image_job_task
    "image_meta_data",
    "image_job_task",
    "image_job",
    "image",
    "atlas",
    "msession",
]

KEEP_SPOT_CHECK = [
    "sys_sec_user",
    "sys_sec_role",
    "sys_sec_user_role",
    "camera",
    "microscope",
    "plugin",
    "pipeline",
    "project",
    "sample_type",
]


def counts(conn, tables):
    return {t: conn.execute(text(f"SELECT COUNT(*) FROM {t}")).scalar() for t in tables}


def show_counts(title, data):
    print(f"\n{title}")
    for t, n in data.items():
        print(f"  {t:22s} {n:>10}")


def configured_home_dir(config):
    directory = config.get("directory_settings", {})
    gpfs_root = directory.get("MAGELLON_GPFS_PATH") or os.getenv("MAGELLON_GPFS_PATH")
    home_dir = directory.get("MAGELLON_HOME_DIR") or os.getenv("MAGELLON_HOME_DIR") or "home"
    if os.path.isabs(home_dir):
        return os.path.normpath(home_dir)
    if not gpfs_root:
        raise RuntimeError("MAGELLON_GPFS_PATH is required when MAGELLON_HOME_DIR is relative")
    return os.path.normpath(os.path.join(gpfs_root, home_dir))


def clear_session_dirs(home_dir, session_names):
    if not session_names:
        return

    home_abs = os.path.abspath(home_dir)
    print("\nClearing imported session directories:")
    for session_name in session_names:
        target = os.path.abspath(os.path.join(home_abs, session_name.lower()))
        if os.path.commonpath([home_abs, target]) != home_abs:
            raise RuntimeError(f"Refusing to remove path outside MAGELLON_HOME_DIR: {target}")
        if os.path.isdir(target):
            trash = f"{target}.reset-trash-{uuid.uuid4().hex}"
            os.rename(target, trash)
            for _ in range(3):
                shutil.rmtree(trash, ignore_errors=True)
                if not os.path.exists(trash):
                    break
                time.sleep(1)
            if os.path.exists(trash):
                print(f"  moved {target} to {trash}; delete is still pending")
            else:
                print(f"  removed {target}")
        else:
            print(f"  not found {target}")


def purge_queues(rmq_host, rmq_port, rmq_user, rmq_password):
    """Purge stale task messages so plugins don't replay them after a reset."""
    if not _HAS_PIKA:
        print("\nSkipping queue purge (pika not installed)")
        return
    print("\nPurging RabbitMQ queues:")
    try:
        conn = pika.BlockingConnection(
            pika.ConnectionParameters(
                host=rmq_host,
                port=rmq_port,
                credentials=pika.PlainCredentials(rmq_user, rmq_password),
                connection_attempts=1,
                socket_timeout=5,
            )
        )
        ch = conn.channel()
        for q in PURGE_QUEUES:
            try:
                result = ch.queue_purge(q)
                n = result.method.message_count
                print(f"  purged {q}: {n} messages")
            except Exception as qe:
                print(f"  skip {q}: {qe}")
        conn.close()
    except Exception as e:
        print(f"  could not connect to RabbitMQ ({rmq_host}:{rmq_port}): {e} — skipping")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--yes", action="store_true", help="execute the truncate (required)")
    parser.add_argument("--config", default=DEFAULT_CONFIG, help="path to app_settings_*.yaml")
    parser.add_argument(
        "--clear-session-dir",
        action="append",
        default=[],
        metavar="SESSION",
        help="also remove MAGELLON_HOME_DIR/<session>; repeat for multiple sessions",
    )
    args = parser.parse_args()

    with open(args.config) as fh:
        config = yaml.safe_load(fh)
        db = config["database_settings"]
    url = (
        f"{db['DB_Driver']}://{db['DB_USER']}:{db['DB_PASSWORD']}"
        f"@{db['DB_HOST']}:{db['DB_Port']}/{db['DB_NAME']}"
    )
    engine = create_engine(url)

    print(f"Target: {db['DB_HOST']}:{db['DB_Port']}/{db['DB_NAME']} as {db['DB_USER']}")

    with engine.connect() as conn:
        show_counts("CLEAR list (will be truncated):", counts(conn, CLEAR_TABLES))
        show_counts("KEEP spot-check (will NOT be touched):", counts(conn, KEEP_SPOT_CHECK))

    if not args.yes:
        print("\nDry run. Re-run with --yes to truncate the CLEAR list.")
        return

    print("\nTruncating...")
    with engine.begin() as conn:
        conn.execute(text("SET FOREIGN_KEY_CHECKS = 0"))
        for t in CLEAR_TABLES:
            conn.execute(text(f"TRUNCATE TABLE {t}"))
            print(f"  truncated {t}")
        conn.execute(text("SET FOREIGN_KEY_CHECKS = 1"))

    rmq = config.get("rabbitmq_settings", {})
    purge_queues(
        rmq_host=rmq.get("HOST_NAME", "localhost"),
        rmq_port=rmq.get("PORT", 5672),
        rmq_user=rmq.get("USER_NAME", "guest"),
        rmq_password=rmq.get("PASSWORD", "guest"),
    )

    clear_session_dirs(configured_home_dir(config), args.clear_session_dir)

    # Clear ops event log so monitoring starts from a clean baseline.
    directory = config.get("directory_settings", {})
    gpfs_root = directory.get("MAGELLON_GPFS_PATH") or os.getenv("MAGELLON_GPFS_PATH")
    if gpfs_root:
        print("\nClearing ops event log:")
        ops_base = os.path.join(gpfs_root, "ops_events.jsonl")
        for suffix in ["", ".1", ".2", ".3", ".4", ".5"]:
            p = ops_base + suffix
            if os.path.exists(p):
                os.remove(p)
                print(f"  removed {p}")

        # Clear plugin job output dirs so results from previous runs don't linger.
        jobs_dir = os.path.join(gpfs_root, "jobs")
        if os.path.isdir(jobs_dir):
            shutil.rmtree(jobs_dir, ignore_errors=True)
            os.makedirs(jobs_dir, exist_ok=True)
            print(f"\nCleared plugin jobs dir: {jobs_dir}")

    with engine.connect() as conn:
        show_counts("After reset:", counts(conn, CLEAR_TABLES))
    print("\nDone. Ready for demo import.")


if __name__ == "__main__":
    main()
