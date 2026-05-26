from typing import Any

try:
    import pymysql
except ImportError:  # pragma: no cover - legacy importer is not a live route
    pymysql = None

from services.importers.BaseImporter import BaseImporter


class LeginonImporter(BaseImporter):
    def __init__(self):
        super().__init__()
        self.leginon_db_connection = None
        self.leginon_cursor: Any = None
        self.image_tasks = []

    def process(self, db_session):
        raise NotImplementedError(
            "Legacy LeginonImporter is not wired. Use "
            "services.leginon_frame_transfer_job_service.LeginonFrameTransferJobService."
        )

    def import_data(self):
        self.open_leginon_connection()
        try:
            self.fetch_session_data()
            self.fetch_image_data()
        finally:
            self.close_leginon_connection()

    def process_imported_data(self):
        self.create_images_and_tasks()
        self.create_atlas_pics()

    def get_image_tasks(self):
        return self.image_tasks
