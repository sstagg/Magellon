"""P8 regression: Consul has been removed from CoreService.

These pin the *absence* of Consul. They're cheap insurance against a
later commit silently re-introducing the python-consul dependency or
re-adding the consul_settings model — both of which were a long-time
source of "is the cluster registered?" boot races we want to stay rid
of now that broker-based discovery (P6) and config (P7) cover the
same ground.
"""
from __future__ import annotations

import importlib


def test_app_settings_no_longer_carries_consul_block():
    """The yaml shouldn't even have a knob to set — drop the field
    from AppSettings so a stale consul_settings: block in a config
    file is silently ignored (pydantic default), and so other code
    can't accidentally read consul host/port from app_settings."""
    from models.pydantic_models_settings import AppSettings

    s = AppSettings()
    assert not hasattr(s, "consul_settings"), (
        "AppSettings still exposes consul_settings — P8 was supposed to drop it."
    )
    assert "consul_settings" not in AppSettings.model_fields


def test_consul_settings_class_is_gone():
    """The class itself should be unimportable so a future grep for
    'ConsulSettings' returns nothing reachable."""
    import models.pydantic_models_settings as m

    assert not hasattr(m, "ConsulSettings")


def test_no_project_source_imports_consul():
    """python-consul may still linger in some local virtualenvs from
    before the cleanup — but no tracked source file should import it.
    A grep over the CoreService source tree is the source-of-truth
    check; the test fails the moment somebody re-adds an `import consul`
    or `from consul`."""
    import re
    from pathlib import Path

    root = Path(__file__).resolve().parent.parent
    pat = re.compile(r"^\s*(import\s+consul|from\s+consul\b)", re.MULTILINE)
    skip_dirs = {"venv", ".venv", "site-packages", "__pycache__", ".git"}
    offenders = []
    for py in root.rglob("*.py"):
        # Skip vendored deps + this test file (it mentions consul on purpose).
        if any(part in skip_dirs for part in py.parts):
            continue
        if py.name == "test_consul_removed.py":
            continue
        if pat.search(py.read_text(encoding="utf-8", errors="replace")):
            offenders.append(str(py.relative_to(root)))
    assert not offenders, f"unexpected `import consul` in: {offenders}"


def test_consul_not_in_requirements():
    """python-consul shouldn't be pinned in requirements.txt anymore."""
    from pathlib import Path

    req = Path(__file__).resolve().parent.parent / "requirements.txt"
    text = req.read_text(encoding="utf-8")
    # Match a bare line, not a comment that mentions it
    for line in text.splitlines():
        stripped = line.split("#", 1)[0].strip().lower()
        assert "python-consul" not in stripped, (
            f"requirements.txt still pins python-consul: {line!r}"
        )


def test_config_module_does_not_import_consul():
    """`config.py` used to do `import consul` at module top — make
    sure that import has been removed, so a missing python-consul
    install can't break the whole CoreService boot."""
    import config
    importlib.reload(config)  # forces the import path to re-run

    # The function exists; it just no longer reads from a consul KV.
    assert callable(config.fetch_image_root_dir)
    # And the legacy globals are gone.
    assert not hasattr(config, "consul_client")
    assert not hasattr(config, "consul_config")
