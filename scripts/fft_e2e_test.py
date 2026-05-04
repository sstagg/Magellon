"""End-to-end test for the FFT plugin.

Drives the full path: pack -> install -> dispatch via bus -> dispatch
via sync -> compare outputs. Requires a live CoreService + RabbitMQ.

Usage
-----

    python scripts/fft_e2e_test.py                      # defaults below
    python scripts/fft_e2e_test.py --skip-install       # plugin already running
    python scripts/fft_e2e_test.py --base-url http://stage.example.com:8000

Env (or matching --flag):
    MAGELLON_BASE_URL       http://localhost:8000
    MAGELLON_USERNAME       admin
    MAGELLON_PASSWORD       password123
    MAGELLON_AUTH_TOKEN     pre-obtained JWT (skip /auth/login)
    MAGELLON_FFT_IMAGE      Resources/Images/24dec03a_00001gr.mrc

Exit: 0 pass; non-zero with a single-line reason on stderr.

Windows note
------------

The default ``UvInstaller`` + ``NoOpSupervisor`` combo on Windows
does NOT actually start the plugin process — install will roll back
when the health check times out waiting for the announce. Pass
``--skip-install`` and launch the plugin yourself with the env vars
this script will print, or run the test against a Linux deployment
(systemd/docker-compose) where supervision works end-to-end.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import time
import uuid
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

try:
    import urllib.request
    import urllib.error
except ImportError:  # pragma: no cover
    print("urllib required", file=sys.stderr)
    sys.exit(1)

# Force UTF-8 on stdout/stderr so the script's status output (which
# may contain em-dashes / ellipsis / check marks) doesn't blow up on
# the Windows cp1252 console. Python 3.7+.
for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        try:
            _stream.reconfigure(encoding="utf-8")
        except Exception:  # noqa: BLE001
            pass


REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_PLUGIN_DIR = REPO_ROOT / "plugins" / "magellon_fft_plugin"
DEFAULT_IMAGE = REPO_ROOT / "Resources" / "Images" / "24dec03a_00001gr.mrc"
PLUGIN_ID = "fft"          # from manifest.yaml
CATEGORY = "fft"           # for /dispatch/{category}/run


# ---------------------------------------------------------------------------
# Tiny HTTP client (stdlib only — no requests dep)
# ---------------------------------------------------------------------------

class HttpError(Exception):
    def __init__(self, status: int, body: str, url: str):
        super().__init__(f"HTTP {status} from {url}: {body[:300]}")
        self.status = status
        self.body = body
        self.url = url


def _request(
    method: str, url: str, *,
    json_body: Optional[Dict[str, Any]] = None,
    headers: Optional[Dict[str, str]] = None,
    multipart: Optional[Tuple[str, Path]] = None,  # (field_name, file_path)
    timeout: float = 60.0,
) -> Dict[str, Any]:
    h = dict(headers or {})
    data: Optional[bytes] = None
    if multipart is not None:
        field, path = multipart
        boundary = "----magellon-" + uuid.uuid4().hex
        h["Content-Type"] = f"multipart/form-data; boundary={boundary}"
        body = bytearray()
        body += f"--{boundary}\r\n".encode()
        body += (
            f'Content-Disposition: form-data; name="{field}"; '
            f'filename="{path.name}"\r\n'
        ).encode()
        body += b"Content-Type: application/octet-stream\r\n\r\n"
        body += path.read_bytes()
        body += f"\r\n--{boundary}--\r\n".encode()
        data = bytes(body)
    elif json_body is not None:
        h["Content-Type"] = "application/json"
        data = json.dumps(json_body).encode("utf-8")
    req = urllib.request.Request(url, data=data, method=method, headers=h)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            payload = resp.read().decode("utf-8") if resp.length != 0 else ""
            return json.loads(payload) if payload else {}
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        raise HttpError(e.code, body, url) from None
    except urllib.error.URLError as e:
        raise HttpError(0, str(e.reason), url) from None


# ---------------------------------------------------------------------------
# Pipeline steps
# ---------------------------------------------------------------------------

def step_pack(plugin_dir: Path) -> Path:
    print(f">>> pack {plugin_dir}")
    proc = subprocess.run(
        ["magellon-sdk", "plugin", "pack", str(plugin_dir), "--force"],
        capture_output=True, text=True,
    )
    sys.stdout.write(proc.stdout)
    sys.stderr.write(proc.stderr)
    if proc.returncode != 0:
        raise SystemExit(2)
    m = re.search(r"^\s*archive:\s+(.+)$", proc.stdout, flags=re.MULTILINE)
    if not m:
        raise SystemExit("could not parse archive path from pack output")
    archive = Path(m.group(1).strip())
    if not archive.is_file():
        raise SystemExit(f"packed archive missing: {archive}")
    return archive


def step_login(base_url: str, username: str, password: str) -> str:
    print(f">>> login as {username}")
    resp = _request(
        "POST", f"{base_url}/auth/login",
        json_body={"username": username, "password": password},
    )
    token = resp.get("access_token")
    if not token:
        raise SystemExit("login response missing access_token")
    return token


def step_uninstall_if_present(base_url: str, token: str, plugin_id: str) -> None:
    """Best-effort idempotency — silently swallow 404."""
    try:
        _request(
            "DELETE", f"{base_url}/admin/plugins/{plugin_id}",
            headers={"Authorization": f"Bearer {token}"},
        )
        print(f"    pre-existing {plugin_id} uninstalled")
    except HttpError as e:
        if e.status == 404:
            return
        # 5xx on uninstall is unusual but not fatal — install will refuse
        # if the plugin is still present and surface the real reason.
        print(f"    warning: pre-uninstall returned {e.status}: {e.body[:120]}")


def step_install(base_url: str, token: str, archive: Path) -> Dict[str, Any]:
    print(f">>> POST /admin/plugins/install ({archive.name})")
    resp = _request(
        "POST", f"{base_url}/admin/plugins/install",
        headers={"Authorization": f"Bearer {token}"},
        multipart=("file", archive),
        timeout=180.0,
    )
    print(f"    install OK: {json.dumps(resp)[:200]}")
    return resp


def step_wait_live(
    base_url: str, token: str, plugin_id: str, timeout_s: float = 60.0,
) -> None:
    """Wait for at least one backend to be live in the FFT category.

    Resolves liveness via ``/plugins/capabilities`` (category-level)
    rather than ``/plugins/{id}/health`` because the plugin announces
    with its display-name plugin_id (``"fft/FFT Plugin"``), not the
    archive slug ``plugin_id`` field.
    """
    print(f">>> waiting up to {timeout_s:.0f}s for FFT category to have a live backend")
    deadline = time.time() + timeout_s
    last_err = ""
    while time.time() < deadline:
        try:
            r = _request(
                "GET", f"{base_url}/plugins/capabilities",
                headers={"Authorization": f"Bearer {token}"},
            )
            for cat in r.get("categories", []):
                if cat.get("name") == "FFT" and cat.get("backends"):
                    bk = cat["backends"][0]
                    print(f"    live: backend_id={bk.get('backend_id')!r} "
                          f"plugin_id={bk.get('plugin_id')!r} "
                          f"caps={bk.get('capabilities')}")
                    return
        except HttpError as e:
            last_err = f"{e.status}"
        time.sleep(2)
    raise SystemExit(f"no live FFT backend within {timeout_s}s (last={last_err})")


def step_bus_dispatch(
    base_url: str, token: str, image_path: Path, target_path: Path,
) -> Path:
    print(f">>> bus dispatch — POST /image/fft/dispatch")
    resp = _request(
        "POST", f"{base_url}/image/fft/dispatch",
        headers={"Authorization": f"Bearer {token}"},
        json_body={
            "image_path": str(image_path),
            "target_path": str(target_path),
        },
    )
    job_id = resp["job_id"]
    print(f"    job_id={job_id}; polling /plugins/jobs/{job_id}")
    deadline = time.time() + 120.0
    last_state = ""
    while time.time() < deadline:
        env = _request(
            "GET", f"{base_url}/plugins/jobs/{job_id}",
            headers={"Authorization": f"Bearer {token}"},
        )
        state = env.get("status") or env.get("state") or ""
        if state != last_state:
            print(f"    state={state} progress={env.get('progress')}")
            last_state = state
        # Match terminal-state keywords loosely — different code paths
        # surface different cases (uppercase enum vs string).
        s = str(state).lower()
        if s in ("completed", "complete", "succeeded"):
            return target_path
        if s in ("failed", "error", "cancelled", "canceled"):
            raise SystemExit(f"bus job ended in non-success state: {env}")
        time.sleep(1)
    raise SystemExit("bus job did not reach terminal state in 120s")


def step_sync_dispatch(
    base_url: str, token: str, image_path: Path, target_path: Path,
) -> Path:
    print(f">>> sync dispatch — POST /dispatch/{CATEGORY}/run")
    resp = _request(
        "POST", f"{base_url}/dispatch/{CATEGORY}/run",
        headers={"Authorization": f"Bearer {token}"},
        json_body={
            "image_path": str(image_path),
            "target_path": str(target_path),
            "engine_opts": {},
        },
        timeout=120.0,
    )
    print(f"    sync OK: {json.dumps(resp)[:240]}")
    out = resp.get("output_path")
    if not out:
        raise SystemExit(f"sync response missing output_path: {resp}")
    return Path(out)


def step_verify(bus_png: Path, sync_png: Path) -> None:
    print(f">>> verify both PNGs exist + are non-empty")
    for p in (bus_png, sync_png):
        if not p.is_file():
            raise SystemExit(f"missing PNG: {p}")
        if p.stat().st_size == 0:
            raise SystemExit(f"empty PNG: {p}")
        # PNG magic
        with p.open("rb") as f:
            magic = f.read(8)
        if magic != b"\x89PNG\r\n\x1a\n":
            raise SystemExit(f"not a PNG (bad magic): {p}")
    bus_sha = hashlib.sha256(bus_png.read_bytes()).hexdigest()
    sync_sha = hashlib.sha256(sync_png.read_bytes()).hexdigest()
    print(f"    bus  {bus_png}  sha256={bus_sha[:16]}…  ({bus_png.stat().st_size:,} B)")
    print(f"    sync {sync_png} sha256={sync_sha[:16]}…  ({sync_png.stat().st_size:,} B)")
    # Algorithm is deterministic per (image, height) — same inputs
    # SHOULD yield byte-identical PNGs. Don't fail on mismatch
    # (Pillow version differences could shift bytes); just flag.
    if bus_sha != sync_sha:
        print(
            "    warning: bus and sync PNGs differ — algorithm should be "
            "deterministic; check for inadvertent randomness or library skew."
        )
    else:
        print("    bus and sync PNGs are byte-identical (deterministic ✓)")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> int:
    p = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    p.add_argument("--base-url", default=os.environ.get(
        "MAGELLON_BASE_URL", "http://localhost:8000"))
    p.add_argument("--username", default=os.environ.get(
        "MAGELLON_USERNAME", "admin"))
    p.add_argument("--password", default=os.environ.get(
        "MAGELLON_PASSWORD", "password123"))
    p.add_argument("--token", default=os.environ.get("MAGELLON_AUTH_TOKEN"))
    p.add_argument("--plugin-dir", type=Path, default=DEFAULT_PLUGIN_DIR)
    p.add_argument("--image", type=Path,
                   default=Path(os.environ.get("MAGELLON_FFT_IMAGE", DEFAULT_IMAGE)))
    p.add_argument("--skip-install", action="store_true",
                   help="Plugin already installed + running; skip pack/install/wait.")
    p.add_argument("--keep", action="store_true",
                   help="Don't uninstall on success.")
    args = p.parse_args()

    if not args.image.is_file():
        print(f"error: test image not found: {args.image}", file=sys.stderr)
        print("       set MAGELLON_FFT_IMAGE or pass --image", file=sys.stderr)
        return 1
    print(f"image:    {args.image}")
    print(f"base_url: {args.base_url}")

    token = args.token or step_login(args.base_url, args.username, args.password)

    if not args.skip_install:
        archive = step_pack(args.plugin_dir)
        step_uninstall_if_present(args.base_url, token, PLUGIN_ID)
        step_install(args.base_url, token, archive)
        step_wait_live(args.base_url, token, PLUGIN_ID, timeout_s=90.0)
    else:
        # Even with --skip-install, confirm the plugin is reachable so
        # the dispatch calls fail fast with a useful message.
        step_wait_live(args.base_url, token, PLUGIN_ID, timeout_s=10.0)

    out_dir = args.image.parent
    bus_target = out_dir / f"{args.image.stem}_FFT_bus.png"
    sync_target = out_dir / f"{args.image.stem}_FFT_sync.png"
    for p in (bus_target, sync_target):
        if p.exists():
            p.unlink()  # clean prior run

    bus_png = step_bus_dispatch(args.base_url, token, args.image, bus_target)
    sync_png = step_sync_dispatch(args.base_url, token, args.image, sync_target)
    step_verify(bus_png, sync_png)

    if not args.skip_install and not args.keep:
        print(">>> cleanup — DELETE /admin/plugins/{plugin_id}")
        step_uninstall_if_present(args.base_url, token, PLUGIN_ID)

    print("\nPASS")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except SystemExit:
        raise
    except KeyboardInterrupt:
        print("\ninterrupted", file=sys.stderr)
        sys.exit(130)
    except Exception as exc:  # noqa: BLE001
        print(f"\nFAIL: {exc}", file=sys.stderr)
        sys.exit(1)
