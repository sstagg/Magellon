"""Unit tests for the in-process result-processor (P3).

Pin the contracts the projection layer must hold, regardless of which
queue or category sent the message:

  - ImageJobTask.status_id and stage advance to the right values for the
    completed/failed × motioncor/ctf matrix.
  - A missing task_id or row is handled silently — the consumer must
    not crash on a stray result whose row has been GC'd.
  - The OutQueueConfig list maps queue_type → category/dir_name.
  - The OUT_QUEUES default ([]) leaves the consumer dormant — the
    safety valve that lets deployments adopt the in-process processor
    without forcing a config change.
"""
from __future__ import annotations

from unittest.mock import MagicMock
from uuid import uuid4

import pytest

from models.pydantic_models_settings import OutQueueConfig, OutQueueType
from services.task_output_processor import (
    STATUS_COMPLETED,
    STATUS_FAILED,
    TaskOutputProcessor,
)


class _StubType:
    def __init__(self, code: int, name: str) -> None:
        self.code = code
        self.name = name


class _StubStatus:
    def __init__(self, code: int) -> None:
        self.code = code


class _StubResult:
    def __init__(
        self,
        *,
        task_id,
        type_code,
        type_name="t",
        status_code=None,
        plugin_id=None,
        plugin_version=None,
        subject_kind=None,
        subject_id=None,
    ):
        self.task_id = task_id
        self.type = _StubType(type_code, type_name)
        self.status = _StubStatus(status_code) if status_code is not None else None
        self.image_id = uuid4()
        self.image_path = "/tmp/img.mrc"
        self.session_name = "sess1"
        self.output_files = []
        self.output_data = None
        self.meta_data = None
        self.plugin_id = plugin_id
        self.plugin_version = plugin_version
        # Phase 3b — runner stamps these onto every result.
        self.subject_kind = subject_kind
        self.subject_id = subject_id


def _make_processor(db_task=None, out_queues=None):
    """Build a TaskOutputProcessor with a stub DB session.

    Bypasses ``__init__``'s settings lookup so the tests don't need
    a populated AppSettingsSingleton.
    """
    db = MagicMock()
    db.query.return_value.filter.return_value.first.return_value = db_task
    proc = TaskOutputProcessor.__new__(TaskOutputProcessor)
    proc.db = db
    proc.magellon_home_dir = "/tmp/magellon"
    proc._queue_type_output_config = (
        TaskOutputProcessor._build_queue_type_output_config(out_queues or [])
    )
    return proc, db


# ---------------------------------------------------------------------------
# State machine
# ---------------------------------------------------------------------------

def test_advance_motioncor_completed_sets_stage_1():
    db_task = MagicMock(status_id=0, stage=0)
    proc, _ = _make_processor(db_task)
    proc._advance_task_state(_StubResult(task_id=uuid4(), type_code=5), status_id=STATUS_COMPLETED)
    assert db_task.status_id == STATUS_COMPLETED
    assert db_task.stage == 1


def test_advance_ctf_failed_sets_stage_2():
    db_task = MagicMock(status_id=0, stage=0)
    proc, _ = _make_processor(db_task)
    proc._advance_task_state(_StubResult(task_id=uuid4(), type_code=2), status_id=STATUS_FAILED)
    assert db_task.status_id == STATUS_FAILED
    assert db_task.stage == 2


def test_unknown_type_lands_at_default_stage_99():
    """Operators look for stage=99 to find rows from an unrecognised
    task type — that's the failure-mode signal we lose if we pick a
    real stage as the default."""
    db_task = MagicMock(status_id=0, stage=0)
    proc, _ = _make_processor(db_task)
    proc._advance_task_state(_StubResult(task_id=uuid4(), type_code=99), status_id=STATUS_COMPLETED)
    assert db_task.stage == 99


def test_advance_skips_when_task_id_is_none():
    """A result with no task_id must not crash the consumer — log + skip."""
    proc, db = _make_processor(db_task=None)
    proc._advance_task_state(_StubResult(task_id=None, type_code=5), status_id=STATUS_COMPLETED)
    db.query.assert_not_called()


def test_advance_skips_when_row_missing():
    """The row may have been deleted between dispatch and result. Don't
    raise — log and move on so the broker can ack the message."""
    proc, _ = _make_processor(db_task=None)
    # Should not raise.
    proc._advance_task_state(_StubResult(task_id=uuid4(), type_code=5), status_id=STATUS_COMPLETED)


# ---------------------------------------------------------------------------
# Queue-config lookup
# ---------------------------------------------------------------------------

def test_queue_config_maps_type_to_category_and_dir():
    """The OUT_QUEUES list is the single source of truth for which
    on-disk subfolder + DB category each result lands under."""
    cfg = [
        OutQueueConfig(name="ctf_out", queue_type=OutQueueType.CTF, dir_name="ctf", category=2),
        OutQueueConfig(name="mc_out", queue_type=OutQueueType.MOTIONCOR, dir_name="fao", category=3),
    ]
    proc, _ = _make_processor(out_queues=cfg)
    assert proc._get_queue_type_output_dir("ctf") == "ctf"
    assert proc._get_queue_type_category("ctf") == 2
    assert proc._get_queue_type_output_dir("motioncor") == "fao"
    assert proc._get_queue_type_category("motioncor") == 3


def test_queue_config_returns_none_for_unknown_type():
    proc, _ = _make_processor(out_queues=[])
    assert proc._get_queue_type_output_dir("ctf") is None
    assert proc._get_queue_type_category("ctf") is None


# ---------------------------------------------------------------------------
# Provenance (P4)
# ---------------------------------------------------------------------------

def test_provenance_written_when_plugin_supplies_it():
    """A plugin that publishes its identity must show up in the row.
    This is the audit-trail guarantee operators rely on when chasing
    'which engine produced this defocus value?'."""
    db_task = MagicMock(status_id=0, stage=0, plugin_id=None, plugin_version=None)
    proc, _ = _make_processor(db_task)
    result = _StubResult(
        task_id=uuid4(),
        type_code=2,
        plugin_id="ctf-ctffind",
        plugin_version="4.1.14",
    )

    proc._advance_task_state(result, status_id=STATUS_COMPLETED)

    assert db_task.plugin_id == "ctf-ctffind"
    assert db_task.plugin_version == "4.1.14"


def test_provenance_preserved_when_plugin_omits_it():
    """A retry from an older plugin (no provenance fields) must NOT
    erase what the previous attempt recorded — the audit trail favours
    what we know over what we don't."""
    db_task = MagicMock(status_id=0, stage=0, plugin_id="ctf-ctffind", plugin_version="4.1.14")
    proc, _ = _make_processor(db_task)
    result = _StubResult(task_id=uuid4(), type_code=2)  # no provenance

    proc._advance_task_state(result, status_id=STATUS_COMPLETED)

    assert db_task.plugin_id == "ctf-ctffind"
    assert db_task.plugin_version == "4.1.14"


def test_destination_dir_falls_back_to_type_name_when_no_config():
    """If the deployer didn't list this queue_type, we still get a
    sensible folder named after the task type — keeps results visible
    instead of routing them to ``/None/``."""
    proc, _ = _make_processor(out_queues=[])
    result = _StubResult(task_id=uuid4(), type_code=5, type_name="MotionCor")
    dest = proc._get_destination_dir(result)
    # OS-agnostic: assert the segments are present, not the slash.
    parts = dest.replace("\\", "/").split("/")
    assert parts[-1] == "img"
    assert parts[-2] == "motioncor"


# ---------------------------------------------------------------------------
# Phase 5+7: artifact projection for PARTICLE_EXTRACTION + TWO_D_CLASSIFICATION
# ---------------------------------------------------------------------------
# Tests below target the artifact-row write that closes the loop on
# ratified rules 1, 2, 6 (project_artifact_bus_invariants.md):
#   * rule 1 — only refs and scalar summaries land on the row
#   * rule 2 — STI table; promoted hot columns + data_json long tail
#   * rule 6 — every call writes a NEW row (never UPDATE)


def _extraction_result(task_id=None, status_code=None, **out_overrides):
    """Synthetic PARTICLE_EXTRACTION (code 10) result for test cases."""
    out = {
        "mrcs_path": "/work/sess/extract/m_particles.mrcs",
        "star_path": "/work/sess/extract/m_particles.star",
        "json_path": "/work/sess/extract/m_particles.json",
        "particle_count": 42,
        "apix": 1.23,
        "box_size": 256,
        "edge_width": 2,
    }
    out.update(out_overrides)
    result = _StubResult(
        task_id=task_id or uuid4(),
        type_code=10,
        type_name="ParticleExtraction",
        status_code=status_code,
    )
    result.output_data = out
    result.job_id = uuid4()
    return result


def _classification_result(task_id=None, status_code=None, **out_overrides):
    """Synthetic TWO_D_CLASSIFICATION (code 4) result for test cases."""
    stack_id = str(uuid4())
    out = {
        "class_averages_path": "/work/sess/can/class_averages.mrcs",
        "assignments_csv_path": "/work/sess/can/assignments.csv",
        "class_counts_csv_path": "/work/sess/can/class_counts.csv",
        "run_summary_path": "/work/sess/can/run_summary.json",
        "iteration_history_path": None,
        "aligned_stack_path": None,
        "num_classes_emitted": 50,
        "num_particles_classified": 20000,
        "source_particle_stack_id": stack_id,
        "apix": 1.23,
    }
    out.update(out_overrides)
    result = _StubResult(
        task_id=task_id or uuid4(),
        type_code=4,
        type_name="TwoDClassification",
        status_code=status_code,
    )
    result.output_data = out
    result.job_id = uuid4()
    return result


def test_extraction_writes_particle_stack_artifact_with_promoted_columns():
    """Rule 2: hot columns (mrcs_path, star_path, particle_count, apix,
    box_size) land as real attributes; long-tail (json_path, edge_width,
    source_micrograph_path) goes in data_json."""
    from models.sqlalchemy_models import Artifact

    proc, db = _make_processor()
    result = _extraction_result()

    artifact_id = proc._maybe_write_artifact(result)

    assert artifact_id is not None
    assert db.add.call_count == 1
    written = db.add.call_args[0][0]
    assert isinstance(written, Artifact)
    assert written.kind == "particle_stack"
    assert written.producing_job_id == result.job_id
    assert written.producing_task_id == result.task_id
    assert written.msession_id == "sess1"
    assert written.mrcs_path == "/work/sess/extract/m_particles.mrcs"
    assert written.star_path == "/work/sess/extract/m_particles.star"
    assert written.particle_count == 42
    assert written.apix == 1.23
    assert written.box_size == 256
    # data_json carries the long-tail metadata.
    assert written.data_json["json_path"] == "/work/sess/extract/m_particles.json"
    assert written.data_json["edge_width"] == 2


def test_classification_writes_class_averages_artifact_with_lineage():
    """Rule 6: classifier output preserves source_particle_stack_id in
    data_json so the lineage graph stays traversable from class
    averages back to the source stack."""
    from models.sqlalchemy_models import Artifact

    proc, db = _make_processor()
    result = _classification_result()
    expected_source = result.output_data["source_particle_stack_id"]

    artifact_id = proc._maybe_write_artifact(result)

    assert artifact_id is not None
    written = db.add.call_args[0][0]
    assert isinstance(written, Artifact)
    assert written.kind == "class_averages"
    assert written.mrcs_path == "/work/sess/can/class_averages.mrcs"
    assert written.particle_count == 20000  # # of particles classified
    assert written.apix == 1.23
    assert written.star_path is None  # class averages have no STAR
    # Lineage + the long-tail outputs ride in data_json.
    assert written.data_json["assignments_csv_path"] == "/work/sess/can/assignments.csv"
    assert written.data_json["class_counts_csv_path"] == "/work/sess/can/class_counts.csv"
    assert written.data_json["num_classes_emitted"] == 50
    assert written.data_json["source_particle_stack_id"] == expected_source


def test_artifact_writer_skips_unrelated_categories():
    """CTF/MotionCor/etc. don't produce artifacts — the writer must
    return None and not call db.add. Otherwise we'd litter the table
    with single-image artifact rows that nothing references."""
    proc, db = _make_processor()
    result = _StubResult(task_id=uuid4(), type_code=2)  # CTF
    result.output_data = {"defocus_u": 12000, "defocus_v": 12100}

    assert proc._maybe_write_artifact(result) is None
    db.add.assert_not_called()


def test_artifact_writer_handles_missing_type():
    """A result with no ``type`` (rare; legacy plugins) must not crash
    the writer — return None and let downstream projection skip."""
    proc, db = _make_processor()
    result = _StubResult(task_id=uuid4(), type_code=10)
    result.type = None
    result.output_data = {"mrcs_path": "/x"}

    assert proc._maybe_write_artifact(result) is None
    db.add.assert_not_called()


def test_repeated_extraction_results_each_get_a_fresh_artifact_id():
    """Ratified rule 6 — re-runs produce NEW rows. Two consecutive
    calls with the same task_id must yield two distinct artifact ids
    (no UPDATE semantics on the writer path)."""
    proc, _ = _make_processor()
    result_a = _extraction_result()
    result_b = _extraction_result(task_id=result_a.task_id)  # same task

    id_a = proc._maybe_write_artifact(result_a)
    id_b = proc._maybe_write_artifact(result_b)

    assert id_a is not None and id_b is not None
    assert id_a != id_b


def test_extraction_stage_is_7():
    """Phase 5: PARTICLE_EXTRACTION (code 10) → stage 7."""
    db_task = MagicMock(status_id=0, stage=0)
    proc, _ = _make_processor(db_task)
    result = _extraction_result()
    proc._advance_task_state(result, status_id=STATUS_COMPLETED)
    assert db_task.stage == 7


def test_classification_stage_is_8():
    """Phase 7: TWO_D_CLASSIFICATION (code 4) → stage 8."""
    db_task = MagicMock(status_id=0, stage=0)
    proc, _ = _make_processor(db_task)
    result = _classification_result()
    proc._advance_task_state(result, status_id=STATUS_COMPLETED)
    assert db_task.stage == 8


# ---------------------------------------------------------------------------
# process(): full projection for the new categories
# ---------------------------------------------------------------------------


def _make_processor_for_full_process(db_task=None, out_queues=None):
    """Like _make_processor but wires the bits process() touches:
    ``commit``, ``rollback``, ``close`` are MagicMocks, ``query``
    returns the supplied db_task. magellon_home_dir set so
    _get_destination_dir doesn't blow up."""
    db = MagicMock()
    db.query.return_value.filter.return_value.first.return_value = db_task
    proc = TaskOutputProcessor.__new__(TaskOutputProcessor)
    proc.db = db
    proc.magellon_home_dir = "/tmp/magellon"
    proc._queue_type_output_config = (
        TaskOutputProcessor._build_queue_type_output_config(out_queues or [])
    )
    return proc, db


def test_process_extraction_projects_particle_stack_id_back_to_output_data():
    """End-to-end through process(): the artifact row is written, its
    id is projected back into output_data['particle_stack_id'] BEFORE
    _save_output_data serialises the blob, so downstream consumers can
    address by id without re-querying."""
    db_task = MagicMock(status_id=0, stage=0, plugin_id=None, plugin_version=None)
    proc, db = _make_processor_for_full_process(db_task)
    result = _extraction_result(status_code=STATUS_COMPLETED)

    out = proc.process(result)

    # Artifact id surfaced in the return for caller logging.
    assert out["artifact_id"] is not None
    # Same id roundtripped into the result's output_data so the
    # ImageMetaData blob captures it.
    assert result.output_data["particle_stack_id"] == out["artifact_id"]
    # Stage advanced to 7, status to COMPLETED.
    assert db_task.stage == 7
    assert db_task.status_id == STATUS_COMPLETED


def test_process_classification_projects_class_averages_id():
    db_task = MagicMock(status_id=0, stage=0, plugin_id=None, plugin_version=None)
    proc, db = _make_processor_for_full_process(db_task)
    result = _classification_result(status_code=STATUS_COMPLETED)

    out = proc.process(result)

    assert out["artifact_id"] is not None
    assert result.output_data["class_averages_id"] == out["artifact_id"]
    assert db_task.stage == 8
    assert db_task.status_id == STATUS_COMPLETED


# ---------------------------------------------------------------------------
# Phase 3c: subject axis backfill from TaskResultMessage to ImageJobTask
# ---------------------------------------------------------------------------
# When the runner echoes subject_kind/subject_id (Phase 3b) onto a
# result, the projector backfills the row IF dispatch left the column
# at its DDL default ('image' for kind, NULL for id). Authoritative
# writes still come from dispatch — this is a back-compat seam for
# pre-Phase-3 importers that don't know about the new columns.


def test_subject_kind_backfilled_when_row_was_default_image():
    """A pre-Phase-3 importer leaves subject_kind at the DDL default
    'image'. If the result asserts something richer (particle_stack
    for a classifier task), the projector accepts the upgrade so the
    row's subject reflects reality."""
    db_task = MagicMock(
        status_id=0, stage=0, plugin_id=None, plugin_version=None,
        subject_kind="image", subject_id=None,
    )
    proc, _ = _make_processor(db_task)
    stack_id = uuid4()
    result = _StubResult(
        task_id=uuid4(), type_code=4, type_name="TwoDClassification",
        subject_kind="particle_stack", subject_id=stack_id,
    )

    proc._advance_task_state(result, status_id=STATUS_COMPLETED)

    assert db_task.subject_kind == "particle_stack"
    assert db_task.subject_id == stack_id


def test_subject_kind_not_overwritten_when_dispatch_already_set_it():
    """If the importer (post-Phase-3) already set subject_kind to a
    non-default value, the projector must NOT overwrite — dispatch is
    authoritative for the dispatch-time subject."""
    pinned_id = uuid4()
    db_task = MagicMock(
        status_id=0, stage=0, plugin_id=None, plugin_version=None,
        subject_kind="particle_stack", subject_id=pinned_id,
    )
    proc, _ = _make_processor(db_task)
    other_id = uuid4()
    result = _StubResult(
        task_id=uuid4(), type_code=4, type_name="TwoDClassification",
        subject_kind="session", subject_id=other_id,
    )

    proc._advance_task_state(result, status_id=STATUS_COMPLETED)

    # Dispatch wins.
    assert db_task.subject_kind == "particle_stack"
    assert db_task.subject_id == pinned_id


def test_subject_id_backfilled_when_dispatch_left_it_null():
    """The DDL default for subject_id is NULL — pre-Phase-3 dispatch
    leaves it that way. If the result carries the same kind ('image')
    plus a subject_id, the projector populates."""
    image_oid = uuid4()
    db_task = MagicMock(
        status_id=0, stage=0, plugin_id=None, plugin_version=None,
        subject_kind="image", subject_id=None,
    )
    proc, _ = _make_processor(db_task)
    result = _StubResult(
        task_id=uuid4(), type_code=2, type_name="CTF",
        subject_kind="image", subject_id=image_oid,
    )

    proc._advance_task_state(result, status_id=STATUS_COMPLETED)

    # subject_kind doesn't escalate (image → image is a no-op) but
    # subject_id is populated since the row had None.
    assert db_task.subject_kind == "image"
    assert db_task.subject_id == image_oid


def test_subject_backfill_skipped_when_result_omits_fields():
    """A pre-Phase-3b plugin (or one whose result_factory drops the
    fields) returns subject_kind/subject_id as None on the result.
    The projector must NOT clobber the row with None — leave it
    alone, the row keeps whatever dispatch set."""
    pinned_id = uuid4()
    db_task = MagicMock(
        status_id=0, stage=0, plugin_id=None, plugin_version=None,
        subject_kind="particle_stack", subject_id=pinned_id,
    )
    proc, _ = _make_processor(db_task)
    result = _StubResult(
        task_id=uuid4(), type_code=4, type_name="TwoDClassification",
        subject_kind=None, subject_id=None,
    )

    proc._advance_task_state(result, status_id=STATUS_COMPLETED)

    assert db_task.subject_kind == "particle_stack"
    assert db_task.subject_id == pinned_id


# ---------------------------------------------------------------------------
# 2026-05-04 reviewer fixes — Blocker / High / Medium regression guards
# ---------------------------------------------------------------------------


def test_high3_process_output_files_returns_path_remap(tmp_path):
    """Reviewer-flagged High #3: artifact paths went stale because the
    file-move ran BEFORE _maybe_write_artifact read paths from
    output_data. Fix: _process_output_files returns {src: dst} so the
    caller rewrites output_data first. Pin the contract."""
    from magellon_sdk.models import OutputFile

    proc, _ = _make_processor()

    src = tmp_path / "stack.mrcs"
    src.write_bytes(b"\x00" * 16)
    dest_dir = tmp_path / "dest"

    result = _StubResult(task_id=uuid4(), type_code=10, type_name="ParticleExtraction")
    result.output_files = [OutputFile(name="stack.mrcs", path=str(src), required=True)]

    remap = proc._process_output_files(result, str(dest_dir))

    assert str(src) in remap
    assert remap[str(src)] == str(dest_dir / "stack.mrcs")
    # The OutputFile in place was updated to the post-move path so
    # downstream consumers see the same value the artifact row will.
    assert result.output_files[0].path == str(dest_dir / "stack.mrcs")


def test_high3_rewrite_output_paths_updates_path_shaped_keys():
    """Path-shaped keys in output_data get rewritten to post-move
    destinations; scalar fields (counts, apix) are untouched."""
    proc, _ = _make_processor()
    result = _extraction_result()
    remap = {
        result.output_data["mrcs_path"]: "/moved/m_particles.mrcs",
        result.output_data["star_path"]: "/moved/m_particles.star",
        result.output_data["json_path"]: "/moved/m_particles.json",
    }
    pre_count = result.output_data["particle_count"]

    proc._rewrite_output_paths(result, remap)

    assert result.output_data["mrcs_path"] == "/moved/m_particles.mrcs"
    assert result.output_data["star_path"] == "/moved/m_particles.star"
    assert result.output_data["json_path"] == "/moved/m_particles.json"
    assert result.output_data["particle_count"] == pre_count
    assert result.output_data["apix"] == 1.23


def test_high5_classification_writes_source_artifact_id_fk():
    """Reviewer-flagged High #5: lineage as a real FK column.
    output_data['source_particle_stack_id'] becomes
    artifact.source_artifact_id (real FK) — the data_json copy stays
    as a back-compat key for one release."""
    from models.sqlalchemy_models import Artifact

    proc, db = _make_processor()
    stack_uuid = uuid4()
    result = _classification_result(source_particle_stack_id=str(stack_uuid))

    proc._maybe_write_artifact(result)

    written = db.add.call_args[0][0]
    assert isinstance(written, Artifact)
    assert written.source_artifact_id == stack_uuid
    # Back-compat copy still in data_json.
    assert written.data_json["source_particle_stack_id"] == str(stack_uuid)


def test_high5_classification_handles_invalid_source_id():
    """Defensive: non-UUID source_particle_stack_id leaves the FK as
    NULL rather than crashing the writer."""
    from models.sqlalchemy_models import Artifact

    proc, db = _make_processor()
    result = _classification_result()
    result.output_data["source_particle_stack_id"] = "not-a-uuid"

    proc._maybe_write_artifact(result)
    written = db.add.call_args[0][0]
    assert isinstance(written, Artifact)
    assert written.source_artifact_id is None


def test_blocker2_out_queue_type_includes_extraction_and_classification():
    """Reviewer-flagged Blocker #2: extraction + classification result
    queues had no enum entry, so the in-process consumer never
    subscribed → tasks never advanced and artifacts never wrote.
    Pin the enum so a regression here fails fast."""
    from models.pydantic_models_settings import OutQueueType

    assert OutQueueType.PARTICLE_EXTRACTION.value == "particle_extraction"
    assert OutQueueType.TWO_D_CLASSIFICATION.value == "two_d_classification"


def test_process_failed_extraction_does_not_write_artifact():
    """A FAILED result has no ``mrcs_path`` (the algorithm crashed
    before writing). Skip the artifact write — otherwise we'd land
    rows with NULL hot columns that no consumer can use."""
    from models.sqlalchemy_models import Artifact

    db_task = MagicMock(status_id=0, stage=0, plugin_id=None, plugin_version=None)
    proc, db = _make_processor_for_full_process(db_task)
    result = _extraction_result(status_code=STATUS_FAILED)
    # Wipe the output paths to model a real crash.
    result.output_data = {}

    out = proc.process(result)

    assert out["artifact_id"] is None
    artifact_adds = [
        c for c in db.add.call_args_list if isinstance(c[0][0], Artifact)
    ]
    assert artifact_adds == []
    assert db_task.status_id == STATUS_FAILED
