"""The image list: related images first, every level on request, resolution included."""
from __future__ import annotations

import json
import uuid
from types import SimpleNamespace

import pytest
from sqlalchemy import create_engine, text

import controllers.webapp_controller as web

SESSION = uuid.uuid4()
IDS = {name: uuid.uuid4() for name in ("a_lonely", "b_parent", "b_parent_child", "c_lonely", "d_parent", "d_parent_child")}
PARENTS = {"b_parent_child": "b_parent", "d_parent_child": "d_parent"}


def _ctf(resolution):
    return json.dumps([{"key": "CTF", "value": json.dumps({"resolution_50_percent": resolution})}])


@pytest.fixture
def db(monkeypatch):
    engine = create_engine("sqlite://")
    connection = engine.connect()
    connection.execute(text("""CREATE TABLE image (oid BLOB, name TEXT, defocus REAL, dose REAL, magnification REAL,
        pixel_size REAL, parent_id BLOB, binning_x INT, session_id BLOB)"""))
    connection.execute(text("CREATE TABLE image_meta_data (image_id BLOB, name TEXT, data_json TEXT)"))
    for name, oid in IDS.items():
        parent = IDS[PARENTS[name]].bytes if name in PARENTS else None
        connection.execute(text("INSERT INTO image (oid, name, parent_id, session_id) VALUES (:o, :n, :p, :s)"),
                           {"o": oid.bytes, "n": name, "p": parent, "s": SESSION.bytes})
    connection.execute(text("INSERT INTO image_meta_data VALUES (:o, 'CTF Meta Data', :d)"),
                       {"o": IDS["b_parent_child"].bytes, "d": _ctf(3.456)})
    monkeypatch.setattr(web, "check_session_access", lambda *a, **k: True)
    monkeypatch.setattr(web, "get_session_filter_clause", lambda user: ("", {}))
    query = SimpleNamespace(filter=lambda *a: SimpleNamespace(first=lambda: SimpleNamespace(oid=SESSION)))
    return SimpleNamespace(query=lambda *a: query, execute=connection.execute)


def _list(db, all_levels=False):
    return web.get_images_route(db_session=db, user_id=uuid.uuid4(), session_name="s", parentId=None,
                                page=1, pageSize=100, all_levels=all_levels)


def _names(result):
    return [image["name"] for image in result["result"]]


def test_top_level_lists_images_with_children_first(db):
    assert _names(_list(db)) == ["b_parent", "d_parent", "a_lonely", "c_lonely"]


def test_every_level_keeps_children_after_their_parent_and_lonely_images_last(db):
    result = _list(db, all_levels=True)

    assert _names(result) == ["b_parent", "b_parent_child", "d_parent", "d_parent_child", "a_lonely", "c_lonely"]
    assert result["total_count"] == 6


def test_one_parent_lists_only_its_children(db):
    result = web.get_images_route(db_session=db, user_id=uuid.uuid4(), session_name="s",
                                  parentId=IDS["b_parent"], page=1, pageSize=100, all_levels=False)

    assert _names(result) == ["b_parent_child"]


def test_resolution_comes_with_the_image(db):
    by_name = {image["name"]: image for image in _list(db, all_levels=True)["result"]}

    assert by_name["b_parent_child"]["resolution"] == 3.46
    assert by_name["b_parent"]["resolution"] is None


@pytest.mark.parametrize("data, expected", [
    ([{"key": "CTF", "value": {"resolution_50_percent": 4.0}}], 4.0),
    (_ctf(2.5), 2.5),
    ([{"key": "CTF", "value": {"defocus1": 1e-6}}], None),
    (_ctf(float("nan")), None),
    ([{"key": "other", "value": {}}], None),
    (None, None),
    ("not json", None),
])
def test_reading_the_resolution(data, expected):
    assert web.ctf_resolution(data) == expected
