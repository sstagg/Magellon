/**
 * End-to-end BoxNet check on the known 24dec03a exposure.
 *
 * The fixture has positive contrast for BoxNet, so the test deliberately
 * selects the BoxNet backend in the image viewer settings panel and enables
 * the plugin's `invert` option before dispatching through the normal RMQ path.
 */
import { expect, test } from '@playwright/test';
import fs from 'node:fs';
import path from 'node:path';

const FRONTEND = 'http://localhost:8080';
const BACKEND = 'http://127.0.0.1:8000';
const SESSION = '24dec03a';
const IMAGE_NAME = '24dec03a_00034gr_00005sq_v01_00003hl_00018ex';
const SHOTS = path.join(process.cwd(), 'tests', 'e2e', 'screenshots', 'boxnet-00018ex');

fs.mkdirSync(SHOTS, { recursive: true });

async function login(): Promise<any> {
  const res = await fetch(`${BACKEND}/auth/login`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ username: 'super', password: 'behd1d2' }),
  });
  expect(res.ok, 'login must succeed').toBeTruthy();
  return res.json();
}

test('boxnet-picker runs end-to-end on 00018ex from the image viewer', async ({ page, context }) => {
  test.setTimeout(360_000);

  const auth = await login();
  const authHeader = { Authorization: `Bearer ${auth.access_token}` };

  const backends = await (await fetch(`${BACKEND}/particle-picking/backends`)).json();
  const topaz = (backends as any[]).find((b) => /topaz/i.test(b.backend_id));
  const boxnet = (backends as any[]).find((b) => b.backend_id === 'boxnet-picker');
  expect(topaz, 'Topaz backend must still be advertised').toBeTruthy();
  expect(boxnet, 'BoxNet backend must be advertised').toBeTruthy();
  expect(boxnet.has_sync, 'BoxNet must advertise sync capability').toBe(true);

  const sessImgs = await (await fetch(
    `${BACKEND}/particle-picking/session-images?session_name=${SESSION}`,
    { headers: authHeader },
  )).json();
  const image = (sessImgs as any[]).find((i) => i.name === IMAGE_NAME);
  expect(image, `image ${IMAGE_NAME} must exist in ${SESSION}`).toBeTruthy();

  await context.addInitScript(
    ({ token, userId, username }) => {
      localStorage.setItem('access_token', token);
      localStorage.setItem(
        'currentUser',
        JSON.stringify({ id: userId, username, active: true, change_password_required: false }),
      );
      localStorage.setItem('currentUserId', userId);
    },
    { token: auth.access_token, userId: auth.user_id, username: auth.username },
  );

  const consoleLog: string[] = [];
  page.on('console', (msg) => consoleLog.push(`[${msg.type()}] ${msg.text()}`));
  page.on('pageerror', (err) => consoleLog.push(`[pageerror] ${err.message}`));

  await page.goto(`${FRONTEND}/en/panel/images`, { waitUntil: 'networkidle' }).catch(() => {});
  await page.waitForTimeout(1500);

  await page.evaluate(async ({ session, img }) => {
    const mod = await import('/src/features/image-viewer/model/imageViewerStore.ts');
    const store = (mod as any).useImageViewerStore;
    store.getState().setCurrentSession({ Oid: session, name: session });
    store.getState().setCurrentImage({ ...img, level: 3 });
  }, { session: SESSION, img: image });
  await page.waitForTimeout(1500);
  await page.screenshot({ path: path.join(SHOTS, '01-store-set.png'), fullPage: true });

  await page.getByRole('tab', { name: /particle/i }).first().click();
  await page.waitForTimeout(800);

  const settingsCandidates = page.locator('button:has(svg[data-testid="SettingsIcon"])');
  const settingsCount = await settingsCandidates.count();
  for (let i = 0; i < settingsCount; i++) {
    const b = settingsCandidates.nth(i);
    const box = await b.boundingBox();
    if (box && box.y > 80) {
      await b.click();
      break;
    }
  }
  await page.waitForTimeout(1500);
  await page.screenshot({ path: path.join(SHOTS, '02-settings-open.png'), fullPage: true });

  await page.getByRole('combobox').filter({ hasText: /Topaz Particle Picking/i }).click();
  await page.getByRole('option', { name: /BoxNet Picker/i }).click({ timeout: 10_000 });
  await expect(page.getByText(/This backend does not advertise no-save preview/i)).toBeVisible({ timeout: 15_000 });

  await page.getByText('Preprocessing', { exact: true }).click();
  const invert = page.getByRole('checkbox', { name: /Toggle ON when raw inference/i });
  await expect(invert).toBeVisible({ timeout: 10_000 });
  if (!(await invert.isChecked())) {
    await invert.check();
  }
  await page.screenshot({ path: path.join(SHOTS, '03-boxnet-configured.png'), fullPage: true });

  const dispatchRequest = page.waitForRequest((req) =>
    req.url().includes('/particle-picking/dispatch') && req.method() === 'POST',
  );
  const dispatchResponsePromise = page.waitForResponse((res) =>
    res.url().includes('/particle-picking/dispatch') && res.request().method() === 'POST',
  );
  await page.getByRole('button', { name: /run and save image/i }).click();
  const [req, dispatchResponse] = await Promise.all([dispatchRequest, dispatchResponsePromise]);
  const dispatchBody = JSON.parse(req.postData() || '{}');
  fs.writeFileSync(path.join(SHOTS, 'dispatch.json'), JSON.stringify(dispatchBody, null, 2));
  expect(dispatchBody.target_backend).toBe('boxnet-picker');
  expect(dispatchBody.engine_opts?.invert).toBe(true);
  expect(dispatchResponse.ok(), 'dispatch request must succeed').toBeTruthy();

  let ipp: any = null;
  let lastPollError = '';
  for (let attempt = 0; attempt < 90 && !ipp; attempt++) {
    await page.waitForTimeout(3000);
    let list: any = null;
    try {
      const response = await fetch(
        `${BACKEND}/web/particle-pickings?img_name=${IMAGE_NAME}&_=${Date.now()}`,
        { headers: authHeader },
      );
      list = await response.json();
    } catch (error) {
      lastPollError = error instanceof Error ? error.message : String(error);
      continue;
    }
    if (Array.isArray(list)) {
      ipp = list.find((item) => item.name === dispatchBody.ipp_name) || null;
    }
  }
  expect(ipp, `BoxNet IPP record must appear. Last poll error: ${lastPollError || 'none'}`).toBeTruthy();

  const particles: any[] = Array.isArray(ipp.data_json) ? ipp.data_json : [];
  expect(particles.length, 'BoxNet should save at least one particle for this fixture with invert=true').toBeGreaterThan(0);

  await expect(page.locator('text=/\\d+\\s+particles\\s+picked/i').first()).toBeVisible({ timeout: 30_000 });
  await page.screenshot({ path: path.join(SHOTS, '04-after-boxnet-pick.png'), fullPage: true });

  const circles = await page.locator('svg circle').count();
  expect(circles, 'particle overlay should render circles').toBeGreaterThan(0);

  fs.writeFileSync(path.join(SHOTS, 'console.log'), consoleLog.join('\n'));
  fs.writeFileSync(path.join(SHOTS, 'report.json'), JSON.stringify({
    image: { name: image.name, oid: image.oid, pixel_size: image.pixel_size },
    backend: boxnet,
    dispatch: dispatchBody,
    ipp: { oid: ipp.oid, name: ipp.name },
    particle_count: particles.length,
    sample_coords: particles.slice(0, 8),
    overlay_circles: circles,
  }, null, 2));

  const looped = consoleLog.some((l) =>
    /Maximum update depth exceeded/i.test(l) || /ImageViewer error/i.test(l),
  );
  expect(looped, 'UI must not hit the previous render loop/error boundary').toBeFalsy();
});
