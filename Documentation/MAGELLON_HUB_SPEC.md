# magellon-hub — Technical Specification

**Status:** Draft 1, 2026-04-17. Implementation spec for a new service.
**Audience:** Developer team building `magellon-hub`. Companion to `UNIFIED_PLATFORM_PLAN.md` (phase H3c) and `magellon-sdk/CONTRACT.md` (archive format).
**Scope:** MVP (phase 1) plus a clearly-scoped phase 2 / 3 backlog. MVP is what the team should build first.

---

## 1. Purpose

`magellon-hub` is a central service that hosts Magellon plugin archives (`.magplugin`) and exposes a read/write HTTP API so plugin authors can publish their work and CoreService deployments can discover and install it.

It plays the same role PyPI plays for Python or npmjs.com plays for Node — a registry of named, versioned, reviewable artifacts with a public discovery surface. It is **not** an alternative to per-deployment catalogs: the CoreService-local catalog (see `CoreService/core/plugin_catalog.py`) remains for private and air-gapped deployments. The hub is where the public ecosystem lives.

**What problem this solves that the per-deployment catalog doesn't:**

- Plugin authors can publish once, every CoreService deployment can discover.
- Central review / verification of community plugins (two-tier trust).
- Stable identity: one `plugin_id` claimed once, not N copies across orgs.
- Reproducibility: every published version is immutable and addressable by `{plugin_id, version}` → exact SHA256.

**What this spec deliberately does NOT cover:**

- Federation across multiple hub instances. Single-hub MVP first; federation is phase 3.
- Running the plugins themselves. That stays with CoreService.
- Any UI beyond the backend API. A small admin UI is nice-to-have; the primary client is CoreService's existing Browse modal, which will gain a "remote" mode pointing at the hub.

---

## 2. Architecture

```
┌─────────────────┐        ┌───────────────────────────────────────┐
│ Plugin author   │───────>│ magellon-hub (FastAPI)                │
│   (CLI / CI)    │ HTTPS  │                                       │
└─────────────────┘        │  ┌─────────────┐  ┌──────────────┐    │
                           │  │  REST API   │  │ Background   │    │
┌─────────────────┐        │  │  (/v1/...)  │  │ jobs         │    │
│ CoreService     │───────>│  └──────┬──────┘  │ (index gen,  │    │
│ (remote catalog │ HTTPS  │         │          │  cleanup)    │    │
│  fetcher)       │        │         │          └──────┬───────┘    │
└─────────────────┘        │  ┌──────┴──────┐          │            │
                           │  │  Business   │<─────────┘            │
┌─────────────────┐        │  │  layer      │                       │
│ Admin reviewer  │───────>│  │  (services) │                       │
│   (web + API)   │ HTTPS  │  └──────┬──────┘                       │
└─────────────────┘        │         │                              │
                           │  ┌──────┴──────┐  ┌──────────────┐     │
                           │  │ PostgreSQL  │  │ Object store │     │
                           │  │ (metadata,  │  │ (archives)   │     │
                           │  │  users,     │  │ FS / S3 /    │     │
                           │  │  reviews)   │  │ R2 / GCS     │     │
                           │  └─────────────┘  └──────────────┘     │
                           └───────────────────────────────────────┘
```

### 2.1 Components

- **FastAPI app** — HTTP surface. Async where it pays (archive upload / download). Sync where it doesn't (simple CRUD).
- **PostgreSQL** — all metadata (users, plugins, versions, reviews, audit log). Same engine as CoreService, shared ops knowledge.
- **Object store** — the `.magplugin` archive bytes. Abstracted behind a `StorageBackend` interface; default filesystem, S3/R2/GCS pluggable. Content-addressed by SHA256 for dedup.
- **Background jobs** — rebuild the public `/v1/index.json` on publish/yank, garbage-collect orphan archives, cron-nudge stale pending reviews. Run under APScheduler or `arq` — something lightweight, same process or a sidecar. Pick one at implementation time.
- **Admin UI** — optional thin page (HTMX / Starlette templates / or a handful of FastAPI routes rendering HTML). MVP can be API-only; reviewers hit endpoints via a CLI or Postman.

### 2.2 Tech stack

| Concern | Choice | Rationale |
|---|---|---|
| Language | Python 3.11+ | Matches CoreService and the SDK; share Pydantic types. |
| Framework | FastAPI | Matches CoreService; typed; OpenAPI for free. |
| ORM | SQLAlchemy 2.x (async or sync — pick one and stay consistent) | Matches CoreService. |
| Migrations | Alembic | Matches CoreService. |
| DB | PostgreSQL 15+ | JSONB for flexible fields; full-text search if we need it in phase 2. |
| Object store (default) | Filesystem under `/var/lib/magellon-hub/archives/` | Dev + small deployments. Abstracted so prod can swap for S3/R2. |
| Object store (prod) | S3 / Cloudflare R2 / GCS via `aiobotocore` | Industry standard; CDN-friendly. |
| Auth — phase 1 | API tokens (prefix-tagged, stored hashed) | Works for CLI + CI without OAuth setup. |
| Auth — phase 2 | GitHub OAuth 2.0 | Matches the plugin-author population. |
| Background jobs | APScheduler (same process) or `arq` (Redis-backed) | MVP: APScheduler is zero-infra. |
| HTTP client (CoreService side) | `httpx` | Already in CoreService. |
| Observability | Python logging → stdout, Prometheus `/metrics`, OpenTelemetry stub | Standard. |

### 2.3 Repository layout (proposed)

```
magellon-hub/
├── pyproject.toml
├── alembic.ini
├── alembic/versions/
├── src/
│   └── magellon_hub/
│       ├── __init__.py
│       ├── main.py              # FastAPI app factory
│       ├── config.py            # Settings via pydantic-settings
│       ├── db/
│       │   ├── models.py        # SQLAlchemy ORM
│       │   ├── session.py
│       │   └── repositories/    # one module per aggregate
│       ├── api/
│       │   ├── v1/
│       │   │   ├── plugins.py
│       │   │   ├── versions.py
│       │   │   ├── auth.py
│       │   │   ├── admin.py
│       │   │   └── me.py
│       │   └── deps.py          # shared dependencies (auth, db, storage)
│       ├── services/
│       │   ├── plugin_service.py
│       │   ├── version_service.py
│       │   ├── review_service.py
│       │   ├── archive_validator.py
│       │   └── index_builder.py # builds /v1/index.json
│       ├── storage/
│       │   ├── base.py          # StorageBackend protocol
│       │   ├── filesystem.py
│       │   └── s3.py
│       ├── auth/
│       │   ├── tokens.py
│       │   └── github_oauth.py  # phase 2
│       ├── workers/             # background jobs
│       │   └── index_rebuild.py
│       └── schemas/             # pydantic DTOs (request/response)
├── tests/
└── docker/
    ├── Dockerfile
    └── docker-compose.yml
```

Separate repo from `CoreService` and `magellon-sdk`. Shares `magellon-sdk` as a pip dependency for the `PluginArchiveManifest` type (the wire shape of `plugin.yaml` is part of the SDK's public contract).

---

## 3. Data model

All tables use `BIGSERIAL` primary keys unless noted. Timestamps are `TIMESTAMPTZ`. Column constraints and indices are called out explicitly — migrations should match.

### 3.1 `users`

Plugin authors and admins.

| Column | Type | Constraint | Purpose |
|---|---|---|---|
| `id` | BIGSERIAL | PK | |
| `username` | VARCHAR(64) | NOT NULL, UNIQUE | Display handle; GitHub login when we add OAuth. |
| `email` | VARCHAR(320) | NOT NULL, UNIQUE | For review notifications. |
| `full_name` | VARCHAR(200) | NULL | |
| `github_id` | BIGINT | NULL, UNIQUE | Populated when GitHub OAuth lands; NULL for tokens-only users. |
| `role` | VARCHAR(16) | NOT NULL, default `'author'`, CHECK IN (`'author'`, `'admin'`) | Admins can approve/reject; authors can only publish under their own name. |
| `is_disabled` | BOOLEAN | NOT NULL, default FALSE | Soft-disable for abuse. Disabled users cannot authenticate. |
| `created_at` | TIMESTAMPTZ | NOT NULL, default `now()` | |
| `last_seen_at` | TIMESTAMPTZ | NULL | Updated on any authenticated request. |

**Indices:** `(github_id)` unique partial where not null; `(role) WHERE role='admin'` for the small admin queue.

### 3.2 `api_tokens`

API tokens for CLI / CI. Tokens are generated as `mhub_<random32>`, stored hashed (bcrypt or SHA-256 of the raw token). The raw token is shown to the user **once** on creation and never again.

| Column | Type | Constraint | Purpose |
|---|---|---|---|
| `id` | BIGSERIAL | PK | |
| `user_id` | BIGINT | NOT NULL, FK→`users.id` ON DELETE CASCADE | Owner. |
| `token_prefix` | VARCHAR(16) | NOT NULL | Shown in UI so the user can identify it ("mhub_a1b2…"); not sensitive. |
| `token_hash` | VARCHAR(128) | NOT NULL | sha256 of the raw token. |
| `name` | VARCHAR(64) | NOT NULL | User-chosen label ("CI robot", "laptop"). |
| `scopes` | JSONB | NOT NULL, default `'["publish"]'::jsonb` | Array of scope strings. `'publish'`, `'admin'`. |
| `created_at` | TIMESTAMPTZ | NOT NULL, default `now()` | |
| `last_used_at` | TIMESTAMPTZ | NULL | Updated on token authentication. |
| `expires_at` | TIMESTAMPTZ | NULL | NULL = never. |
| `revoked_at` | TIMESTAMPTZ | NULL | Soft-revoke; keep the row for audit. |

**Indices:** `(token_hash)` unique; `(user_id)`.

### 3.3 `plugins`

One row per claimed plugin slug. Identity and description live here; versions live in the next table.

| Column | Type | Constraint | Purpose |
|---|---|---|---|
| `id` | BIGSERIAL | PK | |
| `slug` | VARCHAR(64) | NOT NULL, UNIQUE | URL slug, matches `plugin_id` in the manifest. Lowercase slug (same regex as SDK). Immutable once claimed. |
| `display_name` | VARCHAR(200) | NOT NULL | Human name. Editable. |
| `description_short` | VARCHAR(500) | NOT NULL, default `''` | One-liner for list views. |
| `category` | VARCHAR(32) | NOT NULL | `fft`, `ctf`, `motioncor`, `pp`, ... Matches manifest category. Index-friendly. |
| `owner_user_id` | BIGINT | NOT NULL, FK→`users.id` | Who claimed this slug. Transferrable by admin. |
| `is_verified` | BOOLEAN | NOT NULL, default FALSE | Two-tier trust. Admin-set flag. |
| `is_disabled` | BOOLEAN | NOT NULL, default FALSE | Admin takedown (legal, malware, etc.). Disabled = hidden from list and refusing new versions, but existing archives stay downloadable-by-id for reproducibility unless fully purged. |
| `homepage_url` | VARCHAR(500) | NULL | |
| `repository_url` | VARCHAR(500) | NULL | |
| `license` | VARCHAR(64) | NULL | SPDX identifier. Denormalized from the latest published version for list views. |
| `created_at` | TIMESTAMPTZ | NOT NULL, default `now()` | |
| `updated_at` | TIMESTAMPTZ | NOT NULL, default `now()` | Bumped on metadata or new-version publish. |

**Indices:** `(slug)` unique; `(category)`; `(owner_user_id)`; `(is_verified) WHERE is_verified`; `(updated_at DESC)` for "recently updated" list.

### 3.4 `plugin_versions`

One row per submitted version. Versions are immutable after publish; editing republishes as a new version.

| Column | Type | Constraint | Purpose |
|---|---|---|---|
| `id` | BIGSERIAL | PK | |
| `plugin_id` | BIGINT | NOT NULL, FK→`plugins.id` ON DELETE CASCADE | |
| `version` | VARCHAR(64) | NOT NULL | SemVer recommended. `(plugin_id, version)` unique. |
| `sdk_compat` | VARCHAR(64) | NOT NULL | Copy of the manifest's `sdk_compat`; indexed so we can answer "which plugins work with SDK X.Y.Z?" without scanning manifests. |
| `manifest_json` | JSONB | NOT NULL | Full parsed `plugin.yaml`. Denormalized for fast reads; authoritative source is the archive. |
| `archive_id` | BIGINT | NOT NULL, FK→`plugin_archives.id` | The stored bytes. |
| `submitted_by_user_id` | BIGINT | NOT NULL, FK→`users.id` | Token owner who pushed this version. |
| `review_status` | VARCHAR(16) | NOT NULL, default `'pending'`, CHECK IN (`'pending'`, `'published'`, `'rejected'`, `'yanked'`) | State machine; see §7. |
| `review_notes` | TEXT | NULL | Admin-authored comment visible to the author. |
| `reviewed_by_user_id` | BIGINT | NULL, FK→`users.id` | Admin who transitioned to `published` / `rejected`. |
| `reviewed_at` | TIMESTAMPTZ | NULL | |
| `submitted_at` | TIMESTAMPTZ | NOT NULL, default `now()` | |
| `published_at` | TIMESTAMPTZ | NULL | First transition to `published`. Exposed to clients as "release date". |
| `yank_reason` | VARCHAR(200) | NULL | Short explanation shown next to yanked versions. |

**Indices:** `(plugin_id, version)` unique; `(plugin_id, review_status, published_at DESC)`; `(review_status) WHERE review_status='pending'` for the admin queue; `(sdk_compat)` for the "compatible with SDK X" query.

### 3.5 `plugin_archives`

Content-addressed storage metadata. Deduplicates uploads with the same bytes.

| Column | Type | Constraint | Purpose |
|---|---|---|---|
| `id` | BIGSERIAL | PK | |
| `sha256` | CHAR(64) | NOT NULL, UNIQUE | Hex digest of the archive bytes. |
| `size_bytes` | BIGINT | NOT NULL, CHECK ≥ 0 | |
| `storage_key` | VARCHAR(500) | NOT NULL | Opaque handle the storage backend uses. FS: `ar/ab/<sha256>.magplugin`. S3: `s3://<bucket>/archives/ar/ab/<sha256>.magplugin`. |
| `content_type` | VARCHAR(64) | NOT NULL, default `'application/zip'` | |
| `uploaded_at` | TIMESTAMPTZ | NOT NULL, default `now()` | |

**Indices:** `(sha256)` unique.

### 3.6 `plugin_tags` (optional, phase 2 nice-to-have)

Free-form tags for discovery. One tag per row, N:M with plugins.

| Column | Type | Constraint | Purpose |
|---|---|---|---|
| `plugin_id` | BIGINT | NOT NULL, FK→`plugins.id` ON DELETE CASCADE | |
| `tag` | VARCHAR(32) | NOT NULL | Lowercase, slug-like. |
| PRIMARY KEY | `(plugin_id, tag)` | | |

### 3.7 `plugin_downloads`

Aggregate popularity counter. Per-event rows would balloon; we increment columns atomically.

| Column | Type | Constraint | Purpose |
|---|---|---|---|
| `plugin_version_id` | BIGINT | PK, FK→`plugin_versions.id` ON DELETE CASCADE | |
| `downloads_total` | BIGINT | NOT NULL, default 0 | Lifetime. |
| `downloads_30d` | BIGINT | NOT NULL, default 0 | Rolling window, rebuilt by a nightly job. |
| `last_downloaded_at` | TIMESTAMPTZ | NULL | |

A background job maintains `downloads_30d` by re-reading the server access log or a small `download_events` table (if we add one later for ML-style popularity scoring). MVP: the `downloads_total` counter is incremented synchronously on archive fetch. `downloads_30d` is a phase 2 add.

### 3.8 `audit_log`

Who did what, when. Mandatory for the review workflow (accountability) and cheap to add up front.

| Column | Type | Constraint | Purpose |
|---|---|---|---|
| `id` | BIGSERIAL | PK | |
| `actor_user_id` | BIGINT | NULL, FK→`users.id` ON DELETE SET NULL | NULL for system actions. |
| `action` | VARCHAR(64) | NOT NULL | `plugin.claim`, `version.upload`, `version.approve`, `version.reject`, `version.yank`, `plugin.verify`, `plugin.disable`, `token.create`, `token.revoke`. |
| `target_type` | VARCHAR(32) | NOT NULL | `plugin`, `version`, `user`, `token`. |
| `target_id` | BIGINT | NOT NULL | |
| `data` | JSONB | NOT NULL, default `'{}'::jsonb` | Action-specific payload (e.g. review notes, old/new value). |
| `ts` | TIMESTAMPTZ | NOT NULL, default `now()` | |

**Indices:** `(actor_user_id, ts DESC)`; `(target_type, target_id, ts DESC)`; partial on action for admin filters.

---

## 4. API surface

Base path: `/v1`. Responses are JSON unless stated. Archive downloads are `application/zip`.

All endpoints return `application/json` with a consistent error body on non-2xx:

```json
{ "detail": "<short human-readable message>" }
```

HTTP status codes follow the usual contract: `200` success, `201` created, `204` no content, `400` client input shape wrong, `401` unauthenticated, `403` authenticated but not allowed, `404` target not found, `409` conflict (duplicate slug/version, state-machine mismatch), `413` payload too large, `422` validation error (pydantic detail shape), `429` rate limited, `503` dependency down.

### 4.1 Endpoint catalog (summary)

| # | Method | Path | Auth | Purpose |
|---|---|---|---|---|
| **Public (read-only)** | | | | |
| 1 | GET | `/v1/plugins` | none | Search & list plugins. |
| 2 | GET | `/v1/plugins/{slug}` | none | Plugin detail (metadata + latest published version). |
| 3 | GET | `/v1/plugins/{slug}/versions` | none | Version history for one plugin. |
| 4 | GET | `/v1/plugins/{slug}/versions/{version}` | none | One version's metadata. |
| 5 | GET | `/v1/plugins/{slug}/versions/{version}/archive` | none | Download the `.magplugin` archive. |
| 6 | GET | `/v1/categories` | none | Category list with plugin counts. |
| 7 | GET | `/v1/index.json` | none | Full index (CoreService polls this). |
| 8 | GET | `/v1/healthz` | none | Liveness. |
| **Author (token auth, scope `publish`)** | | | | |
| 9 | GET | `/v1/me` | bearer | Current user profile. |
| 10 | POST | `/v1/plugins` | bearer | Claim a new plugin slug. |
| 11 | PATCH | `/v1/plugins/{slug}` | bearer (owner) | Update mutable metadata. |
| 12 | POST | `/v1/plugins/{slug}/versions` | bearer (owner) | Upload a new version (multipart). |
| 13 | POST | `/v1/plugins/{slug}/versions/{version}/yank` | bearer (owner) | Yank a published version. |
| 14 | GET | `/v1/me/plugins` | bearer | My plugins. |
| 15 | GET | `/v1/me/tokens` | bearer | My tokens. |
| 16 | POST | `/v1/me/tokens` | bearer | Mint a new token. |
| 17 | DELETE | `/v1/me/tokens/{id}` | bearer | Revoke a token. |
| **Admin (token auth, scope `admin`)** | | | | |
| 18 | GET | `/v1/admin/reviews` | bearer (admin) | Pending-review queue. |
| 19 | POST | `/v1/admin/plugins/{slug}/versions/{version}/approve` | bearer (admin) | Publish a pending version. |
| 20 | POST | `/v1/admin/plugins/{slug}/versions/{version}/reject` | bearer (admin) | Reject with notes. |
| 21 | POST | `/v1/admin/plugins/{slug}/verify` | bearer (admin) | Flip `is_verified`. |
| 22 | POST | `/v1/admin/plugins/{slug}/disable` | bearer (admin) | Takedown. |
| 23 | GET | `/v1/admin/audit` | bearer (admin) | Audit-log query (paginated). |
| **Auth bootstrap (phase 2)** | | | | |
| 24 | GET | `/v1/auth/github` | none | Redirect to GitHub OAuth. |
| 25 | GET | `/v1/auth/github/callback` | none | OAuth callback; mints a token. |

### 4.2 Public endpoints in detail

**1. `GET /v1/plugins`** — Search & list.

Query params (all optional):
- `search: str` — substring match on display_name, description_short, slug. Case-insensitive.
- `category: str` — exact match.
- `verified: bool` — if true, return only verified plugins.
- `sdk_compat: str` — return only plugins with at least one *published* version whose `sdk_compat` includes this SDK version.
- `sort: str` — one of `updated`, `name`, `downloads`. Default `updated`.
- `page: int` (≥1, default 1), `page_size: int` (1–100, default 20).

Response `200`:

```json
{
  "items": [
    {
      "slug": "fft-classical",
      "display_name": "Classical FFT",
      "description_short": "FFT magnitude spectrum via scipy.fft.",
      "category": "fft",
      "is_verified": true,
      "owner": { "id": 42, "username": "magellon-org" },
      "latest_version": {
        "version": "1.3.0",
        "sdk_compat": ">=1.2,<2.0",
        "published_at": "2026-04-12T18:22:14Z"
      },
      "downloads_total": 1834,
      "updated_at": "2026-04-12T18:22:14Z"
    }
  ],
  "page": 1,
  "page_size": 20,
  "total": 37
}
```

**2. `GET /v1/plugins/{slug}`** — Detail.

Response `200`:

```json
{
  "slug": "fft-classical",
  "display_name": "Classical FFT",
  "description_short": "FFT magnitude spectrum via scipy.fft.",
  "category": "fft",
  "is_verified": true,
  "is_disabled": false,
  "owner": { "id": 42, "username": "magellon-org" },
  "homepage_url": "https://magellon.org/plugins/fft-classical",
  "repository_url": "https://github.com/magellon-org/fft-plugin",
  "license": "MIT",
  "created_at": "2026-03-01T12:00:00Z",
  "updated_at": "2026-04-12T18:22:14Z",
  "latest_version": { /* full version object */ },
  "downloads_total": 1834
}
```

Errors: `404` if slug does not exist or is disabled (do not leak existence of disabled plugins to unauthenticated users).

**3. `GET /v1/plugins/{slug}/versions`** — Version history.

Query params: `include_pending: bool` (default false; only the owner/admin can see pending). Non-owner requests silently filter to `review_status='published'` + `'yanked'`.

Response `200`:

```json
{
  "items": [
    {
      "version": "1.3.0",
      "review_status": "published",
      "sdk_compat": ">=1.2,<2.0",
      "submitted_at": "2026-04-10T09:00:00Z",
      "published_at": "2026-04-12T18:22:14Z",
      "reviewed_by": { "id": 7, "username": "admin-alice" },
      "downloads_total": 1834,
      "sha256": "fa23…",
      "size_bytes": 8247
    },
    { "version": "1.2.1", "review_status": "yanked", "yank_reason": "critical bug in MTF computation", "...": "..." }
  ]
}
```

**4. `GET /v1/plugins/{slug}/versions/{version}`** — Single version.

Returns the row + the full parsed `manifest_json` so a consumer can decide whether to download without pulling the zip:

```json
{
  "version": "1.3.0",
  "review_status": "published",
  "submitted_at": "2026-04-10T09:00:00Z",
  "published_at": "2026-04-12T18:22:14Z",
  "sdk_compat": ">=1.2,<2.0",
  "sha256": "fa23…",
  "size_bytes": 8247,
  "archive_url": "/v1/plugins/fft-classical/versions/1.3.0/archive",
  "manifest": { /* the full plugin.yaml as JSON */ }
}
```

**5. `GET /v1/plugins/{slug}/versions/{version}/archive`** — Download.

Response `200` with `Content-Type: application/zip`, `Content-Length`, `ETag: "<sha256>"`, `Cache-Control: public, max-age=31536000, immutable` (archives are immutable by sha256). Range requests supported for large archives.

Side effect: increments `plugin_downloads.downloads_total` for this version.

**6. `GET /v1/categories`** — Category counts.

```json
{
  "categories": [
    { "code": "fft", "count": 3 },
    { "code": "ctf", "count": 5 },
    { "code": "motioncor", "count": 2 },
    { "code": "pp", "count": 4 }
  ]
}
```

**7. `GET /v1/index.json`** — Full public index.

Flat JSON list of every `published` or `yanked` version across every plugin. Optimized for CoreService's remote-catalog poller: one fetch instead of N listing calls. Served with a short-lived cache header (60 s) and a daily rebuild by the background job; between builds it's regenerated on every publish/yank event.

```json
{
  "generated_at": "2026-04-17T18:22:14Z",
  "hub_version": "1.0.0",
  "plugins": [
    {
      "slug": "fft-classical",
      "display_name": "Classical FFT",
      "category": "fft",
      "is_verified": true,
      "versions": [
        {
          "version": "1.3.0",
          "sdk_compat": ">=1.2,<2.0",
          "sha256": "fa23…",
          "size_bytes": 8247,
          "review_status": "published",
          "published_at": "2026-04-12T18:22:14Z",
          "archive_url": "https://hub.magellon.org/v1/plugins/fft-classical/versions/1.3.0/archive"
        }
      ]
    }
  ]
}
```

**8. `GET /v1/healthz`** — `200` with `{ "status": "ok", "db": "ok", "storage": "ok" }`. Used by load balancers and uptime probes. No auth.

### 4.3 Author endpoints in detail

All require `Authorization: Bearer mhub_<raw_token>`. Token must have scope `publish` (or `admin`).

**9. `GET /v1/me`**

```json
{
  "id": 42,
  "username": "magellon-org",
  "email": "team@magellon.org",
  "role": "author",
  "created_at": "..."
}
```

**10. `POST /v1/plugins`** — Claim a slug.

Request:
```json
{
  "slug": "fft-classical",
  "display_name": "Classical FFT",
  "category": "fft",
  "description_short": "FFT magnitude spectrum via scipy.fft.",
  "homepage_url": "https://magellon.org/plugins/fft-classical",
  "repository_url": "https://github.com/magellon-org/fft-plugin",
  "license": "MIT"
}
```

Response `201` → plugin detail shape from §4.2.

Errors:
- `409` if slug already taken.
- `422` if slug doesn't match the slug regex (`^[a-z0-9._-]+$`), category not in the allowed list, URLs malformed.
- `403` if the caller's token lacks `publish` scope.

Claiming a slug does not create a version. The plugin page exists but has no published version and is not shown in default search results (filter: only plugins with ≥1 published version unless `include_empty=true`).

**11. `PATCH /v1/plugins/{slug}`** — Update metadata.

Request: subset of:
```json
{
  "display_name": "...",
  "description_short": "...",
  "homepage_url": "...",
  "repository_url": "...",
  "license": "..."
}
```

`slug`, `category`, `is_verified`, `is_disabled`, `owner_user_id` are NOT mutable here (category by transfer request only; ownership via admin endpoint; verify/disable admin-only).

Response `200` → plugin detail. Errors: `403` if not owner; `404` if disabled (authors can still see their own disabled plugins; non-owners 404).

**12. `POST /v1/plugins/{slug}/versions`** — Upload a new version.

**Multipart form** with one field:
- `archive`: a `.magplugin` file.

Server extracts `plugin.yaml` from the archive and:
1. Parses the manifest (422 on invalid YAML / unknown schema version / field violations).
2. Verifies `manifest.plugin_id == slug` (409 otherwise — the URL and the archive must agree).
3. Verifies `(slug, manifest.version)` doesn't already exist (409).
4. Computes sha256, dedups against `plugin_archives`.
5. Persists a `plugin_versions` row with `review_status='pending'`.
6. Logs a `version.upload` audit event.
7. Bumps `plugins.updated_at`.

Response `201`:
```json
{
  "plugin_slug": "fft-classical",
  "version": "1.3.0",
  "review_status": "pending",
  "submitted_at": "2026-04-17T18:22:14Z",
  "sha256": "fa23…",
  "size_bytes": 8247
}
```

Limits:
- Max archive size: 20 MiB by default (config `HUB_MAX_ARCHIVE_BYTES`). 413 on over-size.
- One upload of the same `(slug, version)` permitted even if pending; returns the existing row with 200 rather than 409 to make CI re-runs idempotent on transient network failures. A **published** version may not be overwritten — authors bump the version.

**13. `POST /v1/plugins/{slug}/versions/{version}/yank`**

Request:
```json
{ "reason": "critical bug in MTF computation" }
```

Transitions `review_status` from `'published'` → `'yanked'`. The archive remains downloadable by `{slug, version}` (for reproducibility — never break an installed deployment). Yanked versions are:
- filtered out of `/v1/index.json` for new-install discovery (so a fresh CoreService ignores them);
- filtered out of the default Browse view on the hub's public surface;
- still returned for direct `GET /v1/plugins/{slug}/versions/{version}` with an explicit `"review_status": "yanked"` flag.

Errors: `409` if not currently `published`. Owners can yank their own; admins can yank any.

**14–17. `/v1/me/plugins`, `/v1/me/tokens` CRUD** — Straightforward CRUD; token creation response includes the raw token exactly once:

```json
{
  "id": 17,
  "token": "mhub_A1B2C3D4E5F6G7H8I9J0K1L2M3N4O5P6",
  "prefix": "mhub_A1B2",
  "name": "CI robot",
  "scopes": ["publish"],
  "created_at": "...",
  "expires_at": null
}
```

After this response, the hub only stores `token_hash`. Subsequent `GET /v1/me/tokens` returns everything except the raw token.

### 4.4 Admin endpoints in detail

All require `Authorization: Bearer …` from a user with `role='admin'`. Scope `admin` is required in addition to admin role (defense-in-depth: an admin user can mint an author-scope token for a laptop that shouldn't be able to approve reviews from a coffee shop).

**18. `GET /v1/admin/reviews`** — Pending queue.

Query params: `status=pending|rejected|all` (default `pending`), `page`, `page_size`.

Response:
```json
{
  "items": [
    {
      "plugin_slug": "fft-gpu",
      "version": "0.2.0",
      "submitted_at": "2026-04-17T10:00:00Z",
      "submitted_by": { "id": 58, "username": "acme-labs" },
      "sdk_compat": ">=1.2,<2.0",
      "category": "fft",
      "size_bytes": 12083,
      "image_ref": "ghcr.io/acme-labs/fft-gpu:0.2.0",
      "review_url": "/v1/plugins/fft-gpu/versions/0.2.0"
    }
  ],
  "page": 1, "page_size": 20, "total": 4
}
```

**19. `POST /v1/admin/plugins/{slug}/versions/{version}/approve`**

Request (optional):
```json
{ "notes": "LGTM, image scanned clean, manifest sane." }
```

Effects: sets `review_status='published'`, `reviewed_by_user_id`, `reviewed_at=now()`, `published_at=now()`, persists `review_notes`. Triggers a `/v1/index.json` rebuild. Logs `version.approve`.

Errors: `409` if not currently `pending`.

**20. `POST /v1/admin/plugins/{slug}/versions/{version}/reject`**

Request (required):
```json
{ "notes": "Rejected: manifest claims sdk_compat >=1.0 but imports SDK 1.2 symbols (see manifest.yaml line 7)." }
```

Effects: sets `review_status='rejected'`, `reviewed_at`, `reviewed_by_user_id`, `review_notes`. Author is notified by email (phase 2 — MVP is poll-based). No effect on index (rejected never enters it).

**21. `POST /v1/admin/plugins/{slug}/verify`**

Request:
```json
{ "verified": true }
```

Toggles `plugins.is_verified`. Affects the "verified" filter and a badge in the UI. Audit-logged. Reversible.

**22. `POST /v1/admin/plugins/{slug}/disable`**

Request:
```json
{ "reason": "takedown: DMCA / malware / abuse", "purge_archives": false }
```

Sets `plugins.is_disabled=true`. Refuses new versions. Existing archives remain downloadable-by-id unless `purge_archives=true` (in which case archives are removed from storage and the `plugin_archives` rows are deleted, tombstoning reproducibility intentionally — only for legal takedowns).

**23. `GET /v1/admin/audit`** — Paginated `audit_log` query.

Query params: `actor_user_id`, `target_type`, `target_id`, `action`, `since`, `until`, `page`, `page_size`. Response is a list of audit rows.

### 4.5 Phase 2 auth endpoints

**24. `GET /v1/auth/github`** — Redirect (`302`) to GitHub OAuth authorization URL with `state` cookie.

**25. `GET /v1/auth/github/callback?code=…&state=…`** — Exchanges the code for a GitHub access token, fetches the user's profile, upserts a `users` row keyed on `github_id`, mints an API token with scope `publish`, redirects to the configured client URL with the raw token in a one-time fragment (client stores it and redirects cleanly).

---

## 5. Authentication & authorization

### 5.1 Token format

Raw token: `mhub_` + 32-char base62 random. Example: `mhub_A1B2C3D4E5F6G7H8I9J0K1L2M3N4O5P6`.

Stored as `token_prefix` (first 8 chars, for display) + `token_hash` (sha256 of raw). Verification: `bcrypt.verify(raw, token_hash)` or `hashlib.sha256(raw) == token_hash`. Pick sha256 for performance (tokens are high-entropy randoms, not user passwords — bcrypt's KDF is overkill).

Tokens are authenticated via `Authorization: Bearer <raw>`. Reject tokens lacking the `mhub_` prefix with `401`.

### 5.2 Scopes

Enumerated (phase 1):
- `publish` — upload versions, claim plugins, manage own tokens, read own plugins.
- `admin` — everything in `publish` plus admin endpoints. Only a `role='admin'` user can mint an `admin`-scoped token.

Per-endpoint scope requirements are listed in the catalog (§4.1). Enforcement lives in a FastAPI dependency:

```python
def require_scope(scope: str):
    def dep(token: Annotated[ApiToken, Depends(get_current_token)]) -> ApiToken:
        if scope not in token.scopes:
            raise HTTPException(403, detail=f"token missing required scope '{scope}'")
        return token
    return dep
```

### 5.3 Role vs scope

`role='admin'` is a property of the **user**. `scope='admin'` is a property of a **specific token** that user minted. An admin user can (and should) use separate tokens for separate machines and only grant `admin` scope to the ones they review plugins from.

### 5.4 Rate limiting (MVP = light; production = required)

- Unauthenticated: 60 req/min/IP for GETs. 429 on overflow.
- Authenticated author: 300 req/min/token, 10 upload/hour/token.
- Admin: no rate limit on admin endpoints, same rate as author on public ones.

Implement with `slowapi` (Starlette middleware) or equivalent. Configurable via env.

### 5.5 CSRF / CORS

The hub's clients are CoreService deployments (server-to-server) and a small admin UI on the same origin. CSRF is not applicable for token-authenticated APIs (tokens are not sent automatically like cookies). CORS: open `GET` to `*`; authenticated endpoints require an explicit origin allow-list via `HUB_CORS_ORIGINS` env.

---

## 6. Archive storage

### 6.1 Abstraction

```python
class StorageBackend(Protocol):
    async def put(self, *, sha256: str, content_type: str, data: BinaryIO) -> str:
        """Store data, return storage_key. Idempotent on same sha256."""
    async def get(self, storage_key: str) -> AsyncIterator[bytes]:
        """Stream the archive bytes."""
    async def head(self, storage_key: str) -> StorageObjectMeta:
        """size, content_type, last_modified."""
    async def delete(self, storage_key: str) -> None:
        """Purge. Used only for admin takedowns with purge_archives=true."""
```

Two backends at MVP:

**Filesystem** — default for dev and single-node deployments.
- Root: `HUB_STORAGE_FS_ROOT`, default `/var/lib/magellon-hub/archives/`.
- Key scheme: `archives/<sha256[0:2]>/<sha256[2:4]>/<sha256>.magplugin`.
- Serving: stream via FastAPI's `FileResponse` with `Cache-Control: public, max-age=31536000, immutable` and `ETag: <sha256>`. Behind nginx in prod, use X-Accel-Redirect.

**S3-compatible** — for prod with R2 / S3 / MinIO.
- Env: `HUB_STORAGE_S3_BUCKET`, `HUB_STORAGE_S3_ENDPOINT`, `HUB_STORAGE_S3_ACCESS_KEY_ID`, `HUB_STORAGE_S3_SECRET_ACCESS_KEY`, `HUB_STORAGE_S3_REGION`.
- Key scheme: `archives/<sha256[0:2]>/<sha256[2:4]>/<sha256>.magplugin` (same sharding as FS).
- Download: serve via pre-signed URL (redirect `302` to a 5-minute-lived URL) or proxy through the hub app. Redirect is preferred for bandwidth; proxy may be needed if clients need the download counted server-side.

### 6.2 Deduplication

`plugin_archives.sha256` is unique. On upload, compute sha256 before commit; if a row with that sha256 exists, reuse the existing `archive_id`. Two identical archives across two plugins share storage.

### 6.3 Garbage collection

Archives referenced by zero `plugin_versions` rows are orphans. A nightly job selects them and calls `StorageBackend.delete`. Runs with a safety delay (orphans older than 24 h only) to avoid racing in-flight uploads.

---

## 7. Review workflow

State machine on `plugin_versions.review_status`:

```
            upload                    approve
   (nil) ──────────> pending ────────────────> published ─────┐
                        │                           │        yank
                        │ reject                    │         │
                        v                           v         v
                    rejected                     yanked <─────┘
                    (terminal)                   (terminal, still downloadable)
```

**Transitions (who can fire):**

| From | To | Actor | Endpoint |
|---|---|---|---|
| (nil) | pending | owner | POST `/v1/plugins/{slug}/versions` |
| pending | published | admin | POST `/v1/admin/.../approve` |
| pending | rejected | admin | POST `/v1/admin/.../reject` |
| published | yanked | owner or admin | POST `/v1/plugins/.../yank` |

Notably:
- No `rejected → pending` re-submit. If a version is rejected, the author must bump the version number and re-upload. This keeps the `{slug, version}` identity immutable.
- No `yanked → published` un-yank in phase 1. It's a small surface to add in phase 2 if operators ask for it; for now, yanking is a one-way door that forces a version bump for a re-publish, which is simpler to reason about.

**Author visibility:**

Authors always see all states of their own plugins (pending, rejected, yanked, published) on `/v1/me/plugins` and `/v1/plugins/{slug}/versions?include_pending=true`. Anonymous / other-user views see only `published` + `yanked`, with yanked deprioritized.

**Email notifications (phase 2):** `pending→published`, `pending→rejected` fire an email to the author. MVP is poll-only: authors check their own plugin list.

---

## 8. CoreService integration

### 8.1 Remote-catalog fetcher

New module in CoreService: `core/plugin_remote_catalog.py`. A background thread that:

1. On boot and every `HUB_POLL_SECONDS` (default 300 s), fetches `GET {HUB_URL}/v1/index.json` with `If-None-Match: <last_etag>`.
2. Parses the response. Stores it in an in-memory structure indexed the same way as the local catalog.
3. Exposes the remote entries alongside local ones via the existing `GET /plugins/catalog` endpoint — add a `source: 'local' | 'remote'` field to each entry.

**Config:**
- `HUB_URL` — full URL of the hub (e.g. `https://hub.magellon.org`). If unset, the remote fetcher is disabled and the existing local-only behaviour is preserved.
- `HUB_POLL_SECONDS` — default 300.
- `HUB_TRUST_MODE` — one of `verified-only` (default), `all`, `allowlist` (with `HUB_ALLOWLIST=slug1,slug2,...`). Controls which remote entries are shown to operators.

### 8.2 Install from remote

`POST /plugins/catalog/{catalog_id}/install` already accepts a stored local archive. For remote installs:

- New endpoint: `POST /plugins/catalog/remote/{slug}/{version}/install`. CoreService streams the archive from the hub's archive endpoint, validates it (same validation pipeline as local archive uploads), installs it.
- Optional: cache the downloaded archive under the local catalog so a subsequent install for the same `{slug, version}` is hub-free. Operator can clear the cache anytime.

### 8.3 Failure modes

- Hub is down → the background fetcher logs and retries; cached index stays valid. Install-from-remote returns `503` with a clear message ("hub unreachable"); install-from-local-cache still works if the archive was cached earlier.
- Hub is reachable but refuses the CoreService's SDK (all archives target newer SDK) → Browse UI shows them with a "requires SDK X" badge; install returns `409` (same as /install/archive).
- Hub serves a broken archive (sha256 mismatch) → CoreService rejects on validation, logs an integrity warning, does not retry the same archive until the hub republishes.

---

## 9. Versioning policy

### 9.1 Hub API versioning

Base path is `/v1`. Breaking changes to:
- URL shape,
- required fields,
- HTTP status codes for existing error cases,
- auth contract (token format, scope semantics),

trigger a new `/v2` base path. The previous `/v1` is supported for ≥6 months with deprecation headers (`Sunset`, `Deprecation`). Additive changes (new optional fields, new endpoints) do not bump the major.

### 9.2 Archive schema versioning

The archive's own `schema_version` is part of the SDK's public contract (see `magellon-sdk/CONTRACT.md` §7). The hub parses whatever `schema_version` the SDK in its pip dependencies supports. Hub upgrades to a new SDK follow the SDK's SemVer — a minor-bump SDK upgrade is safe; a major is a coordinated event.

### 9.3 DB migrations

Alembic. Migrations are additive-only in production:
- Adding columns with defaults: fine.
- Dropping columns / tables: always in two phases (deploy code that no longer reads, then drop in the next release).
- Backfills: as separate data migrations with progress logging, runnable offline.

---

## 10. Operational concerns

### 10.1 Deployment

- **Dev:** `docker compose up` with `app`, `postgres`, `minio` (S3-compatible) services. `make migrate` runs Alembic; `make seed` adds a local admin user + token.
- **Prod:** containerized FastAPI behind a reverse proxy (nginx / Caddy / Cloudflare). Postgres 15+ (managed is fine). Object storage: R2 / S3. Background jobs in the same container (APScheduler in-process) for MVP; split to a worker container if the job surface grows.

### 10.2 Environment

| Var | Default | Purpose |
|---|---|---|
| `HUB_DATABASE_URL` | `postgresql+asyncpg://hub:hub@localhost/hub` | Postgres DSN. |
| `HUB_STORAGE_BACKEND` | `filesystem` | `filesystem` or `s3`. |
| `HUB_STORAGE_FS_ROOT` | `/var/lib/magellon-hub/archives/` | FS root when backend=filesystem. |
| `HUB_STORAGE_S3_BUCKET` | unset | Bucket when backend=s3. |
| `HUB_STORAGE_S3_ENDPOINT` | unset | Non-AWS endpoint (R2, MinIO). |
| `HUB_STORAGE_S3_REGION` | `us-east-1` | |
| `HUB_STORAGE_S3_ACCESS_KEY_ID` | unset | |
| `HUB_STORAGE_S3_SECRET_ACCESS_KEY` | unset | |
| `HUB_MAX_ARCHIVE_BYTES` | 20971520 (20 MiB) | Upload cap. |
| `HUB_CORS_ORIGINS` | `*` for GET, `[]` for authed | Comma-separated. |
| `HUB_GITHUB_CLIENT_ID` | unset | Phase 2 OAuth. |
| `HUB_GITHUB_CLIENT_SECRET` | unset | Phase 2 OAuth. |
| `HUB_INDEX_REBUILD_INTERVAL_MIN` | 60 | Background rebuild cadence. |
| `HUB_BASE_URL` | `http://localhost:8000` | Used when generating absolute URLs in `/v1/index.json`. |

### 10.3 Observability

- **Structured logs** to stdout: JSON with `ts`, `level`, `actor_id`, `request_id`, `route`, `status`, `duration_ms`.
- **Prometheus metrics** at `/metrics`:
  - `hub_http_requests_total{method,route,status}`
  - `hub_http_request_duration_seconds{method,route}`
  - `hub_archive_upload_bytes_total`
  - `hub_archive_download_bytes_total{slug,version}`
  - `hub_reviews_pending_count`
  - `hub_storage_orphan_count`
- **Tracing:** OpenTelemetry SDK init stubbed; exporter configurable via `OTEL_EXPORTER_OTLP_ENDPOINT`. Off by default.

### 10.4 Backup

- Postgres: daily base backup + WAL archiving. RPO ≤ 5 min for prod.
- Object storage: S3 versioning on the bucket (retention 30 d), or for FS, nightly rsync to cold storage. **Losing archives is catastrophic** — old CoreService installs depend on `{slug, version}` → sha256 stability.
- Audit log: considered part of the DB; same backup cadence.

### 10.5 Monitoring / alerting

- Alert on: `healthz` != 200 for 2 min, `hub_reviews_pending_count > 20`, storage backend errors, DB connection errors, `hub_http_request_duration_seconds` p99 > 2 s for the archive endpoint (suggests disk pressure or slow upstream storage).

---

## 11. Security

### 11.1 Archive validation (upload time)

- Max size enforced in FastAPI before buffering fully (stream with chunk limit).
- Archive must be a valid zip.
- Must contain a top-level `plugin.yaml`.
- Manifest must validate against `PluginArchiveManifest` (see SDK).
- `manifest.plugin_id` must match the URL slug.
- `manifest.image.ref` must be a syntactically valid image reference (image+tag+digest regex).
- **Do NOT** execute the plugin or pull the image server-side — the hub never runs plugin code. Image scanning is a phase 2 integration (Trivy / Grype).

### 11.2 Secrets

- API tokens stored hashed.
- No plaintext secrets in logs. Wrap sensitive handlers with a `sanitize()` helper that strips `Authorization`, `token`, `password` fields.
- OAuth client secret in env, never in DB.

### 11.3 Abuse handling

- `plugins.is_disabled=true` takes a plugin offline instantly.
- Users can be disabled (`users.is_disabled=true`), revoking all their tokens.
- Tokens can be revoked (`api_tokens.revoked_at`).
- Audit log retains actor even for deleted users (`ON DELETE SET NULL` on `audit_log.actor_user_id`).

### 11.4 Supply-chain notes

The hub serves pointers to Docker images; it does NOT host the images themselves (that's what container registries are for). An operator installing a published plugin is still trusting the image's maintainer. The hub's job is to make sure the `{slug, version} → manifest → image_ref` mapping is authoritative, signed, and tamper-evident:

- **Phase 1:** archive sha256 integrity is all we have.
- **Phase 2:** sign archives on publish with an hub-owned key; CoreService verifies the signature.
- **Phase 3:** cosign / in-toto attestations referencing the image digest, so a CoreService that installs the plugin can verify the image hasn't been swapped under the tag.

---

## 12. Phase 2 / 3 backlog

### Phase 2 (after MVP is in production)

- GitHub OAuth login.
- Email notifications on review transitions.
- Search: Postgres full-text index on `display_name + description + manifest.description`.
- Popularity: rolling 30-day downloads, sort-by-popularity.
- Image scanning hook on upload (Trivy via subprocess or API).
- Archive signing (hub signs, CoreService verifies).
- Admin UI as a real HTML surface (HTMX / Starlette templates).

### Phase 3 (when the ecosystem warrants it)

- Federation: multi-hub discovery via a standard `/v1/index.json` format; CoreService polls N hubs.
- Org accounts (teams share ownership of a plugin).
- Usage telemetry from CoreService deployments (opt-in, anonymised).
- Webhook subscriptions for "new version of X published".
- Vulnerability feed integration.

---

## 13. Open decisions for the team

1. **Sync vs async SQLAlchemy.** CoreService is sync. Going async here is a step up but is cleaner for long-running uploads/downloads. **Recommended:** async (`asyncpg`) — archive I/O benefits most.

2. **Object storage default in prod.** R2 vs S3 vs self-hosted MinIO. **Recommended:** R2 for OSS distribution (Cloudflare zero-egress is a big win for a download-heavy service).

3. **Admin UI scope.** MVP is API-only; add HTML admin screens in phase 2, or start with a small Jinja2 page for the review queue only. **Recommended:** start with a single admin HTML page rendering the review queue (≤ 200 LOC). Everything else is API-for-now.

4. **Who runs the canonical instance?** `hub.magellon.org` needs an owner, TLS cert, domain, auth story. Not in scope for the team building the code, but should be decided before launch.

5. **Legal / takedown policy.** We need a stance on malicious plugins, DMCA, re-publishing under a new slug after disable. Phase 1 code supports the `disable` action; the policy doc doesn't exist yet.

6. **CoreService config surface for hub URL.** Environment variable vs `settings.yml` field? **Recommended:** both, with env overriding file, matching CoreService's existing config precedence.

---

## 14. Implementation milestones (suggested)

A rough staging for 3–4 weeks of work, one developer:

**M1 — skeleton (week 1):** repo scaffold, Dockerfile, Alembic, users + api_tokens + plugins + plugin_versions + plugin_archives tables, storage backend interface + filesystem impl, `/v1/healthz`, `/v1/plugins` (list + detail), `/v1/plugins/{slug}` claim, token-auth dependency.

**M2 — publishing (week 2):** upload `/v1/plugins/{slug}/versions`, archive validation, dedup, `GET /archive`, `PATCH /{slug}`, `/v1/me/*`, `/v1/me/tokens/*`.

**M3 — review (week 3):** admin role, `/v1/admin/reviews`, approve/reject/yank endpoints, audit log, `/v1/index.json` background rebuild, `/v1/categories`, `/v1/index.json` end-to-end test.

**M4 — integration (week 4):** CoreService remote-catalog fetcher, install-from-remote endpoint, S3 storage backend, rate limiting, observability metrics, one small admin HTML page for the review queue, dockerized docker-compose dev env, minimal README for operators.

Ship M4 to a staging environment before production.

---

## 15. Out of scope for this spec

- Multi-tenant SaaS (different orgs with isolation).
- Billing / payments.
- CI providers other than GitHub (GitLab, Bitbucket) for OAuth.
- Anything non-Python plugins — the hub is Magellon-plugin-specific; a generic artifact registry (Harbor, Artifactory) is a different product.
- A client-side CLI for `magellon-sdk hub login` / `publish` — that lives in `magellon-sdk`, not here. The hub only exposes the API; the CLI is a follow-up SDK phase.
