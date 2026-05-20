"""Detector geometry constants shared across cryoassess.

These are plain facts about the supported cameras and the fixed network input
size.  They live in ``core`` -- and stay TensorFlow-free -- so the conversion
code, the benchmark, and the model layer all read them from one place instead
of each redefining ``494`` and the per-detector widths.
"""

from __future__ import annotations

# Fixed image height (pixels) the MicAssess models expect.  It doubles as the
# target height for MRC downsampling, since the downsampled micrograph is what
# the model consumes.
IMAGE_HEIGHT = 494

# Loaded-PNG width per detector.  The model graph crops this down to
# ``IMAGE_HEIGHT x IMAGE_HEIGHT`` before the CNN.
DETECTOR_WIDTH = {"K2": 512, "K3": 696}


def detector_width(detector: str) -> int:
    """Return the model input width for ``detector``; raise on an unknown one."""

    try:
        return DETECTOR_WIDTH[detector]
    except KeyError:
        raise ValueError(
            f"unknown detector {detector!r}; expected one of {sorted(DETECTOR_WIDTH)}"
        ) from None
