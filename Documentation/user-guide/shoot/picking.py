"""Screenshots of automatic particle picking. THIS SAVES A PICKING RECORD on
GUIDE_PICK_IMAGE in the EPU session. Run it while the Leginon import from
imports.py is still running, so the Jobs panel shows an import chip too.
"""
from lib import *


def drawer_text(page):
    return page.locator(".MuiDrawer-paper").last.inner_text()


def wait_for(page, done, tries=40):
    for _ in range(tries):
        time.sleep(4)
        text = drawer_text(page)
        if done(text) or "failed" in text.lower():
            return


with sync_playwright() as p:
    b, page = open_page(p)

    def picking():
        open_image(page, EPU_SESSION, PICK_IMAGE)
        page.get_by_role("tab", name="Particle Picking").click()
        time.sleep(4)
        page.get_by_label("Settings", exact=True).last.click()
        time.sleep(4)
        shot(page, "pick_drawer")
        page.get_by_role("button", name="Preview & tune (no save)").click()
        wait_for(page, lambda t: "particles" in t.lower())
        shot(page, "pick_preview")
        page.get_by_role("button", name="Save current image").click()
        wait_for(page, lambda t: "particles picked" in t)
        shot(page, "pick_saved")
        page.keyboard.press("Escape")
        time.sleep(2)
        page.get_by_role("button", name="Jobs").first.click()
        time.sleep(3)
        shot(page, "jobs_panel")
    safe(picking)
    b.close()
