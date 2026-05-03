# Magellon — Categories, Backends, and Wire-Shape Naming

**Status:** Canonical. Track C shipped 2026-04-27 (X.1 `0a3f216`,
X.2 `581518f`, X.3 `4639990`). SDK 1.2 → 1.3 → 2.0. Updated
2026-05-03 with the new aggregate-category seam (subject_kind on
CategoryContract + TaskMessage) and the two new categories
`PARTICLE_EXTRACTION` (code 10) + `TWO_D_CLASSIFICATION` (code 4)
landed end-to-end. See `IMPLEMENTATION_PLAN.md` "Track C" + the
2026-05-03 rollout in `CURRENT_ARCHITECTURE.md` §12.
**Audience:** Architects, plugin developers adding a second backend
under an existing category, callers using `target_backend`.
**Companion:** `ARCHITECTURE_PRINCIPLES.md`, `CURRENT_ARCHITECTURE.md`,
`MESSAGE_BUS_SPEC.md`,
`memory/project_artifact_bus_invariants.md` (the five ratified
rules driving the new aggregate-category work).

This doc proposes three additions on top of the live plugin platform:

1. A **backend** layer — a named, second axis underneath every category.
2. A **capabilities endpoint** — one URL the dispatcher and the UI both
   read for "what categories exist, what backends serve each one,
   which is the default."
3. A **wire-shape naming rule** — every class that crosses the bus ends
   in either `Envelope` or `Message`. Static metadata classes do not.

It does not change the data plane, the bus binders, or job-row
ownership. It is additive (principle 6) and reversible until the final
rename PR.

---

## 1. Why a backend layer

A `TaskCategory` answers *"what kind of work is this?"* — `CTF`,
`MOTIONCOR`, `TOPAZ_PARTICLE_PICKING`. Today, when several plugins
implement the same category, RabbitMQ round-robins between them and
CoreService picks one default per category via
`POST /plugins/categories/{category}/default`
(`plugins/controller.py:691`).

That mechanism works, but the second axis is unnamed in the wire
contract. A caller has no clean way to say *"run this CTF on ctffind4
specifically, not on whatever happens to be the current default."*
Operators who run two CTF engines side-by-side (one CPU, one GPU) for
A/B comparison have no place to record that intent on the task itself.
Logs and provenance say `plugin_id="CTF Plugin"` — uninformative when
two plugins share a category.

The fix is to give that second axis a first-class name and let it ride
on the message.

### Vocabulary: backend, not engine or impl

We use **backend**. Reasons:

- "engine" already means the algorithm itself in cryo-EM literature
  (CTF *engine* = ctffind4 vs gctf as code). Keeping it for the
  algorithm and using "backend" for the platform's substitutable slot
  avoids overloading the word.
- "impl" is the term used inside `_resolve_dispatch_target`. It is
  internal-shorthand, not user-facing. A UI label saying "Default
  impl: ctffind4" reads worse than "Default backend: ctffind4".
- RabbitMQ literature uses `provider`/`variant` interchangeably; we
  pick one term and stick with it.

**Web research confirms** the topic-exchange pattern of
`<category>.<variant>.<...>` is the canonical RabbitMQ approach for a
hierarchical second axis. See sources at the bottom of this doc.

### Backend identity

A backend is identified by a short `backend_id` — lowercase,
alphanumeric, dot-free:

```
ctffind4
gctf
gocsf
motioncor2
motioncor3
topaz
template-picker
```

One plugin = one backend. One backend can be live in multiple replicas
(scale-out); they all share the `backend_id` and the round-robin
behaviour stays. The combination
`(category, backend_id)` is the routable identity.

---

## 2. How backend rides the wire

### 2.1 PluginManifest carries `backend_id`

```python
class PluginManifest(BaseModel):
    info: PluginInfo
    backend_id: str          # NEW — required as of SDK 1.2
    capabilities: list[Capability] = []
    ...
```

Plugin authors set it once; everything else (announce subject, default
queue name, provenance stamp on `TaskResultMessage`) derives from it.

### 2.2 CategoryContract enumerates backends at registry time

```python
class CategoryContract(BaseModel):
    category: TaskCategory
    input_model: Type[BaseModel]
    output_model: Type[CategoryOutput]

    # 2026-05-03 (Phase 3d): the kind of entity tasks of this
    # category operate on. Default 'image'; aggregate categories
    # override (TWO_D_CLASSIFICATION_CATEGORY → 'particle_stack').
    # PluginBrokerRunner._stamp_subject falls back to this when
    # neither dispatch nor plugin set TaskMessage.subject_kind.
    subject_kind: str = "image"

    # NEW — populated by the liveness registry, not hand-coded.
    @property
    def known_backends(self) -> list[str]: ...

    # NEW — the operator-pinned default; falls back to first-seen
    # when unset. Same data the H1 default-impl selector already
    # tracks, just exposed under the "backend" name.
    @property
    def default_backend(self) -> str | None: ...
```

The contract object stays immutable; the live `known_backends` /
`default_backend` views read from `PluginLivenessRegistry` and
`PluginStateStore`. The contract is still the single source of truth
for I/O shape.

### 2.2a Subject axis (Phase 3, 2026-05-03)

Pre-Phase-3 every task was image-keyed: `image_job_task.image_id`
FK + `CryoEmImageInput.image_id` field. The CAN classifier doesn't
fit — its input is a particle stack drawn from M micrographs, not
a single image. The subject axis generalises the model:

| Surface | Field added | Notes |
|---|---|---|
| `TaskMessage` / `TaskResultMessage` | `subject_kind: Optional[str]` + `subject_id: Optional[UUID]` | None defaults; pre-Phase-3 callers unchanged. |
| `image_job_task` (alembic 0004) | `subject_kind` VARCHAR(32) NOT NULL DEFAULT `'image'` + `subject_id` UUID nullable | Per ratified rule 4: VARCHAR + app validation, never MySQL ENUM (the table is tens-of-millions of rows; ENUM ALTER is a multi-hour migration). Migration backfills `subject_id = image_id`. |
| `CategoryContract` | `subject_kind: str = "image"` | Declarative seam — `TWO_D_CLASSIFICATION_CATEGORY` overrides to `'particle_stack'`. |

Allowed values: `image | particle_stack | session | run | artifact`.
The runner's `_stamp_subject` precedence is **plugin-set on result >
task-set on dispatch > contract default**. Authoritative writes
still come from dispatch; the projector backfills only when dispatch
left columns at their DDL default (back-compat seam).

### 2.3 TaskMessage gains `target_backend`

```python
class TaskMessage(BaseModel):           # was TaskDto
    id: UUID
    job_id: UUID
    type: TaskCategory
    target_backend: Optional[str] = None  # NEW
    data: Dict[str, Any]
    ...
```

- `target_backend = None` → category-wide round-robin (today's
  behaviour, unchanged).
- `target_backend = "ctffind4"` → dispatch only to a backend whose
  manifest declares that id. If none is live, dispatch fails with a
  503 (same shape as `_resolve_dispatch_target` returns today).

### 2.4 Bus subjects get an optional fourth segment

Subjects today:

```
magellon.tasks.<category>             # task dispatch (broadcast)
magellon.tasks.<category>.result      # results
```

Subjects after this PR:

```
magellon.tasks.<category>                       # category-wide
magellon.tasks.<category>.<backend>             # backend-pinned (NEW)
magellon.tasks.<category>.result                # results
magellon.tasks.<category>.result.<backend>      # backend-stamped result (NEW)
```

RabbitMQ topic exchanges natively support this (sources below):
plugin queues bind on `magellon.tasks.<category>.*` so they receive
both shapes. The fourth segment is information for the dispatcher,
not a separate routing path.

The category-wide subject stays the default. **A backend-pinned
subject is only used when `target_backend` is set on the message.**
Operators flipping the per-category default does not change the
message shape — it changes which backend wins the round-robin on the
category-wide subject.

### 2.5 Routing rule (one paragraph)

`_BusTaskDispatcher.dispatch(task)`:

1. If `task.target_backend` is set, validate that backend is live for
   `task.type`. If yes, publish to
   `magellon.tasks.<category>.<backend>`. If no, raise — do not
   silently fall back to the default.
2. Else publish to `magellon.tasks.<category>` (today's path).

This satisfies principle 4: it pays its way today on two named
call sites — the operator A/B comparison case, and the importer
that already knows it wants MotionCor3 over MotionCor2 for tilt
series.

---

## 3. The capabilities endpoint

### 3.1 Why one consolidated endpoint

Today the discovery surface is split across:

- `GET /plugins/` — every plugin instance, with manifest excerpts
- `GET /plugins/categories/defaults` — the per-category default-impl
  map
- `GET /plugins/{id}/manifest` — full manifest per plugin

A UI wanting to render a "pick a backend" widget calls all three and
joins them in JS. The dispatcher reads the same data from
`get_liveness_registry()` and `get_state_store()`. Two readers, three
URLs, one shape that should be canonical.

The new endpoint collapses them:

```
GET /plugins/capabilities
```

returns one object that the UI renders directly and the dispatcher
can consume in tests:

```jsonc
{
  "categories": [
    {
      "code": 2,
      "name": "CTF",
      "description": "Contrast Transfer Function",
      "input_schema": { ... },          // CategoryContract.input_model JSON Schema
      "output_schema": { ... },
      "default_backend": "ctffind4",
      "backends": [
        {
          "backend_id": "ctffind4",
          "plugin_id": "ctf/CTF Plugin",
          "version": "0.4.1",
          "schema_version": "1",
          "capabilities": ["cpu_intensive", "idempotent"],
          "isolation": "container",
          "transport": "rmq",
          "live_replicas": 2,
          "enabled": true,
          "is_default_for_category": true,
          "task_queue": "ctf_tasks_queue"
        },
        {
          "backend_id": "gctf",
          "plugin_id": "ctf/gCTF",
          "version": "0.2.0",
          "capabilities": ["gpu_required", "idempotent"],
          ...
        }
      ]
    },
    { "code": 5, "name": "MotionCor", ... }
  ],
  "sdk_version": "0.1.0"
}
```

One read, one snapshot, every consumer aligned. Existing endpoints
stay (principle 6: additive first); they will only be removed if the
follow-up demonstrates they have no callers.

### 3.2 Dispatcher uses the same store, not the endpoint

The dispatcher stays a process-local registry — it reads
`PluginLivenessRegistry` directly, not its own HTTP endpoint. The
capabilities endpoint *projects* that store; the dispatcher
*queries* it. That keeps dispatch off the network and keeps the
"one logical owner per concept" principle (#2) intact: the registry
is the single source of backend availability.

### 3.3 Backend-pin-on-dispatch HTTP shape

The submit endpoints need an optional knob to surface backend pinning:

```
POST /plugins/{plugin_id}/jobs
{
  "input": { ... },
  "target_backend": "gctf"      // NEW — optional
}

POST /tasks/dispatch
{
  "category": "CTF",
  "data": { ... },
  "target_backend": "gctf"      // NEW — optional
}
```

The existing `plugin_id`-based form is preserved; specifying the full
`<category>/<plugin_id>` already pinned a backend in practice. The
new field is the clean way to do it for category-scoped callers.

---

## 4. Wire-shape naming rule

### 4.1 The rule

Every class that **crosses the bus or HTTP wire** ends in:

| Suffix     | Use                                                                                              |
|------------|--------------------------------------------------------------------------------------------------|
| `Envelope` | The CloudEvents 1.0 wrapper (`Envelope[DataT]` in `magellon_sdk.envelope`). One class only.      |
| `Message`  | Any payload that goes inside `Envelope.data`, OR is itself the body of a request/response/event. |

Static metadata, contracts, and value objects do **not** carry these
suffixes. They are nested or referenced — they don't travel
standalone.

### 4.2 Worked classification

| Current name              | Wire shape? | Final name                  | Notes |
|---------------------------|-------------|-----------------------------|-------|
| `Envelope[DataT]`         | yes (outer) | `Envelope[DataT]`           | unchanged |
| `TaskDto`                 | yes         | `TaskMessage`               | what we put inside `Envelope.data` for `magellon.tasks.*` |
| `TaskBase`                | —           | *deleted*                   | only `TaskDto` and `JobDto` extended it; collapse |
| `JobDto`                  | yes         | `JobMessage`                | bundle of tasks; rare on the wire today but kept symmetric |
| `TaskResultDto`           | yes         | `TaskResultMessage`         | `magellon.tasks.*.result` body |
| `TaskOutcome`             | nested      | `TaskOutcome`               | embedded inside TaskMessage; not a message itself |
| `TaskStatus`              | nested      | `TaskStatus`                | value object |
| `TaskCategory`            | nested      | `TaskCategory`              | value object |
| `CancelMessage`           | yes         | `CancelMessage`             | already correct |
| `StepStarted`             | yes (data)  | `StepStartedMessage`        | inside `Envelope[StepStartedMessage]` |
| `StepProgress`            | yes (data)  | `StepProgressMessage`       | same |
| `StepCompleted`           | yes (data)  | `StepCompletedMessage`      | same |
| `StepFailed`              | yes (data)  | `StepFailedMessage`         | same |
| `CryoEmImageTaskData`     | nested      | `CryoEmImageInput`          | inside `TaskMessage.data`; symmetric with `*Output` |
| `CtfTaskData`             | nested      | `CtfInput`                  | symmetric with `CtfOutput` |
| `FftTaskData`             | nested      | `FftInput`                  | symmetric with `FftOutput` |
| `CryoEmMotionCorTaskData` | nested      | `MotionCorInput`            | symmetric with `MotionCorOutput` |
| `MicrographDenoiseTaskData` | nested    | `MicrographDenoiseInput`    | etc. |
| `TopazPickTaskData`       | nested      | `TopazPickInput`            | etc. |
| `PtolemyTaskData`         | nested      | `PtolemyInput`              | etc. |
| `MrcToPngTaskData`        | nested      | `MrcToPngInput`             | etc. |
| `*Output` (CtfOutput, …)  | nested      | unchanged                   | already symmetric, no suffix |
| `CategoryContract`        | metadata    | unchanged                   | not a wire shape |
| `PluginInfo`, `PluginManifest`, `PluginStatus`, `Capability`, `Transport`, `IsolationLevel`, `ResourceHints`, `RequirementResult`, `CheckRequirementsResult` | metadata | unchanged | descriptive, not transmitted as standalone messages |
| `ImageMetaData`, `OutputFile`, `Detection`, `Particle`, `DebugInfo` | nested | unchanged | embedded sub-types |
| `PluginArchiveManifest`   | metadata    | unchanged                   | install-time descriptor |

Concrete-task subclasses (`FftTask`, `CtfTask`, `MotioncorTask`)
collapse out — once `*TaskData` becomes `*Input` and `TaskMessage`
generalises, the typed `TaskMessage[CtfInput]` form replaces them.

### 4.3 Why this rule and not "just rename Dto"

The existing `*Dto` set is mixed: `TaskDto` and `TaskResultDto` are
true wire envelopes; `*TaskData` is *not* — it's a nested input.
Picking `Message` as the suffix only for actual wire envelopes
preserves the boundary the codebase already drew. Using `*Input` /
`*Output` for nested shapes mirrors the symmetry already present in
`categories/outputs.py`.

---

## 5. Phasing

Three PR sequence, every step `git revert`-safe (principle 6).

### Phase X.1 — Add backend layer + capabilities endpoint (additive)

- Add `backend_id: str` to `PluginManifest`. Default to
  `info.name.lower().replace(" ", "-")` for one release so existing
  plugins don't break; deprecation-warn at startup.
- Add `target_backend: Optional[str]` to `TaskMessage` (today's
  `TaskDto`). Default `None`.
- Wire `_BusTaskDispatcher` to honour `target_backend` per §2.5.
- Add `GET /plugins/capabilities`.
- Bind plugin queues to `magellon.tasks.<category>.*` in addition to
  `magellon.tasks.<category>` (one extra binding per queue, RMQ
  topic exchange is fine with both).
- Tests: contract tests (`tests/contracts/`) gain a backend-pin case.
  `_resolve_dispatch_target` gets two new cases: pin matches, pin
  misses (503).

**No renames yet.** Today's call sites keep working unchanged.

### Phase X.2 — Wire-shape rename (alias + migrate)

- Add new names as aliases:
  ```python
  TaskMessage = TaskDto
  TaskResultMessage = TaskResultDto
  JobMessage = JobDto
  CtfInput = CtfTaskData
  ...
  StepStartedMessage = StepStarted
  ...
  ```
- Migrate call sites to import the new names. CoreService first,
  plugins second, tests third.
- Update characterization goldens in
  `CoreService/tests/characterization/`.
- Documentation walk-through (this file, `CURRENT_ARCHITECTURE.md`,
  `MESSAGES_AND_EVENTS.md`).

### Phase X.3 — Drop the aliases

- Remove `TaskDto = TaskMessage` shims and the legacy class names.
- Delete `models/plugins_models.py`'s shim if every CoreService call
  site is on the new names.
- Bump `magellon_sdk` to 0.2.0; bump `PluginInfo.schema_version`.

Plugins that haven't migrated still get a deprecation warning at
import for one release before the rename hits.

---

## 6. Risks and how to read them

- **Backend pinning over-used.** If callers reflexively set
  `target_backend`, we lose the round-robin. Mitigation:
  category-wide is the default in every importer code path; the
  field is opt-in.
- **Plugin authors hand-pick a `backend_id` that collides.** Two
  plugins claim `backend_id="ctffind4"` and the dispatcher can't
  tell them apart. Mitigation: the liveness registry rejects a
  second announce with the same `(category, backend_id)` and a
  different `plugin.version` — one of them has to rename. CoreService
  logs a `DUP_BACKEND_ID` warning to make the conflict visible.
- **Rename churn.** Phase X.2 touches every plugin. Mitigation: the
  alias landing is mechanical (one PR, one search-and-replace per
  caller); the alias-removal PR can wait a release behind it
  (principle 6).

---

## 7. What this document does not change

- **Two planes** (principle 1). Backends are control-plane only;
  bytes still flow on the data plane.
- **One job-row writer** (principle 2). `JobService` /
  `JobManager` still own the job lifecycle.
- **Existing CategoryContract I/O shapes.** `input_model` and
  `output_model` are unchanged; `*Input` / `*Output` rename is a
  type rename, not a schema change.
- **NATS / RMQ binder split.** Bus binders are unaffected.

---

## 7a. Live category catalogue (2026-05-03)

| Category | Code | Subject kind | Input model | Output model | Live backends (`backend_id`) |
|---|---|---|---|---|---|
| `FFT` | 1 | `image` | `FftInput` | `FftOutput` | `fft` (magellon_fft_plugin) |
| `CTF` | 2 | `image` | `CtfInput` | `CtfOutput` | `ctf` (magellon_ctf_plugin) |
| `PARTICLE_PICKING` | 3 | `image` | `CryoEmImageInput` (no canonical input model yet) | `ParticlePickingOutput` | `pp/template-picker` (in-process) + `template-picker` (external, Phase 6 / 2026-05-03) |
| `TWO_D_CLASSIFICATION` | 4 | **`particle_stack`** | `TwoDClassificationInput` | `TwoDClassificationOutput` | `can-classifier` (Phase 7 / 2026-05-03) |
| `MOTIONCOR` | 5 | `image` | `MotionCorInput` | `MotionCorOutput` | `motioncor` (magellon_motioncor_plugin) |
| `SQUARE_DETECTION` | 6 | `image` | `PtolemyInput` | `SquareDetectionOutput` | `ptolemy/square` (magellon_ptolemy_plugin) |
| `HOLE_DETECTION` | 7 | `image` | `PtolemyInput` | `HoleDetectionOutput` | `ptolemy/hole` (magellon_ptolemy_plugin) |
| `TOPAZ_PARTICLE_PICKING` | 8 | `image` | `TopazPickInput` | `ParticlePickingOutput` | `topaz` (magellon_topaz_plugin) |
| `MICROGRAPH_DENOISING` | 9 | `image` | `MicrographDenoiseInput` | `MicrographDenoisingOutput` | `topaz-denoise` (magellon_topaz_plugin) |
| `PARTICLE_EXTRACTION` | 10 | `image` | `ParticleExtractionInput` | `ParticleExtractionOutput` | `stack-maker` (Phase 5 / 2026-05-03) |

Subject-kind column distinguishes the only aggregate-input category
(`TWO_D_CLASSIFICATION`) from the rest. Per ratified rule 7
(extraction is per-mic, not session-merged), `PARTICLE_EXTRACTION`
stays image-keyed even though its OUTPUT is a `particle_stack`
artifact.

---

## 8. Open questions

1. **`target_backend` placement.** Inline on `TaskMessage` (chosen
   above) vs as a CloudEvents extension on `Envelope`
   (`ce_target_backend`). Inline is simpler for today; the extension
   form would survive an envelope-reshape. Decision: inline for now,
   re-evaluate when MB7 (NATS binder) lands.
2. **Per-backend DLQ.** Does a poison message on the
   `<category>.<backend>` subject route to a backend-scoped DLQ, or
   the category DLQ? Today's DLQ topology is per-queue, so the
   answer is "category DLQ" until X.1 ships and the operational
   experience says otherwise.
3. **Health vs `live_replicas`.** The capabilities endpoint exposes
   `live_replicas` as a count. Operators have asked for per-replica
   health. Out of scope for this doc; tracked separately.

---

## 9. Sources

- [RabbitMQ topic exchanges and hierarchical routing keys](https://www.rabbitmq.com/tutorials/tutorial-five-python)
- [RabbitMQ topic exchanges (CloudAMQP)](https://www.cloudamqp.com/blog/rabbitmq-topic-exchange-explained.html)
- [Celery routing — separate queues vs headers](https://docs.celeryq.dev/en/stable/userguide/routing.html)
- [CloudEvents Java SDK + Spring `Message` mapping](https://cloudevents.github.io/sdk-java/spring.html)
- [MassTransit CloudEvents discussion (envelope vs `Message`)](https://github.com/MassTransit/MassTransit/discussions/2539)
- [Knative Eventing CloudEvents `type` convention](https://knative.dev/docs/eventing/event-registry/)
- [Kubernetes aggregated discovery endpoint pattern (`/api`, `/apis`, `/openapi/v3`)](https://kubernetes.io/docs/concepts/overview/kubernetes-api/)
