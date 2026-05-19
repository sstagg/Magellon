"""DuckDB query helper for ops_events.jsonl.

Reads ALL rotation files via glob so history across rotations is visible.

Usage:
    python scripts/query_ops.py                    # summary
    python scripts/query_ops.py recent             # 20 most recent events
    python scripts/query_ops.py failed             # all failures
    python scripts/query_ops.py category motioncor # events for one category
    python scripts/query_ops.py sql "SELECT ..."   # raw SQL

Requirements:
    pip install duckdb pandas
"""
import os
import sys

GPFS_PATH = os.environ.get("MAGELLON_GPFS_PATH", "C:/magellon/gpfs")
LOG_GLOB  = os.path.join(GPFS_PATH, "ops_events.jsonl*").replace("\\", "/")


def _qrun(sql: str) -> None:
    import duckdb
    df = duckdb.connect().execute(sql).fetchdf()
    if df.empty:
        print("(no rows)")
    else:
        print(df.to_string(index=False))


def cmd_summary():
    print(f"\nLog glob: {LOG_GLOB}\n")
    _qrun(f"""
        SELECT
            category,
            status,
            COUNT(*) AS n,
            MIN(ts)  AS first_seen,
            MAX(ts)  AS last_seen,
            ROUND(AVG(TRY_CAST(duration_ms AS DOUBLE)) / 1000.0, 1) AS avg_s
        FROM read_json_auto('{LOG_GLOB}', ignore_errors=true)
        GROUP BY 1, 2
        ORDER BY 1, 2
    """)


def cmd_recent(n: int = 20):
    _qrun(f"""
        SELECT ts, category, status, session_name, image_name, job_id
        FROM read_json_auto('{LOG_GLOB}', ignore_errors=true)
        ORDER BY ts DESC
        LIMIT {n}
    """)


def cmd_failed():
    _qrun(f"""
        SELECT ts, category, session_name, image_name, processor_error, job_id, task_id
        FROM read_json_auto('{LOG_GLOB}', ignore_errors=true)
        WHERE status = 'failed'
        ORDER BY ts DESC
    """)


def cmd_category(cat: str):
    _qrun(f"""
        SELECT ts, status, session_name, image_name, TRY_CAST(duration_ms AS DOUBLE) AS duration_ms
        FROM read_json_auto('{LOG_GLOB}', ignore_errors=true)
        WHERE lower(category) = lower('{cat}')
        ORDER BY ts DESC
        LIMIT 50
    """)


def cmd_sql(query: str):
    src = f"read_json_auto('{LOG_GLOB}', ignore_errors=true)"
    _qrun(query.replace("$LOG", src))


def main():
    args = sys.argv[1:]
    if not args or args[0] == "summary":
        cmd_summary()
    elif args[0] == "recent":
        cmd_recent(int(args[1]) if len(args) > 1 else 20)
    elif args[0] == "failed":
        cmd_failed()
    elif args[0] == "category" and len(args) > 1:
        cmd_category(args[1])
    elif args[0] == "sql" and len(args) > 1:
        cmd_sql(" ".join(args[1:]))
    else:
        print(__doc__)


if __name__ == "__main__":
    main()
