#!/usr/bin/env bash
# nuke.sh — HARD DELETE every Magellon resource in AWS and wipe Terraform state.
#
# Bypasses terraform destroy entirely (useful when state is partial/corrupt).
# Uses AWS CLI directly to delete in the correct dependency order.
# After this completes, run ./deploy.sh for a clean deployment.
#
# Usage:
#   cd infrastructure/terraform
#   ./nuke.sh
set -euo pipefail

REGION="us-east-1"
NAME_PREFIX="magellon-prod-use1"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
STATE_BUCKET="magellon-terraform-state"

RED='\033[0;31m'; YELLOW='\033[1;33m'; GREEN='\033[0;32m'; NC='\033[0m'
info()  { echo -e "${GREEN}[nuke]${NC} $*"; }
warn()  { echo -e "${YELLOW}[nuke]${NC} $*"; }
step()  { echo -e "${RED}[nuke]${NC} >>> $*"; }
ok()    { echo -e "${GREEN}[nuke]${NC}  ✓ $*"; }
skip()  { echo -e "${YELLOW}[nuke]${NC}  - SKIP: $*"; }

aws_() { aws "$@" --region "$REGION" 2>/dev/null || true; }

ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
echo ""
echo -e "${RED}╔══════════════════════════════════════════════════════════╗${NC}"
echo -e "${RED}║  MAGELLON AWS NUKE — deletes EVERYTHING, no undo         ║${NC}"
echo -e "${RED}╚══════════════════════════════════════════════════════════╝${NC}"
echo ""
echo "  Account : $ACCOUNT_ID"
echo "  Region  : $REGION"
echo "  Prefix  : $NAME_PREFIX"
echo ""
read -r -p "Type 'nuke' to confirm: " answer
[[ "$answer" == "nuke" ]] || { echo "Aborted."; exit 1; }
echo ""

# ── 1. ALB + listeners + WAF association ─────────────────────────────────────
step "1. Delete ALB"
ALB_ARN=$(aws_ elbv2 describe-load-balancers \
  --query "LoadBalancers[?LoadBalancerName=='${NAME_PREFIX}-alb'].LoadBalancerArn" \
  --output text)
if [[ -n "$ALB_ARN" && "$ALB_ARN" != "None" ]]; then
  # Delete WAF association first
  aws_ wafv2 disassociate-web-acl --resource-arn "$ALB_ARN" && ok "WAF disassociated" || true
  # Delete all listeners (this frees target groups)
  LISTENERS=$(aws_ elbv2 describe-listeners --load-balancer-arn "$ALB_ARN" \
    --query "Listeners[].ListenerArn" --output text)
  for L in $LISTENERS; do
    aws_ elbv2 delete-listener --listener-arn "$L" && ok "Deleted listener $L"
  done
  aws_ elbv2 delete-load-balancer --load-balancer-arn "$ALB_ARN" && ok "Deleted ALB"
  info "  Waiting for ALB to finish deleting..."
  aws_ elbv2 wait load-balancers-deleted --load-balancer-arns "$ALB_ARN" 2>/dev/null || sleep 20
else
  skip "ALB not found"
fi

# ── 2. Target Groups ──────────────────────────────────────────────────────────
step "2. Delete Target Groups"
TG_ARNS=$(aws_ elbv2 describe-target-groups \
  --query "TargetGroups[?starts_with(TargetGroupName,'${NAME_PREFIX}')].TargetGroupArn" \
  --output text)
for TG in $TG_ARNS; do
  aws_ elbv2 delete-target-group --target-group-arn "$TG" && ok "Deleted TG $TG"
done
[[ -z "$TG_ARNS" || "$TG_ARNS" == "None" ]] && skip "No target groups"

# ── 3. WAF WebACL ─────────────────────────────────────────────────────────────
step "3. Delete WAF WebACL"
WAF_ROW=$(aws_ wafv2 list-web-acls --scope REGIONAL \
  --query "WebACLs[?Name=='${NAME_PREFIX}-waf'].[Id,LockToken]" --output text)
WAF_ID=$(echo "$WAF_ROW" | awk '{print $1}')
WAF_TOKEN=$(echo "$WAF_ROW" | awk '{print $2}')
if [[ -n "$WAF_ID" && "$WAF_ID" != "None" ]]; then
  # Logging config must be deleted first
  WAF_ARN=$(aws_ wafv2 get-web-acl --id "$WAF_ID" --name "${NAME_PREFIX}-waf" \
    --scope REGIONAL --query "WebACL.ARN" --output text)
  aws_ wafv2 delete-logging-configuration --resource-arn "$WAF_ARN" 2>/dev/null || true
  aws_ wafv2 delete-web-acl --id "$WAF_ID" --name "${NAME_PREFIX}-waf" \
    --scope REGIONAL --lock-token "$WAF_TOKEN" && ok "Deleted WAF WebACL"
else
  skip "WAF WebACL not found"
fi

# ── 4. Terminate EC2 instances ───────────────────────────────────────────────
step "4. Terminate EC2 instances"
INSTANCE_IDS=$(aws_ ec2 describe-instances \
  --filters "Name=tag:Project,Values=magellon" \
            "Name=instance-state-name,Values=running,stopped,pending" \
  --query "Reservations[].Instances[].InstanceId" --output text)
if [[ -n "$INSTANCE_IDS" && "$INSTANCE_IDS" != "None" ]]; then
  aws_ ec2 terminate-instances --instance-ids $INSTANCE_IDS
  info "  Waiting for instances to terminate..."
  aws_ ec2 wait instance-terminated --instance-ids $INSTANCE_IDS 2>/dev/null || sleep 60
  ok "Instances terminated: $INSTANCE_IDS"
else
  skip "No running instances"
fi

# Cancel spot requests
SPOT_IDS=$(aws_ ec2 describe-spot-instance-requests \
  --filters "Name=tag:Project,Values=magellon" "Name=state,Values=open,active" \
  --query "SpotInstanceRequests[].SpotInstanceRequestId" --output text)
if [[ -n "$SPOT_IDS" && "$SPOT_IDS" != "None" ]]; then
  aws_ ec2 cancel-spot-instance-requests --spot-instance-request-ids $SPOT_IDS
  ok "Cancelled spot requests: $SPOT_IDS"
fi

# ── 5. EBS volumes ────────────────────────────────────────────────────────────
step "5. Delete EBS volumes (delete_on_termination=false orphans)"
sleep 10  # let terminate propagate
VOL_IDS=$(aws_ ec2 describe-volumes \
  --filters "Name=tag:Project,Values=magellon" "Name=status,Values=available" \
  --query "Volumes[].VolumeId" --output text)
for V in $VOL_IDS; do
  aws_ ec2 delete-volume --volume-id "$V" && ok "Deleted volume $V"
done
[[ -z "$VOL_IDS" || "$VOL_IDS" == "None" ]] && skip "No orphaned EBS volumes"

# ── 6. Secrets Manager ────────────────────────────────────────────────────────
step "6. Force-delete Secrets Manager secrets"
SECRET_ARNS=$(aws_ secretsmanager list-secrets \
  --filters Key=name,Values=/magellon/ \
  --query "SecretList[].ARN" --output text)
for S in $SECRET_ARNS; do
  aws_ secretsmanager delete-secret --secret-id "$S" \
    --force-delete-without-recovery && ok "Deleted secret $S"
done
[[ -z "$SECRET_ARNS" || "$SECRET_ARNS" == "None" ]] && skip "No secrets"

# ── 7. EFS ────────────────────────────────────────────────────────────────────
step "7. Delete EFS (access points → mount targets → file system)"
EFS_IDS=$(aws_ efs describe-file-systems \
  --query "FileSystems[?Tags[?Key=='Project'&&Value=='magellon']].FileSystemId" \
  --output text)
for FS in $EFS_IDS; do
  # Access points
  AP_IDS=$(aws_ efs describe-access-points --file-system-id "$FS" \
    --query "AccessPoints[].AccessPointId" --output text)
  for AP in $AP_IDS; do
    aws_ efs delete-access-point --access-point-id "$AP" && ok "  Deleted access point $AP"
  done
  # Mount targets
  MT_IDS=$(aws_ efs describe-mount-targets --file-system-id "$FS" \
    --query "MountTargets[].MountTargetId" --output text)
  for MT in $MT_IDS; do
    aws_ efs delete-mount-target --mount-target-id "$MT" && ok "  Deleted mount target $MT"
  done
  # Wait for mount targets to finish deleting
  info "  Waiting for mount targets to delete..."
  for i in {1..12}; do
    REMAINING=$(aws_ efs describe-mount-targets --file-system-id "$FS" \
      --query "length(MountTargets)" --output text)
    [[ "$REMAINING" == "0" ]] && break
    sleep 10
  done
  aws_ efs delete-file-system --file-system-id "$FS" && ok "Deleted EFS $FS"
done
[[ -z "$EFS_IDS" || "$EFS_IDS" == "None" ]] && skip "No EFS file systems"

# ── 8. Security Groups ────────────────────────────────────────────────────────
step "8. Delete Security Groups"
SG_IDS=$(aws_ ec2 describe-security-groups \
  --filters "Name=tag:Project,Values=magellon" \
  --query "SecurityGroups[?GroupName!='default'].GroupId" --output text)
for SG in $SG_IDS; do
  aws_ ec2 delete-security-group --group-id "$SG" && ok "Deleted SG $SG" || \
    warn "  Could not delete $SG (may still have dependencies — retrying after NAT cleanup)"
done

# ── 9. NAT Gateways ───────────────────────────────────────────────────────────
step "9. Delete NAT Gateways"
NAT_IDS=$(aws_ ec2 describe-nat-gateways \
  --filter "Name=tag:Project,Values=magellon" "Name=state,Values=available,pending" \
  --query "NatGateways[].NatGatewayId" --output text)
for NAT in $NAT_IDS; do
  aws_ ec2 delete-nat-gateway --nat-gateway-id "$NAT" && ok "Deleting NAT $NAT"
done
if [[ -n "$NAT_IDS" && "$NAT_IDS" != "None" ]]; then
  info "  Waiting for NAT gateways to delete (~60s)..."
  sleep 60
fi
[[ -z "$NAT_IDS" || "$NAT_IDS" == "None" ]] && skip "No NAT gateways"

# ── 10. Elastic IPs ───────────────────────────────────────────────────────────
step "10. Release Elastic IPs"
EIP_ALLOC_IDS=$(aws_ ec2 describe-addresses \
  --filters "Name=tag:Project,Values=magellon" \
  --query "Addresses[].AllocationId" --output text)
for EIP in $EIP_ALLOC_IDS; do
  aws_ ec2 release-address --allocation-id "$EIP" && ok "Released EIP $EIP"
done
[[ -z "$EIP_ALLOC_IDS" || "$EIP_ALLOC_IDS" == "None" ]] && skip "No tagged EIPs"

# ── 11. VPC resources ─────────────────────────────────────────────────────────
step "11. Delete VPC and all its resources"
VPC_ID=$(aws_ ec2 describe-vpcs \
  --filters "Name=tag:Name,Values=${NAME_PREFIX}-vpc" \
  --query "Vpcs[0].VpcId" --output text)

if [[ -n "$VPC_ID" && "$VPC_ID" != "None" ]]; then
  # Route tables (all non-main)
  RT_IDS=$(aws_ ec2 describe-route-tables \
    --filters "Name=vpc-id,Values=$VPC_ID" \
    --query "RouteTables[?Associations[0].Main!=\`true\`].RouteTableId" --output text)
  for RT in $RT_IDS; do
    # Disassociate first
    ASSOC_IDS=$(aws_ ec2 describe-route-tables --route-table-ids "$RT" \
      --query "RouteTables[0].Associations[?!Main].RouteTableAssociationId" --output text)
    for ASSOC in $ASSOC_IDS; do
      aws_ ec2 disassociate-route-table --association-id "$ASSOC" 2>/dev/null || true
    done
    aws_ ec2 delete-route-table --route-table-id "$RT" && ok "Deleted RT $RT" || true
  done

  # Internet Gateway
  IGW_IDS=$(aws_ ec2 describe-internet-gateways \
    --filters "Name=attachment.vpc-id,Values=$VPC_ID" \
    --query "InternetGateways[].InternetGatewayId" --output text)
  for IGW in $IGW_IDS; do
    aws_ ec2 detach-internet-gateway --internet-gateway-id "$IGW" --vpc-id "$VPC_ID"
    aws_ ec2 delete-internet-gateway --internet-gateway-id "$IGW" && ok "Deleted IGW $IGW"
  done

  # Subnets
  SUBNET_IDS=$(aws_ ec2 describe-subnets \
    --filters "Name=vpc-id,Values=$VPC_ID" \
    --query "Subnets[].SubnetId" --output text)
  for S in $SUBNET_IDS; do
    aws_ ec2 delete-subnet --subnet-id "$S" && ok "Deleted subnet $S"
  done

  # Security Groups (retry — now that NAT GWs are gone)
  SG_IDS2=$(aws_ ec2 describe-security-groups \
    --filters "Name=vpc-id,Values=$VPC_ID" \
    --query "SecurityGroups[?GroupName!='default'].GroupId" --output text)
  for SG in $SG_IDS2; do
    aws_ ec2 delete-security-group --group-id "$SG" && ok "Deleted SG $SG" || true
  done

  # VPC Flow Log
  FL_IDS=$(aws_ ec2 describe-flow-logs \
    --filter "Name=resource-id,Values=$VPC_ID" \
    --query "FlowLogs[].FlowLogId" --output text)
  for FL in $FL_IDS; do
    aws_ ec2 delete-flow-logs --flow-log-ids "$FL" && ok "Deleted flow log $FL"
  done

  # VPC itself
  aws_ ec2 delete-vpc --vpc-id "$VPC_ID" && ok "Deleted VPC $VPC_ID"
else
  skip "VPC ${NAME_PREFIX}-vpc not found"
fi

# ── 12. IAM ───────────────────────────────────────────────────────────────────
step "12. Delete IAM roles and instance profile"
delete_role() {
  local ROLE="$1"
  if aws_ iam get-role --role-name "$ROLE" | grep -q RoleId; then
    # Detach managed policies
    POLICIES=$(aws_ iam list-attached-role-policies --role-name "$ROLE" \
      --query "AttachedPolicies[].PolicyArn" --output text)
    for P in $POLICIES; do
      aws_ iam detach-role-policy --role-name "$ROLE" --policy-arn "$P"
    done
    # Delete inline policies
    INLINE=$(aws_ iam list-role-policies --role-name "$ROLE" \
      --query "PolicyNames[]" --output text)
    for P in $INLINE; do
      aws_ iam delete-role-policy --role-name "$ROLE" --policy-name "$P"
    done
    aws_ iam delete-role --role-name "$ROLE" && ok "Deleted role $ROLE"
  else
    skip "Role $ROLE not found"
  fi
}

# Remove from instance profile first
aws_ iam remove-role-from-instance-profile \
  --instance-profile-name "${NAME_PREFIX}-ec2-profile" \
  --role-name "${NAME_PREFIX}-ec2-role" 2>/dev/null || true
aws_ iam delete-instance-profile \
  --instance-profile-name "${NAME_PREFIX}-ec2-profile" && ok "Deleted instance profile"

delete_role "${NAME_PREFIX}-ec2-role"
delete_role "${NAME_PREFIX}-vpc-flow-logs-role"

# ── 13. CloudWatch Log Groups ─────────────────────────────────────────────────
step "13. Delete CloudWatch Log Groups"
LOG_GROUPS=$(aws_ logs describe-log-groups \
  --log-group-name-prefix "/magellon/${NAME_PREFIX}" \
  --query "logGroups[].logGroupName" --output text)
LOG_GROUPS+=" $(aws_ logs describe-log-groups \
  --log-group-name-prefix "/aws/vpc/${NAME_PREFIX}" \
  --query "logGroups[].logGroupName" --output text)"
LOG_GROUPS+=" $(aws_ logs describe-log-groups \
  --log-group-name-prefix "aws-waf-logs-${NAME_PREFIX}" \
  --query "logGroups[].logGroupName" --output text)"
for LG in $LOG_GROUPS; do
  [[ -z "$LG" || "$LG" == "None" ]] && continue
  aws_ logs delete-log-group --log-group-name "$LG" && ok "Deleted log group $LG"
done

# ── 14. CloudWatch Dashboard and Alarms ───────────────────────────────────────
step "14. Delete CloudWatch Dashboard and Alarms"
aws_ cloudwatch delete-dashboards \
  --dashboard-names "${NAME_PREFIX}-overview" && ok "Deleted dashboard" || skip "Dashboard not found"
ALARM_NAMES=$(aws_ cloudwatch describe-alarms \
  --alarm-name-prefix "${NAME_PREFIX}" \
  --query "MetricAlarms[].AlarmName" --output text)
for A in $ALARM_NAMES; do
  aws_ cloudwatch delete-alarms --alarm-names "$A" && ok "Deleted alarm $A"
done

# ── 15. SNS topics ────────────────────────────────────────────────────────────
step "15. Delete SNS Topics"
SNS_ARN=$(aws_ sns list-topics \
  --query "Topics[?ends_with(TopicArn,':${NAME_PREFIX}-alerts')].TopicArn" \
  --output text | head -1)
if [[ -n "$SNS_ARN" && "$SNS_ARN" != "None" ]]; then
  aws_ sns delete-topic --topic-arn "$SNS_ARN" && ok "Deleted SNS topic"
else
  skip "SNS topic not found"
fi

# ── 16. S3 Buckets ────────────────────────────────────────────────────────────
step "16. Delete S3 Buckets"
ALB_BUCKET="${NAME_PREFIX}-alb-logs-${ACCOUNT_ID}"
if aws s3api head-bucket --bucket "$ALB_BUCKET" 2>/dev/null; then
  aws s3 rm "s3://${ALB_BUCKET}" --recursive --quiet && ok "Emptied $ALB_BUCKET"
  aws s3api delete-bucket --bucket "$ALB_BUCKET" --region "$REGION" && ok "Deleted bucket $ALB_BUCKET"
else
  skip "Bucket $ALB_BUCKET not found"
fi

# State bucket — empty and delete
if aws s3api head-bucket --bucket "$STATE_BUCKET" 2>/dev/null; then
  warn "Emptying Terraform state bucket s3://$STATE_BUCKET ..."
  # Delete all versions (versioned bucket)
  aws s3api list-object-versions --bucket "$STATE_BUCKET" \
    --query '{Objects: Versions[].{Key:Key,VersionId:VersionId}}' \
    --output json 2>/dev/null | \
    python3 -c "
import json,sys,subprocess
data=json.load(sys.stdin)
objs=data.get('Objects',[]) or []
if objs:
    subprocess.run(['aws','s3api','delete-objects','--bucket','$STATE_BUCKET',
        '--delete',json.dumps({'Objects':objs,'Quiet':True})])
" 2>/dev/null || aws s3 rm "s3://$STATE_BUCKET" --recursive --quiet
  # Delete delete-markers
  aws s3api list-object-versions --bucket "$STATE_BUCKET" \
    --query '{Objects: DeleteMarkers[].{Key:Key,VersionId:VersionId}}' \
    --output json 2>/dev/null | \
    python3 -c "
import json,sys,subprocess
data=json.load(sys.stdin)
objs=data.get('Objects',[]) or []
if objs:
    subprocess.run(['aws','s3api','delete-objects','--bucket','$STATE_BUCKET',
        '--delete',json.dumps({'Objects':objs,'Quiet':True})])
" 2>/dev/null || true
  aws s3api delete-bucket --bucket "$STATE_BUCKET" --region us-east-1 && \
    ok "Deleted state bucket s3://$STATE_BUCKET"
else
  skip "State bucket $STATE_BUCKET not found"
fi

# ── 17. Wipe local Terraform state ────────────────────────────────────────────
step "17. Wipe local Terraform state files"
for DIR in \
  "$SCRIPT_DIR/global" \
  "$SCRIPT_DIR/regions/us-east-1" \
  "$SCRIPT_DIR/regions/us-west-2"; do
  rm -f "$DIR/terraform.tfstate" "$DIR/terraform.tfstate.backup" "$DIR/tfplan"
  rm -rf "$DIR/.terraform"
  ok "Cleared state in $DIR"
done

echo ""
echo -e "${GREEN}╔══════════════════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║  Nuke complete. AWS is clean. Ready for a fresh deploy.  ║${NC}"
echo -e "${GREEN}╚══════════════════════════════════════════════════════════╝${NC}"
echo ""
echo "  Next step: cd infrastructure/terraform && ./deploy.sh"
echo ""
