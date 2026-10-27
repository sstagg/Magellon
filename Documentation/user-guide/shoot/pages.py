"""Screenshots of pages that only need looking at (nothing is changed).

Needs the EPU and Leginon sessions named in lib.py to be imported already.
"""
from lib import *

with sync_playwright() as p:
    b, page = open_page(p)

    def menu():
        goto(page, "/en/panel/images")
        page.get_by_label("open drawer").click()
        time.sleep(2)
        shot(page, "nav_drawer")
        page.keyboard.press("Escape")
    safe(menu)

    def import_tabs():
        goto(page, "/en/panel/import-job", wait=2)
        page.get_by_role("tab", name="SerialEM").click()
        time.sleep(2)
        shot(page, "import_serialem")
        # A name already in use is flagged while you type.
        goto(page, "/en/panel/import-job", wait=2)
        page.get_by_label("Data Folder").fill("magellon_demo/24dec03a/home")
        page.get_by_label("Leginon Session Name").fill("24dec03a")
        page.get_by_label("Custom Session Name").fill(EPU_SESSION)
        time.sleep(4)
        shot(page, "name_taken")
    safe(import_tabs)

    def image_panel():
        open_image(page, EPU_SESSION, EPU_IMAGE)
        shot(page, "images_page")
        for tab in ("Image", "Particle Picking", "Metadata"):
            page.get_by_role("tab", name=tab).first.click()
            time.sleep(6)
            shot(page, "tab_" + tab.lower().replace(" ", "_"))
    safe(image_panel)

    def leginon_tabs():
        # Open an exposure: the last image of the right-most column, four levels down.
        open_session(page, LEGINON_SESSION)
        time.sleep(3)
        for _ in range(4):
            thumbs = [t for t in page.locator("img[alt]").all()
                      if (t.get_attribute("alt") or "").startswith(LEGINON_SESSION.split("_")[0])]
            if not thumbs:
                break
            thumbs[-1].click()
            time.sleep(5)
        for tab in ("CTF", "Frame Alignment"):
            page.get_by_role("tab", name=tab).first.click()
            time.sleep(6)
            shot(page, "leg_" + tab.lower().replace(" ", "_"))
    safe(leginon_tabs)

    def delete_dialog():
        # Type all but the last letter so Delete stays grey, then cancel.
        open_session(page, EPU_SESSION)
        page.get_by_label("Delete this session").click()
        time.sleep(2)
        page.get_by_role("textbox").last.fill(EPU_SESSION[:-1])
        time.sleep(1)
        shot(page, "delete_dialog")
        close_dialog(page)
    safe(delete_dialog)

    def export():
        goto(page, "/en/panel/export")
        shot(page, "export_relion")
    safe(export)
    b.close()
