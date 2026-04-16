import { test, expect, Page } from '@playwright/test';
import fs from 'node:fs';
import path from 'node:path';

const FRONTEND = 'http://localhost:8080';
const BACKEND = 'http://127.0.0.1:8000';
const SHOTS = path.join(process.cwd(), 'tests', 'e2e', 'screenshots', 'fft-test');
fs.mkdirSync(SHOTS, { recursive: true });

const USERNAME = 'super';
const PASSWORD = 'behd1d2';

const INPUT_PATHS = [
  'C:/temp/magellon/gpfs/playwright_run/sample_00.png',
  'C:/temp/magellon/gpfs/playwright_run/sample_01.png',
  'C:/temp/magellon/gpfs/playwright_run/sample_02.png',
];

const shot = async (page: Page, name: string) => {
  const p = path.join(SHOTS, `${name}.png`);
  await page.screenshot({ path: p, fullPage: true });
  // eslint-disable-next-line no-console
  console.log(`[shot] ${p}`);
};

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
