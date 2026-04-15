#!/usr/bin/env bash
# Full-stack end-to-end smoke test for the Magellon pipeline.
#
# What it does
# ------------
# 1. Brings up the docker-compose stack (MySQL, RabbitMQ, NATS,
#    CoreService, result-processor, and at least one processing plugin).
# 2. Waits for CoreService's /health endpoint to return 200.
# 3. Uploads a known-good test .mrc fixture via the REST API.
# 4. Creates a job that runs MotionCor + CTF on it.
# 5. Polls the job-status endpoint until the job reaches a terminal
#    state or TIMEOUT_SECONDS elapses.
# 6. Asserts the job ended in status=COMPLETED and that the expected
#    ImageJobTask rows moved to stage 1 (MotionCor) and stage 2 (CTF).
# 7. Tears down the stack.
#
# Why this lives in a shell script (not pytest) today
# ---------------------------------------------------
# The full path needs a GPU box to run MotionCor for real. The agent
# session where this was authored does not have one, and wiring the
# fixture up "just so" inside pytest without ever running it
# end-to-end would be speculation. Until CI gets a GPU runner, keep
# this as an operator-driven script — one person, one machine, real
# output — and let the seam test at
# ``tests/integration/test_e2e_seam.py`` gate commits.
#
# Prerequisites
# -------------
# - Docker + docker-compose (v2 plugin: `docker compose`)
# - NVIDIA GPU + nvidia-container-toolkit for the MotionCor plugin
# - A test fixture at ``$TEST_FIXTURE`` (default: tests/fixtures/smoke.mrc)
# - ``curl`` and ``jq``
#
# Usage
# -----
#   cd CoreService
#   ./scripts/e2e_smoke.sh                 # uses defaults below
#   TIMEOUT_SECONDS=1200 ./scripts/e2e_smoke.sh
#   KEEP_STACK=1        ./scripts/e2e_smoke.sh   # don't tear down at end
#
# Exit codes
# ----------
#   0  — job reached COMPLETED and task rows advanced as expected
#   1  — job reached FAILED, or timed out, or task rows did not advance
#   2  — environment problem (stack failed to start, fixture missing, …)

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

COMPOSE_FILE="${COMPOSE_FILE:-$REPO_ROOT/Docker/docker-compose.yml}"
CORESERVICE_URL="${CORESERVICE_URL:-http://127.0.0.1:8000}"
TEST_FIXTURE="${TEST_FIXTURE:-$SCRIPT_DIR/../tests/fixtures/smoke.mrc}"
TIMEOUT_SECONDS="${TIMEOUT_SECONDS:-900}"   # 15 min default
POLL_INTERVAL="${POLL_INTERVAL:-5}"
KEEP_STACK="${KEEP_STACK:-0}"

log() { printf '[e2e] %s\n' "$*" >&2; }
die() { log "FATAL: $*"; exit "${2:-1}"; }

cleanup() {
    if [[ "$KEEP_STACK" == "1" ]]; then
        log "KEEP_STACK=1 — leaving stack running"
        return
    fi
    log "tearing down stack"
    docker compose -f "$COMPOSE_FILE" down -v --remove-orphans || true
}
trap cleanup EXIT

# --- preflight ---
command -v docker >/dev/null || die "docker not on PATH" 2
command -v curl   >/dev/null || die "curl not on PATH"   2
command -v jq     >/dev/null || die "jq not on PATH"     2
[[ -f "$COMPOSE_FILE"  ]] || die "compose file not found: $COMPOSE_FILE" 2
[[ -f "$TEST_FIXTURE"  ]] || die "fixture not found: $TEST_FIXTURE (set TEST_FIXTURE=)" 2

# --- bring stack up ---
log "starting stack: $COMPOSE_FILE"
docker compose -f "$COMPOSE_FILE" up -d

# Wait for /health.
log "waiting on CoreService /health at $CORESERVICE_URL"
deadline=$(( $(date +%s) + 120 ))
until curl -fsS "$CORESERVICE_URL/health" >/dev/null 2>&1; do
    if (( $(date +%s) > deadline )); then
        die "CoreService /health never responded within 120s" 2
    fi
    sleep 2
done
log "CoreService healthy"

# --- upload fixture + create job ---
# NOTE: the exact endpoint names below need to match the live HTTP
# contract. Update them when the import/job API changes — this script
# is the single source of truth for the full-stack contract.
log "uploading fixture: $TEST_FIXTURE"
IMAGE_ID=$(
    curl -fsS -X POST -F "file=@$TEST_FIXTURE" \
        "$CORESERVICE_URL/api/images/upload" \
    | jq -r '.image_id'
)
[[ -n "$IMAGE_ID" && "$IMAGE_ID" != "null" ]] || die "upload did not return image_id" 1
log "image_id=$IMAGE_ID"

log "creating job"
JOB_ID=$(
    curl -fsS -X POST -H 'Content-Type: application/json' \
        -d "{\"plugin_id\":\"magellon_motioncor_plugin\",\"name\":\"e2e-smoke\",\"image_ids\":[\"$IMAGE_ID\"]}" \
        "$CORESERVICE_URL/api/jobs" \
    | jq -r '.job_id'
)
[[ -n "$JOB_ID" && "$JOB_ID" != "null" ]] || die "job create did not return job_id" 1
log "job_id=$JOB_ID"

# --- poll ---
log "polling job status (budget ${TIMEOUT_SECONDS}s, every ${POLL_INTERVAL}s)"
deadline=$(( $(date +%s) + TIMEOUT_SECONDS ))
terminal=""
while :; do
    status=$(curl -fsS "$CORESERVICE_URL/api/jobs/$JOB_ID" | jq -r '.status')
    log "status=$status"
    case "$status" in
        completed|COMPLETED|2) terminal="completed"; break ;;
        failed|FAILED|3)       terminal="failed";    break ;;
    esac
    if (( $(date +%s) > deadline )); then
        terminal="timeout"
        break
    fi
    sleep "$POLL_INTERVAL"
done

if [[ "$terminal" != "completed" ]]; then
    log "job did not complete cleanly (terminal=$terminal)"
    log "dumping last 200 lines of coreservice + plugin logs for triage:"
    docker compose -f "$COMPOSE_FILE" logs --tail=200 || true
    exit 1
fi

# --- assert task rows advanced ---
# Expect at least one task row at stage=1 (MotionCor) and one at
# stage=2 (CTF), both status_id=COMPLETED. The shape of the response
# is plugin-specific; this is the contract CoreService owes the UI.
log "asserting ImageJobTask rows advanced"
curl -fsS "$CORESERVICE_URL/api/jobs/$JOB_ID/tasks" | jq '
    . as $tasks
    | (map(select(.stage == 1 and .status_id == 2)) | length) as $mc
    | (map(select(.stage == 2 and .status_id == 2)) | length) as $ctf
    | if $mc >= 1 and $ctf >= 1 then
          "ok: motioncor=\($mc) ctf=\($ctf)"
      else
          error("expected >=1 MotionCor + >=1 CTF task at status=COMPLETED, got motioncor=\($mc) ctf=\($ctf)")
      end
'

log "PASS"
