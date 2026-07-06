/**
 * Playwright script to capture Phase 1 particle picking UI screenshots.
 * Run with: node tests/e2e/phase1-particle-picking-ui.cjs
 */

const { chromium } = require('playwright');
const fs = require('fs');
const path = require('path');

const FRONTEND = 'http://localhost:8080';
const BACKEND  = 'http://127.0.0.1:8000';
const SHOTS    = path.join(__dirname, 'screenshots');

fs.mkdirSync(SHOTS, { recursive: true });

const CHROMIUM_PATH = 'C:\\Users\\bkhos.BEHDAD\\AppData\\Local\\ms-playwright\\chromium-1223\\chrome-win64\\chrome.exe';

async function run() {
    const browser = await chromium.launch({
        headless: false,
        slowMo: 80,
        executablePath: CHROMIUM_PATH,
    });
    const context = await browser.newContext({ viewport: { width: 1600, height: 900 } });
    const page    = await context.newPage();

    // ── Auth injection ────────────────────────────────────────────────────────
    let token, userId, username;
    try {
        const res = await fetch(`${BACKEND}/auth/login`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ username: process.env.MAGELLON_E2E_USERNAME || 'super', password: process.env.MAGELLON_E2E_PASSWORD }),
        });
        const auth = await res.json();
        token    = auth.access_token;
        userId   = auth.user_id;
        username = auth.username;
        console.log('[auth] logged in as', username);
    } catch (e) {
        console.error('[auth] failed:', e.message);
    }

    if (token) {
        await context.addInitScript(({ token, userId, username }) => {
            localStorage.setItem('access_token', token);
            localStorage.setItem('currentUser', JSON.stringify({
                id: userId, username, active: true, change_password_required: false,
            }));
            localStorage.setItem('currentUserId', userId);
        }, { token, userId, username });
    }

    // ── 1. Navigate to images page ────────────────────────────────────────────
    console.log('[step 1] navigating …');
    await page.goto(`${FRONTEND}/en/panel/images`, { waitUntil: 'networkidle' }).catch(() => {});
    await page.waitForTimeout(2000);
    await page.screenshot({ path: path.join(SHOTS, 'phase1_01_images_page.png') });
    console.log('[step 1] saved');

    // ── 2. Select a session from the dropdown ─────────────────────────────────
    console.log('[step 2] selecting session …');
    const combo = page.locator('[role="combobox"]').first();
    if (await combo.isVisible().catch(() => false)) {
        await combo.click();
        await page.waitForTimeout(800);
        const options = page.locator('[role="option"]').filter({ hasNotText: /Select Collection/i });
        const count = await options.count();
        console.log('[step 2] options:', count);
        if (count > 0) {
            await options.first().click();
            await page.waitForTimeout(3000);
        }
    }
    await page.screenshot({ path: path.join(SHOTS, 'phase1_02_session_selected.png') });

    // ── 3. Click a GR thumbnail (image list at bottom of left panel) ──────────
    console.log('[step 3] clicking a GR-level image thumbnail …');

    // The image list shows cards like "24dec03a_00017gr..." — they have text content.
    // Try clicking any image card that is NOT the atlas navigator region.
    // The thumbnails appear in the lower portion of the left panel.

    // Get all image cards and try one that has "gr" in its text
    let imageClicked = false;

    // Method 1: find cards with "gr" in their label
    const grCards = page.locator('text=/gr/i').first();
    if (await grCards.isVisible().catch(() => false)) {
        await grCards.click();
        imageClicked = true;
        console.log('[step 3] clicked via gr text match');
    }

    if (!imageClicked) {
        // Method 2: find all MuiCard-root elements and pick ones in the lower area
        const allCards = page.locator('.MuiCard-root');
        const cardCount = await allCards.count();
        console.log('[step 3] total MuiCard-root count:', cardCount);

        for (let i = 0; i < cardCount; i++) {
            const card = allCards.nth(i);
            const box = await card.boundingBox();
            // Only click cards in the bottom half of the page (below y=250 on 900px viewport)
            if (box && box.y > 250 && box.width < 300) {
                console.log('[step 3] clicking card at', box);
                await card.click();
                imageClicked = true;
                break;
            }
        }
    }

    await page.waitForTimeout(3000);
    await page.screenshot({ path: path.join(SHOTS, 'phase1_03_after_image_click.png') });
    console.log('[step 3] saved, imageClicked:', imageClicked);

    // ── 4. Look at what tabs are shown now ────────────────────────────────────
    console.log('[step 4] inspecting tabs …');
    const allTabs = await page.locator('[role="tab"]').allTextContents().catch(() => []);
    console.log('[step 4] tabs found:', allTabs);

    const allButtons = await page.locator('button').allTextContents().catch(() => []);
    const particleButtons = allButtons.filter(t => t.toLowerCase().includes('particle'));
    console.log('[step 4] particle-related buttons:', particleButtons);

    // Try to find and click the Particle Picking tab
    let tabClicked = false;
    const tabTexts = ['Particle Picking', 'Particle', 'particle', 'Picking'];
    for (const text of tabTexts) {
        const tab = page.locator(`[role="tab"]:has-text("${text}")`).first();
        if (await tab.isVisible({ timeout: 2000 }).catch(() => false)) {
            console.log('[step 4] found tab:', text);
            await tab.click();
            tabClicked = true;
            break;
        }
    }

    // Also try by button text
    if (!tabClicked) {
        for (const text of tabTexts) {
            const btn = page.locator(`button:has-text("${text}")`).first();
            if (await btn.isVisible({ timeout: 1000 }).catch(() => false)) {
                console.log('[step 4] found button:', text);
                await btn.click();
                tabClicked = true;
                break;
            }
        }
    }

    await page.waitForTimeout(2500);
    await page.screenshot({ path: path.join(SHOTS, 'phase1_04_particle_tab.png') });
    console.log('[step 4] tab clicked:', tabClicked);

    // ── 5. Try to navigate deeper if we see a "HL" level ─────────────────────
    // The image viewer may need several drill-down clicks: GR → SQ → HL → FC
    // Let's check if we need to drill down
    const noImageMsg = await page.locator('text=No Image Selected').isVisible().catch(() => false);
    console.log('[step 5] "No Image Selected" still visible:', noImageMsg);

    if (noImageMsg) {
        console.log('[step 5] trying to find any clickable image thumbnail in list panel …');
        // Dump the page structure to debug
        const bodyHTML = await page.evaluate(() => {
            const leftPanel = document.querySelector('[class*="left"], [class*="panel"], .MuiBox-root');
            return leftPanel ? leftPanel.innerHTML.slice(0, 3000) : document.body.innerHTML.slice(0, 3000);
        });
        console.log('[step 5] page structure sample:', bodyHTML.slice(0, 500));

        // Try clicking images via data attributes or img tags
        const imgs = page.locator('img').filter({ hasNot: page.locator('[alt="logo"]') });
        const imgCount = await imgs.count();
        console.log('[step 5] img elements:', imgCount);

        if (imgCount > 0) {
            // Click the last img (most likely a thumbnail)
            const lastImg = imgs.last();
            const box = await lastImg.boundingBox();
            if (box && box.y > 200) {
                await lastImg.click();
                console.log('[step 5] clicked img at:', box);
                await page.waitForTimeout(3000);
                await page.screenshot({ path: path.join(SHOTS, 'phase1_05_after_img_click.png') });
            }
        }
    }

    // ── 6. Now find the particle picking tab after any image is loaded ────────
    console.log('[step 6] looking for particle picking tab after image load …');
    const allTabsNow = await page.locator('[role="tab"]').allTextContents().catch(() => []);
    console.log('[step 6] tabs now:', allTabsNow);

    // Re-check for the tab
    if (!tabClicked) {
        for (const text of ['Particle Picking', 'Particle', 'Picking']) {
            const tab = page.locator(`[role="tab"]:has-text("${text}")`).first();
            if (await tab.isVisible({ timeout: 2000 }).catch(() => false)) {
                await tab.click();
                tabClicked = true;
                console.log('[step 6] clicked tab:', text);
                break;
            }
        }
    }

    await page.waitForTimeout(2500);
    await page.screenshot({ path: path.join(SHOTS, 'phase1_06_particle_tab_attempt2.png') });

    // ── 7. Check for toolbar elements ─────────────────────────────────────────
    console.log('[step 7] checking toolbar elements …');

    // All toggle buttons (tool buttons in the toolbar)
    const toggleBtns = await page.locator('[role="group"] button, .MuiToggleButtonGroup-root button').allTextContents().catch(() => []);
    console.log('[step 7] toggle buttons:', toggleBtns);

    // All MUI chips
    const allChips = await page.locator('.MuiChip-root').allTextContents().catch(() => []);
    console.log('[step 7] all chips:', allChips);

    // Lasso button specifically
    const lassoBtn = page.locator('[title*="Lasso"], [aria-label*="Lasso"], button:has-text("Lasso")').first();
    const lassoVisible = await lassoBtn.isVisible().catch(() => false);
    console.log('[step 7] lasso button visible:', lassoVisible);

    // Check for canvas
    const canvasEl = page.locator('canvas').first();
    const canvasVisible = await canvasEl.isVisible().catch(() => false);
    console.log('[step 7] canvas visible:', canvasVisible);

    // ── 8. Full page screenshot to see whatever is visible ────────────────────
    await page.screenshot({ path: path.join(SHOTS, 'phase1_07_full_state.png'), fullPage: true });

    // ── 9. If canvas is visible, take targeted shots ──────────────────────────
    if (canvasVisible) {
        const canvasBox = await canvasEl.boundingBox();
        console.log('[step 9] canvas box:', canvasBox);

        // Hover over center of canvas
        if (canvasBox) {
            const cx = canvasBox.x + canvasBox.width / 2;
            const cy = canvasBox.y + canvasBox.height / 2;
            await page.mouse.move(cx, cy);
            await page.waitForTimeout(600);
            await page.screenshot({ path: path.join(SHOTS, 'phase1_08_canvas_hover.png') });
            console.log('[step 9] canvas hover screenshot saved');

            // Zoom in 8x via wheel scroll at canvas center
            await page.mouse.move(cx, cy);
            for (let i = 0; i < 8; i++) {
                await page.mouse.wheel(0, -120);
                await page.waitForTimeout(60);
            }
            await page.waitForTimeout(1000);
            await page.screenshot({ path: path.join(SHOTS, 'phase1_09_canvas_zoomed.png') });

            // Check minimap in bottom-left corner of canvas
            const minimapClip = {
                x: Math.max(0, canvasBox.x),
                y: Math.max(0, canvasBox.y + canvasBox.height - 140),
                width: 200,
                height: 140,
            };
            await page.screenshot({ path: path.join(SHOTS, 'phase1_10_minimap_corner.png'), clip: minimapClip });
            console.log('[step 9] minimap corner screenshot saved');
        }
    }

    // ── 10. Toolbar region crop ───────────────────────────────────────────────
    // Find the toolbar by looking for toggle button groups
    const toolbarEl = page.locator('.MuiToggleButtonGroup-root').first();
    if (await toolbarEl.isVisible().catch(() => false)) {
        const box = await toolbarEl.boundingBox();
        if (box) {
            // Expand region to include chip next to the toggle group
            await page.screenshot({
                path: path.join(SHOTS, 'phase1_11_toolbar_crop.png'),
                clip: {
                    x: Math.max(0, box.x - 10),
                    y: Math.max(0, box.y - 10),
                    width: Math.min(1600, box.width + 300), // include chip to the right
                    height: box.height + 20,
                },
            });
            console.log('[step 10] toolbar crop saved, box:', box);
        }
    }

    console.log('\n[SUMMARY]');
    console.log('  tabClicked:', tabClicked);
    console.log('  lassoVisible:', lassoVisible);
    console.log('  canvasVisible:', canvasVisible);
    console.log('  allChips:', allChips);
    console.log('  Screenshots in:', SHOTS);

    await browser.close();
}

run().catch((err) => {
    console.error('[FATAL]', err);
    process.exit(1);
});
