"""Tests for the sync_dispatcher (PT-3).

Stubs the liveness registry + state store + httpx so the dispatcher
runs end-to-end without a real plugin. Pins resolution priority,
capability gating, error mapping.
"""
from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import httpx
import pytest

from magellon_sdk.models.manifest import Capability
from services.sync_dispatcher import (
    BackendNotLive,
    CapabilityMissing,
    PluginCallFailed,
    dispatch_capability,
)


# ---------------------------------------------------------------------------
# Fakes
# ---------------------------------------------------------------------------


def _liveness_entry(
    plugin_id: str = "template-picker",
    *,
    category: str = "particle_picking",
    backend_id: str = "template-picker",
    capabilities: tuple = (Capability.SYNC, Capability.PREVIEW),
    http_endpoint: str = "http://plugin.test:8000",
):
    """Stand-in for PluginLivenessEntry. SimpleNamespace keeps tests
    immune to ctor changes on the real class."""
    manifest = SimpleNamespace(capabilities=list(capabilities)) if capabilities else None
    return SimpleNamespace(
        plugin_id=plugin_id,
        category=category,
        backend_id=backend_id,
        manifest=manifest,
        http_endpoint=http_endpoint,
        last_heartbeat=None,
        instance_id="i-1",
        plugin_version="1.0.0",
        status="ready",
        task_queue=None,
    )


def _stub_registries(entries, *, default_per_category=None):
    """Patch the liveness registry + state store getters to return
    the canned entries / defaults."""
    fake_liveness = MagicMock()
    fake_liveness.list_live.return_value = list(entries)

    fake_state = MagicMock()
    defaults = default_per_category or {}
    fake_state.get_default.side_effect = lambda cat: defaults.get((cat or "").lower())

    return patch.multiple(
        "services.sync_dispatcher",
        get_liveness_registry=lambda: fake_liveness,
        get_state_store=lambda: fake_state,
    )


class _MockTransport(httpx.MockTransport):
    """httpx mock transport that records every request and returns
    a canned response. Tests reach into ``calls`` to assert the
    dispatcher made the right HTTP call."""

    def __init__(self, response_status=200, response_body=None):
        self.calls: list[httpx.Request] = []
        self._response_status = response_status
        self._response_body = response_body if response_body is not None else {"ok": True}

        def handler(request: httpx.Request) -> httpx.Response:
            self.calls.append(request)
            return httpx.Response(
                self._response_status,
                json=self._response_body,
            )

        super().__init__(handler)


# ---------------------------------------------------------------------------
# Resolution
# ---------------------------------------------------------------------------


def test_dispatch_routes_to_first_capable_plugin():
    transport = _MockTransport(200, {"preview_id": "p-42"})
    client = httpx.Client(transport=transport)

    entry = _liveness_entry()
    with _stub_registries([entry]):
        body = dispatch_capability(
            "particle_picking", Capability.PREVIEW, "POST", "/preview",
            body={"image_path": "img.mrc"}, client=client,
        )

    assert body == {"preview_id": "p-42"}
    assert len(transport.calls) == 1
    req = transport.calls[0]
    assert req.method == "POST"
    assert str(req.url) == "http://plugin.test:8000/preview"


def test_dispatch_honours_target_backend_pin():
    """When the caller pins ``target_backend``, that beats the
    operator default."""
    transport = _MockTransport()
    client = httpx.Client(transport=transport)
    a = _liveness_entry("a", backend_id="default-backend",
                        http_endpoint="http://default:8000")
    b = _liveness_entry("b", backend_id="alt-backend",
                        http_endpoint="http://alt:8000")
    with _stub_registries(
        [a, b], default_per_category={"particle_picking": "a"},
    ):
        dispatch_capability(
            "particle_picking", Capability.PREVIEW, "POST", "/preview",
            target_backend="alt-backend", client=client,
        )

    assert "alt:8000" in str(transport.calls[0].url)


def test_dispatch_routes_to_operator_default_when_no_pin():
    transport = _MockTransport()
    client = httpx.Client(transport=transport)
    default_plugin = _liveness_entry("default", backend_id="d",
                                     http_endpoint="http://default:8000")
    other = _liveness_entry("other", backend_id="o",
                            http_endpoint="http://other:8000")
    with _stub_registries(
        [other, default_plugin],  # default-second to confirm priority
        default_per_category={"particle_picking": "default"},
    ):
        dispatch_capability(
            "particle_picking", Capability.PREVIEW, "POST", "/preview",
            client=client,
        )

    assert "default:8000" in str(transport.calls[0].url)


def test_dispatch_raises_when_no_live_plugin():
    transport = _MockTransport()
    client = httpx.Client(transport=transport)
    with _stub_registries([]):
        with pytest.raises(BackendNotLive):
            dispatch_capability(
                "particle_picking", Capability.PREVIEW, "POST", "/preview",
                client=client,
            )


def test_dispatch_raises_when_target_backend_not_live():
    transport = _MockTransport()
    client = httpx.Client(transport=transport)
    entry = _liveness_entry(backend_id="template-picker")
    with _stub_registries([entry]):
        with pytest.raises(BackendNotLive):
            dispatch_capability(
                "particle_picking", Capability.PREVIEW, "POST", "/preview",
                target_backend="nonexistent", client=client,
            )


def test_dispatch_raises_capability_missing_when_plugin_does_not_advertise():
    """Pinned because dispatching to a plugin without the capability
    would silently call an endpoint that may not exist."""
    transport = _MockTransport()
    client = httpx.Client(transport=transport)
    entry = _liveness_entry(capabilities=(Capability.IDEMPOTENT,))  # no PREVIEW
    with _stub_registries([entry]):
        with pytest.raises(CapabilityMissing, match="preview"):
            dispatch_capability(
                "particle_picking", Capability.PREVIEW, "POST", "/preview",
                client=client,
            )


def test_dispatch_raises_when_plugin_lacks_http_endpoint():
    """A plugin can advertise PREVIEW without setting http_endpoint
    (announce missed it). Surface as BackendNotLive — the operator
    needs to know to restart the plugin."""
    transport = _MockTransport()
    client = httpx.Client(transport=transport)
    entry = _liveness_entry(http_endpoint=None)
    with _stub_registries([entry]):
        with pytest.raises(BackendNotLive, match="http_endpoint"):
            dispatch_capability(
                "particle_picking", Capability.PREVIEW, "POST", "/preview",
                client=client,
            )


# ---------------------------------------------------------------------------
# HTTP error mapping
# ---------------------------------------------------------------------------


def test_dispatch_maps_4xx_to_plugin_call_failed():
    transport = _MockTransport(404, {"detail": "preview expired"})
    client = httpx.Client(transport=transport)
    entry = _liveness_entry()
    with _stub_registries([entry]):
        with pytest.raises(PluginCallFailed) as ei:
            dispatch_capability(
                "particle_picking", Capability.PREVIEW,
                "POST", "/preview/p-1/retune",
                body={"threshold": 0.5},
                client=client,
            )
    assert ei.value.status_code == 404
    assert ei.value.detail == {"detail": "preview expired"}


def test_dispatch_maps_5xx_to_plugin_call_failed():
    transport = _MockTransport(500, {"detail": "boom"})
    client = httpx.Client(transport=transport)
    entry = _liveness_entry()
    with _stub_registries([entry]):
        with pytest.raises(PluginCallFailed) as ei:
            dispatch_capability(
                "particle_picking", Capability.PREVIEW,
                "POST", "/preview", client=client,
            )
    assert ei.value.status_code == 500


def test_dispatch_passes_body_through_unchanged():
    transport = _MockTransport()
    client = httpx.Client(transport=transport)
    entry = _liveness_entry()
    with _stub_registries([entry]):
        dispatch_capability(
            "particle_picking", Capability.PREVIEW, "POST", "/preview",
            body={"image_path": "img.mrc", "diameter_angstrom": 64.0},
            client=client,
        )
    import json
    sent = json.loads(transport.calls[0].content.decode())
    assert sent == {"image_path": "img.mrc", "diameter_angstrom": 64.0}


# ---------------------------------------------------------------------------
# Reviewer B: enabled-state filter (sync path used to ignore /disable)
# ---------------------------------------------------------------------------


def _stub_registries_with_enabled(
    entries, *, default_per_category=None, enabled_map=None,
):
    """Like _stub_registries but with explicit per-plugin enabled state."""
    fake_liveness = MagicMock()
    fake_liveness.list_live.return_value = list(entries)
    fake_state = MagicMock()
    defaults = default_per_category or {}
    enabled = enabled_map or {}
    fake_state.get_default.side_effect = lambda cat: defaults.get((cat or "").lower())
    # Default enabled=True so tests not exercising the disabled path
    # don't have to pass a map.
    fake_state.is_enabled.side_effect = lambda pid: enabled.get(pid, True)
    return patch.multiple(
        "services.sync_dispatcher",
        get_liveness_registry=lambda: fake_liveness,
        get_state_store=lambda: fake_state,
    )


def test_dispatch_skips_disabled_plugin():
    """Reviewer B: pre-fix the sync path didn't check is_enabled — a
    disabled plugin still took sync traffic. Bus dispatcher refuses
    with 409; sync should refuse with BackendNotLive."""
    transport = _MockTransport()
    client = httpx.Client(transport=transport)
    entry = _liveness_entry("template-picker", backend_id="template-picker")
    with _stub_registries_with_enabled(
        [entry], enabled_map={"template-picker": False},
    ):
        with pytest.raises(BackendNotLive, match="disabled"):
            dispatch_capability(
                "particle_picking", Capability.PREVIEW, "POST", "/preview",
                client=client,
            )


def test_dispatch_target_backend_pin_refuses_disabled():
    transport = _MockTransport()
    client = httpx.Client(transport=transport)
    entry = _liveness_entry(backend_id="template-picker")
    with _stub_registries_with_enabled(
        [entry], enabled_map={"template-picker": False},
    ):
        with pytest.raises(BackendNotLive, match="disabled"):
            dispatch_capability(
                "particle_picking", Capability.PREVIEW, "POST", "/preview",
                target_backend="template-picker", client=client,
            )


# ---------------------------------------------------------------------------
# Reviewer C: priority inversion — default lacks cap, sibling has it
# ---------------------------------------------------------------------------


def test_dispatch_falls_through_when_default_lacks_capability():
    """Default backend has SYNC; sibling has PREVIEW. A PREVIEW call
    should fall through to the sibling, not raise CapabilityMissing
    on the default. Pinned: this is exactly what the X.1 backend axis
    exists to support."""
    transport = _MockTransport(200, {"preview_id": "p-1"})
    client = httpx.Client(transport=transport)
    default_plugin = _liveness_entry(
        "default-backend", backend_id="default-backend",
        capabilities=(Capability.SYNC,),  # no PREVIEW
        http_endpoint="http://default:8000",
    )
    sibling = _liveness_entry(
        "preview-backend", backend_id="preview-backend",
        capabilities=(Capability.PREVIEW,),
        http_endpoint="http://preview:8000",
    )
    with _stub_registries_with_enabled(
        [default_plugin, sibling],
        default_per_category={"particle_picking": "default-backend"},
    ):
        dispatch_capability(
            "particle_picking", Capability.PREVIEW, "POST", "/preview",
            client=client,
        )
    # The sibling, not the default, took the call.
    assert "preview:8000" in str(transport.calls[0].url)


def test_dispatch_falls_through_when_default_is_disabled():
    """Default exists + advertises cap, but is operator-disabled.
    Fall through to the next live, enabled candidate instead of
    failing the call (matches the bus dispatcher's behaviour
    pre-fix: bus returns 409, sync used to silently route)."""
    transport = _MockTransport()
    client = httpx.Client(transport=transport)
    default_plugin = _liveness_entry(
        "default-backend", backend_id="default-backend",
        http_endpoint="http://default:8000",
    )
    sibling = _liveness_entry(
        "alt-backend", backend_id="alt-backend",
        http_endpoint="http://alt:8000",
    )
    with _stub_registries_with_enabled(
        [default_plugin, sibling],
        default_per_category={"particle_picking": "default-backend"},
        enabled_map={"default-backend": False, "alt-backend": True},
    ):
        dispatch_capability(
            "particle_picking", Capability.PREVIEW, "POST", "/preview",
            client=client,
        )
    assert "alt:8000" in str(transport.calls[0].url)


# ---------------------------------------------------------------------------
# Reviewer A: sticky preview routing (preview_id → instance_id)
# ---------------------------------------------------------------------------


def test_preview_response_remembers_instance_id_for_retune():
    """First preview lands on replica A, the dispatcher caches the
    mapping. A subsequent retune with sticky pin lands on the same
    replica, not whichever the resolver picks."""
    from services.sync_dispatcher import (
        lookup_preview_route, reset_pooled_client,
    )

    reset_pooled_client()
    transport = _MockTransport(
        200, {"preview_id": "p-42", "particles": [], "num_particles": 0,
              "num_templates": 1, "target_pixel_size": 1.0, "image_binning": 1},
    )
    client = httpx.Client(transport=transport)
    replica_a = _liveness_entry("p", capabilities=(Capability.PREVIEW,))
    replica_a.instance_id = "i-A"
    replica_a.http_endpoint = "http://a:8000"
    replica_b = _liveness_entry("p", capabilities=(Capability.PREVIEW,))
    replica_b.instance_id = "i-B"
    replica_b.http_endpoint = "http://b:8000"

    with _stub_registries_with_enabled([replica_a, replica_b]):
        dispatch_capability(
            "particle_picking", Capability.PREVIEW, "POST", "/preview",
            body={"image_path": "img.mrc"}, client=client,
        )
        assert lookup_preview_route("p-42") == "i-A"


def test_retune_with_instance_id_pins_to_specific_replica():
    transport = _MockTransport()
    client = httpx.Client(transport=transport)
    replica_a = _liveness_entry("p", capabilities=(Capability.PREVIEW,))
    replica_a.instance_id = "i-A"
    replica_a.http_endpoint = "http://a:8000"
    replica_b = _liveness_entry("p", capabilities=(Capability.PREVIEW,))
    replica_b.instance_id = "i-B"
    replica_b.http_endpoint = "http://b:8000"

    with _stub_registries_with_enabled([replica_a, replica_b]):
        dispatch_capability(
            "particle_picking", Capability.PREVIEW,
            "POST", "/preview/p-42/retune",
            instance_id="i-B", client=client,
        )
    # Pinned replica B served the retune, not whichever the resolver
    # would pick first.
    assert "b:8000" in str(transport.calls[0].url)


def test_retune_pin_404s_when_replica_no_longer_live():
    """Replica that owned the preview restarted / fell out of the
    liveness window. The cached state is gone; a fresh resolution
    onto a different replica would 404 inside the plugin. Surface
    early as BackendNotLive with a meaningful message instead."""
    transport = _MockTransport()
    client = httpx.Client(transport=transport)
    other = _liveness_entry("p", capabilities=(Capability.PREVIEW,))
    other.instance_id = "i-OTHER"
    with _stub_registries_with_enabled([other]):
        with pytest.raises(BackendNotLive, match="i-GONE"):
            dispatch_capability(
                "particle_picking", Capability.PREVIEW,
                "POST", "/preview/p-1/retune",
                instance_id="i-GONE", client=client,
            )
