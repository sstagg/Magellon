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

## Robustness options

`correlate_shift()` edge-tapers and (optionally) zero-pads each image before
the FFT so non-periodic micrographs do not produce spurious wrap-around peaks,
and accepts a `lowpass` argument equivalent to Leginon's `measureScopeChange`
`lp`.  Near-zero shift is preserved by default, because zero image movement is
a valid autofocus result near true focus or eucentric height.

Correlation quality includes SNR, primary/secondary peak ratio, and normalized
CCC.  The `focus_pipeline` solvers accept `min_snr`, `min_peak_ratio`, and
`min_normalized_ccc` thresholds that reject weak or ambiguous measurements.

For drift-prone specimens, `solve_objective_focus_from_triple_shots()` consumes
`BeamTiltTripleShot` inputs (images at tilts `[A, B, A]`) and removes linear
specimen drift the way SerialEM's three-shot focus does.  If timestamps are
provided, the drift correction is scaled by the actual timing; otherwise equal
time intervals are assumed.

The numerical solvers return typed result objects (`ObjectiveFocusResult` and
`StageZResult`) accessed by attribute (`result.defocus`).  Pipeline results
also carry the measurements, raw shift results, and weakest quality metrics
observed.

`autofocus_orchestrator.py` contains protocol-based acquisition helpers that
save microscope state, acquire the required image sequence, call the pure
pipeline, optionally apply a correction callback, and restore beam tilt or
stage alpha in a `finally` block.

## JSON Configuration

Runtime settings and calibration matrices can be loaded from JSON with
`load_focus_runtime_config()` and `load_focus_calibration_config()`.

- `config/focus_runtime.example.json` contains acquisition/correlation solver
  settings such as beam tilts, binning, quality thresholds, and stage alphas.
- `config/focus_calibration.example.json` contains microscope/camera-specific
  calibration matrices.

Keep runtime settings separate from calibration values. Runtime settings can be
tuned per workflow; calibration matrices should be tied to the microscope,
camera, magnification, high tension, and probe mode that produced them.

## Notes

The mock examples in `mock_inputs.py` are synthetic sanity checks, not microscope
simulation.  Real use still needs Magellon-side code to provide image arrays,
calibration matrices, beam-tilt values, stage alpha values, and camera binning.
