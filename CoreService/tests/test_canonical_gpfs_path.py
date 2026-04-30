"""Unit tests for ``core.helper.to_canonical_gpfs_path``.

The hybrid Windows-host + Docker-plugin topology has CoreService building
host-absolute paths (``C:/magellon/gpfs/...``) that the plugin container
can't open — its only mount sees data as ``/gpfs/...``. The dispatch
boundary translates host paths to canonical ``/gpfs/...`` so plugins
across realms can resolve them. These tests pin the translation
contract.
"""
from __future__ import annotations

import pytest

from config import app_settings
from core.helper import to_canonical_gpfs_path


@pytest.fixture()
def gpfs_root(monkeypatch):
    """Force MAGELLON_GPFS_PATH to a Windows-style host root."""
    monkeypatch.setattr(
        app_settings.directory_settings, "MAGELLON_GPFS_PATH", "C:/magellon/gpfs"
    )


@pytest.fixture()
def linux_gpfs_root(monkeypatch):
    """A Linux deployment where MAGELLON_GPFS_PATH already equals /gpfs."""
    monkeypatch.setattr(
        app_settings.directory_settings, "MAGELLON_GPFS_PATH", "/gpfs"
    )


class TestToCanonicalGpfsPath:
    def test_translates_forward_slash_host_path(self, gpfs_root):
        result = to_canonical_gpfs_path(
            "C:/magellon/gpfs/24dec03a/home/original/image.mrc"
        )
        assert result == "/gpfs/24dec03a/home/original/image.mrc"

    def test_translates_windows_backslash_path(self, gpfs_root):
        # os.path.join on Windows produces backslashes — must still match.
        result = to_canonical_gpfs_path(
            "C:\\magellon\\gpfs\\24dec03a\\home\\original\\image.mrc"
        )
        assert result == "/gpfs/24dec03a/home/original/image.mrc"

    def test_case_insensitive_drive_letter(self, gpfs_root):
        # Windows is case-insensitive; an upper-case drive must still match.
        result = to_canonical_gpfs_path(
            "c:/MAGELLON/GPFS/24dec03a/home/original/image.mrc"
        )
        assert result == "/gpfs/24dec03a/home/original/image.mrc"

    def test_root_only_path(self, gpfs_root):
        assert to_canonical_gpfs_path("C:/magellon/gpfs") == "/gpfs"

    def test_root_with_trailing_slash_in_setting(self, monkeypatch):
        monkeypatch.setattr(
            app_settings.directory_settings, "MAGELLON_GPFS_PATH", "C:/magellon/gpfs/"
        )
        assert (
            to_canonical_gpfs_path("C:/magellon/gpfs/24dec03a/x.mrc")
            == "/gpfs/24dec03a/x.mrc"
        )

    def test_path_outside_gpfs_root_passes_through(self, gpfs_root):
        # Paths not under the GPFS root must NOT be rewritten — the plugin
        # has no mount for them and silent rewriting would mask bugs.
        assert (
            to_canonical_gpfs_path("C:/elsewhere/file.mrc")
            == "C:/elsewhere/file.mrc"
        )

    def test_already_canonical_path_passes_through(self, gpfs_root):
        # If a caller has already converted, don't double-translate.
        assert (
            to_canonical_gpfs_path("/gpfs/24dec03a/x.mrc")
            == "/gpfs/24dec03a/x.mrc"
        )

    def test_linux_deployment_is_noop(self, linux_gpfs_root):
        # When MAGELLON_GPFS_PATH is /gpfs (Linux container deployments)
        # CoreService and plugins share the same mount, no rewrite needed.
        assert (
            to_canonical_gpfs_path("/gpfs/24dec03a/x.mrc")
            == "/gpfs/24dec03a/x.mrc"
        )

    @pytest.mark.parametrize("falsy", [None, ""])
    def test_falsy_path_passes_through(self, gpfs_root, falsy):
        # dispatch_motioncor_task may pass defects_path=None — must not
        # crash and must not invent a /gpfs path out of nothing.
        assert to_canonical_gpfs_path(falsy) == falsy

    def test_gpfs_root_unset_passes_through(self, monkeypatch):
        # If MAGELLON_GPFS_PATH is unconfigured, do nothing rather than
        # guess.
        monkeypatch.setattr(
            app_settings.directory_settings, "MAGELLON_GPFS_PATH", None
        )
        assert (
            to_canonical_gpfs_path("C:/magellon/gpfs/x.mrc")
            == "C:/magellon/gpfs/x.mrc"
        )
