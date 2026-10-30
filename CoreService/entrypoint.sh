#!/bin/sh
set -e

echo "Running Alembic migrations..."
if ! alembic upgrade head 2>&1; then
    echo "Schema already exists but is untracked; stamping baseline..."
    alembic stamp 0000_baseline_schema
    echo "Applying incremental migrations..."
    alembic upgrade head
fi
echo "Migrations complete. Starting server..."

# On stop: close open connections (browser sockets) within 10 s, then run the
# shutdown that lets result consumers finish their result (compose allows 60 s).
exec uvicorn main:app --host 0.0.0.0 --port 8000 --timeout-graceful-shutdown 10
