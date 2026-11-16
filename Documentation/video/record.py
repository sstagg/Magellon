"""Record the tutorial video's takes on the live site, in step with the narration.

A take is one continuous recording of one or more scenes of narration.md.
The narration is made sentence by sentence (tts_scenes.py), and the take acts
on sentences: t.at(scene, k) waits until sentence k of the scene is due. When
the site is slow and an action comes late, every later sentence moves back by
the delay, so the voice never runs ahead of the picture. At the end the take
writes out/<take>/take.json: where each sentence falls in the video, which
build.py uses to place the narration, and the stretches of waiting cut from
the video (t.wait_cut).

Headless browsers draw no mouse pointer, so one is drawn into the page, with a
ripple on each click.

    python record.py <take> [<take> ...]

Runs in the guide image (Playwright), with the narration at /audio, the output
at /out, tokens in GUIDE_TOKENS, and the Leginon demo data at /data.

Takes that change things: "import" imports 24dec03a as TOUR_SESSION; "stop"
starts and stops 24dec03a_stopdemo; "export" deletes TOUR_DELETE_SESSION
(import it first: EPU tab, folder epudata_jan); "pick" saves picks.
"""
import json
import os
import re
import sys
import time

from playwright.sync_api import sync_playwright

BASE = os.environ.get("GUIDE_BASE", "https://magellon.rcc.fsu.edu")
TOKENS = json.load(open(os.environ["GUIDE_TOKENS"]))
NARRATION = json.load(open("/audio/scenes.json"))["scenes"]
OUT = "/out"
# The page is laid out at 1536 x 864; build.py scales the recording to 1920 x 1080, so text
# comes out a quarter larger than on a full-HD screen. The page is STRIP pixels taller: the
# strip at the bottom carries the sync marks and is cropped away.
WIDTH, HEIGHT = 1536, 864
STRIP = 8
# The recording runs slower than the clock when the browser is busy (about 10%), so the take
# flashes a colour in the strip at known moments; build.py finds them and fits the video
# back onto the clock. The colours cycle so a missed flash is noticed.
MARK_COLOURS = ["#ff0000", "#00ff00", "#0000ff"]
MARK = """(c) => { const d = document.createElement('div');
  d.style.cssText = `position:fixed;left:0;right:0;bottom:0;height:8px;z-index:2147483647;pointer-events:none;background:${c}`;
  document.documentElement.appendChild(d); setTimeout(() => d.remove(), 350); }"""
SESSION = os.environ.get("TOUR_SESSION", "24dec03a_tour")
DELETE_SESSION = os.environ.get("TOUR_DELETE_SESSION", "epu_deletedemo")
SCENE_GAP = 1.0   # pause between scenes in one take, seconds
LATE = 0.15       # an action later than this moves the narration back

CURSOR = """
(() => {
  const install = () => {
    if (document.getElementById('tour-cursor')) return;
    const c = document.createElement('div');
    c.id = 'tour-cursor';
    c.innerHTML = '<svg width="34" height="34" viewBox="0 0 24 24"><path d="M4 2l14 9-6.5 1.5L8 19z" fill="white" stroke="black" stroke-width="1.6" stroke-linejoin="round"/></svg>';
    c.style.cssText = 'position:fixed;left:-60px;top:-60px;z-index:2147483647;pointer-events:none;transition:none;filter:drop-shadow(0 1px 2px rgba(0,0,0,.6))';
    // A yellow halo around the pointer, so it is easy to follow while it moves.
    const h = document.createElement('div');
    h.id = 'tour-halo';
    h.style.cssText = 'position:fixed;left:-60px;top:-60px;width:46px;height:46px;border-radius:50%;z-index:2147483646;' +
      'pointer-events:none;background:rgba(255,213,79,.30);border:2px solid rgba(255,213,79,.9);box-shadow:0 0 10px rgba(255,213,79,.6)';
    document.documentElement.appendChild(h);
    document.documentElement.appendChild(c);
    addEventListener('mousemove', e => {
      c.style.left = (e.clientX - 4) + 'px'; c.style.top = (e.clientY - 3) + 'px';
      h.style.left = (e.clientX - 23) + 'px'; h.style.top = (e.clientY - 23) + 'px';
    }, true);
    addEventListener('mousedown', e => {
      const r = document.createElement('div');
      r.style.cssText = `position:fixed;left:${e.clientX - 18}px;top:${e.clientY - 18}px;width:36px;height:36px;border-radius:50%;` +
        'border:3px solid #ffd54f;z-index:2147483646;pointer-events:none;transition:transform .45s ease-out, opacity .45s ease-out';
      document.documentElement.appendChild(r);
      requestAnimationFrame(() => { r.style.transform = 'scale(1.8)'; r.style.opacity = '0'; });
      setTimeout(() => r.remove(), 600);
    }, true);
  };
  // No hover tooltips: an image's tooltip covers the next column, and the narration names the buttons.
  const style = document.createElement('style');
  style.textContent = '.MuiTooltip-popper{display:none!important}';
  const addStyle = () => document.head && document.head.appendChild(style);
  if (document.readyState === 'loading') addEventListener('DOMContentLoaded', () => { install(); addStyle(); }); else { install(); addStyle(); }
})();
"""




def login_script(who):
    user = TOKENS[who]
    current = {"id": user["id"], "username": user["username"], "active": True, "change_password_required": False}
    return (f"localStorage.setItem('access_token', {json.dumps(user['token'])});"
            f"localStorage.setItem('currentUser', {json.dumps(json.dumps(current))});"
            f"localStorage.setItem('currentUserId', {json.dumps(user['id'])});")


class Take:
    def __init__(self, p, name, scenes, who="member"):
        self.name, self.scenes = name, scenes
        self.dir = f"{OUT}/{name}"
        os.makedirs(self.dir, exist_ok=True)
        self.browser = p.chromium.launch()
        self.ctx = self.browser.new_context(
            viewport={"width": WIDTH, "height": HEIGHT + STRIP}, ignore_https_errors=True,
            record_video_dir=self.dir, record_video_size={"width": WIDTH, "height": HEIGHT + STRIP})
        self.ctx.add_init_script(login_script(who))
        self.ctx.add_init_script(CURSOR)
        self.t0 = time.time()
        self.page = self.ctx.new_page()
        self.mouse = (WIDTH / 2, HEIGHT / 2)
        # Every sentence of the take, in order, where it falls when nothing is late.
        self.sentences, self.index, at = [], {}, 0.0
        for n, scene in enumerate(scenes):
            if n:
                at += SCENE_GAP
            for k, s in enumerate(NARRATION[scene]["sentences"]):
                self.index[(scene, k)] = len(self.sentences)
                self.sentences.append({"scene": scene, "k": k, "file": s["file"], "text": s["text"],
                                       "length": s["length"], "planned": round(at + s["start"], 3)})
            at += NARRATION[scene]["duration"]
        self.planned_length = at
        self.shift = 0.0
        self.shifts = []   # (first sentence it applies to, shift)
        self.cuts = []     # (from, to) in the raw recording, counted from the start of the narration
        self.cut_total = 0.0
        self.real_start = None
        self.marks = []    # (real seconds from the start of the narration, colour index)

    # --- timing ---------------------------------------------------------
    def start(self):
        """The narration starts now; everything before is cut from the video."""
        self.real_start = time.time()
        self.video_offset = self.real_start - self.t0
        self.mark()

    def mark(self):
        """Flash the next sync colour in the strip and note when."""
        colour = len(self.marks) % len(MARK_COLOURS)
        when = time.time() - self.real_start
        try:
            self.page.evaluate(MARK, MARK_COLOURS[colour])
        except Exception:  # a page in the middle of loading: skip this mark
            return
        self.marks.append((round(when, 3), colour))

    def now(self):
        """Time in the finished video, from the start of the narration."""
        return time.time() - self.real_start - self.cut_total

    def _due(self, index, when):
        late = self.now() - when
        if late > LATE:
            self.shift += late
            self.shifts.append((index, round(self.shift, 3)))
        elif late < 0:
            time.sleep(-late)
        if not self.marks or time.time() - self.real_start - self.marks[-1][0] > 0.6:
            self.mark()

    def at(self, scene, k=0, plus=0.0):
        """Wait until sentence k of the scene starts (plus seconds into it)."""
        i = self.index[(scene, k)]
        self._due(i, self.sentences[i]["planned"] + self.shift + plus)

    def after(self, scene, k):
        """Wait until sentence k of the scene has been said."""
        i = self.index[(scene, k)]
        s = self.sentences[i]
        self._due(i + 1, s["planned"] + s["length"] + self.shift)

    def wait_cut(self, ready, timeout=300, keep=1.5):
        """Wait for ready(), cutting the wait from the video but for a moment either side.

        The cut runs from a mark keep seconds into the wait to a mark when it ends; keep
        seconds of the result are shown before going on."""
        begin = time.time()
        end = begin + timeout
        cut_from = None
        while time.time() < end and not ready():
            if cut_from is None and time.time() - begin > keep:
                self.mark()
                cut_from = self.marks[-1][0]
            time.sleep(0.3)
        if cut_from is not None:
            self.mark()
            cut_to = self.marks[-1][0]
            self.cuts.append((cut_from, cut_to))
            self.cut_total += cut_to - cut_from
        time.sleep(keep)

    def finish(self):
        self._due(len(self.sentences), self.planned_length + self.shift + 1.0)
        self.mark()
        time.sleep(0.5)
        length = self.now()
        video = self.page.video
        self.ctx.close()
        os.replace(video.path(), f"{self.dir}/video.webm")
        self.browser.close()
        shifts, shift, placed = dict(), 0.0, []
        for index, value in self.shifts:
            shifts[index] = value
        for i, s in enumerate(self.sentences):
            shift = shifts.get(i, shift)
            placed.append({**s, "start": round(s["planned"] + shift, 3)})
        json.dump({"scenes": self.scenes, "sentences": placed, "crop": [WIDTH, HEIGHT], "strip": STRIP,
                   "marks": self.marks, "mark_colours": MARK_COLOURS, "cuts": self.cuts,
                   "video_offset": round(self.video_offset, 3), "length": round(length, 3)},
                  open(f"{self.dir}/take.json", "w"), indent=1)
        print(f"{self.name}: planned {self.planned_length:.1f}s, video {length:.1f}s, "
              f"narration moved back {self.shift:.1f}s in all")

    # --- acting ---------------------------------------------------------
    def goto(self, path, wait=2.5):
        self.page.goto(BASE + path, wait_until="networkidle")
        time.sleep(wait)
        self.page.mouse.move(*self.mouse)

    def move(self, target, steps=22, pause=0.2):
        """Glide the pointer to a locator (its centre) or to (x, y)."""
        if isinstance(target, tuple):
            x, y = target
        else:
            target.wait_for(state="visible", timeout=60000)
            box = target.bounding_box()
            if box["y"] < 70 or box["y"] + box["height"] > HEIGHT - 40:  # off screen, or under a bar
                target.evaluate("e => e.scrollIntoView({block: 'center', behavior: 'instant'})")
                time.sleep(0.4)
                box = target.bounding_box()
            x, y = box["x"] + box["width"] / 2, box["y"] + box["height"] / 2
        self.page.mouse.move(x, y, steps=steps)
        self.mouse = (x, y)
        time.sleep(pause)

    def click(self, target, pause=0.6):
        self.move(target)
        self.page.mouse.down()
        self.page.mouse.up()
        time.sleep(pause)

    def type(self, target, text, delay=70, clear=False):
        self.click(target, pause=0.3)
        if clear:
            self.page.keyboard.press("Control+A")
        self.page.keyboard.type(text, delay=delay)
        time.sleep(0.3)

    def open_session(self, name=SESSION):
        self.click(self.page.get_by_role("combobox").first)
        self.click(self.page.get_by_role("option", name=name, exact=True), pause=3)

    def tile(self, name_fragment):
        return self.page.locator("[data-image-oid]").filter(
            has=self.page.locator(f'img[alt*="{name_fragment}"]')).first

    def menu(self, item, sub=None):
        """Open the side menu, choose an item (and an item under it), then close the menu."""
        opener = self.page.get_by_label("open drawer")
        if opener.count():
            self.click(opener, pause=0.8)
        drawer = self.page.locator(".MuiDrawer-paper")
        self.click(drawer.get_by_text(item, exact=True).first, pause=0.8 if sub else 1.5)
        if sub:
            self.click(drawer.get_by_text(sub, exact=True).first, pause=1.5)
        closer = self.page.get_by_label("close drawer")
        if closer.count():
            self.click(closer, pause=0.6)


TAKES = {}


def take(name, scenes, **kw):
    def register(fn):
        TAKES[name] = (fn, scenes, kw)
        return fn
    return register


GOOD_PATH = ["24dec03a_00034gr", "_00004sq_v01", "_00004hl", "_00004hl_00009ex"]


def layout(t, value, pause=1.2):
    group = t.page.locator(".MuiToggleButtonGroup-root").filter(has=t.page.locator("button[value=table]"))
    t.click(group.locator(f"button[value={value}]"), pause=pause)


def choose(t, scope, field_index, option):
    """Pick an option in a filter rule's drop-down (0 field, 1 comparison)."""
    t.click(scope.get_by_role("combobox").nth(field_index), pause=0.4)
    t.click(t.page.get_by_role("option", name=option, exact=True), pause=0.4)


# --- Chapter 2 ---------------------------------------------------------------
@take("view", ["2.1", "2.2", "2.3", "2.4", "2.5", "2.6", "2.7"])
def record_view(t):
    page = t.page
    t.goto("/en/panel/images")
    t.start()
    t.at("2.1", 1)
    t.open_session()

    t.at("2.2", 0)
    t.move(page.locator("img:visible").first, pause=0.5)          # the atlas
    t.at("2.2", 1)
    t.move(page.get_by_text("Column View Settings"), pause=0.3)
    for k, fragment in zip((2, 3, 4, 5), GOOD_PATH):
        t.at("2.2", k)
        t.click(t.tile(fragment), pause=0.8)
    t.at("2.2", 6)
    t.move((WIDTH * 0.78, HEIGHT * 0.55), steps=30)
    t.at("2.2", 7)
    t.move(t.tile("24dec03a_00031gr"), pause=0.8)
    t.move(t.tile("24dec03a_00034gr"), pause=0.3)
    t.at("2.2", 8)
    page.mouse.wheel(0, 900)
    t.after("2.2", 8)
    page.mouse.wheel(0, -900)

    t.at("2.3", 0)
    t.move(page.locator(".MuiToggleButtonGroup-root").filter(has=page.locator("button[value=table]")))
    t.at("2.3", 1)
    layout(t, "flat")
    t.move((WIDTH * 0.3, HEIGHT * 0.7))
    page.mouse.wheel(0, 300)
    t.at("2.3", 2)
    layout(t, "tree")
    t.at("2.3", 3)
    layout(t, "table")
    t.at("2.3", 4)
    t.click(page.get_by_role("button", name="Resolution (Å)"), pause=1)
    t.at("2.3", 5)
    t.click(page.locator("[data-testid=image-table] tbody tr").first, pause=1)
    layout(t, "grid")

    t.at("2.4", 0)
    t.move(page.get_by_label("Filter images"))
    t.at("2.4", 1)
    t.click(page.get_by_label("Filter images"), pause=1)
    dialog = page.get_by_role("dialog")
    rule = dialog.get_by_test_id("filter-rule").first
    t.at("2.4", 2)
    t.move(rule)
    t.at("2.4", 3)
    t.move(rule.get_by_role("combobox").nth(0))
    t.at("2.4", 4)
    t.move(rule.get_by_role("combobox").nth(1))
    t.at("2.4", 5)
    t.type(rule.get_by_label("Value (Å)"), "4")
    t.at("2.4", 6)
    t.move(dialog.get_by_test_id("filter-preview"))
    t.at("2.4", 7)
    t.move(rule.locator(".MuiFormHelperText-root"))
    t.at("2.4", 8)
    t.move(dialog.get_by_test_id("filter-preview"))
    t.at("2.4", 9)
    t.click(rule.get_by_role("combobox").nth(0), pause=0.3)
    t.after("2.4", 9)
    page.keyboard.press("Escape")

    t.at("2.5", 1)
    t.click(dialog.get_by_role("button", name="Condition").last, pause=0.5)
    second = dialog.get_by_test_id("filter-rule").nth(1)
    choose(t, second, 0, "Magnification")
    choose(t, second, 1, "=")
    t.type(second.get_by_label("Value (×)"), "59000")
    t.at("2.5", 2)
    t.move(dialog.get_by_role("button", name="AND").first)
    t.at("2.5", 3)
    t.move(dialog.get_by_role("button", name="AND").first, steps=5)
    t.at("2.5", 4)
    t.move(dialog.get_by_role("button", name="OR").first)
    t.at("2.5", 5)
    t.click(dialog.get_by_role("button", name="Group").last, pause=0.8)
    group = dialog.get_by_test_id("filter-group").nth(1)
    t.at("2.5", 6)
    t.move(group)
    t.at("2.5", 7)
    t.click(group.get_by_role("button", name="OR"), pause=0.4)
    t.click(group.get_by_label("NOT"), pause=0.4)
    t.at("2.5", 8)
    first = group.get_by_test_id("filter-rule").nth(0)
    choose(t, first, 0, "Name")
    t.type(first.get_by_label("Value"), "00034gr")
    last = group.get_by_test_id("filter-rule").nth(1)
    choose(t, last, 1, "≠")
    t.type(last.get_by_label("Value (×)"), "59000")
    t.at("2.5", 9)
    t.move(dialog.get_by_test_id("filter-preview"))

    t.at("2.6", 0)
    t.click(dialog.get_by_role("button", name="Apply Filters"), pause=1)
    t.move(page.get_by_test_id("active-filter"))
    t.at("2.6", 2)
    layout(t, "flat", pause=1.5)
    layout(t, "table", pause=1.5)
    t.at("2.6", 3)
    layout(t, "grid", pause=1)
    t.at("2.6", 4)
    for column in range(4):  # down the only branch left
        tiles = page.locator("[data-image-oid]")
        t.click(tiles.nth(tiles.count() - 1) if column else tiles.first, pause=1)
    t.at("2.6", 5)
    layout(t, "tree", pause=1)
    t.at("2.6", 7)
    t.move(page.get_by_test_id("active-filter"))
    t.click(page.get_by_test_id("active-filter").locator("svg").last, pause=0.5)
    layout(t, "grid", pause=1)
    for fragment in GOOD_PATH[:3]:
        t.click(t.tile(fragment), pause=0.6)

    t.at("2.7", 0)
    t.click(t.tile(GOOD_PATH[3]), pause=1)
    t.at("2.7", 1)
    t.move((WIDTH * 0.72, 125))
    t.at("2.7", 2)
    t.click(page.get_by_role("tab", name="Image").first, pause=0.5)
    t.at("2.7", 3)
    t.move((WIDTH * 0.75, HEIGHT * 0.65))
    for _ in range(4):
        page.mouse.wheel(0, -120)
        time.sleep(0.3)
    page.mouse.down()
    page.mouse.move(WIDTH * 0.7, HEIGHT * 0.6, steps=15)
    page.mouse.up()
    t.at("2.7", 4)
    t.click(page.get_by_role("tab", name="FFT").first, pause=0.5)
    t.at("2.7", 5)
    t.click(page.get_by_role("tab", name="CTF").first, pause=1)
    t.at("2.7", 6)
    t.click(page.get_by_role("tab", name="Frame Alignment").first, pause=1)
    t.at("2.7", 7)
    command = page.get_by_test_id("run-command").first
    if command.count():
        t.move(command)
        if command.get_by_role("button").count():
            t.move(command.get_by_role("button").first)
    t.at("2.7", 9)
    t.click(page.get_by_role("tab", name="Metadata").first, pause=0.5)


# --- Chapter 3 ---------------------------------------------------------------
@take("import", ["3.1", "3.2", "3.3", "3.4"])
def record_import(t):
    page = t.page
    t.goto("/en/panel/images")
    t.start()
    t.at("3.1", 1)
    t.menu("Import")
    t.at("3.1", 2)
    for tab in ("Leginon", "Magellon", "EPU", "SerialEM"):
        t.move(page.get_by_role("tab", name=tab), pause=0.3)
    t.at("3.1", 3)
    t.move(page.get_by_role("tab", name="Leginon"))

    t.at("3.2", 0)
    t.type(page.get_by_label("Leginon Session Name"), "24dec03a")
    t.at("3.2", 2)
    t.move(page.get_by_role("alert").filter(has_text="Couldn't find"))
    t.at("3.2", 3)
    t.move(page.get_by_label("Frames Folder", exact=True))
    t.move(page.get_by_label("Gain File", exact=True))
    gain = page.get_by_label("Gain File", exact=True).locator("xpath=ancestor::div[contains(@class,'MuiFormControl')][1]")
    t.at("3.2", 5)
    t.move(gain.get_by_role("button", name="Browse"))
    t.at("3.2", 6)
    t.move(page.get_by_role("alert").filter(has_text="Couldn't find"))
    t.at("3.2", 7)
    t.type(page.get_by_label("Images Folder", exact=True), "magellon_demo/24dec03a/home/original", delay=40)
    images = page.get_by_label("Images Folder", exact=True).locator("xpath=ancestor::div[contains(@class,'MuiFormControl')][1]")
    t.move(images.get_by_role("button", name="Browse"))
    t.at("3.2", 9)
    t.move(images.locator("p").first)
    t.at("3.2", 11)
    t.move(page.get_by_label("Custom Session Name"))
    t.at("3.2", 12)
    t.move(page.get_by_label("Custom Session Name").locator(
        "xpath=ancestor::div[contains(@class,'MuiFormControl')][1]").locator("p").first)
    t.at("3.2", 13)
    t.type(page.get_by_label("Custom Session Name"), SESSION, clear=True)
    t.at("3.2", 14)
    t.move(page.get_by_text("Copy images into the session", exact=False).first, pause=1)
    t.at("3.2", 15)
    t.move(page.get_by_text("Copy movies into the session", exact=False).first)
    t.at("3.2", 16)
    t.move(page.get_by_text("Copy images into the session", exact=False).first)

    t.at("3.3", 0)
    if os.environ.get("DRY"):  # rehearsal: don't start the import
        t.move(page.locator("main button").filter(has_text="Import").last)
        return
    t.click(page.locator("main button").filter(has_text="Import").last, pause=1)
    t.at("3.3", 1)
    t.move(page.get_by_role("dialog"))
    t.at("3.4", 0)
    t.click(page.get_by_role("button", name="Run in background"), pause=1)
    t.at("3.4", 1)
    chip = page.locator("header").get_by_text(SESSION).first
    if chip.count():
        t.move(chip)
    t.at("3.4", 2)
    t.click(page.get_by_role("button", name="Jobs").first, pause=1)
    t.move(page.get_by_text(f"Leginon Import: {SESSION}").first)


@take("done", ["3.5"])
def record_done(t):
    page = t.page
    t.goto("/en/panel/import-job")
    t.start()
    t.at("3.5", 0)
    t.click(page.get_by_role("button", name="Jobs").first, pause=1)
    t.move(page.get_by_text(f"Leginon Import: {SESSION}").first)
    t.at("3.5", 2)
    t.click(page.get_by_role("button", name="Jobs").first, pause=0.5)
    t.menu("Images")
    t.open_session()
    for fragment in GOOD_PATH:
        t.click(t.tile(fragment), pause=0.6)
    t.click(page.get_by_role("tab", name="CTF").first, pause=1.5)


MOVIE = "/data/frames/20241203_54449_integrated_movie.mrc.tif"
GAIN = "/data/gains/20241202_53597_gain_multi_ref.tif"
MICROGRAPH = "/data/original/24dec03a_00031gr_00001sq_v01_00002hl_00002ex.mrc"


@take("test", ["3.6"])
def record_test(t):
    page = t.page
    t.goto("/en/panel/images")
    t.start()
    t.at("3.6", 0)
    t.menu("Jobs")
    if "run-job" not in page.url:
        t.goto("/en/panel/run-job", wait=1)
    t.at("3.6", 1)
    t.move(page.locator("label[for=image-file-upload]"))
    page.locator("input[type=file]").nth(0).set_input_files(MOVIE)
    t.move(page.locator("input[type=file]").nth(1).locator("xpath=following-sibling::label[1]"))
    page.locator("input[type=file]").nth(1).set_input_files(GAIN)
    t.at("3.6", 2)
    t.click(page.get_by_text("Advanced Parameters"), pause=0.6)
    t.type(page.get_by_label("Pixel Size"), "0.395", clear=True)
    t.at("3.6", 3)
    t.click(page.get_by_role("button", name="Run Motion Correction"), pause=0.5)
    result = page.get_by_test_id("motioncor-test-result")
    t.wait_cut(lambda: result.count() > 0 and result.locator("img").count() > 0)
    t.at("3.6", 5)
    t.move(result.get_by_test_id("run-command").first if result.get_by_test_id("run-command").count() else result)

    t.at("3.6", 6)
    page.mouse.wheel(0, -3000)
    time.sleep(0.6)
    t.at("3.6", 7)
    t.click(page.get_by_role("combobox", name="Pipeline"), pause=0.5)
    t.click(page.get_by_role("option", name="CTF Estimation (CTFFIND4)"), pause=1)
    t.move(page.locator("input[type=file]").nth(0).locator("xpath=following-sibling::label[1]"))
    page.locator("input[type=file]").nth(0).set_input_files(MICROGRAPH)
    advanced = page.get_by_text("Advanced Parameters")
    if advanced.count() and not page.get_by_label("Pixel Size").is_visible():
        t.click(advanced.first, pause=0.5)
    if page.get_by_label("Pixel Size").count():
        t.type(page.get_by_label("Pixel Size"), "0.79", clear=True)
    t.at("3.6", 8)
    t.click(page.get_by_role("button", name="Run CTF Estimation"), pause=0.5)
    ctf = page.get_by_test_id("ctf-test-result")
    t.wait_cut(lambda: ctf.count() > 0 and ctf.locator("img").count() > 1)
    t.move(ctf.locator("img").first)
    t.at("3.6", 9)
    t.move((WIDTH / 2, HEIGHT * 0.6))


RECORDS = re.compile(r"Picking record|my picks|Topaz|Auto")


def _records(page):
    """The picking-record drop-down above the image."""
    return page.get_by_role("combobox").filter(has_text=RECORDS).first


@take("pick", ["3.7", "3.7b", "3.7c", "3.7d", "3.7e"])
def record_pick(t):
    page = t.page
    t.goto("/en/panel/run-job")
    t.start()
    # --- by hand
    t.at("3.7", 0)
    t.menu("Images")
    t.open_session()
    t.at("3.7", 1)
    for fragment in GOOD_PATH:
        t.click(t.tile(fragment), pause=0.5)
    t.click(page.get_by_role("tab", name="Particle Picking").first, pause=1.5)
    t.at("3.7", 2)
    t.move(_records(page))
    t.at("3.7", 3)
    t.click(page.get_by_label("Picking record actions"), pause=0.5)
    t.click(page.get_by_role("menuitem", name="New picking record"), pause=0.6)
    t.type(page.get_by_role("dialog").get_by_role("textbox").first, "my picks")
    t.click(page.get_by_role("dialog").get_by_role("button", name="Create"), pause=1)
    t.at("3.7", 4)
    t.click(page.get_by_label("Add (1)"), pause=0.3)
    image = page.locator("svg").filter(has=page.locator("image")).last
    box = image.bounding_box()
    spots = [(box["x"] + box["width"] * fx, box["y"] + box["height"] * fy)
             for fx, fy in ((0.3, 0.35), (0.45, 0.3), (0.6, 0.45), (0.38, 0.6), (0.55, 0.65), (0.7, 0.3))]
    for spot in spots:
        t.click(spot, pause=0.35)
    t.at("3.7", 5)
    t.move(page.get_by_text("Manual", exact=True).first, pause=1.5)
    t.move(page.get_by_text("Conf", exact=True).first)
    t.move((t.mouse[0], t.mouse[1] + 110))
    t.at("3.7", 6)
    t.move(page.get_by_label("Particle radius").first)
    t.at("3.7", 7)
    t.click(page.get_by_label("Remove (2)"), pause=0.3)
    t.click(spots[-1], pause=0.6)
    t.click(page.get_by_label("Undo"), pause=0.6)
    t.at("3.7", 8)
    page.keyboard.press("h")
    time.sleep(2.5)
    page.keyboard.press("Escape")
    page.keyboard.press("Control+s")

    # --- Topaz
    t.at("3.7b", 0)
    t.click(page.get_by_label("Settings", exact=True).last, pause=1)
    method = page.get_by_role("combobox").filter(has_text="Topaz Particle Picking").first
    t.at("3.7b", 1)
    t.move(method)
    t.at("3.7b", 2)
    t.click(method, pause=0.3)
    t.after("3.7b", 2)
    page.keyboard.press("Escape")
    t.at("3.7b", 3)
    t.move(page.get_by_text("Model", exact=True).first)
    t.at("3.7b", 4)
    for label in ("Score Threshold", "NMS Radius", "Scale"):
        target = page.locator(f"text='{label}' >> visible=true").first
        if target.count():
            t.move(target, pause=0.4)
    t.at("3.7b", 5)
    train = page.get_by_role("button", name=re.compile("Train session"))
    if train.count():
        t.move(train.first)
    t.at("3.7b", 6)
    t.click(page.get_by_role("button", name="Preview & tune (no save)"), pause=0.3)
    count = page.get_by_text(re.compile(r"\d+ particles")).first
    t.wait_cut(lambda: count.count() > 0, timeout=300)
    t.at("3.7b", 8)
    t.move(count)
    t.move(page.get_by_text("brighter", exact=False).first if page.get_by_text("brighter", exact=False).count() else count)
    t.at("3.7b", 9)
    thumb = page.get_by_text("Score Threshold").last.locator("xpath=following::span[contains(@class,'MuiSlider-thumb')][1]")
    if thumb.count():
        t.move(thumb)
        page.mouse.down()
        page.mouse.move(t.mouse[0] + 45, t.mouse[1], steps=12)
        page.mouse.up()
        t.mouse = (t.mouse[0] + 45, t.mouse[1])
    before = count.inner_text()
    run = page.get_by_role("button", name="Run", exact=True)
    if run.count():
        t.click(run.first, pause=0.3)
        t.wait_cut(lambda: count.count() > 0 and count.inner_text() != before, timeout=240)
        t.move(count)
    t.at("3.7b", 10)
    t.click(page.get_by_role("button", name="Accept").first, pause=1)
    t.at("3.7b", 11)
    save = page.get_by_role("button", name="Save current image")
    if save.count():
        t.move(save.first)

    # --- template picker
    t.at("3.7c", 0)
    method = page.get_by_role("combobox").filter(has_text="Topaz Particle Picking").first
    t.click(method, pause=0.4)
    t.click(page.get_by_role("option").filter(has_text="Template Picker").first, pause=1)
    t.at("3.7c", 2)
    for label in ("Diameter Angstrom", "Threshold", "Max Peaks", "Image Pixel Size"):
        target = page.locator(f"text=/{label}/ >> visible=true").first
        if target.count():
            t.move(target, pause=0.5)
    t.at("3.7c", 3)
    t.move(page.get_by_role("button", name="Preview & tune (no save)"))
    t.after("3.7c", 3)
    t.click(page.get_by_role("combobox").filter(has_text="Template Picker").first, pause=0.4)
    t.click(page.get_by_role("option").filter(has_text="Topaz").first, pause=0.8)

    # --- batch
    t.at("3.7d", 0)
    t.click(page.get_by_role("button", name="Run batch…"), pause=1.5)
    dialog = page.get_by_role("dialog")
    t.at("3.7d", 1)
    t.move(dialog.get_by_label("Magnification"))
    t.at("3.7d", 2)
    t.move(dialog.get_by_label("Tolerance (±)"))
    t.move(dialog.get_by_label("IPP name"))
    t.at("3.7d", 3)
    t.move(dialog.get_by_role("button", name="Select all"))
    t.at("3.7d", 4)
    t.click(dialog.get_by_role("button", name="Select none"), pause=0.5)
    for name in ("00004hl_00009ex", "00004hl_00011ex", "00004hl_00016ex"):
        row = dialog.get_by_text("24dec03a_00034gr_00004sq_v01_" + name, exact=True).first
        t.move(row, pause=0.2)
        page.mouse.down()
        page.mouse.up()
        time.sleep(0.4)
        box = row.locator("xpath=ancestor::*[.//input[@type='checkbox']][1]//input[@type='checkbox']").first
        if box.count() and not box.is_checked():
            box.check(force=True)
            time.sleep(0.3)
    if not dialog.get_by_text("3 selected", exact=False).count():
        print("batch: expected 3 selected, dialog says", dialog.get_by_text(re.compile(r"\d+ selected")).first.inner_text())
    t.at("3.7d", 5)
    t.click(dialog.get_by_role("button", name=re.compile("Launch on")), pause=0.5)
    t.wait_cut(lambda: dialog.get_by_role("button", name="Close").count() > 0, timeout=900)
    t.at("3.7d", 6)
    t.move(dialog.get_by_text(re.compile(r"\d+ picks")).first)
    t.at("3.7d", 7)
    t.click(dialog.get_by_role("button", name="Close"), pause=0.6)
    t.click(page.get_by_role("button", name="Jobs").first, pause=1)
    t.move(page.get_by_text(re.compile("topaz", re.I)).first)
    t.after("3.7d", 7)
    t.click(page.get_by_role("button", name="Jobs").first, pause=0.5)

    # --- records
    t.at("3.7e", 0)
    t.move(_records(page))
    t.at("3.7e", 1)
    t.click(_records(page), pause=0.5)
    t.click(page.get_by_role("option").filter(has_text="my picks").first, pause=1.2)
    t.at("3.7e", 2)
    for name in ("Topaz batch", "Auto"):
        t.click(_records(page), pause=0.5)
        option = page.get_by_role("option").filter(has_text=name).first
        if option.count():
            t.click(option, pause=1.5)
        else:
            page.keyboard.press("Escape")
    t.at("3.7e", 3)
    t.click(page.get_by_label("Picking record actions"), pause=0.5)
    t.move(page.get_by_role("menuitem", name="Export as COCO"))
    t.after("3.7e", 3)
    page.keyboard.press("Escape")


def start_import(name):
    """Start a Leginon import of 24dec03a in the background, as the member."""
    import ssl
    import urllib.parse
    import urllib.request
    form = dict(magellon_project_name="Leginon", magellon_session_name=name, session_name="24dec03a",
                images_directory="/gpfs/magellon_demo/24dec03a/home/original",
                frames_directory="/gpfs/framesdata/24dec03a",
                gain_path="/gpfs/framesdata/24dec03a/20241202_53597_gain_multi_ref.tif",
                copy_images="false", copy_frames="false", retries="0")
    context = ssl.create_default_context()
    context.check_hostname, context.verify_mode = False, ssl.CERT_NONE
    request = urllib.request.Request(BASE + "/image/import_leginon_job", data=urllib.parse.urlencode(form).encode(),
                                     headers={"Authorization": "Bearer " + TOKENS["member"]["token"]})
    print("started", urllib.request.urlopen(request, context=context, timeout=60).read()[:100])


STOP = "Stop this import and delete what it created"


@take("stop", ["3.8"])
def record_stop(t):
    page = t.page
    start_import("24dec03a_stopdemo")
    t.goto("/en/panel/images")
    time.sleep(8)
    t.start()
    t.at("3.8", 0)
    t.click(page.get_by_role("button", name="Jobs").first, pause=0.8)
    row = page.locator("li, div").filter(has_text="24dec03a_stopdemo").filter(has=page.get_by_label(STOP)).last
    t.move(row.get_by_label(STOP))
    t.at("3.8", 1)
    t.click(row.get_by_label(STOP), pause=0.8)
    t.at("3.8", 2)
    t.move(page.get_by_role("dialog").get_by_text("deleted", exact=False).first)
    t.at("3.8", 4)
    t.move(page.get_by_role("dialog").get_by_role("button", name="Stop and delete"))
    t.after("3.8", 4)
    t.click(page.get_by_role("dialog").get_by_role("button", name="Stop and delete"), pause=2.5)


@take("export", ["3.9"])
def record_export(t):
    page = t.page
    t.goto("/en/panel/images")
    t.start()
    t.at("3.9", 0)
    t.menu("Export")
    t.move(page.get_by_role("combobox").first)
    t.move(page.get_by_label("Output Directory").first)
    t.at("3.9", 1)
    t.menu("Images")
    t.at("3.9", 2)
    t.open_session(DELETE_SESSION)
    t.click(page.get_by_label("Delete this session"), pause=0.8)
    t.at("3.9", 3)
    box = page.get_by_role("dialog").get_by_role("textbox").last
    t.type(box, DELETE_SESSION[:-3], delay=100)
    t.at("3.9", 4)
    t.move(page.get_by_role("dialog").get_by_role("button", name="Delete"))
    t.type(box, DELETE_SESSION[-3:], delay=250)
    t.move(page.get_by_role("dialog").get_by_role("button", name="Delete"))
    t.at("3.9", 5)
    t.click(page.get_by_role("dialog").get_by_role("button", name="Delete"), pause=0.5)
    t.move((WIDTH / 2, HEIGHT - 120))


# --- Chapter 4 ---------------------------------------------------------------
def _row_icons(page):
    """The action icons of the first user in the list (deactivate, password, roles, delete)."""
    return page.locator("tbody tr").first.locator("td").last.locator("button")


def _close(t):
    dialog = t.page.get_by_role("dialog")
    for name in ("Cancel", "Close", "Done"):
        button = dialog.get_by_role("button", name=name)
        if button.count():
            t.click(button.first, pause=0.5)
            return
    t.page.keyboard.press("Escape")


@take("admin", ["4.1", "4.2", "4.3", "4.4"], who="admin")
def record_admin(t):
    page = t.page
    t.goto("/en/panel/images")
    t.start()
    t.at("4.1", 1)
    t.menu("Security")
    t.click(page.get_by_role("tab", name="User Management"), pause=0.8)
    t.at("4.1", 2)
    t.click(page.get_by_role("button", name="Add User"), pause=0.8)
    dialog = page.get_by_role("dialog")
    t.type(dialog.get_by_label("Username"), "new.student")
    t.type(dialog.get_by_label("Password", exact=True), "First-Pass-2026", delay=40)
    t.after("4.1", 2)
    _close(t)  # nothing is created

    icons = _row_icons(page)
    t.at("4.2", 0)
    t.click(icons.nth(2), pause=0.8)  # roles
    t.at("4.2", 1)
    member = page.get_by_role("dialog").get_by_text("Member", exact=True).first
    if member.count():
        t.move(member)
    t.after("4.2", 2)
    _close(t)  # no role is changed
    t.at("4.2", 3)
    t.move(icons.nth(0), pause=1.2)  # deactivate
    t.move(icons.nth(1))              # reset password

    t.at("4.3", 0)
    t.click(page.get_by_role("tab", name="Permission Checker"), pause=1)
    t.at("4.3", 1)
    t.click(page.get_by_role("tab", name="Session Access"), pause=1)
    t.click(page.get_by_role("combobox").first, pause=0.6)
    t.click(page.get_by_role("option").filter(has_text=SESSION).first, pause=1)

    t.at("4.4", 0)
    t.menu("Plugins")
    t.move((WIDTH / 2, HEIGHT / 2))
    t.at("4.4", 1)
    t.menu("Tools", "Pipeline Health")
    t.move((WIDTH / 2, HEIGHT / 3))


@take("close", ["4.5"])
def record_close(t):
    page = t.page
    t.goto("/en/panel/export")
    t.start()
    t.at("4.5", 0)
    t.menu("Images")
    t.open_session()
    for fragment in GOOD_PATH:
        t.click(t.tile(fragment), pause=0.5)
    t.move(page.locator("img:visible").first, pause=1)
    t.at("4.5", 1)
    t.move((WIDTH * 0.78, HEIGHT * 0.55), steps=40)


def main(names):
    with sync_playwright() as p:
        for name in names:
            fn, scenes, kw = TAKES[name]
            t = Take(p, name, scenes, **kw)
            try:
                fn(t)
            except Exception:  # report it, keep the recording for a look, go on with the next take
                import traceback
                traceback.print_exc()
                print(f"TAKE FAILED: {name}")
            finally:
                if t.real_start is None:
                    t.start()
                t.finish()


if __name__ == "__main__":
    main(sys.argv[1:])
