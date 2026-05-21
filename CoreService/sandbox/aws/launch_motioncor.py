"""
Launch motioncor on g4dn.2xlarge via cloud-config write_files + systemd unit.

Strategy (v16):
  - 100 GB EBS root (prevents disk-full during 15 GB frame downloads)
  - Extract ALL pre-signed URLs into /tmp/urls/ files at startup
  - Early S3 connectivity test (file-based curl, not stdin pipe) to fail fast
  - Per-frame: download → run → delete input frame → upload results
  - ALL S3 uploads use `curl -T <file>` (file provides Content-Length)
  - ECR token decoded properly: base64 -d | cut -d: -f2
  - FLAT output path: /scratch/results/${STEM_BASE}  (no per-stem subdir)
  - STEM_BASE strips inner .mrc to avoid double-extension .mrc.mrc
  - Dose params: -kV 300 -PixSize 1.0 -FmDose 1.0 → produces _DW.mrc + log files
  - -LogDir /scratch/results/ → log files land on the mounted volume
  - Tar captures all STEM_BASE* files: .mrc, _DW.mrc, -Full.log, -Patch*.log

Run with:
  python sandbox/aws/launch_motioncor.py
Credentials: AWS_ACCESS_KEY_ID / SECRET / SESSION_TOKEN in env.
"""
import boto3, json

BUCKET    = 'magellon-gpu-eval-work'
SESSION   = '24dec03a'
REGION    = 'us-east-1'
EXPIRE    = 43200
IMAGE     = '789438509093.dkr.ecr.us-east-1.amazonaws.com/magellon-gpu-eval/motioncor:latest'
ECR_HOST  = '789438509093.dkr.ecr.us-east-1.amazonaws.com'
BINARY    = 'MotionCor2'
SUBNET    = 'subnet-0ff0cbd8ad717c562'
AMI       = 'ami-0b729f3f75a1074c4'
SG        = 'sg-0fe348fc1a41d40da'
ROLE_NAME = 'magellon-gpu-eval-batch-instance-role'
SSH_KEY   = 'magellon_test'

FRAME_KEYS = [
    '24dec03a/frames/20241203_54480_integrated_movie.mrc.tif',
    '24dec03a/frames/20241203_54482_integrated_movie.mrc.tif',
    '24dec03a/frames/20241203_54488_integrated_movie.mrc.tif',
    '24dec03a/frames/20241203_54493_integrated_movie.mrc.tif',
    '24dec03a/frames/20241203_54498_integrated_movie.mrc.tif',
    '24dec03a/frames/20241203_54500_integrated_movie.mrc.tif',
    '24dec03a/frames/20241203_54505_integrated_movie.mrc.tif',
    '24dec03a/frames/20241203_54507_integrated_movie.mrc.tif',
    '24dec03a/frames/20241203_54508_integrated_movie.mrc.tif',
    '24dec03a/frames/20241203_54509_integrated_movie.mrc.tif',
    '24dec03a/frames/20241203_54510_integrated_movie.mrc.tif',
    '24dec03a/frames/20241203_54511_integrated_movie.mrc.tif',
    '24dec03a/frames/20241203_54513_integrated_movie.mrc.tif',
    '24dec03a/frames/20241203_54514_integrated_movie.mrc.tif',
    '24dec03a/frames/20241203_54519_integrated_movie.mrc.tif',
    '24dec03a/frames/20241203_54520_integrated_movie.mrc.tif',
    '24dec03a/frames/20241203_54521_integrated_movie.mrc.tif',
    '24dec03a/frames/20241203_54522_integrated_movie.mrc.tif',
    '24dec03a/frames/20241203_54527_integrated_movie.mrc.tif',
    '24dec03a/frames/20241203_54528_integrated_movie.mrc.tif',
    '24dec03a/frames/20241203_54529_integrated_movie.mrc.tif',
    '24dec03a/frames/20241203_54530_integrated_movie.mrc.tif',
    '24dec03a/frames/20241203_54533_integrated_movie.mrc.tif',
    '24dec03a/frames/20241203_54534_integrated_movie.mrc.tif',
    '24dec03a/frames/20241203_54540_integrated_movie.mrc.tif',
    '24dec03a/frames/20241203_54575_integrated_movie.mrc.tif',
    '24dec03a/frames/20241203_54577_integrated_movie.mrc.tif',
    '24dec03a/frames/20241203_54578_integrated_movie.mrc.tif',
    '24dec03a/frames/20241203_54583_integrated_movie.mrc.tif',
    '24dec03a/frames/20241203_54589_integrated_movie.mrc.tif',
]
GAIN_KEY = '24dec03a/gains/20241202_53597_gain_multi_ref.tif'

# ── Clients ──────────────────────────────────────────────────────────────────
s3  = boto3.client('s3',  region_name=REGION)
ecr = boto3.client('ecr', region_name=REGION)
iam = boto3.client('iam', region_name=REGION)
ec2 = boto3.client('ec2', region_name=REGION)

# ── 1. Manifest ──────────────────────────────────────────────────────────────
print('[1] Generating pre-signed URLs...', flush=True)
manifest = {
    'gain_get': s3.generate_presigned_url('get_object',
                    Params={'Bucket': BUCKET, 'Key': GAIN_KEY}, ExpiresIn=EXPIRE),
    'log_put':  s3.generate_presigned_url('put_object',
                    Params={'Bucket': BUCKET, 'Key': SESSION+'/status/run.log'}, ExpiresIn=EXPIRE),
    'done_put': s3.generate_presigned_url('put_object',
                    Params={'Bucket': BUCKET, 'Key': SESSION+'/status/ALL_DONE'}, ExpiresIn=EXPIRE),
    'frames': {}
}
for key in FRAME_KEYS:
    fname = key.split('/')[-1]
    stem  = fname[:-4]   # strip .tif → e.g. 20241203_54480_integrated_movie.mrc
    manifest['frames'][fname] = {
        'get':         s3.generate_presigned_url('get_object',
                           Params={'Bucket': BUCKET, 'Key': key}, ExpiresIn=EXPIRE),
        'put_results': s3.generate_presigned_url('put_object',
                           Params={'Bucket': BUCKET, 'Key': SESSION+'/results/'+stem+'.tar.gz'}, ExpiresIn=EXPIRE),
        'put_status':  s3.generate_presigned_url('put_object',
                           Params={'Bucket': BUCKET, 'Key': SESSION+'/status/'+fname+'.status'}, ExpiresIn=EXPIRE),
    }
ecr_resp  = ecr.get_authorization_token()
ecr_token = ecr_resp['authorizationData'][0]['authorizationToken']
ecr_expiry= ecr_resp['authorizationData'][0]['expiresAt'].isoformat()
manifest['ecr_token']  = ecr_token
manifest['ecr_expiry'] = ecr_expiry

s3.put_object(Bucket=BUCKET, Key=SESSION+'/manifest.json',
              Body=json.dumps(manifest).encode())
manifest_url = s3.generate_presigned_url('get_object',
                   Params={'Bucket': BUCKET, 'Key': SESSION+'/manifest.json'}, ExpiresIn=EXPIRE)
print(f'    Manifest uploaded. ECR expiry: {ecr_expiry}', flush=True)

# ── 2. Build bash script ──────────────────────────────────────────────────────
print('[2] Building bash script...', flush=True)
script_lines = [
    '#!/bin/bash',
    'set -x',
    'LOG=/var/log/motioncor.log',
    'exec >> ${LOG} 2>&1',
    'echo "=== v16 started $(date) ==="',
    '',
    f'IMAGE={IMAGE}',
    f'BINARY={BINARY}',
    'WORKDIR=/scratch',
    f'MANIFEST_URL="{manifest_url}"',
    '',
    'df -h /',
    'mkdir -p ${WORKDIR}/frames ${WORKDIR}/gains ${WORKDIR}/results /tmp/urls',
    '',
    # ── Download manifest ──────────────────────────────────────────────────────
    'echo "=== Downloading manifest ==="',
    'curl -sf -o /tmp/manifest.json "${MANIFEST_URL}" \\',
    '  && echo "Manifest OK" \\',
    '  || { echo "FATAL: manifest download failed"; exit 1; }',
    '',
    # ── Extract all URLs and ECR token into /tmp/urls/ ─────────────────────────
    "python3 << 'PYEOF_URLS'",
    'import json, os',
    "d = json.load(open('/tmp/manifest.json'))",
    "os.makedirs('/tmp/urls', exist_ok=True)",
    "open('/tmp/urls/log_put',   'w').write(d['log_put'])",
    "open('/tmp/urls/done_put',  'w').write(d['done_put'])",
    "open('/tmp/urls/gain_get',  'w').write(d['gain_get'])",
    "open('/tmp/urls/ecr_token', 'w').write(d['ecr_token'])",
    'for fname, urls in d["frames"].items():',
    '    stem = fname[:-4]',
    "    open(f'/tmp/urls/{stem}_get',        'w').write(urls['get'])",
    "    open(f'/tmp/urls/{stem}_put_results','w').write(urls['put_results'])",
    "    open(f'/tmp/urls/{stem}_put_status', 'w').write(urls['put_status'])",
    'print("URLs extracted: {} frames".format(len(d["frames"])))',
    'PYEOF_URLS',
    '[ -f /tmp/urls/log_put ] || { echo "FATAL: URL extraction failed"; exit 1; }',
    '',
    # ── Early S3 connectivity test (file-based PUT, not stdin pipe) ────────────
    'echo "=== S3 connectivity test ==="',
    'echo "ALIVE $(date) v15" > /tmp/alive.txt',
    'LOG_PUT_URL=$(cat /tmp/urls/log_put)',
    'curl -sf -T /tmp/alive.txt "${LOG_PUT_URL}" \\',
    '  && echo "S3 PUT OK" \\',
    '  || { echo "FATAL: S3 PUT test failed"; exit 1; }',
    '',
    # ── ECR login (decode base64 token to extract just the password) ───────────
    'echo "=== ECR login ==="',
    f'ECR_PASSWORD=$(cat /tmp/urls/ecr_token | base64 -d | cut -d: -f2)',
    f'echo "${{ECR_PASSWORD}}" | docker login --username AWS --password-stdin {ECR_HOST} \\',
    '  && echo "ECR OK" \\',
    '  || { echo "FATAL: ECR login failed"; exit 1; }',
    '',
    # ── Docker pull ────────────────────────────────────────────────────────────
    'echo "=== Docker pull $(date) ==="',
    'docker pull ${IMAGE} && echo "Pull OK at $(date)" || { echo "FATAL: docker pull failed"; exit 1; }',
    'df -h /',
    '',
    # ── Download gain ──────────────────────────────────────────────────────────
    'GAIN_URL=$(cat /tmp/urls/gain_get)',
    'curl -sf -o ${WORKDIR}/gains/gain.tif "${GAIN_URL}" \\',
    '  && echo "Gain OK" \\',
    '  || echo "WARN: gain download failed (will proceed anyway)"',
    '',
    # ── Per-frame: download → run → delete input → upload results ──────────────
    'echo "=== Per-frame processing starts at $(date) ==="',
    'N=0',
    'TOTAL=$(ls /tmp/urls/*_get | grep -v gain_get | wc -l)',
    'echo "Total frames: ${TOTAL}"',
    '',
    # Emit STARTED marker now that we know frame count
    'echo "STARTED $(date) frames=${TOTAL}" > /tmp/started.txt',
    'curl -sf -T /tmp/started.txt "${LOG_PUT_URL}" && echo "STARTED marker OK" || echo "WARN: STARTED marker failed"',
    '',
    'for GET_FILE in $(ls /tmp/urls/*_get | grep -v gain_get | sort); do',
    '  STEM=$(basename "${GET_FILE}" _get)',
    # STEM_BASE strips the inner .mrc to avoid double-extension (.mrc.mrc) in output path
    '  STEM_BASE="${STEM%.mrc}"',
    '  FNAME="${STEM}.tif"',
    '  N=$((N+1))',
    '  echo ""',
    '  echo "[${N}/${TOTAL}] $(date) === ${STEM}"',
    '  df -h / | tail -1',
    '',
    '  # Download this frame',
    '  GET_URL=$(cat "${GET_FILE}")',
    '  curl -sf -o ${WORKDIR}/frames/${FNAME} "${GET_URL}" \\',
    '    && echo "  Download OK $(du -sh ${WORKDIR}/frames/${FNAME} | cut -f1)" \\',
    '    || { echo "  WARN: download failed, skipping frame"; continue; }',
    '',
    '  # Run MotionCor2 inside Docker',
    '  # Flat output: /scratch/results/${STEM_BASE}  (no per-frame subdir)',
    '  # -kV 300 -PixSize 0.395 -FmDose 0.803 (60.26 e/A2 / 75 frames) -> _DW.mrc',
    '  # -LogDir points to the results dir so .log files land on the mounted volume',
    '  docker run --rm --gpus all --entrypoint /bin/bash -v ${WORKDIR}:/scratch ${IMAGE} -c "',
    '    /app/${BINARY} \\',
    '      -InTiff /scratch/frames/${FNAME} \\',
    '      -OutMrc /scratch/results/${STEM_BASE}.mrc \\',
    '      -Gain /scratch/gains/gain.tif \\',
    '      -Patch 5 5 -Iter 10 -Tol 0.5 -Gpu 0 -FtBin 2 \\',
    '      -kV 300 -PixSize 0.395 -FmDose 0.803 \\',
    '      -LogDir /scratch/results/',
    '  " && STATUS=OK || STATUS=FAILED',
    '  echo "  MotionCor2 ${STATUS}"',
    '',
    '  # Diagnostic: list everything MotionCor2 produced under /scratch/results/',
    '  echo "  === post-run results listing ==="',
    '  find ${WORKDIR}/results/ -ls 2>/dev/null | head -20',
    '  echo "  === all *.mrc under /scratch/ ==="',
    '  find ${WORKDIR}/ -name "*.mrc" -ls 2>/dev/null | head -20',
    '',
    '  # Delete input frame immediately to keep disk usage low',
    '  rm -f ${WORKDIR}/frames/${FNAME}',
    '',
    '  # Tar all files matching STEM_BASE (aligned MRC, DW MRC, log files)',
    '  # Expected: ${STEM_BASE}.mrc, ${STEM_BASE}_DW.mrc, *-Full.log / *-Patch*.log',
    '  RESULT_COUNT=$(find ${WORKDIR}/results/ -maxdepth 1 -name "${STEM_BASE}*" | wc -l)',
    '  echo "  result files found: ${RESULT_COUNT}"',
    '  find ${WORKDIR}/results/ -maxdepth 1 -name "${STEM_BASE}*" -ls',
    '  if [ "${RESULT_COUNT}" -gt 0 ]; then',
    '    tar czf /tmp/res.tar.gz -C ${WORKDIR}/results/ $(ls ${WORKDIR}/results/ | grep "^${STEM_BASE}") 2>/dev/null || true',
    '  else',
    '    echo "  WARN: no result files for ${STEM_BASE}, uploading empty marker"',
    '    echo "EMPTY ${STATUS} $(date)" > /tmp/empty_result.txt',
    '    cp /tmp/empty_result.txt /tmp/res.tar.gz',
    '  fi',
    '  PUT_RESULTS_URL=$(cat /tmp/urls/${STEM}_put_results)',
    '  curl -sf -T /tmp/res.tar.gz "${PUT_RESULTS_URL}" \\',
    '    && echo "  results PUT OK ($(wc -c < /tmp/res.tar.gz) bytes)" \\',
    '    || echo "  results PUT FAILED"',
    '  rm -f /tmp/res.tar.gz',
    '  rm -f ${WORKDIR}/results/${STEM_BASE}*',
    '',
    '  # Upload frame status (file-based, not stdin pipe)',
    '  echo "${N}/${TOTAL} ${STATUS} $(date)" > /tmp/fstatus.txt',
    '  PUT_STATUS_URL=$(cat /tmp/urls/${STEM}_put_status)',
    '  curl -sf -T /tmp/fstatus.txt "${PUT_STATUS_URL}" \\',
    '    && echo "  status PUT OK" \\',
    '    || echo "  status PUT FAILED"',
    '',
    '  # Upload running log every 5 frames for progress monitoring',
    '  if [ $((N % 5)) -eq 0 ]; then',
    '    curl -sf -T ${LOG} "${LOG_PUT_URL}" || true',
    '  fi',
    'done',
    '',
    'echo "=== All ${N} frames completed at $(date) ==="',
    '',
    # Final ALL_DONE marker
    'DONE_PUT_URL=$(cat /tmp/urls/done_put)',
    'echo "ALL_DONE ${N}/${TOTAL} $(date)" > /tmp/done.txt',
    'curl -sf -T /tmp/done.txt "${DONE_PUT_URL}" \\',
    '  && echo "ALL_DONE PUT OK" \\',
    '  || echo "ALL_DONE PUT FAILED"',
    '',
    # Final log upload
    'curl -sf -T ${LOG} "${LOG_PUT_URL}" || true',
    '',
    'sudo shutdown -h now',
]
script_text = '\n'.join(script_lines) + '\n'
print(f'    Script size: {len(script_text)} bytes', flush=True)

# ── 3. Systemd unit ───────────────────────────────────────────────────────────
systemd_unit = """\
[Unit]
Description=Magellon MotionCor3 batch processing
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

# ── 4. Cloud-config YAML ──────────────────────────────────────────────────────
def yaml_literal_block(text, indent=6):
    pad = ' ' * indent
    return '\n'.join(pad + line for line in text.split('\n'))

script_block  = yaml_literal_block(script_text.rstrip('\n'))
systemd_block = yaml_literal_block(systemd_unit.rstrip('\n'))

cloud_config = f"""#cloud-config
write_files:
  - path: /usr/local/bin/motioncor.sh
    permissions: '0755'
    owner: root:root
    content: |
{script_block}
  - path: /etc/systemd/system/motioncor.service
    permissions: '0644'
    owner: root:root
    content: |
{systemd_block}
runcmd:
  - systemctl daemon-reload
  - systemctl enable motioncor.service
  - systemctl start motioncor.service
"""
print(f'[3] Cloud-config size: {len(cloud_config)} bytes', flush=True)
print(f'    First line: {cloud_config.splitlines()[0]}', flush=True)
assert cloud_config.startswith('#cloud-config'), 'Bad cloud-config start'
assert len(cloud_config) < 16384, f'Cloud-config too large: {len(cloud_config)}'

# ── 5. Instance profile ──────────────────────────────────────────────────────
profile_arn = None
try:
    ip_resp = iam.get_instance_profile(InstanceProfileName=ROLE_NAME)
    profile_arn = ip_resp['InstanceProfile']['Arn']
except Exception:
    try:
        lp = iam.list_instance_profiles_for_role(RoleName=ROLE_NAME)
        if lp['InstanceProfiles']:
            profile_arn = lp['InstanceProfiles'][0]['Arn']
    except Exception as e2:
        print(f'    WARNING: no instance profile: {e2}', flush=True)
print(f'[4] Instance profile: {profile_arn}', flush=True)

# ── 6. Terminate previous instance if still running ──────────────────────────
OLD_IID = 'i-0a8228d6445fe8acb'   # v15
try:
    ec2.terminate_instances(InstanceIds=[OLD_IID])
    print(f'[5] Terminated old v11: {OLD_IID}', flush=True)
except Exception as e:
    print(f'[5] Terminate v11: {e}', flush=True)

# ── 7. Launch ────────────────────────────────────────────────────────────────
print('[6] Launching g4dn.2xlarge v16 (dose params: -kV 300 -PixSize 0.395 -FmDose 0.803 -> _DW.mrc + logs)...', flush=True)
kwargs = dict(
    ImageId          = AMI,
    InstanceType     = 'g4dn.2xlarge',
    MinCount         = 1,
    MaxCount         = 1,
    SubnetId         = SUBNET,
    SecurityGroupIds = [SG],
    KeyName          = SSH_KEY,
    UserData         = cloud_config,
    InstanceInitiatedShutdownBehavior = 'terminate',
    BlockDeviceMappings = [{
        'DeviceName': '/dev/xvda',
        'Ebs': {
            'VolumeSize': 100,
            'VolumeType': 'gp3',
            'DeleteOnTermination': True,
        }
    }],
    TagSpecifications = [{
        'ResourceType': 'instance',
        'Tags': [{'Key': 'Name', 'Value': 'magellon-motioncor-v16'}]
    }],
)
if profile_arn:
    kwargs['IamInstanceProfile'] = {'Arn': profile_arn}

resp = ec2.run_instances(**kwargs)
inst = resp['Instances'][0]
iid  = inst['InstanceId']
az   = inst['Placement']['AvailabilityZone']
state= inst['State']['Name']
print(f'[7] LAUNCHED: {iid}  AZ={az}  State={state}', flush=True)
print(f'    S3 progress: s3://{BUCKET}/{SESSION}/status/run.log', flush=True)
print(f'    S3 done:     s3://{BUCKET}/{SESSION}/status/ALL_DONE', flush=True)
print(f'    Log on instance: /var/log/motioncor.log', flush=True)
print(f'    Systemd: systemctl status motioncor.service', flush=True)
