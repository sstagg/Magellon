#!/usr/bin/env python3
"""Real-GPU validation of MotionCor2 via RunPod.

The local-wiring smoke test (smoke_test_docker.py) mocks the binary, so it
can't catch problems in the real MotionCor2 command, the binary's CUDA
expectations, or output content. This script rents a GPU on RunPod, runs
the actual MotionCor2_1.6.4_Cuda121 binary on one example movie, pulls the
output back, and compares runtime against the local bench file.

Why a 3-minute ceiling: RunPod can stall (pod stuck STARTING, marketplace
empty, image pull stuck). If any single RunPod operation takes longer
than 3 minutes we abort — better to bail and investigate than to burn
credit on a hung pod.

Prerequisites:
    - RunPod account with credit
    - RUNPOD_API_KEY env var
    - SSH key pair (default ~/.ssh/id_ed25519 + .pub)
    - The MotionCor2_1.6.4_Cuda121_Mar312023 binary in the plugin root
    - A TIF movie under C:/temp/motioncor/Magellon-test/example1/ (or set EXAMPLE_DIR)

Usage:
    set RUNPOD_API_KEY=rpa_xxx
    python plugins/magellon_motioncor_plugin/tests/runpod_gpu_test.py

Env overrides:
    RUNPOD_API_KEY      Required.
    SSH_KEY_PATH        Path to private key (default ~/.ssh/id_ed25519)
    SSH_PUB_KEY_PATH    Path to matching .pub (default <SSH_KEY_PATH>.pub)
    EXAMPLE_DIR         Source dir with a TIF + reference output
                        (default C:/temp/motioncor/Magellon-test/example1)
    GPU_TYPES           Comma-separated GPU IDs to try in order (default:
                        "NVIDIA RTX 4000 Ada Generation,NVIDIA L4,NVIDIA RTX A4000")
    POD_IMAGE           Docker image (default runpod/pytorch:2.4.0-py3.11-cuda12.4.1-devel-ubuntu22.04)
    DEPLOY_TIMEOUT      Seconds to wait for pod RUNNING + SSH (default 180)
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
API_KEY = os.environ.get("RUNPOD_API_KEY", "").strip()
SSH_KEY_PATH = os.environ.get("SSH_KEY_PATH", str(Path.home() / ".ssh" / "id_ed25519"))
SSH_PUB_KEY_PATH = os.environ.get("SSH_PUB_KEY_PATH", SSH_KEY_PATH + ".pub")
EXAMPLE_DIR = Path(os.environ.get("EXAMPLE_DIR", "C:/temp/motioncor/Magellon-test/example1"))
GPU_TYPES = [g.strip() for g in os.environ.get(
    "GPU_TYPES",
    "NVIDIA RTX 4000 Ada Generation,NVIDIA L4,NVIDIA RTX A4000",
).split(",") if g.strip()]
POD_IMAGE = os.environ.get(
    "POD_IMAGE", "runpod/pytorch:2.4.0-py3.11-cuda12.4.1-devel-ubuntu22.04",
)
DEPLOY_TIMEOUT = int(os.environ.get("DEPLOY_TIMEOUT", "180"))

PLUGIN_DIR = Path(__file__).resolve().parent.parent
BINARY_PATH = PLUGIN_DIR / "MotionCor2_1.6.4_Cuda121_Mar312023"
BENCH_FILE = Path("C:/temp/motioncor/Magellon-test/motioncor2_benchmark_results.txt")

GRAPHQL_URL = "https://api.runpod.io/graphql"
RUNPOD_REST = "https://rest.runpod.io/v1"  # newer REST endpoints — used for status polling

# Hard ceiling on any individual RunPod call. The user's directive: "don't
# wait more than 3min for runpod's otherwise know that something is broken".
RUNPOD_CALL_DEADLINE = 180


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def fail(msg: str, code: int = 1) -> None:
    print(f"FAIL: {msg}")
    sys.exit(code)


def info(msg: str) -> None:
    print(f"  {msg}")


def graphql(query: str, variables: dict | None = None) -> dict:
    body = json.dumps({"query": query, "variables": variables or {}}).encode()
    req = urllib.request.Request(
        GRAPHQL_URL,
        data=body,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {API_KEY}",
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        payload = json.loads(resp.read())
    if "errors" in payload:
        raise RuntimeError(f"GraphQL error: {payload['errors']}")
    return payload["data"]


def rest(method: str, path: str, body: dict | None = None) -> dict:
    url = f"{RUNPOD_REST}{path}"
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(
        url,
        data=data,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {API_KEY}",
        },
        method=method,
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        raw = resp.read()
        return json.loads(raw) if raw else {}


# ---------------------------------------------------------------------------
# Steps
# ---------------------------------------------------------------------------

def step_preflight() -> tuple[Path, str]:
    print("\n=== Preflight ===")
    if not API_KEY:
        fail("RUNPOD_API_KEY not set")
    info(f"API key: {API_KEY[:8]}...")

    if not BINARY_PATH.exists():
        fail(f"MotionCor2 binary not found at {BINARY_PATH}")
    info(f"Binary: {BINARY_PATH.name} ({BINARY_PATH.stat().st_size // (1024*1024)} MB)")

    if not EXAMPLE_DIR.is_dir():
        fail(f"Example dir not found: {EXAMPLE_DIR}")
    tifs = sorted(EXAMPLE_DIR.glob("*.tif")) + sorted(EXAMPLE_DIR.glob("*.tiff"))
    if not tifs:
        fail(f"No TIF in {EXAMPLE_DIR}")
    tif = tifs[0]
    info(f"Movie: {tif.name} ({tif.stat().st_size // (1024*1024)} MB)")

    for tool in ("ssh", "scp"):
        if shutil.which(tool) is None:
            fail(f"{tool} not on PATH (install OpenSSH)")
    info("ssh + scp available")

    if not Path(SSH_PUB_KEY_PATH).exists():
        fail(
            f"SSH public key not found at {SSH_PUB_KEY_PATH}. "
            "Generate one with: ssh-keygen -t ed25519 -f ~/.ssh/id_ed25519 -N ''"
        )
    pub_key = Path(SSH_PUB_KEY_PATH).read_text().strip()
    info(f"SSH pub key: {pub_key[:40]}...")

    # Sanity-check API access early. If this fails we never spin up a pod.
    me = graphql("query { myself { id email currentSpendPerHr } }")["myself"]
    info(f"Account: {me.get('email', '?')} (spend ${me.get('currentSpendPerHr', 0):.2f}/hr)")
    return tif, pub_key


def step_pick_gpu_type() -> str:
    """Find the cheapest GPU type from our preference list that has stock."""
    print("\n=== Selecting GPU type ===")
    data = graphql("""
        query {
            gpuTypes {
                id
                displayName
                memoryInGb
                communityPrice
                lowestPrice(input: { gpuCount: 1 }) {
                    minimumBidPrice
                    uninterruptablePrice
                }
            }
        }
    """)
    by_name = {g["displayName"]: g for g in data["gpuTypes"]}
    for name in GPU_TYPES:
        g = by_name.get(name)
        if not g:
            info(f"  {name}: not in catalog")
            continue
        price = g.get("lowestPrice", {}).get("uninterruptablePrice")
        if price is None:
            info(f"  {name}: no price (out of stock?)")
            continue
        info(f"  {name}: ${price}/hr — selected")
        return g["id"]
    fail(f"None of the requested GPU types are available: {GPU_TYPES}")


def step_deploy_pod(gpu_type_id: str, pub_key: str) -> dict:
    """Deploy the pod and wait for SSH to be reachable."""
    print(f"\n=== Deploying pod (image={POD_IMAGE}) ===")
    pod_name = f"magellon-mc-test-{int(time.time())}"

    # podFindAndDeployOnDemand returns a Pod with id + machine info if
    # capacity is available. env contains PUBLIC_KEY which the runpod
    # /pytorch images consume on boot to authorise SSH for root.
    mutation = """
        mutation Deploy($input: PodFindAndDeployOnDemandInput) {
            podFindAndDeployOnDemand(input: $input) {
                id
                imageName
                machineId
                desiredStatus
            }
        }
    """
    variables = {
        "input": {
            "cloudType": "ALL",
            "gpuCount": 1,
            "volumeInGb": 0,
            "containerDiskInGb": 20,
            "minVcpuCount": 4,
            "minMemoryInGb": 16,
            "gpuTypeId": gpu_type_id,
            "name": pod_name,
            "imageName": POD_IMAGE,
            "dockerArgs": "",
            "ports": "22/tcp",
            "volumeMountPath": "/workspace",
            "env": [{"key": "PUBLIC_KEY", "value": pub_key}],
        }
    }
    deploy_started = time.time()
    pod = graphql(mutation, variables)["podFindAndDeployOnDemand"]
    if pod is None:
        fail(f"Deploy returned null — no capacity for {gpu_type_id}?")
    info(f"Pod {pod['id']} created on machine {pod.get('machineId')}")

    # Wait for SSH to be reachable. Pod is RUNNING when machine is provisioned;
    # SSH server inside the image can take another ~30s to come up.
    pod_id = pod["id"]
    ssh_info = None
    while time.time() - deploy_started < DEPLOY_TIMEOUT:
        if time.time() - deploy_started > RUNPOD_CALL_DEADLINE:
            fail(f"Pod stuck > {RUNPOD_CALL_DEADLINE}s — aborting (likely a RunPod issue)")
        time.sleep(8)
        status = graphql("""
            query Pod($id: String!) {
                pod(input: { podId: $id }) {
                    id
                    desiredStatus
                    runtime {
                        ports { ip publicPort privatePort isIpPublic }
                    }
                }
            }
        """, {"id": pod_id})["pod"]
        runtime = status.get("runtime") or {}
        ports = runtime.get("ports") or []
        ssh_port = next(
            (p for p in ports if p.get("privatePort") == 22 and p.get("isIpPublic")),
            None,
        )
        elapsed = int(time.time() - deploy_started)
        info(f"  [{elapsed:3d}s] status={status['desiredStatus']} ssh_port={ssh_port}")
        if ssh_port:
            ssh_info = ssh_port
            break

    if not ssh_info:
        fail(f"SSH never came up after {DEPLOY_TIMEOUT}s")

    # Probe with a no-op ssh until the daemon actually accepts us.
    host, port = ssh_info["ip"], ssh_info["publicPort"]
    info(f"SSH endpoint: root@{host}:{port}")
    probe_started = time.time()
    while time.time() - probe_started < 60:
        rc = ssh_run(host, port, "echo ready", check=False, timeout=10)
        if rc.returncode == 0:
            info("SSH handshake OK")
            return {"id": pod_id, "host": host, "port": port}
        time.sleep(5)
    fail("SSH endpoint never accepted handshake")
    return {}  # unreachable


def ssh_args(host: str, port: int) -> list[str]:
    return [
        "-i", SSH_KEY_PATH,
        "-p", str(port),
        "-o", "StrictHostKeyChecking=no",
        "-o", "UserKnownHostsFile=/dev/null",
        "-o", "LogLevel=ERROR",
        f"root@{host}",
    ]


def ssh_run(host: str, port: int, cmd: str, check: bool = True, timeout: int = 600):
    full = ["ssh", *ssh_args(host, port), cmd]
    return subprocess.run(full, check=check, capture_output=True, text=True, timeout=timeout)


def scp_to(local: Path, host: str, port: int, remote: str) -> None:
    cmd = [
        "scp", "-i", SSH_KEY_PATH, "-P", str(port),
        "-o", "StrictHostKeyChecking=no",
        "-o", "UserKnownHostsFile=/dev/null",
        "-o", "LogLevel=ERROR",
        str(local), f"root@{host}:{remote}",
    ]
    subprocess.run(cmd, check=True, timeout=300)


def scp_from(host: str, port: int, remote: str, local: Path) -> None:
    cmd = [
        "scp", "-i", SSH_KEY_PATH, "-P", str(port),
        "-o", "StrictHostKeyChecking=no",
        "-o", "UserKnownHostsFile=/dev/null",
        "-o", "LogLevel=ERROR",
        f"root@{host}:{remote}", str(local),
    ]
    subprocess.run(cmd, check=True, timeout=300)


def step_run_motioncor(pod: dict, tif: Path) -> tuple[float, Path]:
    """Upload the binary + movie, run MotionCor, pull output back."""
    print("\n=== Running MotionCor2 on the pod ===")
    host, port = pod["host"], pod["port"]

    info("Uploading MotionCor2 binary...")
    t0 = time.time()
    scp_to(BINARY_PATH, host, port, "/workspace/MotionCor2")
    info(f"  ({time.time() - t0:.1f}s, {BINARY_PATH.stat().st_size // (1024*1024)} MB)")

    info("Uploading movie...")
    t0 = time.time()
    scp_to(tif, host, port, f"/workspace/{tif.name}")
    info(f"  ({time.time() - t0:.1f}s, {tif.stat().st_size // (1024*1024)} MB)")

    ssh_run(host, port, "chmod +x /workspace/MotionCor2 && nvidia-smi -L")

    info("Running MotionCor2 (mirroring bench script flags)...")
    cmd = (
        "cd /workspace && "
        "/usr/bin/time -f '%e' "
        "./MotionCor2 "
        f"-InTiff {tif.name} "
        "-OutMrc output.mrc "
        "-Gpu 0 "
        "-Patch 5 5 "
        "-Iter 10 "
        "-Tol 0.5 "
        "-FtBin 1 "
        "-kV 300 "
        "> motioncor.log 2>&1; echo EXIT=$?"
    )
    t0 = time.time()
    result = ssh_run(host, port, cmd, timeout=600)
    elapsed = time.time() - t0
    info(f"Wall-clock: {elapsed:.1f}s")
    print(result.stdout)

    # Pull log + output back
    out_dir = PLUGIN_DIR / "tests" / "runpod_output"
    out_dir.mkdir(exist_ok=True)
    info(f"Downloading output to {out_dir}")
    scp_from(host, port, "/workspace/motioncor.log", out_dir / "motioncor.log")
    scp_from(host, port, "/workspace/output.mrc", out_dir / "output.mrc")
    return elapsed, out_dir


def step_compare_to_bench(elapsed: float, out_dir: Path) -> None:
    print("\n=== Comparing against bench ===")
    output_mrc = out_dir / "output.mrc"
    if not output_mrc.exists() or output_mrc.stat().st_size < 1024:
        fail(f"output.mrc missing or empty (size={output_mrc.stat().st_size if output_mrc.exists() else 0})")
    info(f"output.mrc: {output_mrc.stat().st_size // (1024*1024)} MB")

    if not BENCH_FILE.exists():
        info(f"No bench file at {BENCH_FILE} — skipping timing comparison")
        return
    bench_text = BENCH_FILE.read_text()
    # example1's line is "Runtime: 0m49.111598102s" — we just want the seconds.
    import re
    m = re.search(r"example1.*?Runtime:\s*0m([\d.]+)s", bench_text, re.DOTALL)
    if not m:
        info("Couldn't parse example1 runtime from bench file")
        return
    bench_seconds = float(m.group(1))
    ratio = elapsed / bench_seconds
    info(f"Bench (example1): {bench_seconds:.1f}s")
    info(f"Pod:              {elapsed:.1f}s ({ratio:.2f}x bench)")
    if ratio > 3.0:
        info("WARNING: pod ran >3x slower than bench — GPU is much weaker, or something is wrong")


def step_teardown(pod: dict | None) -> None:
    if not pod:
        return
    print(f"\n=== Tearing down pod {pod['id']} ===")
    try:
        graphql("""
            mutation Stop($id: String!) {
                podTerminate(input: { podId: $id })
            }
        """, {"id": pod["id"]})
        info("Terminated")
    except Exception as e:
        info(f"WARNING: terminate failed: {e}")
        info(f"  Manually terminate at https://www.runpod.io/console/pods")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    print("=" * 60)
    print("MotionCor2 RunPod GPU Validation")
    print("=" * 60)

    tif, pub_key = step_preflight()
    gpu_type_id = step_pick_gpu_type()
    pod = None
    try:
        pod = step_deploy_pod(gpu_type_id, pub_key)
        elapsed, out_dir = step_run_motioncor(pod, tif)
        step_compare_to_bench(elapsed, out_dir)
    finally:
        step_teardown(pod)

    print("\n" + "=" * 60)
    print("PASSED — real GPU run completed and output landed locally")
    print("=" * 60)


if __name__ == "__main__":
    main()
