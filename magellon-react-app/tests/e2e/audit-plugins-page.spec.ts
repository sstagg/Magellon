/**
 * Audit /en/panel/plugins across the states an operator actually
 * sees in a day. Captures full-page screenshots + DOM hooks + console
 * errors + slow API responses so we can spot UX/functionality gaps.
 *
 * Run:
 *   pnpm exec playwright test --project=e2e-live tests/e2e/audit-plugins-page.spec.ts
 */
import { test, type Page } from '@playwright/test';
import { E2E_USERNAME, E2E_PASSWORD } from './helpers/credentials';
import fs from 'node:fs';
import path from 'node:path';

const FRONTEND = 'http://localhost:8080';
const BACKEND = 'http://127.0.0.1:8000';
const SHOTS = path.join(process.cwd(), 'tests', 'e2e', 'screenshots', 'audit-plugins-page');
fs.mkdirSync(SHOTS, { recursive: true });

const TEMPLATE_PICKER_PATH = `/en/panel/plugins/${encodeURIComponent('particle_picking/Template Picker')}`;

async function authLocalStorage(context: any) {
  const auth = await (await fetch(`${BACKEND}/auth/login`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ username: E2E_USERNAME, password: E2E_PASSWORD }),
  })).json();
  await context.addInitScript(({ token, userId, username }: any) => {
    localStorage.setItem('access_token', token);
    localStorage.setItem('currentUser', JSON.stringify({ id: userId, username, active: true, change_password_required: false }));
    localStorage.setItem('currentUserId', userId);
  }, { token: auth.access_token, userId: auth.user_id, username: auth.username });
}

const recordPage = (page: Page, network: any[], consoleErrors: string[]) => {
  page.on('console', (m) => { if (m.type() === 'error') consoleErrors.push(m.text()); });
  page.on('response', async (res) => {
    const u = res.url();
    if (!u.includes('127.0.0.1:8000')) return;
    const _ms = (res as any).request?.()?.timing?.()?.responseEnd ?? null;
    const entry: any = { url: u, status: res.status(), method: res.request().method() };
    if (res.status() >= 400) { try { entry.body = (await res.text()).slice(0, 600); } catch {} }
    network.push(entry);
  });
};

test('audit plugins page', async ({ page, context }) => {
  test.setTimeout(240_000);
  await authLocalStorage(context);
  const network: any[] = [];
  const consoleErrors: string[] = [];
  recordPage(page, network, consoleErrors);

  // 01 — inventory page wide viewport
  await page.setViewportSize({ width: 1440, height: 900 });
  await page.goto(`${FRONTEND}/en/panel/plugins`, { waitUntil: 'domcontentloaded' });
  await page.waitForLoadState('networkidle').catch(() => {});
  await page.waitForTimeout(4000);
  await page.screenshot({ path: path.join(SHOTS, '01-inventory-wide.png'), fullPage: true });

  // Capture all clickable controls on the inventory.
  const controls = await page.locator('button, a[role=button], [role=tab]').evaluateAll(
    (els) => els.map((e: any) => ({
      label: (e.innerText || e.getAttribute('aria-label') || '').trim().slice(0, 80),
      title: e.getAttribute('title') ?? null,
      disabled: e.hasAttribute('disabled'),
    })).filter((x: any) => x.label),
  );
  fs.writeFileSync(path.join(SHOTS, '01-buttons.json'), JSON.stringify(controls, null, 2));

  // 02 — Downloaded tab
  await page.getByRole('tab', { name: /^Downloaded$/i }).click();
  await page.waitForTimeout(1500);
  await page.screenshot({ path: path.join(SHOTS, '02-downloaded-tab.png'), fullPage: true });

  // 03 — back to Installed
  await page.getByRole('tab', { name: /^Installed$/i }).click();
  await page.waitForTimeout(800);

  // 04 — Browse hub modal
  await page.getByRole('button', { name: /Browse hub/i }).first().click();
  await page.waitForTimeout(2500);
  await page.screenshot({ path: path.join(SHOTS, '04-browse-hub.png'), fullPage: true });
  // try a search filter to see how the catalog responds
  const hubDialog = page.getByRole('dialog').filter({ hasText: /hub|catalog|browse/i }).first();
  await hubDialog.getByPlaceholder(/Search name/i).fill('motion');
  await page.waitForTimeout(800);
  await page.screenshot({ path: path.join(SHOTS, '05-browse-hub-search.png'), fullPage: true });
  await page.keyboard.press('Escape');
  await page.waitForTimeout(500);

  // 06 — Upload archive modal (empty state)
  await page.getByRole('button', { name: /Upload archive/i }).first().click();
  await page.waitForTimeout(800);
  await page.screenshot({ path: path.join(SHOTS, '06-upload-empty.png'), fullPage: true });
  await page.keyboard.press('Escape');
  await page.waitForTimeout(500);

  // 07 — Plugin detail page (template-picker), Workspace tab
  await page.goto(`${FRONTEND}${TEMPLATE_PICKER_PATH}`, { waitUntil: 'domcontentloaded' });
  await page.waitForLoadState('networkidle').catch(() => {});
  await page.waitForTimeout(2500);
  await page.screenshot({ path: path.join(SHOTS, '07-runner-workspace.png'), fullPage: true });

  // 08 — Logs tab
  await page.getByRole('tab', { name: /^Logs$/i }).click();
  await page.waitForTimeout(2500);
  await page.screenshot({ path: path.join(SHOTS, '08-runner-logs.png'), fullPage: true });

  // 09 — Narrow viewport (tablet-ish) to spot responsive issues
  await page.setViewportSize({ width: 820, height: 1180 });
  await page.goto(`${FRONTEND}/en/panel/plugins`, { waitUntil: 'domcontentloaded' });
  await page.waitForLoadState('networkidle').catch(() => {});
  await page.waitForTimeout(2500);
  await page.screenshot({ path: path.join(SHOTS, '09-inventory-narrow.png'), fullPage: true });

  // 10 — Tiny viewport (mobile-ish)
  await page.setViewportSize({ width: 414, height: 900 });
  await page.reload({ waitUntil: 'domcontentloaded' });
  await page.waitForTimeout(2500);
  await page.screenshot({ path: path.join(SHOTS, '10-inventory-mobile.png'), fullPage: true });

  fs.writeFileSync(path.join(SHOTS, 'console-errors.txt'), consoleErrors.join('\n'));
  fs.writeFileSync(path.join(SHOTS, 'network.json'), JSON.stringify(network.slice(-80), null, 2));
});
