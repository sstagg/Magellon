/**
 * Drive Topaz on a specific exposure (24dec03a_00034gr_00005sq_v01_00003hl_00018ex)
 * and capture two views:
 *   1. UI: side-panel state, canvas with overlaid picks, full-page screenshot.
 *   2. Backend: render the raw image + the picks coordinates from the saved
 *      IPP record so we can confirm the overlay is on the right pixels.
 *
 * Lets us reason about whether the canvas overlay in the Particle Picking
 * tab is showing the right thing, independent of the side-panel summary.
 */
import { expect, test } from '@playwright/test';
import { E2E_USERNAME, E2E_PASSWORD } from './helpers/credentials';
import fs from 'node:fs';
import path from 'node:path';

const FRONTEND = 'http://localhost:8080';
const BACKEND = 'http://127.0.0.1:8000';
const SESSION = '24dec03a';
const IMAGE_NAME = '24dec03a_00034gr_00005sq_v01_00003hl_00018ex';
const SHOTS = path.join(process.cwd(), 'tests', 'e2e', 'screenshots', 'topaz-00018ex');
fs.mkdirSync(SHOTS, { recursive: true });

async function login(): Promise<any> {
  return (await fetch(`${BACKEND}/auth/login`, {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ username: E2E_USERNAME, password: E2E_PASSWORD }),
  })).json();
}

test('drive topaz on 00018ex and snapshot UI + backend view', async ({ page, context }) => {
  test.setTimeout(240_000);
  const auth = await login();
  const authHeader = { Authorization: `Bearer ${auth.access_token}` };

  // Look the image up by name so we have its oid for the store push.
  const sessImgs = await (await fetch(
    `${BACKEND}/particle-picking/session-images?session_name=${SESSION}`,
    { headers: authHeader },
  )).json();
  const image = (sessImgs as any[]).find((i) => i.name === IMAGE_NAME);
  expect(image, `image ${IMAGE_NAME} must exist in session ${SESSION}`).toBeTruthy();
  console.log('[image]', { name: image.name, oid: image.oid, pixel_size: image.pixel_size });

  await context.addInitScript(
    ({ token, userId, username }) => {
      localStorage.setItem('access_token', token);
      localStorage.setItem('currentUser', JSON.stringify({ id: userId, username, active: true, change_password_required: false }));
      localStorage.setItem('currentUserId', userId);
    },
    { token: auth.access_token, userId: auth.user_id, username: auth.username },
  );

  const consoleLog: string[] = [];
  page.on('console', (msg) => consoleLog.push(`[${msg.type()}] ${msg.text()}`));
  page.on('pageerror', (err) => consoleLog.push(`[pageerror] ${err.message}`));

  await page.goto(`${FRONTEND}/en/panel/images`, { waitUntil: 'networkidle' }).catch(() => {});
  await page.waitForTimeout(1500);

  // Push session + image straight into the imageViewerStore through Vite.
  await page.evaluate(async ({ session, img }) => {
    const mod = await import('/src/features/image-viewer/model/imageViewerStore.ts');
    const store = (mod as any).useImageViewerStore;
    store.getState().setCurrentSession({ Oid: session, name: session });
    store.getState().setCurrentImage({ ...img, level: 3 });
  }, { session: SESSION, img: image });
  await page.waitForTimeout(1500);
  await page.screenshot({ path: path.join(SHOTS, '01-store-set.png'), fullPage: true });

  // Open Particle Picking tab.
  const ppTab = page.getByRole('tab', { name: /particle/i }).first();
  await ppTab.waitFor({ state: 'visible', timeout: 15_000 });
  await ppTab.click();
  await page.waitForTimeout(800);

  // Open the in-tab settings panel (NOT the page-header gear).
  const settingsCandidates = page.locator('button:has(svg[data-testid="SettingsIcon"])');
  const count = await settingsCandidates.count();
  for (let i = 0; i < count; i++) {
    const b = settingsCandidates.nth(i);
    const box = await b.boundingBox();
    if (box && box.y > 80) { await b.click(); break; }
  }
  await page.waitForTimeout(1500);
  await page.screenshot({ path: path.join(SHOTS, '02-settings-open.png'), fullPage: true });

  // Confirm backend is topaz and kick off the dispatch. The primary
  // button text varies with canPreview: "Save current image" when the
  // backend has advertised PREVIEW, "Run and save image" otherwise.
  const backendChip = page.getByText(/topaz/i).first();
  await backendChip.waitFor({ state: 'visible', timeout: 5000 }).catch(() => {});
  const saveBtn = page.getByRole('button', { name: /save current image|run and save image/i }).first();
  await expect(saveBtn).toBeVisible({ timeout: 15_000 });
  await saveBtn.click();
  console.log('[ui] Save current image clicked');

  // Wait for Topaz to finish (CNN + save). Poll /web/particle-pickings by image name.
  let ipp: any = null;
  for (let attempt = 0; attempt < 80 && !ipp; attempt++) {
    await page.waitForTimeout(2500);
    const list = await (await fetch(
      `${BACKEND}/web/particle-pickings?img_name=${IMAGE_NAME}`,
      { headers: authHeader },
    )).json();
    if (Array.isArray(list) && list.length > 0) {
      // Pick the freshest one (newest by name suffix; falls back to first).
      ipp = list.sort((a, b) => (b.name || '').localeCompare(a.name || ''))[0];
    }
  }
  expect(ipp, 'an IPP record must appear within ~200s').toBeTruthy();
  const particles: any[] = ipp.data_json || [];
  let meta: any = null;
  if (ipp.data) { try { meta = JSON.parse(ipp.data); } catch { /* ignore */ } }
  console.log('[ipp]', { oid: ipp.oid, name: ipp.name, particles: particles.length });
  console.log('[meta]', meta);
  console.log('[sample-coords]', particles.slice(0, 5).map((p) => ({ x: p.x, y: p.y })));

  // Wait for the in-app poller to load the IPP on its own (5s cadence,
  // up to ~100s). That's the path that drives the new 'results' state
  // transition in the side panel.
  for (let attempt = 0; attempt < 30; attempt++) {
    await page.waitForTimeout(2000);
    const heading = await page.locator('text=/particles picked/i').count();
    if (heading > 0) break;
  }
  await page.screenshot({ path: path.join(SHOTS, '03-after-pick.png'), fullPage: true });

  // Persist the console log NOW so we can see what happened even if
  // the panel-transition assertion fails.
  fs.writeFileSync(path.join(SHOTS, 'console.log'), consoleLog.join('\n'));

  // Assert the side panel landed on the 'results' state — the new
  // behavior we just wired for the dispatch flow.
  const resultsBadge = page.locator('text=/\\d+\\s+particles\\s+picked/i').first();
  await expect(resultsBadge, 'side panel must transition to "results" after dispatch completes').toBeVisible({ timeout: 5000 });

  // Capture the canvas region specifically so we can eyeball the overlay
  // pixels next to the server-side overlay rendered by render_overlay.py.
  const canvas = page.locator('canvas').first();
  if (await canvas.count() > 0) {
    const cbox = await canvas.boundingBox();
    if (cbox) {
      await page.screenshot({
        path: path.join(SHOTS, '04-canvas-region.png'),
        clip: cbox,
      });
    }
  }

  // Don't try to grab the whole tab panel — just the SVG that overlays
  // particles, plus a wide-area screenshot.
  const overlaySvg = page.locator('svg').filter({ has: page.locator('circle') }).first();
  if (await overlaySvg.count() > 0) {
    const obox = await overlaySvg.boundingBox().catch(() => null);
    if (obox) {
      await page.screenshot({ path: path.join(SHOTS, '05-particle-svg.png'), clip: obox });
    }
  }

  // Pull the raw thumbnail so we can overlay particles ourselves and
  // compare against what the canvas renders.
  const thumbRes = await fetch(
    `${BACKEND}/image_thumbnail?name=${IMAGE_NAME}&sessionName=${SESSION}`,
    { headers: authHeader },
  );
  if (thumbRes.ok) {
    const buf = Buffer.from(await thumbRes.arrayBuffer());
    fs.writeFileSync(path.join(SHOTS, 'image-thumbnail.png'), buf);
  }

  // Bounding box of the picks — helps us reason about the coord space.
  let minX = Infinity, maxX = -Infinity, minY = Infinity, maxY = -Infinity;
  for (const p of particles) {
    if (p.x < minX) minX = p.x;
    if (p.x > maxX) maxX = p.x;
    if (p.y < minY) minY = p.y;
    if (p.y > maxY) maxY = p.y;
  }

  fs.writeFileSync(path.join(SHOTS, 'report.json'), JSON.stringify({
    image: { name: image.name, oid: image.oid, pixel_size: image.pixel_size },
    ipp: { oid: ipp.oid, name: ipp.name },
    particle_count: particles.length,
    sample_coords: particles.slice(0, 8),
    saved_meta: meta,
    bbox: { minX, maxX, minY, maxY },
  }, null, 2));
  fs.writeFileSync(path.join(SHOTS, 'console.log'), consoleLog.join('\n'));

  // Sanity: no loop / error boundary.
  const looped = consoleLog.some((l) =>
    /Maximum update depth exceeded/i.test(l) || /ImageViewer error/i.test(l),
  );
  expect(looped, 'must not loop').toBeFalsy();
});
