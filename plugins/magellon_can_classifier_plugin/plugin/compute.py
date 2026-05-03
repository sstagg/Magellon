"""CAN classifier compute glue.

Phase 7 (2026-05-03) ships the SDK contract (TWO_D_CLASSIFICATION_CATEGORY)
and the plugin scaffold. The 1714-line CAN algorithm in
``Sandbox/magellon_can_classifier/classifier.py`` is **not yet vendored
into this plugin** — it has heavy GPU dependencies (torch, skimage)
that warrant their own follow-up review before they ship in a docker
image.

Phase 7b vendoring strategy: copy ``Sandbox/magellon_can_classifier/{classifier,cli}.py``
into ``plugin/algorithm.py`` (or split into ``algorithm/__init__.py``
+ submodules), confirm the bug-fixes from
``MAGELLON_PARTICLE_PIPELINE.md`` (#1 image-token order — already
matches RELION since the classifier *reads* the new format; #2 pixel
size column — classifier already accepts ``_rlnImagePixelSize``), and
update ``classify_stack`` below to delegate to it.

In the meantime ``classify_stack`` raises NotImplementedError with a
pointer to the runbook. Plugin contract tests (``tests/``) can mock
``classify_stack`` and verify the SDK plumbing without the algorithm.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


def classify_stack(
    *,
    mrcs_path: str,
    star_path: str,
    output_dir: str,
    apix: Optional[float],
    num_classes: int,
    num_presentations: int,
    align_iters: int,
    threads: int,
    can_threads: int,
    compute_backend: str,
    max_particles: Optional[int],
    invert: bool,
    write_aligned_stack: bool,
    engine_opts: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Run CAN classification on a particle stack.

    Returns a summary dict consumed by :class:`CanClassifierPlugin.execute`:

        {
            "class_averages_path": str,
            "assignments_csv_path": str,
            "class_counts_csv_path": str,
            "run_summary_path": Optional[str],
            "iteration_history_path": Optional[str],
            "aligned_stack_path": Optional[str],
            "num_classes_emitted": int,
            "num_particles_classified": int,
            "apix": Optional[float],
            "output_dir": str,
        }

    Phase 7b: replace this body with a delegation to the vendored
    ``run_align_and_can(...)`` from ``plugin.algorithm``. Until then,
    raise — the plugin's contract tests mock this function.
    """
    raise NotImplementedError(
        "CAN classifier algorithm not yet vendored — Phase 7b. "
        "Source: Sandbox/magellon_can_classifier/{classifier,cli}.py. "
        "Vendor target: plugin/algorithm.py. "
        "Plugin contract tests mock this function; full integration "
        "requires the algorithm + GPU runtime."
    )
