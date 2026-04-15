"""CLI skeleton tests.

Pin the subcommand surface — plugin authors see these names. Renames
here become documentation breakage downstream.
"""
from __future__ import annotations

import pytest

from magellon_sdk.cli.main import build_parser, main


def test_version_flag(capsys):
    with pytest.raises(SystemExit) as exc:
        main(["--version"])
    assert exc.value.code == 0
    captured = capsys.readouterr()
    assert "magellon-plugin" in captured.out


def test_no_args_prints_help(capsys):
    rc = main([])
    assert rc == 0
    assert "Build, test, and publish" in capsys.readouterr().out


@pytest.mark.parametrize("cmd", ["new", "test", "package", "publish", "worker"])
def test_stub_subcommands_exit_nonzero(cmd, capsys):
    """Until they're implemented, subcommands must not silently succeed."""
    rc = main([cmd])
    assert rc == 2
    assert "not yet implemented" in capsys.readouterr().err


def test_parser_surface_pinned():
    """The public subcommand names the docs reference must not change."""
    parser = build_parser()
    subparsers_action = next(
        a for a in parser._actions if getattr(a, "choices", None) is not None
    )
    assert set(subparsers_action.choices.keys()) == {
        "new",
        "test",
        "package",
        "publish",
        "worker",
    }
