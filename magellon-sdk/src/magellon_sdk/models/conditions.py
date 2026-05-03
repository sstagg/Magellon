"""Condition status type — Kubernetes-style multi-axis status.

PM2 of ``Documentation/PLUGIN_MANAGER_PLAN.md`` (revised 2026-05-04).
Pre-PM2 plugin status was implicit: the UI inferred "running" from
"present in GET /plugins/" and "enabled" from a single boolean. That
collapses orthogonal concerns. A plugin can be:

  * ``Installed=True, Enabled=True, Live=False, Healthy=False`` —
    catalogued, operator approves, but not announcing
  * ``Installed=True, Enabled=False, Live=True`` — running but
    quiesced by the operator
  * ``Installed=True, Enabled=True, Live=True, Healthy=False`` —
    running, recent task results all failed (sick replica)
  * ``Default=True`` — operator-pinned default for at least one
    category (per ``plugin_category_default``)

Each is a separate condition with its own ``status``,
``last_transition_time``, machine-readable ``reason`` token, and
human-readable ``message``. Mirrors the OLM / Kubernetes
``Status.Conditions[]`` pattern.

Allowed condition types (this enum is the SDK-side contract; the
controller's reducer is the only writer).
"""
from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field


class ConditionType(str, Enum):
    """Orthogonal axes of plugin status. Each can be True / False /
    Unknown independently."""

    INSTALLED = "Installed"
    """Plugin row exists in the ``plugin`` catalog (PM1)."""

    ENABLED = "Enabled"
    """Operator has not toggled this plugin off
    (``plugin_state.enabled=true``)."""

    LIVE = "Live"
    """Plugin is announcing + heartbeating on the bus within the
    stale-after window."""

    HEALTHY = "Healthy"
    """Recent task outcomes don't trip the failure heuristic
    (≥1 success in window OR no terminal events at all). Source is
    ``job_event.ts`` joined through ``image_job_task.plugin_id``."""

    DEFAULT = "Default"
    """Plugin is the operator-pinned default for at least one
    category (matches a row in ``plugin_category_default``).
    Multi-category plugins can be Default for one category and not
    another — the UI consumes this with the category in the
    message."""

    PAUSED = "Paused"
    """PM4 (deferred). Not emitted today; reserved so the SDK
    contract doesn't change when PM4 lands. Operationally distinct
    from ``Enabled=False`` only when PM4 designs TTL + reason
    taxonomy."""


class ConditionStatus(str, Enum):
    TRUE = "True"
    FALSE = "False"
    UNKNOWN = "Unknown"


class Condition(BaseModel):
    """One axis of plugin status. Multiple conditions can be True at
    once — that's the point. Pre-PM2 the UI had to derive these
    from inferred fields; the reducer makes them explicit."""

    type: ConditionType
    status: ConditionStatus
    reason: Optional[str] = None
    """Short machine-readable token (e.g. ``'Heartbeat'``,
    ``'NoRecentTask'``, ``'OperatorPinned'``). Filterable / chartable;
    NOT a sentence."""
    message: Optional[str] = None
    """Human-readable longform. Free text."""
    last_transition_time: Optional[datetime] = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )


__all__ = [
    "Condition",
    "ConditionType",
    "ConditionStatus",
]
