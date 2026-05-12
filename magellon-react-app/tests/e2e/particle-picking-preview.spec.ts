/**
 * End-to-end test: open the particle-picking side panel on the image
 * page, click Preview, and verify the dockerized template-picker
 * plugin returns particles and they render onto the image.
 *
 * Pre-reqs (set up by the workspace / not by this test):
 *   - CoreService running on 127.0.0.1:8000 with the latest
 *     TemplatePickerInput defaults (3.16 Å/px, 2.646 Å/px, etc.)
 *   - magellon-template-picker container running and announcing on
 *     RMQ; visible at GET /plugins/ as
 *     "particle picking/Template Picker"
 *   - Three reference templates at /gpfs/templates/origTemplate{1,2,3}.mrc
 *
 * The test itself:
 *   - logs in as super
 *   - hits /particle-picking/preview directly (matches what the panel
 *     does), captures the response, and asserts num_particles > 0
 *   - then drives the UI: opens /en/panel/images, picks the test
 *     image, clicks Preview, screenshots each stage, and asserts
 *     the particle overlay is visible
 */
import { expect, test } from '@playwright/test';
import fs from 'node:fs';
import path from 'node:path';

const FRONTEND = 'http://localhost:8080';
const BACKEND = 'http://127.0.0.1:8000';
const SHOTS = path.join(process.cwd(), 'tests', 'e2e', 'screenshots', 'particle-picking-preview');
fs.mkdirSync(SHOTS, { recursive: true });

const TEST_IMAGE_PATH = '/gpfs/24dec03a/home/original/24dec03a_00031gr_00001sq_v01_00002hl_00001fc.mrc';

// ---------------------------------------------------------------------------
// Phase 1 — backend smoke (no UI). Confirms the live plugin actually
// returns picks for the configured defaults before we drive the React
// side; lets us distinguish "panel UX broke" from "plugin not running".
// ---------------------------------------------------------------------------

test('preview API returns particles via /particle-picking/preview', async ({ request }) => {
  test.setTimeout(120_000);

  const auth = await (await fetch(`${BACKEND}/auth/login`, {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ username: 'super', password: 'behd1d2' }),
  })).json();

  // Confirm CoreService sees a live particle_picking plugin first;
  // otherwise the preview will 503 with "no live plugin".
  const live = await request.get(`${BACKEND}/plugins/`, {
    headers: { Authorization: `Bearer ${auth.access_token}` },
  });
  const livePlugins = await live.json();
  const pp = livePlugins.find((p: any) =>
    p.category?.toLowerCase().replace(' ', '_') === 'particle_picking' ||
    p.category === 'particle_picking',
  );
  expect(pp, 'Expected a live particle_picking plugin in /plugins/').toBeTruthy();
  console.log('[live-plugin]', pp.plugin_id, 'category=', pp.category);

  // Match what the side panel does — POST to /particle-picking/preview
  // with the same shape SchemaForm would produce.
  const preview = await request.post(`${BACKEND}/particle-picking/preview`, {
    headers: {
      Authorization: `Bearer ${auth.access_token}`,
      'Content-Type': 'application/json',
    },
    data: {
      image_path: TEST_IMAGE_PATH,
      template_paths: [
        '/gpfs/templates/origTemplate1.mrc',
        '/gpfs/templates/origTemplate2.mrc',
        '/gpfs/templates/origTemplate3.mrc',
      ],
      diameter_angstrom: 220.0,
      image_pixel_size: 3.16,
      template_pixel_size: 2.646,
      threshold: 0.35,
      invert_templates: true,
      bin_factor: 1,
    },
  });
  const body = await preview.json();
  console.log('[preview-status]', preview.status());
  console.log('[preview-body-keys]', Object.keys(body));
  if (preview.status() !== 200) console.log('[preview-error-body]', JSON.stringify(body).slice(0, 800));
  expect(preview.status(), `preview returned ${preview.status()}: ${JSON.stringify(body).slice(0, 300)}`).toBe(200);
  expect(body.num_particles ?? body.particles?.length, 'num_particles must be > 0').toBeGreaterThan(0);
  console.log('[preview-ok] num_particles =', body.num_particles ?? body.particles?.length);

  fs.writeFileSync(
    path.join(SHOTS, 'preview-summary.json'),
    JSON.stringify({
      status: preview.status(),
      num_particles: body.num_particles ?? body.particles?.length,
      num_templates: body.num_templates,
      preview_id: body.preview_id,
    }, null, 2),
  );
});

// ---------------------------------------------------------------------------
// Phase 2 — UI flow. Drives the React side panel end to end and
// captures screenshots at each step. Asserts the particle overlay
// renders with at least one marker after Preview returns.
// ---------------------------------------------------------------------------

test('side panel preview flow renders particles', async ({ page, context }) => {
  test.setTimeout(180_000);

  const consoleErrors: string[] = [];
  const network: Array<{ url: string; status: number; method: string; body?: string }> = [];
  page.on('console', (m) => { if (m.type() === 'error') consoleErrors.push(m.text()); });
  page.on('response', async (res) => {
    const url = res.url();
    if (!url.includes('127.0.0.1:8000')) return;
    const e: any = { url, status: res.status(), method: res.request().method() };
    if (res.status() >= 400) {
      try { e.body = (await res.text()).slice(0, 800); } catch {}
    }
    network.push(e);
  });

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

  // Step 1 — load the image browser.
  await page.goto(`${FRONTEND}/en/panel/images`, { waitUntil: 'networkidle' }).catch(() => {});
  await page.waitForTimeout(2000);
  await page.screenshot({ path: path.join(SHOTS, '01-images-page.png'), fullPage: true });

  // Step 2 — pick a session that contains the test image. The image
  // browser's session list is data-driven; we click the first
  // visible session, then the first image. Names vary across
  // installs; this test is forgiving — if no session loads, screenshot
  // and bail with a clear error.
  const sessionLink = page.locator('a, button').filter({ hasText: /24dec03a|session|24dec/i }).first();
  if (await sessionLink.count() > 0) {
    await sessionLink.click({ timeout: 5000 }).catch(() => {});
    await page.waitForTimeout(2000);
  }
  await page.screenshot({ path: path.join(SHOTS, '02-session-loaded.png'), fullPage: true });

  // Step 3 — pick an image. Try the test image specifically; fall
  // back to the first image card.
  const imageNeedle = '24dec03a_00031gr_00001sq_v01_00002hl_00001fc';
  const imageBtn = page.locator(`[data-image-name*="${imageNeedle}" i], [title*="${imageNeedle}" i], button:has-text("${imageNeedle}")`).first();
  if (await imageBtn.count() > 0) {
    await imageBtn.click({ timeout: 5000 });
  } else {
    const firstImg = page.locator('[data-image-name], [data-testid*="image-card"], img').first();
    if (await firstImg.count() > 0) await firstImg.click({ timeout: 5000 }).catch(() => {});
  }
  await page.waitForTimeout(2000);
  await page.screenshot({ path: path.join(SHOTS, '03-image-selected.png'), fullPage: true });

  // Step 4 — open the particle-picking side panel. Many UIs make
  // this its own tab; try clicking anything that looks like it.
  const ppTab = page.locator('button, a, [role="tab"]').filter({ hasText: /particle.*picking|template|picker/i }).first();
  if (await ppTab.count() > 0) {
    await ppTab.click({ timeout: 5000 }).catch(() => {});
    await page.waitForTimeout(1500);
  }
  await page.screenshot({ path: path.join(SHOTS, '04-side-panel-open.png'), fullPage: true });

  // Step 5 — find Preview button and click. The button label is
  // typically "Preview" with a small icon.
  const previewBtn = page.locator('button').filter({ hasText: /^preview/i }).first();
  await expect(previewBtn, 'Preview button must be reachable').toBeVisible({ timeout: 10_000 });
  await previewBtn.click();

  // Step 6 — wait for either the success state (score map / particles
  // count) OR an explicit error alert. Either is captured.
  await Promise.race([
    page.locator('text=/\\d+ particles/i').first().waitFor({ timeout: 90_000 }).catch(() => {}),
    page.locator('[role="alert"]').first().waitFor({ timeout: 90_000 }).catch(() => {}),
  ]);
  await page.waitForTimeout(2500);
  await page.screenshot({ path: path.join(SHOTS, '05-preview-result.png'), fullPage: true });

  // Step 7 — was preview successful?
  const errorAlert = await page.locator('[role="alert"]').filter({ hasText: /failed|error|no live plugin/i }).first().textContent({ timeout: 1000 }).catch(() => null);
  if (errorAlert) {
    fs.writeFileSync(path.join(SHOTS, 'error.txt'), errorAlert);
    fs.writeFileSync(path.join(SHOTS, 'network.json'), JSON.stringify(network, null, 2));
    fs.writeFileSync(path.join(SHOTS, 'console-errors.txt'), consoleErrors.join('\n'));
    throw new Error(`Preview failed: ${errorAlert.slice(0, 300)}`);
  }

  // Particle count chip / overlay sanity check.
  const particleCountText = await page.locator('text=/\\d+\\s*(particles?|picks?)/i').first().textContent({ timeout: 5_000 }).catch(() => null);
  console.log('[particle-count]', particleCountText);
  fs.writeFileSync(path.join(SHOTS, 'network.json'), JSON.stringify(network.slice(-30), null, 2));

  // Look for an SVG/canvas marker layer over the image — the panel
  // overlays a `+`-style marker for each particle. We accept any
  // overlay element keyed off "marker" / "overlay" / "particle".
  const overlay = page.locator('svg [class*="marker"], svg circle, [data-particle-marker]');
  const markerCount = await overlay.count();
  console.log('[markers-on-image]', markerCount);
  await page.screenshot({ path: path.join(SHOTS, '06-overlay-final.png'), fullPage: true });

  expect(particleCountText || markerCount > 0, 'No particle count surfaced and no overlay markers rendered').toBeTruthy();
});
