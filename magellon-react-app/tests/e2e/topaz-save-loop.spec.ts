/**
 * Reproduce the "Maximum update depth exceeded" crash that fires
 * when the user clicks "Save current image" in the Topaz panel.
 *
 * Skip the column-browser drilling entirely by importing the
 * Zustand stores from Vite at runtime and pushing the session +
 * image directly.
 */
import { expect, test } from '@playwright/test';
import fs from 'node:fs';
import path from 'node:path';

const FRONTEND = 'http://localhost:8080';
const BACKEND = 'http://127.0.0.1:8000';
const SESSION = '24dec03a';
const SHOTS = path.join(process.cwd(), 'tests', 'e2e', 'screenshots', 'topaz-save-loop');
fs.mkdirSync(SHOTS, { recursive: true });

async function login(): Promise<any> {
  return (await fetch(`${BACKEND}/auth/login`, {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ username: 'super', password: 'behd1d2' }),
  })).json();
}

async function findExposure(token: string): Promise<any> {
  const res = await fetch(`${BACKEND}/particle-picking/session-images?session_name=${SESSION}`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  const list = await res.json();
  if (!Array.isArray(list)) return null;
  // Server returns gr images; an exposure has *ex in name.
  // session-images returns ALL images, including children — find an *ex.
  return list.find((i: any) => /\d+ex$/i.test(i.name)) || null;
}

test('Save current image must not loop', async ({ page, context }) => {
  test.setTimeout(180_000);
  const auth = await login();
  const exposure = await findExposure(auth.access_token);
  if (!exposure) test.skip(true, `no exposure (*ex) image in session ${SESSION}`);
  console.log('[exposure]', exposure.name);

  await context.addInitScript(
    ({ token, userId, username }) => {
      localStorage.setItem('access_token', token);
      localStorage.setItem('currentUser', JSON.stringify({ id: userId, username, active: true, change_password_required: false }));
      localStorage.setItem('currentUserId', userId);
    },
    { token: auth.access_token, userId: auth.user_id, username: auth.username },
  );

  const consoleLog: string[] = [];
  page.on('console', (msg) => {
    const t = msg.text();
    consoleLog.push(`[${msg.type()}] ${t}`);
  });
  page.on('pageerror', (err) => {
    consoleLog.push(`[pageerror] ${err.message}\n${err.stack || ''}`);
  });

  await page.goto(`${FRONTEND}/en/panel/images`, { waitUntil: 'networkidle' }).catch(() => {});
  await page.waitForTimeout(1500);

  // Push session + image straight into the store via Vite's dev module graph.
  const pushResult = await page.evaluate(async ({ session, image }) => {
    try {
      const mod = await import('/src/features/image-viewer/model/imageViewerStore.ts');
      const store = (mod as any).useImageViewerStore;
      store.getState().setCurrentSession({ Oid: session, name: session });
      store.getState().setCurrentImage(image);
      return { ok: true, has: !!store.getState().currentImage };
    } catch (e: any) {
      return { ok: false, error: String(e) };
    }
  }, { session: SESSION, image: { ...exposure, level: 3 } });
  console.log('[push]', pushResult);

  await page.waitForTimeout(1500);
  await page.screenshot({ path: path.join(SHOTS, '01-after-store-push.png'), fullPage: true });

  const ppTab = page.getByRole('tab', { name: /particle/i }).first();
  if (await ppTab.count() === 0) {
    fs.writeFileSync(path.join(SHOTS, 'console.log'), consoleLog.join('\n'));
    test.skip(true, 'Particle Picking tab still missing after store push');
  }
  await ppTab.click();
  await page.waitForTimeout(800);
  await page.screenshot({ path: path.join(SHOTS, '02-pp-tab.png'), fullPage: true });

  // Dump all visible buttons so we can pick the right Settings.
  const buttonInfo = await page.locator('button:visible').evaluateAll((btns) =>
    btns.map((b) => {
      const r = b.getBoundingClientRect();
      return {
        title: (b as HTMLElement).title,
        ariaLabel: b.getAttribute('aria-label'),
        svgIcon: (b.querySelector('svg') as SVGElement | null)?.getAttribute('data-testid'),
        text: ((b as HTMLElement).innerText || '').slice(0, 40),
        x: Math.round(r.x), y: Math.round(r.y), w: Math.round(r.width), h: Math.round(r.height),
      };
    }),
  );
  fs.writeFileSync(path.join(SHOTS, 'all-buttons.json'), JSON.stringify(buttonInfo, null, 2));

  // The toolbar's Settings IconButton wraps a SettingsIcon SVG (data-testid).
  // The PAGE header also has one — distinguish by y-coordinate (toolbar is
  // far down the page, header is at the very top).
  // Pick the toolbar (lower) one, not the page header (top) one.
  const settingsCandidates = page.locator('button:has(svg[data-testid="SettingsIcon"])');
  const count = await settingsCandidates.count();
  console.log('[settings-candidates]', count);
  for (let i = 0; i < count; i++) {
    const b = settingsCandidates.nth(i);
    const box = await b.boundingBox();
    if (box && box.y > 80) {
      await b.click({ timeout: 4000 }).catch(() => {});
      break;
    }
  }
  await page.waitForTimeout(1500);
  await page.screenshot({ path: path.join(SHOTS, '03-settings-open.png'), fullPage: true });

  // Button text depends on the backend's PREVIEW capability:
  // "Save current image" when canPreview, "Run and save image" otherwise.
  const saveBtn = page.getByRole('button', { name: /save current image|run and save image/i }).first();
  await expect(saveBtn).toBeVisible({ timeout: 15_000 });
  console.log('[ui] clicking Save / Run');
  await saveBtn.click();

  // Wait for the progress bar / "task queued" chip to actually render —
  // the user's bug fires *after* this appears.
  await page.waitForTimeout(2500);
  await page.screenshot({ path: path.join(SHOTS, '04-after-click.png'), fullPage: true });
  const beforeSpeed = await page.evaluate(() => (window as any).__ppRenderCount || 0);
  console.log('[render-count] before speedDial', beforeSpeed);

  // The original stack ended in the SpeedDial. Hover over it to force MUI
  // to mount the SpeedDialAction tree; that's what was in the React stack
  // in the user's report.
  const speedDial = page.locator('[aria-label="Particle picking actions"], button[aria-label*="speed" i]').first();
  if (await speedDial.count() > 0) {
    await speedDial.hover().catch(() => {});
    await page.waitForTimeout(800);
    await speedDial.click().catch(() => {});
    await page.waitForTimeout(800);
  }
  await page.screenshot({ path: path.join(SHOTS, '05-after-speeddial.png'), fullPage: true });

  // Let the socket reconnect cycle thrash for a bit so any re-render
  // amplification has a chance to fire.
  await page.waitForTimeout(8000);
  const afterSpeed = await page.evaluate(() => (window as any).__ppRenderCount || 0);
  console.log('[render-count] after speedDial+wait', afterSpeed);
  await page.screenshot({ path: path.join(SHOTS, '06-final.png'), fullPage: true });
  fs.writeFileSync(path.join(SHOTS, 'console.log'), consoleLog.join('\n'));

  const matches = consoleLog.filter((l) =>
    /Maximum update depth exceeded/i.test(l) ||
    /ImageViewer error/i.test(l),
  );
  const looped = matches.length > 0;
  if (looped) {
    console.log(`[LOOP DETECTED]\n${matches.slice(0, 5).join('\n')}`);
  }
  expect(looped, 'must not produce a Maximum update depth loop').toBeFalsy();
});
