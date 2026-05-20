import numpy as np

try:
    from focus.correlation import correlate_shift
    from focus.autofocus_orchestrator import (
        run_objective_focus_sequence,
        run_stage_z_sequence,
    )
    from focus.focus_pipeline import (
        BeamTiltImagePair,
        BeamTiltTripleShot,
        ObjectiveCalibration,
        StageTiltImagePair,
        solve_objective_focus_from_image_pairs,
        solve_objective_focus_from_triple_shots,
        solve_stage_z_from_image_pairs,
        unbin_pixel_shift,
    )
    from focus.mock_inputs import objective_focus_demo, shifted_image_demo, z_focus_demo
    from focus.objective_focus import (
        BeamTiltMeasurement,
        solve_defocus_stig,
        solve_rotation_center_tilt,
    )
    from focus.z_focus import StageTiltMeasurement, solve_stage_z
except ModuleNotFoundError:
    from magellon_focus_extract.correlation import correlate_shift
    from magellon_focus_extract.autofocus_orchestrator import (
        run_objective_focus_sequence,
        run_stage_z_sequence,
    )
    from magellon_focus_extract.focus_pipeline import (
        BeamTiltImagePair,
        BeamTiltTripleShot,
        ObjectiveCalibration,
        StageTiltImagePair,
        solve_objective_focus_from_image_pairs,
        solve_objective_focus_from_triple_shots,
        solve_stage_z_from_image_pairs,
        unbin_pixel_shift,
    )
    from magellon_focus_extract.mock_inputs import objective_focus_demo, shifted_image_demo, z_focus_demo
    from magellon_focus_extract.objective_focus import (
        BeamTiltMeasurement,
        solve_defocus_stig,
        solve_rotation_center_tilt,
    )
    from magellon_focus_extract.z_focus import StageTiltMeasurement, solve_stage_z

import pytest


def test_correlate_shift_integer_roll():
    demo = shifted_image_demo((6, -5))
    assert np.allclose(demo["measured_shift"], (6, -5), atol=0.25)


def test_correlate_shift_keeps_zero_shift_by_default():
    rng = np.random.default_rng(3)
    image = rng.normal(0.0, 1.0, (64, 64))

    result = correlate_shift(image, image)

    assert np.allclose(result.shift, (0.0, 0.0), atol=0.1)
    assert result.normalized_ccc > 0.99


def test_objective_focus_solve_defocus_only():
    matrix = np.array([[1000.0, 0.0], [0.0, 1000.0]])
    measurement = BeamTiltMeasurement((0.01, 0.0), (2.0e-5, 0.0))
    result = solve_defocus_stig(matrix, [measurement])
    assert np.isclose(result["defocus"], 2.0e-6)
    assert result["stigx"] is None
    assert result["stigy"] is None
    assert result["rank"] == 1
    assert result["unknown_count"] == 1
    assert np.isfinite(result["condition_number"])


def test_objective_focus_demo_with_stig():
    result = objective_focus_demo()
    assert np.isclose(result["defocus"], 2.0e-6)
    assert np.isclose(result["stigx"], -0.4e-6)
    assert np.isclose(result["stigy"], 0.7e-6)
    assert result["rank"] == 3
    assert result["unknown_count"] == 3


def test_objective_focus_rejects_rank_deficient_stig_solve():
    matrix = np.eye(2)
    measurements = [
        BeamTiltMeasurement((0.01, 0.0), (1.0e-6, 0.0)),
        BeamTiltMeasurement((0.02, 0.0), (2.0e-6, 0.0)),
    ]

    with pytest.raises(ValueError, match="rank deficient"):
        solve_defocus_stig(
            matrix,
            measurements,
            stigx_matrix=matrix,
            stigy_matrix=matrix,
        )


def test_objective_focus_can_return_legacy_least_squares_without_validation():
    matrix = np.eye(2)
    measurements = [
        BeamTiltMeasurement((0.01, 0.0), (1.0e-6, 0.0)),
        BeamTiltMeasurement((0.02, 0.0), (2.0e-6, 0.0)),
    ]

    result = solve_defocus_stig(
        matrix,
        measurements,
        stigx_matrix=matrix,
        stigy_matrix=matrix,
        validate=False,
    )

    assert result["rank"] < result["unknown_count"]
    assert result["diagnostics"].design.shape == (4, 3)


def test_objective_focus_rejects_poorly_conditioned_solve():
    matrix = np.array([[1.0, 0.2], [0.1, 0.9]])
    measurements = [
        BeamTiltMeasurement((0.01, 0.0), (1.0e-6, 0.0)),
        BeamTiltMeasurement((0.010001, 0.001), (1.0001e-6, 1.0e-7)),
    ]

    with pytest.raises(ValueError, match="poorly conditioned"):
        solve_defocus_stig(
            matrix,
            measurements,
            stigx_matrix=np.array([[0.3, 1.1], [-0.4, 0.2]]),
            stigy_matrix=np.array([[0.7, -0.2], [1.3, 0.5]]),
            max_condition_number=10.0,
        )


def test_stage_z_solve():
    matrix = np.array([[1.0e-9, 0.0], [0.0, 2.0e-9]])
    result = solve_stage_z(
        matrix,
        [
            StageTiltMeasurement(-0.1, (0.0, -74.87506248512112)),
            StageTiltMeasurement(0.1, (0.0, 74.87506248512112)),
        ],
    )
    assert np.isclose(result["z"], 1.5e-6)
    assert np.isclose(result["z_std"], 0.0)
    assert result["measurement_count"] == 2


def test_stage_z_rejects_zero_alpha():
    matrix = np.array([[1.0e-9, 0.0], [0.0, 2.0e-9]])

    with pytest.raises(ValueError, match="too close to zero"):
        solve_stage_z(matrix, [StageTiltMeasurement(0.0, (0.0, 1.0))])


def test_z_focus_demo():
    result = z_focus_demo()
    assert np.isclose(result["z"], 1.5e-6)


def test_unbin_pixel_shift_uses_row_col_binning_order():
    assert unbin_pixel_shift((2.0, -3.0), (4.0, 5.0)) == (8.0, -15.0)


def test_objective_focus_pipeline_from_image_pair():
    rng = np.random.default_rng(11)
    image = rng.normal(0.0, 0.03, (96, 96))
    rr, cc = np.indices(image.shape)
    image += np.exp(-(((rr - 40.0) ** 2 + (cc - 45.0) ** 2) / (2.0 * 4.0**2)))
    shifted = np.roll(image, 6, axis=0)

    result = solve_objective_focus_from_image_pairs(
        ObjectiveCalibration(np.array([[1000.0, 0.0], [0.0, 1000.0]])),
        [
            BeamTiltImagePair(
                first_tilt=(0.0, 0.0),
                second_tilt=(0.01, 0.0),
                first_image=image,
                second_image=shifted,
            )
        ],
    )

    assert np.isclose(result["measurements"][0].pixel_shift[0], 6.0, atol=0.25)
    assert np.isclose(result["defocus"], 0.6, atol=0.03)


def test_stage_z_pipeline_from_image_pairs():
    rng = np.random.default_rng(12)
    image = rng.normal(0.0, 0.03, (96, 96))
    rr, cc = np.indices(image.shape)
    image += np.exp(-(((rr - 35.0) ** 2 + (cc - 50.0) ** 2) / (2.0 * 4.0**2)))
    alpha = 0.1
    col_pixels = 5
    stage_matrix = np.array([[1.0e-9, 0.0], [0.0, 2.0e-9]])
    expected_z = col_pixels * stage_matrix[1, 1] / np.sin(alpha)

    result = solve_stage_z_from_image_pairs(
        stage_matrix,
        [
            StageTiltImagePair(
                alpha=-alpha,
                reference_image=image,
                tilted_image=np.roll(image, -col_pixels, axis=1),
            ),
            StageTiltImagePair(
                alpha=alpha,
                reference_image=image,
                tilted_image=np.roll(image, col_pixels, axis=1),
            ),
        ],
    )

    assert np.isclose(result["z"], expected_z, rtol=0.05)
    assert len(result["shift_results"]) == 2


def leginon_solve_eq10(F, A, B, tilts, shifts):
    """Pure-numpy copy of Leginon ``BeamTiltCalibrationClient.solveEq10``.

    Transcribed from ``references/leginon-3.7.6/calibrationclient.py`` so the
    local solver can be checked against the upstream numerics without pulling
    in Leginon's database/instrument dependencies.
    """

    v = np.array(shifts, np.float64).ravel()
    matrices = [matrix for matrix in (F, A, B) if matrix is not None]
    mt = []
    for tilt in tilts:
        t = np.array(tilt, np.float64)
        t.shape = (2, 1)
        mm = [np.dot(matrix, t) for matrix in matrices]
        mt.append(np.concatenate(mm, 1))
    M = np.concatenate(mt, 0)
    solution = np.linalg.lstsq(M, v, rcond=-1)
    result = {"defocus": solution[0][0]}
    if len(solution[0]) == 3:
        result["stigx"] = solution[0][1]
        result["stigy"] = solution[0][2]
    else:
        result["stigx"] = None
        result["stigy"] = None
    return result


def test_solve_defocus_stig_matches_leginon_solve_eq10():
    defocus_matrix = np.array([[1200.0, 30.0], [-20.0, 1000.0]])
    stigx_matrix = np.array([[200.0, -50.0], [40.0, 150.0]])
    stigy_matrix = np.array([[-80.0, 180.0], [160.0, 20.0]])
    truth = np.array([2.0e-6, -0.4e-6, 0.7e-6])
    tilts = [(0.01, 0.0), (0.0, 0.01)]

    shifts = []
    for tilt in tilts:
        design = np.concatenate(
            [
                matrix @ np.asarray(tilt).reshape(2, 1)
                for matrix in (defocus_matrix, stigx_matrix, stigy_matrix)
            ],
            axis=1,
        )
        shifts.append(tuple(design @ truth))

    local = solve_defocus_stig(
        defocus_matrix,
        [BeamTiltMeasurement(t, s) for t, s in zip(tilts, shifts)],
        stigx_matrix=stigx_matrix,
        stigy_matrix=stigy_matrix,
    )
    leginon = leginon_solve_eq10(defocus_matrix, stigx_matrix, stigy_matrix, tilts, shifts)

    assert np.isclose(local["defocus"], leginon["defocus"], rtol=0.0, atol=1.0e-15)
    assert np.isclose(local["stigx"], leginon["stigx"], rtol=0.0, atol=1.0e-15)
    assert np.isclose(local["stigy"], leginon["stigy"], rtol=0.0, atol=1.0e-15)


def test_solve_defocus_only_matches_leginon_solve_eq10():
    defocus_matrix = np.array([[1000.0, 25.0], [-15.0, 900.0]])
    tilts = [(0.012, 0.0)]
    shifts = [(2.3e-5, -7.0e-7)]

    local = solve_defocus_stig(defocus_matrix, [BeamTiltMeasurement(tilts[0], shifts[0])])
    leginon = leginon_solve_eq10(defocus_matrix, None, None, tilts, shifts)

    assert np.isclose(local["defocus"], leginon["defocus"], rtol=0.0, atol=1.0e-18)
    assert local["stigx"] is None and leginon["stigx"] is None


def test_correlate_shift_recovers_non_periodic_shift():
    """A shift between two genuinely non-periodic crops is recovered.

    The crops are taken from a larger scene, so their edges hold different
    content and the FFT wrap boundary is not periodic.  This is the case the
    edge taper exists for; ``np.roll`` based tests cannot exercise it.
    """

    rng = np.random.default_rng(23)
    base = rng.normal(0.0, 0.05, (192, 192))
    rr, cc = np.indices(base.shape)
    for row0, col0, amp, sigma in [
        (60.0, 70.0, 1.0, 5.0),
        (120.0, 90.0, 0.8, 7.0),
        (95.0, 140.0, 0.9, 4.0),
        (150.0, 55.0, 1.1, 6.0),
    ]:
        base += amp * np.exp(-(((rr - row0) ** 2 + (cc - col0) ** 2) / (2.0 * sigma**2)))

    dr, dc = 8, -6
    window1 = base[40:136, 40:136]
    window2 = base[40 - dr:136 - dr, 40 - dc:136 - dc]

    result = correlate_shift(window2, window1, taper_fraction=0.15)

    assert np.isclose(result.shift[0], dr, atol=0.6)
    assert np.isclose(result.shift[1], dc, atol=0.6)


def test_lowpass_smooths_correlation_without_moving_peak():
    demo_shift = (6, -5)
    rng = np.random.default_rng(7)
    image = rng.normal(0.0, 0.03, (96, 96))
    rr, cc = np.indices(image.shape)
    image += np.exp(-(((rr - 32.0) ** 2 + (cc - 41.0) ** 2) / (2.0 * 3.0**2)))
    shifted = np.roll(np.roll(image, demo_shift[0], axis=0), demo_shift[1], axis=1)

    plain = correlate_shift(shifted, image)
    smoothed = correlate_shift(shifted, image, lowpass=1.0)

    assert np.allclose(smoothed.shift, plain.shift, atol=0.4)
    assert np.std(smoothed.correlation) <= np.std(plain.correlation)


def test_objective_pipeline_rejects_low_snr():
    rng = np.random.default_rng(31)
    first = rng.normal(0.0, 1.0, (96, 96))
    second = rng.normal(0.0, 1.0, (96, 96))

    with pytest.raises(ValueError, match="SNR"):
        solve_objective_focus_from_image_pairs(
            ObjectiveCalibration(np.array([[1000.0, 0.0], [0.0, 1000.0]])),
            [
                BeamTiltImagePair(
                    first_tilt=(0.0, 0.0),
                    second_tilt=(0.01, 0.0),
                    first_image=first,
                    second_image=second,
                )
            ],
            min_snr=20.0,
        )


def test_objective_pipeline_rejects_low_peak_ratio():
    rng = np.random.default_rng(31)
    first = rng.normal(0.0, 1.0, (96, 96))
    second = rng.normal(0.0, 1.0, (96, 96))

    with pytest.raises(ValueError, match="peak ratio"):
        solve_objective_focus_from_image_pairs(
            ObjectiveCalibration(np.array([[1000.0, 0.0], [0.0, 1000.0]])),
            [
                BeamTiltImagePair(
                    first_tilt=(0.0, 0.0),
                    second_tilt=(0.01, 0.0),
                    first_image=first,
                    second_image=second,
                )
            ],
            min_peak_ratio=50.0,
        )


def test_objective_pipeline_rejects_low_normalized_ccc():
    rng = np.random.default_rng(32)
    first = rng.normal(0.0, 1.0, (96, 96))
    second = rng.normal(0.0, 1.0, (96, 96))

    with pytest.raises(ValueError, match="normalized CCC"):
        solve_objective_focus_from_image_pairs(
            ObjectiveCalibration(np.array([[1000.0, 0.0], [0.0, 1000.0]])),
            [
                BeamTiltImagePair(
                    first_tilt=(0.0, 0.0),
                    second_tilt=(0.01, 0.0),
                    first_image=first,
                    second_image=second,
                )
            ],
            min_normalized_ccc=0.95,
        )


def test_objective_pipeline_accepts_high_snr_with_threshold():
    rng = np.random.default_rng(11)
    image = rng.normal(0.0, 0.03, (96, 96))
    rr, cc = np.indices(image.shape)
    image += np.exp(-(((rr - 40.0) ** 2 + (cc - 45.0) ** 2) / (2.0 * 4.0**2)))
    shifted = np.roll(image, 6, axis=0)

    result = solve_objective_focus_from_image_pairs(
        ObjectiveCalibration(np.array([[1000.0, 0.0], [0.0, 1000.0]])),
        [
            BeamTiltImagePair(
                first_tilt=(0.0, 0.0),
                second_tilt=(0.01, 0.0),
                first_image=image,
                second_image=shifted,
            )
        ],
        min_snr=5.0,
    )

    assert result["min_snr_observed"] > 5.0
    assert np.isclose(result["defocus"], 0.6, atol=0.03)


def test_solve_rotation_center_tilt_recovers_tilt():
    defocus_matrix = np.array([[1000.0, 0.0], [0.0, 1000.0]])
    defocus1, defocus2 = -1.0e-6, 1.0e-6
    true_tilt = np.array([0.003, -0.002])
    pixel_shift = (defocus2 - defocus1) * defocus_matrix @ true_tilt

    tilt = solve_rotation_center_tilt(defocus_matrix, defocus1, defocus2, tuple(pixel_shift))

    assert np.allclose(tilt, true_tilt, atol=1.0e-12)


def test_solve_rotation_center_tilt_rejects_equal_defocus():
    matrix = np.eye(2)
    with pytest.raises(ValueError, match="must differ"):
        solve_rotation_center_tilt(matrix, 1.0e-6, 1.0e-6, (1.0, 1.0))


def test_solve_rotation_center_tilt_rejects_singular_matrix():
    singular = np.array([[1.0, 1.0], [1.0, 1.0]])
    with pytest.raises(ValueError, match="singular or poorly conditioned"):
        solve_rotation_center_tilt(singular, -1.0e-6, 1.0e-6, (1.0, 1.0))


def _three_shot_scene(seed=41):
    rng = np.random.default_rng(seed)
    image = rng.normal(0.0, 0.03, (96, 96))
    rr, cc = np.indices(image.shape)
    image += np.exp(-(((rr - 44.0) ** 2 + (cc - 50.0) ** 2) / (2.0 * 4.0**2)))
    image += 0.6 * np.exp(-(((rr - 70.0) ** 2 + (cc - 30.0) ** 2) / (2.0 * 5.0**2)))
    return image


def test_three_shot_cancels_linear_drift():
    """A three-shot triple recovers the beam-tilt shift free of linear drift.

    The second image carries tilt shift + one interval of drift; the third
    carries two intervals of pure drift.  The drift-corrected measurement
    should land on the true tilt shift, while a plain two-shot correlation of
    the first two frames keeps the drift error.
    """

    image = _three_shot_scene()
    tilt_rows = 5
    drift_per_interval = 2
    first_image = image
    second_image = np.roll(image, tilt_rows + drift_per_interval, axis=0)
    third_image = np.roll(image, 2 * drift_per_interval, axis=0)

    result = solve_objective_focus_from_triple_shots(
        ObjectiveCalibration(np.array([[1000.0, 0.0], [0.0, 1000.0]])),
        [
            BeamTiltTripleShot(
                first_tilt=(0.0, 0.0),
                second_tilt=(0.01, 0.0),
                first_image=first_image,
                second_image=second_image,
                third_image=third_image,
            )
        ],
    )
    corrected_rows = result["measurements"][0].pixel_shift[0]
    assert np.isclose(corrected_rows, tilt_rows, atol=0.4)

    two_shot = solve_objective_focus_from_image_pairs(
        ObjectiveCalibration(np.array([[1000.0, 0.0], [0.0, 1000.0]])),
        [
            BeamTiltImagePair(
                first_tilt=(0.0, 0.0),
                second_tilt=(0.01, 0.0),
                first_image=first_image,
                second_image=second_image,
            )
        ],
    )
    two_shot_rows = two_shot["measurements"][0].pixel_shift[0]
    assert abs(two_shot_rows - tilt_rows) > abs(corrected_rows - tilt_rows)


def test_three_shot_uses_timestamp_drift_fraction():
    image = _three_shot_scene(seed=43)
    tilt_rows = 5
    drift_total = 10
    drift_fraction = 0.25
    first_image = image
    second_image = np.roll(image, tilt_rows + int(drift_total * drift_fraction), axis=0)
    third_image = np.roll(image, drift_total, axis=0)

    result = solve_objective_focus_from_triple_shots(
        ObjectiveCalibration(np.array([[1000.0, 0.0], [0.0, 1000.0]])),
        [
            BeamTiltTripleShot(
                first_tilt=(0.0, 0.0),
                second_tilt=(0.01, 0.0),
                first_image=first_image,
                second_image=second_image,
                third_image=third_image,
                first_time=0.0,
                second_time=1.0,
                third_time=4.0,
            )
        ],
        taper_fraction=0.0,
    )

    assert np.isclose(result["measurements"][0].pixel_shift[0], tilt_rows, atol=0.6)


def test_solve_objective_focus_from_triple_shots_defocus():
    image = _three_shot_scene(seed=42)
    result = solve_objective_focus_from_triple_shots(
        ObjectiveCalibration(np.array([[1000.0, 0.0], [0.0, 1000.0]])),
        [
            BeamTiltTripleShot(
                first_tilt=(0.0, 0.0),
                second_tilt=(0.01, 0.0),
                first_image=image,
                second_image=np.roll(image, 7, axis=0),
                third_image=np.roll(image, 4, axis=0),
            )
        ],
    )
    # corrected shift is 7 - 4/2 = 5 rows; defocus = 5 / (1000 * 0.01)
    assert np.isclose(result["defocus"], 0.5, atol=0.05)
    assert len(result["shift_results"]) == 2


class FakeObjectiveInstrument:
    def __init__(self, images):
        self.beam_tilt = (0.0, 0.0)
        self.images = list(images)
        self.set_calls = []

    def get_beam_tilt(self):
        return self.beam_tilt

    def set_beam_tilt(self, tilt):
        self.beam_tilt = tilt
        self.set_calls.append(tilt)

    def acquire_image(self):
        if isinstance(self.images[0], Exception):
            raise self.images.pop(0)
        return self.images.pop(0)


class FakeStageInstrument:
    def __init__(self, images):
        self.stage_alpha = 0.25
        self.images = list(images)
        self.set_calls = []

    def get_stage_alpha(self):
        return self.stage_alpha

    def set_stage_alpha(self, alpha):
        self.stage_alpha = alpha
        self.set_calls.append(alpha)

    def acquire_image(self):
        if isinstance(self.images[0], Exception):
            raise self.images.pop(0)
        return self.images.pop(0)


def test_objective_orchestrator_restores_beam_tilt():
    image = _three_shot_scene(seed=44)
    instrument = FakeObjectiveInstrument([image, np.roll(image, 6, axis=0)])
    result = run_objective_focus_sequence(
        instrument,
        ObjectiveCalibration(np.array([[1000.0, 0.0], [0.0, 1000.0]])),
        [((0.0, 0.0), (0.01, 0.0))],
    )

    assert np.isclose(result["defocus"], 0.6, atol=0.05)
    assert instrument.beam_tilt == (0.0, 0.0)


def test_objective_orchestrator_restores_beam_tilt_on_error():
    image = _three_shot_scene(seed=45)
    instrument = FakeObjectiveInstrument([image, RuntimeError("camera failed")])

    with pytest.raises(RuntimeError, match="camera failed"):
        run_objective_focus_sequence(
            instrument,
            ObjectiveCalibration(np.eye(2)),
            [((0.0, 0.0), (0.01, 0.0))],
        )

    assert instrument.beam_tilt == (0.0, 0.0)


def test_stage_z_orchestrator_restores_alpha():
    image = _three_shot_scene(seed=46)
    alpha = 0.1
    col_pixels = 5
    matrix = np.array([[1.0e-9, 0.0], [0.0, 2.0e-9]])
    instrument = FakeStageInstrument([image, np.roll(image, col_pixels, axis=1)])

    result = run_stage_z_sequence(instrument, matrix, [alpha])

    assert np.isclose(result["z"], col_pixels * matrix[1, 1] / np.sin(alpha), rtol=0.05)
    assert instrument.stage_alpha == 0.25
