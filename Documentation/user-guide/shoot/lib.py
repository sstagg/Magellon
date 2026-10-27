"""Shared helpers for the screenshot scripts.

Each script logs in by putting a token from .tokens.json (see mint_tokens.py)
into the browser's localStorage, drives the live site with Playwright and
saves pictures to ../images/<name>.jpg, the names guide.md refers to.

Settings come from environment variables, with the defaults used for the
current guide:
  GUIDE_BASE              the site                    https://magellon.rcc.fsu.edu
  GUIDE_EPU_SESSION       an imported EPU session     guide_demo
  GUIDE_LEGINON_SESSION   an imported Leginon session guide_leginon
  GUIDE_EPU_IMAGE         an exposure in the EPU session to open
  GUIDE_PICK_IMAGE        an exposure to pick particles on
"""
import io
import json
import os
import time

from PIL import Image
from playwright.sync_api import sync_playwright  # noqa: F401  (used by the scripts)

HERE = os.path.dirname(os.path.abspath(__file__))
IMAGES = os.environ.get("GUIDE_IMAGES", os.path.join(HERE, "..", "images"))
BASE = os.environ.get("GUIDE_BASE", "https://magellon.rcc.fsu.edu")
EPU_SESSION = os.environ.get("GUIDE_EPU_SESSION", "guide_demo")
LEGINON_SESSION = os.environ.get("GUIDE_LEGINON_SESSION", "guide_leginon")
EPU_IMAGE = os.environ.get("GUIDE_EPU_IMAGE", "FoilHole_3446030_Data")
PICK_IMAGE = os.environ.get("GUIDE_PICK_IMAGE", "FoilHole_3446054_Data")
TOKENS = json.load(open(os.environ.get("GUIDE_TOKENS", os.path.join(HERE, ".tokens.json"))))
MEMBER = TOKENS["member"]["username"]


def open_page(p, who="member", size=(1440, 900)):
    """A logged-in browser page; who is "member" or "admin"."""
    browser = p.chromium.launch()
    ctx = browser.new_context(viewport={"width": size[0], "height": size[1]}, device_scale_factor=2,
                              color_scheme="light", ignore_https_errors=True)
    user = TOKENS[who]
    current = {"id": user["id"], "username": user["username"], "active": True, "change_password_required": False}
    ctx.add_init_script(f"""
        localStorage.setItem('access_token', {json.dumps(user['token'])});
        localStorage.setItem('currentUser', {json.dumps(json.dumps(current))});
        localStorage.setItem('currentUserId', {json.dumps(user['id'])});
    """)
    return browser, ctx.new_page()


def shot(page, name, full=False):
    """Save the page as images/<name>.jpg, 2000 px wide (the width the crop
    coordinates in guide.md are measured in)."""
    img = Image.open(io.BytesIO(page.screenshot(full_page=full))).convert("RGB")
    img = img.resize((2000, round(img.height * 2000 / img.width)), Image.LANCZOS)
    img.save(os.path.join(IMAGES, name + ".jpg"), "JPEG", quality=85, optimize=True)
    print("shot", name)


def goto(page, path, wait=3):
    page.goto(BASE + path, wait_until="networkidle")
    time.sleep(wait)


def open_session(page, session):
    """Images page with the session chosen in the drop-down."""
    goto(page, "/en/panel/images")
    page.get_by_role("combobox").first.click()
    time.sleep(1)
    page.get_by_role("option", name=session).click()
    time.sleep(5)


def open_image(page, session, image):
    open_session(page, session)
    page.get_by_text(image, exact=False).first.click()
    time.sleep(5)


def close_dialog(page):
    """Leave the open dialog without changing anything."""
    dialog = page.get_by_role("dialog")
    for name in ("Cancel", "Close", "Keep running"):
        button = dialog.get_by_role("button", name=name)
        if button.count():
            button.first.click()
            time.sleep(1)
            return
    page.keyboard.press("Escape")
    time.sleep(1)


def safe(fn):
    """Run one group of shots; a failure is reported and the rest go on."""
    try:
        fn()
    except Exception as e:  # a changed page should not stop the other shots
        print("FAILED", fn.__name__, str(e)[:200])
