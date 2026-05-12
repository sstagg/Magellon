#!/usr/bin/env bash
# Build the template-picker plugin .mpn archive for e2e tests.
#
# Mirrors scripts/build_fft_mpn.sh — the template-picker e2e
# (test_template_picker_e2e.py) installs from this fixture.
#
# Usage:
#   scripts/build_template_picker_mpn.sh                 # default output path
#   scripts/build_template_picker_mpn.sh /tmp/out.mpn    # custom output
set -euo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
REPO="$(cd "$HERE/../.." && pwd)"
PLUGIN_DIR="$REPO/plugins/magellon_template_picker_plugin"
DEFAULT_OUT_DIR="$REPO/CoreService/tests/integration/fixtures"
SDK_DIR="$REPO/magellon-sdk"

if [[ ! -d "$PLUGIN_DIR" ]]; then
    echo "template-picker plugin source not found: $PLUGIN_DIR" >&2
    exit 1
fi

VERSION="$(grep -E '^version:' "$PLUGIN_DIR/manifest.yaml" | awk '{print $2}')"
if [[ -z "$VERSION" ]]; then
    echo "could not read version from $PLUGIN_DIR/manifest.yaml" >&2
    exit 1
fi

OUT_PATH="${1:-$DEFAULT_OUT_DIR/template-picker-$VERSION.mpn}"
mkdir -p "$(dirname "$OUT_PATH")"

if command -v magellon-sdk >/dev/null 2>&1; then
    magellon-sdk plugin pack "$PLUGIN_DIR" --output "$OUT_PATH" --force
else
    PYTHONPATH="$SDK_DIR/src${PYTHONPATH:+:$PYTHONPATH}" \
        python -m magellon_sdk.cli plugin pack "$PLUGIN_DIR" --output "$OUT_PATH" --force
fi

echo "built: $OUT_PATH"
