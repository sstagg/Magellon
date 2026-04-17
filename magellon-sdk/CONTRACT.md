# magellon-sdk — Public Contract

**Status:** Pre-1.0 draft, 2026-04-17. Companion to `Documentation/UNIFIED_PLATFORM_PLAN.md`.
**Audience:** Plugin authors (what you can rely on), SDK maintainers (what you can change).
**Rule in one line:** *Public surface breaks only on a major version bump. Everything not in §2 is internal; change at will.*

---

## 1. Why this document exists

Plugin authors need to know which imports are stable and which will shift between releases. SDK maintainers need a clear line between "promised" and "internal" so internal churn doesn't freeze the whole codebase. This document draws that line and is the authoritative source of truth — `pyproject.toml` version is just a tag, what's in §2 is the actual contract.

The hub vision (see `Documentation/UNIFIED_PLATFORM_PLAN.md` phase H) depends on stability here. A third-party plugin shipped through the hub pins `magellon-sdk>=1.0,<2.0`; that pin is worthless if the shapes under §2 drift inside a major version.

---

## 2. Public surface (promised stable within a major)

### 2.1 Plugin-author imports

These are the imports every plugin author reaches for. Shape + semantics are promised stable within a major.

```python
# Core contract
from magellon_sdk import PluginBase, Envelope, ProgressReporter, NullReporter, JobCancelledError
from magellon_sdk.base import PluginBase, InputT, OutputT

# Models the plugin declares as input/output
from magellon_sdk.models import (
    PluginInfo, PluginManifest, Capability, IsolationLevel, ResourceHints,
    Transport, TaskDto, TaskResultDto, TaskStatus, TaskCategory,
    OutputFile, ImageMetaData, DebugInfo,
    FAILED, COMPLETED, PENDING, IN_PROGRESS,                    # status enums
    CTF_TASK, FFT_TASK, MOTIONCOR, PARTICLE_PICKING,            # task-type constants
    CtfTaskData, FftTaskData, CryoEmMotionCorTaskData,          # typed input models
    CryoEmImageTaskData, MrcToPngTaskData,                      # base image-task shapes
)

# Category contracts + category outputs
from magellon_sdk.categories import (
    FFT, CTF, MOTIONCOR_CATEGORY, PARTICLE_PICKER,              # category contract instances
    CategoryContract, CATEGORIES,
    FftOutput, CtfOutput, MotionCorOutput, ParticlePickingOutput,
)

# Runner harness + bus facades
from magellon_sdk.runner import PluginBrokerRunner
from magellon_sdk.bus import MessageBus, get_bus, DefaultMessageBus
from magellon_sdk.bus.bootstrap import (
    install_rmq_bus, install_inmemory_bus, install_mock_bus,
    build_rmq_bus, build_inmemory_bus, build_mock_bus,
)
from magellon_sdk.bus.routes import TaskRoute, TaskResultRoute, StepEventRoute

# Step events (if the plugin emits them — most do)
from magellon_sdk.events import (
    StepEventPublisher, BoundStepReporter, make_step_publisher,
    StepStarted, StepProgress, StepCompleted, StepFailed,
)

# Task factories (for producer-side dispatch)
from magellon_sdk.task_factory import CtfTaskFactory, FftTaskFactory, MotioncorTaskFactory, TaskFactory

# Error classification (for plugins that map domain errors to DLQ vs retry)
from magellon_sdk.errors import PermanentError, RetryableError, AckAction, Classification

# Config base (plugins that want settings singletons)
from magellon_sdk.config import BaseAppSettings, BaseAppSettingsSingleton, RabbitMQSettings

# Logging setup (optional)
from magellon_sdk.logging_config import setup_logging
```

### 2.2 Pydantic field guarantees

For every Pydantic class in §2.1:
- **Field names, types, and defaults are part of the contract.** Renaming or retyping is a major-version break.
- **Required fields stay required.** Making a required field optional is non-breaking; the reverse is not.
- **Field ordering is NOT part of the contract.** Plugins using positional args: you're on your own.
- **Extra fields are ignored by default** (Pydantic's `extra="ignore"`). Plugins can safely read newer-than-expected DTOs.

### 2.3 Method signature guarantees

For every class in §2.1:
- **Public method signatures (parameter names, types, return types) are part of the contract.**
- Adding optional keyword parameters with defaults is non-breaking.
- Removing parameters, changing required positional parameters, changing return types — all major-version breaks.

### 2.4 Subject / routing-key format

- Task routes: `magellon.tasks.<category>` where `<category>` is lowercase category name.
- Task-result routes: `magellon.tasks.<category>.result`.
- Step event subjects (NATS form): `magellon.job.<job_id>.step.<step>`.
- Step event routing keys (RMQ form — drops the `magellon.` prefix): `job.<job_id>.step.<step>`.
- Discovery subjects: `magellon.plugins.announce.<category>.<plugin_id>` and `magellon.plugins.heartbeat.<category>.<plugin_id>`.

These strings are part of the contract. Cross-implementation plugins bind to these; we can't rename them inside a major.

### 2.5 CloudEvents envelope shape

- `Envelope` JSON shape is CloudEvents 1.0 binary content mode.
- `data` contains a validated `TaskDto` (for task routes) or `TaskResultDto` (for task-result routes), model-dumped as JSON.
- Headers: `ce-id`, `ce-type`, `ce-source`, `ce-subject`, `ce-time`. Contract-bound.

---

## 3. Internal surface (can change any release)

Everything not in §2 is internal. Don't import from these unless you're editing the SDK itself:

- `magellon_sdk.bus.binders.*` — binder implementations. Use `get_bus()` / `install_*_bus()` instead.
- `magellon_sdk.bus._facade` — internal (re-exported where needed).
- `magellon_sdk.transport.*` — transport clients. Use the bus facade; don't reach into pika/nats directly.
- `magellon_sdk.discovery.DiscoveryPublisher`, `HeartbeatLoop`, `ConfigSubscriber` — harness internals used by `PluginBrokerRunner`. If your plugin needs to announce itself outside of `PluginBrokerRunner`, open an issue — we'll either expose an adapter or document the gap.
- `magellon_sdk.executor.*` — internal harness.
- `magellon_sdk.runner.lifecycle`, `magellon_sdk.runner.plugin_runner._*` — internal helpers.
- Any name starting with `_`.

Anything importable today that's not in §2 is a **happy accident**, not a promise. If you're depending on one, speak up now — we might add it to §2 before 1.0.

---

## 4. SemVer policy

- **MAJOR** (1.x.y → 2.0.0): breaking change to anything in §2.
- **MINOR** (1.x.y → 1.x+1.0): new public API additions, fully backward-compatible. Optional parameters. New Pydantic fields with defaults. New modules.
- **PATCH** (1.x.y → 1.x.y+1): bug fixes that don't change observable behavior on the public surface. Internal refactors. Performance improvements.

**CoreService's SDK pin:** `magellon-sdk>=1.0,<2.0`. Plugins ship with the same pin. CoreService refuses to dispatch to a plugin whose announced manifest declares a SemVer-incompatible SDK (enforcement is an H-tier deliverable; policy is locked now).

---

## 5. Deprecation policy

Breaking changes inside a major aren't allowed. To evolve the contract without cutting a major every sprint:

1. **Add the new shape.** New field, new method, new class, whatever.
2. **Mark the old one deprecated.** `warnings.warn(DeprecationWarning, stacklevel=2)` from the accessor. Document in CHANGELOG.
3. **Keep the old shape for ≥1 minor cycle.** Gives plugin authors time to migrate.
4. **Remove on the next major bump.** Not before.

Example: if we want to rename `TaskBase.sesson_id` to `TaskBase.session_id` (and we should — see §6.A), we add `session_id` as an alias, have `sesson_id` raise `DeprecationWarning` on access, and keep both through all of `2.x`. Then drop `sesson_id` in `3.0`.

---

## 6. Decisions needed before 1.0 tag

This doc is the record of what needs to be resolved before `pyproject.toml` bumps to `1.0.0`. Pre-1.0 we're allowed to do breaking cleanup; post-1.0 we're not. Each item below needs an explicit call.

### 6.A  ``TaskBase.sesson_id`` / ``sesson_name`` typos

**Location:** `magellon_sdk/models/tasks.py:57-58`.
**Impact:** the typo `sesson` (should be `session`) is in every `TaskDto`, every `TaskResultDto`, every DB row's `sesson_name` column mapping, every plugin that reads these fields.
**Options:**
   - **(A) Fix before 1.0.** Rename to `session_id` / `session_name`. Breaking: every in-flight task, every persisted DB row, every plugin reading these fields. Requires DB migration + serialization migration + plugin updates.
   - **(B) Freeze the typo in 1.0.** Document it as a known wart. Never fix (renaming post-1.0 means 2.0).
   - **(C) Alias now, deprecate later.** Add `session_id`/`session_name` as Pydantic aliases that map to the same underlying storage. Both work during 1.x. Kill the typo'd variant in 2.0. Compromise: plugins can migrate at their own pace, DB migration deferred.

**Recommendation:** **(C)**. Lowest friction, gives us the option to clean up without blocking 1.0.

### 6.B  ``CryoEmMotionCorTaskData`` duplicate output-file fields

**Location:** `magellon_sdk/models/tasks.py:158-159`.
Both `OutMrc: str = "output.mrc"` and `outputFile: str = "output.mrc"` exist, default to the same value, and are carried in parallel through the MotionCor pipeline.
**Options:**
   - **(A) Keep both; document that `OutMrc` is the canonical one** (mirrors MotionCor3 CLI `-OutMrc` flag). `outputFile` is a compatibility shim for the TaskBase-style field.
   - **(B) Remove `outputFile` before 1.0.** Breaking for anyone using the TaskBase shape consistently.

**Recommendation:** **(A)**. Document and move on.

### 6.C  Field-naming inconsistency across task classes

See §2.1 `CtfTaskData` (camelCase + one snake_case outlier), `CryoEmMotionCorTaskData` (TitleCase mirroring MotionCor3 CLI), `FftTaskData` (snake_case).
**Options:**
   - **(A) Harmonize to snake_case before 1.0.** Breaking for every plugin. Months of plugin updates.
   - **(B) Lock as-is and document intent.** Each class mirrors its source-domain convention intentionally: MotionCor matches its CLI, FFT matches Python conventions, CTF was hand-written and drifted.

**Recommendation:** **(B)**. The naming is ugly but consistent with the domains it models. Breaking real code to pretty up field names isn't worth it.

### 6.D  ``PARTICLE_PICKER.input_model``

**Location:** `magellon_sdk/categories/contract.py:182`.
Currently `input_model = CryoEmImageTaskData` (the base). Richer picker inputs (templates, thresholds, etc.) ride `engine_opts: Dict[str, Any]` — untyped.
**Options:**
   - **(A) Define a canonical `ParticlePickingTaskData` before 1.0.** Breaking later if it's under-specified now.
   - **(B) Keep `engine_opts` escape hatch in 1.0; define the richer model in 1.x as a non-breaking addition.** Plugin authors can upcast when they're ready.

**Recommendation:** **(B)**. Particle-picking shapes are still settling; don't lock prematurely.

### 6.E  ``discovery.py`` public-or-private?

Currently: `DiscoveryPublisher`, `HeartbeatLoop`, `ConfigSubscriber` are module-level classes with no `_` prefix, importable today, used by `PluginBrokerRunner` internally.
**Options:**
   - **(A) Private.** Rename to `_DiscoveryPublisher` etc.; callers outside `PluginBrokerRunner` break. But no production caller outside the harness should be using these anyway.
   - **(B) Public.** Keep as-is; document as stable surface.

**Recommendation:** **(A)**. Announce + heartbeat are implementation details of the runner; exposing them makes it tempting for plugins to reach around the harness.

### 6.F  Top-level `__init__.py` re-exports

Currently re-exports `Envelope`, `PluginBase`, `ProgressReporter`, `NullReporter`, `JobCancelledError`.
**Options:**
   - **(A) Minimal.** Keep as-is. Plugin authors use submodule paths for everything else.
   - **(B) Broader.** Add `TaskDto`, `TaskResultDto`, `PluginManifest`, `install_rmq_bus`, `PluginBrokerRunner` — the most-used names — so `from magellon_sdk import ...` works for most plugin scaffolds.

**Recommendation:** **(B)**. Easier scaffolding, less typing for the common case. Submodule paths stay valid.

---

## 7. What a plugin author actually needs to read

If you're writing a plugin, read:
1. This file §2 (what you can import).
2. `Documentation/UNIFIED_PLATFORM_PLAN.md` for architectural context.
3. `plugins/magellon_fft_plugin/` as a reference implementation.
4. `magellon_sdk/base.py` — `PluginBase` docstring for the contract the runner calls into.

Everything else — binders, transport, executor — is internal. Open an issue if you think you need it; we'd rather expose a proper API than rubber-stamp undocumented reach-arounds.
