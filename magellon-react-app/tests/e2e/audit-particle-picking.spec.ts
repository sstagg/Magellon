import { test } from '@playwright/test';
import fs from 'node:fs';
import path from 'node:path';

const FRONTEND = 'http://localhost:8080';
const BACKEND = 'http://127.0.0.1:8000';
const SHOTS = path.join(process.cwd(), 'tests', 'e2e', 'screenshots', 'particle-picking-audit');
fs.mkdirSync(SHOTS, { recursive: true });

test('audit particle picking page', async ({ page, context }) => {
  test.setTimeout(120_000);
  const consoleErrors: string[] = [];
  const pageErrors: string[] = [];
  const network: any[] = [];
  page.on('console', (m) => { if (m.type() === 'error') consoleErrors.push(m.text()); });
  page.on('pageerror', (e) => pageErrors.push(String(e)));
  page.on('response', async (res) => {
    const url = res.url();
    if (!url.includes('127.0.0.1:8000') && !url.includes('localhost:8000')) return;
    const e: any = { url, status: res.status(), method: res.request().method() };
    if (res.status() >= 400) { try { e.body = (await res.text()).slice(0, 1500); } catch {} }
    network.push(e);
  });

  const auth = await (await fetch(`${BACKEND}/auth/login`, {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ username: 'super', password: 'behd1d2' }),
  })).json();
  await context.addInitScript(
    ({ token, userId, username }) => {
      localStorage.setItem('access_token', token);
      localStorage.setItem('currentUser', JSON.stringify({ id: userId, username, active: true, change_password_required: false }));
      localStorage.setItem('currentUserId', userId);
    },
    { token: auth.access_token, userId: auth.user_id, username: auth.username },
  );

  const urls = [
    '/en/panel/images',
    '/en/panel/images?tab=particle-picking',
    '/en/panel/images?section=particle-picking',
  ];
  let i = 0;
  for (const u of urls) {
    await page.goto(`${FRONTEND}${u}`, { waitUntil: 'networkidle' }).catch(() => {});
    await page.waitForTimeout(2000);
    await page.screenshot({ path: path.join(SHOTS, `${String(i).padStart(2,'0')}-${u.replace(/[\/?=]/g, '_')}.png`), fullPage: true });
    i++;
  }

  // Try to find a "Particle Picking" nav/tab
  const candidates = await page.locator('button, a, [role="tab"], [role="menuitem"]').filter({ hasText: /particle picking/i }).all();
  console.log('[candidates] found', candidates.length);
  for (let j = 0; j < Math.min(candidates.length, 3); j++) {
    try {
      await candidates[j].scrollIntoViewIfNeeded();
      await candidates[j].click({ timeout: 4000 });
      await page.waitForTimeout(2000);
      await page.screenshot({ path: path.join(SHOTS, `tab-${j}.png`), fullPage: true });
    } catch (e) { console.log('click fail', e); }
  }

  // Also try to open an image session if one exists in left panel
  fs.writeFileSync(path.join(SHOTS, 'audit-report.json'), JSON.stringify({ consoleErrors, pageErrors, network: network.slice(-80) }, null, 2));
  console.log('[console errors]', consoleErrors.slice(0, 20));
  console.log('[page errors]', pageErrors);
});
