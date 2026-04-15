"""Tests for plugin provenance fields on TaskResultDto (P4).

These pin the wire-level guarantees:

  - plugin_id / plugin_version are optional (older plugins still validate).
  - When set, they round-trip through JSON unchanged.
  - Default JSON omits nothing important — the field shows up serialized.
"""
from __future__ import annotations

from uuid import uuid4

from magellon_sdk.models import TaskResultDto


def test_provenance_fields_default_to_none():
    """The fields are additive — a plugin that hasn't been migrated yet
    must still produce a valid TaskResultDto."""
    r = TaskResultDto(task_id=uuid4(), code=200, message="ok")
    assert r.plugin_id is None
    assert r.plugin_version is None


def test_provenance_round_trips_through_json():
    """An emitted result must arrive at the writer with the same
    plugin identity — that's the whole point of provenance."""
    r = TaskResultDto(
        task_id=uuid4(),
        code=200,
        message="ok",
        plugin_id="ctf-ctffind",
        plugin_version="4.1.14",
    )
    restored = TaskResultDto.model_validate_json(r.model_dump_json())
    assert restored.plugin_id == "ctf-ctffind"
    assert restored.plugin_version == "4.1.14"


def test_provenance_present_in_serialized_payload():
    """If the field is set, the JSON wire form must carry it — no
    silent strip via exclude_none or similar."""
    r = TaskResultDto(
        task_id=uuid4(), code=200, plugin_id="motioncor", plugin_version="1.6.4"
    )
    payload = r.model_dump_json()
    assert '"plugin_id":"motioncor"' in payload
    assert '"plugin_version":"1.6.4"' in payload
