# Plugin Manager — Phased Plan

**Status:** Proposal, 2026-05-03.
**Audience:** Reviewers, ops + frontend team, operators.
**Companion docs:**
- `PLUGIN_INSTALL_PLAN.md` (P1–P9 — the **authoring + install** pipeline; complement, not overlap)
- `MAGELLON_HUB_SPEC.md` (the **distribution** registry server)
- `CURRENT_ARCHITECTURE.md` §8 #24–#27 (the 2026-05-03 rollout this plan continues from)
- `memory/project_artifact_bus_invariants.md` (the five ratified rules — same governance applies here)
- `ARCHITECTURE_PRINCIPLES.md` (especially #4 abstractions pay their way today, #6 additive first subtractive second)

This plan is the **runtime / operational** surface — observe, enable / disable, pause / resume, upgrade, uninstall — across the **federated** plugin registries that already exist in Magellon. It does NOT replace the install pipeline (PLUGIN_INSTALL_PLAN P1–P9) or the hub spec; it consumes both.

---

## 0. Why this plan

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
- `GET    /admin/plugins/installed` — list installed (reads R2)
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
| **PM1** | `plugin` + `plugin_state` schema + repository (alembic 0007) | G1, G2, G8 | 2 | yes (drop columns + tables) |
| **PM2** | Conditions[] on `PluginSummary`; `GET /plugins/{id}/status` | G3 | 1–2 | yes |
| **PM3** | `PluginManagerService` facade — server-side join | G7 | 1 | yes |
| **PM4** | Pause / resume verbs + dispatcher gate | G4 | 2 | yes (delete columns + verbs) |
| **PM5** | Per-replica health — keyed by `worker_instance_id` | G5 | 3–4 | yes (additive) |
| **PM6** | Updates view — installed × hub catalog cross-reference | G6 | 2 | yes |
| **PM7** | UI delta — augment existing panels (NOT a rewrite) | — | 2–3 | yes (UI-only) |

Critical path: PM1 → PM2 → PM3 → PM7 (≈ 7 days). PM4 / PM5 / PM6 are parallel branches off PM3.

---

## 4. PM1 — Persistence: alembic 0007 + repository

### 4.1 Schema decision

**Reuse the existing `plugin` table for catalog identity. Add a focused `plugin_state` table for operator-mutable runtime state.**

Rationale: the `plugin` table's existing fields (`name`, `version`, `author`, `type_id`, `status_id`, `input_json`) match what the install pipeline already produces. Mutations (`enabled`, `paused`, `default_for_category`) belong on a separate row so toggling them doesn't trigger XAF audit-column writes that need a full user FK every time the dispatcher flips a flag.

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
    op.add_column("plugin", sa.Column("plugin_id", sa.String(200), nullable=True))
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
    op.create_index("ix_plugin_plugin_id", "plugin", ["plugin_id"], unique=False)
    op.create_index("ix_plugin_category_backend", "plugin", ["category", "backend_id"])

    # plugin_state — mutable operator state, no audit churn.
    op.create_table(
        "plugin_state",
        sa.Column("plugin_id", sa.String(200), primary_key=True),
        sa.Column("enabled", sa.Boolean, nullable=False, server_default=sa.text("1")),
        sa.Column("paused", sa.Boolean, nullable=False, server_default=sa.text("0")),
        sa.Column("paused_reason", sa.String(500), nullable=True),
        sa.Column("paused_at", sa.DateTime, nullable=True),
        # Per-category default — denormalised to plugin_state for the
        # one-row-per-plugin shape, NOT a separate plugin_category_default
        # table (saves a join). 'is_default_for_category' is true on at
        # most one plugin per category; enforced in the repository.
        sa.Column("is_default_for_category", sa.Boolean, nullable=False, server_default=sa.text("0")),
        sa.Column("last_seen_at", sa.DateTime, nullable=True),
        sa.Column("last_heartbeat_at", sa.DateTime, nullable=True),
        sa.Column("OptimisticLockField", sa.Integer, nullable=True),
    )

def downgrade():
    op.drop_table("plugin_state")
    op.drop_index("ix_plugin_category_backend", "plugin")
    op.drop_index("ix_plugin_plugin_id", "plugin")
    for col in ("installed_date", "manifest_json", "archive_id", "container_ref",
                "image_ref", "install_dir", "install_method", "schema_version",
                "category", "backend_id", "plugin_id"):
        op.drop_column("plugin", col)
    op.alter_column("plugin", "version",
        existing_type=sa.String(64), type_=sa.String(10),
    )
```

### 4.3 ORM additions

- Extend `Plugin` ORM class (`models/sqlalchemy_models.py:155`) with the new columns. Keep existing audit columns + relationships; the install path threads the user_id from Casbin.
- New `PluginState` ORM class — PK `plugin_id`, FK to `Plugin.plugin_id`. Bypasses XAF audit; updates are bulk-mutation-safe.

### 4.4 Repository additions (`repositories/plugin_repository.py`)

```python
class PluginRepository:
    def upsert_catalog(plugin_id, manifest, install_result, *, user_id) -> Plugin
    def list_installed() -> list[Plugin]
    def get_by_plugin_id(plugin_id) -> Optional[Plugin]
    def soft_delete(plugin_id) -> None                  # sets deleted_date, GCRecord

class PluginStateRepository:
    def enabled(plugin_id) -> bool                       # default True
    def set_enabled(plugin_id, enabled: bool) -> None
    def paused(plugin_id) -> bool                        # default False
    def set_paused(plugin_id, paused: bool, reason: str | None) -> None
    def get_default_for_category(category) -> Optional[str]
    def set_default_for_category(category, plugin_id) -> None  # clears prior default in same tx
    def touch_heartbeat(plugin_id, when: datetime) -> None
    def snapshot() -> dict
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
- `PluginState` row → `Enabled`, `Paused`, `Default`
- `PluginLivenessRegistry` → `Live` (heartbeat within window)
- Recent `image_job_task` results (last 10 min, by `plugin_id`) → `Healthy` (≥1 success, no all-failures-in-row pattern)

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

### 7.1 Semantics

Three operator levels of "stop":

| Verb | What changes | Plugin process | Use case |
|---|---|---|---|
| `disable` (existing) | Dispatcher refuses new dispatches | Stays running, keeps heartbeating, ready to re-enable | Quiesce while debugging downstream |
| **`pause` (NEW)** | Dispatcher refuses new dispatches **AND** existing in-flight tasks drain to completion. Plugin keeps running. | Stays running | Operator wants the plugin to finish current work, accept no more, without container-kill |
| `restart` (NEW; uses P9 primitive) | Hard kill + relaunch | Container restarts | Hung plugin |
| `uninstall` (existing) | Stop + remove from disk | Container removed | Done with this plugin |

Today only `disable` and `uninstall` exist. `pause` is the missing operator-friendly middle ground.

### 7.2 Implementation

- `POST /plugins/{id}/pause?reason=...` — sets `plugin_state.paused=true`, `paused_reason`, `paused_at`. Dispatcher consults `paused` before publishing (alongside the existing `enabled` check).
- `POST /plugins/{id}/resume` — clears `paused`.
- `POST /plugins/{id}/restart` — issues `docker kill` (existing P9 endpoint) then waits for the container to be re-spawned by the orchestrator. No-op for in-process plugins; returns 422 with explanation.

Compatibility: `paused` and `enabled` are both consulted in dispatcher; either being false refuses new dispatches. Backward-compat for the existing UI's enable/disable button — it doesn't see `paused`, just stays as-is until PM7.

### 7.3 Acceptance

- Pause a plugin mid-task; in-flight task completes; new dispatches return 503 with `reason=PluginPaused`.
- Resume; new dispatches succeed.
- Restart on an in-process plugin returns 422 with the explanation.
- 4 unit tests on the dispatcher gate; 1 contract test on the pause+resume HTTP round-trip.

---

## 8. PM5 — Per-replica health

### 8.1 Why

`PluginLivenessRegistry` keys on `(category, backend_id)`. Three ctffind4 replicas appear as one row; if one silently stops heartbeating but the other two cover, the count drops from 3 → 2 with no UI surface saying which.

### 8.2 Schema change

The announce + heartbeat envelopes already carry `worker_instance_id` (it's on `TaskMessage` and `TaskResultMessage` from the SDK). `PluginLivenessRegistry` ignores it today; PM5 keys by `(category, backend_id, worker_instance_id)`. Storage stays in-memory (rebuilds on reconnect like all liveness data).

New API:

```
GET /plugins/{id}/replicas

[
  {
    "worker_instance_id": "uuid",
    "host": "topaz-2.cluster.internal",
    "container_id": "abc123" | null,
    "first_seen_at": "...",
    "last_heartbeat_at": "...",
    "last_task_completed_at": "..." | null,
    "in_flight_task_count": 2,
    "status": "Healthy" | "Unhealthy" | "Stale" | "Lost"
  },
  ...
]
```

### 8.3 Acceptance

- Spin up 3 replicas of FFT in docker-compose; `GET /plugins/fft/replicas` returns 3 rows.
- Kill one container; within 2× heartbeat interval that replica's `status="Lost"`.
- 3 integration tests in `magellon-sdk/tests/test_bus_services_liveness_registry.py` covering the new key.

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
    "severity": "minor",                    // 'patch' | 'minor' | 'major'
    "release_notes_url": "..." | null,
    "archive_url": "<HUB_URL>/.../1.0.5.mpn"
  }
]
```

### 9.2 Acceptance

- Install ctf 1.0.2; mock the hub index to advertise 1.0.5; `GET /plugins/updates` returns one row with `severity='patch'`.
- 4 unit tests on the version-comparison reducer.

---

## 10. PM7 — UI delta

**Augment, don't rewrite.** The three-panel composition stays.

### 10.1 PluginBrowser (runtime panel)

- Render Conditions[] as chip cluster instead of the implicit `enabled` flag.
- Add per-row "Pause" / "Resume" / "Restart" buttons (next to existing enable / disable / set-default).
- Click on a row → expand to per-replica drilldown (PM5 data).
- New empty-state copy when the plugin is `Installed=True, Live=False`: "Installed but not announcing — check the container logs."

### 10.2 AdminInstalledPanel

- Add per-row "1 update available" chip when PM6 says so. Click → opens `UpgradeMpnDialog` pre-populated with the hub archive URL.
- Show `installed_date` per row (now we have it persisted).

### 10.3 HubCatalogBrowser

- Mark "already installed" rows with a chip showing the installed version side-by-side with the catalog version.
- "Install" button changes to "Upgrade to X" / "Downgrade to X" depending on direction.

### 10.4 No new pages

The existing `PluginsPageView.tsx` composition is the manager. PM7 enhances the three panels in place. ~150–250 lines of TSX changes, mostly chips + dialogs + an expand handler.

### 10.5 Acceptance

- Playwright test: load `/panel/plugins`, verify three panels render, conditions chips visible, click pause, conditions update.
- Visual review: chips color-coded; expand-replica works.

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
| PM1 | `alembic downgrade 0006`. Back-compat shims auto-restore in-memory behaviour. |
| PM2 | `git revert` the SDK + controller commits. UI ignores unknown `conditions` field gracefully. |
| PM3 | `git revert`. The inline join in `list_plugins` is un-deleted; surface unchanged. |
| PM4 | `git revert` + `alembic downgrade -1` (drops `paused`/`paused_reason`/`paused_at` columns added in 0007 — note: those are part of 0007, so PM4 rollback happens together with PM1 unless we split). **Decision:** if PM1 has soaked one release, the `paused` column can land in alembic 0008 separately; keep PM4 fully revertible. |
| PM5 | `git revert`. Liveness registry falls back to the older `(category, backend_id)` key. |
| PM6 | `git revert`. UI hides the chip; no schema change. |
| PM7 | `git revert`. UI returns to current shape. |

PM1 is the only phase with a schema change; PM4's `paused` columns ride along with it, so the split between PM1 and PM4's schema is intentional in §4.2. If a reviewer prefers PM1 truly minimal (no `paused` column until PM4), move those four columns to a future migration 0008 in PM4 — adds one migration, removes coupling.

---

## 15. Sequencing

```
PM1  (alembic 0007 + repos, persistence)             ← lands first; everything else depends on the schema
  ├── PM2  (Conditions[] reducer)
  │     └── PM3  (PluginManagerService facade)
  │            ├── PM4  (pause/resume verbs)
  │            ├── PM5  (per-replica health)
  │            └── PM6  (updates view)
  │
  └── PM7  (UI delta)                                ← after PM2+PM3 minimum; PM4/5/6 feed in incrementally
```

Smallest-valuable-cut: **PM1 alone** kills the silent-state-loss bug. Two days of work; touches 1 migration + 2 repos + 2 shim files + 4 tests; no UI change; no API change. Reviewer effort under an hour.

If picking two: **PM1 + PM2** — the UI gets durable toggles AND a clear status surface in ~4 days.

If picking the full path: **PM1 → PM2 → PM3 → PM7** in ≈ 7 days for the user-visible "yes, we have a Plugin Manager" answer; PM4/5/6 fold in over the following week.

---

## 16. What this plan is NOT

- Not a hub spec. Hub stays in `MAGELLON_HUB_SPEC.md`.
- Not an install pipeline plan. Install pipeline is `PLUGIN_INSTALL_PLAN.md` P1–P9 (P1–P8 shipped; P9 is hub fetch).
- Not an in-process plugin retirement plan. Internal vs external picker stays a separate principle-6 follow-up.
- Not a workflow engine. Per ratified `feedback_yagni_orchestration.md` and the 2026-04-14 Temporal revert.
