/**
 * One-off audit: docker containers were deleted but DB rows remain.
 * Captures the plugins page state so we can decide how Start should
 * behave when the underlying container is gone.
 *
 * Run:
 *   pnpm exec playwright test --project=e2e-live tests/e2e/orphan-plugins-audit.spec.ts
 */
import { test } from '@playwright/test';
import fs from 'node:fs';
import path from 'node:path';

const FRONTEND = 'http://localhost:8080';
const BACKEND = 'http://127.0.0.1:8000';
const SHOTS = path.join(process.cwd(), 'tests', 'e2e', 'screenshots', 'orphan-plugins');
fs.mkdirSync(SHOTS, { recursive: true });

async function authLocalStorage(context: any) {
  const auth = await (await fetch(`${BACKEND}/auth/login`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ username: 'super', password: 'behd1d2' }),
  })).json();
  await context.addInitScript(({ token, userId, username }: any) => {
    localStorage.setItem('access_token', token);
    localStorage.setItem('currentUser', JSON.stringify({ id: userId, username, active: true, change_password_required: false }));
    localStorage.setItem('currentUserId', userId);
  }, { token: auth.access_token, userId: auth.user_id, username: auth.username });
}

test('audit orphan plugin rows after docker rm', async ({ page, context }) => {
  test.setTimeout(120_000);
  await authLocalStorage(context);

  const network: any[] = [];
  page.on('response', async (res) => {
    const u = res.url();
    if (!u.includes('127.0.0.1:8000')) return;
    const entry: any = { url: u, status: res.status(), method: res.request().method() };
    if (res.status() >= 400) { try { entry.body = (await res.text()).slice(0, 600); } catch {} }
    network.push(entry);
  });

  await page.setViewportSize({ width: 1440, height: 900 });
  await page.goto(`${FRONTEND}/en/panel/plugins`, { waitUntil: 'domcontentloaded' });
  await page.waitForLoadState('networkidle').catch(() => {});
  // Give react-query a moment to settle status calls
  await page.waitForTimeout(5000);
  await page.screenshot({ path: path.join(SHOTS, '01-page.png'), fullPage: true });

  // Enumerate every plugin card with its action button state
  const cards = await page.locator('div.MuiCard-root').evaluateAll((els) =>
    els.map((card: any) => {
      const title = card.querySelector('h6')?.innerText?.trim() ?? null;
      const chips = Array.from(card.querySelectorAll('.MuiChip-root')).map((c: any) => c.innerText?.trim()).filter(Boolean);
      const buttons = Array.from(card.querySelectorAll('button')).map((b: any) => ({
        label: (b.getAttribute('aria-label') || b.innerText || '').trim().slice(0, 40),
        disabled: b.disabled || b.hasAttribute('disabled'),
        title: b.closest('[title]')?.getAttribute('title') ?? b.getAttribute('title') ?? null,
      }));
      return { title, chips, buttons };
    }),
  );
  fs.writeFileSync(path.join(SHOTS, 'cards.json'), JSON.stringify(cards, null, 2));

  // Try clicking the Start (play) button on the ctf plugin card and capture the error
  const ctfCard = page.locator('div.MuiCard-root').filter({ hasText: /CTFFIND4|^ctf$/i }).first();
  const ctfCardExists = await ctfCard.count();
  if (ctfCardExists) {
    const startBtn = ctfCard.locator('button[aria-label="start"]').first();
    const disabled = await startBtn.isDisabled().catch(() => null);
    fs.writeFileSync(path.join(SHOTS, 'ctf-start-disabled.txt'), `disabled=${disabled}\n`);
    if (disabled === false) {
      await startBtn.click({ timeout: 4000 }).catch(() => {});
      await page.waitForTimeout(3000);
      await page.screenshot({ path: path.join(SHOTS, '02-after-clicking-start.png'), fullPage: true });
    }
  }
  fs.writeFileSync(path.join(SHOTS, 'network.json'), JSON.stringify(network, null, 2));
});
