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
    assert {"init", "pack", "validate"} <= set(plugin_sub.choices.keys())


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
