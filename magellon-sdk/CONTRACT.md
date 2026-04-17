# magellon-sdk — Public Contract

**Status:** 1.1.0, 2026-04-17. Companion to `Documentation/UNIFIED_PLATFORM_PLAN.md`.
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

- Task routes (category-scoped, legacy): `magellon.tasks.<category>` where `<category>` is lowercase category name. Single-impl deployments and pre-1.1 plugins use this shape.
- Task routes (per-impl, added 1.1): `magellon.tasks.<category>.<plugin_id>` — any queue name the plugin declares via `Announce.task_queue`. Hub deployments route tasks here so a second implementation doesn't auto-round-robin with the default.
- Task-result routes: `magellon.tasks.<category>.result`.
- Step event subjects (NATS form): `magellon.job.<job_id>.step.<step>`.
- Step event routing keys (RMQ form — drops the `magellon.` prefix): `job.<job_id>.step.<step>`.
- Discovery subjects: `magellon.plugins.announce.<category>.<plugin_id>` and `magellon.plugins.heartbeat.<category>.<plugin_id>`.

These strings are part of the contract. Cross-implementation plugins bind to these; we can't rename them inside a major. The per-impl suffix is an additive extension, not a replacement — both shapes are promised stable within 1.x.

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

Example: post-1.0, renaming a field like `TaskBase.session_id` would require adding the new name as an alias, raising `DeprecationWarning` on the old accessor, and keeping both through all of `1.x` — removing the old name only in `2.0`. (Pre-1.0 we took the cheaper path; see §6.)

---

## 6. Pre-1.0 decisions (resolved 2026-04-17)

This section is the audit trail for the six decisions that had to be resolved before cutting the 1.0 tag. Pre-1.0 we were allowed to do breaking cleanup without aliases or deprecation cycles; that latitude is now closed. Each item below records the call that was made and the reason.

Context: at the time of the 1.0 cut the SDK had never been used in production — only in development and testing. That made clean breaking fixes strictly better than alias/deprecation chains, which would have carried the typo/dup-field scars forward for no real migration benefit. Post-1.0, §5's deprecation policy applies in full.

### 6.A  ``TaskBase.sesson_id`` / ``sesson_name`` typos — ✅ FIXED

Renamed to `session_id` / `session_name` in `magellon_sdk/models/tasks.py`. All 16 call sites across CoreService, the three plugins, smoke scripts, and characterization tests were updated in the same commit as the SDK change. No alias kept; the typo is gone. See CHANGELOG 1.0.0 for the file list.

### 6.B  ``CryoEmMotionCorTaskData`` duplicate output-file fields — ✅ FIXED

Dropped `outputFile` from `CryoEmMotionCorTaskData`. `OutMrc` is the single canonical field (mirrors MotionCor3's `-OutMrc` CLI flag — the name the binary actually reads). MotionCor plugin callers consolidated on `OutMrc`; the parallel `outputFile` branch in `service/motioncor_service.py` and the validation block in `utils.py` were removed.

### 6.C  Field-naming inconsistency across task classes — 📝 LOCKED

Locked as-is. Each class intentionally mirrors its source-domain convention: `CryoEmMotionCorTaskData` uses TitleCase because it's a direct handoff to the MotionCor3 CLI; `FftTaskData` uses snake_case because it's pure-Python; `CtfTaskData` is camelCase from its hand-written origins. Harmonizing would have been churn without a behavioral payoff, and each class is internally consistent within its own domain.

### 6.D  ``PARTICLE_PICKER.input_model`` — 📝 DEFERRED

Left as `CryoEmImageTaskData` with `engine_opts: Dict[str, Any]` as the escape hatch. Picker input shapes are still settling across template-picker and future CNN-based engines; introducing a canonical `ParticlePickingTaskData` now would lock assumptions we don't have yet. A richer typed model can be added in 1.x as a non-breaking addition (new optional fields, `engine_opts` still valid).

### 6.E  ``discovery.py`` public-or-private? — 📝 DOCUMENTED as internal

Kept the names un-prefixed (`DiscoveryPublisher`, `HeartbeatLoop`, `ConfigSubscriber`) to avoid a rename churn across the harness, but added a module-level docstring marking them as harness internals used by `PluginBrokerRunner`. They are listed in §3 under "internal surface." Plugin authors who think they need to reach around `PluginBrokerRunner` should open an issue.

### 6.F  Top-level `__init__.py` re-exports — ✅ BROADENED

`magellon_sdk/__init__.py` now re-exports the full common scaffolding: `PluginBase`, `Envelope`, `ProgressReporter`, `NullReporter`, `JobCancelledError` (retained) plus `PluginBrokerRunner`, `TaskDto`, `TaskResultDto`, `PluginInfo`, `PluginManifest`, `install_rmq_bus`, `install_inmemory_bus`, `install_mock_bus`. A minimal plugin scaffold can now `from magellon_sdk import …` without reaching into submodules. Submodule paths remain valid.

---

## 7. What a plugin author actually needs to read

If you're writing a plugin, read:
1. This file §2 (what you can import).
2. `Documentation/UNIFIED_PLATFORM_PLAN.md` for architectural context.
3. `plugins/magellon_fft_plugin/` as a reference implementation.
4. `magellon_sdk/base.py` — `PluginBase` docstring for the contract the runner calls into.

Everything else — binders, transport, executor — is internal. Open an issue if you think you need it; we'd rather expose a proper API than rubber-stamp undocumented reach-arounds.
