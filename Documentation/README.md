# Magellon — Documentation

The documentation has been consolidated into four reference docs under
`magellon/` (2026-05-13). The previous 17 files in this directory and 8
files under `CoreService/docs/` were merged into:

| Doc | What's inside |
|---|---|
| [`magellon/ARCHITECTURE.md`](magellon/ARCHITECTURE.md) | Principles, current architecture, data plane, message bus spec, broker patterns, message + event shapes, categories + backends, cryo-EM workflow walk-through, roadmap (implementation plan, unified platform, pipeline ergonomics). |
| [`magellon/PLUGINS.md`](magellon/PLUGINS.md) | Plugin runtime architecture, `.mpn` archive format, install pipeline, plugin manager, hub specification, developer guide. |
| [`magellon/SECURITY.md`](magellon/SECURITY.md) | Casbin RBAC + RLS architecture, developer guide for authz, security quick reference. |
| [`magellon/OPERATIONS.md`](magellon/OPERATIONS.md) | DLQ migration runbook, common commands, task-data shape comparison, DB schema reference, legacy doc index. |

The originals are gone but recoverable: `git show <old-commit>:Documentation/<filename>.md`.

## Why consolidated

The doc set had grown to 25 files / ~11K lines, with overlapping coverage,
broken cross-references, and no clear top-level entry point. Merging into
four thematic docs preserves every word but makes the corpus searchable
end-to-end and lets each commit message reference one stable file.

## Old filename → new section map

If you arrived here from a link in code, an older doc, or a chat
transcript, the mapping is:

- `ARCHITECTURE_PRINCIPLES.md` → `ARCHITECTURE.md` §1
- `CURRENT_ARCHITECTURE.md` → `ARCHITECTURE.md` §2
- `DATA_PLANE.md` → `ARCHITECTURE.md` §3
- `MESSAGE_BUS_SPEC.md` → `ARCHITECTURE.md` §4
- `BROKER_PATTERNS.md` → `ARCHITECTURE.md` §5
- `MESSAGES_AND_EVENTS.md` → `ARCHITECTURE.md` §6
- `CATEGORIES_AND_BACKENDS.md` → `ARCHITECTURE.md` §7
- `cryo-em-pipeline.md` (CoreService) → `ARCHITECTURE.md` §8
- `IMPLEMENTATION_PLAN.md` → `ARCHITECTURE.md` §9
- `UNIFIED_PLATFORM_PLAN.md` → `ARCHITECTURE.md` §10
- `PIPELINE_ERGONOMICS_PLAN.md` → `ARCHITECTURE.md` §11
- `PIPELINE_ERGONOMICS_FIRST_SLICE.md` → `ARCHITECTURE.md` §12
- `PLUGIN_ARCHITECTURE.md` (CoreService) → `PLUGINS.md` §1
- `PLUGIN_ARCHIVE_FORMAT.md` → `PLUGINS.md` §2
- `PLUGIN_INSTALL_PLAN.md` → `PLUGINS.md` §3
- `PLUGIN_MANAGER_PLAN.md` → `PLUGINS.md` §4
- `MAGELLON_HUB_SPEC.md` → `PLUGINS.md` §5
- `plugin-developer-guide.md` (CoreService) → `PLUGINS.md` §6
- `SECURITY_ARCHITECTURE.md` (CoreService) → `SECURITY.md` §1
- `DEVELOPER_GUIDE.md` (CoreService security) → `SECURITY.md` §2
- `DLQ_MIGRATION_RUNBOOK.md` → `OPERATIONS.md` §1
- `commands.txt` → `OPERATIONS.md` §2
- `task-data-comparison.txt` → `OPERATIONS.md` §3
- `magellon_schemal.sql` (CoreService DB schema dump) — preserved in git history only.

## Leftover non-doc artifacts in this directory

- `MRC_EXTENDED_HEADER_EXAMPLE.json` — sample MRC extended-header payload referenced from the code, not consolidated.
- `tutorial/` — Python tutorial scripts + sample `.mrc` files; not Markdown docs.

These stayed in place because they're code-level reference data, not the
narrative documentation the consolidation absorbed.
