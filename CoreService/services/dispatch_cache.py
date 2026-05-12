"""Lineage-keyed dispatch cache (PE2).

PIPELINE_ERGONOMICS_PLAN.md §PE2 — deduplicate dispatch when the same
plugin at the same version is asked to run with the same input
artifact set and the same parameters. Returns the prior artifact's
producing job_id instead of publishing a new task to the bus.

Key insight (from the plan): the Artifact table already records
*producer + params + inputs* per row; promoting those to indexed
columns (alembic 0010) turns "have we run this before?" into a single
indexed point query. No new cache table — reuse the Artifact table as
its own cache.

What this module is NOT:
  - It is not a write-through cache. Cache rows are populated by
    ``TaskOutputProcessor._maybe_write_artifact`` when a real task
    completes (alembic 0010 columns).
  - It is not invalidation. The plan's three invalidation cases —
    plugin version bump, source supersession, manual admin clear — all
    fall out of "filter by current key and active rows" automatically
    (version bump → cache miss; supersession → ``deleted_at`` filter;
    manual → admin endpoint UPDATEs ``deleted_at``).

Invariant: a cache hit must produce a result indistinguishable from a
real run from the caller's perspective. The hit returns the
*producing job's* envelope, which already references the artifact —
the consumer fetches by job_id like normal.
"""
from __future__ import annotations

import logging
import uuid
from typing import Any, Dict, Iterable, Optional, Sequence

from sqlalchemy.orm import Session

from magellon_sdk.cache import compute_input_set_hash, compute_params_hash
from models.sqlalchemy_models import Artifact

logger = logging.getLogger(__name__)


def lookup_cached_output(
    db: Session,
    *,
    plugin_id: str,
    plugin_version: str,
    params: Dict[str, Any],
    input_oids: Sequence[uuid.UUID | str | None],
) -> Optional[Artifact]:
    """Return the cached ``Artifact`` if one exists for this dispatch.

    Returns ``None`` when:
      - no row matches the (plugin_id, plugin_version, params_hash,
        input_set_hash) tuple,
      - the matching row has been soft-deleted (``deleted_at IS NOT
        NULL``),
      - the matching row's source artifact has been superseded (any
        ancestor with ``deleted_at IS NOT NULL``).

    Conservative on uncertainty — if we can't tell, miss. The caller
    will dispatch a real run, which is correct behaviour.

    Implementation note: the composite covering index
    ``ix_artifact_dispatch_cache`` makes this one indexed equality
    lookup. A SELECT … LIMIT 1 returns the most recent row; multiple
    successful runs at the same key all hash to the same row family
    and the first one wins.

    Args:
        db: live SQLAlchemy session
        plugin_id: producer's manifest plugin_id (string slug)
        plugin_version: producer's manifest version
        params: input params for the would-be task — same dict the
            dispatcher would publish on the bus
        input_oids: artifact OIDs the task would consume

    Returns:
        Cached :class:`Artifact` on hit, ``None`` on miss.
    """
    if not plugin_id or not plugin_version:
        # Can't compute a stable key without identifying provenance.
        return None

    params_hash = compute_params_hash(params)
    input_set_hash = compute_input_set_hash(input_oids)

    candidates = (
        db.query(Artifact)
        .filter(
            Artifact.producer_plugin_id == plugin_id,
            Artifact.producer_plugin_version == plugin_version,
            Artifact.params_hash == params_hash,
            Artifact.input_set_hash == input_set_hash,
            Artifact.deleted_at.is_(None),
        )
        .order_by(Artifact.created_date.desc())
        .all()
    )
    if not candidates:
        return None

    # Walk each candidate's ancestor chain and skip if any source is
    # superseded. Cheap-but-conservative: walks at most a few hops
    # because lineage is single-parent today and the chain rarely
    # exceeds 4–5 nodes (image → motion-corrected → CTF-estimated →
    # picked → extracted → classified).
    for cand in candidates:
        if _has_superseded_ancestor(db, cand):
            continue
        return cand
    return None


def _has_superseded_ancestor(db: Session, artifact: Artifact) -> bool:
    """Walk the source_artifact_id chain — return True if any ancestor
    has been soft-deleted. The plan's invalidation rule #2: cached
    rows whose inputs are superseded should fall through to a real
    dispatch.

    Bounded walk — 20 hops max, matching the existing ``/lineage``
    endpoint's depth cap so callers don't hit infinite recursion on a
    pathological graph."""
    seen: set[uuid.UUID] = set()
    parent_id = artifact.source_artifact_id
    depth = 0
    while parent_id is not None and depth < 20:
        if parent_id in seen:
            return False  # cycle defense; treat as not-superseded
        seen.add(parent_id)
        parent = (
            db.query(Artifact)
            .filter(Artifact.oid == parent_id)
            .first()
        )
        if parent is None:
            return False  # ancestor missing — conservative: not superseded
        if parent.deleted_at is not None:
            return True
        parent_id = parent.source_artifact_id
        depth += 1
    return False


def invalidate_cache(
    db: Session,
    *,
    plugin_id: Optional[str] = None,
    plugin_version: Optional[str] = None,
    artifact_oid: Optional[uuid.UUID] = None,
) -> int:
    """Soft-delete cache-eligible Artifact rows matching the filter.

    Admin-side hard reset for the plan's invalidation rule #3 ("manual
    invalidation"). Sets ``deleted_at = now()`` on every matching row —
    subsequent lookups skip them. Per ratified rule 6 (artifacts
    immutable), we don't DROP the rows; soft-delete preserves audit.

    All filters are optional but ``invalidate_cache(db)`` with no
    filters is a no-op (return 0) — refuse to nuke the whole table
    silently.

    Returns the number of rows soft-deleted.
    """
    from datetime import datetime

    if plugin_id is None and plugin_version is None and artifact_oid is None:
        logger.warning(
            "invalidate_cache called with no filters — refusing to "
            "soft-delete all artifacts; pass at least one filter",
        )
        return 0

    query = db.query(Artifact).filter(Artifact.deleted_at.is_(None))
    if plugin_id is not None:
        query = query.filter(Artifact.producer_plugin_id == plugin_id)
    if plugin_version is not None:
        query = query.filter(Artifact.producer_plugin_version == plugin_version)
    if artifact_oid is not None:
        query = query.filter(Artifact.oid == artifact_oid)

    now = datetime.utcnow()
    count = query.update(
        {Artifact.deleted_at: now}, synchronize_session=False,
    )
    db.commit()
    logger.info(
        "dispatch cache: invalidated %d artifact(s) "
        "(plugin_id=%s, version=%s, oid=%s)",
        count, plugin_id, plugin_version, artifact_oid,
    )
    return count


__all__ = [
    "invalidate_cache",
    "lookup_cached_output",
]
