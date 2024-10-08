from services.importers.EPUImporter import EPUImporter
from services.importers.LeginonImporter import LeginonImporter


class ImporterFactory:
    @staticmethod
    def get_importer(importer_type):
        if importer_type == "leginon":
            return LeginonImporter()
        elif importer_type == "epu":
            return EPUImporter()
        else:
            raise ValueError(f"Unknown importer type: {importer_type}")