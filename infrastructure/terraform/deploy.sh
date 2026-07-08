#!/usr/bin/env bash
# deploy.sh — full Magellon AWS deployment for us-east-1.
#
# Usage:
#   cd infrastructure/terraform
#   ./deploy.sh
#
# Prerequisites:
#   - AWS credentials configured (aws configure, env vars, or IAM instance profile)
#   - Terraform >= 1.10 in PATH
#   - terraform.tfvars filled in at regions/us-east-1/terraform.tfvars
#     (copy from terraform.tfvars.example and edit)
#
# What this does:
#   1. Applies global/ — creates the S3 remote-state bucket (one-time bootstrap)
#   2. Applies regions/us-east-1/ — VPC, EFS, IAM, EC2, ALB, Monitoring
#      EC2 user-data clones the repo, fetches secrets, and starts all containers.
#   3. Prints access URL and useful SSM commands.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
GLOBAL_DIR="$SCRIPT_DIR/global"
REGION_DIR="$SCRIPT_DIR/regions/us-east-1"

# ── Colour helpers ─────────────────────────────────────────────────────────────
GREEN='\033[0;32m'; YELLOW='\033[1;33m'; RED='\033[0;31m'; NC='\033[0m'
info()  { echo -e "${GREEN}[deploy]${NC} $*"; }
warn()  { echo -e "${YELLOW}[deploy]${NC} $*"; }
error() { echo -e "${RED}[deploy]${NC} $*" >&2; exit 1; }

# ── Sanity checks ──────────────────────────────────────────────────────────────
command -v terraform >/dev/null 2>&1 || error "terraform not found in PATH"
command -v aws       >/dev/null 2>&1 || error "aws CLI not found in PATH"

aws sts get-caller-identity >/dev/null 2>&1 \
  || error "AWS credentials not configured. Run 'aws configure' or set AWS_PROFILE."

[[ -f "$REGION_DIR/terraform.tfvars" ]] \
  || error "Missing $REGION_DIR/terraform.tfvars — copy terraform.tfvars.example and fill in secrets."

# Check that the user actually changed the placeholder passwords
if grep -q "CHANGE_ME" "$REGION_DIR/terraform.tfvars" 2>/dev/null; then
  error "terraform.tfvars still contains CHANGE_ME placeholders. Update all secrets before deploying."
fi

# ── Step 1: Bootstrap global/ (S3 state bucket) ───────────────────────────────
info "=== Step 1: Bootstrapping global resources (S3 state bucket) ==="
cd "$GLOBAL_DIR"
terraform init -upgrade
# Apply is idempotent — safe to re-run if bucket already exists
terraform apply -auto-approve

# ── Step 2: Apply region stack ─────────────────────────────────────────────────
info "=== Step 2: Deploying us-east-1 region stack ==="
cd "$REGION_DIR"

# Initialise (or reinitialise) with the remote S3 backend
terraform init -upgrade -reconfigure

# ── Auto-import if resources exist but state is empty ─────────────────────────
# A plan with an empty state against existing AWS resources fails with
# "already exists" errors. Detect this by checking whether any key resource
# is in AWS but not yet in state; if so, run import.sh first.
STATE_COUNT=$(terraform state list 2>/dev/null | wc -l || echo "0")
EFS_EXISTS=$(aws efs describe-file-systems \
  --query "FileSystems[?CreationToken=='magellon-prod-use1-shared'].FileSystemId" \
  --output text --region us-east-1 2>/dev/null || echo "")

if [[ "$STATE_COUNT" -lt 5 && -n "$EFS_EXISTS" && "$EFS_EXISTS" != "None" ]]; then
  warn "Detected existing AWS resources with empty/partial Terraform state."
  warn "Running import.sh to adopt them before applying..."
  cd "$SCRIPT_DIR"
  bash "$SCRIPT_DIR/import.sh"
  cd "$REGION_DIR"
fi

info "Planning deployment..."
terraform plan -out=tfplan

info "Applying..."
terraform apply tfplan
rm -f tfplan

# ── Step 3: Print outputs ──────────────────────────────────────────────────────
info "=== Deployment complete ==="
echo ""
ALB_DNS=$(terraform output -raw alb_dns_name 2>/dev/null || echo "")
MAIN_IP=$(terraform output -raw main_private_ip 2>/dev/null || echo "")
SECRET_ARN=$(terraform output -raw app_secret_arn 2>/dev/null || echo "")

if [[ -n "$ALB_DNS" ]]; then
  echo -e "${GREEN}  App URL:${NC}       http://$ALB_DNS"
fi
if [[ -n "$MAIN_IP" ]]; then
  echo -e "${GREEN}  Main instance:${NC} $MAIN_IP (private)"
fi
if [[ -n "$SECRET_ARN" ]]; then
  echo -e "${GREEN}  Secrets ARN:${NC}   $SECRET_ARN"
fi

echo ""
echo "── Useful commands ───────────────────────────────────────────────────────"
echo ""
echo "  # Connect to main instance via SSM (no bastion/SSH needed):"
MAIN_ID=$(aws ec2 describe-instances \
  --filters "Name=tag:Name,Values=*-main" "Name=instance-state-name,Values=running" \
  --query "Reservations[0].Instances[0].InstanceId" \
  --output text --region us-east-1 2>/dev/null || echo "<instance-id>")
echo "  aws ssm start-session --target $MAIN_ID --region us-east-1"
echo ""
echo "  # Watch bootstrap log on the instance:"
echo "  sudo tail -f /var/log/magellon-bootstrap.log"
echo ""
echo "  # Check container status:"
echo "  sudo docker compose -f /opt/magellon-repo/Docker/AWS_docker_compose/docker-compose.main.yml ps"
echo ""
echo "  # View backend logs:"
echo "  sudo docker logs magellon-core-container -f"
echo ""
echo "──────────────────────────────────────────────────────────────────────────"
echo ""
warn "Bootstrap runs asynchronously inside the EC2 instance."
warn "The app may take 5–10 minutes to be ready after 'terraform apply' completes."
warn "Check http://$ALB_DNS/health once containers are up."
