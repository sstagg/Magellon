"""Targeted tests for PluginCatalogPersistence.rehydrate_announces.

This is what makes the side panel's ``canPreview`` / ``has_sync`` flags
survive a CoreService restart. Without it, plugins' one-shot Announce
is lost on boot and only heartbeats refresh the registry — which only
write manifest-less stubs.
"""
from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace

from magellon_sdk.discovery import Announce
from magellon_sdk.models.manifest import Capability, PluginInfo, PluginManifest

from services.plugin_catalog_persistence import PluginCatalogPersistence


def _make_row(*, plugin_id: str, with_manifest: bool, http_endpoint: str | None = None):
    """Build a Plugin-shaped SimpleNamespace for unit testing."""
    if with_manifest:
        manifest = PluginManifest(
            info=PluginInfo(
                name=plugin_id,
                version="1.0.0",
                developer="test",
                description="",
                schema_version="1",
            ),
            backend_id=plugin_id,
            capabilities=[Capability.SYNC, Capability.PREVIEW],
        )
        manifest_payload = manifest.model_dump(mode="json")
        manifest_payload["name"] = plugin_id
        manifest_payload["version"] = "1.0.0"
        manifest_payload["category"] = "particle_picking"
        manifest_payload["backend_id"] = plugin_id
        manifest_payload["discovered"] = {"source": "announce", "instance_id": "inst-1"}
        manifest_payload["input_schema"] = {"type": "object", "properties": {"k": {"type": "string"}}}
    else:
        # Heartbeat-only stub — no ``info`` / ``capabilities``.
        manifest_payload = {
            "name": plugin_id,
            "version": "1.0.0",
            "category": "particle_picking",
            "backend_id": plugin_id,
            "discovered": {"source": "heartbeat", "instance_id": "inst-1"},
        }

    state = SimpleNamespace(last_heartbeat_at=datetime(2026, 5, 27, 10, 0, 0, tzinfo=timezone.utc))
    return SimpleNamespace(
        manifest_plugin_id=plugin_id,
        name=plugin_id,
        version="1.0.0",
        category="particle_picking",
        backend_id=plugin_id,
        http_endpoint=http_endpoint,
        container_ref=None,
        manifest_json=manifest_payload,
        state=state,
    )


def test_row_to_announce_seeds_capabilities_from_manifest():
    row = _make_row(plugin_id="topaz-particle-picking", with_manifest=True,
                    http_endpoint="http://127.0.0.1:9000")
    announce = PluginCatalogPersistence._row_to_announce(row)
    assert announce is not None
    assert announce.plugin_id == "topaz-particle-picking"
    assert announce.backend_id == "topaz-particle-picking"
    assert announce.http_endpoint.startswith("http://127.0.0.1:9000")
    assert Capability.PREVIEW in announce.manifest.capabilities
    assert announce.input_schema == {"type": "object", "properties": {"k": {"type": "string"}}}


def test_row_to_announce_skips_heartbeat_stub():
    """Stubs created by record_heartbeat have no real manifest. The
    rehydrator must skip them, not crash, and not seed a stub that
    masquerades as a real announce."""
    row = _make_row(plugin_id="orphan", with_manifest=False)
    assert PluginCatalogPersistence._row_to_announce(row) is None


def test_rehydrate_seeds_registry_through_record_announce(monkeypatch):
    """End-to-end: a row with a real manifest lands in the registry
    via record_announce, and the recorded announce carries the
    capabilities the side panel reads."""
    rows = [
        _make_row(plugin_id="topaz-particle-picking", with_manifest=True,
                  http_endpoint="http://127.0.0.1:9000"),
        _make_row(plugin_id="orphan", with_manifest=False),
    ]

    # Stub out the DB layer.
    def _fake_session_factory():
        class _S:
            def close(self):
                pass
        return _S()

    persistence = PluginCatalogPersistence(session_factory=_fake_session_factory)
    monkeypatch.setattr(
        "services.plugin_catalog_persistence.PluginRepository",
        lambda db: SimpleNamespace(list_installed=lambda: rows),
    )

    received: list[Announce] = []
    fake_registry = SimpleNamespace(record_announce=received.append)

    n = persistence.rehydrate_announces(fake_registry)

    assert n == 1, "only the row with a real manifest should be replayed"
    assert len(received) == 1
    assert received[0].plugin_id == "topaz-particle-picking"
    assert Capability.PREVIEW in received[0].manifest.capabilities


def test_runtime_announce_refreshes_existing_manifest_and_endpoint(monkeypatch):
    """A discovered row may have stale capabilities after an upgrade.
    A later announce must refresh the full runtime manifest, not just
    schemas, so PREVIEW survives the next CoreService restart."""
    existing = _make_row(
        plugin_id="topaz-particle-picking",
        with_manifest=True,
        http_endpoint=None,
    )
    existing.oid = "plugin-oid"
    existing.manifest_json["capabilities"] = ["cpu_intensive"]

    class _DB:
        def add(self, row):
            self.row = row

        def commit(self):
            pass

        def rollback(self):
            pass

        def close(self):
            pass

    persistence = PluginCatalogPersistence(session_factory=_DB)
    refreshed_manifest = PluginManifest(
        info=PluginInfo(
            name="Topaz Particle Picking",
            version="1.0.0",
            developer="test",
            schema_version="1",
        ),
        backend_id="topaz-particle-picking",
        capabilities=[Capability.CPU_INTENSIVE, Capability.PREVIEW],
    ).model_dump(mode="json")
    refreshed_manifest.update({
        "name": "Topaz Particle Picking",
        "version": "1.0.0",
        "author": "test",
        "category": "topazparticlepicking",
        "backend_id": "topaz-particle-picking",
        "schema_version": "1",
        "discovered": {"source": "announce", "instance_id": "inst-2"},
        "input_schema": {"type": "object"},
    })

    monkeypatch.setattr(
        "services.plugin_catalog_persistence.PluginRepository",
        lambda db: SimpleNamespace(
            get_by_manifest_plugin_id=lambda plugin_id: existing,
            get_by_category_backend=lambda category, backend_id: None,
            upsert_catalog=lambda *a, **k: None,
        ),
    )
    monkeypatch.setattr(
        "services.plugin_catalog_persistence.PluginStateRepository",
        lambda db: SimpleNamespace(
            touch_heartbeat=lambda oid, seen_at: None,
            set_enabled=lambda oid, enabled: None,
        ),
    )

    persistence._upsert_discovered(
        plugin_id="topaz-particle-picking",
        manifest=refreshed_manifest,
        install_result={
            "install_method": "discovered",
            "container_ref": "topaz_pick_tasks_queue",
            "http_endpoint": "http://127.0.0.1:18003/",
        },
        seen_at=datetime(2026, 5, 27, 10, 0, 0),
    )

    assert "preview" in existing.manifest_json["capabilities"]
    assert existing.manifest_json["input_schema"] == {"type": "object"}
    assert existing.http_endpoint == "http://127.0.0.1:18003/"
    assert existing.container_ref == "topaz_pick_tasks_queue"
