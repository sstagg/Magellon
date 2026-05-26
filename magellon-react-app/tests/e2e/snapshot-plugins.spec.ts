/**
 * Quick one-shot screenshots used to verify the plugins page UX.
 * Captures:
 *   - /en/panel/plugins inventory (08-final-state)
 *   - same with Inactive section expanded (11-inactive-expanded)
 *   - template-picker detail page on the Workspace tab (09-runner-workspace)
 *   - same page after clicking Logs tab (10-runner-logs)
 */
import { test } from '@playwright/test';
import fs from 'node:fs';
import path from 'node:path';

const FRONTEND = 'http://localhost:8080';
const BACKEND = 'http://127.0.0.1:8000';
const SHOTS = path.join(process.cwd(), 'tests', 'e2e', 'screenshots', 'install-hub-docker');
fs.mkdirSync(SHOTS, { recursive: true });

const TEMPLATE_PICKER_PATH = `/en/panel/plugins/${encodeURIComponent('particle_picking/Template Picker')}`;

test('snapshot plugins inventory + runner page tabs', async ({ page, context }) => {
  test.setTimeout(180_000);

  const auth = await (await fetch(`${BACKEND}/auth/login`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ username: 'super', password: 'behd1d2' }),
  })).json();

  await context.addInitScript(({ token, userId, username }: any) => {
    localStorage.setItem('access_token', token);
    localStorage.setItem('currentUser', JSON.stringify({ id: userId, username, active: true, change_password_required: false }));
    localStorage.setItem('currentUserId', userId);
  }, { token: auth.access_token, userId: auth.user_id, username: auth.username });

  // 1. Inventory (default state — Inactive collapsed)
  await page.goto(`${FRONTEND}/en/panel/plugins`, { waitUntil: 'domcontentloaded' });
  await page.waitForLoadState('networkidle').catch(() => {});
  await page.waitForTimeout(5000);
  await page.screenshot({ path: path.join(SHOTS, '08-final-state.png'), fullPage: true });

  // 1b. Inactive section expanded
  const inactiveToggle = page.getByRole('button', { name: /^Inactive \(\d+\)/i }).first();
  if (await inactiveToggle.isVisible().catch(() => false)) {
    await inactiveToggle.click();
    await page.waitForTimeout(800);
    await page.screenshot({ path: path.join(SHOTS, '11-inactive-expanded.png'), fullPage: true });
  }

  // 2. Template-picker runner page — Workspace tab (default)
  await page.goto(`${FRONTEND}${TEMPLATE_PICKER_PATH}`, { waitUntil: 'domcontentloaded' });
  await page.waitForLoadState('networkidle').catch(() => {});
  await page.waitForTimeout(2500);
  await page.screenshot({ path: path.join(SHOTS, '09-runner-workspace.png'), fullPage: true });

  // 3. Switch to Logs tab
  await page.getByRole('tab', { name: /^Logs$/i }).click();
  await page.waitForTimeout(2500);
  await page.screenshot({ path: path.join(SHOTS, '10-runner-logs.png'), fullPage: true });
});
