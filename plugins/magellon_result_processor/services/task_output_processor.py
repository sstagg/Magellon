from typing import Dict, Any, Optional
from uuid import UUID
import os
import json
from sqlalchemy.orm import Session

from core.model_dto import TaskResultDto
from core.settings import AppSettingsSingleton, QueueType
from core.sqlalchemy_models import ImageMetaData
from core.helper import move_file_to_directory

class TaskOutputProcessor:
    def __init__(self, db: Session):
        self.db = db
        self.settings = AppSettingsSingleton.get_instance()
        self._queue_type_output_dirs = self._build_queue_type_output_dirs()

    def _build_queue_type_output_dirs(self) -> Dict[QueueType, str]:
        """
        Build a dictionary mapping queue types to their output directory names.
        Uses the OUT_QUEUES configuration from RabbitMQ settings.
        """
        return {
            queue_config.queue_type: queue_config.dir_name
            for queue_config in self.settings.rabbitmq_settings.OUT_QUEUES
        }


    def _get_queue_type_output_dir(self, queue_type: QueueType) -> Optional[str]:
        """
        Get the output directory name for a specific queue type.

        :param queue_type: The queue type to look up
        :return: The output directory name, or None if not found
        """
        return self._queue_type_output_dirs.get(queue_type)

    def _get_destination_dir(self, task_result: TaskResultDto) -> str:
        """Get the appropriate destination directory based on task type."""
        task_type = task_result.type.name.lower()
        # Try to get directory from queue type first
        queue_specific_dir = self._get_queue_type_output_dir(task_result.type)
        dir_name = queue_specific_dir or task_type

        file_name = os.path.splitext(os.path.basename(task_result.image_path))[0]
        return os.path.join(
            self.settings.MAGELLON_HOME_DIR,
            task_result.session_name,
            dir_name,
            file_name
        )

    # def _save_debug_info(self, task_result: TaskResultDto, destination_dir: str):
    #     """Save debug information if needed."""
    #     try:
    #         if not os.path.exists(destination_dir):
    #             os.makedirs(destination_dir)
    #         debug_file = os.path.join(destination_dir, f"{task_result.type.name.lower()}_message.json")
    #         with open(debug_file, 'w') as f:
    #             json.dump(task_result.dict(), f, indent=4, default=str)
    #     except Exception as e:
    #         print(f"Debug info save error: {e}")

    def _process_output_files(self, task_result: TaskResultDto, destination_dir: str):
        """Process and move output files."""
        for output_file in task_result.output_files:
            move_file_to_directory(output_file.path, destination_dir)

    def _save_output_data(self, task_result: TaskResultDto):
        """Save task output data to database."""
        if task_result.output_data:
            output_meta = ImageMetaData(
                oid=UUID(int=0).int,
                name=f"{task_result.type.name} Data",
                data=json.dumps(task_result.output_data).encode("utf-8"),
                image_id=task_result.image_id
            )
            self.db.add(output_meta)

    def _save_metadata(self, task_result: TaskResultDto):
        """Save task metadata to database."""
        if task_result.meta_data:
            meta_list_dicts = [meta.dict(exclude_none=True) for meta in task_result.meta_data]
            meta_data = ImageMetaData(
                oid=UUID(int=0).int,
                name=f"{task_result.type.name} Meta Data",
                data_json=json.loads(json.dumps(meta_list_dicts, indent=4)),
                image_id=task_result.image_id
            )
            self.db.add(meta_data)

    def process(self, task_result: TaskResultDto) -> Dict[str, Any]:
        """
        Process task output based on its type and save results.
        """
        try:
            destination_dir = self._get_destination_dir(task_result)

            # Save debug information
            # self._save_debug_info(task_result, destination_dir)

            # Process output files
            self._process_output_files(task_result, destination_dir)

            # Save output data and metadata
            self._save_output_data(task_result)
            self._save_metadata(task_result)

            # Commit database changes
            self.db.commit()

            return {"message": f"{task_result.type.name} successfully processed"}

        except Exception as exc:
            self.db.rollback()
            return {"error": str(exc)}
        finally:
            self.db.close()

# Updated do_execute function
# async def do_execute(task_result_param: TaskResultDto, db: Session):
#     processor = TaskOutputProcessor(db)
#     return processor.process(task_result_param)