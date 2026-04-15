"""Smoke test: the SDK scaffold imports and reports its version.

Guards against dumb mistakes in pyproject/packaging — e.g. renaming the
package dir without updating the wheel target, or deleting the __init__.
"""
from __future__ import annotations


def test_sdk_imports():
    import magellon_sdk

    assert hasattr(magellon_sdk, "__version__")
    assert magellon_sdk.__version__ == "0.1.0"


def test_py_typed_marker_present():
    """PEP 561: shipping `py.typed` lets downstream type-check imports."""
    import pathlib

    import magellon_sdk

    pkg_dir = pathlib.Path(magellon_sdk.__file__).parent
    assert (pkg_dir / "py.typed").exists()
