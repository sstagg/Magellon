"""
Tests for the template-picker plugin.

Covers:
  1. Pydantic model validation (input / output contracts)
  2. Core algorithm with synthetic data
  3. Plugin lifecycle (PluginBase contract)
  4. Service layer with temp MRC files
  5. FastAPI endpoint via TestClient
"""

import json
import math
import os
import tempfile

import numpy as np
import pytest

from models.plugins_models import PluginStatus, RecuirementResultEnum
from plugins.pp.models import (
    AngleRange,
    ParticlePick,
    TemplatePickerInput,
    TemplatePickerOutput,
)
from plugins.pp.template_picker.algorithm import pick_particles


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_gaussian_blob(size: int, sigma: float, center: tuple[int, int]) -> np.ndarray:
    """Create a 2D image with a single Gaussian blob."""
    y, x = np.ogrid[:size, :size]
    cy, cx = center
    return np.exp(-((y - cy) ** 2 + (x - cx) ** 2) / (2 * sigma ** 2)).astype(np.float32)


def _make_micrograph_with_particles(
    size: int = 512,
    blob_sigma: float = 8.0,
    positions: list[tuple[int, int]] | None = None,
) -> np.ndarray:
    """Synthetic micrograph: Gaussian blobs on noisy background."""
    rng = np.random.RandomState(42)
    image = rng.normal(0, 0.05, (size, size)).astype(np.float32)
    if positions is None:
        positions = [(128, 128), (128, 384), (384, 128), (384, 384), (256, 256)]
    for cy, cx in positions:
        image += _make_gaussian_blob(size, blob_sigma, (cy, cx))
    return image


def _make_template(size: int = 64, sigma: float = 8.0) -> np.ndarray:
    """Synthetic template: centred Gaussian blob."""
    center = size // 2
    return _make_gaussian_blob(size, sigma, (center, center))


def _write_mrc(path: str, data: np.ndarray) -> None:
    import mrcfile

    with mrcfile.new(path, overwrite=True) as mrc:
        mrc.set_data(data.astype(np.float32))


# ---------------------------------------------------------------------------
# 1. Pydantic model validation tests
# ---------------------------------------------------------------------------

class TestModels:
    """Contract enforcement via Pydantic."""

    def test_particle_pick_valid(self):
        p = ParticlePick(x=10, y=20, score=0.8)
        assert p.x == 10
        assert p.score == 0.8

    def test_particle_pick_rejects_extra_fields(self):
        with pytest.raises(Exception):
            ParticlePick(x=10, y=20, score=0.8, unknown_field="bad")

    def test_input_requires_image_path(self):
        with pytest.raises(Exception):
            TemplatePickerInput(
                template_paths=["t.mrc"],
                image_pixel_size=1.0,
                template_pixel_size=1.0,
                diameter_angstrom=100.0,
            )

    def test_input_requires_at_least_one_template(self):
        with pytest.raises(Exception):
            TemplatePickerInput(
                image_path="img.mrc",
                template_paths=[],
                image_pixel_size=1.0,
                template_pixel_size=1.0,
                diameter_angstrom=100.0,
            )

    def test_input_rejects_negative_pixel_size(self):
        with pytest.raises(Exception):
            TemplatePickerInput(
                image_path="img.mrc",
                template_paths=["t.mrc"],
                image_pixel_size=-1.0,
                template_pixel_size=1.0,
                diameter_angstrom=100.0,
            )

    def test_input_rejects_extra_fields(self):
        with pytest.raises(Exception):
            TemplatePickerInput(
                image_path="img.mrc",
                template_paths=["t.mrc"],
                image_pixel_size=1.0,
                template_pixel_size=1.0,
                diameter_angstrom=100.0,
                bogus=True,
            )

    def test_input_defaults(self):
        inp = TemplatePickerInput(
            image_path="img.mrc",
            template_paths=["t.mrc"],
            image_pixel_size=1.5,
            template_pixel_size=2.0,
            diameter_angstrom=200.0,
        )
        assert inp.threshold == 0.4
        assert inp.max_peaks == 500
        assert inp.bin_factor == 1
        assert inp.invert_templates is False
        assert inp.angle_ranges is None

    def test_angle_range_model(self):
        ar = AngleRange(start=0, end=180, step=15)
        assert ar.end == 180.0

    def test_output_rejects_extra_fields(self):
        with pytest.raises(Exception):
            TemplatePickerOutput(
                particles=[],
                num_particles=0,
                num_templates=1,
                target_pixel_size=1.0,
                image_binning=1,
                rogue_field="nope",
            )

    def test_output_valid(self):
        out = TemplatePickerOutput(
            particles=[ParticlePick(x=1, y=2, score=0.5)],
            num_particles=1,
            num_templates=1,
            target_pixel_size=1.5,
            image_binning=2,
        )
        assert out.num_particles == 1
        assert out.particles[0].x == 1


# ---------------------------------------------------------------------------
# 2. Core algorithm tests
# ---------------------------------------------------------------------------

class TestAlgorithm:
    """Tests against pick_particles() with synthetic numpy arrays."""

    def test_finds_particles_in_synthetic_micrograph(self):
        positions = [(128, 128), (128, 384), (384, 128), (384, 384)]
        image = _make_micrograph_with_particles(size=512, positions=positions)
        template = _make_template(size=64, sigma=8.0)

        result = pick_particles(
            image=image,
            templates=[template],
            params={
                "diameter_angstrom": 64.0,
                "pixel_size_angstrom": 1.0,
                "threshold": 0.1,
                "max_peaks": 100,
            },
        )

        assert "particles" in result
        assert "merged_score_map" in result
        assert "assigned_template_map" in result
        assert "template_results" in result
        assert len(result["particles"]) > 0

    def test_returns_no_particles_with_high_threshold(self):
        image = _make_micrograph_with_particles(size=256, positions=[(128, 128)])
        template = _make_template(size=64, sigma=8.0)

        result = pick_particles(
            image=image,
            templates=[template],
            params={
                "diameter_angstrom": 64.0,
                "pixel_size_angstrom": 1.0,
                "threshold": 0.99,
                "max_peaks": 100,
            },
        )
        assert len(result["particles"]) == 0

    def test_max_peaks_limits_output(self):
        positions = [(64 + 80 * i, 64 + 80 * j) for i in range(5) for j in range(5)]
        image = _make_micrograph_with_particles(size=512, positions=positions)
        template = _make_template(size=48, sigma=6.0)

        result = pick_particles(
            image=image,
            templates=[template],
            params={
                "diameter_angstrom": 48.0,
                "pixel_size_angstrom": 1.0,
                "threshold": 0.05,
                "max_peaks": 3,
            },
        )
        assert len(result["particles"]) <= 3

    def test_multiple_templates(self):
        image = _make_micrograph_with_particles(size=256, positions=[(128, 128)])
        t1 = _make_template(size=64, sigma=8.0)
        t2 = _make_template(size=64, sigma=12.0)

        result = pick_particles(
            image=image,
            templates=[t1, t2],
            params={
                "diameter_angstrom": 64.0,
                "pixel_size_angstrom": 1.0,
                "threshold": 0.1,
                "max_peaks": 50,
            },
        )

        assert len(result["template_results"]) == 2
        assert result["merged_score_map"].shape == image.shape
        assert result["assigned_template_map"].shape == image.shape

    def test_particle_dict_has_required_keys(self):
        image = _make_micrograph_with_particles(size=256, positions=[(128, 128)])
        template = _make_template(size=64, sigma=8.0)

        result = pick_particles(
            image=image,
            templates=[template],
            params={
                "diameter_angstrom": 64.0,
                "pixel_size_angstrom": 1.0,
                "threshold": 0.1,
                "max_peaks": 50,
            },
        )

        if result["particles"]:
            p = result["particles"][0]
            for key in ("x", "y", "score", "stddev", "area", "roundness", "template_index", "angle", "label"):
                assert key in p

    def test_rejects_non_2d_image(self):
        with pytest.raises(ValueError, match="2D"):
            pick_particles(
                image=np.zeros((10, 10, 3)),
                templates=[np.zeros((5, 5))],
                params={"diameter_angstrom": 10.0, "pixel_size_angstrom": 1.0},
            )

    def test_rejects_empty_templates(self):
        with pytest.raises(ValueError, match="at least one"):
            pick_particles(
                image=np.zeros((64, 64)),
                templates=[],
                params={"diameter_angstrom": 10.0, "pixel_size_angstrom": 1.0},
            )

    def test_rejects_template_larger_than_image(self):
        with pytest.raises(ValueError, match="larger than image"):
            pick_particles(
                image=np.zeros((32, 32)),
                templates=[np.zeros((64, 64))],
                params={"diameter_angstrom": 10.0, "pixel_size_angstrom": 1.0},
            )

    def test_score_map_dtype(self):
        image = _make_micrograph_with_particles(size=128, positions=[(64, 64)])
        template = _make_template(size=32, sigma=5.0)

        result = pick_particles(
            image=image,
            templates=[template],
            params={"diameter_angstrom": 32.0, "pixel_size_angstrom": 1.0, "threshold": 0.1},
        )
        assert result["merged_score_map"].dtype == np.float32


# ---------------------------------------------------------------------------
# 3. Plugin lifecycle tests
# ---------------------------------------------------------------------------

class TestPluginLifecycle:
    """Test the PluginBase contract via TemplatePickerPlugin."""

    @pytest.fixture()
    def plugin(self):
        from plugins.pp.template_picker.service import TemplatePickerPlugin
        return TemplatePickerPlugin()

    # -- metadata --

    def test_get_info(self, plugin):
        info = plugin.get_info()
        assert info.name == "template-picker"
        assert info.version == "1.0.0"
        assert info.developer == "Magellon"

    def test_input_schema(self, plugin):
        assert plugin.input_schema() is TemplatePickerInput

    def test_output_schema(self, plugin):
        assert plugin.output_schema() is TemplatePickerOutput

    def test_task_category(self, plugin):
        from models.plugins_models import PARTICLE_PICKING
        assert plugin.task_category == PARTICLE_PICKING

    # -- initial state --

    def test_initial_status_is_discovered(self, plugin):
        assert plugin.status == PluginStatus.DISCOVERED

    # -- check_requirements --

    def test_check_requirements_passes(self, plugin):
        results = plugin.check_requirements()
        assert len(results) >= 2  # mrcfile + scipy
        assert all(r.result == RecuirementResultEnum.SUCCESS for r in results)
        assert plugin.status == PluginStatus.INSTALLED

    def test_check_requirements_reports_conditions(self, plugin):
        results = plugin.check_requirements()
        conditions = {r.condition for r in results}
        assert "mrcfile" in conditions
        assert "scipy" in conditions

    # -- configure --

    def test_configure_sets_status(self, plugin):
        plugin.check_requirements()
        plugin.configure()
        assert plugin.status == PluginStatus.CONFIGURED

    def test_configure_with_settings(self, plugin):
        plugin.check_requirements()
        plugin.configure({"some_key": "some_value"})
        assert plugin._config["some_key"] == "some_value"
        assert plugin.status == PluginStatus.CONFIGURED

    # -- setup --

    def test_setup_sets_ready(self, plugin):
        plugin.check_requirements()
        plugin.configure()
        plugin.setup()
        assert plugin.status == PluginStatus.READY

    # -- teardown --

    def test_teardown_sets_disabled(self, plugin):
        plugin.check_requirements()
        plugin.configure()
        plugin.setup()
        plugin.teardown()
        assert plugin.status == PluginStatus.DISABLED

    # -- health_check --

    def test_health_check(self, plugin):
        health = plugin.health_check()
        assert health["plugin"] == "template-picker"
        assert health["version"] == "1.0.0"
        assert health["status"] == PluginStatus.DISCOVERED.value

    def test_health_check_reflects_status_changes(self, plugin):
        plugin.check_requirements()
        plugin.configure()
        plugin.setup()
        health = plugin.health_check()
        assert health["status"] == PluginStatus.READY.value

    # -- full lifecycle with execution --

    @pytest.fixture()
    def mrc_fixtures(self, tmp_path):
        pytest.importorskip("mrcfile")
        image = _make_micrograph_with_particles(size=256, positions=[(128, 128)])
        template = _make_template(size=64, sigma=8.0)
        img_path = str(tmp_path / "micrograph.mrc")
        tmpl_path = str(tmp_path / "template.mrc")
        _write_mrc(img_path, image)
        _write_mrc(tmpl_path, template)
        return img_path, tmpl_path

    def test_full_lifecycle(self, plugin, mrc_fixtures):
        img_path, tmpl_path = mrc_fixtures

        # 1. check_requirements
        reqs = plugin.check_requirements()
        assert plugin.status == PluginStatus.INSTALLED

        # 2. configure
        plugin.configure()
        assert plugin.status == PluginStatus.CONFIGURED

        # 3. setup
        plugin.setup()
        assert plugin.status == PluginStatus.READY

        # 4. run (pre_execute + execute + post_execute)
        result = plugin.run(TemplatePickerInput(
            image_path=img_path,
            template_paths=[tmpl_path],
            image_pixel_size=1.0,
            template_pixel_size=1.0,
            diameter_angstrom=64.0,
            threshold=0.1,
        ))
        assert isinstance(result, TemplatePickerOutput)
        assert plugin.status == PluginStatus.COMPLETED

        # 5. teardown
        plugin.teardown()
        assert plugin.status == PluginStatus.DISABLED

    def test_run_accepts_raw_dict(self, plugin, mrc_fixtures):
        img_path, tmpl_path = mrc_fixtures
        plugin.check_requirements()
        plugin.configure()
        plugin.setup()

        result = plugin.run({
            "image_path": img_path,
            "template_paths": [tmpl_path],
            "image_pixel_size": 1.0,
            "template_pixel_size": 1.0,
            "diameter_angstrom": 64.0,
            "threshold": 0.1,
        })
        assert isinstance(result, TemplatePickerOutput)

    def test_run_sets_error_on_failure(self, plugin):
        plugin.check_requirements()
        plugin.configure()
        plugin.setup()

        with pytest.raises(Exception):
            plugin.run(TemplatePickerInput(
                image_path="/nonexistent/image.mrc",
                template_paths=["/nonexistent/template.mrc"],
                image_pixel_size=1.0,
                template_pixel_size=1.0,
                diameter_angstrom=64.0,
            ))
        assert plugin.status == PluginStatus.ERROR

    def test_run_validates_input_dict(self, plugin):
        plugin.check_requirements()
        plugin.configure()
        plugin.setup()

        with pytest.raises(Exception):
            plugin.run({"image_path": "x.mrc"})  # missing required fields

    def test_run_recovers_after_error(self, plugin, mrc_fixtures):
        """After an error, the plugin can still accept new work."""
        img_path, tmpl_path = mrc_fixtures
        plugin.check_requirements()
        plugin.configure()
        plugin.setup()

        # First run fails
        with pytest.raises(Exception):
            plugin.run(TemplatePickerInput(
                image_path="/nonexistent.mrc",
                template_paths=["/nonexistent.mrc"],
                image_pixel_size=1.0,
                template_pixel_size=1.0,
                diameter_angstrom=64.0,
            ))
        assert plugin.status == PluginStatus.ERROR

        # Second run succeeds
        result = plugin.run(TemplatePickerInput(
            image_path=img_path,
            template_paths=[tmpl_path],
            image_pixel_size=1.0,
            template_pixel_size=1.0,
            diameter_angstrom=64.0,
            threshold=0.1,
        ))
        assert plugin.status == PluginStatus.COMPLETED
        assert isinstance(result, TemplatePickerOutput)


# ---------------------------------------------------------------------------
# 4. Service layer tests (with real MRC files on disk)
# ---------------------------------------------------------------------------

class TestService:
    """Integration tests using temp MRC files."""

    @pytest.fixture()
    def mrc_fixtures(self, tmp_path):
        """Write synthetic micrograph + template to temp MRC files."""
        mrcfile = pytest.importorskip("mrcfile")

        image = _make_micrograph_with_particles(size=256, positions=[(128, 128)])
        template = _make_template(size=64, sigma=8.0)

        img_path = str(tmp_path / "micrograph.mrc")
        tmpl_path = str(tmp_path / "template.mrc")
        _write_mrc(img_path, image)
        _write_mrc(tmpl_path, template)

        return img_path, tmpl_path, tmp_path

    def test_run_template_picker(self, mrc_fixtures):
        from plugins.pp.template_picker.service import run_template_picker

        img_path, tmpl_path, tmp_path = mrc_fixtures
        out_dir = str(tmp_path / "output")

        inp = TemplatePickerInput(
            image_path=img_path,
            template_paths=[tmpl_path],
            image_pixel_size=1.0,
            template_pixel_size=1.0,
            diameter_angstrom=64.0,
            threshold=0.1,
            output_dir=out_dir,
        )

        result = run_template_picker(inp)

        assert isinstance(result, TemplatePickerOutput)
        assert result.num_templates == 1
        assert result.num_particles >= 0
        assert result.target_pixel_size == 1.0
        assert result.image_binning == 1

        # Check artifacts written
        assert result.particles_csv_path is not None
        assert os.path.isfile(result.particles_csv_path)
        assert os.path.isfile(result.particles_json_path)
        assert os.path.isfile(os.path.join(out_dir, "run_summary.json"))

    def test_run_with_binning(self, mrc_fixtures):
        from plugins.pp.template_picker.service import run_template_picker

        img_path, tmpl_path, _ = mrc_fixtures

        inp = TemplatePickerInput(
            image_path=img_path,
            template_paths=[tmpl_path],
            image_pixel_size=1.0,
            template_pixel_size=1.0,
            diameter_angstrom=64.0,
            threshold=0.1,
            bin_factor=2,
        )

        result = run_template_picker(inp)
        assert result.image_binning == 2
        assert result.target_pixel_size == 2.0

    def test_run_with_invert(self, mrc_fixtures):
        from plugins.pp.template_picker.service import run_template_picker

        img_path, tmpl_path, _ = mrc_fixtures

        inp = TemplatePickerInput(
            image_path=img_path,
            template_paths=[tmpl_path],
            image_pixel_size=1.0,
            template_pixel_size=1.0,
            diameter_angstrom=64.0,
            threshold=0.1,
            invert_templates=True,
        )

        result = run_template_picker(inp)
        assert isinstance(result, TemplatePickerOutput)

    def test_file_not_found(self):
        from plugins.pp.template_picker.service import run_template_picker

        inp = TemplatePickerInput(
            image_path="/nonexistent/image.mrc",
            template_paths=["/nonexistent/template.mrc"],
            image_pixel_size=1.0,
            template_pixel_size=1.0,
            diameter_angstrom=64.0,
        )

        with pytest.raises(Exception):
            run_template_picker(inp)

    def test_output_particles_are_valid_pydantic(self, mrc_fixtures):
        from plugins.pp.template_picker.service import run_template_picker

        img_path, tmpl_path, _ = mrc_fixtures

        inp = TemplatePickerInput(
            image_path=img_path,
            template_paths=[tmpl_path],
            image_pixel_size=1.0,
            template_pixel_size=1.0,
            diameter_angstrom=64.0,
            threshold=0.05,
        )

        result = run_template_picker(inp)

        for p in result.particles:
            assert isinstance(p, ParticlePick)
            assert isinstance(p.x, int)
            assert isinstance(p.y, int)
            assert isinstance(p.score, float)


# ---------------------------------------------------------------------------
# 5. FastAPI endpoint tests
# ---------------------------------------------------------------------------

class TestEndpoint:
    """HTTP-level tests via FastAPI TestClient."""

    @pytest.fixture()
    def client(self):
        from fastapi.testclient import TestClient
        from main import app

        return TestClient(app)

    @pytest.fixture()
    def mrc_files(self, tmp_path):
        pytest.importorskip("mrcfile")

        image = _make_micrograph_with_particles(size=256, positions=[(128, 128)])
        template = _make_template(size=64, sigma=8.0)

        img_path = str(tmp_path / "micrograph.mrc")
        tmpl_path = str(tmp_path / "template.mrc")
        _write_mrc(img_path, image)
        _write_mrc(tmpl_path, template)

        return img_path, tmpl_path

    def test_template_pick_endpoint(self, client, mrc_files):
        img_path, tmpl_path = mrc_files

        payload = {
            "image_path": img_path,
            "template_paths": [tmpl_path],
            "image_pixel_size": 1.0,
            "template_pixel_size": 1.0,
            "diameter_angstrom": 64.0,
            "threshold": 0.1,
        }

        response = client.post("/plugins/pp/template-pick", json=payload)
        assert response.status_code == 200

        data = response.json()
        assert "particles" in data
        assert "num_particles" in data
        assert "num_templates" in data
        assert data["num_templates"] == 1

    def test_endpoint_validation_error(self, client):
        payload = {
            "image_path": "img.mrc",
            "template_paths": [],
            "image_pixel_size": 1.0,
            "template_pixel_size": 1.0,
            "diameter_angstrom": 100.0,
        }

        response = client.post("/plugins/pp/template-pick", json=payload)
        assert response.status_code == 422

    def test_endpoint_rejects_extra_fields(self, client):
        payload = {
            "image_path": "img.mrc",
            "template_paths": ["t.mrc"],
            "image_pixel_size": 1.0,
            "template_pixel_size": 1.0,
            "diameter_angstrom": 100.0,
            "unknown_field": "should fail",
        }

        response = client.post("/plugins/pp/template-pick", json=payload)
        assert response.status_code == 422

    def test_endpoint_file_not_found(self, client):
        payload = {
            "image_path": "/nonexistent/path.mrc",
            "template_paths": ["/nonexistent/template.mrc"],
            "image_pixel_size": 1.0,
            "template_pixel_size": 1.0,
            "diameter_angstrom": 100.0,
        }

        response = client.post("/plugins/pp/template-pick", json=payload)
        assert response.status_code in (404, 500)

    # -- lifecycle endpoints --

    def test_info_endpoint(self, client):
        response = client.get("/plugins/pp/template-pick/info")
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "template-picker"
        assert data["version"] == "1.0.0"

    def test_health_endpoint(self, client):
        response = client.get("/plugins/pp/template-pick/health")
        assert response.status_code == 200
        data = response.json()
        assert data["plugin"] == "template-picker"
        assert "status" in data

    def test_requirements_endpoint(self, client):
        response = client.get("/plugins/pp/template-pick/requirements")
        assert response.status_code == 200
        data = response.json()
        assert len(data) >= 2
        conditions = {r["condition"] for r in data}
        assert "mrcfile" in conditions
        assert "scipy" in conditions

    def test_input_schema_endpoint(self, client):
        response = client.get("/plugins/pp/template-pick/schema/input")
        assert response.status_code == 200
        schema = response.json()
        assert schema["type"] == "object"
        assert "image_path" in schema["properties"]
        assert "template_paths" in schema["properties"]

    def test_output_schema_endpoint(self, client):
        response = client.get("/plugins/pp/template-pick/schema/output")
        assert response.status_code == 200
        schema = response.json()
        assert schema["type"] == "object"
        assert "particles" in schema["properties"]


# ---------------------------------------------------------------------------
# 6. Async endpoint and job tracking tests
# ---------------------------------------------------------------------------

class TestAsyncEndpoint:
    """Tests for async job submission and tracking."""

    @pytest.fixture()
    def client(self):
        from fastapi.testclient import TestClient
        from main import app
        return TestClient(app)

    @pytest.fixture()
    def mrc_files(self, tmp_path):
        pytest.importorskip("mrcfile")
        image = _make_micrograph_with_particles(size=256, positions=[(128, 128)])
        template = _make_template(size=64, sigma=8.0)
        img_path = str(tmp_path / "micrograph.mrc")
        tmpl_path = str(tmp_path / "template.mrc")
        _write_mrc(img_path, image)
        _write_mrc(tmpl_path, template)
        return img_path, tmpl_path

    def test_async_pick_returns_job_id(self, client, mrc_files):
        img_path, tmpl_path = mrc_files
        payload = {
            "image_path": img_path,
            "template_paths": [tmpl_path],
            "image_pixel_size": 1.0,
            "template_pixel_size": 1.0,
            "diameter_angstrom": 64.0,
            "threshold": 0.1,
        }

        response = client.post("/plugins/pp/template-pick-async", json=payload)
        assert response.status_code == 200
        data = response.json()
        assert "job_id" in data
        assert data["status"] == "queued"

    def test_jobs_list_endpoint(self, client):
        response = client.get("/plugins/pp/jobs")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)

    def test_job_detail_not_found(self, client):
        response = client.get("/plugins/pp/jobs/nonexistent-id")
        assert response.status_code == 404

    def test_async_pick_creates_job_in_store(self, client, mrc_files):
        """Async endpoint creates a job entry that can be polled."""
        img_path, tmpl_path = mrc_files
        payload = {
            "image_path": img_path,
            "template_paths": [tmpl_path],
            "image_pixel_size": 1.0,
            "template_pixel_size": 1.0,
            "diameter_angstrom": 64.0,
            "threshold": 0.1,
        }

        resp = client.post("/plugins/pp/template-pick-async", json=payload)
        job_id = resp.json()["job_id"]

        # The job should exist in the jobs list
        detail = client.get(f"/plugins/pp/jobs/{job_id}")
        assert detail.status_code == 200
        job = detail.json()
        assert job["id"] == job_id
        assert job["name"] == "Particle Picking"
        assert job["type"] == "picking"
        # Status may be queued or running depending on timing
        assert job["status"] in ("queued", "running", "completed")


# ---------------------------------------------------------------------------
# 7. Socket.IO helper function tests
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# 7. Preview / retune tests
# ---------------------------------------------------------------------------

class TestPreviewRetune:
    """Tests for the preview → retune → accept flow."""

    @pytest.fixture()
    def client(self):
        from fastapi.testclient import TestClient
        from main import app
        return TestClient(app)

    @pytest.fixture()
    def mrc_files(self, tmp_path):
        pytest.importorskip("mrcfile")
        image = _make_micrograph_with_particles(size=256, positions=[(128, 128)])
        template = _make_template(size=64, sigma=8.0)
        img_path = str(tmp_path / "micrograph.mrc")
        tmpl_path = str(tmp_path / "template.mrc")
        _write_mrc(img_path, image)
        _write_mrc(tmpl_path, template)
        return img_path, tmpl_path

    def test_preview_returns_preview_id_and_particles(self, client, mrc_files):
        img_path, tmpl_path = mrc_files
        resp = client.post("/plugins/pp/template-pick/preview", json={
            "image_path": img_path,
            "template_paths": [tmpl_path],
            "image_pixel_size": 1.0,
            "template_pixel_size": 1.0,
            "diameter_angstrom": 64.0,
            "threshold": 0.1,
        })
        assert resp.status_code == 200
        data = resp.json()
        assert "preview_id" in data
        assert "particles" in data
        assert "score_map_png_base64" in data
        assert "score_range" in data
        assert data["num_templates"] == 1

    def test_retune_changes_particle_count(self, client, mrc_files):
        img_path, tmpl_path = mrc_files

        # Get preview
        resp = client.post("/plugins/pp/template-pick/preview", json={
            "image_path": img_path,
            "template_paths": [tmpl_path],
            "image_pixel_size": 1.0,
            "template_pixel_size": 1.0,
            "diameter_angstrom": 64.0,
            "threshold": 0.1,
        })
        preview_id = resp.json()["preview_id"]
        initial_count = resp.json()["num_particles"]

        # Retune with very high threshold — should find fewer particles
        resp2 = client.post(f"/plugins/pp/template-pick/preview/{preview_id}/retune", json={
            "threshold": 0.99,
        })
        assert resp2.status_code == 200
        assert resp2.json()["num_particles"] <= initial_count

        # Retune with very low threshold — should find more particles
        resp3 = client.post(f"/plugins/pp/template-pick/preview/{preview_id}/retune", json={
            "threshold": 0.01,
        })
        assert resp3.status_code == 200
        assert resp3.json()["num_particles"] >= resp2.json()["num_particles"]

    def test_retune_not_found(self, client):
        resp = client.post("/plugins/pp/template-pick/preview/nonexistent/retune", json={
            "threshold": 0.5,
        })
        assert resp.status_code == 404

    def test_preview_delete(self, client, mrc_files):
        img_path, tmpl_path = mrc_files

        resp = client.post("/plugins/pp/template-pick/preview", json={
            "image_path": img_path,
            "template_paths": [tmpl_path],
            "image_pixel_size": 1.0,
            "template_pixel_size": 1.0,
            "diameter_angstrom": 64.0,
            "threshold": 0.1,
        })
        preview_id = resp.json()["preview_id"]

        # Delete
        del_resp = client.delete(f"/plugins/pp/template-pick/preview/{preview_id}")
        assert del_resp.status_code == 200

        # Retune should now 404
        resp2 = client.post(f"/plugins/pp/template-pick/preview/{preview_id}/retune", json={
            "threshold": 0.5,
        })
        assert resp2.status_code == 404

    def test_score_map_is_valid_base64_png(self, client, mrc_files):
        img_path, tmpl_path = mrc_files
        resp = client.post("/plugins/pp/template-pick/preview", json={
            "image_path": img_path,
            "template_paths": [tmpl_path],
            "image_pixel_size": 1.0,
            "template_pixel_size": 1.0,
            "diameter_angstrom": 64.0,
            "threshold": 0.1,
        })
        b64 = resp.json()["score_map_png_base64"]
        assert b64 is not None

        import base64
        png_bytes = base64.b64decode(b64)
        # PNG magic number
        assert png_bytes[:4] == b'\x89PNG'


# ---------------------------------------------------------------------------
# 8. Socket.IO helper function tests
# ---------------------------------------------------------------------------

class TestSocketIOHelpers:
    """Test the emit_log and emit_job_update helpers."""

    @pytest.mark.asyncio
    async def test_emit_log_no_clients(self):
        """emit_log should not raise even with no connected clients."""
        from core.socketio_server import emit_log
        # Should not raise — graceful no-op
        await emit_log('info', 'test', 'hello world')

    @pytest.mark.asyncio
    async def test_emit_job_update_no_clients(self):
        """emit_job_update should not raise even with no connected clients."""
        from core.socketio_server import emit_job_update
        await emit_job_update(None, {'id': 'test', 'status': 'running'})
