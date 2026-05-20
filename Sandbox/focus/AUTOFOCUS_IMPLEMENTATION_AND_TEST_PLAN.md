# Autofocus Implementation and Test Plan

## Scope

This document compares the local focus extraction with:

- `Koster-1987-AnAutofocusMethod.pdf`
- Leginon 3.7.6 under `C:\projects\MagScopeNext\support\leginon\leginon-3.7.6`
- SerialEM under `C:\temp\SerialEM-master\SerialEM-master`

It describes the recommended way to implement beam-tilt autofocus and stage-tilt Z focus in Magellon, and how to test that the results are correct.

## What the paper actually defines

Koster et al. describe beam-tilt-induced displacement for TEM focus. In the simplified operating regime, two images taken at opposite beam tilts produce an image displacement proportional to defocus:

```text
D ~= 2 * M * beta * (Delta_f + Cs * beta^2)
```

The important ideas are:

- Tilt the illumination beam by known angles.
- Measure the image displacement between tilted images.
- Convert displacement to defocus.
- Measure along different directions to infer astigmatism.
- Use the displacement estimator quality, noise, sampling, magnification, and exposure time to reason about precision.

The paper does not define Leginon's exact `solveEq10` matrix API. Leginon's comment says it solves "Equation 10", but in the PDF equation 10 is a power-spectrum relationship, not the practical defocus/stigmation solve. Treat that name as legacy Leginon terminology.

## What Leginon does

The local extraction is closest to Leginon, not directly to the paper.

Relevant Leginon files:

- `leginon/calibrationclient.py`
- `leginon/singlefocuser.py`
- `leginon/beamtiltcalibrator.py`

### Image shift measurement

Leginon `CalibrationClient.measureScopeChange`:

1. Acquires a second image at the requested microscope state.
2. Inserts both images into the correlator.
3. Uses phase or cross correlation.
4. Finds a subpixel peak.
5. Wraps the peak coordinate into signed `(row, col)` shift.
6. Converts the shift to unbinned pixels by multiplying camera binning and correlator shrink factor.

The local `correlation.py` matches this shape well: FFT correlation, subpixel peak, wrapped coordinate, and unbinned-shift responsibility left to the caller.

### Objective focus and stigmation

Leginon `BeamTiltCalibrationClient.measureDefocusStig`:

1. Retrieves the defocus calibration matrix.
2. Builds a pair of beam tilt deltas.
3. If stigmation correction is enabled and matrices exist, adds an orthogonal beam-tilt pair and retrieves `stigx`/`stigy` matrices.
4. Acquires beam-tilted image pairs.
5. Measures unbinned pixel shifts.
6. Solves the linear system in `solveEq10`.
7. Restores beam tilt.

Leginon `solveEq10` and local `solve_defocus_stig` are essentially the same numerical model:

```text
observed_shift = [F * tilt_delta, A * tilt_delta, B * tilt_delta] * [defocus, stigx, stigy]
```

For defocus-only, use one independent tilt pair and `F`.

For defocus plus objective stigmation, use two independent tilt pairs and `F`, `A`, `B`.

The practical requirement is that the calibration matrices must already encode microscope-specific scale, camera orientation, magnification, beam-tilt units, and sign conventions. The solver should not independently apply the paper's `2 M beta` term unless the calibration strategy is changed to a paper-physics model.

### Stage-tilt Z focus

Leginon `StageTiltCalibrationClient.measureZ` is not from the Koster paper. It:

1. Acquires an image at alpha `0`.
2. Tilts stage to `-alpha`, measures image shift from zero.
3. Returns through zero, reacquires zero image, tilts to `+alpha`, measures image shift.
4. Converts each unbinned pixel shift through the stage calibration transform.
5. Uses the Y stage component only.
6. Computes `z = y / sin(alpha)` and averages the two directions.

The local `z_focus.py` captures the mathematical endpoint, but real integration must preserve Leginon's backlash handling, repeated zero reference, and calibration transform semantics.

## What SerialEM does

Relevant SerialEM files:

- `FocusManager.cpp`
- `FocusManager.h`
- `ShiftManager.cpp`

SerialEM uses the same beam-tilt-induced displacement principle, but the implementation differs from Leginon.

### Calibration-table model

SerialEM autofocus calibration measures shifts over a range of known defocus values:

1. Move to a sequence of defocus offsets.
2. At each defocus, acquire beam-tilted images.
3. Store shift per beam tilt as `shiftX`, `shiftY`, normalized by working beam tilt.
4. Fit slopes around the central calibration range.
5. Store a focus table keyed by magnification, camera, probe mode, beam alpha, and tilt direction.

When measuring defocus, SerialEM projects the measured shift onto the nearest segment of the calibration curve:

```text
defocus = df1 + dot(measured_shift - shift_at_df1, segment_slope) / |segment_slope|^2
```

This is more empirical than Leginon's matrix solve. It also supports nonlinear calibration curves by using piecewise line segments.

### Operational safeguards

SerialEM includes several production safeguards. Some now have local
equivalents (marked *done* below); the rest remain references for Magellon
integration:

- Two-shot or three-shot focus detection. *(done: two-shot image pairs and three-shot triples.)*
- Three-shot mode separates beam-tilt shift from specimen drift. *(done: `solve_objective_focus_from_triple_shots`.)*
- Direct detector binning and filter scaling before correlation. *(partial: binning is handled by the caller via `unbin_pixel_shift`.)*
- Image tapering and padding before correlation. *(done: `correlate_shift` `taper_fraction`/`pad_fraction`.)*
- Optional periodic-peak removal. *(still missing.)*
- Zero-peak rejection or second-peak selection. *(partial: `zero_origin` controls whether the origin peak is kept.)*
- Tilt-image stretching at high stage tilt. *(still missing.)*
- Refocus iteration when measured change is larger than a threshold. *(still missing, needs the orchestration layer.)*
- Abort on inconsistent iterations, too many iterations, near-zero correlations, or focus limits. *(partial: `min_snr` rejects weak correlations; iteration/limit logic needs orchestration.)*
- Accuracy check by measuring at current focus and known positive/negative focus offsets. *(still missing, needs the orchestration layer.)*

These are not just UI details. They are the difference between a mathematical prototype and a robust microscope routine.

## Recommended implementation for Magellon

### 1. Keep the numerical core small and explicit

Use the existing local modules as pure numerical kernels:

- `correlate_shift(image1, image2) -> ShiftResult`
- `solve_defocus_stig(defocus_matrix, measurements, stigx_matrix, stigy_matrix)`
- `solve_stage_z(stage_matrix, measurements)`

Do not put microscope motion, camera acquisition, calibration lookup, or database writes inside these kernels.

### 2. Add an orchestration layer

Create a microscope-facing autofocus service that owns the acquisition sequence:

```text
Objective autofocus:
  save current beam tilt and focus/stig state
  retrieve calibration matrices for current TEM/camera/HT/mag/probe
  compute beam tilt pair
  acquire image at tilt 1
  acquire image at tilt 2
  correlate images and convert to unbinned pixels
  repeat on orthogonal tilt pair if stigmation is enabled
  solve defocus/stig
  apply bounded correction
  restore beam tilt
  return measurement, correction, quality metrics
```

```text
Stage Z focus:
  save current stage alpha
  move through backlash-safe alpha sequence
  acquire zero reference
  acquire -alpha shifted image and correlate
  reacquire zero reference
  acquire +alpha shifted image and correlate
  transform pixel shifts to stage XY
  compute and average z estimates
  restore original alpha
  return z, per-tilt z values, quality metrics
```

### 3. Treat calibration as required data, not constants

For Leginon-compatible objective autofocus, require:

- Defocus matrix `F`, 2x2.
- Optional stigmator matrices `A` and `B`, both 2x2.
- Beam tilt scale and rotation or explicit tilt delta pair.
- Camera binning and any correlator shrink factor.
- Current magnification, high tension, probe mode, camera identity.

For SerialEM-style objective autofocus, require:

- A focus table keyed by mag/camera/probe/alpha/tilt direction.
- Beam tilt value used for calibration.
- Shift-vs-defocus samples.
- Logic to transform calibration tables between cameras/mags only when image-shift/specimen transforms are available.

Do not mix the Leginon matrix solve and SerialEM table solve in one path. Pick one calibration model per autofocus mode and make it visible in logs/results.

### 4. Add missing validation before using results

The local objective solver should reject unsafe solves:

- `rank < number_of_unknowns`
- high condition number
- missing orthogonal measurement when solving stigmation
- correlation SNR/peak score below threshold
- measured shift near zero when expected shift should be resolvable
- defocus/stig correction above configured limits

The result object should include:

- raw shifts
- beam tilts
- matrices/calibration IDs
- solver rank and singular values
- residual
- correlation peak value/SNR
- applied correction
- whether correction was limited or rejected

### 5. Prefer Leginon-compatible first, SerialEM safeguards second

For Magellon, the most direct route is:

1. Implement Leginon-compatible orchestration around the existing matrix solver.
2. Add SerialEM-inspired robustness: three-shot drift mode, iteration/refocus threshold, correction limits, and accuracy check.
3. Later add SerialEM-style focus tables only if empirical piecewise calibration is needed.

This avoids combining two calibration philosophies prematurely.

## Test strategy

Testing needs to be layered. Unit tests alone are not enough because sign conventions, microscope state restoration, and calibration identity are common failure points.

Status: the pure numerical unit tests and Leginon parity tests below largely
exist in `test_focus_algorithms.py` (23 tests) — correlation shift parity,
non-periodic correlation, rank-deficient and ill-conditioned rejection, SNR
gating, three-shot drift cancellation, `solveEq10` parity, and stage-Z solves.
The simulated-microscope, noise/robustness, and hardware tiers are still to do.

### 1. Pure numerical unit tests

Correlation:

- Integer roll recovers exact signed `(row, col)` shift.
- Subpixel synthetic Fourier shift recovers shift within tolerance.
- Wrap behavior works near image boundaries.
- Phase and cross correlation agree on high-SNR images.
- Constant or blank images fail or return low-quality metrics.
- Binning conversion is tested outside `correlate_shift`.

Objective solver:

- Defocus-only noiseless case recovers scalar defocus.
- Defocus plus stig noiseless case recovers all three unknowns.
- Reversed beam tilt signs produce expected sign reversal.
- Orthogonal tilt pair is required for stigmation.
- Rank-deficient design is rejected.
- Ill-conditioned design is reported or rejected.
- Residual is nonzero for inconsistent shifts.

Stage Z:

- Positive and negative alpha measurements average to true Z.
- Alpha near zero is rejected.
- Binning is applied correctly.
- `cos(alpha_for_matrix)` correction is covered.
- Opposite sign conventions are tested explicitly.

### 2. Golden parity tests against Leginon formulas

Build fixtures copied from Leginon behavior:

- Given the same `F`, `A`, `B`, `tilts`, and `shifts`, local `solve_defocus_stig` must match Leginon `solveEq10`.
- Given known pixel shifts and stage matrix, local `solve_stage_z` must match Leginon's `y / sin(alpha)` computation.
- Given a synthetic correlation peak coordinate, local wrapping must match Leginon's `correlator.wrap_coord`.

These tests do not need a microscope. They prevent accidental drift from the known Leginon-compatible API.

### 3. SerialEM-style behavior tests

If a SerialEM-style focus table is added, test it separately:

- Generate a shift-vs-defocus table with known slopes.
- Recover defocus by projection onto a calibration segment.
- Test nonlinear piecewise tables and nearest-segment selection.
- Test calibration transfer through a known scale/rotation matrix.
- Test out-of-range behavior and distance-past-calibration reporting.

Do not use these tests to validate the Leginon matrix solver; they are different models.

### 4. Simulated microscope integration tests

Create a fake microscope/camera that records state changes and returns synthetic shifted images.

Objective autofocus integration assertions:

- Beam tilt sequence is exactly `tilt1 -> tilt2`, and orthogonal pair when stigmation is enabled.
- Original beam tilt is restored on success and on exceptions.
- Images are correlated in the expected order.
- Binning/shrink are applied once, not twice.
- Correction is applied only if validation passes.
- Large corrections are bounded or rejected.
- Result payload contains raw data and quality metrics.

Stage Z integration assertions:

- Stage alpha sequence handles backlash: pre-move, zero, negative tilt, zero, positive tilt.
- Original alpha is restored on success and on exceptions.
- Zero reference image is reacquired before the opposite tilt.
- Per-tilt Z values and mean are returned.

### 5. Noise and robustness tests

Use synthetic images with texture, shot noise, read noise, and drift:

- Defocus estimate variance decreases with exposure/noise level in the expected direction.
- Three-shot mode cancels linear drift better than two-shot mode.
- Low-texture images are rejected by SNR/CCC thresholds.
- Periodic patterns either reject ambiguous peaks or use a configured alternate-peak policy.
- High stage tilt uses stretch/correction if implemented.

The pass/fail should be based on tolerances and quality flags, not only exact equality.

### 6. Hardware acceptance tests

Run on a microscope only after simulation and parity tests pass.

Objective focus:

1. Calibrate defocus matrix at one mag/camera/probe/HT.
2. Apply known defocus offsets, for example `-2`, `-1`, `+1`, `+2` microns where safe.
3. Measure without applying correction.
4. Fit measured vs actual defocus.
5. Acceptance: slope near `1`, small intercept, repeatability within the required focus tolerance, no sign inversion.
6. Enable correction and verify final measured defocus is near target.

Stigmation:

1. Use known objective stig offsets if the microscope API supports safe controlled offsets.
2. Verify the solver recovers both axes with the expected sign.
3. Confirm defocus-only mode is unaffected when stigmation matrices are absent.

Stage Z:

1. Move stage Z by known safe offsets around eucentric height.
2. Measure stage-tilt Z without correction.
3. Verify measured Z vs commanded Z slope/sign.
4. Apply correction and verify the residual Z/defocus is below tolerance.

SerialEM comparison:

- On the same specimen and imaging conditions, run SerialEM's `Check Autofocus` or equivalent.
- Compare measured defocus changes for known focus offsets.
- Expect agreement in sign and approximate scale; exact equality is not required because SerialEM's calibration-table method differs from Leginon's matrix solve.

## Minimum acceptance criteria

Before enabling automatic correction:

- Correlation shift parity with synthetic images passes.
- Leginon solver parity passes for saved fixtures.
- Simulated microscope restores beam tilt/stage alpha on every failure path.
- Rank and quality validation can reject bad measurements.
- Known-offset hardware measurements have correct sign and slope.
- Correction limits prevent damaging or runaway focus changes.

Before enabling stigmation correction:

- Two independent tilt directions are verified.
- `F`, `A`, and `B` matrices are available for the exact operating condition.
- Rank is full for the three-unknown solve.
- Measured residuals are logged and bounded.

Before enabling stage Z correction:

- Stage calibration matrix is available for current mag/camera/HT.
- Alpha sign convention is verified on the target microscope.
- Backlash-safe alpha sequence is implemented.
- Original alpha restoration is verified on error.

## Immediate code recommendations for the local extraction

### Completed

Implemented in commits `5618c77f` and `14ed5813`:

1. Documentation no longer calls the solve "Koster equation 10"; it is described as a Leginon-compatible beam-tilt calibration matrix solve.
2. `solve_defocus_stig` rejects rank-deficient and ill-conditioned designs (`validate=True`).
3. The public result carries residual, rank, condition number, singular values, and a `FocusSolveDiagnostics` object.
4. Tests cover rank-deficient and ill-conditioned stigmation solves.
5. Tests compare `solve_defocus_stig` directly against a Leginon `solveEq10` fixture transcribed from `references/`.
6. `z_focus.py` remains documented as Leginon stage-tilt Z focus, not Koster paper autofocus.

Robustness work landed beyond the original list: SerialEM-style edge taper/pad before correlation, an optional correlation low-pass (Leginon's `lp`), peak-masked SNR with `min_snr` gating, three-shot drift correction, and singular-system validation in `solve_rotation_center_tilt`.

### Still open

7. Add an integration-level orchestration module only after calibration lookup and microscope state APIs are defined.

