"""One-shot MotionCor task publisher for end-to-end Docker testing.

Mirror of ``ctf_smoke_publish.py``. Publishes one CryoEmMotionCorTaskData
per ``.mrc`` in --image-dir to ``motioncor_tasks_queue``.

The Docker.test image's mock_motioncor binary doesn't care about the
optical params — it just produces stub output files in the right shape.
For real GPU validation, point this at a CUDA build (Dockerfile, not
Dockerfile.test) and pass real values for FmDose / PixSize.

Usage from CoreService/ with venv active:

    MSYS_NO_PATHCONV=1 python scripts/motioncor_smoke_publish.py \\
        --image-dir /gpfs/images \\
        --filenames image1.mrc image2.mrc
"""
from __future__ import annotations

import argparse
import logging
import sys
import uuid
from pathlib import Path

from magellon_sdk.messaging import publish_message_to_queue
from magellon_sdk.models import CryoEmMotionCorTaskData, MOTIONCOR, PENDING
from magellon_sdk.task_factory import MotioncorTaskFactory

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("motioncor-smoke")


class _RmqShim:
    def __init__(self, host: str, port: int, user: str, password: str, vhost: str = "/"):
        self.HOST_NAME = host
        self.PORT = port
        self.USER_NAME = user
        self.PASSWORD = password
        self.VIRTUAL_HOST = vhost
        self.SSL_ENABLED = False


def build_task(image_path: str, *, gain: str, fm_dose: float, pix_size: float) -> object:
    file_name = Path(image_path).stem
    out_file = f"{file_name}_motioncor_output.mrc"
    data = CryoEmMotionCorTaskData(
        image_id=uuid.uuid4(),
        image_name=file_name,
        image_path=image_path,
        inputFile=image_path,
        outputFile=out_file,
        Gain=gain,
        PatchesX=5,
        PatchesY=5,
        FmDose=fm_dose,
        PixSize=pix_size,
        kV=300,
        FtBin=2.0,
        Iter=5,
        Tol=0.5,
        Bft=100,
        Gpu="0",
    )
    task = MotioncorTaskFactory.create_task(
        pid=str(uuid.uuid4()),
        instance_id=uuid.uuid4(),
        job_id=uuid.uuid4(),
        data=data.model_dump(),
        ptype=MOTIONCOR,
        pstatus=PENDING,
    )
    task.sesson_name = "smoke-test"
    return task


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--image-dir", required=True,
                   help="Container-side directory holding the .mrc files")
    p.add_argument("--filenames", nargs="+", required=True,
                   help="Filenames to publish (relative to --image-dir)")
    p.add_argument("--queue", default="motioncor_tasks_queue")
    p.add_argument("--rmq-host", default="localhost")
    p.add_argument("--rmq-port", type=int, default=5672)
    p.add_argument("--rmq-user", default="rabbit")
    p.add_argument("--rmq-pass", default="behd1d2")
    p.add_argument("--vhost", default="/")
    p.add_argument("--gain", default="",
                   help="Container-side path to gain reference (mock binary "
                        "doesn't read it; pass empty string for the test)")
    p.add_argument("--fm-dose", type=float, default=1.0)
    p.add_argument("--pix-size", type=float, default=1.0)
    args = p.parse_args()

    rmq = _RmqShim(args.rmq_host, args.rmq_port, args.rmq_user, args.rmq_pass, args.vhost)
    image_dir_str = args.image_dir.rstrip("/")

    log.info("publishing %d task(s) to %s @ %s:%s",
             len(args.filenames), args.queue, args.rmq_host, args.rmq_port)
    failures = 0
    for name in args.filenames:
        container_path = f"{image_dir_str}/{name}"
        task = build_task(
            container_path, gain=args.gain,
            fm_dose=args.fm_dose, pix_size=args.pix_size,
        )
        ok = publish_message_to_queue(task, args.queue, rabbitmq_settings=rmq)
        log.info("  %s -> %s (task_id=%s)", name, "OK" if ok else "FAIL", task.id)
        if not ok:
            failures += 1
    return 0 if failures == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
