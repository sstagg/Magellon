/**
 * Diagnose the narrow-viewport break. Logs offsets of likely
 * culprits so we know whether the issue lives in PluginsPageView,
 * the app shell, or the sidebar drawer.
 */
import { test } from '@playwright/test';
import { E2E_USERNAME, E2E_PASSWORD } from './helpers/credentials';
import fs from 'node:fs';
import path from 'node:path';

const FRONTEND = 'http://localhost:8080';
const BACKEND = 'http://127.0.0.1:8000';
const OUT = path.join(process.cwd(), 'tests', 'e2e', 'screenshots', 'audit-plugins-page');

test('diagnose narrow viewport overflow', async ({ page, context }) => {
  test.setTimeout(60_000);

  const auth = await (await fetch(`${BACKEND}/auth/login`, {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ username: E2E_USERNAME, password: E2E_PASSWORD }),
  })).json();
  await context.addInitScript(({ token, userId, username }: any) => {
    localStorage.setItem('access_token', token);
    localStorage.setItem('currentUser', JSON.stringify({ id: userId, username, active: true, change_password_required: false }));
    localStorage.setItem('currentUserId', userId);
  }, { token: auth.access_token, userId: auth.user_id, username: auth.username });

  await page.setViewportSize({ width: 414, height: 900 });
  await page.goto(`${FRONTEND}/en/panel/plugins`, { waitUntil: 'domcontentloaded' });
  await page.waitForLoadState('networkidle').catch(() => {});
  await page.waitForTimeout(3000);

  const info = await page.evaluate(() => {
    const out: any = { viewport: { w: window.innerWidth, h: window.innerHeight }, scroll: { x: window.scrollX, y: window.scrollY } };
    const html = document.documentElement;
    const body = document.body;
    out.html = { scrollW: html.scrollWidth, clientW: html.clientWidth, dir: getComputedStyle(html).direction };
    out.body  = { scrollW: body.scrollWidth,  clientW: body.clientWidth,  dir: getComputedStyle(body).direction };

    // Walk every element. Report ones whose right edge falls outside
    // the viewport — those drag the page wider.
    const offenders: any[] = [];
    const all = body.querySelectorAll<HTMLElement>('*');
    all.forEach((el) => {
      const r = el.getBoundingClientRect();
      if (r.right > window.innerWidth + 1 || r.left < -1) {
        const tag = el.tagName.toLowerCase();
        const cls = (el.className || '').toString().slice(0, 80);
        const cs = getComputedStyle(el);
        offenders.push({
          tag, cls,
          left: Math.round(r.left), right: Math.round(r.right),
          width: Math.round(r.width),
          minWidth: cs.minWidth,
          dir: cs.direction,
          overflowX: cs.overflowX,
        });
      }
    });
    // Dedup and rank by widest.
    offenders.sort((a, b) => b.width - a.width);
    out.offenders = offenders.slice(0, 25);
    return out;
  });

  fs.writeFileSync(path.join(OUT, 'mobile-diagnose.json'), JSON.stringify(info, null, 2));
  console.log('[viewport]', info.viewport, 'html.scrollW =', info.html.scrollW, 'dir =', info.html.dir);
  console.log('[top offenders]');
  for (const o of info.offenders.slice(0, 10)) {
    console.log(' ', o.tag, 'w', o.width, 'left', o.left, 'right', o.right, 'minW', o.minWidth, 'dir', o.dir, ' [', o.cls.slice(0, 60), ']');
  }
});
