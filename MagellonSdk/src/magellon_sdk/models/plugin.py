"""Plugin-identity and requirement-check models.

These are the pieces of the SDK surface that describe *the plugin itself*
(name, version, requirement-check outcomes). Task-shaped DTOs live in
``magellon_sdk.models.tasks``.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


class PluginStatus(str, Enum):
    """Lifecycle states for a Magellon plugin."""
    DISCOVERED = "discovered"
    INSTALLED = "installed"
    CONFIGURED = "configured"
    READY = "ready"
    RUNNING = "running"
    COMPLETED = "completed"
    ERROR = "error"
    FAILED = "failed"
    DISABLED = "disabled"


class PluginInfo(BaseModel):
    id: Optional[str] = Field(default_factory=lambda: str(uuid.uuid4()))
    instance_id: Optional[str] = Field(default_factory=lambda: str(uuid.uuid4()))
    name: Optional[str] = None
    developer: Optional[str] = None
    description: Optional[str] = None
    copyright: Optional[str] = None
    version: Optional[str] = None
    # Bumped by the plugin author whenever the input or output JSON
    # Schema changes in a breaking way. The frontend compares against
    # its cached value and re-fetches the form when they diverge.
    schema_version: Optional[str] = "1"
    created_date: Optional[datetime] = Field(default_factory=_now_utc)
    last_updated: Optional[datetime] = Field(default_factory=_now_utc)


class PluginInfoSingleton:
    """Process-wide singleton wrapper around :class:`PluginInfo`.

    Plugins call ``PluginInfoSingleton.get_instance(**kwargs)`` once at
    startup to stamp the plugin's identity; subsequent calls return the
    already-constructed instance (kwargs ignored after first call).
    """

    _instance: Optional[PluginInfo] = None

    @classmethod
    def get_instance(cls, **kwargs) -> PluginInfo:
        if cls._instance is None:
            cls._instance = PluginInfo(**kwargs)
        return cls._instance


class CheckRequirementsResult(Enum):
    SUCCESS = 100
    FAILURE_PYTHON_VERSION_ERROR = 201
    FAILURE_OS_ERROR = 202
    FAILURE_REQUIREMENTS = 203


class RecuirementResultEnum(Enum):
    SUCCESS = 10
    WARNING = 20
    FAILURE = 30


class RequirementResult(BaseModel):
    code: Optional[int] = None
    error_type: Optional[CheckRequirementsResult] = None
    result: RecuirementResultEnum = RecuirementResultEnum.FAILURE
    condition: Optional[str] = None
    message: Optional[str] = None
    instructions: Optional[str] = None


__all__ = [
    "CheckRequirementsResult",
    "PluginInfo",
    "PluginInfoSingleton",
    "PluginStatus",
    "RecuirementResultEnum",
    "RequirementResult",
]
