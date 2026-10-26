"""Session ownership: the user who imports a session owns it.

Importers create ``Msession`` rows deep inside their own code and never see
the requesting user, so ownership is stamped here instead of threading a
``user_id`` through every importer:

* each background import runner calls ``set_import_owner(user_id)`` first;
* a ``before_insert`` hook fills ``Msession.user_id`` from that value for any
  session created while the import runs (an explicit ``user_id`` wins);
* ``is_session_owner`` lets the access checks admit owners without needing a
  per-session Casbin grant.

Background tasks run in a copied context, so the value set by one import is
never visible to another request or import.
"""
import contextvars
import logging
from typing import Optional, Set
from uuid import UUID

from sqlalchemy import event

from models.sqlalchemy_models import Msession

logger = logging.getLogger(__name__)

_import_owner: contextvars.ContextVar[Optional[UUID]] = contextvars.ContextVar(
    "magellon_import_owner", default=None
)


def set_import_owner(user_id: Optional[UUID]) -> None:
    """Mark the current import as running on behalf of ``user_id``."""
    _import_owner.set(user_id)


@event.listens_for(Msession, "before_insert")
def _stamp_session_owner(mapper, connection, target: Msession) -> None:
    if target.user_id is None:
        owner = _import_owner.get()
        if owner is not None:
            target.user_id = owner
            logger.info("Session %r owned by user %s", target.name, owner)


def is_session_owner(user_id: UUID, session_id: UUID) -> bool:
    """True if ``user_id`` imported (owns) the session."""
    from database import session_local

    db = session_local()
    try:
        return db.query(Msession.oid).filter(
            Msession.oid == session_id,
            Msession.user_id == user_id,
            Msession.GCRecord.is_(None),
        ).first() is not None
    finally:
        db.close()


def owned_session_ids(user_id: UUID) -> Set[str]:
    """IDs (as strings) of every session ``user_id`` owns."""
    from database import session_local

    db = session_local()
    try:
        rows = db.query(Msession.oid).filter(
            Msession.user_id == user_id,
            Msession.GCRecord.is_(None),
        ).all()
        return {str(oid) for (oid,) in rows}
    finally:
        db.close()
