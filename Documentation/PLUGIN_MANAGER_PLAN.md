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
