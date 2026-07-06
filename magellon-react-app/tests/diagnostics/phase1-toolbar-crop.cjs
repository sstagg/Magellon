/**
 * Phase 1 toolbar crop — captures precise toolbar row showing lasso + chip.
 */
const { chromium } = require('playwright');
const path = require('path');
const SHOTS = path.join(__dirname, 'screenshots');
const CHROMIUM = 'C:/Users/bkhos.BEHDAD/AppData/Local/ms-playwright/chromium-1223/chrome-win64/chrome.exe';

(async () => {
    const browser = await chromium.launch({ headless: false, executablePath: CHROMIUM, slowMo: 60 });
    const context = await browser.newContext({ viewport: { width: 1600, height: 900 } });
    const page = await context.newPage();

    page.on('console', m => { if (m.type() === 'error') console.log('[ERR]', m.text().slice(0,120)); });

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

    // Click last img (scroll into view first)
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
    console.log('Tabs:', await page.locator('[role="tab"]').allTextContents().catch(() => []));

    // Capture full tab
    await page.screenshot({ path: path.join(SHOTS, 'phase1_D_full_particle_tab.png') });
    console.log('Saved full tab');

    // Find all toggle button groups
    const tgs = page.locator('.MuiToggleButtonGroup-root');
    const tgn = await tgs.count();
    console.log('ToggleButtonGroups:', tgn);
    let particleToolbarBox = null;
    for (let i = 0; i < tgn; i++) {
        const tg = tgs.nth(i);
        const box = await tg.boundingBox();
        const cnt = await tg.locator('button').count();
        console.log(`  TG[${i}] x=${box?.x?.toFixed(0)} y=${box?.y?.toFixed(0)} w=${box?.width?.toFixed(0)} h=${box?.height?.toFixed(0)} btns=${cnt}`);
        // The particle toolbar has many buttons (add/remove/select/move/box/lasso/brush/pan = 8)
        if (box && cnt >= 6) {
            particleToolbarBox = box;
        }
    }

    // Log all tooltip titles to find lasso
    const btns = page.locator('button');
    const bcount = await btns.count();
    for (let i = 0; i < bcount; i++) {
        const btn = btns.nth(i);
        const title = await btn.getAttribute('title').catch(() => '');
        if (title) console.log(`btn[${i}] title="${title}"`);
    }

    // Find chip with "Add [1]"
    const chipEls = page.locator('.MuiChip-root');
    const cn = await chipEls.count();
    let addChipBox = null;
    for (let i = 0; i < cn; i++) {
        const chip = chipEls.nth(i);
        const txt = await chip.textContent().catch(() => '');
        const box = await chip.boundingBox();
        console.log(`chip[${i}]: "${txt}" @`, box?.x?.toFixed(0), box?.y?.toFixed(0));
        if (txt.includes('Add') && txt.includes('1')) addChipBox = box;
    }
    console.log('Add chip box:', addChipBox);

    // Crop the particle toolbar toolbar row
    if (particleToolbarBox) {
        // The row includes: picking record dropdown | tool toggle group | Add[1] chip | undo/redo
        const rowY = particleToolbarBox.y - 10;
        const rowH = particleToolbarBox.height + 20;
        // Start from left of the row (dropdown is to the left of toggle group)
        const rowX = Math.max(430, particleToolbarBox.x - 180);
        const rowW = Math.min(1600 - rowX, 900);

        await page.screenshot({
            path: path.join(SHOTS, 'phase1_E_toolbar_row.png'),
            clip: { x: rowX, y: rowY, width: rowW, height: rowH },
        });
        console.log('Saved toolbar row clip');
    } else {
        // Fallback: try the chip coordinate
        if (addChipBox) {
            await page.screenshot({
                path: path.join(SHOTS, 'phase1_E_toolbar_row.png'),
                clip: { x: 430, y: addChipBox.y - 12, width: 1160, height: 50 },
            });
        }
    }

    // Also get a wider crop showing the whole viewer right panel
    await page.screenshot({
        path: path.join(SHOTS, 'phase1_F_viewer_panel.png'),
        clip: { x: 430, y: 55, width: 1160, height: 840 },
    });
    console.log('Saved viewer panel');

    // Check for canvas in particle picking area
    const canvas = page.locator('canvas');
    const ccount = await canvas.count();
    console.log('canvas elements:', ccount);
    for (let i = 0; i < ccount; i++) {
        const c = canvas.nth(i);
        const box = await c.boundingBox();
        const visible = await c.isVisible().catch(() => false);
        console.log(`canvas[${i}]: visible=${visible} box=`, box);
    }

    await browser.close();
    console.log('Done. Screenshots in:', SHOTS);
})().catch(e => { console.error('[FATAL]', e); process.exit(1); });
