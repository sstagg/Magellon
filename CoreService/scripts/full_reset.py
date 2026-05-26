"""
Full pipeline reset for Magellon end-to-end testing.

Purges RabbitMQ queues, truncates session-related DB tables, removes
session home directories, clears the ops event log, and empties the
plugin jobs directory.

Usage:
    python scripts/full_reset.py --session 24dec03a         # dry run
    python scripts/full_reset.py --session 24dec03a --yes   # execute
    python scripts/full_reset.py --yes                      # DB + dirs only

Multiple sessions:
    python scripts/full_reset.py --session 24dec03a --session 24dec04a --yes

Stop plugin containers so tasks queue up for recording instead of being consumed:
    python scripts/full_reset.py --session 24dec03a --yes --stop-plugins

Config:
    Reads DB and RMQ settings from configs/app_settings_dev.yaml by default.
    Override with --config or environment variables:
      DB_HOST  DB_PORT  DB_NAME  DB_USER  DB_PASS
      RMQ_HOST RMQ_PORT RMQ_USER RMQ_PASS
"""

import argparse
import asyncio
import os
import shutil
import subprocess
import sys
import time
import uuid

import pika
import pymysql
import yaml

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_CONFIG = os.path.join(ROOT, "configs", "app_settings_dev.yaml")

CLEAR_TABLES = [
    "artifact",
    "image_meta_data",
    "image_job_task",
    "image_job",
    "image",
    "atlas",
    "msession",
]

PURGE_QUEUES = [
    "motioncor_tasks_queue",
    "motioncor_out_tasks_queue",
    "ctf_tasks_queue",
    "ctf_out_tasks_queue",
    "fft_tasks_queue",
    "fft_out_tasks_queue",
]

# Containers stopped by --stop-plugins so tasks queue up for recording.
# Restarted automatically after reset unless --no-restart is also given.
PLUGIN_CONTAINERS = [
    "magellon-plugin-motioncor",
]


def load_config(path):
    with open(path) as fh:
        return yaml.safe_load(fh)


def db_connect(config):
    db = config["database_settings"]
    host = os.environ.get("DB_HOST") or db["DB_HOST"]
    port = int(os.environ.get("DB_PORT") or db.get("DB_Port", 3306))
    name = os.environ.get("DB_NAME") or db["DB_NAME"]
    user = os.environ.get("DB_USER") or db["DB_USER"]
    pwd  = os.environ.get("DB_PASS") or db["DB_PASSWORD"]
    return pymysql.connect(host=host, port=port, database=name,
                           user=user, password=pwd,
                           connect_timeout=10, autocommit=False)


def rmq_connect(config):
    rmq = config.get("rabbitmq_settings", {})
    host = os.environ.get("RMQ_HOST") or rmq.get("HOST_NAME", "127.0.0.1")
    port = int(os.environ.get("RMQ_PORT") or rmq.get("PORT", 5672))
    user = os.environ.get("RMQ_USER") or rmq.get("USER_NAME", "rabbit")
    pwd  = os.environ.get("RMQ_PASS") or rmq.get("PASSWORD", "")
    params = pika.ConnectionParameters(
        host=host, port=port,
        credentials=pika.PlainCredentials(user, pwd),
        connection_attempts=3,
        retry_delay=2,
    )
    return pika.BlockingConnection(params)


def purge_queues(config, dry_run):
    print("\n--- RabbitMQ queue purge ---")
    try:
        conn = rmq_connect(config)
    except Exception as exc:
        print(f"  WARNING: cannot connect to RabbitMQ: {exc}")
        return
    try:
        ch = conn.channel()
        for q in PURGE_QUEUES:
            try:
                if dry_run:
                    # passive declare to get message count without purging
                    method = ch.queue_declare(queue=q, passive=True)
                    print(f"  [dry run] {q}: {method.method.message_count} messages (would purge)")
                else:
                    ch.queue_purge(q)
                    print(f"  purged {q}")
            except Exception as e:
                print(f"  skip {q}: {e}")
    finally:
        try:
            conn.close()
        except Exception:
            pass


def purge_nats_stream(dry_run):
    """Purge the MAGELLON_STEP_EVENTS JetStream so stale step events for
    old job_ids don't crash the forwarder after the DB is wiped.

    Soft-skips when nats-py isn't installed or NATS isn't reachable;
    this script must keep working in environments that don't use NATS.
    """
    print("\n--- NATS step-event stream purge ---")
    try:
        import nats  # noqa: F401
    except ImportError:
        print("  skip: nats-py not installed")
        return

    nats_url = os.environ.get("NATS_URL", "nats://127.0.0.1:4222")
    stream_name = os.environ.get("NATS_STEP_EVENTS_STREAM", "MAGELLON_STEP_EVENTS")

    async def _run():
        nc = None
        try:
            nc = await asyncio.wait_for(nats.connect(nats_url), timeout=5)
        except Exception as exc:
            print(f"  skip: cannot connect to NATS at {nats_url}: {exc}")
            return
        try:
            js = nc.jetstream()
            try:
                info = await js.stream_info(stream_name)
            except Exception as exc:
                print(f"  skip: stream {stream_name} not found: {exc}")
                return
            count = info.state.messages
            if dry_run:
                print(f"  [dry run] {stream_name}: {count} messages (would purge)")
            else:
                await js.purge_stream(stream_name)
                print(f"  purged {stream_name} ({count} messages)")
        finally:
            await nc.close()

    try:
        asyncio.run(_run())
    except Exception as exc:
        print(f"  WARNING: NATS purge failed: {exc}")


def truncate_db(config, dry_run):
    print("\n--- Database truncation ---")
    conn = db_connect(config)
    cursor = conn.cursor()
    try:
        for t in CLEAR_TABLES:
            cursor.execute(f"SELECT COUNT(*) FROM {t}")
            n = cursor.fetchone()[0]
            if dry_run:
                print(f"  [dry run] {t}: {n} rows (would truncate)")
            else:
                pass  # done in a transaction below
    finally:
        cursor.close()
        conn.close()

    if dry_run:
        return

    conn = db_connect(config)
    cursor = conn.cursor()
    try:
        cursor.execute("SET FOREIGN_KEY_CHECKS = 0")
        for t in CLEAR_TABLES:
            cursor.execute(f"TRUNCATE TABLE {t}")
            print(f"  truncated {t}")
        cursor.execute("SET FOREIGN_KEY_CHECKS = 1")
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        cursor.close()
        conn.close()


def _rmtree_windows_safe(path):
    """Remove a directory tree, falling back to 'rd /s /q' on PermissionError."""
    trash = path + f".reset-trash-{uuid.uuid4().hex}"
    try:
        os.rename(path, trash)
    except PermissionError:
        # Some process has the directory open; try shell removal
        ret = subprocess.call(
            ["cmd", "/c", "rd", "/s", "/q", path],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
        if ret == 0 and not os.path.exists(path):
            return
        # last resort: shutil with ignore_errors
        shutil.rmtree(path, ignore_errors=True)
        return

    for _ in range(4):
        shutil.rmtree(trash, ignore_errors=True)
        if not os.path.exists(trash):
            return
        time.sleep(1)
    print(f"  WARNING: trash dir still present: {trash}")


def clear_session_dirs(config, sessions, dry_run):
    if not sessions:
        return
    directory = config.get("directory_settings", {})
    gpfs_root = directory.get("MAGELLON_GPFS_PATH") or os.getenv("MAGELLON_GPFS_PATH", "")
    home_dir  = directory.get("MAGELLON_HOME_DIR") or os.getenv("MAGELLON_HOME_DIR", "home")
    if not os.path.isabs(home_dir):
        if not gpfs_root:
            print("  WARNING: MAGELLON_GPFS_PATH not set; skipping session dir removal")
            return
        home_dir = os.path.join(gpfs_root, home_dir)
    home_abs = os.path.abspath(home_dir)

    print("\n--- Session directory cleanup ---")
    for session in sessions:
        target = os.path.abspath(os.path.join(home_abs, session.lower()))
        if os.path.commonpath([home_abs, target]) != home_abs:
            print(f"  REFUSED: {target} is outside {home_abs}")
            continue
        if not os.path.isdir(target):
            print(f"  not found: {target}")
            continue
        if dry_run:
            print(f"  [dry run] would remove {target}")
        else:
            _rmtree_windows_safe(target)
            if not os.path.exists(target):
                print(f"  removed {target}")
            else:
                print(f"  WARNING: could not fully remove {target}")


def clear_ops_log(config, dry_run):
    directory = config.get("directory_settings", {})
    gpfs_root = directory.get("MAGELLON_GPFS_PATH") or os.getenv("MAGELLON_GPFS_PATH", "")
    if not gpfs_root:
        return

    print("\n--- Ops event log ---")
    ops_base = os.path.join(gpfs_root, "ops_events.jsonl")
    removed = 0
    for suffix in ["", ".1", ".2", ".3", ".4", ".5"]:
        p = ops_base + suffix
        if os.path.exists(p):
            if dry_run:
                print(f"  [dry run] would remove {p}")
            else:
                os.remove(p)
                print(f"  removed {p}")
                removed += 1
    if removed == 0 and not dry_run:
        print("  (no ops log found)")


def manage_plugin_containers(action, dry_run, containers=None):
    """Stop or start plugin containers. action = 'stop' | 'start'."""
    targets = containers or PLUGIN_CONTAINERS
    label = "Stopping" if action == "stop" else "Starting"
    print(f"\n--- {label} plugin containers ---")
    for name in targets:
        if dry_run:
            print(f"  [dry run] docker {action} {name}")
            continue
        ret = subprocess.run(
            ["docker", action, name],
            capture_output=True, text=True,
        )
        if ret.returncode == 0:
            print(f"  {action}ped {name}")
        else:
            msg = ret.stderr.strip() or ret.stdout.strip()
            print(f"  WARNING: docker {action} {name}: {msg}")


def clear_jobs_dir(config, dry_run):
    directory = config.get("directory_settings", {})
    gpfs_root = directory.get("MAGELLON_GPFS_PATH") or os.getenv("MAGELLON_GPFS_PATH", "")
    if not gpfs_root:
        return

    jobs_dir = os.path.join(gpfs_root, "jobs")
    if not os.path.isdir(jobs_dir):
        return

    print("\n--- Plugin jobs directory ---")
    if dry_run:
        n = sum(1 for _ in os.scandir(jobs_dir))
        print(f"  [dry run] would clear {jobs_dir} ({n} entries)")
    else:
        shutil.rmtree(jobs_dir, ignore_errors=True)
        os.makedirs(jobs_dir, exist_ok=True)
        print(f"  cleared {jobs_dir}")


def main():
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--yes", action="store_true",
                        help="actually execute (default is dry run)")
    parser.add_argument("--config", default=DEFAULT_CONFIG,
                        help="path to app_settings_*.yaml")
    parser.add_argument("--session", action="append", default=[],
                        metavar="SESSION",
                        help="session name(s) whose home dirs to remove (repeat for multiple)")
    parser.add_argument("--skip-rmq", action="store_true",
                        help="skip RabbitMQ purge (useful if broker is down)")
    parser.add_argument("--skip-nats", action="store_true",
                        help="skip NATS step-event stream purge")
    parser.add_argument("--skip-db", action="store_true",
                        help="skip DB truncation")
    parser.add_argument("--stop-plugins", action="store_true",
                        help="stop plugin containers so tasks accumulate for recording; "
                             "restarts them after reset unless --no-restart is given")
    parser.add_argument("--no-restart", action="store_true",
                        help="with --stop-plugins: leave containers stopped after reset")
    args = parser.parse_args()

    dry_run = not args.yes
    if dry_run:
        print("DRY RUN — no changes will be made (pass --yes to execute)")

    config = load_config(args.config)
    db = config["database_settings"]
    print(f"Config: {args.config}")
    print(f"DB:     {db.get('DB_HOST')}:{db.get('DB_Port')}/{db.get('DB_NAME')}")
    print(f"Sessions to clear: {args.session or '(none)'}")
    if args.stop_plugins:
        print(f"Plugin containers: will stop {PLUGIN_CONTAINERS}"
              + (" (leave stopped)" if args.no_restart else " (restart after reset)"))

    if args.stop_plugins:
        manage_plugin_containers("stop", dry_run)

    if not args.skip_rmq:
        purge_queues(config, dry_run)

    if not args.skip_nats:
        purge_nats_stream(dry_run)

    if not args.skip_db:
        truncate_db(config, dry_run)

    clear_session_dirs(config, args.session, dry_run)
    clear_ops_log(config, dry_run)
    clear_jobs_dir(config, dry_run)

    if args.stop_plugins and not args.no_restart:
        manage_plugin_containers("start", dry_run)

    if dry_run:
        print("\nDry run complete. Re-run with --yes to execute.")
    else:
        if args.stop_plugins and args.no_restart:
            print("\nReset complete. Plugin containers are STOPPED.")
            print("Run import, then: python sandbox/aws/record_tasks.py --session <name>")
            print("When done: docker start " + " ".join(PLUGIN_CONTAINERS))
        elif args.stop_plugins:
            print("\nReset complete. Plugin containers restarted.")
        else:
            print("\nReset complete. Ready for fresh import.")


if __name__ == "__main__":
    main()
