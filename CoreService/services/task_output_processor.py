"""In-process result writer — folded in from the out-of-tree
``magellon_result_processor`` plugin (P3).

The plugin used to own this logic and reach into the Magellon DB
directly. That broke invariant I2 ("plugins never touch the DB"):
schema migrations had to chase a separate deploy artefact, and a
plugin crash could leave half-written rows. Promoting the writer
into CoreService gives us:

  - One process owning the per-task DB write (status_id + stage),
    same session that records the metadata.
  - A clear contract for plugins: publish ``TaskResultMessage`` to your
    out-queue and stop. The platform projects it.

Shape and behaviour are kept identical to the old plugin so the
existing characterization tests keep their value — see
``tests/test_task_output_processor.py``.
"""
from __future__ import annotations

import json
import logging
import os
import shutil
import uuid
from typing import Any, Dict, Iterable, Optional

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from config import MAGELLON_HOME_DIR
from magellon_sdk.models import TaskResultMessage
from models.pydantic_models_settings import OutQueueConfig, OutQueueType
from models.sqlalchemy_models import Artifact, ImageJobTask, ImageMetaData

logger = logging.getLogger(__name__)

# ImageJobTask.status_id values — must match services.job_manager.
STATUS_QUEUED = 0
STATUS_RUNNING = 1
STATUS_COMPLETED = 2
STATUS_FAILED = 3

# ImageJobTask.stage values — per task-type code. The stage is the
# position of that step in the per-image (or aggregate) pipeline:
#   1 = MotionCor              (TaskCategory.code == 5)
#   2 = CTF                    (TaskCategory.code == 2)
#   3 = SquareDetection        (TaskCategory.code == 6)
#   4 = HoleDetection          (TaskCategory.code == 7)
#   5 = TopazParticlePicking   (TaskCategory.code == 8)
#   6 = MicrographDenoising    (TaskCategory.code == 9)
#   7 = ParticleExtraction     (TaskCategory.code == 10)  Phase 5
#   8 = TwoDClassification     (TaskCategory.code == 4)   Phase 7
#  12 = ParticlePicking        (TaskCategory.code == 3)   manual step
# Unknown task types land at 99 so operators can spot them in the UI.
_TASK_TYPE_TO_STAGE = {5: 1, 2: 2, 6: 3, 7: 4, 8: 5, 9: 6, 10: 7, 4: 8, 3: 12}
_DEFAULT_STAGE = 99

# TaskCategory codes for the artifact-producing categories handled below.
# Kept as bare ints (matching the SDK constants) so we don't pull a
# magellon_sdk import into this hot path just for two switch-cases.
_TASK_TYPE_PARTICLE_PICKING = 3          # PARTICLE_PICKING (template-picker / boxnet)
_TASK_TYPE_TOPAZ_PARTICLE_PICKING = 8   # TOPAZ_PARTICLE_PICKING — separate queue/code
_TASK_TYPE_PARTICLE_EXTRACTION = 10     # PARTICLE_EXTRACTION
_TASK_TYPE_TWO_D_CLASSIFICATION = 4     # TWO_D_CLASSIFICATION

# Artifact.kind discriminator values. Mirrors magellon_sdk.models.artifact.ArtifactKind
# but kept local to avoid a cross-package coupling on the enum string.
_ARTIFACT_KIND_PARTICLE_STACK = "particle_stack"
_ARTIFACT_KIND_CLASS_AVERAGES = "class_averages"

# Default category id when no OutQueueConfig matches — preserves the
# old plugin's fallback so existing rows keep their lineage.
_DEFAULT_CATEGORY_ID = 10


def _move_file_to_directory(file_path: str, destination_dir: str) -> None:
    """Move ``file_path`` into ``destination_dir``, creating it if missing.

    Plugins write output under their canonical ``/gpfs/jobs/...`` path.
    On Windows (or any host where MAGELLON_GPFS_PATH != /gpfs) that path
    is not a real filesystem path — translate it first so shutil.move
    finds the file.

    Best-effort: a missing source is logged and skipped — the metadata
    write should still happen so the UI can surface the failure.
    """
    try:
        if not file_path:
            return
        from core.helper import from_canonical_gpfs_path
        host_path = from_canonical_gpfs_path(file_path)
        os.makedirs(destination_dir, exist_ok=True)
        filename = os.path.basename(host_path)
        shutil.move(host_path, os.path.join(destination_dir, filename))
    except Exception as exc:
        logger.warning("Could not move %s to %s: %s", file_path, destination_dir, exc)


class TaskOutputProcessor:
    """Project a ``TaskResultMessage`` into the Magellon DB + on-disk layout.

    One instance is built per delivered message. It owns the SQLAlchemy
    session for the duration of ``process()`` and closes it in the
    ``finally`` block — the broker thread keeps no long-lived ORM state.
    """

    def __init__(
        self,
        db: Session,
        out_queues: Optional[Iterable[OutQueueConfig]] = None,
        magellon_home_dir: Optional[str] = None,
    ) -> None:
        self.db = db
        self.magellon_home_dir = magellon_home_dir or MAGELLON_HOME_DIR
        self._queue_type_output_config = self._build_queue_type_output_config(
            out_queues or []
        )

    @staticmethod
    def _build_queue_type_output_config(
        out_queues: Iterable[OutQueueConfig],
    ) -> Dict[str, Dict[str, Any]]:
        """Map ``queue_type`` → ``{dir_name, category}`` for fast lookup.

        Keyed by the enum's *string value* (e.g. ``"ctf"``) because
        ``task_result.type.name.lower()`` produces a string, not the enum.
        """
        return {
            cfg.queue_type.value: {"dir_name": cfg.dir_name, "category": cfg.category}
            for cfg in out_queues
        }

    def _get_queue_type_output_dir(self, queue_type: str) -> Optional[str]:
        return self._queue_type_output_config.get(queue_type, {}).get("dir_name")

    def _get_queue_type_category(self, queue_type: str) -> Optional[int]:
        return self._queue_type_output_config.get(queue_type, {}).get("category")

    def _get_destination_dir(self, task_result: TaskResultMessage) -> str:
        task_type = task_result.type.name.lower() if task_result.type else "unknown"
        dir_name = self._get_queue_type_output_dir(task_type) or task_type
        file_name = os.path.splitext(os.path.basename(task_result.image_path or ""))[0]
        return os.path.join(
            self.magellon_home_dir,
            task_result.session_name or "",
            dir_name,
            file_name,
        )

    def _process_output_files(
        self, task_result: TaskResultMessage, destination_dir: str
    ) -> Dict[str, str]:
        """Move every plugin-emitted output file under ``destination_dir``.

        Returns a ``{original_path: final_path}`` map so the caller can
        rewrite path-shaped fields on ``output_data`` before the
        artifact writer reads them (2026-05-04 reviewer-flagged High #3).
        Files that fail to move keep their original path in the map so
        downstream code at least surfaces something (the warning is
        logged in ``_move_file_to_directory``).
        """
        remap: Dict[str, str] = {}
        for output_file in task_result.output_files or []:
            src = output_file.path
            if not src:
                continue
            new_path = os.path.join(destination_dir, os.path.basename(src))
            _move_file_to_directory(src, destination_dir)
            # Update the OutputFile in place so the result's
            # ``output_files`` list also points at the post-move path.
            output_file.path = new_path
            remap[src] = new_path
        return remap

    # Path-shaped output_data keys whose values get rewritten when
    # _process_output_files moves their target. Listed explicitly so
    # we never accidentally rewrite scalar/non-path fields. New
    # artifact-producing categories should add their canonical path
    # keys here (or the artifact row will store stale paths).
    _PATH_KEYS_FOR_REWRITE = (
        # extraction
        "mrcs_path",
        "star_path",
        "json_path",
        # 2D classification
        "class_averages_path",
        "assignments_csv_path",
        "class_counts_csv_path",
        "run_summary_path",
        "iteration_history_path",
        "aligned_stack_path",
        # generic
        "output_path",
        "particles_json_path",
        "diagnostic_image_path",
        "artifact_path",
        "log_path",
        "aligned_mrc_path",
    )

    def _rewrite_output_paths(
        self,
        task_result: TaskResultMessage,
        remap: Dict[str, str],
    ) -> None:
        """Apply the file-move remap to ``task_result.output_data`` so
        the artifact writer (and any downstream consumer) sees the
        post-move paths. Only path-shaped keys are touched (see
        :attr:`_PATH_KEYS_FOR_REWRITE`); scalars round-trip untouched.
        """
        out = task_result.output_data
        if not out or not remap:
            return
        for key in self._PATH_KEYS_FOR_REWRITE:
            v = out.get(key)
            if isinstance(v, str) and v in remap:
                out[key] = remap[v]
        task_result.output_data = out

    def _save_particle_picks(self, task_result: TaskResultMessage) -> None:
        """Persist particle picks from a PARTICLE_PICKING task result.

        Reads the picks from ``particles_json_path`` in ``output_data``,
        converts to the UI point shape, and writes an ``ImageMetaData``
        row (type=5) under the image.  No-ops gracefully when the image_id
        or path is missing so a bad delivery doesn't abort the whole result.
        """
        if not task_result.image_id:
            logger.warning("_save_particle_picks: no image_id — skipping save")
            return

        out = task_result.output_data or {}
        json_path = out.get("particles_json_path")
        ipp_name = out.get("ipp_name") or "Auto-pick"

        # Plugin writes picks to disk; load them back here.
        particles_payload: list[dict] = []
        # Prefer the exact micrograph shape the plugin reported; the
        # bounding-box estimate below is only a fallback for plugins
        # that don't echo image_shape.
        image_shape: list[int] | None = None
        out_shape = out.get("image_shape")
        if isinstance(out_shape, (list, tuple)) and len(out_shape) == 2:
            image_shape = [int(out_shape[0]), int(out_shape[1])]
        if json_path:
            try:
                from core.helper import from_canonical_gpfs_path
                host_path = from_canonical_gpfs_path(json_path)
                if os.path.exists(host_path):
                    with open(host_path, "r") as f:
                        raw = json.load(f)
                    if isinstance(raw, list):
                        import time as _time
                        now_ms = int(_time.time() * 1000)
                        threshold = float(out.get("threshold", 0.35))
                        max_x, max_y, max_radius = 0, 0, 0
                        for idx, p in enumerate(raw):
                            if isinstance(p, dict):
                                score = float(p.get("score", 0.0))
                                center = p.get("center")
                                if isinstance(center, (list, tuple)) and len(center) >= 2:
                                    px, py = float(center[0]), float(center[1])
                                else:
                                    px, py = float(p.get("x", 0)), float(p.get("y", 0))
                                radius = int(p.get("radius", 0))
                                max_x = max(max_x, int(px))
                                max_y = max(max_y, int(py))
                                max_radius = max(max_radius, radius)
                                particles_payload.append({
                                    "x": px,
                                    "y": py,
                                    "id": f"auto-{now_ms}-{idx}",
                                    "type": "auto",
                                    "confidence": min(score, 1.0),
                                    "class": "1" if score >= threshold else "4",
                                    "timestamp": now_ms,
                                })
                        if particles_payload and image_shape is None:
                            # Fallback: derive image dimensions from the
                            # bounding box of picks when the plugin didn't
                            # report image_shape. The actual image edge is
                            # roughly max_coord + radius pixels away.
                            image_w = max_x + max_radius
                            image_h = max_y + max_radius
                            image_shape = [image_h, image_w]
            except Exception:
                logger.exception("_save_particle_picks: failed to read %s", json_path)

        meta_data = json.dumps({"image_shape": image_shape}) if image_shape else None

        # Upsert: if a record with the same name already exists for this
        # image, update it; otherwise create a new one.
        existing = (
            self.db.query(ImageMetaData)
            .filter(
                ImageMetaData.image_id == task_result.image_id,
                ImageMetaData.name == ipp_name,
            )
            .first()
        )
        if existing:
            existing.data_json = particles_payload
            existing.data = meta_data
            existing.last_modified_date = __import__("datetime").datetime.now()
        else:
            self.db.add(
                ImageMetaData(
                    oid=uuid.uuid4(),
                    name=ipp_name,
                    created_date=__import__("datetime").datetime.now(),
                    image_id=task_result.image_id,
                    type=5,
                    data=meta_data,
                    data_json=particles_payload,
                )
            )

    def _save_output_data(self, task_result: TaskResultMessage) -> None:
        if task_result.output_data:
            self.db.add(
                ImageMetaData(
                    oid=uuid.uuid4(),
                    name=f"{task_result.type.name} Data",
                    data=json.dumps(task_result.output_data).encode("utf-8"),
                    image_id=task_result.image_id,
                )
            )

    def _save_metadata(self, task_result: TaskResultMessage) -> None:
        if not task_result.meta_data:
            return
        try:
            meta_list_dicts = [m.dict(exclude_none=True) for m in task_result.meta_data]
            task_type = task_result.type.name.lower() if task_result.type else "unknown"
            category_id = (
                self._get_queue_type_category(task_type) or _DEFAULT_CATEGORY_ID
            )
            self.db.add(
                ImageMetaData(
                    oid=uuid.uuid4(),
                    name=f"{task_result.type.name} Meta Data",
                    data_json=meta_list_dicts,
                    image_id=task_result.image_id,
                    category_id=category_id,
                )
            )
        except SQLAlchemyError as db_err:
            self.db.rollback()
            logger.error("DB error saving metadata: %s", db_err)
        except (ValueError, TypeError, json.JSONDecodeError) as json_err:
            logger.error("JSON error saving metadata: %s", json_err)

    def _cache_fields_for_task(
        self, task_id: Optional[uuid.UUID],
    ) -> Dict[str, Optional[str]]:
        """Look up the dispatch-cache fields for a result's originating task.

        PE2 (PIPELINE_ERGONOMICS_PLAN §PE2) stamps four fields onto every
        new Artifact row:

          - ``producer_plugin_id``      from ``ImageJobTask.plugin_id``
          - ``producer_plugin_version`` from ``ImageJobTask.plugin_version``
          - ``params_hash``             SHA-256 of the task's input params
          - ``input_set_hash``          SHA-256 of the input artifact OID set

        Returns ``{}``-equivalent values when the task can't be found or
        the originating task didn't carry plugin provenance — the
        artifact row still writes, the cache lookup just won't be able
        to hit on it. Non-fatal by design.
        """
        if task_id is None:
            return {
                "producer_plugin_id": None,
                "producer_plugin_version": None,
                "params_hash": None,
                "input_set_hash": None,
            }
        task = (
            self.db.query(ImageJobTask)
            .filter(ImageJobTask.oid == task_id)
            .first()
        )
        if task is None:
            return {
                "producer_plugin_id": None,
                "producer_plugin_version": None,
                "params_hash": None,
                "input_set_hash": None,
            }

        # Lazy import to avoid a cross-package dependency at module
        # load time — the cache helpers live in magellon_sdk.
        from magellon_sdk.cache import (
            compute_input_set_hash,
            compute_params_hash,
        )

        params = task.data_json or {}
        # The "input set" is the artifact OIDs the task consumed.
        # Today only TWO_D_CLASSIFICATION carries an explicit
        # particle_stack_id; PARTICLE_EXTRACTION feeds an image_id
        # which isn't an Artifact yet (per the rollout doc) — use the
        # subject_id when subject_kind names an artifact-typed subject.
        input_oids: list = []
        ps_id = params.get("particle_stack_id") if isinstance(params, dict) else None
        if ps_id:
            input_oids.append(ps_id)
        # Subject-axis fallback — when subject_kind is an artifact kind,
        # subject_id is the input OID even without an explicit field.
        if task.subject_kind in ("particle_stack", "class_averages") and task.subject_id:
            input_oids.append(task.subject_id)

        return {
            "producer_plugin_id": task.plugin_id,
            "producer_plugin_version": task.plugin_version,
            "params_hash": compute_params_hash(params if isinstance(params, dict) else None),
            "input_set_hash": compute_input_set_hash(input_oids),
        }

    def _maybe_write_artifact(self, task_result: TaskResultMessage) -> Optional[uuid.UUID]:
        """If this result belongs to an artifact-producing category,
        write a new ``artifact`` row and return its id.

        Per ratified rule 6 (project_artifact_bus_invariants.md):
        artifacts are immutable. A re-run produces a *new* row; we
        never UPDATE an existing one. Per rule 1: only refs and
        scalar summaries cross from ``output_data`` into the row —
        the file content stays on disk.

        Categories handled today:

          * PARTICLE_EXTRACTION (code 10) → kind=``particle_stack``
            with ``mrcs_path`` / ``star_path`` / ``particle_count`` /
            ``apix`` / ``box_size`` populated.
          * TWO_D_CLASSIFICATION (code 4) → kind=``class_averages``
            with ``mrcs_path`` set to the class-averages stack;
            ``data_json`` carries the assignments / counts paths and
            ``source_particle_stack_id`` for lineage.

        Anything else returns ``None`` — the rest of the projection
        runs unchanged (status_id, stage, ImageMetaData, etc.).

        PE2 (2026-05-12): every artifact row also carries dispatch-cache
        fields (``producer_plugin_id`` / ``producer_plugin_version`` /
        ``params_hash`` / ``input_set_hash``) computed from the
        originating task — see :meth:`_cache_fields_for_task`.
        """
        if task_result.type is None:
            return None

        type_code = task_result.type.code
        out = task_result.output_data or {}
        artifact_id = uuid.uuid4()
        cache_fields = self._cache_fields_for_task(task_result.task_id)

        if type_code == _TASK_TYPE_PARTICLE_EXTRACTION:
            row = Artifact(
                oid=artifact_id,
                kind=_ARTIFACT_KIND_PARTICLE_STACK,
                producing_job_id=task_result.job_id,
                producing_task_id=task_result.task_id,
                msession_id=task_result.session_name,
                mrcs_path=out.get("mrcs_path"),
                star_path=out.get("star_path"),
                particle_count=out.get("particle_count"),
                apix=out.get("apix"),
                box_size=out.get("box_size"),
                data_json={
                    "json_path": out.get("json_path"),
                    "source_micrograph_path": task_result.image_path,
                    "edge_width": out.get("edge_width"),
                },
                **cache_fields,
            )
            self.db.add(row)
            return artifact_id

        if type_code == _TASK_TYPE_TWO_D_CLASSIFICATION:
            # 2026-05-04 reviewer-flagged High #5: lineage as a real
            # FK column. Pre-fix this lived only in data_json; "all
            # classifications of stack X" was a JSON scan with no
            # integrity. data_json keeps the same key as a back-compat
            # copy for one release.
            source_id = out.get("source_particle_stack_id")
            source_artifact_id = None
            if source_id:
                if isinstance(source_id, str):
                    try:
                        source_artifact_id = uuid.UUID(source_id)
                    except ValueError:
                        source_artifact_id = None
                else:
                    source_artifact_id = source_id

            row = Artifact(
                oid=artifact_id,
                kind=_ARTIFACT_KIND_CLASS_AVERAGES,
                producing_job_id=task_result.job_id,
                producing_task_id=task_result.task_id,
                msession_id=task_result.session_name,
                source_artifact_id=source_artifact_id,
                mrcs_path=out.get("class_averages_path"),
                # No star_path — class averages don't carry STAR
                # metadata, only assignments + counts CSV.
                particle_count=out.get("num_particles_classified"),
                apix=out.get("apix"),
                data_json={
                    "assignments_csv_path": out.get("assignments_csv_path"),
                    "class_counts_csv_path": out.get("class_counts_csv_path"),
                    "run_summary_path": out.get("run_summary_path"),
                    "iteration_history_path": out.get("iteration_history_path"),
                    "aligned_stack_path": out.get("aligned_stack_path"),
                    "num_classes_emitted": out.get("num_classes_emitted"),
                    # Back-compat copy; downstream readers should
                    # prefer artifact.source_artifact_id.
                    "source_particle_stack_id": out.get("source_particle_stack_id"),
                },
                **cache_fields,
            )
            self.db.add(row)
            return artifact_id

        return None

    def _advance_task_state(
        self,
        task_result: TaskResultMessage,
        *,
        status_id: int,
    ) -> None:
        """Advance the ``image_job_task`` row for this result.

        Sets ``status_id`` (COMPLETED / FAILED) and ``stage`` (derived
        from task-type code). Without this the frontend's progress bar
        stalls at "pending" regardless of actual outcome.
        """
        if task_result.task_id is None:
            logger.warning("TaskResultMessage has no task_id — skipping ImageJobTask advance")
            return

        db_task = (
            self.db.query(ImageJobTask)
            .filter(ImageJobTask.oid == task_result.task_id)
            .first()
        )
        if db_task is None:
            logger.warning(
                "ImageJobTask %s not found — cannot advance state", task_result.task_id
            )
            return

        db_task.status_id = status_id
        type_code = task_result.type.code if task_result.type else None
        db_task.stage = _TASK_TYPE_TO_STAGE.get(type_code, _DEFAULT_STAGE)

        # Provenance (P4). Only overwrite when the plugin sent values —
        # leaving them None would erase the previous attempt's record on
        # a retry, and we want the audit trail to favour what we know.
        if task_result.plugin_id is not None:
            db_task.plugin_id = task_result.plugin_id
        if task_result.plugin_version is not None:
            db_task.plugin_version = task_result.plugin_version

        # Subject axis backfill (Phase 3c, 2026-05-03). The runner
        # echoes subject_kind/subject_id from TaskMessage onto every
        # TaskResultMessage (Phase 3b). Use those values to backfill
        # the ``image_job_task`` row when dispatch left them unset —
        # specifically for tasks created before the importer was
        # taught the subject axis. We do not OVERWRITE a non-default
        # subject because dispatch is the authoritative writer.
        if (
            getattr(task_result, "subject_kind", None) is not None
            and getattr(db_task, "subject_kind", None) in (None, "image")
            and task_result.subject_kind != "image"
        ):
            # Only escalate beyond the DDL default ('image') when the
            # result asserts a richer subject. This protects the
            # back-compat path where importers haven't been migrated
            # yet — they leave subject_kind at its 'image' default
            # and we accept the result's stronger claim.
            db_task.subject_kind = task_result.subject_kind
        if (
            getattr(task_result, "subject_id", None) is not None
            and getattr(db_task, "subject_id", None) is None
        ):
            db_task.subject_id = task_result.subject_id

    def process(self, task_result: TaskResultMessage) -> Dict[str, Any]:
        """Project the result. Returns a small dict for caller logging.

        For artifact-producing categories (PARTICLE_EXTRACTION,
        TWO_D_CLASSIFICATION) we also write one ``artifact`` row per
        result and project its id back into ``output_data`` under a
        category-specific key (``particle_stack_id`` for extraction,
        ``class_averages_id`` for classification) so downstream
        consumers can address by id without joining through the
        producing task.
        """
        try:
            destination_dir = self._get_destination_dir(task_result)

            # 2026-05-04 fix (reviewer-flagged High #3). Pre-fix order
            # was: move files → write artifact rows pointing at the
            # ORIGINAL paths. The artifact rows then advertised paths
            # that no longer existed, so downstream consumers (CAN
            # classifier reading a ``particle_stack`` artifact)
            # 404'd. Fix: rewrite ``output_data`` paths to their
            # post-move destinations BEFORE the artifact write reads
            # them. ``_process_output_files`` returns the source→dest
            # map; we apply it to the path-shaped fields the artifact
            # writer cares about.
            path_remap = self._process_output_files(task_result, destination_dir)
            if path_remap:
                self._rewrite_output_paths(task_result, path_remap)

            # Artifact write must happen BEFORE _save_output_data so the
            # projected id rides into the ImageMetaData blob the latter
            # serialises. Failed (status=FAILED) tasks don't produce an
            # artifact — there's no ``mrcs_path`` to record — so guard
            # on the reported status.
            reported_code = task_result.status.code if task_result.status else None
            artifact_id = None
            if reported_code != STATUS_FAILED:
                artifact_id = self._maybe_write_artifact(task_result)
                if artifact_id is not None:
                    type_code = task_result.type.code if task_result.type else None
                    out = task_result.output_data or {}
                    if type_code == _TASK_TYPE_PARTICLE_EXTRACTION:
                        out["particle_stack_id"] = str(artifact_id)
                    elif type_code == _TASK_TYPE_TWO_D_CLASSIFICATION:
                        out["class_averages_id"] = str(artifact_id)
                    task_result.output_data = out

            if reported_code != STATUS_FAILED:
                type_code = task_result.type.code if task_result.type else None
                if type_code in (_TASK_TYPE_PARTICLE_PICKING, _TASK_TYPE_TOPAZ_PARTICLE_PICKING):
                    self._save_particle_picks(task_result)

            self._save_output_data(task_result)
            self._save_metadata(task_result)

            final_status = (
                STATUS_FAILED if reported_code == STATUS_FAILED else STATUS_COMPLETED
            )
            self._advance_task_state(task_result, status_id=final_status)

            self.db.commit()
            type_name = task_result.type.name if task_result.type else "unknown"
            logger.info("TaskOutputProcessor: %s projected", type_name)

            outcome = "failed" if final_status == STATUS_FAILED else "completed"

            # Advance parent ImageJob status. The step-event projector handles
            # this via NATS, but external plugins (Ptolemy, CTF, etc.) may use
            # RMQ-only transport where NATS JetStream is unavailable. Calling
            # job_manager here guarantees the job settles regardless.
            try:
                from services.job_manager import job_manager as _jm
                job_id_s = str(task_result.job_id) if task_result.job_id else None
                task_id_s = str(task_result.task_id) if task_result.task_id else None
                if job_id_s:
                    if final_status == STATUS_FAILED:
                        _jm.fail_job(job_id_s, error=f"{type_name} processing failed")
                    else:
                        if task_id_s:
                            progress = _jm.record_task_completion(job_id_s, task_id_s)
                            if (
                                progress.get("expected", 0) > 0
                                and progress["completed"] >= progress["expected"]
                            ):
                                _jm.complete_job(
                                    job_id_s,
                                    result={"task_count": progress["expected"]},
                                    num_items=progress["expected"],
                                )
                        else:
                            _jm.complete_job(job_id_s, result={})
            except Exception:
                logger.warning(
                    "TaskOutputProcessor: could not advance parent job %s — non-fatal",
                    task_result.job_id, exc_info=True,
                )

            # Structured operational event — queryable later via DuckDB.
            try:
                from services.ops_event_logger import get_logger as _ops
                _ops().log_task_result(
                    job_id=str(task_result.job_id) if task_result.job_id else None,
                    task_id=str(task_result.task_id) if task_result.task_id else None,
                    category=type_name.lower(),
                    status=outcome,
                    session_name=task_result.session_name,
                    image_name=os.path.splitext(
                        os.path.basename(task_result.image_path or "")
                    )[0] or None,
                )
            except Exception:
                pass

            # Push a lightweight wake-up to any UI watching this job.
            # Best-effort: never blocks the writer or affects DLQ routing.
            try:
                from core.socketio_server import schedule_import_progress
                if task_result.job_id:
                    schedule_import_progress(str(task_result.job_id), {
                        "job_id": str(task_result.job_id),
                        "event": "task_complete",
                        "category": type_name.lower(),
                        "status": outcome,
                    })
            except Exception:
                pass

            return {
                "message": f"{type_name} successfully processed",
                "artifact_id": str(artifact_id) if artifact_id else None,
            }

        except Exception as exc:
            type_name = task_result.type.name if task_result.type else "unknown"
            logger.error("TaskOutputProcessor: %s failed: %s", type_name, exc, exc_info=True)
            self.db.rollback()
            try:
                self._advance_task_state(task_result, status_id=STATUS_FAILED)
                self.db.commit()
            except Exception as state_err:
                logger.error("Could not mark ImageJobTask as FAILED: %s", state_err)
                self.db.rollback()
            try:
                from services.ops_event_logger import get_logger as _ops
                _ops().log_task_result(
                    job_id=str(task_result.job_id) if task_result.job_id else None,
                    task_id=str(task_result.task_id) if task_result.task_id else None,
                    category=type_name.lower(),
                    status="failed",
                    session_name=task_result.session_name,
                    extra={"processor_error": str(exc)},
                )
            except Exception:
                pass
            return {"error": str(exc)}

        finally:
            try:
                self.db.close()
            except Exception as close_err:
                logger.error("Error closing DB session: %s", close_err)


__all__ = [
    "STATUS_COMPLETED",
    "STATUS_FAILED",
    "STATUS_QUEUED",
    "STATUS_RUNNING",
    "TaskOutputProcessor",
]
