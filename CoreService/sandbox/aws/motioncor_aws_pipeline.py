"""
Full MotionCor AWS pipeline:

  1. Query DB for all stage=1 MotionCor tasks (after import)
  2. Save task list to JSON (the "record")
  3. Ensure each frame is in S3 (upload if missing)
  4. Generate pre-signed URLs + manifest, launch g4dn.2xlarge
  5. Monitor S3 for ALL_DONE
  6. Download result tarballs → extract _DW.mrc + log files to fao/
  7. Mark each DB task completed + publish result to out-queue

Usage:
    # Full pipeline for session 24dec03a
    python sandbox/aws/motioncor_aws_pipeline.py --session 24dec03a

    # Override acquisition params (kV, pixel size, dose/frame)
    python sandbox/aws/motioncor_aws_pipeline.py --session 24dec03a \\
        --kv 300 --pixsize 0.83 --fmdose 1.5

    # Re-collect results only (instance already done)
    python sandbox/aws/motioncor_aws_pipeline.py --session 24dec03a --collect-only

    # Dry-run: show discovered tasks, do not launch
    python sandbox/aws/motioncor_aws_pipeline.py --session 24dec03a --dry-run

Credentials: AWS_ACCESS_KEY_ID / SECRET / SESSION_TOKEN in environment.
DB / RMQ overrides: DB_HOST DB_PORT DB_NAME DB_USER DB_PASS RMQ_HOST RMQ_PASS
"""
import argparse
import datetime
import io
import json
import os
import sys
import tarfile
import time
import uuid

import boto3
import pika
import pymysql

# ---------------------------------------------------------------------------
# Defaults
# ---------------------------------------------------------------------------
BUCKET    = "magellon-gpu-eval-work"
REGION    = "us-east-1"
EXPIRE    = 43200          # 12 h presigned URL expiry
IMAGE     = "789438509093.dkr.ecr.us-east-1.amazonaws.com/magellon-gpu-eval/motioncor:latest"
ECR_HOST  = "789438509093.dkr.ecr.us-east-1.amazonaws.com"
BINARY    = "MotionCor2"
SUBNET    = "subnet-0ff0cbd8ad717c562"
AMI       = "ami-0b729f3f75a1074c4"
SG        = "sg-0fe348fc1a41d40da"
ROLE_NAME = "magellon-gpu-eval-batch-instance-role"
SSH_KEY   = "magellon_test"

GPFS_HOST_PATH = os.environ.get("MAGELLON_GPFS_PATH", r"C:\magellon\gpfs").replace("\\", "/")

DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_PORT = int(os.environ.get("DB_PORT", "3306"))
DB_NAME = os.environ.get("DB_NAME", "magellon01")
DB_USER = os.environ.get("DB_USER", "root")
DB_PASS = os.environ.get("DB_PASS", "behd1d2")

RMQ_HOST = os.environ.get("RMQ_HOST", "127.0.0.1")
RMQ_PORT = int(os.environ.get("RMQ_PORT", "5672"))
RMQ_USER = os.environ.get("RMQ_USER", "rabbit")
RMQ_PASS = os.environ.get("RMQ_PASS", "behd1d2")
OUT_QUEUE = "motioncor_out_tasks_queue"

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def to_host_path(canonical: str) -> str:
    """Convert /gpfs/... path to host absolute path."""
    p = (canonical or "").replace("\\", "/")
    if p.startswith("/gpfs/"):
        return GPFS_HOST_PATH + p[5:]
    return p


def to_canonical(path: str) -> str:
    p = (path or "").replace("\\", "/")
    if p.startswith(GPFS_HOST_PATH):
        return "/gpfs" + p[len(GPFS_HOST_PATH):]
    return p


def uuid_bytes(u: str) -> bytes:
    return uuid.UUID(u).bytes


# ---------------------------------------------------------------------------
# Phase 1 — Discover tasks from DB
# ---------------------------------------------------------------------------

def discover_tasks(session_name: str) -> list[dict]:
    """Return all stage=1 MotionCor tasks for the session (any status)."""
    conn = pymysql.connect(host=DB_HOST, port=DB_PORT, db=DB_NAME,
                           user=DB_USER, password=DB_PASS, charset="utf8mb4")
    try:
        with conn.cursor() as cur:
            # Find jobs linked to this session name
            cur.execute(
                """
                SELECT t.oid, t.job_id, t.image_id, t.status_id,
                       t.image_name, t.image_path, t.frame_name, t.frame_path,
                       COALESCE(i.pixel_size, 1.0)          AS pixel_size,
                       COALESCE(i.acceleration_voltage, 300) AS kv
                FROM image_job_task t
                LEFT JOIN image i ON i.oid = t.image_id
                LEFT JOIN image_job j ON j.oid = t.job_id
                LEFT JOIN msession s ON s.oid = j.session_id
                WHERE t.stage = 1
                  AND (s.name = %s OR s.name = %s)
                ORDER BY t.image_name
                """,
                (session_name.upper(), session_name.lower()),
            )
            cols = [d[0] for d in cur.description]
            rows = []
            for row in cur.fetchall():
                d = dict(zip(cols, row))
                for f in ("oid", "job_id", "image_id"):
                    if isinstance(d.get(f), (bytes, bytearray)):
                        d[f] = str(uuid.UUID(bytes=bytes(d[f])))
                rows.append(d)
            return rows
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Phase 2 — Ensure frames in S3
# ---------------------------------------------------------------------------

def s3_key_exists(s3, bucket: str, key: str) -> bool:
    try:
        s3.head_object(Bucket=bucket, Key=key)
        return True
    except Exception:
        return False


def ensure_frame_in_s3(s3, bucket: str, s3_key: str, local_path: str) -> bool:
    """Upload local_path to S3 if not already there. Returns True on success."""
    if s3_key_exists(s3, bucket, s3_key):
        return True
    if not os.path.exists(local_path):
        print(f"    WARN: frame not in S3 and not on disk: {local_path}", flush=True)
        return False
    size_mb = os.path.getsize(local_path) / 1024 / 1024
    print(f"    Uploading {os.path.basename(local_path)} ({size_mb:.0f} MB) ...", flush=True)
    s3.upload_file(local_path, bucket, s3_key)
    return True


# ---------------------------------------------------------------------------
# Phase 3 — Build manifest + cloud-init script
# ---------------------------------------------------------------------------

def build_manifest(s3, ecr, tasks: list[dict], session: str,
                   kv: float, pixsize: float, fmdose: float,
                   gain_s3_key: str) -> tuple[dict, str]:
    """Returns (manifest_dict, manifest_presigned_url)."""
    ecr_resp  = ecr.get_authorization_token()
    ecr_token = ecr_resp["authorizationData"][0]["authorizationToken"]
    ecr_expiry= ecr_resp["authorizationData"][0]["expiresAt"].isoformat()

    manifest = {
        "kv":      kv,
        "pixsize": pixsize,
        "fmdose":  fmdose,
        "gain_get": s3.generate_presigned_url("get_object",
                        Params={"Bucket": BUCKET, "Key": gain_s3_key}, ExpiresIn=EXPIRE),
        "log_put":  s3.generate_presigned_url("put_object",
                        Params={"Bucket": BUCKET, "Key": f"{session}/status/run.log"}, ExpiresIn=EXPIRE),
        "done_put": s3.generate_presigned_url("put_object",
                        Params={"Bucket": BUCKET, "Key": f"{session}/status/ALL_DONE"}, ExpiresIn=EXPIRE),
        "ecr_token":  ecr_token,
        "ecr_expiry": ecr_expiry,
        "frames": {},
    }

    for task in tasks:
        # frame filename is the last component of frame_path (canonical)
        frame_path = task.get("frame_path") or task.get("image_path") or ""
        fname = os.path.basename(frame_path)
        if not fname.lower().endswith(".tif"):
            fname = fname + ".tif"
        stem  = fname[:-4]   # strip .tif
        s3_frame_key = f"{session}/frames/{fname}"
        manifest["frames"][fname] = {
            "task_id":    task["oid"],
            "job_id":     task["job_id"],
            "image_id":   task.get("image_id", ""),
            "image_name": task.get("image_name", stem),
            "get":         s3.generate_presigned_url("get_object",
                               Params={"Bucket": BUCKET, "Key": s3_frame_key}, ExpiresIn=EXPIRE),
            "put_results": s3.generate_presigned_url("put_object",
                               Params={"Bucket": BUCKET, "Key": f"{session}/results/{stem}.tar.gz"}, ExpiresIn=EXPIRE),
            "put_status":  s3.generate_presigned_url("put_object",
                               Params={"Bucket": BUCKET, "Key": f"{session}/status/{fname}.status"}, ExpiresIn=EXPIRE),
        }

    s3.put_object(Bucket=BUCKET, Key=f"{session}/manifest.json",
                  Body=json.dumps(manifest).encode())
    url = s3.generate_presigned_url("get_object",
              Params={"Bucket": BUCKET, "Key": f"{session}/manifest.json"}, ExpiresIn=EXPIRE)
    print(f"    Manifest: {len(manifest['frames'])} frames, ECR expiry {ecr_expiry}", flush=True)
    return manifest, url


def build_cloud_init(manifest_url: str, kv: float, pixsize: float, fmdose: float) -> str:
    script_lines = [
        "#!/bin/bash",
        "set -x",
        "LOG=/var/log/motioncor.log",
        "exec >> ${LOG} 2>&1",
        f'echo "=== pipeline-v1 started $(date) ==="',
        "",
        f"IMAGE={IMAGE}",
        f"BINARY={BINARY}",
        "WORKDIR=/scratch",
        f'MANIFEST_URL="{manifest_url}"',
        f"KV={kv}",
        f"PIXSIZE={pixsize}",
        f"FMDOSE={fmdose}",
        "",
        "df -h /",
        "mkdir -p ${WORKDIR}/frames ${WORKDIR}/gains ${WORKDIR}/results /tmp/urls",
        "",
        # Download manifest
        'echo "=== Downloading manifest ==="',
        'curl -sf -o /tmp/manifest.json "${MANIFEST_URL}" \\',
        '  && echo "Manifest OK" \\',
        '  || { echo "FATAL: manifest download failed"; exit 1; }',
        "",
        # Extract URLs
        "python3 << 'PYEOF_URLS'",
        "import json, os",
        "d = json.load(open('/tmp/manifest.json'))",
        "os.makedirs('/tmp/urls', exist_ok=True)",
        "open('/tmp/urls/log_put',   'w').write(d['log_put'])",
        "open('/tmp/urls/done_put',  'w').write(d['done_put'])",
        "open('/tmp/urls/gain_get',  'w').write(d['gain_get'])",
        "open('/tmp/urls/ecr_token', 'w').write(d['ecr_token'])",
        "for fname, info in d['frames'].items():",
        "    stem = fname[:-4]",
        "    open(f'/tmp/urls/{stem}_get',        'w').write(info['get'])",
        "    open(f'/tmp/urls/{stem}_put_results','w').write(info['put_results'])",
        "    open(f'/tmp/urls/{stem}_put_status', 'w').write(info['put_status'])",
        "print('URLs extracted: {} frames'.format(len(d['frames'])))",
        "PYEOF_URLS",
        "[ -f /tmp/urls/log_put ] || { echo 'FATAL: URL extraction failed'; exit 1; }",
        "",
        # S3 connectivity test
        'echo "=== S3 connectivity test ==="',
        'echo "ALIVE $(date) pipeline-v1" > /tmp/alive.txt',
        "LOG_PUT_URL=$(cat /tmp/urls/log_put)",
        'curl -sf -T /tmp/alive.txt "${LOG_PUT_URL}" \\',
        '  && echo "S3 PUT OK" \\',
        '  || { echo "FATAL: S3 PUT test failed"; exit 1; }',
        "",
        # ECR login
        'echo "=== ECR login ==="',
        f"ECR_PASSWORD=$(cat /tmp/urls/ecr_token | base64 -d | cut -d: -f2)",
        f'echo "${{ECR_PASSWORD}}" | docker login --username AWS --password-stdin {ECR_HOST} \\',
        '  && echo "ECR OK" \\',
        '  || { echo "FATAL: ECR login failed"; exit 1; }',
        "",
        # Docker pull
        'echo "=== Docker pull $(date) ==="',
        "docker pull ${IMAGE} && echo 'Pull OK' || { echo 'FATAL: docker pull failed'; exit 1; }",
        "df -h /",
        "",
        # Download gain
        "GAIN_URL=$(cat /tmp/urls/gain_get)",
        'curl -sf -o ${WORKDIR}/gains/gain.tif "${GAIN_URL}" \\',
        '  && echo "Gain OK" \\',
        '  || echo "WARN: gain download failed (will proceed anyway)"',
        "",
        # Per-frame loop
        'echo "=== Per-frame processing starts at $(date) ==="',
        "N=0",
        "TOTAL=$(ls /tmp/urls/*_get | grep -v gain_get | wc -l)",
        'echo "Total frames: ${TOTAL}"',
        "",
        'echo "STARTED $(date) frames=${TOTAL}" > /tmp/started.txt',
        'curl -sf -T /tmp/started.txt "${LOG_PUT_URL}" && echo "STARTED marker OK" || echo "WARN: STARTED marker failed"',
        "",
        "for GET_FILE in $(ls /tmp/urls/*_get | grep -v gain_get | sort); do",
        "  STEM=$(basename ${GET_FILE} _get)",
        '  STEM_BASE="${STEM%.mrc}"',
        '  FNAME="${STEM}.tif"',
        "  N=$((N+1))",
        '  echo ""',
        '  echo "[${N}/${TOTAL}] $(date) === ${STEM}"',
        "  df -h / | tail -1",
        "",
        "  GET_URL=$(cat ${GET_FILE})",
        '  curl -sf -o ${WORKDIR}/frames/${FNAME} "${GET_URL}" \\',
        '    && echo "  Download OK $(du -sh ${WORKDIR}/frames/${FNAME} | cut -f1)" \\',
        '    || { echo "  WARN: download failed, skipping"; continue; }',
        "",
        # Run MotionCor2 with dose params from manifest
        "  docker run --rm --gpus all --entrypoint /bin/bash -v ${WORKDIR}:/scratch ${IMAGE} -c \"",
        "    /app/${BINARY} \\",
        "      -InTiff /scratch/frames/${FNAME} \\",
        "      -OutMrc /scratch/results/${STEM_BASE}.mrc \\",
        "      -Gain /scratch/gains/gain.tif \\",
        "      -Patch 5 5 -Iter 10 -Tol 0.5 -Gpu 0 -FtBin 2 \\",
        "      -kV ${KV} -PixSize ${PIXSIZE} -FmDose ${FMDOSE} \\",
        "      -LogDir /scratch/results/",
        '  " && STATUS=OK || STATUS=FAILED',
        '  echo "  MotionCor2 ${STATUS}"',
        "",
        "  rm -f ${WORKDIR}/frames/${FNAME}",
        "",
        "  RESULT_COUNT=$(find ${WORKDIR}/results/ -maxdepth 1 -name '${STEM_BASE}*' | wc -l)",
        '  echo "  result files: ${RESULT_COUNT}"',
        "  find ${WORKDIR}/results/ -maxdepth 1 -name '${STEM_BASE}*' -ls",
        "  if [ ${RESULT_COUNT} -gt 0 ]; then",
        "    tar czf /tmp/res.tar.gz -C ${WORKDIR}/results/ $(ls ${WORKDIR}/results/ | grep ^${STEM_BASE}) 2>/dev/null || true",
        "  else",
        '    echo "  WARN: no results for ${STEM_BASE}"',
        "    echo 'EMPTY' > /tmp/empty.txt && cp /tmp/empty.txt /tmp/res.tar.gz",
        "  fi",
        "  PUT_RESULTS_URL=$(cat /tmp/urls/${STEM}_put_results)",
        '  curl -sf -T /tmp/res.tar.gz "${PUT_RESULTS_URL}" \\',
        '    && echo "  results PUT OK ($(wc -c < /tmp/res.tar.gz) bytes)" \\',
        '    || echo "  results PUT FAILED"',
        "  rm -f /tmp/res.tar.gz",
        "  rm -f ${WORKDIR}/results/${STEM_BASE}*",
        "",
        '  echo "${N}/${TOTAL} ${STATUS} $(date)" > /tmp/fstatus.txt',
        "  PUT_STATUS_URL=$(cat /tmp/urls/${STEM}_put_status)",
        '  curl -sf -T /tmp/fstatus.txt "${PUT_STATUS_URL}" || true',
        "",
        "  if [ $((N % 5)) -eq 0 ]; then",
        "    curl -sf -T ${LOG} ${LOG_PUT_URL} || true",
        "  fi",
        "done",
        "",
        'echo "=== All ${N} frames completed at $(date) ==="',
        "",
        "DONE_PUT_URL=$(cat /tmp/urls/done_put)",
        'echo "ALL_DONE ${N}/${TOTAL} $(date)" > /tmp/done.txt',
        'curl -sf -T /tmp/done.txt "${DONE_PUT_URL}" && echo "ALL_DONE PUT OK" || echo "ALL_DONE PUT FAILED"',
        "curl -sf -T ${LOG} ${LOG_PUT_URL} || true",
        "sudo shutdown -h now",
    ]

    script_text = "\n".join(script_lines) + "\n"

    systemd_unit = """\
[Unit]
Description=Magellon MotionCor pipeline
After=docker.service network-online.target
Requires=docker.service

[Service]
Type=simple
ExecStart=/usr/local/bin/motioncor.sh
StandardOutput=append:/var/log/motioncor.log
StandardError=append:/var/log/motioncor.log
TimeoutStartSec=0
TimeoutStopSec=0
KillMode=process
Restart=no

[Install]
WantedBy=multi-user.target
"""

    def yaml_block(text, indent=6):
        pad = " " * indent
        return "\n".join(pad + line for line in text.split("\n"))

    cloud_config = (
        "#cloud-config\n"
        "write_files:\n"
        "  - path: /usr/local/bin/motioncor.sh\n"
        "    permissions: '0755'\n"
        "    owner: root:root\n"
        "    content: |\n"
        + yaml_block(script_text.rstrip("\n"))
        + "\n  - path: /etc/systemd/system/motioncor.service\n"
        "    permissions: '0644'\n"
        "    owner: root:root\n"
        "    content: |\n"
        + yaml_block(systemd_unit.rstrip("\n"))
        + "\nruncmd:\n"
        "  - systemctl daemon-reload\n"
        "  - systemctl enable motioncor.service\n"
        "  - systemctl start motioncor.service\n"
    )
    return cloud_config


# ---------------------------------------------------------------------------
# Phase 4 — Launch instance
# ---------------------------------------------------------------------------

def launch_instance(ec2, iam, cloud_config: str, session: str) -> str:
    """Launch a g4dn.2xlarge; return instance ID."""
    profile_arn = None
    try:
        ip = iam.get_instance_profile(InstanceProfileName=ROLE_NAME)
        profile_arn = ip["InstanceProfile"]["Arn"]
    except Exception:
        pass

    kwargs = dict(
        ImageId          = AMI,
        InstanceType     = "g4dn.2xlarge",
        MinCount=1, MaxCount=1,
        SubnetId         = SUBNET,
        SecurityGroupIds = [SG],
        KeyName          = SSH_KEY,
        UserData         = cloud_config,
        InstanceInitiatedShutdownBehavior = "terminate",
        BlockDeviceMappings = [{
            "DeviceName": "/dev/xvda",
            "Ebs": {"VolumeSize": 100, "VolumeType": "gp3", "DeleteOnTermination": True},
        }],
        TagSpecifications = [{
            "ResourceType": "instance",
            "Tags": [{"Key": "Name", "Value": f"magellon-motioncor-{session}"}],
        }],
    )
    if profile_arn:
        kwargs["IamInstanceProfile"] = {"Arn": profile_arn}

    resp = ec2.run_instances(**kwargs)
    iid  = resp["Instances"][0]["InstanceId"]
    return iid


# ---------------------------------------------------------------------------
# Phase 5 — Monitor
# ---------------------------------------------------------------------------

def monitor(s3, ec2, session: str, iid: str, launch_utc: datetime.datetime,
            poll_secs: int = 90, timeout_min: int = 120) -> bool:
    """Poll S3 until ALL_DONE or timeout. Returns True on success."""
    ticks = int(timeout_min * 60 / poll_secs)
    last_results = 0

    for _ in range(ticks):
        time.sleep(poll_secs)
        elapsed = int((datetime.datetime.now(datetime.timezone.utc) - launch_utc).total_seconds() / 60)
        try:
            state = ec2.describe_instances(InstanceIds=[iid])[
                "Reservations"][0]["Instances"][0]["State"]["Name"]

            results  = s3.list_objects_v2(Bucket=BUCKET, Prefix=f"{session}/results/").get("Contents", [])
            ok_res   = [o for o in results if o["LastModified"] > launch_utc]
            all_done = [o for o in s3.list_objects_v2(
                            Bucket=BUCKET, Prefix=f"{session}/status/ALL_DONE").get("Contents", [])
                        if o["LastModified"] > launch_utc]

            status_objs = s3.list_objects_v2(
                Bucket=BUCKET, Prefix=f"{session}/status/").get("Contents", [])
            ok_status = [o for o in status_objs
                         if o["Key"].endswith(".status") and o["LastModified"] > launch_utc]

            print(f"[~{elapsed}m] state={state} | status={len(ok_status)} | results={len(ok_res)}",
                  flush=True)

            if len(ok_res) > last_results:
                last_results = len(ok_res)
                if last_results == 1:
                    r0 = ok_res[0]
                    mins = (r0["LastModified"] - launch_utc).total_seconds() / 60
                    print(f"  *** First result at ~{mins:.1f}m: {r0['Key'].split('/')[-1]} ({r0['Size']}B)",
                          flush=True)

            if all_done:
                print(f"  *** ALL_DONE! {len(ok_res)}/{len(results)} results newer than launch", flush=True)
                return True

        except Exception as e:
            print(f"[poll error] {e}", flush=True)

    print("Timeout — no ALL_DONE", flush=True)
    return False


# ---------------------------------------------------------------------------
# Phase 6 — Collect results and update DB
# ---------------------------------------------------------------------------

def collect_results(s3, tasks: list[dict], session: str,
                    launch_utc: datetime.datetime, fao_root: str) -> list[dict]:
    """
    Download result tarballs, extract to fao/<image_name>/, return list of
    completed task dicts (with 'result_files' key added).
    """
    results_raw = s3.list_objects_v2(Bucket=BUCKET, Prefix=f"{session}/results/").get("Contents", [])
    ok_results  = {o["Key"].split("/")[-1]: o for o in results_raw
                   if o["LastModified"] > launch_utc}

    completed = []
    for task in tasks:
        frame_path = task.get("frame_path") or task.get("image_path") or ""
        fname = os.path.basename(frame_path)
        if not fname.lower().endswith(".tif"):
            fname += ".tif"
        stem      = fname[:-4]            # e.g. 20241203_54480_integrated_movie.mrc
        stem_base = stem[:-4] if stem.endswith(".mrc") else stem  # strip inner .mrc
        tar_key   = f"{stem}.tar.gz"      # matches put_results key

        if tar_key not in ok_results:
            print(f"  MISSING result for {stem}", flush=True)
            continue

        image_name = task.get("image_name") or stem_base
        outdir = os.path.join(fao_root, stem)   # fao/20241203_54480_integrated_movie.mrc/
        os.makedirs(outdir, exist_ok=True)

        obj_key  = ok_results[tar_key]["Key"]
        obj_size = ok_results[tar_key]["Size"]
        print(f"  [{len(completed)+1}/{len(tasks)}] {image_name}  ({obj_size//1024//1024} MB) ...",
              end=" ", flush=True)

        body = s3.get_object(Bucket=BUCKET, Key=obj_key)["Body"].read()
        with tarfile.open(fileobj=io.BytesIO(body), mode="r:gz") as tf:
            members = tf.getmembers()
            tf.extractall(path=outdir)

        extracted = os.listdir(outdir)
        print(f"-> {len(members)} files: {extracted}", flush=True)
        task["result_files"] = [os.path.join(outdir, f) for f in extracted]
        completed.append(task)

    return completed


def mark_tasks_complete(completed: list[dict]) -> None:
    """Set status_id=2 for each completed task in DB."""
    if not completed:
        return
    conn = pymysql.connect(host=DB_HOST, port=DB_PORT, db=DB_NAME,
                           user=DB_USER, password=DB_PASS, charset="utf8mb4")
    try:
        with conn.cursor() as cur:
            for task in completed:
                cur.execute(
                    "UPDATE image_job_task SET status_id=2 WHERE oid=%s",
                    (uuid_bytes(task["oid"]),),
                )
        conn.commit()
        print(f"  DB: {len(completed)} tasks marked completed.", flush=True)
    finally:
        conn.close()


def publish_results_to_queue(completed: list[dict]) -> None:
    """Publish TaskResultMessage to motioncor_out_tasks_queue for each completed task."""
    if not completed:
        return
    creds  = pika.PlainCredentials(RMQ_USER, RMQ_PASS)
    params = pika.ConnectionParameters(host=RMQ_HOST, port=RMQ_PORT, credentials=creds, heartbeat=60)
    conn   = pika.BlockingConnection(params)
    ch     = conn.channel()
    ch.queue_declare(queue=OUT_QUEUE, durable=True)

    now = datetime.datetime.now(datetime.timezone.utc).isoformat()
    for task in completed:
        result_files = task.get("result_files", [])
        output_files = [{"name": os.path.basename(f), "path": to_canonical(f), "required": True}
                        for f in result_files]
        msg = {
            "worker_instance_id": str(uuid.uuid4()),
            "task_id":    task["oid"],
            "job_id":     task["job_id"],
            "image_id":   task.get("image_id", ""),
            "image_path": task.get("image_path", ""),
            "session_name": task.get("image_name", "").split("_")[0],
            "code":        200,
            "message":     "MotionCor completed on AWS",
            "description": "Aligned MRC and DW MRC from GPU batch run",
            "status":      {"code": 2, "name": "completed", "description": "Completed"},
            "type":        {"code": 5, "name": "MOTIONCOR", "description": "Motion Correction"},
            "created_date": now,
            "started_on":   now,
            "ended_on":     now,
            "meta_data":    [],
            "output_files": output_files,
        }
        ch.basic_publish(exchange="", routing_key=OUT_QUEUE,
                         body=json.dumps(msg),
                         properties=pika.BasicProperties(delivery_mode=2))
    conn.close()
    print(f"  RMQ: {len(completed)} result messages published to {OUT_QUEUE}.", flush=True)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--session",       default="24dec03a")
    ap.add_argument("--gain",          default=None,
                    help="Host path to gain reference (auto-detected from GPFS if omitted)")
    ap.add_argument("--kv",            type=float, default=300.0)
    ap.add_argument("--pixsize",       type=float, default=1.0)
    ap.add_argument("--fmdose",        type=float, default=1.0)
    ap.add_argument("--fao-root",      default=None,
                    help="Host root of fao/ directories (default: inferred from GPFS path)")
    ap.add_argument("--tasks-file",    default=None,
                    help="Re-use saved tasks JSON instead of querying DB")
    ap.add_argument("--collect-only",  action="store_true",
                    help="Skip launch; only download results for LAST run")
    ap.add_argument("--no-publish",    action="store_true",
                    help="Do not publish to motioncor_out_tasks_queue after collecting")
    ap.add_argument("--no-db-update",  action="store_true",
                    help="Do not mark tasks complete in DB")
    ap.add_argument("--dry-run",       action="store_true")
    args = ap.parse_args()

    session  = args.session.lower()
    fao_root = args.fao_root or os.path.join(
        GPFS_HOST_PATH.replace("/", os.sep), session, "home", "fao"
    )
    gain_key  = f"{session}/gains"
    gain_path = args.gain or os.path.join(
        GPFS_HOST_PATH.replace("/", os.sep), session, "home", "gains"
    )

    # ------------------------------------------------------------------ AWS clients
    s3  = boto3.client("s3",  region_name=REGION)
    ecr = boto3.client("ecr", region_name=REGION)
    iam = boto3.client("iam", region_name=REGION)
    ec2 = boto3.client("ec2", region_name=REGION)

    # ------------------------------------------------------------------ Phase 1: Discover tasks
    if args.tasks_file:
        with open(args.tasks_file) as f:
            tasks = json.load(f)
        print(f"[1] Loaded {len(tasks)} tasks from {args.tasks_file}", flush=True)
    else:
        print(f"[1] Querying DB for stage=1 MotionCor tasks (session={session.upper()}) ...", flush=True)
        tasks = discover_tasks(session)
        print(f"    Found {len(tasks)} tasks.", flush=True)
        if not tasks:
            print("    Nothing to do — run the import first.", flush=True)
            sys.exit(0)

        save_path = f"sandbox/aws/motioncor_tasks_{session}.json"
        with open(save_path, "w") as f:
            json.dump(tasks, f, indent=2, default=str)
        print(f"    Tasks saved to {save_path}", flush=True)

        # Use actual kV/PixSize from DB if available
        sample = tasks[0]
        if not args.kv and sample.get("kv"):
            args.kv = float(sample["kv"])
        if not args.pixsize and sample.get("pixel_size"):
            args.pixsize = float(sample["pixel_size"])

    if args.dry_run:
        print("\n--- DRY RUN ---")
        for t in tasks[:5]:
            fp = t.get("frame_path") or t.get("image_path", "")
            print(f"  {t['oid'][:8]}  {os.path.basename(fp)}  kv={args.kv}  px={args.pixsize}")
        if len(tasks) > 5:
            print(f"  ... ({len(tasks)-5} more)")
        return

    # ------------------------------------------------------------------ Phase 2: Ensure frames in S3
    if not args.collect_only:
        print(f"\n[2] Checking frames in S3 (bucket={BUCKET}) ...", flush=True)
        gain_files = [f for f in os.listdir(gain_path) if f.endswith(".tif")] if os.path.isdir(gain_path) else []
        if not gain_files:
            print(f"    WARN: no gain .tif found in {gain_path}; proceeding without gain", flush=True)
            gain_s3_key = f"{session}/gains/placeholder.tif"
        else:
            gain_file = gain_files[0]
            gain_s3_key = f"{session}/gains/{gain_file}"
            ensure_frame_in_s3(s3, BUCKET, gain_s3_key, os.path.join(gain_path, gain_file))

        frames_missing = 0
        for task in tasks:
            frame_path = task.get("frame_path") or task.get("image_path") or ""
            fname = os.path.basename(frame_path)
            if not fname.lower().endswith(".tif"):
                fname += ".tif"
            s3_key = f"{session}/frames/{fname}"
            local  = to_host_path(frame_path) if frame_path.startswith("/gpfs") else frame_path
            if not ensure_frame_in_s3(s3, BUCKET, s3_key, local):
                frames_missing += 1
        print(f"    {len(tasks)-frames_missing}/{len(tasks)} frames available in S3", flush=True)
        if frames_missing == len(tasks):
            print("FATAL: no frames available in S3", flush=True)
            sys.exit(1)
    else:
        gain_files = [k.split("/")[-1] for k in [
            o["Key"] for o in s3.list_objects_v2(
                Bucket=BUCKET, Prefix=f"{session}/gains/").get("Contents", [])
        ]]
        gain_s3_key = f"{session}/gains/{gain_files[0]}" if gain_files else f"{session}/gains/gain.tif"

    # ------------------------------------------------------------------ Collect-only shortcut
    if args.collect_only:
        print("\n[collect-only] Downloading results from last run ...", flush=True)
        # Use a very early LAUNCH_UTC to include all existing results
        launch_utc = datetime.datetime(2020, 1, 1, tzinfo=datetime.timezone.utc)
        completed = collect_results(s3, tasks, session, launch_utc, fao_root)
        print(f"\nCollected {len(completed)}/{len(tasks)} frames to {fao_root}")
        if not args.no_db_update:
            mark_tasks_complete(completed)
        if not args.no_publish:
            publish_results_to_queue(completed)
        return

    # ------------------------------------------------------------------ Phase 3: Manifest
    print(f"\n[3] Building manifest (kV={args.kv}, PixSize={args.pixsize}, FmDose={args.fmdose}) ...", flush=True)
    manifest, manifest_url = build_manifest(s3, ecr, tasks, session,
                                            args.kv, args.pixsize, args.fmdose, gain_s3_key)
    cloud_config = build_cloud_init(manifest_url, args.kv, args.pixsize, args.fmdose)
    assert cloud_config.startswith("#cloud-config")
    assert len(cloud_config) < 16384, f"Cloud-config too large: {len(cloud_config)}"
    print(f"    Cloud-config: {len(cloud_config)} bytes", flush=True)

    # ------------------------------------------------------------------ Phase 4: Launch
    print(f"\n[4] Launching g4dn.2xlarge for {len(tasks)} frames ...", flush=True)
    iid = launch_instance(ec2, iam, cloud_config, session)
    launch_utc = datetime.datetime.now(datetime.timezone.utc)
    print(f"    Instance: {iid}  launched at {launch_utc.strftime('%H:%M:%S')} UTC", flush=True)
    print(f"    S3 log:   s3://{BUCKET}/{session}/status/run.log", flush=True)

    # ------------------------------------------------------------------ Phase 5: Monitor
    print(f"\n[5] Monitoring (~{len(tasks)} min expected at ~60s/frame) ...", flush=True)
    success = monitor(s3, ec2, session, iid, launch_utc,
                      poll_secs=90, timeout_min=int(len(tasks) * 2 + 30))
    if not success:
        print("WARNING: timed out — results may be partial", flush=True)

    # ------------------------------------------------------------------ Phase 6: Collect
    print(f"\n[6] Collecting results to {fao_root} ...", flush=True)
    os.makedirs(fao_root, exist_ok=True)
    completed = collect_results(s3, tasks, session, launch_utc, fao_root)
    print(f"\nDone. {len(completed)}/{len(tasks)} frames collected.", flush=True)

    if not args.no_db_update:
        print("\n[7] Updating DB ...", flush=True)
        mark_tasks_complete(completed)

    if not args.no_publish:
        print("\n[8] Publishing results to RabbitMQ ...", flush=True)
        publish_results_to_queue(completed)

    print("\nPipeline complete.", flush=True)


if __name__ == "__main__":
    main()
