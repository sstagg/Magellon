"""
Shared CRUD scaffolding for the security controllers.

The sys_sec_* controllers historically copy-pasted the same plumbing into
every route: the get-by-id-or-404 check, the ``try/except`` envelope that
logs and converts any failure into a 500, and the "repository returned
False -> 500" success check. These helpers centralize that scaffolding so
each route body only contains route-specific logic.

Behavioral notes (deliberately preserved from the original inline code):

- The original ``except Exception`` blocks also caught ``HTTPException``,
  so e.g. a 404 raised *inside* one of those try blocks came back to the
  client as the route's generic 500. ``crud_guard`` reproduces that by
  default. Routes that historically had an explicit
  ``except HTTPException: raise`` passthrough must pass
  ``reraise_http=True``.
- A handful of routes exposed ``str(exc)`` in the 500 detail
  (``detail=f'Error ...: {e}'``); those pass ``append_error=True``.
"""
from contextlib import contextmanager
from typing import Optional
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy.orm import Session
from starlette import status

from repositories.security.sys_sec_role_repository import SysSecRoleRepository
from repositories.security.sys_sec_user_repository import SysSecUserRepository


def found_or_404(entity, detail: str):
    """Return the fetched entity, or raise 404 with the given detail."""
    if not entity:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=detail
        )
    return entity


def get_user_or_404(db: Session, user_id: UUID):
    """Fetch a user by id or raise the standard 404."""
    return found_or_404(SysSecUserRepository.fetch_by_id(db, user_id), "User not found")


def get_role_or_404(db: Session, role_id: UUID):
    """Fetch a role by id or raise the standard 404."""
    return found_or_404(SysSecRoleRepository.fetch_by_id(db, role_id), "Role not found")


def ensure_success(success, detail: str) -> None:
    """Repositories signal failure by returning a falsy value; the routes
    turn that into a 500 with a route-specific detail message."""
    if not success:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=detail
        )


@contextmanager
def crud_guard(
        logger,
        log_message: str,
        detail: Optional[str] = None,
        *,
        reraise_http: bool = False,
        append_error: bool = False,
):
    """Reproduce the controllers' historical try/except envelope.

    Logs the exception with the module's own logger (so log records keep
    their original logger name) and raises a 500 with ``detail``
    (defaulting to ``log_message``). See module docstring for the
    ``reraise_http`` / ``append_error`` semantics.
    """
    try:
        yield
    except HTTPException as e:
        if reraise_http:
            raise
        logger.exception(log_message)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=_detail(detail or log_message, e, append_error)
        )
    except Exception as e:
        logger.exception(log_message)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=_detail(detail or log_message, e, append_error)
        )


def _detail(detail: str, exc: Exception, append_error: bool) -> str:
    return f"{detail}: {str(exc)}" if append_error else detail
