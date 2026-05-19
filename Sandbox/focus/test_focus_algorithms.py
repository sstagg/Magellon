import numpy as np

try:
    from focus.mock_inputs import objective_focus_demo, shifted_image_demo, z_focus_demo
    from focus.objective_focus import BeamTiltMeasurement, solve_defocus_stig
    from focus.z_focus import StageTiltMeasurement, solve_stage_z
except ModuleNotFoundError:
    from magellon_focus_extract.mock_inputs import objective_focus_demo, shifted_image_demo, z_focus_demo
    from magellon_focus_extract.objective_focus import BeamTiltMeasurement, solve_defocus_stig
    from magellon_focus_extract.z_focus import StageTiltMeasurement, solve_stage_z


def test_correlate_shift_integer_roll():
    demo = shifted_image_demo((6, -5))
    assert np.allclose(demo["measured_shift"], (6, -5), atol=0.25)


def test_objective_focus_solve_defocus_only():
    matrix = np.array([[1000.0, 0.0], [0.0, 1000.0]])
    measurement = BeamTiltMeasurement((0.01, 0.0), (2.0e-5, 0.0))
    result = solve_defocus_stig(matrix, [measurement])
    assert np.isclose(result["defocus"], 2.0e-6)
    assert result["stigx"] is None
    assert result["stigy"] is None


def test_objective_focus_demo_with_stig():
    result = objective_focus_demo()
    assert np.isclose(result["defocus"], 2.0e-6)
    assert np.isclose(result["stigx"], -0.4e-6)
    assert np.isclose(result["stigy"], 0.7e-6)


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


def test_z_focus_demo():
    result = z_focus_demo()
    assert np.isclose(result["z"], 1.5e-6)
