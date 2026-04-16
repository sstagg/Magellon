#!/usr/bin/env bash
# Request a spot g4dn.xlarge, run the container via user data, terminate on finish.
# Instance auto-registers logs to CloudWatch /aws/ec2/magellon-gpu-eval-baseline.

set -euo pipefail
SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" &>/dev/null && pwd)"
source "${SCRIPT_DIR}/../common/activate.sh"

SG_NAME="${PROJECT}-ec2-spot-sg"
LG_NAME="/aws/ec2/${PROJECT}-baseline"
TIMESTAMP=$(date +%Y%m%d-%H%M%S)
JOB_ID="ec2spot-${TIMESTAMP}"
INPUT_S3="s3://${S3_TEST_BUCKET}/${S3_DATA_PREFIX}/20241203_54530_integrated_movie.mrc.tif"
OUTPUT_S3="s3://${S3_WORK_BUCKET}/test-4-ec2-spot/"

# Find ECS-optimized GPU AMI (SSM public param not always reachable here; query AMIs directly).
AMI_ID=$(aws ec2 describe-images --owners amazon \
    --filters "Name=name,Values=amzn2-ami-ecs-gpu-hvm-*" "Name=state,Values=available" \
    --query 'reverse(sort_by(Images,&CreationDate))[0].ImageId' --output text)
echo "AMI: $AMI_ID"

# Log group
aws logs create-log-group --log-group-name "$LG_NAME" 2>/dev/null || true
aws logs tag-log-group --log-group-name "$LG_NAME" --tags "Project=${PROJECT},Owner=${OWNER},CostCenter=${COST_CENTER}" 2>/dev/null || true

# SG (egress only)
SG_ID=$(aws ec2 describe-security-groups --filters "Name=group-name,Values=${SG_NAME}" "Name=vpc-id,Values=${VPC_ID}" --query 'SecurityGroups[0].GroupId' --output text 2>/dev/null || echo "None")
if [ "$SG_ID" = "None" ] || [ -z "$SG_ID" ]; then
  SG_ID=$(aws ec2 create-security-group --group-name "$SG_NAME" --description "egress SG for ${PROJECT} EC2 baseline" --vpc-id "$VPC_ID" \
    --tag-specifications "ResourceType=security-group,Tags=${TAGS_SHORT}" --query GroupId --output text)
fi
echo "SG: $SG_ID"

# Use a public subnet
SUBNET_ID=$(echo "$SUBNETS" | tr ',' '\n' | head -1)
echo "Subnet: $SUBNET_ID"

IAM_PROFILE="${ROLE_BATCH_INSTANCE}"  # already has ECS + S3 read; we'll add S3 write below
# Add S3 write for this test (idempotent)
aws iam put-role-policy --role-name "$ROLE_BATCH_INSTANCE" --policy-name "ec2-baseline-s3-write" --policy-document '{
  "Version":"2012-10-17","Statement":[
    {"Effect":"Allow","Action":["s3:PutObject","s3:PutObjectAcl","s3:GetObject","s3:ListBucket"],
     "Resource":["arn:aws:s3:::'${S3_WORK_BUCKET}'","arn:aws:s3:::'${S3_WORK_BUCKET}'/*","arn:aws:s3:::'${S3_TEST_BUCKET}'","arn:aws:s3:::'${S3_TEST_BUCKET}'/*"]},
    {"Effect":"Allow","Action":["logs:CreateLogStream","logs:PutLogEvents","logs:DescribeLogStreams"],"Resource":"*"}
  ]}' >/dev/null

# User data: install CloudWatch agent, pull+run container, terminate.
USER_DATA=$(cat <<EOF
#!/bin/bash
set -uxo pipefail
exec > >(tee /var/log/user-data.log | logger -t user-data -s) 2>&1
trap 'echo "user-data exiting; shutting down in 30s"; sleep 30; shutdown -h now' EXIT

INSTANCE_ID=\$(curl -s http://169.254.169.254/latest/meta-data/instance-id)
REGION=${AWS_DEFAULT_REGION}

# Simple log forwarder: tail /var/log/user-data.log to CloudWatch
dnf install -y amazon-cloudwatch-agent unzip || yum install -y amazon-cloudwatch-agent unzip || true

# AL2 ECS-GPU AMI doesn't ship AWS CLI — install v2
if ! command -v aws >/dev/null 2>&1; then
  curl -fsSL "https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip" -o /tmp/awscliv2.zip
  (cd /tmp && unzip -q awscliv2.zip && ./aws/install --bin-dir /usr/local/bin --install-dir /usr/local/aws-cli)
fi
export PATH=/usr/local/bin:\$PATH
cat > /opt/aws/amazon-cloudwatch-agent/etc/amazon-cloudwatch-agent.json <<CFG
{"logs":{"logs_collected":{"files":{"collect_list":[
  {"file_path":"/var/log/user-data.log","log_group_name":"${LG_NAME}","log_stream_name":"\${INSTANCE_ID}"}
]}}}}
CFG
/opt/aws/amazon-cloudwatch-agent/bin/amazon-cloudwatch-agent-ctl -a fetch-config -m ec2 -c file:/opt/aws/amazon-cloudwatch-agent/etc/amazon-cloudwatch-agent.json -s || true

# ECR login + pull + run
aws ecr get-login-password --region \${REGION} | docker login --username AWS --password-stdin ${AWS_ACCOUNT_ID}.dkr.ecr.\${REGION}.amazonaws.com

docker pull ${ECR_URI}:latest

docker run --rm --gpus all \
  -e MOTIONCOR_INPUT_S3=${INPUT_S3} \
  -e MOTIONCOR_OUTPUT_PREFIX=${OUTPUT_S3} \
  -e MOTIONCOR_JOB_ID=${JOB_ID} \
  ${ECR_URI}:latest || echo "container failed with \$?"

echo "done — shutting down"
sleep 5
shutdown -h now
EOF
)

# Launch spot instance (instance-initiated shutdown → terminate)
echo "Requesting spot instance..."
INSTANCE_ID=$(MSYS_NO_PATHCONV=1 aws ec2 run-instances \
  --image-id "$AMI_ID" \
  --instance-type g4dn.2xlarge \
  --count 1 \
  --subnet-id "$SUBNET_ID" \
  --security-group-ids "$SG_ID" \
  --iam-instance-profile "Name=${IAM_PROFILE}" \
  --instance-initiated-shutdown-behavior terminate \
  --block-device-mappings 'DeviceName=/dev/xvda,Ebs={VolumeSize=40,VolumeType=gp3,DeleteOnTermination=true}' \
  --instance-market-options 'MarketType=spot,SpotOptions={SpotInstanceType=one-time,InstanceInterruptionBehavior=terminate}' \
  --user-data "$USER_DATA" \
  --tag-specifications \
      "ResourceType=instance,Tags=[{Key=Project,Value=${PROJECT}},{Key=Owner,Value=${OWNER}},{Key=CostCenter,Value=${COST_CENTER}},{Key=Name,Value=${JOB_ID}}]" \
      "ResourceType=volume,Tags=${TAGS_SHORT}" \
  --query 'Instances[0].InstanceId' --output text)
echo "Instance: $INSTANCE_ID"

T0=$(date +%s)
PREV=""
while true; do
  S=$(aws ec2 describe-instances --instance-ids "$INSTANCE_ID" --query 'Reservations[0].Instances[0].State.Name' --output text 2>/dev/null || echo unknown)
  if [ "$S" != "$PREV" ]; then
    printf "%6ds  %s\n" "$(( $(date +%s) - T0 ))" "$S"
    PREV="$S"
  fi
  case "$S" in
    terminated|shutting-down) break ;;
  esac
  sleep 15
  # Guard: don't run forever
  [ $(( $(date +%s) - T0 )) -gt 1800 ] && { echo "TIMEOUT"; break; }
done

echo
echo "=== Recent spot prices (g4dn.xlarge $AWS_DEFAULT_REGION) ==="
aws ec2 describe-spot-price-history --instance-types g4dn.xlarge --product-descriptions "Linux/UNIX" \
  --max-items 5 --query 'SpotPriceHistory[].[AvailabilityZone,SpotPrice,Timestamp]' --output table

echo
echo "=== Output listing ==="
aws s3 ls "${OUTPUT_S3}${JOB_ID}/" --recursive --human-readable || echo "  (empty)"

echo
echo "=== Log tail ==="
STREAM="$INSTANCE_ID"
aws logs get-log-events --log-group-name "$LG_NAME" --log-stream-name "$STREAM" --limit 30 --start-from-head \
  --query 'events[].message' --output text 2>/dev/null | tail -30 || echo "  (no logs)"
