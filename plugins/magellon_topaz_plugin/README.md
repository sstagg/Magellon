# magellon-topaz-plugin

Magellon plugin that serves two cryo-EM tasks from a single container:

- **Topaz particle picking** — CNN-based detection on high-mag MRCs, no training required.
- **Micrograph denoising** — patch-and-stitch UNet denoising with the same ONNX runtime.

Upstream [tbepler/topaz](https://github.com/tbepler/topaz) (GPL-3.0) internals are vendored under `plugin/topaz_lib/` and the three bundled ONNX weight files stay under GPL terms. All other code follows the Magellon repository license.

---

## Categories

| Category | `TaskCategory` code | Input | Output |
|---|---:|---|---|
| `topaz_particle_picking` | 8 | High-mag MRC (0.5–2 Å/px) | Ranked particle list + score + radius |
| `micrograph_denoising` | 9 | High-mag MRC (0.5–2 Å/px) | Denoised MRC + pixel-intensity stats |

Both categories are served from the same plugin process. The manifest advertises `topaz_particle_picking` as the primary surface; a second consumer registered in `main.py` handles denoising tasks.

---

## Quick start

### Docker (recommended)

```bash
# Build
cd plugins/magellon_topaz_plugin
docker build -t magellon-topaz-plugin:latest .

# Run — wire to your RMQ broker and GPFS mount
docker run -d \
  -e RABBITMQ_HOST=rmq.internal \
  -e RABBITMQ_USER=rabbit \
  -e RABBITMQ_PASS=secret \
  -e PICK_QUEUE_NAME=topaz_pick_tasks_queue \
  -e PICK_OUT_QUEUE_NAME=topaz_pick_out_tasks_queue \
  -e DENOISE_QUEUE_NAME=micrograph_denoise_tasks_queue \
  -e DENOISE_OUT_QUEUE_NAME=micrograph_denoise_out_tasks_queue \
  -v /your/gpfs:/gpfs \
  magellon-topaz-plugin:latest
```

### Local dev (uv)

```bash
cd plugins/magellon_topaz_plugin
uv sync                          # installs from pyproject.toml
cp configs/settings_dev.yml .    # adjust paths + credentials
uvicorn main:app --host 0.0.0.0 --port 8039 --reload
```

The SDK wheel bundled under `wheels/` is used by `requirements.txt` during the Docker build so the image does not need PyPI access for the SDK.

---

## Configuration

Settings are loaded from `configs/settings_dev.yml` (dev) or `configs/settings_prod.yml` (prod), and can be overridden by environment variables.

| Setting | Default (dev) | Description |
|---|---|---|
| `PORT_NUMBER` | `8039` | HTTP liveness port |
| `MAGELLON_GPFS_PATH` | `C:/magellon/gpfs` | Host path of the shared filesystem |
| `PICK_QUEUE_NAME` | `topaz_pick_tasks_queue` | Inbound RMQ queue for picking tasks |
| `PICK_OUT_QUEUE_NAME` | `topaz_pick_out_tasks_queue` | Result queue CoreService consumes |
| `DENOISE_QUEUE_NAME` | `micrograph_denoise_tasks_queue` | Inbound queue for denoising tasks |
| `DENOISE_OUT_QUEUE_NAME` | `micrograph_denoise_out_tasks_queue` | Result queue for denoising results |
| `rabbitmq_settings.HOST_NAME` | `127.0.0.1` | RMQ broker host |
| `rabbitmq_settings.PORT` | `5672` | RMQ broker port |
| `rabbitmq_settings.USER_NAME` | `rabbit` | RMQ username |

---

## Engine options

Pass these as `engine_opts` in the task payload. Any key absent from the payload uses the listed default.

### Particle picking (`topaz_particle_picking`)

| Key | Type | Default | Notes |
|---|---|---|---|
| `model` | `str` | `"resnet16"` | Detector architecture. Also `"resnet8"` (faster, slightly lower recall). |
| `radius` | `int` | `14` | NMS exclusion radius in preprocessed-grid pixels. |
| `threshold` | `float` | `-3.0` | Log-likelihood cutoff. Lower = more sensitive (topaz default is −6). |
| `scale` | `int` | `8` | DFT downsampling factor applied before inference. |

### Micrograph denoising (`micrograph_denoising`)

| Key | Type | Default | Notes |
|---|---|---|---|
| `model` | `str` | `"unet"` | Denoising architecture. Also `"unet_l2"` (larger, smoother output). |
| `patch_size` | `int` | `1024` | Tile size for patch-and-stitch inference (pixels). |
| `padding` | `int` | `128` | Overlap absorbed at tile edges (pixels). Prevents seam artefacts. |

---

## Output conventions

### Particle picking

Picks are written to:
```
<MAGELLON_HOME>/<session>/topaz_picks/<image_stem>/picks.json
```

The result envelope on the bus carries a path reference and a scalar summary — downstream consumers read the JSON file directly (per bus-invariant rule 1: bus carries refs and summaries only, not the full particle list).

**picks.json schema** (one object per particle):
```json
[
  { "x": 1024, "y": 2048, "score": -1.43, "radius": 14 },
  ...
]
```

- `x`, `y` — pixel coordinates in **original** (undownsampled) image space.
- `score` — Topaz log-likelihood. Higher is better; threshold default is −3.0.
- `radius` — same as the `radius` engine opt; used by the viewer to draw circles.

### Micrograph denoising

Denoised MRC written to:
```
<MAGELLON_HOME>/<session>/topaz_denoised/<image_stem>.mrc
```

The result envelope includes pixel statistics (`min`, `max`, `mean`, `std`) and the full output path.

---

## ONNX models

Three weight files ship inside `plugin/weights/` (~17 MB total). No PyTorch or topaz-em installation is required at runtime.

| File | Architecture | Task |
|---|---|---|
| `topaz_resnet16_u64.onnx` | ResNet-16 U64 | Particle detection (more accurate) |
| `topaz_resnet8_u64.onnx` | ResNet-8 U64 | Particle detection (faster) |
| `topaz_unet_l2.onnx` | UNet L2 | Micrograph denoising |

The `plugin/topaz_lib/` module provides the preprocessing, FFT downsampling, GMM normalisation, NMS, and tile-stitch logic ported from upstream topaz (pure numpy/scipy, no PyTorch calls).

---

## Resource requirements

| Resource | Value |
|---|---|
| RAM | ~2 GB (float32 buffers for up to ~7000×7000 micrograph) |
| CPU cores | 4 |
| GPU | Optional — ONNX CPU provider only; no CUDA dependency |
| Typical duration | ~30 s per micrograph |

GPU support could be enabled by swapping in `onnxruntime-gpu` and selecting the `CUDAExecutionProvider`, but is not wired today.

---

## Testing

```bash
cd plugins/magellon_topaz_plugin
uv sync
pytest tests/ -v
```

Key test files:

| File | What it checks |
|---|---|
| `tests/test_smoke.py` | Plugin classes instantiate, `input_schema()` / `output_schema()` return the right Pydantic types |
| `tests/test_topaz_plugin.py` | End-to-end `execute()` with a synthetic MRC; verifies picks JSON is written and result fields are populated |

---

## Bus dispatch (reference)

CoreService dispatches tasks via RMQ. A minimal picking payload looks like:

```json
{
  "id": "<uuid>",
  "type": { "code": 8, "name": "topaz_particle_picking" },
  "data": {
    "input_file": "/gpfs/home/<session>/original/<image>.mrc",
    "session_name": "<session>",
    "engine_opts": {
      "model": "resnet16",
      "radius": 14,
      "threshold": -3.0,
      "scale": 8
    }
  }
}
```

Published to `topaz_pick_tasks_queue`; the result comes back on `topaz_pick_out_tasks_queue` and is consumed by CoreService's `TaskOutputProcessor`.

---

## Back-compat shim

`plugin/plugin.py` re-exports `TopazBrokerRunner = PluginBrokerRunner` (from SDK). This shim exists for callers that imported `TopazBrokerRunner` before Phase 1b absorbed the runner into the SDK. Remove in 2026-Q3 once `main.py` and tests migrate to `PluginBrokerRunner` directly.

---

## License

`plugin/topaz_lib/` and the three ONNX weight files are derived from [tbepler/topaz](https://github.com/tbepler/topaz) and remain under **GPL-3.0**. All other code in this repository follows the Magellon project license (see root `LICENSE`).
