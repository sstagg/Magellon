"""CLI surface tests.

Pins the public subcommand surface — plugin authors learn these
names from docs; renames here become breaking changes downstream.
The CLI ships ``magellon-sdk plugin {init, pack, validate}`` today;
hub commands land later under their own group.
"""
from __future__ import annotations

import pytest

from magellon_sdk import __version__
from magellon_sdk.cli.main import build_parser, main


def test_version_flag(capsys):
    """``--version`` prints the SDK version and exits 0."""
    with pytest.raises(SystemExit) as exc:
        main(["--version"])
    assert exc.value.code == 0
    assert f"magellon-sdk {__version__}" in capsys.readouterr().out


def test_no_args_prints_help_and_exits_zero(capsys):
    """Bare ``magellon-sdk`` prints help — the operator may be
    discovering the tool and shouldn't be punished with an error."""
    rc = main([])
    assert rc == 0
    out = capsys.readouterr().out
    assert "plugin" in out  # the subcommand name


def test_plugin_group_subcommands_pinned():
    """``plugin {init, pack, validate}`` is the surface plugin authors
    write code against. Adding a new subcommand is fine; renaming or
    removing one breaks every tutorial that mentions it."""
    parser = build_parser()
    # Find the top-level subparsers action, then drill into the
    # plugin group's subparsers.
    top = next(a for a in parser._actions if getattr(a, "choices", None) is not None)
    plugin_parser = top.choices["plugin"]
    plugin_sub = next(
        a for a in plugin_parser._actions if getattr(a, "choices", None) is not None
    )
    assert {"init", "pack", "validate", "lint", "scaffold", "test"} <= set(plugin_sub.choices.keys())


def test_plugin_init_no_name_errors(capsys):
    """Missing positional must print the parser error, not pretend
    init succeeded."""
    with pytest.raises(SystemExit):
        main(["plugin", "init"])


def test_plugin_pack_no_dir_errors(capsys):
    with pytest.raises(SystemExit):
        main(["plugin", "pack"])


def test_plugin_validate_missing_path_errors(capsys, tmp_path):
    """``validate`` on a nonexistent path returns 1 with a clear
    error, NOT a stack trace and NOT silent success."""
    rc = main(["plugin", "validate", str(tmp_path / "does-not-exist")])
    assert rc == 1
    assert "not found" in capsys.readouterr().err.lower() or \
           "invalid" in capsys.readouterr().err.lower()


# ---------------------------------------------------------------------------
# lint (Wave 6 Phase 22)
# ---------------------------------------------------------------------------


def _write_minimal_plugin_dir(target, *, plugin_id="testp", version="1.0.0"):
    """Write the minimum valid plugin layout: manifest.yaml + a stub
    Dockerfile so the docker install spec resolves cleanly."""
    target.mkdir(parents=True, exist_ok=True)
    (target / "manifest.yaml").write_text(
        f"""manifest_version: "1.1"
plugin_id: {plugin_id}
archive_id: 00000000-0000-7000-8000-000000000000
name: Test
version: {version}
requires_sdk: ">=2.0,<3.0"
author: Test
license: MIT
description: A test plugin
category: fft
backend_id: {plugin_id}
tags: [test]
install:
  - method: docker
    dockerfile: Dockerfile
""",
        encoding="utf-8",
    )
    (target / "Dockerfile").write_text("FROM python:3.12\n", encoding="utf-8")


def test_plugin_lint_happy_path_returns_zero(tmp_path, capsys):
    _write_minimal_plugin_dir(tmp_path / "p")
    rc = main(["plugin", "lint", str(tmp_path / "p")])
    assert rc == 0
    out = capsys.readouterr().out
    assert "OK" in out


def test_plugin_lint_missing_manifest_returns_error(tmp_path, capsys):
    empty = tmp_path / "empty"
    empty.mkdir()
    rc = main(["plugin", "lint", str(empty)])
    assert rc == 1
    err = capsys.readouterr().err
    assert "manifest" in err.lower()


def test_plugin_lint_missing_dockerfile_is_error(tmp_path, capsys):
    """Docker install spec references Dockerfile but the file is
    missing — operator wouldn't be able to install."""
    target = tmp_path / "p"
    _write_minimal_plugin_dir(target)
    (target / "Dockerfile").unlink()  # remove the file the manifest names

    rc = main(["plugin", "lint", str(target)])
    assert rc == 1
    err = capsys.readouterr().err
    assert "Dockerfile" in err


def test_plugin_lint_warns_on_low_health_check_timeout(tmp_path, capsys):
    target = tmp_path / "p"
    _write_minimal_plugin_dir(target)
    (target / "manifest.yaml").write_text(
        """manifest_version: "1.1"
plugin_id: testp
archive_id: 00000000-0000-7000-8000-000000000000
name: Test
version: 1.0.0
requires_sdk: ">=2.0,<3.0"
author: Test
license: MIT
description: Test
category: fft
backend_id: testp
tags: [test]
health_check:
  timeout_seconds: 1
install:
  - method: docker
    dockerfile: Dockerfile
""",
        encoding="utf-8",
    )

    rc = main(["plugin", "lint", str(target)])
    # Default mode: warnings don't fail the build.
    assert rc == 0
    err = capsys.readouterr().err
    assert "health_check" in err.lower()


def test_plugin_lint_strict_treats_warnings_as_failures(tmp_path, capsys):
    """The CI gate flag — strict mode flips warnings to exit code 1
    so unmaintained plugins don't ship without action."""
    target = tmp_path / "p"
    _write_minimal_plugin_dir(target)
    (target / "manifest.yaml").write_text(
        """manifest_version: "1.1"
plugin_id: testp
archive_id: 00000000-0000-7000-8000-000000000000
name: Test
version: 1.0.0
requires_sdk: ">=2.0,<3.0"
author: Test
license: MIT
description: Test
category: fft
backend_id: testp
tags: [test]
health_check:
  timeout_seconds: 1
install:
  - method: docker
    dockerfile: Dockerfile
""",
        encoding="utf-8",
    )

    rc = main(["plugin", "lint", str(target), "--strict"])
    assert rc == 1


def test_plugin_lint_warns_on_stale_bundled_sdk_wheel(tmp_path, capsys):
    """A bundled SDK wheel older than the CLI's SDK version is the
    #1 install-time DX trap (see project_plugin_sdk_wheel_drift
    memory). Lint must surface it."""
    target = tmp_path / "p"
    _write_minimal_plugin_dir(target)
    wheels = target / "wheels"
    wheels.mkdir()
    # Stale wheel — version "0.1.0" is far older than the CLI's SDK.
    (wheels / "magellon_sdk-0.1.0-py3-none-any.whl").write_bytes(b"")

    rc = main(["plugin", "lint", str(target)])
    assert rc == 0
    err = capsys.readouterr().err
    assert "wheel" in err.lower()


def test_lint_plugin_dir_pure_function_returns_tuples(tmp_path):
    """The pure-function entry point lint_plugin_dir returns
    (severity, message) tuples — testable without capsys parsing."""
    from magellon_sdk.cli.main import (
        LINT_ERROR, LINT_INFO, LINT_WARN, lint_plugin_dir,
    )
    target = tmp_path / "p"
    _write_minimal_plugin_dir(target)

    issues = lint_plugin_dir(target)
    severities = {sev for sev, _ in issues}
    # Happy path: no errors. Tags + author etc. are populated, so no
    # info messages either.
    assert LINT_ERROR not in severities


# ---------------------------------------------------------------------------
# scaffold (Wave 6 Phase 23)
# ---------------------------------------------------------------------------


def test_plugin_scaffold_creates_full_skeleton(tmp_path, capsys):
    target = tmp_path / "my-plugin"
    rc = main([
        "plugin", "scaffold", str(target),
        "--category", "fft", "--plugin-id", "my-plugin",
    ])
    assert rc == 0, capsys.readouterr().err
    # Every templated file landed.
    assert (target / "manifest.yaml").is_file()
    assert (target / "main.py").is_file()
    assert (target / "plugin" / "plugin.py").is_file()
    assert (target / "plugin" / "compute.py").is_file()
    assert (target / "Dockerfile").is_file()
    assert (target / "pyproject.toml").is_file()
    assert (target / "requirements.txt").is_file()
    assert (target / "tests" / "test_compute.py").is_file()
    assert (target / "README.md").is_file()
    assert (target / ".gitignore").is_file()


def test_plugin_scaffold_output_is_lint_clean(tmp_path):
    """The most important property: a freshly scaffolded plugin must
    pass ``plugin lint`` without errors. Future authors run scaffold
    → lint as their first sanity check; if scaffold ships errors,
    every onboarding starts on the wrong foot."""
    from magellon_sdk.cli.main import LINT_ERROR, lint_plugin_dir
    target = tmp_path / "fresh"
    rc = main([
        "plugin", "scaffold", str(target),
        "--category", "fft", "--plugin-id", "fresh",
    ])
    assert rc == 0
    issues = lint_plugin_dir(target)
    errors = [m for sev, m in issues if sev == LINT_ERROR]
    assert errors == [], f"scaffold produced lint errors: {errors}"


def test_plugin_scaffold_output_is_pack_clean(tmp_path, capsys):
    """The freshly scaffolded plugin must also pack cleanly. Pack
    validates the manifest + walks the file tree; if scaffold misses
    a required field, pack will surface it here."""
    target = tmp_path / "packable"
    rc = main([
        "plugin", "scaffold", str(target),
        "--category", "fft", "--plugin-id", "packable",
    ])
    assert rc == 0
    out_archive = tmp_path / "packable-out.mpn"
    rc = main([
        "plugin", "pack", str(target),
        "--output", str(out_archive), "--force",
    ])
    assert rc == 0, capsys.readouterr().err
    assert out_archive.is_file()


def test_plugin_scaffold_refuses_nonempty_target(tmp_path, capsys):
    target = tmp_path / "occupied"
    target.mkdir()
    (target / "existing.txt").write_text("hi")
    rc = main([
        "plugin", "scaffold", str(target),
        "--category", "fft",
    ])
    assert rc == 1
    assert "exists" in capsys.readouterr().err.lower()


def test_plugin_scaffold_class_name_derivation():
    """plugin_id ``ctf-plugin`` → class name ``Ctf`` so the generated
    code reads as ``CtfPlugin`` after the template's Plugin suffix."""
    from magellon_sdk.cli.main import _class_name_from_plugin_id
    assert _class_name_from_plugin_id("ctf") == "Ctf"
    assert _class_name_from_plugin_id("ctf-plugin") == "Ctf"
    assert _class_name_from_plugin_id("magellon_fft_plugin") == "MagellonFft"
    assert _class_name_from_plugin_id("two-d-classifier") == "TwoDClassifier"


# ---------------------------------------------------------------------------
# test (Wave 6 Phase 24)
# ---------------------------------------------------------------------------


def test_plugin_test_runs_lint_first(tmp_path, capsys):
    """``plugin test`` is lint-then-pytest. A lint failure should
    short-circuit before pytest runs (no point testing a broken
    manifest)."""
    target = tmp_path / "broken"
    target.mkdir()
    # Empty dir → lint fails on missing manifest.
    rc = main(["plugin", "test", str(target)])
    assert rc == 1
    assert "manifest" in capsys.readouterr().err.lower()


def test_plugin_test_skips_pytest_when_no_tests_dir(tmp_path, capsys):
    """A plugin without a tests/ directory is not an error — lint
    suffices. Pytest run is skipped with a notice."""
    target = tmp_path / "p"
    _write_minimal_plugin_dir(target)
    rc = main(["plugin", "test", str(target)])
    assert rc == 0
    out = capsys.readouterr().out
    assert "no tests" in out.lower() or "skipping pytest" in out.lower()


def test_plugin_test_invokes_pytest_when_tests_present(tmp_path, capsys):
    """When tests/ exists, ``plugin test`` shells out to pytest. We
    can't trivially intercept subprocess.run from this test, but we
    can write a passing pytest test and verify the overall exit code
    is 0 (which requires the subprocess to have run + returned 0)."""
    target = tmp_path / "p"
    _write_minimal_plugin_dir(target)
    tests_dir = target / "tests"
    tests_dir.mkdir()
    (tests_dir / "test_trivial.py").write_text(
        "def test_trivial():\n    assert 1 == 1\n", encoding="utf-8",
    )

    rc = main(["plugin", "test", str(target)])
    assert rc == 0
