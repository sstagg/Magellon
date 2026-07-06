# Magellon Production Readiness Checklist

Use this before promoting CoreService, magellon-sdk based plugins, and the React app into a shared or production environment.

## CoreService

- Set `APP_ENV=production`.
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

- `python scripts/check_repo_hygiene.py`
- CoreService ruff checks
- SDK ruff checks
- SDK tests
- React type-check
- React lint

## Release Smoke Checks

- Login as an administrator and a non-administrator.
- Confirm non-admin users cannot access administrator routes.
- Confirm `/configs` returns redacted values.
- Confirm plugin install/start/stop/status flows.
- Confirm one representative image workflow from import through plugin result display.
- Confirm logs and generated plugin outputs are written under runtime paths, not the repository.
