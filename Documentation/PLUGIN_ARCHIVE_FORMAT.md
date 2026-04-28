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
