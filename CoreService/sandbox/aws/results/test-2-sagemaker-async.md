# Test 2 — SageMaker Async Inference (ml.g4dn.2xlarge)

## Outcome
SUCCEEDED. Same 528 MB movie → 256 MB corrected.mrc, served via a persistent SM Async endpoint with scale-to-zero autoscaling.

## Architecture (distinct from other tests)
This is the **only** tested service that keeps a persistent endpoint — separate FastAPI server (`server.py`) wrapping `run_motioncor.py`'s helpers, deployed in a SM-compatible container (serves `/ping` and `/invocations` on port 8080). Endpoint accepts S3-located JSON payloads, returns output JSON to a different S3 location. Autoscaling policy targets `ApproximateBacklogSizePerInstance=5`, min=0, max=2.

## Timings (first invocation, warm endpoint)
| Phase | Seconds |
| --- | --- |
| Build + push SM-compatible image to ECR | ~20 (done once) |
| `create_endpoint` → InService | 128 |
| Payload upload to S3 | <1 |
| `invoke_endpoint_async` → result ready in S3 | 52.5 |
| - Container processing (download + MC2 + upload) | 41.99 |
| - SM Async queuing + HTTP overhead | ~10.5 |
| Teardown (deregister scaling, delete endpoint, config, model) | ~15 |

MC2 internal: ~33 s (as in all tests). Download/upload: ~3 s + 2.5 s. Everything above that is FastAPI/uvicorn + SM orchestration.

## Cost
- ml.g4dn.2xlarge on-demand: $1.0515/hr = $0.000292/s
- While InService: ~250 s for this test (deploy 128s + invoke-and-result 52s + teardown draining ~70s)
- **One-off cost: ~$0.073** (mostly the 2-min deploy and scale-down grace period, not the invoke itself)
- **Steady-state** (warm endpoint already InService, just invoke): 52 s × $0.000292 = **$0.015 per invocation** while scaled up
- Scale-to-zero cost: $0 during idle periods. But **scale-from-zero pays another full endpoint deploy (~2 min)** on the next invoke = another ~$0.04 cold-start tax each wake-up

## AWS resources (all teardowned)
- ECR repo: `magellon-gpu-eval/motioncor-sm-async` (image retained for future use — reusable for redeploy)
- Model: `magellon-gpu-eval-async-model` ❌ deleted
- EndpointConfig: `magellon-gpu-eval-async-config` ❌ deleted
- Endpoint: `magellon-gpu-eval-async-ep` ❌ deleted
- Autoscaling target: deregistered ❌
- Output: `s3://magellon-gpu-eval-work/test-2-sm-async/results/async-20260416-115838/` (retained)

## When this shines vs. others
- **Only** option that handles **concurrent requests** on a warm instance (queueing built-in via SM Async; other tests are one-shot)
- **Only** option with sub-second invoke latency from an already-warm endpoint
- Pays per-second while InService — if you cluster invocations in time, per-request cost drops toward zero
- Scale-to-zero + cold-start: ~$0.04 wake-up tax + 2-min first-invoke latency

## When other services win
- Batch is ~2× cheaper for throughput (~$0.007/movie spot) — no managed-endpoint markup
- Processing is simpler code (no FastAPI layer) at $0.034/movie — better for nightly cron jobs
- EC2 raw spot is cheapest cold-start one-off

## Gotchas hit during Test 2
- `01-build-push.sh` failed on Windows git-bash: Docker read `.` as empty context (2 B Dockerfile transfer). Fixed by adding explicit `-f ./Dockerfile`. Added to the script.
