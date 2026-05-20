"""
Replay recorded MotionCor tasks on AWS using the full Magellon plugin stack.

Workflow:
  1. (optional) Build + push the motioncor plugin image to ECR
  2. Upload frame TIF/MRC files to S3
  3. Upload the recorded tasks JSON to S3
  4. Launch a g4dn.2xlarge with cloud-init that:
       - Installs Docker + NVIDIA Container Toolkit
       - Pulls the plugin image from ECR
       - Downloads frames from S3 to /gpfs/home/{session}/
       - Starts docker-compose (RabbitMQ + motioncor plugin)
       - Pushes recorded tasks to the local RabbitMQ
       - Waits for all N out-queue messages
       - Uploads /gpfs/jobs/ result dirs to S3
       - Writes PLUGIN_ALL_DONE marker
  5. Monitor S3 for PLUGIN_ALL_DONE
  6. Download results to local C:/magellon/gpfs/jobs/
  7. Collect out-queue result messages from S3
  8. Forward result messages to local motioncor_out_tasks_queue
  9. (optional) Mark DB tasks complete

Usage:
    # 1. Record tasks after import:
    python sandbox/aws/record_tasks.py --session 24dec03a

    # 2. Launch replay (builds + pushes image on first run):
    python sandbox/aws/replay_plugin_stack.py \\
        --session 24dec03a \\
        --tasks   sandbox/aws/motioncor_tasks_24dec03a.json

    # Skip ECR build (use existing image):
    python sandbox/aws/replay_plugin_stack.py \\
        --session 24dec03a \\
        --tasks   sandbox/aws/motioncor_tasks_24dec03a.json \\
        --ecr-image 789438509093.dkr.ecr.us-east-1.amazonaws.com/magellon-plugin-motioncor:latest

    # Collect-only (instance already ran):
    python sandbox/aws/replay_plugin_stack.py \\
        --session 24dec03a \\
        --tasks   sandbox/aws/motioncor_tasks_24dec03a.json \\
        --collect-only

Env: AWS_ACCESS_KEY_ID  AWS_SECRET_ACCESS_KEY  AWS_SESSION_TOKEN
     RMQ_HOST  RMQ_PORT  RMQ_USER  RMQ_PASS  (local broker for result forwarding)
     DB_HOST   DB_PORT   DB_NAME   DB_USER    DB_PASS
"""

import argparse
import base64
import datetime
import json
import os
import subprocess
import sys
import time

import boto3
import pika
import pymysql

# ---------------------------------------------------------------------------
# Defaults
# ---------------------------------------------------------------------------
AWS_REGION    = os.environ.get("AWS_DEFAULT_REGION", "us-east-1")
BUCKET        = "magellon-gpu-eval-work"
ACCOUNT_ID    = "789438509093"
ECR_REPO      = "magellon-plugin-motioncor"
ECR_TAG       = "latest"

INSTANCE_TYPE = "g4dn.2xlarge"
AMI_ID        = "ami-0c7217cdde317cfec"  # Ubuntu 22.04 LTS us-east-1 (hvm:ebs-ssd)
KEY_NAME      = "magellon-aws-key"
SECURITY_GROUP = "sg-0be12ee48e72a547b"
IAM_PROFILE    = "arn:aws:iam::789438509093:instance-profile/magellon-ec2-s3-role"
EBS_SIZE_GB    = 200

LOCAL_GPFS    = os.environ.get("MAGELLON_GPFS_PATH", r"C:\magellon\gpfs")

RMQ_HOST  = os.environ.get("RMQ_HOST", "127.0.0.1")
RMQ_PORT  = int(os.environ.get("RMQ_PORT", "5672"))
RMQ_USER  = os.environ.get("RMQ_USER", "rabbit")
RMQ_PASS  = os.environ.get("RMQ_PASS", "behd1d2")
RMQ_OUT_Q = "motioncor_out_tasks_queue"

DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_PORT = int(os.environ.get("DB_PORT", "3306"))
DB_NAME = os.environ.get("DB_NAME", "magellon01")
DB_USER = os.environ.get("DB_USER", "root")
DB_PASS = os.environ.get("DB_PASS", "behd1d2")

PLUGIN_DIR = os.path.normpath(
    os.path.join(os.path.dirname(__file__), "..", "..",
                 "plugins", "magellon_motioncor_plugin")
)

HERE = os.path.dirname(os.path.abspath(__file__))

# Gain reference relative path inside /gpfs/home/{session}/
GAIN_SUBDIR  = "gains"
FRAME_SUBDIR = "frames"

# ---------------------------------------------------------------------------
# AWS helpers
# ---------------------------------------------------------------------------

def s3():
    return boto3.client("s3", region_name=AWS_REGION)

def ec2():
    return boto3.client("ec2", region_name=AWS_REGION)

def ecr():
    return boto3.client("ecr", region_name=AWS_REGION)

def s3_objs(prefix):
    r = s3().list_objects_v2(Bucket=BUCKET, Prefix=prefix)
    return r.get("Contents", [])

def s3_key_exists(key):
    try:
        s3().head_object(Bucket=BUCKET, Key=key)
        return True
    except Exception:
        return False


# ---------------------------------------------------------------------------
# Phase 1 — Build + push plugin image to ECR
# ---------------------------------------------------------------------------

def ecr_image_uri(tag=ECR_TAG):
    return f"{ACCOUNT_ID}.dkr.ecr.{AWS_REGION}.amazonaws.com/{ECR_REPO}:{tag}"


def ensure_ecr_repo():
    client = ecr()
    try:
        client.describe_repositories(repositoryNames=[ECR_REPO])
        print(f"  ECR repo exists: {ECR_REPO}")
    except client.exceptions.RepositoryNotFoundException:
        client.create_repository(repositoryName=ECR_REPO)
        print(f"  Created ECR repo: {ECR_REPO}")


def build_and_push_image(dry_run=False):
    print(f"\n[Phase 1] Building plugin image from {PLUGIN_DIR}")
    uri = ecr_image_uri()
    if dry_run:
        print(f"  [dry run] would build {uri}")
        return uri

    ensure_ecr_repo()

    # ECR login
    token = ecr().get_authorization_token()
    token_data   = token["authorizationData"][0]
    ecr_endpoint = token_data["proxyEndpoint"]
    decoded      = base64.b64decode(token_data["authorizationToken"]).decode()
    ecr_password = decoded.split(":", 1)[1]

    login_cmd = [
        "docker", "login", "--username", "AWS",
        "--password-stdin", ecr_endpoint,
    ]
    proc = subprocess.run(login_cmd, input=ecr_password,
                          capture_output=True, text=True)
    if proc.returncode != 0:
        raise RuntimeError(f"ECR login failed: {proc.stderr}")
    print("  ECR login OK")

    # Build
    build_cmd = [
        "docker", "build",
        "--platform", "linux/amd64",
        "-t", uri,
        PLUGIN_DIR,
    ]
    print(f"  Building: {' '.join(build_cmd)}")
    subprocess.run(build_cmd, check=True)

    # Push
    print(f"  Pushing: {uri}")
    subprocess.run(["docker", "push", uri], check=True)
    print(f"  Pushed: {uri}")
    return uri


# ---------------------------------------------------------------------------
# Phase 2 — Upload frames + gain to S3
# ---------------------------------------------------------------------------

def collect_frame_paths(tasks):
    """Return list of (canonical_path, local_path) for all unique input frames."""
    seen = set()
    result = []
    for task in tasks:
        data = task.get("data", {})
        canonical = data.get("inputFile") or data.get("image_path") or ""
        if not canonical or canonical in seen:
            continue
        seen.add(canonical)
        local = canonical.replace("/gpfs", LOCAL_GPFS.rstrip("/\\")).replace("/", os.sep)
        result.append((canonical, local))
    return result


def collect_gain_paths(tasks):
    """Return list of (canonical_path, local_path) for all unique gain files."""
    seen = set()
    result = []
    for task in tasks:
        data = task.get("data", {})
        canonical = data.get("Gain") or data.get("gain_file") or ""
        if not canonical or canonical in seen:
            continue
        seen.add(canonical)
        local = canonical.replace("/gpfs", LOCAL_GPFS.rstrip("/\\")).replace("/", os.sep)
        result.append((canonical, local))
    return result


def upload_files_to_s3(session, file_pairs, label, dry_run):
    print(f"\n[Phase 2] Uploading {label} to S3...")
    client = s3()
    uploaded = skipped = 0
    for canonical, local_path in file_pairs:
        fname = os.path.basename(local_path)
        # Map /gpfs/home/{session}/frames/... to S3 key
        # Preserve the sub-path under /gpfs/home/{session}/
        rel = canonical.replace(f"/gpfs/home/{session}/", "")
        s3_key = f"{session}/{rel}"

        if not os.path.exists(local_path):
            print(f"  WARNING: missing local file: {local_path}")
            continue

        if s3_key_exists(s3_key):
            skipped += 1
            continue

        size_mb = os.path.getsize(local_path) // 1024 // 1024
        if dry_run:
            print(f"  [dry run] would upload {fname} ({size_mb} MB) -> s3://{BUCKET}/{s3_key}")
        else:
            print(f"  uploading {fname} ({size_mb} MB)...", end=" ", flush=True)
            client.upload_file(local_path, BUCKET, s3_key)
            print("done")
            uploaded += 1

    print(f"  {label}: {uploaded} uploaded, {skipped} already present")


# ---------------------------------------------------------------------------
# Phase 3 — Upload tasks JSON + helper scripts to S3
# ---------------------------------------------------------------------------

def upload_tasks(session, tasks, dry_run):
    print("\n[Phase 3] Uploading tasks JSON to S3...")
    key = f"{session}/tasks.json"
    body = json.dumps(tasks, indent=2, default=str).encode()
    if dry_run:
        print(f"  [dry run] would upload {len(tasks)} tasks to s3://{BUCKET}/{key}")
    else:
        s3().put_object(Bucket=BUCKET, Key=key, Body=body)
        print(f"  uploaded {len(tasks)} tasks to s3://{BUCKET}/{key}")


# ---------------------------------------------------------------------------
# Cloud-init generation
# ---------------------------------------------------------------------------

PUSH_TASKS_PY = '''\
import pika, json, sys, time

tasks = json.load(open("/opt/tasks.json"))
total = len(tasks)
print(f"Pushing {total} tasks to motioncor_tasks_queue...", flush=True)

for attempt in range(20):
    try:
        conn = pika.BlockingConnection(pika.ConnectionParameters(
            "localhost", 5672, "/",
            pika.PlainCredentials("rabbit", "rabbit123"),
            connection_attempts=3, retry_delay=5))
        break
    except Exception as exc:
        print(f"  RMQ not ready ({exc}), retry {attempt+1}/20...", flush=True)
        time.sleep(15)
else:
    print("ERROR: RabbitMQ never became available", file=sys.stderr)
    sys.exit(1)

ch = conn.channel()
ch.queue_declare(queue="motioncor_tasks_queue", durable=True)
for i, task in enumerate(tasks, 1):
    ch.basic_publish(
        exchange="", routing_key="motioncor_tasks_queue",
        body=json.dumps(task),
        properties=pika.BasicProperties(delivery_mode=2))
    if i % 10 == 0:
        print(f"  pushed {i}/{total}", flush=True)
conn.close()
print(f"Done. Pushed {total} tasks.", flush=True)
'''

COLLECT_RESULTS_PY = '''\
import pika, json, sys, time

total = int(sys.argv[1])
print(f"Waiting for {total} results in motioncor_out_tasks_queue...", flush=True)

conn = pika.BlockingConnection(pika.ConnectionParameters(
    "localhost", 5672, "/",
    pika.PlainCredentials("rabbit", "rabbit123"),
    heartbeat=600))
ch = conn.channel()
ch.queue_declare(queue="motioncor_out_tasks_queue", durable=True)

results = []
deadline = time.time() + 14400  # 4 hours max

while len(results) < total and time.time() < deadline:
    method, _, body = ch.basic_get("motioncor_out_tasks_queue", auto_ack=False)
    if method is None:
        print(f"  progress: {len(results)}/{total}", flush=True)
        time.sleep(30)
        continue
    results.append(json.loads(body))
    ch.basic_ack(method.delivery_tag)
    print(f"  result {len(results)}/{total}", flush=True)

conn.close()
with open("/opt/result_messages.json", "w") as f:
    json.dump(results, f)
print(f"Collected {len(results)} result messages.", flush=True)
if len(results) < total:
    print(f"WARNING: only {len(results)} of {total} tasks completed", flush=True)
'''


def _docker_compose_yaml(ecr_image):
    return f"""\
version: '3.8'
services:
  rabbitmq:
    image: rabbitmq:3.12-management-alpine
    container_name: rabbitmq-aws
    environment:
      RABBITMQ_DEFAULT_USER: rabbit
      RABBITMQ_DEFAULT_PASS: rabbit123
    ports:
      - "5672:5672"
      - "15672:15672"
    healthcheck:
      test: ["CMD", "rabbitmq-diagnostics", "-q", "ping"]
      interval: 15s
      timeout: 10s
      retries: 20
      start_period: 30s

  motioncor:
    image: {ecr_image}
    container_name: motioncor-plugin
    environment:
      APP_ENV: production
      NVIDIA_VISIBLE_DEVICES: all
    volumes:
      - /gpfs:/gpfs
      - /opt/plugin_settings.yml:/app/configs/settings_prod.yml:ro
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              count: all
              capabilities: [gpu]
    depends_on:
      rabbitmq:
        condition: service_healthy
    restart: unless-stopped
    logging:
      driver: "json-file"
      options:
        max-size: "100m"
        max-file: "3"
"""


def _plugin_settings_yaml():
    # No DB needed — plugin publishes to out queue; DB updates done locally
    return """\
ENV_TYPE: production
MAGELLON_GPFS_PATH: /gpfs
JOBS_DIR: /gpfs/jobs
HOST_JOBS_DIR: /gpfs/jobs

rabbitmq_settings:
  HOST_NAME: rabbitmq
  PORT: 5672
  USER_NAME: rabbit
  PASSWORD: rabbit123
  VIRTUAL_HOST: /
  QUEUE_NAME: motioncor_tasks_queue
  OUT_QUEUE_NAME: motioncor_out_tasks_queue
  PREFETCH_COUNT: 2
  CONNECTION_TIMEOUT: 60

database_settings:
  DB_Driver: mysql+pymysql
  DB_HOST: localhost
  DB_NAME: magellon01
  DB_USER: root
  DB_PASSWORD: not_used_on_aws
  DB_Port: 3306
"""


def build_cloud_init(session, ecr_image, total_tasks, aws_creds):
    compose_b64  = base64.b64encode(_docker_compose_yaml(ecr_image).encode()).decode()
    settings_b64 = base64.b64encode(_plugin_settings_yaml().encode()).decode()
    push_b64     = base64.b64encode(PUSH_TASKS_PY.encode()).decode()
    collect_b64  = base64.b64encode(COLLECT_RESULTS_PY.encode()).decode()

    ak  = aws_creds.get("AccessKeyId", "")
    sk  = aws_creds.get("SecretAccessKey", "")
    st  = aws_creds.get("SessionToken", "")

    script = f"""\
#!/bin/bash
set -euo pipefail
LOG=/var/log/magellon-pipeline.log
exec > >(tee -a $LOG) 2>&1

export AWS_DEFAULT_REGION={AWS_REGION}
export AWS_ACCESS_KEY_ID="{ak}"
export AWS_SECRET_ACCESS_KEY="{sk}"
export AWS_SESSION_TOKEN="{st}"

BUCKET={BUCKET}
SESSION={session}
ECR_IMAGE="{ecr_image}"
TOTAL_TASKS={total_tasks}
ACCOUNT={ACCOUNT_ID}
REGION={AWS_REGION}

echo "=== Magellon Plugin Replay Pipeline ==="
echo "Session: $SESSION  Tasks: $TOTAL_TASKS"
echo "Started at $(date -u)"

# --- Decode helper files ---
echo "{compose_b64}" | base64 -d > /opt/docker-compose.yml
echo "{settings_b64}" | base64 -d > /opt/plugin_settings.yml
echo "{push_b64}"     | base64 -d > /opt/push_tasks.py
echo "{collect_b64}"  | base64 -d > /opt/collect_results.py

# --- Install Docker ---
echo "[Setup] Installing Docker..."
apt-get update -qq
apt-get install -y -q ca-certificates curl gnupg lsb-release awscli python3-pip
install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | gpg --dearmor -o /etc/apt/keyrings/docker.gpg
chmod a+r /etc/apt/keyrings/docker.gpg
echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu $(lsb_release -cs) stable" > /etc/apt/sources.list.d/docker.list
apt-get update -qq
apt-get install -y -q docker-ce docker-ce-cli containerd.io docker-compose-plugin
pip3 install -q pika awscli

# --- Install NVIDIA Container Toolkit ---
echo "[Setup] Installing NVIDIA Container Toolkit..."
curl -fsSL https://nvidia.github.io/libnvidia-container/gpgkey | gpg --dearmor -o /usr/share/keyrings/nvidia-container-toolkit-keyring.gpg
curl -s -L https://nvidia.github.io/libnvidia-container/stable/deb/nvidia-container-toolkit.list | \\
  sed 's#deb https://#deb [signed-by=/usr/share/keyrings/nvidia-container-toolkit-keyring.gpg] https://#g' | \\
  tee /etc/apt/sources.list.d/nvidia-container-toolkit.list
apt-get update -qq
apt-get install -y -q nvidia-container-toolkit
nvidia-ctk runtime configure --runtime=docker
systemctl restart docker
echo "[Setup] nvidia-smi check:"
nvidia-smi || echo "WARNING: nvidia-smi failed — GPU may not be ready yet"

# --- Create directory structure ---
mkdir -p /gpfs/home/$SESSION/{FRAME_SUBDIR}
mkdir -p /gpfs/home/$SESSION/{GAIN_SUBDIR}
mkdir -p /gpfs/jobs

# --- Download frames from S3 ---
echo "[Phase 3] Downloading frames from S3..."
aws s3 sync s3://$BUCKET/$SESSION/{FRAME_SUBDIR}/ /gpfs/home/$SESSION/{FRAME_SUBDIR}/
aws s3 sync s3://$BUCKET/$SESSION/{GAIN_SUBDIR}/  /gpfs/home/$SESSION/{GAIN_SUBDIR}/
echo "[Phase 3] Frames downloaded."

# --- Download tasks JSON ---
echo "[Phase 4] Downloading tasks JSON..."
aws s3 cp s3://$BUCKET/$SESSION/tasks.json /opt/tasks.json

# --- ECR login and pull image ---
echo "[Phase 5] Pulling plugin image from ECR..."
aws ecr get-login-password --region $REGION | \\
  docker login --username AWS --password-stdin $(echo $ECR_IMAGE | cut -d/ -f1)
docker pull $ECR_IMAGE

# --- Start services ---
echo "[Phase 6] Starting RabbitMQ + plugin..."
cd /opt
docker compose -f /opt/docker-compose.yml up -d

echo "[Phase 6] Waiting for RabbitMQ to be healthy..."
for i in $(seq 1 40); do
  if docker exec rabbitmq-aws rabbitmq-diagnostics -q ping 2>/dev/null; then
    echo "  RabbitMQ ready (attempt $i)"
    break
  fi
  echo "  Waiting... ($i/40)"
  sleep 15
done

# --- Push tasks to local RMQ ---
echo "[Phase 7] Pushing $TOTAL_TASKS tasks..."
python3 /opt/push_tasks.py

# --- Wait for completion ---
echo "[Phase 8] Monitoring $TOTAL_TASKS tasks..."
python3 /opt/collect_results.py $TOTAL_TASKS

# --- Upload results to S3 ---
echo "[Phase 9] Uploading results..."
aws s3 cp /opt/result_messages.json s3://$BUCKET/$SESSION/result_messages.json

echo "[Phase 9] Uploading job output dirs..."
cd /gpfs/jobs
UPLOADED=0
for dir in */; do
  name="${{dir%/}}"
  tar -czf /tmp/${{name}}.tar.gz -C /gpfs/jobs "${{name}}"
  aws s3 cp /tmp/${{name}}.tar.gz s3://$BUCKET/$SESSION/plugin_results/${{name}}.tar.gz
  rm /tmp/${{name}}.tar.gz
  UPLOADED=$((UPLOADED+1))
  echo "  uploaded $UPLOADED: ${{name}}"
done
echo "[Phase 9] Done. $UPLOADED job dirs uploaded."

# --- Done ---
echo "=== Pipeline complete at $(date -u) ==="
aws s3 cp /dev/null s3://$BUCKET/$SESSION/status/PLUGIN_ALL_DONE
echo "PLUGIN_ALL_DONE marker written."
"""

    cloud_config = {
        "write_files": [
            {
                "path": "/opt/run_pipeline.sh",
                "content": script,
                "permissions": "0755",
            }
        ],
        "runcmd": [
            "bash /opt/run_pipeline.sh"
        ],
    }

    import yaml as _yaml
    return "#cloud-config\n" + _yaml.dump(cloud_config, default_flow_style=False)


# ---------------------------------------------------------------------------
# Phase 4 — Launch EC2
# ---------------------------------------------------------------------------

def launch_instance(user_data, dry_run=False):
    if dry_run:
        print("  [dry run] would launch g4dn.2xlarge")
        return "i-dryrun"

    resp = ec2().run_instances(
        ImageId=AMI_ID,
        InstanceType=INSTANCE_TYPE,
        MinCount=1, MaxCount=1,
        KeyName=KEY_NAME,
        SecurityGroupIds=[SECURITY_GROUP],
        IamInstanceProfile={"Arn": IAM_PROFILE},
        BlockDeviceMappings=[{
            "DeviceName": "/dev/sda1",
            "Ebs": {"VolumeSize": EBS_SIZE_GB, "VolumeType": "gp3", "DeleteOnTermination": True},
        }],
        UserData=user_data,
        TagSpecifications=[{
            "ResourceType": "instance",
            "Tags": [{"Key": "Name", "Value": "magellon-plugin-replay"}],
        }],
    )
    iid = resp["Instances"][0]["InstanceId"]
    print(f"  Launched: {iid}  (type: {INSTANCE_TYPE})")
    return iid


# ---------------------------------------------------------------------------
# Phase 5 — Monitor
# ---------------------------------------------------------------------------

def monitor(session, launch_utc, total_tasks):
    print(f"\n[Phase 5] Monitoring — waiting for PLUGIN_ALL_DONE ({total_tasks} tasks)...")
    done_key = f"{session}/status/PLUGIN_ALL_DONE"
    while True:
        objs = s3_objs(f"{session}/plugin_results/")
        done = [o for o in s3_objs(f"{session}/status/")
                if "PLUGIN_ALL_DONE" in o["Key"] and o["LastModified"] > launch_utc]
        print(f"  {datetime.datetime.utcnow().strftime('%H:%M:%S')} UTC  "
              f"results={len(objs)}/{total_tasks}  done={bool(done)}")
        if done:
            break
        time.sleep(60)
    print("  PLUGIN_ALL_DONE detected.")


# ---------------------------------------------------------------------------
# Phase 6 — Collect results
# ---------------------------------------------------------------------------

def collect_results(session, tasks, local_jobs_dir, dry_run=False):
    print(f"\n[Phase 6] Downloading {len(tasks)} result tarballs...")
    client = s3()
    objs   = s3_objs(f"{session}/plugin_results/")
    print(f"  Found {len(objs)} result dirs in S3")

    import io, tarfile
    ok = 0
    for obj in sorted(objs, key=lambda o: o["Key"]):
        key   = obj["Key"]
        stem  = key.split("/")[-1].replace(".tar.gz", "")
        outdir = os.path.join(local_jobs_dir, stem)

        if dry_run:
            print(f"  [dry run] would extract {stem}")
            continue

        os.makedirs(outdir, exist_ok=True)
        body = client.get_object(Bucket=BUCKET, Key=key)["Body"].read()
        with tarfile.open(fileobj=io.BytesIO(body), mode="r:gz") as tf:
            tf.extractall(path=local_jobs_dir)
        ok += 1
        print(f"  [{ok}/{len(objs)}] {stem}")

    print(f"  Extracted {ok} result dirs to {local_jobs_dir}")


# ---------------------------------------------------------------------------
# Phase 7 — Forward result messages + DB update
# ---------------------------------------------------------------------------

def download_result_messages(session):
    key = f"{session}/result_messages.json"
    try:
        body = s3().get_object(Bucket=BUCKET, Key=key)["Body"].read()
        msgs = json.loads(body)
        print(f"  Downloaded {len(msgs)} result messages from S3")
        return msgs
    except Exception as exc:
        print(f"  WARNING: could not download result_messages.json: {exc}")
        return []


def forward_to_local_rmq(messages, dry_run=False):
    if not messages:
        return
    print(f"\n[Phase 7] Forwarding {len(messages)} result messages to local RMQ...")
    if dry_run:
        print(f"  [dry run] would publish {len(messages)} messages to {RMQ_OUT_Q}")
        return

    conn = pika.BlockingConnection(pika.ConnectionParameters(
        host=RMQ_HOST, port=RMQ_PORT,
        credentials=pika.PlainCredentials(RMQ_USER, RMQ_PASS),
        connection_attempts=3, retry_delay=2,
    ))
    ch = conn.channel()
    ch.queue_declare(queue=RMQ_OUT_Q, durable=True)
    for msg in messages:
        ch.basic_publish(
            exchange="", routing_key=RMQ_OUT_Q,
            body=json.dumps(msg, default=str),
            properties=pika.BasicProperties(delivery_mode=2),
        )
    conn.close()
    print(f"  Published {len(messages)} messages to {RMQ_OUT_Q}")


def mark_db_tasks_complete(tasks, dry_run=False):
    print(f"\n[Phase 7] Marking {len(tasks)} DB tasks complete...")
    if dry_run:
        print(f"  [dry run] would update {len(tasks)} image_job_task rows to status_id=2")
        return

    task_ids = [t.get("id") for t in tasks if t.get("id")]
    if not task_ids:
        print("  No task IDs found in recorded tasks")
        return

    conn = pymysql.connect(host=DB_HOST, port=DB_PORT, database=DB_NAME,
                           user=DB_USER, password=DB_PASS, connect_timeout=10)
    cursor = conn.cursor()
    try:
        placeholders = ", ".join(["%s"] * len(task_ids))
        cursor.execute(
            f"UPDATE image_job_task SET status_id = 2 WHERE oid IN ({placeholders})",
            task_ids,
        )
        conn.commit()
        print(f"  Updated {cursor.rowcount} rows to status_id=2")
    finally:
        cursor.close()
        conn.close()


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--session",   required=True,
                        help="Magellon session name (e.g. 24dec03a)")
    parser.add_argument("--tasks",     required=False,
                        help="Path to recorded tasks JSON (from record_tasks.py)")
    parser.add_argument("--ecr-image", default=None,
                        help="Skip ECR build; use this image URI instead")
    parser.add_argument("--dry-run",   action="store_true",
                        help="Print what would happen without doing it")
    parser.add_argument("--collect-only", action="store_true",
                        help="Skip launch; assume instance already ran and collect results")
    parser.add_argument("--no-publish",   action="store_true",
                        help="Skip forwarding results to local RMQ")
    parser.add_argument("--no-db-update", action="store_true",
                        help="Skip DB status update")
    parser.add_argument("--iid",       default=None,
                        help="Existing instance ID (with --collect-only)")
    args = parser.parse_args()

    # --- Load tasks ---
    tasks_path = args.tasks or os.path.join(HERE, f"motioncor_tasks_{args.session}.json")
    if not os.path.exists(tasks_path):
        print(f"ERROR: tasks file not found: {tasks_path}")
        print("Run record_tasks.py first.")
        sys.exit(1)

    with open(tasks_path) as fh:
        tasks = json.load(fh)
    print(f"Loaded {len(tasks)} tasks from {tasks_path}")

    if not tasks:
        print("ERROR: tasks file is empty")
        sys.exit(1)

    session = args.session
    dry_run = args.dry_run
    launch_utc = datetime.datetime.now(datetime.timezone.utc)

    local_jobs_dir = os.path.join(LOCAL_GPFS, "jobs")
    os.makedirs(local_jobs_dir, exist_ok=True)

    # --- AWS credentials check ---
    if not dry_run and not args.collect_only:
        try:
            boto3.client("sts").get_caller_identity()
        except Exception as exc:
            print(f"ERROR: AWS credentials not configured: {exc}")
            sys.exit(1)

    # === Phase 1: ECR image ===
    if args.ecr_image:
        ecr_image = args.ecr_image
        print(f"\n[Phase 1] Using provided ECR image: {ecr_image}")
    elif args.collect_only:
        ecr_image = ecr_image_uri()
        print(f"\n[Phase 1] collect-only; assuming image: {ecr_image}")
    else:
        ecr_image = build_and_push_image(dry_run=dry_run)

    if args.collect_only:
        # Jump to collection
        collect_results(session, tasks, local_jobs_dir, dry_run=dry_run)
        result_messages = download_result_messages(session)
        if not args.no_publish:
            forward_to_local_rmq(result_messages, dry_run=dry_run)
        if not args.no_db_update:
            mark_db_tasks_complete(tasks, dry_run=dry_run)
        print("\nDone.")
        return

    # === Phase 2: Upload frames ===
    frame_pairs = collect_frame_paths(tasks)
    gain_pairs  = collect_gain_paths(tasks)
    upload_files_to_s3(session, frame_pairs, "frames", dry_run)
    upload_files_to_s3(session, gain_pairs,  "gains",  dry_run)

    # === Phase 3: Upload tasks JSON ===
    upload_tasks(session, tasks, dry_run)

    # === Phase 4: Launch EC2 ===
    print(f"\n[Phase 4] Generating cloud-init for {len(tasks)} tasks...")
    aws_creds = {}
    if not dry_run:
        ident = boto3.client("sts").get_caller_identity()
        # Retrieve current session credentials
        sess   = boto3.session.Session()
        creds  = sess.get_credentials().get_frozen_credentials()
        aws_creds = {
            "AccessKeyId":     creds.access_key,
            "SecretAccessKey": creds.secret_key,
            "SessionToken":    creds.token or "",
        }

    user_data = build_cloud_init(session, ecr_image, len(tasks), aws_creds)
    print(f"  Cloud-init size: {len(user_data)} bytes")

    iid = launch_instance(user_data, dry_run=dry_run)

    # === Phase 5: Monitor ===
    if not dry_run:
        print(f"\n[Phase 5] Instance {iid} started. Waiting for pipeline to complete.")
        print(f"  SSH: ssh -i {KEY_NAME}.pem ubuntu@<public-ip>")
        print(f"  Logs: ssh ... 'tail -f /var/log/magellon-pipeline.log'")
        monitor(session, launch_utc, len(tasks))

    # === Phase 6: Collect ===
    collect_results(session, tasks, local_jobs_dir, dry_run=dry_run)

    # === Phase 7: Forward + DB ===
    result_messages = download_result_messages(session) if not dry_run else []
    if not args.no_publish:
        forward_to_local_rmq(result_messages, dry_run=dry_run)
    if not args.no_db_update:
        mark_db_tasks_complete(tasks, dry_run=dry_run)

    print("\nAll phases complete.")
    print(f"  Results in: {local_jobs_dir}")
    print(f"  Next: check CoreService result consumer for DB updates")


if __name__ == "__main__":
    main()
