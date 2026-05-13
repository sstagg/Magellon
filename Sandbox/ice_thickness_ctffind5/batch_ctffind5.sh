#!/usr/bin/env bash
# Batch CTFFIND5 over a glob of exposures, accumulating thickness in TSV.
#
# Usage:
#   batch_ctffind5.sh <output_tsv> <glob>
# Example:
#   batch_ctffind5.sh results.tsv 'C:/magellon/gpfs/24dec03a/home/original/*ex.mrc'
set -euo pipefail
OUT="${1:?usage: batch_ctffind5.sh <out.tsv> <glob>}"
shift
WORK="C:/Users/bkhos.BEHDAD/AppData/Local/Temp/ctffind5_run"
mkdir -p "$WORK"

# Header
printf "image\tdefocus1_A\tdefocus2_A\tcc\tthickness_A\tthickness_nm\n" > "$OUT"

count=0
for path in "$@"; do
    [[ -f "$path" ]] || continue
    stem=$(basename "${path%.*}")
    cp "$path" "$WORK/in.mrc"
    rm -f "$WORK/diag.mrc" "$WORK/diag.txt" "$WORK/diag_avrot.txt"

    MSYS_NO_PATHCONV=1 docker run --rm -i \
        -v "$WORK":/work \
        -v "C:/projects/Magellon/Sandbox/ice_thickness_ctffind5":/opt/ctffind5:ro \
        ctffind5:latest <<'EOF' >/dev/null 2>&1
/work/in.mrc
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
no
yes
yes
yes
30.0
3.0
no
no
no
EOF

    if [[ -f "$WORK/diag.txt" ]]; then
        # Last (and only) data line: micnum d1 d2 azim phase cc spacing tilt_ax tilt thickness_A
        line=$(grep -v '^#' "$WORK/diag.txt" | tail -1)
        d1=$(echo "$line"  | awk '{print $2}')
        d2=$(echo "$line"  | awk '{print $3}')
        cc=$(echo "$line"  | awk '{print $6}')
        tA=$(echo "$line"  | awk '{print $10}')
        tnm=$(awk -v x="$tA" 'BEGIN{printf "%.2f", x/10.0}')
        printf "%s\t%s\t%s\t%s\t%s\t%s\n" "$stem" "$d1" "$d2" "$cc" "$tA" "$tnm" >> "$OUT"
        count=$((count+1))
        printf "[%3d] %-58s thickness = %6.1f A = %5.1f nm\n" "$count" "$stem" "$tA" "$tnm"
    else
        printf "[ERR] %s\n" "$stem" >&2
    fi
done

echo
echo "Wrote $count rows to $OUT"
