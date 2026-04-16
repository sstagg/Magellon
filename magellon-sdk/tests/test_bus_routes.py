"""Route value object tests (MB1.2).

Pins the invariant: every route's subject string must match what
``CategoryContract`` produces today. Drift between the routes and
the contract would mean the bus talks to the wrong subjects on the
wire — caught here cheaply rather than in an integration test.

Also verifies the ``RouteRef`` / ``PatternRef`` structural Protocols
from MB1.1 actually accept the MB1.2 concrete classes.
"""
from __future__ import annotations

import pytest

from magellon_sdk.bus.interfaces import PatternRef, RouteRef
from magellon_sdk.bus.routes import (
    AnnounceRoute,
    ConfigRoute,
    EventPattern,
    HeartbeatRoute,
    StepEventRoute,
    TaskResultRoute,
    TaskRoute,
)
from magellon_sdk.categories.contract import (
    CONFIG_BROADCAST_SUBJECT,
    CTF,
    FFT,
    MOTIONCOR_CATEGORY,
    PARTICLE_PICKER,
    announce_subject,
    config_subject,
    heartbeat_subject,
    result_subject,
    task_subject,
)


# ---------------------------------------------------------------------------
# TaskRoute / TaskResultRoute — delegate to CategoryContract
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("contract", [CTF, MOTIONCOR_CATEGORY, FFT, PARTICLE_PICKER])
def test_task_route_for_category_matches_contract(contract):
    route = TaskRoute.for_category(contract)
    assert route.subject == contract.task_subject
    assert route.subject == task_subject(contract.category.name)


def test_task_route_named_passes_subject_through():
    """Escape hatch for test queues (e.g. motioncor_test_inqueue)."""
    assert TaskRoute.named("motioncor_test_inqueue").subject == "motioncor_test_inqueue"


def test_task_route_ctf_subject_exact():
    """Guard against silent subject drift — the canonical CTF
    subject is what production currently expects."""
    assert TaskRoute.for_category(CTF).subject == "magellon.tasks.ctf"


@pytest.mark.parametrize("contract", [CTF, MOTIONCOR_CATEGORY, FFT, PARTICLE_PICKER])
def test_task_result_route_for_category_matches_contract(contract):
    route = TaskResultRoute.for_category(contract)
    assert route.subject == contract.result_subject
    assert route.subject == result_subject(contract.category.name)


def test_task_result_route_all_glob():
    """Result fan-in consumer (CoreService TaskOutputProcessor)
    subscribes on every category's result subject."""
    pattern = TaskResultRoute.all()
    assert pattern.subject_glob == "magellon.tasks.*.result"


def test_task_routes_are_frozen():
    """Dataclasses are frozen — routes are value objects, not mutable."""
    route = TaskRoute.for_category(CTF)
    with pytest.raises(Exception):  # FrozenInstanceError
        route.subject = "mutated"  # type: ignore[misc]


# ---------------------------------------------------------------------------
# HeartbeatRoute / AnnounceRoute — plugin-scoped
# ---------------------------------------------------------------------------

def test_heartbeat_route_for_plugin_matches_contract():
    route = HeartbeatRoute.for_plugin(CTF, "ctffind4")
    assert route.subject == heartbeat_subject(CTF.category.name, "ctffind4")
    assert route.subject == "magellon.plugins.heartbeat.ctf.ctffind4"


def test_heartbeat_route_all_glob():
    """Liveness registry subscribes to every plugin's heartbeat."""
    assert HeartbeatRoute.all().subject_glob == "magellon.plugins.heartbeat.>"


def test_announce_route_for_plugin_matches_contract():
    route = AnnounceRoute.for_plugin(MOTIONCOR_CATEGORY, "motioncor2")
    assert route.subject == announce_subject(MOTIONCOR_CATEGORY.category.name, "motioncor2")
    assert route.subject == "magellon.plugins.announce.motioncor.motioncor2"


def test_announce_route_all_glob():
    assert AnnounceRoute.all().subject_glob == "magellon.plugins.announce.>"


# ---------------------------------------------------------------------------
# ConfigRoute — per-category and broadcast
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("contract", [CTF, MOTIONCOR_CATEGORY, FFT, PARTICLE_PICKER])
def test_config_route_for_category_matches_contract(contract):
    route = ConfigRoute.for_category(contract)
    assert route.subject == contract.config_subject
    assert route.subject == config_subject(contract.category.name)


def test_config_route_broadcast_matches_contract_constant():
    """Broadcast subject is a fixed constant — don't recompute it
    from a fake category."""
    assert ConfigRoute.broadcast().subject == CONFIG_BROADCAST_SUBJECT
    assert ConfigRoute.broadcast().subject == "magellon.plugins.config.broadcast"


def test_config_route_all_glob_includes_broadcast_and_per_category():
    """The pattern must catch both ``config.broadcast`` and
    ``config.<category>``. ``magellon.plugins.config.>`` matches both."""
    pattern = ConfigRoute.all()
    assert pattern.subject_glob == "magellon.plugins.config.>"


# ---------------------------------------------------------------------------
# StepEventRoute — job-scoped, intentionally NOT magellon-prefixed
# ---------------------------------------------------------------------------

def test_step_event_route_format_preserves_today_wire_shape():
    """MB1–MB5 is no behavior change. Today's RabbitmqEventPublisher
    publishes on subject ``job.<id>.step.<step>`` (no magellon prefix);
    MB1.2 preserves that exactly so MB5's flip is wire-compatible."""
    route = StepEventRoute.create(job_id="abc-123", step="ctf")
    assert route.subject == "job.abc-123.step.ctf"


def test_step_event_route_all_matches_today_forwarder_binding():
    """Today's step-event forwarder binds ``job.*.step.*``."""
    assert StepEventRoute.all().subject_glob == "job.*.step.*"


# ---------------------------------------------------------------------------
# RouteRef / PatternRef structural Protocol checks
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "route",
    [
        TaskRoute.for_category(CTF),
        TaskResultRoute.for_category(CTF),
        HeartbeatRoute.for_plugin(CTF, "x"),
        AnnounceRoute.for_plugin(CTF, "x"),
        ConfigRoute.for_category(CTF),
        ConfigRoute.broadcast(),
        StepEventRoute.create(job_id="1", step="ctf"),
    ],
)
def test_every_route_satisfies_route_ref(route):
    """Every concrete route must structurally implement RouteRef so
    bus.tasks.send / bus.events.publish type-check without a
    protocol-wrapping adapter."""
    assert isinstance(route, RouteRef)


@pytest.mark.parametrize(
    "pattern",
    [
        TaskResultRoute.all(),
        HeartbeatRoute.all(),
        AnnounceRoute.all(),
        ConfigRoute.all(),
        StepEventRoute.all(),
    ],
)
def test_every_pattern_satisfies_pattern_ref(pattern):
    assert isinstance(pattern, PatternRef)
    assert isinstance(pattern, EventPattern)
