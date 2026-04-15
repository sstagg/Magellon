"""Canonical plugin-contract types.

Plugins and the Magellon host agree on these shapes. Everything here is
part of the public SDK surface — renames or field removals are breaking
changes and require a major-version bump.

TaskBase / TaskDto / JobDto envelope types are *not* declared here yet —
they move in a later PR (CloudEvents envelope). This module is limited
to what `PluginBase` needs at the function-signature level.
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
    DISCOVERED = "discovered"      # Found on disk / in registry
    INSTALLED = "installed"        # Dependencies resolved
    CONFIGURED = "configured"      # Settings validated
    READY = "ready"                # setup() completed, can accept work
    RUNNING = "running"            # execute() in progress
    COMPLETED = "completed"        # Last execution succeeded
    ERROR = "error"                # Recoverable error, can retry
    FAILED = "failed"              # Terminal failure
    DISABLED = "disabled"          # Administratively disabled


class TaskCategory(BaseModel):
    code: int
    name: str
    description: str

    def __hash__(self) -> int:
        return hash(self.code)

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, TaskCategory):
            return False
        return self.code == other.code


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
    # Using default_factory so each instance gets a fresh timestamp, not
    # the module-import time frozen into the class default. Also
    # timezone-aware (datetime.utcnow() is deprecated and banned inside
    # Temporal's workflow sandbox).
    created_date: Optional[datetime] = Field(default_factory=_now_utc)
    last_updated: Optional[datetime] = Field(default_factory=_now_utc)


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
    "PluginStatus",
    "RecuirementResultEnum",
    "RequirementResult",
    "TaskCategory",
]
