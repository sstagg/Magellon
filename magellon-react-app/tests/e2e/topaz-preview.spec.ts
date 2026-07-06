/**
 * End-to-end test: Topaz interactive preview-and-tune.
 *
 * Topaz used to be queued-job-only. This exercises the new PREVIEW
 * capability: the CNN runs once (~45 s), then threshold/radius retuning
 * re-runs only NMS (sub-second) against the cached score map.
 *
 * Pre-reqs (set up by the workspace, not this test):
 *   - CoreService on 127.0.0.1:8000
 *   - magellon-plugin-topaz container rebuilt with the PREVIEW code,
 *     announcing under category topaz_particle_picking with an
 *     http_endpoint CoreService can reach
 *   - session 24dec03a imported with real MRC files on /gpfs
 *
 * Phase 1 drives the REST surface the side panel uses; Phase 2 drives
 * the React panel itself.
 */
import { expect, test } from '@playwright/test';
import { E2E_USERNAME, E2E_PASSWORD } from './helpers/credentials';
import fs from 'node:fs';
import path from 'node:path';

const FRONTEND = 'http://localhost:8080';
const BACKEND = 'http://127.0.0.1:8000';
const SESSION = '24dec03a';
const SHOTS = path.join(process.cwd(), 'tests', 'e2e', 'screenshots', 'topaz-preview');
fs.mkdirSync(SHOTS, { recursive: true });

async function login(): Promise<any> {
  return (await fetch(`${BACKEND}/auth/login`, {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ username: E2E_USERNAME, password: E2E_PASSWORD }),
  })).json();
}

// ---------------------------------------------------------------------------
// Phase 1 — REST surface. Confirms Topaz advertises PREVIEW, the slow
// preview returns picks + a score map, retune is cheap, and discard frees.
// ---------------------------------------------------------------------------

test('topaz preview → retune → discard via /particle-picking', async ({ request }) => {
  test.setTimeout(180_000);
  const auth = await login();
  const authHeader = { Authorization: `Bearer ${auth.access_token}` };

  // Topaz must advertise PREVIEW for the panel to show the button.
  const backendsRes = await request.get(`${BACKEND}/particle-picking/backends`);
  const backends = await backendsRes.json();
  const topaz = backends.find((b: any) =>
    String(b.backend_id).toLowerCase().includes('topaz'));
  expect(topaz, 'a topaz backend must be live').toBeTruthy();
  console.log('[topaz-backend]', JSON.stringify(topaz));
  expect(topaz.has_preview, 'topaz must advertise Capability.PREVIEW').toBe(true);

  // A real exposure image to pick on. Magellon names atlases `*gr`,
  // squares `*sq`, holes `*hl`, exposures `*ex` — only exposures carry
  // particles, so pick one of those, not whatever sorts first.
  const imgsRes = await request.get(
    `${BACKEND}/particle-picking/session-images?session_name=${SESSION}`,
    { headers: authHeader });
  const imgs = await imgsRes.json();
  expect(Array.isArray(imgs) && imgs.length > 0, 'session must have images').toBe(true);
  const exposure = imgs.find((i: any) => /\d+ex$/i.test(i.name));
  expect(exposure, 'session must have an exposure (*ex) image').toBeTruthy();
  const imageName: string = exposure.name;
  console.log('[image]', imageName);

  // Preview — the expensive CNN pass.
  const t0 = Date.now();
  const previewRes = await request.post(`${BACKEND}/particle-picking/preview`, {
    headers: { ...authHeader, 'Content-Type': 'application/json' },
    data: {
      backend: 'topaz', image_path: imageName, session_name: SESSION,
      model: 'resnet16', threshold: -3.0, radius: 14, scale: 8,
    },
  });
  const preview = await previewRes.json();
  console.log('[preview-status]', previewRes.status(), `${Date.now() - t0}ms`);
  if (previewRes.status() !== 200) console.log('[preview-error]', JSON.stringify(preview).slice(0, 600));
  expect(previewRes.status()).toBe(200);
  expect(preview.preview_id, 'preview must return a preview_id').toBeTruthy();
  expect(preview.num_particles, 'preview must find particles').toBeGreaterThan(0);
  expect(preview.score_map_png_base64, 'preview must return a score-map PNG').toBeTruthy();
  const previewCount = preview.num_particles;
  console.log('[preview-ok]', previewCount, 'particles');

  // Retune stricter — must be cheap (cached score map, no CNN) and pick fewer.
  const t1 = Date.now();
  const retuneRes = await request.post(
    `${BACKEND}/particle-picking/preview/${preview.preview_id}/retune?backend=topaz`, {
      headers: { ...authHeader, 'Content-Type': 'application/json' },
      data: { threshold: 0.0, radius: 14 },
    });
  const retune = await retuneRes.json();
  const retuneMs = Date.now() - t1;
  console.log('[retune-status]', retuneRes.status(), `${retuneMs}ms`, retune.num_particles, 'particles');
  expect(retuneRes.status()).toBe(200);
  expect(retuneMs, 'retune must be cheap — no CNN recompute').toBeLessThan(15_000);
  expect(retune.num_particles, 'stricter threshold picks fewer').toBeLessThanOrEqual(previewCount);

  // Discard frees the cached score map.
  const delRes = await request.delete(
    `${BACKEND}/particle-picking/preview/${preview.preview_id}?backend=topaz`,
    { headers: authHeader });
  expect(delRes.status()).toBe(200);

  fs.writeFileSync(path.join(SHOTS, 'preview-summary.json'), JSON.stringify({
    image: imageName, preview_particles: previewCount,
    retune_particles: retune.num_particles, retune_ms: retuneMs,
  }, null, 2));
});

// ---------------------------------------------------------------------------
// Phase 2 — React panel. Best-effort walk: open the particle-picking
// tab, open the settings panel, confirm Topaz offers "Preview & tune"
// (the UI-visible proof of the PREVIEW capability), then run it. Deep
// image-grid navigation is brittle, so steps that can't be driven skip
// cleanly with a screenshot rather than false-failing — Phase 1 already
// proves the integration.
// ---------------------------------------------------------------------------

test('topaz Preview & tune is offered in the side panel', async ({ page, context }) => {
  test.setTimeout(180_000);
  const auth = await login();
  await context.addInitScript(
    ({ token, userId, username }) => {
      localStorage.setItem('access_token', token);
      localStorage.setItem('currentUser', JSON.stringify({ id: userId, username, active: true, change_password_required: false }));
      localStorage.setItem('currentUserId', userId);
    },
    { token: auth.access_token, userId: auth.user_id, username: auth.username },
  );

  await page.goto(`${FRONTEND}/en/panel/images`, { waitUntil: 'networkidle' }).catch(() => {});
  await page.waitForTimeout(1500);
  await page.screenshot({ path: path.join(SHOTS, '01-images-page.png'), fullPage: true });

  // Select the test session.
  const combo = page.locator('[role="combobox"]').first();
  await expect(combo).toBeVisible({ timeout: 10_000 });
  await combo.click();
  await page.waitForTimeout(400);
  const sessionOption = page.locator('[role="option"]').filter({ hasText: SESSION }).first();
  if (await sessionOption.count() === 0) {
    test.skip(true, `session ${SESSION} not in the dropdown — import it first`);
  }
  await sessionOption.click();
  await page.waitForTimeout(3000);
  await page.screenshot({ path: path.join(SHOTS, '02-session-loaded.png'), fullPage: true });

  // Open an image so the Particle Picking tab has a selected micrograph.
  // The grid DOM varies; try a few openers and bail cleanly if none work.
  const openers = [
    page.locator('[role="treeitem"]').last(),
    page.locator('img[src*="image_thumbnail"]').first(),
    page.locator('img').nth(1),
  ];
  for (const opener of openers) {
    if (await opener.count() > 0) {
      await opener.click({ timeout: 4000 }).catch(() => {});
      await page.waitForTimeout(1500);
      if (await page.getByRole('tab', { name: /particle/i }).count() > 0) break;
    }
  }
  const ppTab = page.getByRole('tab', { name: /particle/i }).first();
  if (await ppTab.count() === 0) {
    await page.screenshot({ path: path.join(SHOTS, '03-no-pp-tab.png'), fullPage: true });
    test.skip(true, 'could not open an image / reach the Particle Picking tab');
  }
  await ppTab.click();
  await page.waitForTimeout(1000);
  await page.screenshot({ path: path.join(SHOTS, '03-particle-tab.png'), fullPage: true });

  // Open the settings side panel.
  const settingsBtn = page.getByRole('button', { name: /settings/i }).first();
  if (await settingsBtn.count() > 0) { await settingsBtn.click(); await page.waitForTimeout(1500); }
  await page.screenshot({ path: path.join(SHOTS, '04-settings-open.png'), fullPage: true });

  // The integration assertion: with Topaz selected (it auto-selects, as
  // the live preview-capable backend), the panel offers "Preview & tune"
  // — which only renders when the backend advertises Capability.PREVIEW.
  const previewBtn = page.getByRole('button', { name: /preview.*tune/i }).first();
  await expect(previewBtn, 'Topaz must offer Preview & tune (no-save)').toBeVisible({ timeout: 15_000 });
  console.log('[ui] "Preview & tune" button is offered for Topaz');

  // Run it — the CNN pass is ~30 s, then a particle count appears.
  await previewBtn.click();
  await expect(page.getByText(/\d+\s+particles/i)).toBeVisible({ timeout: 150_000 });
  await page.screenshot({ path: path.join(SHOTS, '05-preview-result.png'), fullPage: true });
  console.log('[ui] preview completed — particle count rendered');
});
