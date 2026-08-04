"""Stable response models shared by CoreService controllers.

The API historically returned several incompatible error shapes.  These
models establish a small envelope without forcing a breaking rewrite of
successful legacy responses.
"""
from __future__ import annotations

from typing import Any, Generic, Optional, TypeVar

from pydantic import BaseModel, Field


T = TypeVar("T")


class ErrorResponse(BaseModel):
    code: str = Field(description="Stable machine-readable error code")
    message: str
    request_id: Optional[str] = None
    details: Optional[Any] = None


class ApiResponse(BaseModel, Generic[T]):
    data: T
    request_id: Optional[str] = None

