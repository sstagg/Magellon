# Magellon — Unified Platform Plan

**Status:** Proposal, 2026-04-17. Companion to `MESSAGE_BUS_SPEC.md` (the bus foundations the unified architecture composes over).
**Scope:** Retire the dual plugin architecture, then build toward a plugin hub on top of one coherent contract.
**Not in scope:** MB7 (second binder), orchestration engines, UI redesigns outside the plugins page.

---

## 1. Why

Magellon currently has two plugin architectures living side-by-side:

- **In-process plugins** live under `CoreService/plugins/<category>/<name>/service.py` as `PluginBase` subclasses. They're discovered by a filesystem walk at startup (`plugins/registry.py`) and invoked via `POST /plugins/{id}/jobs`, which calls `plugin.run(input)` directly in the CoreService process.
- **Broker plugins** live in their own repos / Docker images (`plugins/magellon_*_plugin/`). They announce themselves on `magellon.plugins.liveness`, consume from RMQ category queues via `PluginBrokerRunner`, and publish results back to the bus. Dispatch flows through `bus.tasks.send`.

The two paths diverged out of migration order — MB0–MB6 introduced the bus and moved external plugins to it; in-process plugins haven't moved yet. Every divergence is a tax:

- Two discovery mechanisms (filesystem walk vs liveness heartbeat) → `/plugins/` page missed FFT until 2026-04-17.
- Two dispatch code paths (`plugin.run()` vs `bus.tasks.send`) → every new dispatch feature has to be implemented twice or gets skipped on one side.
- Two status sources, two failure modes (Python exception vs envelope-with-error), two result projections.
- No clean story for "swap the default FFT with a user-supplied one" — the in-process version can't be replaced at runtime without a CoreService restart.

One architecture, multiple deployment topologies, multiple invocation modes (see §3) is the target shape. This doc sequences the migration.

---

## 2. Target architecture

### 2.1 One plugin contract

Every plugin is a `PluginBase[InputT, OutputT]` subclass. `execute(input_data) -> output` is the only business-logic surface a plugin author writes. No branches on topology.

### 2.2 One discovery path

Every plugin announces itself on `magellon.plugins.liveness` (announce on boot, heartbeat every 15s). `CoreService.core.plugin_liveness_registry` is the single source of truth. The filesystem walk in `plugins/registry.py` goes away.

**In-process plugins announce too.** They run a `PluginBrokerRunner` inside the CoreService Python process; it calls `install_rmq_bus(settings)` at startup and announces via the same discovery code external plugins use. The fact that the consumer lives in-process is a *deployment topology*, not a different path.

### 2.3 One invocation path

All dispatch goes through `bus.tasks.send(route, envelope)`. The HTTP endpoints (`POST /plugins/{id}/jobs`, `/image/fft/dispatch`, etc.) become thin shims that wrap input + publish. They don't know (or care) whether the receiver is in-process, in a container, or remote.

### 2.4 Deployment topologies (orthogonal to contract)

- **in-process** — `PluginBrokerRunner` spawned inside CoreService on startup. Same queue a container would consume. Good for dev, plugins that need DB access, zero-Docker deployments.
- **container** — Docker image running `PluginBrokerRunner`. Same queue. Good for GPU, isolation, heterogeneous hosts, horizontal scale.
- **subprocess** — spawn per-task, consume one and exit. For legacy binaries and strict quarantine.
- **remote-host** — future; no contract change.

Multiple instances of the same implementation compete naturally on the same queue — RMQ round-robins deliveries. `2 bare-metal + 6 containers = 8 instances` works out of the box.

### 2.5 Invocation modes (orthogonal to topology)

- **async bus** — default. Publish → fire-and-forget. Result comes back as a result envelope + step-event stream.
- **sync bus (request/reply)** — future SDK primitive for UI blocking on human input (e.g. plugin-runner "Run" button). Correlation-ID over the bus. Works with any topology.
- **preview** — explicit `Capability.PREVIEW` opt-out. Sync HTTP to the plugin's own `/preview` endpoint for interactive UX (`pp/template-picker` today). Bypasses the bus. Documented as an exception, not a general path.

**No direct in-process call escape hatch.** Tests don't use one; they use the in-memory or mock binder (see §2.6).

### 2.6 Test strategy — bind, don't bypass

We already shipped three binders (MB1–MB2). They are the test strategy:

| Binder | `install_*_bus()` | Use case | Sync? |
|---|---|---|---|
| **RMQ** | `install_rmq_bus` | Production, local dev with `docker compose`. | No |
| **In-memory** | `install_inmemory_bus` | Integration tests, local dev without RMQ. Broker-shaped semantics, real threads. | No |
| **Mock** | `install_mock_bus` | Unit tests, asserting on published envelopes without threads. | **Yes** |

**Rule:** no test uses RabbitMQ. Plugin-layer unit tests use mock. Integration tests use in-memory. Docker-level smoke tests use RMQ against a container. Any test reaching for `install_rmq_bus` needs justification in review.

---

## 3. Hub vision (outcome of the whole program)

Long-term target: `/en/panel/plugins` is a marketplace. Users browse available implementations, compare popularity, install, enable/disable. The platform supports multiple implementations of the same capability coexisting or replacing each other.

Mechanics enabled by the unified architecture:

- A plugin is a Docker image / pip package that declares: which capability it provides (`fft`, `ctf`, `motioncor`, custom), SDK version it was built against, resource hints, input/output JSON schemas.
- A user uploads a plugin archive or provides a URL → review workflow → if approved, the plugin becomes installable from the plugins page.
- Capability routing lets operators choose which implementation handles which jobs.
- Reproducibility: every `image_job` row carries `plugin_id + version` of the implementation that ran it.

What prevents this today:

- Contract isn't SemVer-stable. Field-default shifts (e.g. `outputFile` typo fix) ripple through third-party plugins.
- No capability routing — multiple implementations on the same queue just compete at RMQ round-robin.
- No install flow, no archive format, no review workflow, no central registry.
- No two-tier trust (verified vs community) — real concern for scientific compute where a malicious or buggy plugin's output looks plausible.

---

## 4. Phase sequence

### U — Unify architecture

| Phase | Goal | Est |
|---|---|---|
| **U1** | Retire the dual plugin architecture. `/plugins/` backed by liveness registry only. In-process plugins run `PluginBrokerRunner`. Dispatch always via bus. Tests migrate to mock/in-memory binders. | 1–2 sessions |
| **U2** | SDK SemVer hardening. Freeze `magellon_sdk.models.*` public shapes behind major-version bumps. Document contract surface. Plugins pin `magellon-sdk>=1.0,<2.0`. | 1 session |

### H — Hub foundations

| Phase | Goal | Est |
|---|---|---|
| **H1** | Per-plugin enable/disable toggles in `/plugins` UI. Per-implementation queues (route `magellon.tasks.fft.<impl-id>`) so installing a replacement doesn't just load-balance with the default. | 2–3 sessions |
| **H2** | Install-from-URL / Install-from-image flow on the plugins page. `POST /plugins/install` accepts a Docker image ref or Git URL, CoreService spawns a managed subprocess/container that runs the plugin, announces on the bus, shows up in the UI. No central registry yet. | 1–2 sessions |
| **H3a** | Plugin archive format spec (manifest.yaml + Dockerfile or source + dependencies). Author tooling (`magellon-sdk plugin init`, `magellon-sdk plugin pack`). | 1–2 sessions |
| **H3b** | Upload-and-review workflow. Author submits archive → automated checks (contract pinning, SDK version, manifest validity, schema emit) → human review for verified tier. | 3+ sessions |
| **H3c** | Central registry service. Search, popularity metrics, install-by-id. Two-tier trust (verified / community). | 5+ sessions |

### S — Small enablers (can slot in anywhere)

| Item | Rationale | Est |
|---|---|---|
| **Input/output JSON schemas in manifest** | Plugins already have `input_schema()` / `output_schema()` Pydantic classes. Emitting `model_json_schema()` in `PluginManifest` unlocks form rendering, upload validation, cross-version compatibility checks. | 30 min |
| **Reproducibility audit** | Every `image_job` row should show `plugin_id + plugin_version`. Most infrastructure is there via `TaskResultDto.plugin_id/plugin_version`; just surface it in the UI. | 1 session |
| **Plugin lifecycle API** | `/admin/plugins/{id}/stop`, `/start`, `/restart` — needed before H1 is usable. | 1 session |

---

## 5. Hard parts (up front, not surfacing mid-phase)

### 5.1 `pp/template-picker` preview

Sub-100ms interactive UX. The bus roundtrip — even in-memory — is the wrong tool. Keep `Capability.PREVIEW` as the explicit opt-out. Document it as the one exception to "everything through the bus."

### 5.2 In-process plugins sharing CoreService's DB session

In-process `TaskOutputProcessor` writes DB rows. Post-MB4.5 this logic lives in CoreService's in-process result consumer; plugins just publish results. The split is clean: **plugins compute, CoreService owns state.** In-process plugins don't get DB access just because they're in-process — they publish results and CoreService's result consumer writes DB rows, same path containers use.

### 5.3 Discovery timing

External plugins announce asynchronously. Dispatch-before-announce races: publish a task before any consumer exists. RMQ queues the task until a consumer attaches — fine for short delays. For long ones (no consumer ever attaches), need a timeout → fail job policy. Already partially addressed by existing binder reconnect logic; formalize in H1.

### 5.4 Scientific reproducibility

A misbehaving plugin that returns plausible-looking wrong defocus values is hard to detect. Mitigations across the program:

- **U2**: SemVer contract hardening means which fields mean what is stable across versions.
- **H3b**: automated contract-validation checks before a plugin enters the hub.
- **Two-tier trust** in the hub (verified vs community).
- **Reproducibility audit** (S-tier): every result carries plugin_id + version; operators can cross-check.

This is fundamentally a *community + review* problem, not just a technical one. Don't hand-wave.

### 5.5 Versioning and upgrade pain

If CoreService upgrades its SDK to 2.0 while the user has a community plugin pinned to 1.x, the plugin breaks. Policies to decide:

- Does CoreService refuse to dispatch to a plugin with incompatible SDK version? (Yes — fail-fast is better than silent data corruption.)
- Does the UI warn before upgrading?
- How long do we support each major?

This is a U2 deliverable.

---

## 6. Definition of Done

End of U1:
- `GET /plugins/` returns only liveness-registry entries. `plugins/registry.py` deleted.
- `POST /plugins/{id}/jobs` publishes via `bus.tasks.send`, not `plugin.run()`.
- `CoreService/plugins/*/service.py` files deleted (their broker-side equivalents already exist).
- All tests use `install_mock_bus` or `install_inmemory_bus`; no test imports pika or starts an RMQ container.
- Docker-level smoke tests use real RMQ in their container.

End of U2:
- `magellon-sdk` ships v1.0 with a frozen `magellon_sdk.models.*` public surface.
- Deprecation policy documented.
- All shipping plugins pin `magellon-sdk>=1.0,<2.0`.

End of H1:
- Plugin Browser has per-plugin enable/disable toggles.
- Installing a second FFT implementation doesn't auto-load-balance with the default; operator chooses.

End of H3c:
- Third-party plugin authors can submit archives, get reviewed, and users can install their plugins from the UI without code changes to CoreService.

---

## 7. What we are NOT doing in this plan

- **Workflow engine reintroduction.** Temporal was reverted for a reason. See `feedback_yagni_orchestration`.
- **Envelope format changes.** CloudEvents 1.0 stays.
- **Multi-language plugins.** Python-only for now. The contract is JSON-serializable so cross-language is possible in principle, but adding it pre-hub is premature abstraction.
- **Distributed tracing / OpenTelemetry.** Orthogonal. Rides the envelope when it lands; not a phase.
- **Plugin runtime sandboxing (cgroups, seccomp).** Container isolation is enough for V1. Real sandboxing is a hub-tier item for community plugins, not a foundation.
