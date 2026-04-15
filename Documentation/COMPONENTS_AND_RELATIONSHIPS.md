# Magellon — Components and Relationships

**Purpose:** Canonical source for the infographic set. Every component name,
arrow label, and zone grouping below is meant to be used verbatim in
diagrams. Keep this doc terse; prose lives in `CURRENT_ARCHITECTURE.md` and
`TARGET_ARCHITECTURE_AND_PLAN.md`.

**Status:** Target (minimal working) architecture. No commercial/community
tier split yet — we are keeping Temporal, NATS, and Dragonfly in the stack
to learn and test.

---

## 1. Zones

Six zones, in dependency order from user-facing to foundational:

1. **User surface** — what a human touches
2. **Application** — the stable API and data model
3. **Orchestration** — workflow engine + workers
4. **Event & data plane** — bus, state, cache
5. **Plugin runtime** — where plugin code actually runs
6. **Plugin ecosystem** — SDK + Plugin Hub

A seventh zone, **Observability**, sits alongside all of them.

---

## 2. Component inventory

| Zone               | Component          | Kind                | Role                                                                       |
|--------------------|--------------------|---------------------|----------------------------------------------------------------------------|
| User surface       | **Researcher**     | Actor               | Submits jobs, reviews results, browses plugins                             |
| User surface       | **Plugin Author**  | Actor               | Develops a plugin locally, publishes to the hub                            |
| User surface       | **Magellon Web**   | React SPA           | Main UI. REST + Socket.IO client                                           |
| User surface       | **Plugin CLI**     | `magellon-plugin`   | Scaffold, test, publish plugins. Ships with the SDK                        |
| Application        | **CoreService**    | FastAPI app         | Auth (Casbin + RLS), data model, import pipelines, plugin HTTP controller  |
| Application        | **JobService**     | Module in CoreService | Thin boundary: inserts job row, starts workflow, projects events into row |
| Application        | **UI Gateway**     | NATS→Socket.IO bridge | Forwards bus events to the browser per-`sid`                              |
| Orchestration      | **Temporal**       | Server              | Durable workflow state, retries, cancellation, queries, Web UI             |
| Orchestration      | **Temporal Worker**| Process per plugin  | Polls Temporal task queue, runs plugin activities                          |
| Event & data plane | **NATS JetStream** | Event bus           | Carries CloudEvents on `magellon.job.*` / `magellon.step.*` / `magellon.worker.*` |
| Event & data plane | **MySQL**          | RDBMS               | State of record: users, sessions, images, jobs, tasks, results              |
| Event & data plane | **Dragonfly**      | KV + pub/sub        | Idempotency tokens, rate limits, cache. Not a job store                    |
| Plugin runtime     | **Executor**       | SDK abstraction     | Strategy for *where* a plugin runs                                         |
| Plugin runtime     | ↳ LocalProcess     | Executor            | Same OS process as the worker                                              |
| Plugin runtime     | ↳ LocalDocker      | Executor            | Spawn container via Docker SDK                                             |
| Plugin runtime     | ↳ Kubernetes       | Executor            | Create a `Job` object                                                      |
| Plugin runtime     | ↳ RunPod           | Executor            | `POST /run` → webhook-driven cloud GPU                                     |
| Plugin runtime     | ↳ SLURM            | Executor            | `sbatch` + `sacct` poll                                                    |
| Plugin ecosystem   | **Magellon SDK**   | Python package      | `PluginBase`, `ProgressReporter`, `Executor`, CLI. The plugin contract     |
| Plugin ecosystem   | **Plugin Hub**     | Web service         | Discover, publish, version, install plugins. Like HuggingFace Hub for plugins |
| Plugin ecosystem   | ↳ Hub API          | REST                | `GET /plugins`, `POST /plugins/<id>/versions`, package download            |
| Plugin ecosystem   | ↳ Hub Web          | UI                  | Browse, search, read plugin cards                                          |
| Plugin ecosystem   | ↳ Hub Storage      | Object store        | Plugin packages (wheels + manifests + schemas)                             |
| Plugin ecosystem   | ↳ Hub Metadata     | DB                  | Plugin records, versions, authors, ratings                                 |
| Observability      | Prometheus         | Metrics scraper     | Scrapes `/metrics` from CoreService and workers                            |
| Observability      | Grafana            | Dashboards          | Operator view of the stack                                                 |
| Observability      | Consul             | Service discovery   | Workers and executors register here                                        |

---

## 3. Three canonical flows

These are the three flows every infographic should be able to tell. Arrow
labels are canonical — reuse them.

### Flow A — Submit and run a job

```
Researcher ─ submit ─► Magellon Web ─ POST /plugins/<id>/jobs ─► CoreService
                                                                 │
                                                                 │ insert row
                                                                 ▼
                                                               MySQL
                                                                 │
                                          CoreService ─ start_workflow ─► Temporal
                                                                          │
                                                                          │ dispatch
                                                                          ▼
                                                                   Temporal Worker
                                                                          │
                                                                          │ Executor.submit
                                                                          ▼
                                                                        Plugin
                                                                          │
                                                                          │ reporter.report
                                                                          ▼
                                                                 NATS (step.progress)
                                                                          │
                    ┌─────────────────────────────────────────────────────┤
                    ▼                                                     ▼
               UI Gateway                                          JobService projector
                    │                                                     │
                    │ Socket.IO emit                                      │ UPDATE job row
                    ▼                                                     ▼
              Magellon Web                                             MySQL
```

**Numbered steps for an infographic:**

1. Researcher submits from the browser.
2. CoreService authorises and inserts a `job` row in MySQL.
3. CoreService starts a Temporal workflow keyed by the job id.
4. Temporal dispatches activities to the worker for that plugin.
5. Worker asks the Executor to run the plugin (locally, Docker, RunPod…).
6. Plugin calls `reporter.report(percent, msg)` as it works.
7. Reporter publishes `magellon.step.progress` on NATS.
8. UI Gateway forwards the event to the browser over Socket.IO.
9. JobService projector updates the MySQL row so REST queries see progress.
10. On completion, workflow returns; JobService marks the row complete and
    publishes `magellon.job.completed`.

### Flow B — Publish and install a plugin (Plugin Hub)

```
Plugin Author ─ magellon-plugin new ─► local project (scaffold)
                │
                │ code + tests
                ▼
         Plugin Author ─ magellon-plugin publish ─► Plugin Hub API
                                                     │
                                                     ├─ write → Hub Storage (wheel)
                                                     └─ write → Hub Metadata (version row)

Researcher ─ browse ─► Plugin Hub Web ─ read ─► Hub Metadata
                │
                │ "install X"
                ▼
       CoreService admin ─ GET /plugins/<id>/versions/<v> ─► Hub API
                            │
                            ▼
                    download wheel ─► pip install into CoreService env
                            │
                            ▼
               PluginRegistry.refresh() — plugin appears in /plugins/
```

**Numbered steps:**

1. Author scaffolds a plugin with the CLI (`magellon-plugin new`).
2. Author implements `execute()`, writes tests, runs them locally.
3. Author publishes with `magellon-plugin publish` — CLI uploads the wheel
   to Hub Storage and creates a version row in Hub Metadata.
4. Researcher browses the Hub web UI, reads the plugin card, reviews
   versions and schemas.
5. Admin installs the plugin into CoreService; the registry picks it up on
   refresh.
6. The plugin immediately appears under `/plugins/` — no code change to
   CoreService.

### Flow C — Real-time progress

```
Plugin ─ reporter.report ─► NATS (magellon.step.progress)
                                │
                ┌───────────────┼────────────────┐
                ▼               ▼                ▼
          UI Gateway      JobService        Audit log
                │           projector      subscriber
                │               │                │
                │ Socket.IO     │ UPDATE         │ append
                ▼               ▼                ▼
          Magellon Web      MySQL row      log store
```

**Design note:** Every consumer (UI, MySQL projection, audit log, metrics
collector) subscribes to the same subject. There is **no polling** and **no
direct call** from the plugin to the UI or to the DB. Everything flows
through the bus. This is the actor/message-pump pattern, with NATS as the
mailbox.

---

## 4. Relationship map (dense view — for the "architecture at a glance" infographic)

```
                        ┌────────────────────────┐
                        │       Researcher       │
                        │     Plugin Author      │
                        └───────────┬────────────┘
                                    │
                ┌───────────────────┼───────────────────┐
                │                   │                   │
                ▼                   ▼                   ▼
         ┌────────────┐       ┌──────────┐       ┌────────────┐
         │ Magellon   │       │ Plugin   │       │ Plugin Hub │
         │   Web      │       │   CLI    │──────►│    Web     │
         └─────┬──────┘       └────┬─────┘       └─────┬──────┘
               │ REST + WS         │ publish           │
               ▼                   ▼                   ▼
         ┌──────────────────────────────┐       ┌────────────┐
         │         CoreService          │       │  Hub API   │
         │   (FastAPI, JobService,      │◄─────►│            │
         │    UI Gateway, PluginRegistry)│       └─────┬──────┘
         └────┬──────────┬──────────┬───┘             │
              │          │          │                 ▼
              │ start    │ insert   │ publish    ┌────────────┐
              ▼          ▼          ▼            │    Hub     │
         ┌─────────┐  ┌──────┐ ┌─────────┐       │  Storage   │
         │Temporal │  │MySQL │ │  NATS   │       │+ Metadata  │
         └────┬────┘  └──────┘ └────┬────┘       └────────────┘
              │ poll              ▲ │
              ▼                   │ │ subscribe
         ┌───────────┐            │ │
         │  Temporal │────────────┘ │
         │   Worker  │              │
         └─────┬─────┘              │
               │ Executor.submit    │
               ▼                    │
         ┌───────────┐              │
         │  Plugin   │──────────────┘
         │  (SDK)    │  reporter.report
         └─────┬─────┘
               │ runs on
               ▼
   LocalProcess │ LocalDocker │ Kubernetes │ RunPod │ SLURM
```

Legend:

- **Solid lines** = request/call (synchronous or RPC)
- **Arrow labels** = operation verb (submit, publish, poll, etc.)
- **Dashed subscribe arrows** (not drawn above due to ASCII) = event subscription on NATS

---

## 5. Data contracts in one view

Three contracts appear on every diagram — keep their names consistent:

| Contract         | Owner          | Where on the wire                                   |
|------------------|----------------|-----------------------------------------------------|
| **Envelope**     | Magellon SDK   | Every NATS message, every plugin input/output       |
| **Plugin Info**  | Plugin author  | `/plugins/<id>/info`, Hub Metadata                  |
| **Job Row**      | JobService     | MySQL `jobs` table, REST `/plugins/jobs/<id>`       |

**Envelope shape** (CloudEvents frame + typed payload — "packet and data" in
Magellon's original language):

```
┌──────────────────── envelope ─────────────────────┐
│ specversion   "1.0"                               │
│ id            ULID                                │
│ source        "magellon/core" | "magellon/plugin" │
│ type          "magellon.job.progress.v1"          │
│ subject       "job/<job_id>"                      │
│ time          RFC3339                             │
│ dataschema    "magellon://schemas/.../v1"         │
│ datacontenttype "application/json"                │
│ ┌─────────────── data ─────────────────────────┐  │
│ │ Pydantic-validated payload, per schema       │  │
│ │ e.g. { job_id, step_id, percent, message }   │  │
│ └──────────────────────────────────────────────┘  │
└───────────────────────────────────────────────────┘
```

---

## 6. Deployment view (one box = one container)

```
┌─────────────────────────── docker-compose ──────────────────────────┐
│                                                                     │
│  ┌─────────────┐  ┌────────────┐  ┌────────────┐  ┌──────────────┐  │
│  │ core_service│  │  temporal  │  │    nats    │  │   mysql      │  │
│  │  (FastAPI)  │  │  (server)  │  │ (jetstream)│  │              │  │
│  └─────────────┘  └────────────┘  └────────────┘  └──────────────┘  │
│                                                                     │
│  ┌─────────────┐  ┌────────────┐  ┌────────────┐  ┌──────────────┐  │
│  │ worker_ctf  │  │ worker_mc  │  │ worker_pp  │  │  dragonfly   │  │
│  │             │  │            │  │            │  │              │  │
│  └─────────────┘  └────────────┘  └────────────┘  └──────────────┘  │
│                                                                     │
│  ┌─────────────┐  ┌────────────┐  ┌────────────┐  ┌──────────────┐  │
│  │ plugin_hub  │  │ hub_storage│  │ prometheus │  │   grafana    │  │
│  │  (API+Web)  │  │  (MinIO)   │  │            │  │              │  │
│  └─────────────┘  └────────────┘  └────────────┘  └──────────────┘  │
│                                                                     │
│  ┌─────────────┐                                                    │
│  │   consul    │                                                    │
│  │             │                                                    │
│  └─────────────┘                                                    │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 7. Infographic guidance

Suggested set of three infographics from this document:

### Infographic 1 — "Magellon at a glance"
Zone-coloured boxes, one per entry in the inventory (§2). Thin arrows for
the main flows (§3). Target audience: new team members, conference poster,
website homepage.

- Use the six zones as colour bands.
- Highlight **Plugin Hub** and **SDK** as the "ecosystem" story.
- Keep Observability visually subdued (it's plumbing).

### Infographic 2 — "Submit a job"
Horizontal timeline of Flow A (§3). Ten numbered steps, icons for each
component. Target audience: developers evaluating Magellon, docs landing
page.

- Show both the request path (top) and the event path (bottom).
- Emphasise that progress flows through NATS, not through HTTP polling.

### Infographic 3 — "Plugin ecosystem"
Flow B (§3) with the Hub centred. Show three personas: **Author**,
**Researcher**, **Operator**. Target audience: plugin developer docs,
marketing for the hub.

- Authors push, researchers discover, operators install.
- Version lane on the right (semver badges).
- Schema-version pinning as a callout.

---

## 8. Name glossary (use these exact terms in diagrams)

| Prefer              | Not                                     |
|---------------------|-----------------------------------------|
| **CoreService**     | "backend", "the API", "core"            |
| **JobService**      | "job manager", "orchestrator"           |
| **Temporal Worker** | "activity runner", "executor" (ambiguous) |
| **Executor**        | "runner", "backend" (overloaded)        |
| **Plugin Hub**      | "plugin marketplace", "registry" (overloaded with PluginRegistry) |
| **Magellon SDK**    | "plugin framework", "plugin lib"        |
| **Magellon Web**    | "frontend", "the UI"                    |
| **Envelope**        | "message", "packet" (use "envelope" in diagrams; "packet and data" is fine in prose) |

Consistent names across infographics matter more than the specific choice.
If a future doc diverges, update this file first.
