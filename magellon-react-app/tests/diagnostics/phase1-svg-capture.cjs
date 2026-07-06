/**
 * Phase 1 final SVG capture — we know the SVG canvas is at x=932, y=359, w=659, h=532.
 * Capture canvas hover, zoom, and minimap.
 */
const { chromium } = require('playwright');
const path = require('path');
const SHOTS = path.join(__dirname, 'screenshots');
const CHROMIUM = 'C:/Users/bkhos.BEHDAD/AppData/Local/ms-playwright/chromium-1223/chrome-win64/chrome.exe';

(async () => {
    const browser = await chromium.launch({ headless: false, executablePath: CHROMIUM, slowMo: 60 });
    const context = await browser.newContext({ viewport: { width: 1600, height: 900 } });
    const page = await context.newPage();

    // Track image requests to verify which image loads
    const imageRequests = [];
    page.on('request', req => {
        const url = req.url();
        if (url.includes('thumbnail') || url.includes('gpfs') || url.includes('image')) {
            imageRequests.push(url.slice(0, 120));
        }
    });
    page.on('response', resp => {
        const url = resp.url();
        if (url.includes('thumbnail') || url.includes('gpfs') || url.includes('images')) {
            console.log(`[response] ${resp.status()} ${url.slice(0, 100)}`);
        }
    });

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

    // The SVG canvas is at x=932, y=359, w=659, h=532 (from DOM debug)
    // Let's verify this is still the case
    const svgBoxes = await page.evaluate(() => {
        const svgs = document.querySelectorAll('svg');
        return Array.from(svgs).map(svg => {
            const rect = svg.getBoundingClientRect();
            return { w: rect.width, h: rect.height, x: rect.x, y: rect.y,
                     display: window.getComputedStyle(svg).display };
        }).filter(s => s.w > 200);
    });
    console.log('SVG boxes:', JSON.stringify(svgBoxes));

    // Find the particle canvas SVG (right side, x > 800)
    const svgCanvas = svgBoxes.find(s => s.x > 800);
    const cx = svgCanvas ? svgCanvas.x + svgCanvas.w / 2 : 1262;
    const cy = svgCanvas ? svgCanvas.y + svgCanvas.h / 2 : 625;
    const svgX = svgCanvas?.x ?? 932;
    const svgY = svgCanvas?.y ?? 359;
    const svgW = svgCanvas?.w ?? 659;
    const svgH = svgCanvas?.h ?? 532;

    console.log(`Canvas SVG: x=${svgX.toFixed(0)} y=${svgY.toFixed(0)} w=${svgW.toFixed(0)} h=${svgH.toFixed(0)}`);

    // === SCREENSHOT 1: Full particle picking tab ===
    await page.screenshot({
        path: path.join(SHOTS, 'phase1_01_full_particle_picking_tab.png'),
        clip: { x: 430, y: 55, width: 1165, height: 840 },
    });
    console.log('Saved phase1_01_full_particle_picking_tab.png');

    // === SCREENSHOT 2: Toolbar row ===
    // Toolbar is at y≈268-310, from x≈755 to x≈1500
    await page.screenshot({
        path: path.join(SHOTS, 'phase1_02_toolbar_with_chip.png'),
        clip: { x: 755, y: 265, width: 800, height: 50 },
    });
    console.log('Saved phase1_02_toolbar_with_chip.png');

    // === SCREENSHOT 3: Tool toggle group close-up ===
    await page.screenshot({
        path: path.join(SHOTS, 'phase1_03_tool_toggle_group.png'),
        clip: { x: 1060, y: 270, width: 300, height: 44 },
    });
    console.log('Saved phase1_03_tool_toggle_group.png');

    // === SCREENSHOT 4: Canvas area (zoomed normal) ===
    await page.screenshot({
        path: path.join(SHOTS, 'phase1_04_canvas_normal.png'),
        clip: { x: svgX, y: svgY, width: svgW, height: svgH },
    });
    console.log('Saved phase1_04_canvas_normal.png');

    // === SCREENSHOT 5: Hover over canvas center — should show ghost ring ===
    await page.mouse.move(cx, cy);
    await page.waitForTimeout(400);
    await page.screenshot({
        path: path.join(SHOTS, 'phase1_05_canvas_hover.png'),
        clip: { x: svgX, y: svgY, width: svgW, height: svgH },
    });
    console.log('Saved phase1_05_canvas_hover.png');

    // Hover close-up (smaller region around cursor)
    await page.screenshot({
        path: path.join(SHOTS, 'phase1_05b_canvas_hover_closeup.png'),
        clip: { x: cx - 80, y: cy - 80, width: 160, height: 160 },
    });

    // === SCREENSHOT 6: Zoom in via ctrl+= or wheel scroll ===
    // Try keyboard zoom first ('+' key zooms in per the new shortcuts)
    await page.mouse.move(cx, cy);
    await page.mouse.click(cx, cy); // focus the canvas area
    await page.waitForTimeout(200);

    // Press '=' (plus without shift) 6 times to zoom in
    for (let i = 0; i < 6; i++) {
        await page.keyboard.press('Equal');
        await page.waitForTimeout(100);
    }
    await page.waitForTimeout(800);
    await page.screenshot({
        path: path.join(SHOTS, 'phase1_06_canvas_zoomed.png'),
        clip: { x: svgX, y: svgY, width: svgW, height: svgH },
    });
    console.log('Saved phase1_06_canvas_zoomed.png');

    // Check for minimap in bottom-left corner of SVG
    await page.screenshot({
        path: path.join(SHOTS, 'phase1_07_minimap_corner.png'),
        clip: { x: svgX, y: svgY + svgH - 170, width: 200, height: 170 },
    });
    console.log('Saved phase1_07_minimap_corner.png');

    // Check for minimap canvas element
    const minimapInfo = await page.evaluate(() => {
        const canvases = document.querySelectorAll('canvas');
        return Array.from(canvases).map(c => {
            const rect = c.getBoundingClientRect();
            return {
                display: window.getComputedStyle(c).display,
                rect: { x: rect.x, y: rect.y, w: rect.width, h: rect.height },
                w: c.offsetWidth, h: c.offsetHeight,
                parentClass: c.parentElement?.className?.slice(0, 80),
            };
        });
    });
    console.log('Canvas elements after zoom:', JSON.stringify(minimapInfo, null, 2));

    // === Full viewport after zoom ===
    await page.screenshot({ path: path.join(SHOTS, 'phase1_08_full_zoomed.png') });
    console.log('Saved phase1_08_full_zoomed.png');

    // Also try wheel zoom on the SVG
    await page.mouse.move(cx, cy);
    for (let i = 0; i < 5; i++) {
        await page.mouse.wheel(0, -150);
        await page.waitForTimeout(60);
    }
    await page.waitForTimeout(1000);
    await page.screenshot({ path: path.join(SHOTS, 'phase1_09_wheel_zoomed.png') });

    // Minimap corner check after wheel zoom
    const minimapInfo2 = await page.evaluate(() => {
        const canvases = document.querySelectorAll('canvas');
        return Array.from(canvases).map(c => {
            const rect = c.getBoundingClientRect();
            return {
                display: window.getComputedStyle(c).display,
                visible: rect.width > 0,
                rect: { x: Math.round(rect.x), y: Math.round(rect.y), w: Math.round(rect.width), h: Math.round(rect.height) },
            };
        });
    });
    console.log('Canvas elements after wheel zoom:', JSON.stringify(minimapInfo2));

    if (minimapInfo2.some(c => c.visible)) {
        await page.screenshot({
            path: path.join(SHOTS, 'phase1_10_minimap_after_wheel_zoom.png'),
            clip: { x: svgX, y: svgY + svgH - 170, width: 200, height: 170 },
        });
    }

    await page.screenshot({ path: path.join(SHOTS, 'phase1_11_final.png') });

    console.log('\n=== DONE ===\nAll screenshots saved to:', SHOTS);
    await browser.close();
})().catch(e => { console.error('[FATAL]', e); process.exit(1); });
