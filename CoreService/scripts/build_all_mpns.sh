#!/usr/bin/env bash
# Build .mpn archives for every production plugin under plugins/.
# Wave 6 Phase 25 — used by tests/integration/ for e2e fixtures and
# by the hub-publish workflow when authoring a new plugin release.
#
# Pre-pack steps per plugin:
#   1. ``magellon-sdk plugin lint <dir>`` — fail-fast if any plugin
#      has an error-level issue.
#   2. ``magellon-sdk plugin pack <dir> -o <output>/<plugin>-<v>.mpn``
#
# Output: every plugin produces a versioned .mpn under
# ``CoreService/tests/integration/fixtures/``.
#
# Usage:
#   scripts/build_all_mpns.sh                 # default output dir
#   scripts/build_all_mpns.sh /tmp/mpns       # custom output dir
set -euo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
REPO="$(cd "$HERE/../.." && pwd)"
PLUGINS_DIR="$REPO/plugins"
SDK_DIR="$REPO/magellon-sdk"
DEFAULT_OUT_DIR="$REPO/CoreService/tests/integration/fixtures"

OUT_DIR="${1:-$DEFAULT_OUT_DIR}"
mkdir -p "$OUT_DIR"

# Plugin → manifest.yaml directories under plugins/. Add new entries
# here when a new production plugin lands; ``build_fft_mpn.sh`` (Wave
# 2) stays as the single-plugin shorthand.
PLUGINS=(
    "magellon_fft_plugin"
    "magellon_ctf_plugin"
    "magellon_motioncor_plugin"
    "magellon_topaz_plugin"
    "magellon_ptolemy_plugin"
    "magellon_stack_maker_plugin"
    "magellon_can_classifier_plugin"
)

SDK_RUN="env PYTHONPATH=\"$SDK_DIR/src\${PYTHONPATH:+:\$PYTHONPATH}\" python -m magellon_sdk.cli"
if command -v magellon-sdk >/dev/null 2>&1; then
    SDK_RUN="magellon-sdk"
fi

failures=0
for plugin in "${PLUGINS[@]}"; do
    src="$PLUGINS_DIR/$plugin"
    if [[ ! -d "$src" ]]; then
        echo "skip: $plugin not found at $src" >&2
        continue
    fi
    if [[ ! -f "$src/manifest.yaml" ]]; then
        echo "skip: $plugin has no manifest.yaml" >&2
        continue
    fi

    echo "=== Linting $plugin ==="
    if ! eval "$SDK_RUN" plugin lint "\"$src\""; then
        echo "lint failed for $plugin" >&2
        failures=$((failures + 1))
        continue
    fi

    version="$(grep -E '^version:' "$src/manifest.yaml" | awk '{print $2}')"
    plugin_id="$(grep -E '^plugin_id:' "$src/manifest.yaml" | awk '{print $2}')"
    out_path="$OUT_DIR/${plugin_id}-${version}.mpn"

    echo "=== Packing $plugin → $out_path ==="
    if ! eval "$SDK_RUN" plugin pack "\"$src\"" --output "\"$out_path\"" --force; then
        echo "pack failed for $plugin" >&2
        failures=$((failures + 1))
        continue
    fi
done

if (( failures > 0 )); then
    echo "FAIL: $failures plugin(s) did not pack cleanly" >&2
    exit 1
fi
echo "OK: built $(ls "$OUT_DIR"/*.mpn 2>/dev/null | wc -l) .mpn archive(s) under $OUT_DIR"
