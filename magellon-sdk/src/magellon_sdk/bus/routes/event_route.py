"""Event (pub-sub) routes.

Four concrete route types, matching the existing broker-neutral
subjects owned by ``CategoryContract``:

- ``HeartbeatRoute``  — per-plugin liveness pulse
- ``AnnounceRoute``   — one-shot manifest publish at plugin startup
- ``ConfigRoute``     — dynamic config push (per-category or global broadcast)
- ``StepEventRoute``  — job-scoped step-progress events

Every route's ``subject`` string is the source of truth; binders
translate to their native form. Patterns use NATS-style ``*`` (one
segment) and ``>`` (one-or-more tail).
"""
from __future__ import annotations

from dataclasses import dataclass

from magellon_sdk.bus.routes.patterns import EventPattern
from magellon_sdk.categories.contract import (
    CONFIG_BROADCAST_SUBJECT,
    CategoryContract,
)


# ---------------------------------------------------------------------------
# Discovery — heartbeat + announce
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class HeartbeatRoute:
    """Per-plugin liveness pulse — ``magellon.plugins.heartbeat.<cat>.<plugin>``."""

    subject: str

    @classmethod
    def for_plugin(
        cls, contract: CategoryContract, plugin_name: str
    ) -> "HeartbeatRoute":
        return cls(subject=contract.heartbeat_subject(plugin_name))

    @classmethod
    def all(cls) -> EventPattern:
        """Match every plugin's heartbeat across all categories."""
        return EventPattern(subject_glob="magellon.plugins.heartbeat.>")


@dataclass(frozen=True)
class AnnounceRoute:
    """Manifest publish at plugin startup — ``magellon.plugins.announce.<cat>.<plugin>``."""

    subject: str

    @classmethod
    def for_plugin(
        cls, contract: CategoryContract, plugin_name: str
    ) -> "AnnounceRoute":
        return cls(subject=contract.announce_subject(plugin_name))

    @classmethod
    def all(cls) -> EventPattern:
        return EventPattern(subject_glob="magellon.plugins.announce.>")


# ---------------------------------------------------------------------------
# Dynamic config
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class ConfigRoute:
    """Config push — per-category or global broadcast.

    Per-category: ``magellon.plugins.config.<cat>`` via
    :meth:`for_category`. Global: the fixed
    ``magellon.plugins.config.broadcast`` subject via
    :meth:`broadcast`.
    """

    subject: str

    @classmethod
    def for_category(cls, contract: CategoryContract) -> "ConfigRoute":
        return cls(subject=contract.config_subject)

    @classmethod
    def broadcast(cls) -> "ConfigRoute":
        return cls(subject=CONFIG_BROADCAST_SUBJECT)

    @classmethod
    def all(cls) -> EventPattern:
        """Match every config push, per-category or broadcast."""
        return EventPattern(subject_glob="magellon.plugins.config.>")


# ---------------------------------------------------------------------------
# Step events — job-scoped progress
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class StepEventRoute:
    """Job-scoped step progress — ``job.<job_id>.step.<step>``.

    Subject format is **not** prefixed with ``magellon.`` — it matches
    today's ``RabbitmqEventPublisher`` wire format on the
    ``magellon.events`` exchange. Preserving the format is an MB1–MB5
    behavior-preservation requirement; realignment to the ``magellon.*``
    convention would be a later phase if we wanted it.
    """

    subject: str

    @classmethod
    def create(cls, *, job_id: str, step: str) -> "StepEventRoute":
        return cls(subject=f"job.{job_id}.step.{step}")

    @classmethod
    def all(cls) -> EventPattern:
        """Match every step of every job."""
        return EventPattern(subject_glob="job.*.step.*")


__all__ = [
    "AnnounceRoute",
    "ConfigRoute",
    "HeartbeatRoute",
    "StepEventRoute",
]
