# Pipeline Ergonomics — Plan

**Status:** Proposal, 2026-05-10.
**Audience:** Plugin authors, dispatcher / job-service maintainers, frontend (plugin catalog).
**Scope:** OSS Magellon. The visual workflow / pipeline builder is explicitly out of scope (reserved for Magellon Pro).
**Companion docs:**
- `ARCHITECTURE_PRINCIPLES.md` — especially #4 (abstractions pay their way today), #6 (additive first), and the immutability rule.
- `PLUGIN_MANAGER_PLAN.md` — runtime/operational plane for plugins; the registry UX phase below complements PM6/PM7.
- `MAGELLON_HUB_SPEC.md` — distribution registry; the registry-discovery work consumes Hub.
- `PLUGIN_INSTALL_PLAN.md` — authoring + install pipeline; the install-from-Hub flow is the existing P9.
- `CATEGORIES_AND_BACKENDS.md` §2.2a — the existing subject axis the typed-socket tags extend.
- `CURRENT_ARCHITECTURE.md` §8 — the gap list; this plan closes three of those gaps.

This plan groups four ergonomics improvements adapted from ComfyUI's design that fit the current Magellon contracts with no new infrastructure — additive metadata, one dispatcher-side optimization, and a UX-only layer on top of the existing Hub. Each is independently shippable.

The four tracks:

| Track | What | Why ship it |
|---|---|---|
| **PE1** | Typed-socket subject tags | Wire-shape validation in the schema endpoints + a catalog filter — no more "plugin runs, then fails because the input was wrong shape" |
| **PE2** | Lineage-keyed dispatch cache | Parameter sweeps and re-renders cost zero plugin runs |
| **PE3** | Workflow-as-JSON in exports | Offline reproducibility; users can share runs without DB access |
| **PE4** | Registry-UX layer on the Hub | Discovery / version-pin / "updates available" — completes the OSS plugin marketplace story |

---

## PE1. Typed-socket subject tags

### Goal

Make it impossible to dispatch a plugin against an input whose subject type doesn't match what it accepts. Today the schema endpoints (`GET /plugins/{id}/schema/{input,output}`, shipped in Track C) carry field types but not semantic input subjects, so the only validation is "did the dispatcher pass the right number of artifact ids."

### Contract change (additive)

Plugin authors add `accepts:` to input schema fields and `produces:` to output schema fields. Both are lists of subject-axis tags drawn from the same vocabulary `CATEGORIES_AND_BACKENDS.md` §2.2a already uses for the `subject` axis on plugin manifests.

Example (manifest fragment):

```yaml
# manifest.yaml — additive fields only
inputs:
  micrograph:
    type: file
    accepts: ["Micrograph"]
  particle_stack:
    type: file
    accepts: ["ParticleStack"]
    optional: true

outputs:
  picks:
    type: file
    produces: "PickList"
  ctf_estimate:
    type: file
    produces: "CTFEstimate"
```

Type-tag grammar (intentionally minimal):

```
Subject              exact subject match
Subject<sub_tag>     subject with a refinement (reserved; not used in PE1)
*                    any subject (escape hatch; discouraged)
```

We do **not** introduce a richer type system in PE1 — multi-tag (`Layer<Raster:ice_thickness>`) is a Pro-only generalization. Keep OSS narrow.

### Validation seam

`/plugins/capabilities` (Track C) is the dispatch-side authority. Extend it to return the per-field `accepts:` / `produces:` for each plugin. Validation lives in **one** place — `services/dispatch_service.py` (or current owner) — at the moment an artifact-id set is bound to a plugin invocation. Reject with `400 SUBJECT_TAG_MISMATCH` and the exact field + offered subject vs declared subject. Plugin-side validation stays advisory; the gate is server-side.

### Frontend payoff

The plugin catalog grows a "consumes" / "produces" filter that operates entirely on capability metadata. Same surface that already powers the Track-C backend axis filter — additive UI, no new endpoint.

### Migration

- **Manifests without `accepts:` / `produces:`.** Treat as legacy: implicit `accepts: ["*"]`, `produces: "*"`. Log a deprecation warning at announce time. Lint rule (per principle #3): new plugins must declare both. Existing plugins given a deadline before the dispatcher rejects.
- **Alembic.** None — the metadata lives in plugin schemas, not the DB.
- **SDK bump.** Minor (e.g. 2.2 → 2.3); manifest validator gains the optional fields.

### Acceptance

1. A plugin declaring `accepts: ["Micrograph"]` rejects an invocation with a `ParticleStack` input, at the dispatcher, before any worker is woken.
2. The catalog's "what consumes `Micrograph`?" query returns ≥1 result and is computed from `/plugins/capabilities` alone.

---

## PE2. Lineage-keyed dispatch cache

### Goal

The five Artifact invariants (memory: `project_artifact_bus_invariants.md`) — immutability, deterministic params hash, lineage as DAG — already give us everything to deduplicate dispatch. Concretely: if the same plugin at the same version is asked to run with the same input artifact set and the same parameters, return the existing output artifact without re-running the worker.

This is the biggest cost lever for users doing parameter sweeps, picker re-runs after a setting tweak, or re-export operations.

### Cache key

```
cache_key = SHA-256 of (
    plugin_id,
    plugin_version,
    sorted(input_artifact_oids),         # one entry per declared input field
    canonicalized_params_json,           # already computed for params_hash
    category,                            # disambiguate when one plugin serves N categories
)
```

`plugin_version` includes both the package version and the manifest content hash, so a re-installed plugin with edited code produces a different key even at the same SemVer.

### Storage

Two options; recommend **(a)**:

**(a) Reuse the Artifact table.** Add a covering index `(producer_plugin_id, producer_plugin_version, params_hash, input_set_hash)` on `Artifact`. `input_set_hash` is a new hot column on Artifact (cheap; consistent with the existing hot-column policy). Pre-dispatch the controller does a single point lookup against this index. If hit → return the existing artifact's `oid`. No new table.

**(b) Sibling `dispatch_cache` table.** Cleaner separation, but a second source of truth for "what runs have happened" — violates principle #2 (one logical owner). Reject.

### Dispatcher seam

`services/dispatch_service.py` (or current owner) gains one method:

```python
def lookup_cached_output(
    plugin_id: UUID, plugin_version: str,
    category: Category, input_oids: list[UUID], params: dict
) -> UUID | None:
    """Return existing artifact oid if a prior run produced it; else None."""
```

Called right after subject-tag validation (PE1), before the bus publish. On hit, the controller emits the standard `task.completed` event with the cached `oid` so downstream consumers see no difference from a real run — they only notice the latency.

### Cache invalidation

Three cases, in order of frequency:

1. **Plugin version bump.** Key changes naturally; old hits stay valid for re-export but new runs go through.
2. **Input artifact superseded.** Lineage already marks superseded artifacts. The cache lookup filters: if any `input_oid` is superseded, skip the cache (fall through to a real run). This is the correct conservative default.
3. **Manual invalidation.** Admin endpoint (`POST /admin/dispatch-cache/invalidate`) with filters. Rare; expected only after a known-bad plugin run gets identified.

### Acceptance

1. A picker re-run with identical params returns in < 50 ms (cache hit) instead of seconds (worker dispatch).
2. A 5-value colormap sweep against the same upstream artifact set fires exactly 1 plugin run + 4 cache hits.
3. Cache hits are observable in `bus.events` audit (so ops can measure hit rate).
4. Cold-cache behavior is unchanged from today (no regression risk on the slow path).

### Risks

- **False hits from non-determinism.** If a plugin's output depends on wall clock, RNG without seed, or floating-point non-determinism, two runs at the same key are not identical. PE2 is not at fault — those plugins are buggy. Document the contract explicitly: plugins MUST be deterministic given (input artifacts, params). Lint via the existing manifest declaration `deterministic: true` (default true; opt-out plugins skip the cache).
- **Index cost.** One additional index on `Artifact`. Measured cost is bounded by Artifact row count, which is already the system's scale ceiling.

---

## PE3. Workflow-as-JSON in exports

### Goal

When a user exports a result (a stack, a particle list, a CTF estimate), embed enough metadata so they can later answer "how did this come to exist?" without DB access — the same trick ComfyUI plays with PNG metadata. Server-side we already have full lineage in the DAG; the work is **serializing** the relevant subgraph and **embedding** it in exports.

### Wire shape

A compact JSON object describing the lineage subgraph that produced an artifact:

```json
{
  "magellon_workflow_version": 1,
  "exported_at": "2026-05-10T19:00:00Z",
  "root_artifact": {
    "oid": "…",
    "subject": "ParticleStack",
    "producer": {"plugin_id": "…", "version": "1.4.2", "params_hash": "sha256:…"}
  },
  "nodes": [
    {"oid": "…", "subject": "Micrograph",     "source": "imported", "import_uri": "…"},
    {"oid": "…", "subject": "CTFEstimate",    "producer": {…}, "params": {…}},
    {"oid": "…", "subject": "PickList",       "producer": {…}, "params": {…}},
    {"oid": "…", "subject": "ParticleStack",  "producer": {…}, "params": {…}}
  ],
  "edges": [
    {"from": "<oid>", "to": "<oid>", "kind": "input"}
  ]
}
```

Keys:

- `nodes` is the transitive lineage closure of the root, capped (see §3.1).
- Each node carries enough to **re-create** the run if all referenced plugins/versions are installed locally — `params` (full, not hashed), `producer.{plugin_id, version}`, `subject`, and either an `import_uri` (root data sources) or upstream edges.
- No artifact bytes embedded. Refs only.

### Where it goes

| Export type | Embed location | Reader |
|---|---|---|
| Plugin-emitted file (e.g. `.mrcs`) | Sidecar `<filename>.magellon-workflow.json` | Any CLI tool / Magellon importer |
| Star file (`.star`) | Header comment block prefixed `# magellon-workflow:` | Magellon importer; ignored by Relion |
| PNG / WebP thumbnails | `tEXt` / `EXIF` block (key: `magellon:workflow`) | Magellon UI drag-and-drop |
| Bulk export (zip / tar) | Top-level `magellon-workflow.json` | Magellon importer |

### Producing it

One service endpoint:

```
GET /artifacts/{oid}/workflow.json
```

Returns the JSON above. Existing lineage queries already traverse the DAG; this is a serializer on top.

### Sub-questions

- **§3.1 Lineage closure cap.** Practical exports want bounded JSON. Cap at N=200 nodes by default; truncate with a `"truncated_at_depth": K` marker. Full closure available behind a flag.
- **§3.2 Plugin params confidentiality.** Some plugins accept secrets (API keys, paths to private datasets). Manifest extension `params.<key>.export: false` redacts the value in workflow.json. Reuse the existing secret-handling vocabulary (or introduce it here if absent).

### Acceptance

1. A user drags an exported `.png` of a 2D class average back into the Magellon UI and sees the full lineage from import → CTF → pick → extract → class2d.
2. The JSON, fed to a `magellon workflow replay` CLI command on a second deployment with the same plugins installed, produces an identical artifact (same `params_hash`, same `content_hash`).
3. Truncated exports remain valid JSON and are flagged as truncated.

### Out of scope

- The CLI replay tool is a follow-on (own plan).
- Visual rendering of the workflow inside the UI is the Pro workflow-builder's job; OSS keeps a plain JSON view + a tree of artifact cards.

---

## PE4. Registry-UX layer on the Hub

### Goal

Plugin discovery, install, version-pin, and "updates available" in the Magellon UI. This is the missing operational UX on top of the already-shipped Hub spec and install pipeline.

### What already exists

- **MAGELLON_HUB_SPEC.md** — distribution registry server (H1–H3 in progress).
- **PLUGIN_INSTALL_PLAN.md** — P1–P8 shipped; P9 (hub-fetch) deferred.
- **PLUGIN_MANAGER_PLAN.md** — runtime / operational verbs (pause, resume, disable, health). PM6/PM7 sketch updates-badge plumbing.

### What PE4 adds (UX only, no new contract)

A new frontend route `/plugins/registry` with three panes:

1. **Browse.** Search / filter Hub plugins by category, backend, subject-tag (PE1), and capability flag. Lists install state (`installed` / `update available` / `not installed`).
2. **Pinned versions.** For each installed plugin, current version + pin / unpin toggle + history.
3. **Update inbox.** Aggregated "updates available" — one click → diff (manifest + changelog) → confirm → triggers the install pipeline at P9 (hub-fetch).

All three are thin views over existing endpoints + the Hub. The one new endpoint:

```
GET /plugins/registry/index            # local merged view: Hub catalog + local install state
```

Internal-only; the merge logic lives server-side so the frontend never holds Hub credentials.

### Dependencies

- P9 (hub-fetch install) needs to land first or in parallel; PE4 is the UX cap on it.
- PM6 (updates badge) is the per-plugin scalar version; PE4 is the cross-plugin aggregate.

### Acceptance

1. A new operator with an empty install browses the registry, installs three plugins, and sees them announce themselves within the configured liveness window — all from the UI, no CLI.
2. After a Hub publish of plugin X v1.5, an existing X@1.4 install shows the update badge within the existing PM6 refresh cadence.
3. Version pin survives a CoreService restart (lives in DB, not in-process state).

### Out of scope

- Hub submission UX for plugin authors (separate; lives in `MAGELLON_HUB_SPEC.md`).
- Permission model for who can install vs who can browse — assumes the same admin gate as PLUGIN_MANAGER_PLAN PM4.
- Per-tenant catalogs / private registries — Pro-only.

---

## Cross-cutting non-goals

- **Visual workflow / pipeline builder.** Pro.
- **Layered images.** Pro (see `magellon-rust-mrc/docs/image-layers-architecture.md`).
- **Cross-plugin scheduling primitives.** YAGNI (memory: `feedback_yagni_orchestration.md`). The four tracks here add value without orchestration.

---

## Sequencing recommendation

PE1 first — it unblocks the cache-key precision in PE2 (subject-aware caching is sharper than blind-input caching) and the registry filter in PE4. PE2 and PE3 can land in parallel after PE1. PE4 waits on P9.

```
PE1 ─┬─→ PE2 ─┐
     ├─→ PE3 ─┤
     └─→ PE4  ┘   (also waits on P9)
```

No track requires a feature flag — all four are additive, off-by-default-friendly, and revertable by reverting the metadata.
