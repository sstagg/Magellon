# Test 4 — EC2 Spot Baseline (g4dn.xlarge)

Directly launches a spot `g4dn.xlarge`, runs our container via user data, terminates itself. This is the **cost floor** — nothing on top of raw EC2 pricing.

## Why run this test

To prove what the managed services (Batch, SageMaker) charge in overhead beyond raw GPU time. If Batch spot costs match raw spot, Batch adds no markup. If SageMaker Processing costs 40% more than raw EC2, that's the markup.

## Method

1. Launch spot g4dn.xlarge using ECS-optimized GPU AMI (has NVIDIA drivers + Docker pre-installed)
2. User data: login to ECR, pull image, run container with env vars, `shutdown -h now`
3. `--instance-initiated-shutdown-behavior terminate` kills the instance (and spot request) on shutdown
4. After termination, inspect CloudWatch + Spot pricing history for actual $ spent

## Expected

- Spot price for g4dn.xlarge us-east-1: ~$0.158/hr (~70% off $0.526 on-demand)
- Boot + pull + run ≈ 3-4 min provisioning + 5 min MotionCor = ~9 min total
- Cost: ~9 min × $0.158/hr = **~$0.024**

## Files

| File | Purpose |
|---|---|
| `launch-and-run.sh` | One-shot: request spot, wait for termination, report cost |
| `teardown.sh` | Cleans up any orphan spot requests + SG |

## Run

```bash
source ../common/activate.sh
./launch-and-run.sh
```
