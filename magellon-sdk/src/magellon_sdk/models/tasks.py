"""Task envelope and task-data DTOs shared across CoreService and plugins.

The shapes here used to live in ``core/model_dto.py`` inside each plugin
(and in ``models/plugins_models.py`` inside CoreService). They are
consolidated here so that plugin-contract fields only change in one
place.

Plugin-specific task-data subclasses (e.g. a plugin's own input schema)
should still live in the plugin — subclass :class:`CryoEmImageTaskData`
and pair it with a :class:`TaskDto` subclass as :class:`FftTask` /
:class:`CtfTask` below do.
"""
from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


class TaskCategory(BaseModel):
    code: int
    name: str
    description: str

    def __hash__(self) -> int:
        return hash(self.code)

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, TaskCategory):
            return False
        return self.code == other.code


class TaskStatus(BaseModel):
    code: int
    name: str
    description: str


class TaskOutcome(BaseModel):
    code: int
    message: str
    description: str
    output_data: Dict[str, Any] = {}


class TaskBase(BaseModel):
    id: Optional[UUID] = None
    session_id: Optional[UUID] = None
    session_name: Optional[str] = None
    worker_instance_id: Optional[UUID] = None
    data: Dict[str, Any]
    status: Optional[TaskStatus] = None
    type: Optional[TaskCategory] = None
    created_date: Optional[datetime] = Field(default_factory=_now_utc)
    start_on: Optional[datetime] = None
    end_on: Optional[datetime] = None
    result: Optional[TaskOutcome] = None
    target_backend: Optional[str] = None
    """When set, the dispatcher routes this task only to a live plugin
    whose ``PluginManifest.backend_id`` matches. Unset (the default)
    keeps today's category-wide round-robin. Added in SDK 1.3."""

    subject_kind: Optional[str] = None
    """The kind of thing this task operates on. One of:
    ``'image' | 'particle_stack' | 'session' | 'run' | 'artifact'``.
    Pre-Phase-3 callers leave this ``None`` and rely on
    ``data['image_id']`` — the runner falls back to that on subject
    extraction. Per ratified rule 4 this is a string, not a
    typed enum, so adding a kind doesn't churn the contract."""

    subject_id: Optional[UUID] = None
    """The id of the entity ``subject_kind`` names. For
    ``subject_kind='image'`` this mirrors ``data['image_id']`` for
    back-compat; for ``subject_kind='particle_stack'`` this is the
    artifact UUID. Pre-Phase-3 callers leave it ``None``."""

    @classmethod
    def calculate_data_hash(cls, data: Dict[str, Any]) -> str:
        data_str = str(data)
        return hashlib.sha256(data_str.encode("utf-8")).hexdigest()


class TaskMessage(TaskBase):
    """The wire envelope a dispatcher publishes. SDK 1.3+ canonical name.

    Wraps a category-shaped ``data`` payload with routing-time metadata
    (``job_id``, ``type``, ``status``, optional ``target_backend``).
    Pre-1.3 callers know it as ``TaskDto`` — the alias at the bottom
    of this module keeps that name working through 1.x.
    """

    job_id: Optional[UUID] = Field(default_factory=uuid4)

    @classmethod
    def create(
        cls,
        pid: UUID,
        job_id: UUID,
        ptype: TaskCategory,
        pstatus: TaskStatus,
        instance_id: UUID,
        data: Dict[str, Any],
    ) -> "TaskMessage":
        return cls(
            id=pid,
            job_id=job_id,
            worker_instance_id=instance_id,
            created_date=_now_utc(),
            status=pstatus,
            type=ptype,
            data=data,
        )


class JobMessage(TaskBase):
    """Bundle of tasks under one logical user-visible unit. SDK 1.3+ name.

    Pre-1.3 callers know it as ``JobDto``."""

    tasks: List[TaskMessage] = []

    @classmethod
    def create(cls, pdata: Dict[str, Any], ptype: TaskCategory) -> "JobMessage":
        return cls(
            id=uuid4(),
            data=pdata,
            created_date=_now_utc(),
            status=TaskStatus(code=0, name="pending", description="Job is pending"),
            type=ptype,
        )


class CryoEmImageInput(BaseModel):
    """Base for category input shapes that operate on a single image.

    Renamed from ``CryoEmImageTaskData`` in SDK 1.3 to symmetrize with
    the existing ``*Output`` naming. The old name aliases the new one
    at module bottom, so existing plugins keep importing it unchanged."""

    image_id: Optional[UUID] = None
    image_name: Optional[str] = None
    image_path: Optional[str] = None
    # Contravariant-input escape hatch: plugin-specific knobs that
    # the category contract doesn't know about. Every subclass
    # inherits this so CtfInput, FftInput, etc. all support
    # engine-specific extras without the category schema growing.
    # Opaque to the backend — round-trips untouched.
    engine_opts: Dict[str, Any] = Field(default_factory=dict)


class MrcToPngInput(CryoEmImageInput):
    image_target: Optional[str] = None
    frame_name: Optional[str] = None
    frame_path: Optional[str] = None


class FftInput(CryoEmImageInput):
    target_name: Optional[str] = Field(
        default=None,
        description="Output filename stem for the FFT image (PNG).",
        json_schema_extra={
            "ui_widget": "text",
            "ui_group": "Output",
            "ui_order": 1,
            "ui_placeholder": "fft.png",
        },
    )
    target_path: Optional[str] = Field(
        default=None,
        description="Absolute output path. Auto-derived from session paths when omitted.",
        json_schema_extra={
            "ui_widget": "file_path",
            "ui_group": "Output",
            "ui_order": 2,
            "ui_advanced": True,
        },
    )
    frame_name: Optional[str] = Field(
        default=None,
        description="Source frame stem (when FFT'ing a frame rather than the micrograph).",
        json_schema_extra={
            "ui_widget": "text",
            "ui_group": "Frames",
            "ui_order": 1,
            "ui_advanced": True,
        },
    )
    frame_path: Optional[str] = Field(
        default=None,
        description="Absolute path to the source frame.",
        json_schema_extra={
            "ui_widget": "file_path",
            "ui_group": "Frames",
            "ui_order": 2,
            "ui_advanced": True,
            "ui_file_ext": [".mrc", ".tif", ".tiff", ".eer"],
        },
    )


class TopazPickInput(CryoEmImageInput):
    """Input for the Topaz particle-picking category.

    The MRC to pick is at ``input_file``. Engine knobs (model, NMS radius,
    score threshold, preprocess scale) ride on the inherited
    ``engine_opts`` dict so the canonical category contract stays narrow.
    Defaults match the Topaz tutorial: model=resnet16, radius=14,
    threshold=-3, scale=8.
    """

    input_file: str = Field(
        ...,
        description="Absolute path to the micrograph (.mrc) to pick.",
        json_schema_extra={
            "ui_widget": "file_path",
            "ui_group": "Input",
            "ui_order": 1,
            "ui_file_ext": [".mrc", ".mrcs"],
        },
    )


class MicrographDenoiseInput(CryoEmImageInput):
    """Input for the Topaz-Denoise category — one MRC in, denoised MRC out.

    ``input_file`` is the source. ``output_file`` is where the plugin
    writes the denoised MRC; defaults to ``<input>_denoised.mrc`` when
    omitted. Engine knobs (model, patch_size) ride on ``engine_opts``.
    """

    input_file: str = Field(
        ...,
        description="Source micrograph (.mrc) to denoise.",
        json_schema_extra={
            "ui_widget": "file_path",
            "ui_group": "Input",
            "ui_order": 1,
            "ui_file_ext": [".mrc"],
        },
    )
    output_file: Optional[str] = Field(
        default=None,
        description="Where to write the denoised MRC. Defaults to "
                    "<input>_denoised.mrc next to the source.",
        json_schema_extra={
            "ui_widget": "file_path",
            "ui_group": "Output",
            "ui_order": 1,
            "ui_advanced": True,
        },
    )


class PtolemyInput(CryoEmImageInput):
    """Input for either ptolemy category — just the MRC to analyze.

    The same shape serves both square-detection (low-mag MRC) and
    hole-detection (med-mag MRC). The category chosen by the caller
    tells the plugin which pipeline to run; no type discriminator
    field is needed in the body.
    """

    input_file: str = Field(
        ...,
        description="Absolute path to the MRC for square / hole detection.",
        json_schema_extra={
            "ui_widget": "file_path",
            "ui_group": "Input",
            "ui_order": 1,
            "ui_file_ext": [".mrc"],
        },
    )


class CtfInput(CryoEmImageInput):
    inputFile: str = Field(
        ...,
        description="Absolute path to the micrograph (.mrc) to estimate CTF for.",
        json_schema_extra={
            "ui_widget": "file_path",
            "ui_group": "Input",
            "ui_order": 1,
            "ui_file_ext": [".mrc"],
        },
    )
    outputFile: str = Field(
        default="output.mrc",
        description="Output filename stem for CTF results (text + diagnostic image).",
        json_schema_extra={
            "ui_widget": "text",
            "ui_group": "Output",
            "ui_order": 1,
            "ui_advanced": True,
        },
    )
    pixelSize: float = Field(
        default=1.0,
        gt=0.0,
        description="Pixel size at the detector level (after any binning).",
        json_schema_extra={
            "ui_widget": "number",
            "ui_group": "Microscope",
            "ui_order": 1,
            "ui_step": 0.01,
            "ui_unit": "Å",
            "ui_help": "Detector pixel size in Ångström. Wrong value shifts every "
                       "downstream estimate — verify against the microscope's "
                       "calibration table.",
        },
    )
    accelerationVoltage: float = Field(
        default=300.0,
        gt=0.0,
        description="Microscope accelerating voltage.",
        json_schema_extra={
            "ui_widget": "select",
            "ui_group": "Microscope",
            "ui_order": 2,
            "ui_unit": "kV",
            "ui_options": [80.0, 100.0, 120.0, 200.0, 300.0],
        },
    )
    sphericalAberration: float = Field(
        default=2.70,
        ge=0.0,
        description="Spherical aberration coefficient (Cs).",
        json_schema_extra={
            "ui_widget": "number",
            "ui_group": "Microscope",
            "ui_order": 3,
            "ui_step": 0.01,
            "ui_unit": "mm",
            "ui_advanced": True,
        },
    )
    amplitudeContrast: float = Field(
        default=0.07,
        ge=0.0,
        le=1.0,
        description="Amplitude contrast fraction (typical 0.07–0.10 for cryo).",
        json_schema_extra={
            "ui_widget": "slider",
            "ui_group": "Microscope",
            "ui_order": 4,
            "ui_step": 0.01,
            "ui_marks": [
                {"value": 0.07, "label": "0.07"},
                {"value": 0.10, "label": "0.10"},
            ],
            "ui_advanced": True,
        },
    )
    sizeOfAmplitudeSpectrum: int = Field(
        default=512,
        gt=0,
        description="Box size for the amplitude spectrum (power-of-two recommended).",
        json_schema_extra={
            "ui_widget": "select",
            "ui_group": "Search",
            "ui_order": 1,
            "ui_options": [256, 512, 1024, 2048],
            "ui_unit": "px",
            "ui_advanced": True,
        },
    )
    minimumResolution: float = Field(
        default=30.0,
        gt=0.0,
        description="Low-resolution limit of the fit (lower frequencies ignored).",
        json_schema_extra={
            "ui_widget": "number",
            "ui_group": "Search",
            "ui_order": 2,
            "ui_step": 1.0,
            "ui_unit": "Å",
        },
    )
    maximumResolution: float = Field(
        default=5.0,
        gt=0.0,
        description="High-resolution limit of the fit.",
        json_schema_extra={
            "ui_widget": "number",
            "ui_group": "Search",
            "ui_order": 3,
            "ui_step": 0.5,
            "ui_unit": "Å",
        },
    )
    minimumDefocus: float = Field(
        default=5000.0,
        ge=0.0,
        description="Minimum defocus to consider during the search.",
        json_schema_extra={
            "ui_widget": "number",
            "ui_group": "Defocus search",
            "ui_order": 1,
            "ui_step": 500.0,
            "ui_unit": "Å",
            "ui_tunable": True,
        },
    )
    maximumDefocus: float = Field(
        default=50000.0,
        ge=0.0,
        description="Maximum defocus to consider.",
        json_schema_extra={
            "ui_widget": "number",
            "ui_group": "Defocus search",
            "ui_order": 2,
            "ui_step": 500.0,
            "ui_unit": "Å",
            "ui_tunable": True,
        },
    )
    defocusSearchStep: float = Field(
        default=100.0,
        gt=0.0,
        description="Defocus search granularity. Smaller is more accurate but slower.",
        json_schema_extra={
            "ui_widget": "slider",
            "ui_group": "Defocus search",
            "ui_order": 3,
            "ui_step": 50.0,
            "ui_unit": "Å",
            "ui_marks": [
                {"value": 50, "label": "50"},
                {"value": 100, "label": "100"},
                {"value": 500, "label": "500"},
                {"value": 1000, "label": "1000"},
            ],
            "ui_tunable": True,
        },
    )
    binning_x: int = Field(
        default=1,
        ge=1,
        description="Detector binning factor (1 = no binning).",
        json_schema_extra={
            "ui_widget": "select",
            "ui_group": "Microscope",
            "ui_order": 5,
            "ui_options": [1, 2, 4, 8],
            "ui_advanced": True,
        },
    )


class MotionCorInput(CryoEmImageInput):
    InMrc: Optional[str] = Field(
        default=None,
        description="MRC frame stack input (-InMrc).",
        json_schema_extra={
            "ui_widget": "file_path",
            "ui_group": "Frames",
            "ui_order": 1,
            "ui_file_ext": [".mrc", ".mrcs"],
        },
    )
    InTiff: Optional[str] = Field(
        default=None,
        description="TIFF frame stack input (-InTiff). Mutually exclusive with InMrc/InEer.",
        json_schema_extra={
            "ui_widget": "file_path",
            "ui_group": "Frames",
            "ui_order": 2,
            "ui_file_ext": [".tif", ".tiff"],
        },
    )
    InEer: Optional[str] = Field(
        default=None,
        description="EER frame stack input (-InEer). Set EerSampling below.",
        json_schema_extra={
            "ui_widget": "file_path",
            "ui_group": "Frames",
            "ui_order": 3,
            "ui_file_ext": [".eer"],
        },
    )
    inputFile: str = Field(
        ...,
        description="Canonical input path (matches the active In{Mrc,Tiff,Eer}).",
        json_schema_extra={
            "ui_widget": "hidden",
        },
    )
    OutMrc: str = Field(
        default="output.mrc",
        description="Output filename for the aligned, dose-weighted sum.",
        json_schema_extra={
            "ui_widget": "text",
            "ui_group": "Output",
            "ui_order": 1,
        },
    )
    Gain: str = Field(
        ...,
        description="Gain reference image — REQUIRED for accurate alignment.",
        json_schema_extra={
            "ui_widget": "file_path",
            "ui_group": "Calibration",
            "ui_order": 1,
            "ui_file_ext": [".mrc", ".dm4"],
        },
    )
    Dark: Optional[str] = Field(
        default=None,
        description="Dark reference image (optional, K3/Falcon).",
        json_schema_extra={
            "ui_widget": "file_path",
            "ui_group": "Calibration",
            "ui_order": 2,
            "ui_advanced": True,
        },
    )
    DefectFile: Optional[str] = Field(
        default=None,
        description="Detector defect map (text file with rows/cols to mask).",
        json_schema_extra={
            "ui_widget": "file_path",
            "ui_group": "Calibration",
            "ui_order": 3,
            "ui_advanced": True,
        },
    )
    DefectMap: Optional[str] = Field(
        default=None,
        description="Defect map as MRC (alternative to DefectFile).",
        json_schema_extra={
            "ui_widget": "file_path",
            "ui_group": "Calibration",
            "ui_order": 4,
            "ui_advanced": True,
        },
    )
    PatchesX: int = Field(
        default=1,
        ge=1,
        description="Local-alignment patch count, X axis. Typical: 5–7 for thick samples.",
        json_schema_extra={
            "ui_widget": "slider",
            "ui_group": "Local alignment",
            "ui_order": 1,
            "ui_step": 1,
            "ui_marks": [
                {"value": 1, "label": "1 (global)"},
                {"value": 5, "label": "5"},
                {"value": 9, "label": "9"},
            ],
            "ui_tunable": True,
        },
    )
    PatchesY: int = Field(
        default=1,
        ge=1,
        description="Local-alignment patch count, Y axis.",
        json_schema_extra={
            "ui_widget": "slider",
            "ui_group": "Local alignment",
            "ui_order": 2,
            "ui_step": 1,
            "ui_marks": [
                {"value": 1, "label": "1"},
                {"value": 5, "label": "5"},
                {"value": 9, "label": "9"},
            ],
            "ui_tunable": True,
        },
    )
    Iter: int = Field(
        default=5,
        ge=1,
        description="Maximum alignment iterations.",
        json_schema_extra={
            "ui_widget": "number",
            "ui_group": "Alignment",
            "ui_order": 1,
            "ui_advanced": True,
        },
    )
    Tol: float = Field(
        default=0.5,
        gt=0.0,
        description="Convergence tolerance (pixels).",
        json_schema_extra={
            "ui_widget": "number",
            "ui_group": "Alignment",
            "ui_order": 2,
            "ui_step": 0.1,
            "ui_unit": "px",
            "ui_advanced": True,
        },
    )
    Bft: int = Field(
        default=100,
        ge=0,
        description="B-factor for low-pass filtering during alignment.",
        json_schema_extra={
            "ui_widget": "number",
            "ui_group": "Alignment",
            "ui_order": 3,
            "ui_unit": "Å²",
            "ui_advanced": True,
        },
    )
    LogDir: str = Field(
        default=".",
        description="Where MotionCor writes its per-job log.",
        json_schema_extra={
            "ui_widget": "file_path",
            "ui_group": "Output",
            "ui_order": 2,
            "ui_advanced": True,
        },
    )
    Gpu: str = Field(
        default="0",
        description="GPU index(es), space-separated (e.g. '0 1' for 2-GPU run).",
        json_schema_extra={
            "ui_widget": "text",
            "ui_group": "Runtime",
            "ui_order": 1,
            "ui_placeholder": "0",
        },
    )
    FtBin: float = Field(
        default=2,
        gt=0.0,
        description="Fourier-cropping factor (1=no crop, 2=half-size sums).",
        json_schema_extra={
            "ui_widget": "select",
            "ui_group": "Runtime",
            "ui_order": 2,
            "ui_options": [1, 1.5, 2, 4],
        },
    )
    FmDose: Optional[float] = Field(
        default=None,
        description="Per-frame dose (e-/Å²). Required for dose weighting.",
        json_schema_extra={
            "ui_widget": "number",
            "ui_group": "Dose weighting",
            "ui_order": 1,
            "ui_step": 0.1,
            "ui_unit": "e⁻/Å²",
        },
    )
    PixSize: Optional[float] = Field(
        default=None,
        description="Pixel size at the detector. Overrides MRC header when set.",
        json_schema_extra={
            "ui_widget": "number",
            "ui_group": "Microscope",
            "ui_order": 1,
            "ui_step": 0.01,
            "ui_unit": "Å",
        },
    )
    kV: int = Field(
        default=300,
        gt=0,
        description="Accelerating voltage.",
        json_schema_extra={
            "ui_widget": "select",
            "ui_group": "Microscope",
            "ui_order": 2,
            "ui_options": [80, 100, 120, 200, 300],
            "ui_unit": "kV",
        },
    )
    Cs: int = Field(
        default=0,
        ge=0,
        description="Spherical aberration (mm). 0 lets MotionCor skip the CTF correction step.",
        json_schema_extra={
            "ui_widget": "number",
            "ui_group": "Microscope",
            "ui_order": 3,
            "ui_unit": "mm",
            "ui_advanced": True,
        },
    )
    AmpCont: float = Field(
        default=0.07,
        ge=0.0,
        le=1.0,
        description="Amplitude contrast fraction.",
        json_schema_extra={
            "ui_widget": "slider",
            "ui_group": "Microscope",
            "ui_order": 4,
            "ui_step": 0.01,
            "ui_advanced": True,
        },
    )
    ExtPhase: float = Field(
        default=0,
        description="Extra phase shift (degrees) — set for phase-plate data.",
        json_schema_extra={
            "ui_widget": "number",
            "ui_group": "Microscope",
            "ui_order": 5,
            "ui_unit": "°",
            "ui_advanced": True,
        },
    )
    SumRangeMinDose: int = Field(
        default=3,
        ge=0,
        description="Minimum cumulative dose to include in the sum (e-/Å²).",
        json_schema_extra={
            "ui_widget": "number",
            "ui_group": "Dose weighting",
            "ui_order": 2,
            "ui_unit": "e⁻/Å²",
            "ui_advanced": True,
        },
    )
    SumRangeMaxDose: int = Field(
        default=25,
        ge=0,
        description="Maximum cumulative dose.",
        json_schema_extra={
            "ui_widget": "number",
            "ui_group": "Dose weighting",
            "ui_order": 3,
            "ui_unit": "e⁻/Å²",
            "ui_advanced": True,
        },
    )
    Group: Optional[int] = Field(
        default=None,
        description="Frame grouping factor — average groups of N frames before alignment.",
        json_schema_extra={
            "ui_widget": "number",
            "ui_group": "Alignment",
            "ui_order": 4,
            "ui_advanced": True,
        },
    )
    RotGain: int = Field(
        default=0,
        description="Rotate gain reference (0/1/2/3 = 0/90/180/270 deg).",
        json_schema_extra={
            "ui_widget": "select",
            "ui_group": "Calibration",
            "ui_order": 5,
            "ui_options": [0, 1, 2, 3],
            "ui_advanced": True,
        },
    )
    FlipGain: int = Field(
        default=0,
        description="Flip gain reference (0=none, 1=Y, 2=X).",
        json_schema_extra={
            "ui_widget": "select",
            "ui_group": "Calibration",
            "ui_order": 6,
            "ui_options": [0, 1, 2],
            "ui_advanced": True,
        },
    )
    InvGain: Optional[int] = Field(
        default=None,
        description="Invert the gain reference (1=invert).",
        json_schema_extra={
            "ui_widget": "select",
            "ui_group": "Calibration",
            "ui_order": 7,
            "ui_options": [0, 1],
            "ui_advanced": True,
        },
    )
    FmIntFile: Optional[str] = Field(
        default=None,
        description="Frame-intensity file (advanced dose weighting).",
        json_schema_extra={
            "ui_widget": "file_path",
            "ui_group": "Dose weighting",
            "ui_order": 4,
            "ui_advanced": True,
        },
    )
    EerSampling: int = Field(
        default=1,
        ge=1,
        description="EER super-resolution factor (1, 2, or 4).",
        json_schema_extra={
            "ui_widget": "select",
            "ui_group": "Frames",
            "ui_order": 4,
            "ui_options": [1, 2, 4],
            "ui_advanced": True,
        },
    )


class ParticleExtractionInput(CryoEmImageInput):
    """Input for the PARTICLE_EXTRACTION (stack maker) category.

    Subject is the source micrograph (carried in the inherited
    ``image_*`` fields) — extraction is per-mic by default per ratified
    rule 7 (see project_artifact_bus_invariants.md, 2026-05-03). The
    extractor reads the picker's particle coordinates from
    ``particles_path`` (a path on the data plane — never inline JSON
    per ratified rule 1), boxes each particle out of ``micrograph_path``,
    edge-normalises, and writes one ``.mrcs`` + one ``.star`` to disk.

    ``ctf_path`` is optional CTF metadata (e.g. ``ctffind_results.txt``
    or a CTF JSON) that the extractor copies into per-particle STAR
    columns. Engine-specific knobs (allow_partial, write_aligned_stack,
    etc.) ride on the inherited ``engine_opts`` dict.
    """

    micrograph_path: str = Field(
        ...,
        description="Source micrograph (.mrc) from which to box particles.",
        json_schema_extra={
            "ui_widget": "file_path",
            "ui_group": "Input",
            "ui_order": 1,
            "ui_file_ext": [".mrc"],
        },
    )
    particles_path: str = Field(
        ...,
        description="Picker output containing particle coordinates "
                    "(.star / .box / .json — read by the extraction backend).",
        json_schema_extra={
            "ui_widget": "file_path",
            "ui_group": "Input",
            "ui_order": 2,
            "ui_file_ext": [".star", ".box", ".json"],
        },
    )
    ctf_path: Optional[str] = Field(
        default=None,
        description="Optional CTF estimate to copy into per-particle STAR columns.",
        json_schema_extra={
            "ui_widget": "file_path",
            "ui_group": "Input",
            "ui_order": 3,
            "ui_advanced": True,
        },
    )
    box_size: int = Field(
        ...,
        gt=0,
        description="Box size in pixels. Should be at least 1.5× the particle "
                    "diameter to capture CTF rings.",
        json_schema_extra={
            "ui_widget": "slider",
            "ui_group": "Boxing",
            "ui_order": 1,
            "ui_step": 16,
            "ui_unit": "px",
            "ui_marks": [
                {"value": 64, "label": "64"},
                {"value": 256, "label": "256"},
                {"value": 512, "label": "512"},
            ],
        },
    )
    edge_width: int = Field(
        default=2,
        ge=0,
        description="Edge-normalisation ring width (pixels). 2 is a good default.",
        json_schema_extra={
            "ui_widget": "number",
            "ui_group": "Boxing",
            "ui_order": 2,
            "ui_unit": "px",
            "ui_advanced": True,
        },
    )
    apix: Optional[float] = Field(
        default=None,
        description="Pixel size override. When omitted, read from the MRC header.",
        json_schema_extra={
            "ui_widget": "number",
            "ui_group": "Microscope",
            "ui_order": 1,
            "ui_step": 0.01,
            "ui_unit": "Å",
        },
    )
    output_dir: Optional[str] = Field(
        default=None,
        description="Where ``.mrcs`` + ``.star`` land. Defaults to a sibling "
                    "directory of the micrograph; overridden inside jobs.",
        json_schema_extra={
            "ui_widget": "file_path",
            "ui_group": "Output",
            "ui_order": 1,
            "ui_advanced": True,
        },
    )


class TwoDClassificationInput(BaseModel):
    """Input for the TWO_D_CLASSIFICATION (CAN classifier) category.

    The subject of this task is a particle stack, not an image — see
    ratified rule 5 (subject axis) and rule 7 (one task per stack).
    Today the runtime is image-keyed (``ImageJobTask.image_id`` / the
    inherited ``CryoEmImageInput`` fields); once Phase 3 lands the
    runner will read ``subject_kind='particle_stack'`` /
    ``subject_id=<artifact.oid>`` from :class:`TaskMessage` instead of
    these explicit fields. Until then the plugin reads paths directly.

    Outputs (class averages, assignments, FRC) are written under
    ``output_dir`` and surfaced as paths on the
    :class:`TwoDClassificationOutput` — not inlined, per rule 1.
    """

    particle_stack_id: Optional[UUID] = Field(
        default=None,
        description="Artifact OID of the particle stack to classify. The dispatch "
                    "gate verifies this references an Artifact of kind 'particle_stack'.",
        json_schema_extra={
            "ui_widget": "hidden",  # supplied by the artifact picker, not typed
        },
    )
    mrcs_path: str = Field(
        ...,
        description="Particle stack file (.mrcs) — one image per boxed particle.",
        json_schema_extra={
            "ui_widget": "file_path",
            "ui_group": "Input",
            "ui_order": 1,
            "ui_file_ext": [".mrcs", ".mrc"],
        },
    )
    star_path: str = Field(
        ...,
        description="STAR file with per-particle metadata (RELION format).",
        json_schema_extra={
            "ui_widget": "file_path",
            "ui_group": "Input",
            "ui_order": 2,
            "ui_file_ext": [".star"],
        },
    )
    output_dir: str = Field(
        ...,
        description="Where class averages + assignments will be written.",
        json_schema_extra={
            "ui_widget": "file_path",
            "ui_group": "Output",
            "ui_order": 1,
        },
    )
    apix: Optional[float] = Field(
        default=None,
        description="Pixel size override. Read from MRC header when omitted.",
        json_schema_extra={
            "ui_widget": "number",
            "ui_group": "Microscope",
            "ui_order": 1,
            "ui_step": 0.01,
            "ui_unit": "Å",
        },
    )
    num_classes: int = Field(
        default=50,
        ge=2,
        description="Number of 2D classes to find. Typical range 50–200.",
        json_schema_extra={
            "ui_widget": "slider",
            "ui_group": "CAN topology",
            "ui_order": 1,
            "ui_step": 10,
            "ui_marks": [
                {"value": 10, "label": "10"},
                {"value": 50, "label": "50"},
                {"value": 200, "label": "200"},
            ],
            "ui_tunable": True,
        },
    )
    num_presentations: int = Field(
        default=200_000,
        ge=1000,
        description="Total training presentations. More = better convergence, slower.",
        json_schema_extra={
            "ui_widget": "number",
            "ui_group": "Training",
            "ui_order": 1,
            "ui_step": 10000,
        },
    )
    align_iters: int = Field(
        default=3,
        ge=1,
        description="Per-presentation alignment iterations.",
        json_schema_extra={
            "ui_widget": "number",
            "ui_group": "Training",
            "ui_order": 2,
            "ui_advanced": True,
        },
    )
    threads: int = Field(
        default=8,
        ge=1,
        description="CPU worker threads.",
        json_schema_extra={
            "ui_widget": "number",
            "ui_group": "Runtime",
            "ui_order": 1,
        },
    )
    can_threads: int = Field(
        default=8,
        ge=1,
        description="CAN algorithm parallelism (independent of `threads`).",
        json_schema_extra={
            "ui_widget": "number",
            "ui_group": "Runtime",
            "ui_order": 2,
            "ui_advanced": True,
        },
    )
    compute_backend: str = Field(
        default="torch-auto",
        description="Compute backend selection.",
        json_schema_extra={
            "ui_widget": "select",
            "ui_group": "Runtime",
            "ui_order": 3,
            "ui_options": ["cpu", "torch-auto", "torch-cuda", "torch-mps", "torch-cpu"],
        },
    )
    max_particles: Optional[int] = Field(
        default=None,
        description="Cap on particles fed to training (random sub-sample). "
                    "None = use all.",
        json_schema_extra={
            "ui_widget": "number",
            "ui_group": "Training",
            "ui_order": 3,
            "ui_advanced": True,
        },
    )
    invert: bool = Field(
        default=False,
        description="Invert particle contrast (set when particles are dark-on-light).",
        json_schema_extra={
            "ui_widget": "toggle",
            "ui_group": "Input",
            "ui_order": 3,
        },
    )
    write_aligned_stack: bool = Field(
        default=False,
        description="Write the aligned particle stack to disk (4× extra space).",
        json_schema_extra={
            "ui_widget": "toggle",
            "ui_group": "Output",
            "ui_order": 2,
            "ui_advanced": True,
        },
    )
    engine_opts: Dict[str, Any] = Field(
        default_factory=dict,
        description="Engine-specific overrides (learn, max_age, fft_scale, …).",
        json_schema_extra={
            "ui_hidden": True,  # raw dict; surfaced via richer UI later
        },
    )


class FftTask(TaskMessage):
    data: FftInput


class CtfTask(TaskMessage):
    data: CtfInput


class MotioncorTask(TaskMessage):
    data: MotionCorInput


class TaskStatusEnum(Enum):
    PENDING = {"code": 0, "name": "pending", "description": "Task is pending"}
    IN_PROGRESS = {"code": 1, "name": "in_progress", "description": "Task is in progress"}
    COMPLETED = {"code": 2, "name": "completed", "description": "Task has been completed"}
    FAILED = {"code": 3, "name": "failed", "description": "Task has failed"}


# Task-type constants — plugin dispatchers switch on these codes.
FFT_TASK = TaskCategory(code=1, name="FFT", description="Fast Fourier Transform")
CTF_TASK = TaskCategory(code=2, name="CTF", description="Contrast Transfer Function")
PARTICLE_PICKING = TaskCategory(code=3, name="Particle Picking", description="Identifying particles in images")
TWO_D_CLASSIFICATION = TaskCategory(code=4, name="2D Classification", description="Classifying 2D images")
MOTIONCOR = TaskCategory(code=5, name="MotionCor", description="Motion correction for electron microscopy")
SQUARE_DETECTION = TaskCategory(code=6, name="SquareDetection", description="Low-mag square detection and pickability scoring")
HOLE_DETECTION = TaskCategory(code=7, name="HoleDetection", description="Medium-mag hole detection and pickability scoring")
TOPAZ_PARTICLE_PICKING = TaskCategory(code=8, name="TopazParticlePicking", description="High-mag particle picking via Topaz CNN")
MICROGRAPH_DENOISING = TaskCategory(code=9, name="MicrographDenoising", description="Topaz-Denoise UNet on a single MRC")
PARTICLE_EXTRACTION = TaskCategory(code=10, name="ParticleExtraction", description="Box particles from a micrograph given coordinates (RELION-style stack)")

# Task-status constants.
PENDING = TaskStatus(code=0, name="pending", description="Task is pending")
IN_PROGRESS = TaskStatus(code=1, name="in_progress", description="Task is in progress")
COMPLETED = TaskStatus(code=2, name="completed", description="Task has been completed")
FAILED = TaskStatus(code=3, name="failed", description="Task has failed")


class ImageMetaData(BaseModel):
    key: str
    value: str
    is_persistent: Optional[bool] = None
    image_id: Optional[str] = None


class OutputFile(BaseModel):
    name: Optional[str] = None
    path: Optional[str] = None
    required: bool


class TaskResultMessage(BaseModel):
    """The wire envelope a plugin publishes when a task finishes.

    SDK 1.3+ canonical name; pre-1.3 callers know it as ``TaskResultDto``."""

    worker_instance_id: Optional[UUID] = None
    job_id: Optional[UUID] = None
    task_id: Optional[UUID] = None
    image_id: Optional[UUID] = None
    image_path: Optional[str] = None
    session_id: Optional[UUID] = None
    session_name: Optional[str] = None
    # Subject axis (Phase 3b, 2026-05-03). The runner echoes these
    # from the incoming TaskMessage into the result so downstream
    # consumers (TaskOutputProcessor, artifact writer, UI) can read
    # the subject without re-querying the originating task. Plugins
    # that build TaskResultMessage manually (CTF / MotionCor wrap a
    # do_*-built result) leave them None and the runner fills them
    # from the task in ``_stamp_provenance``. ``image_id`` stays
    # populated for back-compat when subject_kind == 'image'.
    subject_kind: Optional[str] = None
    subject_id: Optional[UUID] = None
    code: Optional[int] = None
    message: Optional[str] = None
    description: Optional[str] = None
    status: Optional[TaskStatus] = None
    type: Optional[TaskCategory] = None
    created_date: Optional[datetime] = Field(default_factory=_now_utc)
    started_on: Optional[datetime] = None
    ended_on: Optional[datetime] = None
    output_data: Dict[str, Any] = {}
    # Optional so result_processor can emit results where no per-image
    # metadata is attached (e.g. aggregate outcomes).
    meta_data: Optional[List[ImageMetaData]] = None
    output_files: List[OutputFile] = []
    # Provenance (P4). The plugin that produced this result identifies
    # itself so operators can answer "which engine processed this
    # micrograph?" without grepping logs. Optional because (a) older
    # plugins won't populate them yet, and (b) aggregator results have
    # no single-plugin owner. Both should match the values exposed in
    # the plugin's manifest (PluginInfo.name + .version) so the audit
    # trail and the registry agree.
    plugin_id: Optional[str] = None
    plugin_version: Optional[str] = None


class DebugInfo(BaseModel):
    id: Optional[str] = None
    line1: Optional[str] = None
    line2: Optional[str] = None
    line3: Optional[str] = None
    line4: Optional[str] = None
    line5: Optional[str] = None
    line6: Optional[str] = None
    line7: Optional[str] = None
    line8: Optional[str] = None


__all__ = [
    # Envelope.
    "TaskBase",
    "TaskCategory",
    "TaskMessage",
    "JobMessage",
    "TaskOutcome",
    "TaskStatus",
    "TaskStatusEnum",
    # Per-category input shapes.
    "CryoEmImageInput",
    "MrcToPngInput",
    "FftInput",
    "CtfInput",
    "MotionCorInput",
    "TopazPickInput",
    "MicrographDenoiseInput",
    "PtolemyInput",
    "ParticleExtractionInput",
    "TwoDClassificationInput",
    # Concrete tasks.
    "FftTask",
    "CtfTask",
    "MotioncorTask",
    # Constants.
    "FFT_TASK",
    "CTF_TASK",
    "PARTICLE_PICKING",
    "TWO_D_CLASSIFICATION",
    "MOTIONCOR",
    "SQUARE_DETECTION",
    "HOLE_DETECTION",
    "TOPAZ_PARTICLE_PICKING",
    "MICROGRAPH_DENOISING",
    "PARTICLE_EXTRACTION",
    "PENDING",
    "IN_PROGRESS",
    "COMPLETED",
    "FAILED",
    # Result / debug.
    "ImageMetaData",
    "OutputFile",
    "TaskResultMessage",
    "DebugInfo",
]
