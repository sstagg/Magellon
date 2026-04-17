# MotionCor Plugin — Docker Smoke Test

End-to-end test for the MotionCor plugin. Two complementary paths:

| Path | Script | Verifies | GPU? |
|---|---|---|---|
| **Local-wiring** | `smoke_test_docker.py` | RMQ in/out + step events + output-file shape | No (mocks the binary) |
| **RunPod GPU** | `runpod_gpu_test.py` | Real MotionCor2 produces correct output on actual movies | Yes (rented) |

Run the local-wiring test on every change. Run the RunPod test before
shipping a release or when changing the MotionCor command builder.

## Why two scripts

The real MotionCor2 binary needs CUDA, ~32 GB RAM, and ~20-60 s per movie.
A dev laptop can't run it. But ~95% of what we want to verify is *wiring*
(does the plugin correctly consume from RMQ, write the right files in the
right place, emit step events, publish a result?) — and that doesn't need
a real GPU. The local test mocks the binary with a bash stub that writes
the expected output-file shape, so we get fast feedback on the plugin
itself. Real-GPU validation runs less often via RunPod.

---

## 1. Local-wiring smoke test (mocked GPU)

### Prerequisites

| Requirement | Details |
|---|---|
| Docker Desktop | Running, with the `docker_magellon-network` bridge |
| RabbitMQ | `magellon-rabbitmq-container` on the magellon network |
| Movies (auto-seeded) | Any TIF/MRC under `C:/temp/motioncor/Magellon-test/example*` |
| Python | 3.10+ with `pika` installed (`pip install pika`) |
| SDK wheel | `magellon_sdk-1.1.0-py3-none-any.whl` in the plugin root |

The script auto-seeds test data from `C:/temp/motioncor/Magellon-test/example*`
into `C:/temp/magellon/gpfs/motioncor_test/` on first run. Set `SKIP_SEED=1`
if you've curated that directory by hand.

### Building the SDK wheel

If the wheel doesn't exist yet:

```bash
cd magellon-sdk
pip install build
python -m build --wheel
cp dist/magellon_sdk-1.1.0-py3-none-any.whl ../plugins/magellon_motioncor_plugin/
```

### Run it

```bash
python plugins/magellon_motioncor_plugin/tests/smoke_test_docker.py
```

Skip the Docker build if the test image already exists:

```bash
SKIP_BUILD=1 python plugins/magellon_motioncor_plugin/tests/smoke_test_docker.py
```

The script will:
1. Auto-seed test data from `C:/temp/motioncor/Magellon-test/`
2. Run preflight checks (movies, gain reference, Docker network, RMQ, SDK wheel)
3. Build `magellon-motioncor-plugin:test` from `Dockerfile.test`
4. Purge `motioncor_tasks_queue` and `motioncor_out_tasks_queue`
5. Start step-event + result collectors on background threads
6. Start the container on `docker_magellon-network`
7. Publish `NUM_TASKS` MotionCor TaskDto messages
8. Wait for output dirs (named by `image_id`) to contain `_DW.mrc` (timeout 180s)
9. Verify each task wrote `_DW.mrc` + aligned MRC + 3 patch logs
10. Verify `started` + `completed`/`failed` step events per task on `magellon.events`
11. Verify at least one TaskResultDto reached `motioncor_out_tasks_queue`
12. Check container logs for errors and clean up

### What is verified

| Check | Source | Required |
|---|---|---|
| Output dir per task (named by `image_id`) | Host filesystem | Yes |
| `_DW.mrc` exists, > 256 bytes | Host filesystem | Yes |
| Aligned `.mrc` exists | Host filesystem | Yes |
| 3 patch logs (with PatchesX/Y > 1) | Host filesystem | Yes |
| `started` step event per task | `magellon.events` (`magellon.job.*.step.motioncor`) | Yes |
| `completed`/`failed` step event per task | `magellon.events` | Yes |
| At least one `TaskResultDto` from our tasks | `motioncor_out_tasks_queue` | Yes |
| No errors in container logs | `docker logs` | Warning only |

### Why output dirs are named by `image_id`, not `task_id`

Quirk of `motioncor_service.py`: it uses `image_id` for the per-task
output directory (CTF uses `task_id`). The smoke test's `image_ids` list
is what you grep for under `JOBS_ROOT/`.

### Note on result messages vs step events

Step events go through the **topic exchange** `magellon.events` — every
bound queue gets its own copy, so the smoke test always sees all of them.

The result queue `motioncor_out_tasks_queue` is **point-to-point**. If
CoreService's `result_consumer` is running it will round-robin against
the smoke test's collector and we'll only see a fraction. The script
treats partial result-queue coverage as a pass (step events already
prove the per-task lifecycle).

### Environment overrides

| Variable | Default | Description |
|---|---|---|
| `GPFS_ROOT` | `C:/temp/magellon/gpfs` | Host path to gpfs mount |
| `JOBS_ROOT` | `C:/temp/magellon/jobs/motioncor_test` | Host path for job output |
| `RMQ_HOST` | `127.0.0.1` | RabbitMQ host (from host machine) |
| `RMQ_PORT` | `5672` | RabbitMQ port |
| `RMQ_USER` | `rabbit` | RabbitMQ username |
| `RMQ_PASS` | `behd1d2` | RabbitMQ password |
| `DOCKER_NETWORK` | `docker_magellon-network` | Docker network name |
| `NUM_TASKS` | `5` | How many tasks to dispatch |
| `SKIP_BUILD` | _(empty)_ | Set to `1` to skip image build |
| `SKIP_SEED` | _(empty)_ | Set to `1` to skip auto-seeding |

---

## 2. Manual local test (no smoke-test wrapper)

### Build the test image

```bash
cd plugins/magellon_motioncor_plugin
docker build -f Dockerfile.test -t magellon-motioncor-plugin:test .
```

### Run the container

```bash
docker run -d --name magellon-motioncor-test \
  --network docker_magellon-network \
  -v C:/temp/magellon/gpfs:/gpfs \
  -v C:/temp/magellon/jobs/motioncor_test:/jobs \
  magellon-motioncor-plugin:test
```

### Dispatch tasks

```bash
python CoreService/scripts/dispatch_motioncor_test.py
```

Movies are auto-discovered from `C:/temp/magellon/gpfs/motioncor_test/`.
Override with `MOVIE_HOST_DIR` / `MOVIE_DIR` / `NUM_TASKS`.

### Watch logs

```bash
docker logs -f magellon-motioncor-test
```

### Check output

Each task creates a directory at
`C:/temp/magellon/jobs/motioncor_test/<image_id>/` containing:

| File | Description |
|---|---|
| `<stem>_aligned.mrc` | Motion-corrected micrograph |
| `<stem>_aligned_DW.mrc` | Dose-weighted variant |
| `<stem>-patch-Patch.log` | Per-patch shifts |
| `<stem>-patch-Full.log` | Full-frame integrated shifts |
| `<stem>-patch-Frame.log` | Per-frame shifts |

### Cleanup

```bash
docker rm -f magellon-motioncor-test
```

---

## 3. RunPod GPU validation

The local-wiring test can't catch problems in the real MotionCor2 command
or argument formatting because the mock accepts everything. For that we
rent a GPU on RunPod and run the actual binary on one of our example
movies.

### Prerequisites

- RunPod account with credit and an API key
- API key in `RUNPOD_API_KEY` environment variable
- One example movie under `C:/temp/motioncor/Magellon-test/example1/` (or set `EXAMPLE_DIR`)
- `MotionCor2_1.6.4_Cuda121_Mar312023` binary in the plugin root (already vendored)

### Run it

```bash
RUNPOD_API_KEY=rpa_xxx python plugins/magellon_motioncor_plugin/tests/runpod_gpu_test.py
```

The script will:
1. Verify API key + binary + example movie are present
2. Find the cheapest available CUDA-12 GPU (RTX 4000 Ada / A4000 / L4)
3. Spin up a pod with `runpod/pytorch:2.1.0-py3.10-cuda12.1.1-devel-ubuntu22.04`
4. Wait for SSH to be reachable (max 3 minutes)
5. SCP the MotionCor2 binary + one TIF + the gain reference to the pod
6. Run MotionCor2 with the same flags the plugin uses
7. SCP the output MRC + DW + logs back
8. Compare runtime against `motioncor2_benchmark_results.txt`
9. Tear down the pod (always — even on failure)

### Why a 3-minute ceiling on RunPod calls

RunPod can be flaky (pod stuck in `STARTING`, marketplace empty for a
GPU type, image pull stalls). If we exceed 3 minutes on any single
RunPod operation, the script bails and tells you to investigate
manually. This stops a runaway test from burning credit on a stuck pod.

### Cost expectations

A single end-to-end run is ~5 minutes wall-clock on a $0.20-$0.40/hr
GPU = a few cents. The script always tears down the pod in `finally:`
so a crash doesn't leave one running.

---

## Dockerfile.test notes

Differences vs the production `Dockerfile`:

- Ubuntu 22.04 + Python 3.11, **no CUDA layer** (production needs CUDA
  for the real binary; this image runs on any host)
- Bakes in `tests/mock_motioncor` and sets `MOTIONCOR_BINARY=/app/mock_motioncor`
- `MAGELLON_SETTINGS_FILE=/app/configs/settings_docker_test.yml` baked in
  (Docker Desktop on Windows mangles Unix paths passed via `-e`)
- `MAGELLON_STEP_EVENTS_ENABLED=1` + `MAGELLON_STEP_EVENTS_RMQ=1` so the
  smoke test can subscribe to `magellon.events` and verify lifecycle
- No CUDA = build is fast (~2 minutes), image is small (~1.5 GB)
