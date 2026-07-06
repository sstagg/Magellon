/**
 * Install FFT plugin from the hub (docker method), then pause + resume.
 *
 * Sequence:
 *   1. Audit /en/panel/plugins — capture screenshots + DOM hooks so we
 *      know which control opens the hub browser and which submits the
 *      install.
 *   2. Open the hub browser, find FFT, pick docker method, click Install.
 *   3. Wait for install to complete (status → installed, container up).
 *   4. Click Pause on the FFT row.
 *   5. Click Resume.
 *
 * Driven by Playwright. Username super / the shared e2e password.
 */
import { test } from '@playwright/test';
import { E2E_USERNAME, E2E_PASSWORD } from './helpers/credentials';
import fs from 'node:fs';
import path from 'node:path';

const FRONTEND = 'http://localhost:8080';
const BACKEND = 'http://127.0.0.1:8000';
const SHOTS = path.join(process.cwd(), 'tests', 'e2e', 'screenshots', 'install-fft-docker');
fs.mkdirSync(SHOTS, { recursive: true });

const snap = async (page: any, name: string) => {
  await page.screenshot({ path: path.join(SHOTS, `${name}.png`), fullPage: true });
};

test('audit /en/panel/plugins to discover the hub install flow', async ({ page, context }) => {
  test.setTimeout(60_000);
  const consoleErrors: string[] = [];
  const network: any[] = [];
  page.on('console', (m) => { if (m.type() === 'error') consoleErrors.push(m.text()); });
  page.on('response', async (res) => {
    const url = res.url();
    if (!url.includes('127.0.0.1:8000')) return;
    const e: any = { url, status: res.status(), method: res.request().method() };
    if (res.status() >= 400) { try { e.body = (await res.text()).slice(0, 800); } catch {} }
    network.push(e);
  });

  const auth = await (await fetch(`${BACKEND}/auth/login`, {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ username: E2E_USERNAME, password: E2E_PASSWORD }),
  })).json();
  await context.addInitScript(({ token, userId, username }) => {
    localStorage.setItem('access_token', token);
    localStorage.setItem('currentUser', JSON.stringify({ id: userId, username, active: true, change_password_required: false }));
    localStorage.setItem('currentUserId', userId);
  }, { token: auth.access_token, userId: auth.user_id, username: auth.username });

  await page.goto(`${FRONTEND}/en/panel/plugins`, { waitUntil: 'networkidle' }).catch(() => {});
  await page.waitForTimeout(2500);
  await snap(page, '01-plugins-page');

  // Dump body text + button labels so we can see what's clickable.
  const body = await page.locator('body').innerText();
  fs.writeFileSync(path.join(SHOTS, 'body.txt'), body.slice(0, 8000));
  const buttons = await page.locator('button, a[role=button], [role=tab]').evaluateAll(
    (els) => els.map((e: any) => (e.innerText || e.getAttribute('aria-label') || '').trim()).filter(Boolean)
  );
  fs.writeFileSync(path.join(SHOTS, 'buttons.json'), JSON.stringify(buttons.slice(0, 60), null, 2));
  fs.writeFileSync(path.join(SHOTS, 'network.json'), JSON.stringify(network.slice(-30), null, 2));
  fs.writeFileSync(path.join(SHOTS, 'console-errors.txt'), consoleErrors.join('\n'));

  console.log('[buttons]', buttons.slice(0, 30));
  console.log('[console-errors]', consoleErrors.length);
});
