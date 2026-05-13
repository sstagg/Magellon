#!/usr/bin/env bash
# Run CTFFIND5 in Docker on a single MRC, extracting per-image thickness.
#
# Usage:
#   run_ctffind5.sh <input.mrc> [pixel_size_A] [kV] [Cs_mm]
#
# Defaults match the 24dec03a session (300 kV, Cs=2.7 mm, exposure-level
# pixel size 0.79 A from the MRC header).
#
# Assumes:
#   * the cisTEM ctffind5 binary lives at C:/projects/Magellon/Sandbox/ice_thickness_ctffind5/ctffind
#     (extract from cisTEM-ctffind5-b21db55.tar.gz; see README.md)
#   * the image docker tag is "ctffind5:latest" (build with build.sh)
#
set -euo pipefail

INPUT="${1:?usage: run_ctffind5.sh <input.mrc> [pixel_size_A] [kV] [Cs_mm]}"
APIX="${2:-0.79}"
KV="${3:-300}"
CS="${4:-2.7}"

SBX_DIR="$(cd "$(dirname "$0")" && pwd)"
BIN_DIR="$SBX_DIR"   # ctffind binary lives next to this script

# Stage the input + output in a tmp dir to mount into the container
WORK="$(mktemp -d)"
cp "$INPUT" "$WORK/in.mrc"

STEM="$(basename "${INPUT%.*}")"

# CTFFIND5 expects stdin-driven config; the relevant lines for thickness
# estimation come from Elferich et al. 2024 (eLife) and the cisTEM docs:
#   * "Estimate sample tilt?"  -> no (single image, no tilt)
#   * "Estimate sample thickness?" -> yes
#   * "Use brute force for thickness" -> yes (slower but more robust)
docker run --rm \
    -v "$WORK":/work \
    -v "$BIN_DIR":/opt/ctffind5:ro \
    ctffind5:latest <<EOF
/work/in.mrc
/work/out_diag.mrc
${APIX}
${KV}
${CS}
0.07
512
30.0
4.0
5000.0
50000.0
500.0
no
no
yes
no
no
yes
no
EOF

# CTFFIND5 emits *_diag.txt next to the diagnostic image with per-image
# values. Copy results out.
mkdir -p "$SBX_DIR/results"
cp "$WORK"/*.txt "$SBX_DIR/results/${STEM}.txt" || true
cp "$WORK/out_diag.mrc" "$SBX_DIR/results/${STEM}_diag.mrc" || true

# Extract the thickness line for stdout
grep -i thickness "$SBX_DIR/results/${STEM}.txt" || \
    echo "(no thickness line found — inspect $SBX_DIR/results/${STEM}.txt)"

rm -rf "$WORK"
