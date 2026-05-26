from __future__ import annotations

from importlib import import_module


class ImporterFactory:
    _IMPORTERS = {
        "magellon": ("services.importers.MagellonImporter", "MagellonImporter"),
        "epu": ("services.importers.EPUImporter", "EPUImporter"),
        "serialem": ("services.importers.SerialEmImporter", "SerialEmImporter"),
        "serial_em": ("services.importers.SerialEmImporter", "SerialEmImporter"),
    }

    @staticmethod
    def get_importer(importer_type):
        importer_key = (importer_type or "").lower()
        if importer_key == "leginon":
            raise ValueError(
                "Legacy LeginonImporter is not supported by ImporterFactory; "
                "use LeginonFrameTransferJobService instead."
            )

        try:
            module_name, class_name = ImporterFactory._IMPORTERS[importer_key]
        except KeyError as exc:
            raise ValueError(f"Unknown importer type: {importer_type}") from exc

        module = import_module(module_name)
        return getattr(module, class_name)()


def import_data(importer_type, input_data, db_session):
    importer = ImporterFactory.get_importer(importer_type)
    importer.setup(input_data, db_session)
    return importer.process(db_session)
