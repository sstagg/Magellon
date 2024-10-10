import pymysql

import BaseImporter

class LeginonImporter(BaseImporter):
    def __init__(self):
        super().__init__()
        self.leginon_db_connection = None
        self.leginon_cursor: pymysql.cursors.Cursor = None
        self.image_tasks = []

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