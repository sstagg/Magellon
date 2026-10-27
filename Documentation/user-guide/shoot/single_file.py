"""Screenshots of the single-file CTF and MotionCor tests (Run Processing Jobs).
Each test uses a GPU for a minute or two; nothing is saved in the database.

The Leginon demo data must be mounted read-only at /data:
    -v /gpfs/research/stagg/magellon_demo/24dec03a/home:/data:ro
"""
from lib import *

MOVIE = "/data/frames/20241203_54449_integrated_movie.mrc.tif"
GAIN = "/data/gains/20241202_53597_gain_multi_ref.tif"
IMAGE = "/data/original/24dec03a_00031gr_00001sq_v01_00002hl_00002ex.mrc"


def wait_for_text(page, text, tries=60):
    for _ in range(tries):
        time.sleep(5)
        if text in page.inner_text("body"):
            return


with sync_playwright() as p:
    b, page = open_page(p)

    def ctf():
        goto(page, "/en/panel/run-job")
        page.get_by_role("combobox", name="Pipeline").click()
        time.sleep(1)
        page.get_by_role("option", name="CTF Estimation (CTFFIND4)").click()
        time.sleep(2)
        page.locator("input[type=file]").first.set_input_files(IMAGE)
        page.get_by_role("button", name="Run CTF Estimation").click()
        wait_for_text(page, "Power spectrum")
        time.sleep(6)  # let the plots load
        shot(page, "rj_ctf_result", full=True)
    safe(ctf)

    def motioncor():
        goto(page, "/en/panel/run-job")
        inputs = page.locator("input[type=file]")
        inputs.nth(0).set_input_files(MOVIE)
        inputs.nth(1).set_input_files(GAIN)
        page.get_by_role("button", name="Run Motion Correction").click()
        wait_for_text(page, "Result File")
        page.get_by_role("button", name="View", exact=False).first.click()
        time.sleep(15)
        shot(page, "rj_mc_view")
    safe(motioncor)
    b.close()
