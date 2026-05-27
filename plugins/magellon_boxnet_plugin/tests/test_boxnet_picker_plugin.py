"""Contract pin tests for the external BoxNet picker plugin.

Mirrors the template-picker test suite. Most tests run without torch /
mrcfile / scikit-image installed — algorithm.py defers those imports
to inside ``pick_with_boxnet``, and the SDK contract checks here only
import the Pydantic shapes + the PluginBase subclass.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest


_PLUGIN_ROOT = Path(__file__).resolve().parents[1]
if str(_PLUGIN_ROOT) not in sys.path:
    sys.path.insert(0, str(_PLUGIN_ROOT))


# ---------------------------------------------------------------------------
# Contract
# ---------------------------------------------------------------------------


def test_input_schema_is_plugin_owned_rich_model():
    """PE2-UI (2026-05-12): the plugin owns its input model so the
    runner page renders sliders + selects instead of the category
    contract's bare CryoEmImageInput shape."""
    from plugin.models import BoxnetPickerInput
    from plugin.plugin import BoxnetPickerPlugin

    assert BoxnetPickerPlugin.input_schema() is BoxnetPickerInput

    schema = BoxnetPickerInput.model_json_schema()
    assert "threshold" in schema["properties"]
    assert schema["properties"]["threshold"]["ui_widget"] == "slider"
    assert schema["properties"]["scale"]["ui_widget"] == "select"
    assert schema["properties"]["scale"]["ui_options"] == [1, 2, 4, 8]


def test_output_schema_matches_particle_picker_contract():
    """Output stays at the category-shared shape so downstream
    consumers can swap pickers without recompiling. Only the input
    shape is plugin-owned."""
    from magellon_sdk.categories.contract import PARTICLE_PICKER
    from plugin.plugin import BoxnetPickerPlugin

    assert BoxnetPickerPlugin.output_schema() is PARTICLE_PICKER.output_model


def test_get_info_provenance():
    from plugin.plugin import BoxnetPickerPlugin

    info = BoxnetPickerPlugin().get_info()
    assert info.name == "BoxNet Picker"
    assert info.version == "0.1.0"


def test_manifest_advertises_progress_and_rmq_default():
    from magellon_sdk.models.manifest import Capability, Transport
    from plugin.plugin import BoxnetPickerPlugin

    manifest = BoxnetPickerPlugin().manifest()
    assert Capability.PROGRESS_REPORTING in manifest.capabilities
    assert Capability.SYNC in manifest.capabilities
    # No PREVIEW for now — BoxNet's only knob is the threshold and the
    # bus path already accepts it inline.
    assert Capability.PREVIEW not in manifest.capabilities
    assert manifest.default_transport == Transport.RMQ


# ---------------------------------------------------------------------------
# Required-field validation
# ---------------------------------------------------------------------------


def test_input_rejects_missing_image_path():
    from pydantic import ValidationError
    from plugin.models import BoxnetPickerInput

    with pytest.raises(ValidationError, match="image_path"):
        BoxnetPickerInput(threshold=0.3)


def test_input_rejects_extra_fields():
    """``extra=forbid`` on the model — typos in field names fail the
    Pydantic layer instead of silently passing through."""
    from pydantic import ValidationError
    from plugin.models import BoxnetPickerInput

    with pytest.raises(ValidationError):
        BoxnetPickerInput(image_path="/tmp/x.mrc", thresholdz=0.5)


def test_input_accepts_coreservice_transport_fields():
    """CoreService adds these fields to RMQ particle-picking tasks."""
    from plugin.models import BoxnetPickerInput

    parsed = BoxnetPickerInput(
        image_path="/tmp/x.mrc",
        input_file="/tmp/x.mrc",
        ipp_name="Auto-pick",
    )

    assert parsed.input_file == "/tmp/x.mrc"
    assert parsed.ipp_name == "Auto-pick"


def test_input_clamps_threshold_to_unit_interval():
    from pydantic import ValidationError
    from plugin.models import BoxnetPickerInput

    with pytest.raises(ValidationError):
        BoxnetPickerInput(image_path="/tmp/x.mrc", threshold=1.5)
    with pytest.raises(ValidationError):
        BoxnetPickerInput(image_path="/tmp/x.mrc", threshold=-0.1)


def test_input_min_distance_must_be_positive():
    from pydantic import ValidationError
    from plugin.models import BoxnetPickerInput

    with pytest.raises(ValidationError):
        BoxnetPickerInput(image_path="/tmp/x.mrc", min_distance=0)


# ---------------------------------------------------------------------------
# Data-plane path mapping
# ---------------------------------------------------------------------------


def test_compute_rewrites_canonical_gpfs_path_for_windows(monkeypatch):
    from core.settings import AppSettingsSingleton
    from plugin import compute

    class Settings:
        MAGELLON_GPFS_PATH = "C:/magellon/gpfs"

    monkeypatch.setattr(
        AppSettingsSingleton,
        "get_instance",
        staticmethod(lambda: Settings()),
    )

    assert (
        compute._resolve_local_path("/gpfs/home/s/mic.mrc")
        == "C:/magellon/gpfs/home/s/mic.mrc"
    )


def test_compute_returns_wire_path_from_local_gpfs_path(monkeypatch):
    from core.settings import AppSettingsSingleton
    from plugin import compute

    class Settings:
        MAGELLON_GPFS_PATH = "C:/magellon/gpfs"

    monkeypatch.setattr(
        AppSettingsSingleton,
        "get_instance",
        staticmethod(lambda: Settings()),
    )

    assert (
        compute._to_wire_path("C:/magellon/gpfs/home/s/particles.json")
        == "/gpfs/home/s/particles.json"
    )


# ---------------------------------------------------------------------------
# Weight discovery
# ---------------------------------------------------------------------------


def test_default_weights_path_raises_when_missing(monkeypatch, tmp_path):
    """``default_weights_path`` raises FileNotFoundError when neither
    BOXNET_WEIGHTS_DIR nor weights/ contains boxnet.pt — useful as the
    fail-fast signal at plugin boot."""
    monkeypatch.setenv("BOXNET_WEIGHTS_DIR", str(tmp_path))
    from plugin import algorithm

    # Also blank-out the in-package weights/ for the duration of the test
    # by pointing __file__ at tmp_path/algo.py via monkeypatch.
    monkeypatch.setattr(algorithm, "__file__",
                        str(tmp_path / "algorithm.py"))
    with pytest.raises(FileNotFoundError, match="boxnet.pt"):
        algorithm.default_weights_path()


def test_default_weights_path_finds_env_dir_weight(monkeypatch, tmp_path):
    monkeypatch.setenv("BOXNET_WEIGHTS_DIR", str(tmp_path))
    pt_path = tmp_path / "boxnet.pt"
    pt_path.write_bytes(b"")  # presence is what's tested
    from plugin import algorithm

    found = algorithm.default_weights_path()
    assert Path(found) == pt_path.resolve()
