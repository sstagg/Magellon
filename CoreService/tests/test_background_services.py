from __future__ import annotations

from types import SimpleNamespace

from core.background_services import BackgroundServiceRegistry, ensure_background_registry


def test_background_registry_records_started_failed_and_disabled():
    registry = BackgroundServiceRegistry()

    registry.started("worker", object())
    registry.failed("forwarder", RuntimeError("boom"))
    registry.disabled("optional")
    registry.stopped("stoppable")

    snapshot = registry.snapshot()
    assert snapshot["worker"]["status"] == "ok"
    assert snapshot["worker"]["enabled"] is True
    assert snapshot["forwarder"]["status"] == "error"
    assert snapshot["forwarder"]["error"] == "boom"
    assert snapshot["optional"]["status"] == "disabled"
    assert snapshot["optional"]["enabled"] is False
    assert snapshot["stoppable"]["status"] == "stopped"
    assert snapshot["stoppable"]["enabled"] is True


def test_ensure_background_registry_reuses_existing_registry():
    app = SimpleNamespace(state=SimpleNamespace())

    first = ensure_background_registry(app)
    second = ensure_background_registry(app)

    assert first is second
