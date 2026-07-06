import os
import sys
import logging

import pytest


def pytest_configure():
    sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
    sys.path.append(os.path.dirname(__file__))
    logging.basicConfig(level=logging.DEBUG)
    print("Unit test started!")


# ---------------------------------------------------------------------------
# requires_db auto-skip
#
# Tests marked ``requires_db`` run only when a MySQL that accepts the
# configured credentials is actually reachable. Without this, the
# default `pytest` run was red on any machine without the dev stack —
# and it was exactly the security tests failing, which trains people to
# ignore them. CI runs these for real against a MySQL service container.
# ---------------------------------------------------------------------------

_db_probe_result = None


def _db_available() -> bool:
    try:
        from sqlalchemy import create_engine, text

        from config import get_db_connection

        probe = create_engine(
            get_db_connection(),
            connect_args={"connect_timeout": 3},
        )
        try:
            with probe.connect() as conn:
                conn.execute(text("SELECT 1"))
            return True
        finally:
            probe.dispose()
    except Exception:
        return False


def pytest_collection_modifyitems(config, items):
    global _db_probe_result
    marked = [item for item in items if item.get_closest_marker("requires_db")]
    if not marked:
        return
    if _db_probe_result is None:
        _db_probe_result = _db_available()
    if _db_probe_result:
        return
    skip = pytest.mark.skip(
        reason="requires_db: no MySQL reachable with the configured credentials"
    )
    for item in marked:
        item.add_marker(skip)
