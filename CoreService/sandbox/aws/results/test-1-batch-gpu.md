# Test 1 — AWS Batch + GPU spot (g4dn.2xlarge)

## Outcome
SUCCEEDED. Input `20241203_54530_integrated_movie.mrc.tif` (528 MB) → `*.mrc` (256 MB).

## Instance sizing — why not g4dn.xlarge
The initial plan used `g4dn.xlarge` (16 GB host RAM, 1× T4). All attempts failed at ~10–25 s with MC2 killed by SIGKILL (-9). Investigation via `test-1-batch-gpu/ec2-diag.sh` (captures host `dmesg`) showed the kernel OOM killer firing on the container:

```
Out of memory: Killed process <pid> MotionCor2 ...
total-vm:40309036kB, anon-rss:3922528kB, file-rss:74240kB, shmem-rss:11285152kB
```

MC2 pins ~11 GB of CUDA host memory (`cudaHostAlloc` — accounted as shmem-rss). Plus heap (~4 GB) the process is ~15.3 GB RSS. That leaves no headroom on a 16 GB host for anything else (kernel, Docker, ECS agent, CW agent). Linux OOM-kills MC2 as the largest process.

Tested mitigations on g4dn.xlarge, all failed:
- `-GpuMemUsage 0.5` — cgroup-OOM at 9.6 s
- `-GpuMemUsage 0.3` — kernel-OOM at 23.6 s (longer because pinned-alloc is slower)

**Fix: g4dn.2xlarge (32 GB host).** MC2 ran to completion in ~33 s with default `-GpuMemUsage 0.75`.

## Timings (g4dn.2xlarge, spot, cold start)
| Phase | Seconds |
| --- | --- |
| SUBMITTED → RUNNABLE | ~10 |
| RUNNABLE → STARTING (spot-fleet acquire + ECS register + image pull init) | 80 |
| STARTING → RUNNING (image pull + container init) | 80 |
| S3 download (528 MB) | 3.4 |
| MC2 `-Patch 5 5 -Iter 10 -Tol 0.5 -FtBin 1 -kV 300 -Gpu 0` | 35.0 |
| S3 upload (256 MB) | 2.5 |
| RUNNING → SUCCEEDED | 32 |
| **Total wall clock** | **~200 s (~3m20s)** |
| **Billable compute (STARTING→SUCCEEDED)** | **~112 s** |

Second+ jobs on a warm instance: RUNNABLE→RUNNING ~1 s, saving the ~160 s cold-start.

## MC2 output excerpt
```
Patch alignment time: 1.02(sec)
Correction of local motion: 4.446824 sec
Computation time: 18.147141 sec
Total time: 32.747818 sec
```

## AWS resources created
- Compute env: `magellon-gpu-eval-ce-spot-g4dn2xl` (SPOT g4dn.2xlarge, 0–8 vCPU, ECS-GPU AMI)
- Job queue: `magellon-gpu-eval-queue-2xl`
- Job definition: `magellon-gpu-eval-motioncor` (unchanged — resourceRequirements set per-job)
- S3 work prefix: `s3://magellon-gpu-eval-work/test-1-batch/`
- Log group: `/aws/batch/job`

## Cost (spot pricing us-east-1, as of 2026-04-16)
- g4dn.2xlarge spot: ~$0.226/hr
- One job ≈ 112 s billable ≈ **$0.007 / movie** on a warm queue
- Cold start adds ~160 s = another ~$0.010 on a cold queue
- Typical throughput batch-of-N on warm queue: ~$0.007/movie

## Key findings
1. `g4dn.xlarge` is insufficient for MC2 on 528 MB single-frame TIFFs. Go direct to **g4dn.2xlarge** for this workload; only revisit xlarge if a future MC2 version reduces pinned memory.
2. The MC2 `-9` crash is invisible from the container side (empty stdout/stderr because glibc full-buffers file I/O and SIGKILL discards the buffer). `dmesg -T` on the host is the only source of truth for OOM diagnosis.
3. Spot acquisition in us-east-1 for g4dn.2xlarge: ~80 s consistently. No interruptions seen in this test run.
4. Keep compute env `minvCpus=0, desiredvCpus=0` so costs drop to $0 between runs.
