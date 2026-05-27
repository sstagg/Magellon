from __future__ import annotations

import json
from types import SimpleNamespace
from uuid import uuid4

from controllers import particle_export_pipeline_controller as pc


def test_normalise_picks_filters_to_requested_classes():
    raw = [
        {"x": 10, "y": 20, "score": 0.8, "class": "1", "radius": 12},
        {"center": [30, 40], "confidence": 0.4, "class": "4"},
        {"center": ["bad", 40], "class": "1"},
        {"x": 50, "y": 60, "class": "2"},
    ]

    picks = pc._normalise_picks(raw, {"1", "2"})

    assert picks == [
        {
            "center": [10.0, 20.0],
            "x": 10.0,
            "y": 20.0,
            "score": 0.8,
            "class": "1",
            "radius": 12.0,
        },
        {
            "center": [50.0, 60.0],
            "x": 50.0,
            "y": 60.0,
            "score": 1.0,
            "class": "2",
        },
    ]


def test_class_counts_defaults_unlabelled_picks_to_good():
    assert pc._class_counts([
        {"x": 1, "y": 2},
        {"center": [3, 4], "class": "4"},
        {"center": [5, 6], "class_number": 2},
    ]) == {"1": 1, "4": 1, "2": 1}


def test_write_manifest_emits_stack_maker_batch_json(monkeypatch, tmp_path):
    session = SimpleNamespace(oid=uuid4())
    image_id = uuid4()
    image = SimpleNamespace(oid=image_id, name="mic_0001", path=None)
    metadata = SimpleNamespace(
        data_json=[
            {"center": [12, 14], "score": 0.9, "class": "1"},
            {"center": [20, 22], "score": 0.2, "class": "4"},
        ]
    )

    monkeypatch.setattr(pc, "_picking_rows", lambda *_args, **_kwargs: [(metadata, image)])
    monkeypatch.setattr(pc, "_resolve_mrc_path", lambda *_args, **_kwargs: "C:/data/mic_0001.mrc")

    info = pc._write_manifest(
        object(),
        session=session,
        session_name="24dec03a",
        picking_run_name="Topaz run",
        output_root=str(tmp_path),
        include_classes={"1"},
    )

    manifest = json.loads((tmp_path / "stack_maker_batch_manifest.json").read_text())
    picks_path = tmp_path / "picks" / "mic_0001.json"
    picks = json.loads(picks_path.read_text())

    assert info["particle_count"] == 1
    assert info["image_count"] == 1
    assert info["image_ids"] == [str(image_id)]
    assert manifest["items"] == [
        {
            "micrograph_path": "C:/data/mic_0001.mrc",
            "particles_path": str(picks_path),
            "micrograph_name": "mic_0001",
        }
    ]
    assert picks[0]["center"] == [12.0, 14.0]
