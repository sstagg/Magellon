# Autofocus Reference Sources

This folder keeps local copies of the upstream code paths used to compare the
Magellon focus extraction against Leginon and SerialEM.

## Leginon 3.7.6

Source copied from:

`C:\projects\MagScopeNext\support\leginon\leginon-3.7.6\leginon`

Files:

- `leginon-3.7.6/calibrationclient.py`
- `leginon-3.7.6/singlefocuser.py`
- `leginon-3.7.6/beamtiltcalibrator.py`

Important locations:

- `calibrationclient.py:144` - `measureScopeChange`; image acquisition, correlation, subpixel peak, wrapped shift, and unbinned pixel conversion.
- `calibrationclient.py:805` - `measureDefocusStig`; beam-tilt image-pair acquisition and defocus/stigmation measurement.
- `calibrationclient.py:881` - `solveEq10`; Leginon-compatible calibrated matrix solve for defocus, `stigx`, and `stigy`.
- `calibrationclient.py:930` - `solveEq10_t`; beam-tilt misalignment solve from a defocus-change displacement.
- `calibrationclient.py:1763` - `StageTiltCalibrationClient.measureZ`; stage-alpha sequence and Z calculation from tilt-induced Y motion.
- `singlefocuser.py:223` - focus correction orchestration; sets eucentric focus for Stage Z and resets preset defocus for objective focus.
- `singlefocuser.py:250` - objective defocus/stig measurement call.
- `singlefocuser.py:405` - stage-tilt Z measurement call.
- `beamtiltcalibrator.py` - calibration workflows and eucentric focus helpers.

Notes:

- Leginon calls the matrix solve `solveEq10`, but this should be treated as a legacy name. It is not a direct implementation of the paper's equation 10.
- The local `objective_focus.py` mirrors the numerical shape of Leginon's `solveEq10`.
- The local `z_focus.py` mirrors the endpoint of Leginon's `measureZ`, but not its full microscope motion/backlash sequence.

## SerialEM

Source copied from:

`C:\temp\SerialEM-master\SerialEM-master`

Files:

- `serialem/FocusManager.cpp`
- `serialem/FocusManager.h`
- `serialem/ShiftManager.cpp`
- `serialem/ShiftManager.h`

Important locations:

- `FocusManager.cpp:760` - autofocus calibration startup and focus-range setup.
- `FocusManager.cpp:840` - `CalFocusData`; records shift versus defocus and fits calibration slopes.
- `FocusManager.cpp:922` - slope fitting for focus calibration.
- `FocusManager.cpp:1033` - `FocusReady`; checks whether autofocus calibration exists.
- `FocusManager.cpp:1067` - `AutoFocusStart`; starts measure-only or correction autofocus.
- `FocusManager.cpp:1217` - `AutoFocusData`; converts measured shift to defocus, applies correction, reiterates, and aborts on inconsistent behavior.
- `FocusManager.cpp:1347` - `CurrentDefocusFromShift`; calibration lookup and defocus adjustment for offsets and tilted specimen geometry.
- `FocusManager.cpp:1399` - `DetectFocus`; two-shot or three-shot beam-tilt acquisition setup.
- `FocusManager.cpp:1539` - `FocusDone`; image preprocessing, correlation, peak finding, drift estimation, beam tilt reset, and dispatch.
- `FocusManager.cpp:1763` - three-shot correlation path and drift separation.
- `FocusManager.cpp:1786` - two-shot correlation path.
- `FocusManager.cpp:1917` - autofocus accuracy check using known positive and negative defocus changes.
- `FocusManager.cpp:2005` - focus calibration lookup/transfer routines.
- `FocusManager.cpp:2131` - `DefocusFromCal`; piecewise projection of measured shift onto the calibration curve.
- `ShiftManager.cpp` / `ShiftManager.h` - camera/specimen/image-shift transforms and calibration transfer helpers used by SerialEM focus calibration.

Notes:

- SerialEM uses an empirical focus table rather than Leginon's `F/A/B` matrix solve.
- SerialEM's production safeguards are important references for Magellon integration: three-shot drift protection, peak rejection, taper/pad/bin preprocessing, focus limits, refocus thresholds, and accuracy checks.

