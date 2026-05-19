import { expect, test } from '@playwright/test';

const FRONTEND = process.env.MAGELLON_FRONTEND ?? 'http://localhost:8080';
const BACKEND = process.env.MAGELLON_BACKEND ?? 'http://127.0.0.1:8000';

interface AuthBody {
  access_token: string;
  user_id: string;
  username: string;
}

async function login(): Promise<AuthBody> {
  const res = await fetch(`${BACKEND}/auth/login`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ username: 'super', password: 'behd1d2' }),
  });
  if (!res.ok) throw new Error(`login failed: ${res.status} ${await res.text()}`);
  return res.json();
}

test('image tab exposes Ptolemy square detection and dispatches current image', async ({ page, context }) => {
  test.skip(process.env.MAGELLON_E2E_LIVE !== '1', 'live Magellon stack required');

  const auth = await login();
  await context.addInitScript(
    ({ token, userId, username }) => {
      localStorage.setItem('access_token', token);
      localStorage.setItem('currentUser', JSON.stringify({
        id: userId,
        username,
        active: true,
        change_password_required: false,
      }));
      localStorage.setItem('currentUserId', userId);
    },
    { token: auth.access_token, userId: auth.user_id, username: auth.username },
  );

  let dispatchBody: any = null;
  page.on('request', (request) => {
    if (request.url().includes('/image/ptolemy/square/dispatch')) {
      dispatchBody = request.postDataJSON();
    }
  });

  await page.goto(`${FRONTEND}/en/panel/images`, { waitUntil: 'domcontentloaded' });
  await page.getByRole('combobox').first().click();
  await page.getByRole('option', { name: '24DEC03A' }).click();
  await page.getByText('24dec03a_00017gr', { exact: true }).first().click();

  const squareButton = page.getByLabel('Run square detection');
  const holeButton = page.getByLabel('Run hole detection');
  await expect(squareButton).toBeVisible({ timeout: 10_000 });
  await expect(squareButton).toBeEnabled();
  await expect(holeButton).toBeVisible();
  await expect(holeButton).toBeEnabled();

  const responsePromise = page.waitForResponse((response) =>
    response.url().includes('/image/ptolemy/square/dispatch') && response.request().method() === 'POST',
  );
  await squareButton.click();
  const response = await responsePromise;
  expect(response.ok(), await response.text()).toBeTruthy();

  await expect(page.getByText('Square detection dispatched')).toBeVisible({ timeout: 5_000 });
  expect(dispatchBody?.image_path).toBe('/gpfs/home/24dec03a/original/24dec03a_00017gr.mrc');
  expect(dispatchBody?.session_name).toBe('24DEC03A');
  expect(dispatchBody?.image_id).toBeTruthy();
});
