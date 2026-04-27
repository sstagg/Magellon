"""Characterization tests for the Task envelope on the wire.

Pins the JSON shape of CTF and MotionCor task envelopes so that any
future schema change is caught at test time rather than at runtime by
a downstream plugin.

To regenerate goldens after an intentional envelope change:

    UPDATE_GOLDENS=1 pytest tests/characterization/test_envelope_golden.py

Do not regenerate casually — the goldens are the on-the-wire contract.
"""
from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path
from uuid import UUID

import pytest

from models.plugins_models import (
    CTF_TASK,
    MOTIONCOR_TASK,
    PENDING,
    MotionCorInput,
    CtfInput,
    TaskMessage,
)

GOLDEN_DIR = Path(__file__).parent / "goldens"
UPDATE = os.environ.get("UPDATE_GOLDENS") == "1"

# --- deterministic inputs ---------------------------------------------------
# Frozen UUIDs and timestamps so the envelope dump is byte-stable.
FIXED_TASK_ID = UUID("00000000-0000-0000-0000-000000000001")
FIXED_JOB_ID = UUID("00000000-0000-0000-0000-000000000002")
FIXED_WORKER_ID = UUID("00000000-0000-0000-0000-000000000003")
FIXED_SESSION_ID = UUID("00000000-0000-0000-0000-000000000004")
FIXED_IMAGE_ID = UUID("00000000-0000-0000-0000-000000000005")
FIXED_DATETIME = datetime(2026, 4, 14, 0, 0, 0)


def _make_ctf_envelope() -> dict:
    """Build a canonical CTF task envelope — every field explicitly set."""
    data = CtfInput(
        image_id=FIXED_IMAGE_ID,
        image_name="sample",
        image_path="/data/sample.mrc",
        inputFile="/data/sample.mrc",
        outputFile="sample_ctf_output.mrc",
        pixelSize=1.0,
        accelerationVoltage=300.0,
        sphericalAberration=2.7,
        amplitudeContrast=0.07,
        sizeOfAmplitudeSpectrum=512,
        minimumResolution=30.0,
        maximumResolution=5.0,
        minimumDefocus=5000.0,
        maximumDefocus=50000.0,
        defocusSearchStep=100.0,
        binning_x=1,
    )
    task = TaskMessage(
        id=FIXED_TASK_ID,
        job_id=FIXED_JOB_ID,
        session_id=FIXED_SESSION_ID,
        session_name="sample_session",
        worker_instance_id=FIXED_WORKER_ID,
        data=data.model_dump(),
        status=PENDING,
        type=CTF_TASK,
        created_date=FIXED_DATETIME,
        start_on=None,
        end_on=None,
        result=None,
    )
    return task.model_dump(mode="json")


def _make_motioncor_envelope() -> dict:
    """Build a canonical MotionCor task envelope — every field explicitly set."""
    data = MotionCorInput(
        image_id=FIXED_IMAGE_ID,
        image_name="sample",
        image_path="/data/sample.tif",
        inputFile="/data/sample.tif",
        OutMrc="sample.mrc",
        outputFile="sample.mrc",
        Gain="/data/gain.mrc",
        PatchesX=5,
        PatchesY=5,
        Iter=5,
        Tol=0.5,
        Bft=100,
        LogDir=".",
        Gpu="0",
        FtBin=2,
        FmDose=0.75,
        PixSize=1.0,
        kV=300,
        Cs=0,
        AmpCont=0.07,
        ExtPhase=0,
        SumRangeMinDose=0,
        SumRangeMaxDose=0,
        Group=3,
        RotGain=0,
        FlipGain=0,
    )
    task = TaskMessage(
        id=FIXED_TASK_ID,
        job_id=FIXED_JOB_ID,
        session_id=FIXED_SESSION_ID,
        session_name="sample_session",
        worker_instance_id=FIXED_WORKER_ID,
        data=data.model_dump(),
        status=PENDING,
        type=MOTIONCOR_TASK,
        created_date=FIXED_DATETIME,
        start_on=None,
        end_on=None,
        result=None,
    )
    return task.model_dump(mode="json")


def _assert_matches_golden(name: str, envelope: dict) -> None:
    path = GOLDEN_DIR / f"{name}.json"
    if UPDATE or not path.exists():
        GOLDEN_DIR.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(envelope, indent=2, sort_keys=True) + "\n")
        pytest.skip(f"golden written to {path} — rerun without UPDATE_GOLDENS to verify")
    expected = json.loads(path.read_text())
    assert envelope == expected, (
        f"\nEnvelope {name} drifted from golden at {path}.\n"
        f"Run UPDATE_GOLDENS=1 pytest to accept the new shape AFTER confirming "
        f"all downstream consumers can handle it."
    )


@pytest.mark.characterization
def test_ctf_task_envelope_matches_golden():
    _assert_matches_golden("ctf_task_envelope", _make_ctf_envelope())


@pytest.mark.characterization
def test_motioncor_task_envelope_matches_golden():
    _assert_matches_golden("motioncor_task_envelope", _make_motioncor_envelope())


@pytest.mark.characterization
def test_ctf_envelope_top_level_keys():
    """Independent assertion: the envelope's top-level keys don't drift.

    Catches additions/removals even if the golden is regenerated carelessly.
    ``target_backend`` was added in SDK 1.3 (Track C / X.1) for backend
    pinning; pre-1.3 plugins decoding the wire ignore the field.
    """
    envelope = _make_ctf_envelope()
    assert set(envelope.keys()) == {
        "id", "job_id", "session_id", "session_name", "worker_instance_id",
        "data", "status", "type", "created_date", "start_on", "end_on", "result",
        "target_backend",
    }


@pytest.mark.characterization
def test_motioncor_envelope_top_level_keys():
    envelope = _make_motioncor_envelope()
    assert set(envelope.keys()) == {
        "id", "job_id", "session_id", "session_name", "worker_instance_id",
        "data", "status", "type", "created_date", "start_on", "end_on", "result",
        "target_backend",
    }


@pytest.mark.characterization
def test_task_category_codes_are_stable():
    """Task category codes are part of the queue routing contract."""
    assert CTF_TASK.code == 2
    assert CTF_TASK.name == "CTF"
    assert MOTIONCOR_TASK.code == 5
    assert MOTIONCOR_TASK.name == "MotionCor"


@pytest.mark.characterization
def test_pending_status_is_stable():
    """The PENDING status shape is part of every freshly-dispatched envelope."""
    assert PENDING.code == 0
    assert PENDING.name == "pending"
