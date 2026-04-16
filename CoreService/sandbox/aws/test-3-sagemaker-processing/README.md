# Test 3 — SageMaker Processing Job (g4dn.xlarge)

Runs MotionCor2 as a one-shot SageMaker Processing job. SageMaker spins up a container, downloads input from S3, runs the script, uploads outputs, and terminates.

## Why this vs. Batch

| Property | Batch | SageMaker Processing |
|---|---|---|
| Provisioning latency | ~2-4 min (spot) | ~2-3 min (on-demand only) |
| Per-second billing | Yes | Yes |
| Spot support | Yes | **No — on-demand only** |
| S3 data movement | You write code | SageMaker manages automatically |
| Minimum billing unit | 1 second | 1 second |
| Good fit for | Production pipelines | One-off scripts / tutorials |

**Expected cost for one 5-min MotionCor2 run: ~$0.06 (on-demand) vs ~$0.018 (Batch spot). Batch wins on cost.**

## What Processing gives you for free

- `--inputs` S3 URI → mounted at `/opt/ml/processing/input/<channel>/`
- `--outputs` S3 URI → anything the script writes to `/opt/ml/processing/output/<channel>/` gets uploaded
- IAM + logging + auto-cleanup

So the entrypoint is one line: `python3 /app/run_motioncor.py sm-processing`.

## Files

| File | Purpose |
|---|---|
| `run.py`      | Creates Processor, runs job, polls, prints timings + cost |
| `teardown.py` | Deletes the Processing job record (optional — auto-reaped) |

## Run

```bash
source ../common/activate.sh
python3 run.py
```
