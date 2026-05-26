# Microscopy Importer Code Reference

Status: source-aligned snapshot, 2026-05-26. The Python code is the
source of truth for behavior.

## Live HTTP Surface

`controllers/import_controller.py` is mounted under `/export` by `main.py`.

- `POST /export/magellon-import` schedules a FastAPI background task and
  returns immediately with `job_id` and `status="scheduled"`.
- `GET /export/jobs/active`, `GET /export/job/{job_id}`, and
  `GET /export/job/{job_id}/summary` provide the import UI status surface.
- `POST /export/epu-import` runs `EPUImporter` synchronously in the request.
- `POST /export/serialem-import` runs `SerialEmImporter` synchronously in the
  request.
- Validation endpoints exist for Magellon and EPU directories. Magellon
  validation resolves `/gpfs/...` to the configured host GPFS root.

## Current Package Shape

### BaseImporter

`BaseImporter` is an abstract base class with common helpers, not a complete
template method implementation. `setup()` stores request params and creates
`ImportFileService` / `ImportDatabaseService`. Shared helpers cover:

- project/session/job creation;
- `Image` row construction from normalized source metadata;
- `ImageJobTask` creation with stable task/job IDs for broker callbacks;
- target directory creation;
- source subdirectory copying for reference inputs such as `gains` and
  `defects`;
- frame transfer and image copy;
- PNG conversion and FFT computation;
- CTF, MotionCor, Topaz pick, and Topaz denoise dispatch;
- a generic `process_task()` / `run_tasks()` loop;
- atlas image record creation.

Concrete importers override `process()` and often bypass parts of these
helpers.

### MagellonImporter

`MagellonImporter.process()` is the backgrounded Magellon import path:

1. Read `session.json` from `source_dir`.
2. Upsert `Project` and `Msession` through `BaseImporter` manifest helpers.
3. Create an `ImageJob` through `BaseImporter.create_import_job_record()`,
   using `pre_assigned_job_id` when the controller scheduled one.
4. Create or update `Image` records recursively from the exported manifest.
5. Create `ImageJobTask` rows and `ImportTaskDto` values for source images
   present under `home/original`.
6. Create the session directory tree under `MAGELLON_HOME_DIR` and copy
   `original`, `gains`, and `defects`.
7. Run PNG/FFT in-process and dispatch CTF/MotionCor through `core.helper`.
8. Mark stage-0 import tasks complete and attempt atlas creation.

The class has a custom progress-aware `run_tasks()` implementation that emits
Socket.IO import progress through `schedule_import_progress`.

### EPUImporter

`EPUImporter.process()` is synchronous from the HTTP request. It uses
`BaseImporter.initialize_db_records()` for initial project/session/job rows,
then owns the EPU-specific workflow:

- recursively scan the EPU directory for XML;
- parse XML metadata into `EPUMetadata`;
- build parent-child relationships from the EPU session tree;
- create `Image`, `ImageJobTask`, and `EPUImportTaskDto` records with matching
  task IDs and job IDs for plugin callbacks;
- copy gains/defects folders into the target session directory;
- run the shared post-import task pipeline for frame transfer, optional copy,
  PNG, FFT, and CTF dispatch. EPU currently disables MotionCor and Topaz
  dispatch from this path.

### SerialEmImporter

`SerialEmImporter.process()` delegates to `create_db_project_session()`, which
is a full import workflow in one method:

- create or retrieve project/session rows through `BaseImporter` upsert
  helpers;
- validate `settings`, `gains`, `medium_mag`, and optional `defects`
  directories;
- find settings/gain/defect files;
- scan MDOC metadata and parse navigator labels;
- stitch montage MRC files;
- convert TIFF movies to MRC;
- create `Image`, `ImageJobTask`, and `SerialEMImportTaskDto` records with
  matching task IDs and job IDs for plugin callbacks;
- establish parent-child relationships from `.nav`;
- run the shared post-import task pipeline while skipping CTF/MotionCor for
  montage images.

### ImporterFactory

`ImporterFactory` lazy-loads Magellon, EPU, and SerialEM importers. The live
HTTP controller still instantiates those importers directly instead of routing
through the factory. Legacy Leginon import through the factory is intentionally
rejected; live Leginon transfer uses `LeginonFrameTransferJobService`.

## Duplication and Design Debt

The package already points toward Template Method, but the concrete importers
do not yet share one orchestration skeleton. Current duplication includes:

- `ImportDatabaseService` remains as a compatibility facade for older
  `BaseImporter._init_database_records()` flows, but it now uses valid
  `Project`/`Msession` columns and resolves `magellon_session_name` before
  creating the job;
- image row construction and `ImageJobTask` row construction now use shared
  `BaseImporter` helpers for Magellon, EPU, and SerialEM;
- target directory creation still happens in importer-specific flows, but
  gains/defects directory copying now uses a shared `BaseImporter` helper for
  Magellon and EPU;
- task loops for PNG, FFT, CTF, and MotionCor were duplicated across
  `BaseImporter`, `EPUImporter`, and `SerialEmImporter`; the shared
  `post_import_steps.ImportTaskPipeline` now owns that post-import task
  template for the standard paths. `MagellonImporter` still keeps a custom
  progress-aware task loop for import-progress Socket.IO counters.
- mixed responsibilities: source parsing, file transformation, DB writes, and
  broker dispatch live in the same large classes;
- duplicate exception names were cleaned up by aliasing
  `import_file_service.FileError` at import time;
- `BaseImporter.create_atlas_images()` now calls `services.atlas.create_atlas_images()`
  instead of recursing into itself;
- `ImporterFactory.import_data()` now passes the DB session into
  `setup(input_data, db_session)`.
- Magellon MotionCor no longer falls back to a hard-coded `/gpfs/24dec03a`
  gain file. It uses the copied target gain reference when available and
  skips MotionCor when no gain reference exists.

## Refactor Direction

Use Template Method for the invariant import lifecycle:

1. Validate the source.
2. Parse source data into a normalized import manifest.
3. Upsert project and session.
4. Create or attach the import job.
5. Create image and job-task rows.
6. Materialize files and session directories.
7. Execute post-import steps.
8. Finalize job status and progress events.

Use Strategy objects for source-specific behavior:

- `MagellonSessionJsonStrategy` for `session.json` exports.
- `EpuXmlStrategy` for XML/session-tree parsing.
- `SerialEmMdocStrategy` for MDOC/nav/montage parsing.

Use small post-import step strategies with `is_applicable()` and `run()`:

- PNG conversion.
- FFT computation.
- CTF dispatch.
- MotionCor dispatch.
- Atlas generation.
- Optional Topaz particle picking or denoise.

The first safe implementation step should be characterization tests around
one happy-path import per source type, plus targeted tests for status mapping,
MotionCor eligibility, and atlas generation. After that, extract only the
smallest shared skeleton that can remove real duplication without changing the
wire/API behavior.
