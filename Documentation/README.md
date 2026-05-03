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
