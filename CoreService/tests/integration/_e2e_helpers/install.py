"""Install/uninstall/lifecycle helpers for the e2e wave.

Wraps the admin endpoints under ``/admin/plugins/`` so individual tests
stay narrative. Each helper raises ``AssertionError`` with a useful
message on protocol-level failure so pytest's diff output stays
actionable.
"""
from __future__ import annotations

import time
from pathlib import Path
from typing import Any, Dict, Optional

import httpx


def install_plugin_from_archive(
    client: httpx.Client,
    archive_path: Path,
    *,
    install_method: Optional[str] = None,
    timeout: float = 120.0,
) -> Dict[str, Any]:
    """POST /admin/plugins/install with the archive bytes.

    ``install_method`` pins the manager to a specific method (``uv`` /
    ``docker``); ``None`` lets the manager auto-pick. Returns the parsed
    InstallResponse body on 201, asserts otherwise.
    """
    with archive_path.open("rb") as fh:
        files = {
            "file": (archive_path.name, fh, "application/octet-stream"),
        }
        data = {"install_method": install_method} if install_method else None
        resp = client.post(
            "/admin/plugins/install", files=files, data=data, timeout=timeout,
        )
    assert resp.status_code == 201, (
        f"install failed: {resp.status_code} {resp.text[:400]}"
    )
    body = resp.json()
    assert body.get("success") is True, body
    return body


def uninstall_plugin(
    client: httpx.Client, plugin_id: str, *, timeout: float = 60.0,
) -> Dict[str, Any]:
    """DELETE /admin/plugins/{plugin_id}. Returns the parsed
    UninstallResponse; asserts a 2xx."""
    resp = client.delete(
        f"/admin/plugins/{plugin_id}", timeout=timeout,
    )
    assert 200 <= resp.status_code < 300, (
        f"uninstall failed: {resp.status_code} {resp.text[:400]}"
    )
    return resp.json()


def wait_for_lifecycle_status(
    client: httpx.Client,
    plugin_id: str,
    target_status: str,
    *,
    timeout: float = 30.0,
    poll_interval: float = 0.5,
) -> Dict[str, Any]:
    """Poll GET /admin/plugins/{id}/status until ``status`` matches
    ``target_status`` ("running" / "stopped" / "paused" / "unknown").

    Returns the final status body. Asserts (with the last-seen payload)
    if the target isn't reached within ``timeout``.
    """
    deadline = time.monotonic() + timeout
    last_body: Optional[Dict[str, Any]] = None
    while time.monotonic() < deadline:
        resp = client.get(
            f"/admin/plugins/{plugin_id}/status", timeout=5.0,
        )
        if resp.status_code == 200:
            last_body = resp.json()
            if last_body.get("status") == target_status:
                return last_body
        time.sleep(poll_interval)
    raise AssertionError(
        f"plugin {plugin_id!r} did not reach status={target_status!r} "
        f"within {timeout}s. Last body: {last_body!r}"
    )


def wait_for_plugin_announce(
    client: httpx.Client,
    plugin_id: str,
    *,
    timeout: float = 30.0,
    poll_interval: float = 0.5,
) -> Dict[str, Any]:
    """Poll GET /plugins/{id}/status until the plugin's Live condition
    is True. Returns the conditions array.

    Distinct from :func:`wait_for_lifecycle_status` — that one checks
    the supervisor/container state via /admin/plugins/*; this one
    checks the announce-based liveness registry, which is what the
    React UI reads.
    """
    deadline = time.monotonic() + timeout
    last_conditions: Optional[list] = None
    while time.monotonic() < deadline:
        resp = client.get(
            f"/plugins/{plugin_id}/status", timeout=5.0,
        )
        if resp.status_code == 200:
            last_conditions = resp.json()
            live = next(
                (c for c in last_conditions if c.get("type") == "Live"), None,
            )
            if live and live.get("status") == "True":
                return last_conditions
        time.sleep(poll_interval)
    raise AssertionError(
        f"plugin {plugin_id!r} did not announce Live=True within "
        f"{timeout}s. Last conditions: {last_conditions!r}"
    )
