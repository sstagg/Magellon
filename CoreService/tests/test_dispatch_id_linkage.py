"""Regression tests for the FK-safe dispatch task_id contract.

Plugin step events come back over the bus carrying ``task_id`` and
``job_id``, and the writer persists them to ``job_event``, which has
FK constraints on both:

    job_event.task_id REFERENCES image_job_task(oid)
    job_event.job_id  REFERENCES image_job(oid)

Historically two import paths each generated a fresh ``uuid.uuid4()`` for
the in-memory DTO that was *not* the persisted ``ImageJobTask.oid`` —
plugin events then failed FK on insert, and ``task_output_processor``
logged "ImageJobTask <id> not found — cannot advance state". These
tests pin the linkage so a future refactor can't reintroduce the gap.

Bypasses ``__init__`` and uses fake DB sessions so the linkage logic
runs in isolation from MrcImageService / file IO / real DB.
"""
from __future__ import annotations

import os
import uuid
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from models.pydantic_models import LeginonFrameTransferJobDto
from models.sqlalchemy_models import Image, ImageJobTask
from services.importers.MagellonImporter import MagellonImporter
from services.leginon_frame_transfer_job_service import LeginonFrameTransferJobService


class _FakeQuery:
    """``db_session.query(X).filter(...).first()`` always returns None."""

    def filter(self, *_a, **_kw):
        return self

    def first(self):
        return None


class _FakeSession:
    """Captures ``add()`` calls; all queries return no match."""

    def __init__(self):
        self.added: list = []

    def query(self, _model):
        return _FakeQuery()

    def add(self, obj):
        self.added.append(obj)

    def flush(self):
        pass


def _image_data(name: str = "img_a") -> dict:
    return {
        "name": name,
        "frame_name": None,
        "path": f"home/original/{name}.mrc",
        "magnification": 50000,
        "dose": 30.0,
        "defocus": 1.5e-6,
        "pixel_size": 1.0e-10,
        "dimension_x": 4096,
        "dimension_y": 4096,
        "binning_x": 1,
        "binning_y": 1,
        "exposure_time": 1.0,
        "stage_x": 0.0,
        "stage_y": 0.0,
        "atlas_delta_row": None,
        "atlas_delta_column": None,
        "atlas_dimxy": None,
        "acceleration_voltage": 300,
        "spherical_aberration": 2.7,
        "stage_alpha_tilt": 0.0,
    }


class TestMagellonImporterDispatchIdLinkage:
    """``ImportTaskDto.task_id`` must match the persisted ``ImageJobTask.oid``."""

    def _make_importer(self) -> MagellonImporter:
        # Bypass __init__ — it instantiates MrcImageService which has
        # heavy non-test deps. We only exercise process_images here.
        importer = MagellonImporter.__new__(MagellonImporter)
        importer.db_msession = SimpleNamespace(oid=uuid.uuid4())
        importer.db_job = SimpleNamespace(oid=uuid.uuid4())
        importer.params = SimpleNamespace(source_dir="/fake/source")
        importer.task_dto_list = []
        return importer

    def test_process_images_returns_persisted_task_oid(self):
        importer = self._make_importer()
        db = _FakeSession()

        with patch("services.importers.MagellonImporter.os.path.exists", return_value=True):
            results = importer.process_images(db, [_image_data("img_a"), _image_data("img_b")])

        assert len(results) == 2
        added_tasks = [obj for obj in db.added if isinstance(obj, ImageJobTask)]
        assert len(added_tasks) == 2

        # For each tuple, the returned task_oid must equal the oid of
        # the corresponding persisted ImageJobTask row, AND that row's
        # image_id must match the image in the tuple.
        for (image, _file_path, task_oid), task_row in zip(results, added_tasks):
            assert task_oid == task_row.oid
            assert task_row.image_id == image.oid
            assert task_row.job_id == importer.db_job.oid

    def test_process_images_returns_unique_task_oids_per_image(self):
        # Distinct images must get distinct task oids — protects against
        # a copy-paste regression where one shared oid leaks across rows.
        importer = self._make_importer()
        db = _FakeSession()
        with patch("services.importers.MagellonImporter.os.path.exists", return_value=True):
            results = importer.process_images(db, [_image_data("img_a"), _image_data("img_b")])

        oids = {r[2] for r in results}
        assert len(oids) == 2

    def test_process_images_skips_missing_files(self):
        # When the source MRC is missing, no ImageJobTask is created and
        # the image isn't included in the dispatch tuple list — so the
        # tuple unpacking in process() never sees a missing task_oid.
        importer = self._make_importer()
        db = _FakeSession()
        with patch("services.importers.MagellonImporter.os.path.exists", return_value=False):
            results = importer.process_images(db, [_image_data("img_a")])

        assert results == []
        assert not any(isinstance(o, ImageJobTask) for o in db.added)


class TestLeginonFrameTransferDispatchIdLinkage:
    """``LeginonFrameTransferTaskDto.task_id`` must equal the persisted
    ``ImageJobTask.oid``, and ``.job_id`` must be the actual ``ImageJob.oid``."""

    def _make_service(self) -> LeginonFrameTransferJobService:
        svc = LeginonFrameTransferJobService.__new__(LeginonFrameTransferJobService)
        # The DTO under test references self.params (validated as a real
        # LeginonFrameTransferJobDto), so we build one rather than a stub.
        svc.params = LeginonFrameTransferJobDto(
            magellon_project_name="proj",
            magellon_session_name="23oct13a",
            camera_directory="/fake/camera",
            task_list=[],
            leginon_mysql_port=3306,
        )
        return svc

    def _leginon_image(self, image_id: int = 1) -> dict:
        return {
            "image_id": image_id,
            "filename": f"23oct13a_{image_id:05d}",
            "image_name": f"23oct13a_{image_id:05d}.mrc",
            "frame_names": None,
            "mag": 50000,
            "defocus": 1.5e-6,
            "calculated_dose": 30.0,
            "pixelsize": 1.0e-10,
            "bining_x": 1,
            "bining_y": 1,
            "stage_x": 0.0,
            "stage_y": 0.0,
            "stage_alpha_tilt": 0.0,
            "dimx": 4096,
            "delta_row": 0.0,
            "delta_column": 0.0,
            "acceleration_voltage": 300,
            "spherical_aberration": 2.7e-3,
        }

    def test_build_image_records_links_task_id_and_job_id(self):
        svc = self._make_service()
        job = SimpleNamespace(oid=uuid.uuid4())
        magellon_session = SimpleNamespace(oid=uuid.uuid4())
        session_result = {"name": "23oct13a"}

        leginon_image_list = [self._leginon_image(1), self._leginon_image(2)]
        _, db_job_item_list, _ = svc._build_image_records(
            leginon_image_list,
            session_result,
            presets_pattern=None,
            job=job,
            magellon_session=magellon_session,
        )

        # Two images → two persisted task rows + two DTOs in params.task_list.
        assert len(db_job_item_list) == 2
        assert len(svc.params.task_list) == 2

        for db_task, task_dto in zip(db_job_item_list, svc.params.task_list):
            # The bug: task_dto.task_id was uuid.uuid4() — orphan to the DB.
            assert task_dto.task_id == db_task.oid, (
                "DTO task_id must equal persisted ImageJobTask.oid — otherwise "
                "plugin step events fail FK on job_event.task_id"
            )
            # The other bug: task_dto.job_id was set to db_task.oid (the
            # *task* oid). Real job_event.job_id FK targets ImageJob.oid.
            assert task_dto.job_id == job.oid
            assert task_dto.job_id != db_task.oid

    def test_build_image_records_unique_task_oids(self):
        svc = self._make_service()
        job = SimpleNamespace(oid=uuid.uuid4())
        magellon_session = SimpleNamespace(oid=uuid.uuid4())
        leginon_image_list = [self._leginon_image(1), self._leginon_image(2)]

        _, db_job_item_list, _ = svc._build_image_records(
            leginon_image_list,
            {"name": "23oct13a"},
            presets_pattern=None,
            job=job,
            magellon_session=magellon_session,
        )
        oids = {t.oid for t in db_job_item_list}
        dto_ids = {d.task_id for d in svc.params.task_list}
        assert len(oids) == 2
        assert oids == dto_ids
