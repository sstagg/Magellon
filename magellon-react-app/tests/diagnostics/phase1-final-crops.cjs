/**
 * Phase 1 final crops — get clean isolated shots of each UI element.
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

    // === SCREENSHOT 1: Full particle picking tab (wide viewer) ===
    await page.screenshot({
        path: path.join(SHOTS, 'phase1_01_full_particle_picking_tab.png'),
        clip: { x: 430, y: 55, width: 1165, height: 840 },
    });

    // === SCREENSHOT 2: Toolbar row — tight crop of tool group + chip ===
    // TG[2] (particle tools) is at x=1067, y=280, w=222, h=28
    // Add [1] chip is at x=1297, y=284, w=49, h=20
    // Show from the picking record dropdown (~x=755) to end of chip (~x=1355) + undo buttons
    await page.screenshot({
        path: path.join(SHOTS, 'phase1_02_toolbar_with_chip.png'),
        clip: { x: 755, y: 268, width: 680, height: 46 },
    });

    // === SCREENSHOT 3: Just the toggle group (lasso button area) ===
    // x=1067, y=280, w=222, h=28 — zoom in on this
    await page.screenshot({
        path: path.join(SHOTS, 'phase1_03_tool_toggle_group.png'),
        clip: { x: 1060, y: 272, width: 295, height: 42 },
    });

    // === SCREENSHOT 4: Tab row + toolbar row together ===
    await page.screenshot({
        path: path.join(SHOTS, 'phase1_04_tab_and_toolbar.png'),
        clip: { x: 430, y: 225, width: 1165, height: 100 },
    });

    // Now check for the canvas (may be loaded once viewer panel renders)
    const canvas = page.locator('canvas');
    const ccount = await canvas.count();
    console.log('canvas count:', ccount);

    // The viewer image is probably shown as an img tag, not canvas
    // Let's see what's in the right panel
    const imgEls = page.locator('img');
    const imgn = await imgEls.count();
    for (let i = 0; i < imgn; i++) {
        const img = imgEls.nth(i);
        const box = await img.boundingBox();
        if (box && box.x > 430 && box.width > 200) {
            const src = await img.getAttribute('src').catch(() => '');
            console.log(`viewer img[${i}]: x=${box.x.toFixed(0)} y=${box.y.toFixed(0)} w=${box.width.toFixed(0)} h=${box.height.toFixed(0)} src=${src.slice(0,60)}`);
        }
    }

    // Try to find the canvas/particle area by looking at the right panel
    // The particle canvas is a React canvas component. It may be hidden if image didn't load.
    // Let's see what's at the coordinates where the particle tab content should be.
    const elementAt = await page.evaluate(() => {
        // Check around y=400-800, x=800-1600 for the canvas
        for (let y = 400; y < 850; y += 50) {
            for (let x = 850; x < 1600; x += 100) {
                const el = document.elementFromPoint(x, y);
                if (el && el.tagName === 'CANVAS') {
                    return { tag: el.tagName, id: el.id, class: el.className, x, y,
                        w: el.offsetWidth, h: el.offsetHeight,
                        rect: el.getBoundingClientRect() };
                }
            }
        }
        return null;
    });
    console.log('Canvas element from evaluate:', elementAt);

    // Check if there's a particle canvas hidden under a loading spinner
    const allEls = await page.evaluate(() => {
        const canvases = document.querySelectorAll('canvas');
        return Array.from(canvases).map(c => ({
            id: c.id, class: c.className.slice(0, 60),
            w: c.offsetWidth, h: c.offsetHeight,
            display: window.getComputedStyle(c).display,
            visibility: window.getComputedStyle(c).visibility,
            rect: c.getBoundingClientRect(),
        }));
    });
    console.log('All canvases in DOM:', JSON.stringify(allEls, null, 2));

    // The micrograph image is shown as an <img>, let's find it in the viewer
    const viewerImg = await page.evaluate(() => {
        const imgs = document.querySelectorAll('img');
        const results = [];
        for (const img of imgs) {
            const rect = img.getBoundingClientRect();
            if (rect.x > 430 && rect.width > 100) {
                results.push({ src: img.src.slice(0, 80), x: rect.x, y: rect.y, w: rect.width, h: rect.height });
            }
        }
        return results;
    });
    console.log('Viewer imgs:', JSON.stringify(viewerImg));

    // === SCREENSHOT 5: Final overview ===
    await page.screenshot({ path: path.join(SHOTS, 'phase1_05_overview.png') });

    console.log('\nAll phase1 screenshots saved to:', SHOTS);
    await browser.close();
})().catch(e => { console.error('[FATAL]', e); process.exit(1); });
