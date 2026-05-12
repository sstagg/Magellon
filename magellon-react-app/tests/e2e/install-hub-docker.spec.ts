/**
 * Drive the plugin install flow via the Upload archive dialog using
 * the locally-packed .mpn files, in docker mode. Captures screenshots
 * at each step.
 *
 * The hub-published .mpn files at demo.magellon.org bundle SDK 2.2.0
 * which is missing magellon_sdk.paths (added 2026-04-30) — installing
 * those via "Browse hub" → docker bootstraps a container that crashes
 * on import. The local pack pipeline (scripts/pack_and_install.ps1)
 * produces a fresh .mpn with SDK 2.4.0 bundled, which is what this
 * spec uploads.
 *
 * Pre-reqs (operator):
 *   - CoreService running with:
 *       MAGELLON_DOCKER_NETWORK=docker_magellon-network
 *       MAGELLON_PLUGIN_BROKER_URL=amqp://rabbit:behd1d2@rabbitmq:5672/
 *   - Frontend dev server on :8080.
 *   - magellon-rabbitmq-container + magellon-nats-container up.
 *   - Locally-packed .mpn files at:
 *       C:\projects\Magellon\plugins\fft-1.1.0.mpn
 *       C:\projects\Magellon\plugins\template-picker-0.1.0.mpn
 *
 * Run:
 *   pnpm exec playwright test --project=e2e-live tests/e2e/install-hub-docker.spec.ts
 */
import { test, expect, Page } from '@playwright/test';
import fs from 'node:fs';
import path from 'node:path';

const FRONTEND = process.env.MAGELLON_E2E_FRONTEND ?? 'http://localhost:8080';
const BACKEND = process.env.MAGELLON_E2E_BACKEND ?? 'http://127.0.0.1:8000';
const USERNAME = process.env.MAGELLON_E2E_USERNAME ?? 'super';
const PASSWORD = process.env.MAGELLON_E2E_PASSWORD ?? 'behd1d2';
const SHOTS_ROOT = path.join(process.cwd(), 'tests', 'e2e', 'screenshots', 'install-hub-docker');

const TARGETS = [
  { pluginId: 'fft',             archive: 'C:\\projects\\Magellon\\plugins\\fft-1.1.0.mpn' },
  { pluginId: 'template-picker', archive: 'C:\\projects\\Magellon\\plugins\\template-picker-0.1.0.mpn' },
];

interface AuthBody { access_token: string; user_id: string; username: string }
interface Installed { plugin_id: string; install_method: string }

const apiFetch = (token: string, url: string, init: RequestInit = {}) => {
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
  if (!res.ok) throw new Error(`login failed: ${res.status} ${await res.text()}`);
  return (await res.json()) as AuthBody;
};

const ensureClean = async (token: string, pluginId: string) => {
  await apiFetch(token, `${BACKEND}/admin/plugins/${pluginId}`, { method: 'DELETE' });
  await expect.poll(async () => {
    const r = await apiFetch(token, `${BACKEND}/admin/plugins/installed`);
    if (!r.ok) return true;
    const b = (await r.json()) as { installed?: Installed[] };
    return !(b.installed ?? []).some(
      (p) => p.plugin_id === pluginId && p.install_method !== 'discovered',
    );
  }, { timeout: 30_000 }).toBeTruthy();
};

const installOne = async (
  page: Page,
  token: string,
  pluginId: string,
  archive: string,
  shotsDir: string,
) => {
  fs.mkdirSync(shotsDir, { recursive: true });
  const shot = async (name: string) => {
    await page.screenshot({ path: path.join(shotsDir, `${name}.png`), fullPage: true });
  };

  expect(fs.existsSync(archive), `local .mpn missing: ${archive}`).toBeTruthy();
  await ensureClean(token, pluginId);

  await page.goto(`${FRONTEND}/en/panel/plugins`, { waitUntil: 'domcontentloaded' });
  await page.waitForLoadState('networkidle').catch(() => {});
  await expect(page.getByRole('heading', { name: 'Plugins' })).toBeVisible({ timeout: 30_000 });
  await shot('01-plugins-page');

  // Open Upload archive dialog
  await page.getByRole('button', { name: /Upload archive/i }).first().click();
  const dialog = page.getByRole('dialog').filter({ hasText: /upload|drop|\.mpn/i }).first();
  await expect(dialog).toBeVisible({ timeout: 15_000 });
  await shot('02-upload-dialog');

  // The dialog uses a hidden file input. setInputFiles bypasses the
  // visual drop-zone and just feeds the file straight in.
  const fileInput = dialog.locator('input[type="file"]').first();
  await fileInput.setInputFiles(archive);
  await shot('03-file-picked');

  // Wait for inspect to populate the method dropdown.
  await expect(dialog.getByLabel(/Install method/i)).toBeVisible({ timeout: 60_000 });
  await shot('04-inspect-ready');

  // Switch method dropdown to docker.
  await dialog.getByLabel(/Install method/i).click();
  await page.getByRole('option', { name: /^docker/i }).click();
  await shot('05-method-docker');

  // Click Install (the dialog's primary button — disambiguate from any
  // other "Install" by binding it to the dialog scope).
  await dialog.getByRole('button', { name: /^Install$/i }).click();
  await shot('06-installing');

  // Wait for success Alert OR error Alert.
  const success = dialog.locator('.MuiAlert-standardSuccess').first();
  const error = dialog.locator('.MuiAlert-standardError').first();
  await Promise.race([
    success.waitFor({ state: 'visible', timeout: 240_000 }),
    error.waitFor({ state: 'visible', timeout: 240_000 }),
  ]).catch(() => {});
  await shot('07-result');

  const succeeded = await success.isVisible().catch(() => false);
  const errText = succeeded ? null : await error.innerText().catch(() => null);

  // Confirm against the backend's source of truth.
  const installedAfter = await (await apiFetch(token, `${BACKEND}/admin/plugins/installed`)).json();
  fs.writeFileSync(
    path.join(shotsDir, 'installed-after.json'),
    JSON.stringify(installedAfter, null, 2),
  );

  // Close the dialog cleanly so the next iteration starts from a known state.
  await dialog.getByRole('button', { name: /Close|Done/i }).first().click().catch(() => {});
  await page.keyboard.press('Escape').catch(() => {});

  return { succeeded, errText, installedAfter };
};

test('install fft + template-picker via docker (local .mpn upload)', async ({ page, context }) => {
  test.setTimeout(20 * 60 * 1000);

  const auth = await login();
  await context.addInitScript(
    ({ token, userId, username }) => {
      localStorage.setItem('access_token', token);
      localStorage.setItem(
        'currentUser',
        JSON.stringify({ id: userId, username, active: true, change_password_required: false }),
      );
      localStorage.setItem('currentUserId', userId);
    },
    { token: auth.access_token, userId: auth.user_id, username: auth.username },
  );

  const network: any[] = [];
  page.on('response', async (res) => {
    const url = res.url();
    if (!url.includes('127.0.0.1:8000')) return;
    const entry: any = { url, status: res.status(), method: res.request().method() };
    if (res.status() >= 400) {
      try { entry.body = (await res.text()).slice(0, 1200); } catch {}
    }
    network.push(entry);
  });

  const summary: Record<string, any> = {};
  for (const t of TARGETS) {
    const shots = path.join(SHOTS_ROOT, t.pluginId);
    console.log(`[install] ${t.pluginId} → docker`);
    summary[t.pluginId] = await installOne(page, auth.access_token, t.pluginId, t.archive, shots);
    fs.writeFileSync(
      path.join(shots, 'network.json'),
      JSON.stringify(network.slice(-30), null, 2),
    );
  }

  fs.mkdirSync(SHOTS_ROOT, { recursive: true });
  fs.writeFileSync(path.join(SHOTS_ROOT, 'summary.json'), JSON.stringify(summary, null, 2));

  // Hard-fail if either failed — at this point everything's tuned.
  for (const [id, r] of Object.entries(summary)) {
    expect((r as any).succeeded, `${id} failed: ${(r as any).errText}`).toBeTruthy();
  }
});
