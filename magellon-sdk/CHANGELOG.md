# magellon-sdk changelog

Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).
Version pattern follows SemVer as defined in `CONTRACT.md` §4.

---

## [Unreleased]

(no changes yet)

---

## 2.1.0 — 2026-05-04

**Minor.** Additive contracts from the 2026-05-03 extraction +
classification rollout. Pre-fix these landed in source under the
`[Unreleased]` heading against `version = "2.0.0"`; the version was
not bumped, so plugin manifests pinning `requires_sdk: ">=2.0,<3.0"`
could resolve against an actual 2.0.x release that lacked the new
shapes — reviewer-flagged Medium #9. This release explicitly tags
the contracts as 2.1.0 so plugin manifests can pin
`requires_sdk: ">=2.1,<3.0"` and fail-fast on too-old SDKs.

### Added

- **`PluginBrokerRunner` absorbs the active-task ContextVar +
  daemon-loop + step-reporter helpers.** Every external plugin (FFT,
  topaz, CTF, MotionCor, ptolemy) used to hand-roll the same
  ~80-line block. New module `magellon_sdk.runner.active_task`
  exposes `current_task()`, `set_active_task()`, `reset_active_task()`,
  `get_step_event_loop()`, `emit_step()`, `make_step_reporter()`.
  Per-plugin `*BrokerRunner` subclasses are no longer needed; back-
  compat shims preserve the old import names for one release.
- **Subject axis** on `TaskMessage` and `TaskResultMessage` —
  `subject_kind: Optional[str]` (`'image' | 'particle_stack' |
  'session' | 'run' | 'artifact'` per ratified rule 4 — VARCHAR not
  ENUM) and `subject_id: Optional[UUID]`. `PluginBrokerRunner._stamp_subject`
  echoes them from incoming task to outgoing result; falls back to
  `CategoryContract.subject_kind` when the dispatcher / plugin both
  leave it unset. Closes the dispatch→completion loop for non-image-
  keyed categories.
- **`CategoryContract.subject_kind`** (default `'image'`,
  `TWO_D_CLASSIFICATION_CATEGORY` overrides to `'particle_stack'`).
  Declarative seam that lets pre-Phase-3 dispatchers automatically
  populate the right subject for aggregate categories.
- **New categories**: `PARTICLE_EXTRACTION` (code 10, contract
  `PARTICLE_EXTRACTION_CATEGORY`, input `ParticleExtractionInput`,
  output `ParticleExtractionOutput`). `TWO_D_CLASSIFICATION` was
  reserved at code 4 in 1.0; the contract pairing now lands as
  `TWO_D_CLASSIFICATION_CATEGORY` with `TwoDClassificationInput` /
  `TwoDClassificationOutput`.
- **`Artifact` / `ArtifactKind` Pydantic models** in
  `magellon_sdk.models.artifact`. The typed bridge between a producing
  job/task and downstream consumers. Mirrors the alembic-0005
  `artifact` table 1:1 — promoted hot columns (mrcs_path, star_path,
  particle_count, apix, box_size) + long-tail `data_json`. Per
  ratified rule 6: artifacts are immutable; only `deleted_at` mutates.

### Notes

Pyproject version bumped from 1.2.0 → 2.0.0 to match the existing
`magellon_sdk.__version__` constant — pre-existing drift between the
two locations (the 2.0 wire-shape rename had landed in source but
the build metadata wasn't bumped).

---

## 2.0.0 — 2026-04-27

**Major.** Wire-shape rename. Every 1.x plugin needs a one-line import
update; field shapes on the wire are unchanged.

### Removed (breaking)

The legacy alias names landed in 1.3 are deleted in 2.0. Plugins must
import the canonical names instead:

| Old name (≤ 1.3)            | New name (2.0+)               |
|-----------------------------|-------------------------------|
| `TaskDto`                   | `TaskMessage`                 |
| `TaskResultDto`             | `TaskResultMessage`           |
| `JobDto`                    | `JobMessage`                  |
| `CryoEmImageTaskData`       | `CryoEmImageInput`            |
| `MrcToPngTaskData`          | `MrcToPngInput`               |
| `FftTaskData`               | `FftInput`                    |
| `CtfTaskData`               | `CtfInput`                    |
| `CryoEmMotionCorTaskData`   | `MotionCorInput`              |
| `TopazPickTaskData`         | `TopazPickInput`              |
| `MicrographDenoiseTaskData` | `MicrographDenoiseInput`      |
| `PtolemyTaskData`           | `PtolemyInput`                |
| `StepStarted`               | `StepStartedMessage`          |
| `StepProgress`              | `StepProgressMessage`         |
| `StepCompleted`             | `StepCompletedMessage`        |
| `StepFailed`                | `StepFailedMessage`           |

The wire JSON shape is **identical** — only Python class names changed.
A plugin running on 2.0 talks to a plugin running on 1.3 over the bus
without issue. Migration for plugin authors is a search-and-replace.

### Changed

- **`PluginInfo.schema_version` default `"1"` → `"2"`.** The frontend
  refetches plugin form schemas when this changes; the JSON Schema
  `title` strings differ even though field shapes are unchanged. Plugin
  authors who pinned their own value (most don't) keep theirs.
- **`ce-subject` header for backend-pinned dispatches** now carries the
  symbolic subject ``magellon.tasks.<category>.<backend>`` instead of
  the destination queue name. Pre-X.7 the dispatcher emitted the
  queue name (e.g. ``ctf_ctffind4_queue``); post-X.7 it emits
  ``magellon.tasks.ctf.ctffind4``. Consumers parsing ``ce-subject`` for
  observability or routing should expect the new shape. The actual
  AMQP routing target is unchanged — the binder still publishes to
  the queue declared in ``Announce.task_queue`` via the
  ``TaskRoute.physical_queue`` override.

---

## 1.3.0 — 2026-04-27

**Minor.** Additive — every 1.2 plugin keeps working.

### Added — backend layer (Track C / X.1)

- **`PluginManifest.backend_id: Optional[str]`.** A plugin's
  substitutable identity within its category. Two plugins serving the
  same category (`ctffind4` vs `gctf` under `CTF`) declare distinct
  `backend_id`s so the dispatcher can address them individually.
  Defaults to a slug of `info.name` when omitted, so pre-1.3 plugins
  keep dispatching unchanged.
- **`PluginManifest.resolved_backend_id()`** helper for hosts that
  want the effective backend id without caring whether it was
  declared explicitly or auto-derived.
- **`PluginBase.backend_id: ClassVar[Optional[str]]`** — declare it
  as a class field, the default `manifest()` picks it up.
- **`TaskMessage.target_backend: Optional[str]`** (new field on the
  wire envelope). When set, the dispatcher routes only to a live
  plugin whose `backend_id` matches; unset preserves today's
  category-wide round-robin.
- **`Announce.backend_id: Optional[str]`** — propagated through the
  liveness registry so consumers can index by `(category, backend_id)`
  without unpacking the manifest.
- **`PluginLivenessEntry.backend_id`** + duplicate-backend collision
  warning (`DUP_BACKEND_ID`) when two plugin_ids in one category
  claim the same `backend_id`.
- **`CategoryContract.task_subject_for_backend(backend_id)`** +
  module-level `task_subject_for_backend(category, backend)` for
  symbolic logging of backend-pinned routes.

### Added — wire-shape rename (Track C / X.2)

New canonical names landed alongside the old ones as importable
aliases. Both names work in 1.3; the old names are removed in 2.0.

- **`TaskMessage`, `TaskResultMessage`, `JobMessage`** alongside
  `TaskDto`/`TaskResultDto`/`JobDto`.
- **`*Input`** classes alongside `*TaskData` (every per-category input
  schema; see the table in 2.0's "Removed" section above).
- **`Step{Started,Progress,Completed,Failed}Message`** alongside the
  short names.

`isinstance(x, TaskMessage)` and `isinstance(x, TaskDto)` both succeed
for any instance built either way — they are the same class object
under two names.

---

## 1.2.0 — 2026-04-17

Minor. Additive — every 1.x plugin keeps working.

### Added

- **`magellon_sdk.archive`** — plugin archive format for the hub
  (H3a). Pydantic `PluginArchiveManifest` + `load_manifest_bytes` +
  `check_sdk_compat` helpers. Archive is a zip containing
  `plugin.yaml` at the top level; see `CONTRACT.md` §7 for the full
  shape.
- **`magellon-sdk` CLI** (entry point renamed from the `magellon-plugin`
  scaffolding stub). Three subcommands, all argparse-based, no new
  runtime dep:
  - `magellon-sdk plugin init <name>` — scaffolds a directory with a
    ready-to-edit `plugin.yaml` and a README.
  - `magellon-sdk plugin pack <dir>` — validates the manifest and
    zips to `<plugin_id>-<version>.mpn`.
  - `magellon-sdk plugin validate <path>` — accepts a directory, a
    `plugin.yaml` file, or a `.mpn` zip. SDK compat mismatch
    is a warning here; `/plugins/install/archive` hard-fails.
- **`pyyaml` promoted to a core dependency** (was an optional extra).
  `archive.manifest` needs it unconditionally; plugins already pulled
  it via `[config]` so the net effect is nil.

### Changed

- **Console-script entry point renamed** `magellon-plugin` →
  `magellon-sdk`. Only the name changed; no plugin depended on the
  old stub (it was a pre-H3 scaffolding placeholder that printed
  "not yet implemented"). Worth a note in case someone had scripted
  around it.

---

## 1.1.0 — 2026-04-17

Minor. Additive changes only — every 1.0 plugin keeps working.

### Added

- **`Announce.task_queue: Optional[str]`.** Plugins now surface their
  input-queue name in the announce message. `PluginBrokerRunner` wires
  the runner's `in_queue` through `start_discovery()` into the
  announce. Enables the dispatcher to target a specific implementation
  when multiple impls coexist in the same category (hub phase H1).
  Back-compat: old plugins that still announce with `task_queue=None`
  still work; the dispatcher falls back to the legacy category-scoped
  queue name in that case.
- **`start_discovery()` gained a `task_queue=` keyword parameter.**
  Defaults to `None` to preserve existing callers.

### Changed

- CONTRACT.md §2.4 updated to document the per-impl routing pattern
  that H1 uses: `magellon.tasks.<category>.<plugin_id>` (or any
  plugin-chosen queue name declared via `Announce.task_queue`).
  Legacy `magellon.tasks.<category>` route remains valid.

---

## 1.0.0 — 2026-04-17

First frozen public contract. See `CONTRACT.md` for the scope of
what's covered. Everything listed there is promised stable within
the 1.x.y major.

### Changed — breaking, pre-1.0 cleanup (acceptable because the SDK
### had not been used in production)

- **`TaskBase.sesson_id` / `sesson_name` → `session_id` / `session_name`.**
  Fixed a typo that had propagated through 16 files. Every caller
  updated in the same commit; no compatibility alias kept.
- **`CryoEmMotionCorTaskData.outputFile` dropped.** Redundant with
  the canonical `OutMrc` (which mirrors the MotionCor3 binary's
  `-OutMrc` CLI flag and is the name the binary actually reads).
  Plugin callers consolidated on `OutMrc`.
- **Top-level `magellon_sdk.__init__.py` re-exports broadened.**
  `PluginBrokerRunner`, `TaskDto`, `TaskResultDto`, `PluginInfo`,
  `PluginManifest`, `install_rmq_bus`, `install_inmemory_bus`,
  `install_mock_bus` are now importable from `magellon_sdk` directly.
  Previous short list (`PluginBase`, `Envelope`, `NullReporter`,
  `ProgressReporter`, `JobCancelledError`) is retained.

### Added

- `magellon-sdk/CONTRACT.md` — authoritative public-surface map,
  SemVer policy, deprecation policy. Commit `bfa8845`.
- `magellon-sdk/CHANGELOG.md` — this file.
- JSON Schemas (`input_schema` / `output_schema`) in `PluginManifest`
  via `PluginBase.manifest()`. Best-effort emit from the plugin's
  Pydantic input/output classes. Unlocks UI form-rendering and
  upload-validation for the hub. Commit `0ec2cb2`.
- `__all__` added to `magellon_sdk/transport/rabbitmq.py` (explicit
  public surface is `RabbitmqClient` only).
- Module docstring on `magellon_sdk/discovery.py` clarifying that
  `DiscoveryPublisher` / `HeartbeatLoop` are harness internals —
  plugin authors run a `PluginBrokerRunner` which wires them up.

### Fixed

- `CtfTaskData.outputFile`: default was `"ouput.mrc"` (typo). Now
  `"output.mrc"`. Commit `7bc0d47`.
- `NatsPublisher.connect`: added `connect_timeout` parameter
  (default 3s). Prevents indefinite hang on `js.add_stream` when a
  NATS broker is reachable but JetStream isn't enabled — previously
  stalled plugin boot. Commit `07f8497`.
- `_RmqAsyncAdapter.publish`: strips `magellon.` prefix when
  translating a NATS subject to an RMQ routing key. Without this,
  step events published from plugins landed on `magellon.events` but
  matched no binding. Silent data loss. Commit `07f8497`.
- `RmqBinder.publish_task`: reconnect once on stale-connection
  errors (`AMQPConnectionError` / `ChannelError` / `StreamLostError`).
  Pika's `BlockingConnection` doesn't auto-reconnect; an idle drop
  used to mean every subsequent publish failed until binder restart.
  Commit `47339f3`.

### Migration notes (if you built against 0.1.0)

- Rename `sesson_*` → `session_*` in your plugin code. `grep -rn
  sesson_ . --include="*.py"` finds every hit.
- `CryoEmMotionCorTaskData.outputFile` → `OutMrc` (the field was
  never sent to the binary; it was parallel to `OutMrc`). All
  existing MotionCor logic already uses `OutMrc` internally.
- Pin `magellon-sdk>=1.0,<2.0` in your plugin's requirements.
- The bundled wheel filename is now `magellon_sdk-1.0.0-py3-none-any.whl`.
  Dockerfiles that `COPY` the wheel need the filename updated.

---

## 0.1.0 — 2026-03-xx

Initial SDK. Bus Protocol + binders (MB1–MB2), discovery harness,
step events, `PluginBase` contract, `PluginBrokerRunner`.
Reference plugins: FFT, CTF, MotionCor. No public contract
guarantees.
