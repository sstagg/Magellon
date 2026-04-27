"""MB3.1 / X.1 — verify _BusTaskDispatcher dispatches tasks through the bus.

Pins the runtime contract that characterization tests alone don't
cover:

  - dispatch(task) wraps the TaskMessage in a CloudEvents envelope
  - the envelope's ``data`` is the original task
  - the envelope's ``subject`` matches the route
  - ``bus.tasks.send`` is called on the overridden (mock) bus
  - the dispatcher propagates ``receipt.ok`` as its return value
  - ``target_backend`` pinning routes to the resolver-provided queue
  - a missing-backend pin raises BackendNotLive (no silent fallback)
"""
from __future__ import annotations

from uuid import uuid4

import pytest

from core.dispatcher_registry import (
    BackendNotLive,
    _BusTaskDispatcher,
)
from magellon_sdk.bus import DefaultMessageBus, PublishReceipt, get_bus
from magellon_sdk.bus.binders.mock import MockBinder
from magellon_sdk.bus.routes import TaskRoute
from magellon_sdk.categories.contract import CTF
from magellon_sdk.models import CTF_TASK, TaskMessage


@pytest.fixture
def mock_bus():
    """Inject a mock bus for the duration of the test. Clean up after
    so subsequent tests don't inherit the override."""
    binder = MockBinder()
    bus = DefaultMessageBus(binder)
    bus.start()
    get_bus.override(bus)
    try:
        yield bus, binder
    finally:
        get_bus.reset()
        bus.close()


def _task(*, target_backend=None) -> TaskMessage:
    return TaskMessage(
        id=uuid4(),
        job_id=uuid4(),
        type=CTF_TASK,
        data={"image_path": "/gpfs/x.mrc"},
        target_backend=target_backend,
    )


def test_dispatch_wraps_task_in_cloudevents_envelope(mock_bus):
    bus, binder = mock_bus
    disp = _BusTaskDispatcher(
        route=TaskRoute.for_category(CTF), name="bus:ctf", contract=CTF,
    )
    task = _task()

    ok = disp.dispatch(task)

    assert ok is True
    assert len(binder.published_tasks) == 1
    subject, envelope = binder.published_tasks[0]

    # Route subject matches the envelope subject + the wire address
    assert subject == "magellon.tasks.ctf"
    assert envelope.subject == "magellon.tasks.ctf"
    # CloudEvents envelope fields set by the dispatcher
    assert envelope.source == "magellon/core_service/dispatcher"
    assert envelope.type == "magellon.task.dispatch"
    # Task survives wrapping — handler on the other side gets it back
    assert envelope.data == task


def test_dispatch_returns_false_when_bus_reports_not_ok(mock_bus):
    """Publish failures shouldn't bubble as exceptions; the dispatcher
    returns False so callers (push_task_to_task_queue) can log and
    move on. Matches the legacy ``publish_message_to_queue`` contract."""
    bus, binder = mock_bus
    disp = _BusTaskDispatcher(
        route=TaskRoute.for_category(CTF), name="bus:ctf", contract=CTF,
    )

    # Replace the mock binder's publish with one that fails
    def _fail(route, envelope):
        return PublishReceipt(ok=False, message_id=str(envelope.id), error="broker down")

    binder.publish_task = _fail

    ok = disp.dispatch(_task())
    assert ok is False


# ---------------------------------------------------------------------------
# X.1 — backend pinning
# ---------------------------------------------------------------------------


def test_dispatch_routes_to_resolver_queue_when_target_backend_set(mock_bus):
    """A task with target_backend reaches the queue the resolver returns
    for ``(category, backend)``. Pinning is binding.

    X.7: the *envelope subject* stays symbolic
    (``magellon.tasks.ctf.ctffind4``) so the audit log + ce-subject
    header carry the pin signal; the binder publishes to the resolved
    queue via ``TaskRoute.physical_queue``."""
    _bus, binder = mock_bus

    def resolver(contract, backend):
        assert contract is CTF
        assert backend == "ctffind4"
        return "ctf_ctffind4_queue"

    disp = _BusTaskDispatcher(
        route=TaskRoute.for_category(CTF),
        name="bus:ctf",
        contract=CTF,
        backend_resolver=resolver,
    )

    ok = disp.dispatch(_task(target_backend="ctffind4"))

    assert ok is True
    [(subject, envelope)] = binder.published_tasks
    # Symbolic subject on the envelope — operator-grepable.
    assert subject == "magellon.tasks.ctf.ctffind4"
    assert envelope.subject == "magellon.tasks.ctf.ctffind4"


def test_dispatch_pinned_route_carries_physical_queue_for_binder(mock_bus):
    """The TaskRoute returned for a pinned task carries
    physical_queue=<resolver result>. This is what the binder uses to
    publish (bypassing legacy_queue_map). Without this the binder
    would treat the symbolic subject as a literal queue name and
    publish to a queue nobody consumes."""
    _bus, binder = mock_bus

    def resolver(contract, backend):
        return "ctf_gctf_queue"

    disp = _BusTaskDispatcher(
        route=TaskRoute.for_category(CTF),
        name="bus:ctf",
        contract=CTF,
        backend_resolver=resolver,
    )

    route = disp._route_for(_task(target_backend="gctf"))
    assert route.subject == "magellon.tasks.ctf.gctf"
    assert route.physical_queue == "ctf_gctf_queue"


def test_dispatch_unset_target_backend_uses_category_default_route(mock_bus):
    """When the caller doesn't pin a backend, today's behavior (publish
    to the category-default route) must be unchanged."""
    _bus, binder = mock_bus

    def resolver(contract, backend):
        pytest.fail("resolver should not be called for unpinned tasks")

    disp = _BusTaskDispatcher(
        route=TaskRoute.for_category(CTF),
        name="bus:ctf",
        contract=CTF,
        backend_resolver=resolver,
    )

    ok = disp.dispatch(_task())  # target_backend=None
    assert ok is True
    [(subject, _envelope)] = binder.published_tasks
    assert subject == "magellon.tasks.ctf"


def test_dispatch_raises_when_pinned_backend_not_live(mock_bus):
    """Resolver returning None means no live plugin claims this backend.
    The dispatcher refuses to silently fall back — masking that would
    surface as a wrong-result bug far away from the configuration
    mistake. Raise instead so the caller's HTTP boundary returns 503."""
    _bus, _binder = mock_bus

    def resolver(contract, backend):
        return None  # no live backend by that name

    disp = _BusTaskDispatcher(
        route=TaskRoute.for_category(CTF),
        name="bus:ctf",
        contract=CTF,
        backend_resolver=resolver,
    )

    with pytest.raises(BackendNotLive) as excinfo:
        disp.dispatch(_task(target_backend="ctffind4"))
    msg = str(excinfo.value)
    assert "ctffind4" in msg
    assert "CTF" in msg


def test_dispatch_pinned_without_resolver_raises_clearly(mock_bus):
    """If the registry was built without a resolver but a caller still
    passes target_backend, raise rather than silently use the category
    default — that mismatch is a programmer bug worth surfacing."""
    _bus, _binder = mock_bus

    disp = _BusTaskDispatcher(
        route=TaskRoute.for_category(CTF),
        name="bus:ctf",
        contract=CTF,
        backend_resolver=None,
    )

    with pytest.raises(BackendNotLive):
        disp.dispatch(_task(target_backend="ctffind4"))
