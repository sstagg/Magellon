# magellon_fft_plugin

Reference / blueprint plugin for Magellon. Computes a 2D FFT of a
micrograph and writes the magnitude spectrum as a PNG. The plugin is
small on purpose — it exists so plugin authors have a working,
production-shipped example to copy from.

If you're forking this to build a new plugin, **the only directory you
need to edit is `plugin/`**. Everything else (`core/`, `main.py`,
`Dockerfile`, `requirements.txt`, `configs/`) is boilerplate.

---

## Layout

```
magellon_fft_plugin/
├── plugin/                 ← all developer-written code lives here
│   ├── compute.py          # pure algorithm — no SDK awareness
│   ├── plugin.py           # FftPlugin class, FftBrokerRunner, build_fft_result
│   ├── events.py           # step-event binding (step name + RMQ settings)
│   └── __init__.py         # public surface
│
├── core/                   ← boilerplate — copy as-is
│   ├── settings.py         # AppSettings subclass (config singleton)
│   └── helper.py           # queue publish helpers bound to plugin settings
│
├── configs/                ← env-specific YAML (broker URLs, queue names)
│   ├── settings_dev.yml
│   └── settings_prod.yml
│
├── tests/
│   ├── test_fft_plugin.py                     # unit (no broker)
│   └── integration/
│       ├── conftest.py                        # testcontainers RMQ + NATS
│       ├── test_fft_messaging_e2e.py          # in-process plugin
│       └── test_fft_subprocess_e2e.py         # uvicorn subprocess
│
├── main.py                 ← FastAPI host + broker runner startup + /health
├── Dockerfile
├── requirements.txt
└── pytest.ini
```

---

## How a task flows through this plugin

```
CoreService POST /image/fft/batch_dispatch
  → JobManager persists ImageJob + 10 ImageJobTask rows
    → backend publishes 10 TaskDtos onto fft_tasks_queue (RMQ)
      → FftBrokerRunner (this plugin, daemon thread in main.py) drains
        → FftPlugin.execute() runs FFT, writes PNG
          → emits started / progress / completed envelopes
            → NATS JetStream + (opt) RMQ topic exchange
              → CoreService forwarder writes job_event + emits Socket.IO
                → React UI updates live via useJobStepEvents hook
```

The broker path is the only production path. The HTTP server only
exposes `/health` and Prometheus `/metrics`.

---

## Forking checklist

1. Copy the directory, rename it to `magellon_<your_thing>_plugin`.
2. Edit `plugin/compute.py` — replace `compute_file_fft` with your
   algorithm. Keep it pure: no broker, no SDK imports, just inputs in
   and outputs out.
3. Edit `plugin/plugin.py`:
   - Pick the right `CategoryContract` from `magellon_sdk.categories.contract`
     (or define a new one in the SDK if your task category doesn't exist
     yet — the contract pins the input/output Pydantic models).
   - Rename `FftPlugin` → `<Your>Plugin`. Update `get_info()`, `capabilities`,
     `resource_hints`, `tags`. The class-level fields drive the manifest
     the platform uses for discovery.
   - Rename `FftBrokerRunner` → `<Your>BrokerRunner` (the only reason the
     subclass exists is to expose the active TaskDto via ContextVar so
     `execute()` can emit step events keyed on `job_id`).
   - Rewrite `build_fft_result()` to wrap your output in a `TaskResultDto`
     (worker_instance_id / job_id / task_id come from the envelope;
     output_files / output_data come from your output model).
4. Edit `plugin/events.py` — set `STEP_NAME = "<your_step>"`. The lazy
   factory in the SDK does the rest.
5. Edit `core/settings.py` — only if your plugin needs extra
   configuration beyond the standard broker / GPFS / database blocks.
6. Edit `configs/settings_*.yml` — set `QUEUE_NAME` /
   `OUT_QUEUE_NAME` to your plugin's queues.
7. Edit `Dockerfile` — change the `COPY plugins/magellon_fft_plugin/...`
   lines to point at your plugin's directory.
8. `main.py` should need no changes beyond the import line and the
   FastAPI title — the broker runner startup is identical for every
   plugin.

---

## Running tests

### Unit (no broker)

```bash
cd plugins/magellon_fft_plugin
python -m pytest tests/test_fft_plugin.py -v
```

### Integration (testcontainers — needs Docker)

```bash
python -m pytest tests/integration/ -v
```

Spins up RabbitMQ + NATS in throwaway containers, runs the plugin
against them, asserts the round-trip. ~30s including container cold
start.

### Full-stack e2e (CoreService side)

```bash
cd Docker && docker compose up -d              # whole stack
set MAGELLON_E2E_STACK=up
set MAGELLON_GPFS_HOST_PATH=c:\magellon\gpfs    # whatever your .env points at
cd ../CoreService
python -m pytest tests/integration/test_fft_full_stack_e2e.py -v
```

Dispatches 10 FFTs through the live backend → broker → plugin → DB →
Socket.IO chain. ~5–7s when warm.

---

## Configuration knobs

Set in `configs/settings_<env>.yml` (loaded by `AppSettingsSingleton`)
or as environment variables:

| Var                              | Default                          | Purpose                            |
| -------------------------------- | -------------------------------- | ---------------------------------- |
| `QUEUE_NAME`                     | `fft_tasks_queue`                | input task queue                   |
| `OUT_QUEUE_NAME`                 | `fft_out_tasks_queue`            | result queue                       |
| `MAGELLON_STEP_EVENTS_ENABLED`   | unset                            | `1` to publish step events         |
| `MAGELLON_STEP_EVENTS_RMQ`       | unset                            | `1` to mirror step events to RMQ   |
| `NATS_URL`                       | `nats://localhost:4222`          | step-event NATS bus                |
| `NATS_STEP_EVENTS_STREAM`        | `MAGELLON_STEP_EVENTS`           | JetStream stream                   |
| `NATS_STEP_EVENTS_SUBJECTS`      | `magellon.job.*.step.*`          | subject pattern                    |

If `MAGELLON_STEP_EVENTS_ENABLED` is unset, the plugin runs as a pure
pipeline processor with no observability emits — useful for batch
backfills.

---

## What this plugin does not do

- **No HTTP `/execute` endpoint.** Tasks come in over the broker.
  This was deliberately removed when the broker runner became the
  canonical path; if you need direct HTTP invocation for debugging,
  call `FftPlugin().execute(FftTaskData(...))` from a Python REPL.
- **No Consul.** Plugin discovery and dynamic config flow over the
  broker (`magellon.plugins.{announce,heartbeat,config}.*`).
- **No singleton Settings outside of `core/settings.py`.** Plugin code
  reads configuration through `AppSettingsSingleton.get_instance()` —
  test fixtures override the singleton via `update_settings_from_yaml`.
