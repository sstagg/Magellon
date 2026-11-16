"""Join the recorded takes, narration and title cards into the tutorial video.

    python build.py

Reads /audio (tts_scenes.py) and /out/<take> (record.py), writes
/out/final/magellon-tutorial.mp4 with chapter markers and a subtitle track,
and magellon-tutorial.srt beside it. Each sentence's audio goes where
record.py says it fell in the video, so speech and picture stay together.
Runs in the guide image (ffmpeg, Playwright).
"""
import json
import os
import subprocess
import wave

from playwright.sync_api import sync_playwright

AUDIO = "/audio"
OUT = "/out"
FINAL = f"{OUT}/final"
NARRATION = json.load(open(f"{AUDIO}/scenes.json"))
SCENES, RATE = NARRATION["scenes"], NARRATION["rate"]
FPS = 30

# The video in order: ("card", title, subtitle, seconds or a scene spoken over it),
# ("chapter", title, subtitle) or ("take", name).
PLAN = [
    ("card", "Magellon", "A guided tour", "1.1"),
    ("chapter", "For everyone", "Viewing a session"),
    ("take", "view"),
    ("chapter", "For Members", "Importing and processing"),
    ("take", "import"),
    ("card", "About an hour later", "", 2.0),
    ("take", "done"),
    ("take", "test"),
    ("take", "pick"),
    ("take", "stop"),
    ("take", "export"),
    ("chapter", "For administrators", "Accounts and the processing services"),
    ("take", "admin"),
    ("take", "close"),
    ("card", "magellon.rcc.fsu.edu", "Questions: ask a Magellon administrator", 4),
]
CHAPTER_SECONDS = 2.5

CARD_HTML = """<!doctype html><html><head><meta charset="utf-8"><style>
html,body{margin:0;width:1920px;height:1080px;background:#0a1929;color:#e3f2fd;
font-family:'Segoe UI',Roboto,'Helvetica Neue',Arial,sans-serif;display:flex;align-items:center;justify-content:center}
.box{text-align:center;max-width:1500px}
.kicker{font-size:30px;letter-spacing:6px;text-transform:uppercase;color:#4fc3f7;margin-bottom:24px}
h1{font-size:104px;margin:0 0 28px;font-weight:600}
p{font-size:40px;margin:0;color:#90caf9;line-height:1.4}
.bar{width:160px;height:6px;background:#4fc3f7;margin:36px auto 0;border-radius:3px}
</style></head><body><div class="box">{kicker}<h1>{title}</h1><p>{subtitle}</p><div class="bar"></div></div></body></html>"""


def run(*args):
    subprocess.run(args, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)


def encode_args():
    return ["-c:v", "libx264", "-preset", "medium", "-crf", "20", "-pix_fmt", "yuv420p", "-r", str(FPS),
            "-c:a", "aac", "-b:a", "160k", "-ar", "48000", "-ac", "2"]


def narration_track(sentences, seconds, path):
    """A WAV of the given length with each sentence's audio at its start time."""
    track = bytearray(b"\x00\x00" * int(RATE * seconds))
    for s in sentences:
        with wave.open(f"{AUDIO}/{s['file']}") as w:
            pcm = w.readframes(w.getnframes())
        at = int(s["start"] * RATE) * 2
        end = min(len(track), at + len(pcm))
        track[at:end] = pcm[:end - at]
    with wave.open(path, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(RATE)
        w.writeframes(bytes(track))


def card_image(browser, name, title, subtitle, kicker=""):
    page = browser.new_page(viewport={"width": 1920, "height": 1080})
    html = (CARD_HTML.replace("{title}", title).replace("{subtitle}", subtitle)
            .replace("{kicker}", f'<div class="kicker">{kicker}</div>' if kicker else ""))
    page.set_content(html)
    path = f"{FINAL}/{name}.png"
    page.screenshot(path=path)
    page.close()
    return path


def card_segment(image, seconds, audio, out):
    if audio:
        run("ffmpeg", "-y", "-loop", "1", "-framerate", str(FPS), "-i", image, "-i", audio,
            "-t", f"{seconds:.3f}", *encode_args(), out)
    else:
        run("ffmpeg", "-y", "-loop", "1", "-framerate", str(FPS), "-i", image,
            "-f", "lavfi", "-i", "anullsrc=r=48000:cl=stereo", "-t", f"{seconds:.3f}", *encode_args(), out)


def find_marks(video, width, height, strip, colours):
    """[(seconds into the recording, colour index)] of the sync flashes in the strip below the page."""
    rgb = [tuple(int(c[i:i + 2], 16) for i in (1, 3, 5)) for c in colours]
    fps = 50
    raw = subprocess.run(["ffmpeg", "-loglevel", "error", "-i", video, "-vf",
                          f"crop={width}:{strip - 2}:0:{height + 1},scale=48:1,fps={fps}",
                          "-f", "rawvideo", "-pix_fmt", "rgb24", "-"], capture_output=True, check=True).stdout
    found, current = [], None
    for i in range(len(raw) // 144):
        px = raw[i * 144:(i + 1) * 144]
        mean = [sum(px[c::3]) / 48 for c in range(3)]
        colour = next((k for k, (r, g, b) in enumerate(rgb)
                       if all(abs(m - v) < 70 for m, v in zip(mean, (r, g, b)))), None)
        if colour is not None and colour != current:
            found.append((i / fps, colour))
        current = colour
    return found


def match_marks(expected, found):
    """Pair the flashes made with the ones found, in order; a flash missing on either side is skipped."""
    pairs, j = [], 0
    for i, (real, colour) in enumerate(expected):
        while j < len(found) and found[j][1] != colour:
            if i + 1 < len(expected) and found[j][1] == expected[i + 1][1]:
                break  # this flash is missing from the video
            j += 1
        if j < len(found) and found[j][1] == colour:
            pairs.append((real, found[j][0]))
            j += 1
    return pairs


def fitted_video(meta, video):
    """A filter graph putting the recording back on the clock, without the cuts: [v] is the take."""
    width, height = meta["crop"]
    found = match_marks(meta["marks"], find_marks(video, width, height, meta["strip"], meta["mark_colours"]))
    if len(found) < 2:
        raise SystemExit(f"{video}: only {len(found)} sync marks found")
    # A mark missing from the video (a dropped frame) is placed from its neighbours, at the local
    # rate: the marks at the edges of a cut must all be there for the cut to land in the right place.
    seen = dict(found)
    pairs = []
    for real, _ in meta["marks"]:
        if real in seen:
            pairs.append((real, seen[real]))
            continue
        before = [p for p in found if p[0] < real][-2:]
        after = [p for p in found if p[0] > real][:2]
        a, b = (before[-1], after[0]) if before and after else ((before or after)[0], (before or after)[-1])
        rate = (b[1] - a[1]) / (b[0] - a[0]) if b[0] != a[0] else 1.0
        pairs.append((real, a[1] + (real - a[0]) * rate))
    cuts = meta.get("cuts", [])
    pieces = []
    for (r0, v0), (r1, v1) in zip(pairs, pairs[1:]):
        if v1 <= v0 or any(r0 >= a - 0.01 and r1 <= b + 0.01 for a, b in cuts):
            continue
        pieces.append((v0, v1, (r1 - r0) / (v1 - v0)))
    graph = f"[0:v]split={len(pieces)}" + "".join(f"[s{i}]" for i in range(len(pieces))) + ";"
    graph += "".join(f"[s{i}]trim=start={v0:.3f}:end={v1:.3f},setpts=(PTS-STARTPTS)*{k:.5f}[p{i}];"
                     for i, (v0, v1, k) in enumerate(pieces))
    graph += "".join(f"[p{i}]" for i in range(len(pieces))) + f"concat=n={len(pieces)}:v=1:a=0[cat];"
    graph += f"[cat]crop={width}:{height}:0:0,scale=1920:1080:flags=lanczos,fps={FPS},setsar=1"
    print(f"   {len(found)} of {len(meta['marks'])} sync marks found; "
          f"recording ran {100 * (sum(v1 - v0 for v0, v1, _ in pieces) / sum((v1 - v0) * k for v0, v1, k in pieces) - 1):+.0f}% against the clock")
    return graph


def take_segment(name, out):
    meta = json.load(open(f"{OUT}/{name}/take.json"))
    sentences = meta["sentences"]
    spoken_end = max((s["start"] + s["length"] for s in sentences), default=0) + 0.5
    length = max(meta["length"], spoken_end)
    audio = f"{FINAL}/{name}.wav"
    narration_track(sentences, length, audio)
    hold = max(0.0, length - meta["length"]) + 1.0
    graph = fitted_video(meta, f"{OUT}/{name}/video.webm") + f",tpad=stop_mode=clone:stop_duration={hold:.3f}[v]"
    run("ffmpeg", "-y", "-i", f"{OUT}/{name}/video.webm", "-i", audio, "-filter_complex", graph,
        "-map", "[v]", "-map", "1:a", "-t", f"{length:.3f}", *encode_args(), out)
    return length, sentences


def subtitle_lines(sentence, offset):
    """A sentence, split at commas when long, timed by length."""
    pieces, text = [], sentence["text"]
    while len(text) > 80:
        cut = text.rfind(", ", 0, 80)
        if cut < 25:
            cut = text.rfind(" ", 0, 80)
        pieces.append(text[:cut + 1].strip())
        text = text[cut + 1:].strip()
    if text:
        pieces.append(text)
    total = sum(len(p) for p in pieces) or 1
    t = offset + sentence["start"]
    for piece in pieces:
        span = sentence["length"] * len(piece) / total
        yield t, t + span, piece
        t += span


def srt_time(seconds):
    ms = int(round(seconds * 1000))
    return f"{ms // 3600000:02}:{ms // 60000 % 60:02}:{ms // 1000 % 60:02},{ms % 1000:03}"


def main():
    os.makedirs(FINAL, exist_ok=True)
    segments, subtitles, chapters, clock = [], [], [], 0.0
    with sync_playwright() as p:
        browser = p.chromium.launch()
        for i, item in enumerate(PLAN):
            out = f"{FINAL}/seg{i:02}.mp4"
            kind = item[0]
            if kind in ("card", "chapter"):
                title, subtitle = item[1], item[2]
                image = card_image(browser, f"card{i:02}", title, subtitle, "Chapter" if kind == "chapter" else "")
                spoken = item[3] if kind == "card" and isinstance(item[3], str) else None
                sentences = []
                if spoken:
                    lead = 1.0
                    sentences = [{**s, "start": s["start"] + lead} for s in SCENES[spoken]["sentences"]]
                    seconds = lead + SCENES[spoken]["duration"] + 1.0
                    narration_track(sentences, seconds, f"{FINAL}/card{i:02}.wav")
                else:
                    seconds = item[3] if kind == "card" else CHAPTER_SECONDS
                card_segment(image, seconds, f"{FINAL}/card{i:02}.wav" if spoken else None, out)
                if kind == "chapter" or i == 0:
                    chapters.append((clock, title if i else "Welcome"))
            else:
                if not os.path.exists(f"{OUT}/{item[1]}/take.json"):
                    print("missing take", item[1])
                    continue
                seconds, sentences = take_segment(item[1], out)
            for sentence in sentences:
                subtitles.extend(subtitle_lines(sentence, clock))
            segments.append(out)
            clock += seconds
            print(f"{i:2} {kind:7} {seconds:6.1f}s  total {clock / 60:5.2f} min")
        browser.close()

    with open(f"{FINAL}/list.txt", "w") as f:
        f.writelines(f"file '{s}'\n" for s in segments)
    run("ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", f"{FINAL}/list.txt", "-c", "copy", f"{FINAL}/joined.mp4")

    srt = f"{FINAL}/magellon-tutorial.srt"
    with open(srt, "w") as f:
        for n, (a, b, text) in enumerate(subtitles, 1):
            f.write(f"{n}\n{srt_time(a)} --> {srt_time(b)}\n{text}\n\n")
    with open(f"{FINAL}/chapters.txt", "w") as f:
        f.write(";FFMETADATA1\ntitle=Magellon: a guided tour\n")
        ends = [c[0] for c in chapters[1:]] + [clock]
        for (start, title), end in zip(chapters, ends):
            f.write(f"[CHAPTER]\nTIMEBASE=1/1000\nSTART={int(start * 1000)}\nEND={int(end * 1000)}\ntitle={title}\n")
    # One even loudness for the whole narration; the video is copied as it is.
    run("ffmpeg", "-y", "-i", f"{FINAL}/joined.mp4", "-i", srt, "-i", f"{FINAL}/chapters.txt",
        "-map", "0:v", "-map", "0:a", "-map", "1", "-map_metadata", "2", "-map_chapters", "2",
        "-c:v", "copy", "-af", "highpass=f=70,loudnorm=I=-16:TP=-1.5:LRA=11", "-c:a", "aac", "-b:a", "160k",
        "-ar", "48000", "-c:s", "mov_text", "-metadata:s:s:0", "language=eng",
        "-movflags", "+faststart", f"{FINAL}/magellon-tutorial.mp4")
    print(f"done: {clock / 60:.1f} min, {len(subtitles)} subtitles, {len(chapters)} chapters")


if __name__ == "__main__":
    main()
