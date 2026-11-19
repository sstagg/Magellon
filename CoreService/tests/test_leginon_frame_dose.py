"""MotionCor's -FmDose for a Leginon movie is its total dose over its frames."""
from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import patch

import pytest

from services import leginon_frame_transfer_job_service as service
from services.leginon_frame_transfer_job_service import LeginonFrameTransferJobService, frame_dose


@pytest.mark.parametrize("dose, frames, expected", [
    (59.96468672612987, 46, 1.3036),   # 26nov02a
    (60.26107013213771, 75, 0.8035),   # 24dec03a
    (40, "50", 0.8),
])
def test_dose_per_frame_is_total_dose_over_frames(dose, frames, expected):
    assert frame_dose(dose, frames) == expected


@pytest.mark.parametrize("dose, frames", [(None, 46), (60, None), (0, 46), (60, 0), ("x", 46)])
def test_missing_or_bad_values_give_none(dose, frames):
    assert frame_dose(dose, frames) is None


def _service(typed_dose=None):
    svc = LeginonFrameTransferJobService.__new__(LeginonFrameTransferJobService)
    svc.gains_path, svc.defects_path, svc._warned_dose = "/gain.mrc", None, False
    svc.params = SimpleNamespace(camera_directory="/frames", frames_directory="/frames", total_dose=typed_dose)
    return svc


def _task(**extra):
    values = dict(task_id="t", file_name="movie", frame_name="movie.tif", frame_path="/frames/movie.tif",
                  image_path="/images/movie.mrc", acceleration_voltage=200.0,
                  job_dto=SimpleNamespace(session_name="s"))
    values.update(extra)
    return SimpleNamespace(**values)


def _sent_settings(task, typed_dose=None):
    with patch.object(service, "find_matching_file", return_value="/frames/movie.tif"), \
            patch.object(service, "dispatch_motioncor_task", return_value=True) as dispatch:
        result = _service(typed_dose).compute_motioncor_task(task.image_path, task)
    assert "on the way" in result["message"]
    return dispatch.call_args.kwargs["motioncor_settings"]


def test_motioncor_gets_the_movies_dose_per_frame_and_voltage():
    settings = _sent_settings(_task(total_dose=59.96468672612987, frame_count=46))
    assert settings["FmDose"] == 1.3036
    assert settings["kV"] == 200


def test_without_a_dose_there_is_no_dose_weighting():
    # None, not left out: it overrides the dispatcher's own default dose.
    settings = _sent_settings(_task(total_dose=None, frame_count=46))
    assert "FmDose" in settings and settings["FmDose"] is None


def test_a_typed_total_dose_is_used_over_frames():
    settings = _sent_settings(_task(total_dose=None, frame_count=46), typed_dose=46)
    assert settings["FmDose"] == 1.0


def test_a_typed_total_dose_wins_over_leginons():
    settings = _sent_settings(_task(total_dose=59.96, frame_count=46), typed_dose=92)
    assert settings["FmDose"] == 2.0
