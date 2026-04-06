"""Imaging domain exceptions."""

from core.exceptions import MagellonError


class ImageNotFoundError(MagellonError):
    def __init__(self, identifier=None):
        super().__init__(f"Image not found: {identifier}" if identifier else "Image not found")


class SessionNotFoundError(MagellonError):
    def __init__(self, identifier=None):
        super().__init__(f"Session not found: {identifier}" if identifier else "Session not found")


class InvalidImageHierarchyError(MagellonError):
    def __init__(self, message="Invalid image hierarchy"):
        super().__init__(message)
