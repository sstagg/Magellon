"""Idempotent persistence of plugin lifecycle events into ``job_event``.

The same logical event can arrive on two channels (NATS and RMQ),
from two consumers, or on retry. Dedup is keyed on CloudEvents
``id`` (column ``event_id``, UNIQUE). The writer uses the MySQL
``INSERT ... ON DUPLICATE KEY UPDATE oid = oid`` idiom so the second
insert is a no-op rather than an IntegrityError.

Progress events (``magellon.step.progress``) are *not* persisted —
they're live-only. Only the four lifecycle types pass through to the
DB.
"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Optional
from uuid import UUID

from sqlalchemy.dialects.mysql import insert as mysql_insert
from sqlalchemy.orm import Session

from magellon_sdk.envelope import Envelope
from magellon_sdk.events import STEP_EVENT_TYPES, STEP_PROGRESS

from models.sqlalchemy_models import JobEvent

logger = logging.getLogger(__name__)


# Event types we persist — lifecycle only. Progress is live-only.
PERSISTED_EVENT_TYPES = STEP_EVENT_TYPES - {STEP_PROGRESS}


class JobEventWriter:
    """Persist a :class:`magellon_sdk.envelope.Envelope` as a ``JobEvent`` row.

    Stateless apart from the DB session — safe to construct per event
    or share across a consumer. The writer never raises on duplicate
    event_id; it logs at ``debug`` and returns ``False`` so callers
    can distinguish "wrote a new row" from "duplicate, no-op".
    """

    def __init__(self, db: Session) -> None:
        self.db = db

    def write(self, envelope: Envelope[Any]) -> bool:
        """Persist ``envelope`` if it is a lifecycle event and not a dup.

        Returns ``True`` if a new row was inserted, ``False`` if it was
        filtered (progress event or non-step-event) or deduped.
        """
        if envelope.type not in PERSISTED_EVENT_TYPES:
            logger.debug("JobEventWriter: skipping non-persisted type %s", envelope.type)
            return False

        data = envelope.data if isinstance(envelope.data, dict) else {}
        job_id = _as_uuid(data.get("job_id"))
        if job_id is None:
            logger.warning("JobEventWriter: envelope %s missing job_id — dropping", envelope.id)
            return False

        task_id = _as_uuid(data.get("task_id"))
        step = data.get("step") or ""
        ts = envelope.time or datetime.now(timezone.utc)

        row = {
            "oid": uuid.uuid4(),
            "event_id": envelope.id,
            "job_id": job_id,
            "task_id": task_id,
            "event_type": envelope.type,
            "step": step,
            "source": envelope.source,
            "ts": ts,
            "data_json": data,
            "created_date": datetime.now(timezone.utc),
        }

        stmt = mysql_insert(JobEvent).values(**row)
        # ON DUPLICATE KEY UPDATE oid=oid is the MySQL idiom for
        # "insert if new, silently ignore if dup". We set a trivial
        # assignment because DO NOTHING is Postgres-only.
        stmt = stmt.on_duplicate_key_update(oid=JobEvent.oid)

        result = self.db.execute(stmt)
        self.db.commit()

        # rowcount: 1 = inserted, 0 = dup (no-op), 2 = updated (not our case)
        inserted = result.rowcount == 1
        if inserted:
            logger.info("JobEvent persisted: type=%s step=%s event_id=%s", envelope.type, step, envelope.id)
        else:
            logger.debug("JobEvent dup: event_id=%s already recorded", envelope.id)
        return inserted


def _as_uuid(value: Any) -> Optional[UUID]:
    if value is None:
        return None
    if isinstance(value, UUID):
        return value
    try:
        return UUID(str(value))
    except (ValueError, AttributeError):
        return None


__all__ = ["JobEventWriter", "PERSISTED_EVENT_TYPES"]
