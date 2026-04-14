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
        JobSvc[JobService]
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

### JobService

**File:** `CoreService/services/job_service.py`
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
    participant JobSvc as JobService
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
| Job service | `CoreService/services/job_service.py` |
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
