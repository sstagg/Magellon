# Live-stack Playwright e2e tests

These specs drive a real browser against the **full Magellon stack**:
CoreService, plugin runners, Vite dev server, RabbitMQ, NATS, MySQL.
They are **opt-in** — without `MAGELLON_E2E_LIVE=1` each spec calls
`test.skip(...)` so contributors who only have the frontend repo
checked out are never blocked by them.

## Running locally

1. Boot the brokers in Docker:
   ```
   docker compose up -d rabbitmq nats
   ```
2. Start CoreService (uvicorn) on `:8000`. On Windows always use
   `NATS_URL=nats://127.0.0.1:4222` — `localhost` resolves to IPv6
   first under ProactorEventLoop and the NATS container only listens
   on IPv4.
3. Start the FFT plugin runner on `:8010` with
   `MAGELLON_STEP_EVENTS_ENABLED=1` and (optionally)
   `MAGELLON_STEP_EVENTS_RMQ=1` for the dual-channel mirror.
4. Start the Vite dev server: `npm run dev`.
5. Drop three small input PNGs into the fixture directory
   (defaults to `C:/temp/magellon/gpfs/playwright_run`):
   `sample_00.png`, `sample_01.png`, `sample_02.png`.
6. Run the e2e project:
   ```
   MAGELLON_E2E_LIVE=1 npm run test:e2e
   ```

## Environment overrides

| variable                       | default                                           |
| ------------------------------ | ------------------------------------------------- |
| `MAGELLON_E2E_LIVE`            | unset (skip)                                      |
| `MAGELLON_E2E_FRONTEND`        | `http://localhost:8080`                           |
| `MAGELLON_E2E_BACKEND`         | `http://127.0.0.1:8000`                           |
| `MAGELLON_E2E_FIXTURE_DIR`     | `C:/temp/magellon/gpfs/playwright_run`            |
| `MAGELLON_E2E_USERNAME`        | `super`                                           |
| `MAGELLON_E2E_PASSWORD`        | `behd1d2`                                         |

Screenshots land in `tests/e2e/screenshots/<spec-name>/`.

## Wiring into CI

The `e2e-live` Playwright project is the integration point. A CI job
that boots the stack (e.g. via `docker compose up`) can then run:

```
MAGELLON_E2E_LIVE=1 npx playwright test --project=e2e-live
```

The default `chromium` / `firefox` / `webkit` projects ignore
`tests/e2e/**`, so the regular unit-style Playwright runs stay fast
and don't require any backend.
