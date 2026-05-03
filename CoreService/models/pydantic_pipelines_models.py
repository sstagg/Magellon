"""Pydantic DTOs for the PipelineRun HTTP surface (Phase 8b)."""
from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class PipelineRunCreate(BaseModel):
    """POST /pipelines/runs request body."""

    name: str = Field(..., min_length=1, max_length=200, description="Display name")
    description: Optional[str] = Field(None, description="Free-text notes")
    msession_id: Optional[str] = Field(
        None,
        max_length=100,
        description="Session this run belongs to (empty for cross-session runs)",
    )
    settings: Optional[Dict[str, Any]] = Field(
        None,
        description=(
            "Free-form workflow parameters. Example: "
            '{"picker": {"backend": "topaz", "threshold": -3.0}, '
            '"extractor": {"box_size": 256}, '
            '"classifier": {"num_classes": 50}}.'
        ),
    )


class PipelineRunSummary(BaseModel):
    """Compact list-view row."""

    model_config = ConfigDict(from_attributes=True)

    oid: UUID
    name: Optional[str] = None
    msession_id: Optional[str] = None
    status_id: int
    created_date: Optional[datetime] = None
    started_date: Optional[datetime] = None
    ended_date: Optional[datetime] = None
    job_count: int = 0


class PipelineRunJobSummary(BaseModel):
    """One child ImageJob inside a PipelineRunDetail."""

    model_config = ConfigDict(from_attributes=True)

    oid: UUID
    name: Optional[str] = None
    status_id: Optional[int] = None
    type_id: Optional[int] = None
    plugin_id: Optional[str] = None
    created_date: Optional[datetime] = None
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None


class PipelineRunDetail(BaseModel):
    """GET /pipelines/runs/{oid} response — full row + child jobs."""

    model_config = ConfigDict(from_attributes=True)

    oid: UUID
    name: Optional[str] = None
    description: Optional[str] = None
    msession_id: Optional[str] = None
    status_id: int
    created_date: Optional[datetime] = None
    started_date: Optional[datetime] = None
    ended_date: Optional[datetime] = None
    settings: Optional[Dict[str, Any]] = None
    user_id: Optional[str] = None
    deleted_at: Optional[datetime] = None
    jobs: List[PipelineRunJobSummary] = Field(default_factory=list)


__all__ = [
    "PipelineRunCreate",
    "PipelineRunSummary",
    "PipelineRunJobSummary",
    "PipelineRunDetail",
]
