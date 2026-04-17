import { test, expect } from '@playwright/test';
import fs from 'node:fs';
import path from 'node:path';

const FRONTEND = 'http://localhost:8080';
const BACKEND = 'http://127.0.0.1:8000';
const IMAGES_DIR = 'C:/magellon/gpfs/images';
const SHOTS = path.join(process.cwd(), 'tests', 'e2e', 'screenshots', 'fft-batch-flow');
fs.mkdirSync(SHOTS, { recursive: true });

test('FFT batch: dispatch 4 images, watch lifecycle, then check pipeline-health', async ({ page, context }) => {
    test.setTimeout(180_000);

    const consoleErrors: string[] = [];
    const stepEventTraffic: string[] = [];
    page.on('console', (m) => {
        if (m.type() === 'error') consoleErrors.push(m.text());
    });
    page.on('framenavigated', (f) => console.log('[nav]', f.url()));
    page.on('websocket', (ws) => {
        ws.on('framereceived', (f) => {
            if (typeof f.payload === 'string' && f.payload.includes('step_event')) {
                stepEventTraffic.push(f.payload.slice(0, 200));
            }
        });
    });

    // 1. Auth — match the existing e2e harness pattern (super/behd1d2)
    const auth = await (await fetch(`${BACKEND}/auth/login`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ username: 'super', password: 'behd1d2' }),
    })).json();
    expect(auth.access_token, 'login should return access_token').toBeTruthy();

    await context.addInitScript(
        ({ token, userId, username }) => {
            localStorage.setItem('access_token', token);
            localStorage.setItem('currentUser', JSON.stringify({ id: userId, username, active: true, change_password_required: false }));
            localStorage.setItem('currentUserId', userId);
        },
        { token: auth.access_token, userId: auth.user_id, username: auth.username },
    );

    // 2. Confirm output dir is empty before dispatch
    const beforePngs = fs.readdirSync(IMAGES_DIR).filter((f) => f.endsWith('.png'));
    expect(beforePngs.length, 'no PNGs should exist before dispatch').toBe(0);

    // 3. Open the FFT test page
    await page.goto(`${FRONTEND}/en/panel/dev/fft-test`);
    await expect(page.getByRole('heading', { name: 'FFT plugin test bed' })).toBeVisible();
    await page.screenshot({ path: path.join(SHOTS, '01-page-loaded.png'), fullPage: true });

    // 4. Switch to batch mode
    await page.getByLabel('Batch dispatch (one job, N tasks)').click();
    await expect(page.getByRole('button', { name: /Pick images/ })).toBeVisible();

    // 5. Open picker dialog
    await page.getByRole('button', { name: /Pick images/ }).click();
    await expect(page.getByRole('dialog')).toBeVisible();
    await page.screenshot({ path: path.join(SHOTS, '02-picker-open.png'), fullPage: true });

    // 6. Navigate to the images directory
    const pathField = page.getByRole('dialog').getByLabel('Path');
    await pathField.fill(IMAGES_DIR);
    await pathField.press('Enter');

    // Wait for the listing to load — the 4 .mrc files should appear
    await expect(page.getByRole('dialog').getByText(/image1_.+\.mrc/)).toBeVisible({ timeout: 10_000 });
    await page.screenshot({ path: path.join(SHOTS, '03-picker-listed.png'), fullPage: true });

    // 7. Click each .mrc to select (multi-select via Checkbox in the row)
    const mrcRows = page.getByRole('dialog').getByRole('button').filter({ hasText: /\.mrc/ });
    const count = await mrcRows.count();
    console.log(`Found ${count} .mrc rows in picker`);
    expect(count, 'expected 4 .mrc files in C:/magellon/gpfs/images').toBeGreaterThanOrEqual(4);

    for (let i = 0; i < count; i++) {
        await mrcRows.nth(i).click();
    }
    await expect(page.getByText(`${count} file(s) selected`)).toBeVisible();
    await page.screenshot({ path: path.join(SHOTS, '04-picker-selected.png'), fullPage: true });

    // 8. Confirm picker
    await page.getByRole('dialog').getByRole('button', { name: /Use \d+ file/ }).click();
    await expect(page.getByText(`${count} images selected`)).toBeVisible();
    await page.screenshot({ path: path.join(SHOTS, '05-chips-shown.png'), fullPage: true });

    // 9. Dispatch
    const dispatchBtn = page.getByRole('button', { name: 'Dispatch FFT' });
    await dispatchBtn.click();

    // Wait for the Tasks panel to appear (DispatchTrace)
    await expect(page.getByRole('heading', { name: 'Tasks' })).toBeVisible({ timeout: 15_000 });
    await page.screenshot({ path: path.join(SHOTS, '06-tasks-queued.png'), fullPage: true });

    // 10. Wait for at least one "completed" chip to appear in the Tasks panel.
    // FFT on a 4k MRC takes ~1-3s per image; allow 60s for the whole batch.
    const completedChip = page.locator('.MuiChip-colorSuccess').filter({ hasText: 'completed' });
    await expect(completedChip.first()).toBeVisible({ timeout: 60_000 });

    // Wait until all 4 are completed (or the deadline lapses)
    await page.waitForFunction(
        (expected) => {
            const chips = Array.from(document.querySelectorAll('.MuiChip-label'));
            const done = chips.filter((c) => c.textContent === 'completed').length;
            return done >= expected;
        },
        count,
        { timeout: 90_000 },
    );
    await page.screenshot({ path: path.join(SHOTS, '07-tasks-done.png'), fullPage: true });

    // 11. Scroll the Tasks panel into view + screenshot the per-task lifecycle
    await page.getByRole('heading', { name: 'Tasks' }).scrollIntoViewIfNeeded();
    await page.waitForTimeout(500);
    await page.screenshot({ path: path.join(SHOTS, '08-tasks-panel.png'), fullPage: true });

    // 12. Navigate to Pipeline Health
    await page.goto(`${FRONTEND}/en/panel/admin/pipeline-health`);
    await expect(page.getByRole('heading', { name: 'Pipeline Health' })).toBeVisible();
    // Let it poll once
    await page.waitForTimeout(2000);
    await page.screenshot({ path: path.join(SHOTS, '09-pipeline-health.png'), fullPage: true });

    // 13. Verify the FFT plugin shows in the Plugin Liveness table
    await expect(page.getByText('FFT Plugin')).toBeVisible({ timeout: 20_000 });

    // 14. Verify PNGs were created on disk
    const afterPngs = fs.readdirSync(IMAGES_DIR).filter((f) => f.endsWith('.png'));
    console.log(`PNGs created: ${afterPngs.length}`, afterPngs);
    expect(afterPngs.length, 'each input MRC should have produced an FFT PNG').toBeGreaterThanOrEqual(count);

    // 15. Diagnostics
    fs.writeFileSync(path.join(SHOTS, 'console-errors.json'), JSON.stringify(consoleErrors, null, 2));
    fs.writeFileSync(path.join(SHOTS, 'step-events-on-wire.json'), JSON.stringify(stepEventTraffic, null, 2));
    console.log(`Captured ${stepEventTraffic.length} step_event websocket frames`);
    console.log(`Console errors: ${consoleErrors.length}`);
});
