"""Real-time permission updates.

Permission checks read Casbin's in-memory policy, which used to be built only
at startup (``CasbinPolicySyncService.sync_all_policies``): a role assigned or
a permission changed in User Management did nothing until a restart.

Now every commit that touches a security table is followed by a reconcile:

1. compute the policy the database describes — the same mapping the startup
   sync uses (action, navigation, type and object permissions per role, plus
   user → role links, skipping soft-deleted roles);
2. diff it against the live enforcer;
3. apply only the difference (add the missing rules, remove the stale ones).
   Casbin's auto-save writes each change through to ``casbin_rule``.

The users whose effective permissions moved are then pushed a
``permissions_changed`` socket event, so their browser re-reads ``/auth/me``
and the menu updates without a reload.

Change capture uses SQLAlchemy session events instead of hooks in every
endpoint, so no write path (UI, script, repository) can be missed. Bulk
``query.delete()``/``update()`` don't report rows, so they mark the policy
dirty as a whole; the diff still applies only real differences.

Scope: one backend process holds one enforcer. If CoreService ever runs
several workers, each needs the same delta — add a Casbin watcher over the
message bus (RabbitMQ/NATS) that triggers ``reconcile`` in every process.
"""
import logging
import threading
from typing import Iterable, Set, Tuple

from sqlalchemy import event
from sqlalchemy.orm import Session

from models.sqlalchemy_models import (
    SysSecActionPermission,
    SysSecNavigationPermission,
    SysSecObjectPermission,
    SysSecRole,
    SysSecTypePermission,
    SysSecUserRole,
)

logger = logging.getLogger(__name__)

SECURITY_MODELS = (
    SysSecUserRole,
    SysSecRole,
    SysSecTypePermission,
    SysSecActionPermission,
    SysSecNavigationPermission,
    SysSecObjectPermission,
)

_FLAG = "magellon_security_changed"
_lock = threading.Lock()

Policy = Tuple[str, str, str, str]   # (subject, resource, action, effect)
Grouping = Tuple[str, str]           # (user id, role name)

_TYPE_ACTIONS = (
    ("ReadState", "read"),
    ("WriteState", "write"),
    ("CreateState", "create"),
    ("DeleteState", "delete"),
    ("NavigateState", "navigate"),
)
# Object permissions carry no create: you can't create an existing instance.
_OBJECT_ACTIONS = tuple(a for a in _TYPE_ACTIONS if a[1] != "create")


def _live(role) -> bool:
    return role is not None and role.GCRecord is None


def desired_policy(db: Session) -> Tuple[Set[Policy], Set[Grouping]]:
    """The full policy the security tables describe (mirrors the startup sync)."""
    from services.security.criteria_parser_service import CriteriaParserService

    policies: Set[Policy] = set()
    groupings: Set[Grouping] = set()

    for ur in db.query(SysSecUserRole).all():
        if _live(ur.sys_sec_role):
            groupings.add((str(ur.People), ur.sys_sec_role.Name))

    for perm in db.query(SysSecActionPermission).filter(SysSecActionPermission.GCRecord.is_(None)):
        if _live(perm.sys_sec_role):
            policies.add((perm.sys_sec_role.Name, f"action:{perm.ActionId}", "execute", "allow"))

    for perm in db.query(SysSecNavigationPermission).filter(SysSecNavigationPermission.GCRecord.is_(None)):
        if _live(perm.sys_sec_role):
            effect = "allow" if perm.NavigateState == 1 else "deny"
            policies.add((perm.sys_sec_role.Name, f"navigation:{perm.ItemPath}", "navigate", effect))

    for perm in db.query(SysSecTypePermission).filter(SysSecTypePermission.GCRecord.is_(None)):
        if _live(perm.sys_sec_role):
            for state, action in _TYPE_ACTIONS:
                if getattr(perm, state) == 1:
                    policies.add((perm.sys_sec_role.Name, f"{perm.TargetType}:*", action, "allow"))

    for perm in db.query(SysSecObjectPermission).filter(SysSecObjectPermission.GCRecord.is_(None)):
        type_perm = perm.sys_sec_type_permission
        if not type_perm or not _live(type_perm.sys_sec_role):
            continue
        parsed = CriteriaParserService.parse_and_categorize(perm.Criteria or "", type_perm.TargetType)
        if not parsed["can_sync_to_casbin"]:
            continue  # dynamic criteria are filtered in the application layer
        for resource in parsed["resources"]:
            for state, action in _OBJECT_ACTIONS:
                if getattr(perm, state) == 1:
                    policies.add((type_perm.sys_sec_role.Name, resource, action, "allow"))

    return policies, groupings


def reconcile() -> Set[str]:
    """Bring the live enforcer in line with the database; return affected user ids."""
    from database import session_local
    from services.casbin_service import CasbinService

    with _lock:
        db = session_local()
        try:
            want_p, want_g = desired_policy(db)
        finally:
            db.close()

        enforcer = CasbinService.get_enforcer()
        have_p = {tuple((list(p) + ["allow"])[:4]) for p in enforcer.get_policy()}
        have_g = {tuple(g[:2]) for g in enforcer.get_grouping_policy()}

        add_p, del_p = want_p - have_p, have_p - want_p
        add_g, del_g = want_g - have_g, have_g - want_g
        for rule in del_p:
            enforcer.remove_policy(*rule)
        for rule in add_p:
            enforcer.add_policy(*rule)
        for link in del_g:
            enforcer.remove_grouping_policy(*link)
        for link in add_g:
            enforcer.add_grouping_policy(*link)
        if add_p or del_p or add_g or del_g:
            # CasbinService caches answers and indexes rules; edits made on
            # the enforcer directly must drop both, as its own methods do.
            CasbinService._invalidate_authorization_cache()

        changed_roles = {rule[0] for rule in add_p | del_p}
        affected = {user for user, _ in add_g | del_g}
        affected |= {user for user, role in want_g | have_g if role in changed_roles}

    if add_p or del_p or add_g or del_g:
        logger.info(
            "Permissions updated live: +%d/-%d rules, +%d/-%d role links, %d user(s) notified",
            len(add_p), len(del_p), len(add_g), len(del_g), len(affected),
        )
    return affected


def _notify(user_ids: Iterable[str]) -> None:
    if not user_ids:
        return
    try:
        from core.socketio_server import schedule_permissions_changed
        schedule_permissions_changed(user_ids)
    except Exception:
        logger.debug("permissions_changed notify failed", exc_info=True)


# ---------------------------------------------------------------------------
# Change capture
# ---------------------------------------------------------------------------

@event.listens_for(Session, "after_flush")
def _capture_flush(session, flush_context):
    for obj in (*session.new, *session.dirty, *session.deleted):
        if isinstance(obj, SECURITY_MODELS):
            session.info[_FLAG] = True
            return


@event.listens_for(Session, "do_orm_execute")
def _capture_bulk(execute_state):
    if execute_state.is_update or execute_state.is_delete:
        mapper = execute_state.bind_mapper
        if mapper is not None and issubclass(mapper.class_, SECURITY_MODELS):
            execute_state.session.info[_FLAG] = True


@event.listens_for(Session, "after_commit")
def _apply_after_commit(session):
    if not session.info.pop(_FLAG, False):
        return
    try:
        _notify(reconcile())
    except Exception:
        # Never fail the caller's request: the database change is committed,
        # and the next change (or a restart) reconciles again.
        logger.exception("Live permission update failed; it will be retried on the next change")


@event.listens_for(Session, "after_rollback")
def _discard_on_rollback(session):
    session.info.pop(_FLAG, None)
