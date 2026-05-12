#!/usr/bin/env bash
# Build the FFT plugin .mpn archive for e2e tests.
#
# The e2e wave centerpiece (test_install_lifecycle_dispatch_e2e.py)
# installs FFT via POST /admin/plugins/install with a .mpn upload.
# This script produces that archive deterministically:
#
#   scripts/build_fft_mpn.sh
#     -> tests/integration/fixtures/fft-<version>.mpn
#
# Re-runs are idempotent (passes --force). The archive_id changes on
# each pack (UUID v7); the install endpoint uses plugin_id + version,
# not archive_id, so this is fine for re-installation across test runs.
#
# Usage:
#   scripts/build_fft_mpn.sh                 # default output path
#   scripts/build_fft_mpn.sh /tmp/out.mpn    # custom output
set -euo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
REPO="$(cd "$HERE/../.." && pwd)"
PLUGIN_DIR="$REPO/plugins/magellon_fft_plugin"
DEFAULT_OUT_DIR="$REPO/CoreService/tests/integration/fixtures"
SDK_DIR="$REPO/magellon-sdk"

if [[ ! -d "$PLUGIN_DIR" ]]; then
    echo "fft plugin source not found: $PLUGIN_DIR" >&2
    exit 1
fi

VERSION="$(grep -E '^version:' "$PLUGIN_DIR/manifest.yaml" | awk '{print $2}')"
if [[ -z "$VERSION" ]]; then
    echo "could not read version from $PLUGIN_DIR/manifest.yaml" >&2
    exit 1
fi

OUT_PATH="${1:-$DEFAULT_OUT_DIR/fft-$VERSION.mpn}"
mkdir -p "$(dirname "$OUT_PATH")"

# Prefer the installed magellon-sdk CLI; fall back to running the
# module directly with the SDK src/ on PYTHONPATH (useful when the
# SDK isn't pip-installed in the active env).
if command -v magellon-sdk >/dev/null 2>&1; then
    magellon-sdk plugin pack "$PLUGIN_DIR" --output "$OUT_PATH" --force
else
    PYTHONPATH="$SDK_DIR/src${PYTHONPATH:+:$PYTHONPATH}" \
        python -m magellon_sdk.cli plugin pack "$PLUGIN_DIR" --output "$OUT_PATH" --force
fi

echo "built: $OUT_PATH"
