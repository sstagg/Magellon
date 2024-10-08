import BaseImporter

class EPUImporter(BaseImporter):
    def __init__(self):
        super().__init__()
        self.image_tasks = []

    def import_data(self):
        # Implement EPU-specific data import logic
        # This might involve parsing XML files
        pass

    def process_imported_data(self):
        # Implement EPU-specific data processing logic
        pass

    def get_image_tasks(self):
        return self.image_tasks