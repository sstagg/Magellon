# Magellon Plugin Developer Guide

This guide covers everything you need to build a processing plugin for Magellon. A plugin is a self-contained algorithm (particle picking, CTF estimation, motion correction, etc.) that integrates with the backend via a strict contract and gets a UI settings panel generated automatically from its Pydantic model.

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────┐
│                    Frontend                         │
│                                                     │
│  Settings Drawer ◄── GET /schema/input ──► SchemaForm│
│       │                                             │
│       └── pickerParams dict ──► POST /template-pick  │
│                                      │              │
│  JobsPanel ◄── Socket.IO job_update  │              │
│  LogsPanel ◄── Socket.IO log_entry   │              │
└──────────────────────────────────────┼──────────────┘
                                       │
┌──────────────────────────────────────┼──────────────┐
│                   Backend            ▼              │
│                                                     │
│  controller.py ──► PluginBase.run()                 │
│                        │                            │
│               ┌────────┼────────┐                   │
│               ▼        ▼        ▼                   │
│          pre_execute  execute  post_execute          │
│                        │                            │
│                   algorithm.py                      │
│                                                     │
│  Models:  InputT (Pydantic) ──► OutputT (Pydantic)  │
└─────────────────────────────────────────────────────┘
```

The frontend never has hard-coded knowledge of any plugin's parameters. It fetches the JSON Schema from the backend and renders the settings panel dynamically.

---

## Data Plane: Shared Filesystem

Magellon separates **metadata** from **bytes**:

- **Control plane** — the MessageBus (`magellon_sdk.bus`) carries task dispatch, results metadata, progress events, and cancellation. Small payloads only (≤ 10 KB per envelope).
- **Data plane** — a shared POSIX filesystem mounted at `$MAGELLON_HOME_DIR` on CoreService and every plugin worker. Carries MRC files, motion-corrected outputs, CTF star files, thumbnails. Large payloads (MB–GB per file).

**Your plugin's obligations on the data plane:**

1. Read input files from paths provided in the task envelope. Do not re-fetch over the network; the file is already on disk where you can see it.
2. Write outputs under `$MAGELLON_HOME_DIR/<session>/<category>/<image>/`. This is the layout `TaskOutputProcessor` projects into the database — any other layout breaks the result pipeline.
3. Return file **paths**, not file bytes, in `TaskResultMessage`. The result processor moves files based on the paths you report.
4. Write atomically: write to a temp name in the session directory, then `os.rename` to the final name. `rename` within one filesystem is atomic on POSIX.
5. Never use `/tmp` for cross-plugin artifacts — it is not shared between workers.

**What you can assume:** if another plugin wrote `$MAGELLON_HOME_DIR/<session>/foo.mrc` and reported completion, you can open that path and read it. The platform guarantees a single filesystem namespace across all workers.

**What you cannot assume:** object-storage semantics (S3, GCS). Magellon is not deployed against those backends — see `Documentation/DATA_PLANE.md` for the full architectural decision and deployment matrix.

---

## Quick Start: Creating a New Plugin

### 1. Create the directory structure

```
plugins/pp/
└── my_picker/
    ├── __init__.py
    ├── algorithm.py      # Pure computation, no Magellon dependencies
    └── service.py        # PluginBase subclass, wires algorithm to framework
```

### 2. Define your input/output models

Create Pydantic models with `json_schema_extra` on each `Field()` to control UI rendering.

```python
# plugins/pp/models.py  (or your own models file)

from pydantic import BaseModel, ConfigDict, Field
from typing import List, Optional

class MyPickerInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    image_path: str = Field(
        ...,
        description="Path to input micrograph",
        json_schema_extra={
            "ui_hidden": True,  # auto-filled by the app
        },
    )

    template_paths: List[str] = Field(
        ...,
        min_length=1,
        description="Template images for matching",
        json_schema_extra={
            "ui_widget": "file_path_list",
            "ui_group": "Templates",
            "ui_order": 1,
            "ui_file_ext": [".mrc", ".mrcs"],
            "ui_help": "Drag and drop template files here.",
        },
    )

    threshold: float = Field(
        default=0.5,
        ge=0.0,
        le=1.0,
        description="Detection sensitivity",
        json_schema_extra={
            "ui_widget": "slider",
            "ui_group": "Detection",
            "ui_order": 10,
            "ui_step": 0.05,
            "ui_marks": [
                {"value": 0.2, "label": "Low"},
                {"value": 0.5, "label": "Medium"},
                {"value": 0.8, "label": "High"},
            ],
            "ui_help": "Lower = more particles, higher = fewer but more confident.",
        },
    )


class MyPickerOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    particles: List[ParticlePick]
    num_particles: int
```

### 3. Write the algorithm

Keep it pure — numpy in, dicts out. No framework imports.

```python
# plugins/pp/my_picker/algorithm.py

import numpy as np

def detect_particles(image, templates, params):
    """Pure computation. Returns list of particle dicts."""
    # ... your detection logic ...
    return [{"x": 100, "y": 200, "score": 0.85, ...}, ...]
```

### 4. Implement the PluginBase subclass

```python
# plugins/pp/my_picker/service.py

from plugins.base import PluginBase
from plugins.pp.models import MyPickerInput, MyPickerOutput, ParticlePick
from plugins.pp.my_picker.algorithm import detect_particles
from models.plugins_models import PluginInfo, PARTICLE_PICKING, ...

class MyPickerPlugin(PluginBase[MyPickerInput, MyPickerOutput]):

    task_category = PARTICLE_PICKING

    def get_info(self) -> PluginInfo:
        return PluginInfo(
            name="my-picker",
            developer="Your Name",
            description="My custom particle picker",
            version="1.0.0",
        )

    @classmethod
    def input_schema(cls):
        return MyPickerInput

    @classmethod
    def output_schema(cls):
        return MyPickerOutput

    def check_requirements(self):
        # verify dependencies are installed
        ...

    def execute(self, input_data: MyPickerInput) -> MyPickerOutput:
        image = load_mrc(input_data.image_path)
        templates = [load_mrc(p) for p in input_data.template_paths]

        raw = detect_particles(image, templates, {
            "threshold": input_data.threshold,
        })

        particles = [ParticlePick(**p) for p in raw]
        return MyPickerOutput(
            particles=particles,
            num_particles=len(particles),
        )
```

### 5. Register the endpoint

Add a route in the controller or create a new one:

```python
# plugins/pp/controller.py

from plugins.pp.my_picker.service import MyPickerPlugin

my_plugin = MyPickerPlugin()
my_plugin.check_requirements()
my_plugin.configure()
my_plugin.setup()

@pp_router.post("/my-pick")
async def my_pick(input_data: MyPickerInput):
    return my_plugin.run(input_data)

@pp_router.get("/my-pick/schema/input")
async def my_pick_schema():
    return MyPickerInput.model_json_schema()
```

That's it. The frontend will fetch `/my-pick/schema/input` and render a settings panel automatically.

---

## Plugin Lifecycle

```
              check_requirements()
                     │
  DISCOVERED ──► INSTALLED ──► configure() ──► CONFIGURED
                                                  │
                                             setup()
                                                  │
                                                READY
                                               ┌──┴──┐
                                    pre_execute│     │
                                        execute│     │
                                   post_execute│     │
                                               ▼     │
                                   COMPLETED/ERROR   │
                                       │   retry─────┘
                                       │
                                  teardown()
                                       │
                                DISABLED / FAILED
```

### Lifecycle Methods

| Method | Required | When Called | Purpose |
|--------|----------|-------------|---------|
| `get_info()` | **Yes** | Anytime | Return `PluginInfo` (name, version, developer) |
| `input_schema()` | **Yes** | Anytime | Return the Pydantic input model class |
| `output_schema()` | **Yes** | Anytime | Return the Pydantic output model class |
| `check_requirements()` | No | Before first use | Verify dependencies (libraries, GPU, binaries) |
| `configure(settings)` | No | After requirements | Apply external config (DB credentials, paths) |
| `setup()` | No | After configure | One-time init (load ML models, open connections) |
| `pre_execute(input)` | No | Before each run | Logging, input enrichment, validation |
| `execute(input)` | **Yes** | Each run | Core processing — the actual algorithm |
| `post_execute(input, output)` | No | After each run | Logging, metrics, output enrichment |
| `teardown()` | No | On shutdown | Release resources (GPU memory, connections) |
| `health_check()` | No | On demand | Quick liveness probe |

### The `run()` Method (Do Not Override)

`run()` is the public entry point called by the controller. It:

1. Validates input against `input_schema()` (accepts dict or model instance)
2. Calls `pre_execute()` → `execute()` → `post_execute()`
3. Validates output against `output_schema()`
4. Manages status transitions (RUNNING → COMPLETED / ERROR)

```python
# Called by the controller — accepts raw dict or Pydantic model
output = plugin.run({"image_path": "...", "template_paths": [...]})
output = plugin.run(validated_input_model)
```

---

## Input Model Specification

### Pydantic Field Rules

- Use `ConfigDict(extra="forbid")` — rejects unknown fields
- Use `Field(...)` for required, `Field(default=...)` for optional
- Add validation: `gt=0`, `ge=0`, `le=1`, `min_length=1`
- Add `description` for all fields

### UI Metadata (`json_schema_extra`)

Every field can carry UI hints that control how the frontend renders it.

#### Widget Types

| `ui_widget` | Renders As | Best For |
|-------------|------------|----------|
| `slider` | MUI Slider | Bounded floats/ints with meaningful range |
| `number` | Number input | Unbounded or precise numeric values |
| `text` | Text input | Free-form strings |
| `toggle` | Switch | Boolean on/off |
| `select` | Dropdown | Enum or fixed option list |
| `file_path` | Text input | Single file path |
| `file_path_list` | Drag-and-drop zone + list | Multiple file paths |
| `hidden` | Not rendered | Internal fields |

#### Grouping & Ordering

| Key | Type | Effect |
|-----|------|--------|
| `ui_group` | `str` | Accordion section heading. Fields with the same group appear together. |
| `ui_order` | `int` | Sort key within group. Lower numbers appear first. |
| `ui_advanced` | `bool` | If `True`, the group starts collapsed. |
| `ui_hidden` | `bool` | Field is never rendered (use for auto-filled or internal fields). |

#### Slider Configuration

| Key | Type | Effect |
|-----|------|--------|
| `ui_step` | `float` | Slider increment |
| `ui_marks` | `list[{value, label}]` | Labeled tick marks on the slider |
| `ui_unit` | `str` | Unit suffix shown after the label ("Å", "px") |

#### File Pickers

| Key | Type | Effect |
|-----|------|--------|
| `ui_file_ext` | `list[str]` | Accepted file extensions: `[".mrc", ".mrcs"]` |
| `ui_placeholder` | `str` | Placeholder text in the input field |

#### Help & Validation

| Key | Type | Effect |
|-----|------|--------|
| `ui_help` | `str` | Tooltip shown on hover — explain what the parameter does |
| `ui_placeholder` | `str` | Greyed-out hint text inside input fields |
| `ui_required_message` | `str` | Custom error message when required field is empty |

#### Conditional Visibility

| Key | Type | Effect |
|-----|------|--------|
| `ui_depends_on` | `dict` | Only show this field when condition is met |

Example: Show "lowpass_resolution" only when a toggle is enabled:

```python
lowpass_enabled: bool = Field(
    default=False,
    json_schema_extra={"ui_widget": "toggle", "ui_group": "Preprocessing", "ui_order": 21},
)

lowpass_resolution: Optional[float] = Field(
    default=None,
    json_schema_extra={
        "ui_widget": "number",
        "ui_group": "Preprocessing",
        "ui_order": 22,
        "ui_depends_on": {"lowpass_enabled": True},
    },
)
```

### Complete Field Example

```python
threshold: float = Field(
    default=0.4,
    ge=0.0,
    le=1.0,
    description="Normalized cross-correlation score cutoff",
    json_schema_extra={
        "ui_widget": "slider",
        "ui_group": "Detection",
        "ui_order": 6,
        "ui_step": 0.05,
        "ui_unit": "",
        "ui_marks": [
            {"value": 0.2, "label": "Low"},
            {"value": 0.5, "label": "Medium"},
            {"value": 0.8, "label": "High"},
        ],
        "ui_help": "Lower values detect more particles (including noise); "
                   "higher values are more selective.",
        "ui_advanced": False,
    },
)
```

This single field definition produces:
- A slider in the "Detection" section of the settings panel
- Range 0.0–1.0 with 0.05 steps
- Three labeled tick marks
- A tooltip on hover explaining the parameter
- JSON Schema validation (ge=0, le=1)
- Backend validation via Pydantic

---

## Output Model

The output model defines what the plugin returns. The `ParticlePick` model is shared across all particle-picking backends:

```python
class ParticlePick(BaseModel):
    model_config = ConfigDict(extra="forbid")

    x: int              # Particle X coordinate (pixels)
    y: int              # Particle Y coordinate (pixels)
    score: float        # Detection confidence (0-1)
    stddev: float       # Score standard deviation within blob
    area: int           # Blob area in pixels
    roundness: float    # Blob circularity (0-1)
    template_index: int # Which template matched (1-based)
    angle: float        # Best matching rotation angle (degrees)
    label: str          # Human-readable label
```

Your output model should include `List[ParticlePick]` plus any summary fields:

```python
class MyPickerOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    particles: List[ParticlePick]
    num_particles: int
    # Add plugin-specific output fields as needed
    processing_time_seconds: Optional[float] = None
```

---

## REST API Endpoints

Each plugin backend exposes these endpoints (registered in a FastAPI `APIRouter`):

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/plugins/pp/<name>` | POST | Synchronous execution |
| `/plugins/pp/<name>-async` | POST | Async execution (returns `job_id`) |
| `/plugins/pp/<name>/schema/input` | GET | JSON Schema for the input model |
| `/plugins/pp/<name>/schema/output` | GET | JSON Schema for the output model |
| `/plugins/pp/<name>/info` | GET | Plugin metadata (PluginInfo) |
| `/plugins/pp/<name>/health` | GET | Health check (status + version) |
| `/plugins/pp/<name>/requirements` | GET | Dependency check results |
| `/plugins/pp/jobs` | GET | List all jobs |
| `/plugins/pp/jobs/{job_id}` | GET | Get job details + results |

### Socket.IO Events

For async jobs, the backend emits real-time events:

| Event | Direction | Payload |
|-------|-----------|---------|
| `job_update` | Server → Client | `{id, name, type, status, progress, num_particles, error, result}` |
| `log_entry` | Server → Client | `{id, timestamp, level, source, message}` |

---

## Testing Your Plugin

Write tests at four levels:

```python
# 1. Model validation — does the contract reject bad input?
def test_rejects_negative_pixel_size():
    with pytest.raises(Exception):
        MyPickerInput(image_path="x.mrc", ..., image_pixel_size=-1)

# 2. Algorithm — does the core logic work with synthetic data?
def test_detects_particles():
    image = make_test_micrograph()
    result = detect_particles(image, [template], {"threshold": 0.3})
    assert len(result) > 0

# 3. Plugin lifecycle — do state transitions work?
def test_full_lifecycle():
    plugin = MyPickerPlugin()
    assert plugin.status == PluginStatus.DISCOVERED
    plugin.check_requirements()
    assert plugin.status == PluginStatus.INSTALLED
    plugin.configure()
    plugin.setup()
    assert plugin.status == PluginStatus.READY
    result = plugin.run(valid_input)
    assert plugin.status == PluginStatus.COMPLETED

# 4. HTTP endpoint — does the API work end-to-end?
def test_endpoint(client, mrc_files):
    response = client.post("/plugins/pp/my-pick", json={...})
    assert response.status_code == 200
    assert response.json()["num_particles"] >= 0
```

---

## Directory Layout

```
plugins/
├── __init__.py
├── base.py                          # PluginBase ABC — do not modify
└── pp/                              # Particle picking category
    ├── __init__.py
    ├── models.py                    # Shared models (ParticlePick, etc.)
    ├── controller.py                # FastAPI router for all pp backends
    ├── template_picker/             # One backend
    │   ├── __init__.py
    │   ├── algorithm.py             # Pure computation
    │   └── service.py               # PluginBase subclass
    └── my_picker/                   # Your new backend
        ├── __init__.py
        ├── algorithm.py
        └── service.py
```

---

## Checklist for a New Plugin

- [ ] Create `algorithm.py` with pure computation (no framework imports)
- [ ] Define input model with `ConfigDict(extra="forbid")` and `json_schema_extra` on every field
- [ ] Define output model using shared `ParticlePick`
- [ ] Subclass `PluginBase` — implement `get_info()`, `input_schema()`, `output_schema()`, `execute()`
- [ ] Override `check_requirements()` if you need special libraries/GPU
- [ ] Override `setup()` if you load ML models or heavy resources
- [ ] Register routes in `controller.py` (POST endpoint + GET schema endpoint)
- [ ] Include router in `main.py`
- [ ] Write tests: models, algorithm, lifecycle, endpoint
- [ ] Verify the settings panel renders correctly from your schema
- [ ] Mark tunable fields with `"ui_tunable": True` for preview/retune support
- [ ] Add preview/retune endpoints if applicable

---

## Preview / Retune Flow

Plugins that have an expensive compute phase and cheap re-parameterization can support interactive tuning:

```
POST /preview        → runs expensive computation, stores intermediates, returns preview_id + particles + score_map
POST /preview/{id}/retune  → re-applies tunable params to stored intermediates (instant)
DELETE /preview/{id}       → free memory
```

Mark fields that can be re-tuned without recomputation with `"ui_tunable": True`:

```python
threshold: float = Field(
    default=0.4,
    json_schema_extra={
        "ui_widget": "slider",
        "ui_tunable": True,  # ← can be changed in preview mode without recomputing FFT
        ...
    },
)
```

The frontend `SchemaForm` component accepts `tunableOnly={true}` to render only these fields during the preview phase.

---

## AI-Assisted Development Prompts

Use these prompts with Claude Code, Codex, or similar AI coding tools to create new plugins or refactor existing algorithms into the Magellon plugin format.

### Prompt 1: Create a New Plugin from Scratch

Copy-paste this into your AI assistant session:

```
I need to create a new Magellon processing plugin. Here is the specification:

## Context
- Project: Magellon Core Service (FastAPI backend for cryo-EM image processing)
- Location: C:\projects\Magellon\CoreService
- Plugin base class: plugins/base.py (PluginBase[InputT, OutputT] ABC)
- Existing reference: plugins/pp/template_picker/ (fully working example)

## What I need
Create a new plugin backend called "[YOUR_ALGORITHM_NAME]" in:
  plugins/pp/[your_algorithm_name]/

## Architecture rules
1. **algorithm.py** — Pure computation. No Magellon/FastAPI imports. Takes numpy arrays
   and plain dicts, returns list of dicts. This file should be testable standalone.

2. **service.py** — PluginBase subclass that:
   - Implements get_info(), input_schema(), output_schema(), execute()
   - Loads files (MRC via mrcfile) in execute(), calls algorithm, maps results to Pydantic output
   - Overrides check_requirements() to verify dependencies
   - Module-level singleton + run_xxx() convenience function

3. **Input model** (in plugins/pp/models.py or own file) — Pydantic BaseModel with:
   - ConfigDict(extra="forbid")
   - Every Field has json_schema_extra with ui_* metadata for auto-generated UI
   - Required keys per field: ui_widget, ui_group, ui_order
   - Mark interactive-tuning fields with "ui_tunable": True
   - Auto-filled fields (like image_path) get "ui_hidden": True
   - Add ui_help tooltip text explaining each parameter

4. **Output model** — Use shared ParticlePick for particle-picking plugins:
   ```python
   class ParticlePick(BaseModel):
       x: int, y: int, score: float, stddev: float, area: int,
       roundness: float, template_index: int, angle: float, label: str
   ```

5. **Controller routes** — Add to plugins/pp/controller.py:
   - POST /<name> (sync), POST /<name>-async (background job)
   - POST /<name>/preview + POST /<name>/preview/{id}/retune (if applicable)
   - GET /<name>/schema/input, GET /<name>/info, GET /<name>/health

6. **Tests** — In tests/test_[name].py covering:
   - Model validation (required fields, extra="forbid", value ranges)
   - Algorithm with synthetic numpy data
   - Plugin lifecycle (DISCOVERED→INSTALLED→CONFIGURED→READY→COMPLETED)
   - HTTP endpoints via FastAPI TestClient

## UI metadata spec for json_schema_extra
- ui_widget: "slider"|"number"|"text"|"file_path"|"file_path_list"|"toggle"|"select"|"hidden"
- ui_group: section heading (e.g. "Templates", "Detection Settings", "Preprocessing", "Advanced")
- ui_order: sort within group (lower = first)
- ui_step: slider/number increment
- ui_marks: [{value, label}] for slider ticks
- ui_unit: suffix ("Å", "px", "Å/px")
- ui_help: tooltip text
- ui_advanced: true → collapsed by default
- ui_tunable: true → can be changed in preview mode without recomputing
- ui_hidden: true → not shown in UI
- ui_file_ext: [".mrc"] for file pickers
- ui_placeholder: input placeholder
- ui_depends_on: {"other_field": value} conditional visibility

## My algorithm does:
[DESCRIBE YOUR ALGORITHM HERE — what it takes as input, what it produces,
 what parameters it has, what's expensive vs cheap to recompute]
```

### Prompt 2: Refactor an Existing Script into a Plugin

```
I have an existing Python script that I need to refactor into a Magellon plugin.

## The existing code
[PASTE YOUR SCRIPT OR POINT TO THE FILE PATH]

## Target structure
Refactor into the Magellon plugin format:

  plugins/pp/[name]/
  ├── __init__.py
  ├── algorithm.py    # Extract pure computation here (no framework deps)
  └── service.py      # PluginBase subclass wrapping the algorithm

## Refactoring rules
1. **Separate concerns**: Move all numpy/scipy computation into algorithm.py.
   Move file I/O, MRC loading, and Magellon integration into service.py.

2. **Replace interactive prompts**: The original script may use input() or argparse.
   Convert ALL user inputs into Pydantic Field() definitions with ui_* metadata.
   Every CLI flag becomes a typed, validated, UI-rendered field.

3. **Replace hardcoded paths**: Config file paths, model weights, output dirs
   should become Field() parameters (with ui_hidden if auto-filled).

4. **Identify tunable params**: Parameters that can be re-applied without
   re-running the expensive computation get "ui_tunable": True.

5. **Preserve the algorithm**: Don't change the core math/logic — just wrap it.
   The algorithm.py should be a drop-in replacement that passes the same tests.

6. **Add Pydantic contracts**: Input model with extra="forbid" and full ui_*
   metadata. Output model using shared ParticlePick (for pp plugins).

7. **Add tests**: Synthetic data test for the algorithm, lifecycle test for the
   plugin, endpoint test for the HTTP API.

## Reference implementation
Read these files for the exact patterns to follow:
- plugins/base.py (PluginBase ABC)
- plugins/pp/models.py (TemplatePickerInput with full ui_* metadata)
- plugins/pp/template_picker/algorithm.py (pure computation)
- plugins/pp/template_picker/service.py (TemplatePickerPlugin)
- plugins/pp/controller.py (routes including preview/retune)
- tests/test_template_picker.py (62 tests across all layers)
```

### Prompt 3: Add Preview/Retune Support to an Existing Plugin

```
I have an existing Magellon plugin at plugins/pp/[name]/ and I want to add
preview/retune support so users can interactively tune parameters without
re-running the expensive computation.

## Current state
- algorithm.py has a main function that does everything in one pass
- service.py has execute() that calls it

## What I need
1. Split the algorithm into two phases:
   - Phase 1 (expensive): [DESCRIBE — e.g. "FFT correlation, model inference"]
   - Phase 2 (cheap): [DESCRIBE — e.g. "thresholding, filtering, peak extraction"]

2. Store Phase 1 results in memory under a preview_id

3. Add these endpoints to the controller:
   - POST /<name>/preview → runs Phase 1, returns preview_id + initial results
   - POST /<name>/preview/{id}/retune → runs Phase 2 with new params (instant)
   - DELETE /<name>/preview/{id} → free memory

4. Mark the Phase 2 parameters with "ui_tunable": True in the input model

5. Add RetuneRequest model with just the tunable fields

6. Return a score/confidence map as base64 PNG for visualization

## Reference
See how template_picker implements this:
- plugins/pp/controller.py: template_pick_preview() and template_pick_retune()
- plugins/pp/models.py: PreviewResult, RetuneRequest, RetuneResult
- Fields with "ui_tunable": True: threshold, max_peaks, overlap_multiplier, etc.
```

### Prompt 4: Validate and Improve an Existing Plugin's UI Metadata

```
Review the input model for my Magellon plugin and improve the UI metadata.

## The model
[PASTE YOUR INPUT MODEL CLASS]

## Check for
1. Every Field has json_schema_extra with at minimum: ui_widget, ui_group, ui_order
2. All user-facing fields have ui_help tooltip text
3. Sliders have ui_marks with meaningful labels (not just numbers)
4. File inputs have ui_file_ext
5. Fields are grouped logically (Templates, Detection, Preprocessing, Advanced)
6. Advanced/expert fields are marked ui_advanced: True
7. Auto-filled fields are marked ui_hidden: True
8. Tunable fields are marked ui_tunable: True
9. Numeric fields have appropriate validation (gt, ge, le, etc.)
10. Required fields have ui_required_message with user-friendly text
11. Conditional fields use ui_depends_on

## Reference spec
- ui_widget: "slider"|"number"|"text"|"file_path"|"file_path_list"|"toggle"|"select"|"hidden"
- ui_group: accordion section heading
- ui_order: sort within group (lower = first)
- ui_step, ui_marks, ui_unit: slider/number config
- ui_help: tooltip, ui_placeholder: input hint
- ui_advanced: collapsed by default
- ui_tunable: changeable without recompute
- ui_hidden: not rendered
- ui_depends_on: conditional visibility
- ui_required_message: custom validation error
```
