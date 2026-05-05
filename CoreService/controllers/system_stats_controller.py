"""Live system stats for the plugins dashboard.

``GET /system/stats`` returns one snapshot of host CPU, RAM, network,
and (optionally) GPU usage. Polled by the React side every few seconds —
kept intentionally cheap (a single ``psutil`` walk plus an optional
NVML query) so callers can refetch frequently without thrashing.

Authorization: ``Administrator`` only — system-level metrics are not
something every authenticated user needs to see, and the same gate
matches the install pipeline endpoints next to it.

Why polling instead of Socket.IO push: this is dashboard data, low
stakes, and the existing react-query pattern (``useAdminPluginProcessStatus``
already polls at 5s) keeps the implementation tight. Push would buy
us a smoother feel at the cost of room subscriptions, fan-out
considerations, and another moving piece to debug.
"""
from __future__ import annotations

import logging
import shutil
import subprocess
import time
from dataclasses import dataclass
from threading import Lock
from typing import List, Optional

import psutil
from fastapi import APIRouter, Depends
from pydantic import BaseModel

from dependencies.permissions import require_role

logger = logging.getLogger(__name__)

system_stats_router = APIRouter()


# ---------------------------------------------------------------------------
# Response models
# ---------------------------------------------------------------------------


class CpuStats(BaseModel):
    percent: float
    """0-100 percent across all cores, averaged since the last call."""
    cores: int
    """Logical cores (psutil.cpu_count())."""
    load_avg: Optional[List[float]] = None
    """Unix load average 1/5/15 min. None on Windows."""


class RamStats(BaseModel):
    total_bytes: int
    used_bytes: int
    available_bytes: int
    percent: float


class NetworkStats(BaseModel):
    rx_bytes_per_sec: float
    tx_bytes_per_sec: float
    rx_total_bytes: int
    tx_total_bytes: int


class GpuDeviceStats(BaseModel):
    index: int
    name: str
    util_percent: Optional[float] = None
    memory_used_bytes: Optional[int] = None
    memory_total_bytes: Optional[int] = None
    temperature_c: Optional[float] = None


class GpuStats(BaseModel):
    available: bool
    devices: List[GpuDeviceStats] = []
    error: Optional[str] = None


class SystemStatsResponse(BaseModel):
    cpu: CpuStats
    ram: RamStats
    network: NetworkStats
    gpu: GpuStats
    sampled_at: float
    """Server-side timestamp (seconds since epoch) when the snapshot
    was taken. Useful for sanity-checking client/server clock drift."""


# ---------------------------------------------------------------------------
# Network rate — needs a previous sample to compute bytes/sec
# ---------------------------------------------------------------------------


@dataclass
class _NetSample:
    ts: float
    rx: int
    tx: int


_net_lock = Lock()
_net_last: Optional[_NetSample] = None


def _net_rate() -> NetworkStats:
    """Return current rx/tx rates by diffing against the last sample.

    First call after process start returns 0/0 — there's no prior
    sample to diff against. That's fine for the UI: subsequent polls
    surface the real rate within one tick.
    """
    global _net_last
    counters = psutil.net_io_counters()
    now = time.monotonic()
    rx_bytes = int(counters.bytes_recv)
    tx_bytes = int(counters.bytes_sent)

    with _net_lock:
        prev = _net_last
        _net_last = _NetSample(ts=now, rx=rx_bytes, tx=tx_bytes)

    if prev is None or now <= prev.ts:
        rx_rate = tx_rate = 0.0
    else:
        dt = now - prev.ts
        rx_rate = max(0.0, (rx_bytes - prev.rx) / dt)
        tx_rate = max(0.0, (tx_bytes - prev.tx) / dt)

    return NetworkStats(
        rx_bytes_per_sec=rx_rate,
        tx_bytes_per_sec=tx_rate,
        rx_total_bytes=rx_bytes,
        tx_total_bytes=tx_bytes,
    )


# ---------------------------------------------------------------------------
# GPU — try pynvml first, fall back to nvidia-smi shell, fall back to None
# ---------------------------------------------------------------------------


def _gpu_via_pynvml() -> Optional[GpuStats]:
    """NVML-bound query. Returns None when pynvml isn't installed or
    initialization fails (e.g. no driver)."""
    try:
        import pynvml  # type: ignore
    except ImportError:
        return None
    try:
        pynvml.nvmlInit()
    except Exception as exc:  # noqa: BLE001
        return GpuStats(available=False, error=f"NVML init failed: {exc}")

    devices: List[GpuDeviceStats] = []
    try:
        count = pynvml.nvmlDeviceGetCount()
        for i in range(count):
            handle = pynvml.nvmlDeviceGetHandleByIndex(i)
            name = pynvml.nvmlDeviceGetName(handle)
            if isinstance(name, bytes):
                name = name.decode("utf-8", errors="replace")
            util = pynvml.nvmlDeviceGetUtilizationRates(handle)
            mem = pynvml.nvmlDeviceGetMemoryInfo(handle)
            try:
                temp = float(
                    pynvml.nvmlDeviceGetTemperature(
                        handle, pynvml.NVML_TEMPERATURE_GPU,
                    )
                )
            except Exception:  # noqa: BLE001
                temp = None
            devices.append(GpuDeviceStats(
                index=i,
                name=name,
                util_percent=float(util.gpu),
                memory_used_bytes=int(mem.used),
                memory_total_bytes=int(mem.total),
                temperature_c=temp,
            ))
    finally:
        try:
            pynvml.nvmlShutdown()
        except Exception:  # noqa: BLE001
            pass
    return GpuStats(available=True, devices=devices)


def _gpu_via_smi() -> Optional[GpuStats]:
    """Fallback: shell out to ``nvidia-smi`` and parse the CSV. Returns
    None when ``nvidia-smi`` isn't on PATH (most dev hosts)."""
    if shutil.which("nvidia-smi") is None:
        return None
    try:
        result = subprocess.run(
            [
                "nvidia-smi",
                "--query-gpu=index,name,utilization.gpu,memory.used,memory.total,temperature.gpu",
                "--format=csv,noheader,nounits",
            ],
            capture_output=True,
            text=True,
            timeout=2.0,
        )
    except Exception as exc:  # noqa: BLE001
        return GpuStats(available=False, error=f"nvidia-smi error: {exc}")
    if result.returncode != 0:
        return GpuStats(
            available=False,
            error=f"nvidia-smi rc={result.returncode}: {result.stderr.strip()}",
        )
    devices: List[GpuDeviceStats] = []
    for line in (result.stdout or "").splitlines():
        parts = [p.strip() for p in line.split(",")]
        if len(parts) < 6:
            continue
        try:
            devices.append(GpuDeviceStats(
                index=int(parts[0]),
                name=parts[1],
                util_percent=float(parts[2]),
                memory_used_bytes=int(float(parts[3]) * 1024 * 1024),
                memory_total_bytes=int(float(parts[4]) * 1024 * 1024),
                temperature_c=float(parts[5]) if parts[5] else None,
            ))
        except (ValueError, IndexError):
            continue
    return GpuStats(available=True, devices=devices)


def _gather_gpu() -> GpuStats:
    for source in (_gpu_via_pynvml, _gpu_via_smi):
        result = source()
        if result is not None:
            return result
    return GpuStats(available=False)


# ---------------------------------------------------------------------------
# Endpoint
# ---------------------------------------------------------------------------


@system_stats_router.get(
    "/stats",
    response_model=SystemStatsResponse,
    summary="One snapshot of host CPU / RAM / GPU / network usage.",
)
def get_system_stats(
    _: None = Depends(require_role("Administrator")),
) -> SystemStatsResponse:
    """Single sample of host metrics. Cheap enough to poll at 1-2s.

    Network rates are computed against a process-local previous sample
    (see ``_net_rate``); the first call returns 0/0 by design.
    """
    cpu = psutil.cpu_percent(interval=None)  # non-blocking — uses last interval
    cores = psutil.cpu_count(logical=True) or 0
    try:
        load_avg = list(psutil.getloadavg())
    except (AttributeError, OSError):
        # Windows doesn't expose load average.
        load_avg = None

    vm = psutil.virtual_memory()
    ram = RamStats(
        total_bytes=int(vm.total),
        used_bytes=int(vm.used),
        available_bytes=int(vm.available),
        percent=float(vm.percent),
    )

    return SystemStatsResponse(
        cpu=CpuStats(percent=float(cpu), cores=int(cores), load_avg=load_avg),
        ram=ram,
        network=_net_rate(),
        gpu=_gather_gpu(),
        sampled_at=time.time(),
    )


__all__ = ["system_stats_router"]
