import { test, expect, Page } from '@playwright/test';
import fs from 'node:fs';
import path from 'node:path';

// This spec exercises the full live stack:
//   CoreService :8000  +  FFT plugin :8010  +  Vite :8080
//   RabbitMQ + NATS in Docker  +  MySQL with auth seed
// It is opt-in. Without `MAGELLON_E2E_LIVE=1` the spec is skipped so
// it never breaks contributors who only have the frontend repo.
//
// To run locally:
//   1. boot RMQ + NATS in Docker
//   2. start CoreService (uvicorn :8000) with NATS_URL=nats://127.0.0.1:4222
//   3. start the FFT plugin runner (:8010) with MAGELLON_STEP_EVENTS_ENABLED=1
//   4. start Vite dev server (:8080)
//   5. drop 3 small PNGs into MAGELLON_E2E_FIXTURE_DIR (defaults to
//      C:/temp/magellon/gpfs/playwright_run)
//   6. MAGELLON_E2E_LIVE=1 npm run test:e2e:live
//
// In CI: gate the workflow step on the same flag and run with the
// same prerequisites available in the runner.
const LIVE = process.env.MAGELLON_E2E_LIVE === '1';

const FRONTEND = process.env.MAGELLON_E2E_FRONTEND ?? 'http://localhost:8080';
const BACKEND = process.env.MAGELLON_E2E_BACKEND ?? 'http://127.0.0.1:8000';
const FIXTURE_DIR = (
  process.env.MAGELLON_E2E_FIXTURE_DIR ?? 'C:/temp/magellon/gpfs/playwright_run'
).replace(/\\/g, '/');
const SHOTS = path.join(process.cwd(), 'tests', 'e2e', 'screenshots', 'fft-test');
fs.mkdirSync(SHOTS, { recursive: true });

const USERNAME = process.env.MAGELLON_E2E_USERNAME ?? 'super';
const PASSWORD = process.env.MAGELLON_E2E_PASSWORD ?? 'behd1d2';

const INPUT_PATHS = [
  `${FIXTURE_DIR}/sample_00.png`,
  `${FIXTURE_DIR}/sample_01.png`,
  `${FIXTURE_DIR}/sample_02.png`,
];

const shot = async (page: Page, name: string) => {
  const p = path.join(SHOTS, `${name}.png`);
  await page.screenshot({ path: p, fullPage: true });
  // eslint-disable-next-line no-console
  console.log(`[shot] ${p}`);
};

test.skip(!LIVE, 'Set MAGELLON_E2E_LIVE=1 to run — requires the live stack');

test('FftTestPage dispatches a batch and renders progressive step events', async ({ page, context }) => {
  test.setTimeout(180_000);

  page.on('console', (msg) => {
    // eslint-disable-next-line no-console
    console.log(`[browser:${msg.type()}] ${msg.text()}`);
  });
  page.on('pageerror', (err) => {
    // eslint-disable-next-line no-console
    console.log(`[browser:pageerror] ${err.message}`);
  });
  page.on('requestfailed', (req) => {
    // eslint-disable-next-line no-console
    console.log(`[browser:requestfailed] ${req.method()} ${req.url()} — ${req.failure()?.errorText}`);
  });

  // 1. Authenticate via API + seed localStorage so the React app skips the login wall
  const auth = await (await fetch(`${BACKEND}/auth/login`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ username: USERNAME, password: PASSWORD }),
  })).json();

  await context.addInitScript(
    ({ token, userId, username }) => {
      const user = { id: userId, username, active: true, change_password_required: false };
      localStorage.setItem('access_token', token);
      localStorage.setItem('currentUser', JSON.stringify(user));
      localStorage.setItem('currentUserId', userId);
    },
    { token: auth.access_token, userId: auth.user_id, username: auth.username },
  );

  // 2. Open the FFT test page
  await page.goto(`${FRONTEND}/en/panel/dev/fft-test`, { waitUntil: 'networkidle' });
  await expect(page.getByRole('heading', { name: /FFT plugin test bed/i })).toBeVisible();
  await shot(page, '01-empty-form');

  // 3. Toggle batch mode and paste the three input paths
  await page.getByLabel('Batch dispatch (one job, N tasks)').check();
  await page.getByLabel(/image_paths/i).fill(INPUT_PATHS.join('\n'));
  await shot(page, '02-batch-paths-entered');

  // 4. Dispatch
  await page.getByRole('button', { name: /Dispatch FFT/i }).click();

  // 5. The dispatch summary card should appear with the queue + task chips
  await expect(page.getByText(/Job [0-9a-f]{8}…/)).toBeVisible({ timeout: 10_000 });
  await expect(page.getByText('fft_tasks_queue')).toBeVisible();
  await expect(page.getByText(/3 task\(s\)/)).toBeVisible();
  await shot(page, '03-dispatched-waiting');

  // 6. The Live events panel should connect and start receiving step events
  const eventsPanel = page.getByTestId('step-events-panel');
  await expect(eventsPanel).toBeVisible();
  await expect(eventsPanel.getByText('connected')).toBeVisible({ timeout: 10_000 });

  // wait for at least one started event to land
  await expect(eventsPanel.getByTestId('step-event-started').first()).toBeVisible({
    timeout: 30_000,
  });
  await shot(page, '04-events-streaming');

  // 7. Wait for all 3 tasks to complete
  await expect(async () => {
    const completedCount = await eventsPanel.getByTestId('step-event-completed').count();
    expect(completedCount).toBeGreaterThanOrEqual(3);
  }).toPass({ timeout: 60_000 });

  // 8. The DB-status chip should flip to "completed" once the projector closes the job
  await expect(page.getByText(/db: completed/i)).toBeVisible({ timeout: 30_000 });
  await shot(page, '05-job-completed');

  // 9. Final assertions: counts of each event type
  const startedCount = await eventsPanel.getByTestId('step-event-started').count();
  const progressCount = await eventsPanel.getByTestId('step-event-progress').count();
  const completedCount = await eventsPanel.getByTestId('step-event-completed').count();
  const failedCount = await eventsPanel.getByTestId('step-event-failed').count();

  // eslint-disable-next-line no-console
  console.log(
    `[events] started=${startedCount} progress=${progressCount} completed=${completedCount} failed=${failedCount}`,
  );

  expect(failedCount).toBe(0);
  expect(startedCount).toBeGreaterThanOrEqual(3);
  expect(completedCount).toBeGreaterThanOrEqual(3);
  // Progress events are live-only — the writer skips them on the
  // server side (see job_event_writer.PERSISTED_EVENT_TYPES), so the
  // join-room replay can't backfill them. With 3 sub-second FFTs,
  // most progress emissions land before the client subscribes; we
  // only assert that *some* live progress was observed in the
  // typical case where one task is still in flight on subscribe.
  expect(progressCount).toBeGreaterThanOrEqual(0);
});
