#!/usr/bin/env bash
# Rebuild magellon-sdk wheel and refresh the bundled copy in every plugin
# directory that has a requirements.docker.txt referencing it.
#
# Why: the production Dockerfiles (CTF, MotionCor) install the SDK from a
# bundled wheel inside the plugin dir rather than via an editable
# ``../../magellon-sdk`` path, because the editable path doesn't exist
# inside the Docker build context. Without this script, plugin Docker
# images silently install a stale SDK any time the SDK is edited locally
# but the wheel isn't rebuilt + recommitted.
#
# Run this BEFORE ``docker build`` for any of the bundled-wheel plugins.
# Replaces the wheel unconditionally — pip-built wheels embed build-time
# metadata so byte-comparison is unreliable; just refresh.
#
# Usage:
#     scripts/rebuild-sdk-wheels.sh
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
SDK_DIR="${REPO_ROOT}/magellon-sdk"
TMP_DIR="$(mktemp -d)"
trap 'rm -rf "$TMP_DIR"' EXIT

# Plugins with a bundled wheel.
#
# Two destination layouts are supported per-plugin:
#   * Default: wheel goes at the plugin root next to requirements.docker.txt
#     (the original Docker-bundle pattern: CTF, MotionCor).
#   * "wheels/" subdir: wheel goes under <plugin>/wheels/ for plugins
#     whose pyproject.toml uses ``[tool.uv.sources] magellon-sdk =
#     { path = "wheels/<wheel>" }`` (the .mpn install pipeline pattern:
#     FFT). Append ``:wheels`` to the plugin path to opt in.
BUNDLED_PLUGINS=(
    "plugins/magellon_ctf_plugin"
    "plugins/magellon_motioncor_plugin"
    "plugins/magellon_fft_plugin:wheels"
)

echo "→ building magellon-sdk wheel from ${SDK_DIR}..."
pip wheel --quiet --no-deps --wheel-dir "$TMP_DIR" "$SDK_DIR"
NEW_WHEEL="$(ls "$TMP_DIR"/magellon_sdk-*.whl | head -1)"
if [[ -z "$NEW_WHEEL" ]]; then
    echo "  ERROR: pip wheel produced no .whl in $TMP_DIR" >&2
    exit 1
fi
WHEEL_NAME="$(basename "$NEW_WHEEL")"
echo "  built: $WHEEL_NAME"

for entry in "${BUNDLED_PLUGINS[@]}"; do
    plugin="${entry%%:*}"
    layout="${entry#*:}"
    [[ "$layout" == "$entry" ]] && layout=""
    plugin_root="${REPO_ROOT}/${plugin}"
    if [[ ! -d "$plugin_root" ]]; then
        echo "  skip ${plugin} — directory not found"
        continue
    fi
    if [[ "$layout" == "wheels" ]]; then
        dst_dir="${plugin_root}/wheels"
        mkdir -p "$dst_dir"
        # Wipe any prior wheels in this dir so a stale version doesn't
        # silently linger if the SDK version was bumped.
        rm -f "${dst_dir}"/magellon_sdk-*.whl
    else
        dst_dir="$plugin_root"
    fi
    cp "$NEW_WHEEL" "${dst_dir}/${WHEEL_NAME}"
    echo "  ${plugin}: refreshed → ${dst_dir#${REPO_ROOT}/}/${WHEEL_NAME}"
done

echo "done. Remember to ${0##*/}-then-rebuild Docker images and commit"
echo "the refreshed .whl files alongside any SDK changes."
