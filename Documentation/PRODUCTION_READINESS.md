# Magellon Production Readiness Checklist

Use this before promoting CoreService, magellon-sdk based plugins, and the React app into a shared or production environment.

## Credential Rotation (one-time, after 2026-07 security pass)

- Git history contains the historical dev-stack password and one revoked AWS key pair (`infrastructure/Deployment/assets/terraform/aws/instance.tf`, removed 2026-07-06). Deactivate that AWS key in IAM and rotate any real system still using the dev-stack password before exposing it beyond a trusted network.
- The dev-stack default password remains valid ONLY for local/dev infrastructure; the CI repo-hygiene gate blocks it from appearing in any new file.

## CoreService

- Set `APP_ENV=production`.
- Set `JWT_SECRET_KEY` (32+ chars). Startup hard-fails in production without it.
- Set `MAGELLON_CORS_ALLOWED_ORIGINS` to the exact React app origins. Do not rely on wildcard CORS in production.
- Provide secrets through environment variables or a secret manager, not committed YAML:
  - database user/password/host/name
  - RabbitMQ credentials
  - API docs credentials
  - security setup token
  - Slack and Leginon credentials when enabled
- Keep `security_setup_settings.ENABLED=false` after initial bootstrap, or use `AUTO_DISABLE=true` and verify `.security_setup_completed` is present.
- Tune DB pool settings for the deployment:
  - `MAGELLON_DB_POOL_SIZE`
  - `MAGELLON_DB_MAX_OVERFLOW`
  - `MAGELLON_DB_POOL_TIMEOUT`
  - `MAGELLON_DB_POOL_RECYCLE`
- Verify `/health/live` returns `200`.
- Verify `/health/ready` returns `200` only after DB, bus, and enabled background services are healthy.
- Treat `/admin/*`, `/web/ops/*`, `/db/security/*`, and `/configs` as administrator-only surfaces.
- Confirm request logs include `X-Request-ID`, method, path, status, and duration without request bodies or secret values.

## Database Migrations

- Fresh environments: `alembic upgrade head` builds the full schema from an empty database (baseline migration `0000_baseline_schema` + chain). No manual dump loading required; the container entrypoint runs this automatically.
- Existing environments (schema loaded from the dump before 2026-07): adopt with `alembic stamp <revision>` matching the database's actual state, then upgrade. The baseline migration refuses to run against a database that already has the base schema.
- The Docker init dump (`Docker/services/mysql/init/magellon01db.sql`) still seeds dev stacks with data; migrations are the source of truth for schema.

## Container Notes

- CoreService listens on port **8000** inside the container (non-root user cannot bind 80); compose maps `MAGELLON_BACKEND_PORT` to it. The image runs as user `magellon` and no longer ships the test suite.
- The React image reads `API_URL` (and optional `WEB_API_URL`) **at container start** and generates `/config.js`; retargeting the backend requires only an env change and restart, not a rebuild.

## Message Bus And Background Services

- Confirm RabbitMQ/NATS URLs and credentials point at the intended environment.
- Confirm enabled background services show `status=ok` in `/health/ready`.
- Explicitly disable unused forwarders/listeners with their `MAGELLON_*` toggle instead of leaving them half-configured.
- Keep broker management credentials separate from application publish/consume credentials where possible.

## Plugins And SDK

- Build plugins against the current `magellon-sdk` major version.
- Keep plugin runtime files out of git:
  - `.env`
  - `app.log`
  - `logs/`
  - generated outputs
- Decide per plugin whether `uv.lock` is a tracked reproducibility artifact. Do not mix generated local locks and committed locks accidentally.
- Run `magellon-sdk` tests in CI with `pip install -e ".[dev]"`.
- Check plugin manifests for correct `plugin_id`, version, category, install method, and required SDK range.

## React App

- Run `pnpm run type-check`; this includes `noImplicitAny` and `strictNullChecks`.
- Run `pnpm run lint`; warnings fail the gate.
- Keep Playwright debug scripts, logs, screenshots, and reports out of git unless they are stable named tests.
- Point the app at the production CoreService API and web API URLs through environment-specific config.

## CI Gates

- `python scripts/check_repo_hygiene.py` (includes secret patterns + dev-password ratchet)
- `python scripts/refresh_sdk_wheel.py --check` (bundled plugin wheels match SDK version)
- CoreService ruff checks
- CoreService tests, no infra (`pytest` — must be green; `requires_db` auto-skips)
- CoreService `requires_db` suite against a MySQL service container (security/RLS tests run for real)
- SDK ruff checks
- SDK tests, including the real-RabbitMQ e2e suite against a broker service container
- React type-check
- React lint
- Route-table auth gate (`CoreService/tests/test_route_auth_policy.py`, part of the test suite)

## Release Smoke Checks

- Login as an administrator and a non-administrator.
- Confirm non-admin users cannot access administrator routes.
- Confirm `/configs` returns redacted values.
- Confirm plugin install/start/stop/status flows.
- Confirm one representative image workflow from import through plugin result display.
- Confirm logs and generated plugin outputs are written under runtime paths, not the repository.
