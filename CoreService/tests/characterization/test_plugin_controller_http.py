"""HTTP contract tests for the generic broker plugins router.

The first block keeps a handful of retired Architecture B assertions as
explicitly skipped historical records. The active tests inject broker
liveness and state fakes so the current controller contract runs in a
unit-test process.
"""
from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from plugins.controller import plugins_router


legacy_architecture_b = pytest.mark.skip(
    reason="Pins the retired Architecture B in-process plugin registry.",
)


@pytest.fixture(scope="module")
def client() -> TestClient:
    from uuid import uuid4

    from dependencies.auth import get_current_user_id

    app = FastAPI()
    app.include_router(plugins_router, prefix="/plugins")
    # The router requires an authenticated user; these tests pin the
    # HTTP contract, not auth (tests/test_route_auth_policy.py owns that).
    app.dependency_overrides[get_current_user_id] = lambda: uuid4()
    return TestClient(app)


@legacy_architecture_b
@pytest.mark.characterization
def test_list_plugins_shape(client):
    resp = client.get("/plugins/")
    assert resp.status_code == 200
    body = resp.json()
    assert isinstance(body, list)
    assert len(body) >= 1

    # Every entry must carry these fields — they drive the plugin picker UI
    # and now also the manager's transport/isolation routing decisions.
    required = {
        "plugin_id", "category", "name", "version", "schema_version",
        "description", "developer",
        # New capability surface — added with the PluginManifest work
        "capabilities", "supported_transports", "default_transport", "isolation",
    }
    for entry in body:
        assert required.issubset(entry.keys()), f"Missing keys in {entry}"


@legacy_architecture_b
@pytest.mark.characterization
def test_template_picker_advertises_real_capabilities(client):
    """Template-picker is the worked example of a plugin that opts into
    the new capability fields. Discovery must surface them so a UI/
    manager can route accordingly without fetching the full manifest."""
    body = client.get("/plugins/").json()
    tp = next(e for e in body if e["plugin_id"] == "pp/template-picker")
    assert "cpu_intensive" in tp["capabilities"]
    assert "progress_reporting" in tp["capabilities"]
    assert "in_process" in tp["supported_transports"]
    assert "http" in tp["supported_transports"]
    assert tp["isolation"] == "in_process"


@legacy_architecture_b
@pytest.mark.characterization
def test_motioncor_advertises_gpu_and_container_isolation(client):
    """MotionCor is the canonical "don't run me in-process" plugin.
    The manifest must reflect that so the future dispatcher knows to
    route it to a GPU container, not the backend process itself —
    this is why the manifest field exists at all."""
    body = client.get("/plugins/").json()
    mc = next(e for e in body if e["plugin_id"] == "motioncor/motioncor2")
    assert "gpu_required" in mc["capabilities"]
    assert "memory_intensive" in mc["capabilities"]
    assert "long_running" in mc["capabilities"]
    assert mc["isolation"] == "container"

    # Manifest endpoint exposes the resource hints a scheduler needs.
    m = client.get("/plugins/motioncor/motioncor2/manifest").json()
    assert m["resources"]["gpu_count"] == 1
    assert m["resources"]["memory_mb"] >= 16_000


@legacy_architecture_b
@pytest.mark.characterization
def test_ctffind_advertises_cpu_only_shape(client):
    """Sanity check that ctffind doesn't accidentally claim GPU — it's
    a CPU-bound binary and misclassifying it would starve GPU capacity
    for plugins that actually need it."""
    body = client.get("/plugins/").json()
    ctf = next(e for e in body if e["plugin_id"] == "ctf/ctffind")
    assert "cpu_intensive" in ctf["capabilities"]
    assert "gpu_required" not in ctf["capabilities"]
    assert ctf["isolation"] == "in_process"


@legacy_architecture_b
@pytest.mark.characterization
def test_plugin_manifest_endpoint_round_trips(client):
    """The /manifest endpoint returns the full PluginManifest. Same
    shape a remote/containerized plugin will eventually serve, so the
    manager can consume in-house and remote plugins through one model."""
    resp = client.get("/plugins/pp/template-picker/manifest")
    assert resp.status_code == 200
    m = resp.json()
    assert m["info"]["name"] == "template-picker"
    assert "resources" in m
    assert m["resources"]["memory_mb"] == 2_000
    assert m["resources"]["cpu_cores"] == 2
    assert m["isolation"] == "in_process"
    assert "tags" in m


@legacy_architecture_b
@pytest.mark.characterization
def test_list_plugins_contains_expected_ids(client):
    body = client.get("/plugins/").json()
    ids = {entry["plugin_id"] for entry in body}
    assert {"ctf/ctffind", "motioncor/motioncor2", "pp/template-picker"}.issubset(ids)


@legacy_architecture_b
@pytest.mark.characterization
@pytest.mark.parametrize("plugin_id", [
    "ctf/ctffind",
    "motioncor/motioncor2",
    "pp/template-picker",
])
def test_plugin_info_endpoint(client, plugin_id):
    resp = client.get(f"/plugins/{plugin_id}/info")
    assert resp.status_code == 200
    info = resp.json()
    assert info["name"] == plugin_id.split("/", 1)[1]
    assert "version" in info
    assert "schema_version" in info


@legacy_architecture_b
@pytest.mark.characterization
@pytest.mark.parametrize("plugin_id", [
    "ctf/ctffind",
    "motioncor/motioncor2",
    "pp/template-picker",
])
def test_plugin_input_schema_endpoint(client, plugin_id):
    resp = client.get(f"/plugins/{plugin_id}/schema/input")
    assert resp.status_code == 200
    schema = resp.json()
    # JSON Schema envelope — the React form generator depends on these keys.
    assert schema.get("type") == "object" or "properties" in schema or "$ref" in schema


@legacy_architecture_b
@pytest.mark.characterization
@pytest.mark.parametrize("plugin_id", [
    "ctf/ctffind",
    "motioncor/motioncor2",
    "pp/template-picker",
])
def test_plugin_output_schema_endpoint(client, plugin_id):
    resp = client.get(f"/plugins/{plugin_id}/schema/output")
    assert resp.status_code == 200
    schema = resp.json()
    assert schema.get("type") == "object" or "properties" in schema or "$ref" in schema


@pytest.mark.characterization
def test_unknown_plugin_returns_404(client):
    resp = client.get("/plugins/does-not-exist/info")
    assert resp.status_code == 404
    assert "not found" in resp.json()["detail"].lower()


# ---------------------------------------------------------------------------
# X.1 — capabilities endpoint
# ---------------------------------------------------------------------------
#
# These tests inject live entries into the singleton liveness registry
# directly, then call the endpoint, then clean up. The capabilities
# endpoint reads the registry + state store at request time, so this
# is the same shape a real plugin's announce would produce.

import pytest as _pytest

from core.plugin_liveness_registry import PluginLivenessRegistry
from core.plugin_state import get_state_store
from magellon_sdk.discovery import Announce
from magellon_sdk.models.manifest import (
    Capability as _Cap,
    IsolationLevel as _Isolation,
    PluginManifest as _PluginManifest,
    Transport as _Transport,
)
from magellon_sdk.models.plugin import PluginInfo as _PluginInfo


class _FakeStateStore:
    def __init__(self):
        self.enabled = {}
        self.default_impl = {}

    def is_enabled(self, plugin_id: str) -> bool:
        return self.enabled.get(plugin_id, True)

    def set_enabled(self, plugin_id: str, enabled: bool) -> None:
        self.enabled[plugin_id] = enabled

    def get_default(self, category: str):
        return self.default_impl.get(category.lower())

    def set_default(self, category: str, plugin_id: str | None) -> None:
        key = category.lower()
        if plugin_id is None:
            self.default_impl.pop(key, None)
        else:
            self.default_impl[key] = plugin_id


def _make_announce(*, plugin_id: str, category: str, backend_id: str,
                   version: str = "1.0", instance: str = "i-1",
                   task_queue: str = None) -> Announce:
    return Announce(
        plugin_id=plugin_id,
        plugin_version=version,
        category=category,
        instance_id=instance,
        manifest=_PluginManifest(
            info=_PluginInfo(name=plugin_id, version=version, description="t"),
            backend_id=backend_id,
            capabilities=[_Cap.CPU_INTENSIVE],
            supported_transports=[_Transport.RMQ],
            default_transport=_Transport.RMQ,
            isolation=_Isolation.CONTAINER,
        ),
        backend_id=backend_id,
        task_queue=task_queue,
    )


@_pytest.fixture
def isolated_plugin_state(monkeypatch):
    fresh = _FakeStateStore()
    monkeypatch.setattr("core.plugin_state._STORE", fresh, raising=False)
    return fresh


@_pytest.fixture
def isolated_liveness_registry(monkeypatch, isolated_plugin_state):
    """Swap the process-wide liveness registry singleton for a clean
    per-test instance so tests can inject entries without leaking
    across tests."""
    fresh = PluginLivenessRegistry(stale_after_seconds=300)
    monkeypatch.setattr(
        "core.plugin_liveness_registry._REGISTRY", fresh, raising=False,
    )
    # Mirror in the SDK module — controller.py reads through it.
    monkeypatch.setattr(
        "magellon_sdk.bus.services.liveness_registry._REGISTRY", fresh,
        raising=False,
    )
    return fresh


@_pytest.mark.characterization
def test_list_plugins_shape_for_live_broker(client, isolated_liveness_registry):
    isolated_liveness_registry.record_announce(_make_announce(
        plugin_id="ctf-ctffind4",
        category="ctf",
        backend_id="ctffind4",
        task_queue="ctf_q",
    ))

    resp = client.get("/plugins/")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert len(body) == 1
    row = body[0]
    assert row["plugin_id"] == "ctf/ctf-ctffind4"
    assert row["kind"] == "broker"
    assert row["default_transport"] == "rmq"
    assert row["isolation"] == "container"
    assert row["task_queue"] == "ctf_q"


@_pytest.mark.characterization
def test_capabilities_endpoint_returns_categories_with_no_backends(
    client, isolated_liveness_registry,
):
    """With no live broker plugins, every known category still appears
    — backends list is empty, schemas still embedded. UI uses this to
    render an empty-state."""
    resp = client.get("/plugins/capabilities")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert "sdk_version" in body
    cats = {c["name"] for c in body["categories"]}
    # All known categories surface, regardless of liveness.
    assert {"CTF", "MotionCor", "FFT"}.issubset(cats)
    # Every category embeds its schema for UI form rendering.
    ctf = next(c for c in body["categories"] if c["name"] == "CTF")
    assert ctf["input_schema"] is not None
    assert ctf["output_schema"] is not None


@_pytest.mark.characterization
def test_capabilities_endpoint_surfaces_examples(
    client, isolated_liveness_registry,
):
    """Gradio-style examples on the CategoryContract flow through to
    the HTTP response so the React test panel can render a "Try
    example" chip per pre-filled input."""
    body = client.get("/plugins/capabilities").json()
    ctf = next(c for c in body["categories"] if c["name"] == "CTF")
    assert isinstance(ctf["examples"], list)
    assert len(ctf["examples"]) >= 1
    first = ctf["examples"][0]
    # Every example carries the three contract fields.
    assert set(first.keys()) >= {"name", "description", "values"}
    assert isinstance(first["values"], dict)
    # The example's values reference real input-model fields.
    assert "pixelSize" in first["values"]
    assert "accelerationVoltage" in first["values"]


@_pytest.mark.characterization
def test_capabilities_endpoint_groups_replicas_by_backend_id(
    client, isolated_liveness_registry,
):
    """Two announces with the same plugin_id under different
    instance_ids are scale-out replicas of one backend. The endpoint
    must collapse them into one ``backends[]`` row with ``live_replicas=2``,
    not show two duplicate rows."""
    isolated_liveness_registry.record_announce(_make_announce(
        plugin_id="ctf-ctffind4", category="ctf", backend_id="ctffind4",
        instance="i-1", task_queue="ctf_q",
    ))
    isolated_liveness_registry.record_announce(_make_announce(
        plugin_id="ctf-ctffind4", category="ctf", backend_id="ctffind4",
        instance="i-2", task_queue="ctf_q",
    ))

    body = client.get("/plugins/capabilities").json()
    ctf = next(c for c in body["categories"] if c["name"] == "CTF")
    backends = [b for b in ctf["backends"] if b["backend_id"] == "ctffind4"]
    assert len(backends) == 1
    assert backends[0]["live_replicas"] == 2
    assert backends[0]["task_queue"] == "ctf_q"


@_pytest.mark.characterization
def test_capabilities_endpoint_lists_distinct_backends_separately(
    client, isolated_liveness_registry,
):
    """Two distinct backends (ctffind4, gctf) under one category must
    both appear, each as its own row, so the UI can render a backend
    picker."""
    isolated_liveness_registry.record_announce(_make_announce(
        plugin_id="ctf-ctffind4", category="ctf", backend_id="ctffind4",
        task_queue="ctf_ctffind4_q", instance="i-1",
    ))
    isolated_liveness_registry.record_announce(_make_announce(
        plugin_id="ctf-gctf", category="ctf", backend_id="gctf",
        task_queue="ctf_gctf_q", instance="i-2",
    ))

    body = client.get("/plugins/capabilities").json()
    ctf = next(c for c in body["categories"] if c["name"] == "CTF")
    backend_ids = {b["backend_id"] for b in ctf["backends"]}
    assert {"ctffind4", "gctf"}.issubset(backend_ids)


@_pytest.mark.characterization
def test_capabilities_endpoint_sorts_backends_default_first_then_alpha(
    client, isolated_liveness_registry,
):
    """X.9: ``backends[]`` ordering is part of the contract — UI
    renders the list directly without re-sorting. Default-flagged
    backend is index 0; remaining backends sort alphabetically by
    backend_id."""
    isolated_liveness_registry.record_announce(_make_announce(
        plugin_id="ctf-zzz-engine", category="ctf", backend_id="zzz",
        task_queue="ctf_zzz_q", instance="i-1",
    ))
    isolated_liveness_registry.record_announce(_make_announce(
        plugin_id="ctf-aaa-engine", category="ctf", backend_id="aaa",
        task_queue="ctf_aaa_q", instance="i-2",
    ))
    isolated_liveness_registry.record_announce(_make_announce(
        plugin_id="ctf-mmm-engine", category="ctf", backend_id="mmm",
        task_queue="ctf_mmm_q", instance="i-3",
    ))
    # Pin mmm as the default — it should come first regardless of
    # alphabetical position.
    get_state_store().set_default("ctf", "ctf-mmm-engine")
    try:
        body = client.get("/plugins/capabilities").json()
        ctf = next(c for c in body["categories"] if c["name"] == "CTF")
        backend_ids = [b["backend_id"] for b in ctf["backends"]]
        # Default first, then the remaining two in alpha order.
        assert backend_ids[0] == "mmm"
        assert backend_ids[1:] == ["aaa", "zzz"]
        assert ctf["backends"][0]["is_default_for_category"] is True
    finally:
        get_state_store().set_default("ctf", None)


@_pytest.mark.characterization
def test_capabilities_endpoint_marks_default_backend(
    client, isolated_liveness_registry, monkeypatch,
):
    """When the operator has pinned a default impl for a category, the
    endpoint must reflect both ``default_backend`` at the category
    level and ``is_default_for_category`` on the matching backend row.
    UI uses this to render the 'Default' badge."""
    isolated_liveness_registry.record_announce(_make_announce(
        plugin_id="ctf-ctffind4", category="ctf", backend_id="ctffind4",
        task_queue="ctf_q", instance="i-1",
    ))
    isolated_liveness_registry.record_announce(_make_announce(
        plugin_id="ctf-gctf", category="ctf", backend_id="gctf",
        task_queue="ctf_gctf_q", instance="i-2",
    ))
    # Pin ctffind4 as the default — the same path
    # POST /plugins/categories/{cat}/default takes.
    get_state_store().set_default("ctf", "ctf-ctffind4")
    try:
        body = client.get("/plugins/capabilities").json()
        ctf = next(c for c in body["categories"] if c["name"] == "CTF")
        assert ctf["default_backend"] == "ctf-ctffind4"
        ctffind4 = next(b for b in ctf["backends"] if b["backend_id"] == "ctffind4")
        gctf = next(b for b in ctf["backends"] if b["backend_id"] == "gctf")
        assert ctffind4["is_default_for_category"] is True
        assert gctf["is_default_for_category"] is False
    finally:
        # Don't leak the pinned default into other tests.
        get_state_store().set_default("ctf", None)


@pytest.mark.characterization
def test_submit_job_validates_input(client, isolated_liveness_registry):
    """Bad input returns 422 with a helpful detail, not a 500."""
    isolated_liveness_registry.record_announce(_make_announce(
        plugin_id="ctf-ctffind4",
        category="ctf",
        backend_id="ctffind4",
        task_queue="ctf_q",
    ))
    resp = client.post(
        "/plugins/ctf/ctffind4/jobs",
        json={"input": {"clearly": "wrong"}},
    )
    assert resp.status_code == 422
    assert "Invalid input" in resp.json()["detail"]


# ---------------------------------------------------------------------------
# PE1-A (2026-05-10): subject-tag socket validation
# ---------------------------------------------------------------------------
#
# The capabilities endpoint must surface ``subject_kind`` /
# ``produces_subject_kind`` from the SDK contract so the catalog UI
# and a future workflow composer can wire plugin outputs to plugin
# inputs without parsing the input schema. The dispatch gate rejects
# aggregate-category jobs that lack the required subject id.


@_pytest.mark.characterization
def test_capabilities_endpoint_surfaces_subject_kind(
    client, isolated_liveness_registry,
):
    """Every category surfaces ``subject_kind`` — defaulting to
    ``'image'`` but overridden to ``'particle_stack'`` for aggregate
    categories. PE1-A: lets the UI/composer answer "which plugins can
    consume this artifact?" without inspecting the input schema."""
    body = client.get("/plugins/capabilities").json()
    by_name = {c["name"]: c for c in body["categories"]}

    # Default is "image" for the bulk of categories.
    assert by_name["CTF"]["subject_kind"] == "image"
    assert by_name["MotionCor"]["subject_kind"] == "image"
    assert by_name["FFT"]["subject_kind"] == "image"

    # Override for aggregate-keyed categories.
    assert by_name["2D Classification"]["subject_kind"] == "particle_stack"


@_pytest.mark.characterization
def test_capabilities_endpoint_surfaces_produces_subject_kind_for_extraction(
    client, isolated_liveness_registry,
):
    """``produces_subject_kind`` is the output subject when it differs
    from the input. ``ParticleExtraction`` is the canonical transforming
    category — reads images, emits particle stacks. In-place categories
    (CTF, MotionCor, FFT) leave it ``None`` (= same as input)."""
    body = client.get("/plugins/capabilities").json()
    by_name = {c["name"]: c for c in body["categories"]}

    assert by_name["ParticleExtraction"]["produces_subject_kind"] == "particle_stack"
    # In-place categories — input and output share a subject.
    assert by_name["CTF"]["produces_subject_kind"] is None
    assert by_name["MotionCor"]["produces_subject_kind"] is None


@_pytest.mark.characterization
def test_capabilities_endpoint_surfaces_input_subjects(
    client, isolated_liveness_registry,
):
    """PE1-B: per-input-field subject tags ride alongside the category-
    level subject_kind. Every image-keyed category tags ``image_id``;
    2D classification additionally tags ``particle_stack_id`` (the one
    artifact-OID input field today, validated by the dispatch gate)."""
    body = client.get("/plugins/capabilities").json()
    by_name = {c["name"]: c for c in body["categories"]}

    # Every image-keyed category tags image_id.
    assert by_name["CTF"]["input_subjects"]["image_id"] == "image"
    assert by_name["FFT"]["input_subjects"]["image_id"] == "image"
    assert by_name["MotionCor"]["input_subjects"]["image_id"] == "image"

    # 2D classification tags the artifact-OID input.
    cls_in = by_name["2D Classification"]["input_subjects"]
    assert cls_in["particle_stack_id"] == "particle_stack"


@_pytest.mark.characterization
def test_capabilities_endpoint_surfaces_output_subjects_for_extraction(
    client, isolated_liveness_registry,
):
    """PE1-B: ``output_subjects`` identifies which output field carries
    the produced-artifact OID. Particle extraction emits a
    ``particle_stack`` artifact and tags ``particle_stack_id`` on the
    output — the catalog UI uses this to distinguish the artifact
    reference from scalar summaries like ``particle_count``."""
    body = client.get("/plugins/capabilities").json()
    by_name = {c["name"]: c for c in body["categories"]}

    assert (
        by_name["ParticleExtraction"]["output_subjects"]["particle_stack_id"]
        == "particle_stack"
    )
    # In-place categories don't yet tag outputs (no produced-artifact OID).
    assert by_name["CTF"]["output_subjects"] == {}


@_pytest.mark.characterization
def test_submit_job_rejects_particle_stack_category_without_subject_id(
    client, isolated_liveness_registry,
):
    """Aggregate-category dispatch (``subject_kind='particle_stack'``)
    must carry ``particle_stack_id`` on the input. Today the SDK's
    ``TwoDClassificationInput`` marks the field ``Optional[UUID]``, so
    Pydantic validation alone won't catch a missing subject — without
    PE1-A's explicit gate, the job would land with ``subject_id=None``
    and the projector couldn't link it back to its source artifact."""
    # Register a live 2D-classification backend so _find_broker_plugin
    # resolves the route (otherwise: 404 before reaching the gate).
    # The category string is normalized space/underscore/case-insensitively
    # against contract.category.name ("2D Classification") so any of
    # these forms works.
    isolated_liveness_registry.record_announce(_make_announce(
        plugin_id="can-classifier",
        category="2D Classification",
        backend_id="can-classifier",
        task_queue="cls_q",
    ))

    resp = client.post(
        "/plugins/2D Classification/can-classifier/jobs",
        json={"input": {
            "mrcs_path": "/x/y.mrcs",
            "star_path": "/x/y.star",
            "output_dir": "/x/out",
            # particle_stack_id intentionally omitted
        }},
    )
    assert resp.status_code == 422, resp.text
    detail = resp.json()["detail"]
    assert "particle_stack" in detail.lower()
    assert "particle_stack_id" in detail


@pytest.mark.characterization
def test_cancel_unknown_job_returns_404(client, monkeypatch):
    """Pins the LookupError -> 404 mapping without needing a live DB."""
    from services.job_manager import job_manager

    def _unknown(job_id, include_result=False):
        raise LookupError(job_id)

    monkeypatch.setattr(job_manager, "get_job", _unknown)
    resp = client.delete("/plugins/jobs/00000000-0000-0000-0000-000000000999")
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# PE1-B (2026-05-11): dispatch gate validates artifact-kind on UUID inputs
# ---------------------------------------------------------------------------
#
# Unit tests against ``_reject_if_subject_tag_mismatch`` directly. The
# HTTP-route wiring is proven by the existing PE1-A test
# (``test_submit_job_rejects_particle_stack_category_without_subject_id``)
# — same call site, same exception shape, so the wiring assertion
# carries over for free. These tests focus on the gate's semantics:
# OK on match, 422 on mismatch, 422 on missing row, no-op on legacy
# contracts.


from unittest.mock import MagicMock as _MagicMock
import uuid as _uuid

from fastapi import HTTPException as _HTTPException

from magellon_sdk.categories.contract import (
    CTF as _CTF,
    TWO_D_CLASSIFICATION_CATEGORY as _TWO_D_CLASSIFICATION_CATEGORY,
)
from magellon_sdk.models.tasks import TwoDClassificationInput as _TwoDClassificationInput
from plugins.controller import _reject_if_subject_tag_mismatch as _gate


class _FakeArtifact:
    def __init__(self, oid: _uuid.UUID, kind: str, deleted_at=None):
        self.oid = oid
        self.kind = kind
        self.deleted_at = deleted_at


def _install_fake_session(monkeypatch, *artifacts: _FakeArtifact):
    """Wire ``database.session_local`` to return a session that resolves
    ``Artifact.oid == X`` to the matching ``_FakeArtifact``, or None.

    Kept inline because no other test in this module touches the DB and
    spinning up a real Alembic-migrated test DB just to assert one
    rejection would be overkill.
    """
    by_oid = {a.oid: a for a in artifacts}

    def _filter(predicate):
        # The gate calls ``db.query(Artifact).filter(Artifact.oid == oid)``;
        # SQLAlchemy expressions are opaque here, so we read the oid from
        # the call site's locals via the most recent invocation captured
        # below. Tests pin the captured oid before asserting.
        return _QueryStub(predicate)

    class _QueryStub:
        def __init__(self, predicate):
            self._predicate = predicate
            # The predicate is `Artifact.oid == <UUID>`. Pull the rhs.
            try:
                self._wanted = predicate.right.value
            except AttributeError:
                self._wanted = None

        def filter(self, *args, **kwargs):
            # The gate doesn't chain a second filter on Artifact lookups,
            # but lineage helpers do — be permissive.
            return self

        def first(self):
            return by_oid.get(self._wanted)

    fake_session = _MagicMock()
    fake_session.query.return_value.filter.side_effect = _filter
    fake_session.close = _MagicMock()

    import database as _database
    monkeypatch.setattr(_database, "session_local", lambda: fake_session)


def test_gate_passes_when_artifact_kind_matches_tag(monkeypatch):
    """Happy path: ``particle_stack_id`` tagged ``particle_stack`` and
    the row's ``kind`` matches — the gate returns silently."""
    oid = _uuid.uuid4()
    _install_fake_session(monkeypatch, _FakeArtifact(oid, "particle_stack"))

    inp = _TwoDClassificationInput(
        particle_stack_id=oid,
        mrcs_path="/x/y.mrcs",
        star_path="/x/y.star",
        output_dir="/x/out",
    )
    # No raise = pass.
    _gate(_TWO_D_CLASSIFICATION_CATEGORY, inp)


def test_gate_rejects_when_artifact_kind_does_not_match(monkeypatch):
    """A 2D-class dispatch pointing at a ``class_averages`` artifact
    (wrong kind for the field) is rejected with 422 before any worker
    is woken — the headline PE1 payoff."""
    oid = _uuid.uuid4()
    _install_fake_session(monkeypatch, _FakeArtifact(oid, "class_averages"))

    inp = _TwoDClassificationInput(
        particle_stack_id=oid,
        mrcs_path="/x/y.mrcs",
        star_path="/x/y.star",
        output_dir="/x/out",
    )
    with pytest.raises(_HTTPException) as exc:
        _gate(_TWO_D_CLASSIFICATION_CATEGORY, inp)
    assert exc.value.status_code == 422
    assert "particle_stack_id" in exc.value.detail
    assert "particle_stack" in exc.value.detail
    assert "class_averages" in exc.value.detail


def test_gate_rejects_when_artifact_missing(monkeypatch):
    """OID with no row in the table (deleted or never existed) is a
    dispatch error, not a silent fall-through. Without this, a stale
    OID would land a queued task that fails far downstream."""
    oid = _uuid.uuid4()
    _install_fake_session(monkeypatch)  # no artifacts seeded

    inp = _TwoDClassificationInput(
        particle_stack_id=oid,
        mrcs_path="/x/y.mrcs",
        star_path="/x/y.star",
        output_dir="/x/out",
    )
    with pytest.raises(_HTTPException) as exc:
        _gate(_TWO_D_CLASSIFICATION_CATEGORY, inp)
    assert exc.value.status_code == 422
    assert "unknown artifact" in exc.value.detail


def test_gate_rejects_soft_deleted_artifact(monkeypatch):
    """An artifact with ``deleted_at`` set is invisible to the gate —
    consistent with the read endpoints (artifacts_controller) treating
    soft-deleted rows as 404s."""
    from datetime import datetime
    oid = _uuid.uuid4()
    _install_fake_session(
        monkeypatch,
        _FakeArtifact(oid, "particle_stack", deleted_at=datetime.utcnow()),
    )

    inp = _TwoDClassificationInput(
        particle_stack_id=oid,
        mrcs_path="/x/y.mrcs",
        star_path="/x/y.star",
        output_dir="/x/out",
    )
    with pytest.raises(_HTTPException) as exc:
        _gate(_TWO_D_CLASSIFICATION_CATEGORY, inp)
    assert exc.value.status_code == 422


def test_gate_is_noop_on_legacy_contract_with_no_tags():
    """A contract with no ``input_subjects`` declared must pass the
    gate unchanged — the migration story for pre-PE1-B categories."""
    # Construct a contract with the input_subjects map intentionally empty.
    from magellon_sdk.categories.contract import CategoryContract
    from magellon_sdk.categories.outputs import CtfOutput
    from magellon_sdk.models.tasks import CTF_TASK, CtfInput

    legacy = CategoryContract(
        category=CTF_TASK,
        input_model=CtfInput,
        output_model=CtfOutput,
    )
    inp = CtfInput(inputFile="/x.mrc")
    # No raise even without a session fixture — the gate short-circuits
    # before touching the DB when input_subjects is empty.
    _gate(legacy, inp)


def test_gate_skips_image_tags(monkeypatch):
    """Image-tagged fields aren't validated today (Image isn't an
    Artifact subtype). The gate must not query the DB for them —
    if it did, the existing image-keyed dispatches would all fail."""
    from magellon_sdk.models.tasks import CtfInput

    # Image id present but DB has no artifact rows. The gate must
    # ignore the ``image`` tag entirely and not raise.
    _install_fake_session(monkeypatch)
    inp = CtfInput(inputFile="/x.mrc", image_id=_uuid.uuid4())
    _gate(_CTF, inp)
