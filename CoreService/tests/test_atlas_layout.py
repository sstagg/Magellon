"""The atlas picture shows every tile, at one scale, inside the square."""
import json
from types import SimpleNamespace

from PIL import Image

from services import atlas


def _build(tmp_path, monkeypatch, positions):
    images = tmp_path / "s" / "images"
    images.mkdir(parents=True)
    settings = SimpleNamespace(directory_settings=SimpleNamespace(MAGELLON_HOME_DIR=str(tmp_path)))
    monkeypatch.setattr(atlas, "app_settings", settings)
    tiles = []
    for i, (row, column) in enumerate(positions):
        Image.new("RGB", (100, 100), "white").save(images / f"t{i}.png")
        tiles.append({"id": i, "dimx": 100, "dimy": 100, "filename": f"t{i}",
                      "delta_row": row, "delta_column": column})
    out = tmp_path / "atlas.png"
    html, _ = atlas.create_atlas_picture("s", tiles, 1600, 1600, "black", str(out))
    coords = [[int(n) for n in a["coords"].split()] for a in json.loads(html)["areas"]]
    return coords, Image.open(out).convert("L")


def test_a_single_column_is_not_cut_off_or_stretched(tmp_path, monkeypatch):
    coords, picture = _build(tmp_path, monkeypatch, [(0, 0), (100, 0), (200, 0), (300, 0)])
    assert all(c[2] == c[3] for c in coords)
    assert max(c[1] + c[3] for c in coords) <= 1600
    assert [c[1] for c in coords] == sorted(c[1] for c in coords)
    assert picture.getbbox() == (600, 0, 1000, 1600)


def test_columns_run_across_and_rows_run_down(tmp_path, monkeypatch):
    coords, _ = _build(tmp_path, monkeypatch, [(0, 0), (0, 300)])
    assert coords[1][0] > coords[0][0]
    assert coords[1][1] == coords[0][1]


def test_a_full_grid_fills_the_square(tmp_path, monkeypatch):
    coords, picture = _build(tmp_path, monkeypatch, [(r, c) for r in (0, 100) for c in (0, 100)])
    assert picture.getbbox() == (0, 0, 1600, 1600)
    assert max(c[0] + c[2] for c in coords) <= 1600
