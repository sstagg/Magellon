# CTF Plugin — Docker Ground-Truth Test

End-to-end test that builds the CTF plugin Docker image, dispatches
10 real MRC micrographs through RabbitMQ, runs ctffind4 inside the
container, and verifies the output files and defocus estimates.

## Prerequisites

| Requirement | Details |
|---|---|
| Docker Desktop | Running, with the `docker_magellon-network` bridge |
| RabbitMQ | `magellon-rabbitmq-container` on the magellon network |
| MySQL | `magellon-mysql_container` on the magellon network |
| MRC test data | 10 files in `C:/temp/magellon/gpfs/ctf_test/` |
| Python | 3.10+ with `pika` installed (`pip install pika`) |
| SDK wheel | `magellon_sdk-0.1.0-py3-none-any.whl` in the plugin root |

### MRC test files

Copy the 10 ground-truth micrographs into `C:/temp/magellon/gpfs/ctf_test/`:

```
23oct13x_23oct13a_a_00034gr_00008sq_v02_00017hl_00003ex.mrc
24dec03a_00034gr_00004sq_v01_00003hl_00016ex.mrc
24dec03a_00034gr_00005sq_v01_00003hl_00014ex.mrc
24dec03a_00034gr_00004sq_v01_00002hl_00003ex.mrc
24dec03a_00034gr_00004sq_v01_00002hl_00004ex.mrc
24dec03a_00034gr_00004sq_v01_00002hl_00005ex.mrc
24dec03a_00034gr_00004sq_v01_00002hl_00006ex.mrc
24dec03a_00034gr_00004sq_v01_00002hl_00007ex.mrc
24dec03a_00034gr_00004sq_v01_00002hl_00008ex.mrc
24dec03a_00034gr_00004sq_v01_00002hl_00009ex.mrc
```

### Building the SDK wheel

If the wheel doesn't exist yet:

```bash
cd magellon-sdk
pip install build
python -m build --wheel
cp dist/magellon_sdk-0.1.0-py3-none-any.whl ../plugins/magellon_ctf_plugin/
```

## Automated test

Run the full smoke test (build + dispatch + verify):

```bash
python plugins/magellon_ctf_plugin/tests/smoke_test_docker.py
```

Skip the Docker build if the image already exists:

```bash
SKIP_BUILD=1 python plugins/magellon_ctf_plugin/tests/smoke_test_docker.py
```

The script will:
1. Check prerequisites (MRC files, Docker network, RabbitMQ)
2. Build the `magellon-ctf-plugin:test` image from `Dockerfile.test`
3. Purge leftover messages from `ctf_tasks_queue` and `ctf_out_tasks_queue`
4. Start background RabbitMQ collectors for step events and result messages
5. Start a container on `docker_magellon-network`
6. Publish 10 CTF TaskDto messages to `ctf_tasks_queue`
7. Wait for all 10 output directories to appear (timeout: 180s)
8. Verify each task produced 5 files with valid defocus estimates
9. Verify step events: `started` + `completed` per task on `magellon.events` exchange
10. Verify result messages: `TaskResultDto` per task on `ctf_out_tasks_queue`
11. Check container logs for errors
12. Clean up the container

Exit code 0 = all passed, non-zero = failure.

### What is verified

| Check | Source | Required |
|---|---|---|
| Output files (5 per task) | Host filesystem | Yes |
| Defocus estimates in range | `*_ctf_output.txt` | Yes |
| File sizes > 1 KB | MRC, PNG, JPG | Yes |
| `started` step event per task | `magellon.events` exchange (`magellon.job.*.step.ctf`) | Yes |
| `completed` step event per task | `magellon.events` exchange | Yes |
| At least one `TaskResultDto` from our tasks | `ctf_out_tasks_queue` | Yes |
| `progress` step events | `magellon.events` exchange | No (CTF is single-step) |
| No errors in container logs | `docker logs` | Warning only |

### Note on result messages vs step events

Step events use a **topic exchange** (`magellon.events`) — every bound queue gets its
own copy of each event, so the smoke test's exclusive queue always sees all 10.

Result messages are published directly to the **point-to-point queue** `ctf_out_tasks_queue`.
If the CoreService `result_consumer` is running, RMQ round-robins between it and the smoke
test's collector, so we see only ~half the results. The smoke test treats this as
expected — step events already provide authoritative per-task lifecycle verification,
and the result-queue check just needs to prove the publish path works at all.

### Environment overrides

| Variable | Default | Description |
|---|---|---|
| `GPFS_ROOT` | `C:/temp/magellon/gpfs` | Host path to gpfs mount |
| `JOBS_ROOT` | `C:/temp/magellon/jobs/ctf_test` | Host path for job output |
| `RMQ_HOST` | `127.0.0.1` | RabbitMQ host (from host machine) |
| `RMQ_PORT` | `5672` | RabbitMQ port |
| `RMQ_USER` | `rabbit` | RabbitMQ username |
| `RMQ_PASS` | `behd1d2` | RabbitMQ password |
| `DOCKER_NETWORK` | `docker_magellon-network` | Docker network name |
| `SKIP_BUILD` | _(empty)_ | Set to `1` to skip image build |

## Manual test

### 1. Build the image

```bash
cd plugins/magellon_ctf_plugin
docker build -f Dockerfile.test -t magellon-ctf-plugin:test .
```

### 2. Run the container

```bash
docker run -d --name magellon-ctf-test \
  --network docker_magellon-network \
  -v C:/temp/magellon/gpfs:/gpfs \
  -v C:/temp/magellon/jobs/ctf_test:/jobs \
  magellon-ctf-plugin:test
```

### 3. Dispatch tasks

```bash
python CoreService/scripts/dispatch_ctf_test.py
```

### 4. Watch logs

```bash
docker logs -f magellon-ctf-test
```

### 5. Check output

Each task creates a directory under `C:/temp/magellon/jobs/ctf_test/<task-id>/`
with 5 files:

| File | Description |
|---|---|
| `*_ctf_output.mrc` | Diagnostic power spectrum (MRC format) |
| `*_ctf_output.mrc-plots.png` | 1D CTF fit plot |
| `*_ctf_output.mrc-powerspec.jpg` | 2D power spectrum image |
| `*_ctf_output.txt` | Defocus parameters (defocus1, defocus2, astigmatism angle, phase shift, CC, resolution) |
| `*_ctf_output_avrot.txt` | Rotational average data |

### 6. Cleanup

```bash
docker rm -f magellon-ctf-test
```

## Dockerfile.test notes

Four fixes/additions vs. the production Dockerfile:

- `DEBIAN_FRONTEND=noninteractive` + `TZ=Etc/UTC` — prevents `tzdata` from hanging the build
- `nats` extra in SDK install — the SDK imports `nats-py` unconditionally
- `MAGELLON_SETTINGS_FILE` baked into the image — Docker Desktop on Windows
  mangles Unix paths passed via `-e`, converting `/app/...` to `C:/git/app/...`
- `MAGELLON_STEP_EVENTS_ENABLED=1` + `MAGELLON_STEP_EVENTS_RMQ=1` — enable
  the step-event publisher's RMQ mirror so the smoke test can subscribe to
  the `magellon.events` exchange and verify lifecycle events
