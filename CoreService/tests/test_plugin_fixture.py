"""Sanity test for ``tests/fixtures/plugins/sample.mpn`` (P3).

Pin the fixture's contract so a regression in the SDK's pack CLI or
in our build script (``tests/fixtures/plugins/build.py``) surfaces
here, not in the install tests that consume the fixture downstream.
"""
from __future__ import annotations

import zipfile
from pathlib import Path

import pytest

from magellon_sdk.archive.manifest import load_manifest_bytes


FIXTURE_DIR = Path(__file__).parent / "fixtures" / "plugins"
SAMPLE_MPN = FIXTURE_DIR / "sample.mpn"


@pytest.fixture(scope="module")
def sample_manifest():
    if not SAMPLE_MPN.exists():
        pytest.fail(
            f"{SAMPLE_MPN} missing — rebuild with "
            f"`python {FIXTURE_DIR / 'build.py'}`"
        )
    with zipfile.ZipFile(SAMPLE_MPN) as z:
        with z.open("manifest.yaml") as f:
            return load_manifest_bytes(f.read())


def test_sample_archive_exists():
    assert SAMPLE_MPN.exists(), (
        f"committed fixture {SAMPLE_MPN} missing — rebuild via build.py"
    )


def test_sample_manifest_validates(sample_manifest):
    """The fixture must round-trip through the same Pydantic model
    the install pipeline uses. If this fails after a manifest schema
    change, regenerate the fixture."""
    assert sample_manifest.plugin_id == "sample-plugin"
    assert sample_manifest.version == "0.1.0"
    assert sample_manifest.install[0].method == "uv"


def test_sample_archive_carries_legacy_plugin_yaml_alias():
    """The committed fixture must carry both manifest names so
    install controllers reading the legacy ``plugin.yaml`` keep
    working until P4 retires that path."""
    with zipfile.ZipFile(SAMPLE_MPN) as z:
        names = z.namelist()
    assert "manifest.yaml" in names
    assert "plugin.yaml" in names


def test_sample_archive_has_complete_checksums(sample_manifest):
    """The pack-CLI invariant — every non-manifest file in the
    archive has a SHA256 entry. A regression here would let the
    UvInstaller's checksum verification step pass on tampered
    files."""
    import hashlib

    with zipfile.ZipFile(SAMPLE_MPN) as z:
        archive_files = {
            n for n in z.namelist()
            if n not in ("manifest.yaml", "plugin.yaml")
        }
        # Every actual file must be in the manifest's table.
        assert archive_files == set(sample_manifest.file_checksums.keys())

        # Each recorded checksum matches the bytes in the zip.
        for arcname, expected in sample_manifest.file_checksums.items():
            with z.open(arcname) as f:
                actual = hashlib.sha256(f.read()).hexdigest()
            assert actual == expected, f"checksum mismatch for {arcname}"


def test_sample_archive_id_is_uuid_v7(sample_manifest):
    assert sample_manifest.archive_id.version == 7
