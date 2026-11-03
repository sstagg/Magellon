"""Finding a Leginon image's movie among the session's files."""
from core.file_utils import find_matching_file
from services.leginon_frame_transfer_job_service import find_movie, index_movies


def _session(tmp_path, *names):
    raw = tmp_path / "rawdata"
    raw.mkdir()
    for name in names:
        (raw / name).write_bytes(b"")
    return tmp_path, str(raw)


def test_movie_named_after_its_frame(tmp_path):
    root, raw = _session(tmp_path, "20241203_54552_integrated_movie.mrc.tif")
    name = "20241203_54552_integrated_movie.mrc"
    assert find_movie(index_movies(str(root)), name, "24dec03a_00001ex") == (name, raw)


def test_movie_named_after_its_image(tmp_path):
    root, raw = _session(tmp_path, "26oct27a_00003ex.tif", "26oct27a_00003ex.txt")
    assert find_movie(index_movies(str(root)), "20261028_1641001_0_movie.mrc", "26oct27a_00003ex") == (
        "26oct27a_00003ex", raw)


def test_frame_name_wins_over_image_name(tmp_path):
    root, _ = _session(tmp_path, "frame_1.mrc.tif", "image_1.tif")
    assert find_movie(index_movies(str(root)), "frame_1.mrc", "image_1")[0] == "frame_1.mrc"


def test_missing_movie_keeps_the_frame_name_for_the_error(tmp_path):
    root, _ = _session(tmp_path, "other.tif")
    assert find_movie(index_movies(str(root)), "frame_1.mrc", "image_1") == ("frame_1.mrc", None)


def test_image_without_a_frame_has_no_movie(tmp_path):
    root, _ = _session(tmp_path, "image_1.tif")
    assert find_movie(index_movies(str(root)), None, "image_1") == (None, None)


def test_gain_is_never_taken_for_a_movie(tmp_path):
    root, _ = _session(tmp_path, "image_1_gain_ref.tif")
    assert find_movie(index_movies(str(root)), "f.mrc", "image_1_gain_ref") == ("f.mrc", None)


def test_exact_name_beats_a_longer_name_with_the_same_start(tmp_path):
    _, raw = _session(tmp_path, "x_00002ex_v01.tif", "x_00002ex.tif")
    assert find_matching_file(raw, "x_00002ex").endswith("x_00002ex.tif")


def test_movie_format_still_beats_an_exact_mrc_image_beside_it(tmp_path):
    _, raw = _session(tmp_path, "x_00002ex.mrc", "x_00002ex_fractions.tif")
    assert find_matching_file(raw, "x_00002ex").endswith("x_00002ex_fractions.tif")


def test_frame_name_with_an_extra_extension_is_still_found(tmp_path):
    _, raw = _session(tmp_path, "f.mrc.tif")
    assert find_matching_file(raw, "f.mrc").endswith("f.mrc.tif")
