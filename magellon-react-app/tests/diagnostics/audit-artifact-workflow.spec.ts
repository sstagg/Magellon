/**
 * Audit the artifact workflow page (/en/panel/artifacts/:oid).
 *
 * Fetches a real artifact OID from the backend, navigates to the workflow
 * page, and captures the rendered lineage chain. Covers:
 *   - WorkflowChainView renders (not blank, not 500)
 *   - NodeCard structure (kind badge, producer info, Re-run button)
 *   - 404/empty-state path (invalid OID → graceful error message)
 *
 * Run:
 *   pnpm exec playwright test --project=e2e-live tests/e2e/audit-artifact-workflow.spec.ts
 */
import { test, expect } from '@playwright/test';
import { E2E_USERNAME, E2E_PASSWORD } from '../e2e/helpers/credentials';
import fs from 'node:fs';
import path from 'node:path';

const FRONTEND = 'http://localhost:8080';
const BACKEND = 'http://127.0.0.1:8000';
const SHOTS = path.join(process.cwd(), 'tests', 'e2e', 'screenshots', 'audit-artifact-workflow');
fs.mkdirSync(SHOTS, { recursive: true });

async function login(context: any) {
  const auth = await (await fetch(`${BACKEND}/auth/login`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ username: E2E_USERNAME, password: E2E_PASSWORD }),
  })).json();
  await context.addInitScript(({ token, userId, username }: any) => {
    localStorage.setItem('access_token', token);
    localStorage.setItem('currentUser', JSON.stringify({ id: userId, username, active: true, change_password_required: false }));
    localStorage.setItem('currentUserId', userId);
  }, { token: auth.access_token, userId: auth.user_id, username: auth.username });
  return auth.access_token as string;
}

test('audit artifact workflow page — known OID', async ({ page, context }) => {
  test.setTimeout(120_000);
  const token = await login(context);
  const consoleErrors: string[] = [];
  const network: any[] = [];
  page.on('console', (m) => { if (m.type() === 'error') consoleErrors.push(m.text()); });
  page.on('response', async (res) => {
    const u = res.url();
    if (!u.includes('127.0.0.1:8000')) return;
    const e: any = { url: u, status: res.status(), method: res.request().method() };
    if (res.status() >= 400) { try { e.body = (await res.text()).slice(0, 600); } catch {} }
    network.push(e);
  });

  // Resolve a real artifact OID from the server.
  let artifactOid: string | null = null;
  try {
    const resp = await fetch(`${BACKEND}/artifacts?limit=1`, {
      headers: { Authorization: `Bearer ${token}` },
    });
    if (resp.ok) {
      const data = await resp.json();
      artifactOid = (Array.isArray(data) ? data[0]?.oid : data?.items?.[0]?.oid) ?? null;
    }
  } catch {}

  // Record which OID (if any) we resolved.
  fs.writeFileSync(path.join(SHOTS, 'resolved-oid.txt'), artifactOid ?? '(none)');

  if (artifactOid) {
    // 01 — workflow page for the resolved OID
    await page.goto(`${FRONTEND}/en/panel/artifacts/${artifactOid}`, { waitUntil: 'domcontentloaded' });
    await page.waitForLoadState('networkidle').catch(() => {});
    await page.waitForTimeout(3000);
    await page.screenshot({ path: path.join(SHOTS, '01-workflow-loaded.png'), fullPage: true });

    const body = await page.locator('body').innerText();
    fs.writeFileSync(path.join(SHOTS, '01-body.txt'), body.slice(0, 5000));

    // Sanity: page should not show "Something went wrong" or a blank white screen.
    const errorBanners = await page.locator('text=/something went wrong|500|unexpected error/i').count();
    expect(errorBanners, 'Unexpected error banner on valid OID').toBe(0);

    // WorkflowChainView is present when at least one NodeCard renders.
    const nodeCards = await page.locator('[data-testid="workflow-node"], .workflow-node, text=/kind:/i').count();
    fs.writeFileSync(path.join(SHOTS, '01-node-count.txt'), String(nodeCards));

    // 02 — Re-run button visibility
    const rerunCount = await page.locator('button:has-text("Re-run")').count();
    fs.writeFileSync(path.join(SHOTS, '01-rerun-count.txt'), String(rerunCount));

    // 03 — narrow viewport
    await page.setViewportSize({ width: 820, height: 1024 });
    await page.reload({ waitUntil: 'domcontentloaded' });
    await page.waitForTimeout(2000);
    await page.screenshot({ path: path.join(SHOTS, '02-narrow.png'), fullPage: true });

  } else {
    // No artifact on this server yet — just audit the page renders an empty state.
    const sentinelOid = '00000000-0000-0000-0000-000000000000';
    await page.goto(`${FRONTEND}/en/panel/artifacts/${sentinelOid}`, { waitUntil: 'domcontentloaded' });
    await page.waitForLoadState('networkidle').catch(() => {});
    await page.waitForTimeout(2000);
    await page.screenshot({ path: path.join(SHOTS, '01-empty-state.png'), fullPage: true });
  }

  fs.writeFileSync(path.join(SHOTS, 'console-errors.txt'), consoleErrors.join('\n'));
  fs.writeFileSync(path.join(SHOTS, 'network.json'), JSON.stringify(network.slice(-40), null, 2));
});

test('artifact workflow page — invalid OID shows graceful error', async ({ page, context }) => {
  test.setTimeout(60_000);
  await login(context);
  const consoleErrors: string[] = [];
  page.on('console', (m) => { if (m.type() === 'error') consoleErrors.push(m.text()); });

  await page.goto(`${FRONTEND}/en/panel/artifacts/not-a-real-oid`, { waitUntil: 'domcontentloaded' });
  await page.waitForLoadState('networkidle').catch(() => {});
  await page.waitForTimeout(2000);
  await page.screenshot({ path: path.join(SHOTS, '03-invalid-oid.png'), fullPage: true });

  // Should NOT crash to a blank white page — some error UI must be present.
  const bodyText = await page.locator('body').innerText();
  expect(bodyText.trim().length, 'Page body is empty on invalid OID').toBeGreaterThan(10);

  // Must not be an uncaught React error boundary ("Minified React error" or "Something went wrong")
  const hardCrash = await page.locator('text=/Minified React error/i').count();
  expect(hardCrash, 'Uncaught React error on invalid OID').toBe(0);

  fs.writeFileSync(path.join(SHOTS, '03-console-errors.txt'), consoleErrors.join('\n'));
});
