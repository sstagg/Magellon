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
