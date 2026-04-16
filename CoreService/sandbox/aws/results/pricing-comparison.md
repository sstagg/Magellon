# Pricing Comparison — Magellon MotionCor2 on AWS

Actual cost + runtime measurements for each service tested, against the same input:
`s3://motioncortest/Magellon-test/Magellon-test/example1/20241203_54530_integrated_movie.mrc.tif`
(528 MB TIFF → 256 MB corrected .mrc), using single T4 GPU.

**Key finding upfront:** MC2 on this movie requires **g4dn.2xlarge (32 GB host RAM)**, not g4dn.xlarge (16 GB). MC2 pins ~11 GB of CUDA host memory, plus ~4 GB heap, which exceeds xlarge's host and triggers kernel OOM — invisibly (stdout/stderr are empty because glibc full-buffers through SIGKILL). See `test-1-batch-gpu.md` for dmesg evidence. All tests below therefore run on `g4dn.2xlarge` / `ml.g4dn.2xlarge`.

## Reference pricing (us-east-1, 2026-04-16)

| Resource | On-demand | Spot (typical) |
|---|---|---|
| `g4dn.xlarge` raw EC2 | $0.526/hr | ~$0.158/hr (~70% off) |
| `g4dn.2xlarge` raw EC2 | $0.752/hr | **~$0.226/hr** (~70% off) |
| `ml.g4dn.2xlarge` (SageMaker Processing) | **$1.0515/hr** | n/a |
| `ml.g4dn.2xlarge` (SM Async endpoint) | **$1.0515/hr** | n/a |
| EBS gp3 (40 GB root) | $0.08/GB-month | prorated (~$0.11/day/vol) |
| S3 PUT + storage | $5/M req + $0.023/GB-mo | — |

SageMaker's `ml.g4dn.2xlarge` is **+40%** over raw `g4dn.2xlarge`. No spot for Processing or Async. That's the cost of "managed".

## Measured results

All four tests ran the exact same MC2 args: `-Patch 5 5 -Iter 10 -Tol 0.5 -Gpu 0 -FtBin 1 -kV 300`. Internal MC2 wall time was ~33 s in all four. The differences below are entirely in **cold-start / provisioning / billing semantics.**

| # | Service | Status | Provision (s) | MC2 (s) | Total wall (s) | Billable (s) | Cost/movie | Scale-to-0 |
|---|---|---|---|---|---|---|---|---|
| 1 | AWS Batch (spot g4dn.2xlarge) | ✅ | 160 | 33 | 200 | 112 | **$0.007** | Yes (desired=0) |
| 2 | SageMaker Async (ml.g4dn.2xl) | ✅ | 128 | 33 | 52 invoke / 250 end-to-end | 250 first / 52 warm | **$0.073** one-off, **$0.015** warm-invoke | Yes (min=0, 2-min wake-up) |
| 3 | SageMaker Processing (ml.g4dn.2xl) | ✅ | 43 | 33 | 303 | 115 | **$0.034** | Yes (ephemeral) |
| 4 | EC2 spot (g4dn.2xlarge, raw) | ✅ | ~15 | 33 | 190 | 190 | **$0.012** | No (you manage) |

### Details

**Test 1 — AWS Batch spot.** Fastest per-movie on a warm queue (RUNNABLE→RUNNING ~1 s) at ~$0.007 each. Cold start pays 2-3 min for spot-fleet acquire + ECS register + image pull. Queue's `desiredvCpus=0` drives $0 idle.

**Test 3 — SageMaker Processing.** Per-job ephemeral container, provisioned by SM. Cheapest code-plumbing wise (S3 mount and upload are free SM features), but no spot → ~5× Batch cost. Good for fits-and-starts workloads where ops simplicity matters more than $0.03 per movie.

**Test 4 — EC2 spot baseline.** Minimum cost floor when you run-once. Slightly cheaper wall-clock than Batch on a cold start (raw EC2 skips Batch's ECS-register step), but no queue, no retries, no built-in concurrency. Pay full 190 s (includes 30 s shutdown buffer). Billable can be trimmed to ~100 s by pre-baking an AMI with Docker image + AWS CLI.

**Test 2 — SageMaker Async endpoint.** Scale-to-zero inference endpoint with managed queuing. Endpoint deploy: 128 s. Warm invoke: 52 s end-to-end (MC2 ~33 s + ~10 s queuing + ~3 s S3 download + ~3 s S3 upload + overhead). One-off test cost: $0.073 (the deploy dominates). Steady-state warm-invoke cost: $0.015/request. Scale-from-zero pays another ~128 s deploy the next time idle → warm. **Only tested service with true concurrent/queued invocations** — the others are one-shot per container.

## Conclusions

1. **For batched / throughput workloads (many movies): AWS Batch spot wins** — ~$0.007/movie amortized over a warm queue. Scales out trivially by changing `maxvCpus`.

2. **For single one-offs or ad-hoc runs: raw EC2 spot is cheapest cold-start** ~$0.012/movie. The operational overhead (SG, user-data, shutdown trap) is small — see `test-4-ec2-spot/launch-and-run.sh` — and we already validated the pattern.

3. **For ops-simplicity with bearable cost premium: SageMaker Processing** — $0.034/movie, zero infra management, inherits SM's native S3 I/O and lineage tracking. If a future Magellon pipeline runs hundreds of movies/day this would be cost-prohibitive (~$50-100/day), but for exploratory runs or demos it's the "no surprises" choice.

4. **For interactive / near-real-time queries: SageMaker Async** — if the UI needs to kick off MC2 in response to user upload and the latency budget is "a few minutes, not half an hour", this is the only option of the four that supports concurrent warm invocations. Idle cost is $0 via scale-to-zero.

5. **Host RAM sizing is NON-OBVIOUS and universal across all four services.** g4dn.xlarge is a trap — MC2 silently SIGKILLs because pinned CUDA shmem exceeds 16 GB. Default to g4dn.2xlarge ($0.226/hr spot).

## Caveats

- All numbers measured on a **single** 528 MB movie. Larger TIFFs may push shmem past 2xlarge's 32 GB → may need g4dn.4xlarge (64 GB host).
- Spot pricing varies — in our test window spot g4dn.2xlarge was $0.226/hr. During capacity crunches it can approach on-demand.
- Cost Explorer tagged cost data lags by ~24 h. Cross-check totals against CE filtered by `Project=magellon-gpu-eval` after that.

## Sources

- EC2: https://aws.amazon.com/ec2/instance-types/g4/
- SageMaker: https://aws.amazon.com/sagemaker/pricing/
- Detailed per-test notes: `test-1-batch-gpu.md`, `test-3-sagemaker-processing.md`, `test-4-ec2-spot.md`
