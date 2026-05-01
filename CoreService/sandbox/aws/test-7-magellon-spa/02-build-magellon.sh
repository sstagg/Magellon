#!/usr/bin/env bash
# Clone magellon-rust-mrc + cargo build --release --features spa.
# ~5 min on a c5.4xlarge for the first build (release profile, full
# dependency tree).
set -euo pipefail
SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" &>/dev/null && pwd)"
MY_DIR="$SCRIPT_DIR"; source "${SCRIPT_DIR}/../common/activate.sh"; SCRIPT_DIR="$MY_DIR"
source "${SCRIPT_DIR}/.instance-env"

# The repo is on github.com/khoshbin/magellon-rust-mrc. Clone HEAD on
# main; the binary we need is the CLI built in commit f8bb8fd or later.
REPO_URL="https://github.com/khoshbin/magellon-rust-mrc.git"

ssh -o StrictHostKeyChecking=no -i "$KEY_FILE" ubuntu@"$PUBLIC_IP" 'bash -s' <<REMOTE
set -euxo pipefail
cd /src
if [ ! -d magellon-rust-mrc ]; then
  git clone --depth 1 ${REPO_URL}
fi
cd magellon-rust-mrc
git pull --ff-only || true

echo "=== HEAD commit ==="
git log -1 --oneline

echo "=== building --release --features spa --bin magellon-spa ==="
# Use ~all CPUs for the build itself.
cargo build --release --features spa --bin magellon-spa 2>&1 | tail -30

ls -la target/release/magellon-spa
sudo ln -sf /src/magellon-rust-mrc/target/release/magellon-spa /usr/local/bin/magellon-spa

echo "=== smoke test ==="
magellon-spa --help | head -20
REMOTE

echo
echo "Next: ./10-run-full-pipeline.sh (or run 03–07 manually)"
