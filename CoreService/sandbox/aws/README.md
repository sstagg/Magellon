# AWS GPU Serverless Evaluation — Magellon

Evaluating AWS GPU services for the MotionCor plugin, with a complete upload → process → download pipeline. All resources tagged `Project=magellon-gpu-eval` so costs are attributable.

## Account context

- **Account**: 789438509093 (FSU, SSO admin)
- **Region**: us-east-1 (us-east-2 is blocked by an FSU org SCP)
- **Creds**: SSO temporary (ASIA...). Put in `.env` locally — **never commit**
- **Quotas**: us-east-1 has 768 vCPU G-family on-demand, 64 vCPU G-family spot — plenty for testing

## What we're testing

| # | Service | Why | Est. cost / single 500MB movie |
|---|---|---|---|
| 1 | AWS Batch + spot g4dn.xlarge | Batch workload, cheapest | ~$0.05 |
| 2 | SageMaker Async Inference | Endpoint-style, scale-to-zero | ~$0.20 |
| 3 | SageMaker Processing Job | One-shot job | ~$0.15 |
| 4 | EC2 spot baseline | Cost floor — raw GPU pricing | ~$0.02 |
| + | Upload pipeline (Lambda + S3 presigned URLs) | Feeds all of the above | ~$0.01 |

## Layout

```
common/                    Shared config, IAM, budget, ECR push, start/stop
image/                     Shared GPU container (motioncor2 + S3 wrapper)
upload-pipeline/           Presigned-URL S3 upload + trigger Lambda
test-1-batch-gpu/          AWS Batch test
test-2-sagemaker-async/    SageMaker Async Inference test
test-3-sagemaker-processing/   SageMaker Processing Job test
test-4-ec2-spot/           Raw EC2 spot baseline
results/                   pricing-comparison.md + timings.csv
```

## Quickstart

```bash
# 1. Set creds in .env (copy from .env.example) — never commit
cp .env.example .env
vim .env

# 2. Activate env in every shell
source common/activate.sh

# 3. One-time setup (IAM roles, budget, ECR repo, push image)
common/00-setup-iam.sh
common/01-setup-budget.sh
common/02-push-image.sh

# 4. Run tests (each is fully torn down at the end)
test-1-batch-gpu/run.sh

# 5. Audit: what's alive, what did it cost?
common/tag-audit.sh
```

## Cost controls

- **AWS Budget $50/mo** filtered to `Project=magellon-gpu-eval` with 50/80/100% email alerts to b.khoshbin@gmail.com
- **Every resource tagged** `Project`, `Owner`, `CostCenter` (see `common/config.sh`)
- **All teardown scripts** idempotent — safe to re-run
- **Cost tags must be activated manually** once in the billing console (payer account only). See `common/enable-cost-tags.md`

## `magellon-gpu-server` (separate g4dn)

Pre-existing instance `i-059b91233e481b50a`, **stopped 2026-04-16** after observing <10% CPU avg over 30 days.
- EIP `34.235.206.46` persists across stop/start
- Start / stop: `common/start-gpu-server.sh` / `common/stop-gpu-server.sh`
- Stopped cost ~$12/mo (EBS + idle EIP) vs $384/mo running. Saves ~$372/mo.

## Results

See `results/pricing-comparison.md` (populated after test runs).
