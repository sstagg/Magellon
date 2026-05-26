/**
 * Plugin installer E2E tests — covers the AdminInstalledPanel and the
 * /admin/plugins/* endpoints it is backed by.
 *
 * What is tested without a live .mpn archive:
 *   1. Page structure  — drop-zone renders, refresh button is present,
 *      installed-list area appears (empty state or rows).
 *   2. File-type gate  — selecting a non-.mpn file produces the inline
 *      validation error ("Expected a .mpn archive").
 *   3. API 200/403 ping — GET /admin/plugins/installed returns 200 for
 *      Administrators; non-admin would get 403 (role pinned here).
 *   4. Process-control buttons — for each installed plugin the row must
 *      show both Upgrade and Uninstall buttons.
 *   5. Inspect endpoint smoke — POST /admin/plugins/inspect with a bad
 *      archive returns a 4xx (not a 500 crash).
 *
 * Run with the live stack:
 *   pnpm exec playwright test --project=e2e-live tests/e2e/plugin-installer.spec.ts
 */
import { test, expect } from '@playwright/test';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';

const FRONTEND = 'http://localhost:8080';
const BACKEND = 'http://127.0.0.1:8000';
const SHOTS = path.join(process.cwd(), 'tests', 'e2e', 'screenshots', 'plugin-installer');
fs.mkdirSync(SHOTS, { recursive: true });

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

async function login(context: any): Promise<string> {
  const auth = await (await fetch(`${BACKEND}/auth/login`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ username: 'super', password: 'behd1d2' }),
  })).json();
  await context.addInitScript(({ token, userId, username }: any) => {
    localStorage.setItem('access_token', token);
    localStorage.setItem('currentUser', JSON.stringify({
      id: userId, username, active: true, change_password_required: false,
    }));
    localStorage.setItem('currentUserId', userId);
  }, { token: auth.access_token, userId: auth.user_id, username: auth.username });
  return auth.access_token as string;
}

// Creates a small temp file with the given name + content for setInputFiles.
function tmpFile(name: string, content: string): string {
  const p = path.join(os.tmpdir(), name);
  fs.writeFileSync(p, content, 'utf8');
  return p;
}

// ---------------------------------------------------------------------------
// 1. Structure audit — the AdminInstalledPanel renders correctly
// ---------------------------------------------------------------------------

test('plugin installer — page structure renders', async ({ page, context }) => {
  test.setTimeout(90_000);
  await login(context);
  const consoleErrors: string[] = [];
  const network: any[] = [];
  page.on('console', (m) => { if (m.type() === 'error') consoleErrors.push(m.text()); });
  page.on('response', async (res) => {
    const u = res.url();
    if (!u.includes('127.0.0.1:8000')) return;
    const e: any = { url: u, status: res.status(), method: res.request().method() };
    if (res.status() >= 400) { try { e.body = (await res.text()).slice(0, 600); } catch {} }
    network.push(e);
  });

  await page.goto(`${FRONTEND}/en/panel/plugins`, { waitUntil: 'domcontentloaded' });
  await page.waitForLoadState('networkidle').catch(() => {});
  await page.waitForTimeout(3000);
  await page.screenshot({ path: path.join(SHOTS, '01-plugins-installed-tab.png'), fullPage: true });

  // Installed tab should be the default.
  const installedTab = page.getByRole('tab', { name: /^Installed$/i });
  await expect(installedTab).toBeVisible();
  await expect(installedTab).toHaveAttribute('aria-selected', 'true');

  // Drop zone must be present (aria-label defined in the component).
  const dropZone = page.getByRole('button', { name: /Drop or browse for a .mpn archive/i });
  await expect(dropZone).toBeVisible();

  // Refresh icon button.
  const refreshBtn = page.getByRole('button', { name: /refresh/i });
  await expect(refreshBtn).toBeVisible();

  // "Admin install" heading.
  await expect(page.getByText('Admin install')).toBeVisible();

  // The installed-list section renders — either entries or an info alert.
  const listOrEmpty = page.locator('[role=alert][class*=MuiAlert-standard], [data-installed-row]');
  await expect(listOrEmpty.first()).toBeVisible();
  // At minimum, no blank white screen.
  const bodyLen = (await page.locator('body').innerText()).trim().length;
  expect(bodyLen, 'Body is empty').toBeGreaterThan(50);

  fs.writeFileSync(path.join(SHOTS, '01-console-errors.txt'), consoleErrors.join('\n'));
  fs.writeFileSync(path.join(SHOTS, '01-network.json'), JSON.stringify(network.slice(-30), null, 2));
});

// ---------------------------------------------------------------------------
// 2. File-type gate — non-.mpn triggers inline validation error
// ---------------------------------------------------------------------------

test('plugin installer — non-mpn file is rejected with inline error', async ({ page, context }) => {
  test.setTimeout(60_000);
  await login(context);

  await page.goto(`${FRONTEND}/en/panel/plugins`, { waitUntil: 'domcontentloaded' });
  await page.waitForLoadState('networkidle').catch(() => {});
  await page.waitForTimeout(2500);

  // Reveal the hidden file input by bypassing the click handler.
  const txtPath = tmpFile('not-a-plugin.txt', 'this is not an mpn archive');
  await page.locator('input[type="file"][accept=".mpn,.zip"]').setInputFiles(txtPath);
  await page.waitForTimeout(800);
  await page.screenshot({ path: path.join(SHOTS, '02-file-type-rejected.png'), fullPage: true });

  // The component renders an MUI Alert with the rejection message.
  const errorAlert = page.getByText(/Expected a \.mpn archive/i);
  await expect(errorAlert).toBeVisible();

  // No Install button should appear — the bad file is not staged.
  const installBtn = page.locator('button:has-text("Install")');
  await expect(installBtn).not.toBeVisible();

  fs.unlinkSync(txtPath);
});

// ---------------------------------------------------------------------------
// 3. API ping — GET /admin/plugins/installed returns 200 for the super user
// ---------------------------------------------------------------------------

test('plugin installer — GET /admin/plugins/installed returns 200', async ({ context }) => {
  test.setTimeout(30_000);
  const token = await login(context as any);

  const resp = await fetch(`${BACKEND}/admin/plugins/installed`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  expect(resp.status, `Expected 200 from /admin/plugins/installed, got ${resp.status}`).toBe(200);

  const body = await resp.json();
  // Response shape: { installed: [...] }
  expect(Array.isArray(body.installed), 'installed field is an array').toBe(true);
  fs.writeFileSync(
    path.join(SHOTS, '03-installed-api.json'),
    JSON.stringify(body, null, 2),
  );
});

// ---------------------------------------------------------------------------
// 4. Process-control buttons — every installed row has Upgrade + Uninstall
// ---------------------------------------------------------------------------

test('plugin installer — installed rows expose Upgrade and Uninstall buttons', async ({ page, context }) => {
  test.setTimeout(60_000);
  const token = await login(context);

  // First check if any plugins are installed.
  const listResp = await fetch(`${BACKEND}/admin/plugins/installed`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  const listBody = await listResp.json();
  if (!listBody.installed || listBody.installed.length === 0) {
    test.skip(false, 'No plugins installed — skip process-control button check');
    return;
  }

  await page.goto(`${FRONTEND}/en/panel/plugins`, { waitUntil: 'domcontentloaded' });
  await page.waitForLoadState('networkidle').catch(() => {});
  await page.waitForTimeout(3000);
  await page.screenshot({ path: path.join(SHOTS, '04-installed-rows.png'), fullPage: true });

  // Each installed plugin row must have an Upgrade and an Uninstall button.
  const upgradeButtons = await page.locator('button:has-text("Upgrade")').count();
  const uninstallButtons = await page.locator('button:has-text("Uninstall")').count();
  const pluginCount = listBody.installed.length;

  expect(upgradeButtons, `Expected ${pluginCount} Upgrade buttons`).toBe(pluginCount);
  expect(uninstallButtons, `Expected ${pluginCount} Uninstall buttons`).toBe(pluginCount);
});

// ---------------------------------------------------------------------------
// 5. Inspect endpoint smoke — bad zip returns 4xx not 500
// ---------------------------------------------------------------------------

test('plugin installer — POST /admin/plugins/inspect with corrupt archive returns 4xx', async ({ context }) => {
  test.setTimeout(30_000);
  const token = await login(context as any);

  // Create a tiny file that is not a valid zip.
  const badPath = tmpFile('corrupt.mpn', 'NOT A REAL ZIP HEADER');
  const fileBytes = fs.readFileSync(badPath);
  const blob = new Blob([fileBytes], { type: 'application/octet-stream' });
  const form = new FormData();
  form.append('file', blob, 'corrupt.mpn');

  const resp = await fetch(`${BACKEND}/admin/plugins/inspect`, {
    method: 'POST',
    headers: { Authorization: `Bearer ${token}` },
    body: form,
  });

  // Controller must answer 400 (bad archive), 422 (validation), or similar — NOT 500.
  expect(resp.status, `Inspect with corrupt archive should not be 500`).not.toBe(500);
  expect(resp.status, `Inspect with corrupt archive should be 4xx`).toBeGreaterThanOrEqual(400);
  expect(resp.status, `Inspect with corrupt archive should be 4xx`).toBeLessThan(500);

  const body = await resp.json().catch(() => ({}));
  fs.writeFileSync(path.join(SHOTS, '05-inspect-corrupt.json'), JSON.stringify({ status: resp.status, body }, null, 2));
  fs.unlinkSync(badPath);
});

// ---------------------------------------------------------------------------
// 6. Full viewport sweep — wide + narrow + mobile
// ---------------------------------------------------------------------------

test('plugin installer — responsive layout snapshot', async ({ page, context }) => {
  test.setTimeout(90_000);
  await login(context);

  for (const [name, w, h] of [
    ['wide', 1440, 900],
    ['narrow', 820, 1024],
    ['mobile', 414, 900],
  ] as [string, number, number][]) {
    await page.setViewportSize({ width: w, height: h });
    await page.goto(`${FRONTEND}/en/panel/plugins`, { waitUntil: 'domcontentloaded' });
    await page.waitForLoadState('networkidle').catch(() => {});
    await page.waitForTimeout(2000);
    await page.screenshot({ path: path.join(SHOTS, `06-layout-${name}.png`), fullPage: true });

    // Drop zone must be visible at every breakpoint.
    const dropZone = page.getByRole('button', { name: /Drop or browse/i });
    await expect(dropZone, `Drop zone hidden at ${name} viewport`).toBeVisible();
  }
});
