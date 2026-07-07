"""Install-flow logic shared by the lifecycle routes.

Archive parsing / SDK-compat enforcement / docker-run-from-manifest —
the pieces both the raw-archive upload path and the catalog-install
path share once a validated manifest is in hand.
"""
from __future__ import annotations

import io
import zipfile
from typing import Any, Dict

from fastapi import HTTPException

from core.installed_plugins import get_installed_registry
from core.plugin_docker_runner import (
    VolumeMount,
    get_runner as get_docker_runner,
)
from magellon_sdk import __version__ as sdk_version
from magellon_sdk.archive import (
    SchemaVersionError,
    SdkCompatError,
    check_sdk_compat,
    load_manifest_bytes,
)


def _ensure_docker() -> None:
    """Fail fast with 503 when the docker CLI / daemon is unreachable.

    Called from every /installed endpoint before we touch the runner —
    better to tell the client "Docker unavailable" than surface a
    FileNotFoundError as a 500.
    """
    if not get_docker_runner().ping():
        raise HTTPException(
            status_code=503,
            detail="Docker is not available on this CoreService host.",
        )


def _parse_archive_bytes(raw: bytes):
    """Extract + validate plugin.yaml from archive bytes. Raises the
    right HTTPExceptions so callers can just propagate."""
    try:
        with zipfile.ZipFile(io.BytesIO(raw)) as z:
            try:
                with z.open("plugin.yaml") as f:
                    manifest_bytes = f.read()
            except KeyError:
                raise HTTPException(
                    status_code=422,
                    detail="archive has no top-level plugin.yaml — "
                           "pack with `magellon-sdk plugin pack <dir>`",
                )
    except zipfile.BadZipFile:
        raise HTTPException(status_code=422, detail="archive is not a valid zip file")

    try:
        return load_manifest_bytes(manifest_bytes)
    except SchemaVersionError as exc:
        raise HTTPException(status_code=422, detail=f"unsupported schema_version: {exc}")
    except Exception as exc:  # noqa: BLE001 — surface pydantic + yaml errors as-is
        raise HTTPException(status_code=422, detail=f"invalid plugin.yaml: {exc}")


def _enforce_sdk_compat(manifest) -> None:
    try:
        check_sdk_compat(manifest.sdk_compat, sdk_version)
    except SdkCompatError as exc:
        # Hard-fail: installing a plugin whose SDK pin excludes us
        # risks field-shape drift at runtime. Better the operator
        # rebuilds their plugin against a compatible SDK.
        raise HTTPException(
            status_code=409,
            detail=f"plugin incompatible with this CoreService (SDK {sdk_version}): {exc}",
        )


def _install_from_manifest(manifest) -> Dict[str, Any]:
    """Docker-run the image declared in ``manifest`` with its defaults.

    Shared by both the raw-archive upload path and the catalog-install
    path — the "spawn the container + record the install" behaviour
    is identical once we have a validated manifest in hand.
    """
    _ensure_docker()
    runner = get_docker_runner()
    volumes = [
        VolumeMount(v.host, v.container, v.read_only)
        for v in manifest.install_defaults.volumes
    ]
    entry = runner.run_image(
        image_ref=manifest.image.ref,
        env=dict(manifest.install_defaults.env),
        volumes=volumes,
        network=manifest.install_defaults.network,
    )
    if entry.state == "failed":
        get_installed_registry().add(entry)
        raise HTTPException(
            status_code=502,
            detail=f"docker run failed: {entry.error or 'unknown error'}",
        )
    get_installed_registry().add(entry)

    response = entry.to_dict()
    response["archive"] = {
        "plugin_id": manifest.plugin_id,
        "name": manifest.name,
        "version": manifest.version,
        "category": manifest.category,
    }
    return response
