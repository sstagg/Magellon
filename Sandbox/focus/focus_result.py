"""JSON-safe result serialization for autofocus runs."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Optional

import numpy as np

from .correlation import ShiftResult
from .objective_focus import BeamTiltMeasurement, ObjectiveFocusResult
from .z_focus import StageTiltMeasurement, StageZResult


RESULT_SCHEMA_VERSION = 1


def objective_result_to_json_dict(
    result: ObjectiveFocusResult,
    *,
    metadata: Optional[Mapping[str, Any]] = None,
) -> dict[str, Any]:
    """Convert an objective-focus result to a JSON-safe audit dictionary."""

    return _base_result("objective_focus", metadata) | {
        "result": {
            "defocus": _json_safe(result.defocus),
            "stigx": _json_safe(result.stigx),
            "stigy": _json_safe(result.stigy),
            "residual": _json_safe(result.residual),
            "residual_vector": _array_to_list(result.residual_vector),
            "rank": result.rank,
            "unknown_count": result.unknown_count,
            "singular_values": _array_to_list(result.singular_values),
            "condition_number": result.condition_number,
            "measurements": [_beam_tilt_measurement_to_dict(m) for m in result.measurements],
            "shift_results": [_shift_result_to_dict(s) for s in result.shift_results],
            "quality": {
                "min_snr_observed": _json_safe(result.min_snr_observed),
                "min_peak_ratio_observed": _json_safe(result.min_peak_ratio_observed),
                "min_normalized_ccc_observed": _json_safe(result.min_normalized_ccc_observed),
            },
        },
        "diagnostics": {
            "design_shape": list(result.diagnostics.design.shape),
            "observed": _array_to_list(result.diagnostics.observed),
            "predicted": _array_to_list(result.diagnostics.predicted),
            "residual_vector": _array_to_list(result.diagnostics.residual_vector),
        },
    }


def stage_z_result_to_json_dict(
    result: StageZResult,
    *,
    metadata: Optional[Mapping[str, Any]] = None,
) -> dict[str, Any]:
    """Convert a stage-Z result to a JSON-safe audit dictionary."""

    return _base_result("stage_z", metadata) | {
        "result": {
            "z": _json_safe(result.z),
            "z_values": _array_to_list(result.z_values),
            "stage_xy": [_vector_to_list(value) for value in result.stage_xy],
            "z_std": _json_safe(result.z_std),
            "z_range": _json_safe(result.z_range),
            "measurement_count": result.measurement_count,
            "measurements": [_stage_tilt_measurement_to_dict(m) for m in result.measurements],
            "shift_results": [_shift_result_to_dict(s) for s in result.shift_results],
            "quality": {
                "min_snr_observed": _json_safe(result.min_snr_observed),
                "min_peak_ratio_observed": _json_safe(result.min_peak_ratio_observed),
                "min_normalized_ccc_observed": _json_safe(result.min_normalized_ccc_observed),
            },
        },
    }


def save_focus_result_json(path: str | Path, payload: Mapping[str, Any]) -> None:
    """Write a JSON-safe autofocus result payload to disk."""

    with Path(path).open("w", encoding="utf-8") as stream:
        json.dump(payload, stream, indent=2, sort_keys=True, allow_nan=False)
        stream.write("\n")


def _base_result(kind: str, metadata: Optional[Mapping[str, Any]]) -> dict[str, Any]:
    return {
        "schema_version": RESULT_SCHEMA_VERSION,
        "kind": kind,
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "metadata": _json_safe(metadata or {}),
    }


def _beam_tilt_measurement_to_dict(measurement: Any) -> dict[str, Any]:
    if not isinstance(measurement, BeamTiltMeasurement):
        return _json_safe(measurement)
    return {
        "tilt_delta": _vector_to_list(measurement.tilt_delta),
        "pixel_shift": _vector_to_list(measurement.pixel_shift),
    }


def _stage_tilt_measurement_to_dict(measurement: Any) -> dict[str, Any]:
    if not isinstance(measurement, StageTiltMeasurement):
        return _json_safe(measurement)
    return {
        "alpha": _json_safe(float(measurement.alpha)),
        "pixel_shift": _vector_to_list(measurement.pixel_shift),
    }


def _shift_result_to_dict(shift: Any) -> dict[str, Any]:
    if not isinstance(shift, ShiftResult):
        return _json_safe(shift)
    return {
        "shift": _vector_to_list(shift.shift),
        "peak": _vector_to_list(shift.peak),
        "peak_value": _json_safe(float(shift.peak_value)),
        "snr": _json_safe(float(shift.snr)),
        "peak_ratio": _json_safe(float(shift.peak_ratio)),
        "normalized_ccc": _json_safe(float(shift.normalized_ccc)),
        "correlation_shape": list(shift.correlation.shape),
    }


def _array_to_list(value: np.ndarray) -> list[Any]:
    return _json_safe(np.asarray(value).tolist())


def _vector_to_list(value: Any) -> list[float]:
    array = np.asarray(value, dtype=np.float64)
    if array.ndim != 1:
        raise ValueError("expected a vector value")
    return [float(item) for item in array]


def _json_safe(value: Any) -> Any:
    if isinstance(value, np.ndarray):
        return _json_safe(value.tolist())
    if isinstance(value, np.generic):
        return _json_safe(value.item())
    if isinstance(value, Mapping):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, tuple):
        return [_json_safe(item) for item in value]
    if isinstance(value, list):
        return [_json_safe(item) for item in value]
    if isinstance(value, float):
        return value if np.isfinite(value) else None
    if value is None or isinstance(value, (str, int, bool)):
        return value
    return str(value)
