"""Compatibility shim — re-exports the shared task factories."""
from magellon_sdk.task_factory import (  # noqa: F401
    CtfTaskFactory,
    FftTaskFactory,
    MotioncorTaskFactory,
    TaskFactory,
)
