# Magellon — Plugins (Architecture, Format, Install, Manager, Hub, Author's Guide)

**Status:** Consolidated reference. Merged from six source documents on 2026-05-13.
**Audience:** Plugin authors, install-pipeline maintainers, hub publishers, operators managing plugin lifecycle.
**Companion:** `ARCHITECTURE.md` (system reference), `SECURITY.md`, `OPERATIONS.md`.

End-to-end plugin documentation: how plugins work in the runtime, how
they're packed and shipped (`.mpn` archives), how the install pipeline
processes them, how operators manage installed instances, how the public
hub catalogs them, and how to write one from scratch.

## Contents

1. [Plugin Architecture (Runtime)](#1-plugin-architecture-runtime)
2. [Plugin Archive Format (.mpn)](#2-plugin-archive-format-mpn)
3. [Plugin Install Pipeline](#3-plugin-install-pipeline)
4. [Plugin Manager](#4-plugin-manager)
5. [Magellon Hub Specification](#5-magellon-hub-specification)
6. [Plugin Developer Guide](#6-plugin-developer-guide)

---

<!--
  Section: 1. Plugin Architecture (Runtime)
  Originated from: CoreService/docs/architecture/PLUGIN_ARCHITECTURE.md
  Merged into this consolidated reference 2026-05-13.
-->

# Plugin Architecture

How Magellon plugins work end-to-end: from `PluginBase` on the backend to the React plugin runner and image-viewer integrations on the frontend. Uses the `pp/template-picker` (particle picking) plugin as the running example.

- [1. High-level picture](#1-high-level-picture)
- [2. Backend: the plugin contract](#2-backend-the-plugin-contract)
- [3. Backend: discovery and router mounting](#3-backend-discovery-and-router-mounting)
- [4. Backend: job service + Socket.IO](#4-backend-job-service--socketio)
- [5. Backend: the `pp` particle-picking plugin](#5-backend-the-pp-particle-picking-plugin)
- [6. Frontend: the plugin runner page](#6-frontend-the-plugin-runner-page)
- [7. Frontend: image-viewer integration](#7-frontend-image-viewer-integration)
- [8. End-to-end flows (sequence diagrams)](#8-end-to-end-flows-sequence-diagrams)
- [9. Data shapes cheat sheet](#9-data-shapes-cheat-sheet)
- [10. File index](#10-file-index)

---

## 1. High-level picture

```mermaid
flowchart LR
    subgraph Frontend["React frontend"]
        PR[PluginRunner page]
        IV[Image viewer<br/>ParticlePickingTab]
        SocketClient[Socket.IO client<br/>SocketProvider]
        Stores[Zustand stores<br/>jobs · logs · sidePanel]
    end

    subgraph Backend["FastAPI backend"]
        GenericRouter["/plugins/* <br/>generic router"]
        PPRouter["/plugins/pp/* <br/>plugin-specific router"]
        Registry[PluginRegistry<br/>lazy scan]
        PluginImpl[TemplatePickerPlugin<br/>: PluginBase]
        JobSvc[JobManager]
        Sio[Socket.IO server<br/>/socket.io]
    end

    subgraph Storage["Storage"]
        DB[(MariaDB<br/>image_job · image_meta_data<br/>plugin · image)]
        FS[(Filesystem<br/>.mrc micrographs<br/>templates)]
    end

    PR -->|HTTP| GenericRouter
    PR -->|HTTP| PPRouter
    IV -->|HTTP| PPRouter
    GenericRouter --> Registry --> PluginImpl
    PPRouter --> PluginImpl
    GenericRouter --> JobSvc
    PPRouter --> JobSvc
    JobSvc --> DB
    PPRouter --> DB
    PluginImpl --> FS
    JobSvc -. emits .-> Sio
    PPRouter -. emits .-> Sio
    Sio -->|websocket| SocketClient
    SocketClient --> Stores
    Stores --> PR
    Stores --> IV
```

Every plugin is built the same way:

1. A Python class that inherits `PluginBase[InputT, OutputT]` and implements `execute()`.
2. A `service.py` module so the registry can find it by filename convention.
3. Optionally, a plugin-specific FastAPI router (like `pp/controller.py`) for endpoints the generic `/plugins/{id}/jobs` contract can't express — preview/retune flows, batch jobs, DB persistence variants.
4. Frontend code that either drops into the generic `PluginRunner` page (schema-driven form) or embeds the plugin into a richer feature (the particle-picking tab in the image viewer).

---

## 2. Backend: the plugin contract

Every plugin subclasses `PluginBase` — a generic abstract class parameterised by its input and output Pydantic models.

**File:** `CoreService/plugins/base.py`

```mermaid
classDiagram
    class PluginBase~InputT, OutputT~ {
        <<abstract>>
        -_status: PluginStatus
        -_config: dict
        +get_info() PluginInfo*
        +input_schema() Type[InputT]*
        +output_schema() Type[OutputT]*
        +execute(input_data) OutputT*
        +check_requirements() List[RequirementResult]
        +configure(settings) None
        +setup() None
        +teardown() None
        +pre_execute(input_data) InputT
        +post_execute(input, output) OutputT
        +health_check() dict
        +run(raw_input) OutputT
    }

    class TemplatePickerPlugin {
        +task_category = PARTICLE_PICKING
        +get_info()
        +input_schema() TemplatePickerInput
        +output_schema() TemplatePickerOutput
        +execute(input) TemplatePickerOutput
    }

    class TemplatePickerInput {
        +image_path: str
        +template_paths: List[str]
        +diameter_angstrom: float
        +threshold: float
        +bin_factor: int
        +...
    }

    class TemplatePickerOutput {
        +particles: List[ParticlePick]
        +num_particles: int
        +image_shape: List[int]
    }

    PluginBase <|-- TemplatePickerPlugin
    TemplatePickerPlugin ..> TemplatePickerInput
    TemplatePickerPlugin ..> TemplatePickerOutput
```

Only `get_info`, `input_schema`, `output_schema`, and `execute` are required. Everything else has a default. The top-level entry point is `run(raw_input)` which orchestrates the pipeline:

```mermaid
flowchart LR
    A[raw_input<br/>dict or InputT] --> B{validate}
    B --> C[pre_execute]
    C --> D[execute]
    D --> E[post_execute]
    E --> F{validate}
    F --> G[OutputT]
    B -. ValidationError .-> X[HTTPException 422]
    D -. exception .-> Y[status = ERROR]
```

`PluginStatus` tracks lifecycle: `DISCOVERED → INSTALLED → CONFIGURED → READY → RUNNING → COMPLETED/ERROR → DISABLED`.

---

## 3. Backend: discovery and router mounting

### Discovery

**File:** `CoreService/plugins/registry.py`

The registry is a lazy singleton. Nothing is loaded at import time; the first call to `registry.list()` or `registry.get(plugin_id)` triggers a filesystem scan under `plugins/` for modules named `*.service`. For each hit, the module is imported, scanned for `PluginBase` subclasses, and one instance is cached.

```mermaid
sequenceDiagram
    participant HTTP as HTTP client
    participant Router as /plugins/ router
    participant Registry as PluginRegistry
    participant FS as plugins/ dir
    participant Mod as pp.template_picker.service
    participant Cls as TemplatePickerPlugin

    HTTP->>Router: GET /plugins/
    Router->>Registry: list()
    alt first call
        Registry->>FS: glob **/*.service.py
        FS-->>Registry: [pp.template_picker.service, ...]
        Registry->>Mod: import_module(...)
        Mod-->>Registry: module
        Registry->>Cls: instantiate()
        Cls->>Cls: get_info()
        Registry->>Registry: store PluginEntry<br/>id = "pp/template-picker"
    end
    Registry-->>Router: list of entries
    Router-->>HTTP: [PluginSummary, ...]
```

Plugin id format: `{category}/{info.name}`, where `category` is the directory directly under `plugins/` (e.g. `pp`) and `info.name` comes from `get_info()`.

### Router mounting

**File:** `CoreService/main.py` (lines 49–50, 303–304, 322)

Two routers mount, plus Socket.IO:

| Path prefix | Router | Purpose |
|---|---|---|
| `/plugins` | `plugins_router` | Generic contract: list, info, schema, submit, jobs |
| `/plugins/pp` | `pp_router` | Plugin-specific endpoints for particle picking |
| `/socket.io` | `sio` ASGI app | Real-time job progress + logs |

The generic router is enough to run any plugin — the plugin-specific one adds endpoints the generic contract can't express cleanly (preview/retune, DB-image run-and-save, batch).

---

## 4. Backend: job service + Socket.IO

Async plugins don't block the HTTP request. They return a **job envelope** immediately; actual execution runs in `asyncio.create_task(...)` and streams progress via Socket.IO.

### JobManager

**File:** `CoreService/services/job_manager.py`
**Table:** `image_job` (+ `image_job_task` per image)

```mermaid
stateDiagram-v2
    [*] --> queued: create_job()
    queued --> running: mark_running()
    running --> running: update_progress()
    running --> completed: complete_job()
    running --> failed: fail_job()
    completed --> [*]
    failed --> [*]
```

Envelope shape (same for every call that returns a job):

```json
{
  "job_id": "<uuid>",
  "plugin_id": "pp/template-picker",
  "name": "Particle Picking",
  "status": "queued|running|completed|failed",
  "progress": 0,
  "num_items": 0,
  "started_at": null,
  "ended_at": null,
  "error": null,
  "settings": { "...input params..." },
  "result": { "...only on completion..." }
}
```

### Socket.IO

**File:** `CoreService/core/socketio_server.py`

Two events, both emitted from the backend:

| Event | Emitter | Payload | Listener |
|---|---|---|---|
| `job_update` | `emit_job_update(sid, envelope)` | Job envelope (as above) | `SocketProvider` → `useJobStore` |
| `log_entry` | `emit_log(level, source, message)` | `{ id, timestamp, level, source, message }` | `SocketProvider` → `useLogStore` |

When the frontend submits a job it passes its connection's `sid` as a query param; the backend scopes emits to that room so only the submitter sees progress.

---

## 5. Backend: the `pp` particle-picking plugin

Directory: `CoreService/plugins/pp/`

```
plugins/pp/
├── controller.py          FastAPI router at /plugins/pp
├── models.py              Pydantic: TemplatePickerInput/Output, BatchPickRequest, ...
└── template_picker/
    ├── service.py         TemplatePickerPlugin : PluginBase
    └── algorithm.py       FFT correlation, peak extraction, merging
```

### Endpoint map

| Endpoint | Sync/Async | Saves to DB? | Use case |
|---|---|---|---|
| `POST /template-pick` | sync | no | Stateless; used by the plugin runner and by the fallback path when no DB image is selected. |
| `POST /template-pick/preview` | sync | no (TTL cache) | Runs the expensive FFT once; returns `preview_id`, initial picks, and a score-map thumbnail. |
| `POST /template-pick/preview/{id}/retune` | sync | no | Re-thresholds the cached maps — fast param sweeps with no recompute. |
| `DELETE /template-pick/preview/{id}` | sync | — | Evict from the 10-minute TTL cache. |
| `POST /template-pick-async` | async | `image_job` row only | Generic async job with Socket.IO progress. |
| `POST /template-pick/run-and-save` | async | `image_meta_data` row | Run on a DB image and persist particles so the picking-record dropdown finds them. |
| `POST /template-pick/batch` | async | one `image_meta_data` row per image | Many images, one job, templates preprocessed once. |
| `GET /template-pick/records/{ipp_oid}/coco` | sync | no | Export a saved picking record as COCO JSON. |
| `GET /template-pick/session-images` | sync | no | List candidate images for batch selection, filtered by magnification. |
| `GET /template-pick/schema/{input,output}` | sync | no | JSON schema introspection (used by the plugin runner's form). |

### Persistence model for particle picks

Each saved picking record is a row in `image_meta_data` with `type=5` and `plugin_id` pointing to the `plugin` row whose `name='pp'`.

```mermaid
erDiagram
    image ||--o{ image_meta_data : has
    plugin ||--o{ image_meta_data : produced_by
    image_job ||--o{ image_job_task : has
    image ||--o{ image_job_task : targets

    image {
        uuid oid PK
        string name
        int dimension_x
        int dimension_y
        uuid session_id FK
    }
    image_meta_data {
        uuid oid PK
        uuid image_id FK
        uuid plugin_id FK
        string name "IPP record name"
        int type "5 for particle picking"
        json data_json "Point array"
    }
    plugin {
        uuid oid PK
        string name "'pp'"
        string version
    }
    image_job {
        uuid oid PK
        string plugin_id "'pp/template-picker'"
        smallint status_id
        json settings
        json processed_json "progress, result"
    }
```

The `Point` array inside `data_json`:

```json
[
  { "x": 1024, "y": 512, "id": "auto-...-0",
    "type": "auto", "confidence": 0.87, "class": "1", "timestamp": 1742000000 },
  ...
]
```

`class` is the id of the frontend particle class (`1=Good, 2=Edge, 3=Contamination, 4=Uncertain`). For auto-picks the controller assigns `class=1` when `score ≥ threshold` and `class=4` otherwise.

### COCO export

`GET /plugins/pp/template-pick/records/{ipp_oid}/coco?radius=<r>` loads the record, joins to `image`, and emits a COCO annotation JSON. Circles are represented as square bboxes (`[cx-r, cy-r, 2r, 2r]`, `area=πr²`, empty segmentation) with non-standard `score`, `pick_type`, `radius` keys preserved for round-trips — the convention used by crYOLO/Topaz converters.

---

## 6. Frontend: the plugin runner page

**File:** `magellon-react-app/src/features/plugin-runner/ui/PluginRunner.tsx`

Purpose: a generic page that can run *any* registered plugin without writing plugin-specific UI. The form is built from the plugin's input schema.

```mermaid
flowchart TB
    A[User opens page] --> B[GET /plugins/]
    B --> C[Pick plugin from list]
    C --> D[GET /plugins/pluginId/schema/input]
    D --> E[SchemaForm renders<br/>fields from JSON Schema]
    E --> F{pp/template-picker?}
    F -- yes --> G[Preview mode:<br/>POST /template-pick/preview]
    F -- no --> H[Submit job:<br/>POST /plugins/pluginId/jobs ?sid=...]
    G --> I[Show score map,<br/>retune with slider]
    H --> J[Job envelope stored<br/>in useJobStore]
    J --> K[Socket.IO job_update<br/>events update progress bar]
```

### Schema-driven forms

**File:** `magellon-react-app/src/features/plugin-runner/ui/SchemaForm.tsx`

Pydantic models add UI hints via `Field(json_schema_extra={...})`. The form reads those hints to pick a widget.

| `ui_widget` | Widget |
|---|---|
| `slider` | MUI Slider with `ui_step`, `ui_marks`, `ui_unit` |
| `number` | TextField type=number |
| `toggle` | Switch |
| `select` | Select with options |
| `file_path` / `file_path_list` | Custom file picker dialog |
| `hidden` | Not rendered (caller fills it, e.g. `image_path`) |

Other keys: `ui_group` (accordion section), `ui_order` (sort within group), `ui_advanced` (collapse under "Advanced"), `ui_tunable` (whether retune supports this field).

---

## 7. Frontend: image-viewer integration

The image viewer doesn't use the generic plugin runner — it embeds `pp/template-picker` in a richer UI (canvas, stats sidebar, undo/redo, manual picks, batch dialog).

**Key files:**

- `features/image-viewer/ui/ParticlePickingTab.tsx` — page layout, class definitions, snackbar.
- `features/image-viewer/ui/ParticleToolbar.tsx` — top bar: picking-record dropdown, tool toggles, zoom, export.
- `features/image-viewer/ui/ParticleCanvas.tsx` — SVG canvas with particles.
- `features/image-viewer/ui/ParticleSettingsDrawer.tsx` — settings panel content (rendered in the app side panel).
- `features/image-viewer/ui/BatchRunDialog.tsx` — session-scoped batch.
- `features/image-viewer/lib/useParticleOperations.ts` — all the state + backend calls.

```mermaid
flowchart TB
    subgraph Tab[ParticlePickingTab]
        TB[ParticleToolbar]
        CV[ParticleCanvas]
        SB[ParticleStatsBar]
        SP[ParticleSettingsPanel<br/>via side-panel slot]
        BD[BatchRunDialog]
    end

    Hook[useParticleOperations<br/>particles, history, runAutoPicking, ...]

    TB -->|onAutoPickRun| Hook
    SP -->|onRun| Hook
    BD -->|POST /template-pick/batch| Backend[pp router]
    Hook -->|POST /template-pick/run-and-save| Backend
    Hook -->|POST /template-pick fallback| Backend
    CV -->|onParticlesUpdate| Hook
    Hook --> CV
    Hook --> SB
```

### Side-panel slot

The settings UI isn't rendered inside the tab — it's *registered* into a global slot (`useSettingsPanelSlot.setContent(...)`) and the app-level `SidePanelArea` renders whichever content is registered when `useSidePanelStore.activePanel === 'settings'`. This is the same mechanism Jobs and Logs use.

### `useParticleOperations` — the central hook

| Field | What it holds |
|---|---|
| `particles` | Current pick list (Point[]) |
| `history` + `historyIndex` | Undo/redo stack |
| `selectedParticles` | Set of selected Point ids |
| `imageShape` | `[height, width]` from backend so canvas sizes its viewBox correctly |
| `stats` | Counts per class, manual/auto split, avg confidence |
| `isAutoPickingRunning`, `autoPickingProgress` | UI progress state |

The hook's `runAutoPicking()` branches on whether the image is in the DB:

```mermaid
flowchart TB
    A[runAutoPicking] --> B{selectedImage.oid<br/>and sessionName?}
    B -- yes --> C["POST /template-pick/run-and-save"]
    C --> D[Row upserted in<br/>image_meta_data]
    D --> E[onIppSaved → reload dropdown]
    B -- no --> F["POST /template-pick<br/>stateless"]
    F --> G[Convert ParticlePick<br/>to Point, append locally]
```

---

## 8. End-to-end flows (sequence diagrams)

### 8.1 Auto-pick on a DB image (run-and-save)

```mermaid
sequenceDiagram
    autonumber
    actor U as User
    participant UI as ParticlePickingTab
    participant Hook as useParticleOperations
    participant API as /plugins/pp/run-and-save
    participant Svc as template_picker.service
    participant FS as filesystem
    participant DB as image_meta_data

    U->>UI: Click Auto-pick
    UI->>Hook: runAutoPicking()
    Hook->>API: POST { session_name, image_oid, ipp_name, picker_params }
    API->>API: authorize session_id
    API->>FS: _resolve_mrc_path(...)
    FS-->>API: /data/.../image.mrc
    API->>Svc: preprocess_templates()
    API->>Svc: pick_in_image(...)
    Svc-->>API: raw_particles, image_shape
    API->>API: convert to Point[]<br/>(class = 1 if score≥threshold else 4)
    API->>DB: upsert image_meta_data<br/>(plugin_id=pp, type=5, data_json=Point[])
    DB-->>API: row
    API-->>Hook: { ipp_oid, ipp_name, num_particles, image_shape }
    Hook->>Hook: setImageShape(...)
    Hook->>UI: onIppSaved() → onParticlePickingLoad()
    UI->>UI: refetch IPP list, dropdown updates
```

No Socket.IO here — it's a single HTTP round-trip. The frontend sees progress ticks (10% → 40% → 70% → 100%) that `runAutoPicking()` sets locally as milestones, not from the server.

### 8.2 Batch run across a session (Socket.IO progress)

```mermaid
sequenceDiagram
    autonumber
    actor U as User
    participant BD as BatchRunDialog
    participant Sock as Socket.IO client
    participant API as /template-pick/batch
    participant JobSvc as JobManager
    participant Task as asyncio task
    participant Svc as template_picker
    participant DB as image_meta_data
    participant SIO as Socket.IO server

    U->>BD: Open dialog, select images, Run
    BD->>Sock: read sid
    BD->>API: POST ?sid=... { session, images[], picker_params, ipp_name }
    API->>JobSvc: create_job(image_ids=[...])
    JobSvc->>DB: INSERT image_job + image_job_tasks
    JobSvc-->>API: envelope (status=queued)
    API->>Task: asyncio.create_task(_run_batch_job(...))
    API-->>BD: envelope (returned immediately)
    BD->>Sock: on('job_update'), on('log_entry')

    Task->>JobSvc: mark_running(progress=1)
    JobSvc-->>Task: envelope
    Task->>SIO: emit_job_update(sid, envelope)
    SIO-->>Sock: job_update
    Sock-->>BD: progress=1

    Task->>Svc: preprocess_templates() [once]

    loop for each image
        Task->>Svc: pick_in_image(...)
        Svc-->>Task: raw_particles, shape
        Task->>DB: upsert image_meta_data
        Task->>JobSvc: update_progress(progress, num_items)
        Task->>SIO: emit_job_update + emit_log
        SIO-->>Sock: events
        Sock-->>BD: progress bar, per-image log line
    end

    Task->>JobSvc: complete_job(result=BatchPickResult)
    Task->>SIO: emit_job_update(status=completed, result)
    SIO-->>Sock: final job_update
    Sock-->>BD: show "9/10 succeeded", close spinner
```

### 8.3 Preview / retune on the plugin runner page

```mermaid
sequenceDiagram
    autonumber
    actor U as User
    participant PR as PluginRunner page
    participant API as /template-pick/preview
    participant Cache as TTL cache (10 min)
    participant Svc as algorithm.pick_particles

    U->>PR: Pick templates, set params, Preview
    PR->>API: POST /preview { image_path, templates, params }
    API->>Svc: expensive FFT correlation
    Svc-->>API: template_results, merged score map
    API->>Cache: store(preview_id, results)
    API-->>PR: { preview_id, particles, score_map_png_base64 }
    PR->>PR: render score map + picks overlay

    loop while user drags threshold slider
        U->>PR: slide threshold
        PR->>API: POST /preview/{preview_id}/retune { threshold, max_peaks, ... }
        API->>Cache: get(preview_id)
        Cache-->>API: cached maps
        API->>API: re-extract + merge (no FFT)
        API-->>PR: { particles } (<100ms typical)
        PR->>PR: update overlay
    end

    U->>PR: Close
    PR->>API: DELETE /preview/{preview_id}
```

---

## 9. Data shapes cheat sheet

### Job envelope (Socket.IO + HTTP)
```json
{
  "job_id": "uuid",
  "plugin_id": "pp/template-picker",
  "status": "queued|running|completed|failed",
  "progress": 0,
  "num_items": 0,
  "settings": { "...": "..." },
  "result": { "...": "..." }
}
```

### Log entry
```json
{
  "id": "log-1742000000000",
  "timestamp": "10:30:45",
  "level": "info|warning|error",
  "source": "batch-picking",
  "message": "[3/10] image_003.mrc: done (142 particles)"
}
```

### Point (frontend + `data_json`)
```json
{
  "x": 1024,
  "y": 512,
  "id": "auto-1742000000000-0",
  "type": "manual|auto|suggested",
  "confidence": 0.87,
  "class": "1",
  "timestamp": 1742000000000
}
```

### COCO annotation (export)
```json
{
  "id": 1,
  "image_id": 1,
  "category_id": 1,
  "bbox": [1009.0, 497.0, 30.0, 30.0],
  "area": 706.858,
  "segmentation": [],
  "iscrowd": 0,
  "score": 0.87,
  "pick_type": "auto",
  "radius": 15.0
}
```

---

## 10. File index

### Backend

| Concern | File |
|---|---|
| Plugin base class | `CoreService/plugins/base.py` |
| Plugin registry | `CoreService/plugins/registry.py` |
| Generic router | `CoreService/plugins/controller.py` |
| `pp` router | `CoreService/plugins/pp/controller.py` |
| `pp` Pydantic models | `CoreService/plugins/pp/models.py` |
| `pp` algorithm | `CoreService/plugins/pp/template_picker/service.py`, `algorithm.py` |
| Job service | `CoreService/services/job_manager.py` |
| Socket.IO server | `CoreService/core/socketio_server.py` |
| SQLAlchemy models | `CoreService/models/sqlalchemy_models.py` (`Image`, `ImageMetaData`, `ImageJob`, `Plugin`) |
| Plugin enums / info | `CoreService/models/plugins_models.py` (`PluginStatus`, `TaskCategory`, `PluginInfo`) |
| ASGI mount points | `CoreService/main.py` |

### Frontend

| Concern | File |
|---|---|
| Plugin runner page | `magellon-react-app/src/features/plugin-runner/ui/PluginRunner.tsx` |
| Plugin API client | `magellon-react-app/src/features/plugin-runner/api/PluginApi.ts` |
| Schema-driven form | `magellon-react-app/src/features/plugin-runner/ui/SchemaForm.tsx` |
| Particle picking tab | `magellon-react-app/src/features/image-viewer/ui/ParticlePickingTab.tsx` |
| Particle operations hook | `magellon-react-app/src/features/image-viewer/lib/useParticleOperations.ts` |
| Batch run dialog | `magellon-react-app/src/features/image-viewer/ui/BatchRunDialog.tsx` |
| Particle toolbar | `magellon-react-app/src/features/image-viewer/ui/ParticleToolbar.tsx` |
| Socket.IO provider | `magellon-react-app/src/shared/lib/SocketProvider.tsx`, `useSocket.ts` |
| Job store | `magellon-react-app/src/app/layouts/PanelLayout/useJobStore.ts` |
| Side-panel stores | `magellon-react-app/src/app/layouts/PanelLayout/useBottomPanelStore.ts`, `useSettingsPanelSlot.ts` |

### Related docs

- `CoreService/docs/plugin-developer-guide.md` — how to write a new plugin step-by-step.
- `CoreService/docs/architecture/EVENT_ARCHITECTURE.md` — broader Socket.IO event catalogue.
- `CoreService/docs/architecture/WORKFLOW_ARCHITECTURE.md` — pipeline/workflow orchestration (supersedes single-plugin jobs).


---

<!--
  Section: 2. Plugin Archive Format (.mpn)
  Originated from: Documentation/PLUGIN_ARCHIVE_FORMAT.md
  Merged into this consolidated reference 2026-05-13.
-->

# Magellon Plugin Archive Format (`.mpn`)

**Status:** Draft 1, 2026-04-28. Awaiting first archive landed.
**Audience:** Plugin authors building / packing plugins for distribution;
CoreService developers building the install pipeline; hub developers
indexing archives.
**Companion docs:** `MAGELLON_HUB_SPEC.md` (registry server),
`UNIFIED_PLATFORM_PLAN.md` (H3a phase this implements),
`PLUGIN_INSTALL_PLAN.md` (phased implementation plan),
`DATA_PLANE.md` (why broker/GPFS config is NOT in the archive).

This document specifies the on-disk layout and manifest schema of a
Magellon plugin archive. It does **not** specify the install pipeline
that consumes archives — that's `PLUGIN_INSTALL_PLAN.md`.

---

## 1. Why this exists

A Magellon plugin today is a Python project under
`plugins/magellon_*_plugin/` with a Dockerfile, README, and a
`PluginBrokerRunner` in `main.py`. To distribute one — to the hub or
direct between teams — we need a **single shippable file** with:

- Self-describing metadata (so the hub can index it without
  unpacking)
- A manifest that pins compatibility (SDK version, category)
- Both install paths in one bundle: the Dockerfile *and* the source
  for `uv` install
- File-level checksums so the install controller can detect tampering
- A stable extension (`.mpn`, "Magellon plugin")

The archive format is **frozen content** — once a `.mpn` is built,
its contents and hashes don't change. Anything that varies per
deployment (broker host, GPFS root, secrets, active flag) lives
*outside* the archive. See §6.

---

## 2. Layout

A `.mpn` is a zip file. After unzip, the directory tree mirrors a
plugin's working repo today:

```
my_plugin.mpn  (zip)
└── my_plugin/                  # package root, name matches plugin_id slug
    ├── manifest.yaml           # REQUIRED — see §3
    ├── README.md               # REQUIRED — surfaced in plugin manager UI
    ├── LICENSE                 # REQUIRED for community-tier publish
    ├── pyproject.toml          # REQUIRED for uv install path
    ├── uv.lock                 # OPTIONAL but strongly encouraged
    ├── requirements.txt        # OPTIONAL — fallback for non-uv installs
    ├── Dockerfile              # REQUIRED for docker install path (build mode)
    ├── main.py                 # entry point — what `python -m` or container CMD runs
    ├── plugin/                 # plugin code (the PluginBase impl)
    │   ├── __init__.py
    │   └── plugin.py
    ├── service/                # any helper services
    │   └── service.py
    ├── core/                   # plugin's local copy of helpers
    │   └── settings.py
    ├── configs/                # algorithm DEFAULTS only — see §6
    │   └── settings.yml
    ├── schemas/                # auto-emitted from input/output Pydantic models
    │   ├── input.json
    │   └── output.json
    └── tests/                  # plugin's own pytest suite (optional in archive)
```

The reference layout matches `plugins/magellon_fft_plugin/` 1:1 —
`magellon-sdk plugin pack` reads exactly that shape.

**What's NOT in the archive:** see §6.

---

## 3. Manifest

The manifest is `manifest.yaml` at the package root. It's loaded as
the Pydantic model
`magellon_sdk.archive.manifest.PluginArchiveManifest`.

### 3.1 Identity

Two distinct ids — both required:

| Field | Type | Purpose |
|---|---|---|
| `plugin_id` | string slug (lowercase, dashes, no spaces) | Human-readable identity. Used in subjects (`magellon.plugins.heartbeat.ctf.ctffind4`), provenance (`TaskResultMessage.plugin_id`), log lines, UI labels. **Stable across versions.** |
| `archive_id` | UUID v7 | Machine identity for this *one specific build*. Time-sortable so the hub can list "newest first" without a separate index. **New per build** — `magellon-sdk plugin pack` generates one. |

Why two: changing `plugin_id` to a UUID would make every log entry
unreadable. UUID is right for the hub's storage; slug is right for
human-facing surfaces. PyPI does the same split (`requests` =
package name, wheel hash = unique fingerprint).

### 3.2 Required fields

```yaml
manifest_version: "1"           # so future schema changes don't break old archives

plugin_id: ctffind4             # slug — see §3.1
archive_id: 0193b1c1-7e8a-7f1d-9b2e-...  # UUID v7

name: "CTFfind v4 — CTF Estimation"
version: "1.2.3"                # SemVer
requires_sdk: ">=2.0,<3.0"      # CoreService SDK SemVer range — refused on mismatch

author: "Magellon Team <team@magellon.io>"
license: "MIT"                  # SPDX identifier
created: "2026-04-28T15:00:00Z"
updated: "2026-04-28T15:00:00Z"

# Plugin classification — both required, must match an existing TaskCategory
category: ctf                   # lowercase TaskCategory name
backend_id: ctffind4            # substitutable identity within category (Track C)

# What the plugin needs from the host. Install controller refuses to
# install if any required deployment surface isn't available.
requires:
  - broker                      # plugin uses bus.tasks / bus.events
  - gpfs                        # plugin reads/writes MAGELLON_HOME_DIR
  # rarer: db (in-process plugins that touch ImageJob directly — discouraged)

# Resource hints — install controller uses these to pick a host.
resources:
  cpu_cores: 4
  memory_mb: 8192
  gpu_count: 0                  # 0 = no GPU needed; nonzero = require nvidia
  gpu_memory_mb: null
  typical_duration_seconds: 90

# Schemas (relative paths into the archive)
input_schema: schemas/input.json
output_schema: schemas/output.json

# Install methods — ORDERED list of preferences. Install controller
# walks top-to-bottom and uses the first one whose `requires:`
# predicates the host satisfies. See §4.
install:
  - method: docker
    image: ghcr.io/magellon/ctffind4:1.2.3   # pre-built — fastest install
    requires:
      - docker_daemon
  - method: docker
    dockerfile: Dockerfile                    # build path — slower fallback
    build_context: .
    requires:
      - docker_daemon
  - method: uv
    pyproject: pyproject.toml
    requires:
      - python: ">=3.11"
      - binary: ctffind4                      # PATH probe — must exist

# Health-check contract for the install controller's smoke test
health_check:
  timeout_seconds: 30           # plugin must announce within this window
  expected_announce: true        # liveness registry sees announce

# UI integration. v1 only allows null OR a docs URL. Custom React
# components are reserved for v2 (post-trust-tier hub work).
ui: null

# File integrity — populated by `magellon-sdk plugin pack`.
# install controller verifies these BEFORE running anything.
checksum_algorithm: sha256
file_checksums:
  manifest.yaml: "<self-checksum-line-omitted-from-its-own-content>"
  README.md: "abc123..."
  pyproject.toml: "def456..."
  # ... every file in the archive listed
```

### 3.3 Optional fields

- `copyright: "Copyright 2026 Magellon Team"`
- `description: "Estimates contrast transfer function via ctffind4"` —
  long-form; surfaced in plugin-manager card
- `homepage: "https://github.com/magellon/ctffind4-plugin"`
- `tags: ["cryo-em", "ctf", "ctffind"]` — search keywords for hub
- `replaces: []` — plugin_ids this archive supersedes (rare; for
  forks)
- `deprecates: []` — plugin_ids this archive marks obsolete

### 3.4 Validation

The Pydantic model rejects:
- `manifest_version` not in the supported set
- `plugin_id` containing whitespace, uppercase, or non-`[a-z0-9-]`
- `archive_id` not a valid UUID v7
- `version` not parseable as SemVer
- `requires_sdk` not a valid SemVer range
- `category` not in the known `TaskCategory` enum
- `install` empty (must have at least one method)
- Two install entries with the same `(method, predicates)` shape

`magellon-sdk plugin pack` runs validation locally before producing
the `.mpn`. The hub re-validates on upload. The install controller
re-validates on install. Three checkpoints because each catches a
different class of mistake.

---

## 4. Install methods

Each entry in `install:` is one viable installation path. Order is
preference, not branching — the controller picks **one** at install
time based on `requires:` satisfaction.

### 4.1 `method: docker`

Two sub-modes:

| Sub-mode | Manifest fields | Behavior |
|---|---|---|
| Pre-built image | `image: <ref>` | `docker pull <ref>` then run |
| Build from source | `dockerfile: <path>`, `build_context: <path>` | `docker build` then run |

If both `image:` and `dockerfile:` are set, the install controller
prefers `image:` (faster). Plugin authors who want a guaranteed
reproducible build skip `image:` and ship only `dockerfile:`.

The container is run with:
- `MAGELLON_HOME_DIR` mounted (the GPFS root, deployment-supplied)
- Broker connection env vars (deployment-supplied; see §6)
- An auto-generated container name `magellon-plugin-<plugin_id>-<short>`

### 4.2 `method: uv`

Unpacks the archive's source under
`<coreservice>/plugins/installed/<plugin_id>/`, then:

```
uv venv <plugins-dir>/<plugin_id>/.venv
uv pip install --python <venv>/python --requirement pyproject.toml
```

Each plugin gets its **own venv** — a plugin pinning `numpy<1.20`
must not downgrade CoreService's numpy. CoreService spawns the
plugin process pointing at the venv's Python:

```
<venv>/python <plugins-dir>/<plugin_id>/main.py
```

with deployment env vars set the same way as the Docker path.

### 4.3 `method: subprocess` (reserved for v2)

Spawn-per-task model for legacy binaries that don't speak the bus
directly. Not implemented in v1.

### 4.4 `requires:` predicates

The host condition the install controller checks. Each predicate is
one key with a value:

| Predicate | Value | Check |
|---|---|---|
| `docker_daemon` | bool | `docker info` succeeds |
| `binary` | string | binary present on PATH |
| `python` | SemVer range | `python --version` matches |
| `gpu_count_min` | int | nvidia-smi reports ≥ this many GPUs |
| `os` | `linux` / `windows` / `macos` | `platform.system()` matches |
| `arch` | `x86_64` / `arm64` | `platform.machine()` matches |

A predicate that's not in this list fails closed (refuses the
install). The install controller logs which predicates failed for
operator debugging.

---

## 5. UI integration

### 5.1 v1 — schema-driven only

The plugin's `schemas/input.json` (Pydantic-emitted JSON Schema) is
read by the React app and rendered as a form. This already works
today via `GET /plugins/{id}/schema/input`. Most plugins (CTF,
MotionCor, FFT) only need this — fields with sensible types and
labels.

In manifest: `ui: null`.

### 5.2 v2 — custom React components (deferred)

Some plugins want richer UI: particle-picker's interactive canvas,
heatmap displays, custom validation widgets. Loading arbitrary JS
from arbitrary plugins is a security concern that needs the trust
tier from H3b/c before it's safe. Until then:

- `ui: { docs_url: "https://..." }` — plugin manager renders a "Open
  docs" link to the plugin author's external page

When v2 lands, `ui:` will gain optional fields like `bundle:
ui/dist/`, `entry: index.js`, `mount: { route: "/plugins/ctffind4" }`
— but those are NOT supported in v1 archives. Hub upload rejects them.

---

## 6. What does NOT go in the archive

This is the most-violated part of the spec, called out explicitly so
plugin authors don't try to bake deployment-specific values into
their archives.

| Surface | Why NOT in archive | Where it actually lives |
|---|---|---|
| Broker host, port, credentials, vhost | Same for every plugin on a CoreService; secret | `BaseAppSettings.rabbitmq_settings`, env vars |
| Database URL / credentials | Same; secret | Env vars |
| `MAGELLON_HOME_DIR` / GPFS root | Per-deployment | Env var; mounted into containers |
| Active / disabled flag | Operational state, not plugin definition | CoreService DB; toggled via admin UI |
| Per-deployment algorithm overrides | Operator's call | Bus push (`ConfigUpdate`) — see `BROKER_PATTERNS.md` §4 + §8.3 |
| Container resource limits (cpu, mem caps) | Deployment policy | Docker Compose / K8s manifests |
| Network policy (which queues this replica binds) | Operational | Plugin's `settings_*.yml` overrides |

The archive **declares what the plugin needs** (via `requires:`); the
deployment **provides the values** (via env / mount / config push).

This split is non-negotiable. Putting broker credentials inside a
`.mpn` published to a community hub leaks production secrets the
moment someone re-uploads.

### 6.1 What about the plugin's own algorithm defaults?

Algorithm defaults (e.g., `max_resolution: 5.0`, `iterations: 10`)
DO go in the archive — under `configs/settings.yml`. They're the
plugin's baked-in starting point. The deployment can override via
the `PluginConfigResolver` precedence chain:

```
defaults (archive) → YAML (deployment) → env vars → bus push (runtime)
```

So algorithm defaults travel with the plugin; tuning travels with
the deployment.

---

## 7. Examples

### 7.1 Minimal — FFT-grade pure-Python plugin

```yaml
manifest_version: "1"
plugin_id: fft-numpy
archive_id: 0193b1c2-1234-7abc-9def-...
name: "FFT (numpy reference)"
version: "0.2.0"
requires_sdk: ">=2.0,<3.0"
author: "Magellon Team"
license: "MIT"
created: "2026-04-28T15:00:00Z"
updated: "2026-04-28T15:00:00Z"
category: fft
backend_id: numpy
requires: [broker, gpfs]
resources:
  cpu_cores: 1
  memory_mb: 512
  gpu_count: 0
input_schema: schemas/input.json
output_schema: schemas/output.json
install:
  - method: uv
    pyproject: pyproject.toml
    requires:
      - python: ">=3.11"
health_check:
  timeout_seconds: 15
  expected_announce: true
ui: null
checksum_algorithm: sha256
file_checksums:
  # populated by `plugin pack`
```

### 7.2 Heavy — CTF with Docker preferred + uv fallback

```yaml
manifest_version: "1"
plugin_id: ctffind4
archive_id: 0193b1c2-5678-7def-...
name: "CTFfind v4"
version: "4.1.14"
requires_sdk: ">=2.0,<3.0"
author: "Magellon Team"
license: "BSD-3-Clause"
created: "2026-04-28T15:00:00Z"
updated: "2026-04-28T15:00:00Z"
category: ctf
backend_id: ctffind4
requires: [broker, gpfs]
resources:
  cpu_cores: 4
  memory_mb: 8192
  gpu_count: 0
  typical_duration_seconds: 60
input_schema: schemas/input.json
output_schema: schemas/output.json
install:
  - method: docker
    image: ghcr.io/magellon/ctffind4:4.1.14
    requires: [docker_daemon]
  - method: docker
    dockerfile: Dockerfile
    build_context: .
    requires: [docker_daemon]
  - method: uv
    pyproject: pyproject.toml
    requires:
      - python: ">=3.11"
      - binary: ctffind4
health_check:
  timeout_seconds: 60
  expected_announce: true
ui: null
checksum_algorithm: sha256
file_checksums:
  # populated by `plugin pack`
```

A host with no Docker daemon installs via uv if `ctffind4` is on
PATH; a host with Docker uses the pre-built image; a host with
Docker but a custom build pulls the source and `docker build`s.
Plugin author writes the manifest once; deployment heterogeneity is
absorbed by the controller.

---

## 8. Versioning

The archive format itself is versioned via `manifest_version`. v1
is what this document specifies. Breaking changes to the format
require:

1. A new `manifest_version` value
2. A new pass in the install controller that handles the new shape
3. A migration note for plugin authors

Within v1, additive optional fields can land at any time (the
Pydantic model uses `extra="ignore"` so unknown fields don't break
old controllers reading new manifests).

---

## 9. Companion specs

- **Hub indexing**: `MAGELLON_HUB_SPEC.md` §4 — the hub's
  `index.json` lists every available archive's `archive_id`,
  `plugin_id`, `version`, SHA256, and download URL. Install
  controller fetches the index, downloads the archive, verifies
  hash, then runs the install pipeline.
- **Install pipeline**: `PLUGIN_INSTALL_PLAN.md` — the multi-phase
  plan to build the controller, the CLI tools, the test harness,
  and the admin UI.
- **Trust model**: `MAGELLON_HUB_SPEC.md` §6 — verified vs community
  tier, signature verification (post-v1).


---

<!--
  Section: 3. Plugin Install Pipeline
  Originated from: Documentation/PLUGIN_INSTALL_PLAN.md
  Merged into this consolidated reference 2026-05-13.
-->

# Plugin Install Pipeline — Phased Plan

**Status:** Proposal, 2026-04-28.
**Scope:** Build the archive creator, the install controller, and
the operator surfaces that consume `.mpn` archives. The hub is a
separate track that depends on this work but doesn't block it.
**Companion docs:** `PLUGIN_ARCHIVE_FORMAT.md` (the spec this plan
implements), `MAGELLON_HUB_SPEC.md` (the registry server, separate
track), `UNIFIED_PLATFORM_PLAN.md` H2/H3a (the higher-level phases
this plan refines).

---

## 0. Why phased

Three cuts give an end-to-end demo without a hub or a UI:

1. **Pack a plugin → get a `.mpn` file.** Plugin author surface.
2. **Install a `.mpn` from a local file.** CoreService surface.
3. **Uninstall + reinstall a different version.** Lifecycle.

Each lands in a few PRs. Each is independently testable against the
existing FFT plugin. No phase requires the next; if hub work
slips, install-from-local-file keeps working.

The hub-facing work (download from URL, verify against hub's
index.json, admin-gated approve flow) lands after this plan
completes — see §10.

---

## 1. Phase order

| # | Phase | Output | Days* |
|---|---|---|---|
| **P1** | Archive format spec lands | This + `PLUGIN_ARCHIVE_FORMAT.md` + `magellon_sdk.archive.manifest` Pydantic model + golden-file tests | 1–2 |
| **P2** | `magellon-sdk plugin pack` CLI | A working CLI that turns the FFT plugin directory into a valid `.mpn` | 1–2 |
| **P3** | FFT as canonical test fixture | `tests/fixtures/fft.mpn` committed; reproducible-build test asserts the pack output | 0.5 |
| **P4** | `Installer` Protocol + `UvInstaller` | CoreService can install the FFT `.mpn` from a local file path; plugin announces and shows up in liveness registry | 2–3 |
| **P5** | `DockerInstaller` | Same Protocol; CTF/MotionCor `.mpn` installs via `docker pull` (image mode) and `docker build` (dockerfile mode) | 2–3 |
| **P6** | Uninstall + version upgrade | `uninstall(plugin_id)` and `upgrade(plugin_id, new_archive)` work for both installer impls; in-flight task drains correctly | 2 |
| **P7** | Admin REST endpoints | `POST /admin/plugins/install`, `DELETE /admin/plugins/{id}`, `POST /admin/plugins/{id}/upgrade`. Casbin Administrator role. | 1–2 |
| **P8** | React plugin manager UI | Browse installed; upload `.mpn`; confirm + install dialog; uninstall button | 2–3 |
| **P9** | Hub integration | `GET /v1/index.json` browse; click "Install" → admin gate → download → run installer | 2–3 |

*Calendar days — assumes one engineer, sequential. P1+P2 can run
in parallel with each other (different files); P4+P5 share the
Protocol, do P4 first.

---

## 2. Phase P1 — Archive format spec + Pydantic model

**Goal:** `from magellon_sdk.archive.manifest import PluginArchiveManifest`
and use it.

**Files:**
- `Documentation/PLUGIN_ARCHIVE_FORMAT.md` (already drafted)
- `magellon-sdk/src/magellon_sdk/archive/manifest.py` —
  `PluginArchiveManifest` Pydantic v2 model with all fields from
  `PLUGIN_ARCHIVE_FORMAT.md` §3
- `magellon-sdk/src/magellon_sdk/archive/__init__.py` — re-exports
- `magellon-sdk/tests/test_archive_manifest.py` — round-trips, validation
  rejections (bad slug, bad UUID v7, bad SemVer, empty install list,
  unknown method)

**Acceptance:**
- All FFT, CTF, MotionCor manifests in
  `Documentation/PLUGIN_ARCHIVE_FORMAT.md` §7 round-trip through the
  model.
- A manifest with `archive_id: "not-a-uuid"` raises ValidationError.
- A manifest with `install: []` raises ValidationError.
- A manifest with `requires_sdk: ">=99.0"` parses (range validation
  happens at install time, not at the Pydantic layer).

**Rollback:** revert; the SDK gains and loses the module cleanly.

---

## 3. Phase P2 — `magellon-sdk plugin pack` CLI

**Goal:** Plugin author runs `cd magellon_fft_plugin && magellon-sdk
plugin pack` and gets `magellon_fft_plugin-0.2.0.mpn`.

**Files:**
- `magellon-sdk/src/magellon_sdk/cli/plugin_pack.py` — the pack
  command implementation
- `magellon-sdk/src/magellon_sdk/cli/main.py` — wire the
  subcommand (currently a stub)
- `magellon-sdk/tests/test_plugin_pack.py`

**Behavior:**
1. Read `manifest.yaml` from the current directory; validate against
   the Pydantic model (P1).
2. Auto-emit `schemas/input.json` and `schemas/output.json` from
   the plugin's Pydantic models (`plugin.py:input_schema` /
   `output_schema`). Author doesn't hand-maintain these.
3. Compute SHA256 of every file that will be in the archive.
4. Generate a UUID v7 if `archive_id` is missing or `auto`.
5. Stamp `created` / `updated` (preserve `created` from any prior
   build; always update `updated`).
6. Populate `file_checksums` and write the final manifest into the
   zip.
7. Output: `<plugin_id>-<version>.mpn`, with size + hash printed.

**Acceptance:**
- Running pack on `plugins/magellon_fft_plugin/` produces a `.mpn`
  whose manifest validates against the Pydantic model and whose
  `file_checksums` match every file in the zip.
- Running pack twice in a row produces archives with the same
  `file_checksums` (provided source files unchanged) — reproducible
  build property.
- A plugin with a malformed `manifest.yaml` exits nonzero with a
  pointed error.

**Rollback:** revert; the pack subcommand goes back to its current
stub.

---

## 4. Phase P3 — FFT as canonical test fixture

**Goal:** Other phases have a known-good `.mpn` to install against
without re-running the pack CLI in every test.

**Files:**
- `CoreService/tests/fixtures/plugins/fft.mpn` — committed binary
- `CoreService/tests/fixtures/plugins/Makefile` — one-liner to
  rebuild it from source (`magellon-sdk plugin pack ../../plugins/magellon_fft_plugin`)
- `CoreService/tests/test_plugin_fixture.py` — sanity test: the
  fixture round-trips through the manifest validator, has a
  non-empty file_checksums

**Acceptance:**
- The fixture validates.
- `make -C tests/fixtures/plugins fft.mpn` regenerates an identical
  archive (modulo `archive_id` and timestamps).

**Rollback:** delete the fixture file; tests that depend on it skip.

---

## 5. Phase P4 — `Installer` Protocol + `UvInstaller`

**Goal:** `POST /admin/plugins/install` (P7) calls into a clean
Protocol; FFT installs from `fft.mpn` and shows up live in the
liveness registry.

**Files:**
- `CoreService/services/plugin_installer/__init__.py` — `Installer`
  Protocol, `InstallResult` / `UninstallResult` dataclasses,
  `predicates` module with the host-probe checks (P3 spec §4.4)
- `CoreService/services/plugin_installer/uv_installer.py` —
  `UvInstaller` impl
- `CoreService/services/plugin_installer/manager.py` —
  `PluginInstallManager` orchestrator: validates archive, picks
  install method, dispatches to the right `Installer`, runs the
  health check, registers the plugin
- `CoreService/tests/services/test_uv_installer.py`

**`Installer` Protocol:**

```python
class Installer(Protocol):
    method: ClassVar[str]  # "uv", "docker", "subprocess"

    def supports(self, install_spec: InstallSpec, host: HostInfo) -> bool: ...

    def install(self, archive_dir: Path, manifest: PluginArchiveManifest, runtime: RuntimeConfig) -> InstallResult: ...
    def uninstall(self, plugin_id: str) -> UninstallResult: ...
    def is_installed(self, plugin_id: str) -> bool: ...
```

`RuntimeConfig` carries the deployment-supplied values (broker,
GPFS root, etc.) — the plugin's archive doesn't have these, the
installer injects them when it spawns the plugin process.

**UvInstaller behavior:**
1. Unzip `<archive>` to `<coreservice>/plugins/installed/<plugin_id>/`.
2. `uv venv .venv` in that directory.
3. `uv pip install -r requirements.txt` (or `pyproject.toml` if no
   requirements.txt).
4. Write `<plugins_dir>/<plugin_id>/runtime.env` with the resolved
   broker / GPFS values.
5. Spawn the plugin: `<venv>/python main.py` with the env loaded
   from `runtime.env`. Track the PID.
6. Wait for announce on the bus (with the manifest's
   `health_check.timeout_seconds`); return `InstallResult.success`
   or `failure_with_logs`.
7. On uninstall: stop the process (SIGTERM, then SIGKILL after
   grace), remove the directory.

**Acceptance:**
- `manager.install(fft.mpn)` lands the plugin live in the liveness
  registry within the health-check window.
- A simulated bus task (via in-memory binder OR real RMQ if
  available) routes to the installed FFT and gets a result.
- `manager.uninstall("fft-numpy")` stops the process and removes
  the directory; subsequent `is_installed` returns False.
- Re-installing without uninstalling first raises a typed error
  ("already installed; use upgrade").
- Health-check timeout produces a clean failure with the plugin's
  stdout/stderr captured.

**Rollback:** revert; admin endpoints go back to no-op stubs.

---

## 6. Phase P5 — `DockerInstaller`

**Goal:** Same Protocol as P4, different execution path. CTF or
MotionCor `.mpn` installs via Docker.

**Files:**
- `CoreService/services/plugin_installer/docker_installer.py`
- `CoreService/tests/services/test_docker_installer.py` — uses
  Docker SDK; skips cleanly when no daemon

**DockerInstaller behavior:**
1. Two sub-modes per `install` entry:
   - `image:` set → `docker pull <image>` (no build needed)
   - `dockerfile:` set → `docker build` from the unpacked archive
     directory
2. Run the container with the runtime config:
   - Mount `MAGELLON_HOME_DIR` at the deployment-configured path
   - Pass broker connection as env vars
   - Container name `magellon-plugin-<plugin_id>-<short>`
   - `--network` matches CoreService's compose network
3. Health check: same announce wait as P4.
4. Uninstall: `docker stop` + `docker rm` (and `docker rmi` of the
   built image if `dockerfile:` was used; preserve pulled images
   in case they're shared).

**Acceptance:**
- A `.mpn` whose first install entry is `method: docker, image: ...`
  installs by pulling the image when Docker daemon is present.
- A `.mpn` whose only path is `dockerfile:` builds the image from
  the archive's source.
- Skip-clean when Docker daemon absent (matches existing
  `_broker_reachable()` skip pattern in `test_e2e_rabbitmq.py`).

**Rollback:** revert.

---

## 7. Phase P6 — Uninstall + version upgrade

**Goal:** Operator can upgrade ctffind4 from 4.1.14 → 4.2.0 with
zero-downtime semantics for queued tasks.

**Files:**
- `CoreService/services/plugin_installer/manager.py` — gain
  `upgrade(plugin_id, new_archive_path)`
- `CoreService/tests/services/test_install_lifecycle.py`

**`upgrade` semantics:**
1. Validate new archive's `plugin_id` matches the installed one.
2. Validate new `version` > old version (SemVer); bypass with
   `--force-downgrade` flag if operator wants it.
3. Install the new version under
   `<plugins_dir>/installed/<plugin_id>.next/`.
4. Wait for new replica to announce.
5. Drain old: stop accepting new tasks (cooperative — flip a flag in
   the dispatcher), wait for in-flight to complete or timeout.
6. Stop old replica.
7. Atomically rename: `<plugin_id>` → `<plugin_id>.<old-version>.bak`,
   `<plugin_id>.next` → `<plugin_id>`.
8. Keep the `.bak` directory for one upgrade cycle (rollback
   surface), then GC it on the next `upgrade`.

**Acceptance:**
- Upgrade FFT 0.2.0 → 0.3.0 with 5 in-flight tasks: all 5 finish on
  0.2.0, the 6th onward run on 0.3.0.
- Failed upgrade (new version's health-check times out) leaves the
  old version live and untouched. `.next` directory cleaned up.
- Rollback (manual): operator runs upgrade with the `.bak` archive.

**Rollback:** revert; operators upgrade via uninstall-then-install
manually.

---

## 8. Phase P7 — Admin REST endpoints

**Goal:** Operator CLI / curl / Postman flow works.

**Files:**
- `CoreService/controllers/admin/plugin_install_controller.py`
- `CoreService/tests/controllers/test_plugin_install_controller.py`

**Endpoints:**

| Method | Path | Casbin role | Body | Response |
|---|---|---|---|---|
| `POST` | `/admin/plugins/install` | Administrator | `multipart: file=<.mpn>` OR `json: {url}` | `InstallResult` |
| `DELETE` | `/admin/plugins/{plugin_id}` | Administrator | — | `UninstallResult` |
| `POST` | `/admin/plugins/{plugin_id}/upgrade` | Administrator | same as install | `InstallResult` |
| `GET` | `/admin/plugins/installed` | Administrator | — | List of installed plugins (id, version, install method, status) |
| `POST` | `/admin/plugins/{plugin_id}/active` | Administrator | `json: {active: bool}` | toggles the active flag in CoreService DB (the H1 active/inactive contract) |

**Acceptance:**
- Casbin denies non-Administrator users (403).
- Upload of an invalid `.mpn` (bad checksum, malformed manifest)
  returns 400 with the validator's error.
- Successful install returns 201 with the registered plugin's
  manifest snapshot.
- DELETE on a non-existent plugin returns 404.

**Rollback:** revert; operators install via direct manager calls
in a Python REPL (the dev path).

---

## 9. Phase P8 — React plugin manager UI

**Goal:** End-user surface — admin opens the plugin manager, sees
installed plugins, uploads a `.mpn`, confirms, sees the new plugin
appear live.

**Files:**
- `magellon-react-app/src/features/plugin-manager/` — new feature
  module per the FSD layout
- Pages: `InstalledPluginsPage.tsx`, `InstallPluginDialog.tsx`,
  `PluginDetailDrawer.tsx`
- API client: `services/admin/plugins-api.ts`

**Flows:**
1. **Browse installed**: list with name, version, category,
   backend_id, install method, last heartbeat, active toggle.
2. **Install from local file**: file picker → upload progress → confirmation
   modal showing parsed manifest → install button.
3. **Install from URL**: paste URL → CoreService fetches → same
   confirmation flow. (Hub flow extends this in P9.)
4. **Upgrade**: click "Upgrade" on a plugin → file/URL picker →
   diff-style display (old version vs new) → confirm.
5. **Uninstall**: confirmation modal with consequences ("3 in-flight
   tasks will be allowed to complete; new tasks rejected"); admin
   confirms.

**Acceptance:**
- Admin can install FFT `.mpn` end-to-end through the UI without
  using curl.
- Active toggle reflects in the dispatcher's routing within one
  heartbeat tick.
- Non-admin users see a "you don't have permission" page (Casbin).

**Rollback:** revert; admins use the REST endpoints directly.

---

## 10. Phase P9 — Hub integration

**Goal:** `GET /v1/index.json` from the hub feeds a "Browse remote"
tab in the plugin manager. Admin clicks "Install" → CoreService
downloads, verifies against the hub's SHA256, runs the install
pipeline.

This phase **depends on the hub being deployed** (per
`MAGELLON_HUB_SPEC.md`). Until that lands, P8's "Install from URL"
path covers the gap manually (admin pastes any URL pointing at a
`.mpn`).

**Files:**
- `CoreService/services/plugin_installer/hub_client.py` — typed
  client for the hub REST API
- `magellon-react-app/src/features/plugin-manager/hub-browse/`

**Flows:**
1. **Browse remote**: fetch `index.json`, render searchable list
   (filter by category, sort by version / popularity if available).
2. **Plugin detail**: fetch `<hub>/v1/plugins/{plugin_id}`, render
   README, manifest summary, version history.
3. **Install from hub**: download archive → verify SHA256 against
   hub-supplied hash → run installer → register.

**Trust:** v1 reads the hub's `verified` / `community` tier; UI
warns visibly when installing community-tier. Signature
verification is post-v1 (depends on the hub adding a signing flow
per `MAGELLON_HUB_SPEC.md` §6).

**Acceptance:**
- A hub-published FFT plugin installs end-to-end through the UI.
- A tampered archive (operator-supplied URL hash mismatch) is
  refused with a clear error.

**Rollback:** revert the UI tab; manual `POST /admin/plugins/install`
with a hub-style URL still works.

---

## 11. Test strategy

| Layer | Lives in | Runs when |
|---|---|---|
| Manifest validation | `magellon-sdk/tests/test_archive_manifest.py` | SDK CI |
| Pack CLI | `magellon-sdk/tests/test_plugin_pack.py` | SDK CI |
| UvInstaller | `CoreService/tests/services/test_uv_installer.py` | CoreService CI |
| DockerInstaller | `CoreService/tests/services/test_docker_installer.py` | CoreService CI (skips without Docker daemon) |
| Lifecycle (install/upgrade/uninstall) | `CoreService/tests/services/test_install_lifecycle.py` | CoreService CI |
| Admin endpoints | `CoreService/tests/controllers/test_plugin_install_controller.py` | CoreService CI |
| End-to-end against in-memory bus | `CoreService/tests/integration/test_plugin_install_e2e.py` | CoreService CI |
| End-to-end against real RMQ | `CoreService/tests/integration/test_plugin_install_rmq_e2e.py` | CoreService CI (skips without broker) |
| UI flows | `magellon-react-app/tests/e2e/plugin-manager.spec.ts` | frontend CI |

The FFT plugin is the canonical happy-path fixture across all
layers — pack it once in P3, every later phase reads the same
`.mpn`.

---

## 12. What we're NOT building

Carving these out so the plan stays scoped:

- **Cross-deployment plugin sharing** (federation between hubs).
  Single-hub MVP first. Per `MAGELLON_HUB_SPEC.md`.
- **Sandboxing beyond Docker isolation.** uv-installed plugins
  share the host process namespace. cgroups / seccomp is hub-tier
  community-plugin work, not foundation.
- **Plugin marketplace ranking / popularity.** Ship discovery
  first; metrics second.
- **Custom React component injection.** Reserved for v2 archive
  format; see `PLUGIN_ARCHIVE_FORMAT.md` §5.2.
- **Multi-language plugins.** Python-only in v1. The contract is
  JSON-serializable, so cross-language is possible later but
  premature today.
- **Live-migration / rolling restart with zero in-flight loss.**
  Upgrade has a small drain window. Zero-downtime is overkill for a
  cryo-EM workload where tasks are minutes-long anyway.

---

## 13. First move

Start with **P1 + P2 in one session** (sequential, but small):
write the Pydantic model, write the pack CLI, dogfood by packing
FFT. The result is a real `.mpn` you can hand-inspect, which makes
the rest of the design concrete instead of theoretical.

Then **P3 + P4**: commit the FFT fixture, build UvInstaller against
it, watch the plugin appear in the liveness registry.

After that the docker / lifecycle / endpoints / UI phases are
mechanical — every one of them reads the `.mpn` the same way.


---

<!--
  Section: 4. Plugin Manager
  Originated from: Documentation/PLUGIN_MANAGER_PLAN.md
  Merged into this consolidated reference 2026-05-13.
-->

# Plugin Manager — Phased Plan

**Status:** Proposal, 2026-05-03 (revised 2026-05-04 per reviewer feedback).
**Audience:** Reviewers, ops + frontend team, operators.

**Revision 2026-05-04** — fixes nine reviewer-flagged issues from the
first pass: identity layering, multi-category default routing,
liveness re-keying (current state was misread), Healthy reducer's
data source, pause-vs-disable semantics, alembic split, installed
inventory accuracy, PM7 sub-phasing, PM6 severity example. Each
finding is annotated inline below where it applies.
**Companion docs:**
- `PLUGIN_INSTALL_PLAN.md` (P1–P9 — the **authoring + install** pipeline; complement, not overlap)
- `MAGELLON_HUB_SPEC.md` (the **distribution** registry server)
- `CURRENT_ARCHITECTURE.md` §8 #24–#27 (the 2026-05-03 rollout this plan continues from)
- `memory/project_artifact_bus_invariants.md` (the five ratified rules — same governance applies here)
- `ARCHITECTURE_PRINCIPLES.md` (especially #4 abstractions pay their way today, #6 additive first subtractive second)

This plan is the **runtime / operational** surface — observe, enable / disable, pause / resume, upgrade, uninstall — across the **federated** plugin registries that already exist in Magellon. It does NOT replace the install pipeline (PLUGIN_INSTALL_PLAN P1–P9) or the hub spec; it consumes both.

---

## 0. Identity layers (read first)

Plugin "identity" lives at five distinct layers in this codebase.
Conflating them is the first mistake reviewers found in revision 1;
fixing it shapes every PM phase below. Each layer has one
authoritative carrier:

| Layer | Identifier | Owner | Lifetime |
|---|---|---|---|
| **DB row identity** | `plugin.oid` (UUID) | DB; FK target for `ImageMetaData.plugin_id` and the new `plugin_state.plugin_oid` | Forever; soft-delete via `deleted_date`/`GCRecord` |
| **Install package identity** | `manifest_plugin_id` (string slug from `manifest.yaml`, e.g. `"ctf"`, `"can-classifier"`, `"stack-maker"`) | Plugin author; declared in the archive | Per archive |
| **Dispatch identity** | `(category, backend_id)` — e.g. `(CTF, "ctffind4")`, `(MICROGRAPH_DENOISING, "topaz-denoise")` | The plugin's `PluginManifest`; stamped on every announce | Per announce |
| **Live replica identity** | `instance_id` (UUID per process) | The plugin runner at boot; rotates on restart | Per process |
| **Default routing policy** | `(category, plugin_oid)` row in `plugin_category_default` | Operator decision; survives restart | Persistent, mutable |

Why this matters:

- A plugin can serve **multiple categories** (e.g. topaz serves
  `TOPAZ_PARTICLE_PICKING` AND `MICROGRAPH_DENOISING`). One boolean on
  the plugin row can't say "default for picking, not for denoising".
  → Default policy lives on a separate `plugin_category_default`
  table keyed by `(category, plugin_oid)`. Reviewer-flagged High #1.
- The new `plugin` extensions must NOT add a column called
  `plugin_id` — that name conflicts with `ImageMetaData.plugin_id`
  which is already a FK to `plugin.oid`. The new column is
  `manifest_plugin_id`; FK relationships continue to use
  `plugin.oid`. Reviewer-flagged High #2.
- The SDK's liveness registry is already keyed on `(plugin_id,
  instance_id)` (`magellon-sdk/.../bus/services/liveness_registry.py:137`)
  — replica granularity exists today. Announce + heartbeat use
  `instance_id`, not `worker_instance_id`
  (`magellon-sdk/.../discovery.py:88`). PM5 exposes the data, doesn't
  re-key. Reviewer-flagged High #3.

---

## 0a. Why this plan

Three driving observations:

1. **The Plugin Manager UI already exists** at `/panel/plugins` (`magellon-react-app/src/pages/plugins/PluginsPageView.tsx`). It composes three panels (HubCatalogBrowser → AdminInstalledPanel → PluginBrowser) reading from three different APIs. No replacement is needed; gaps are filled around it.

2. **The state the UI flips is non-persistent.** `PluginStateStore` (`enabled`, `default_impl`) and `InstalledPluginsRegistry` are both in-memory. A CoreService restart silently resets every operator decision. This is the **#1 user-visible bug** — the UI's toggles look durable and aren't.

3. **The `plugin` + `plugin_type` DB tables already exist** (`models/sqlalchemy_models.py:49,155`) — XAF-style schema with `name`, `version`, `author`, `status_id`, `input_json`, full audit columns. Used today only as a sentinel FK target for `ImageMetaData.plugin_id` in `plugins/pp/controller.py:549`. Reusing them is cheaper than adding parallel tables.

The work below adds persistence + Conditions[] + pause/resume + per-replica health + updates view + a thin `PluginManagerService` facade. Each phase is reversible-by-`git revert` per principle 6.

---

## 1. Complete inventory (so reviewers don't have to re-discover)

### 1.1 Backend registries (federated)

| # | Component | Persistence | Source of truth for | Live consumer |
|---|---|---|---|---|
| R1 | `PluginRegistry` (`CoreService/plugins/registry.py:42`) | in-memory, populated by walking `plugins.*` at boot | discovered in-process plugins | `plugins/controller.py::list_plugins` (joins) |
| R2 | `InstalledPluginsRegistry` (`core/installed_plugins.py:23`) | **in-memory, lost on restart** | docker installs from the H2 pipeline | `admin_plugin_install_controller.list_installed`, `services/plugin_installer/manager.py` |
| R3 | `PluginStateStore` (`core/plugin_state.py:28`) | **in-memory, lost on restart** | per-plugin `enabled`, per-category `default_impl` | `plugins/controller.py::list_plugins`, `dispatcher_registry`, every `POST /plugins/{id}/enable\|disable` |
| R4 | `PluginLivenessRegistry` (`magellon-sdk/.../bus/services/liveness_registry.py:125`, plus `core/plugin_liveness_registry.py`) | bus-driven (announce + heartbeat) | what's running right now | `dispatcher_registry`, `plugins/controller.py`, `GET /plugins/capabilities` |
| R5 | `TaskDispatcherRegistry` (`core/dispatcher_registry.py`) | in-memory | `(category, backend_id)` → physical queue routing | every dispatch call site |

### 1.2 Existing DB tables (under-used)

| Table | Defined at | Today's usage | Gap |
|---|---|---|---|
| `plugin` | `sqlalchemy_models.py:155` | One sentinel row with `name='pp'` so `ImageMetaData.plugin_id` FK has a target | One row total in production. Catalog-shaped fields (`name`, `version`, `author`, `type_id`, `status_id`, `input_json`) sit unused. |
| `plugin_type` | `sqlalchemy_models.py:49` | Lookup table; populated minimally if at all | Available — would distinguish e.g. `image-task`, `aggregate-task`, `result-processor`. |

The XAF audit columns on `plugin` (`created_by` FK, `last_modified_by` FK, `OptimisticLockField`, `GCRecord`) are real — installs from the admin pipeline have a Casbin-authenticated user already, so threading the user_id through is mechanical.

### 1.3 Backend HTTP surface (already shipped)

#### Runtime / dispatch — `plugins_router` (`plugins/controller.py`)
- `GET    /plugins/` — joined list (R1 ∪ R3 ∪ R4 + manifest)
- `GET    /plugins/{id}/info|manifest|health|requirements`
- `GET    /plugins/{id}/schema/input|output`
- `POST   /plugins/{id}/jobs` / `POST /plugins/{id}/jobs/batch`
- `GET    /plugins/jobs` / `GET /plugins/jobs/{job_id}` / `DELETE /plugins/jobs/{job_id}`
- `GET    /plugins/capabilities` (Track C — single consolidated read)
- `POST   /plugins/{id}/enable` / `POST /plugins/{id}/disable`
- `GET    /plugins/categories/defaults` / `POST /plugins/categories/{c}/default`

#### Admin install — `admin_plugin_install_router` (`admin_plugin_install_controller.py`)
- `POST   /admin/plugins/install` — multipart `.mpn` upload
- `POST   /admin/plugins/{id}/upgrade` — multipart upload, optional `force_downgrade`
- `DELETE /admin/plugins/{id}` — uninstall (stop + remove dir)
- `GET    /admin/plugins/installed` — calls `PluginInstallManager.list_installed()` which **scans the installer's directory tree on disk** (`services/plugin_installer/manager.py:399`); does NOT read R2. Reviewer-flagged Medium #7. R2 is a separate H2-era container registry consumed by the docker runner; the two surfaces co-exist and PM1 consolidates them onto the persisted `plugin` table.
- `GET    /admin/plugins/{id}` — describe one installed plugin

#### Pipeline rollup — `pipelines_router` (`pipelines_controller.py`, Phase 8b 2026-05-03)
- `POST   /pipelines/runs`, `GET /pipelines/runs/{id}`, `GET /pipelines/runs`, `DELETE /pipelines/runs/{id}`

### 1.4 Frontend (already shipped)

`magellon-react-app/src/pages/plugins/PluginsPageView.tsx` composes three feature panels:

| Panel | Component | API hooks | Backed by |
|---|---|---|---|
| Hub catalog (top) | `HubCatalogBrowser.tsx` | `hubApi.ts` | `<HUB_URL>/v1/index.json` (default `https://demo.magellon.org`) |
| Admin installed (middle) | `AdminInstalledPanel.tsx` + `UpgradeMpnDialog.tsx` + `HubInstallDialog.tsx` | `installerApi.ts` | `/admin/plugins/*` |
| Runtime browser (bottom) | `PluginBrowser.tsx` | `PluginApi.ts` (`usePlugins`, `useTogglePlugin`, `useSetCategoryDefault`, `useInstalledPlugins`, `useStopInstalled`, `useRemoveInstalled`) | `/plugins/*` |

`PluginRunnerPageView.tsx` is the per-plugin run page (separate from manager).

### 1.5 Install pipeline phases (per `PLUGIN_INSTALL_PLAN.md`)

P1 archive format → P2 pack CLI → P3 fixture → **P4 Installer Protocol + UvInstaller** (in `services/plugin_installer/`) → **P5 DockerInstaller** → **P6 uninstall + upgrade** → **P7 admin REST endpoints** (shipped, see §1.3) → **P8 React UI** (shipped, see §1.4) → P9 hub integration. So P1–P8 are largely landed; P9 (hub fetch + admin gate) remains the gap on the **install** side.

---

## 2. Gaps (what this plan adds)

| # | Gap | Severity | Named driver |
|---|---|---|---|
| G1 | `PluginStateStore.enabled` and `default_impl` lost on every CoreService restart | **High** (silent UX bug) | Operator clicks "Set ctffind4 as default", restarts CoreService, the choice is gone. |
| G2 | `InstalledPluginsRegistry` in-memory — restart loses the docker-runner mapping | **High** (operational risk) | Docker containers stay running but CoreService no longer knows which `install_id` they belong to. |
| G3 | No unified `Conditions[]` on plugin status — UI implicitly derives liveness from "did it appear in `/plugins/`?" | Medium | A plugin that crashed 4s ago hasn't missed a heartbeat yet; UI shows green; operator dispatches a task that fails. |
| G4 | No `pause` / `resume` verb between `enabled` (refuse new) and `uninstall` (remove from disk) | Medium | Operators reach for SSH + `docker pause` today. The P9 container-kill is the only existing hard-stop. |
| G5 | Per-replica health is aggregated away — liveness keys on `(category, backend_id)` only | Medium | 3 ctffind4 replicas; 1 silently dies; aggregate count drops to 2 with no surface saying which one. |
| G6 | No "1 update available" cross-reference between AdminInstalledPanel and HubCatalogBrowser | Low | UI shows installed and available separately; no badge. |
| G7 | No server-side `PluginManagerService` facade — UI does the four-way join client-side | Low | Server-side callers (dispatcher, programmatic clients) re-implement. ~80 lines of pass-throughs would consolidate. |
| G8 | `plugin` + `plugin_type` DB tables exist but are unused beyond a sentinel | Low (latent) | Catalog-shaped fields are waiting; reusing them avoids parallel-schema drift. |

---

## 3. Phased plan (PM1–PM7)

PR ordering. Each PR is `git revert`-safe. Days assume one engineer, sequential. PM3+PM4+PM6 can interleave once PM1 is in.

| # | Phase | Closes gap | Days | Reversible |
|---|---|---|---|---|
| **PM1** | `plugin` extensions + `plugin_state` + `plugin_category_default` (alembic 0007) — **enabled flag only**, no paused | G1, G2, G8 | 2 | yes (drop columns + 2 tables) |
| **PM2** | `Conditions[]` on `PluginSummary` + `GET /plugins/{id}/status`; Healthy reducer reads `job_event.ts` | G3 | 1–2 | yes |
| **PM3** | `PluginManagerService` facade — server-side join | G7 | 1 | yes |
| **PM4** | Pause / resume / restart — **DEFERRED** until pause semantics are meaningfully distinct from disable (TTL + reason taxonomy) | G4 | TBD | yes (own alembic 0008) |
| **PM5** | Per-replica health — expose existing `(plugin_id, instance_id)` keying via `GET /plugins/{id}/replicas`; no re-key | G5 | 2 | yes (additive) |
| **PM6** | Updates view — installed × hub catalog cross-reference | G6 | 2 | yes |
| **PM7a** | UI: Conditions chips (after PM2) | — | 1 | yes (UI-only) |
| **PM7b** | UI: pause/resume/restart (after PM4) | — | 1 | yes (UI-only) |
| **PM7c** | UI: replica drilldown (after PM5) | — | 1 | yes (UI-only) |
| **PM7d** | UI: update chips (after PM6) | — | 1 | yes (UI-only) |

Revised critical path: **PM1 → PM2 → PM3 → PM7a** (≈ 5–6 days) ships
the user-visible "yes, we have a Plugin Manager" answer with chips
and durable state. PM5/6 are parallel after PM3; PM7c/7d follow each.
PM4 + PM7b ship together when pause's design lands.

---

## 4. PM1 — Persistence: alembic 0007 + repository

### 4.1 Schema decision

**Reuse the existing `plugin` table for catalog identity. Add a `plugin_state` companion for operator-mutable runtime state. Add a separate `plugin_category_default` table for default routing policy.**

Rationale: the `plugin` table's existing fields (`name`, `version`,
`author`, `type_id`, `status_id`, `input_json`) match what the
install pipeline already produces. Mutations (`enabled`) belong on a
separate row so toggling them doesn't trigger XAF audit-column
writes. **Default routing is per-category, not per-plugin** —
topaz serves both `TOPAZ_PARTICLE_PICKING` and `MICROGRAPH_DENOISING`,
and an operator can pick it as default for one but not the other.
That can't fit on a boolean on the plugin row, so it lives on its
own table (reviewer-flagged High #1).

### 4.2 alembic migration 0007

```python
# 0007_plugin_state.py — adds plugin_state, extends plugin

def upgrade():
    # Widen plugin.version VARCHAR(10) → VARCHAR(64) for SemVer with prerelease tags.
    op.alter_column("plugin", "version",
        existing_type=sa.String(10),
        type_=sa.String(64),
    )

    # Promoted catalog hot fields (currently buried in input_json).
    # NOTE: ``manifest_plugin_id`` (NOT ``plugin_id``). The latter
    # would collide with the existing image_meta_data.plugin_id FK
    # to plugin.oid. Reviewer-flagged High #2.
    op.add_column("plugin", sa.Column("manifest_plugin_id", sa.String(200), nullable=True))
    op.add_column("plugin", sa.Column("backend_id", sa.String(64), nullable=True))
    op.add_column("plugin", sa.Column("category", sa.String(64), nullable=True))
    op.add_column("plugin", sa.Column("schema_version", sa.String(16), nullable=True))
    op.add_column("plugin", sa.Column("install_method", sa.String(16), nullable=True))   # 'uv' | 'docker'
    op.add_column("plugin", sa.Column("install_dir", sa.String(500), nullable=True))
    op.add_column("plugin", sa.Column("image_ref", sa.String(500), nullable=True))
    op.add_column("plugin", sa.Column("container_ref", sa.String(200), nullable=True))
    op.add_column("plugin", sa.Column("archive_id", sa.String(64), nullable=True))
    op.add_column("plugin", sa.Column("manifest_json", sa.dialects.mysql.JSON, nullable=True))
    op.add_column("plugin", sa.Column("installed_date", sa.DateTime, nullable=True))
    op.create_index("ix_plugin_manifest_plugin_id", "plugin", ["manifest_plugin_id"], unique=False)
    op.create_index("ix_plugin_category_backend", "plugin", ["category", "backend_id"])

    # plugin_state — mutable operator state, no audit churn. FK to
    # plugin.oid (NOT a string copy — High #2). Per reviewer-flagged
    # Medium #6: PM4's paused* columns live in alembic 0008, NOT
    # here. PM1 ships ONLY the enabled flag.
    op.create_table(
        "plugin_state",
        sa.Column("plugin_oid", sa.BINARY(length=16), primary_key=True),
        sa.Column("enabled", sa.Boolean, nullable=False, server_default=sa.text("1")),
        sa.Column("last_seen_at", sa.DateTime, nullable=True),
        sa.Column("last_heartbeat_at", sa.DateTime, nullable=True),
        sa.Column("OptimisticLockField", sa.Integer, nullable=True),
        sa.ForeignKeyConstraint(
            ["plugin_oid"], ["plugin.oid"], name="fk_plugin_state_plugin",
        ),
    )

    # plugin_category_default — default routing policy; PK=category,
    # FK to plugin.oid. Multi-category plugins have one row per
    # category they're default for (reviewer-flagged High #1).
    op.create_table(
        "plugin_category_default",
        sa.Column("category", sa.String(64), primary_key=True),
        sa.Column("plugin_oid", sa.BINARY(length=16), nullable=False),
        sa.Column("set_at", sa.DateTime, nullable=False),
        sa.Column("set_by_user_id", sa.String(100), nullable=True),
        sa.ForeignKeyConstraint(
            ["plugin_oid"], ["plugin.oid"],
            name="fk_pcd_plugin",
            ondelete="CASCADE",
        ),
    )
    op.create_index("ix_pcd_plugin_oid", "plugin_category_default", ["plugin_oid"])

def downgrade():
    op.drop_index("ix_pcd_plugin_oid", "plugin_category_default")
    op.drop_table("plugin_category_default")
    op.drop_table("plugin_state")
    op.drop_index("ix_plugin_category_backend", "plugin")
    op.drop_index("ix_plugin_manifest_plugin_id", "plugin")
    for col in ("installed_date", "manifest_json", "archive_id", "container_ref",
                "image_ref", "install_dir", "install_method", "schema_version",
                "category", "backend_id", "manifest_plugin_id"):
        op.drop_column("plugin", col)
    op.alter_column("plugin", "version",
        existing_type=sa.String(64), type_=sa.String(10),
    )
```

### 4.3 ORM additions

- Extend `Plugin` ORM class (`models/sqlalchemy_models.py:155`) with the new columns. Keep existing audit columns + relationships; the install path threads the user_id from Casbin.
- New `PluginState` ORM class — PK `plugin_oid` BINARY(16), FK to `Plugin.oid`. Bypasses XAF audit; updates are bulk-mutation-safe.
- New `PluginCategoryDefault` ORM class — PK `category` (one row per category at most), `plugin_oid` FK to `Plugin.oid`.

### 4.4 Repository additions (`repositories/plugin_repository.py`)

```python
class PluginRepository:
    def upsert_catalog(manifest_plugin_id, manifest, install_result, *, user_id) -> Plugin
    def list_installed() -> list[Plugin]
    def get_by_oid(oid: UUID) -> Optional[Plugin]
    def get_by_manifest_plugin_id(manifest_plugin_id: str) -> Optional[Plugin]
    def soft_delete(oid: UUID) -> None                  # sets deleted_date, GCRecord

class PluginStateRepository:
    def enabled(plugin_oid: UUID) -> bool                # default True
    def set_enabled(plugin_oid: UUID, enabled: bool) -> None
    def touch_heartbeat(plugin_oid: UUID, when: datetime) -> None
    def snapshot() -> dict
    # PM4 (deferred) extends this with paused/set_paused/paused_until

class PluginCategoryDefaultRepository:
    """One row per category. Multi-category plugins have multiple
    rows pointing at them — or rows pointing elsewhere. That's the
    whole point of separating this from plugin_state."""
    def get_default(category: str) -> Optional[UUID]            # → plugin.oid
    def set_default(category: str, plugin_oid: UUID, user_id) -> None
    def clear_default(category: str) -> None
    def list_all() -> dict[str, UUID]
```

### 4.5 Swap-in plan (one PR, atomic)

1. Land alembic 0007 + ORM + repos (no behaviour change yet).
2. `PluginStateStore` is rewritten to delegate to `PluginStateRepository`. The in-memory module stays as a thin pass-through for one release (back-compat shim, like the `<Plugin>BrokerRunner` aliases). `get_state_store()` returns the same singleton interface; consumers don't change.
3. `InstalledPluginsRegistry` similarly delegates to `PluginRepository`. The `install_id` → `InstalledPlugin` map becomes a DB query.
4. `services/plugin_installer/manager.py::install_archive` writes the catalog row (`PluginRepository.upsert_catalog`) on success.
5. Liveness listener (`core/plugin_liveness_registry.py`) calls `PluginStateRepository.touch_heartbeat()` on each heartbeat — feeds PM2's `lastTransitionTime`.

### 4.6 Acceptance

- Toggle "enable", restart CoreService, toggle survives.
- Set `ctffind4` as default for CTF, restart, default survives.
- `pp` sentinel row from `plugins/pp/controller.py:549` keeps working — it's just one of many `plugin` rows now.
- 4 unit tests: `PluginRepository.upsert_catalog` round-trips; `PluginStateRepository` enabled+paused+default toggles; `PluginStateRepository.set_default_for_category` clears prior default in same tx; soft-deleted plugins don't leak into `list_installed`.

### 4.7 Rollback

Drop migration 0007; the back-compat shim restores in-memory behaviour. No data loss because pre-PM1 there was no persistence.

---

## 5. PM2 — Conditions[] on plugin status

### 5.1 Conditions schema

```python
# magellon-sdk/src/magellon_sdk/models/conditions.py
class Condition(BaseModel):
    type: Literal["Installed", "Enabled", "Live", "Healthy", "Paused", "Default"]
    status: Literal["True", "False", "Unknown"]
    reason: Optional[str] = None         # short machine token: 'Heartbeat' | 'Operator' | 'NoRecentTask'
    message: Optional[str] = None        # human-readable
    last_transition_time: Optional[datetime] = None
```

OLM-style. Multiple conditions can be true at once — that's the point. A plugin can be `Installed=True, Enabled=True, Live=True, Healthy=False` (heartbeating but every recent task failed).

### 5.2 Reducer

`PluginManagerService.compute_conditions(plugin_id) -> list[Condition]` joins:
- `Plugin` row → `Installed`
- `PluginState` row → `Enabled` (PM1) / `Paused` (PM4 — deferred)
- `PluginCategoryDefault` row → `Default` (per-category, not boolean per plugin — multi-category plugins can be default for one category but not another)
- `PluginLivenessRegistry` → `Live` (heartbeat within window)
- Recent `job_event` rows (`event_type IN ('completed','failed')`, last N min) → `Healthy`. **Reviewer-flagged High #4 fix**: revision 1 claimed an `(plugin_id, ended_on DESC)` index existed on `image_job_task`. It doesn't, and there's no `ended_on` column. The right source is `job_event.ts` (already indexed via `(event_id UNIQUE, task_id)` from migration 0002). Reducer joins `image_job_task` (for `plugin_id`) to `job_event` (for terminal events + ts). PM2 may add `(task_id, ts DESC)` if benchmarks warrant.

### 5.3 Wire-shape additions

- Extend `PluginSummary` (`magellon-sdk` + Pydantic shape used by `plugins/controller.py`) with `conditions: list[Condition]`.
- New `GET /plugins/{id}/status` returning `Conditions[]` — useful for narrow polls (UI condition pills) without re-fetching the full join.

### 5.4 Acceptance

5 unit tests covering each Condition type + the reducer's "all-failures-in-row → Healthy=False, reason=RecentFailures" branch. Front-end change is zero in PM2 (UI carries on rendering existing fields); PM7 picks up the chips.

---

## 6. PM3 — `PluginManagerService` facade

`services/plugin_manager.py`. ~80 lines, no new state. Joins R1–R5 + the PM1 repos. The single class server-side code asks "who's running ctffind4?" / "is ctf-ctffind4 healthy?" without re-implementing the join.

```python
class PluginManagerService:
    def __init__(
        self,
        in_process: PluginRegistry,
        plugin_repo: PluginRepository,
        state_repo: PluginStateRepository,
        liveness: PluginLivenessRegistry,
        dispatcher: TaskDispatcherRegistry,
    ) -> None: ...

    # Reads
    def list_all(self) -> list[PluginView]
    def list_installed(self) -> list[PluginView]
    def list_running(self) -> list[PluginView]
    def list_updates(self, hub_index: HubIndex | None) -> list[UpdateInfo]
    def get(self, plugin_id) -> PluginView
    def status(self, plugin_id) -> list[Condition]
    def replicas(self, plugin_id) -> list[ReplicaInfo]   # PM5

    # Mutations (delegate to existing services)
    def enable(self, plugin_id) -> None
    def disable(self, plugin_id) -> None
    def pause(self, plugin_id, reason: str | None) -> None
    def resume(self, plugin_id) -> None
    def set_default(self, category, plugin_id) -> None
    def restart(self, plugin_id) -> None                 # delegates to P9 docker-kill + relaunch
```

`plugins/controller.py::list_plugins` is rewritten to delegate (replaces the inline four-way join). Tests pin the same wire shape — the join logic moves, the surface doesn't.

### 6.1 Acceptance

- Existing `GET /plugins/` characterization test still passes byte-for-byte.
- 6 unit tests on `PluginManagerService` (one per public read method) using fakes for the five collaborators.

---

## 7. PM4 — Pause / resume verbs

### 7.1 Why this is deferred (reviewer-flagged Medium #5)

The first revision defined `pause` and `disable` as operationally
identical (both refuse new dispatches; plugin stays running;
in-flight tasks drain). Two verbs that do the same thing don't pay
their way (principle 4). PM4 is deferred until pause has semantics
meaningfully different from disable. Three candidate semantic
differences worth designing toward:

1. **TTL / auto-resume** — `pause` carries `paused_until: DateTime`;
   the dispatcher's gate auto-clears the flag on expiry. `disable`
   stays indefinite.
2. **Reason taxonomy** — `paused_reason_code: enum`
   (`'maintenance' | 'circuit-breaker' | 'awaiting-investigation' |
   'manual'`). Combined with TTL, ops dashboards can surface "5
   plugins paused for circuit-breaker, all auto-clear in <2 min".
3. **Origin distinction** — `disable` is operator policy
   (durable, manual revert); `pause` is system policy
   (a circuit breaker, a deploy fence — system can clear without
   human action).

### 7.2 What this means for PM1 (reviewer-flagged Medium #6)

PM1 ships **only** the `enabled` flag. **No `paused` columns** until
PM4's design lands. PM4 owns its own alembic 0008 with the full set:
`paused`, `paused_reason_code`, `paused_at`, `paused_until`, plus a
polymorphic `paused_by_user_id` / `paused_by_system_actor`. Two
phases fully independent.

### 7.3 Restart verb

Mostly orthogonal to the pause/disable question — it's the missing
"kill + relaunch" hard-stop. P9's container-kill endpoint already
covers the operational gap; `restart` ships with PM4 once
soft-stop ("drain in-flight then restart") has somewhere to live.

---

## 8. PM5 — Per-replica health (revised: expose, don't re-key)

### 8.1 Reviewer correction (High #3)

The first revision claimed `PluginLivenessRegistry` keyed on
`(category, backend_id)` and proposed widening the key. **That was
wrong**: the registry already keys on `(plugin_id, instance_id)`
(`magellon-sdk/.../bus/services/liveness_registry.py:137`). Replica
granularity exists today. Announce + heartbeat envelopes carry
`instance_id`, NOT `worker_instance_id`
(`magellon-sdk/.../discovery.py:88`).

PM5's actual scope is therefore:

1. **Expose replica snapshots** via `GET /plugins/{id}/replicas` —
   the data exists; the controller doesn't surface it yet.
2. **Provide aggregate views** — "1 of 3 replicas of ctffind4 is
   stale" — derived from the existing keying.
3. **Add per-replica health derivation** — combine the registry's
   `last_heartbeat_at` with task-completion timestamps from
   `job_event.ts` (per PM2's reducer) to compute Healthy / Stale / Lost.

No registry re-keying needed. No SDK schema change.

### 8.2 New API

```
GET /plugins/{id}/replicas

[
  {
    "instance_id": "uuid",                         // SDK uses ``instance_id``
    "host": "topaz-2.cluster.internal",
    "container_id": "abc123" | null,
    "first_seen_at": "...",
    "last_heartbeat_at": "...",
    "last_task_completed_at": "..." | null,        // from job_event.ts
    "in_flight_task_count": 2,
    "status": "Healthy" | "Stale" | "Lost"
  },
  ...
]
```

### 8.3 Acceptance

- Spin up 3 replicas of FFT in compose; `GET /plugins/fft/replicas` returns 3 rows (the registry's existing per-instance entries).
- Kill one container; within 2× heartbeat interval that replica's `status="Lost"`.
- 2 unit tests on the controller's reducer over a fake `PluginLivenessRegistry`. Re-keying tests are NOT needed — the registry is already replica-keyed.

---

## 9. PM6 — Updates view

### 9.1 What

`GET /plugins/updates` cross-references installed (`Plugin` rows from PM1) against a catalog source. Two catalog sources, in priority order:

1. The hub `<HUB_URL>/v1/index.json` (already consumed by `HubCatalogBrowser`).
2. The local CoreService catalog (`core/plugin_catalog.py`) for air-gapped deployments.

Returns:

```jsonc
[
  {
    "plugin_id": "ctf/CTF Plugin",
    "current_version": "1.0.2",
    "latest_version": "1.0.5",
    "channel": "stable",
    "severity": "patch",                    // 'patch' | 'minor' | 'major'
    "release_notes_url": "..." | null,
    "archive_url": "<HUB_URL>/.../1.0.5.mpn"
  }
]
```

### 9.2 Acceptance

- Install ctf 1.0.2; mock the hub index to advertise 1.0.5; `GET /plugins/updates` returns one row with `severity='patch'`.
- 4 unit tests on the version-comparison reducer.

---

## 10. PM7 — UI delta (revised: split into 7a/7b/7c/7d)

**Augment, don't rewrite.** The three-panel composition stays.
Reviewer-flagged Medium #8: PM7 was monolithic and depended on APIs
from phases the critical path called optional. Split by upstream
phase so each landing-PR pins to one dependency.

### 10.1 PM7a — Conditions UI *(after PM2)*

- `PluginBrowser` renders `Conditions[]` as chip cluster instead of the implicit `enabled` flag.
- Empty-state when `Installed=True, Live=False`: "Installed but not announcing — check the container logs."
- 1 component test pinning chip rendering.

### 10.2 PM7b — Pause / resume / restart UI *(after PM4 — deferred)*

- Per-row "Pause" / "Resume" / "Restart" buttons.
- "Pause for ___ minutes" affordance to set `paused_until`.
- Reason picker dropdown when pausing.
- Restart confirmation dialog (not idempotent for hung plugins).

### 10.3 PM7c — Per-replica drilldown *(after PM5)*

- Click on a runtime-panel row → expand to per-replica list rendered from `GET /plugins/{id}/replicas`.
- Per-replica `status` chip; "Force-stop replica" button (post-P9 hook).

### 10.4 PM7d — Update chips *(after PM6)*

- AdminInstalledPanel: per-row "1 update available" chip; click → `UpgradeMpnDialog` pre-populated with the hub archive URL.
- HubCatalogBrowser: "already installed" rows show installed-version + latest-version side by side; "Install" button becomes "Upgrade to X" / "Downgrade to X".
- AdminInstalledPanel: show `installed_date` per row (now persisted via PM1).

### 10.5 No new pages

The existing `PluginsPageView.tsx` composition is the manager. PM7a–7d enhance the three panels in place. Total ~150–250 lines of TSX changes spread across four PRs, each gated on its own backend phase.

---

## 11. What this plan does NOT change

Per principle 6 (additive first, subtractive second):

- **The in-process template-picker at `CoreService/plugins/pp/template_picker/`** stays. The user requested deletion in the 2026-05-03 session; this plan keeps it deferred until the React app dispatches via the broker (the new external `magellon_template_picker_plugin` from Phase 6 is the new path; UI rewire is its own PR).
- **`PLUGIN_INSTALL_PLAN.md` P9** (hub fetch + admin gate) is a separate work-stream. PM6 reads from the hub but does not introduce server-side hub-fetch flow.
- **`MAGELLON_HUB_SPEC.md`** stays a separate service. PM6 just consumes the existing `/v1/index.json`.
- **The two pre-existing in-memory registries (R2, R3) classes** stay as back-compat shims for one release after PM1 — same pattern as `<Plugin>BrokerRunner` aliases. Removable in a follow-up once consumers migrate to the repo APIs.

---

## 12. Risks and open questions

### 12.1 Risks

| # | Risk | Mitigation |
|---|---|---|
| K1 | Schema change to `plugin.version` (VARCHAR(10)→VARCHAR(64)) on a table with one production row is technically safe but sets a precedent. | Land in 0007; future widening goes through alembic. The pp sentinel row's `version=NULL` is unaffected. |
| K2 | `PluginStateRepository.set_default_for_category` must clear prior default in the same transaction to maintain "at most one default per category". Race with concurrent toggles. | Single `UPDATE ... WHERE category=... AND is_default_for_category=true; UPDATE ... WHERE plugin_id=? SET is_default_for_category=true;` in one transaction. Test pinned. |
| K3 | Conditions[] reducer reads recent task results — could become a hot query as `image_job_task` grows. | Index on `(plugin_id, ended_on DESC)` already exists from prior provenance work; bound the lookup window to 10 minutes. Cache per-plugin with 5s TTL if needed. |
| K4 | Pause semantics — what does "in-flight tasks drain" mean if a plugin replica is hung? | Pause is operator soft-stop; if the plugin is hung, operator escalates to `restart` (PM4 verb). Pause does not enforce a deadline. |
| K5 | Per-replica health needs `worker_instance_id` to be set on every announce. Three older plugins (CTF, MotionCor, ptolemy) generate it via `magellon_sdk.runner.PluginBrokerRunner`; verify before PM5 lands. | Quick survey + add a contract test that fails if any plugin's announce envelope lacks `worker_instance_id`. |

### 12.2 Open questions for reviewers

| # | Question | Recommendation |
|---|---|---|
| Q1 | Should `pause` halt the plugin's bus subscription (pika `basic.cancel`) or only stop dispatch? | Stop dispatch only. The plugin's bus connection stays warm so `resume` is sub-second. (Halting subscription would force reconnect handshake.) |
| Q2 | Should `restart` be a separate verb or fold into `disable; enable`? | Separate. `restart` implies a fresh container; `disable; enable` keeps the same process. Different operational intent. |
| Q3 | Should `Healthy` Condition consider plugin-reported metrics (e.g. tasks-failed-rate) or only platform observations? | Platform observations only for PM2. Plugin-reported metrics can land in a `Capability` extension later. |
| Q4 | Does `is_default_for_category` belong on `plugin_state` (denormalised, current proposal) or in a separate `plugin_category_default` table? | On `plugin_state` — saves a join on the hot path; uniqueness enforced in the repository. |
| Q5 | Should PM6 surface yanked / withdrawn versions? | Yes (red badge), once `MAGELLON_HUB_SPEC.md` defines the yank field. Drop from PM6 if the hub doesn't yet. |
| Q6 | Should we bother removing the in-memory `PluginStateStore` after PM1, or leave the shim forever? | Leave the shim for one release; remove in a follow-up after consumers migrate. Same pattern as the `<Plugin>BrokerRunner` aliases from this session. |

---

## 13. Reviewer checklist

Phase-by-phase items reviewers should confirm before approving:

### PM1
- [ ] Alembic 0007 `upgrade()` + `downgrade()` are inverses; tested against a real MySQL.
- [ ] `plugin.version` widening doesn't break the one production row (pp sentinel — version is NULL today).
- [ ] `PluginRepository.upsert_catalog` threads the user_id from Casbin; the audit columns get a real user.
- [ ] `PluginStateRepository.set_default_for_category` is transactional (one prior default cleared in same tx).
- [ ] `pp/controller.py:549` sentinel-row upsert still works after migration.
- [ ] In-memory `PluginStateStore` and `InstalledPluginsRegistry` are back-compat shims, not deleted.
- [ ] Restart-survives-toggle test in CI.

### PM2
- [ ] `Condition` Pydantic model lives in `magellon_sdk.models.conditions`; characterization-tested.
- [ ] Reducer covers all six condition types.
- [ ] `GET /plugins/{id}/status` returns same Conditions[] as embedded in `GET /plugins/`.

### PM3
- [ ] `plugins/controller.py::list_plugins` shape is byte-identical pre-/post-PM3 (characterization golden).
- [ ] `PluginManagerService` is constructor-injected (no module-level singleton), so tests don't need monkey-patching.

### PM4
- [ ] Dispatcher consults `paused` AND `enabled`.
- [ ] In-flight tasks drain on pause (test against `magellon_fft_plugin` end-to-end).
- [ ] `restart` returns 422 for in-process plugins with the explanation in the body.

### PM5
- [ ] Liveness registry keying widened to `(category, backend_id, worker_instance_id)` without breaking existing `(category, backend_id)` lookups (the latter aggregates across replicas).
- [ ] Three older plugins announce with `worker_instance_id` populated.
- [ ] `replicas[].status="Lost"` after 2× heartbeat-interval-without-heartbeat.

### PM6
- [ ] Reads `<HUB_URL>/v1/index.json` (existing) — no new server-side hub-fetch flow.
- [ ] Version comparison handles SemVer prerelease tags.
- [ ] Air-gapped fallback to local catalog.

### PM7
- [ ] No new pages created.
- [ ] Playwright test loads `/panel/plugins` and exercises pause + restart + upgrade-via-update-chip.
- [ ] Existing PluginRunnerPageView (per-plugin run page) is untouched.

---

## 14. Rollback strategy per phase

| Phase | Rollback |
|---|---|
| PM1 | `alembic downgrade 0006`. Drops `manifest_plugin_id` + the new columns + `plugin_state` + `plugin_category_default`. Back-compat shims auto-restore in-memory behaviour. |
| PM2 | `git revert`. UI ignores unknown `conditions` field gracefully. |
| PM3 | `git revert`. The inline join in `list_plugins` is un-deleted; surface unchanged. |
| PM4 | `alembic downgrade` to undo 0008 (drops `paused*` columns); `git revert` for the verbs. **Fully separate** from PM1 per Medium #6. |
| PM5 | `git revert`. No schema change — registry was already replica-keyed. |
| PM6 | `git revert`. UI hides the chip; no schema change. |
| PM7a/b/c/d | Each is `git revert`-safe independently. UI returns to current shape per sub-phase. |

**Decision per reviewer-flagged Medium #6**: PM4's pause columns live in alembic 0008, owned by PM4. PM1 ships ONLY the `enabled` flag. PM1 minimal, PM4 self-contained, no coupling.

---

## 15. Sequencing (revised)

```
PM1  (alembic 0007: plugin ext + plugin_state + plugin_category_default)
  ├── PM2  (Conditions[] reducer; reads job_event.ts for Healthy)
  │     └── PM3  (PluginManagerService facade)
  │            ├── PM5  (replicas controller; no re-key)
  │            └── PM6  (updates view)
  │
  ├── PM7a (Conditions chips UI)                      ← after PM2
  ├── PM7c (replicas drilldown UI)                    ← after PM5
  ├── PM7d (update chips UI)                          ← after PM6
  │
  └── PM4  (pause + alembic 0008: paused/paused_until/paused_reason_code)
        DEFERRED until pause semantics are designed
        └── PM7b (pause/resume UI)                    ← after PM4
```

Smallest-valuable-cut: **PM1 alone** kills the silent-state-loss
bug (2 days; 1 migration + 3 repos + 2 shim files + 4 tests).

Two-phase cut: **PM1 + PM2** — durable toggles + clear status
surface in ~4 days.

Full minimum-viable cut: **PM1 → PM2 → PM3 → PM7a** in ≈ 5–6 days
ships the "yes, we have a Plugin Manager" answer with chips and
durable state. PM5 + PM6 + PM7c/d add the following week.

PM4 + PM7b ship later as one unit, gated on pause-design.

---

## 16. What this plan is NOT

- Not a hub spec. Hub stays in `MAGELLON_HUB_SPEC.md`.
- Not an install pipeline plan. Install pipeline is `PLUGIN_INSTALL_PLAN.md` P1–P9 (P1–P8 shipped; P9 is hub fetch).
- Not an in-process plugin retirement plan. Internal vs external picker stays a separate principle-6 follow-up.
- Not a workflow engine. Per ratified `feedback_yagni_orchestration.md` and the 2026-04-14 Temporal revert.


---

<!--
  Section: 5. Magellon Hub Specification
  Originated from: Documentation/MAGELLON_HUB_SPEC.md
  Merged into this consolidated reference 2026-05-13.
-->

# magellon-hub — Technical Specification

**Status:** Draft 1, 2026-04-17. Implementation spec for a new service.
**Audience:** Developer team building `magellon-hub`. Companion to `UNIFIED_PLATFORM_PLAN.md` (phase H3c) and `magellon-sdk/CONTRACT.md` (archive format).
**Scope:** MVP (phase 1) plus a clearly-scoped phase 2 / 3 backlog. MVP is what the team should build first.

---

## 1. Purpose

`magellon-hub` is a central service that hosts Magellon plugin archives (`.mpn`) and exposes a read/write HTTP API so plugin authors can publish their work and CoreService deployments can discover and install it.

It plays the same role PyPI plays for Python or npmjs.com plays for Node — a registry of named, versioned, reviewable artifacts with a public discovery surface. It is **not** an alternative to per-deployment catalogs: the CoreService-local catalog (see `CoreService/core/plugin_catalog.py`) remains for private and air-gapped deployments. The hub is where the public ecosystem lives.

**What problem this solves that the per-deployment catalog doesn't:**

- Plugin authors can publish once, every CoreService deployment can discover.
- Central review / verification of community plugins (two-tier trust).
- Stable identity: one `plugin_id` claimed once, not N copies across orgs.
- Reproducibility: every published version is immutable and addressable by `{plugin_id, version}` → exact SHA256.

**What this spec deliberately does NOT cover:**

- Federation across multiple hub instances. Single-hub MVP first; federation is phase 3.
- Running the plugins themselves. That stays with CoreService.
- Any UI beyond the backend API. A small admin UI is nice-to-have; the primary client is CoreService's existing Browse modal, which will gain a "remote" mode pointing at the hub.

---

## 2. Architecture

```
┌─────────────────┐        ┌───────────────────────────────────────┐
│ Plugin author   │───────>│ magellon-hub (FastAPI)                │
│   (CLI / CI)    │ HTTPS  │                                       │
└─────────────────┘        │  ┌─────────────┐  ┌──────────────┐    │
                           │  │  REST API   │  │ Background   │    │
┌─────────────────┐        │  │  (/v1/...)  │  │ jobs         │    │
│ CoreService     │───────>│  └──────┬──────┘  │ (index gen,  │    │
│ (remote catalog │ HTTPS  │         │          │  cleanup)    │    │
│  fetcher)       │        │         │          └──────┬───────┘    │
└─────────────────┘        │  ┌──────┴──────┐          │            │
                           │  │  Business   │<─────────┘            │
┌─────────────────┐        │  │  layer      │                       │
│ Admin reviewer  │───────>│  │  (services) │                       │
│   (web + API)   │ HTTPS  │  └──────┬──────┘                       │
└─────────────────┘        │         │                              │
                           │  ┌──────┴──────┐  ┌──────────────┐     │
                           │  │ PostgreSQL  │  │ Object store │     │
                           │  │ (metadata,  │  │ (archives)   │     │
                           │  │  users,     │  │ FS / S3 /    │     │
                           │  │  reviews)   │  │ R2 / GCS     │     │
                           │  └─────────────┘  └──────────────┘     │
                           └───────────────────────────────────────┘
```

### 2.1 Components

- **FastAPI app** — HTTP surface. Async where it pays (archive upload / download). Sync where it doesn't (simple CRUD).
- **PostgreSQL** — all metadata (users, plugins, versions, reviews, audit log). Same engine as CoreService, shared ops knowledge.
- **Object store** — the `.mpn` archive bytes. Abstracted behind a `StorageBackend` interface; default filesystem, S3/R2/GCS pluggable. Content-addressed by SHA256 for dedup.
- **Background jobs** — rebuild the public `/v1/index.json` on publish/yank, garbage-collect orphan archives, cron-nudge stale pending reviews. Run under APScheduler or `arq` — something lightweight, same process or a sidecar. Pick one at implementation time.
- **Admin UI** — optional thin page (HTMX / Starlette templates / or a handful of FastAPI routes rendering HTML). MVP can be API-only; reviewers hit endpoints via a CLI or Postman.

### 2.2 Tech stack

| Concern | Choice | Rationale |
|---|---|---|
| Language | Python 3.11+ | Matches CoreService and the SDK; share Pydantic types. |
| Framework | FastAPI | Matches CoreService; typed; OpenAPI for free. |
| ORM | SQLAlchemy 2.x (async or sync — pick one and stay consistent) | Matches CoreService. |
| Migrations | Alembic | Matches CoreService. |
| DB | PostgreSQL 15+ | JSONB for flexible fields; full-text search if we need it in phase 2. |
| Object store (default) | Filesystem under `/var/lib/magellon-hub/archives/` | Dev + small deployments. Abstracted so prod can swap for S3/R2. |
| Object store (prod) | S3 / Cloudflare R2 / GCS via `aiobotocore` | Industry standard; CDN-friendly. |
| Auth — phase 1 | API tokens (prefix-tagged, stored hashed) | Works for CLI + CI without OAuth setup. |
| Auth — phase 2 | GitHub OAuth 2.0 | Matches the plugin-author population. |
| Background jobs | APScheduler (same process) or `arq` (Redis-backed) | MVP: APScheduler is zero-infra. |
| HTTP client (CoreService side) | `httpx` | Already in CoreService. |
| Observability | Python logging → stdout, Prometheus `/metrics`, OpenTelemetry stub | Standard. |

### 2.3 Repository layout (proposed)

```
magellon-hub/
├── pyproject.toml
├── alembic.ini
├── alembic/versions/
├── src/
│   └── magellon_hub/
│       ├── __init__.py
│       ├── main.py              # FastAPI app factory
│       ├── config.py            # Settings via pydantic-settings
│       ├── db/
│       │   ├── models.py        # SQLAlchemy ORM
│       │   ├── session.py
│       │   └── repositories/    # one module per aggregate
│       ├── api/
│       │   ├── v1/
│       │   │   ├── plugins.py
│       │   │   ├── versions.py
│       │   │   ├── auth.py
│       │   │   ├── admin.py
│       │   │   └── me.py
│       │   └── deps.py          # shared dependencies (auth, db, storage)
│       ├── services/
│       │   ├── plugin_service.py
│       │   ├── version_service.py
│       │   ├── review_service.py
│       │   ├── archive_validator.py
│       │   └── index_builder.py # builds /v1/index.json
│       ├── storage/
│       │   ├── base.py          # StorageBackend protocol
│       │   ├── filesystem.py
│       │   └── s3.py
│       ├── auth/
│       │   ├── tokens.py
│       │   └── github_oauth.py  # phase 2
│       ├── workers/             # background jobs
│       │   └── index_rebuild.py
│       └── schemas/             # pydantic DTOs (request/response)
├── tests/
└── docker/
    ├── Dockerfile
    └── docker-compose.yml
```

Separate repo from `CoreService` and `magellon-sdk`. Shares `magellon-sdk` as a pip dependency for the `PluginArchiveManifest` type (the wire shape of `plugin.yaml` is part of the SDK's public contract).

---

## 3. Data model

All tables use `BIGSERIAL` primary keys unless noted. Timestamps are `TIMESTAMPTZ`. Column constraints and indices are called out explicitly — migrations should match.

### 3.1 `users`

Plugin authors and admins.

| Column | Type | Constraint | Purpose |
|---|---|---|---|
| `id` | BIGSERIAL | PK | |
| `username` | VARCHAR(64) | NOT NULL, UNIQUE | Display handle; GitHub login when we add OAuth. |
| `email` | VARCHAR(320) | NOT NULL, UNIQUE | For review notifications. |
| `full_name` | VARCHAR(200) | NULL | |
| `github_id` | BIGINT | NULL, UNIQUE | Populated when GitHub OAuth lands; NULL for tokens-only users. |
| `role` | VARCHAR(16) | NOT NULL, default `'author'`, CHECK IN (`'author'`, `'admin'`) | Admins can approve/reject; authors can only publish under their own name. |
| `is_disabled` | BOOLEAN | NOT NULL, default FALSE | Soft-disable for abuse. Disabled users cannot authenticate. |
| `created_at` | TIMESTAMPTZ | NOT NULL, default `now()` | |
| `last_seen_at` | TIMESTAMPTZ | NULL | Updated on any authenticated request. |

**Indices:** `(github_id)` unique partial where not null; `(role) WHERE role='admin'` for the small admin queue.

### 3.2 `api_tokens`

API tokens for CLI / CI. Tokens are generated as `mhub_<random32>`, stored hashed (bcrypt or SHA-256 of the raw token). The raw token is shown to the user **once** on creation and never again.

| Column | Type | Constraint | Purpose |
|---|---|---|---|
| `id` | BIGSERIAL | PK | |
| `user_id` | BIGINT | NOT NULL, FK→`users.id` ON DELETE CASCADE | Owner. |
| `token_prefix` | VARCHAR(16) | NOT NULL | Shown in UI so the user can identify it ("mhub_a1b2…"); not sensitive. |
| `token_hash` | VARCHAR(128) | NOT NULL | sha256 of the raw token. |
| `name` | VARCHAR(64) | NOT NULL | User-chosen label ("CI robot", "laptop"). |
| `scopes` | JSONB | NOT NULL, default `'["publish"]'::jsonb` | Array of scope strings. `'publish'`, `'admin'`. |
| `created_at` | TIMESTAMPTZ | NOT NULL, default `now()` | |
| `last_used_at` | TIMESTAMPTZ | NULL | Updated on token authentication. |
| `expires_at` | TIMESTAMPTZ | NULL | NULL = never. |
| `revoked_at` | TIMESTAMPTZ | NULL | Soft-revoke; keep the row for audit. |

**Indices:** `(token_hash)` unique; `(user_id)`.

### 3.3 `plugins`

One row per claimed plugin slug. Identity and description live here; versions live in the next table.

| Column | Type | Constraint | Purpose |
|---|---|---|---|
| `id` | BIGSERIAL | PK | |
| `slug` | VARCHAR(64) | NOT NULL, UNIQUE | URL slug, matches `plugin_id` in the manifest. Lowercase slug (same regex as SDK). Immutable once claimed. |
| `display_name` | VARCHAR(200) | NOT NULL | Human name. Editable. |
| `description_short` | VARCHAR(500) | NOT NULL, default `''` | One-liner for list views. |
| `category` | VARCHAR(32) | NOT NULL | `fft`, `ctf`, `motioncor`, `pp`, ... Matches manifest category. Index-friendly. |
| `owner_user_id` | BIGINT | NOT NULL, FK→`users.id` | Who claimed this slug. Transferrable by admin. |
| `is_verified` | BOOLEAN | NOT NULL, default FALSE | Two-tier trust. Admin-set flag. |
| `is_disabled` | BOOLEAN | NOT NULL, default FALSE | Admin takedown (legal, malware, etc.). Disabled = hidden from list and refusing new versions, but existing archives stay downloadable-by-id for reproducibility unless fully purged. |
| `homepage_url` | VARCHAR(500) | NULL | |
| `repository_url` | VARCHAR(500) | NULL | |
| `license` | VARCHAR(64) | NULL | SPDX identifier. Denormalized from the latest published version for list views. |
| `created_at` | TIMESTAMPTZ | NOT NULL, default `now()` | |
| `updated_at` | TIMESTAMPTZ | NOT NULL, default `now()` | Bumped on metadata or new-version publish. |

**Indices:** `(slug)` unique; `(category)`; `(owner_user_id)`; `(is_verified) WHERE is_verified`; `(updated_at DESC)` for "recently updated" list.

### 3.4 `plugin_versions`

One row per submitted version. Versions are immutable after publish; editing republishes as a new version.

| Column | Type | Constraint | Purpose |
|---|---|---|---|
| `id` | BIGSERIAL | PK | |
| `plugin_id` | BIGINT | NOT NULL, FK→`plugins.id` ON DELETE CASCADE | |
| `version` | VARCHAR(64) | NOT NULL | SemVer recommended. `(plugin_id, version)` unique. |
| `sdk_compat` | VARCHAR(64) | NOT NULL | Copy of the manifest's `sdk_compat`; indexed so we can answer "which plugins work with SDK X.Y.Z?" without scanning manifests. |
| `manifest_json` | JSONB | NOT NULL | Full parsed `plugin.yaml`. Denormalized for fast reads; authoritative source is the archive. |
| `archive_id` | BIGINT | NOT NULL, FK→`plugin_archives.id` | The stored bytes. |
| `submitted_by_user_id` | BIGINT | NOT NULL, FK→`users.id` | Token owner who pushed this version. |
| `review_status` | VARCHAR(16) | NOT NULL, default `'pending'`, CHECK IN (`'pending'`, `'published'`, `'rejected'`, `'yanked'`) | State machine; see §7. |
| `review_notes` | TEXT | NULL | Admin-authored comment visible to the author. |
| `reviewed_by_user_id` | BIGINT | NULL, FK→`users.id` | Admin who transitioned to `published` / `rejected`. |
| `reviewed_at` | TIMESTAMPTZ | NULL | |
| `submitted_at` | TIMESTAMPTZ | NOT NULL, default `now()` | |
| `published_at` | TIMESTAMPTZ | NULL | First transition to `published`. Exposed to clients as "release date". |
| `yank_reason` | VARCHAR(200) | NULL | Short explanation shown next to yanked versions. |

**Indices:** `(plugin_id, version)` unique; `(plugin_id, review_status, published_at DESC)`; `(review_status) WHERE review_status='pending'` for the admin queue; `(sdk_compat)` for the "compatible with SDK X" query.

### 3.5 `plugin_archives`

Content-addressed storage metadata. Deduplicates uploads with the same bytes.

| Column | Type | Constraint | Purpose |
|---|---|---|---|
| `id` | BIGSERIAL | PK | |
| `sha256` | CHAR(64) | NOT NULL, UNIQUE | Hex digest of the archive bytes. |
| `size_bytes` | BIGINT | NOT NULL, CHECK ≥ 0 | |
| `storage_key` | VARCHAR(500) | NOT NULL | Opaque handle the storage backend uses. FS: `ar/ab/<sha256>.mpn`. S3: `s3://<bucket>/archives/ar/ab/<sha256>.mpn`. |
| `content_type` | VARCHAR(64) | NOT NULL, default `'application/zip'` | |
| `uploaded_at` | TIMESTAMPTZ | NOT NULL, default `now()` | |

**Indices:** `(sha256)` unique.

### 3.6 `plugin_tags` (optional, phase 2 nice-to-have)

Free-form tags for discovery. One tag per row, N:M with plugins.

| Column | Type | Constraint | Purpose |
|---|---|---|---|
| `plugin_id` | BIGINT | NOT NULL, FK→`plugins.id` ON DELETE CASCADE | |
| `tag` | VARCHAR(32) | NOT NULL | Lowercase, slug-like. |
| PRIMARY KEY | `(plugin_id, tag)` | | |

### 3.7 `plugin_downloads`

Aggregate popularity counter. Per-event rows would balloon; we increment columns atomically.

| Column | Type | Constraint | Purpose |
|---|---|---|---|
| `plugin_version_id` | BIGINT | PK, FK→`plugin_versions.id` ON DELETE CASCADE | |
| `downloads_total` | BIGINT | NOT NULL, default 0 | Lifetime. |
| `downloads_30d` | BIGINT | NOT NULL, default 0 | Rolling window, rebuilt by a nightly job. |
| `last_downloaded_at` | TIMESTAMPTZ | NULL | |

A background job maintains `downloads_30d` by re-reading the server access log or a small `download_events` table (if we add one later for ML-style popularity scoring). MVP: the `downloads_total` counter is incremented synchronously on archive fetch. `downloads_30d` is a phase 2 add.

### 3.8 `audit_log`

Who did what, when. Mandatory for the review workflow (accountability) and cheap to add up front.

| Column | Type | Constraint | Purpose |
|---|---|---|---|
| `id` | BIGSERIAL | PK | |
| `actor_user_id` | BIGINT | NULL, FK→`users.id` ON DELETE SET NULL | NULL for system actions. |
| `action` | VARCHAR(64) | NOT NULL | `plugin.claim`, `version.upload`, `version.approve`, `version.reject`, `version.yank`, `plugin.verify`, `plugin.disable`, `token.create`, `token.revoke`. |
| `target_type` | VARCHAR(32) | NOT NULL | `plugin`, `version`, `user`, `token`. |
| `target_id` | BIGINT | NOT NULL | |
| `data` | JSONB | NOT NULL, default `'{}'::jsonb` | Action-specific payload (e.g. review notes, old/new value). |
| `ts` | TIMESTAMPTZ | NOT NULL, default `now()` | |

**Indices:** `(actor_user_id, ts DESC)`; `(target_type, target_id, ts DESC)`; partial on action for admin filters.

---

## 4. API surface

Base path: `/v1`. Responses are JSON unless stated. Archive downloads are `application/zip`.

All endpoints return `application/json` with a consistent error body on non-2xx:

```json
{ "detail": "<short human-readable message>" }
```

HTTP status codes follow the usual contract: `200` success, `201` created, `204` no content, `400` client input shape wrong, `401` unauthenticated, `403` authenticated but not allowed, `404` target not found, `409` conflict (duplicate slug/version, state-machine mismatch), `413` payload too large, `422` validation error (pydantic detail shape), `429` rate limited, `503` dependency down.

### 4.1 Endpoint catalog (summary)

| # | Method | Path | Auth | Purpose |
|---|---|---|---|---|
| **Public (read-only)** | | | | |
| 1 | GET | `/v1/plugins` | none | Search & list plugins. |
| 2 | GET | `/v1/plugins/{slug}` | none | Plugin detail (metadata + latest published version). |
| 3 | GET | `/v1/plugins/{slug}/versions` | none | Version history for one plugin. |
| 4 | GET | `/v1/plugins/{slug}/versions/{version}` | none | One version's metadata. |
| 5 | GET | `/v1/plugins/{slug}/versions/{version}/archive` | none | Download the `.mpn` archive. |
| 6 | GET | `/v1/categories` | none | Category list with plugin counts. |
| 7 | GET | `/v1/index.json` | none | Full index (CoreService polls this). |
| 8 | GET | `/v1/healthz` | none | Liveness. |
| **Author (token auth, scope `publish`)** | | | | |
| 9 | GET | `/v1/me` | bearer | Current user profile. |
| 10 | POST | `/v1/plugins` | bearer | Claim a new plugin slug. |
| 11 | PATCH | `/v1/plugins/{slug}` | bearer (owner) | Update mutable metadata. |
| 12 | POST | `/v1/plugins/{slug}/versions` | bearer (owner) | Upload a new version (multipart). |
| 13 | POST | `/v1/plugins/{slug}/versions/{version}/yank` | bearer (owner) | Yank a published version. |
| 14 | GET | `/v1/me/plugins` | bearer | My plugins. |
| 15 | GET | `/v1/me/tokens` | bearer | My tokens. |
| 16 | POST | `/v1/me/tokens` | bearer | Mint a new token. |
| 17 | DELETE | `/v1/me/tokens/{id}` | bearer | Revoke a token. |
| **Admin (token auth, scope `admin`)** | | | | |
| 18 | GET | `/v1/admin/reviews` | bearer (admin) | Pending-review queue. |
| 19 | POST | `/v1/admin/plugins/{slug}/versions/{version}/approve` | bearer (admin) | Publish a pending version. |
| 20 | POST | `/v1/admin/plugins/{slug}/versions/{version}/reject` | bearer (admin) | Reject with notes. |
| 21 | POST | `/v1/admin/plugins/{slug}/verify` | bearer (admin) | Flip `is_verified`. |
| 22 | POST | `/v1/admin/plugins/{slug}/disable` | bearer (admin) | Takedown. |
| 23 | GET | `/v1/admin/audit` | bearer (admin) | Audit-log query (paginated). |
| **Auth bootstrap (phase 2)** | | | | |
| 24 | GET | `/v1/auth/github` | none | Redirect to GitHub OAuth. |
| 25 | GET | `/v1/auth/github/callback` | none | OAuth callback; mints a token. |

### 4.2 Public endpoints in detail

**1. `GET /v1/plugins`** — Search & list.

Query params (all optional):
- `search: str` — substring match on display_name, description_short, slug. Case-insensitive.
- `category: str` — exact match.
- `verified: bool` — if true, return only verified plugins.
- `sdk_compat: str` — return only plugins with at least one *published* version whose `sdk_compat` includes this SDK version.
- `sort: str` — one of `updated`, `name`, `downloads`. Default `updated`.
- `page: int` (≥1, default 1), `page_size: int` (1–100, default 20).

Response `200`:

```json
{
  "items": [
    {
      "slug": "fft-classical",
      "display_name": "Classical FFT",
      "description_short": "FFT magnitude spectrum via scipy.fft.",
      "category": "fft",
      "is_verified": true,
      "owner": { "id": 42, "username": "magellon-org" },
      "latest_version": {
        "version": "1.3.0",
        "sdk_compat": ">=1.2,<2.0",
        "published_at": "2026-04-12T18:22:14Z"
      },
      "downloads_total": 1834,
      "updated_at": "2026-04-12T18:22:14Z"
    }
  ],
  "page": 1,
  "page_size": 20,
  "total": 37
}
```

**2. `GET /v1/plugins/{slug}`** — Detail.

Response `200`:

```json
{
  "slug": "fft-classical",
  "display_name": "Classical FFT",
  "description_short": "FFT magnitude spectrum via scipy.fft.",
  "category": "fft",
  "is_verified": true,
  "is_disabled": false,
  "owner": { "id": 42, "username": "magellon-org" },
  "homepage_url": "https://magellon.org/plugins/fft-classical",
  "repository_url": "https://github.com/magellon-org/fft-plugin",
  "license": "MIT",
  "created_at": "2026-03-01T12:00:00Z",
  "updated_at": "2026-04-12T18:22:14Z",
  "latest_version": { /* full version object */ },
  "downloads_total": 1834
}
```

Errors: `404` if slug does not exist or is disabled (do not leak existence of disabled plugins to unauthenticated users).

**3. `GET /v1/plugins/{slug}/versions`** — Version history.

Query params: `include_pending: bool` (default false; only the owner/admin can see pending). Non-owner requests silently filter to `review_status='published'` + `'yanked'`.

Response `200`:

```json
{
  "items": [
    {
      "version": "1.3.0",
      "review_status": "published",
      "sdk_compat": ">=1.2,<2.0",
      "submitted_at": "2026-04-10T09:00:00Z",
      "published_at": "2026-04-12T18:22:14Z",
      "reviewed_by": { "id": 7, "username": "admin-alice" },
      "downloads_total": 1834,
      "sha256": "fa23…",
      "size_bytes": 8247
    },
    { "version": "1.2.1", "review_status": "yanked", "yank_reason": "critical bug in MTF computation", "...": "..." }
  ]
}
```

**4. `GET /v1/plugins/{slug}/versions/{version}`** — Single version.

Returns the row + the full parsed `manifest_json` so a consumer can decide whether to download without pulling the zip:

```json
{
  "version": "1.3.0",
  "review_status": "published",
  "submitted_at": "2026-04-10T09:00:00Z",
  "published_at": "2026-04-12T18:22:14Z",
  "sdk_compat": ">=1.2,<2.0",
  "sha256": "fa23…",
  "size_bytes": 8247,
  "archive_url": "/v1/plugins/fft-classical/versions/1.3.0/archive",
  "manifest": { /* the full plugin.yaml as JSON */ }
}
```

**5. `GET /v1/plugins/{slug}/versions/{version}/archive`** — Download.

Response `200` with `Content-Type: application/zip`, `Content-Length`, `ETag: "<sha256>"`, `Cache-Control: public, max-age=31536000, immutable` (archives are immutable by sha256). Range requests supported for large archives.

Side effect: increments `plugin_downloads.downloads_total` for this version.

**6. `GET /v1/categories`** — Category counts.

```json
{
  "categories": [
    { "code": "fft", "count": 3 },
    { "code": "ctf", "count": 5 },
    { "code": "motioncor", "count": 2 },
    { "code": "pp", "count": 4 }
  ]
}
```

**7. `GET /v1/index.json`** — Full public index.

Flat JSON list of every `published` or `yanked` version across every plugin. Optimized for CoreService's remote-catalog poller: one fetch instead of N listing calls. Served with a short-lived cache header (60 s) and a daily rebuild by the background job; between builds it's regenerated on every publish/yank event.

```json
{
  "generated_at": "2026-04-17T18:22:14Z",
  "hub_version": "1.0.0",
  "plugins": [
    {
      "slug": "fft-classical",
      "display_name": "Classical FFT",
      "category": "fft",
      "is_verified": true,
      "versions": [
        {
          "version": "1.3.0",
          "sdk_compat": ">=1.2,<2.0",
          "sha256": "fa23…",
          "size_bytes": 8247,
          "review_status": "published",
          "published_at": "2026-04-12T18:22:14Z",
          "archive_url": "https://hub.magellon.org/v1/plugins/fft-classical/versions/1.3.0/archive"
        }
      ]
    }
  ]
}
```

**8. `GET /v1/healthz`** — `200` with `{ "status": "ok", "db": "ok", "storage": "ok" }`. Used by load balancers and uptime probes. No auth.

### 4.3 Author endpoints in detail

All require `Authorization: Bearer mhub_<raw_token>`. Token must have scope `publish` (or `admin`).

**9. `GET /v1/me`**

```json
{
  "id": 42,
  "username": "magellon-org",
  "email": "team@magellon.org",
  "role": "author",
  "created_at": "..."
}
```

**10. `POST /v1/plugins`** — Claim a slug.

Request:
```json
{
  "slug": "fft-classical",
  "display_name": "Classical FFT",
  "category": "fft",
  "description_short": "FFT magnitude spectrum via scipy.fft.",
  "homepage_url": "https://magellon.org/plugins/fft-classical",
  "repository_url": "https://github.com/magellon-org/fft-plugin",
  "license": "MIT"
}
```

Response `201` → plugin detail shape from §4.2.

Errors:
- `409` if slug already taken.
- `422` if slug doesn't match the slug regex (`^[a-z0-9._-]+$`), category not in the allowed list, URLs malformed.
- `403` if the caller's token lacks `publish` scope.

Claiming a slug does not create a version. The plugin page exists but has no published version and is not shown in default search results (filter: only plugins with ≥1 published version unless `include_empty=true`).

**11. `PATCH /v1/plugins/{slug}`** — Update metadata.

Request: subset of:
```json
{
  "display_name": "...",
  "description_short": "...",
  "homepage_url": "...",
  "repository_url": "...",
  "license": "..."
}
```

`slug`, `category`, `is_verified`, `is_disabled`, `owner_user_id` are NOT mutable here (category by transfer request only; ownership via admin endpoint; verify/disable admin-only).

Response `200` → plugin detail. Errors: `403` if not owner; `404` if disabled (authors can still see their own disabled plugins; non-owners 404).

**12. `POST /v1/plugins/{slug}/versions`** — Upload a new version.

**Multipart form** with one field:
- `archive`: a `.mpn` file.

Server extracts `plugin.yaml` from the archive and:
1. Parses the manifest (422 on invalid YAML / unknown schema version / field violations).
2. Verifies `manifest.plugin_id == slug` (409 otherwise — the URL and the archive must agree).
3. Verifies `(slug, manifest.version)` doesn't already exist (409).
4. Computes sha256, dedups against `plugin_archives`.
5. Persists a `plugin_versions` row with `review_status='pending'`.
6. Logs a `version.upload` audit event.
7. Bumps `plugins.updated_at`.

Response `201`:
```json
{
  "plugin_slug": "fft-classical",
  "version": "1.3.0",
  "review_status": "pending",
  "submitted_at": "2026-04-17T18:22:14Z",
  "sha256": "fa23…",
  "size_bytes": 8247
}
```

Limits:
- Max archive size: 20 MiB by default (config `HUB_MAX_ARCHIVE_BYTES`). 413 on over-size.
- One upload of the same `(slug, version)` permitted even if pending; returns the existing row with 200 rather than 409 to make CI re-runs idempotent on transient network failures. A **published** version may not be overwritten — authors bump the version.

**13. `POST /v1/plugins/{slug}/versions/{version}/yank`**

Request:
```json
{ "reason": "critical bug in MTF computation" }
```

Transitions `review_status` from `'published'` → `'yanked'`. The archive remains downloadable by `{slug, version}` (for reproducibility — never break an installed deployment). Yanked versions are:
- filtered out of `/v1/index.json` for new-install discovery (so a fresh CoreService ignores them);
- filtered out of the default Browse view on the hub's public surface;
- still returned for direct `GET /v1/plugins/{slug}/versions/{version}` with an explicit `"review_status": "yanked"` flag.

Errors: `409` if not currently `published`. Owners can yank their own; admins can yank any.

**14–17. `/v1/me/plugins`, `/v1/me/tokens` CRUD** — Straightforward CRUD; token creation response includes the raw token exactly once:

```json
{
  "id": 17,
  "token": "mhub_A1B2C3D4E5F6G7H8I9J0K1L2M3N4O5P6",
  "prefix": "mhub_A1B2",
  "name": "CI robot",
  "scopes": ["publish"],
  "created_at": "...",
  "expires_at": null
}
```

After this response, the hub only stores `token_hash`. Subsequent `GET /v1/me/tokens` returns everything except the raw token.

### 4.4 Admin endpoints in detail

All require `Authorization: Bearer …` from a user with `role='admin'`. Scope `admin` is required in addition to admin role (defense-in-depth: an admin user can mint an author-scope token for a laptop that shouldn't be able to approve reviews from a coffee shop).

**18. `GET /v1/admin/reviews`** — Pending queue.

Query params: `status=pending|rejected|all` (default `pending`), `page`, `page_size`.

Response:
```json
{
  "items": [
    {
      "plugin_slug": "fft-gpu",
      "version": "0.2.0",
      "submitted_at": "2026-04-17T10:00:00Z",
      "submitted_by": { "id": 58, "username": "acme-labs" },
      "sdk_compat": ">=1.2,<2.0",
      "category": "fft",
      "size_bytes": 12083,
      "image_ref": "ghcr.io/acme-labs/fft-gpu:0.2.0",
      "review_url": "/v1/plugins/fft-gpu/versions/0.2.0"
    }
  ],
  "page": 1, "page_size": 20, "total": 4
}
```

**19. `POST /v1/admin/plugins/{slug}/versions/{version}/approve`**

Request (optional):
```json
{ "notes": "LGTM, image scanned clean, manifest sane." }
```

Effects: sets `review_status='published'`, `reviewed_by_user_id`, `reviewed_at=now()`, `published_at=now()`, persists `review_notes`. Triggers a `/v1/index.json` rebuild. Logs `version.approve`.

Errors: `409` if not currently `pending`.

**20. `POST /v1/admin/plugins/{slug}/versions/{version}/reject`**

Request (required):
```json
{ "notes": "Rejected: manifest claims sdk_compat >=1.0 but imports SDK 1.2 symbols (see manifest.yaml line 7)." }
```

Effects: sets `review_status='rejected'`, `reviewed_at`, `reviewed_by_user_id`, `review_notes`. Author is notified by email (phase 2 — MVP is poll-based). No effect on index (rejected never enters it).

**21. `POST /v1/admin/plugins/{slug}/verify`**

Request:
```json
{ "verified": true }
```

Toggles `plugins.is_verified`. Affects the "verified" filter and a badge in the UI. Audit-logged. Reversible.

**22. `POST /v1/admin/plugins/{slug}/disable`**

Request:
```json
{ "reason": "takedown: DMCA / malware / abuse", "purge_archives": false }
```

Sets `plugins.is_disabled=true`. Refuses new versions. Existing archives remain downloadable-by-id unless `purge_archives=true` (in which case archives are removed from storage and the `plugin_archives` rows are deleted, tombstoning reproducibility intentionally — only for legal takedowns).

**23. `GET /v1/admin/audit`** — Paginated `audit_log` query.

Query params: `actor_user_id`, `target_type`, `target_id`, `action`, `since`, `until`, `page`, `page_size`. Response is a list of audit rows.

### 4.5 Phase 2 auth endpoints

**24. `GET /v1/auth/github`** — Redirect (`302`) to GitHub OAuth authorization URL with `state` cookie.

**25. `GET /v1/auth/github/callback?code=…&state=…`** — Exchanges the code for a GitHub access token, fetches the user's profile, upserts a `users` row keyed on `github_id`, mints an API token with scope `publish`, redirects to the configured client URL with the raw token in a one-time fragment (client stores it and redirects cleanly).

---

## 5. Authentication & authorization

### 5.1 Token format

Raw token: `mhub_` + 32-char base62 random. Example: `mhub_A1B2C3D4E5F6G7H8I9J0K1L2M3N4O5P6`.

Stored as `token_prefix` (first 8 chars, for display) + `token_hash` (sha256 of raw). Verification: `bcrypt.verify(raw, token_hash)` or `hashlib.sha256(raw) == token_hash`. Pick sha256 for performance (tokens are high-entropy randoms, not user passwords — bcrypt's KDF is overkill).

Tokens are authenticated via `Authorization: Bearer <raw>`. Reject tokens lacking the `mhub_` prefix with `401`.

### 5.2 Scopes

Enumerated (phase 1):
- `publish` — upload versions, claim plugins, manage own tokens, read own plugins.
- `admin` — everything in `publish` plus admin endpoints. Only a `role='admin'` user can mint an `admin`-scoped token.

Per-endpoint scope requirements are listed in the catalog (§4.1). Enforcement lives in a FastAPI dependency:

```python
def require_scope(scope: str):
    def dep(token: Annotated[ApiToken, Depends(get_current_token)]) -> ApiToken:
        if scope not in token.scopes:
            raise HTTPException(403, detail=f"token missing required scope '{scope}'")
        return token
    return dep
```

### 5.3 Role vs scope

`role='admin'` is a property of the **user**. `scope='admin'` is a property of a **specific token** that user minted. An admin user can (and should) use separate tokens for separate machines and only grant `admin` scope to the ones they review plugins from.

### 5.4 Rate limiting (MVP = light; production = required)

- Unauthenticated: 60 req/min/IP for GETs. 429 on overflow.
- Authenticated author: 300 req/min/token, 10 upload/hour/token.
- Admin: no rate limit on admin endpoints, same rate as author on public ones.

Implement with `slowapi` (Starlette middleware) or equivalent. Configurable via env.

### 5.5 CSRF / CORS

The hub's clients are CoreService deployments (server-to-server) and a small admin UI on the same origin. CSRF is not applicable for token-authenticated APIs (tokens are not sent automatically like cookies). CORS: open `GET` to `*`; authenticated endpoints require an explicit origin allow-list via `HUB_CORS_ORIGINS` env.

---

## 6. Archive storage

### 6.1 Abstraction

```python
class StorageBackend(Protocol):
    async def put(self, *, sha256: str, content_type: str, data: BinaryIO) -> str:
        """Store data, return storage_key. Idempotent on same sha256."""
    async def get(self, storage_key: str) -> AsyncIterator[bytes]:
        """Stream the archive bytes."""
    async def head(self, storage_key: str) -> StorageObjectMeta:
        """size, content_type, last_modified."""
    async def delete(self, storage_key: str) -> None:
        """Purge. Used only for admin takedowns with purge_archives=true."""
```

Two backends at MVP:

**Filesystem** — default for dev and single-node deployments.
- Root: `HUB_STORAGE_FS_ROOT`, default `/var/lib/magellon-hub/archives/`.
- Key scheme: `archives/<sha256[0:2]>/<sha256[2:4]>/<sha256>.mpn`.
- Serving: stream via FastAPI's `FileResponse` with `Cache-Control: public, max-age=31536000, immutable` and `ETag: <sha256>`. Behind nginx in prod, use X-Accel-Redirect.

**S3-compatible** — for prod with R2 / S3 / MinIO.
- Env: `HUB_STORAGE_S3_BUCKET`, `HUB_STORAGE_S3_ENDPOINT`, `HUB_STORAGE_S3_ACCESS_KEY_ID`, `HUB_STORAGE_S3_SECRET_ACCESS_KEY`, `HUB_STORAGE_S3_REGION`.
- Key scheme: `archives/<sha256[0:2]>/<sha256[2:4]>/<sha256>.mpn` (same sharding as FS).
- Download: serve via pre-signed URL (redirect `302` to a 5-minute-lived URL) or proxy through the hub app. Redirect is preferred for bandwidth; proxy may be needed if clients need the download counted server-side.

### 6.2 Deduplication

`plugin_archives.sha256` is unique. On upload, compute sha256 before commit; if a row with that sha256 exists, reuse the existing `archive_id`. Two identical archives across two plugins share storage.

### 6.3 Garbage collection

Archives referenced by zero `plugin_versions` rows are orphans. A nightly job selects them and calls `StorageBackend.delete`. Runs with a safety delay (orphans older than 24 h only) to avoid racing in-flight uploads.

---

## 7. Review workflow

State machine on `plugin_versions.review_status`:

```
            upload                    approve
   (nil) ──────────> pending ────────────────> published ─────┐
                        │                           │        yank
                        │ reject                    │         │
                        v                           v         v
                    rejected                     yanked <─────┘
                    (terminal)                   (terminal, still downloadable)
```

**Transitions (who can fire):**

| From | To | Actor | Endpoint |
|---|---|---|---|
| (nil) | pending | owner | POST `/v1/plugins/{slug}/versions` |
| pending | published | admin | POST `/v1/admin/.../approve` |
| pending | rejected | admin | POST `/v1/admin/.../reject` |
| published | yanked | owner or admin | POST `/v1/plugins/.../yank` |

Notably:
- No `rejected → pending` re-submit. If a version is rejected, the author must bump the version number and re-upload. This keeps the `{slug, version}` identity immutable.
- No `yanked → published` un-yank in phase 1. It's a small surface to add in phase 2 if operators ask for it; for now, yanking is a one-way door that forces a version bump for a re-publish, which is simpler to reason about.

**Author visibility:**

Authors always see all states of their own plugins (pending, rejected, yanked, published) on `/v1/me/plugins` and `/v1/plugins/{slug}/versions?include_pending=true`. Anonymous / other-user views see only `published` + `yanked`, with yanked deprioritized.

**Email notifications (phase 2):** `pending→published`, `pending→rejected` fire an email to the author. MVP is poll-only: authors check their own plugin list.

---

## 8. CoreService integration

### 8.1 Remote-catalog fetcher

New module in CoreService: `core/plugin_remote_catalog.py`. A background thread that:

1. On boot and every `HUB_POLL_SECONDS` (default 300 s), fetches `GET {HUB_URL}/v1/index.json` with `If-None-Match: <last_etag>`.
2. Parses the response. Stores it in an in-memory structure indexed the same way as the local catalog.
3. Exposes the remote entries alongside local ones via the existing `GET /plugins/catalog` endpoint — add a `source: 'local' | 'remote'` field to each entry.

**Config:**
- `HUB_URL` — full URL of the hub (e.g. `https://hub.magellon.org`). If unset, the remote fetcher is disabled and the existing local-only behaviour is preserved.
- `HUB_POLL_SECONDS` — default 300.
- `HUB_TRUST_MODE` — one of `verified-only` (default), `all`, `allowlist` (with `HUB_ALLOWLIST=slug1,slug2,...`). Controls which remote entries are shown to operators.

### 8.2 Install from remote

`POST /plugins/catalog/{catalog_id}/install` already accepts a stored local archive. For remote installs:

- New endpoint: `POST /plugins/catalog/remote/{slug}/{version}/install`. CoreService streams the archive from the hub's archive endpoint, validates it (same validation pipeline as local archive uploads), installs it.
- Optional: cache the downloaded archive under the local catalog so a subsequent install for the same `{slug, version}` is hub-free. Operator can clear the cache anytime.

### 8.3 Failure modes

- Hub is down → the background fetcher logs and retries; cached index stays valid. Install-from-remote returns `503` with a clear message ("hub unreachable"); install-from-local-cache still works if the archive was cached earlier.
- Hub is reachable but refuses the CoreService's SDK (all archives target newer SDK) → Browse UI shows them with a "requires SDK X" badge; install returns `409` (same as /install/archive).
- Hub serves a broken archive (sha256 mismatch) → CoreService rejects on validation, logs an integrity warning, does not retry the same archive until the hub republishes.

---

## 9. Versioning policy

### 9.1 Hub API versioning

Base path is `/v1`. Breaking changes to:
- URL shape,
- required fields,
- HTTP status codes for existing error cases,
- auth contract (token format, scope semantics),

trigger a new `/v2` base path. The previous `/v1` is supported for ≥6 months with deprecation headers (`Sunset`, `Deprecation`). Additive changes (new optional fields, new endpoints) do not bump the major.

### 9.2 Archive schema versioning

The archive's own `schema_version` is part of the SDK's public contract (see `magellon-sdk/CONTRACT.md` §7). The hub parses whatever `schema_version` the SDK in its pip dependencies supports. Hub upgrades to a new SDK follow the SDK's SemVer — a minor-bump SDK upgrade is safe; a major is a coordinated event.

### 9.3 DB migrations

Alembic. Migrations are additive-only in production:
- Adding columns with defaults: fine.
- Dropping columns / tables: always in two phases (deploy code that no longer reads, then drop in the next release).
- Backfills: as separate data migrations with progress logging, runnable offline.

---

## 10. Operational concerns

### 10.1 Deployment

- **Dev:** `docker compose up` with `app`, `postgres`, `minio` (S3-compatible) services. `make migrate` runs Alembic; `make seed` adds a local admin user + token.
- **Prod:** containerized FastAPI behind a reverse proxy (nginx / Caddy / Cloudflare). Postgres 15+ (managed is fine). Object storage: R2 / S3. Background jobs in the same container (APScheduler in-process) for MVP; split to a worker container if the job surface grows.

### 10.2 Environment

| Var | Default | Purpose |
|---|---|---|
| `HUB_DATABASE_URL` | `postgresql+asyncpg://hub:hub@localhost/hub` | Postgres DSN. |
| `HUB_STORAGE_BACKEND` | `filesystem` | `filesystem` or `s3`. |
| `HUB_STORAGE_FS_ROOT` | `/var/lib/magellon-hub/archives/` | FS root when backend=filesystem. |
| `HUB_STORAGE_S3_BUCKET` | unset | Bucket when backend=s3. |
| `HUB_STORAGE_S3_ENDPOINT` | unset | Non-AWS endpoint (R2, MinIO). |
| `HUB_STORAGE_S3_REGION` | `us-east-1` | |
| `HUB_STORAGE_S3_ACCESS_KEY_ID` | unset | |
| `HUB_STORAGE_S3_SECRET_ACCESS_KEY` | unset | |
| `HUB_MAX_ARCHIVE_BYTES` | 20971520 (20 MiB) | Upload cap. |
| `HUB_CORS_ORIGINS` | `*` for GET, `[]` for authed | Comma-separated. |
| `HUB_GITHUB_CLIENT_ID` | unset | Phase 2 OAuth. |
| `HUB_GITHUB_CLIENT_SECRET` | unset | Phase 2 OAuth. |
| `HUB_INDEX_REBUILD_INTERVAL_MIN` | 60 | Background rebuild cadence. |
| `HUB_BASE_URL` | `http://localhost:8000` | Used when generating absolute URLs in `/v1/index.json`. |

### 10.3 Observability

- **Structured logs** to stdout: JSON with `ts`, `level`, `actor_id`, `request_id`, `route`, `status`, `duration_ms`.
- **Prometheus metrics** at `/metrics`:
  - `hub_http_requests_total{method,route,status}`
  - `hub_http_request_duration_seconds{method,route}`
  - `hub_archive_upload_bytes_total`
  - `hub_archive_download_bytes_total{slug,version}`
  - `hub_reviews_pending_count`
  - `hub_storage_orphan_count`
- **Tracing:** OpenTelemetry SDK init stubbed; exporter configurable via `OTEL_EXPORTER_OTLP_ENDPOINT`. Off by default.

### 10.4 Backup

- Postgres: daily base backup + WAL archiving. RPO ≤ 5 min for prod.
- Object storage: S3 versioning on the bucket (retention 30 d), or for FS, nightly rsync to cold storage. **Losing archives is catastrophic** — old CoreService installs depend on `{slug, version}` → sha256 stability.
- Audit log: considered part of the DB; same backup cadence.

### 10.5 Monitoring / alerting

- Alert on: `healthz` != 200 for 2 min, `hub_reviews_pending_count > 20`, storage backend errors, DB connection errors, `hub_http_request_duration_seconds` p99 > 2 s for the archive endpoint (suggests disk pressure or slow upstream storage).

---

## 11. Security

### 11.1 Archive validation (upload time)

- Max size enforced in FastAPI before buffering fully (stream with chunk limit).
- Archive must be a valid zip.
- Must contain a top-level `plugin.yaml`.
- Manifest must validate against `PluginArchiveManifest` (see SDK).
- `manifest.plugin_id` must match the URL slug.
- `manifest.image.ref` must be a syntactically valid image reference (image+tag+digest regex).
- **Do NOT** execute the plugin or pull the image server-side — the hub never runs plugin code. Image scanning is a phase 2 integration (Trivy / Grype).

### 11.2 Secrets

- API tokens stored hashed.
- No plaintext secrets in logs. Wrap sensitive handlers with a `sanitize()` helper that strips `Authorization`, `token`, `password` fields.
- OAuth client secret in env, never in DB.

### 11.3 Abuse handling

- `plugins.is_disabled=true` takes a plugin offline instantly.
- Users can be disabled (`users.is_disabled=true`), revoking all their tokens.
- Tokens can be revoked (`api_tokens.revoked_at`).
- Audit log retains actor even for deleted users (`ON DELETE SET NULL` on `audit_log.actor_user_id`).

### 11.4 Supply-chain notes

The hub serves pointers to Docker images; it does NOT host the images themselves (that's what container registries are for). An operator installing a published plugin is still trusting the image's maintainer. The hub's job is to make sure the `{slug, version} → manifest → image_ref` mapping is authoritative, signed, and tamper-evident:

- **Phase 1:** archive sha256 integrity is all we have.
- **Phase 2:** sign archives on publish with an hub-owned key; CoreService verifies the signature.
- **Phase 3:** cosign / in-toto attestations referencing the image digest, so a CoreService that installs the plugin can verify the image hasn't been swapped under the tag.

---

## 12. Phase 2 / 3 backlog

### Phase 2 (after MVP is in production)

- GitHub OAuth login.
- Email notifications on review transitions.
- Search: Postgres full-text index on `display_name + description + manifest.description`.
- Popularity: rolling 30-day downloads, sort-by-popularity.
- Image scanning hook on upload (Trivy via subprocess or API).
- Archive signing (hub signs, CoreService verifies).
- Admin UI as a real HTML surface (HTMX / Starlette templates).

### Phase 3 (when the ecosystem warrants it)

- Federation: multi-hub discovery via a standard `/v1/index.json` format; CoreService polls N hubs.
- Org accounts (teams share ownership of a plugin).
- Usage telemetry from CoreService deployments (opt-in, anonymised).
- Webhook subscriptions for "new version of X published".
- Vulnerability feed integration.

---

## 13. Open decisions for the team

1. **Sync vs async SQLAlchemy.** CoreService is sync. Going async here is a step up but is cleaner for long-running uploads/downloads. **Recommended:** async (`asyncpg`) — archive I/O benefits most.

2. **Object storage default in prod.** R2 vs S3 vs self-hosted MinIO. **Recommended:** R2 for OSS distribution (Cloudflare zero-egress is a big win for a download-heavy service).

3. **Admin UI scope.** MVP is API-only; add HTML admin screens in phase 2, or start with a small Jinja2 page for the review queue only. **Recommended:** start with a single admin HTML page rendering the review queue (≤ 200 LOC). Everything else is API-for-now.

4. **Who runs the canonical instance?** `hub.magellon.org` needs an owner, TLS cert, domain, auth story. Not in scope for the team building the code, but should be decided before launch.

5. **Legal / takedown policy.** We need a stance on malicious plugins, DMCA, re-publishing under a new slug after disable. Phase 1 code supports the `disable` action; the policy doc doesn't exist yet.

6. **CoreService config surface for hub URL.** Environment variable vs `settings.yml` field? **Recommended:** both, with env overriding file, matching CoreService's existing config precedence.

---

## 14. Implementation milestones (suggested)

A rough staging for 3–4 weeks of work, one developer:

**M1 — skeleton (week 1):** repo scaffold, Dockerfile, Alembic, users + api_tokens + plugins + plugin_versions + plugin_archives tables, storage backend interface + filesystem impl, `/v1/healthz`, `/v1/plugins` (list + detail), `/v1/plugins/{slug}` claim, token-auth dependency.

**M2 — publishing (week 2):** upload `/v1/plugins/{slug}/versions`, archive validation, dedup, `GET /archive`, `PATCH /{slug}`, `/v1/me/*`, `/v1/me/tokens/*`.

**M3 — review (week 3):** admin role, `/v1/admin/reviews`, approve/reject/yank endpoints, audit log, `/v1/index.json` background rebuild, `/v1/categories`, `/v1/index.json` end-to-end test.

**M4 — integration (week 4):** CoreService remote-catalog fetcher, install-from-remote endpoint, S3 storage backend, rate limiting, observability metrics, one small admin HTML page for the review queue, dockerized docker-compose dev env, minimal README for operators.

Ship M4 to a staging environment before production.

---

## 15. Out of scope for this spec

- Multi-tenant SaaS (different orgs with isolation).
- Billing / payments.
- CI providers other than GitHub (GitLab, Bitbucket) for OAuth.
- Anything non-Python plugins — the hub is Magellon-plugin-specific; a generic artifact registry (Harbor, Artifactory) is a different product.
- A client-side CLI for `magellon-sdk hub login` / `publish` — that lives in `magellon-sdk`, not here. The hub only exposes the API; the CLI is a follow-up SDK phase.


---

<!--
  Section: 6. Plugin Developer Guide
  Originated from: CoreService/docs/plugin-developer-guide.md
  Merged into this consolidated reference 2026-05-13.
-->

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

