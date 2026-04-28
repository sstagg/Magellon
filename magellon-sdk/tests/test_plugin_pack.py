"""Tests for the ``magellon-sdk plugin pack`` CLI.

Pin the contracts the install pipeline depends on:

  - Pack produces a `.mpn` zip with both ``manifest.yaml`` (canonical)
    and ``plugin.yaml`` (legacy alias) at the archive root.
  - ``archive_id`` is auto-generated as a UUID v7 per build (so two
    builds of the same source get different ids, naturally
    time-sortable on the hub).
  - ``updated`` is stamped to now; ``created`` is preserved if
    already meaningful.
  - ``file_checksums`` covers every non-manifest file in the archive
    with SHA256 hashes.
  - Hidden files / __pycache__ / .pyc / build artifacts are skipped
    so plugin authors don't accidentally ship a 200 MB archive full
    of caches.
  - Source manifest itself is NOT duplicated as a regular file — pack
    writes a *regenerated* one at the canonical name.
  - Reading the archive back through the validator round-trips the
    manifest cleanly.
"""
from __future__ import annotations

import hashlib
import io
import json
import os
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from textwrap import dedent

import pytest
import yaml

from magellon_sdk.archive.manifest import (
    PluginArchiveManifest,
    load_manifest_bytes,
    uuid7,
)
from magellon_sdk.cli.main import (
    ARCHIVE_EXT,
    CANONICAL_MANIFEST,
    LEGACY_MANIFEST,
    main,
)


# ---------------------------------------------------------------------------
# Fixture helpers
# ---------------------------------------------------------------------------

def _write_minimal_plugin(root: Path, *, plugin_id: str = "test-plugin") -> None:
    """Build a minimal plugin source tree under root."""
    manifest = dedent(f"""
    manifest_version: "1"
    plugin_id: {plugin_id}
    name: "Test Plugin"
    version: 0.1.0
    requires_sdk: ">=2.0,<3.0"
    category: fft
    install:
      - method: uv
        pyproject: pyproject.toml
        requires:
          - python: ">=3.11"
    """).strip()
    (root / CANONICAL_MANIFEST).write_text(manifest)
    (root / "README.md").write_text("# Test Plugin\n")
    (root / "pyproject.toml").write_text('[project]\nname = "test-plugin"\nversion = "0.1.0"\n')
    (root / "main.py").write_text("# entry point\nprint('hello')\n")
    (root / "plugin").mkdir()
    (root / "plugin" / "__init__.py").write_text("")
    (root / "plugin" / "logic.py").write_text("def run(): pass\n")


def _read_archive_manifest(archive_path: Path) -> PluginArchiveManifest:
    with zipfile.ZipFile(archive_path) as z:
        with z.open(CANONICAL_MANIFEST) as f:
            return load_manifest_bytes(f.read())


def _archive_filenames(archive_path: Path) -> set[str]:
    with zipfile.ZipFile(archive_path) as z:
        return set(z.namelist())


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------

def test_pack_produces_mpn_archive(tmp_path):
    src = tmp_path / "test_plugin"
    src.mkdir()
    _write_minimal_plugin(src)

    rc = main(["plugin", "pack", str(src), "--output", str(tmp_path / "out.mpn")])

    assert rc == 0
    out = tmp_path / "out.mpn"
    assert out.exists()
    assert out.stat().st_size > 0


def test_pack_writes_both_canonical_and_legacy_manifest(tmp_path):
    """Until the existing controller (plugins/controller.py) is updated
    to read manifest.yaml first, every packed archive must carry the
    legacy plugin.yaml alias too — otherwise v0 install endpoints
    can't read v1 archives."""
    src = tmp_path / "p"
    src.mkdir()
    _write_minimal_plugin(src)

    main(["plugin", "pack", str(src), "--output", str(tmp_path / "p.mpn")])

    names = _archive_filenames(tmp_path / "p.mpn")
    assert CANONICAL_MANIFEST in names
    assert LEGACY_MANIFEST in names


def test_pack_default_output_path(tmp_path, monkeypatch):
    """Default output is <plugin_id>-<version>.mpn alongside the
    source dir. Plugin authors expect one consistent naming so they
    can find their builds."""
    src = tmp_path / "p"
    src.mkdir()
    _write_minimal_plugin(src, plugin_id="my-plugin")

    rc = main(["plugin", "pack", str(src)])

    assert rc == 0
    expected = tmp_path / f"my-plugin-0.1.0{ARCHIVE_EXT}"
    assert expected.exists()


def test_pack_archive_round_trips_through_validator(tmp_path):
    """The ultimate compatibility test — pack output must validate
    when read back. If this fails, install controllers can't load
    what we just produced."""
    src = tmp_path / "p"
    src.mkdir()
    _write_minimal_plugin(src)
    archive = tmp_path / "p.mpn"

    main(["plugin", "pack", str(src), "--output", str(archive)])
    manifest = _read_archive_manifest(archive)

    assert manifest.plugin_id == "test-plugin"
    assert manifest.install[0].method == "uv"


# ---------------------------------------------------------------------------
# archive_id + timestamps stamping
# ---------------------------------------------------------------------------

def test_pack_generates_uuid_v7_archive_id(tmp_path):
    src = tmp_path / "p"
    src.mkdir()
    _write_minimal_plugin(src)
    archive = tmp_path / "p.mpn"

    main(["plugin", "pack", str(src), "--output", str(archive)])
    manifest = _read_archive_manifest(archive)

    assert manifest.archive_id.version == 7


def test_pack_assigns_fresh_archive_id_each_build(tmp_path):
    """Two pack runs of the same source produce different archive_ids
    — each build is a distinct artifact that the hub indexes
    separately. If we kept archive_id stable across builds, the hub
    couldn't distinguish ctffind4 v1.0 (built Tuesday) from
    ctffind4 v1.0 (built Friday with a different binary)."""
    src = tmp_path / "p"
    src.mkdir()
    _write_minimal_plugin(src)

    main(["plugin", "pack", str(src), "--output", str(tmp_path / "a.mpn")])
    main(["plugin", "pack", str(src), "--output", str(tmp_path / "b.mpn")])
    a = _read_archive_manifest(tmp_path / "a.mpn")
    b = _read_archive_manifest(tmp_path / "b.mpn")

    assert a.archive_id != b.archive_id


def test_pack_stamps_updated_to_now(tmp_path):
    src = tmp_path / "p"
    src.mkdir()
    _write_minimal_plugin(src)
    archive = tmp_path / "p.mpn"

    before = datetime.now(timezone.utc)
    main(["plugin", "pack", str(src), "--output", str(archive)])
    after = datetime.now(timezone.utc)

    manifest = _read_archive_manifest(archive)
    assert before <= manifest.updated <= after


# ---------------------------------------------------------------------------
# file_checksums
# ---------------------------------------------------------------------------

def test_pack_computes_checksums_for_every_file(tmp_path):
    """The install controller will verify each file against this
    table. A missing entry means the controller would silently
    accept a tampered file — the test pins that the table is
    complete."""
    src = tmp_path / "p"
    src.mkdir()
    _write_minimal_plugin(src)
    archive = tmp_path / "p.mpn"

    main(["plugin", "pack", str(src), "--output", str(archive)])
    manifest = _read_archive_manifest(archive)

    expected_files = {
        "README.md",
        "pyproject.toml",
        "main.py",
        "plugin/__init__.py",
        "plugin/logic.py",
    }
    assert set(manifest.file_checksums.keys()) == expected_files


def test_pack_checksum_table_excludes_manifest(tmp_path):
    """The manifest's own file_checksums dict can't contain its own
    hash (chicken-and-egg). The archive's overall integrity is
    asserted via the .mpn file's SHA256 in the hub's index.json."""
    src = tmp_path / "p"
    src.mkdir()
    _write_minimal_plugin(src)
    archive = tmp_path / "p.mpn"

    main(["plugin", "pack", str(src), "--output", str(archive)])
    manifest = _read_archive_manifest(archive)

    assert CANONICAL_MANIFEST not in manifest.file_checksums
    assert LEGACY_MANIFEST not in manifest.file_checksums


def test_pack_checksums_match_actual_file_content(tmp_path):
    """The whole point of file_checksums — verify they match the
    files in the archive. A regression that hashed the source files
    instead of the archive contents would still pass other tests."""
    src = tmp_path / "p"
    src.mkdir()
    _write_minimal_plugin(src)
    archive = tmp_path / "p.mpn"

    main(["plugin", "pack", str(src), "--output", str(archive)])
    manifest = _read_archive_manifest(archive)

    with zipfile.ZipFile(archive) as z:
        for arcname, expected in manifest.file_checksums.items():
            with z.open(arcname) as f:
                actual = hashlib.sha256(f.read()).hexdigest()
            assert actual == expected, f"checksum mismatch for {arcname}"


# ---------------------------------------------------------------------------
# Skipped files
# ---------------------------------------------------------------------------

def test_pack_skips_pycache_and_hidden_dirs(tmp_path):
    """Plugin authors leave __pycache__ + .venv lying around. A
    naive zip would balloon the archive size for no benefit."""
    src = tmp_path / "p"
    src.mkdir()
    _write_minimal_plugin(src)
    (src / "__pycache__").mkdir()
    (src / "__pycache__" / "junk.pyc").write_bytes(b"junk")
    (src / ".venv").mkdir()
    (src / ".venv" / "bin").mkdir()
    (src / ".venv" / "bin" / "python").write_bytes(b"fake-python")
    (src / ".hidden").write_text("secret")

    archive = tmp_path / "p.mpn"
    main(["plugin", "pack", str(src), "--output", str(archive)])
    names = _archive_filenames(archive)

    assert not any("__pycache__" in n for n in names)
    assert not any(".venv" in n for n in names)
    assert ".hidden" not in names
    assert not any(n.endswith(".pyc") for n in names)


def test_pack_skips_source_manifest_files(tmp_path):
    """The pack output writes a *regenerated* manifest with stamped
    archive_id + checksums. The source manifest must not be
    duplicated as a regular archive entry, otherwise we'd carry
    both the pre-stamp and post-stamp version (the loader picks one
    arbitrarily)."""
    src = tmp_path / "p"
    src.mkdir()
    _write_minimal_plugin(src)
    archive = tmp_path / "p.mpn"

    main(["plugin", "pack", str(src), "--output", str(archive)])

    # Each manifest filename appears exactly once — the regenerated copy.
    with zipfile.ZipFile(archive) as z:
        names = z.namelist()
    assert names.count(CANONICAL_MANIFEST) == 1
    assert names.count(LEGACY_MANIFEST) == 1


# ---------------------------------------------------------------------------
# Source-side input options (legacy + canonical)
# ---------------------------------------------------------------------------

def test_pack_reads_legacy_plugin_yaml_when_canonical_absent(tmp_path):
    """v0 plugin layouts have plugin.yaml not manifest.yaml. The
    pack CLI must handle them so existing plugins migrate without
    a rename step."""
    src = tmp_path / "old_plugin"
    src.mkdir()
    _write_minimal_plugin(src)
    (src / CANONICAL_MANIFEST).rename(src / LEGACY_MANIFEST)

    rc = main(["plugin", "pack", str(src), "--output", str(tmp_path / "old.mpn")])

    assert rc == 0
    manifest = _read_archive_manifest(tmp_path / "old.mpn")
    assert manifest.plugin_id == "test-plugin"


def test_pack_prefers_canonical_when_both_source_manifests_exist(tmp_path):
    """If a plugin in the middle of migration has both names, the
    canonical one wins. Otherwise a stale plugin.yaml could shadow
    a fresher manifest.yaml."""
    src = tmp_path / "p"
    src.mkdir()
    _write_minimal_plugin(src)
    # Stale plugin.yaml with a different plugin_id.
    (src / LEGACY_MANIFEST).write_text(
        (src / CANONICAL_MANIFEST).read_text().replace("test-plugin", "stale-plugin")
    )

    main(["plugin", "pack", str(src), "--output", str(tmp_path / "p.mpn")])
    manifest = _read_archive_manifest(tmp_path / "p.mpn")

    assert manifest.plugin_id == "test-plugin"


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------

def test_pack_refuses_existing_output_without_force(tmp_path, capsys):
    """Don't silently clobber the operator's previous build."""
    src = tmp_path / "p"
    src.mkdir()
    _write_minimal_plugin(src)
    archive = tmp_path / "p.mpn"
    archive.write_bytes(b"existing")

    rc = main(["plugin", "pack", str(src), "--output", str(archive)])

    assert rc == 1
    assert "already exists" in capsys.readouterr().err
    assert archive.read_bytes() == b"existing"


def test_pack_force_overwrites_existing_output(tmp_path):
    src = tmp_path / "p"
    src.mkdir()
    _write_minimal_plugin(src)
    archive = tmp_path / "p.mpn"
    archive.write_bytes(b"x" * 50)

    rc = main(["plugin", "pack", str(src), "--output", str(archive), "--force"])

    assert rc == 0
    assert archive.stat().st_size > 50  # actually the new archive


def test_pack_rejects_invalid_manifest(tmp_path, capsys):
    src = tmp_path / "p"
    src.mkdir()
    _write_minimal_plugin(src)
    # Corrupt the manifest.
    (src / CANONICAL_MANIFEST).write_text("not: [valid: yaml")

    rc = main(["plugin", "pack", str(src), "--output", str(tmp_path / "p.mpn")])

    assert rc == 1
    assert "error" in capsys.readouterr().err.lower()
    assert not (tmp_path / "p.mpn").exists()


def test_pack_rejects_directory_with_no_manifest(tmp_path, capsys):
    src = tmp_path / "empty"
    src.mkdir()
    (src / "README.md").write_text("# nothing to see")

    rc = main(["plugin", "pack", str(src), "--output", str(tmp_path / "x.mpn")])

    assert rc == 1
    err = capsys.readouterr().err
    assert CANONICAL_MANIFEST in err or LEGACY_MANIFEST in err
