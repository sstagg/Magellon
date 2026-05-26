"""Smoke test: the SDK scaffold imports and reports its version.

Guards against dumb mistakes in pyproject/packaging — e.g. renaming the
package dir without updating the wheel target, or deleting the __init__.
"""
from __future__ import annotations

import argparse


def test_sdk_imports():
    import magellon_sdk

    assert hasattr(magellon_sdk, "__version__")
    # Pin major version only so a 2.x patch release doesn't churn this
    # test. The 0.1.0 pin pre-dated SDK 1.x and was stale on every
    # release between then and 2.0.0.
    assert magellon_sdk.__version__.startswith("2."), magellon_sdk.__version__


def test_py_typed_marker_present():
    """PEP 561: shipping `py.typed` lets downstream type-check imports."""
    import pathlib

    import magellon_sdk

    pkg_dir = pathlib.Path(magellon_sdk.__file__).parent
    assert (pkg_dir / "py.typed").exists()


def test_plugin_scaffold_uses_current_bus_bootstrap(tmp_path):
    from magellon_sdk.cli.main import cmd_plugin_scaffold

    target = tmp_path / "demo-fft-plugin"
    rc = cmd_plugin_scaffold(
        argparse.Namespace(
            name=str(target),
            plugin_id=None,
            display_name=None,
            category="fft",
        )
    )

    assert rc == 0
    main_py = (target / "main.py").read_text(encoding="utf-8")
    assert "from magellon_sdk.bus.bootstrap import install_rmq_bus" in main_py
    assert "magellon_sdk.bus.transport.rabbitmq" not in main_py
