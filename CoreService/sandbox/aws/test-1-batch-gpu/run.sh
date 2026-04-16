#!/usr/bin/env bash
# End-to-end: setup, submit, wait. Does NOT teardown — run 04-teardown.sh when done.
set -euo pipefail
SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" &>/dev/null && pwd)"
cd "$SCRIPT_DIR"
bash ./01-setup-compute-env.sh
bash ./02-setup-queue-and-def.sh
bash ./03-submit.sh
