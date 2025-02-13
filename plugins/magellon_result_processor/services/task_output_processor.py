from typing import Dict, Any, Optional
from uuid import UUID
import os
import json
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError
import uuid
from core.model_dto import TaskResultDto
from core.settings import AppSettingsSingleton, QueueType
from core.sqlalchemy_models import ImageMetaData
from core.helper import move_file_to_directory
import logging
logger = logging.getLogger(__name__)
class TaskOutputProcessor:
    def __init__(self, db: Session):
        self.db = db
        self.settings = AppSettingsSingleton.get_instance()
        self._queue_type_output_config = self._build_queue_type_output_config()

    def _build_queue_type_output_config(self) -> Dict[QueueType, Dict[str, Any]]:
        """
        Build a dictionary mapping queue types to their configuration details.
        Uses the OUT_QUEUES configuration from RabbitMQ settings.
        """
        return {
            queue_config.queue_type: {
                "dir_name": queue_config.dir_name,
                "category": queue_config.category
            }
            for queue_config in self.settings.rabbitmq_settings.OUT_QUEUES
        }


    def _get_queue_type_output_dir(self, queue_type: QueueType) -> Optional[str]:
        """
        Get the output directory name for a specific queue type.

        :param queue_type: The queue type to look up
        :return: The output directory name, or None if not found
        """
        queue_config = self._queue_type_output_config.get(queue_type, {})
        return queue_config.get("dir_name")

    def _get_queue_type_category(self, queue_type: QueueType) -> Optional[int]:
        """
        Get the category for a specific queue type.

        :param queue_type: The queue type to look up
        :return: The category, or None if not found
        """
        queue_config = self._queue_type_output_config.get(queue_type, {})
        return queue_config.get("category")

    def _get_destination_dir(self, task_result: TaskResultDto) -> str:
        """Get the appropriate destination directory based on task type."""
        task_type = task_result.type.name.lower()
        # Try to get directory from queue type first
        queue_specific_dir = self._get_queue_type_output_dir(task_type)
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
                oid=uuid.uuid4(),
                name=f"{task_result.type.name} Data",
                data=json.dumps(task_result.output_data).encode("utf-8"),
                image_id=task_result.image_id
            )
            self.db.add(output_meta)

    def _save_metadata(self, task_result: TaskResultDto):
        """Save task metadata to database."""
        try:
            if task_result.meta_data:
                meta_list_dicts = [meta.dict(exclude_none=True) for meta in task_result.meta_data]
                task_type = task_result.type.name.lower()
                category_id = self._get_queue_type_category(task_type) or 10  # Default to 10 if no category found

                meta_data = ImageMetaData(
                    oid=uuid.uuid4(),
                    name=f"{task_result.type.name} Meta Data",
                    data_json=json.loads(json.dumps(meta_list_dicts, indent=4)),
                    image_id=task_result.image_id,
                    category_id=category_id  # if task_result.type == ctf, if it is motioncor it would be 3
                )

                self.db.add(meta_data)
                self.db.commit()
        
        except SQLAlchemyError as db_err:
            self.db.rollback()  # Rollback transaction in case of database error
            print(f"Database error: {db_err}")
        
        except (ValueError, TypeError, json.JSONDecodeError) as json_err:
            print(f"JSON processing error: {json_err}")
        
        except AttributeError as attr_err:
            print(f"Attribute error: {attr_err}")
        
        except Exception as e:
            print(f"Unexpected error: {e}")

    def process(self, task_result: TaskResultDto) -> Dict[str, Any]:
        """
        Process task output based on its type and save results.
        """
        try:
            destination_dir = self._get_destination_dir(task_result)

            # Process output files
            self._process_output_files(task_result, destination_dir)

            # Save output data and metadata
            self._save_output_data(task_result)
            logger.info("Successfully copied files.")

            self._save_metadata(task_result)

            # Commit database changes
            self.db.commit()
            logger.info("Successfully added to database.")

            return {"message": f"{task_result.type.name} successfully processed"}

        except Exception as exc:
            logger.error(f"Error processing {task_result.type.name}: {exc}", exc_info=True)
            self.db.rollback()
            return {"error": str(exc)}

        finally:
            try:
                self.db.close()
            except Exception as db_close_err:
                logger.error(f"Error closing the database connection: {db_close_err}", exc_info=True)

# Updated do_execute function
# async def do_execute(task_result_param: TaskResultDto, db: Session):
#     processor = TaskOutputProcessor(db)
#     return processor.process(task_result_param)