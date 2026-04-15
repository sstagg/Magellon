# Phase 0 — Pytest Baseline

**Date:** 2026-04-14
**Branch:** `main`
**Command:** `venv/Scripts/python.exe -m pytest tests/ --ignore=tests/test_create_images.py --ignore=tests/test_motioncor_result_plot.py`

## Numbers

| Metric                       | Count |
|------------------------------|-------|
| Total collected              | 179   |
| Passing                      | 148   |
| Failing                      | 30    |
| Skipped                      | 1     |
| Collection errors (ignored)  | 2     |

## Collection-error files (excluded from suite)

Both fail because they reference paths that don't exist on a fresh checkout —
not because they're broken tests.

| File                                       | Reason                                                        |
|--------------------------------------------|---------------------------------------------------------------|
| `tests/test_create_images.py`              | `FileNotFoundError: 'C:\\temp\\data'` at collection            |
| `tests/test_motioncor_result_plot.py`      | Missing `./23mar23b_a_..._Log.txt` at collection              |

**Action:** leave excluded. Revisit in a later cleanup PR — they should be
reworked to skip when the fixture file is absent, instead of erroring at
collection.

## Failing-test categorisation

Each failure category is either environment-dependent or pre-existing
breakage unrelated to the Phase 0 safety-net work. None were caused by
recent changes.

| Category | Count | Example | Diagnosis | Phase-0 action |
|---|---|---|---|---|
| `test_say_hello` 404s | 3 | `test_home::test_say_hello` | Endpoints were renamed/removed; tests not updated | Leave. Fix in a dedicated "hello-route drift" PR. |
| RLS / row-level security | ~18 | `test_security_integration::*`, `test_webapp_rls::*` | Require live MySQL with seeded users | Tag with `@pytest.mark.requires_db` in a later PR; skip in unit-level CI. |
| Casbin admin bypass | 1 | `test_casbin_basic::test_administrator_bypass` | Requires live authz config | Same as RLS — mark `requires_db`. |
| Docker deployment | 1 | `test_deployment_docker` | Requires Docker daemon | Mark `requires_docker`. |
| Socket.IO | 2 | `test_socketio::test_asgi_app_wraps_fastapi` | Import error — API changed in the Socket.IO refactor (commit `fc0f325`) | Update test when we write PR 0.6 (Socket.IO emit shape tests). |
| Template picker async | 2 | `test_template_picker::TestAsyncEndpoint::test_async_pick_creates_job_in_store` | Job-store API changed after plugin-controller refactor | Update when we write PR 0.5 (HTTP contract tests). |
| Template picker 404 | 1 | `test_job_detail_not_found` | Route moved from per-plugin to generic `/plugins/jobs/{id}` | Update alongside PR 0.5. |
| Performance | 1 | `test_row_level_security::TestPerformance::test_performance_100_sessions` | Requires seeded DB | `requires_db`. |
| Security summary | 1 | `test_comprehensive_security_summary` | Requires seeded DB | `requires_db`. |

## Interpretation

The 148-passing set is the stable baseline Phase 0 characterization tests
build on top of. The 30 failures split into three actionable groups:

1. **Infrastructure-gated (~21 tests)** — need MySQL / Docker / RabbitMQ to
   pass. Not our baseline problem; will be marked with `requires_*` markers
   so CI can skip them in the unit tier and a nightly tier can run them.
2. **Tests that will be rewritten as part of Phase 0's own PRs (~5 tests)**
   — Socket.IO and template-picker tests get refreshed when we write
   PR 0.5 and PR 0.6.
3. **Endpoint drift (~3 tests)** — stale "hello" routes. Trivial to fix in a
   dedicated cleanup PR; not blocking.

No hidden regressions. We can proceed to **PR 0.2 — envelope golden files**
on top of this baseline.

## Reproduction

```
cd CoreService
venv/Scripts/python.exe -m pytest tests/ \
    --ignore=tests/test_create_images.py \
    --ignore=tests/test_motioncor_result_plot.py \
    -q
```

Expected (at the time of writing): `30 failed, 148 passed, 1 skipped`.
