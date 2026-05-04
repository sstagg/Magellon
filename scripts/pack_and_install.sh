#!/usr/bin/env bash
# pack_and_install.sh — validate, pack, install, and verify a plugin.
#
# Usage:
#   ./scripts/pack_and_install.sh <plugin_dir> [--base-url URL] [--no-install] [--no-wait]
#
# Env (or use the corresponding flags):
#   MAGELLON_BASE_URL       default http://localhost:8000
#   MAGELLON_USERNAME       default admin
#   MAGELLON_PASSWORD       default password123
#   MAGELLON_AUTH_TOKEN     supply directly to skip /auth/login
#
# What it does:
#   1. magellon-sdk plugin validate <dir>
#   2. magellon-sdk plugin pack <dir> --force
#   3. POST <base>/auth/login   → JWT (skipped if MAGELLON_AUTH_TOKEN set)
#   4. POST <base>/admin/plugins/install (multipart)
#   5. Poll <base>/plugins/<plugin_id>/health until 200, or fail after
#      manifest's health_check.timeout_seconds.
#
# Exit codes: 0 success, 1 caller error, 2 pack/validate fail,
# 3 auth fail, 4 install fail, 5 liveness wait timed out.
set -euo pipefail

PLUGIN_DIR=""
BASE_URL="${MAGELLON_BASE_URL:-http://localhost:8000}"
USERNAME="${MAGELLON_USERNAME:-admin}"
PASSWORD="${MAGELLON_PASSWORD:-password123}"
TOKEN="${MAGELLON_AUTH_TOKEN:-}"
DO_INSTALL=1
DO_WAIT=1

while (( "$#" )); do
  case "$1" in
    --base-url)   BASE_URL="$2"; shift 2 ;;
    --username)   USERNAME="$2"; shift 2 ;;
    --password)   PASSWORD="$2"; shift 2 ;;
    --token)      TOKEN="$2"; shift 2 ;;
    --no-install) DO_INSTALL=0; shift ;;
    --no-wait)    DO_WAIT=0; shift ;;
    -h|--help)
      sed -n '2,25p' "$0"; exit 0 ;;
    --) shift; break ;;
    -*) echo "unknown flag $1" >&2; exit 1 ;;
     *) PLUGIN_DIR="$1"; shift ;;
  esac
done

if [[ -z "$PLUGIN_DIR" ]]; then
  echo "usage: $0 <plugin_dir> [...]" >&2
  exit 1
fi
if [[ ! -d "$PLUGIN_DIR" ]]; then
  echo "error: $PLUGIN_DIR is not a directory" >&2
  exit 1
fi

command -v magellon-sdk >/dev/null || {
  echo "error: magellon-sdk CLI not on PATH (uv pip install -e magellon-sdk/)" >&2; exit 1
}
command -v curl >/dev/null || { echo "error: curl required" >&2; exit 1; }
command -v python3 >/dev/null || command -v python >/dev/null || {
  echo "error: python required" >&2; exit 1
}
PY=$(command -v python3 || command -v python)

# --- 1. validate -----------------------------------------------------------
echo ">>> validate $PLUGIN_DIR"
magellon-sdk plugin validate "$PLUGIN_DIR" || exit 2

# --- 2. pack ---------------------------------------------------------------
echo ">>> pack $PLUGIN_DIR"
PACK_OUT=$(magellon-sdk plugin pack "$PLUGIN_DIR" --force) || exit 2
echo "$PACK_OUT"
ARCHIVE=$(echo "$PACK_OUT" | sed -nE 's/^[[:space:]]*archive:[[:space:]]+(.+)$/\1/p' | tr -d '\r')
if [[ -z "$ARCHIVE" || ! -f "$ARCHIVE" ]]; then
  echo "error: could not locate packed archive in pack output" >&2; exit 2
fi
echo "    -> $ARCHIVE"

# Read plugin_id + health-check timeout from the manifest. Use Python
# rather than yq so we don't need an extra dep on operator boxes.
MANIFEST="$PLUGIN_DIR/manifest.yaml"
[[ -f "$MANIFEST" ]] || MANIFEST="$PLUGIN_DIR/plugin.yaml"
read -r PLUGIN_ID HEALTH_TIMEOUT < <("$PY" - <<PYEOF
import sys, yaml
with open(r"$MANIFEST", "r", encoding="utf-8") as f:
    m = yaml.safe_load(f)
hc = (m.get("health_check") or {}).get("timeout_seconds", 30)
print(m["plugin_id"], int(hc))
PYEOF
)

if (( DO_INSTALL == 0 )); then
  echo ">>> --no-install set; archive ready at $ARCHIVE"
  exit 0
fi

# --- 3. login --------------------------------------------------------------
if [[ -z "$TOKEN" ]]; then
  echo ">>> login as $USERNAME"
  LOGIN_RESP=$(curl -sS -X POST "$BASE_URL/auth/login" \
    -H "Content-Type: application/json" \
    -d "{\"username\":\"$USERNAME\",\"password\":\"$PASSWORD\"}")
  TOKEN=$("$PY" -c "import json,sys; print(json.loads(sys.stdin.read()).get('access_token',''))" <<<"$LOGIN_RESP")
  if [[ -z "$TOKEN" ]]; then
    echo "error: /auth/login returned no access_token: $LOGIN_RESP" >&2
    exit 3
  fi
fi

# --- 4. install ------------------------------------------------------------
echo ">>> POST /admin/plugins/install"
HTTP_CODE=$(curl -sS -o /tmp/install.json -w '%{http_code}' \
  -X POST "$BASE_URL/admin/plugins/install" \
  -H "Authorization: Bearer $TOKEN" \
  -F "file=@$ARCHIVE")
INSTALL_BODY=$(cat /tmp/install.json)
if [[ "$HTTP_CODE" != "201" && "$HTTP_CODE" != "200" ]]; then
  echo "error: install failed (HTTP $HTTP_CODE): $INSTALL_BODY" >&2
  exit 4
fi
echo "    install OK: $INSTALL_BODY"

# --- 5. liveness wait ------------------------------------------------------
if (( DO_WAIT == 0 )); then
  echo ">>> --no-wait set; not polling /plugins/$PLUGIN_ID/health"
  exit 0
fi
echo ">>> waiting up to ${HEALTH_TIMEOUT}s for $PLUGIN_ID to announce..."
DEADLINE=$(( $(date +%s) + HEALTH_TIMEOUT ))
while (( $(date +%s) < DEADLINE )); do
  CODE=$(curl -sS -o /dev/null -w '%{http_code}' \
    -H "Authorization: Bearer $TOKEN" \
    "$BASE_URL/plugins/$PLUGIN_ID/health" || true)
  if [[ "$CODE" == "200" ]]; then
    echo "    $PLUGIN_ID is live."
    exit 0
  fi
  sleep 2
done
echo "error: $PLUGIN_ID did not appear live within ${HEALTH_TIMEOUT}s" >&2
exit 5
