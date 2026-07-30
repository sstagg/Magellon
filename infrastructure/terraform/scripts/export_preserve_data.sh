#!/bin/bash
##############################################################################
# export_preserve_data.sh
#
# Run this on the OLD EC2 BEFORE running terraform apply / destroying the
# old infrastructure.
#
# Dumps all tables EXCEPT the seven import/session tables so that accounts,
# roles, camera configs, plugins, pipelines, and projects are preserved on
# the new instance. Session images and jobs are intentionally excluded.
#
# The dump is written to EFS (/mnt/efs/magellon/db-migration/preserve_data.sql).
# Since EFS is shared and persists across instance replacements, the new EC2
# picks it up automatically on first boot and imports it after MySQL starts.
#
# Usage:
#   ssh ubuntu@<old-ec2>  (or: aws ssm start-session --target <instance-id>)
#   sudo bash /opt/magellon-repo/infrastructure/terraform/scripts/export_preserve_data.sh
##############################################################################
set -euo pipefail

# ── Load credentials from the running .env ────────────────────────────────────
ENV_FILE="/opt/magellon/.env"
if [ -f "$ENV_FILE" ]; then
  # shellcheck disable=SC1090
  set -a; source "$ENV_FILE"; set +a
fi

MYSQL_ROOT_PASSWORD="${MYSQL_ROOT_PASSWORD:-behd1d2}"
MYSQL_DATABASE="${MYSQL_DATABASE:-magellon01}"
CONTAINER="magellon-mysql_container"
DEST_DIR="/mnt/efs/magellon/db-migration"
DEST="$DEST_DIR/preserve_data.sql"

# ── Tables to EXCLUDE (import/session data — can be rebuilt by re-importing) ──
# These match the CLEAR_TABLES list in CoreService/scripts/reset_demo_data.py.
IGNORE_ARGS=""
for TABLE in msession image image_meta_data image_job image_job_task artifact atlas; do
  IGNORE_ARGS="$IGNORE_ARGS --ignore-table=${MYSQL_DATABASE}.${TABLE}"
done

echo "=== Magellon DB preserve export ==="
echo "Source container : $CONTAINER"
echo "Database         : $MYSQL_DATABASE"
echo "Destination      : $DEST"
echo ""
echo "Excluded (import data):"
echo "  msession, image, image_meta_data, image_job, image_job_task, artifact, atlas"
echo ""
echo "Preserved (accounts, config):"
echo "  sys_sec_user, sys_sec_role, sys_sec_user_role, camera, microscope,"
echo "  plugin, pipeline, project, sample_type, casbin_rule, and all other tables"
echo ""

# ── Verify MySQL is running ───────────────────────────────────────────────────
if ! docker ps --format '{{.Names}}' | grep -q "^${CONTAINER}$"; then
  echo "ERROR: Container '$CONTAINER' is not running."
  exit 1
fi

if ! docker exec "$CONTAINER" \
    mysql -u root -p"$MYSQL_ROOT_PASSWORD" -e "SELECT 1" >/dev/null 2>&1; then
  echo "ERROR: Cannot connect to MySQL in container '$CONTAINER'."
  exit 1
fi

# ── Create destination on EFS ─────────────────────────────────────────────────
mkdir -p "$DEST_DIR"
chmod 777 "$DEST_DIR"

# ── Dump (schema + data, minus excluded tables) ───────────────────────────────
echo "Running mysqldump..."
# shellcheck disable=SC2086
docker exec "$CONTAINER" mysqldump \
  -u root -p"$MYSQL_ROOT_PASSWORD" \
  --single-transaction \
  --routines \
  --triggers \
  --set-gtid-purged=OFF \
  $IGNORE_ARGS \
  "$MYSQL_DATABASE" > "$DEST"

chmod 644 "$DEST"
LINES=$(wc -l < "$DEST")
SIZE=$(du -sh "$DEST" | cut -f1)

echo ""
echo "=== Export complete ==="
echo "  $DEST"
echo "  $LINES lines / $SIZE"
echo ""
echo "Next steps:"
echo "  1. Run: cd infrastructure/terraform && ./deploy.sh"
echo "  2. Terraform creates a new EC2. On first boot it will auto-import"
echo "     this dump after MySQL starts."
echo "  3. After verifying the new instance is healthy, terminate the old one."
