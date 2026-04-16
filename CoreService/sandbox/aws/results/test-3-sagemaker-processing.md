# Test 3 — SageMaker Processing Job (ml.g4dn.2xlarge)

## Outcome
SUCCEEDED. Same 528 MB movie → 256 MB corrected.mrc, run as a one-off `ProcessingJob` against our existing motioncor image (added a `sm-processing` mode to `run_motioncor.py` that reads from the fixed SageMaker mount paths `/opt/ml/processing/input/movie` and writes to `/opt/ml/processing/output`).

## Service quota gotcha
By default AWS accounts have **0** for all `ml.g4dn.* for processing job usage` quotas (unlike endpoint usage, which comes with sensible defaults). First submission failed with `ResourceLimitExceeded: account-level service limit 'ml.g4dn.2xlarge for processing job usage' is 0 Instances`. Quota increase request `L-41C11899` to 2 instances was auto-approved within ~30 min (surprisingly fast — the console warns 24-72 h).

## Timings
| Phase | Seconds |
| --- | --- |
| `create_processing_job` → `InProgress` start | — (instant) |
| Provision (instance + image pull) | 42.6 |
| Runtime (S3 mount, MC2, S3 upload via SM contract) | 114.5 |
| **Total (create → Completed)** | **303** |

Note: "Runtime" here includes SM's managed S3 download + upload machinery. MC2 itself is still ~33 s — the rest is SM's batch I/O.

## Cost
- ml.g4dn.2xlarge on-demand: $1.0515/hr (~40% markup over raw EC2 g4dn.2xlarge $0.752/hr; no spot available for Processing)
- One job: 114.5 s billable (provision time is NOT billed — nice) = **$0.0335 / movie**
- Compare:
  - Test 1 (Batch spot): $0.007/movie (~5× cheaper)
  - Test 4 (raw EC2 spot): $0.012/movie (~3× cheaper)
- No scale-to-zero cost — compute disappears after each job, same as Batch.

## AWS resources
- Job definition created on-the-fly (ProcessingJob is ephemeral — no persistent resources)
- IAM role: `magellon-gpu-eval-sagemaker-exec-role` (pre-existing with sagemaker-full + s3 rw)
- Output: `s3://magellon-gpu-eval-work/test-3-sm-processing/magellon-gpu-eval-proc-20260416-114845/20241203_54530_integrated_movie.mrc`

## Operational pros/cons vs. Batch
Pros:
- Zero cluster management (no CE, no queue, no SG)
- S3 I/O handled by SageMaker — `run_binary` just reads from / writes to local paths
- Built-in retries, lineage tracking, model-registry integration
Cons:
- No spot pricing → ~5× more expensive than Batch spot
- Provision time (43 s) not parallelizable — each movie pays it if jobs are spawned individually
- Cold-start latency similar to Batch on a cold queue, but Batch beats it when queue is warm
