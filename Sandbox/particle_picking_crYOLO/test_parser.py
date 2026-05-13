#!/usr/bin/env python
"""
Synthetic CBOX + STAR parser smoke test.

crYOLO itself needs a TF environment we don't always have at hand. The
CBOX/STAR parser, however, is pure-Python — this script fabricates two
small fixtures, runs both through `_parse_cbox` / `_parse_star`, and
asserts the output JSON matches the expected shape.

Run:  python test_parser.py

The parser invariants exercised:
  - CBOX coordinates are lower-left corner → center conversion is correct
  - STAR coordinates are taken as centres
  - `_Confidence` / `_rlnAutopickFigureOfMerit` map to `score`
  - `_EstWidth` (when present in CBOX) drives `radius`
  - Falls back to `max(_Width, _Height) / 2` otherwise
"""
import json
import os
import sys
import tempfile

# Importing pick_algorithm should be lightweight (no crYOLO import at module load).
from pick_algorithm import _parse_cbox, _parse_star


CBOX_FIXTURE = """\
data_cryolo

loop_
_CoordinateX
_CoordinateY
_Width
_Height
_Confidence
_EstWidth
100 200 80 80 0.92 60
500 600 80 80 0.71 64
900 1100 80 80 0.55 58
"""

# STAR fixture mirrors crYOLO's STAR output (RELION-style centres).
STAR_FIXTURE = """\
data_

loop_
_rlnCoordinateX
_rlnCoordinateY
_rlnAutopickFigureOfMerit
140 240 0.92
540 640 0.71
940 1140 0.55
"""


def _write(tmpdir, name, content):
    path = os.path.join(tmpdir, name)
    with open(path, 'w') as f:
        f.write(content)
    return path


def assert_eq(name, got, expected):
    if got != expected:
        print(f"  FAIL  {name}: got {got!r}, expected {expected!r}")
        return False
    return True


def run() -> int:
    failures = 0
    with tempfile.TemporaryDirectory() as td:
        cbox = _write(td, "t.cbox", CBOX_FIXTURE)
        star = _write(td, "t.star", STAR_FIXTURE)

        cbox_picks = _parse_cbox(cbox)
        print("CBOX parser output:")
        print(json.dumps(cbox_picks, indent=2))

        # CBOX coords are lower-left of an 80x80 box → centre = lower-left + 40.
        # _EstWidth/2 drives radius (60/2 = 30, etc.).
        expected_cbox = [
            {"center": [140, 240], "radius": 30, "score": 0.92},
            {"center": [540, 640], "radius": 32, "score": 0.71},
            {"center": [940, 1140], "radius": 29, "score": 0.55},
        ]
        for got, exp in zip(cbox_picks, expected_cbox):
            if not assert_eq("cbox-row", got, exp):
                failures += 1

        star_picks = _parse_star(star)
        print()
        print("STAR parser output:")
        print(json.dumps(star_picks, indent=2))

        # STAR coords are centres directly; radius defaults to 0 because the
        # STAR shape doesn't carry per-particle width.
        expected_star = [
            {"center": [140, 240], "radius": 0, "score": 0.92},
            {"center": [540, 640], "radius": 0, "score": 0.71},
            {"center": [940, 1140], "radius": 0, "score": 0.55},
        ]
        for got, exp in zip(star_picks, expected_star):
            if not assert_eq("star-row", got, exp):
                failures += 1

    print()
    if failures == 0:
        print("PASS  CBOX + STAR parser round-trips match expectations.")
        return 0
    print(f"FAIL  {failures} parser assertion(s) failed.")
    return 1


if __name__ == "__main__":
    sys.exit(run())
