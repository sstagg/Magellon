"""Tests for _stamp_image_subject — A.2, importer subject axis at dispatch.

Phase 3 made dispatch the authoritative writer of the subject axis.
``_stamp_image_subject`` runs inside ``push_task_to_task_queue`` (the
single chokepoint every importer + detection/picking dispatch flows
through) and derives ``subject_kind='image'`` / ``subject_id=<image_id>``
from the task payload when the caller hasn't set a richer subject.

Pre-A.2 importer-dispatched tasks left the subject axis None and relied
entirely on the runner's contract-default fallback + the projector's
Phase-3c backfill.
"""
from __future__ import annotations

import uuid

from magellon_sdk.models import CTF_TASK, TaskMessage

from core.helper import _stamp_image_subject


def _task(data: dict, **kw) -> TaskMessage:
    return TaskMessage(id=uuid.uuid4(), job_id=uuid.uuid4(), data=data,
                       type=CTF_TASK, **kw)


def test_stamps_image_subject_from_payload_image_id():
    image_id = uuid.uuid4()
    task = _task({"image_id": str(image_id), "image_path": "/gpfs/x.mrc"})

    _stamp_image_subject(task)

    assert task.subject_kind == "image"
    assert task.subject_id == image_id


def test_accepts_image_id_already_a_uuid():
    image_id = uuid.uuid4()
    task = _task({"image_id": image_id})

    _stamp_image_subject(task)

    assert task.subject_kind == "image"
    assert task.subject_id == image_id


def test_noop_when_caller_already_set_subject_kind():
    """A 2D-classification dispatch sets subject_kind='particle_stack'
    explicitly — the image-subject stamp must not clobber it."""
    stack_id = uuid.uuid4()
    task = _task({"image_id": str(uuid.uuid4())},
                 subject_kind="particle_stack", subject_id=stack_id)

    _stamp_image_subject(task)

    assert task.subject_kind == "particle_stack"
    assert task.subject_id == stack_id


def test_noop_when_payload_has_no_image_id():
    task = _task({"image_path": "/gpfs/x.mrc"})

    _stamp_image_subject(task)

    assert task.subject_kind is None
    assert task.subject_id is None


def test_noop_when_image_id_is_empty_string():
    """dispatch_particle_pick_task writes ``None`` as ``str(None)`` is
    avoided, but an empty image_id can still reach here — treat it as
    absent rather than crashing on UUID('')."""
    task = _task({"image_id": ""})

    _stamp_image_subject(task)

    assert task.subject_kind is None


def test_unparseable_image_id_keeps_kind_drops_id():
    """A non-UUID image_id still routes correctly on kind alone;
    subject_id stays None rather than raising."""
    task = _task({"image_id": "not-a-uuid"})

    _stamp_image_subject(task)

    assert task.subject_kind == "image"
    assert task.subject_id is None
