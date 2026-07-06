/**
 * Verify lasso button presence by checking tooltip text.
 */
const { chromium } = require('playwright');
const path = require('path');
const SHOTS = path.join(__dirname, 'screenshots');
const CHROMIUM = 'C:/Users/bkhos.BEHDAD/AppData/Local/ms-playwright/chromium-1223/chrome-win64/chrome.exe';

(async () => {
    const browser = await chromium.launch({ headless: false, executablePath: CHROMIUM, slowMo: 60 });
    const context = await browser.newContext({ viewport: { width: 1600, height: 900 } });
    const page = await context.newPage();

    const res = await fetch('http://127.0.0.1:8000/auth/login', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ username: process.env.MAGELLON_E2E_USERNAME || 'super', password: process.env.MAGELLON_E2E_PASSWORD }),
    });
    const auth = await res.json();
    await context.addInitScript(({ token, userId, username }) => {
        localStorage.setItem('access_token', token);
        localStorage.setItem('currentUser', JSON.stringify({ id: userId, username, active: true, change_password_required: false }));
        localStorage.setItem('currentUserId', userId);
    }, { token: auth.access_token, userId: auth.user_id, username: auth.username });

    await page.goto('http://localhost:8080/en/panel/images', { waitUntil: 'networkidle' }).catch(() => {});
    await page.waitForTimeout(2000);

    // Select session
    const combo = page.locator('[role="combobox"]').first();
    await combo.click();
    await page.waitForTimeout(600);
    const opts = page.locator('[role="option"]').filter({ hasNotText: /Select Collection/i });
    if (await opts.count() > 0) { await opts.first().click(); await page.waitForTimeout(3000); }

    // Click last img
    const imgs = page.locator('img');
    const n = await imgs.count();
    for (let i = n - 1; i >= 0; i--) {
        const img = imgs.nth(i);
        const box = await img.boundingBox();
        if (box && box.width > 40) {
            await img.scrollIntoViewIfNeeded();
            await img.click();
            await page.waitForTimeout(4000);
            break;
        }
    }

    // Click Particle Picking tab
    const tab = page.locator('[role="tab"]:has-text("Particle Picking")').first();
    if (await tab.isVisible({ timeout: 3000 }).catch(() => false)) {
        await tab.click();
        await page.waitForTimeout(3000);
    }

    // Find all buttons in the toggle group and check their tooltips
    // The particle tool toggle group has 8 buttons; hover each to read tooltip
    const particleTG = page.locator('.MuiToggleButtonGroup-root').nth(2); // TG[2] is the particle toolbar
    const tgBox = await particleTG.boundingBox();
    console.log('Particle ToggleGroup box:', tgBox);

    const btns = particleTG.locator('button');
    const count = await btns.count();
    console.log('Button count in TG[2]:', count);

    for (let i = 0; i < count; i++) {
        const btn = btns.nth(i);
        const box = await btn.boundingBox();
        const val = await btn.getAttribute('value').catch(() => '');
        const ariaLabel = await btn.getAttribute('aria-label').catch(() => '');

        // Hover to trigger tooltip
        if (box) {
            await page.mouse.move(box.x + box.width / 2, box.y + box.height / 2);
            await page.waitForTimeout(400);

            // Read tooltip if it appears
            const tooltip = page.locator('[role="tooltip"]');
            const tooltipText = await tooltip.textContent({ timeout: 500 }).catch(() => '');
            console.log(`btn[${i}] value="${val}" ariaLabel="${ariaLabel}" tooltip="${tooltipText}"`);
        }
    }

    // Hover the lasso button and screenshot
    const lassoBtn = page.locator('[value="lasso"]');
    if (await lassoBtn.isVisible().catch(() => false)) {
        const box = await lassoBtn.boundingBox();
        if (box) {
            await page.mouse.move(box.x + box.width / 2, box.y + box.height / 2);
            await page.waitForTimeout(600);
            await page.screenshot({
                path: path.join(SHOTS, 'phase1_lasso_hover_tooltip.png'),
                clip: { x: Math.max(0, box.x - 30), y: Math.max(0, box.y - 50), width: 200, height: 100 },
            });
            console.log('Saved lasso hover screenshot');
        }
    }

    // Click lasso button and verify chip changes
    const lassoBtnEl = page.locator('[value="lasso"]');
    if (await lassoBtnEl.isVisible().catch(() => false)) {
        await lassoBtnEl.click();
        await page.waitForTimeout(600);
        const chips = await page.locator('.MuiChip-root').allTextContents();
        console.log('Chips after clicking lasso:', chips);
        await page.screenshot({
            path: path.join(SHOTS, 'phase1_lasso_active_chip.png'),
            clip: { x: 755, y: 265, width: 800, height: 50 },
        });
        console.log('Saved lasso active chip screenshot');
    }

    await browser.close();
})().catch(e => { console.error('[FATAL]', e); process.exit(1); });
