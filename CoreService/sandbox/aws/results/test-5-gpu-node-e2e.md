# Test 5 — GPU Node End-to-End (MotionCor Plugin via RabbitMQ)

**Date:** 2026-04-16
**Instance:** g4dn.2xlarge spot, us-east-1 (1× T4 GPU, 32 GB RAM)
**AMI:** amzn2-ami-ecs-gpu-hvm (Amazon Linux 2 + Docker + NVIDIA toolkit)
**Instance ID:** i-09759155584afaaf9
**IP:** 52.201.255.172

## Objective

Verify the full MotionCor plugin dispatch path works end-to-end on a real GPU:
Windows → RabbitMQ → plugin consumer → MotionCor2 binary → output queue → results

This exercises the actual plugin code path (FastAPI + daemon-thread RabbitMQ consumer + MC2 subprocess), not just the MC2 binary in isolation.

## Architecture

```
Windows (test_batch_publish.py)
  → pika publish to EC2:5672 (motioncor_tasks_queue)
  → Docker Compose on EC2:
      rabbitmq:3.13-management
      motioncor plugin (NVIDIA runtime, /data:/data:ro, /jobs:/jobs)
  → MC2 binary processes .tif frames on T4 GPU
  → result on motioncor_out_tasks_queue
  ← pika consume on Windows
```

## Results — Run 1 (PASS)

| Example | Status | Time | Output |
|---------|--------|------|--------|
| example1 (553 MB, 8192×8192) | code=200 OK | 43.2s | `/jobs/<uuid>/example1_output_DW.mrc` + alignment logs + JPGs |
| example2 (529 MB, 8192×8192) | code=200 OK | 85.3s | `/jobs/<uuid>/example2_output_DW.mrc` + alignment logs + JPGs |

Output files per task:
- `*_DW.mrc` — dose-weighted sum (main output)
- `*_mco_one.jpg`, `*_mco_two.jpg` — patch alignment visualizations
- `*-patch-Patch.log`, `*-patch-Full.log`, `*-patch-Frame.log` — alignment logs

## Run 2 (NOT COMPLETED)

AWS credentials expired before Run 2 could connect. Run 1 proves the pipeline works; repeatability check deferred.

## Gotchas Hit (in order)

| # | Issue | Fix |
|---|-------|-----|
| 1 | `rsync` not available in Windows git-bash | Rewrote deploy to use `tar czf` + `scp` |
| 2 | `activate.sh` overwrites `SCRIPT_DIR` | Save/restore: `MY_DIR="$SCRIPT_DIR"` before source |
| 3 | Dockerfile doesn't COPY `.whl` before `pip install` | Patch Dockerfile on instance: `sed -i "/COPY requirements.txt/i COPY magellon_sdk-0.1.0-py3-none-any.whl ./" Dockerfile` |
| 4 | MSYS converts `/data` env var to `C:/git/data` | `export MSYS2_ENV_CONV_EXCL="REMOTE_DATA_ROOT;GAIN_PATH"` — MSYS_NO_PATHCONV only covers CLI args, not env vars |
| 5 | MC2 binary not executable after tar extraction | `chmod +x` before Docker build |
| 6 | `02-wait-ready.sh` JSON parsing fails | `docker compose ps --format json` output format differs across versions; manual check confirmed services healthy |
| 7 | Spot capacity unavailable in first subnet | Loop through subnets in `00-launch.sh` |

## Timing

| Phase | Duration |
|-------|----------|
| Instance launch + SSH ready | ~3 min |
| Deploy (tar+scp code, S3 pull test data) | ~5 min |
| Docker build (first time) | ~3 min |
| Consumer ready | <10s after compose up |
| Run 1 (2 tasks) | ~90s total (43s + 85s sequential) |
| **Total wall time** | **~12 min** |

## Cost

- g4dn.2xlarge spot: ~$0.226/hr × ~0.25 hr ≈ **$0.06**
- S3 data transfer (in-region): negligible
- **Total: < $0.10**

## Scripts

All in `sandbox/aws/test-5-gpu-node-e2e/`:
- `00-launch.sh` — spot instance + SG + key pair
- `01-deploy.sh` — tar+scp plugin+SDK, S3 pull test data, synthetic gain, docker compose build+up
- `02-wait-ready.sh` — poll for consumer + pre-declare debug_queue
- `03-run-test.sh` — test_batch_publish.py × 2 runs
- `04-verify.sh` — scp outputs + verify.py validation
- `99-teardown.sh` — terminate + cleanup + tag audit

## Operational Notes

- Test data (~1 GB) is pulled from S3 in-region at ~190 MB/s — much faster than uploading from Windows
- Synthetic all-ones gain file avoids the need for a real gain reference
- The plugin's `REPLACE_TYPE: none` is critical — `standard` mode would mangle `/data/...` paths
- `shm_size: 16gb` in compose prevents MC2's ~11 GB pinned CUDA allocation from exhausting /dev/shm
- Instance teardown still pending (credentials expired) — user needs to run `99-teardown.sh` with fresh creds

## Conclusion

The MotionCor plugin works correctly end-to-end on AWS GPU hardware. The full dispatch path — RabbitMQ publish → consumer → MC2 execution → result queue — produces valid dose-weighted MRC outputs with alignment logs and visualization JPGs. The plugin processed two ~500 MB movies in 43s and 85s respectively on a T4 GPU.
