"""Envelope contract tests.

The envelope is the public wire format between every Magellon component
(JobManager, NATS subscribers, Temporal activities, Plugin Hub, UI
gateway). The shape cannot drift silently — these tests pin it.
"""
from __future__ import annotations

from datetime import datetime, timezone

import pytest
from pydantic import BaseModel

from magellon_sdk.envelope import Envelope


class CtfCompletedV1(BaseModel):
    job_id: str
    defocus_a: float


def test_envelope_required_fields():
    env = Envelope[CtfCompletedV1](
        source="magellon/plugins/ctf",
        type="magellon.step.completed",
        data=CtfCompletedV1(job_id="j1", defocus_a=12345.0),
    )

    # CloudEvents 1.0 required fields:
    assert env.specversion == "1.0"
    assert env.source == "magellon/plugins/ctf"
    assert env.type == "magellon.step.completed"
    assert env.id  # auto-generated UUID
    assert isinstance(env.time, datetime)
    assert env.time.tzinfo is not None  # must be timezone-aware
    assert env.datacontenttype == "application/json"


def test_envelope_subject_routes_on_job_step():
    """Magellon routes on `magellon.job.<id>.step.<step>` — subject preserves that."""
    env = Envelope[CtfCompletedV1](
        source="magellon/plugins/ctf",
        type="magellon.step.completed",
        subject="magellon.job.abc123.step.ctf",
        data=CtfCompletedV1(job_id="abc123", defocus_a=1.0),
    )
    assert env.subject == "magellon.job.abc123.step.ctf"


def test_envelope_wrap_helper():
    env = Envelope.wrap(
        source="magellon/plugins/ctf",
        type="magellon.step.progress",
        subject="magellon.job.j1.step.ctf",
        data=CtfCompletedV1(job_id="j1", defocus_a=0.0),
    )
    assert env.source == "magellon/plugins/ctf"
    assert env.subject == "magellon.job.j1.step.ctf"


def test_envelope_round_trip():
    original = Envelope[CtfCompletedV1](
        source="magellon/plugins/ctf",
        type="magellon.step.completed",
        subject="magellon.job.abc/step.ctf",
        data=CtfCompletedV1(job_id="abc", defocus_a=999.9),
    )

    wire = original.model_dump_json()
    restored = Envelope[CtfCompletedV1].model_validate_json(wire)

    assert restored.id == original.id
    assert restored.source == original.source
    assert restored.type == original.type
    assert restored.subject == original.subject
    assert restored.time == original.time
    assert restored.data == original.data


def test_envelope_unknown_keys_preserved():
    """CloudEvents allows extension attributes; dropping them on the
    floor would lose information set by upstream producers."""
    payload = {
        "specversion": "1.0",
        "id": "00000000-0000-0000-0000-000000000001",
        "source": "magellon/core",
        "type": "magellon.step.progress",
        "time": "2026-04-14T00:00:00+00:00",
        "datacontenttype": "application/json",
        "partitionkey": "tenant-7",  # CloudEvents extension
        "data": {"job_id": "j1", "defocus_a": 1.0},
    }
    env = Envelope[CtfCompletedV1].model_validate(payload)
    assert env.model_dump().get("partitionkey") == "tenant-7"


def test_envelope_missing_required_raises():
    with pytest.raises(Exception):
        Envelope[CtfCompletedV1].model_validate(
            {"specversion": "1.0", "data": {"job_id": "j1", "defocus_a": 1.0}}
        )
