"""Contract pin tests for the CAN classifier plugin.

The 1714-line algorithm is not yet vendored (Phase 7b). These tests
mock ``compute.classify_stack`` to verify the SDK contract layer:
schemas match the category, manifest carries GPU + progress
capabilities, ``execute()`` round-trips a typed input/output, and the
result factory carries envelope identifiers + path refs only (rule 1).
"""
from __future__ import annotations

import sys
from pathlib import Path
from uuid import uuid4

import pytest


_PLUGIN_ROOT = Path(__file__).resolve().parents[1]
if str(_PLUGIN_ROOT) not in sys.path:
    sys.path.insert(0, str(_PLUGIN_ROOT))


# ---------------------------------------------------------------------------
# Contract
# ---------------------------------------------------------------------------


def test_input_and_output_schema_match_category_contract():
    from magellon_sdk.categories.contract import TWO_D_CLASSIFICATION_CATEGORY
    from plugin.plugin import CanClassifierPlugin

    assert (
        CanClassifierPlugin.input_schema()
        is TWO_D_CLASSIFICATION_CATEGORY.input_model
    )
    assert (
        CanClassifierPlugin.output_schema()
        is TWO_D_CLASSIFICATION_CATEGORY.output_model
    )


def test_get_info_matches_provenance():
    from plugin.plugin import CanClassifierPlugin

    info = CanClassifierPlugin().get_info()
    assert info.name == "CAN Classifier"
    assert info.version == "0.1.0"


def test_manifest_advertises_gpu_and_progress():
    from magellon_sdk.models.manifest import Capability, Transport
    from plugin.plugin import CanClassifierPlugin

    manifest = CanClassifierPlugin().manifest()
    assert Capability.GPU_REQUIRED in manifest.capabilities
    assert Capability.PROGRESS_REPORTING in manifest.capabilities
    assert manifest.default_transport == Transport.RMQ
    # Resource hints reflect the heavyweight nature of the algorithm.
    assert manifest.resources.memory_mb >= 4000
    assert manifest.resources.typical_duration_seconds >= 60


# ---------------------------------------------------------------------------
# execute() with mocked compute
# ---------------------------------------------------------------------------


def test_execute_round_trip_with_mocked_compute(monkeypatch, tmp_path):
    """Phase 7b vendors the algorithm; today execute() is verified
    against a mocked ``classify_stack``. Pin the wiring so the
    vendoring doesn't silently change the contract."""
    from magellon_sdk.categories.outputs import TwoDClassificationOutput
    from magellon_sdk.models.tasks import TwoDClassificationInput
    from plugin import plugin as plugin_mod

    # Synthetic input refs (don't have to exist — compute is mocked)
    inp = TwoDClassificationInput(
        particle_stack_id=uuid4(),
        mrcs_path=str(tmp_path / "stack.mrcs"),
        star_path=str(tmp_path / "stack.star"),
        output_dir=str(tmp_path / "out"),
        apix=1.23,
        num_classes=10,
        num_presentations=1000,
        align_iters=2,
    )

    captured = {}

    def _fake_classify(**kwargs):
        captured.update(kwargs)
        return {
            "class_averages_path": str(tmp_path / "out/class_averages.mrcs"),
            "assignments_csv_path": str(tmp_path / "out/assignments.csv"),
            "class_counts_csv_path": str(tmp_path / "out/class_counts.csv"),
            "run_summary_path": str(tmp_path / "out/run_summary.json"),
            "iteration_history_path": None,
            "aligned_stack_path": None,
            "num_classes_emitted": 10,
            "num_particles_classified": 1234,
            "apix": 1.23,
            "output_dir": str(tmp_path / "out"),
        }

    monkeypatch.setattr(plugin_mod, "classify_stack", _fake_classify)

    out = plugin_mod.CanClassifierPlugin().execute(inp)

    assert isinstance(out, TwoDClassificationOutput)
    assert out.num_classes_emitted == 10
    assert out.num_particles_classified == 1234
    assert out.class_averages_path.endswith("class_averages.mrcs")
    assert out.source_particle_stack_id == str(inp.particle_stack_id)
    # Compute saw the right knobs threaded through.
    assert captured["num_classes"] == 10
    assert captured["align_iters"] == 2
    assert captured["mrcs_path"] == str(tmp_path / "stack.mrcs")


def test_execute_propagates_compute_failure(monkeypatch, tmp_path):
    """A crash inside compute must re-raise so the runner classifies
    via P2's exception taxonomy (DLQ vs requeue)."""
    from magellon_sdk.models.tasks import TwoDClassificationInput
    from plugin import plugin as plugin_mod

    def _boom(**kwargs):
        raise RuntimeError("CAN training diverged")

    monkeypatch.setattr(plugin_mod, "classify_stack", _boom)

    inp = TwoDClassificationInput(
        mrcs_path=str(tmp_path / "stack.mrcs"),
        star_path=str(tmp_path / "stack.star"),
        output_dir=str(tmp_path / "out"),
    )
    with pytest.raises(RuntimeError, match="diverged"):
        plugin_mod.CanClassifierPlugin().execute(inp)


def test_compute_classify_stack_no_longer_raises_not_implemented():
    """Phase 7b (2026-05-03) vendored the algorithm into
    ``plugin/algorithm/classifier.py`` (1714 lines from
    Sandbox/magellon_can_classifier). compute.classify_stack now
    delegates instead of raising NotImplementedError. Pin so a future
    refactor doesn't accidentally re-stub it."""
    import inspect

    from plugin import compute as compute_mod

    # The function's body must reference the vendored module — pin
    # via inspect to catch a regression that re-stubs the body.
    src = inspect.getsource(compute_mod.classify_stack)
    assert "NotImplementedError" not in src or "raise NotImplementedError" not in src
    assert "from plugin.algorithm import" in src or "plugin.algorithm" in src


def test_algorithm_subpackage_exposes_run_align_and_can():
    """Pin the public API surface the plugin's compute layer depends
    on. If the vendored ``classifier.py`` reorganises and a name
    drops, this fails loudly here rather than at task-time."""
    from plugin.algorithm import (  # noqa: F401
        CanParams,
        class_half_averages,
        frc_curve,
        frc_resolution,
        preprocess_stack,
        run_align_and_can,
    )

    # CanParams is a dataclass; constructible with the documented
    # core kwargs (primary_learn/secondary_learn mirror the Sandbox
    # CLI's --learn / --ilearn).
    p = CanParams(
        num_classes=10,
        num_presentations=1000,
        primary_learn=0.01,
        secondary_learn=0.0005,
        max_age=200,
    )
    assert p.num_classes == 10
    assert p.num_presentations == 1000
    assert p.primary_learn == 0.01


def test_execute_propagates_filesystem_error_from_missing_star(tmp_path):
    """End-to-end smoke against a missing STAR — the algorithm's
    file I/O surfaces a clear error rather than silently succeeding.
    Regression guard: pre-Phase-7b this raised NotImplementedError
    BEFORE touching the disk; post-vendor it must hit the FS layer
    and report a usable diagnostic."""
    from magellon_sdk.models.tasks import TwoDClassificationInput
    from plugin import plugin as plugin_mod

    inp = TwoDClassificationInput(
        mrcs_path=str(tmp_path / "stack.mrcs"),
        star_path=str(tmp_path / "missing.star"),
        output_dir=str(tmp_path / "out"),
    )
    with pytest.raises((FileNotFoundError, RuntimeError, OSError)):
        plugin_mod.CanClassifierPlugin().execute(inp)


# ---------------------------------------------------------------------------
# Result factory — wire shape only carries refs + summaries (rule 1)
# ---------------------------------------------------------------------------


def test_build_classification_result_carries_refs_only():
    from magellon_sdk.categories.outputs import TwoDClassificationOutput
    from magellon_sdk.models import TaskMessage
    from plugin.plugin import build_classification_result

    job_id = uuid4()
    task_id = uuid4()
    task = TaskMessage(id=task_id, job_id=job_id, data={})
    output = TwoDClassificationOutput(
        class_averages_path="/work/can/class_averages.mrcs",
        assignments_csv_path="/work/can/assignments.csv",
        class_counts_csv_path="/work/can/class_counts.csv",
        run_summary_path="/work/can/run_summary.json",
        num_classes_emitted=50,
        num_particles_classified=20000,
        apix=1.23,
        source_particle_stack_id=str(uuid4()),
    )

    result = build_classification_result(task, output)

    assert result.job_id == job_id
    assert result.task_id == task_id
    assert result.code == 200
    # Rule 1: result carries paths + scalar summaries; never inline
    # mrcs/csv content.
    assert result.output_data["class_averages_path"] == "/work/can/class_averages.mrcs"
    assert result.output_data["num_classes_emitted"] == 50
    assert result.output_data["num_particles_classified"] == 20000
    # All four output files shape up correctly.
    file_names = {f.name for f in result.output_files}
    assert "class_averages.mrcs" in file_names
    assert "assignments.csv" in file_names
    assert "class_counts.csv" in file_names
    assert "run_summary.json" in file_names
