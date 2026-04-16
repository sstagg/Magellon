#!/usr/bin/env bash
# Launch an EC2 spot g4dn.xlarge that runs MotionCor2 DIRECTLY (bypassing run_motioncor.py)
# and ships verbose logs + dmesg to CloudWatch. Goal: find what actually sends SIGKILL at ~10s
# inside Batch, which the Python subprocess has been hiding.
set -euo pipefail
SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" &>/dev/null && pwd)"
source "${SCRIPT_DIR}/../common/activate.sh"

SG_NAME="${PROJECT}-ec2-spot-sg"
LG_NAME="/aws/ec2/${PROJECT}-baseline"
TIMESTAMP=$(date +%Y%m%d-%H%M%S)
JOB_ID="ec2diag-${TIMESTAMP}"
INPUT_S3="s3://${S3_TEST_BUCKET}/${S3_DATA_PREFIX}/20241203_54530_integrated_movie.mrc.tif"

AMI_ID=$(aws ec2 describe-images --owners amazon \
    --filters "Name=name,Values=amzn2-ami-ecs-gpu-hvm-*" "Name=state,Values=available" \
    --query 'reverse(sort_by(Images,&CreationDate))[0].ImageId' --output text)
echo "AMI: $AMI_ID"

aws logs create-log-group --log-group-name "$LG_NAME" 2>/dev/null || true

SG_ID=$(aws ec2 describe-security-groups --filters "Name=group-name,Values=${SG_NAME}" "Name=vpc-id,Values=${VPC_ID}" \
  --query 'SecurityGroups[0].GroupId' --output text 2>/dev/null || echo "None")
if [ "$SG_ID" = "None" ] || [ -z "$SG_ID" ]; then
  SG_ID=$(aws ec2 create-security-group --group-name "$SG_NAME" --description "egress SG ${PROJECT}" \
    --vpc-id "$VPC_ID" --tag-specifications "ResourceType=security-group,Tags=${TAGS_SHORT}" \
    --query GroupId --output text)
fi
echo "SG: $SG_ID"

SUBNET_ID=$(echo "$SUBNETS" | tr ',' '\n' | head -1)

aws iam put-role-policy --role-name "$ROLE_BATCH_INSTANCE" --policy-name "ec2-baseline-s3-write" --policy-document '{
  "Version":"2012-10-17","Statement":[
    {"Effect":"Allow","Action":["s3:PutObject","s3:PutObjectAcl","s3:GetObject","s3:ListBucket"],
     "Resource":["arn:aws:s3:::'${S3_WORK_BUCKET}'","arn:aws:s3:::'${S3_WORK_BUCKET}'/*","arn:aws:s3:::'${S3_TEST_BUCKET}'","arn:aws:s3:::'${S3_TEST_BUCKET}'/*"]},
    {"Effect":"Allow","Action":["logs:CreateLogStream","logs:PutLogEvents","logs:DescribeLogStreams"],"Resource":"*"}
  ]}' >/dev/null

USER_DATA=$(cat <<EOF
#!/bin/bash
set -x
exec > >(tee /var/log/user-data.log | logger -t user-data -s) 2>&1
INSTANCE_ID=\$(curl -s http://169.254.169.254/latest/meta-data/instance-id)
REGION=${AWS_DEFAULT_REGION}

yum install -y unzip amazon-cloudwatch-agent || true

# AL2 ECS-GPU AMI doesn't ship aws CLI — install v2.
echo "=== installing aws cli v2 ==="
curl -fsSL "https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip" -o /tmp/awscliv2.zip
cd /tmp && unzip -q awscliv2.zip && ./aws/install --bin-dir /usr/local/bin --install-dir /usr/local/aws-cli
export PATH=/usr/local/bin:\$PATH
which aws && aws --version
cd /

cat > /opt/aws/amazon-cloudwatch-agent/etc/amazon-cloudwatch-agent.json <<CFG
{"logs":{"logs_collected":{"files":{"collect_list":[
  {"file_path":"/var/log/user-data.log","log_group_name":"${LG_NAME}","log_stream_name":"\${INSTANCE_ID}"}
]}}}}
CFG
/opt/aws/amazon-cloudwatch-agent/bin/amazon-cloudwatch-agent-ctl -a fetch-config -m ec2 -c file:/opt/aws/amazon-cloudwatch-agent/etc/amazon-cloudwatch-agent.json -s || true

echo "=== host nvidia-smi ==="
nvidia-smi || true

echo "=== ECR login + pull ==="
aws ecr get-login-password --region \${REGION} | docker login --username AWS --password-stdin ${AWS_ACCOUNT_ID}.dkr.ecr.\${REGION}.amazonaws.com
docker pull ${ECR_URI}:latest

echo "=== Download movie from S3 on HOST ==="
mkdir -p /opt/mc2-in /opt/mc2-out
aws s3 cp ${INPUT_S3} /opt/mc2-in/movie.tif

echo "=== Start background memory monitor ==="
(while true; do
  date -u +%H:%M:%S.%3N
  free -m | head -2
  nvidia-smi --query-gpu=memory.used,memory.free,utilization.gpu --format=csv,noheader 2>/dev/null || true
  echo "---"
  sleep 1
done) > /var/log/mc2-monitor.log &
MON_PID=\$!

echo "=== Run MC2 in container, direct invocation, output to host-mounted file ==="
# Bind-mount input/output, override entrypoint to bash so we control invocation.
# No --memory limit so cgroup can use all host memory.
set +e
docker run --rm --gpus all \\
  --entrypoint /bin/bash \\
  -v /opt/mc2-in:/in:ro \\
  -v /opt/mc2-out:/out \\
  ${ECR_URI}:latest \\
  -c '
    echo "--- inside container ---"
    nvidia-smi
    echo
    ls -la /app/MotionCor2
    echo
    echo "--- run MC2 unbuffered via stdbuf ---"
    stdbuf -oL -eL /app/MotionCor2 \\
        -InTiff /in/movie.tif \\
        -OutMrc /out/corrected.mrc \\
        -Patch 5 5 -Iter 10 -Tol 0.5 -Gpu 0 -FtBin 1 -kV 300 \\
        > /out/mc2.stdout.log 2> /out/mc2.stderr.log
    echo "MC2 exit=\$?"
    echo "--- stdout (head+tail) ---"
    head -40 /out/mc2.stdout.log
    echo "..."
    tail -40 /out/mc2.stdout.log
    echo "--- stderr ---"
    cat /out/mc2.stderr.log
  '
DOCKER_RC=\$?
set -e
echo "docker run returned: \$DOCKER_RC"
kill \$MON_PID 2>/dev/null || true

echo "=== dmesg tail (look for OOM killer or GPU errors) ==="
dmesg -T | tail -120 || true

echo "=== monitor log tail ==="
tail -60 /var/log/mc2-monitor.log || true

echo "=== output listing ==="
ls -la /opt/mc2-out/ || true

echo "=== upload outputs to S3 ==="
aws s3 cp /opt/mc2-out/ s3://${S3_WORK_BUCKET}/test-1-ec2diag/${JOB_ID}/ --recursive || true
aws s3 cp /var/log/mc2-monitor.log s3://${S3_WORK_BUCKET}/test-1-ec2diag/${JOB_ID}/mc2-monitor.log || true

echo "=== done; shutting down in 30s ==="
sleep 30
shutdown -h now
EOF
)

INSTANCE_ID=$(MSYS_NO_PATHCONV=1 aws ec2 run-instances \
  --image-id "$AMI_ID" --instance-type g4dn.xlarge --count 1 \
  --subnet-id "$SUBNET_ID" --security-group-ids "$SG_ID" \
  --iam-instance-profile "Name=${ROLE_BATCH_INSTANCE}" \
  --instance-initiated-shutdown-behavior terminate \
  --block-device-mappings 'DeviceName=/dev/xvda,Ebs={VolumeSize=40,VolumeType=gp3,DeleteOnTermination=true}' \
  --instance-market-options 'MarketType=spot,SpotOptions={SpotInstanceType=one-time,InstanceInterruptionBehavior=terminate}' \
  --user-data "$USER_DATA" \
  --tag-specifications \
      "ResourceType=instance,Tags=[{Key=Project,Value=${PROJECT}},{Key=Owner,Value=${OWNER}},{Key=CostCenter,Value=${COST_CENTER}},{Key=Name,Value=${JOB_ID}}]" \
      "ResourceType=volume,Tags=${TAGS_SHORT}" \
  --query 'Instances[0].InstanceId' --output text)
echo "Instance: $INSTANCE_ID"
echo "Log group: $LG_NAME, stream: $INSTANCE_ID"
echo "Job tag:   $JOB_ID"
echo "$INSTANCE_ID" > /tmp/current-ec2diag
