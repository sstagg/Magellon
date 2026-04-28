"""Tests for the X.1 backend layer.

What we pin here:

- ``Announce`` carries ``backend_id`` and round-trips cleanly.
- ``PluginLivenessRegistry`` records and exposes ``backend_id``.
- A pre-1.3 announce (no ``backend_id`` field) gets a sensible fallback
  derived from the manifest, not ``None``, so the dispatcher's pinning
  path keeps working for legacy plugins.
- A duplicate-backend collision (two plugin_ids in one category claiming
  the same backend_id) emits a ``DUP_BACKEND_ID`` log warning so the
  operator notices.
- ``CategoryContract.task_subject_for_backend`` produces the expected
  subject form for symbolic logging.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone

from magellon_sdk.bus.services.liveness_registry import (
    PluginLivenessRegistry,
)
from magellon_sdk.categories.contract import (
    CTF,
    task_subject,
    task_subject_for_backend,
)
from magellon_sdk.discovery import Announce, Heartbeat
from magellon_sdk.models.manifest import (
    Capability,
    PluginManifest,
    Transport,
)
from magellon_sdk.models.plugin import PluginInfo


def _manifest(*, name: str = "ctf-ctffind4", backend_id=None) -> PluginManifest:
    return PluginManifest(
        info=PluginInfo(name=name, version="0.4.1"),
        backend_id=backend_id,
        capabilities=[Capability.CPU_INTENSIVE],
        supported_transports=[Transport.RMQ],
        default_transport=Transport.RMQ,
    )


# ---------------------------------------------------------------------------
# Wire shapes
# ---------------------------------------------------------------------------

def test_announce_carries_backend_id_through_json():
    """The X.1 contract: Announce.backend_id rides on the wire so a
    listener can index by ``(category, backend_id)`` without unpacking
    the manifest."""
    msg = Announce(
        plugin_id="ctf-ctffind4",
        plugin_version="0.4.1",
        category="ctf",
        manifest=_manifest(backend_id="ctffind4"),
        backend_id="ctffind4",
    )
    restored = Announce.model_validate_json(msg.model_dump_json())
    assert restored.backend_id == "ctffind4"


def test_announce_backend_id_optional_for_pre_1_3_plugins():
    """A plugin built against SDK ≤1.2 won't set the new field. The
    decoder must accept that and leave the field None — the registry
    is responsible for the fallback."""
    msg = Announce(
        plugin_id="legacy-ctf",
        plugin_version="0.1.0",
        category="ctf",
        manifest=_manifest(name="legacy-ctf"),
    )
    assert msg.backend_id is None


# ---------------------------------------------------------------------------
# CategoryContract subject helpers
# ---------------------------------------------------------------------------

def test_task_subject_for_backend_appends_lowercased_backend_id():
    """Subject naming has to be deterministic from (category, backend_id);
    the bus, the audit log, and the operator dashboard all derive the
    same string from the same inputs."""
    assert task_subject("CTF") == "magellon.tasks.ctf"
    assert task_subject_for_backend("CTF", "ctffind4") == "magellon.tasks.ctf.ctffind4"
    # Backend ids are slug-shaped already, but normalize defensively.
    assert task_subject_for_backend("CTF", "GCTF") == "magellon.tasks.ctf.gctf"


def test_category_contract_exposes_backend_subject_helper():
    """Plugins / dispatchers consume this through the contract instance,
    not the module function — pin both forms."""
    assert CTF.task_subject == "magellon.tasks.ctf"
    assert CTF.task_subject_for_backend("ctffind4") == "magellon.tasks.ctf.ctffind4"


# ---------------------------------------------------------------------------
# PluginLivenessRegistry indexes by backend_id
# ---------------------------------------------------------------------------

def test_registry_records_backend_id_from_announce():
    """When an SDK 1.3+ plugin announces with backend_id set, the
    registry stores it verbatim — no manifest unpacking needed."""
    reg = PluginLivenessRegistry(stale_after_seconds=60)
    msg = Announce(
        plugin_id="ctf-ctffind4",
        plugin_version="0.4.1",
        category="ctf",
        manifest=_manifest(backend_id="ctffind4"),
        backend_id="ctffind4",
    )
    reg.record_announce(msg)

    [entry] = reg.list_live(now=datetime.now(timezone.utc))
    assert entry.backend_id == "ctffind4"


def test_registry_falls_back_to_manifest_resolved_backend_id():
    """A pre-1.3 announce skips ``backend_id`` on the wire but the
    manifest's resolved value is still recoverable. The registry uses
    that so the dispatcher's pinning path remains functional."""
    reg = PluginLivenessRegistry(stale_after_seconds=60)
    msg = Announce(
        plugin_id="legacy-ctf",
        plugin_version="0.1.0",
        category="ctf",
        manifest=_manifest(name="ctffind4"),
        # backend_id not set — pre-1.3 wire shape
    )
    reg.record_announce(msg)

    [entry] = reg.list_live()
    assert entry.backend_id == "ctffind4"  # derived from manifest.info.name


def test_registry_warns_on_duplicate_backend_id_in_category(caplog):
    """Two distinct plugin_ids claiming the same backend_id in one
    category is the misconfig the doc warns about — log loudly so
    the operator notices."""
    reg = PluginLivenessRegistry(stale_after_seconds=60)
    a = Announce(
        plugin_id="vendor-a-ctf",
        plugin_version="1.0",
        category="ctf",
        manifest=_manifest(name="ctffind4"),
        backend_id="ctffind4",
    )
    b = Announce(
        plugin_id="vendor-b-ctf",
        plugin_version="2.0",
        category="ctf",
        manifest=_manifest(name="ctffind4"),
        backend_id="ctffind4",
    )

    reg.record_announce(a)
    with caplog.at_level(
        logging.WARNING,
        logger="magellon_sdk.bus.services.liveness_registry",
    ):
        reg.record_announce(b)

    assert any("DUP_BACKEND_ID" in rec.message for rec in caplog.records)


def test_registry_does_not_warn_on_replicas_of_one_backend():
    """Two announces with the same plugin_id but different instance_ids
    are scale-out replicas, not a collision. Don't log on those."""
    reg = PluginLivenessRegistry(stale_after_seconds=60)
    a = Announce(
        plugin_id="ctf-ctffind4",
        plugin_version="1.0",
        category="ctf",
        manifest=_manifest(name="ctffind4"),
        backend_id="ctffind4",
    )
    b = Announce(
        plugin_id="ctf-ctffind4",
        plugin_version="1.0",
        category="ctf",
        manifest=_manifest(name="ctffind4"),
        backend_id="ctffind4",
    )
    assert a.instance_id != b.instance_id

    reg.record_announce(a)
    # If this raised or warned, the registry would be unfit for HPA.
    reg.record_announce(b)

    live = reg.list_live()
    assert len(live) == 2
    assert {e.backend_id for e in live} == {"ctffind4"}


def test_registry_to_dict_includes_backend_id():
    """Anyone reading the registry as JSON (debug endpoints,
    capabilities endpoint) needs the backend_id field present."""
    reg = PluginLivenessRegistry(stale_after_seconds=60)
    reg.record_announce(Announce(
        plugin_id="ctf-ctffind4",
        plugin_version="0.4.1",
        category="ctf",
        manifest=_manifest(backend_id="ctffind4"),
        backend_id="ctffind4",
    ))
    [snap] = reg.snapshot()
    assert snap["backend_id"] == "ctffind4"


def test_heartbeat_only_entry_gets_backend_id_fallback():
    """Heartbeat-before-announce arrives in CoreService restart cases.
    The stub entry must still have a backend_id so a backend-pinned
    dispatch can find it (pre-announce is the brief window — accept
    the cost of a slug-from-plugin-id fallback for that interval)."""
    reg = PluginLivenessRegistry(stale_after_seconds=60)
    reg.record_heartbeat(Heartbeat(
        plugin_id="ctf-ctffind4",
        plugin_version="0.4.1",
        category="ctf",
    ))
    [entry] = reg.list_live()
    assert entry.backend_id == "ctf-ctffind4"
