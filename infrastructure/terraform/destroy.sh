#!/usr/bin/env bash
# destroy.sh — tear down the entire Magellon AWS deployment.
#
# Usage:
#   cd infrastructure/terraform
#   ./destroy.sh [--force]
#
# --force  skips the confirmation prompts (for scripted teardowns)
#
# What this destroys:
#   1. us-east-1 region stack (EC2, ALB, EFS, VPC, IAM roles, CloudWatch, WAF…)
#   2. Orphaned EBS volumes (delete_on_termination=false — Terraform leaves these)
#   3. Force-deletes the Secrets Manager secret (skips the 7-day recovery window)
#   4. Optionally destroys global/ (S3 state bucket) — prompts separately
#
# What is NOT automatically deleted:
#   - EFS data: snapshots or leftover mount targets may need manual cleanup
#   - CloudWatch log groups: retained by default; delete via console if desired
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
GLOBAL_DIR="$SCRIPT_DIR/global"
REGION_DIR="$SCRIPT_DIR/regions/us-east-1"
REGION="us-east-1"
FORCE=false

for arg in "$@"; do
  [[ "$arg" == "--force" ]] && FORCE=true
done

# ── Colour helpers ─────────────────────────────────────────────────────────────
GREEN='\033[0;32m'; YELLOW='\033[1;33m'; RED='\033[0;31m'; NC='\033[0m'
info()  { echo -e "${GREEN}[destroy]${NC} $*"; }
warn()  { echo -e "${YELLOW}[destroy]${NC} $*"; }
error() { echo -e "${RED}[destroy]${NC} $*" >&2; exit 1; }

confirm() {
  if $FORCE; then return 0; fi
  echo -e "${RED}WARNING:${NC} $1"
  read -r -p "Type 'yes' to continue: " answer
  [[ "$answer" == "yes" ]] || { echo "Aborted."; exit 1; }
}

# ── Sanity checks ──────────────────────────────────────────────────────────────
command -v terraform >/dev/null 2>&1 || error "terraform not found in PATH"
command -v aws       >/dev/null 2>&1 || error "aws CLI not found in PATH"

aws sts get-caller-identity >/dev/null 2>&1 \
  || error "AWS credentials not configured. Run 'aws configure' or set AWS_PROFILE."

# ── Confirmation ───────────────────────────────────────────────────────────────
confirm "This will PERMANENTLY DELETE all Magellon AWS resources in us-east-1."

# ── Step 1: Destroy region stack ───────────────────────────────────────────────
info "=== Step 1: Destroying us-east-1 region stack ==="
cd "$REGION_DIR"

if [[ -f ".terraform/terraform.tfstate" || -f "terraform.tfstate" ]]; then
  terraform init -reconfigure -upgrade 2>/dev/null || true
  terraform destroy -auto-approve || warn "terraform destroy reported errors — continuing cleanup"
else
  warn "No Terraform state found in regions/us-east-1 — skipping terraform destroy"
fi

# ── Step 2: Force-delete Secrets Manager secret ────────────────────────────────
# Terraform schedules deletion with a 7-day recovery window. Force-delete
# it immediately so a fresh deploy can reuse the same secret name.
info "=== Step 2: Force-deleting Secrets Manager secrets ==="
SECRET_ARNS=$(aws secretsmanager list-secrets \
  --filters Key=name,Values=/magellon/ \
  --query "SecretList[].ARN" \
  --output text \
  --region "$REGION" 2>/dev/null || echo "")

if [[ -n "$SECRET_ARNS" ]]; then
  for arn in $SECRET_ARNS; do
    info "  Force-deleting secret: $arn"
    aws secretsmanager delete-secret \
      --secret-id "$arn" \
      --force-delete-without-recovery \
      --region "$REGION" 2>/dev/null || warn "  Could not delete $arn (may already be gone)"
  done
else
  info "  No /magellon/ secrets found — nothing to clean up"
fi

# ── Step 3: Delete orphaned EBS volumes ────────────────────────────────────────
# Volumes have delete_on_termination=false so they survive instance termination.
info "=== Step 3: Cleaning up orphaned EBS volumes ==="
VOLUME_IDS=$(aws ec2 describe-volumes \
  --filters \
    "Name=status,Values=available" \
    "Name=tag:Project,Values=magellon" \
  --query "Volumes[].VolumeId" \
  --output text \
  --region "$REGION" 2>/dev/null || echo "")

if [[ -n "$VOLUME_IDS" ]]; then
  warn "Found orphaned Magellon EBS volumes: $VOLUME_IDS"
  confirm "Delete these EBS volumes? This CANNOT be undone."
  for vol in $VOLUME_IDS; do
    info "  Deleting volume $vol"
    aws ec2 delete-volume --volume-id "$vol" --region "$REGION" 2>/dev/null \
      || warn "  Could not delete $vol (may be in-use or already deleted)"
  done
else
  info "  No orphaned EBS volumes found"
fi

# ── Step 4: Delete orphaned EFS file systems ───────────────────────────────────
info "=== Step 4: Checking for orphaned EFS file systems ==="
EFS_IDS=$(aws efs describe-file-systems \
  --query "FileSystems[?Tags[?Key=='Project' && Value=='magellon']].FileSystemId" \
  --output text \
  --region "$REGION" 2>/dev/null || echo "")

if [[ -n "$EFS_IDS" ]]; then
  warn "Found Magellon EFS file systems: $EFS_IDS"
  warn "EFS deletion requires removing all mount targets first."
  warn "Run: aws efs describe-mount-targets --file-system-id <id> --region $REGION"
  warn "Then: aws efs delete-mount-target --mount-target-id <mt-id>"
  warn "Then: aws efs delete-file-system --file-system-id <id>"
  warn "Skipping automatic EFS deletion to avoid accidental data loss."
fi

# ── Step 5: Optionally destroy global/ (S3 state bucket) ──────────────────────
info "=== Step 5: Global resources (S3 state bucket) ==="
echo ""
warn "The S3 state bucket 'magellon-terraform-state' was NOT destroyed."
warn "It contains all Terraform state files and has force_destroy=false."
echo ""
echo "To delete it (only if you are SURE you no longer need the state):"
echo "  1. aws s3 rm s3://magellon-terraform-state --recursive"
echo "  2. cd $GLOBAL_DIR && terraform destroy -auto-approve"
echo ""

if ! $FORCE; then
  read -r -p "Destroy the S3 state bucket now? (yes/no): " ans
  if [[ "$ans" == "yes" ]]; then
    info "Emptying S3 state bucket..."
    aws s3 rm s3://magellon-terraform-state --recursive --region "$REGION" \
      || warn "S3 rm failed — bucket may already be empty or may not exist"

    cd "$GLOBAL_DIR"
    terraform init -reconfigure -upgrade 2>/dev/null || true
    terraform destroy -auto-approve \
      || warn "global destroy failed — bucket may already be gone"
    info "Global resources destroyed."
  else
    info "Skipped. The state bucket is preserved for future use."
  fi
fi

# ── Done ───────────────────────────────────────────────────────────────────────
info "=== Teardown complete ==="
echo ""
echo "Remaining manual cleanup (if desired):"
echo "  - CloudWatch Log Groups: /magellon/prod/* (retained by default)"
echo "  - CloudWatch Dashboard"
echo "  - EFS data (if EFS was not deleted above)"
echo "  - Route 53 records (if domain was configured)"
echo ""
