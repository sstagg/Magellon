/**
 * Close-up script: navigate directly to particle picking tab and capture
 * the toolbar with lasso + chip + canvas hover + minimap.
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
    const browser = await chromium.launch({ headless: false, slowMo: 60, executablePath: CHROMIUM_PATH });
    const context = await browser.newContext({ viewport: { width: 1600, height: 900 } });
    const page = await context.newPage();

    // Log console errors
    page.on('console', (m) => {
        if (m.type() === 'error') console.log('[console.error]', m.text().slice(0, 200));
    });

    // Auth
    const res = await fetch(`${BACKEND}/auth/login`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ username: process.env.MAGELLON_E2E_USERNAME || 'super', password: process.env.MAGELLON_E2E_PASSWORD }),
    });
    const auth = await res.json();
    await context.addInitScript(({ token, userId, username }) => {
        localStorage.setItem('access_token', token);
        localStorage.setItem('currentUser', JSON.stringify({ id: userId, username, active: true, change_password_required: false }));
        localStorage.setItem('currentUserId', userId);
    }, { token: auth.access_token, userId: auth.user_id, username: auth.username });

    // Navigate
    await page.goto(`${FRONTEND}/en/panel/images`, { waitUntil: 'networkidle' }).catch(() => {});
    await page.waitForTimeout(2000);

    // Select session
    const combo = page.locator('[role="combobox"]').first();
    await combo.click();
    await page.waitForTimeout(600);
    const opts = page.locator('[role="option"]').filter({ hasNotText: /Select Collection/i });
    if (await opts.count() > 0) { await opts.first().click(); await page.waitForTimeout(2500); }

    // Drill into image: find the first GR-level img in the scrollable image list
    const imgs = page.locator('img');
    const imgCount = await imgs.count();
    console.log('img count:', imgCount);

    // Find an img that's a thumbnail (small, in the left panel list area)
    let selectedImg = null;
    for (let i = 0; i < imgCount; i++) {
        const img = imgs.nth(i);
        const box = await img.boundingBox();
        // Thumbnails are ~80x80 or ~150x150 and far down the page (scrollable list)
        if (box && box.height >= 50 && box.height <= 200 && box.width >= 50) {
            // Skip the atlas thumbnail at top-left (~30x30 region)
            const src = await img.getAttribute('src').catch(() => '');
            if (src && (src.includes('thumbnail') || src.includes('image') || src.includes('gpfs'))) {
                console.log(`img[${i}] box:`, box, 'src:', src.slice(0, 80));
                selectedImg = img;
                break;
            }
        }
    }

    if (!selectedImg) {
        // Just pick any img in page lower region
        for (let i = imgCount - 1; i >= 0; i--) {
            const img = imgs.nth(i);
            const box = await img.boundingBox();
            if (box && box.width > 40) {
                selectedImg = img;
                console.log('fallback img[' + i + ']:', box);
                break;
            }
        }
    }

    if (selectedImg) {
        await selectedImg.scrollIntoViewIfNeeded();
        await selectedImg.click();
        await page.waitForTimeout(3500);
    }

    await page.screenshot({ path: path.join(SHOTS, 'phase1_A_after_click.png') });

    // Click the Particle Picking tab
    let tabEl = null;
    for (const txt of ['Particle Picking', 'Particle', 'Picking']) {
        const t = page.locator(`[role="tab"]:has-text("${txt}")`).first();
        if (await t.isVisible({ timeout: 2000 }).catch(() => false)) {
            tabEl = t;
            break;
        }
    }
    if (tabEl) {
        await tabEl.click();
        await page.waitForTimeout(2500);
        console.log('Clicked Particle Picking tab');
    } else {
        console.log('Tab not found, tabs:', await page.locator('[role="tab"]').allTextContents().catch(() => []));
    }

    // === SCREENSHOT: full tab with toolbar ===
    await page.screenshot({ path: path.join(SHOTS, 'phase1_B_full_particle_tab.png') });
    console.log('Saved phase1_B_full_particle_tab.png');

    // Find the particle-picking toolbar. It's in the right viewer panel.
    // Look for toggle button groups in the right panel.
    const toggleGroups = page.locator('.MuiToggleButtonGroup-root');
    const tgCount = await toggleGroups.count();
    console.log('ToggleButtonGroup count:', tgCount);

    let particleToolbarBox = null;
    for (let i = 0; i < tgCount; i++) {
        const tg = toggleGroups.nth(i);
        const box = await tg.boundingBox();
        const btns = await tg.locator('button').allTextContents();
        console.log(`ToggleGroup[${i}] box:`, box, 'buttons:', btns);
        if (box && box.x > 400) { // right-panel toggle groups
            particleToolbarBox = box;
            break;
        }
    }

    // Also find all chips to locate the "Add [1]" chip
    const chipEls = page.locator('.MuiChip-root');
    const chipCount = await chipEls.count();
    let addChipBox = null;
    for (let i = 0; i < chipCount; i++) {
        const chip = chipEls.nth(i);
        const txt = await chip.textContent().catch(() => '');
        const box = await chip.boundingBox();
        console.log(`chip[${i}]: "${txt}" box:`, box);
        if (txt.includes('Add') && txt.includes('[1]')) {
            addChipBox = box;
        }
    }

    // === SCREENSHOT: toolbar region crop (find a combined bounding box) ===
    if (particleToolbarBox || addChipBox) {
        // Compute a wide clip that covers toolbar + chip
        const clipX = Math.max(0, (particleToolbarBox?.x ?? addChipBox?.x ?? 400) - 20);
        const clipY = Math.max(0, (particleToolbarBox?.y ?? addChipBox?.y ?? 50) - 15);
        const rightEdge = Math.min(1600,
            (addChipBox ? addChipBox.x + addChipBox.width : 0) + 60 ||
            (particleToolbarBox ? particleToolbarBox.x + particleToolbarBox.width : 800) + 200
        );
        const bottomEdge = Math.max(
            particleToolbarBox ? particleToolbarBox.y + particleToolbarBox.height : 0,
            addChipBox ? addChipBox.y + addChipBox.height : 0
        ) + 25;

        await page.screenshot({
            path: path.join(SHOTS, 'phase1_C_toolbar_lasso_chip.png'),
            clip: {
                x: clipX,
                y: clipY,
                width: rightEdge - clipX,
                height: bottomEdge - clipY,
            },
        });
        console.log('Saved phase1_C_toolbar_lasso_chip.png, clip:', { x: clipX, y: clipY, w: rightEdge - clipX, h: bottomEdge - clipY });
    } else {
        // Fallback: grab a wide strip across the top of the viewer panel
        await page.screenshot({
            path: path.join(SHOTS, 'phase1_C_toolbar_lasso_chip.png'),
            clip: { x: 430, y: 55, width: 1160, height: 80 },
        });
    }

    // === Check for canvas and hover ===
    const canvas = page.locator('canvas').first();
    const canvasVisible = await canvas.isVisible().catch(() => false);
    console.log('Canvas visible:', canvasVisible);

    if (canvasVisible) {
        const cbox = await canvas.boundingBox();
        console.log('Canvas box:', cbox);
        const cx = cbox.x + cbox.width / 2;
        const cy = cbox.y + cbox.height / 2;
        await page.mouse.move(cx, cy);
        await page.waitForTimeout(500);
        await page.screenshot({ path: path.join(SHOTS, 'phase1_D_canvas_hover.png') });
        console.log('Saved phase1_D_canvas_hover.png');

        // Zoom in with wheel
        for (let i = 0; i < 10; i++) {
            await page.mouse.wheel(0, -150);
            await page.waitForTimeout(50);
        }
        await page.waitForTimeout(1200);
        await page.screenshot({ path: path.join(SHOTS, 'phase1_E_canvas_zoomed.png') });

        // Bottom-left minimap region
        await page.screenshot({
            path: path.join(SHOTS, 'phase1_F_minimap_corner.png'),
            clip: { x: cbox.x, y: cbox.y + cbox.height - 150, width: 200, height: 150 },
        });
        console.log('Saved minimap corner screenshot');
    } else {
        console.log('No canvas — the image file is probably not accessible from GPFS. Capturing canvas area anyway.');
        // The particle picking tab may show a placeholder
        await page.screenshot({ path: path.join(SHOTS, 'phase1_D_canvas_area.png') });
    }

    // === Summary ===
    const lasso = page.locator('[title*="Lasso"], button:has([data-testid*="asso"])').first();
    console.log('\n--- SUMMARY ---');
    console.log('Particle tab clicked:', !!tabEl);
    console.log('Lasso visible:', await lasso.isVisible().catch(() => false));
    console.log('Add [1] chip box:', addChipBox);
    console.log('Canvas visible:', canvasVisible);
    console.log('All chips:', await page.locator('.MuiChip-root').allTextContents().catch(() => []));

    await browser.close();
}

run().catch((e) => { console.error('[FATAL]', e); process.exit(1); });
