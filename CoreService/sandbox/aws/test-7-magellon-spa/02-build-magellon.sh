#!/usr/bin/env bash
# Ship the local source tree + cargo build --release --features spa.
# ~5 min on a c5.4xlarge for the first build (release profile, full
# dependency tree).
#
# Why scp instead of git clone: the magellon-rust-mrc repo is private
# on github.com/khoshbin/. A non-interactive ssh session on the
# instance can't auth to GitHub (no TTY for username/token prompt),
# so `git clone` fails silently with "could not read Username". The
# instance never gets the source, the build never runs, and
# subsequent stages all fail to find magellon-spa. Shipping the
# already-checked-out local tree sidesteps the auth problem and is
# faster anyway.

set -euo pipefail
SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" &>/dev/null && pwd)"
MY_DIR="$SCRIPT_DIR"; source "${SCRIPT_DIR}/../common/activate.sh"; SCRIPT_DIR="$MY_DIR"
source "${SCRIPT_DIR}/.instance-env"

# Where the local checkout lives. Adjust if you move the repo.
LOCAL_REPO="${LOCAL_REPO:-C:/projects/magellon-rust-mrc}"
if [ ! -d "$LOCAL_REPO" ]; then
  echo "ERROR: LOCAL_REPO=${LOCAL_REPO} not found. Set LOCAL_REPO env or check path." >&2
  exit 1
fi

# Tar + scp the source. Exclude target/ + .git so we don't ship a
# multi-GB build cache + history. The instance starts fresh.
echo "=== bundling source from $LOCAL_REPO ==="
TMP_TAR=$(mktemp --suffix=.tar.gz)
trap 'rm -f "$TMP_TAR"' EXIT
tar --exclude='target' --exclude='.git' --exclude='node_modules' \
    --exclude='*.mrc' --exclude='*.mrcs' \
    -C "$LOCAL_REPO" -czf "$TMP_TAR" .
du -h "$TMP_TAR"

echo "=== shipping to instance ==="
scp -o StrictHostKeyChecking=no -i "$KEY_FILE" "$TMP_TAR" \
    ubuntu@"$PUBLIC_IP":/tmp/magellon-source.tar.gz

ssh -o StrictHostKeyChecking=no -i "$KEY_FILE" ubuntu@"$PUBLIC_IP" 'bash -s' <<'REMOTE'
set -euxo pipefail
mkdir -p /src/magellon-rust-mrc
cd /src/magellon-rust-mrc
tar -xzf /tmp/magellon-source.tar.gz
rm /tmp/magellon-source.tar.gz

echo "=== source landed ==="
ls Cargo.toml src/algorithms/spa | head -10

echo "=== building --release --features spa --bin magellon-spa ==="
cargo build --release --features spa --bin magellon-spa 2>&1 | tail -30

ls -la target/release/magellon-spa
sudo ln -sf /src/magellon-rust-mrc/target/release/magellon-spa /usr/local/bin/magellon-spa

echo "=== smoke test ==="
magellon-spa --help | head -20
REMOTE

echo
echo "Next: ./10-run-full-pipeline.sh (or run 03–07 manually)"
