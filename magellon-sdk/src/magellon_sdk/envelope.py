"""CloudEvents 1.0 envelope for Magellon inter-service messages.

Every event that flows through NATS JetStream or the Temporal activity
boundary is wrapped in this envelope. The schema matches the
`CloudEvents 1.0 <https://github.com/cloudevents/spec/blob/v1.0.2/cloudevents/spec.md>`_
specification so Magellon events interoperate with the broader
CloudEvents ecosystem (routers, replay tools, external consumers).

The generic ``data`` payload preserves the existing Magellon
packet+data shape: the transport concerns (id, source, type, subject,
time) live on the envelope; the domain payload stays intact as ``data``.

Example:

    from magellon_sdk.envelope import Envelope
    from pydantic import BaseModel

    class CtfCompleted(BaseModel):
        job_id: str
        defocus_a: float

    env = Envelope[CtfCompleted](
        source="magellon/plugins/ctf",
        type="magellon.step.completed",
        subject="magellon.job.abc123.step.ctf",
        data=CtfCompleted(job_id="abc123", defocus_a=12345.0),
    )
    wire_bytes = env.model_dump_json().encode("utf-8")
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Generic, Optional, TypeVar

from pydantic import BaseModel, ConfigDict, Field


DataT = TypeVar("DataT")


def _new_id() -> str:
    return str(uuid.uuid4())


def _now() -> datetime:
    return datetime.now(timezone.utc)


class Envelope(BaseModel, Generic[DataT]):
    """CloudEvents 1.0 envelope. All fields follow the spec's casing.

    Required fields per the spec: ``specversion``, ``id``, ``source``,
    ``type``. Magellon additionally requires ``subject`` (because we
    route on `magellon.job.<id>.step.<step>`) and ``time``, and declares
    the datacontenttype as ``application/json`` by default.
    """

    model_config = ConfigDict(extra="allow")

    specversion: str = "1.0"
    id: str = Field(default_factory=_new_id)
    source: str
    type: str
    subject: Optional[str] = None
    time: datetime = Field(default_factory=_now)
    datacontenttype: str = "application/json"
    dataschema: Optional[str] = None
    data: DataT

    @classmethod
    def wrap(
        cls,
        *,
        source: str,
        type: str,
        data: DataT,
        subject: Optional[str] = None,
        dataschema: Optional[str] = None,
    ) -> "Envelope[DataT]":
        """Convenience constructor that fills id/time for callers.

        Most call sites want ``Envelope.wrap(source=..., type=...,
        data=...)`` — this signature keeps the keyword list short.
        """
        return cls(
            source=source,
            type=type,
            subject=subject,
            dataschema=dataschema,
            data=data,
        )


__all__ = ["DataT", "Envelope"]
