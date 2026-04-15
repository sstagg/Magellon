"""Compatibility shim — re-exports plugin bootstrap checks from magellon-sdk."""
from magellon_sdk.bootstrap import (  # noqa: F401
    check_operating_system,
    check_python_version,
    check_requirements_txt,
)

__all__ = [
    "check_operating_system",
    "check_python_version",
    "check_requirements_txt",
]
