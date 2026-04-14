import { test, expect } from '@playwright/test';

const FRONTEND = 'http://localhost:8080';
const BACKEND = 'http://127.0.0.1:8000';

test('Hidden-marked fields (angle_ranges, image_path, output_dir) do not render', async ({ page, context }) => {
  test.setTimeout(60_000);
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
  await page.goto(`${FRONTEND}/en/panel/plugins/pp/template-picker`, { waitUntil: 'networkidle' });
  await page.waitForTimeout(1500);

  const body = await page.locator('body').innerText();
  expect(body).not.toMatch(/Angle Ranges/i);
  expect(body).not.toMatch(/Output Dir/i);
  // image_path is ui_hidden; should not show as a field
  const imagePathFields = await page.getByLabel(/^Image Path$/i).count();
  expect(imagePathFields).toBe(0);
});
