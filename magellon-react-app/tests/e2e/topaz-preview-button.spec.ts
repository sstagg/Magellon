/**
 * Confirm the side panel offers the "Preview & tune" button for Topaz
 * (the visible proof that ``has_preview`` is true on the backend).
 *
 * Pushes the session + image straight into the imageViewerStore so the
 * test isn't fighting the column-browser navigation.
 */
import { expect, test } from '@playwright/test';
import { E2E_USERNAME, E2E_PASSWORD } from './helpers/credentials';
import path from 'node:path';
import fs from 'node:fs';

const FRONTEND = 'http://localhost:8080';
const BACKEND = 'http://127.0.0.1:8000';
const SESSION = '24dec03a';
const IMAGE_NAME = '24dec03a_00034gr_00005sq_v01_00003hl_00018ex';
const SHOTS = path.join(process.cwd(), 'tests', 'e2e', 'screenshots', 'topaz-preview-button');
fs.mkdirSync(SHOTS, { recursive: true });

async function login(): Promise<any> {
  return (await fetch(`${BACKEND}/auth/login`, {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ username: E2E_USERNAME, password: E2E_PASSWORD }),
  })).json();
}

test('side panel offers "Preview & tune" for Topaz', async ({ page, context }) => {
  test.setTimeout(60_000);
  const auth = await login();
  const authHeader = { Authorization: `Bearer ${auth.access_token}` };

  // Quick backend sanity check — fail fast if topaz isn't advertising preview.
  const backends = await (await fetch(`${BACKEND}/particle-picking/backends`)).json();
  const topaz = (backends as any[]).find((b) => /topaz/i.test(b.backend_id));
  expect(topaz, 'topaz backend must be live').toBeTruthy();
  expect(topaz.has_preview, 'backend must advertise has_preview=true').toBe(true);

  const sessImgs = await (await fetch(
    `${BACKEND}/particle-picking/session-images?session_name=${SESSION}`,
    { headers: authHeader },
  )).json();
  const image = (sessImgs as any[]).find((i) => i.name === IMAGE_NAME);
  expect(image, `image ${IMAGE_NAME} must exist`).toBeTruthy();

  await context.addInitScript(
    ({ token, userId, username }) => {
      localStorage.setItem('access_token', token);
      localStorage.setItem('currentUser', JSON.stringify({ id: userId, username, active: true, change_password_required: false }));
      localStorage.setItem('currentUserId', userId);
    },
    { token: auth.access_token, userId: auth.user_id, username: auth.username },
  );

  await page.goto(`${FRONTEND}/en/panel/images`, { waitUntil: 'networkidle' }).catch(() => {});
  await page.waitForTimeout(1200);

  await page.evaluate(async ({ session, img }) => {
    const mod = await import('/src/features/image-viewer/model/imageViewerStore.ts');
    const store = (mod as any).useImageViewerStore;
    store.getState().setCurrentSession({ Oid: session, name: session });
    store.getState().setCurrentImage({ ...img, level: 3 });
  }, { session: SESSION, img: image });
  await page.waitForTimeout(1500);

  await page.getByRole('tab', { name: /particle/i }).first().click();
  await page.waitForTimeout(600);

  // Open the in-tab settings panel (NOT the page-header gear).
  const settingsCandidates = page.locator('button:has(svg[data-testid="SettingsIcon"])');
  const count = await settingsCandidates.count();
  for (let i = 0; i < count; i++) {
    const b = settingsCandidates.nth(i);
    const box = await b.boundingBox();
    if (box && box.y > 80) { await b.click(); break; }
  }
  await page.waitForTimeout(1500);
  await page.screenshot({ path: path.join(SHOTS, '01-settings-open.png'), fullPage: true });

  // The integration assertion: with Topaz selected, the panel must
  // render the "Preview & tune" button. If the alert "Topaz currently
  // runs as a queued job..." is showing instead, has_preview is false
  // on the panel side — that's the bug this work just fixed.
  const previewBtn = page.getByRole('button', { name: /preview.*tune/i }).first();
  await expect(previewBtn).toBeVisible({ timeout: 10_000 });
});
