"""Kubernetes-style ``Conditions[]`` reducer for plugin status (PM2).

Joins five collaborators to compute orthogonal status axes:

  R1  PluginRegistry           — in-process plugin discovery
  R2  PluginRepository         — installed plugin catalog (PM1)
  R3  PluginStateRepository    — operator enabled flag (PM1)
  R4  PluginCategoryDefault…   — per-category default routing (PM1)
  R5  PluginLivenessRegistry   — bus-driven announce + heartbeat
  --
  job_event.ts                 — recent task outcomes for Healthy

Reviewer-flagged High #4 from the plan revision: pre-fix the
Healthy reducer claimed an ``image_job_task.ended_on`` index that
doesn't exist. The right source is ``job_event.ts`` (table created
in alembic 0002, with ``task_id`` indexed). We join
``job_event`` ← ``image_job_task`` (FK) ← ``Plugin`` (by name) and
look at the most recent terminal events (``event_type IN
('completed', 'failed')``) within the last N minutes.

The reducer is read-only: it never writes. Cheap to call per
``GET /plugins/{id}/status``; the dispatch hot path doesn't go
through here.
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import List, Optional

from sqlalchemy.orm import Session

from magellon_sdk.models.conditions import (
    Condition,
    ConditionStatus,
    ConditionType,
)
from models.sqlalchemy_models import (
    ImageJobTask,
    JobEvent,
    Plugin,
    PluginCategoryDefault,
    PluginState,
)

logger = logging.getLogger(__name__)


# How far back to look for recent task outcomes. 30 minutes is a
# compromise: long enough to catch a fast plugin's bursts, short
# enough that a once-per-week occasional run doesn't keep marking
# the plugin as Healthy.
_HEALTHY_LOOKBACK = timedelta(minutes=30)

# Heartbeat staleness window. Mirrors PluginLivenessRegistry's
# default of 60 s (4× the SDK default heartbeat interval of 15 s).
_LIVE_STALE_AFTER = timedelta(seconds=60)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _condition(
    type_: ConditionType,
    status: bool,
    *,
    reason: Optional[str] = None,
    message: Optional[str] = None,
    last_transition_time: Optional[datetime] = None,
) -> Condition:
    return Condition(
        type=type_,
        status=ConditionStatus.TRUE if status else ConditionStatus.FALSE,
        reason=reason,
        message=message,
        last_transition_time=last_transition_time or _utcnow(),
    )


def _is_live(last_heartbeat_at: Optional[datetime]) -> bool:
    if last_heartbeat_at is None:
        return False
    last = last_heartbeat_at
    if last.tzinfo is None:
        last = last.replace(tzinfo=timezone.utc)
    return (_utcnow() - last) <= _LIVE_STALE_AFTER


def _has_recent_success(
    db: Session, plugin_oid, *, lookback: timedelta = _HEALTHY_LOOKBACK
) -> Optional[bool]:
    """Healthy heuristic. Returns:

      * True  — at least one ``completed`` event in window
      * False — terminal events exist in window AND every one was ``failed``
      * None  — no terminal events in window (== "no recent task";
        treated as Healthy=Unknown by the caller)

    Why ``Unknown`` for "no events": a plugin can be Live and Enabled
    but simply not have run any tasks recently — that's not unhealthy.
    Marking it Healthy=False would surface false alarms.
    """
    cutoff = _utcnow() - lookback
    # Naive datetime for MySQL compat. job_event.ts is naive.
    cutoff_naive = cutoff.replace(tzinfo=None)

    rows = (
        db.query(JobEvent.event_type)
        .join(ImageJobTask, JobEvent.task_id == ImageJobTask.oid)
        .filter(ImageJobTask.plugin_id != None)  # noqa: E711
        .filter(
            (ImageJobTask.plugin_id == _plugin_id_string(plugin_oid))
            | _identity_match_clauses(db, plugin_oid)
        )
        .filter(JobEvent.event_type.in_(["completed", "failed"]))
        .filter(JobEvent.ts >= cutoff_naive)
        .all()
    )
    if not rows:
        return None
    types = [r[0] for r in rows]
    if any(t == "completed" for t in types):
        return True
    return False


def _plugin_id_string(plugin_oid) -> str:
    """ImageJobTask.plugin_id is a STRING (matching PluginInfo.name);
    accept both UUID and string callers for symmetry."""
    return str(plugin_oid)


def _identity_match_clauses(db: Session, plugin_oid):
    """Match the legacy plugin_id-string column against either
    Plugin.name or Plugin.manifest_plugin_id. Returns a SQLAlchemy
    expression usable in a filter."""
    plugin = db.query(Plugin).filter(Plugin.oid == plugin_oid).first()
    if plugin is None:
        # Empty clause that still composes — equivalent to FALSE.
        return ImageJobTask.plugin_id == "__no_match__"
    candidates = [plugin.name]
    if plugin.manifest_plugin_id:
        candidates.append(plugin.manifest_plugin_id)
    return ImageJobTask.plugin_id.in_(candidates)


def compute_conditions(
    db: Session,
    *,
    plugin_oid=None,
    plugin_name: Optional[str] = None,
    is_live: Optional[bool] = None,
    last_heartbeat_at: Optional[datetime] = None,
) -> List[Condition]:
    """Compute the full ``Conditions[]`` list for one plugin.

    Caller may pass ``plugin_oid`` (preferred — DB FK) or
    ``plugin_name`` (the runtime ``plugin_id`` string the controller
    has pre-PM3 facade landing). ``is_live`` / ``last_heartbeat_at``
    let the caller inject liveness data the reducer can't derive
    from the DB alone (the registry is in-memory).
    """
    plugin: Optional[Plugin] = None
    if plugin_oid is not None:
        plugin = db.query(Plugin).filter(Plugin.oid == plugin_oid).first()
    elif plugin_name is not None:
        plugin = (
            db.query(Plugin)
            .filter(Plugin.deleted_date.is_(None))
            .filter(
                (Plugin.manifest_plugin_id == plugin_name)
                | (Plugin.name == plugin_name)
            )
            .first()
        )

    out: List[Condition] = []

    # Installed.
    out.append(
        _condition(
            ConditionType.INSTALLED,
            plugin is not None,
            reason="Catalogued" if plugin is not None else "Uncatalogued",
            message=(
                None
                if plugin is not None
                else "No plugin row found by manifest_plugin_id or name"
            ),
        )
    )

    # Enabled — PluginState.enabled, default True for missing.
    enabled = True
    enabled_reason = "DefaultTrue"
    if plugin is not None:
        state = (
            db.query(PluginState)
            .filter(PluginState.plugin_oid == plugin.oid)
            .first()
        )
        if state is not None:
            enabled = bool(state.enabled)
            enabled_reason = "Operator" if not enabled else "OperatorEnabled"
    out.append(
        _condition(
            ConditionType.ENABLED,
            enabled,
            reason=enabled_reason,
        )
    )

    # Live — caller supplies (registry data is in-memory).
    live_status = bool(is_live) if is_live is not None else _is_live(last_heartbeat_at)
    out.append(
        _condition(
            ConditionType.LIVE,
            live_status,
            reason="Heartbeat" if live_status else "NoHeartbeat",
            message=(
                None if live_status else "No heartbeat within stale window"
            ),
        )
    )

    # Healthy — only if Live and Installed; otherwise Unknown is
    # truthful but UNKNOWN isn't a TRUE/FALSE so we encode as
    # status=False with reason='Unknown'. Callers wanting strict
    # tri-state can read ``reason``.
    if plugin is None or not live_status:
        out.append(
            Condition(
                type=ConditionType.HEALTHY,
                status=ConditionStatus.UNKNOWN,
                reason="NotLive" if plugin is not None else "Uncatalogued",
                last_transition_time=_utcnow(),
            )
        )
    else:
        recent = _has_recent_success(db, plugin.oid)
        if recent is None:
            out.append(
                Condition(
                    type=ConditionType.HEALTHY,
                    status=ConditionStatus.UNKNOWN,
                    reason="NoRecentTasks",
                    message=f"No completed/failed events in last {_HEALTHY_LOOKBACK}",
                    last_transition_time=_utcnow(),
                )
            )
        else:
            out.append(
                _condition(
                    ConditionType.HEALTHY,
                    recent,
                    reason="RecentSuccess" if recent else "RecentFailures",
                )
            )

    # Default — match plugin.oid against any plugin_category_default row.
    is_default = False
    default_categories: List[str] = []
    if plugin is not None:
        rows = (
            db.query(PluginCategoryDefault)
            .filter(PluginCategoryDefault.plugin_oid == plugin.oid)
            .all()
        )
        if rows:
            is_default = True
            default_categories = [r.category for r in rows]
    out.append(
        _condition(
            ConditionType.DEFAULT,
            is_default,
            reason="OperatorPinned" if is_default else "NotDefault",
            message=(
                f"Default for: {', '.join(default_categories)}"
                if default_categories
                else None
            ),
        )
    )

    return out


__all__ = ["compute_conditions"]
