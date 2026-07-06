import { test } from '@playwright/test';
import { E2E_USERNAME, E2E_PASSWORD } from '../e2e/helpers/credentials';
import fs from 'node:fs';
import path from 'node:path';

const FRONTEND = 'http://localhost:8080';
const BACKEND  = 'http://127.0.0.1:8000';
const SHOTS = path.join(process.cwd(), 'tests', 'e2e', 'screenshots', 'topaz-dispatch');
fs.mkdirSync(SHOTS, { recursive: true });

test('diagnose topaz dispatch flow', async ({ page, context }) => {
  test.setTimeout(180_000);

  const networkLog: any[] = [];
  const consoleErrors: string[] = [];

  page.on('console', m => { if (m.type() === 'error') consoleErrors.push(m.text()); });
  page.on('pageerror', e => consoleErrors.push(String(e)));
  page.on('response', async res => {
    const url = res.url();
    if (!url.includes('8000')) return;
    const entry: any = { url, status: res.status(), method: res.request().method() };
    if (res.status() >= 300) {
      try { entry.body = (await res.text()).slice(0, 2000); } catch {}
    }
    networkLog.push(entry);
    if (url.includes('/dispatch') || url.includes('/backends') || url.includes('/particle')) {
      console.log(`[NET] ${entry.method} ${url} → ${entry.status}`, entry.body ?? '');
    }
  });

  // Login
  const auth = await (await fetch(`${BACKEND}/auth/login`, {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ username: E2E_USERNAME, password: E2E_PASSWORD }),
  })).json();
  console.log('[AUTH]', auth.user_id ? 'ok' : 'FAILED', auth);

  await context.addInitScript(
    ({ token, userId, username }) => {
      localStorage.setItem('access_token', token);
      localStorage.setItem('currentUser', JSON.stringify({ id: userId, username, active: true, change_password_required: false }));
      localStorage.setItem('currentUserId', userId);
    },
    { token: auth.access_token, userId: auth.user_id, username: auth.username },
  );

  // Test dispatch directly with auth token
  const dispatchTest = await fetch(`${BACKEND}/particle-picking/dispatch`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${auth.access_token}` },
    body: JSON.stringify({
      image_path: 'test.mrc',
      target_backend: 'topaz-particle-picking',
      ipp_name: 'test-dispatch',
    }),
  });
  console.log('[DISPATCH-TEST] status:', dispatchTest.status, await dispatchTest.text());

  // Check backends
  const backends = await fetch(`${BACKEND}/particle-picking/backends`).then(r => r.json());
  console.log('[BACKENDS]', JSON.stringify(backends));

  // Navigate to images page
  await page.goto(`${FRONTEND}/en/panel/images`, { waitUntil: 'networkidle', timeout: 30_000 }).catch(() => {});
  await page.waitForTimeout(2000);
  await page.screenshot({ path: path.join(SHOTS, '01-images-page.png'), fullPage: true });

  // Click an image from the left panel (first thumbnail or list item)
  const imageCandidates = await page.locator('[data-testid="image-item"], .image-item, img[src*="thumbnail"], img[src*="image"]').all();
  console.log('[IMAGES] found', imageCandidates.length, 'candidates');

  if (imageCandidates.length > 0) {
    await imageCandidates[0].click({ timeout: 5000 }).catch(() => {});
    await page.waitForTimeout(2000);
    await page.screenshot({ path: path.join(SHOTS, '02-image-selected.png'), fullPage: true });
  }

  // Find and click "Particle Picking" tab
  const ppTab = page.locator('button, [role="tab"]').filter({ hasText: /particle.?picking/i }).first();
  if (await ppTab.count() > 0) {
    await ppTab.click({ timeout: 5000 }).catch(() => {});
    await page.waitForTimeout(2000);
    await page.screenshot({ path: path.join(SHOTS, '03-pp-tab.png'), fullPage: true });
  }

  // Find and click the Settings button (gear/tune icon)
  const settingsBtn = page.locator('button').filter({ hasText: /settings|tune/i }).first();
  const altSettingsBtn = page.locator('[aria-label*="settings" i], [title*="settings" i], [data-testid*="settings"]').first();
  const tuneBtn = page.locator('button svg[data-testid="TuneIcon"]').first();

  for (const btn of [settingsBtn, altSettingsBtn, tuneBtn]) {
    if (await btn.count() > 0) {
      await btn.click({ timeout: 3000 }).catch(() => {});
      await page.waitForTimeout(1500);
      await page.screenshot({ path: path.join(SHOTS, '04-settings-open.png'), fullPage: true });
      break;
    }
  }

  // Find the backend selector dropdown
  const backendSelect = page.locator('select, [role="combobox"]').first();
  const _topazOption = page.locator('[role="option"]').filter({ hasText: /topaz/i }).first();
  console.log('[BACKEND-SELECT] found:', await backendSelect.count(), 'selects');

  // Take screenshot of current drawer state
  await page.screenshot({ path: path.join(SHOTS, '05-drawer-state.png'), fullPage: true });

  // Find and click the Run button
  const runBtn = page.locator('button').filter({ hasText: /run on image|run$/i }).first();
  console.log('[RUN-BTN] found:', await runBtn.count());
  if (await runBtn.count() > 0) {
    await runBtn.click({ timeout: 5000 }).catch(e => console.log('[RUN-BTN] click error:', e));
    await page.waitForTimeout(3000);
    await page.screenshot({ path: path.join(SHOTS, '06-after-run.png'), fullPage: true });
  }

  // Wait and check for dispatch call
  await page.waitForTimeout(5000);
  await page.screenshot({ path: path.join(SHOTS, '07-after-wait.png'), fullPage: true });

  // Capture canvas state
  const canvas = page.locator('canvas').first();
  if (await canvas.count() > 0) {
    console.log('[CANVAS] found canvas element');
    await canvas.screenshot({ path: path.join(SHOTS, '08-canvas.png') }).catch(() => {});
  }

  // Write full report
  const report = { auth: { user_id: auth.user_id, ok: !!auth.access_token }, backends, networkLog, consoleErrors };
  fs.writeFileSync(path.join(SHOTS, 'report.json'), JSON.stringify(report, null, 2));

  console.log('[CONSOLE ERRORS]', consoleErrors);
  console.log('[NETWORK dispatch calls]', networkLog.filter(e => e.url.includes('dispatch')));
  console.log('[NETWORK particle calls]', networkLog.filter(e => e.url.includes('particle')));
});
