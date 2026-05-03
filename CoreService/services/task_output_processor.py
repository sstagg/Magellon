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
from models.plugins_models import TaskResultMessage
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
# Unknown task types land at 99 so operators can spot them in the UI.
_TASK_TYPE_TO_STAGE = {5: 1, 2: 2, 6: 3, 7: 4, 8: 5, 9: 6, 10: 7, 4: 8}
_DEFAULT_STAGE = 99

# TaskCategory codes for the artifact-producing categories handled below.
# Kept as bare ints (matching the SDK constants) so we don't pull a
# magellon_sdk import into this hot path just for two switch-cases.
_TASK_TYPE_PARTICLE_EXTRACTION = 10  # PARTICLE_EXTRACTION
_TASK_TYPE_TWO_D_CLASSIFICATION = 4  # TWO_D_CLASSIFICATION

# Artifact.kind discriminator values. Mirrors magellon_sdk.models.artifact.ArtifactKind
# but kept local to avoid a cross-package coupling on the enum string.
_ARTIFACT_KIND_PARTICLE_STACK = "particle_stack"
_ARTIFACT_KIND_CLASS_AVERAGES = "class_averages"

# Default category id when no OutQueueConfig matches — preserves the
# old plugin's fallback so existing rows keep their lineage.
_DEFAULT_CATEGORY_ID = 10


def _move_file_to_directory(file_path: str, destination_dir: str) -> None:
    """Move ``file_path`` into ``destination_dir``, creating it if missing.

    Best-effort: a missing source is logged and skipped — the metadata
    write should still happen so the UI can surface the failure.
    """
    try:
        if not file_path:
            return
        os.makedirs(destination_dir, exist_ok=True)
        filename = os.path.basename(file_path)
        shutil.move(file_path, os.path.join(destination_dir, filename))
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
    ) -> None:
        for output_file in task_result.output_files or []:
            _move_file_to_directory(output_file.path, destination_dir)

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
        """
        if task_result.type is None:
            return None

        type_code = task_result.type.code
        out = task_result.output_data or {}
        artifact_id = uuid.uuid4()

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
            )
            self.db.add(row)
            return artifact_id

        if type_code == _TASK_TYPE_TWO_D_CLASSIFICATION:
            row = Artifact(
                oid=artifact_id,
                kind=_ARTIFACT_KIND_CLASS_AVERAGES,
                producing_job_id=task_result.job_id,
                producing_task_id=task_result.task_id,
                msession_id=task_result.session_name,
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
                    "source_particle_stack_id": out.get("source_particle_stack_id"),
                },
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
            self._process_output_files(task_result, destination_dir)

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

            self._save_output_data(task_result)
            self._save_metadata(task_result)

            final_status = (
                STATUS_FAILED if reported_code == STATUS_FAILED else STATUS_COMPLETED
            )
            self._advance_task_state(task_result, status_id=final_status)

            self.db.commit()
            type_name = task_result.type.name if task_result.type else "unknown"
            logger.info("TaskOutputProcessor: %s projected", type_name)
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
