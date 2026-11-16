# Magellon tutorial video

A narrated walkthrough of Magellon: a short welcome, then viewing (everyone),
importing and processing (Members), and administration. About 14 minutes, with
chapter markers and an English subtitle track.

| File | What it is |
|---|---|
| narration.md | The script: what is said in each scene, and [what is on screen]. One idea per sentence. Edit this first. |
| tts_scenes.py | Turns the script into narration, one WAV per sentence (Piper, voice en_US-hfc_male-medium, pace 1.2). A sentence keeps its audio while its text, the voice and the pace don't change. |
| record.py | Records each take on the live site with Playwright. Actions wait for the sentence they belong to (`t.at(scene, k)`); when the site is slow, later sentences move back, so the voice never runs ahead. |
| build.py | Places each sentence's audio where it fell, fits each recording back onto the clock, and joins everything into magellon-tutorial.mp4 with chapters and subtitles. |

## Keeping picture and voice together

Two things kept them apart in the first version, and both are handled now:

- **Waiting on the site.** Actions are tied to sentences, not to guessed times; a
  late action moves the rest of the narration back by the delay.
- **The recording runs slow.** Playwright's video runs 4-12% slower than the clock
  when the browser is busy. The page is recorded 8 px taller than shown; at every
  sentence the recorder flashes a colour in that strip (cropped away later), and
  build.py finds the flashes and stretches each stretch of video between two of
  them back to its real length.

Long waits (a test run, Topaz picking) are cut out with `t.wait_cut`.

## Rebuilding

1. Edit narration.md, then run tts_scenes.py (python:3.11-slim with piper-tts):
   `python tts_scenes.py narration.md voices/en_US-hfc_male-medium.onnx audio`
2. Record the takes whose scenes changed: `python record.py <take> ...` in the
   magellon-guide image, with the narration at /audio, output at /out, tokens from
   ../user-guide/shoot/mint_tokens.py in GUIDE_TOKENS, and the Leginon demo data at /data.
3. Run build.py in the same image.

Takes: view, import, done, test, pick, stop, export, admin, close.

- **import** starts a real import of 24dec03a as TOUR_SESSION (default
  24dec03a_tour), which the other takes then show; it must be finished (about an
  hour) before recording view, done, pick and close.
- **stop** starts 24dec03a_stopdemo and stops it, which deletes it.
- **export** deletes the session epu_deletedemo; import it first (EPU tab, folder
  epudata_jan, about 10 minutes).
- **pick** saves a picking record in the tour session.
- The other takes change nothing.
