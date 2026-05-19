# Magellon Focus Algorithms

This folder contains clean numerical autofocus routines extracted from Leginon
without Leginon, PyAMI, GUI, microscope-control, database, or acquisition
dependencies.

## Source Mapping

- `objective_focus.py` is based on the beam-tilt autofocus equations in
  `leginon/calibrationclient.py`, especially `BeamTiltCalibrationClient.solveEq10`.
- `z_focus.py` is based on `StageTiltCalibrationClient.measureZ`, after removing
  stage motion, image acquisition, and database calibration lookup.
- `correlation.py` is a standalone replacement for the correlation and
  subpixel-peak portions of `pyami/correlator.py`, `pyami/peakfinder.py`, and
  `CalibrationClient.measureScopeChange`.

## Intended Data Flow

Objective focus:

1. Acquire two images at known beam tilts.
2. Use `correlate_shift()` to measure the image displacement.
3. Build `BeamTiltMeasurement` objects from beam-tilt deltas and shifts.
4. Call `solve_defocus_stig()` with calibration matrices.

Stage Z focus:

1. Acquire an untilted reference and images at negative and positive stage alpha.
2. Use `correlate_shift()` to measure each tilted displacement.
3. Build `StageTiltMeasurement` objects from alpha angles and shifts.
4. Call `solve_stage_z()` with the stage calibration matrix.

## Notes

The mock examples in `mock_inputs.py` are synthetic sanity checks, not microscope
simulation.  Real use still needs Magellon-side code to provide image arrays,
calibration matrices, beam-tilt values, stage alpha values, and camera binning.
