"""Dispatch-time input validation gates (PE1-A / PE1-B).

Everything that decides whether a broker-job input is even eligible to
be published: Pydantic validation against the category contract, the
subject-kind required-field gate, per-field subject-tag checks against
the Artifact table, and subject-axis derivation.
"""
from __future__ import annotations

import uuid
from typing import Dict, List, Optional, Tuple, Any

from fastapi import HTTPException

from magellon_sdk.categories.contract import CategoryContract


def _validate_broker_input(contract: CategoryContract, raw: Dict[str, Any]):
    """Validate input against the category's Pydantic input model.

    Contracts like ``CTF``/``FFT``/``MOTIONCOR_CATEGORY`` pin
    ``input_model`` (e.g. ``CtfInput``). ``PARTICLE_PICKER`` doesn't
    pin one yet (see contract.py) — fall back to round-tripping the
    raw dict so dispatch still works for those.
    """
    model = contract.input_model
    if model is None:
        return raw
    try:
        return model.model_validate(raw)
    except Exception as exc:
        raise HTTPException(status_code=422, detail=f"Invalid input: {exc}")


def _reject_if_subject_missing(
    contract: CategoryContract,
    validated_input,
) -> None:
    """PE1-A (2026-05-10): explicit subject-kind gate at dispatch.

    For aggregate categories (``subject_kind='particle_stack'``), the
    input model declares ``particle_stack_id`` as ``Optional[UUID]``
    so the SDK can evolve without breaking older callers — but the
    contract still requires it. Without this check, a missing
    particle_stack_id slips past Pydantic and lands a job with
    ``subject_id=None``, which the projector then can't link back
    to its source artifact.

    Image-keyed categories aren't gated here; the input model
    + outer ``request.image_id`` give callers several ways to refer
    to an image, and gating would risk breaking legitimate paths.
    """
    if contract.subject_kind == "particle_stack":
        candidate = getattr(validated_input, "particle_stack_id", None)
        if candidate is None:
            raise HTTPException(
                status_code=422,
                detail=(
                    f"Category {contract.category.name} operates on "
                    f"subject_kind='particle_stack'; input.particle_stack_id is required."
                ),
            )


# Subject tags that name Artifact subtypes — these are the only tags the
# dispatch gate validates today, because they map 1:1 to ``Artifact.kind``.
# ``image`` is descriptive metadata (Image rows live in a separate table);
# session/run/artifact are task-bag concepts, not field-level references.
# When Image migrates to Artifact STI, add ``"image"`` here.
_ARTIFACT_TAG_VOCAB = frozenset({"particle_stack", "class_averages"})


def _reject_if_subject_tag_mismatch(
    contract: CategoryContract,
    validated_input,
) -> None:
    """PE1-B (2026-05-11): per-field subject-tag validation at dispatch.

    Walk ``contract.input_subjects`` and, for each artifact-kind tag
    that names an existing Artifact subtype (today: ``particle_stack``,
    ``class_averages``), resolve the referenced Artifact row and
    confirm its ``kind`` matches. Reject with 422 on mismatch — the
    plugin would have failed downstream after a queue round-trip
    otherwise, leaving a hung job row.

    Fields with no value (``None``) are skipped — that case is owned
    by ``_reject_if_subject_missing`` (PE1-A), which handles the
    aggregate-category required-subject contract separately.

    Fields tagged with vocabulary outside ``_ARTIFACT_TAG_VOCAB``
    (today: ``"image"``) are skipped — those tags exist for catalog
    metadata, not dispatch validation. When Image becomes an Artifact
    subtype the validation extends without code changes here.
    """
    if not contract.input_subjects:
        return

    pending_lookups: List[Tuple[str, str, uuid.UUID]] = []
    for field_name, expected_tag in contract.input_subjects.items():
        if expected_tag not in _ARTIFACT_TAG_VOCAB:
            continue
        raw = getattr(validated_input, field_name, None)
        if raw is None:
            continue
        if isinstance(raw, uuid.UUID):
            candidate = raw
        else:
            try:
                candidate = uuid.UUID(str(raw))
            except (ValueError, AttributeError):
                raise HTTPException(
                    status_code=422,
                    detail=(
                        f"Category {contract.category.name} field "
                        f"{field_name!r} expected an artifact OID "
                        f"(subject={expected_tag!r}); got {raw!r}."
                    ),
                )
        pending_lookups.append((field_name, expected_tag, candidate))

    if not pending_lookups:
        return

    # One short-lived session for the whole gate, mirroring the
    # _resolve_plugin_category pattern elsewhere in this module.
    from sqlalchemy.orm import Session as _Session
    from database import session_local
    from models.sqlalchemy_models import Artifact

    db: _Session = session_local()
    try:
        for field_name, expected_tag, oid in pending_lookups:
            row = (
                db.query(Artifact)
                .filter(Artifact.oid == oid)
                .first()
            )
            if row is None or row.deleted_at is not None:
                raise HTTPException(
                    status_code=422,
                    detail=(
                        f"Category {contract.category.name} field "
                        f"{field_name!r} references unknown artifact {oid}."
                    ),
                )
            if row.kind != expected_tag:
                raise HTTPException(
                    status_code=422,
                    detail=(
                        f"Category {contract.category.name} field "
                        f"{field_name!r} expected subject={expected_tag!r}; "
                        f"artifact {oid} is kind={row.kind!r}."
                    ),
                )
    finally:
        db.close()


def _derive_subject(
    contract: CategoryContract,
    validated_input,
) -> Tuple[Optional[str], Optional[uuid.UUID]]:
    """Derive (subject_kind, subject_id) for dispatch (Phase 3 / 2026-05-04 fix).

    Authoritative resolution at dispatch time so the runner's
    contract-default fallback isn't load-bearing. Three cases:

      * Aggregate-input categories (TWO_D_CLASSIFICATION → input has
        ``particle_stack_id``): subject is the source artifact.
      * Image-keyed categories (everything else): subject_kind comes
        from the contract (default ``'image'``); subject_id stays
        None here — the dispatch layer at ``_submit_broker_job``
        threads ``request.image_id`` into ImageJobTask.subject_id
        directly via ``create_job``.

    Returns (subject_kind, subject_id). Either may be None.
    """
    subject_kind: Optional[str] = (
        contract.subject_kind if contract is not None else None
    )
    subject_id: Optional[uuid.UUID] = None

    # Aggregate categories carry the subject id explicitly on the
    # input model. Read it without coupling to the concrete class.
    candidate_id = getattr(validated_input, "particle_stack_id", None)
    if candidate_id is not None:
        if isinstance(candidate_id, str):
            try:
                subject_id = uuid.UUID(candidate_id)
            except ValueError:
                subject_id = None
        else:
            subject_id = candidate_id

    return subject_kind, subject_id
