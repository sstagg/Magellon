"""End-to-end FFT plugin demo -- no RabbitMQ, no docker, one process.

Exercises the full bus-driven task flow using the InMemoryBinder:

  1. Download 10 small sample images (falls back to synthetic if
     picsum.photos is unreachable).
  2. Install an in-memory bus as the process-wide ``MessageBus`` --
     the seam CoreService + plugins both talk through in production.
  3. Start the FFT plugin's runner on a background thread. This is
     architecturally the "plugin process" -- it consumes task
     deliveries from the bus.
  4. From the main thread, simulate the CoreService dispatcher:
     wrap each image's ``TaskDto`` in a CloudEvents envelope and
     call ``bus.tasks.send(...)``.
  5. Wait for the binder to drain (all handlers returned, all result
     publishes enqueued).
  6. Inspect the published result envelopes and print a summary.

Why this is a useful demo:

- Shows the bus contract end-to-end without infrastructure.
- Proves the MB4.2 FFT migration works: ``install_rmq_bus`` swaps
  for ``install_inmemory_bus``, nothing else changes on the plugin
  side -- same runner, same ``_handle_task``, same provenance.
- Reusable pattern for plugin smoke tests that don't want a broker.

Run::

    cd examples/fft_end_to_end
    python run_demo.py                # downloads + runs
    python run_demo.py --offline      # skip network, synthetic images
    python run_demo.py --count 20     # different sample size
"""
from __future__ import annotations

import argparse
import logging
import sys
import threading
import time
from pathlib import Path
from types import SimpleNamespace
from typing import List
from urllib.error import URLError
from urllib.request import Request, urlopen
from uuid import uuid4


# ---------------------------------------------------------------------------
# sys.path -- allow "from plugin.plugin import ..." to resolve against the
# FFT plugin directory without installing it.
# ---------------------------------------------------------------------------
REPO_ROOT = Path(__file__).resolve().parents[2]
FFT_PLUGIN_DIR = REPO_ROOT / "plugins" / "magellon_fft_plugin"
if str(FFT_PLUGIN_DIR) not in sys.path:
    sys.path.insert(0, str(FFT_PLUGIN_DIR))


# ---------------------------------------------------------------------------
# Imports after sys.path is set up
# ---------------------------------------------------------------------------
from magellon_sdk.bus.bootstrap import install_inmemory_bus  # noqa: E402
from magellon_sdk.bus.routes import TaskRoute  # noqa: E402
from magellon_sdk.envelope import Envelope  # noqa: E402
from magellon_sdk.models import FFT_TASK, TaskDto  # noqa: E402
from magellon_sdk.models.tasks import FftTaskData  # noqa: E402

# Plugin-side pieces -- live inside plugins/magellon_fft_plugin.
from plugin.plugin import (  # noqa: E402
    FftBrokerRunner,
    FftPlugin,
    build_fft_result,
)


logger = logging.getLogger("fft_demo")

IMAGES_DIR = Path(__file__).parent / "sample_images"
OUTPUT_DIR = Path(__file__).parent / "outputs"

# Logical routes. Subjects here double as the InMemoryBinder's internal
# queue names -- no legacy_queue_map needed for a single-process demo.
IN_SUBJECT = "demo.fft.tasks"
OUT_SUBJECT = "demo.fft.tasks.result"


# ---------------------------------------------------------------------------
# Image acquisition -- download or synthesize
# ---------------------------------------------------------------------------

def _download_image(index: int, dest: Path, timeout: float) -> bool:
    """Fetch one 256×256 sample from picsum.photos. Returns True on
    success, False on any network error so the caller can fall back."""
    url = f"https://picsum.photos/seed/magellon-fft-{index}/256/256"
    try:
        req = Request(url, headers={"User-Agent": "magellon-fft-demo/1.0"})
        with urlopen(req, timeout=timeout) as resp:
            data = resp.read()
        dest.write_bytes(data)
        return True
    except (URLError, TimeoutError, OSError) as exc:
        logger.info("download failed (%s) -- falling back to synthetic", exc)
        return False


def _synthetic_image(index: int, dest: Path) -> None:
    """Generate a deterministic grating-over-noise PNG for FFT demo.

    The periodic grating gives the output FFT a visible cross -- a good
    smoke test that the plugin's compute is actually running.
    """
    import numpy as np
    from PIL import Image

    rng = np.random.default_rng(index)
    size = 256
    axis = np.arange(size)
    period = 16 + index  # different grating period per image
    grating_h = np.sin(2 * np.pi * axis / period).reshape(1, -1)
    grating_v = np.sin(2 * np.pi * axis / period).reshape(-1, 1)
    noise = rng.normal(0.0, 0.5, (size, size))
    raw = grating_h + grating_v + noise
    normed = (raw - raw.min()) / (raw.max() - raw.min())
    pixels = (normed * 255).astype(np.uint8)
    Image.fromarray(pixels).save(dest)


def acquire_images(n: int, *, offline: bool, download_timeout: float) -> List[Path]:
    """Assemble N image paths -- cached, downloaded, or synthetic."""
    IMAGES_DIR.mkdir(parents=True, exist_ok=True)
    paths: List[Path] = []
    for i in range(n):
        path = IMAGES_DIR / f"sample_{i:02d}.png"
        if path.exists():
            paths.append(path)
            continue
        downloaded = False
        if not offline:
            downloaded = _download_image(i, path, timeout=download_timeout)
        if not downloaded:
            _synthetic_image(i, path)
        paths.append(path)
    return paths


# ---------------------------------------------------------------------------
# Bus wiring
# ---------------------------------------------------------------------------

def build_plugin_runner(bus) -> FftBrokerRunner:
    """Construct the FFT plugin + its runner, pointed at our demo subjects.

    ``settings`` is a throwaway -- the runner only consults it if
    ``_require_bus`` can't find an installed bus. We pass ``bus=``
    explicitly so the path is never taken.

    The plugin's step-event publisher tries to read
    ``AppSettingsSingleton.get_instance().rabbitmq_settings`` on first
    use; in this demo we have no AppSettings, so we short-circuit the
    publisher lookup. Step events are a separate subsystem (MB5
    target) -- they're not part of what this example demonstrates.
    """
    import plugin.plugin as _plugin_mod
    import plugin.events as _events_mod

    async def _no_publisher() -> None:
        return None

    _events_mod.get_publisher = _no_publisher  # type: ignore[assignment]
    # Silence the non-fatal-but-noisy "publisher init failed" messages
    # if an older cached value tries to init.
    logging.getLogger("plugin.plugin").setLevel(logging.CRITICAL)

    dummy_settings = SimpleNamespace(
        HOST_NAME="unused",
        USER_NAME="unused",
        PASSWORD="unused",
    )
    runner = FftBrokerRunner(
        plugin=FftPlugin(),
        settings=dummy_settings,
        in_queue=IN_SUBJECT,
        out_queue=OUT_SUBJECT,
        result_factory=build_fft_result,
        contract=None,  # disable discovery + config (no broker here)
        enable_discovery=False,
        enable_config=False,
        bus=bus,
    )
    return runner


def dispatch_fft_tasks(bus, image_paths: List[Path]) -> List[TaskDto]:
    """CoreService's role: build TaskDtos and publish via the bus."""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    tasks: List[TaskDto] = []
    in_route = TaskRoute.named(IN_SUBJECT)
    for image_path in image_paths:
        output_path = OUTPUT_DIR / f"{image_path.stem}_FFT.png"
        task = TaskDto(
            id=uuid4(),
            job_id=uuid4(),
            type=FFT_TASK,
            data=FftTaskData(
                image_path=str(image_path),
                target_path=str(output_path),
            ).model_dump(),
        )
        envelope = Envelope.wrap(
            source="magellon/examples/fft_end_to_end",
            type="magellon.task.dispatch",
            subject=in_route.subject,
            data=task,
        )
        receipt = bus.tasks.send(in_route, envelope)
        if not receipt.ok:
            logger.error("dispatch failed: %s", receipt.error)
        tasks.append(task)
    return tasks


# ---------------------------------------------------------------------------
# Summary reporting
# ---------------------------------------------------------------------------

def summarize(tasks: List[TaskDto], binder) -> None:
    """Print a one-line-per-task summary from the binder's capture."""
    # Result envelopes land on OUT_SUBJECT -- InMemoryBinder stores them
    # in published_tasks regardless of whether a consumer exists.
    result_publishes = [
        (s, e) for s, e in binder.published_tasks if s == OUT_SUBJECT
    ]
    results_by_task = {}
    for _subject, envelope in result_publishes:
        data = envelope.data
        task_id = (
            data.get("task_id") if isinstance(data, dict) else str(data.task_id)
        )
        results_by_task[str(task_id)] = envelope

    print()
    print("=" * 72)
    print(f"FFT demo -- dispatched {len(tasks)} tasks, received {len(result_publishes)} results")
    print("=" * 72)
    for i, task in enumerate(tasks, start=1):
        envelope = results_by_task.get(str(task.id))
        if envelope is None:
            print(f"  [{i:2d}] {task.id}  MISSING RESULT")
            continue
        data = envelope.data
        if isinstance(data, dict):
            output_files = data.get("output_files") or []
            code = data.get("code")
            message = data.get("message")
        else:
            output_files = data.output_files
            code = data.code
            message = data.message
        out_path = output_files[0]["path"] if output_files and isinstance(output_files[0], dict) else (
            output_files[0].path if output_files else "?"
        )
        print(f"  [{i:2d}] {task.id}  code={code}  msg={message!r}")
        print(f"       -> {out_path}")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> int:
    parser = argparse.ArgumentParser(description="FFT plugin end-to-end demo")
    parser.add_argument("--count", type=int, default=10, help="number of images (default 10)")
    parser.add_argument("--offline", action="store_true", help="skip downloads, generate synthetic only")
    parser.add_argument("--download-timeout", type=float, default=5.0)
    parser.add_argument("--drain-timeout", type=float, default=60.0)
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(name)s %(levelname)s %(message)s",
    )

    # 1. Images
    print(f"[1/4] acquiring {args.count} images -> {IMAGES_DIR}")
    images = acquire_images(
        args.count, offline=args.offline, download_timeout=args.download_timeout
    )
    print(f"       got {len(images)} image(s)")

    # 2. Bus
    print(f"[2/4] installing in-memory bus")
    bus = install_inmemory_bus()
    binder = bus._binder  # InMemoryBinder instance for wait_for_drain + inspection

    # 3. Plugin runner on a background thread
    print(f"[3/4] starting FFT plugin runner (consume={IN_SUBJECT})")
    runner = build_plugin_runner(bus)
    plugin_thread = threading.Thread(
        target=runner.start_blocking,
        name="fft-plugin-runner",
        daemon=True,
    )
    plugin_thread.start()

    # Tiny delay so the consumer thread has bound to the queue before
    # we start publishing -- in_flight tracking depends on the consumer
    # registration being visible to the publisher.
    time.sleep(0.1)

    try:
        # 4. Dispatch + wait
        print(f"[4/4] dispatching {len(images)} FFT tasks")
        tasks = dispatch_fft_tasks(bus, images)

        print(f"       waiting for drain (timeout={args.drain_timeout}s)")
        drained = binder.wait_for_drain(timeout=args.drain_timeout)
        if not drained:
            print("       !! drain timed out -- some tasks may still be in-flight")

        summarize(tasks, binder)
        return 0
    finally:
        runner.stop()
        bus.close()


if __name__ == "__main__":
    raise SystemExit(main())
