# Test 2 — SageMaker Asynchronous Inference

Deploys the motioncor logic as a SageMaker Async Inference endpoint with scale-to-zero. Clients submit work via `InvokeEndpointAsync`, SM queues, cold-starts a `ml.g4dn.xlarge` if needed, runs inference, writes output to S3.

## Why this vs. Batch

| Property | Batch | SageMaker Async |
|---|---|---|
| Spot support | ✓ | ✗ |
| Scale-to-zero | ✓ | ✓ (via app-autoscaling, 10-min cooldown default) |
| Cold start | ~2-4 min (spot) | ~2-5 min (first req after idle) |
| Warm start | n/a | ~seconds |
| Instance markup | 0% | +40% (`ml.g4dn.xlarge`) |
| Built-in queue | ✗ (you add SQS) | ✓ (managed) |
| Concurrency limits | ✓ | ✓ + auto-scaling rules |
| Good fit for | Dense pipelines | Interactive/bursty workloads |

**Tradeoff:** If requests cluster (10 movies in a row), Async is cheaper than Batch (one warm instance vs. N cold starts). If requests are spaced out, Batch wins (spot discount + no markup).

## Request contract

POST body `/invocations`:
```json
{"input_s3":"s3://bucket/key.tif", "output_prefix_s3":"s3://bucket/prefix/", "job_id":"optional"}
```

Response:
```json
{"status":"ok", "outputs":["s3://bucket/prefix/<job_id>/corrected.mrc", ...], "seconds":123.4}
```

## Files

| File | Purpose |
|---|---|
| `Dockerfile` | Adds FastAPI + uvicorn on top of `magellon-gpu-eval/motioncor:latest` |
| `server.py` | `/ping` + `/invocations` handlers |
| `01-build-push.sh` | Build SM-compatible image, push to ECR (`motioncor-sm-async` repo) |
| `02-deploy.py` | Create Model + EndpointConfig + Endpoint + app-autoscaling to zero |
| `03-invoke.py` | Fire an `InvokeEndpointAsync`, wait for result, print timings |
| `04-teardown.py` | Tear down endpoint + autoscaling target + config + model |

## Run

```bash
source ../common/activate.sh
./01-build-push.sh
python3 02-deploy.py
python3 03-invoke.py
python3 04-teardown.py  # don't forget — endpoint keeps billing if left alive
```

## Cost caveats

- **First-request cold start** hits a full instance boot + image pull + container ready (~5 min)
- **Scale-to-zero cooldown** default 600s — you pay for those idle 10 minutes after a request
- If you invoke sparsely (once/hour), you pay: 1 warm req ≈ run time; 9 idle 10-min cooldowns ≈ 1.5 hr = ~$1.10/hr × markup

**Best fit:** dense workloads. Sparse → Batch.
