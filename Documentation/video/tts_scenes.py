"""Narration audio for the tutorial video: one WAV per sentence, from narration.md.

Each scene's spoken text (everything that isn't a heading or a [bracketed]
stage direction) is split into sentences, and each sentence is synthesised on
its own with Piper. record.py then waits for a sentence before doing what it
describes, and build.py places each sentence's audio where its action happened,
so the voice can never run ahead of the picture.

audio/scenes.json lists, per scene, its sentences: text, paragraph, file,
length, and where it falls in the scene when spoken without waiting (the gaps
between sentences and paragraphs below are the minimum pauses).

A sentence keeps its audio while its text, the voice and the pace are
unchanged: Piper never says a sentence exactly the same way twice.

    python tts_scenes.py narration.md voice.onnx out_dir
"""
import hashlib
import json
import os
import re
import sys
import wave

from piper import PiperVoice
from piper.config import SynthesisConfig

PACE = float(os.environ.get("TOUR_PACE", "1.2"))   # >1 is slower than the voice's default
SENTENCE_GAP = 0.45
PARAGRAPH_GAP = 0.9

# How the voice should say things the script writes for readers.
SPOKEN = [
    (r"C-T-F-FIND", "C T F find"),
    (r"C-T-F", "C T F"),
    (r"F-F-T", "F F T"),
    (r"E-P-U", "E P U"),
    (r"\bGPUs\b", "G P Us"),
    (r"\bSerialEM\b", "Serial E M"),
    (r"\bMotionCor\b", "Motion Cor"),
    (r"\bRELION\b", "Relion"),
]
# How subtitles should show them.
SHOWN = [(r"C-T-F-FIND", "CTFFIND"), (r"C-T-F", "CTF"), (r"F-F-T", "FFT"), (r"E-P-U", "EPU")]


def scenes(markdown: str):
    """[(scene id, title, [[sentence, ...] per paragraph])] in order."""
    out = []
    for block in re.split(r"^### ", markdown, flags=re.M)[1:]:
        heading, _, body = block.partition("\n")
        match = re.match(r"Scene (\S+)\s+(.*)", heading.strip())
        if not match:
            continue
        body = body.split("\n---")[0]
        paragraphs = [" ".join(p.split()) for p in re.split(r"\n\s*\n", body)]
        paragraphs = [p for p in paragraphs if p and not p.startswith("[") and not p.startswith("#")]
        out.append((match.group(1), match.group(2),
                    [[s for s in re.split(r"(?<=[.!?])\s+", p) if s] for p in paragraphs]))
    return out


def apply(rules, text):
    for pattern, replacement in rules:
        text = re.sub(pattern, replacement, text)
    return text


def main(markdown_path, model, out_dir):
    voice = PiperVoice.load(model)
    rate = voice.config.sample_rate
    config = SynthesisConfig(length_scale=PACE)
    voice_name = os.path.basename(model)
    index = {}
    for scene_id, title, paragraphs in scenes(open(markdown_path).read()):
        os.makedirs(f"{out_dir}/{scene_id}", exist_ok=True)
        sentences, at = [], 0.0
        for p, paragraph in enumerate(paragraphs):
            for s, sentence in enumerate(paragraph):
                if sentences:
                    at += SENTENCE_GAP if s else PARAGRAPH_GAP
                digest = hashlib.sha1(json.dumps([voice_name, PACE, sentence]).encode()).hexdigest()[:16]
                path = f"{out_dir}/{scene_id}/{digest}.wav"
                if not os.path.exists(path):
                    pcm = b"".join(chunk.audio_int16_bytes for chunk in
                                   voice.synthesize(apply(SPOKEN, sentence), syn_config=config))
                    with wave.open(path, "wb") as wf:
                        wf.setnchannels(1)
                        wf.setsampwidth(2)
                        wf.setframerate(rate)
                        wf.writeframes(pcm)
                with wave.open(path) as wf:
                    length = wf.getnframes() / wf.getframerate()
                sentences.append({"text": apply(SHOWN, sentence), "paragraph": p, "file": f"{scene_id}/{digest}.wav",
                                  "start": round(at, 3), "length": round(length, 3)})
                at += length
        index[scene_id] = {"title": title, "sentences": sentences, "duration": round(at, 3)}
        print(f"{scene_id:5} {at:6.1f}s  {len(sentences):2} sentences  {title}")
    json.dump({"voice": voice_name, "pace": PACE, "rate": rate, "scenes": index},
              open(f"{out_dir}/scenes.json", "w"), indent=1)
    print(f"total {sum(s['duration'] for s in index.values()) / 60:.1f} min (without waits)")


if __name__ == "__main__":
    main(*sys.argv[1:4])
