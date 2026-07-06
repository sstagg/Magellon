/**
 * Quick visual check of the new Activity tab on the FFT plugin's
 * runner page. Captures Workspace + Logs + Activity tabs so the
 * three are easy to compare.
 */
import { test } from '@playwright/test';
import { E2E_USERNAME, E2E_PASSWORD } from './helpers/credentials';
import fs from 'node:fs';
import path from 'node:path';

const FRONTEND = 'http://localhost:8080';
const BACKEND = 'http://127.0.0.1:8000';
const SHOTS = path.join(process.cwd(), 'tests', 'e2e', 'screenshots', 'activity-tab');
fs.mkdirSync(SHOTS, { recursive: true });

const FFT_PAGE = encodeURI('/en/panel/plugins/fft/FFT — magnitude spectrum');

test('snapshot activity tab on fft runner', async ({ page, context }) => {
  test.setTimeout(120_000);
  const auth = await (await fetch(`${BACKEND}/auth/login`, {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ username: E2E_USERNAME, password: E2E_PASSWORD }),
  })).json();
  await context.addInitScript(({ token, userId, username }: any) => {
    localStorage.setItem('access_token', token);
    localStorage.setItem('currentUser', JSON.stringify({ id: userId, username, active: true, change_password_required: false }));
    localStorage.setItem('currentUserId', userId);
  }, { token: auth.access_token, userId: auth.user_id, username: auth.username });

  await page.setViewportSize({ width: 1440, height: 900 });
  await page.goto(`${FRONTEND}${FFT_PAGE}`, { waitUntil: 'domcontentloaded' });
  await page.waitForLoadState('networkidle').catch(() => {});
  await page.waitForTimeout(3000);

  // Switch to Activity tab
  await page.getByRole('tab', { name: /^Activity$/i }).click();
  // Wait for the Queues subtitle to render so the first poll has
  // landed before we take the screenshot.
  await page.getByText(/^Queues$/i).waitFor({ timeout: 15_000 }).catch(() => {});
  await page.waitForTimeout(2000);
  await page.screenshot({ path: path.join(SHOTS, '01-activity-tab.png'), fullPage: true });

  // Narrow viewport
  await page.setViewportSize({ width: 820, height: 1180 });
  await page.waitForTimeout(2000);
  await page.screenshot({ path: path.join(SHOTS, '02-activity-narrow.png'), fullPage: true });
});
