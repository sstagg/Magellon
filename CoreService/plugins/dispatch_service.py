"""Broker dispatch — publish to magellon.tasks.<category> via the bus.

Owns target-impl resolution (backend pin / URL-named impl / operator
default), the PE2 dispatch cache probe, TaskMessage assembly, the bus
publish, and the single/batch submit flows on top of them. Validation
gates live in :mod:`plugins.dispatch_validation`.
"""
from __future__ import annotations

import logging
import uuid
from typing import Any, Dict, List, Optional

from fastapi import HTTPException

from core.plugin_liveness_registry import get_registry as get_liveness_registry
from core.plugin_state import get_state_store
from magellon_sdk.bus import get_bus
from magellon_sdk.bus.routes import TaskRoute
from magellon_sdk.categories.contract import CategoryContract
from magellon_sdk.envelope import Envelope
from magellon_sdk.models import TaskMessage, TaskStatus
from services.job_manager import job_manager

from plugins.dispatch_validation import (
    _derive_subject,
    _reject_if_subject_missing,
    _reject_if_subject_tag_mismatch,
    _validate_broker_input,
)
from plugins.registry_service import _strip_category_prefix
from plugins.schemas import BatchSubmitRequest, JobSubmitRequest

logger = logging.getLogger(__name__)

_BROKER_ENVELOPE_SOURCE = "magellon/core_service/plugin_controller"


def _resolve_dispatch_target(
    plugin_id: str, contract: CategoryContract,
    *,
    target_backend: Optional[str] = None,
) -> "PluginLivenessEntry":
    """Pick the live plugin instance that should receive this dispatch.

    Three HTTP-layer failures short-circuit here so callers see a real
    error instead of a silently queued task:

    * ``target_backend`` set but no live plugin claims it → 503.
    * No live impl for this category → 503 (H1.c).
    * Named impl is present but disabled → 409.

    The target has to be both ``enabled`` and in the liveness window.
    A disabled default still counts as the default — we don't silently
    fail over to a different impl — so the UI can surface the real
    state to the operator.

    When ``target_backend`` is set, the backend pin wins over the
    operator-pinned default and over the URL-named impl: the caller
    asked for a specific implementation and silently routing to a
    different one would mask their intent.
    """
    from core.plugin_liveness_registry import PluginLivenessEntry  # local: avoid cycle

    state = get_state_store()
    short_id = _strip_category_prefix(plugin_id)

    # Candidates for this category, from the liveness registry.
    live: list[PluginLivenessEntry] = [
        e for e in get_liveness_registry().list_live()
        if e.category.lower() == contract.category.name.lower()
    ]

    # Backend pin wins. We do not consult the URL-named impl or the
    # operator default — the pin is a binding directive.
    if target_backend:
        wanted = target_backend.lower()
        for e in live:
            if (e.backend_id or "").lower() != wanted:
                continue
            if not state.is_enabled(e.plugin_id):
                raise HTTPException(
                    status_code=409,
                    detail=(
                        f"Backend {wanted!r} for category "
                        f"{contract.category.name!r} is disabled"
                    ),
                )
            return e
        raise HTTPException(
            status_code=503,
            detail=(
                f"No live plugin claims backend_id={target_backend!r} for "
                f"category {contract.category.name!r}"
            ),
        )

    # Explicit impl? Must match the URL exactly. Disabled → 409.
    for e in live:
        if e.plugin_id == short_id:
            if not state.is_enabled(e.plugin_id):
                raise HTTPException(
                    status_code=409,
                    detail=f"Plugin {short_id} is disabled",
                )
            return e

    # No explicit impl name — caller passed a category-scoped id.
    # Route to the pinned default if it's live and enabled.
    default_id = state.get_default(contract.category.name.lower())
    if default_id:
        for e in live:
            if e.plugin_id == default_id:
                if not state.is_enabled(e.plugin_id):
                    raise HTTPException(
                        status_code=409,
                        detail=(
                            f"Default impl {default_id!r} for category "
                            f"{contract.category.name!r} is disabled"
                        ),
                    )
                return e

    # No default and no explicit id — any live enabled candidate will do.
    for e in live:
        if state.is_enabled(e.plugin_id):
            return e

    raise HTTPException(
        status_code=503,
        detail=(
            f"No live enabled plugin for category "
            f"{contract.category.name!r} — cannot dispatch"
        ),
    )


def _build_task_dto(
    contract: CategoryContract,
    validated_input,
    task_id: uuid.UUID,
    job_id: str,
    user_id: Optional[str],
    target_backend: Optional[str] = None,
    subject_kind: Optional[str] = None,
    subject_id: Optional[uuid.UUID] = None,
) -> TaskMessage:
    """Wrap a validated input in the TaskMessage the bus transports.

    ``task_id`` must match the one registered with ``job_manager.create_job``;
    otherwise the step-event projector can't link events back to the
    job row and the row stays ``queued`` forever.

    ``target_backend`` rides on the DTO so the dispatcher can route to
    a specific backend's queue. The controller path uses the resolved
    ``target.task_queue`` directly (no round-trip through the
    dispatcher), but the field is still set so the consuming plugin
    can confirm it was the intended recipient.

    ``subject_kind`` / ``subject_id`` (Phase 3, reviewer-flagged High #4
    in 2026-05-04 fix) are stamped explicitly here. The runner's
    contract-default fallback (Phase 3d) covers ``subject_kind`` even
    when None; ``subject_id`` MUST be set here for aggregate-input
    categories or the projector loses the lineage link.
    """
    data = (
        validated_input.model_dump(mode="json")
        if hasattr(validated_input, "model_dump")
        else validated_input
    )
    return TaskMessage(
        id=task_id,
        worker_instance_id=uuid.uuid4(),
        job_id=uuid.UUID(job_id),
        data=data,
        type=contract.category,
        status=TaskStatus(code=0, name="pending", description="Task is pending"),
        target_backend=target_backend,
        subject_kind=subject_kind,
        subject_id=subject_id,
    )


def _publish_to_bus(
    contract: CategoryContract, task: TaskMessage, target_queue: Optional[str] = None,
) -> bool:
    """Publish to the target impl's queue (SDK 1.1+) or the legacy
    category-scoped route when no impl-specific queue is known.

    The fallback matters for pre-1.1 plugins whose announce doesn't
    carry ``task_queue``; they still consume from the legacy category
    queue and the binder's legacy_queue_map resolves the route.
    """
    if target_queue:
        route = TaskRoute.named(target_queue)
    else:
        route = TaskRoute.for_category(contract)
    envelope = Envelope.wrap(
        source=_BROKER_ENVELOPE_SOURCE,
        type="magellon.task.dispatch",
        subject=route.subject,
        data=task,
    )
    receipt = get_bus().tasks.send(route, envelope)
    if not receipt.ok:
        logger.error(
            "broker dispatch failed on %s: %s", route.subject, receipt.error,
        )
    return receipt.ok


def _try_dispatch_cache_hit(
    plugin_id: str,
    contract: CategoryContract,
    validated: Any,
    settings: Dict[str, Any],
) -> Optional[Dict[str, Any]]:
    """Probe the PE2 dispatch cache; return a synthetic envelope on
    hit, ``None`` to fall through to a real dispatch.

    The lookup is intentionally narrow:

      - Only artifact-producing categories cache (others have no
        Artifact rows to point at).
      - Only categories declaring a ``produces_subject_kind`` qualify
        — they're the "transforming" categories where a new run with
        identical params re-produces the same artifact. CTF /
        MotionCor / FFT in-place categories don't write Artifacts and
        therefore can't cache via this path.
      - The plugin's ``produces_subject_kind`` resolves to one of the
        Artifact ``kind`` values (``particle_stack`` / ``class_averages``).

    On hit we return the original producing job's envelope so the
    consumer's job_id reference still resolves to a real ``ImageJob``
    row. The ``cached`` flag in the response is the wire signal —
    callers that care (the React UI) can surface "served from cache".
    """
    # Today only PARTICLE_EXTRACTION and TWO_D_CLASSIFICATION write
    # Artifact rows. ``produces_subject_kind != None`` is the gate
    # (in-place categories like CTF leave it None per the contract).
    if not getattr(contract, "produces_subject_kind", None):
        return None

    # Plugin version: read from the live announce registry — the
    # version that would actually run this task. Same source the
    # dispatch path uses to pick a backend.
    plugin_version = _resolve_live_plugin_version(plugin_id)
    if plugin_version is None:
        return None

    # Input OIDs: the artifact-typed inputs declared by the contract.
    # Today the only artifact-OID input is ``particle_stack_id``;
    # other UUID fields point at Image / Session rows that aren't
    # Artifacts. Restricting to artifact inputs keeps the cache
    # honest — we can only claim "same inputs" when those inputs are
    # in fact the same Artifact OIDs.
    input_oids: list = []
    raw_dict = (
        validated.model_dump(mode="json") if hasattr(validated, "model_dump")
        else dict(validated)
    )
    for field, tag in (contract.input_subjects or {}).items():
        if tag in ("particle_stack", "class_averages", "artifact"):
            value = raw_dict.get(field)
            if value:
                input_oids.append(value)

    try:
        from database import session_local
        from services.dispatch_cache import lookup_cached_output

        db = session_local()
        try:
            hit = lookup_cached_output(
                db,
                plugin_id=plugin_id,
                plugin_version=plugin_version,
                params=settings,
                input_oids=input_oids,
            )
        finally:
            db.close()
    except Exception as exc:  # noqa: BLE001 — cache miss on any failure
        logger.warning(
            "dispatch cache lookup failed (falling through): %s", exc,
        )
        return None

    if hit is None:
        return None

    logger.info(
        "dispatch cache HIT plugin_id=%s v=%s → artifact %s (job %s)",
        plugin_id, plugin_version, hit.oid, hit.producing_job_id,
    )
    # Synthetic envelope — same shape as job_manager.create_job
    # returns. The job_id reference is the *original* producing job.
    return {
        "job_id": str(hit.producing_job_id) if hit.producing_job_id else None,
        "name": f"{plugin_id} job (cached)",
        "status": "completed",
        "cached": True,
        "cached_artifact_id": str(hit.oid),
    }


def _resolve_live_plugin_version(plugin_id: str) -> Optional[str]:
    """Look up the version of the plugin currently announced.

    Returns ``None`` when no live entry exists — the caller treats
    this as a cache miss (we don't know what version *would* run).
    """
    try:
        from core.plugin_liveness_registry import get_registry
        for entry in get_registry().list_live():
            if entry.plugin_id == plugin_id:
                return entry.plugin_version
    except Exception:  # noqa: BLE001
        return None
    return None


async def _submit_broker_job(
    plugin_id: str,
    contract: CategoryContract,
    request: JobSubmitRequest,
) -> Dict[str, Any]:
    validated = _validate_broker_input(contract, request.input)
    _reject_if_subject_missing(contract, validated)
    _reject_if_subject_tag_mismatch(contract, validated)
    settings = (
        validated.model_dump(mode="json")
        if hasattr(validated, "model_dump") else validated
    )
    # PE2 dispatch cache (PIPELINE_ERGONOMICS_PLAN.md §PE2). Skip the
    # bus publish entirely when an identical run has already
    # completed — the prior artifact's producing job is returned
    # verbatim. The cache lookup is one indexed point query against
    # the (plugin_id, plugin_version, params_hash, input_set_hash)
    # tuple on Artifact (alembic 0010).
    cached_envelope = _try_dispatch_cache_hit(
        plugin_id, contract, validated, settings,
    )
    if cached_envelope is not None:
        return cached_envelope

    # Resolve the target impl BEFORE creating a job row — that way
    # H1.c's 503 ("no live enabled impl") doesn't leave an orphan
    # queued row behind.
    target = _resolve_dispatch_target(
        plugin_id, contract, target_backend=request.target_backend,
    )

    # Generate the task_id up front so the same id registered with the
    # job_manager rides inside the TaskMessage. The step-event projector
    # needs this linkage to flip the job row's status.
    task_id = uuid.uuid4()

    # Phase 3 / 2026-05-04 reviewer-flagged High #4: derive subject
    # axis at dispatch time so it lands on both the ImageJobTask row
    # and the TaskMessage. The classifier's particle_stack_id flows
    # from the input dict here straight onto the persistent row.
    subject_kind, subject_id = _derive_subject(contract, validated)

    envelope = job_manager.create_job(
        plugin_id=plugin_id,
        name=request.name or f"{plugin_id} job",
        settings=settings,
        task_ids=[task_id],
        image_ids=[request.image_id] if request.image_id else None,
        user_id=request.user_id,
        msession_id=request.msession_id,
        parent_run_id=getattr(request, "parent_run_id", None),
        subject_kind=subject_kind,
        subject_id=subject_id,
    )
    task = _build_task_dto(
        contract, validated, task_id, envelope["job_id"], request.user_id,
        target_backend=request.target_backend,
        subject_kind=subject_kind,
        subject_id=subject_id,
    )
    if not _publish_to_bus(contract, task, target.task_queue):
        job_manager.fail_job(envelope["job_id"], error="Failed to publish task to bus")
        raise HTTPException(status_code=502, detail="Failed to publish task to bus")
    return envelope


async def _submit_broker_batch(
    plugin_id: str,
    contract: CategoryContract,
    request: BatchSubmitRequest,
) -> Dict[str, Any]:
    # Up-front validation — fail the whole batch cleanly rather than
    # creating half the jobs then failing mid-flight.
    validated_inputs = [
        _validate_broker_input(contract, raw) for raw in request.inputs
    ]
    for validated in validated_inputs:
        _reject_if_subject_missing(contract, validated)
        _reject_if_subject_tag_mismatch(contract, validated)

    # Resolve the target impl once for the whole batch. Rolls any 503
    # (no live impl) / 409 (disabled) before a single job row is
    # created, so a batch never half-lands.
    target = _resolve_dispatch_target(
        plugin_id, contract, target_backend=request.target_backend,
    )

    envelopes: List[Dict[str, Any]] = []
    publish_failures: List[str] = []
    for idx, validated in enumerate(validated_inputs):
        image_id = request.image_ids[idx] if request.image_ids else None
        settings = (
            validated.model_dump(mode="json")
            if hasattr(validated, "model_dump") else validated
        )
        task_id = uuid.uuid4()
        # Same Phase-3 / Medium-#6 wiring as _submit_broker_job.
        subject_kind, subject_id = _derive_subject(contract, validated)
        env = job_manager.create_job(
            plugin_id=plugin_id,
            name=request.name or f"{plugin_id} batch [{idx + 1}/{len(validated_inputs)}]",
            settings=settings,
            task_ids=[task_id],
            image_ids=[image_id] if image_id else None,
            user_id=request.user_id,
            msession_id=request.msession_id,
            parent_run_id=getattr(request, "parent_run_id", None),
            subject_kind=subject_kind,
            subject_id=subject_id,
        )
        envelopes.append(env)
        task = _build_task_dto(
            contract, validated, task_id, env["job_id"], request.user_id,
            target_backend=request.target_backend,
            subject_kind=subject_kind,
            subject_id=subject_id,
        )
        if not _publish_to_bus(contract, task, target.task_queue):
            job_manager.fail_job(env["job_id"], error="Failed to publish task to bus")
            publish_failures.append(env["job_id"])

    if publish_failures:
        raise HTTPException(
            status_code=502,
            detail=f"Failed to publish {len(publish_failures)}/{len(envelopes)} tasks to bus",
        )
    return {"jobs": envelopes, "count": len(envelopes)}
