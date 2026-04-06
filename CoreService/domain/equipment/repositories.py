"""Abstract repository interfaces for the equipment domain."""

from abc import ABC, abstractmethod
from typing import Optional
from uuid import UUID


class CameraRepositoryInterface(ABC):
    """Interface for camera persistence operations."""

    @abstractmethod
    def fetch_by_id(self, db, _id: UUID):
        pass

    @abstractmethod
    def fetch_by_name(self, db, name: str):
        pass

    @abstractmethod
    def fetch_all(self, db, skip: int = 0, limit: int = 100):
        pass

    @abstractmethod
    async def create(self, db, entity):
        pass

    @abstractmethod
    async def delete(self, db, _id: UUID):
        pass

    @abstractmethod
    async def update(self, db, entity):
        pass
