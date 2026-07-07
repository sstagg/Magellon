"""SDK/CoreService boundary contracts.

These tests pin the places where CoreService validates or rewrites SDK
payloads before handing them to external plugins. The goal is to catch
contract drift before it becomes a plugin-only failure.
"""
from __future__ import annotations

from uuid import uuid4


def test_sdk_category_validation_preserves_plugin_specific_fields(monkeypatch):
    from config import app_settings
    from core.helper import canonicalize_paths_in_payload
    from magellon_sdk.categories import CTF

    monkeypatch.setattr(
        app_settings.directory_settings,
        "MAGELLON_GPFS_PATH",
        "C:/magellon/gpfs",
    )

    payload = {
        "image_path": "C:/magellon/gpfs/session/mic.mrc",
        "inputFile": "C:/magellon/gpfs/session/mic.mrc",
        "gpu_id": 3,
        "engine_opts": {
            "diagnostic_mask": "C:/magellon/gpfs/masks/mic-mask.mrc",
        },
    }

    canonical = canonicalize_paths_in_payload(payload)
    validated = CTF.validate_input(canonical)

    assert validated.inputFile == "/gpfs/session/mic.mrc"
    assert validated.model_extra == {"gpu_id": 3}
    assert validated.engine_opts["diagnostic_mask"] == "/gpfs/masks/mic-mask.mrc"


def test_particle_pick_dispatch_canonicalizes_template_picker_extras(monkeypatch):
    from config import app_settings
    from core import helper as helper_mod
    from magellon_sdk.models.tasks import PARTICLE_PICKING

    monkeypatch.setattr(
        app_settings.directory_settings,
        "MAGELLON_GPFS_PATH",
        "C:/magellon/gpfs",
    )

    captured = {}

    def _capture(task):
        captured["task"] = task
        return True

    # Patch the builder module — dispatch_particle_pick_task resolves
    # push_task_to_task_queue from core.dispatch_builders' namespace
    # since the core.helper split.
    import core.dispatch_builders as builders_mod
    monkeypatch.setattr(builders_mod, "push_task_to_task_queue", _capture)

    ok = helper_mod.dispatch_particle_pick_task(
        "C:/magellon/gpfs/session/mic.mrc",
        image_id=uuid4(),
        target_backend="template-picker",
        engine_opts={
            "template_paths": [
                "C:/magellon/gpfs/templates/t1.mrc",
                "C:/magellon/gpfs/templates/t2.mrc",
            ],
            "threshold": 0.42,
        },
    )

    assert ok is True
    task = captured["task"]
    assert task.type == PARTICLE_PICKING
    assert task.target_backend == "template-picker"
    assert task.data["image_path"] == "/gpfs/session/mic.mrc"
    assert task.data["input_file"] == "/gpfs/session/mic.mrc"
    assert task.data["template_paths"] == [
        "/gpfs/templates/t1.mrc",
        "/gpfs/templates/t2.mrc",
    ]
    assert task.data["threshold"] == 0.42
