"""The images list: composite filter, ancestors, search, sort, paging, in SQL."""
from __future__ import annotations

import json
import uuid
from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine, text

import controllers.webapp_controller as web
from services.image_filter import FilterError, compile_filter, parse_filter
from services.image_query import filter_summary, image_path, list_images

SESSION = uuid.uuid4()
# name: (parent, magnification, ctf resolution Å, defocus m)
IMAGES = {
    "gr1": (None, 64, None, None),
    "gr1_sq1": ("gr1", 320, None, None),
    "gr1_sq1_ex1": ("gr1_sq1", 59000, 3.2, -1.5e-6),
    "gr1_sq1_ex2": ("gr1_sq1", 59000, 8.0, -2.0e-6),
    "gr2": (None, 64, None, None),
    "gr2_sq1": ("gr2", 320, None, None),
    "gr2_sq1_ex1": ("gr2_sq1", 59000, 4.5, -1.8e-6),
    "lone_ex%": (None, 59000, None, None),
    "lone_gr": (None, 64, None, None),
}
IDS = {name: uuid.uuid4() for name in IMAGES}


@pytest.fixture
def db():
    engine = create_engine("sqlite://")
    connection = engine.connect()
    connection.execute(text("""CREATE TABLE image (oid BLOB, name TEXT, defocus REAL, dose REAL, magnification INT,
        pixel_size REAL, parent_id BLOB, binning_x INT, session_id BLOB)"""))
    connection.execute(text("CREATE TABLE image_meta_data (image_id BLOB, name TEXT, data_json TEXT)"))
    for name, (parent, mag, resolution, defocus) in IMAGES.items():
        connection.execute(text("""INSERT INTO image VALUES (:o, :n, :d, NULL, :m, 1e-10, :p, 1, :s)"""), {
            "o": IDS[name].bytes, "n": name, "d": defocus, "m": mag, "s": SESSION.bytes,
            "p": IDS[parent].bytes if parent else None})
        if resolution is not None:  # stored as the CTF plugin stores it: the value as JSON text
            ctf = json.dumps({"defocus1": 1e-6, "resolution_50_percent": resolution})
            connection.execute(text("INSERT INTO image_meta_data VALUES (:o, 'CTF Meta Data', :d)"),
                               {"o": IDS[name].bytes, "d": json.dumps([{"key": "CTF", "value": ctf}])})
    # A failed evaluation: a CTF result without a resolution.
    connection.execute(text("INSERT INTO image_meta_data VALUES (:o, 'CTF Meta Data', :d)"), {
        "o": IDS["lone_ex%"].bytes, "d": json.dumps([{"key": "CTF", "value": json.dumps({"defocus1": 1e-6})}])})
    return SimpleNamespace(execute=connection.execute, get_bind=lambda: engine)


def rule(field, operator, value=""):
    return {"kind": "rule", "field": field, "operator": operator, "value": value}


def group(*rules, combinator="and", negate=False):
    return {"kind": "group", "combinator": combinator, "not": negate, "rules": list(rules)}


def names(db, flt=None, **kw):
    kw.setdefault("all_levels", True)
    kw.setdefault("page_size", 100)
    image_filter = parse_filter(json.dumps(flt)) if flt else None
    result = list_images(db, SESSION.bytes, "", {}, image_filter=image_filter, **kw)
    return [image["name"] for image in result["result"]]


def matching(db, flt):
    return sorted(names(db, flt))


def test_numbers_and_missing_values(db):
    assert matching(db, group(rule("resolution", "le", "4"))) == ["gr1_sq1_ex1"]
    # Without a resolution, an image is "not equal" to anything and nothing else.
    assert len(matching(db, group(rule("resolution", "ne", "8")))) == len(IMAGES) - 1
    assert matching(db, group(rule("resolution", "notEmpty"))) == ["gr1_sq1_ex1", "gr1_sq1_ex2", "gr2_sq1_ex1"]
    assert matching(db, group(rule("defocus", "lt", "-1.7"))) == ["gr1_sq1_ex2", "gr2_sq1_ex1"]
    assert matching(db, group(rule("children", "eq", "2"))) == ["gr1_sq1"]


def test_and_or_not_in_nested_groups(db):
    either = group(rule("resolution", "lt", "4"), rule("mag", "eq", "320"), combinator="or")
    assert matching(db, either) == ["gr1_sq1", "gr1_sq1_ex1", "gr2_sq1"]
    # NOT over a group: images without a resolution are kept, as on the page.
    not_either = group(either, negate=True)
    assert "gr1" in matching(db, not_either) and "gr1_sq1_ex1" not in matching(db, not_either)
    nested = group(rule("mag", "eq", "59000"), group(rule("resolution", "le", "5"), negate=True))
    assert matching(db, nested) == ["gr1_sq1_ex2", "lone_ex%"]


def test_names_ignore_case_and_wildcards_are_literal(db):
    assert matching(db, group(rule("name", "contains", "SQ1_EX"))) == ["gr1_sq1_ex1", "gr1_sq1_ex2", "gr2_sq1_ex1"]
    assert matching(db, group(rule("name", "contains", "%"))) == ["lone_ex%"]
    assert matching(db, group(rule("name", "startsWith", "lone"))) == ["lone_ex%", "lone_gr"]
    assert "lone_gr" not in matching(db, group(rule("name", "notContains", "lone")))


def test_unfinished_conditions_are_left_out_and_bad_ones_refused():
    assert compile_filter(parse_filter(json.dumps(group(rule("resolution", "le", ""), rule("mag", "gt", "abc"))))) is None
    with pytest.raises(FilterError):
        compile_filter(parse_filter(json.dumps(group(rule("mag", "contains", "5")))))
    with pytest.raises(FilterError):
        parse_filter(json.dumps(group(rule("drop table", "eq", "1"))))
    deep = group(rule("mag", "eq", "1"))
    for _ in range(7):
        deep = group(deep)
    with pytest.raises(FilterError):
        compile_filter(parse_filter(json.dumps(deep)))


def test_values_are_bound_not_pasted():
    sql, params = compile_filter(parse_filter(json.dumps(group(rule("name", "eq", "x' OR '1'='1")))))
    assert "x'" not in sql and list(params.values()) == ["x' or '1'='1"]


def test_columns_keep_the_images_above_a_match(db):
    good = group(rule("resolution", "le", "5"))
    assert names(db, good, all_levels=False, include_ancestors=True) == ["gr1", "gr2"]
    assert names(db, good, all_levels=False, include_ancestors=True,
                 parent_id=IDS["gr1_sq1"].bytes) == ["gr1_sq1_ex1"]
    # Without ancestors (grid and table) only the matches.
    assert names(db, good) == ["gr1_sq1_ex1", "gr2_sq1_ex1"]


def test_related_first_then_sorting_by_a_field(db):
    assert names(db, all_levels=False) == ["gr1", "gr2", "lone_ex%", "lone_gr"]
    assert names(db, all_levels=False, descending=True) == ["gr2", "gr1", "lone_gr", "lone_ex%"]
    assert names(db, sort="resolution")[:3] == ["gr1_sq1_ex1", "gr2_sq1_ex1", "gr1_sq1_ex2"]
    # Images without the value last, either way.
    assert names(db, sort="resolution", descending=True)[:3] == ["gr1_sq1_ex2", "gr2_sq1_ex1", "gr1_sq1_ex1"]


def test_paging_counts_the_filtered_images(db):
    flt = parse_filter(json.dumps(group(rule("mag", "eq", "59000"))))
    first = list_images(db, SESSION.bytes, "", {}, all_levels=True, image_filter=flt, page=1, page_size=3)
    last = list_images(db, SESSION.bytes, "", {}, all_levels=True, image_filter=flt, page=2, page_size=3)
    assert (first["total_count"], first["next_page"], len(first["result"])) == (4, 2, 3)
    assert (last["next_page"], len(last["result"])) == (None, 1)


def test_search_within_a_level(db):
    assert names(db, all_levels=False, parent_id=IDS["gr1_sq1"].bytes, search="EX2") == ["gr1_sq1_ex2"]


def test_resolution_and_values_come_with_the_image(db):
    image = next(i for i in list_images(db, SESSION.bytes, "", {}, all_levels=True, page_size=100)["result"]
                 if i["name"] == "gr1_sq1_ex1")
    assert (image["resolution"], image["defocus"], image["mag"]) == (3.2, -1.5, 59000)


def test_summary_counts_and_lists_values(db):
    summary = filter_summary(db, SESSION.bytes, "", {}, parse_filter(json.dumps(group(rule("resolution", "le", "5")))))
    assert (summary["total"], summary["matching"]) == (9, 2)
    assert summary["fields"]["mag"]["values"] == [64, 320, 59000]
    assert (summary["fields"]["resolution"]["min"], summary["fields"]["resolution"]["max"],
            summary["fields"]["resolution"]["count"]) == (3.2, 8.0, 3)


def test_path_from_the_top(db):
    assert [i["name"] for i in image_path(db, IDS["gr1_sq1_ex2"].bytes)] == ["gr1", "gr1_sq1", "gr1_sq1_ex2"]


def test_route_refuses_an_invalid_filter(monkeypatch):
    monkeypatch.setattr(web, "check_session_access", lambda *a, **k: True)
    session = SimpleNamespace(oid=SESSION)
    db = SimpleNamespace(query=lambda *a: SimpleNamespace(filter=lambda *a: SimpleNamespace(first=lambda: session)))
    with pytest.raises(HTTPException) as e:
        web.get_images_route(db_session=db, user_id=uuid.uuid4(), session_name="s", parentId=None, page=1,
                             pageSize=10, all_levels=True, filter="{not json", include_ancestors=False,
                             search=None, sort="related", order="asc")
    assert e.value.status_code == 422
