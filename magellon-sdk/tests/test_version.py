from __future__ import annotations

from importlib.metadata import PackageNotFoundError, version

import pytest

import magellon_sdk


def test_public_version_matches_installed_package_metadata() -> None:
    try:
        package_version = version("magellon-sdk")
    except PackageNotFoundError:
        pytest.skip("magellon-sdk is not installed in this environment")

    assert magellon_sdk.__version__ == package_version
