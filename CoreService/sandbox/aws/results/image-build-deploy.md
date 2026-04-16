# MotionCor Plugin Image — Build & Deploy Guide

How to build the `magellon-gpu-eval/motioncor` GPU container and deploy it to the four target services (Batch / SM Processing / SM Async / EC2 spot). Every pitfall actually hit during test runs is documented here so the next person doesn't waste hours on the same traps.

## 0. TL;DR

```bash
cd sandbox/aws
source common/activate.sh            # loads .env + verifies SSO creds
common/00-setup-iam.sh               # one-time: IAM roles (Batch service/instance, Lambda exec, SM exec)
common/03-setup-buckets.sh           # one-time: S3 buckets (work + results)
common/02-push-image.sh              # builds + pushes motioncor:latest to ECR
```

After this, pick your target service and run its `setup` + `submit` scripts. See §3.

---

## 1. The base image

`image/Dockerfile` — used by Batch, SM Processing, and EC2 spot. (SageMaker Async has its own FastAPI wrapper layer, see §4.)

```dockerfile
FROM --platform=linux/amd64 nvidia/cuda:12.1.1-runtime-ubuntu22.04
```

### 1.1 Why these exact versions

| Choice | Reason |
|---|---|
| `cuda:12.1.1` | MotionCor2 1.6.4 `Cuda121` build — must match major.minor |
| `runtime-ubuntu22.04` (not `devel`) | We don't compile on the image; runtime image is ~2 GB smaller |
| `--platform=linux/amd64` | g4dn is x86_64. Omit this and an ARM-Mac developer will silently push arm64 layers that won't execute on the instance |
| `libtiff5` + symlink to `libtiff.so.6` | MC2 binary dlopens `libtiff.so.6`, Ubuntu 22.04 only ships `libtiff.so.5`. Without the symlink you get `error while loading shared libraries: libtiff.so.6: cannot open shared object file` with no hint that the fix is a one-line `ln -sf` |
| `sed` to rewrite apt sources to HTTPS | Docker Desktop's HTTP proxy tops out at ~500 KB/s; HTTPS gets ~6 MB/s. Cuts `apt-get update` from ~3 min to ~20 s |

### 1.2 The MC2 binary source

The binary lives in the Magellon plugin tree, not in the sandbox:

```
plugins/magellon_motioncor_plugin/motioncor2_binaryfiles/MotionCor2_1.6.4_Cuda121_Mar312023
```

`common/02-push-image.sh` copies it to `image/MotionCor2` at build time, then deletes after push. Don't check the binary into `image/` — it's 3 MB of redundant blob vs. being available in the plugin.

---

## 2. Building and pushing to ECR

```bash
common/02-push-image.sh
```

That script:
1. Stages `MotionCor2` next to the Dockerfile
2. `aws ecr get-login-password | docker login …`
3. `docker build --platform=linux/amd64 -t ${ECR_URI}:${TAG} -t ${ECR_URI}:latest image/`
4. `docker push` both tags
5. Cleans up the staged binary

### 2.1 Windows-specific gotchas (git-bash)

These bit us in every test that shelled out to `docker` or `aws`:

| Symptom | Cause | Fix |
|---|---|---|
| `failed to solve: failed to read dockerfile: open /var/lib/docker/...: no such file or directory` and Docker reports "transferring dockerfile: 2B" | git-bash MSYS rewrote `.` to a Windows path before Docker CLI parsed it | `cd "$SCRIPT_DIR"` + `-f ./Dockerfile` explicitly (see `test-2-sagemaker-async/01-build-push.sh`) |
| `An error occurred (ValidationException): Parameter name must be a fully qualified name` (on `ssm put-parameter --name /magellon/...`) | MSYS rewrote `/magellon/...` → `C:/Program Files/Git/magellon/...` | `export MSYS_NO_PATHCONV=1` **before** the aws call. Applied globally in `upload-pipeline/deploy.sh` |
| `Unable to load paramfile fileb:///tmp/…: [Errno 2] No such file or directory` | `MSYS_NO_PATHCONV=1` was set (needed for SSM paths) but native `aws.exe` then couldn't resolve the Unix `/tmp/...` path | Convert with `cygpath -w "$path"` before passing to aws (see `deploy.sh`'s `winpath` helper) |
| `zip: command not found` | git-bash doesn't ship `zip` | Python one-liner fallback using `zipfile.ZipFile` (see `deploy.sh`'s `zip_dir` helper) |
| `Python was not found; run without arguments to install from the Microsoft Store` | Windows App Execution Aliases intercept `python3` | Use `python` instead, or `python -c ... 2>/dev/null \|\| python3 -c ...` fallback |
| CORS error: `'cors.allowMethods' failed … Member must have length less than or equal to 6` | AWS caps each allowed method to 6 chars; `OPTIONS` is 7 | Use `["*"]` for allowMethods, or individual short verbs (`POST`, `GET`) |

### 2.2 Cross-platform alternatives

If you hit Windows issues, any of these work cleanly:

1. **WSL2 Ubuntu** — everything just works, no path-conv or CLI quirks
2. **A Linux EC2 micro** — `ssh` in, clone, run `common/02-push-image.sh`, pay $0.01
3. **CodeBuild in the account** — deterministic, no laptop deps; overkill for one-shot but good for CI

We've kept the scripts working on git-bash because that was the dev env. If you move to a CI context, drop the `MSYS_NO_PATHCONV` / `cygpath` / `zip_dir` shims.

---

## 3. Deploying by target service

### 3.1 AWS Batch (spot)

```bash
test-1-batch-gpu/01-setup-compute-env.sh   # CE with g4dn.2xlarge spot + ECS-GPU AMI
test-1-batch-gpu/02-setup-queue-and-def.sh # queue + job def (7 vCPU, 28000 MB, 1 GPU)
test-1-batch-gpu/03-submit.sh              # submits one movie
```

**Gotcha: Default Batch AMI is AL2023 without the ECS agent.** Jobs stay in `RUNNABLE` forever because the instance boots but never registers with the ECS cluster. Fix: pin the ECS-optimized GPU AMI explicitly (`amzn2-ami-ecs-gpu-hvm-*`). See `01-setup-compute-env.sh:17-19`.

**Gotcha: `desiredvCpus=0` is required** if you want the CE to scale back down when no jobs are queued. Setting it to anything >0 keeps instances alive burning ~$0.23/h idle.

### 3.2 SageMaker Processing

```bash
test-3-sagemaker-processing/run.py   # creates one-off ProcessingJob
```

**Gotcha: quota for `ml.g4dn.2xlarge for processing job usage` is 0 by default.** First submission fails with `ResourceLimitExceeded`. File a quota increase to 2 (quota code `L-41C11899`) — auto-approved in ~30 min despite the console warning of 24-72h.

Uses the same image as Batch. `run_motioncor.py` has a `sm-processing` mode that reads from fixed SageMaker mount paths `/opt/ml/processing/input/movie` / `/opt/ml/processing/output`.

### 3.3 SageMaker Async Inference

```bash
test-2-sagemaker-async/01-build-push.sh    # different image: FROM motioncor + FastAPI layer
test-2-sagemaker-async/02-deploy.py        # creates model + endpoint-config + endpoint + autoscaling
test-2-sagemaker-async/03-invoke.py        # upload-invoke-wait cycle
test-2-sagemaker-async/99-teardown.py      # deregister scaling, delete endpoint/config/model
```

**Distinct from other tests**: the image wraps our motioncor base with a FastAPI server serving `/ping` and `/invocations` on port 8080 — the SM Async contract. `01-build-push.sh` uses `--build-arg BASE_IMAGE=${ECR_URI}:latest` so you don't duplicate the MC2 layer.

Autoscaling policy: `min=0, max=2`, targets `ApproximateBacklogSizePerInstance=5`. Scale-to-zero works; scale-from-zero costs ~2 min latency + ~$0.04.

### 3.4 EC2 spot (raw)

```bash
test-4-ec2-spot/launch-and-run.sh          # requestSpotInstances + user-data
```

The user-data script does: install AWS CLI v2 → login to ECR → pull image → `docker run` → upload result → `shutdown -h now`.

**Gotcha: The AL2 ECS-GPU AMI does NOT ship the AWS CLI.** So user-data `aws ecr get-login-password …` dies immediately, cloud-init aborts with `set -e`, the `shutdown` never runs, and you pay for an idle instance until you spot it in the console.

Fix (already in `launch-and-run.sh`):
```bash
set -uxo pipefail   # no -e: tolerate partial steps and still reach the shutdown trap
trap 'echo "user-data exiting; shutting down in 30s"; sleep 30; shutdown -h now' EXIT

if ! command -v aws >/dev/null 2>&1; then
  curl -fsSL "https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip" -o /tmp/awscliv2.zip
  (cd /tmp && unzip -q awscliv2.zip && ./aws/install --bin-dir /usr/local/bin --install-dir /usr/local/aws-cli)
fi
export PATH=/usr/local/bin:$PATH
```

The `trap EXIT` + `set +e` pattern is load-bearing: it ensures any failure still triggers shutdown, so you don't bleed spot $ while you sleep.

---

## 4. MotionCor2 host-memory sizing — the universal trap

**This is the single most important non-obvious fact** across all four services.

MotionCor2 1.6.4 allocates ~11 GB of pinned CUDA host memory (`cudaHostAlloc`, shows up as `shmem-rss` in `ps`) for a standard ~500 MB .tif movie, plus ~4 GB of heap. **On g4dn.xlarge (16 GB host RAM) this triggers a Linux kernel OOM kill** (not a cgroup OOM — different code path). You will see:

- Exit code `-9` (SIGKILL)
- Empty stdout / stderr (glibc line-buffered, flushed nothing before SIGKILL)
- No hint in the job log as to why
- `dmesg` on the host (if you can get there) shows `Out of memory: Killed process … (MotionCor2)`

### 4.1 Symptoms by service

| Service | How it manifests |
|---|---|
| Batch | Job ends `FAILED` with `statusReason: Essential container exited`. CloudWatch log group is present but empty |
| SM Processing | Job ends `Failed` with `FailureReason: AlgorithmError: InternalServerError`. No useful log |
| SM Async | Invocation returns error to S3 output, pod restarted silently |
| EC2 spot | Instance shuts down via our trap, .mrc never uploaded to S3 |

### 4.2 The only fix

**Use g4dn.2xlarge** (32 GB host) or larger. Raw spot: $0.226/h vs xlarge $0.158/h — costs ~40% more but is the only size where MC2 actually completes on this movie class.

Larger movies (>800 MB TIFF) may need g4dn.4xlarge (64 GB). Rule of thumb: host RAM >= 6× compressed movie size.

`-GpuMemUsage` (default 0.75) controls pinned memory fraction; reducing to 0.3 buys a few seconds before SIGKILL but doesn't actually fix anything because the 11 GB is measured on the *host*, not the GPU.

### 4.3 Why this is silent

Two reasons compound:

1. Kernel OOM kills the process with SIGKILL — no chance to flush stdout/stderr
2. MC2 binary doesn't override glibc's default buffering, which is block-buffered for non-tty stdout (the typical container scenario). Whatever MC2 printed between the last flush and the kill is lost

**Takeaway**: if an MC2 job dies with no output on any service, suspect host-RAM OOM first. Check the instance type before anything else.

---

## 5. Upload pipeline (optional end-to-end)

```bash
upload-pipeline/deploy.sh
```

Deploys:
- Lambda `${PROJECT}-upload-api` — mints presigned upload/download URLs, behind API key (stored in SSM Parameter Store)
- Lambda Function URL (auth NONE; handler enforces the API key so we can serve directly to browser)
- Lambda `${PROJECT}-on-upload` — S3 `ObjectCreated` on `uploads/` → `batch:SubmitJob`
- S3 event notification wiring

**Prereq:** the Batch queue + job def from §3.1 must exist, or the on-upload Lambda will fail to submit jobs.

Demo UI in `upload-pipeline/web/index.html` — paste the printed `API_URL` + `API_KEY` and open in a browser.

---

## 6. Teardown

Each test dir has its own teardown script. Full wipe:

```bash
common/cleanup-all.sh         # walks every resource tagged Project=magellon-gpu-eval
```

Then `common/tag-audit.sh` confirms nothing alive.

**Batch compute environments take ~5 min to actually delete** after `DELETE` is requested — they drain the instance fleet first. `tag-audit.sh` will show CE status `DELETING` for a while; this is normal.

---

## 7. Quick reference — which gotcha belongs to which script?

| Where | What it does | Why it exists |
|---|---|---|
| `image/Dockerfile:14` | symlink libtiff.so.5 → .so.6 | MC2 dlopen expectation |
| `image/Dockerfile:9` | apt → HTTPS | Docker Desktop proxy speed |
| `common/02-push-image.sh` | stage + clean MotionCor2 binary | Avoid duplicating 3 MB in `image/` |
| `test-1/01-setup-compute-env.sh:17` | pin `amzn2-ami-ecs-gpu-hvm-*` | Default AMI lacks ECS agent |
| `test-1/02-setup-queue-and-def.sh` | 7 vCPU / 28000 MB / 1 GPU | Fits g4dn.2xlarge (8/32/1), not xlarge (4/16/1) |
| `test-2/01-build-push.sh` | `cd $SCRIPT_DIR && -f ./Dockerfile` | Windows Docker path mangle |
| `test-4/launch-and-run.sh` | install AWS CLI inline + `trap EXIT` | AL2 ECS-GPU AMI missing CLI |
| `upload-pipeline/deploy.sh` | `MSYS_NO_PATHCONV=1` + `cygpath` + `zip_dir` helper | git-bash path + missing `zip` |
| `upload-pipeline/deploy.sh` CORS | `allowMethods=["*"]` | AWS 6-char limit per method |
