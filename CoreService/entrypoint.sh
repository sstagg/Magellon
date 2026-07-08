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

exec uvicorn main:app --host 0.0.0.0 --port 8000
