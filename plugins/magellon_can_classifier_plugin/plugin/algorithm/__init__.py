"""CAN classifier algorithm — vendored from Sandbox/magellon_can_classifier.

Phase 7b (2026-05-03). Re-exports the public API needed by the
plugin's compute layer. The implementation lives in ``classifier.py``
(1714 lines copied verbatim) and depends on numpy + scipy
unconditionally; on torch / scikit-image / scikit-learn for the
GPU-accelerated paths (loaded lazily inside the relevant functions).

The plugin's ``compute.classify_stack`` is the one consumer; STAR
parsing + per-particle ndarray loading live there, not here, so the
algorithm crate stays focused on "particles in, classes out".
"""
from __future__ import annotations

from plugin.algorithm.classifier import (
    CanParams,
    class_half_averages,
    frc_curve,
    frc_resolution,
    preprocess_stack,
    run_align_and_can,
)

__all__ = [
    "CanParams",
    "class_half_averages",
    "frc_curve",
    "frc_resolution",
    "preprocess_stack",
    "run_align_and_can",
]
