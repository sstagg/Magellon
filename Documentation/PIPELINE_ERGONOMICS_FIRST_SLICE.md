# Pipeline Ergonomics — First Slice (Cheap Cut)

**Status:** Shipped 2026-05-10 — see commit log around `b747f8c`. PE1-A and PE3-lite both landed; PE2 + PE3-full + PE4 + multi-input lineage remain deferred per the table at the bottom. This doc is retained as the implementation reference; once any of the deferred tracks ship, expand or supersede.
**Audience:** Implementer of the slice, reviewer.
**Companion docs:** `PIPELINE_ERGONOMICS_PLAN.md` (four-track roadmap), `ARCHITECTURE_PRINCIPLES.md`.

This doc names the two tracks worth landing now and the two worth deferring. Each change is grounded in a current file path and existing seam — no new infrastructure, no DB migrations, no breaking contract changes.

---

## Scope

**In — land in this slice:**

- **PE1-A — Subject-tag socket validation (lite).** Surface the existing `CategoryContract.subject_kind` on the capabilities endpoint, add `produces_subject_kind` for outputs, and add an explicit dispatch-side rejection for subject-kind mismatches.
- **PE3-lite — Workflow-as-JSON endpoint.** One new endpoint `GET /artifacts/{oid}/workflow.json` that serializes the existing single-parent ancestor chain + producer plugin metadata. No file-format embedding (PNG `tEXt`, star comments, zip top-level) in this slice.

**Deferred — flagged at end:**

- **PE2 — Dispatch cache.** Requires a new hot column + index on `Artifact` + Alembic migration. Worth doing, but not this slice.
- **PE3 full — Format embedding.** PNG `tEXt`, `.star` header comments, zip top-level. Per-format work; ship the endpoint first, let it bake.
- **PE4 — Registry UX.** Depends on `PLUGIN_INSTALL_PLAN` P9 (hub-fetch install, currently deferred). Blocked.

**Out — not this plan:**

- Multi-input lineage. `Artifact.source_artifact_id` is a single-parent FK (`models/sqlalchemy_models.py:718`). True DAG lineage is a separate effort; PE3-lite serializes what's representable today.
- Visual workflow / pipeline builder (Pro).

---

## Current state (grounded, 2026-05-10)

Each track's "what's missing" depends on what's already there. The relevant seams:

| Concept | Lives at | Shape today |
|---|---|---|
| Category contract | `magellon-sdk/src/magellon_sdk/categories/contract.py:136` | `CategoryContract(BaseModel)` with `subject_kind: str = "image"` (line 158) and `input_model` / `output_model` (Pydantic) |
| Subject-kind on dispatch | `CoreService/plugins/controller.py:816` | `_derive_subject(contract, validated)` already threads `(subject_kind, subject_id)` into the bus task |
| Capabilities endpoint | `CoreService/plugins/controller.py:194` | `GET /capabilities` returns `_CategoryCapabilities` with `input_schema` / `output_schema` but **no `subject_kind`** field |
| Schema endpoints | `CoreService/plugins/controller.py:572, 590` | `GET /plugins/{id}/schema/{input,output}` returns `contract.{input,output}_model.model_json_schema()` |
| Artifact + lineage | `CoreService/models/sqlalchemy_models.py:691` | Single parent via `source_artifact_id` (self-FK). `producing_task_id` carries plugin reference. `data_json` for cold metadata. |
| Lineage walk | `CoreService/controllers/artifacts_controller.py:148` | `GET /artifacts/{oid}/lineage` already walks ancestors (bounded depth 20) + direct descendants |

What's missing for the slice:

- `CategoryContract.produces_subject_kind` (none today; output subject is implicit).
- Subject-kind exposure on `_CategoryCapabilities` (the schema is there; the tag isn't).
- An explicit "your input doesn't match this plugin's subject" rejection at dispatch.
- A `/artifacts/{oid}/workflow.json` serializer.

---

## PE1-A — Subject-tag socket validation (lite)

### Changes, file by file

**1. `magellon-sdk/src/magellon_sdk/categories/contract.py`** — add one field.

```python
class CategoryContract(BaseModel):
    # existing fields...
    subject_kind: str = "image"               # already present
    produces_subject_kind: str | None = None  # NEW — None means "same as subject_kind"
```

`None` default keeps every existing contract valid. For categories that transform subjects (e.g. `PARTICLE_EXTRACTION`: image → particle_stack), the call site in `categories/__init__.py` sets it explicitly. SDK minor bump (2.2 → 2.3).

**2. `CoreService/plugins/controller.py`** — extend the capability response shape.

```python
class _CategoryCapabilities(BaseModel):
    # existing fields...
    input_schema: Optional[Dict[str, Any]] = None
    output_schema: Optional[Dict[str, Any]] = None
    subject_kind: str = "image"               # NEW
    produces_subject_kind: str | None = None  # NEW
```

Populate in `list_capabilities()` (line 199) from the contract — three new lines next to the existing `input_schema` block (line 273).

**3. `CoreService/plugins/controller.py`** — add the dispatch gate.

The current dispatch path (`submit_job` line 602 → `_submit_broker_job` → `_derive_subject`) currently accepts whatever the request carries. Add **one validation call** between request parse and `_derive_subject`:

```python
def _reject_if_subject_mismatch(
    contract: CategoryContract,
    validated: BaseModel,
    request: JobSubmitRequest,
) -> None:
    """Reject 422 if the caller's input subject doesn't match
    contract.subject_kind. Idempotent — silent on match."""
    # Aggregate categories (subject == particle_stack etc.) require
    # subject_id on the request; image categories use request.image_id.
    expected = contract.subject_kind
    if expected == "particle_stack" and request.particle_stack_id is None:
        raise HTTPException(422, f"Category requires particle_stack_id (subject={expected})")
    if expected == "image" and request.image_id is None and request.subject_id is None:
        raise HTTPException(422, f"Category requires image_id (subject={expected})")
```

Hooked into `_submit_broker_job` and `_submit_broker_batch`. The existing `_derive_subject` already handles the happy path, so this is the explicit rejection seam the plan called for.

**4. Tests.** Add to `tests/characterization/test_plugin_controller_http.py`:

- Capabilities response includes `subject_kind` per category.
- Submitting a `PARTICLE_EXTRACTION` job with only `image_id` (no `particle_stack_id`) returns 422.
- Submitting a `CTF` job with `image_id` succeeds (regression check on the happy path).

### Acceptance

1. `GET /plugins/capabilities` includes `subject_kind` and (where set) `produces_subject_kind` per category.
2. Dispatching a particle-stack-keyed plugin without `particle_stack_id` returns 422 at the controller, before any bus publish.
3. No existing characterization test fails.

### Cost estimate

≈ 1–2 days. SDK field + capability shape + dispatch gate + tests + manifest doc note. No migration, no breaking API change (additive only).

---

## PE3-lite — Workflow-as-JSON endpoint

### Goal

Ship `GET /artifacts/{oid}/workflow.json` as a serializer over the existing single-parent ancestor walk. No format embedding yet. The endpoint is the reusable primitive; embed-in-PNG / embed-in-star can follow when there's demand.

### Wire shape

Re-using the structure from `PIPELINE_ERGONOMICS_PLAN.md` §PE3, scoped to single-parent lineage:

```json
{
  "magellon_workflow_version": 1,
  "exported_at": "2026-05-10T19:00:00Z",
  "lineage_shape": "single_parent_chain",
  "root_artifact": {
    "oid": "…",
    "kind": "particle_stack",
    "producer": {
      "plugin_id": "…",
      "plugin_version": "1.4.2",
      "category": "PARTICLE_EXTRACTION",
      "params": { … }
    }
  },
  "ancestors": [
    {"oid": "…", "kind": "image",        "producer": null,  "source": "imported"},
    {"oid": "…", "kind": "ctf_estimate", "producer": { … }},
    {"oid": "…", "kind": "pick_list",    "producer": { … }}
  ],
  "truncated_at_depth": null
}
```

`lineage_shape` is literal `"single_parent_chain"` — honest about the current schema. When multi-input DAG lineage lands, the value becomes `"dag"` and `ancestors` grows edges.

### Changes, file by file

**1. `CoreService/controllers/artifacts_controller.py`** — one new endpoint next to the existing `/lineage` route (line 148).

```python
@artifacts_router.get("/{oid}/workflow.json", response_model=WorkflowExport)
def get_artifact_workflow(
    oid: UUID,
    db: Session = Depends(get_db),
    user_id: UUID = Depends(get_current_user_id),
):
    """Serialize the single-parent ancestor chain + producer plugin
    metadata. Stable JSON for offline reproducibility / sharing.
    """
    root = db.query(Artifact).filter(Artifact.oid == oid).first()
    if root is None or root.deleted_at is not None:
        raise HTTPException(404, "Artifact not found")

    chain = _walk_ancestors(db, root, max_depth=200)
    return WorkflowExport(
        magellon_workflow_version=1,
        exported_at=datetime.utcnow(),
        lineage_shape="single_parent_chain",
        root_artifact=_artifact_to_workflow_node(db, root),
        ancestors=[_artifact_to_workflow_node(db, a) for a in chain],
        truncated_at_depth=200 if len(chain) >= 200 else None,
    )
```

The existing `/lineage` walk (line 167–178) uses depth 20 — re-use the same pattern, raised to 200 per the plan. Factor the walk into `_walk_ancestors(db, artifact, max_depth)` and call it from both endpoints. This is a tiny refactor; reject it if it bloats the diff.

**2. Producer extraction.** `_artifact_to_workflow_node` joins `artifact → producing_task → plugin` to recover `plugin_id`, `plugin_version`, `category`, `params`. The join already exists implicitly via `producing_task_id` (line 711). New helper, ~15 lines.

**3. Pydantic response models.** Two small classes (`WorkflowProducer`, `WorkflowNode`, `WorkflowExport`) in `models/pydantic_models.py` next to the existing `ArtifactView` / `ArtifactLineageView`.

**4. Secret redaction.** Producer `params` may contain secrets. Two options:

  - **Cheap (this slice):** Redact any param whose **key** matches `re.compile(r"(secret|password|token|api[_-]?key)", re.I)` — replace value with `"<redacted>"`. Documented behavior.
  - **Robust (later):** Manifest declares `params.<key>.export: false`. Out of scope here.

Pick (a) for now and call it out in the docstring.

**5. Tests.** Add to `tests/controllers/test_artifacts_controller.py`:

- Workflow JSON for a leaf artifact returns the full chain back to an imported root.
- Producer block populated for non-imported artifacts; `null` for the imported root.
- Param key `"api_key"` is redacted to `"<redacted>"`.
- Truncation flag set when chain exceeds depth 200.

### Acceptance

1. `GET /artifacts/{oid}/workflow.json` returns a JSON document parseable by `pydantic.BaseModel.model_validate`.
2. Output matches the existing `/lineage` ancestor list (same artifacts, same order).
3. Secret-keyed params are redacted.
4. A CLI smoke command (`curl … | jq .root_artifact.producer.plugin_id`) prints the producing plugin id without errors.

### Cost estimate

≈ 1 day. One endpoint, three Pydantic models, ≈ 50 lines of serialization, four tests.

---

## Sequencing — as shipped

Landed in four commits on `main` on 2026-05-10:

| Commit | Track | Scope |
|---|---|---|
| `e6e70e6` | docs | `PIPELINE_ERGONOMICS_PLAN.md` + this doc + README index |
| `35e7b65` | sdk | `CategoryContract.produces_subject_kind`; bump 2.2.0 → 2.3.0 + CHANGELOG entry |
| `3d5cb46` | core PE1-A | `subject_kind`/`produces_subject_kind` on `/plugins/capabilities`; `_reject_if_subject_missing` gate in `_submit_broker_job`/`_submit_broker_batch`; 3 characterization tests |
| `b747f8c` | core PE3-lite | `GET /artifacts/{oid}/workflow.json` + Pydantic models + secret redaction + 9 tests (7 happy path + 2 truncation boundary) |

Original sequencing rationale (PE1-A before PE3-lite because the SDK change is a release artifact) held.

---

## Deferred — what's worth doing next

| Track | Trigger to start | Cost when picked up |
|---|---|---|
| **PE2 dispatch cache** | After PE1-A — subject-kind-aware cache key is sharper | Migration + index + dispatcher pre-check + audit event. ≈ 1 sprint. |
| **PE3 full** — format embedding | When a real user case lands (e.g. "I exported a star file and want to re-import its lineage") | Per-format adapters; PNG `tEXt` first (drop-in zone). ≈ 3 days per format. |
| **PE4 registry UX** | After `PLUGIN_INSTALL_PLAN` P9 (hub-fetch install) | UX layer only — depends on Hub MVP. ≈ 1 sprint. |
| **Multi-input DAG lineage** | When a plugin needs to record ≥ 2 input parents (e.g. CTF + Micrograph → ParticleStack) | New `artifact_input_edge` table + migration + lineage walk update + PE3 `lineage_shape: "dag"`. ≈ 1 sprint. |

---

## Non-goals

- Backwards-incompatible changes to `CategoryContract` or `_CategoryCapabilities`. All additions are optional fields with safe defaults.
- New DB tables or migrations in this slice.
- Visual rendering of `workflow.json` in the UI. Pro workflow builder territory; OSS users get the JSON.
- Replacing the existing `/lineage` endpoint. `workflow.json` is a sibling, not a successor.
