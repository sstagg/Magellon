#!/usr/bin/env bash
# import.sh — import existing AWS resources into Terraform state.
#
# Run this when a previous deployment left resources in AWS but the Terraform
# state is empty (e.g., state file lost, fresh init, or failed first apply).
#
# Usage:
#   cd infrastructure/terraform
#   ./import.sh
#
# After this completes successfully, run ./deploy.sh to reconcile and apply
# any pending changes.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REGION_DIR="$SCRIPT_DIR/regions/us-east-1"
REGION="us-east-1"
NAME_PREFIX="magellon-prod-use1"

GREEN='\033[0;32m'; YELLOW='\033[1;33m'; NC='\033[0m'
info() { echo -e "${GREEN}[import]${NC} $*"; }
skip() { echo -e "${YELLOW}[import]${NC} SKIP: $*"; }

# ── Helper: import only if not already in state ───────────────────────────────
tf_import() {
  local addr="$1"; local id="$2"
  if terraform state show "$addr" >/dev/null 2>&1; then
    skip "$addr already in state"
    return 0
  fi
  if [[ -z "$id" || "$id" == "None" || "$id" == "null" ]]; then
    skip "$addr — resource not found in AWS, will be created by apply"
    return 0
  fi
  info "Importing $addr → $id"
  terraform import "$addr" "$id" || skip "$addr import failed (may not exist yet)"
}

# ── Sanity checks ──────────────────────────────────────────────────────────────
command -v terraform >/dev/null 2>&1 || { echo "terraform not in PATH"; exit 1; }
command -v aws       >/dev/null 2>&1 || { echo "aws CLI not in PATH"; exit 1; }
ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
info "Account: $ACCOUNT_ID  Region: $REGION  Prefix: $NAME_PREFIX"

cd "$REGION_DIR"
terraform init -reconfigure -upgrade -input=false >/dev/null

# ══════════════════════════════════════════════════════════════════════════════
info "=== VPC ==="
VPC_ID=$(aws ec2 describe-vpcs \
  --filters "Name=tag:Name,Values=${NAME_PREFIX}-vpc" \
  --query "Vpcs[0].VpcId" --output text --region "$REGION" 2>/dev/null || echo "")
tf_import "module.vpc.aws_vpc.this" "$VPC_ID"

if [[ -n "$VPC_ID" && "$VPC_ID" != "None" ]]; then
  # Public subnets
  for i in 1 2; do
    SUBNET_ID=$(aws ec2 describe-subnets \
      --filters "Name=tag:Name,Values=${NAME_PREFIX}-public-${i}" \
      --query "Subnets[0].SubnetId" --output text --region "$REGION" 2>/dev/null || echo "")
    tf_import "module.vpc.aws_subnet.public[$((i-1))]" "$SUBNET_ID"
  done

  # Private subnets
  for i in 1 2; do
    SUBNET_ID=$(aws ec2 describe-subnets \
      --filters "Name=tag:Name,Values=${NAME_PREFIX}-private-${i}" \
      --query "Subnets[0].SubnetId" --output text --region "$REGION" 2>/dev/null || echo "")
    tf_import "module.vpc.aws_subnet.private[$((i-1))]" "$SUBNET_ID"
  done

  # Internet Gateway
  IGW_ID=$(aws ec2 describe-internet-gateways \
    --filters "Name=tag:Name,Values=${NAME_PREFIX}-igw" \
    --query "InternetGateways[0].InternetGatewayId" --output text --region "$REGION" 2>/dev/null || echo "")
  tf_import "module.vpc.aws_internet_gateway.this" "$IGW_ID"

  # EIP for NAT (only index 0 — single_nat_gateway = true)
  EIP_ALLOC=$(aws ec2 describe-addresses \
    --filters "Name=tag:Name,Values=${NAME_PREFIX}-nat-eip-1" \
    --query "Addresses[0].AllocationId" --output text --region "$REGION" 2>/dev/null || echo "")
  tf_import "module.vpc.aws_eip.nat[0]" "$EIP_ALLOC"

  # NAT Gateway (only index 0)
  NAT_ID=$(aws ec2 describe-nat-gateways \
    --filter "Name=tag:Name,Values=${NAME_PREFIX}-nat-1" "Name=state,Values=available,pending" \
    --query "NatGateways[0].NatGatewayId" --output text --region "$REGION" 2>/dev/null || echo "")
  tf_import "module.vpc.aws_nat_gateway.this[0]" "$NAT_ID"

  # Route tables
  PUBLIC_RT=$(aws ec2 describe-route-tables \
    --filters "Name=tag:Name,Values=${NAME_PREFIX}-public-rt" \
    --query "RouteTables[0].RouteTableId" --output text --region "$REGION" 2>/dev/null || echo "")
  tf_import "module.vpc.aws_route_table.public" "$PUBLIC_RT"

  for i in 1 2; do
    PRIVATE_RT=$(aws ec2 describe-route-tables \
      --filters "Name=tag:Name,Values=${NAME_PREFIX}-private-rt-${i}" \
      --query "RouteTables[0].RouteTableId" --output text --region "$REGION" 2>/dev/null || echo "")
    tf_import "module.vpc.aws_route_table.private[$((i-1))]" "$PRIVATE_RT"
  done

  # Route table associations (public)
  if [[ -n "$PUBLIC_RT" && "$PUBLIC_RT" != "None" ]]; then
    ASSOC_IDS=$(aws ec2 describe-route-tables \
      --route-table-ids "$PUBLIC_RT" \
      --query "RouteTables[0].Associations[].RouteTableAssociationId" \
      --output text --region "$REGION" 2>/dev/null || echo "")
    IDX=0
    for ASSOC_ID in $ASSOC_IDS; do
      tf_import "module.vpc.aws_route_table_association.public[$IDX]" "$ASSOC_ID"
      IDX=$((IDX + 1))
    done
  fi

  # Route table associations (private)
  for i in 1 2; do
    PRIVATE_RT=$(aws ec2 describe-route-tables \
      --filters "Name=tag:Name,Values=${NAME_PREFIX}-private-rt-${i}" \
      --query "RouteTables[0].RouteTableId" --output text --region "$REGION" 2>/dev/null || echo "")
    if [[ -n "$PRIVATE_RT" && "$PRIVATE_RT" != "None" ]]; then
      ASSOC_ID=$(aws ec2 describe-route-tables \
        --route-table-ids "$PRIVATE_RT" \
        --query "RouteTables[0].Associations[0].RouteTableAssociationId" \
        --output text --region "$REGION" 2>/dev/null || echo "")
      tf_import "module.vpc.aws_route_table_association.private[$((i-1))]" "$ASSOC_ID"
    fi
  done

  # VPC Flow Logs
  CW_FLOW_LOG=$(aws ec2 describe-flow-logs \
    --filter "Name=resource-id,Values=$VPC_ID" \
    --query "FlowLogs[0].FlowLogId" --output text --region "$REGION" 2>/dev/null || echo "")
  tf_import "module.vpc.aws_flow_log.this" "$CW_FLOW_LOG"
fi

# VPC Flow Logs IAM role + log group
tf_import "module.vpc.aws_iam_role.flow_logs"            "${NAME_PREFIX}-vpc-flow-logs-role"
tf_import "module.vpc.aws_iam_role_policy.flow_logs"     "${NAME_PREFIX}-vpc-flow-logs-role:${NAME_PREFIX}-flow-logs-policy"
tf_import "module.vpc.aws_cloudwatch_log_group.flow_logs" "/aws/vpc/${NAME_PREFIX}/flow-logs"

# ══════════════════════════════════════════════════════════════════════════════
info "=== IAM ==="
tf_import "module.iam.aws_iam_role.ec2"             "${NAME_PREFIX}-ec2-role"
tf_import "module.iam.aws_iam_instance_profile.ec2" "${NAME_PREFIX}-ec2-profile"
tf_import "module.iam.aws_iam_role_policy_attachment.ssm" \
  "${NAME_PREFIX}-ec2-role/arn:aws:iam::aws:policy/AmazonSSMManagedInstanceCore"
tf_import "module.iam.aws_iam_role_policy_attachment.ecr" \
  "${NAME_PREFIX}-ec2-role/arn:aws:iam::aws:policy/AmazonEC2ContainerRegistryReadOnly"
tf_import "module.iam.aws_iam_role_policy_attachment.cloudwatch" \
  "${NAME_PREFIX}-ec2-role/arn:aws:iam::aws:policy/CloudWatchAgentServerPolicy"
tf_import "module.iam.aws_iam_role_policy.secrets" \
  "${NAME_PREFIX}-ec2-role:${NAME_PREFIX}-secrets-read"

# ══════════════════════════════════════════════════════════════════════════════
info "=== EFS ==="
EFS_ID=$(aws efs describe-file-systems \
  --query "FileSystems[?CreationToken=='${NAME_PREFIX}-shared'].FileSystemId" \
  --output text --region "$REGION" 2>/dev/null || echo "")
tf_import "module.efs.aws_efs_file_system.this" "$EFS_ID"

EFS_SG=$(aws ec2 describe-security-groups \
  --filters "Name=tag:Name,Values=${NAME_PREFIX}-efs-sg" \
  --query "SecurityGroups[0].GroupId" --output text --region "$REGION" 2>/dev/null || echo "")
tf_import "module.efs.aws_security_group.efs" "$EFS_SG"

if [[ -n "$EFS_ID" && "$EFS_ID" != "None" ]]; then
  # Mount targets (one per private subnet)
  MT_IDS=$(aws efs describe-mount-targets \
    --file-system-id "$EFS_ID" \
    --query "MountTargets[].MountTargetId" \
    --output text --region "$REGION" 2>/dev/null || echo "")
  IDX=0
  for MT_ID in $MT_IDS; do
    tf_import "module.efs.aws_efs_mount_target.this[$IDX]" "$MT_ID"
    IDX=$((IDX + 1))
  done

  # Backup policy
  tf_import "module.efs.aws_efs_backup_policy.this" "$EFS_ID"

  # Access points
  AP_IDS=$(aws efs describe-access-points \
    --file-system-id "$EFS_ID" \
    --query "AccessPoints[].[AccessPointId,RootDirectory.Path]" \
    --output text --region "$REGION" 2>/dev/null || echo "")
  while IFS=$'\t' read -r AP_ID AP_PATH; do
    case "$AP_PATH" in
      /magellon) tf_import "module.efs.aws_efs_access_point.magellon" "$AP_ID" ;;
      /gpfs)     tf_import "module.efs.aws_efs_access_point.gpfs"     "$AP_ID" ;;
      /jobs)     tf_import "module.efs.aws_efs_access_point.jobs"     "$AP_ID" ;;
    esac
  done <<< "$AP_IDS"
fi

# ══════════════════════════════════════════════════════════════════════════════
info "=== Secrets Manager ==="
SECRET_ARN=$(aws secretsmanager describe-secret \
  --secret-id "/magellon/${NAME_PREFIX}/app-secrets" \
  --query "ARN" --output text --region "$REGION" 2>/dev/null || echo "")
tf_import "module.ec2_stack.aws_secretsmanager_secret.app" "$SECRET_ARN"
if [[ -n "$SECRET_ARN" && "$SECRET_ARN" != "None" ]]; then
  SECRET_VER=$(aws secretsmanager describe-secret \
    --secret-id "$SECRET_ARN" \
    --query "VersionIdsToStages | keys(@) | [0]" \
    --output text --region "$REGION" 2>/dev/null || echo "")
  tf_import "module.ec2_stack.aws_secretsmanager_secret_version.app" \
    "${SECRET_ARN}|${SECRET_VER}"
fi

# ══════════════════════════════════════════════════════════════════════════════
info "=== EC2 Security Groups ==="
MAIN_SG=$(aws ec2 describe-security-groups \
  --filters "Name=tag:Name,Values=${NAME_PREFIX}-main-sg" \
  --query "SecurityGroups[0].GroupId" --output text --region "$REGION" 2>/dev/null || echo "")
tf_import "module.ec2_stack.aws_security_group.main" "$MAIN_SG"

GPU_SG=$(aws ec2 describe-security-groups \
  --filters "Name=tag:Name,Values=${NAME_PREFIX}-gpu-sg" \
  --query "SecurityGroups[0].GroupId" --output text --region "$REGION" 2>/dev/null || echo "")
tf_import "module.ec2_stack.aws_security_group.gpu" "$GPU_SG"

# ══════════════════════════════════════════════════════════════════════════════
info "=== EC2 Instances ==="
MAIN_INSTANCE=$(aws ec2 describe-instances \
  --filters "Name=tag:Name,Values=${NAME_PREFIX}-main" "Name=instance-state-name,Values=running,stopped" \
  --query "Reservations[0].Instances[0].InstanceId" --output text --region "$REGION" 2>/dev/null || echo "")
tf_import "module.ec2_stack.aws_instance.main" "$MAIN_INSTANCE"

# Spot instance request
GPU_SPOT=$(aws ec2 describe-spot-instance-requests \
  --filters "Name=tag:Name,Values=${NAME_PREFIX}-gpu-spot-request" "Name=state,Values=active,open" \
  --query "SpotInstanceRequests[0].SpotInstanceRequestId" --output text --region "$REGION" 2>/dev/null || echo "")
tf_import "module.ec2_stack.aws_spot_instance_request.gpu" "$GPU_SPOT"

# ══════════════════════════════════════════════════════════════════════════════
info "=== ALB ==="
ALB_ARN=$(aws elbv2 describe-load-balancers \
  --query "LoadBalancers[?LoadBalancerName=='${NAME_PREFIX}-alb'].LoadBalancerArn" \
  --output text --region "$REGION" 2>/dev/null || echo "")
tf_import "module.alb.aws_lb.this" "$ALB_ARN"

ALB_SG=$(aws ec2 describe-security-groups \
  --filters "Name=tag:Name,Values=${NAME_PREFIX}-alb-sg" \
  --query "SecurityGroups[0].GroupId" --output text --region "$REGION" 2>/dev/null || echo "")
tf_import "module.alb.aws_security_group.alb" "$ALB_SG"

TG_ARN=$(aws elbv2 describe-target-groups \
  --names "${NAME_PREFIX}-frontend-tg" \
  --query "TargetGroups[0].TargetGroupArn" --output text --region "$REGION" 2>/dev/null || echo "")
tf_import "module.alb.aws_lb_target_group.frontend" "$TG_ARN"

# ALB listener (HTTP:80)
if [[ -n "$ALB_ARN" && "$ALB_ARN" != "None" ]]; then
  LISTENER_ARN=$(aws elbv2 describe-listeners \
    --load-balancer-arn "$ALB_ARN" \
    --query "Listeners[?Port==\`80\`].ListenerArn" \
    --output text --region "$REGION" 2>/dev/null || echo "")
  tf_import "module.alb.aws_lb_listener.http" "$LISTENER_ARN"

  TG_ATTACH=$(aws elbv2 describe-target-health \
    --target-group-arn "$TG_ARN" 2>/dev/null | \
    jq -r ".TargetHealthDescriptions[0].Target.Id" 2>/dev/null || echo "")
fi

# Target group attachment
if [[ -n "$TG_ARN" && "$TG_ARN" != "None" && -n "$MAIN_INSTANCE" && "$MAIN_INSTANCE" != "None" ]]; then
  tf_import "module.alb.aws_lb_target_group_attachment.main" \
    "${TG_ARN}/${MAIN_INSTANCE}/8080" 2>/dev/null || true
fi

# S3 bucket for ALB logs
S3_BUCKET="${NAME_PREFIX}-alb-logs-${ACCOUNT_ID}"
BUCKET_EXISTS=$(aws s3api head-bucket --bucket "$S3_BUCKET" 2>/dev/null && echo "yes" || echo "")
if [[ "$BUCKET_EXISTS" == "yes" ]]; then
  tf_import "module.alb.aws_s3_bucket.alb_logs" "$S3_BUCKET"
  tf_import "module.alb.aws_s3_bucket_lifecycle_configuration.alb_logs" "$S3_BUCKET"
  tf_import "module.alb.aws_s3_bucket_policy.alb_logs" "$S3_BUCKET"
fi

# WAF WebACL
WAF_INFO=$(aws wafv2 list-web-acls --scope REGIONAL --region "$REGION" \
  --query "WebACLs[?Name=='${NAME_PREFIX}-waf'].[Id,Name]" \
  --output text 2>/dev/null || echo "")
WAF_ID=$(echo "$WAF_INFO" | awk '{print $1}')
WAF_NAME=$(echo "$WAF_INFO" | awk '{print $2}')
if [[ -n "$WAF_ID" && "$WAF_ID" != "None" ]]; then
  tf_import "module.alb.aws_wafv2_web_acl.this" "${WAF_ID}/${WAF_NAME}/REGIONAL"
fi

# WAF CloudWatch log group + association
CW_WAF="aws-waf-logs-${NAME_PREFIX}"
tf_import "module.alb.aws_cloudwatch_log_group.waf" "$CW_WAF"

if [[ -n "$WAF_ID" && "$WAF_ID" != "None" ]]; then
  WAF_ARN=$(aws wafv2 get-web-acl --id "$WAF_ID" --name "$WAF_NAME" --scope REGIONAL \
    --region "$REGION" --query "WebACL.ARN" --output text 2>/dev/null || echo "")
  tf_import "module.alb.aws_wafv2_web_acl_logging_configuration.this" "$WAF_ARN"
  if [[ -n "$ALB_ARN" && "$ALB_ARN" != "None" ]]; then
    tf_import "module.alb.aws_wafv2_web_acl_association.alb" "$ALB_ARN"
  fi
fi

# ══════════════════════════════════════════════════════════════════════════════
info "=== Monitoring ==="
SNS_ARN=$(aws sns list-topics \
  --query "Topics[?ends_with(TopicArn,':${NAME_PREFIX}-alerts')].TopicArn" \
  --output text --region "$REGION" 2>/dev/null | head -1 || echo "")
tf_import "module.monitoring.aws_sns_topic.alerts" "$SNS_ARN"

for svc in backend web mysql rabbitmq dragonfly nats ctf-plugin; do
  tf_import "module.monitoring.aws_cloudwatch_log_group.main[\"$svc\"]" \
    "/magellon/${NAME_PREFIX}/${svc}"
done
tf_import "module.monitoring.aws_cloudwatch_log_group.gpu" \
  "/magellon/${NAME_PREFIX}/motioncor-plugin"

# CloudWatch Dashboard
DASH_NAME="${NAME_PREFIX}-overview"
DASH_EXISTS=$(aws cloudwatch get-dashboard --dashboard-name "$DASH_NAME" \
  --region "$REGION" 2>/dev/null && echo "yes" || echo "")
if [[ "$DASH_EXISTS" == "yes" ]]; then
  tf_import "module.monitoring.aws_cloudwatch_dashboard.overview" "$DASH_NAME"
fi

# ══════════════════════════════════════════════════════════════════════════════
info "=== Done importing existing resources ==="
info "Run './deploy.sh' to apply any pending changes."
