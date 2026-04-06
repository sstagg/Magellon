"""Import domain exceptions."""

from core.exceptions import MagellonError


class ImportSourceNotFoundError(MagellonError):
    def __init__(self, source_type: str, path: str):
        self.source_type = source_type
        self.path = path
        super().__init__(f"{source_type} source not found: {path}")


class ImportValidationError(MagellonError):
    def __init__(self, message: str):
        super().__init__(message)


class UnsupportedImportFormatError(MagellonError):
    def __init__(self, format_name: str):
        super().__init__(f"Unsupported import format: {format_name}")
