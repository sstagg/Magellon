# Magellon — Operations (Runbooks + Cheatsheets + Reference)

**Status:** Consolidated reference. Merged from five source documents on 2026-05-13.
**Audience:** Operators running Magellon in dev or production; SRE-style readers needing recovery / migration / drain procedures.
**Companion:** `ARCHITECTURE.md`, `PLUGINS.md`, `SECURITY.md`.

Procedure-oriented documentation: how to migrate the DLQ topology, what
the day-to-day command snippets look like, how task data shapes have
changed across versions, and the DB schema reference.

## Contents

1. [DLQ Topology Migration Runbook](#1-dlq-topology-migration-runbook)
2. [Common Commands](#2-common-commands)
3. [Task Data — Shape Comparison](#3-task-data--shape-comparison)
4. [Database Schema Reference (CoreService)](#4-database-schema-reference-coreservice)
5. [CoreService docs/architecture stub](#5-coreservice-docsarchitecture-stub)
6. [Legacy Documentation index](#6-legacy-documentation-index)

---

<!--
  Section: 1. DLQ Topology Migration Runbook
  Originated from: Documentation/DLQ_MIGRATION_RUNBOOK.md
  Merged into this consolidated reference 2026-05-13.
-->

# DLQ Topology Migration — Operator Runbook (MB6.4)

**Status:** Ops procedure, 2026-04-21. Paired with
`CoreService/scripts/migrate_dlq_topology.py`.
**Risk:** High. This is the single non-revertible-by-`git revert`
operation in the MessageBus migration plan.
**Companion:** `MESSAGE_BUS_SPEC.md` §7.2 (DLQ design); this runbook
was originally inline in the spec's §9.6.1 and extracted here
2026-04-21 alongside the MB6.4 script.

---

## What this migrates

Seven production RMQ queues that predate MB6.4 have no dead-letter
exchange wired:

| Queue | Exchange | Routing keys |
|---|---|---|
| `ctf_tasks_queue` | default | — |
| `motioncor_tasks_queue` | default | — |
| `fft_tasks_queue` | default | — |
| `ctf_out_tasks_queue` | default | — |
| `motioncor_out_tasks_queue` | default | — |
| `fft_out_tasks_queue` | default | — |
| `core_step_events_queue` | `magellon.events` | `job.*.step.*` |

After the migration each queue is declared with
`x-dead-letter-exchange=""` + `x-dead-letter-routing-key=<queue>_dlq`
and a companion `<queue>_dlq` queue exists to catch poisoned messages.

## Why it cannot be a quiet rolling change

RabbitMQ returns `PRECONDITION_FAILED` (code 406) if you try to
redeclare a queue with different `x-*` args than it was created with.
The only path to retrofit DLQ args is **`queue_delete` + `queue_declare`**
— and `queue_delete` drops any messages in the queue. So a brief
outage window is unavoidable.

## Preconditions

Check all of these before executing in production.

1. **Dry-run on staging is signed off.** Run
   `python scripts/migrate_dlq_topology.py --dry-run --all
   --rmq-url amqp://…@staging-rmq:5672/` against a staging replica of
   production topology. The output should be error-free and match
   the expected queue list.
2. **All producers stopped.** No `bus.tasks.send` / `bus.events.publish`
   call is in flight. In docker-compose this usually means scaling
   CoreService to 0 and keeping the frontend off.
3. **All consumers stopped.** Plugin containers scaled to 0 (CTF,
   MotionCor, FFT, result processor). CoreService's in-process
   result-consumer exits with CoreService shutdown.
4. **Queues are empty.** `rabbitmqctl list_queues name messages_ready
   messages_unacknowledged consumers` returns 0 for all three counters
   on each target queue. The migration script also checks this and
   refuses to proceed otherwise; this is a belt-and-braces step.
5. **Backup.** Not strictly required for queue topology but take one
   anyway: `rabbitmqctl export_definitions /path/to/backup.json`.

## Execution

Run in a scheduled ops window. The window needs to cover:

- ~30 seconds of actual migration (per queue: declare DLQ + delete
  main + redeclare main + rebind, all sub-second; script loops
  sequentially).
- Time to scale consumers/producers back up after verify.

### Per-queue step order (failure-safe)

The script applies operations in this order so a partial failure
leaves the system recoverable:

1. **Declare the DLQ** (`<queue>_dlq`). Idempotent if it already
   exists. If this step fails, the main queue is still untouched —
   operator fixes the cause and reruns.
2. **Delete the main queue** (`if_empty=True, if_unused=True`). Now
   the destructive part begins; the DLQ already exists so the
   recovery surface is "redeclare main", not "rebuild DLQ + main".
3. **Redeclare the main queue with DLQ args**.
4. **Rebind** the main queue to its exchange / routing keys (only
   `core_step_events_queue` has bindings; the task / out queues use
   the default exchange).

Live run for all production queues:

```
cd CoreService
python scripts/migrate_dlq_topology.py \
    --all \
    --yes \
    --rmq-url amqp://rabbit:PASSWORD@PROD-HOST:5672/
```

`--yes` is required for `--all` in live mode. It is the sign-off
that you've read this runbook; the script refuses without it.

For a single queue:

```
python scripts/migrate_dlq_topology.py \
    --queue ctf_tasks_queue \
    --rmq-url amqp://rabbit:PASSWORD@PROD-HOST:5672/
```

## Verify after execution

1. **DLQ wiring visible.** Run the script's verify mode:

    ```
    python scripts/migrate_dlq_topology.py --verify --all \
        --rmq-url amqp://rabbit:PASSWORD@PROD-HOST:5672/
    ```

    Every target queue should report `DLQ-wired`.

2. **Companion DLQs exist.** `rabbitmqctl list_queues name` should
   now show `ctf_tasks_queue_dlq`, `motioncor_tasks_queue_dlq`, etc.

3. **Poison-message smoke test** (on staging replica or the quietest
   prod queue): publish a deliberately-malformed message and confirm
   it routes to the DLQ. Example with `rabbitmqadmin`:

    ```
    rabbitmqadmin publish exchange="" routing_key=ctf_tasks_queue \
        payload='{not-valid-json}'

    # Start a plugin replica pointed at staging; let it reject.
    # Then:
    rabbitmqadmin get queue=ctf_tasks_queue_dlq count=1
    # Should return the malformed payload.
    ```

4. **Start producers + consumers back up.** Scale plugin containers
   to their production replica count; restart CoreService. Confirm
   a normal import flows end-to-end.

## Rollback

The destructive steps (delete + redeclare + rebind) are not
reversible by `git revert`. Rollback options:

1. **Redeclare without DLQ args.** Run the script with a `--no-dlq`
   flag (TODO: add if rollback ever becomes likely — current script
   only has the forward path because rollback during the ops window
   is expected to be rare). Manual equivalent: `queue_delete` each
   migrated queue and `queue_declare` without `x-*` args.
2. **Restore from `export_definitions` backup** taken in the
   preconditions. Broker-wide but clean.

Either way: messages dispatched during the rollback window publish
successfully — the pre-MB6.4 state (no DLQ) is a valid equilibrium.

## Why this script is a one-shot and not ongoing automation

New queues created after MB6.4 land should call
`RabbitmqClient.declare_queue_with_dlq` at construction time
(`magellon_sdk.bus.binders.rmq._client`). The binder already does
this for bus-declared queues via `TaskConsumerPolicy(dlq_enabled=True)`.
This script only exists for the one-time migration of queues that
existed before DLQ wiring was possible. After it runs once cleanly,
the script itself becomes archaeology — safe to delete.


---

<!--
  Section: 2. Common Commands
  Originated from: Documentation/commands.txt
  Merged into this consolidated reference 2026-05-13.
-->

sed -i 's/^#*\s*PermitRootLogin .*/PermitRootLogin yes/' /etc/ssh/sshd_config
systemctl restart sshd

touch /var/lib/mysql/mysql.pid
touch /var/lib/mysql/mysqld.sock
chown mysql:mysql -R /var/lib/mysql/mysql.pid
chown mysql:mysql -R /var/lib/mysql/mysqld.sock
rm -rf /var/lib/mysql/grastate.dat /var/lib/mysql/gvwstate.dat

mysqld --wsrep-recover
systemctl start mysql@bootstrap.service
systemctl start mysqld


       wget http://www.severalnines.com/downloads/cmon/install-cc
       chmod +x install-cc
       ssh-keygen -t rsa
       ssh-copy-id root@185.170.8.16
       ssh-copy-id root@185.170.8.17
       ssh-copy-id root@185.170.8.18
       ./install-cc


---

<!--
  Section: 3. Task Data — Shape Comparison
  Originated from: Documentation/task-data-comparison.txt
  Merged into this consolidated reference 2026-05-13.
-->

Task data classes — side-by-side comparison
=============================================

Source: magellon-sdk/src/magellon_sdk/models/tasks.py
Confirmed: there is NO ``MotionCorTaskData`` class in the SDK or in
any plugin. The only MotionCor-related task data class is
``CryoEmMotionCorTaskData``. Both ``CtfTaskData`` and
``CryoEmMotionCorTaskData`` extend the same base
``CryoEmImageTaskData``.


Common base — CryoEmImageTaskData (lines 112–121)
-------------------------------------------------
Every task-data class below inherits these:

    image_id      : Optional[UUID]
    image_name    : Optional[str]
    image_path    : Optional[str]
    engine_opts   : Dict[str, Any]   # opaque plugin-specific extras


CtfTaskData (lines 137–150)              CryoEmMotionCorTaskData (lines 153–185)
-------------------------------          ---------------------------------------
inputFile           : str                inputFile          : str
outputFile          : str = "ouput.mrc"  outputFile         : str = "output.mrc"
pixelSize           : float = 1.0        PixSize            : Optional[float] = None
accelerationVoltage : float = 300.0      kV                 : int = 300
sphericalAberration : float = 2.70       Cs                 : int = 0
amplitudeContrast   : float = 0.07       AmpCont            : float = 0.07
sizeOfAmplitudeSpectrum : int = 512      —
minimumResolution   : float = 30.0       —
maximumResolution   : float = 5.0        —
minimumDefocus      : float = 5000.0     —
maximumDefocus      : float = 50000.0    —
defocusSearchStep   : float = 100.0      —
binning_x           : int = 1            FtBin              : float = 2

— (CTF doesn't have these)               InMrc              : Optional[str]
                                         InTiff             : Optional[str]
                                         InEer              : Optional[str]
                                         OutMrc             : str = "output.mrc"
                                         Gain               : str
                                         Dark               : Optional[str]
                                         DefectFile         : Optional[str]
                                         DefectMap          : Optional[str]
                                         PatchesX           : int = 1
                                         PatchesY           : int = 1
                                         Iter               : int = 5
                                         Tol                : float = 0.5
                                         Bft                : int = 100
                                         LogDir             : str = "."
                                         Gpu                : str = "0"
                                         FmDose             : Optional[float]
                                         ExtPhase           : float = 0
                                         SumRangeMinDose    : int = 3
                                         SumRangeMaxDose    : int = 25
                                         Group              : Optional[int]
                                         RotGain            : int = 0
                                         FlipGain           : int = 0
                                         InvGain            : Optional[int]
                                         FmIntFile          : Optional[str]
                                         EerSampling        : int = 1


Notes
-----
1. There is no ``MotionCorTaskData``. Searched the SDK,
   CoreService/models, all plugins/*/core/model_dto.py — only
   ``CryoEmMotionCorTaskData`` exists, and every layer that uses
   it imports it from the SDK (re-exported in plugin model_dto
   files).

2. Naming style differs: CTF uses lowerCamelCase / snake_case
   (``pixelSize``, ``binning_x``); MotionCor uses TitleCase that
   mirrors the MotionCor3 binary's CLI flags (``PixSize``,
   ``FtBin``, ``Gpu``). The MotionCor field names look like the
   MotionCor3 binary's own argv shape.

3. ``CtfTaskData.outputFile`` has the typo ``"ouput.mrc"`` (missing
   ``t``) — minor latent bug, separate from this comparison.

4. ``CryoEmMotionCorTaskData`` requires a ``Gain`` field (no default).
   For input data without a gain reference, callers must pass an
   empty string explicitly (``Gain=""``) — easy to miss in test
   harnesses and dispatch code.

5. The two classes overlap minimally — only the inherited base fields
   plus ``inputFile``/``outputFile`` and the optical parameters
   (``pixelSize``↔``PixSize``, ``kV``↔``accelerationVoltage``,
   ``Cs``↔``sphericalAberration``, ``AmpCont``↔``amplitudeContrast``).
   The actual algorithm-specific fields are disjoint, which is
   correct: CTF estimation and motion correction take different
   inputs.


---

<!--
  Section: 4. Database Schema Reference (CoreService)
  Originated from: CoreService/docs/README.md
  Merged into this consolidated reference 2026-05-13.
-->

# Magellon Core Service - Documentation

**Project documentation hub**

---

## 📁 Documentation Structure

```
docs/
├── README.md (this file)
├── magellon_schemal.sql (database schema)
├── architecture/
│   ├── README.md (architecture docs index)
│   ├── WORKFLOW_ARCHITECTURE.md (Temporal + NATS workflow system)
│   └── EVENT_ARCHITECTURE.md (event system & CloudEvents evaluation)
└── security/
    ├── README.md (security docs index)
    ├── SECURITY_ARCHITECTURE.md (complete security guide)
    └── DEVELOPER_GUIDE.md (developer quick reference)
```

---

## 📚 Available Documentation

### Architecture Documentation

**Location:** `architecture/`

**Start Here:** [architecture/README.md](architecture/README.md)

**Documents:**
- **[WORKFLOW_ARCHITECTURE.md](architecture/WORKFLOW_ARCHITECTURE.md)** - Distributed workflow system
- **[EVENT_ARCHITECTURE.md](architecture/EVENT_ARCHITECTURE.md)** - Event system design

**Coverage:**
- ✅ Temporal workflow orchestration
- ✅ NATS event broadcasting
- ✅ Distributed workers
- ✅ Job management
- ✅ Quick start guide
- ✅ Deployment guide

### Security Documentation

**Location:** `security/`

**Start Here:** [security/README.md](security/README.md)

**Documents:**
- **[SECURITY_ARCHITECTURE.md](security/SECURITY_ARCHITECTURE.md)** - Complete security architecture
- **[DEVELOPER_GUIDE.md](security/DEVELOPER_GUIDE.md)** - Developer quick reference

**Coverage:**
- ✅ JWT Authentication
- ✅ Casbin Authorization
- ✅ Row-Level Security (RLS)
- ✅ Database Security
- ✅ API Security
- ✅ Deployment Guide
- ✅ Troubleshooting
- ✅ Code Examples
- ✅ Testing Guide

### Database Schema

**File:** `magellon_schemal.sql`

Complete MySQL database schema including:
- Application tables (Image, Msession, Camera, etc.)
- Security tables (sys_sec_*)
- Casbin tables (casbin_rule)

---

## 🚀 Quick Links

### For Developers

- **Quick Start:** [security/DEVELOPER_GUIDE.md § Quick Start](security/DEVELOPER_GUIDE.md#quick-start-30-seconds)
- **Code Examples:** [security/DEVELOPER_GUIDE.md § Code Examples](security/DEVELOPER_GUIDE.md#code-examples)
- **Testing:** [security/DEVELOPER_GUIDE.md § Testing Guide](security/DEVELOPER_GUIDE.md#testing-guide)

### For Architects

- **Architecture Overview:** [security/SECURITY_ARCHITECTURE.md § System Architecture](security/SECURITY_ARCHITECTURE.md#system-architecture)
- **Security Layers:** [security/SECURITY_ARCHITECTURE.md § Security Layers](security/SECURITY_ARCHITECTURE.md#security-layers)
- **Audit Results:** [security/SECURITY_ARCHITECTURE.md § Security Audit Results](security/SECURITY_ARCHITECTURE.md#security-audit-results)

### For Operations

- **Deployment:** [security/SECURITY_ARCHITECTURE.md § Deployment Guide](security/SECURITY_ARCHITECTURE.md#deployment-guide)
- **Troubleshooting:** [security/SECURITY_ARCHITECTURE.md § Troubleshooting](security/SECURITY_ARCHITECTURE.md#troubleshooting)

---

## 📖 Documentation Standards

### Recently Consolidated (2025-12-09)

We consolidated all documentation into organized folders:

**Deleted from root:**
- 11 workflow/architecture markdown files → `docs/architecture/`
- 3 security markdown files → `docs/security/`
- 2 personal notes files

**Current Structure:**
- `docs/architecture/` - 2 comprehensive architecture documents
- `docs/security/` - 2 comprehensive security documents
- Root has only `CLAUDE.md` and `Readme.md`

### Document Status

| Document | Version | Last Updated | Status |
|----------|---------|--------------|--------|
| WORKFLOW_ARCHITECTURE.md | 1.0 | 2025-12-09 | ✅ Current |
| EVENT_ARCHITECTURE.md | 1.0 | 2025-12-09 | ✅ Current |
| SECURITY_ARCHITECTURE.md | 3.1 | 2025-12-09 | ✅ Current |
| DEVELOPER_GUIDE.md | 3.0 | 2025-11-18 | ✅ Current |
| Database Schema | - | 2024-10-21 | 🟡 Stable |

---

## 🛠️ Contributing to Documentation

### Guidelines

1. **Update existing docs** rather than creating new files
2. **Keep information current** - update dates and version numbers
3. **Follow existing format** - maintain consistency
4. **Test code examples** - ensure they work
5. **Add to changelog** - document significant changes

### Where to Update

- **Workflow/architecture changes** → `architecture/WORKFLOW_ARCHITECTURE.md`
- **Event system changes** → `architecture/EVENT_ARCHITECTURE.md`
- **Security changes** → `security/SECURITY_ARCHITECTURE.md`
- **Developer examples** → `security/DEVELOPER_GUIDE.md`
- **Database schema** → `magellon_schemal.sql`

---

## 📞 Support

### Security Issues

Report to security team immediately

### Documentation Issues

- Outdated information? → Update the relevant document
- Missing information? → Add to existing document
- Unclear explanation? → Improve existing section

### Code Questions

See inline documentation in:
- `dependencies/auth.py` - Authentication
- `dependencies/permissions.py` - Authorization
- `core/sqlalchemy_row_level_security.py` - RLS
- `services/casbin_service.py` - Casbin

---

## 🔗 Related Documentation

- **Project README:** `../Readme.md`
- **Project Instructions (for Claude Code):** `../CLAUDE.md`
- **Configuration Examples:** `../configs/`
- **Test Suite:** `../tests/`

---

**Last Updated:** 2025-12-09
**Maintained By:** Magellon Development Team

---

**GET STARTED:**
- New to the project? → [security/DEVELOPER_GUIDE.md](security/DEVELOPER_GUIDE.md)
- Need workflow info? → [architecture/WORKFLOW_ARCHITECTURE.md](architecture/WORKFLOW_ARCHITECTURE.md)
- Need security info? → [security/SECURITY_ARCHITECTURE.md](security/SECURITY_ARCHITECTURE.md)
- Have questions? → [security/DEVELOPER_GUIDE.md § FAQ](security/DEVELOPER_GUIDE.md#faq)


---

<!--
  Section: 5. CoreService docs/architecture stub
  Originated from: CoreService/docs/architecture/README.md
  Merged into this consolidated reference 2026-05-13.
-->

# Architecture Documentation

This folder contains architecture and design documentation for Magellon Core Service.

## Documents

| Document | Description |
|----------|-------------|
| [WORKFLOW_ARCHITECTURE.md](WORKFLOW_ARCHITECTURE.md) | Distributed workflow system (Temporal + NATS) |
| [EVENT_ARCHITECTURE.md](EVENT_ARCHITECTURE.md) | Event system design and CloudEvents evaluation |

## Quick Links

- **Start here:** [WORKFLOW_ARCHITECTURE.md](WORKFLOW_ARCHITECTURE.md)
- **Security docs:** `../security/`
- **Main README:** `../../Readme.md`

---

**Last Updated:** 2025-12-09


---

<!--
  Section: 6. Legacy Documentation index
  Originated from: Documentation/README.md
  Merged into this consolidated reference 2026-05-13.
-->

# Magellon Documentation — Index

**Status:** Index of `Documentation/`. Updated 2026-05-03.
**Audience:** Anyone opening this directory for the first time.

This file is a signpost. Open the doc that answers your question;
don't read the directory top-to-bottom. Each entry below names
**when** to read it.

---

## Read first — canonical governance

The shortest path to "what rules does this codebase live by?"

| Doc | Open when |
|---|---|
| [`ARCHITECTURE_PRINCIPLES.md`](ARCHITECTURE_PRINCIPLES.md) | You are reviewing a non-trivial PR or proposing a new abstraction. Seven principles, every PR is checked against them. |
| [`DATA_PLANE.md`](DATA_PLANE.md) | You are touching anything that reads or writes image bytes. Decision: shared POSIX filesystem; object-storage-only is an explicit non-goal. |

---

## Current state — how the system actually runs

| Doc | Open when |
|---|---|
| [`CURRENT_ARCHITECTURE.md`](CURRENT_ARCHITECTURE.md) | You need a concrete walk-through of CoreService + the two plugin architectures + the MessageBus wiring. The §8 limitations table tracks which gaps are still open. |

---

## Forward plan — what's next

| Doc | Open when |
|---|---|
| [`IMPLEMENTATION_PLAN.md`](IMPLEMENTATION_PLAN.md) | You want to know what work is in flight or recently shipped. The "Active tracks" section is the live one; earlier phases are kept above for history. |
| [`UNIFIED_PLATFORM_PLAN.md`](UNIFIED_PLATFORM_PLAN.md) | You want the longer-arc story: retire the dual plugin architecture, build toward a plugin hub on top of one contract. Forward-looking phases (U, H, S). |
| [`PLUGIN_INSTALL_PLAN.md`](PLUGIN_INSTALL_PLAN.md) | You are working on the **authoring + install pipeline**: archive creator (`plugin pack`), Installer Protocol, uv vs Docker installer impls, uninstall + upgrade, admin REST + UI. Nine sequential phases (P1–P9; P1–P8 shipped, P9 hub-fetch deferred). |
| [`PLUGIN_MANAGER_PLAN.md`](PLUGIN_MANAGER_PLAN.md) | You are working on the **runtime + operational** surface: persistence for plugin state (the silent-state-loss-on-restart bug), Conditions[] status, pause / resume verbs, per-replica health, updates badge. Seven phases (PM1–PM7). Complement to PLUGIN_INSTALL_PLAN, not overlap. |
| [`MAGELLON_HUB_SPEC.md`](MAGELLON_HUB_SPEC.md) | You are working on the **distribution registry** (`magellon-hub` service). MVP spec; phases H1–H3 in progress. |
| [`PIPELINE_ERGONOMICS_PLAN.md`](PIPELINE_ERGONOMICS_PLAN.md) | You are adding subject-tag socket validation, dispatch caching, workflow-as-JSON exports, or the registry-UX layer. Four independent tracks (PE1–PE4) adapted from ComfyUI patterns; OSS-scope only (the visual workflow builder is Pro). |
| [`PIPELINE_ERGONOMICS_FIRST_SLICE.md`](PIPELINE_ERGONOMICS_FIRST_SLICE.md) | You are implementing the cheap-cut subset of the ergonomics plan (PE1-A subject-tag dispatch gate + PE3-lite workflow.json endpoint). Concrete file paths + acceptance criteria. ≈ 1 week. |

---

## Specific references — pinpoint topics

Open these to answer a focused question, not as background reading.

| Doc | Open when |
|---|---|
| [`MESSAGE_BUS_SPEC.md`](MESSAGE_BUS_SPEC.md) | You are reading or extending the `magellon_sdk.bus` abstraction (L1/L2/L3/L4 layers, Binder SPI, routes, audit, DLQ). Canonical post-Track-A. |
| [`BROKER_PATTERNS.md`](BROKER_PATTERNS.md) | You need to understand the six RMQ patterns Magellon uses (work queues, topic fanout, DLX). Pedagogical. §8 maps the patterns onto candidate alternate transports. |
| [`MESSAGES_AND_EVENTS.md`](MESSAGES_AND_EVENTS.md) | You need the wire-shape catalogue: every message that crosses a process boundary, which transport carries it, where the schema lives. |
| [`CATEGORIES_AND_BACKENDS.md`](CATEGORIES_AND_BACKENDS.md) | You are adding a second backend under an existing category (e.g. `gctf` alongside `ctffind4`), or working with `target_backend` / `GET /plugins/capabilities`. §7a is the live category catalogue (10 categories as of 2026-05-03 including `PARTICLE_EXTRACTION` + `TWO_D_CLASSIFICATION`); §2.2a covers the subject axis (image vs particle_stack). |
| [`PLUGIN_ARCHIVE_FORMAT.md`](PLUGIN_ARCHIVE_FORMAT.md) | You are building a `.mpn` archive: manifest schema, layout, install-method declaration, what does NOT go in (deployment config). |
| [`DLQ_MIGRATION_RUNBOOK.md`](DLQ_MIGRATION_RUNBOOK.md) | You are running the DLQ-topology migration in ops. Paired with `CoreService/scripts/migrate_dlq_topology.py`. |

---

## Recently retired (for stale-link readers)

If you arrived here from a link in code, an older doc, or a chat
transcript: these files were retired from `Documentation/` on
2026-04-28. Content is in git history.

| Retired doc | Where the surviving content is |
|---|---|
| `MESSAGE_BUS_SPEC_AND_PLAN.md` | Spec content → `MESSAGE_BUS_SPEC.md`; phased plan → git log + `IMPLEMENTATION_PLAN.md` Track A history. |
| `MESSAGE_BUS_EXECUTION_PLAN.md` | All 13 PRs shipped; status table in `IMPLEMENTATION_PLAN.md` "Track A". |
| `TARGET_ARCHITECTURE_AND_PLAN.md` | Surviving principles → `ARCHITECTURE_PRINCIPLES.md`; data-plane decision → `DATA_PLANE.md`. Temporal-centric sections obsolete. |
| `COMPONENTS_AND_RELATIONSHIPS.md` | Temporal-era component glossary; current component map is in `CURRENT_ARCHITECTURE.md` §1–§4. |
| `PHASE_0_BASELINE.md`, `PHASE_0_DEAD_CODE_AUDIT.md` | Phase 0 historical artifacts; safety-net work + dead-code recommendations applied. See git log. |

---

## How to add a new doc

Before adding to this directory, ask:

1. **Is it canonical?** Then it gets a status banner, a date, and a
   companion link. Update this index.
2. **Is it a phase / migration runbook?** Same shape. Plan to retire it
   from this index once the work ships — leave the file in git for
   history.
3. **Is it a draft / proposal?** Mark `Status: Proposal, <date>`. If it
   doesn't land within a release cycle, retire it.

Avoid `*_PLAN.md` filenames for content that survives the plan; rename
to `*_SPEC.md` once the plan section is gone.

