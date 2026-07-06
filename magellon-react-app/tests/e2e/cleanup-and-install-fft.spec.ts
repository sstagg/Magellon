/**
 * UI-driven cleanup: uninstall every orphaned docker plugin (containers
 * were deleted behind Magellon's back) via the trash icon on each card,
 * then install FFT from the hub. Captures screenshots at each step.
 *
 * Run:
 *   $env:MAGELLON_E2E_LIVE=1; $env:MAGELLON_E2E_HUB_INSTALL=1; `
 *     pnpm exec playwright test --project=e2e-live tests/e2e/cleanup-and-install-fft.spec.ts
 */
import { test, expect, type Page } from '@playwright/test';
import { E2E_USERNAME, E2E_PASSWORD } from './helpers/credentials';
import fs from 'node:fs';
import path from 'node:path';

const FRONTEND = 'http://localhost:8080';
const BACKEND = 'http://127.0.0.1:8000';
const USERNAME = E2E_USERNAME;
const PASSWORD = E2E_PASSWORD;
const SHOTS = path.join(process.cwd(), 'tests', 'e2e', 'screenshots', 'cleanup-and-install-fft');
fs.mkdirSync(SHOTS, { recursive: true });

// Orphan plugins from /plugins/db install_method='docker' whose containers
// were deleted (only docker-installed rows; legacy 'discovered' rows
// auto-expire when their bus heartbeat times out).
const ORPHAN_PLUGINS = [
  { name: /BoxNet/, label: 'boxnet-picker' },
  { name: /CTFFIND4/, label: 'ctf' },
  { name: /MotionCor2/, label: 'motioncor' },
  { name: /Ptolemy/, label: 'ptolemy' },
  { name: /Template Picker/, label: 'template-picker' },
  { name: /Topaz/, label: 'topaz' },
];

const shot = async (page: Page, name: string) => {
  const p = path.join(SHOTS, `${name}.png`);
  await page.screenshot({ path: p, fullPage: true });
  console.log(`[shot] ${p}`);
};

const login = async () => {
  const res = await fetch(`${BACKEND}/auth/login`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ username: USERNAME, password: PASSWORD }),
  });
  if (!res.ok) throw new Error(`login failed: ${res.status}`);
  return await res.json() as { access_token: string; user_id: string; username: string };
};

test('uninstall orphan plugins and install FFT from hub', async ({ page, context }) => {
  test.setTimeout(600_000);

  const auth = await login();
  await context.addInitScript(
    ({ token, userId, username }) => {
      localStorage.setItem('access_token', token);
      localStorage.setItem('currentUser', JSON.stringify({ id: userId, username, active: true, change_password_required: false }));
      localStorage.setItem('currentUserId', userId);
    },
    { token: auth.access_token, userId: auth.user_id, username: auth.username },
  );

  // Auto-confirm window.confirm() that Uninstall raises
  page.on('dialog', (d) => d.accept().catch(() => {}));

  await page.setViewportSize({ width: 1440, height: 900 });
  await page.goto(`${FRONTEND}/en/panel/plugins`, { waitUntil: 'domcontentloaded' });
  // Wait for SPA to actually render — vite optimizer can be mid-bundle
  await expect(page.getByRole('heading', { name: 'Plugins' })).toBeVisible({ timeout: 60_000 });
  await expect(page.locator('div.MuiCard-root').filter({ hasText: /CTFFIND4/ })).toBeVisible({ timeout: 30_000 });
  // Let react-query settle the /admin/plugins/.../status calls — needed
  // for the new container-missing alert to render.
  await page.waitForTimeout(6000);
  await shot(page, '01-before-cleanup');

  // Verify Start is now disabled and the container-missing alert appears
  const ctfCard = page.locator('div.MuiCard-root').filter({ hasText: /CTFFIND4/ }).first();
  const startBtn = ctfCard.locator('button[aria-label="start"]').first();
  await expect(startBtn).toBeDisabled({ timeout: 15_000 });
  await expect(ctfCard.locator('[data-testid="container-missing-alert"]')).toBeVisible({ timeout: 8000 });

  // Uninstall each orphan via the trash icon
  for (const orphan of ORPHAN_PLUGINS) {
    const card = page.locator('div.MuiCard-root').filter({ hasText: orphan.name }).first();
    if (await card.count() === 0) {
      console.log(`[skip] no card for ${orphan.label}`);
      continue;
    }
    const uninstallBtn = card.locator('button[aria-label="uninstall"]').first();
    await expect(uninstallBtn).toBeVisible({ timeout: 4000 });
    await uninstallBtn.click();
    // Wait for either success alert or the card to disappear from the list
    await page.waitForFunction(
      (label) => {
        const cards = Array.from(document.querySelectorAll('div.MuiCard-root'));
        return !cards.some((c) => (c.textContent ?? '').match(new RegExp(label, 'i')));
      },
      orphan.label,
      { timeout: 60_000 },
    ).catch(() => {});
    await page.waitForTimeout(500);
  }
  await shot(page, '02-after-cleanup');

  // Now install FFT from the hub
  await page.getByRole('button', { name: /Browse hub/i }).first().click();
  const hubDialog = page.getByRole('dialog', { name: /Browse plugin hub/i });
  await expect(hubDialog).toBeVisible({ timeout: 10_000 });
  await shot(page, '03-hub-open');

  await hubDialog.getByPlaceholder(/Search name/i).fill('fft');
  await page.waitForTimeout(800);
  const fftCard = hubDialog.locator('.MuiCard-root').filter({ hasText: /fft/i }).first();
  await expect(fftCard).toBeVisible({ timeout: 60_000 });
  await shot(page, '04-hub-fft-found');
  await fftCard.getByRole('button', { name: /^Install$/i }).click();

  // Install confirmation dialog opens
  const installDialog = page.getByRole('dialog').filter({ hasText: /plugin_id|install_method/i }).last();
  await expect(installDialog.getByLabel(/Install method/i)).toBeVisible({ timeout: 180_000 });
  await shot(page, '05-install-dialog');
  await installDialog.getByRole('button', { name: /^Install$/i }).click();
  await expect(installDialog.getByText(/fft installed|installed successfully|completed/i)).toBeVisible({
    timeout: 300_000,
  });
  await shot(page, '06-install-complete');
  await installDialog.getByRole('button', { name: /^Close$/i }).click().catch(() => {});

  // Confirm the new FFT card shows up
  await page.waitForTimeout(3000);
  await shot(page, '07-installed-list');
});
