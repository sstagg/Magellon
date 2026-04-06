"""Domain exceptions for the Magellon Core Service.

Services should raise these instead of HTTPException.
Controllers catch them and convert to appropriate HTTP responses.
"""


class MagellonError(Exception):
    """Base exception for all domain errors."""
    pass


class EntityNotFoundError(MagellonError):
    """Raised when a requested entity does not exist."""
    def __init__(self, entity_type: str, identifier=None):
        self.entity_type = entity_type
        self.identifier = identifier
        msg = f"{entity_type} not found"
        if identifier:
            msg += f": {identifier}"
        super().__init__(msg)


class DuplicateEntityError(MagellonError):
    """Raised when attempting to create an entity that already exists."""
    def __init__(self, entity_type: str, name: str):
        self.entity_type = entity_type
        self.name = name
        super().__init__(f"{entity_type} already exists: {name}")


class ImportError(MagellonError):
    """Base exception for data import failures."""
    pass


class FileProcessingError(MagellonError):
    """Raised when file I/O or processing fails."""
    pass


class TaskDispatchError(MagellonError):
    """Raised when a task cannot be dispatched to the queue."""
    pass


class ExternalServiceError(MagellonError):
    """Raised when an external service (Leginon DB, RabbitMQ, etc.) fails."""
    pass


class ValidationError(MagellonError):
    """Raised when domain validation rules are violated."""
    pass


class PermissionDeniedError(MagellonError):
    """Raised when an operation is not permitted."""
    pass
