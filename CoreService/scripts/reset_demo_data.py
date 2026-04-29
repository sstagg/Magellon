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
import sys

import yaml
from sqlalchemy import create_engine, text

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_CONFIG = os.path.join(ROOT, "configs", "app_settings_dev.yaml")


# Order matters: children before parents.
CLEAR_TABLES = [
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


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--yes", action="store_true", help="execute the truncate (required)")
    parser.add_argument("--config", default=DEFAULT_CONFIG, help="path to app_settings_*.yaml")
    args = parser.parse_args()

    with open(args.config) as fh:
        db = yaml.safe_load(fh)["database_settings"]
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

    with engine.connect() as conn:
        show_counts("After reset:", counts(conn, CLEAR_TABLES))
    print("\nDone. Ready for demo import.")


if __name__ == "__main__":
    main()
