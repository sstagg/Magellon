"""Progress-reporting contract.

The plugin-facing Protocol is the only thing plugins should depend on —
the host supplies a concrete implementation (e.g. CoreService's
`JobReporter`) that writes to a job store and emits Socket.IO frames.
When a plugin runs outside a job context (unit tests, ad-hoc calls) the
host passes a :class:`NullReporter` so plugins can call `report()`
unconditionally.

`JobReporter` itself stays in CoreService because it depends on
CoreService internals (JobService, Socket.IO). That split keeps the SDK
host-free.
"""
from __future__ import annotations

from typing import Optional, Protocol


class JobCancelledError(Exception):
    """Raised by a reporter when the user has asked to cancel this job.

    Plugins don't need to catch this — it propagates out of ``execute()``
    and the host translates it into a cancelled-job envelope.
    """


class ProgressReporter(Protocol):
    """Minimal contract every reporter implements.

    Plugins depend on this Protocol, not a concrete class — so test code
    can hand in a plain mock with a ``report`` attribute.
    """

    def report(self, percent: int, message: Optional[str] = None) -> None: ...

    def log(self, level: str, message: str) -> None: ...


class NullReporter:
    """No-op reporter used when a plugin runs outside a job context."""

    def report(self, percent: int, message: Optional[str] = None) -> None:
        return

    def log(self, level: str, message: str) -> None:
        return


__all__ = ["JobCancelledError", "NullReporter", "ProgressReporter"]
