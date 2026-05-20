from cryoassess.core.starfile import (
    micrograph_blockcode,
    read_star,
    star_to_micrograph_list,
    write_star,
)

MINIMAL_STAR = "data_\n\nloop_\n_rlnMicrographName\nmics/a.mrc\nmics/b.mrc\n"

RELION31_STAR = (
    "data_optics\n\n"
    "loop_\n_rlnOpticsGroup\n1\n\n"
    "data_micrographs\n\n"
    "loop_\n_rlnMicrographName\n_rlnOpticsGroup\n"
    "mics/a.mrc 1\nmics/b.mrc 1\n"
)


def test_read_minimal_star(tmp_path):
    path = tmp_path / "m.star"
    path.write_text(MINIMAL_STAR)
    star_df = read_star(path)
    block = micrograph_blockcode(star_df)
    names = list(star_df[block][0]["_rlnMicrographName"])
    assert names == ["mics/a.mrc", "mics/b.mrc"]


def test_star_to_micrograph_list(tmp_path):
    path = tmp_path / "m.star"
    path.write_text(MINIMAL_STAR)
    assert star_to_micrograph_list(path) == ["mics/a.mrc", "mics/b.mrc"]


def test_single_block_uses_that_block():
    star_df = {"data_": [object()]}
    assert micrograph_blockcode(star_df) == "data_"


def test_multi_block_uses_data_micrographs(tmp_path):
    path = tmp_path / "r.star"
    path.write_text(RELION31_STAR)
    star_df = read_star(path)
    assert micrograph_blockcode(star_df) == "data_micrographs"
    assert star_to_micrograph_list(path) == ["mics/a.mrc", "mics/b.mrc"]


def test_write_star_round_trip(tmp_path):
    path = tmp_path / "m.star"
    path.write_text(MINIMAL_STAR)
    star_df = read_star(path)
    out = tmp_path / "out.star"
    write_star(star_df, out)
    assert star_to_micrograph_list(out) == ["mics/a.mrc", "mics/b.mrc"]
