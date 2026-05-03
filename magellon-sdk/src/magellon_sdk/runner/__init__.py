"""Plugin broker runner package.

MB0 split the single-file ``magellon_sdk/runner.py`` into two modules
to make the composition seam visible before the MessageBus lands:

- :mod:`magellon_sdk.runner.plugin_runner` — the
  :class:`PluginBrokerRunner` harness class: pika consume loop,
  per-message decode / validate / run / encode flow, provenance
  stamping, reconnect.
- :mod:`magellon_sdk.runner.lifecycle` — thin wrappers around
  :class:`DiscoveryPublisher` + :class:`HeartbeatLoop` (announce and
  heartbeat) and :class:`ConfigSubscriber` (dynamic config). These are
  the services the bus will absorb in MB5; isolating them here makes
  the seam explicit.

External callers keep importing from ``magellon_sdk.runner`` — this
package re-exports everything the old single-file module exposed.
"""
from magellon_sdk.runner.active_task import (
    PublisherFactory,
    current_task,
    emit_step,
    get_step_event_loop,
    make_step_reporter,
    reset_active_task,
    set_active_task,
)
from magellon_sdk.runner.plugin_runner import PluginBrokerRunner, ResultFactory

__all__ = [
    "PluginBrokerRunner",
    "PublisherFactory",
    "ResultFactory",
    "current_task",
    "emit_step",
    "get_step_event_loop",
    "make_step_reporter",
    "reset_active_task",
    "set_active_task",
]
