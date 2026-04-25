"""In-process result writer — folded in from the out-of-tree
``magellon_result_processor`` plugin (P3).

The plugin used to own this logic and reach into the Magellon DB
directly. That broke invariant I2 ("plugins never touch the DB"):
schema migrations had to chase a separate deploy artefact, and a
plugin crash could leave half-written rows. Promoting the writer
into CoreService gives us:

  - One process owning the per-task DB write (status_id + stage),
    same session that records the metadata.
  - A clear contract for plugins: publish ``TaskResultDto`` to your
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
from models.plugins_models import TaskResultDto
from models.pydantic_models_settings import OutQueueConfig, OutQueueType
from models.sqlalchemy_models import ImageJobTask, ImageMetaData

logger = logging.getLogger(__name__)

# ImageJobTask.status_id values — must match services.job_manager.
STATUS_QUEUED = 0
STATUS_RUNNING = 1
STATUS_COMPLETED = 2
STATUS_FAILED = 3

# ImageJobTask.stage values — per task-type code. The stage is the
# position of that step in the per-image pipeline:
#   1 = MotionCor              (TaskCategory.code == 5)
#   2 = CTF                    (TaskCategory.code == 2)
#   3 = SquareDetection        (TaskCategory.code == 6)
#   4 = HoleDetection          (TaskCategory.code == 7)
#   5 = TopazParticlePicking   (TaskCategory.code == 8)
#   6 = MicrographDenoising    (TaskCategory.code == 9)
# Unknown task types land at 99 so operators can spot them in the UI.
_TASK_TYPE_TO_STAGE = {5: 1, 2: 2, 6: 3, 7: 4, 8: 5, 9: 6}
_DEFAULT_STAGE = 99

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
    """Project a ``TaskResultDto`` into the Magellon DB + on-disk layout.

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

    def _get_destination_dir(self, task_result: TaskResultDto) -> str:
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
        self, task_result: TaskResultDto, destination_dir: str
    ) -> None:
        for output_file in task_result.output_files or []:
            _move_file_to_directory(output_file.path, destination_dir)

    def _save_output_data(self, task_result: TaskResultDto) -> None:
        if task_result.output_data:
            self.db.add(
                ImageMetaData(
                    oid=uuid.uuid4(),
                    name=f"{task_result.type.name} Data",
                    data=json.dumps(task_result.output_data).encode("utf-8"),
                    image_id=task_result.image_id,
                )
            )

    def _save_metadata(self, task_result: TaskResultDto) -> None:
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

    def _advance_task_state(
        self,
        task_result: TaskResultDto,
        *,
        status_id: int,
    ) -> None:
        """Advance the ``image_job_task`` row for this result.

        Sets ``status_id`` (COMPLETED / FAILED) and ``stage`` (derived
        from task-type code). Without this the frontend's progress bar
        stalls at "pending" regardless of actual outcome.
        """
        if task_result.task_id is None:
            logger.warning("TaskResultDto has no task_id — skipping ImageJobTask advance")
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

    def process(self, task_result: TaskResultDto) -> Dict[str, Any]:
        """Project the result. Returns a small dict for caller logging."""
        try:
            destination_dir = self._get_destination_dir(task_result)
            self._process_output_files(task_result, destination_dir)
            self._save_output_data(task_result)
            self._save_metadata(task_result)

            reported_code = task_result.status.code if task_result.status else None
            final_status = (
                STATUS_FAILED if reported_code == STATUS_FAILED else STATUS_COMPLETED
            )
            self._advance_task_state(task_result, status_id=final_status)

            self.db.commit()
            type_name = task_result.type.name if task_result.type else "unknown"
            logger.info("TaskOutputProcessor: %s projected", type_name)
            return {"message": f"{type_name} successfully processed"}

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
