"""Property-style probes for ``canonicalize_paths_in_payload``.

A real hypothesis-driven suite would generate richer payload shapes;
since hypothesis isn't a project dependency, this file rolls its own
randomization with ``random`` + a deterministic seed so failures
reproduce on rerun.

Properties tested:

  1. Idempotency: applying the walker twice equals applying it once.
  2. Type-preserving: every value in the output payload has the same
     type as the corresponding value in the input.
  3. Non-targeted strings pass through unchanged (no false rewrites).
  4. Recursion preserves dict/list/tuple nesting depth.
  5. Linux deployment (root='/gpfs') is a pure no-op.
"""
from __future__ import annotations

import random
import string
from typing import Any

import pytest

from config import app_settings
from core.helper import canonicalize_paths_in_payload, to_canonical_gpfs_path


SEED = 1234567  # deterministic; bump if a failure reveals a regression
ITERATIONS = 200


@pytest.fixture()
def gpfs_windows(monkeypatch):
    monkeypatch.setattr(
        app_settings.directory_settings, "MAGELLON_GPFS_PATH", "C:/magellon/gpfs",
    )


@pytest.fixture()
def gpfs_linux(monkeypatch):
    monkeypatch.setattr(
        app_settings.directory_settings, "MAGELLON_GPFS_PATH", "/gpfs",
    )


# ---------------------------------------------------------------------------
# Random payload generator
# ---------------------------------------------------------------------------


def _random_scalar(rng: random.Random) -> Any:
    """Pick a random scalar — string, int, float, bool, or None."""
    bucket = rng.randint(0, 6)
    if bucket == 0:
        return None
    if bucket == 1:
        return rng.randint(-1000, 1000)
    if bucket == 2:
        return rng.uniform(-1000, 1000)
    if bucket == 3:
        return rng.choice([True, False])
    if bucket == 4:
        # A path-like string under the GPFS root.
        depth = rng.randint(1, 5)
        parts = [
            "".join(rng.choices(string.ascii_lowercase + string.digits, k=8))
            for _ in range(depth)
        ]
        return "C:/magellon/gpfs/" + "/".join(parts)
    if bucket == 5:
        # A path-like string outside the GPFS root.
        return "C:/elsewhere/" + "".join(
            rng.choices(string.ascii_lowercase, k=8),
        )
    # Random unrelated string.
    return "".join(rng.choices(string.ascii_letters + " ", k=rng.randint(1, 30)))


def _random_payload(rng: random.Random, depth: int = 3) -> Any:
    if depth == 0:
        return _random_scalar(rng)
    kind = rng.choice(["dict", "list", "tuple", "scalar"])
    if kind == "scalar":
        return _random_scalar(rng)
    if kind == "dict":
        n = rng.randint(0, 5)
        return {
            f"k{i}": _random_payload(rng, depth - 1) for i in range(n)
        }
    if kind == "list":
        n = rng.randint(0, 5)
        return [_random_payload(rng, depth - 1) for _ in range(n)]
    # tuple
    n = rng.randint(0, 5)
    return tuple(_random_payload(rng, depth - 1) for _ in range(n))


def _types_match(a: Any, b: Any) -> bool:
    """Compare top-level types — recursing for collections."""
    if type(a) is not type(b):
        # Allow bool / int equivalence — they're distinct types but
        # bool is a subclass of int, harmless to swap.
        if isinstance(a, bool) and isinstance(b, bool):
            return True
        return False
    if isinstance(a, dict):
        if set(a) != set(b):
            return False
        return all(_types_match(a[k], b[k]) for k in a)
    if isinstance(a, (list, tuple)):
        if len(a) != len(b):
            return False
        return all(_types_match(x, y) for x, y in zip(a, b))
    return True


# ---------------------------------------------------------------------------
# Property tests
# ---------------------------------------------------------------------------


class TestProperties:
    def test_idempotent_under_repeated_application(self, gpfs_windows):
        rng = random.Random(SEED)
        for _ in range(ITERATIONS):
            payload = _random_payload(rng)
            once = canonicalize_paths_in_payload(payload)
            twice = canonicalize_paths_in_payload(once)
            assert once == twice, (
                f"non-idempotent on payload: {payload!r} → "
                f"once={once!r} twice={twice!r}"
            )

    def test_types_preserved_through_walk(self, gpfs_windows):
        rng = random.Random(SEED + 1)
        for _ in range(ITERATIONS):
            payload = _random_payload(rng)
            out = canonicalize_paths_in_payload(payload)
            assert _types_match(payload, out), (
                f"type drift: {payload!r} → {out!r}"
            )

    def test_strings_outside_root_unchanged(self, gpfs_windows):
        """Any string that doesn't start with the GPFS root must come
        through identical. The walker shouldn't 'help'."""
        rng = random.Random(SEED + 2)
        for _ in range(ITERATIONS):
            # Generate strings that are NOT under the root.
            choice = rng.choice([
                "/etc/passwd",
                "C:/elsewhere/" + "".join(rng.choices(string.ascii_lowercase, k=6)),
                "just a normal sentence about C:/magellon/gpfs/x",
                "" if rng.random() < 0.5 else "no path here at all",
                "https://magellon.org/v1/plugins/foo.json",
            ])
            out = canonicalize_paths_in_payload(choice)
            assert out == choice, (
                f"unexpected rewrite of unrelated string: {choice!r} → {out!r}"
            )

    def test_linux_deployment_is_pure_noop(self, gpfs_linux):
        """When MAGELLON_GPFS_PATH=/gpfs the walker must be the
        identity function — no allocations needed, no string rewrites."""
        rng = random.Random(SEED + 3)
        for _ in range(ITERATIONS):
            payload = _random_payload(rng)
            out = canonicalize_paths_in_payload(payload)
            assert out == payload

    def test_path_strings_under_root_always_rewrite(self, gpfs_windows):
        """Any standalone string that begins with the configured GPFS
        root must be rewritten to start with ``/gpfs/`` (or equal
        ``/gpfs`` if it's the root exactly)."""
        rng = random.Random(SEED + 4)
        for _ in range(ITERATIONS):
            suffix_depth = rng.randint(0, 4)
            suffix = "/".join(
                "".join(rng.choices(string.ascii_lowercase + string.digits, k=6))
                for _ in range(suffix_depth)
            )
            if suffix:
                input_path = "C:/magellon/gpfs/" + suffix
                expected_prefix = "/gpfs/"
            else:
                input_path = "C:/magellon/gpfs"
                expected_prefix = "/gpfs"
            out = canonicalize_paths_in_payload(input_path)
            if expected_prefix == "/gpfs":
                assert out in ("/gpfs", "/gpfs/")
            else:
                assert out.startswith(expected_prefix), (
                    f"expected rewrite, got {out!r} from {input_path!r}"
                )

    def test_dict_key_set_preserved(self, gpfs_windows):
        rng = random.Random(SEED + 5)
        for _ in range(ITERATIONS):
            payload = _random_payload(rng, depth=2)
            out = canonicalize_paths_in_payload(payload)
            if isinstance(payload, dict):
                assert set(payload) == set(out)
