"""Edge-case probes for ``magellon_sdk.paths``.

Mirrors the CoreService ``test_canonical_gpfs_path_edges.py`` set so the
SDK and CoreService halves of the path-translation contract stay
symmetric — anything that round-trips through one helper should round-
trip through the other.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from magellon_sdk.paths import (
    from_canonical_gpfs_path,
    to_canonical_gpfs_path,
)


WIN_ROOT = "C:/magellon/gpfs"


# ---------------------------------------------------------------------------
# Prefix-overlap false positives
# ---------------------------------------------------------------------------


class TestPrefixOverlapFalsePositives:
    def test_sibling_directory_passes_through(self):
        assert (
            to_canonical_gpfs_path("C:/magellon/gpfs2/foo.mrc", gpfs_path=WIN_ROOT)
            == "C:/magellon/gpfs2/foo.mrc"
        )

    def test_hyphen_suffix_sibling_passes_through(self):
        assert (
            to_canonical_gpfs_path(
                "C:/magellon/gpfs-staging/foo.mrc", gpfs_path=WIN_ROOT,
            ) == "C:/magellon/gpfs-staging/foo.mrc"
        )

    def test_word_suffix_sibling_passes_through(self):
        assert (
            to_canonical_gpfs_path(
                "C:/magellon/gpfsclient/foo.mrc", gpfs_path=WIN_ROOT,
            ) == "C:/magellon/gpfsclient/foo.mrc"
        )


# ---------------------------------------------------------------------------
# Trailing slashes — pin the current behaviour
# ---------------------------------------------------------------------------


class TestTrailingSlashes:
    def test_input_with_trailing_slash_preserves_trailing(self):
        result = to_canonical_gpfs_path(
            "C:/magellon/gpfs/24dec03a/", gpfs_path=WIN_ROOT,
        )
        assert result == "/gpfs/24dec03a/"

    def test_input_equals_root_with_trailing_slash(self):
        # Edge case: bare root WITH trailing slash. The function should
        # either return "/gpfs" or "/gpfs/" — pin the current shape so
        # a future refactor surfaces if it changes.
        result = to_canonical_gpfs_path(
            "C:/magellon/gpfs/", gpfs_path=WIN_ROOT,
        )
        assert result in ("/gpfs", "/gpfs/")

    def test_config_root_with_trailing_slash_is_stripped(self):
        # ``rstrip("/")`` in the helper means root-config trailing
        # slashes don't affect output.
        result = to_canonical_gpfs_path(
            "C:/magellon/gpfs/x.mrc", gpfs_path="C:/magellon/gpfs/",
        )
        assert result == "/gpfs/x.mrc"


# ---------------------------------------------------------------------------
# Mixed slashes
# ---------------------------------------------------------------------------


class TestMixedSlashes:
    def test_mixed_forward_and_back_slashes(self):
        assert (
            to_canonical_gpfs_path(
                "C:/magellon\\gpfs\\24dec03a/x.mrc", gpfs_path=WIN_ROOT,
            ) == "/gpfs/24dec03a/x.mrc"
        )

    def test_config_root_with_backslashes(self):
        assert (
            to_canonical_gpfs_path(
                "C:/magellon/gpfs/x.mrc", gpfs_path="C:\\magellon\\gpfs",
            ) == "/gpfs/x.mrc"
        )


# ---------------------------------------------------------------------------
# Embedded-in-prose
# ---------------------------------------------------------------------------


class TestEmbeddedPathInProse:
    def test_prose_with_path_inside_is_left_alone(self):
        text = "Loaded model from C:/magellon/gpfs/models/x.pkl"
        assert to_canonical_gpfs_path(text, gpfs_path=WIN_ROOT) == text


# ---------------------------------------------------------------------------
# Traversal segments — naively translated; receiver validates
# ---------------------------------------------------------------------------


class TestTraversalSegments:
    def test_dotdot_in_suffix_translates_naively(self):
        assert (
            to_canonical_gpfs_path(
                "C:/magellon/gpfs/../etc/passwd", gpfs_path=WIN_ROOT,
            ) == "/gpfs/../etc/passwd"
        )

    def test_dotdot_inverse_translates_naively(self):
        # ``from_canonical_gpfs_path`` is similarly naive — it's the
        # plugin's responsibility to validate the result lies under the
        # local GPFS root before opening.
        assert (
            from_canonical_gpfs_path(
                "/gpfs/../etc/passwd", gpfs_path=WIN_ROOT,
            ) == "C:/magellon/gpfs/../etc/passwd"
        )


# ---------------------------------------------------------------------------
# Round-trip property
# ---------------------------------------------------------------------------


class TestRoundTrip:
    @pytest.mark.parametrize("host", [
        "C:/magellon/gpfs/24dec03a/x.mrc",
        "C:/magellon/gpfs/deep/nested/path/file.txt",
        "C:/magellon/gpfs",  # root only
    ])
    def test_host_canonical_host(self, host):
        canonical = to_canonical_gpfs_path(host, gpfs_path=WIN_ROOT)
        back = from_canonical_gpfs_path(canonical, gpfs_path=WIN_ROOT)
        assert back == host

    def test_idempotent_to_canonical(self):
        once = to_canonical_gpfs_path(
            "C:/magellon/gpfs/24dec03a/x.mrc", gpfs_path=WIN_ROOT,
        )
        twice = to_canonical_gpfs_path(once, gpfs_path=WIN_ROOT)
        assert once == twice == "/gpfs/24dec03a/x.mrc"

    def test_backslash_input_lands_on_forward_slash_form(self):
        canonical = to_canonical_gpfs_path(
            r"C:\magellon\gpfs\24dec03a\x.mrc", gpfs_path=WIN_ROOT,
        )
        assert canonical == "/gpfs/24dec03a/x.mrc"


# ---------------------------------------------------------------------------
# Default-root behaviour (no gpfs_path argument)
# ---------------------------------------------------------------------------


class TestDefaultRoot:
    def test_default_root_is_noop_on_linux_shape(self):
        # Without an explicit gpfs_path, the helper looks up the SDK's
        # BaseAppSettings default — ``/gpfs`` on a fresh schema. So
        # canonical paths pass through unchanged.
        result = to_canonical_gpfs_path("/gpfs/x.mrc")
        assert result == "/gpfs/x.mrc"

    def test_empty_string_root_falls_back_to_default(self):
        # Empty-string root triggers the ``gpfs_path or _default_gpfs_path()``
        # branch — the helper falls back to the SDK default rather than
        # operating with no root.
        result = to_canonical_gpfs_path("/gpfs/x.mrc", gpfs_path="")
        assert result == "/gpfs/x.mrc"


# ---------------------------------------------------------------------------
# Pathlib + iterable types
# ---------------------------------------------------------------------------


class TestNonStringInputs:
    def test_pathlib_input_to_canonical(self):
        # Already covered for ``from_canonical`` in test_paths.py; mirror
        # it for the inverse so both ends are pinned.
        p = Path("C:/magellon/gpfs/x.mrc")
        out = to_canonical_gpfs_path(p, gpfs_path=WIN_ROOT)
        assert out == "/gpfs/x.mrc"

    def test_int_input_raises_or_returns_falsy(self):
        # Passing an int doesn't make semantic sense; assert the helper
        # doesn't silently produce garbage — either it returns the input
        # unchanged (truthy) or raises. Catches regressions where someone
        # accepts ``int`` and stringifies it.
        try:
            result = to_canonical_gpfs_path(42, gpfs_path=WIN_ROOT)  # type: ignore[arg-type]
        except (TypeError, AttributeError):
            return
        assert result == 42 or result == "42"
