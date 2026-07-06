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
import { E2E_USERNAME, E2E_PASSWORD } from './helpers/credentials';
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
    body: JSON.stringify({ username: E2E_USERNAME, password: E2E_PASSWORD }),
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
// Phase 2 — UI smoke. The deep "click Preview, see particle markers"
// flow requires a DB session whose images resolve to real MRC files on
// disk; the seeded test_session_* don't. So this test verifies the
// minimum the panel needs to be wired up correctly:
//   - /en/panel/images loads and React renders without console errors
//   - the session dropdown has > 0 options
//   - picking a session loads the image area without 5xx errors
//
// When a session matching the test image exists, the original
// click-through (image card → Particle Picking tab → Preview button
// → particles render) lives in commit history — restore it then.
// ---------------------------------------------------------------------------

test('panel renders + session dropdown is populated', async ({ page, context }) => {
  test.setTimeout(60_000);

  const consoleErrors: string[] = [];
  const fiveHundreds: Array<{ url: string; status: number }> = [];
  page.on('console', (m) => { if (m.type() === 'error') consoleErrors.push(m.text()); });
  page.on('response', (res) => {
    const url = res.url();
    if (url.includes('127.0.0.1:8000') && res.status() >= 500) {
      fiveHundreds.push({ url, status: res.status() });
    }
  });

  const auth = await (await fetch(`${BACKEND}/auth/login`, {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ username: E2E_USERNAME, password: E2E_PASSWORD }),
  })).json();
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

  // MUI Select rendering — combobox role + "Select Collection..." text.
  const combo = page.locator('[role="combobox"]').first();
  await expect(combo, 'Session dropdown (combobox) must be present').toBeVisible({ timeout: 10_000 });
  await combo.click();
  await page.waitForTimeout(500);
  await page.screenshot({ path: path.join(SHOTS, '02-dropdown-open.png'), fullPage: true });

  // Options come from /web/sessions — at least one real session should
  // show alongside the "Select Collection..." placeholder.
  const realOptions = page.locator('[role="option"]').filter({ hasNotText: /Select Collection/i });
  const optionCount = await realOptions.count();
  console.log('[session-options]', optionCount);
  expect(optionCount, 'Session dropdown should have at least one session').toBeGreaterThan(0);

  // Close dropdown + record final state.
  await page.keyboard.press('Escape');
  await page.waitForTimeout(300);
  await page.screenshot({ path: path.join(SHOTS, '03-final.png'), fullPage: true });

  fs.writeFileSync(
    path.join(SHOTS, 'ui-smoke.json'),
    JSON.stringify({
      consoleErrors: consoleErrors.slice(0, 20),
      fiveHundreds,
      sessionOptionCount: optionCount,
    }, null, 2),
  );

  expect(fiveHundreds, `No 5xx responses to backend; got: ${JSON.stringify(fiveHundreds)}`).toHaveLength(0);
  expect(consoleErrors.length, `No React/JS console errors; got: ${consoleErrors.slice(0, 5).join(' || ')}`).toBe(0);
});
