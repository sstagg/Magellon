"""JSON configuration for the focus algorithms."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional, Tuple

import numpy as np

from .focus_pipeline import ObjectiveCalibration


Vector2 = Tuple[float, float]
BeamTiltPair = Tuple[Vector2, Vector2]


@dataclass(frozen=True)
class ObjectiveFocusSettings:
    """Runtime settings for beam-tilt objective autofocus."""

    mode: str = "beam_tilt_pair"
    camera_binning: Vector2 = (1.0, 1.0)
    correlation_type: str = "phase"
    subpixel_window: int = 5
    taper_fraction: float = 0.1
    pad_fraction: float = 0.0
    lowpass: float = 0.0
    zero_origin: bool = False
    min_snr: float = 0.0
    min_peak_ratio: float = 0.0
    min_normalized_ccc: float = -1.0
    validate: bool = True
    max_condition_number: float = 1.0e12
    beam_tilt_pairs: Tuple[BeamTiltPair, ...] = (((0.0, 0.0), (0.01, 0.0)),)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ObjectiveFocusSettings":
        allowed = set(cls.__dataclass_fields__)
        extra = set(data) - allowed
        if extra:
            raise ValueError(f"unknown objective_focus settings: {sorted(extra)}")
        values = dict(data)
        if "camera_binning" in values:
            values["camera_binning"] = _vector2(values["camera_binning"], "objective_focus.camera_binning")
        if "beam_tilt_pairs" in values:
            values["beam_tilt_pairs"] = tuple(
                (_vector2(pair[0], "objective_focus.beam_tilt_pairs.first"), _vector2(pair[1], "objective_focus.beam_tilt_pairs.second"))
                for pair in values["beam_tilt_pairs"]
            )
        settings = cls(**values)
        settings.validate_settings()
        return settings

    def validate_settings(self) -> None:
        if self.mode not in {"beam_tilt_pair", "beam_tilt_triple"}:
            raise ValueError("objective_focus.mode must be 'beam_tilt_pair' or 'beam_tilt_triple'")
        _validate_common_correlation(self)
        if not self.beam_tilt_pairs:
            raise ValueError("objective_focus.beam_tilt_pairs must not be empty")

    def pipeline_kwargs(self) -> dict[str, Any]:
        return {
            "camera_binning": self.camera_binning,
            "correlation_type": self.correlation_type,
            "subpixel_window": self.subpixel_window,
            "taper_fraction": self.taper_fraction,
            "pad_fraction": self.pad_fraction,
            "lowpass": self.lowpass,
            "zero_origin": self.zero_origin,
            "min_snr": self.min_snr,
            "min_peak_ratio": self.min_peak_ratio,
            "min_normalized_ccc": self.min_normalized_ccc,
            "validate": self.validate,
            "max_condition_number": self.max_condition_number,
        }


@dataclass(frozen=True)
class StageZSettings:
    """Runtime settings for stage-tilt Z measurement."""

    camera_binning: Vector2 = (1.0, 1.0)
    alphas: Tuple[float, ...] = (-0.1, 0.1)
    alpha_for_matrix: float = 0.0
    correlation_type: str = "phase"
    subpixel_window: int = 5
    taper_fraction: float = 0.1
    pad_fraction: float = 0.0
    lowpass: float = 0.0
    zero_origin: bool = False
    min_snr: float = 0.0
    min_peak_ratio: float = 0.0
    min_normalized_ccc: float = -1.0

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "StageZSettings":
        allowed = set(cls.__dataclass_fields__)
        extra = set(data) - allowed
        if extra:
            raise ValueError(f"unknown stage_z settings: {sorted(extra)}")
        values = dict(data)
        if "camera_binning" in values:
            values["camera_binning"] = _vector2(values["camera_binning"], "stage_z.camera_binning")
        if "alphas" in values:
            values["alphas"] = tuple(float(value) for value in values["alphas"])
        settings = cls(**values)
        settings.validate_settings()
        return settings

    def validate_settings(self) -> None:
        _validate_common_correlation(self)
        if not self.alphas:
            raise ValueError("stage_z.alphas must not be empty")
        if not np.all(np.isfinite(self.alphas)):
            raise ValueError("stage_z.alphas must contain finite values")
        if abs(np.cos(self.alpha_for_matrix)) < 1.0e-12:
            raise ValueError("stage_z.alpha_for_matrix is too close to 90 degrees")

    def pipeline_kwargs(self) -> dict[str, Any]:
        return {
            "camera_binning": self.camera_binning,
            "alpha_for_matrix": self.alpha_for_matrix,
            "correlation_type": self.correlation_type,
            "subpixel_window": self.subpixel_window,
            "taper_fraction": self.taper_fraction,
            "pad_fraction": self.pad_fraction,
            "lowpass": self.lowpass,
            "zero_origin": self.zero_origin,
            "min_snr": self.min_snr,
            "min_peak_ratio": self.min_peak_ratio,
            "min_normalized_ccc": self.min_normalized_ccc,
        }


@dataclass(frozen=True)
class FocusRuntimeConfig:
    """Runtime focus settings loaded from JSON."""

    objective_focus: ObjectiveFocusSettings = field(default_factory=ObjectiveFocusSettings)
    stage_z: StageZSettings = field(default_factory=StageZSettings)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "FocusRuntimeConfig":
        allowed = {"objective_focus", "stage_z"}
        extra = set(data) - allowed
        if extra:
            raise ValueError(f"unknown runtime config sections: {sorted(extra)}")
        return cls(
            objective_focus=ObjectiveFocusSettings.from_dict(data.get("objective_focus", {})),
            stage_z=StageZSettings.from_dict(data.get("stage_z", {})),
        )


@dataclass(frozen=True)
class FocusCalibrationConfig:
    """Calibration matrices loaded from JSON."""

    objective_focus: ObjectiveCalibration
    stage_matrix: np.ndarray

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "FocusCalibrationConfig":
        allowed = {"objective_focus", "stage_z"}
        extra = set(data) - allowed
        if extra:
            raise ValueError(f"unknown calibration config sections: {sorted(extra)}")

        objective = data.get("objective_focus", {})
        stage = data.get("stage_z", {})
        defocus_matrix = _matrix2(objective.get("defocus_matrix"), "objective_focus.defocus_matrix")
        stigx_matrix = _optional_matrix2(objective.get("stigx_matrix"), "objective_focus.stigx_matrix")
        stigy_matrix = _optional_matrix2(objective.get("stigy_matrix"), "objective_focus.stigy_matrix")
        if (stigx_matrix is None) != (stigy_matrix is None):
            raise ValueError("objective_focus.stigx_matrix and stigy_matrix must be provided together")
        return cls(
            objective_focus=ObjectiveCalibration(defocus_matrix, stigx_matrix, stigy_matrix),
            stage_matrix=_matrix2(stage.get("stage_matrix"), "stage_z.stage_matrix"),
        )


def load_focus_runtime_config(path: str | Path) -> FocusRuntimeConfig:
    """Load runtime focus settings from a JSON file."""

    return FocusRuntimeConfig.from_dict(_load_json_object(path))


def load_focus_calibration_config(path: str | Path) -> FocusCalibrationConfig:
    """Load focus calibration matrices from a JSON file."""

    return FocusCalibrationConfig.from_dict(_load_json_object(path))


def _load_json_object(path: str | Path) -> dict[str, Any]:
    with Path(path).open("r", encoding="utf-8") as stream:
        data = json.load(stream)
    if not isinstance(data, dict):
        raise ValueError("focus config JSON root must be an object")
    return data


def _validate_common_correlation(settings: Any) -> None:
    if settings.correlation_type not in {"phase", "cross"}:
        raise ValueError("correlation_type must be 'phase' or 'cross'")
    if settings.subpixel_window < 3 or settings.subpixel_window % 2 == 0:
        raise ValueError("subpixel_window must be an odd integer >= 3")
    if not np.all(
        np.isfinite(
            (
                settings.camera_binning[0],
                settings.camera_binning[1],
                settings.taper_fraction,
                settings.pad_fraction,
                settings.lowpass,
                settings.min_snr,
                settings.min_peak_ratio,
                settings.min_normalized_ccc,
            )
        )
    ):
        raise ValueError("focus settings must contain finite numeric values")
    if settings.camera_binning[0] <= 0.0 or settings.camera_binning[1] <= 0.0:
        raise ValueError("camera_binning values must be positive")
    if not 0.0 <= settings.taper_fraction <= 0.5:
        raise ValueError("taper_fraction must be in [0.0, 0.5]")
    if settings.pad_fraction < 0.0:
        raise ValueError("pad_fraction must be non-negative")
    if settings.lowpass < 0.0:
        raise ValueError("lowpass must be non-negative")


def _vector2(value: Any, name: str) -> Vector2:
    array = np.asarray(value, dtype=np.float64)
    if array.shape != (2,) or not np.all(np.isfinite(array)):
        raise ValueError(f"{name} must contain exactly two finite values")
    return (float(array[0]), float(array[1]))


def _matrix2(value: Any, name: str) -> np.ndarray:
    if value is None:
        raise ValueError(f"{name} is required")
    array = np.asarray(value, dtype=np.float64)
    if array.shape != (2, 2) or not np.all(np.isfinite(array)):
        raise ValueError(f"{name} must be a finite 2x2 matrix")
    return array


def _optional_matrix2(value: Any, name: str) -> Optional[np.ndarray]:
    if value is None:
        return None
    return _matrix2(value, name)

