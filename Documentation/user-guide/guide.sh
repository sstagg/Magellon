#!/usr/bin/env bash
# Build the user guide, or retake its screenshots. See README.md.
#   ./guide.sh pdf                    build Magellon-User-Guide.pdf from guide.md
#   ./guide.sh tokens MEMBER ADMIN    log-in tokens for the screenshot scripts (2 hours)
#   ./guide.sh shoot SCRIPT           run shoot/SCRIPT.py (pages, accounts, imports, picking, single_file)
set -euo pipefail
cd "$(dirname "$0")"
IMAGE=magellon-guide:1
docker image inspect $IMAGE >/dev/null 2>&1 || docker build -t $IMAGE .
run() { docker run --rm --user "$(id -u):$(id -g)" -v "$PWD:/guide" -w /guide "$@"; }
case "${1:-}" in
  pdf)    run $IMAGE python build_pdf.py ;;
  tokens) docker exec -i -w /app/CoreService magellon-core-container python - "$2" "$3" \
            < shoot/mint_tokens.py > shoot/.tokens.json && echo "tokens written to shoot/.tokens.json" ;;
  shoot)  run --network host -e HOME=/tmp \
            -v /gpfs/research/stagg/magellon_demo/24dec03a/home:/data:ro \
            -w /guide/shoot $IMAGE python "$2.py" ;;
  *)      sed -n 2,6p "$0"; exit 1 ;;
esac
