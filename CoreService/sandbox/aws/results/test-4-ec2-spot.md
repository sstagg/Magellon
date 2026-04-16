# Test 4 — EC2 spot baseline (g4dn.2xlarge)

## Outcome
SUCCEEDED. Raw EC2 spot instance, no Batch, no queue. Launches via `ec2 run-instances` with user-data that installs AWS CLI, configures CloudWatch agent, pulls ECR image, runs MC2 in container, uploads to S3, then `shutdown -h now` to terminate.

## Timings (first attempt, cold launch)
| Phase | Seconds |
| --- | --- |
| `run-instances` → `running` | ~15 |
| user-data boot (cloud-init + pkg install) | ~60 |
| docker pull (ECR) | 64 |
| S3 download (528 MB) | 3.5 |
| MC2 (same args as Test 1) | 35.0 |
| S3 upload (256 MB) | 2.7 |
| shutdown trap sleep (buffer) | 30 |
| **`running` → `shutting-down`** | **190** |

MC2 internal timing matches Test 1 exactly: Total 32.9s, Computation 17.9s.

## Bug caught & fixed
First launch (`i-02b0a10aceb55c1cc`) stuck running forever. Root cause: AL2 ECS-GPU AMI ships **without** AWS CLI (same gotcha as Test 1's diag script). The user-data hit `aws ecr get-login-password` → `command not found` → cloud-init aborted → `shutdown` at end of script never reached. Fixed by:
1. Install AWS CLI v2 in user-data (`curl awscliv2.zip && unzip && ./aws/install`)
2. Drop `-e` from `set -euxo pipefail` so non-critical failures don't abort
3. Add `trap 'sleep 30; shutdown -h now' EXIT` so termination is guaranteed even if MC2 / docker / network fails

## AWS resources
- SG: `magellon-gpu-eval-ec2-spot-sg` (egress-only)
- IAM instance profile: `magellon-gpu-eval-batch-instance-role` (reused from Test 1; has ECR/S3/logs permissions)
- Log group: `/aws/ec2/magellon-gpu-eval-baseline`
- Output: `s3://magellon-gpu-eval-work/test-4-ec2-spot/ec2spot-20260416-113638/`

## Cost (spot pricing us-east-1, 2026-04-16)
- g4dn.2xlarge spot: ~$0.226/hr = $0.0000628/s
- Billable time (running → terminated): ~190s = **$0.0119 / movie**
- If script is trimmed (remove 30s shutdown buffer, pre-bake AMI with CLI+image): could drop to ~100s = $0.006/movie

## vs. Test 1 (Batch)
Wall-clock almost identical on cold start — Test 1 is 200s, Test 4 is 190s — because both fundamentally provision a g4dn.2xlarge spot instance and pull the image. The key difference is **operational**:
- Test 1 (Batch): queue-managed, concurrency, automatic retry, desiredvCpus=0 → $0 when idle. ~$0.007/movie warm.
- Test 4 (EC2 spot): raw — you wrote the plumbing. One instance = one movie. No scaling beyond that. ~$0.012/movie cold each time.

Batch wins when there are multiple movies in flight or a persistent workload. Raw EC2 wins when scripting something one-off or needing full control of user-data.
