import { test, expect } from '@playwright/test';
import fs from 'node:fs';
import path from 'node:path';

const FRONTEND = 'http://localhost:8080';
const BACKEND = 'http://127.0.0.1:8000';
const SHOTS = path.join(process.cwd(), 'tests', 'e2e', 'screenshots');
fs.mkdirSync(SHOTS, { recursive: true });

test('Optional number fields render as number inputs, not JSON textareas', async ({ page, context }) => {
  test.setTimeout(60_000);

  const auth = await (await fetch(`${BACKEND}/auth/login`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ username: 'super', password: 'behd1d2' }),
  })).json();

  await context.addInitScript(
    ({ token, userId, username }) => {
      const user = { id: userId, username, active: true, change_password_required: false };
      localStorage.setItem('access_token', token);
      localStorage.setItem('currentUser', JSON.stringify(user));
      localStorage.setItem('currentUserId', userId);
    },
    { token: auth.access_token, userId: auth.user_id, username: auth.username },
  );

  await page.goto(`${FRONTEND}/en/panel/plugins/pp/template-picker`, { waitUntil: 'networkidle' });
  await page.waitForTimeout(1500);

  const screenshot = (n: string) =>
    page.screenshot({ path: path.join(SHOTS, n), fullPage: true });

  await screenshot('optional-fields-before.png');

  const results: Record<string, string> = {};
  for (const labelText of ['Max Threshold', 'Lowpass Resolution']) {
    const fld = page.getByLabel(labelText, { exact: false }).first();
    const tag = await fld.evaluate((el) => el.tagName.toLowerCase()).catch(() => 'missing');
    const type = await fld.evaluate((el: any) => el.type ?? '').catch(() => '');
    const rows = await fld.evaluate((el: any) => el.rows ?? '').catch(() => '');
    results[labelText] = `${tag} type=${type} rows=${rows}`;
  }
  console.log('[field results]', results);
  fs.writeFileSync(path.join(SHOTS, 'optional-fields.json'), JSON.stringify(results, null, 2));

  for (const v of Object.values(results)) {
    expect(v).toMatch(/^input\s+type=number/);
  }
});
