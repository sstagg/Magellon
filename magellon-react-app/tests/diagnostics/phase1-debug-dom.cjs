/**
 * Debug the DOM structure of the particle picking tab content.
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

    // Debug: what does the tab panel area contain?
    const tabPanelInfo = await page.evaluate(() => {
        // Find the active tab panel
        const tabPanels = document.querySelectorAll('[role="tabpanel"]');
        const results = [];
        for (const panel of tabPanels) {
            if (panel.hidden || panel.getAttribute('aria-hidden') === 'true') continue;
            const rect = panel.getBoundingClientRect();
            const children = Array.from(panel.children).map(c => ({
                tag: c.tagName,
                class: c.className.slice(0, 80),
                rect: c.getBoundingClientRect(),
            }));
            results.push({
                id: panel.id,
                rect,
                childCount: panel.children.length,
                children: children.slice(0, 5),
                innerHTML: panel.innerHTML.slice(0, 500),
            });
        }
        return results;
    });
    console.log('Tab panels:', JSON.stringify(tabPanelInfo, null, 2).slice(0, 3000));

    // Look for SVG elements (ParticleCanvas uses SVG)
    const svgInfo = await page.evaluate(() => {
        const svgs = document.querySelectorAll('svg');
        return Array.from(svgs).map(svg => ({
            class: svg.className?.baseVal?.slice(0, 60) || '',
            display: window.getComputedStyle(svg).display,
            visibility: window.getComputedStyle(svg).visibility,
            rect: svg.getBoundingClientRect(),
            width: svg.getAttribute('width'),
            height: svg.getAttribute('height'),
        })).filter(s => s.rect.width > 50);
    });
    console.log('\nSVG elements with width > 50:', JSON.stringify(svgInfo, null, 2));

    // Explore what the particle picking tab actually shows
    const particleTabContent = await page.evaluate(() => {
        // Find elements that might be the particle canvas or its container
        const candidates = document.querySelectorAll('[class*="particle"], [class*="Particle"], [class*="canvas"], [class*="Canvas"]');
        return Array.from(candidates).map(el => ({
            tag: el.tagName,
            class: el.className.slice(0, 80),
            display: window.getComputedStyle(el).display,
            rect: el.getBoundingClientRect(),
        })).slice(0, 10);
    });
    console.log('\nParticle/Canvas class elements:', JSON.stringify(particleTabContent, null, 2));

    // Check the imageUrl that ParticleCanvas receives by looking at network calls
    const imageRequests = [];
    page.on('request', req => {
        if (req.url().includes('thumbnail') || req.url().includes('image') || req.url().includes('gpfs')) {
            imageRequests.push({ url: req.url().slice(0, 100), method: req.method() });
        }
    });

    // Wait a bit more to capture any lazy requests
    await page.waitForTimeout(2000);

    // Screenshot of what we see
    await page.screenshot({ path: path.join(SHOTS, 'phase1_Z_debug.png') });

    // Look for the image URL in component state via React fiber
    const imageUrlFromReact = await page.evaluate(() => {
        // Walk fiber tree to find imageUrl prop
        function findProp(fiber, propName, depth = 0) {
            if (!fiber || depth > 50) return null;
            if (fiber.memoizedProps && fiber.memoizedProps[propName]) {
                return fiber.memoizedProps[propName];
            }
            return findProp(fiber.child, propName, depth + 1) || findProp(fiber.sibling, propName, depth + 1);
        }

        // Get root fiber
        const rootEl = document.getElementById('root');
        if (!rootEl) return 'no root element';
        const fiberKey = Object.keys(rootEl).find(k => k.startsWith('__reactFiber') || k.startsWith('__reactInternalInstance'));
        if (!fiberKey) return 'no fiber key found';
        const fiber = rootEl[fiberKey];
        return findProp(fiber, 'imageUrl');
    });
    console.log('\nimageUrl from React fiber:', imageUrlFromReact);

    await browser.close();
})().catch(e => { console.error('[FATAL]', e); process.exit(1); });
