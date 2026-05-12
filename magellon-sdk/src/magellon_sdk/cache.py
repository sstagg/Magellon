"""Dispatch-cache key helpers (PE2).

PE2 deduplicates dispatch when the same plugin at the same version is
asked to run with the same input artifact set and the same parameters.
The cache key is a SHA-256 of the canonical form of:

    (plugin_id, plugin_version, sorted(input_oids), params, category)

Three small pure functions live here; CoreService and any plugin that
wants to compute a cache key (e.g. the future replay CLI) call them.

The functions are *deterministic* and *Python-version-independent* —
they avoid ``repr()``, dict ordering quirks, and locale-dependent
formatting. The canonical JSON path uses ``sort_keys=True`` and
``separators=(",", ":")`` so two semantically equal dicts hash to the
same bytes regardless of insertion order.
"""
from __future__ import annotations

import hashlib
import json
from typing import Any, Iterable, Sequence
from uuid import UUID


def compute_input_set_hash(input_oids: Iterable[UUID | str | None]) -> str:
    """Return SHA-256 hex of the sorted, normalized OID list.

    Two input sets that contain the same OIDs in any order hash to the
    same value — sorting is the only normalization step. ``None`` and
    empty strings are dropped; ``UUID`` objects are converted to their
    canonical string form.

    Empty input set returns the SHA-256 of an empty array — a stable
    sentinel for "this plugin takes no artifact inputs."
    """
    canonical_oids: list[str] = []
    for oid in input_oids:
        if oid is None:
            continue
        s = str(oid).strip()
        if not s:
            continue
        canonical_oids.append(s)
    canonical_oids.sort()
    payload = json.dumps(canonical_oids, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def compute_params_hash(params: dict[str, Any] | None) -> str:
    """Return SHA-256 hex of the canonical-JSON form of ``params``.

    Canonical form means:
      - dict keys sorted alphabetically (``sort_keys=True``)
      - no whitespace between separators (``separators=(",", ":")``)
      - non-JSON-serializable values (``Path``, ``UUID``, etc.)
        stringified via ``default=str``

    Two semantically equal params dicts hash to the same value
    regardless of insertion order. ``None`` and empty dict both hash
    to the same sentinel (the canonical form of ``{}``).
    """
    canonical = json.dumps(
        params or {},
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def compute_cache_key(
    *,
    plugin_id: str,
    plugin_version: str,
    category: str,
    input_oids: Sequence[UUID | str | None],
    params: dict[str, Any] | None,
) -> str:
    """Return SHA-256 hex of the full PE2 cache key.

    Wraps :func:`compute_input_set_hash` and :func:`compute_params_hash`
    plus the three plain string parts. The output is the value the
    cache-lookup index needs to point-query against.

    Used by the plugin-side replay tool (one day) — CoreService doesn't
    point-query the full key today; it filters on
    ``(producer_plugin_id, producer_plugin_version, params_hash,
    input_set_hash)`` via the composite index. The full-key function
    exists so external tools can produce a single-string fingerprint
    that's stable across implementations.
    """
    parts = [
        plugin_id,
        plugin_version,
        category,
        compute_input_set_hash(input_oids),
        compute_params_hash(params),
    ]
    payload = "\x1f".join(parts)  # unit separator — won't appear in OIDs/slugs
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


__all__ = [
    "compute_cache_key",
    "compute_input_set_hash",
    "compute_params_hash",
]
