# Magellon — Architectural Principles

**Status:** Canonical as of 2026-04-21.
**Audience:** Reviewers, architects, plugin developers.
**Companion docs:** `CURRENT_ARCHITECTURE.md`, `DATA_PLANE.md`, `IMPLEMENTATION_PLAN.md`.

This document is the short list of principles every non-trivial PR is
reviewed against. It is deliberately terse — if a principle needs a page
of nuance, it belongs in its own doc (like `DATA_PLANE.md`), not here.

The principles are derived from operational experience of the P1–P9
plugin platform refactor (2026-04-15) and the MessageBus migration
specified in `MESSAGE_BUS_SPEC.md` (Track A, shipped 2026-04-21).
Each rule below names a live call site or a past incident that
motivated it.

---

## 1. Two planes, clearly separated

**Rule.** Metadata flows on the bus (control plane). Bytes flow on the
shared filesystem (data plane). The bus carries path references to
files the data plane makes real.

**Why.** Cryo-EM payloads are GB-scale. Routing micrographs through
a broker would blow past envelope limits, defeat broker durability,
and double the I/O cost. Every mature platform in this domain
(CryoSPARC, Relion, Scipion) assumes a shared filesystem.

**How to apply.** Any PR that proposes serializing image data through
the bus (`TaskDto.data`, `TaskResultDto`, event payload) is rejected;
carry a path reference instead. Any PR that proposes reading or
writing image data from somewhere other than `MAGELLON_HOME_DIR`
needs a design doc. See `DATA_PLANE.md`.

---

## 2. One logical owner per concept

**Rule.** One row of truth per job (`services/job_service.py`). One
bus API (`magellon_sdk.bus`). One envelope (`Envelope[T]`). One
progress seam (`ProgressReporter`). No shadow implementations.

**Why.** The three-job-manager split (Dragonfly `job_manager.py`,
Temporal `temporal_job_manager.py`, live `job_service.py`) was the
single worst class of bug Magellon has shipped: races between
writers, conflicting status enums, lost progress. The platform
refactor collapsed it to one live path; the dead managers were
deleted in A.1 (`7d1f657`).

**How to apply.** Before introducing a new class, check whether an
existing one owns the concept. If two classes exist and you can't
name which is authoritative, that's the PR to open — collapse them —
not the PR you're writing.

---

## 3. Layer boundaries are lint-enforced, not guideline-enforced

**Rule.** When you declare an abstraction layer, ship a linter rule
that fails CI on a violation. Guidelines alone decay.

**Why.** The MB plan's L1 → L2 → L3 → L4 layering is worth what the
lint rule enforces and nothing more. MB6.3's rule (`pika` imports
forbidden outside `bus/binders/rmq/`) is the enforceable version.
Without it, one careless PR re-couples the call-site code to the
transport and the abstraction silently regresses.

**How to apply.** Same pattern for the two planes: once an artifact
resolver exists, forbid direct `MAGELLON_HOME_DIR` / `shutil.move`
calls outside it. Same for Socket.IO: once Phase C.1 lands, forbid
`sio.emit` outside `JobService`. Write the ruff or grep rule in the
same PR as the abstraction; don't defer.

---

## 4. Every abstraction pays its way today

**Rule.** Abstractions are justified by present-day call-site
consolidation, not by hypothetical future flexibility.

**Why.** The Temporal revert (`86fe9cc`, 2026-04-14) is the
cautionary tale: an orchestrator adopted for a workflow story that
had no concrete consumer. The MessageBus spec, by contrast, is
justified on the 16 present-day call sites it collapses (spec §1.2)
— not on the hypothetical NATS / SQS binder (MB7, explicitly
deferred).

**How to apply.** A PR proposing a Protocol, SPI, or plugin point
must name the call sites that collapse onto it today. "So we can
swap X later" without a named customer is not sufficient
justification.

---

## 5. Contracts are versioned and tested

**Rule.** Every wire contract (envelope, plugin I/O, event schema)
carries an explicit schema version and has a golden test pinning its
bytes-on-the-wire shape.

**Why.** Silent schema drift is the bug class that motivated the
Phase 0 characterization tests. CloudEvents `specversion`,
`PluginInfo.schema_version`, and `CategoryContract` are the three
layers of versioning the platform already enforces. Golden tests
under `CoreService/tests/characterization/` keep them honest.

**How to apply.** A PR that changes a Pydantic model on the wire, a
bus route subject, or a plugin's `schema_version` must update the
golden test in the same PR. Reviewer rejects if the golden file is
untouched.

---

## 6. Additive first, subtractive second

**Rule.** The add-new-path PR and the delete-old-path PR are always
separate. Every phase ships reversible-by-`git revert` until the
legacy path is empirically safe to remove.

**Why.** The MessageBus plan's MB3 → MB6 ordering is the template:
producers migrate first (smallest blast radius), consumers next,
operator primitives last, DLQ topology migration only after the rest
has soaked in production for a week. Every step is `git revert`-safe
except the DLQ migration, and that one has a runbook.

**How to apply.** A PR titled "refactor X, remove Y" is split into
two. The first lands and soaks; the second follows. Reviewer rejects
dual-purpose PRs. Exception: pure renames with no semantic change
can land atomically.

---

## 7. Operator surface is first-class

**Rule.** Every subsystem ships with documented answers to: how do I
observe it, how do I drain it, how do I recover it?

**Why.** P9 (queue purge + container kill) and the DLQ migration
runbook (`DLQ_MIGRATION_RUNBOOK.md`) set the bar.
Subsystems without this surface are the ones that page operators at
3 AM with no tools.

**How to apply.** A PR introducing a new subsystem (a new consumer,
a new event stream, a new integration) must include: (a) a
healthcheck or status endpoint, (b) a documented way to drain or
purge its queue / stream, (c) a runbook entry or log keywords that
point an operator at the problem.

---

## Meta: when to update this document

Update this file when:

- A new principle survives three PR reviews (you found yourself
  writing the same comment three times — that's a principle).
- A principle turns out wrong in practice. Delete it, don't soften
  it — a principle that's sometimes-true is just noise.
- A principle's motivating evidence is superseded (e.g., the MB
  work lands and the "two planes" principle inherits new examples).

Do *not* add principles here speculatively. Every rule is justified
by a concrete incident, commit, or named call site.
