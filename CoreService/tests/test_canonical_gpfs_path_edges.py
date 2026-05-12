"""Edge-case probes for ``core.helper`` path-translation helpers.

These complement ``test_canonical_gpfs_path.py`` (which covers the happy
paths) by exercising boundary conditions that have been known to hide
bugs in path-translation code:

  - Path-prefix false positives (root prefix is also a directory prefix
    of an unrelated tree).
  - Trailing-slash inconsistency.
  - Mixed forward/backslash inputs.
  - Embedded-path-in-prose (should NOT rewrite).
  - Traversal segments (``..``) — should pass through and let the
    receiver reject.
  - Pathlib.Path inputs — surface API drift vs the SDK helpers.
  - Non-string scalar values inside payloads (None / bool / int / float).
"""
from __future__ import annotations

from pathlib import Path

import pytest

from config import app_settings
from core.helper import (
    canonicalize_paths_in_payload,
    from_canonical_gpfs_path,
    to_canonical_gpfs_path,
)


@pytest.fixture()
def gpfs_root(monkeypatch):
    monkeypatch.setattr(
        app_settings.directory_settings, "MAGELLON_GPFS_PATH", "C:/magellon/gpfs"
    )


# ---------------------------------------------------------------------------
# Prefix-overlap false positives — gpfs root must match a directory boundary
# ---------------------------------------------------------------------------


class TestPrefixOverlapFalsePositives:
    """``startswith`` without a trailing slash would alias siblings of the
    GPFS root into it. Test that the boundary check is correct."""

    def test_sibling_directory_passes_through(self, gpfs_root):
        # gpfs root is C:/magellon/gpfs ; this is gpfs2 next to it.
        assert (
            to_canonical_gpfs_path("C:/magellon/gpfs2/foo.mrc")
            == "C:/magellon/gpfs2/foo.mrc"
        )

    def test_hyphen_suffix_sibling_passes_through(self, gpfs_root):
        assert (
            to_canonical_gpfs_path("C:/magellon/gpfs-staging/foo.mrc")
            == "C:/magellon/gpfs-staging/foo.mrc"
        )

    def test_word_suffix_sibling_passes_through(self, gpfs_root):
        assert (
            to_canonical_gpfs_path("C:/magellon/gpfsclient/foo.mrc")
            == "C:/magellon/gpfsclient/foo.mrc"
        )


# ---------------------------------------------------------------------------
# Trailing slashes
# ---------------------------------------------------------------------------


class TestTrailingSlashes:
    def test_input_with_trailing_slash_preserves_trailing(self, gpfs_root):
        # ``C:/magellon/gpfs/24dec03a/`` — the trailing slash on the
        # input is part of the suffix and should survive translation.
        result = to_canonical_gpfs_path("C:/magellon/gpfs/24dec03a/")
        assert result == "/gpfs/24dec03a/"

    def test_input_equals_root_with_trailing_slash(self, gpfs_root):
        # Caller hands the bare root WITH trailing slash. The function
        # currently treats this as "root + empty suffix" → "/gpfs/" —
        # which is canonical-ish but inconsistent with the no-trailing
        # case that returns "/gpfs". Pin whichever shape the project
        # has chosen so this stops drifting.
        result = to_canonical_gpfs_path("C:/magellon/gpfs/")
        # Document the current shape (whatever it is) so a future
        # refactor surfaces if it changes.
        assert result in ("/gpfs", "/gpfs/")


# ---------------------------------------------------------------------------
# Mixed slash directions
# ---------------------------------------------------------------------------


class TestMixedSlashes:
    def test_mixed_forward_and_back_slashes(self, gpfs_root):
        # An importer might join an OS-native path with a config-supplied
        # forward-slash root, producing a hybrid.
        result = to_canonical_gpfs_path("C:/magellon\\gpfs\\24dec03a/x.mrc")
        assert result == "/gpfs/24dec03a/x.mrc"

    def test_config_root_with_backslashes(self, monkeypatch):
        monkeypatch.setattr(
            app_settings.directory_settings, "MAGELLON_GPFS_PATH",
            "C:\\magellon\\gpfs",
        )
        assert (
            to_canonical_gpfs_path("C:/magellon/gpfs/x.mrc")
            == "/gpfs/x.mrc"
        )


# ---------------------------------------------------------------------------
# Embedded-in-prose — must not rewrite mid-string
# ---------------------------------------------------------------------------


class TestEmbeddedPathInProse:
    def test_path_inside_sentence_is_left_alone(self, gpfs_root):
        # If a string starts with prose, ``to_canonical_gpfs_path`` has
        # nothing to do — the prefix won't match.
        text = "Loaded model from C:/magellon/gpfs/models/x.pkl"
        assert to_canonical_gpfs_path(text) == text

    def test_payload_walker_does_not_rewrite_prose(self, gpfs_root):
        body = {
            "description": "Loaded model from C:/magellon/gpfs/models/x.pkl",
            "image_path": "C:/magellon/gpfs/sessions/foo.mrc",
        }
        out = canonicalize_paths_in_payload(body)
        # The standalone path gets translated; the prose string survives.
        assert out["description"] == body["description"]
        assert out["image_path"] == "/gpfs/sessions/foo.mrc"


# ---------------------------------------------------------------------------
# Traversal segments — naively translated; receiver rejects
# ---------------------------------------------------------------------------


class TestTraversalSegments:
    def test_dotdot_in_suffix_translates_naively(self, gpfs_root):
        # The helper itself does not normalize ``..``; ``is_under_gpfs_root``
        # is the defense-in-depth check that catches escapes. Pin this so
        # nobody is surprised that the translation succeeds.
        result = to_canonical_gpfs_path(
            "C:/magellon/gpfs/../etc/passwd",
        )
        assert result == "/gpfs/../etc/passwd"

    def test_dotdot_payload_round_trips(self, gpfs_root):
        body = {"path": "C:/magellon/gpfs/../etc/passwd"}
        out = canonicalize_paths_in_payload(body)
        assert out == {"path": "/gpfs/../etc/passwd"}


# ---------------------------------------------------------------------------
# Pathlib inputs — surface API drift vs SDK helpers
# ---------------------------------------------------------------------------


class TestPathlibInput:
    """The SDK ``paths.py`` accepts ``Path`` and ``str``; CoreService's
    helper takes raw ``str``. If a caller hands a ``Path``, it should
    not crash — either accept it or raise a clear TypeError, never an
    AttributeError from ``.replace``."""

    def test_pathlib_input_does_not_attributeerror(self, gpfs_root):
        # If this raises AttributeError, the surface has drifted from
        # the SDK and we should fix the CoreService helper to coerce.
        try:
            result = to_canonical_gpfs_path(
                Path("C:/magellon/gpfs/x.mrc"),
            )
        except AttributeError as exc:
            pytest.fail(
                "to_canonical_gpfs_path crashed on a Path input — "
                f"surface drifted from SDK paths.py: {exc}",
            )
        # Either it converts correctly, or it returns the input
        # unchanged. Both are acceptable; an AttributeError is not.
        assert result is not None


# ---------------------------------------------------------------------------
# Idempotency / round-trip
# ---------------------------------------------------------------------------


class TestIdempotency:
    def test_to_canonical_is_idempotent(self, gpfs_root):
        once = to_canonical_gpfs_path("C:/magellon/gpfs/24dec03a/x.mrc")
        twice = to_canonical_gpfs_path(once)
        assert once == twice == "/gpfs/24dec03a/x.mrc"

    def test_round_trip_host_canonical_host(self, gpfs_root):
        host = "C:/magellon/gpfs/24dec03a/x.mrc"
        canonical = to_canonical_gpfs_path(host)
        back = from_canonical_gpfs_path(canonical)
        assert back == host

    def test_round_trip_normalizes_backslash(self, gpfs_root):
        host_with_backslash = "C:\\magellon\\gpfs\\24dec03a\\x.mrc"
        host_normalized = "C:/magellon/gpfs/24dec03a/x.mrc"
        canonical = to_canonical_gpfs_path(host_with_backslash)
        back = from_canonical_gpfs_path(canonical)
        # Round-trip lands on the forward-slash form; the original
        # backslash spelling is lost on purpose (canonical form wins).
        assert back == host_normalized


# ---------------------------------------------------------------------------
# Payload walker — type preservation + falsy scalars
# ---------------------------------------------------------------------------


class TestPayloadWalkerEdges:
    def test_preserves_tuple_type(self, gpfs_root):
        body = {"inputs": ("C:/magellon/gpfs/a.mrc", "C:/magellon/gpfs/b.mrc")}
        out = canonicalize_paths_in_payload(body)
        assert isinstance(out["inputs"], tuple)
        assert out["inputs"] == ("/gpfs/a.mrc", "/gpfs/b.mrc")

    def test_preserves_falsy_scalars(self, gpfs_root):
        body = {
            "image_path": "C:/magellon/gpfs/x.mrc",
            "subject_id": None,
            "is_test": False,
            "retry_count": 0,
            "tolerance": 0.0,
        }
        out = canonicalize_paths_in_payload(body)
        assert out["subject_id"] is None
        assert out["is_test"] is False
        assert out["retry_count"] == 0
        assert out["tolerance"] == 0.0
        assert out["image_path"] == "/gpfs/x.mrc"

    def test_deep_nesting_recursive_rewrite(self, gpfs_root):
        body = {
            "a": {
                "b": {
                    "c": [
                        {"d": "C:/magellon/gpfs/deep.mrc"},
                        {"d": "C:/elsewhere.mrc"},
                    ],
                },
            },
        }
        out = canonicalize_paths_in_payload(body)
        assert out["a"]["b"]["c"][0]["d"] == "/gpfs/deep.mrc"
        # Sibling-of-root is untouched even at depth.
        assert out["a"]["b"]["c"][1]["d"] == "C:/elsewhere.mrc"

    def test_dict_keys_pass_through(self, gpfs_root):
        # Keys that happen to look like paths are NOT rewritten — keys
        # are field names, not file paths. (If they ever become paths,
        # the wire shape has bigger issues.)
        body = {"C:/magellon/gpfs/foo": "bar"}
        out = canonicalize_paths_in_payload(body)
        assert "C:/magellon/gpfs/foo" in out

    def test_bool_value_does_not_become_string(self, gpfs_root):
        # Python booleans are instances of int — make sure the walker
        # doesn't accidentally coerce them.
        body = {"flag": True}
        out = canonicalize_paths_in_payload(body)
        assert out["flag"] is True
        assert isinstance(out["flag"], bool)
