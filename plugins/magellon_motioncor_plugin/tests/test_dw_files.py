"""Both dose-weighted sums are found by name, never by file-system order."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

utils = pytest.importorskip("utils")


def _touch(folder, *names):
    for name in names:
        (folder / name).write_bytes(b"")


def test_both_files_are_returned_by_their_own_suffix(tmp_path):
    _touch(tmp_path, "movie.mrc", "movie_DWS.mrc", "movie_DW.mrc")
    dw, dws = utils.get_dw_files(str(tmp_path))
    assert dw.endswith("movie_DW.mrc")
    assert dws.endswith("movie_DWS.mrc")
    assert utils.get_dw_file(str(tmp_path)) == dw


def test_dws_alone_is_still_the_main_result(tmp_path):
    _touch(tmp_path, "movie_DWS.mrc")
    assert utils.get_dw_files(str(tmp_path))[0] is None
    assert utils.get_dw_file(str(tmp_path)).endswith("movie_DWS.mrc")


def test_nothing_written_gives_none(tmp_path):
    _touch(tmp_path, "movie.mrc")
    assert utils.get_dw_files(str(tmp_path)) == (None, None)
    assert utils.get_dw_file(str(tmp_path)) is None
