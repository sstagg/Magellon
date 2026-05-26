from __future__ import annotations

import uuid
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from models.pydantic_models import DefaultParams, EpuImportJobDto, SerialEMImportJobDto
from models.sqlalchemy_models import Atlas, Image, ImageJob, ImageJobTask, Msession, Project
from services.importers.BaseImporter import BaseImporter
from services.importers.EPUImporter import EPUMetadata, EPUImporter
from services.importers.ImporterFactory import import_data
from services.importers.import_database_service import ImportDatabaseService
from services.importers.SerialEmImporter import SerialEMMetadata, SerialEmImporter
from services.importers.source_strategies import MagellonSessionJsonStrategy


class _DummyImporter(BaseImporter):
    def process(self, db_session):
        return {"status": "success"}


class _NoResultQuery:
    def filter(self, *_args, **_kwargs):
        return self

    def first(self):
        return None


class _CaptureSession:
    def __init__(self):
        self.added = []
        self.commits = 0
        self.refreshed = []

    def query(self, _model):
        return _NoResultQuery()

    def add(self, obj):
        self.added.append(obj)

    def flush(self):
        pass

    def commit(self):
        self.commits += 1

    def refresh(self, obj):
        self.refreshed.append(obj)


def _epu_params(tmp_path):
    return EpuImportJobDto(
        magellon_project_name="proj",
        magellon_session_name="epu_session",
        session_name="epu_session",
        epu_dir_path=str(tmp_path),
        default_data=DefaultParams(),
    )


def _serialem_params(tmp_path):
    return SerialEMImportJobDto(
        magellon_project_name="proj",
        magellon_session_name="serialem_session",
        serial_em_dir_path=str(tmp_path),
        target_directory=str(tmp_path),
        default_data=DefaultParams(),
    )


def test_epu_record_builder_links_task_dto_to_persisted_task(tmp_path):
    image_base = tmp_path / "FoilHole_123_0001"
    xml_path = image_base.with_suffix(".xml")
    image_path = image_base.with_suffix(".tif")
    frame_path = tmp_path / "FoilHole_123_0001_0002.eer"
    image_path.write_bytes(b"image")
    frame_path.write_bytes(b"frames")

    importer = EPUImporter.__new__(EPUImporter)
    importer.params = _epu_params(tmp_path)
    metadata = EPUMetadata(
        file_path=str(xml_path),
        magnification=50000,
        defocus=1.5,
        dose=20.0,
        pixel_size=1e-10,
        binning_x=1,
        binning_y=1,
        acceleration_voltage=300000,
        spherical_aberration=2700,
    )

    images, job_tasks, task_dtos, parent_child = importer.create_image_and_task_records(
        _CaptureSession(),
        [metadata],
        uuid.uuid4(),
        uuid.uuid4(),
        {"sessions": []},
    )

    assert len(images) == 1
    assert len(job_tasks) == 1
    assert len(task_dtos) == 1
    assert parent_child == {}
    assert task_dtos[0].task_id == job_tasks[0].oid
    assert task_dtos[0].job_id == job_tasks[0].job_id
    assert task_dtos[0].image_id == images[0].oid
    assert task_dtos[0].image_path == str(image_path)
    assert task_dtos[0].frame_path == str(frame_path)
    assert job_tasks[0].subject_kind == "image"
    assert job_tasks[0].subject_id == images[0].oid


def test_serialem_montage_record_builder_links_task_dto_to_persisted_task(tmp_path):
    montage_path = tmp_path / "montages" / "session_1.mrc"
    montage_path.parent.mkdir()
    montage_path.write_bytes(b"mrc")

    importer = SerialEmImporter.__new__(SerialEmImporter)
    importer.params = _serialem_params(tmp_path)
    session = SimpleNamespace(oid=uuid.uuid4())
    job = SimpleNamespace(oid=uuid.uuid4())

    image, job_task, task_dto = importer._create_montage_image_entry(
        str(montage_path),
        session,
        job,
    )

    assert isinstance(image, Image)
    assert isinstance(job_task, ImageJobTask)
    assert task_dto.task_id == job_task.oid
    assert task_dto.job_id == job.oid
    assert job_task.job_id == job.oid
    assert job_task.image_id == image.oid
    assert job_task.subject_kind == "image"
    assert job_task.subject_id == image.oid


def test_serialem_metadata_record_builder_links_task_dto_to_persisted_task(tmp_path, monkeypatch):
    movie_path = tmp_path / "movie_001.tif"
    movie_path.write_bytes(b"tif")
    output_path = tmp_path / "jobs" / "movie_001.mrc"

    importer = SerialEmImporter.__new__(SerialEmImporter)
    importer.params = _serialem_params(tmp_path)
    session = SimpleNamespace(oid=uuid.uuid4())
    job = SimpleNamespace(oid=uuid.uuid4())
    metadata = SerialEMMetadata(
        file_path=str(movie_path),
        magnification=50000,
        defocus=1.5,
        dose=20.0,
        pixel_size=1.2,
        binning_x=1,
        binning_y=1,
        stage_alpha_tilt=0.0,
        stage_x=0.0,
        stage_y=0.0,
        atlas_delta_row=0.0,
        atlas_delta_column=0.0,
        acceleration_voltage=300,
        spherical_aberration=2.7,
    )

    monkeypatch.setattr(
        "services.importers.SerialEmImporter.convert_tiff_to_mrc",
        lambda *_args, **_kwargs: str(output_path),
    )

    image, job_task, task_dto = importer._process_metadata_entry(
        metadata,
        session,
        job,
        "gain.tif",
    )

    assert isinstance(image, Image)
    assert isinstance(job_task, ImageJobTask)
    assert task_dto.task_id == job_task.oid
    assert task_dto.job_id == job.oid
    assert job_task.job_id == job.oid
    assert job_task.image_id == image.oid
    assert job_task.subject_kind == "image"
    assert job_task.subject_id == image.oid


def test_serialem_process_task_skips_ctf_and_motioncor_for_montage(tmp_path):
    montage_dir = tmp_path / "montages"
    montage_dir.mkdir()
    image_path = montage_dir / "session_6.mrc"
    image_path.write_bytes(b"mrc")

    importer = SerialEmImporter.__new__(SerialEmImporter)
    importer.params = SimpleNamespace(copy_images=False)
    importer.transfer_frame = Mock()
    importer.copy_image = Mock()
    importer.convert_image_to_png = Mock(return_value={"message": "png"})
    importer.compute_fft = Mock(return_value={"message": "fft"})
    importer.compute_ctf = Mock(return_value={"message": "ctf"})
    importer.compute_motioncor = Mock(return_value={"message": "motioncor"})

    result = importer.process_task(
        SimpleNamespace(
            image_path=str(image_path),
            frame_name="session_6",
            frame_path=str(image_path),
        )
    )

    assert result["status"] == "success"
    importer.transfer_frame.assert_called_once()
    importer.convert_image_to_png.assert_called_once_with(str(image_path))
    importer.compute_fft.assert_called_once_with(str(image_path))
    importer.compute_ctf.assert_not_called()
    importer.compute_motioncor.assert_not_called()


class _ImageQuery:
    def __init__(self, rows):
        self.rows = rows

    def filter(self, *_args, **_kwargs):
        return self

    def order_by(self, *_args, **_kwargs):
        return self

    def all(self):
        return self.rows


class _SessionQuery:
    def __init__(self, row):
        self.row = row

    def filter(self, *_args, **_kwargs):
        return self

    def first(self):
        return self.row


class _AtlasSession:
    def __init__(self, images, session):
        self.images = images
        self.session = session
        self.saved = []
        self.commits = 0
        self.rollbacks = 0

    def query(self, model):
        if model is Image:
            return _ImageQuery(self.images)
        if model is Msession:
            return _SessionQuery(self.session)
        raise AssertionError(f"unexpected model query: {model}")

    def bulk_save_objects(self, objects):
        self.saved.extend(objects)

    def commit(self):
        self.commits += 1

    def rollback(self):
        self.rollbacks += 1


def test_base_importer_create_atlas_images_uses_atlas_service(monkeypatch):
    session_id = uuid.uuid4()
    image_id = uuid.uuid4()
    importer = _DummyImporter.__new__(_DummyImporter)
    importer.db_msession = SimpleNamespace(oid=session_id)

    db = _AtlasSession(
        images=[
            SimpleNamespace(
                oid=image_id,
                name="session_g1_0001",
                atlas_dimxy=12,
                atlas_delta_row=1,
                atlas_delta_column=2,
            )
        ],
        session=SimpleNamespace(name="session"),
    )

    build_atlas = Mock(
        return_value=[
            {
                "imageFilePath": r"C:\magellon\gpfs\home\session\atlases\g1.png",
                "imageMap": {"tiles": []},
            }
        ]
    )
    monkeypatch.setattr("services.importers.BaseImporter.build_atlas_images", build_atlas)

    result = BaseImporter.create_atlas_images(importer, db, session_id)

    assert result["count"] == 1
    build_atlas.assert_called_once()
    assert len(db.saved) == 1
    assert isinstance(db.saved[0], Atlas)
    assert db.saved[0].name == "g1"
    assert db.commits == 1
    assert db.rollbacks == 0


def test_base_importer_upsert_project_from_manifest_data_creates_project():
    importer = _DummyImporter.__new__(_DummyImporter)
    db = _CaptureSession()
    project_id = uuid.uuid4()
    owner_id = uuid.uuid4()

    project = importer.upsert_project_from_data(
        db,
        {
            "oid": str(project_id),
            "name": "project-a",
            "description": "Project A",
            "owner_id": str(owner_id),
            "start_on": "2026-05-01T10:00:00",
            "end_on": "2026-05-02T10:00:00",
        },
    )

    assert isinstance(project, Project)
    assert project.oid == project_id
    assert project.name == "project-a"
    assert project.description == "Project A"
    assert project.owner_id == owner_id
    assert db.added == [project]


def test_base_importer_create_import_job_uses_preassigned_id():
    importer = _DummyImporter.__new__(_DummyImporter)
    importer.pre_assigned_job_id = uuid.uuid4()
    db = _CaptureSession()
    session_id = uuid.uuid4()

    job = importer.create_import_job_record(
        db,
        session_id,
        name="Import: session-a",
        description="Import job for session-a",
        output_directory=r"C:\out",
    )

    assert isinstance(job, ImageJob)
    assert job.oid == importer.pre_assigned_job_id
    assert job.msession_id == session_id
    assert job.status_id == 1
    assert job.type_id == 1
    assert job.output_directory == r"C:\out"
    assert db.added == [job]


def test_base_importer_legacy_job_helper_uses_import_job_helper():
    importer = _DummyImporter.__new__(_DummyImporter)
    importer.pre_assigned_job_id = uuid.uuid4()
    db = _CaptureSession()
    session_id = uuid.uuid4()

    job = importer.create_job_record(
        db,
        session_id,
        "EPU Import: session-a",
        "EPU Import for session-a",
        r"C:\target",
    )

    assert job.oid == importer.pre_assigned_job_id
    assert job.name == "EPU Import: session-a"
    assert job.description == "EPU Import for session-a"
    assert job.msession_id == session_id
    assert job.output_directory == r"C:\target"
    assert job.status_id == 1
    assert job.type_id == 1
    assert db.added == [job]


def test_import_database_service_uses_magellon_session_name_for_job():
    db = _CaptureSession()
    service = ImportDatabaseService(db)

    project, session, job = service.initialize_import_records(
        SimpleNamespace(
            magellon_project_name="project-a",
            magellon_session_name="session-a",
            session_name=None,
        )
    )

    assert isinstance(project, Project)
    assert isinstance(session, Msession)
    assert isinstance(job, ImageJob)
    assert project.name == "project-a"
    assert project.last_accessed_date is not None
    assert session.name == "session-a"
    assert session.project_id == project.oid
    assert session.last_accessed_date is not None
    assert job.name == "Import: session-a"
    assert job.description == "Import job for session: session-a"
    assert job.msession_id == session.oid
    assert job.status_id == 1
    assert job.type_id == 1
    assert db.refreshed == [project, session, job]


def test_import_database_service_create_image_record_uses_valid_image_columns():
    db = _CaptureSession()
    service = ImportDatabaseService(db)
    session_id = uuid.uuid4()

    image = service.create_image_record(
        {
            "name": "image-a",
            "path": r"C:\images\image-a.mrc",
            "pixel_size": 1e-10,
        },
        session_id,
    )

    assert isinstance(image, Image)
    assert image.name == "image-a"
    assert image.path == r"C:\images\image-a.mrc"
    assert image.session_id == session_id
    assert image.last_accessed_date is not None
    assert db.refreshed == [image]


def test_base_importer_standard_task_pipeline_runs_expected_steps(tmp_path):
    image_path = tmp_path / "micrograph.mrc"
    image_path.write_bytes(b"mrc")

    importer = _DummyImporter.__new__(_DummyImporter)
    importer.params = SimpleNamespace(copy_images=False)
    importer.transfer_frame = Mock()
    importer.convert_image_to_png = Mock(return_value={"message": "png"})
    importer.compute_fft = Mock(return_value={"message": "fft"})
    importer.compute_ctf = Mock(return_value={"message": "ctf"})
    importer.compute_motioncor = Mock(return_value={"message": "motioncor"})

    result = importer.run_standard_task(
        SimpleNamespace(image_path=str(image_path), frame_name="frames", frame_path=str(image_path)),
        topaz_pick=False,
        topaz_denoise=False,
    )

    importer.transfer_frame.assert_called_once()
    importer.convert_image_to_png.assert_called_once_with(str(image_path))
    importer.compute_fft.assert_called_once_with(str(image_path))
    importer.compute_ctf.assert_called_once()
    importer.compute_motioncor.assert_called_once()
    assert result["png"] == {"message": "png"}
    assert result["fft"] == {"message": "fft"}


def test_import_data_passes_db_session_to_setup(monkeypatch):
    fake_importer = Mock()
    fake_importer.process.return_value = {"status": "success"}
    db_session = object()
    input_data = object()

    monkeypatch.setattr(
        "services.importers.ImporterFactory.ImporterFactory.get_importer",
        staticmethod(lambda _importer_type: fake_importer),
    )

    assert import_data("epu", input_data, db_session) == {"status": "success"}
    fake_importer.setup.assert_called_once_with(input_data, db_session)
    fake_importer.process.assert_called_once_with(db_session)


def test_magellon_session_json_strategy_validates_required_shape(tmp_path):
    (tmp_path / "session.json").write_text('{"msession": {"name": "s"}, "images": []}')

    data = MagellonSessionJsonStrategy().load(str(tmp_path))

    assert data["msession"]["name"] == "s"
    assert data["images"] == []


def test_magellon_session_json_strategy_rejects_missing_images(tmp_path):
    (tmp_path / "session.json").write_text('{"msession": {"name": "s"}}')

    with pytest.raises(Exception) as exc:
        MagellonSessionJsonStrategy().load(str(tmp_path))

    assert "images" in str(exc.value)


@pytest.mark.performance
def test_magellon_process_images_scales_linearly_for_large_manifest(monkeypatch):
    from services.importers.MagellonImporter import MagellonImporter

    class FakeSession:
        def query(self, _model):
            return _NoResultQuery()

        def add(self, _obj):
            pass

    importer = MagellonImporter.__new__(MagellonImporter)
    importer.db_msession = SimpleNamespace(oid=uuid.uuid4())
    importer.db_job = SimpleNamespace(oid=uuid.uuid4())
    importer.params = SimpleNamespace(source_dir=r"C:\source")

    monkeypatch.setattr("services.importers.MagellonImporter.os.path.exists", lambda _p: True)

    images = [
        {
            "name": f"img_{idx:05d}",
            "frame_name": None,
            "path": None,
            "pixel_size": 1e-10,
            "spherical_aberration": 2.7,
        }
        for idx in range(1000)
    ]

    import time

    start = time.perf_counter()
    result = importer.process_images(FakeSession(), images)
    elapsed = time.perf_counter() - start

    assert len(result) == 1000
    assert elapsed < 5.0
