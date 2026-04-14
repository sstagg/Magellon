"""
Template-picker plugin — concrete PluginBase implementation.

Responsibilities:
  - Load MRC files from disk
  - Preprocess (bin, rescale, lowpass, invert)
  - Call the core algorithm
  - Map raw dicts back to validated Pydantic output models
  - Optionally write result artifacts to disk
"""

from __future__ import annotations

import csv
import json
import logging
import os
from typing import Any, Dict, List, Type

import numpy as np
from scipy import ndimage

from models.plugins_models import (
    PluginInfo,
    PluginStatus,
    RequirementResult,
    RecuirementResultEnum,
    TaskCategory,
    PARTICLE_PICKING,
)
from plugins.base import PluginBase
from plugins.progress import NullReporter, ProgressReporter
from plugins.pp.models import (
    ParticlePick,
    TemplatePickerInput,
    TemplatePickerOutput,
)
from plugins.pp.template_picker.algorithm import pick_particles

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# MRC I/O
# ---------------------------------------------------------------------------

def _read_mrc(path: str) -> np.ndarray:
    import mrcfile

    with mrcfile.open(path, permissive=True) as mrc:
        data = np.asarray(mrc.data, dtype=np.float32)
    if data.ndim == 3:
        data = data[0]
    if data.ndim != 2:
        raise ValueError(f"Expected 2D MRC data in {path}, got shape {data.shape}")
    return data


# ---------------------------------------------------------------------------
# Preprocessing helpers
# ---------------------------------------------------------------------------

def _is_power_of_two(value: int) -> bool:
    return value > 0 and (value & (value - 1)) == 0


def _bin_image(image: np.ndarray, bin_factor: int) -> np.ndarray:
    if bin_factor == 1:
        return image
    if not _is_power_of_two(bin_factor):
        raise ValueError("bin_factor must be a power-of-two integer (1,2,4,8,...)")
    height, width = image.shape
    bh = (height // bin_factor) * bin_factor
    bw = (width // bin_factor) * bin_factor
    if bh == 0 or bw == 0:
        raise ValueError("bin_factor is too large for image dimensions")
    cropped = image[:bh, :bw]
    reshaped = cropped.reshape(bh // bin_factor, bin_factor, bw // bin_factor, bin_factor)
    return reshaped.mean(axis=(1, 3), dtype=np.float32)


def _rescale_template(template: np.ndarray, template_apix: float, target_apix: float) -> np.ndarray:
    scale = template_apix / target_apix
    if abs(scale - 1.0) < 1e-6:
        return template
    return ndimage.zoom(template, zoom=scale, order=1)


def _lowpass_gaussian(image: np.ndarray, apix: float, resolution: float | None) -> np.ndarray:
    if resolution is None or resolution <= 0:
        return image
    sigma_pixels = 0.187 * resolution / apix
    if sigma_pixels <= 0:
        return image
    return ndimage.gaussian_filter(image, sigma=sigma_pixels)


# ---------------------------------------------------------------------------
# Output writers
# ---------------------------------------------------------------------------

def _write_particles_csv(path: str, particles: list[dict]) -> None:
    fields = ["x", "y", "score", "stddev", "area", "roundness", "template_index", "angle", "label"]
    with open(path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        for p in particles:
            writer.writerow({k: p.get(k) for k in fields})


# ---------------------------------------------------------------------------
# Plugin implementation
# ---------------------------------------------------------------------------

class TemplatePickerPlugin(PluginBase[TemplatePickerInput, TemplatePickerOutput]):
    """
    FindEM-like FFT template matching particle picker.

    Lifecycle:
        plugin = TemplatePickerPlugin()
        plugin.check_requirements()
        plugin.configure()
        plugin.setup()
        output = plugin.run(input_data)   # or plugin.run(raw_dict)
        plugin.teardown()
    """

    task_category: TaskCategory = PARTICLE_PICKING

    # -- metadata ----------------------------------------------------------

    def get_info(self) -> PluginInfo:
        return PluginInfo(
            name="template-picker",
            developer="Magellon",
            description="FFT-based template matching particle picker with normalized correlation",
            version="1.0.0",
        )

    @classmethod
    def input_schema(cls) -> Type[TemplatePickerInput]:
        return TemplatePickerInput

    @classmethod
    def output_schema(cls) -> Type[TemplatePickerOutput]:
        return TemplatePickerOutput

    # -- lifecycle: requirements -------------------------------------------

    def check_requirements(self) -> List[RequirementResult]:
        results: List[RequirementResult] = []

        # Check mrcfile
        try:
            import mrcfile  # noqa: F401
            results.append(RequirementResult(
                result=RecuirementResultEnum.SUCCESS,
                condition="mrcfile",
                message="mrcfile is available",
            ))
        except ImportError:
            results.append(RequirementResult(
                result=RecuirementResultEnum.FAILURE,
                condition="mrcfile",
                message="mrcfile is not installed",
                instructions="pip install mrcfile",
            ))

        # Check scipy
        try:
            from scipy import ndimage as _nd  # noqa: F401
            results.append(RequirementResult(
                result=RecuirementResultEnum.SUCCESS,
                condition="scipy",
                message="scipy is available",
            ))
        except ImportError:
            results.append(RequirementResult(
                result=RecuirementResultEnum.FAILURE,
                condition="scipy",
                message="scipy is not installed",
                instructions="pip install scipy",
            ))

        all_ok = all(r.result == RecuirementResultEnum.SUCCESS for r in results)
        self._status = PluginStatus.INSTALLED if all_ok else PluginStatus.ERROR
        return results

    # -- lifecycle: execution ----------------------------------------------

    def pre_execute(self, input_data: TemplatePickerInput) -> TemplatePickerInput:
        logger.info(
            "Template picker: image=%s, templates=%d, diameter=%.1f A",
            input_data.image_path,
            len(input_data.template_paths),
            input_data.diameter_angstrom,
        )
        return input_data

    def execute(
        self,
        input_data: TemplatePickerInput,
        *,
        reporter: ProgressReporter = NullReporter(),
    ) -> TemplatePickerOutput:
        # --- Load and preprocess micrograph ---
        reporter.report(5, f"Loading micrograph: {os.path.basename(input_data.image_path)}")
        image = _read_mrc(input_data.image_path)
        binned = _bin_image(image, input_data.bin_factor)
        target_apix = input_data.image_pixel_size * input_data.bin_factor
        filtered_image = _lowpass_gaussian(binned, target_apix, input_data.lowpass_resolution)

        # --- Load and preprocess templates ---
        n_templates = len(input_data.template_paths)
        reporter.report(15, f"Preprocessing {n_templates} template(s)")
        processed_templates: List[np.ndarray] = []
        for idx, path in enumerate(input_data.template_paths):
            tmpl = _read_mrc(path)
            if input_data.invert_templates:
                tmpl = -1.0 * tmpl
            scaled = _rescale_template(tmpl, input_data.template_pixel_size, target_apix)
            filtered = _lowpass_gaussian(scaled, target_apix, input_data.lowpass_resolution)
            processed_templates.append(filtered.astype(np.float32))
            if n_templates > 1:
                pct = 15 + int(15 * (idx + 1) / n_templates)
                reporter.report(pct)

        # --- Build angle ranges ---
        if input_data.angle_ranges is not None:
            if len(input_data.angle_ranges) == 1 and len(processed_templates) > 1:
                ar = input_data.angle_ranges[0]
                angle_ranges = [(ar.start, ar.end, ar.step)] * len(processed_templates)
            elif len(input_data.angle_ranges) == len(processed_templates):
                angle_ranges = [(ar.start, ar.end, ar.step) for ar in input_data.angle_ranges]
            else:
                raise ValueError("angle_ranges must have 1 entry or one per template")
        else:
            angle_ranges = [(0.0, 360.0, 10.0)] * len(processed_templates)

        # --- Run core algorithm ---
        reporter.report(35, "Running FFT correlation and peak extraction")
        result = pick_particles(
            image=filtered_image,
            templates=processed_templates,
            params={
                "diameter_angstrom": input_data.diameter_angstrom,
                "pixel_size_angstrom": target_apix,
                "bin": 1.0,
                "threshold": input_data.threshold,
                "max_threshold": input_data.max_threshold,
                "max_peaks": input_data.max_peaks,
                "overlap_multiplier": input_data.overlap_multiplier,
                "max_blob_size_multiplier": input_data.max_blob_size_multiplier,
                "min_blob_roundness": input_data.min_blob_roundness,
                "peak_position": input_data.peak_position,
                "angle_ranges": angle_ranges,
            },
        )

        raw_particles = result["particles"]
        particles = [ParticlePick(**p) for p in raw_particles]
        reporter.report(90, f"Found {len(particles)} particle(s)")

        # --- Write artifacts if output_dir requested ---
        csv_path = None
        json_path = None
        summary = None

        if input_data.output_dir:
            os.makedirs(input_data.output_dir, exist_ok=True)

            csv_path = os.path.join(input_data.output_dir, "particles.csv")
            _write_particles_csv(csv_path, raw_particles)

            json_path = os.path.join(input_data.output_dir, "particles.json")
            with open(json_path, "w") as f:
                json.dump(raw_particles, f, indent=2)

            summary = {
                "num_templates": len(processed_templates),
                "num_particles": len(particles),
                "target_pixel_size_angstrom": target_apix,
                "image_binning": input_data.bin_factor,
                "lowpass_resolution_angstrom": input_data.lowpass_resolution,
                "invert_templates": input_data.invert_templates,
            }
            with open(os.path.join(input_data.output_dir, "run_summary.json"), "w") as f:
                json.dump(summary, f, indent=2)

        return TemplatePickerOutput(
            particles=particles,
            num_particles=len(particles),
            num_templates=len(processed_templates),
            target_pixel_size=target_apix,
            image_binning=input_data.bin_factor,
            image_shape=[int(filtered_image.shape[0]), int(filtered_image.shape[1])],
            particles_csv_path=csv_path,
            particles_json_path=json_path,
            summary=summary,
        )

    def post_execute(
        self, input_data: TemplatePickerInput, output_data: TemplatePickerOutput
    ) -> TemplatePickerOutput:
        logger.info("Template picker: found %d particles", output_data.num_particles)
        return output_data


# ---------------------------------------------------------------------------
# Convenience function (backwards-compatible with controller)
# ---------------------------------------------------------------------------

# Module-level singleton — setup once, reuse across requests
_plugin_instance: TemplatePickerPlugin | None = None


def _get_plugin() -> TemplatePickerPlugin:
    global _plugin_instance
    if _plugin_instance is None:
        _plugin_instance = TemplatePickerPlugin()
        _plugin_instance.check_requirements()
        _plugin_instance.configure()
        _plugin_instance.setup()
    return _plugin_instance


def run_template_picker(
    input_data: TemplatePickerInput,
    *,
    reporter: ProgressReporter | None = None,
) -> TemplatePickerOutput:
    """Convenience wrapper — the controller calls this."""
    return _get_plugin().run(input_data, reporter=reporter)


# ---------------------------------------------------------------------------
# Batch helpers — let callers preprocess templates once and reuse across many
# images. MRC read + rescale + lowpass is the bulk of cold-start cost; the
# per-image step is just the FFT + correlation.
# ---------------------------------------------------------------------------

def preprocess_templates(
    input_data: TemplatePickerInput,
    target_apix: float,
) -> tuple[List[np.ndarray], List[tuple[float, float, float]]]:
    """Return (processed_templates, angle_ranges) ready for `pick_particles`."""
    processed: List[np.ndarray] = []
    for path in input_data.template_paths:
        tmpl = _read_mrc(path)
        if input_data.invert_templates:
            tmpl = -1.0 * tmpl
        scaled = _rescale_template(tmpl, input_data.template_pixel_size, target_apix)
        filtered = _lowpass_gaussian(scaled, target_apix, input_data.lowpass_resolution)
        processed.append(filtered.astype(np.float32))

    if input_data.angle_ranges is not None:
        if len(input_data.angle_ranges) == 1 and len(processed) > 1:
            ar = input_data.angle_ranges[0]
            angle_ranges = [(ar.start, ar.end, ar.step)] * len(processed)
        elif len(input_data.angle_ranges) == len(processed):
            angle_ranges = [(ar.start, ar.end, ar.step) for ar in input_data.angle_ranges]
        else:
            raise ValueError("angle_ranges must have 1 entry or one per template")
    else:
        angle_ranges = [(0.0, 360.0, 10.0)] * len(processed)

    return processed, angle_ranges


def pick_in_image(
    image_path: str,
    processed_templates: List[np.ndarray],
    angle_ranges: List[tuple[float, float, float]],
    input_data: TemplatePickerInput,
    target_apix: float,
) -> tuple[List[dict], tuple[int, int]]:
    """Run the per-image picking step using already-preprocessed templates.

    Returns (raw_particle_dicts, filtered_image_shape).
    """
    image = _read_mrc(image_path)
    binned = _bin_image(image, input_data.bin_factor)
    filtered_image = _lowpass_gaussian(binned, target_apix, input_data.lowpass_resolution)

    result = pick_particles(
        image=filtered_image,
        templates=processed_templates,
        params={
            "diameter_angstrom": input_data.diameter_angstrom,
            "pixel_size_angstrom": target_apix,
            "bin": 1.0,
            "threshold": input_data.threshold,
            "max_threshold": input_data.max_threshold,
            "max_peaks": input_data.max_peaks,
            "overlap_multiplier": input_data.overlap_multiplier,
            "max_blob_size_multiplier": input_data.max_blob_size_multiplier,
            "min_blob_roundness": input_data.min_blob_roundness,
            "peak_position": input_data.peak_position,
            "angle_ranges": angle_ranges,
        },
    )
    return result["particles"], (int(filtered_image.shape[0]), int(filtered_image.shape[1]))
