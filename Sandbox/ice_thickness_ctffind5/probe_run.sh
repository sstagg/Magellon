#!/usr/bin/env bash
# Probe a single CTFFIND5 run interactively to discover the exact prompt
# sequence for the v5 thickness-aware mode.
set -euo pipefail
INPUT="${1:-/data/24dec03a/home/original/24dec03a_00031gr_00001sq_v01_00003hl_00002ex.mrc}"
WORK="$(mktemp -d)"
cp "$INPUT" "$WORK/in.mrc"

# 24dec03a session: 300 kV, Cs=2.7 mm, exposure pixel size 0.79 A
# Defaults from Elferich et al. 2024:
#   spectrum size 512, search 30..4 A, defocus 5000..50000 A in 100 A
#   astigmatism known? no
#   sample tilt? no
#   sample thickness? yes (with brute-force + 2D refinement)
docker run --rm -i \
    -v "$WORK":/work \
    -v "C:/projects/Magellon/Sandbox/ice_thickness_ctffind5":/opt/ctffind5:ro \
    ctffind5:latest <<'EOF' 2>&1 | tee "$WORK/log.txt"
/work/in.mrc
no
/work/diag.mrc
0.79
300
2.7
0.07
512
30
4
5000
50000
100
no
no
no
no
yes
yes
yes
no
no
EOF

echo "---out files---"
ls -la "$WORK/"
echo "---thickness lines---"
grep -iE "(thickness|nodes|sample)" "$WORK/log.txt" || true
echo "---diag txt if any---"
[ -f "$WORK/diag.txt" ] && cat "$WORK/diag.txt"
rm -rf "$WORK" 2>/dev/null || true
