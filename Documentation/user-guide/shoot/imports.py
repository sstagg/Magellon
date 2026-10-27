"""Screenshots of the import forms and progress. THIS STARTS TWO REAL IMPORTS,
named by GUIDE_EPU_SESSION and GUIDE_LEGINON_SESSION, which pages.py and
picking.py then use. Delete any old sessions with those names first.

EPU data: the folder epudata_jan in the research storage.
Leginon data: magellon_demo/24dec03a/home, session 24dec03a.
"""
from lib import *

with sync_playwright() as p:
    b, page = open_page(p)

    def epu():
        goto(page, "/en/panel/import-job", wait=2)
        page.get_by_role("tab", name="EPU").click()
        time.sleep(2)
        shot(page, "epu_browser")
        page.get_by_text("epudata_jan", exact=True).dblclick()
        time.sleep(2)
        page.get_by_placeholder("e.g. epudata_jan_25apr04a").fill(EPU_SESSION)
        time.sleep(2)
        shot(page, "epu_settings")
        page.get_by_role("button", name="Import EPU Data").click()
        time.sleep(15)
        shot(page, "epu_progress")
        page.get_by_role("button", name="Run in background").click()
        time.sleep(2)
    safe(epu)

    def leginon():
        goto(page, "/en/panel/import-job", wait=2)
        page.get_by_label("Data Folder").fill("magellon_demo/24dec03a/home")
        page.get_by_label("Leginon Session Name").fill("24dec03a")
        page.get_by_label("Custom Session Name").fill(LEGINON_SESSION)
        time.sleep(3)
        shot(page, "leg_form", full=True)
        page.locator("main button").filter(has_text="Import").last.click()
        time.sleep(40)
        shot(page, "leg_progress")
        page.get_by_role("button", name="Run in background").click()
        time.sleep(2)
    safe(leginon)

    def stop_dialog():
        # Open the stop confirmation on a running import, then keep it running.
        page.get_by_role("button", name="Jobs").first.click()
        time.sleep(3)
        page.get_by_label("Stop this import and delete what it created").first.click()
        time.sleep(2)
        shot(page, "stop_dialog")
        page.get_by_role("button", name="Keep running").click()
    safe(stop_dialog)
    b.close()
