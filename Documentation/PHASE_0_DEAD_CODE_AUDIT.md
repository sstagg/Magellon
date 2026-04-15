# Phase 0 Dead Code Audit Report
**Date:** 2026-04-14  
**Scope:** CoreService codebase (excluding tests/, alembic/, venv/, __pycache__)  
**Purpose:** Identify code that can be safely deleted before migration, ensuring deletions stay reversible and focused

This audit examined 150+ Python modules across controllers, services, workflows, and utilities to identify dead code, unreferenced imports, unused controllers, and duplicate/superseded files.

---

## Findings by Category

### 1. Unused Controllers/Routers

| File | Evidence | Recommendation |
|------|----------|---|
| `controllers/workflow_job_controller.py` | 0 imports found via `grep -r "workflow_job_controller"`; not included in `main.py`'s `app.include_router` calls | **SAFE TO DELETE** — Scaffolded endpoint for Temporal workflow integration; not wired into live application |

### 2. Unreferenced Service Modules

| File | Evidence | Recommendation |
|------|----------|---|
| `services/criteria_parser_service.py` (ROOT) | 0 direct imports; shadowed by `services/security/criteria_parser_service.py` which is actively used | **SAFE TO DELETE** — Duplicate file; security folder version is the canonical implementation |
| `services/ctf_service.py` | 0 imports found; class `CTFService` defined but never called | **NEEDS HUMAN REVIEW** — Unknown if orphaned by design or legitimately stale. Check commit history. |
| `services/diagrams_service.py` | 0 imports found across codebase | **NEEDS HUMAN REVIEW** — Unclear if legitimately dead or used by external client. Verify before deletion. |
| `services/epu_frame_transfer_service.py` | Only reference: commented line in `image_processing_controller.py` line ~245 | **SAFE TO DELETE** — Evidently abandoned workflow step (comment-only); no active usage |
| `services/event_logging_service.py` | 0 imports found | **NEEDS HUMAN REVIEW** — May be intended for future logging pipeline; check requirements. |
| `services/image_file_service.py` | 0 imports found | **SAFE TO DELETE** — No usage detected; likely superseded by `file_service.py` or `image_file_service.py` elsewhere |

### 3. Broken/Malformed Imports

| File | Issue | Recommendation |
|------|-------|---|
| `services/job_event_publisher.py` line 12 | `from magellon_event_service import MagellonEventService` — relative import, should be `from services.magellon_event_service` | **FIX REQUIRED** — Correct import path or disable module until fixed |
| `services/magellon_job_manager.py` line (similar) | Same broken import | **FIX REQUIRED** — Apply same fix |

### 4. Unused Root-Level Scripts

| File | Type | Evidence | Recommendation |
|------|------|----------|---|
| `test_user_auth_debug.py` | Debug utility | 0 references in codebase; manual CLI tool | **SAFE TO DELETE** — Useful for troubleshooting but not part of runtime. Archive if needed. |
| `worker_all.py` | RabbitMQ worker | 0 references; likely superseded by activity workers | **NEEDS HUMAN REVIEW** — Confirm if replaced by Temporal activities before deletion |
| `worker_ctf.py` | RabbitMQ worker | 0 references | **NEEDS HUMAN REVIEW** — Same rationale as above |
| `worker_motioncor.py` | RabbitMQ worker | 0 references | **NEEDS HUMAN REVIEW** — Same rationale as above |
| `worker_thumbnail.py` | RabbitMQ worker | 0 references | **NEEDS HUMAN REVIEW** — Same rationale as above |
| `get-pip.py` | Bootstrap script | Standard pip installer (base85 encoded zip) | **KEEP** — Safe bootstrap utility, not dead code |

### 5. Scripts Directory (Utility Scripts)

| File | Purpose | Status | Recommendation |
|------|---------|--------|---|
| `scripts/reset_demo_data.py` | One-off data reset utility | Not auto-imported; called manually | **KEEP** — Utility for dev/demo; safe to maintain |
| `scripts/setup_security_permissions.py` | Initial RBAC setup | Not auto-imported; called manually | **KEEP** — Essential for permission initialization |
| `scripts/sync_policies_to_casbin.py` | Policy sync helper | Referenced in error message in `test_user_auth_debug.py` | **KEEP** — Used for Casbin policy synchronization |

### 6. Example/Reference Files

| File | Status | Recommendation |
|------|--------|---|
| `controllers/security/examples/property_controller_rbac_example.py` | Not included in `main.py`; purely educational | **KEEP** — Useful documentation for developers; low cost to maintain |

### 7. Workflow/Activity Modules

| File | Status | Recommendation |
|------|--------|---|
| `workflows/image_processing_workflow.py` | Imported by `workflow_job_controller.py` | **KEEP** — Part of Temporal scaffolding; linked to scaffolded controller |
| `activities/image_processing_activities.py` | Likely used by workflow module | **KEEP** — Part of Temporal scaffolding |

---

## Summary

**Safe to Delete (3 items):**
- `services/criteria_parser_service.py` (root-level duplicate)
- `services/epu_frame_transfer_service.py` (abandoned, comment-only reference)
- `controllers/workflow_job_controller.py` (scaffolded, not wired)

**Needs Human Review (6 items):**
- `services/ctf_service.py`
- `services/diagrams_service.py`
- `services/event_logging_service.py`
- `worker_all.py`, `worker_ctf.py`, `worker_motioncor.py`, `worker_thumbnail.py` (4 RabbitMQ workers—verify Temporal migration completeness)

**Fix Required (2 items):**
- `services/job_event_publisher.py` — Correct import path
- `services/magellon_job_manager.py` — Correct import path

**Keep (retain for now):**
- All other files (in use, examples, utilities, or bootstrap)

---

## Recommended Next Steps for Phase 0

1. **Confirm Temporal migration:** Verify that the four RabbitMQ workers are fully replaced before deletion.
2. **Fix broken imports:** Correct the import paths in `job_event_publisher.py` and `magellon_job_manager.py`.
3. **Review context:** For `ctf_service`, `diagrams_service`, and `event_logging_service`, check commit history and design docs to confirm they are intentionally orphaned.
4. **Delete in small, reversible commits:** Once confirmed, delete the "Safe" items one at a time with minimal PR diffs per Phase 0 goal.

No DAGs or `.old`/`.bak` suffixed files were found. All FastAPI routers mentioned in the background are correctly wired into `main.py`.
