"""Clean autofocus algorithms extracted from Leginon.

This package contains only numerical routines.  It does not acquire images,
move a microscope, talk to a database, or import Leginon/PyAMI.
"""

from .correlation import correlate_shift, cross_correlate, phase_correlate
from .autofocus_orchestrator import (
    ObjectiveFocusInstrument,
    StageZInstrument,
    run_objective_focus_sequence,
    run_stage_z_sequence,
)
from .focus_pipeline import (
    BeamTiltImagePair,
    BeamTiltTripleShot,
    ObjectiveCalibration,
    StageTiltImagePair,
    beam_tilt_measurements_from_images,
    beam_tilt_measurements_from_triple_shots,
    solve_objective_focus_from_image_pairs,
    solve_objective_focus_from_triple_shots,
    solve_stage_z_from_image_pairs,
    stage_tilt_measurements_from_images,
    unbin_pixel_shift,
)
from .objective_focus import (
    BeamTiltMeasurement,
    FocusSolveDiagnostics,
    ObjectiveFocusResult,
    solve_defocus_stig,
    solve_rotation_center_tilt,
)
from .z_focus import StageTiltMeasurement, StageZResult, solve_stage_z

__all__ = [
    "BeamTiltMeasurement",
    "BeamTiltImagePair",
    "BeamTiltTripleShot",
    "FocusSolveDiagnostics",
    "ObjectiveFocusInstrument",
    "ObjectiveCalibration",
    "ObjectiveFocusResult",
    "StageTiltMeasurement",
    "StageTiltImagePair",
    "StageZInstrument",
    "StageZResult",
    "beam_tilt_measurements_from_images",
    "beam_tilt_measurements_from_triple_shots",
    "correlate_shift",
    "cross_correlate",
    "phase_correlate",
    "run_objective_focus_sequence",
    "run_stage_z_sequence",
    "solve_defocus_stig",
    "solve_objective_focus_from_image_pairs",
    "solve_objective_focus_from_triple_shots",
    "solve_rotation_center_tilt",
    "solve_stage_z",
    "solve_stage_z_from_image_pairs",
    "stage_tilt_measurements_from_images",
    "unbin_pixel_shift",
]
