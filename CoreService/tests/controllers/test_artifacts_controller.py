"""Tests for the Artifact HTTP controller — focused on PE3-lite's
``/artifacts/{oid}/workflow.json`` portable provenance export.

Uses FastAPI ``dependency_overrides`` to inject a fake session that
serves pre-built Artifact + ImageJobTask stand-ins. The endpoint only
calls ``db.query(Model).filter(Model.oid == X).first()`` so the fake
session is small and contained — no SQLite mirror needed.
"""
from __future__ import annotations

from datetime import datetime
from types import SimpleNamespace
from typing import Dict
from uuid import UUID, uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from controllers.artifacts_controller import artifacts_router
from database import get_db
from dependencies.auth import get_current_user_id
from models.sqlalchemy_models import Artifact, ImageJobTask


# ---------------------------------------------------------------------------
# Test fixtures: fake session + tiny artifact / task constructors
# ---------------------------------------------------------------------------


class _FakeQuery:
    """Honors the minimal ``query(M).filter(M.oid == oid).first()``
    pattern the endpoint uses. Pulls the literal from the comparison's
    right-hand BindParameter."""

    def __init__(self, lookup: Dict[UUID, object]):
        self._lookup = lookup
        self._target_oid = None

    def filter(self, expr):
        # SQLAlchemy column-equality renders as BinaryExpression with
        # .right being a BindParameter; .value holds the python literal.
        self._target_oid = getattr(expr.right, "value", None)
        return self

    def first(self):
        return self._lookup.get(self._target_oid)


class _FakeDb:
    def __init__(self, artifacts, tasks):
        self._artifacts = artifacts
        self._tasks = tasks

    def query(self, model):
        if model is Artifact:
            return _FakeQuery(self._artifacts)
        if model is ImageJobTask:
            return _FakeQuery(self._tasks)
        raise NotImplementedError(f"Unhandled model: {model!r}")


def _mk_artifact(
    *,
    oid: UUID | None = None,
    kind: str = "particle_stack",
    source_artifact_id: UUID | None = None,
    producing_task_id: UUID | None = None,
    msession_id: str = "s1",
    created_date: datetime | None = None,
    deleted_at: datetime | None = None,
):
    return SimpleNamespace(
        oid=oid or uuid4(),
        kind=kind,
        source_artifact_id=source_artifact_id,
        producing_task_id=producing_task_id,
        msession_id=msession_id,
        created_date=created_date or datetime.utcnow(),
        deleted_at=deleted_at,
    )


def _mk_task(
    *,
    oid: UUID | None = None,
    plugin_id: str = "ctf-ctffind4",
    plugin_version: str = "1.4.2",
    data_json: dict | None = None,
):
    return SimpleNamespace(
        oid=oid or uuid4(),
        plugin_id=plugin_id,
        plugin_version=plugin_version,
        data_json=data_json or {},
    )


def _client(artifacts, tasks) -> TestClient:
    app = FastAPI()
    app.include_router(artifacts_router, prefix="/artifacts")
    app.dependency_overrides[get_db] = lambda: _FakeDb(artifacts, tasks)
    app.dependency_overrides[get_current_user_id] = lambda: uuid4()
    return TestClient(app)


# ---------------------------------------------------------------------------
# PE3-lite — workflow.json
# ---------------------------------------------------------------------------


def test_workflow_returns_root_plus_chain():
    """Leaf artifact's workflow.json walks ``source_artifact_id``
    upward to the imported root, in most-recent-first order."""
    root_oid, mid_oid, leaf_oid = uuid4(), uuid4(), uuid4()
    mid_task_oid, leaf_task_oid = uuid4(), uuid4()

    imported = _mk_artifact(oid=root_oid, kind="image", producing_task_id=None)
    mid = _mk_artifact(
        oid=mid_oid, kind="ctf_estimate",
        source_artifact_id=root_oid, producing_task_id=mid_task_oid,
    )
    leaf = _mk_artifact(
        oid=leaf_oid, kind="particle_stack",
        source_artifact_id=mid_oid, producing_task_id=leaf_task_oid,
    )

    artifacts = {root_oid: imported, mid_oid: mid, leaf_oid: leaf}
    tasks = {
        mid_task_oid: _mk_task(plugin_id="ctf-ctffind4", plugin_version="1.4.2"),
        leaf_task_oid: _mk_task(plugin_id="extractor", plugin_version="0.9"),
    }

    resp = _client(artifacts, tasks).get(f"/artifacts/{leaf_oid}/workflow.json")
    assert resp.status_code == 200, resp.text

    body = resp.json()
    assert body["magellon_workflow_version"] == 1
    assert body["lineage_shape"] == "single_parent_chain"
    assert body["root_artifact"]["oid"] == str(leaf_oid)
    assert body["root_artifact"]["kind"] == "particle_stack"

    ancestor_oids = [a["oid"] for a in body["ancestors"]]
    # Most-recent first: mid (direct parent), then imported (root).
    assert ancestor_oids == [str(mid_oid), str(root_oid)]
    assert body["truncated_at_depth"] is None


def test_workflow_producer_null_for_imported_root():
    """An artifact with no ``producing_task_id`` (imported into the
    system, not produced by a plugin) reports ``producer: null``."""
    root_oid = uuid4()
    imported = _mk_artifact(oid=root_oid, kind="image", producing_task_id=None)

    resp = _client({root_oid: imported}, {}).get(f"/artifacts/{root_oid}/workflow.json")
    assert resp.status_code == 200
    body = resp.json()
    assert body["root_artifact"]["producer"] is None
    assert body["ancestors"] == []


def test_workflow_producer_populated_from_task():
    """Producer block carries plugin_id, plugin_version, and params
    from the producing task's ``data_json``."""
    art_oid = uuid4()
    task_oid = uuid4()
    art = _mk_artifact(
        oid=art_oid, kind="ctf_estimate",
        source_artifact_id=None, producing_task_id=task_oid,
    )
    task = _mk_task(
        oid=task_oid,
        plugin_id="ctf-ctffind4", plugin_version="1.4.2",
        data_json={"box_size": 256, "apix": 1.06},
    )

    resp = _client({art_oid: art}, {task_oid: task}).get(
        f"/artifacts/{art_oid}/workflow.json",
    )
    assert resp.status_code == 200
    producer = resp.json()["root_artifact"]["producer"]
    assert producer["plugin_id"] == "ctf-ctffind4"
    assert producer["plugin_version"] == "1.4.2"
    assert producer["params"] == {"box_size": 256, "apix": 1.06}


def test_workflow_redacts_secret_keyed_params():
    """Params with keys matching ``secret|password|token|api[_-]?key``
    (case-insensitive) are redacted to ``'<redacted>'``. Heuristic
    until manifest-driven ``export: false`` lands."""
    art_oid = uuid4()
    task_oid = uuid4()
    art = _mk_artifact(oid=art_oid, producing_task_id=task_oid)
    task = _mk_task(
        oid=task_oid,
        data_json={
            "box_size": 256,        # public
            "api_key": "sk-abc",    # redact
            "API_TOKEN": "xyz",     # redact (case insensitive)
            "user_password": "p",   # redact
            "model_secret": "m",    # redact
            "innocuous": "ok",      # public
        },
    )

    resp = _client({art_oid: art}, {task_oid: task}).get(
        f"/artifacts/{art_oid}/workflow.json",
    )
    params = resp.json()["root_artifact"]["producer"]["params"]
    assert params["box_size"] == 256
    assert params["innocuous"] == "ok"
    assert params["api_key"] == "<redacted>"
    assert params["API_TOKEN"] == "<redacted>"
    assert params["user_password"] == "<redacted>"
    assert params["model_secret"] == "<redacted>"


def test_workflow_404_for_unknown_artifact():
    """Unknown oid → 404, consistent with the existing /artifacts/{oid}
    detail endpoint."""
    resp = _client({}, {}).get(f"/artifacts/{uuid4()}/workflow.json")
    assert resp.status_code == 404


def test_workflow_404_for_soft_deleted_artifact():
    """Soft-deleted rows are invisible to the export (same contract as
    /artifacts/{oid})."""
    art_oid = uuid4()
    art = _mk_artifact(oid=art_oid, deleted_at=datetime.utcnow())
    resp = _client({art_oid: art}, {}).get(f"/artifacts/{art_oid}/workflow.json")
    assert resp.status_code == 404


def test_workflow_truncates_at_depth_200():
    """Chains exceeding the 200-deep walk cap return a 200-element
    ``ancestors`` list and signal truncation via ``truncated_at_depth``.
    The cap is intentionally generous (UI display uses 20) — export
    callers usually want the full chain when possible — but pathological
    chains shouldn't unbound the response."""
    # Build a 250-deep chain: leaf → a249 → a248 → ... → a0 (top).
    # Each artifact points at the next via source_artifact_id.
    chain_len = 250
    oids = [uuid4() for _ in range(chain_len)]
    artifacts = {}
    # a0 is top-of-chain (source_artifact_id=None); higher indices
    # point one step further down toward a0.
    for i, oid in enumerate(oids):
        parent_oid = oids[i - 1] if i > 0 else None
        artifacts[oid] = _mk_artifact(
            oid=oid, kind="step", source_artifact_id=parent_oid,
        )
    leaf_oid = oids[-1]

    resp = _client(artifacts, {}).get(f"/artifacts/{leaf_oid}/workflow.json")
    assert resp.status_code == 200
    body = resp.json()
    assert len(body["ancestors"]) == 200
    assert body["truncated_at_depth"] == 200


def test_workflow_no_truncation_flag_at_exact_depth_boundary():
    """A chain of exactly 200 ancestors fits without truncation —
    the cap is inclusive, and the for/else's ``cursor is None`` check
    distinguishes "ran out of parents" from "hit the cap with more to
    go". Pins this off-by-one boundary."""
    # 201 artifacts total: leaf + 200 ancestors. After walking 200
    # parents the cursor is None (top-of-chain), so truncated=False.
    chain_len = 201
    oids = [uuid4() for _ in range(chain_len)]
    artifacts = {}
    for i, oid in enumerate(oids):
        parent_oid = oids[i - 1] if i > 0 else None
        artifacts[oid] = _mk_artifact(
            oid=oid, kind="step", source_artifact_id=parent_oid,
        )
    leaf_oid = oids[-1]

    resp = _client(artifacts, {}).get(f"/artifacts/{leaf_oid}/workflow.json")
    body = resp.json()
    assert len(body["ancestors"]) == 200
    assert body["truncated_at_depth"] is None


def test_workflow_handles_cycle_safely():
    """A pathological cycle (shouldn't happen under immutability, but
    defensive) terminates the walk without infinite looping. The
    ``seen`` guard breaks the loop when the cursor revisits a known
    oid."""
    a_oid, b_oid = uuid4(), uuid4()
    # Artificial cycle: a → b → a
    a = _mk_artifact(oid=a_oid, source_artifact_id=b_oid)
    b = _mk_artifact(oid=b_oid, source_artifact_id=a_oid)

    resp = _client({a_oid: a, b_oid: b}, {}).get(f"/artifacts/{a_oid}/workflow.json")
    assert resp.status_code == 200
    # Walk records exactly one step before the cycle guard fires.
    assert len(resp.json()["ancestors"]) == 1
