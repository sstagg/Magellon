"""One session name, one import.

Importers used to look a session up by name and reuse it, so importing a
name that already existed added a second copy of its images to the existing
session and its home folder — and stopping or deleting that second import
would have destroyed the original. Every import now gets a name nobody else
uses: not an existing session, and not another queued or running import.

Checked when an import is submitted (so the user hears at once) and again
when a worker starts it (two submissions in the same instant).
"""
from typing import Optional

from database import session_local
from models.sqlalchemy_models import ImportJobQueue, Msession, SysSecUser


class SessionNameTaken(Exception):
    """The requested session name is already used; the message says by what."""


def problem(name: Optional[str], job_id: Optional[str] = None, check_queue: bool = True) -> Optional[str]:
    """Why ``name`` can't be used for a new import (None = it's free).

    ``job_id`` is the import asking, so its own queue row doesn't count;
    ``check_queue=False`` looks only at existing sessions.
    """
    name = (name or "").strip()
    if not name:
        return "A session name is required."
    db = session_local()
    try:
        session = (db.query(Msession).filter(Msession.name == name, Msession.GCRecord.is_(None)).first())
        if session is not None:
            owner = None
            if session.user_id:
                owner = db.query(SysSecUser.USERNAME).filter(SysSecUser.oid == session.user_id).scalar()
            return (f"Session '{name}' already exists" + (f" (owner {owner})" if owner else "")
                    + ". Choose another session name, or delete the existing session first.")
        if not check_queue:
            return None
        query = db.query(ImportJobQueue).filter(
            ImportJobQueue.label == name, ImportJobQueue.status.in_(("queued", "running", "stopping")))
        if job_id:
            query = query.filter(ImportJobQueue.id != str(job_id))
        other = query.order_by(ImportJobQueue.created_at).first()
        if other is not None:
            return (f"Another import named '{name}' is already {other.status}. "
                    "Choose another session name.")
        return None
    finally:
        db.close()


def require_free(name: Optional[str], job_id: Optional[str] = None) -> None:
    reason = problem(name, job_id)
    if reason:
        raise SessionNameTaken(reason)


def first_claim(name: str, job_id: str) -> bool:
    """Whether ``job_id`` is the earliest active import using ``name`` (it
    wins a tie between two submissions made at the same moment)."""
    db = session_local()
    try:
        first = (db.query(ImportJobQueue.id)
                 .filter(ImportJobQueue.label == name, ImportJobQueue.status.in_(("queued", "running", "stopping")))
                 .order_by(ImportJobQueue.created_at).first())
        return first is None or first[0] == str(job_id)
    finally:
        db.close()
