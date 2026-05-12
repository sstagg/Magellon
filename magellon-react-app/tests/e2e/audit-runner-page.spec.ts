/**
 * Audit /en/panel/plugins/{category}/{plugin_id} across states.
 * Captures the runner page at wide + narrow viewports, Workspace
 * + Logs tabs, with the plugin running and stopped, so we can spot
 * UX/functionality gaps.
 *
 * Run:
 *   pnpm exec playwright test --project=e2e-live tests/e2e/audit-runner-page.spec.ts
 */
import { test, type Page } from '@playwright/test';
import fs from 'node:fs';
import path from 'node:path';

const FRONTEND = 'http://localhost:8080';
const BACKEND = 'http://127.0.0.1:8000';
const SHOTS = path.join(process.cwd(), 'tests', 'e2e', 'screenshots', 'audit-runner-page');
fs.mkdirSync(SHOTS, { recursive: true });

const TEMPLATE_PICKER = encodeURI(
  '/en/panel/plugins/particle_picking/Template Picker — particle picking',
);
const FFT_PAGE = encodeURI(
  '/en/panel/plugins/fft/FFT — magnitude spectrum',
);

async function auth(context: any) {
  const a = await (await fetch(`${BACKEND}/auth/login`, {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ username: 'super', password: 'behd1d2' }),
  })).json();
  await context.addInitScript(({ token, userId, username }: any) => {
    localStorage.setItem('access_token', token);
    localStorage.setItem('currentUser', JSON.stringify({ id: userId, username, active: true, change_password_required: false }));
    localStorage.setItem('currentUserId', userId);
  }, { token: a.access_token, userId: a.user_id, username: a.username });
}

test('audit runner page', async ({ page, context }) => {
  test.setTimeout(180_000);
  await auth(context);
  const network: any[] = [];
  const consoleErrors: string[] = [];
  page.on('console', (m) => { if (m.type() === 'error') consoleErrors.push(m.text()); });
  page.on('response', async (res) => {
    const u = res.url();
    if (!u.includes('127.0.0.1:8000')) return;
    const entry: any = { url: u, status: res.status(), method: res.request().method() };
    if (res.status() >= 400) { try { entry.body = (await res.text()).slice(0, 600); } catch {} }
    network.push(entry);
  });

  // 01 — Template picker, wide viewport, Workspace tab (default)
  await page.setViewportSize({ width: 1440, height: 900 });
  await page.goto(`${FRONTEND}${TEMPLATE_PICKER}`, { waitUntil: 'domcontentloaded' });
  await page.waitForLoadState('networkidle').catch(() => {});
  await page.waitForTimeout(3000);
  await page.screenshot({ path: path.join(SHOTS, '01-runner-workspace-wide.png'), fullPage: true });

  // 02 — Logs tab
  await page.getByRole('tab', { name: /^Logs$/i }).click();
  await page.waitForTimeout(3000);
  await page.screenshot({ path: path.join(SHOTS, '02-runner-logs-wide.png'), fullPage: true });

  // 03 — Same page but narrow viewport (tablet)
  await page.setViewportSize({ width: 820, height: 1180 });
  await page.reload({ waitUntil: 'domcontentloaded' });
  await page.waitForTimeout(2500);
  await page.screenshot({ path: path.join(SHOTS, '03-runner-narrow.png'), fullPage: true });

  // 04 — Mobile viewport
  await page.setViewportSize({ width: 414, height: 900 });
  await page.reload({ waitUntil: 'domcontentloaded' });
  await page.waitForTimeout(2500);
  await page.screenshot({ path: path.join(SHOTS, '04-runner-mobile.png'), fullPage: true });

  // 05 — FFT page (different category, single sync method) at wide
  await page.setViewportSize({ width: 1440, height: 900 });
  await page.goto(`${FRONTEND}${FFT_PAGE}`, { waitUntil: 'domcontentloaded' });
  await page.waitForTimeout(2500);
  await page.screenshot({ path: path.join(SHOTS, '05-fft-runner.png'), fullPage: true });

  // Snapshot every clickable to find dead controls / unlabeled icons
  const controls = await page.locator('button, a[role=button], [role=tab]').evaluateAll(
    (els) => els.map((e: any) => ({
      label: (e.innerText || e.getAttribute('aria-label') || '').trim().slice(0, 80),
      title: e.getAttribute('title') ?? null,
      disabled: e.hasAttribute('disabled'),
    })).filter((x: any) => x.label || x.title),
  );
  fs.writeFileSync(path.join(SHOTS, 'controls.json'), JSON.stringify(controls, null, 2));
  fs.writeFileSync(path.join(SHOTS, 'network.json'), JSON.stringify(network.slice(-80), null, 2));
  fs.writeFileSync(path.join(SHOTS, 'console-errors.txt'), consoleErrors.join('\n'));
});
