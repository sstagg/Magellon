"""One-shot CTF task publisher for end-to-end smoke testing.

Publishes one CTF task per ``.mrc`` in --image-dir to the queue the CTF
plugin (Docker or local) consumes. Uses the CTF plugin's bundled
defaults for the optical params; override with --pixel-size etc. if
the test images need different values.

Run from CoreService/ with the venv active:

    python scripts/ctf_smoke_publish.py \\
        --image-dir /gpfs/images \\
        --queue ctf_tasks_queue \\
        --rmq-host localhost --rmq-user rabbit --rmq-pass behd1d2

The ``--image-dir`` path is **container-side** — what the CTF plugin
sees inside its Docker container — not the host path.
"""
from __future__ import annotations

import argparse
import logging
import sys
import uuid
from pathlib import Path

from magellon_sdk.messaging import publish_message_to_queue
from magellon_sdk.models import CTF_TASK, PENDING, CtfInput
from magellon_sdk.task_factory import CtfTaskFactory

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("ctf-smoke")


class _RmqShim:
    """Settings object shaped for SDK's publish_message_to_queue."""
    def __init__(self, host: str, port: int, user: str, password: str, vhost: str = "/"):
        self.HOST_NAME = host
        self.PORT = port
        self.USER_NAME = user
        self.PASSWORD = password
        self.VIRTUAL_HOST = vhost
        self.SSL_ENABLED = False


def build_task(image_path: str, *, pixel_size: float, voltage: float, cs: float,
               amp_contrast: float) -> object:
    file_name = Path(image_path).stem
    out_file = f"{file_name}_ctf_output.mrc"
    data = CtfInput(
        image_id=uuid.uuid4(),
        image_name=file_name,
        image_path=image_path,
        inputFile=image_path,
        outputFile=out_file,
        pixelSize=pixel_size,
        accelerationVoltage=voltage,
        sphericalAberration=cs,
        amplitudeContrast=amp_contrast,
        sizeOfAmplitudeSpectrum=512,
        minimumResolution=30.0,
        maximumResolution=5.0,
        minimumDefocus=5000.0,
        maximumDefocus=50000.0,
        defocusSearchStep=100.0,
        binning_x=1,
    )
    task = CtfTaskFactory.create_task(
        pid=str(uuid.uuid4()),
        instance_id=uuid.uuid4(),
        job_id=uuid.uuid4(),
        data=data.model_dump(),
        ptype=CTF_TASK,
        pstatus=PENDING,
    )
    task.session_name = "smoke-test"
    return task


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--image-dir", required=True,
                   help="Container-side directory holding the .mrc files")
    p.add_argument("--queue", default="ctf_tasks_queue")
    p.add_argument("--rmq-host", default="localhost")
    p.add_argument("--rmq-port", type=int, default=5672)
    p.add_argument("--rmq-user", default="rabbit")
    p.add_argument("--rmq-pass", default="behd1d2")
    p.add_argument("--vhost", default="/")
    p.add_argument("--pixel-size", type=float, default=1.0)
    p.add_argument("--voltage", type=float, default=300.0)
    p.add_argument("--cs", type=float, default=2.7)
    p.add_argument("--amp-contrast", type=float, default=0.07)
    p.add_argument("--limit", type=int, default=None,
                   help="Only publish the first N images (for smoke testing)")
    p.add_argument("--filenames", nargs="*",
                   help="Filenames to publish (relative to --image-dir). If omitted, "
                        "publishes one task per .mrc in the dir.")
    args = p.parse_args()

    rmq = _RmqShim(args.rmq_host, args.rmq_port, args.rmq_user, args.rmq_pass, args.vhost)
    # Plain string concat — pathlib.Path("/gpfs/images") on Windows gets
    # rewritten to C:/git/gpfs/images by MSYS, which is meaningless inside
    # the container. We never resolve this path host-side; it's just a
    # string the container will dereference.
    image_dir_str = args.image_dir.rstrip("/")

    if args.filenames:
        names = args.filenames
    else:
        host_dir = Path("/c/magellon/gpfs/images")
        if not host_dir.exists():
            log.error("Could not list .mrc files: %s does not exist host-side. "
                      "Pass --filenames explicitly.", host_dir)
            return 2
        names = sorted(p.name for p in host_dir.glob("*.mrc"))

    if args.limit:
        names = names[:args.limit]

    log.info("publishing %d task(s) to %s @ %s:%s",
             len(names), args.queue, args.rmq_host, args.rmq_port)
    failures = 0
    for name in names:
        container_path = f"{image_dir_str}/{name}"
        task = build_task(container_path, pixel_size=args.pixel_size,
                          voltage=args.voltage, cs=args.cs,
                          amp_contrast=args.amp_contrast)
        ok = publish_message_to_queue(task, args.queue, rabbitmq_settings=rmq)
        log.info("  %s → %s (task_id=%s)", name, "OK" if ok else "FAIL", task.id)
        if not ok:
            failures += 1
    return 0 if failures == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
