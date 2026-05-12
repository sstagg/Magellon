import { test } from '@playwright/test';
import fs from 'node:fs';
import path from 'node:path';
const FRONTEND = 'http://localhost:8080';
const BACKEND  = 'http://127.0.0.1:8000';
const SHOTS = path.join(process.cwd(), 'tests', 'e2e', 'screenshots', 'plugin-page-audit');
fs.mkdirSync(SHOTS, { recursive: true });

test('audit plugin runner page for template picker', async ({ page, context }) => {
  test.setTimeout(60_000);
  const consoleLogs: string[] = [];
  page.on('console', (m) => consoleLogs.push(`[${m.type()}] ${m.text()}`));

  const auth = await (await fetch(`${BACKEND}/auth/login`, {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ username: 'super', password: 'behd1d2' }),
  })).json();
  await context.addInitScript(({ token, userId, username }) => {
    localStorage.setItem('access_token', token);
    localStorage.setItem('currentUser', JSON.stringify({ id: userId, username, active: true, change_password_required: false }));
    localStorage.setItem('currentUserId', userId);
  }, { token: auth.access_token, userId: auth.user_id, username: auth.username });

  const url = `${FRONTEND}/en/panel/plugins/particle%20picking%2FTemplate%20Picker`;
  await page.goto(url, { waitUntil: 'networkidle' }).catch(() => {});
  await page.waitForTimeout(2500);
  await page.screenshot({ path: path.join(SHOTS, 'full.png'), fullPage: true });

  // Dump the rendered DOM body so we can see exactly what got mounted.
  const bodyText = await page.locator('body').innerText();
  fs.writeFileSync(path.join(SHOTS, 'body-text.txt'), bodyText.slice(0, 6000));

  // Find headings + any "particle picking"-specific UI hints.
  const headings = await page.locator('h1, h2, h3, h4').allTextContents();
  fs.writeFileSync(path.join(SHOTS, 'headings.json'), JSON.stringify(headings, null, 2));
  console.log('[heading]', headings.slice(0, 6));
  console.log('[has-image-picker]', await page.locator('button:has-text("Pick test image")').count());
  console.log('[has-template-paths-field]', await page.locator('text=/template[_ ]paths/i').count());
  console.log('[has-preview]', await page.locator('button:has-text("Preview")').count());

  fs.writeFileSync(path.join(SHOTS, 'console.txt'), consoleLogs.join('\n'));
});
