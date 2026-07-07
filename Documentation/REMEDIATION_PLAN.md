# Magellon Remediation & Improvement Plan

**Status:** EXECUTED 2026-07-06 — commits `56e73d70` (S), `07084aa4` (R, SDK 2.5.0 tagged), `69074b8b` (T), `70b5ee88` (D), `82e6f6ef` (F), `5fdbeaa9` (C).
Remaining operator actions: rotate the AWS key found in terraform (deactivate in IAM) and any real system using the dev-stack password; decide on git-history scrub. Deferred by design: knip CI gate (43-file report needs triage), RLS f-string→Core SQL rewrite (needs live-DB verification loop), plugin install/uninstall role escalation, F3 React Query migration (opportunistic per ADR 0001).
**Source:** Full-platform review of CoreService (6.5/10), magellon-react-app (6.5/10), magellon-sdk (7/10) run 2026-07-06.
**Goal:** Close the security, runtime-truth, and hygiene gaps without touching the (sound) architecture. Estimated total: ~2 weeks of focused work for phases S/R/T/D; F and C are ongoing budgeted work.

Ordering rule: phases S → (R ∥ T) → D → F → C. Within a phase, items are ordered by severity. Each item has an acceptance check; an item is not done until its check passes.

---

## Phase S — Security hardening (do first, ~2 days)

### S1. Rotate and scrub the committed password
The same real password is committed in `CoreService/MyNotes.md` and `magellon-react-app/tests/e2e/plugin-runner.spec.ts`.
- Rotate the credential everywhere it is used (MySQL root, Postgres, the `super` app user).
- Delete `MyNotes.md` and `messages.md` from the repo; scrub history (`git filter-repo`) or accept the rotation as sufficient if history rewrite is too disruptive — decide explicitly, don't default.
- Parametrize Playwright credentials via env (`E2E_USERNAME` / `E2E_PASSWORD`), fail the spec with a clear message when unset.
- Add secret scanning to CI: extend `scripts/check_repo_hygiene.py` with a gitleaks-style pattern pass (or add gitleaks action) so this class of leak blocks PRs.
- **Accept:** grep for the old password returns nothing; CI fails on a planted fake secret.

### S2. JWT secret must hard-fail in production
`dependencies/auth.py:31` falls back to a hardcoded signing key.
- On startup with `APP_ENV=production` and `JWT_SECRET_KEY` unset (or equal to the known fallback, or < 32 chars): raise and refuse to bind.
- Outside production, log a prominent warning.
- **Accept:** unit test asserting startup failure; `PRODUCTION_READINESS.md` updated.

### S3. Authenticate the dispatch and registry surfaces
`controllers/dispatch_controller.py` and mutating routes in `plugin_registry_controller.py` have no auth dependencies.
- Require an authenticated user for `POST /dispatch/{category}/run` and all dispatch/preview/sync routes; decide role policy (any authenticated user vs a `CanDispatch` permission) and write it down in one line in the controller docstring.
- Sweep all routers for the same gap: everything except `/health/*`, docs (already gated), and explicitly public routes gets an auth dependency. Add a characterization test that walks the FastAPI route table and asserts every route is either in an allowlist or carries an auth dependency — this turns policy into a gate.
- **Accept:** the route-table test passes and is the source of truth for "public" routes.

### S4. Socket.IO and CORS
- `core/socketio_server.py:33`: replace `cors_allowed_origins='*'` with the `MAGELLON_CORS_ALLOWED_ORIGINS` list; authenticate `connect` (JWT in auth payload) and authorize room joins per user.
- `core/exception_handlers.py:22-31`: stop reflecting arbitrary `Origin` with `allow-credentials`; reuse the main CORS allowlist.
- `main.py:120`: non-production default of `["*"]` with credentials — keep for dev if desired, but never with `allow_credentials=True` on wildcard.
- **Accept:** integration test — a disallowed origin gets no CORS headers on both success and error paths; unauthenticated socket connect is rejected.

---

## Phase R — SDK runtime truth (~3 days, parallel with T)

The theme: make the runtime match what CONTRACT.md, docstrings, and tests already claim.

### R1. RMQ consumer reconnect
`bus/binders/rmq/binder.py:108-113` — a broker drop permanently kills consumption while the plugin's `/health` stays green.
- Wrap the consume loop in a reconnect-with-backoff loop (cap + jitter); expose consumer health so the runner/plugin `/health` can report degraded instead of ok.
- Fix the `plugin_runner.py:445-447` docstring or make it true — prefer making it true.
- **Accept:** e2e test (real broker): restart RabbitMQ mid-consume, task published after restart is processed; plugin `/health` reflects the gap.

### R2. Poison-message handling on real RMQ
The `x-magellon-redelivery` header is only written by `InMemoryBinder`, so the retry ceiling never fires in production and poison messages hot-loop with zero backoff.
- Either write the header on the republish path (nack→republish with incremented header instead of `requeue=True`), or switch task queues to quorum queues and read `x-delivery-count`. Pick one; document in CONTRACT.md.
- Honor `RetryableError.retry_after_seconds` (delayed republish or per-message TTL + DLX), or delete the field from the API — don't ship a no-op knob.
- **Accept:** e2e test: a handler that always raises lands in the DLQ after `max_retries` on a real broker.

### R3. Async handler support
`interfaces.py:69-74` promises "binder handles the sync/async boundary"; RmqBinder never awaits coroutines and ACKs them as success.
- Detect coroutine results and run them (dedicated loop/thread in the binder), or reject async handlers at `subscribe()` time with a clear error. Prefer support — the type signature already promises it.
- Same decision for the "return Envelope → publish to result route" promise in `interfaces.py:154-157`: implement or delete from the contract.
- **Accept:** test with an async handler round-trips on both binders; no silent-ACK path remains.

### R4. `call_rpc` thread safety
`binder.py:459-495` publishes and polls on the shared pika connection without `_publish_lock`.
- Take the lock, or give RPC its own connection; add the same reconnect-once behavior as publish.
- **Accept:** stress test: concurrent RPC + publish from multiple threads, no connection corruption.

### R5. Contract and versioning hygiene
- Update CONTRACT.md header/pins to 2.x; remove or implement the `TaskDto` alias claim (`models/__init__.py:9`, `tasks.py:97-99`); fix the `extra='ignore'` claim vs `CryoEmImageInput.extra="allow"`.
- Fix `httpx2` typo in `pyproject.toml:41`; tag `v2.4.0` and tag all future releases; reconcile the stale MB5 migration comments in `plugin_runner.py` / `discovery.py`.
- Add a CI step that builds the SDK wheel and refreshes the copies bundled in plugin Dockerfiles (kills the stale-wheel `ImportError` class permanently).
- **Accept:** a doc-drift test importing every name in CONTRACT.md §2.1; `git tag` shows the current release.

---

## Phase T — Test & CI integrity (~2 days, parallel with R)

### T1. Green default pytest for CoreService
54 failures/errors, all unmarked live-MySQL dependence — concentrated in the security test files.
- Mark them `requires_db`; default run skips them and is green.
- Add a CI job with a MySQL service container that runs the `requires_db` set — the security tests must actually execute somewhere on every PR, not just be skippable.
- **Accept:** `pytest` clean locally with no infra; CI shows the DB job passing.

### T2. SDK e2e against a real broker in CI
`test_e2e_rabbitmq.py` currently skips when no broker is reachable, so R1/R2 fixes would be untested in CI.
- Add a rabbitmq service container to the SDK test job (or a separate job) so the e2e suite runs for real on every PR touching `magellon-sdk/`.
- **Accept:** CI log shows the e2e suite executed, not skipped.

---

## Phase D — Deploy & data hygiene (~3 days)

### D1. Alembic owns the schema
Migration 0001 assumes a schema that only exists in `database/magellon01db.sql`.
- Create a baseline migration `0000` capturing the full current schema (autogenerate against a dump-restored DB, then hand-verify); make `alembic upgrade head` build a working DB from empty.
- Add a CI check: upgrade-from-empty + a model/schema diff (autogenerate produces no ops).
- **Accept:** fresh MySQL + `alembic upgrade head` boots CoreService with all tests passing.

### D2. CoreService Docker hardening
- Add non-root `USER`; drop `tests/` and `test_main.http` from the image; pin `fastapi`/`uvicorn`/`scipy`; remove `apache-airflow-client` and runtime `pylint`.
- **Accept:** image runs as non-root; `pip check` clean; image size drops.

### D3. React runtime config
Replace the build-time `sed` patch of `src/shared/config/configs.json`.
- Serve `/config.json` at runtime (fetched at boot) or use `import.meta.env.VITE_*`; one image runs against any backend.
- Fix the axios singleton while in here (see F1 — same files).
- Remove the unused `.env` copy and `--config.dangerouslyAllowAllBuilds=true` from the Dockerfile if no longer needed.
- **Accept:** retarget API host by env/config change alone, no rebuild.

---

## Phase F — Frontend quality (budgeted, ~1 week spread out)

### F1. Correctness fixes (do with D3)
- `shared/api/AxiosClient.ts:117-123`: singleton ignores `baseUrl` after first call across 43 call sites. Key the cache by baseUrl (two named clients: `apiClient`, `webApiClient`).
- App-level ErrorBoundary wrapping the router in `main.tsx` (reuse the image-viewer boundary pattern).
- `shared/lib/useSocket.ts`: return reactive socket/sid state (useSyncExternalStore or state, not refs); stop tearing down/recreating the global socket on transient zero-refcount during route transitions.
- **Accept:** unit tests for client routing per baseUrl; a thrown render error shows a fallback, not a white screen.

### F2. Decompose the top god components
Budget: one per work session, top four only — `PluginRunner.tsx` (1,144 lines / 21 useState), `DashboardView.tsx` (1,170), `UserManagementPage.tsx` (1,067), `ParticleSettingsDrawer.tsx` (1,016).
- Extract embedded sub-components to their own files; collapse related useState clusters into reducers/stores (PluginRunner preview state: 8 → 1).
- Add a lint gate afterward: `max-lines` warning threshold so regressions surface.
- **Accept:** no file in the four exceeds ~400 lines; behavior pinned by existing tests + one Playwright pass.

### F3. One data-fetching idiom
- Configure the shared `QueryClient` (staleTime, retry) in `main.tsx`; write the pattern in a short ADR.
- Migrate raw axios-in-useEffect features to React Query opportunistically — every time a file is touched for another reason, not as a big-bang.
- **Accept:** ADR merged; net count of raw-fetch files goes down each month (track in review).

### F4. Dead surface and tooling
- Decide i18n: adopt (wire remaining components) or remove i18next + 3 locale trees. Current state (one consumer) is the worst of both.
- Delete starter-template fossils in `shared/config/settings.ts` (`twitterColor`, jsonplaceholder URL); remove empty `src/entities/session/`.
- Wire `knip` to a script + CI (it's already installed); gate dev/test routes (`/dev/realtime-mock`, FFT/Topaz test pages) behind `import.meta.env.DEV`.
- Playwright: move diagnostic scripts out of `tests/e2e` into an untracked `tests/diagnostics/`; keep only stable named specs; set `baseURL` + `webServer` in config; remove machine-specific `C:/projects/...` paths via env.
- Flip `tsconfig` to full `strict: true` (remaining flags are cheap given noImplicitAny/strictNullChecks already pass).
- **Accept:** knip runs in CI; prod bundle has no dev routes; `strict: true` type-checks clean.

---

## Phase C — CoreService structural cleanup (ongoing, lowest priority)

### C1. Split the grab-bags
- `plugins/controller.py` (1,839 lines) → routes vs service vs install-pipeline modules.
- `core/helper.py` (829 lines) → path canonicalization / queue naming / dispatch builders as separate modules.
- `push_task_to_task_queue` (`helper.py:252-262`): stop swallowing all exceptions into `False`; raise a typed error or return a result object, and audit callers.

### C2. Legacy stratum
- Replace f-string `text(f"...")` SQL in `webapp_controller.py` with bound parameters even where currently safe.
- Repositories: drop fake-`async` methods (make them sync, or truly async with a session-per-request pattern); remove module-level singletons.
- Consolidate the four copy-pasted `sys_sec_*` controllers behind a generic CRUD helper.
- Migrate `@app.on_event` to lifespan handlers; delete stale line-number comments in `main.py`.

### C3. Dead code sweep
- Delete: `tasks/` orphan `.pyc`, `sandbox/` scratch (monitor_v12/14/16), `main.spec`, `test_main.http`, root `uvicorn*.log` (gitignore the pattern), `session_access_controller_v2` naming (rename to canonical), commented-out logic in `MagellonImporter.py`.
- **Accept for all of C:** each item lands with its own commit and no behavior change per characterization suite.

---

## Explicitly deferred (recorded so they aren't re-litigated)

- SQLAlchemy 2.0-style model rewrite and XAF-residue column removal (`OptimisticLockField`, `GCRecord`) — high churn, low current pain; revisit after D1 gives Alembic ownership.
- `settings: Any` → typed Protocol across SDK entry points — do opportunistically when touching those seams (R-phase will touch several).
- `RecuirementResultEnum` rename — contract-locked; fix at the next SDK major, with alias.
- SDK env-var config seam (`MAGELLON_STEP_EVENTS_ENABLED` import-order landmine) — fold into the next deliberate SDK config redesign, not a point fix.

## Tracking

Work each phase as a short-lived branch series with the existing CI gates. Suggested cadence: S this week; R+T next; D after; F2/F3/C as standing budget (one item per session). Re-run the review scorecard after S+R+T+D — expected movement: CoreService 6.5 → ~8, SDK 7 → ~8.5, React 6.5 → 7 (F-phase carries the rest).
