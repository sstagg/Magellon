import { test, expect, Page } from '@playwright/test';
import fs from 'node:fs';
import path from 'node:path';

const FRONTEND = 'http://localhost:8080';
const BACKEND = 'http://127.0.0.1:8000';
const SANDBOX = 'C:/projects/Magellon/Sandbox/magellon_template_picker';
const SHOTS = path.join(process.cwd(), 'tests', 'e2e', 'screenshots');
fs.mkdirSync(SHOTS, { recursive: true });

const USERNAME = 'super';
const PASSWORD = 'behd1d2';

const shot = async (page: Page, name: string) => {
  const p = path.join(SHOTS, `${name}.png`);
  await page.screenshot({ path: p, fullPage: true });
  console.log(`[shot] ${p}`);
};

type NetworkEntry = {
  url: string;
  status: number;
  method: string;
  body?: string;
};

test('submit template-picker job and capture real error', async ({ page, context }) => {
  test.setTimeout(240_000);

  const consoleErrors: string[] = [];
  const pageErrors: string[] = [];
  const network: NetworkEntry[] = [];

  page.on('console', (msg) => {
    if (msg.type() === 'error') consoleErrors.push(msg.text());
  });
  page.on('pageerror', (err) => pageErrors.push(String(err)));
  page.on('response', async (res) => {
    const url = res.url();
    if (!url.includes('127.0.0.1:8000') && !url.includes('localhost:8000')) return;
    const entry: NetworkEntry = {
      url,
      status: res.status(),
      method: res.request().method(),
    };
    if (res.status() >= 400) {
      try {
        entry.body = (await res.text()).slice(0, 3000);
      } catch {
        entry.body = '<unreadable>';
      }
    }
    network.push(entry);
  });

  // 1. Get token via API and seed localStorage
  const auth = await (await fetch(`${BACKEND}/auth/login`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ username: USERNAME, password: PASSWORD }),
  })).json();
  console.log('[auth] user_id =', auth.user_id);

  await context.addInitScript(
    ({ token, userId, username }) => {
      const user = { id: userId, username, active: true, change_password_required: false };
      localStorage.setItem('access_token', token);
      localStorage.setItem('currentUser', JSON.stringify(user));
      localStorage.setItem('currentUserId', userId);
    },
    { token: auth.access_token, userId: auth.user_id, username: auth.username },
  );

  // 2. Navigate to the plugin runner
  await page.goto(`${FRONTEND}/en/panel/plugins/pp/template-picker`, {
    waitUntil: 'networkidle',
  });
  await page.waitForTimeout(2000);
  await shot(page, '01-plugin-runner');

  // 3. Pick image
  await page.getByRole('button', { name: /pick test image/i }).click();
  await page.waitForTimeout(600);
  await page.getByLabel(/^path$/i).fill(SANDBOX);
  await page.locator('button').filter({ hasText: /^Go$/ }).click();
  await page.waitForTimeout(1500);
  await shot(page, '02-image-picker');

  await page.getByText('24may23b_a_00044gr_00009sq_v01_00004hl_00006ex.mrc', { exact: true }).click();
  await page.waitForTimeout(300);
  await page.getByRole('button', { name: /use this image/i }).click();
  await page.waitForTimeout(1500);
  await shot(page, '03-image-confirmed');

  // 4. Pick templates
  await page.getByRole('button', { name: /pick templates/i }).click();
  await page.waitForTimeout(800);
  await page.getByLabel(/^path$/i).fill(SANDBOX);
  await page.locator('button').filter({ hasText: /^Go$/ }).click();
  await page.waitForTimeout(1500);

  for (const name of ['origTemplate1.mrc', 'origTemplate2.mrc', 'origTemplate3.mrc']) {
    await page.getByText(name, { exact: true }).click();
    await page.waitForTimeout(200);
  }
  await shot(page, '04-templates-selected');

  await page.getByRole('button', { name: /use \d+ file/i }).click();
  await page.waitForTimeout(1500);
  await shot(page, '05-templates-confirmed');

  // 5. Submit
  const runBtn = page.getByRole('button', { name: /^run(?! plugin)$|run plugin|submit|start run/i }).first();
  await runBtn.click();
  await page.waitForTimeout(3000);
  await shot(page, '06-just-after-run');

  // Wait up to 60s for the job chip / status to flip to completed
  for (let i = 0; i < 60; i++) {
    const bodyText = await page.locator('body').innerText();
    if (/completed|found \d+ particles|particles found|0 particles|\bDone\b/i.test(bodyText)) break;
    await page.waitForTimeout(1000);
  }
  await shot(page, '07-final-state');

  // Close-up of the preview pane to verify overlay alignment
  const previewBox = page.locator('img[alt="Test image preview"]').first();
  if (await previewBox.count()) {
    await previewBox.scrollIntoViewIfNeeded();
    const box = await previewBox.boundingBox();
    if (box) {
      await page.screenshot({
        path: path.join(SHOTS, '08-overlay-closeup.png'),
        clip: {
          x: Math.max(0, box.x - 8),
          y: Math.max(0, box.y - 8),
          width: box.width + 16,
          height: box.height + 16,
        },
      });
      console.log('[shot] 08-overlay-closeup.png');
    }
  }

  // 6. Dump everything we captured
  const alerts = await page.locator('.MuiAlert-message, [role="alert"]').allTextContents();
  const report = {
    auth: { user_id: auth.user_id, username: auth.username },
    consoleErrors,
    pageErrors,
    alerts,
    network: network.slice(-60),
  };
  fs.writeFileSync(path.join(SHOTS, 'report.json'), JSON.stringify(report, null, 2));
  console.log('[report]', JSON.stringify(report, null, 2));
});
