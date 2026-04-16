# Test 1 — AWS Batch with GPU Spot

Runs MotionCor2 against a single 500MB movie on a spot `g4dn.xlarge` via AWS Batch.

## Why Batch

- Submit a job, Batch provisions the EC2 instance, runs the container, tears it down
- Scales to zero when idle — pure per-second billing for compute
- Spot: ~70% off on-demand price for T4 GPUs
- Best fit for: async batch processing pipelines (our actual motioncor workload)

## Pricing assumptions (us-east-1, 2026)

| Item | Unit price |
|---|---|
| g4dn.xlarge on-demand | $0.526/hr |
| g4dn.xlarge spot | ~$0.158/hr (varies) |
| EBS gp3 (job root) | ~$0.08/GB/mo, prorated per second |
| ECR storage | $0.10/GB/mo |
| Data xfer S3→EC2 same region | $0 |

**Expected cost for one 5-minute MotionCor2 run on spot: ~$0.013 compute + negligible storage.**

## Architecture

```
./03-submit.sh → Batch JobQueue → Batch CE (SPOT g4dn.xlarge, min=0 max=4)
                                    ↓
                                  EC2 spot instance auto-provisions
                                    ↓
                                  Runs ECR image with env vars
                                    ↓
                                  MotionCor2 processes 500MB .tif
                                    ↓
                                  Uploads .mrc to s3://magellon-gpu-eval-work/batch-test/
                                    ↓
                                  Instance auto-terminates (~5 min after job)
```

## Files

| File | Purpose |
|---|---|
| `01-setup-compute-env.sh` | Create SG, CE (spot g4dn, min=0 max=4), wait VALID |
| `02-setup-queue-and-def.sh` | Create job queue + job definition |
| `03-submit.sh` | Submit one job, poll until SUCCEEDED/FAILED, print timings |
| `04-teardown.sh` | Disable + delete queue, CE, SG (leave IAM roles for reuse) |
| `run.sh` | `01` + `02` + `03` end-to-end |

## Run

```bash
source ../common/activate.sh
./run.sh
# ... wait ...
./04-teardown.sh
```
