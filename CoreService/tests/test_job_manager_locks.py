"""Job updates lock the row, so a task's result arriving at the same moment
isn't overwritten and lost (which leaves the job running forever)."""
from __future__ import annotations

from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest

from services import job_manager as jm


class _Stop(Exception):
    pass


@pytest.mark.parametrize("call", [
    lambda m, j: m.mark_running(j),
    lambda m, j: m.update_progress(j, progress=5),
    lambda m, j: m.complete_job(j, result={}),
    lambda m, j: m.fail_job(j, error="x"),
    lambda m, j: m.cancel_job(j),
])
def test_writers_take_the_job_lock(call):
    manager = jm.job_manager
    with patch.object(jm, "session_local", MagicMock()), \
            patch.object(type(manager), "_get_or_404", side_effect=_Stop) as get:
        with pytest.raises(_Stop):
            call(manager, str(uuid4()))
    assert get.call_args.kwargs.get("lock") is True
