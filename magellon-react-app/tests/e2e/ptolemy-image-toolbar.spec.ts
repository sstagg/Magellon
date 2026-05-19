import { expect, test } from '@playwright/test';

const FRONTEND = process.env.MAGELLON_FRONTEND ?? 'http://localhost:8080';
const BACKEND = process.env.MAGELLON_BACKEND ?? 'http://127.0.0.1:8000';

interface AuthBody {
  access_token: string;
  user_id: string;
  username: string;
}

async function login(): Promise<AuthBody> {
  const res = await fetch(`${BACKEND}/auth/login`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ username: 'super', password: 'behd1d2' }),
  });
  if (!res.ok) throw new Error(`login failed: ${res.status} ${await res.text()}`);
  return res.json();
}

async function injectAuth(context: any, auth: AuthBody) {
  await context.addInitScript(
    ({ access_token, user_id, username }: AuthBody) => {
      localStorage.setItem('access_token', access_token);
      localStorage.setItem('currentUser', JSON.stringify({
        id: user_id,
        username,
        active: true,
        change_password_required: false,
      }));
      localStorage.setItem('currentUserId', user_id);
    },
    auth,
  );
}

test('image tab exposes Ptolemy square detection and dispatches current image', async ({ page, context }) => {
  test.skip(process.env.MAGELLON_E2E_LIVE !== '1', 'live Magellon stack required');

  const auth = await login();
  await injectAuth(context, auth);

  let dispatchBody: any = null;
  page.on('request', (request) => {
    if (request.url().includes('/image/ptolemy/square/dispatch')) {
      dispatchBody = request.postDataJSON();
    }
  });

  await page.goto(`${FRONTEND}/en/panel/images`, { waitUntil: 'networkidle' });
  await page.getByRole('combobox').first().click({ timeout: 15_000 });
  await page.getByRole('option', { name: '24DEC03A' }).click();
  await page.getByText('24dec03a_00017gr', { exact: true }).first().click();

  const squareButton = page.getByLabel('Run square detection');
  const holeButton = page.getByLabel('Run hole detection');
  await expect(squareButton).toBeVisible({ timeout: 10_000 });
  await expect(squareButton).toBeEnabled();
  await expect(holeButton).toBeVisible();
  await expect(holeButton).toBeEnabled();

  const responsePromise = page.waitForResponse((response) =>
    response.url().includes('/image/ptolemy/square/dispatch') && response.request().method() === 'POST',
  );
  await squareButton.click();
  const response = await responsePromise;
  expect(response.ok(), await response.text()).toBeTruthy();

  await expect(page.getByText('Square detection dispatched')).toBeVisible({ timeout: 5_000 });
  expect(dispatchBody?.image_path).toBe('/gpfs/home/24dec03a/original/24dec03a_00017gr.mrc');
  expect(dispatchBody?.session_name).toBe('24DEC03A');
  expect(dispatchBody?.image_id).toBeTruthy();
});

test('hole detection button dispatches and toolbar begins polling for job status', async ({ page, context }) => {
  test.skip(process.env.MAGELLON_E2E_LIVE !== '1', 'live Magellon stack required');

  const auth = await login();
  await injectAuth(context, auth);

  let dispatchBody: any = null;
  const jobStatusUrls: string[] = [];

  page.on('request', (request) => {
    if (request.url().includes('/image/ptolemy/hole/dispatch')) {
      dispatchBody = request.postDataJSON();
    }
    if (request.url().includes('/image/jobs/')) {
      jobStatusUrls.push(request.url());
    }
  });

  await page.goto(`${FRONTEND}/en/panel/images`, { waitUntil: 'networkidle' });
  await page.getByRole('combobox').first().click({ timeout: 15_000 });
  await page.getByRole('option', { name: '24DEC03A' }).click();

  // Use a grid-level image (available at first tree level)
  await page.getByText('24dec03a_00034gr', { exact: true }).first().click();

  const holeButton = page.getByLabel('Run hole detection');
  await expect(holeButton).toBeVisible({ timeout: 10_000 });
  await expect(holeButton).toBeEnabled();

  const dispatchResponse = page.waitForResponse((r) =>
    r.url().includes('/image/ptolemy/hole/dispatch') && r.request().method() === 'POST',
  );
  await holeButton.click();
  const resp = await dispatchResponse;
  expect(resp.ok(), await resp.text()).toBeTruthy();

  await expect(page.getByText('Hole detection dispatched')).toBeVisible({ timeout: 5_000 });
  expect(dispatchBody?.image_path).toContain('24dec03a_00034gr');
  expect(dispatchBody?.image_id).toBeTruthy();

  // After dispatch the toolbar starts polling /image/jobs/{job_id}
  await page.waitForTimeout(3_000);
  expect(jobStatusUrls.length).toBeGreaterThan(0);
  expect(jobStatusUrls[0]).toMatch(/\/image\/jobs\/[0-9a-f-]+$/);
});

test('square detection dispatches for grid images and shows running chip', async ({ page, context }) => {
  test.skip(process.env.MAGELLON_E2E_LIVE !== '1', 'live Magellon stack required');

  const auth = await login();
  await injectAuth(context, auth);

  await page.goto(`${FRONTEND}/en/panel/images`, { waitUntil: 'networkidle' });
  await page.getByRole('combobox').first().click({ timeout: 15_000 });
  await page.getByRole('option', { name: '24DEC03A' }).click();
  await page.getByText('24dec03a_00034gr', { exact: true }).first().click();

  const squareButton = page.getByLabel('Run square detection');
  await expect(squareButton).toBeVisible({ timeout: 10_000 });

  const dispatchResponse = page.waitForResponse((r) =>
    r.url().includes('/image/ptolemy/square/dispatch') && r.request().method() === 'POST',
  );
  await squareButton.click();
  await dispatchResponse;

  // The chip should show category + "running…" while polling
  await expect(page.getByText('SquareDetection running…')).toBeVisible({ timeout: 5_000 });
});

test('job status endpoint returns status for a dispatched job', async ({ request: apiRequest }) => {
  test.skip(process.env.MAGELLON_E2E_LIVE !== '1', 'live Magellon stack required');

  // Get a token
  const loginResp = await apiRequest.post(`${BACKEND}/auth/login`, {
    data: { username: 'super', password: 'behd1d2' },
  });
  const { access_token } = await loginResp.json();

  // Dispatch a square detection to get a real job_id
  const dispatchResp = await apiRequest.post(`${BACKEND}/image/ptolemy/square/dispatch`, {
    headers: { Authorization: `Bearer ${access_token}` },
    data: {
      image_path: '/gpfs/home/24dec03a/original/24dec03a_00034gr.mrc',
      session_name: '24DEC03A',
    },
  });
  expect(dispatchResp.ok()).toBeTruthy();
  const { job_id } = await dispatchResp.json();
  expect(job_id).toBeTruthy();

  // Immediately poll status — should be queued or running
  const statusResp = await apiRequest.get(`${BACKEND}/image/jobs/${job_id}`, {
    headers: { Authorization: `Bearer ${access_token}` },
  });
  expect(statusResp.ok()).toBeTruthy();
  const status = await statusResp.json();
  expect(status.job_id).toBe(job_id);
  expect(['queued', 'running', 'completed', 'failed']).toContain(status.status);
});
