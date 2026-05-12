"""Unit tests for ``magellon_sdk.cache`` (PE2 helpers).

Pure functions — we exercise the determinism guarantees the
dispatch-cache lookup relies on:

  - Same input set in any order → same hash.
  - Same params dict in any insertion order → same hash.
  - None / empty inputs are stable sentinels.
  - UUID and str inputs interoperate.
  - Path / UUID values inside params don't break json.dumps.
"""
from __future__ import annotations

from pathlib import Path
from uuid import UUID, uuid4

from magellon_sdk.cache import (
    compute_cache_key,
    compute_input_set_hash,
    compute_params_hash,
)


# ---------------------------------------------------------------------------
# input_set_hash
# ---------------------------------------------------------------------------


class TestInputSetHash:
    def test_empty_input_is_stable_sentinel(self):
        assert compute_input_set_hash([]) == compute_input_set_hash([])

    def test_none_and_empty_filtered_out(self):
        oid = uuid4()
        assert compute_input_set_hash([oid, None, ""]) == compute_input_set_hash([oid])

    def test_order_independent(self):
        a, b, c = uuid4(), uuid4(), uuid4()
        h1 = compute_input_set_hash([a, b, c])
        h2 = compute_input_set_hash([c, a, b])
        h3 = compute_input_set_hash([b, c, a])
        assert h1 == h2 == h3

    def test_uuid_and_str_interoperate(self):
        oid = uuid4()
        assert compute_input_set_hash([oid]) == compute_input_set_hash([str(oid)])

    def test_different_oids_differ(self):
        assert compute_input_set_hash([uuid4()]) != compute_input_set_hash([uuid4()])

    def test_subset_differs(self):
        a, b = uuid4(), uuid4()
        assert compute_input_set_hash([a]) != compute_input_set_hash([a, b])

    def test_hex_format(self):
        out = compute_input_set_hash([uuid4()])
        # SHA-256 hex is 64 lower-case hex chars.
        assert len(out) == 64
        assert all(c in "0123456789abcdef" for c in out)


# ---------------------------------------------------------------------------
# params_hash
# ---------------------------------------------------------------------------


class TestParamsHash:
    def test_none_and_empty_equal(self):
        assert compute_params_hash(None) == compute_params_hash({})

    def test_key_order_independent(self):
        h1 = compute_params_hash({"a": 1, "b": 2, "c": 3})
        h2 = compute_params_hash({"c": 3, "a": 1, "b": 2})
        assert h1 == h2

    def test_int_vs_float_differ(self):
        # ``1`` and ``1.0`` are distinct in JSON canonical form.
        assert compute_params_hash({"n": 1}) != compute_params_hash({"n": 1.0})

    def test_nested_dict_order_independent(self):
        h1 = compute_params_hash({"engine_opts": {"x": 1, "y": 2}})
        h2 = compute_params_hash({"engine_opts": {"y": 2, "x": 1}})
        assert h1 == h2

    def test_uuid_value_stringified(self):
        oid = uuid4()
        # default=str coerces UUID — must not crash and must be stable.
        h1 = compute_params_hash({"id": oid})
        h2 = compute_params_hash({"id": str(oid)})
        assert h1 == h2

    def test_path_value_stringified(self):
        p = Path("/gpfs/foo.mrc")
        # default=str handles Path; the hash matches the equivalent string.
        h1 = compute_params_hash({"path": p})
        h2 = compute_params_hash({"path": str(p)})
        assert h1 == h2

    def test_different_values_differ(self):
        assert compute_params_hash({"n": 1}) != compute_params_hash({"n": 2})


# ---------------------------------------------------------------------------
# compute_cache_key — composite
# ---------------------------------------------------------------------------


class TestCacheKey:
    def test_identical_args_yield_identical_key(self):
        oid = uuid4()
        params = {"box_size": 256, "apix": 1.0}
        k1 = compute_cache_key(
            plugin_id="stack-maker", plugin_version="1.0.0",
            category="PARTICLE_EXTRACTION",
            input_oids=[oid], params=params,
        )
        k2 = compute_cache_key(
            plugin_id="stack-maker", plugin_version="1.0.0",
            category="PARTICLE_EXTRACTION",
            input_oids=[oid], params=dict(params),
        )
        assert k1 == k2

    def test_version_bump_changes_key(self):
        oid = uuid4()
        k1 = compute_cache_key(
            plugin_id="stack-maker", plugin_version="1.0.0",
            category="PARTICLE_EXTRACTION",
            input_oids=[oid], params={"box_size": 256},
        )
        k2 = compute_cache_key(
            plugin_id="stack-maker", plugin_version="1.1.0",
            category="PARTICLE_EXTRACTION",
            input_oids=[oid], params={"box_size": 256},
        )
        assert k1 != k2

    def test_category_changes_key(self):
        oid = uuid4()
        k1 = compute_cache_key(
            plugin_id="x", plugin_version="1",
            category="CTF",
            input_oids=[oid], params={},
        )
        k2 = compute_cache_key(
            plugin_id="x", plugin_version="1",
            category="FFT",
            input_oids=[oid], params={},
        )
        assert k1 != k2

    def test_input_order_does_not_change_key(self):
        a, b = uuid4(), uuid4()
        k1 = compute_cache_key(
            plugin_id="x", plugin_version="1",
            category="X", input_oids=[a, b], params={},
        )
        k2 = compute_cache_key(
            plugin_id="x", plugin_version="1",
            category="X", input_oids=[b, a], params={},
        )
        assert k1 == k2
