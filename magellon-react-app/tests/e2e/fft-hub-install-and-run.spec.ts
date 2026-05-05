import { test, expect, Page } from '@playwright/test';
import fs from 'node:fs';
import path from 'node:path';

const LIVE = process.env.MAGELLON_E2E_LIVE === '1';
const HUB_INSTALL = process.env.MAGELLON_E2E_HUB_INSTALL === '1';

const FRONTEND = process.env.MAGELLON_E2E_FRONTEND ?? 'http://localhost:8080';
const BACKEND = process.env.MAGELLON_E2E_BACKEND ?? 'http://127.0.0.1:8000';
const USERNAME = process.env.MAGELLON_E2E_USERNAME ?? 'super';
const PASSWORD = process.env.MAGELLON_E2E_PASSWORD ?? 'behd1d2';
const INPUT_FILE = (
  process.env.MAGELLON_E2E_FFT_INPUT ??
  'C:/magellon/gpfs/24dec03a_00031gr_00002sq_v01_00002hl_00001fc.mrc'
).replace(/\\/g, '/');
const SHOTS = path.join(process.cwd(), 'tests', 'e2e', 'screenshots', 'fft-hub-install-and-run');

fs.mkdirSync(SHOTS, { recursive: true });

test.skip(!LIVE, 'Set MAGELLON_E2E_LIVE=1 to run against the live stack');
test.skip(
  !HUB_INSTALL,
  'Set MAGELLON_E2E_HUB_INSTALL=1 to allow downloading and installing the FFT plugin from the public hub',
);
test.skip(!fs.existsSync(INPUT_FILE), `FFT input fixture is missing: ${INPUT_FILE}`);

type AuthBody = {
  access_token: string;
  user_id: string;
  username: string;
};

type Condition = {
  type: string;
  status: string;
};

const shot = async (page: Page, name: string) => {
  const p = path.join(SHOTS, `${name}.png`);
  await page.screenshot({ path: p, fullPage: true });
  // eslint-disable-next-line no-console
  console.log(`[shot] ${p}`);
};

const apiFetch = async (
  token: string,
  url: string,
  init: RequestInit = {},
) => {
  const headers = new Headers(init.headers);
  headers.set('Authorization', `Bearer ${token}`);
  return fetch(url, { ...init, headers });
};

const login = async (): Promise<AuthBody> => {
  const res = await fetch(`${BACKEND}/auth/login`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ username: USERNAME, password: PASSWORD }),
  });
  if (!res.ok) {
    throw new Error(`login failed: ${res.status} ${await res.text()}`);
  }
  return (await res.json()) as AuthBody;
};

const uninstallFftIfPresent = async (token: string) => {
  const installed = await apiFetch(token, `${BACKEND}/admin/plugins/installed`);
  if (!installed.ok) {
    throw new Error(`installed-list failed: ${installed.status} ${await installed.text()}`);
  }
  const body = await installed.json() as { installed?: { plugin_id: string }[] };
  if (!body.installed?.some((p) => p.plugin_id === 'fft')) return;

  const res = await apiFetch(token, `${BACKEND}/admin/plugins/fft`, { method: 'DELETE' });
  if (!res.ok && res.status !== 404) {
    throw new Error(`pre-test uninstall failed: ${res.status} ${await res.text()}`);
  }

  await expect.poll(async () => {
    const after = await apiFetch(token, `${BACKEND}/admin/plugins/installed`);
    if (!after.ok) return true;
    const afterBody = await after.json() as { installed?: { plugin_id: string }[] };
    return !(afterBody.installed ?? []).some((p) => p.plugin_id === 'fft');
  }, { timeout: 30_000 }).toBeTruthy();
};

const waitForFftLive = async (token: string) => {
  await expect.poll(async () => {
    const res = await apiFetch(token, `${BACKEND}/plugins/fft/status`);
    if (!res.ok) return false;
    const conditions = await res.json() as Condition[];
    return conditions.some((c) => c.type === 'Live' && c.status === 'True');
  }, {
    timeout: 180_000,
    message: 'FFT plugin should announce on the bus after hub install',
  }).toBeTruthy();
};

test('install FFT from hub and run one GPFS-backed FFT', async ({ page, context }) => {
  test.setTimeout(600_000);

  const auth = await login();
  await uninstallFftIfPresent(auth.access_token);

  await context.addInitScript(
    ({ token, userId, username }) => {
      localStorage.setItem('access_token', token);
      localStorage.setItem('currentUser', JSON.stringify({
        id: userId,
        username,
        active: true,
        change_password_required: false,
      }));
      localStorage.setItem('currentUserId', userId);
    },
    { token: auth.access_token, userId: auth.user_id, username: auth.username },
  );

  await page.goto(`${FRONTEND}/en/panel/plugins`, { waitUntil: 'networkidle' });
  await expect(page.getByRole('heading', { name: 'Plugins' })).toBeVisible();
  await shot(page, '01-plugins-page');

  await page.getByRole('button', { name: /Browse hub/i }).first().click();
  const hubDialog = page.getByRole('dialog', { name: /Browse plugin hub/i });
  await expect(hubDialog).toBeVisible();
  await hubDialog.getByPlaceholder(/Search name/i).fill('fft');

  const fftCard = hubDialog.locator('.MuiCard-root').filter({ hasText: /fft/i }).first();
  await expect(fftCard).toBeVisible({ timeout: 60_000 });
  await shot(page, '02-hub-filtered-fft');
  await fftCard.getByRole('button', { name: /^Install$/i }).click();

  const installDialog = page.getByRole('dialog').filter({ hasText: /plugin_id/i }).last();
  await expect(installDialog.getByLabel(/Install method/i)).toBeVisible({ timeout: 180_000 });
  await shot(page, '03-install-ready');
  await installDialog.getByRole('button', { name: /^Install$/i }).click();
  await expect(installDialog.getByText(/fft installed/i)).toBeVisible({ timeout: 300_000 });
  await shot(page, '04-installed');
  await installDialog.getByRole('button', { name: /^Close$/i }).click();

  await waitForFftLive(auth.access_token);

  const stem = path.basename(INPUT_FILE, path.extname(INPUT_FILE));
  const expectedOutput = path.join(path.dirname(INPUT_FILE), `${stem}_FFT.png`);
  const beforeMtime = fs.existsSync(expectedOutput)
    ? fs.statSync(expectedOutput).mtimeMs
    : 0;

  await page.goto(`${FRONTEND}/en/panel/dev/fft-test`, { waitUntil: 'networkidle' });
  await expect(page.getByRole('heading', { name: /FFT plugin test bed/i })).toBeVisible();
  await page.getByLabel(/image_path/i).fill(INPUT_FILE);
  await shot(page, '05-fft-input');
  await page.getByRole('button', { name: /^Dispatch FFT$/i }).click();

  await expect(page.getByText(/1 task\(s\)/)).toBeVisible({ timeout: 15_000 });
  await expect(page.getByText(/db: completed/i)).toBeVisible({ timeout: 180_000 });
  await shot(page, '06-fft-completed');

  await expect.poll(() => {
    if (!fs.existsSync(expectedOutput)) return false;
    const stat = fs.statSync(expectedOutput);
    return stat.size > 0 && stat.mtimeMs >= beforeMtime;
  }, {
    timeout: 30_000,
    message: `FFT output should be written under GPFS: ${expectedOutput}`,
  }).toBeTruthy();
});
