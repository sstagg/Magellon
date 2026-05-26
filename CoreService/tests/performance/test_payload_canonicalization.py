"""Performance guardrails for dispatch-boundary payload rewriting."""
from __future__ import annotations

import time

import pytest


@pytest.mark.performance
def test_canonicalize_large_plugin_payload_under_budget(monkeypatch):
    from config import app_settings
    from core.helper import canonicalize_paths_in_payload

    monkeypatch.setattr(
        app_settings.directory_settings,
        "MAGELLON_GPFS_PATH",
        "C:/magellon/gpfs",
    )
    payload = {
        "image_path": "C:/magellon/gpfs/session/mic.mrc",
        "template_paths": [
            f"C:/magellon/gpfs/templates/t{i:04d}.mrc"
            for i in range(2_000)
        ],
        "engine_opts": {
            "masks": [
                f"C:/magellon/gpfs/masks/m{i:04d}.mrc"
                for i in range(500)
            ],
            "threshold": 0.42,
        },
    }

    start = time.perf_counter()
    out = canonicalize_paths_in_payload(payload)
    elapsed = time.perf_counter() - start

    assert out["image_path"] == "/gpfs/session/mic.mrc"
    assert out["template_paths"][0] == "/gpfs/templates/t0000.mrc"
    assert out["template_paths"][-1] == "/gpfs/templates/t1999.mrc"
    assert out["engine_opts"]["masks"][-1] == "/gpfs/masks/m0499.mrc"
    assert elapsed < 1.0
