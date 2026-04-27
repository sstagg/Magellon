"""Broker-native topaz plugin — two PluginBase classes, one container.

Serves two categories from a single process:

* ``TOPAZ_PARTICLE_PICKING`` — high-mag MRC -> ranked particles (Topaz CNN)
* ``MICROGRAPH_DENOISING``   — high-mag MRC -> cleaned MRC (Topaz-Denoise UNet)

Mirror of ``magellon_ptolemy_plugin``: ContextVar for active-task recovery,
daemon asyncio loop for step events, runner subclasses for plugin-local
bookkeeping.
"""
from __future__ import annotations

import asyncio
import logging
import os
import threading
from contextvars import ContextVar
from typing import Optional, Type

from magellon_sdk.base import PluginBase
from magellon_sdk.categories.outputs import (
    MicrographDenoisingOutput,
    Particle,
    ParticlePickingOutput,
)
from magellon_sdk.events import BoundStepReporter
from magellon_sdk.models import OutputFile, PluginInfo, TaskMessage, TaskResultMessage
from magellon_sdk.models.manifest import (
    Capability,
    IsolationLevel,
    ResourceHints,
    Transport,
)
from magellon_sdk.models.tasks import MicrographDenoiseInput, TopazPickInput
from magellon_sdk.progress import NullReporter, ProgressReporter
from magellon_sdk.runner import PluginBrokerRunner

from plugin.compute import run_denoise, run_pick
from plugin.events import STEP_NAME, get_publisher

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Active-task ContextVar (one per process — both categories share it)
# ---------------------------------------------------------------------------

_active_task: ContextVar[Optional[TaskMessage]] = ContextVar(
    "_topaz_active_task", default=None
)


def get_active_task() -> Optional[TaskMessage]:
    return _active_task.get()


# ---------------------------------------------------------------------------
# Daemon-thread asyncio loop for step-event emission
# ---------------------------------------------------------------------------

_loop: Optional[asyncio.AbstractEventLoop] = None
_loop_lock = threading.Lock()


def _get_loop() -> asyncio.AbstractEventLoop:
    global _loop
    if _loop is not None:
        return _loop
    with _loop_lock:
        if _loop is None:
            _loop = asyncio.new_event_loop()
            threading.Thread(
                target=_loop.run_forever, name="topaz-step-events", daemon=True
            ).start()
    return _loop


def _emit(coro) -> None:
    try:
        fut = asyncio.run_coroutine_threadsafe(coro, _get_loop())
        fut.result(timeout=5.0)
    except Exception:
        logger.exception("step-event emit failed (non-fatal)")


def _make_reporter(step_suffix: str) -> Optional[BoundStepReporter]:
    task = _active_task.get()
    if task is None:
        return None
    try:
        fut = asyncio.run_coroutine_threadsafe(get_publisher(), _get_loop())
        publisher = fut.result(timeout=15.0)
    except Exception:
        logger.exception("step-event publisher init failed (non-fatal)")
        return None
    if publisher is None:
        return None
    return BoundStepReporter(
        publisher,
        job_id=task.job_id,
        task_id=task.id,
        step=f"{STEP_NAME}.{step_suffix}",
    )


# ---------------------------------------------------------------------------
# Shared plugin metadata
# ---------------------------------------------------------------------------

_CAPABILITIES = [
    Capability.CPU_INTENSIVE,
    Capability.IDEMPOTENT,
    Capability.PROGRESS_REPORTING,
]
_TRANSPORTS = [
    Transport.RMQ,
    Transport.NATS,
    Transport.HTTP,
    Transport.IN_PROCESS,
]
_RESOURCES = ResourceHints(
    # ORT sessions for detector + denoise UNet, plus float32 buffers for a
    # ~7000x7000 micrograph and its preprocessed copy. ~2 GB headroom.
    memory_mb=2000,
    cpu_cores=4,
    typical_duration_seconds=30.0,
)


# ---------------------------------------------------------------------------
# Where do per-task outputs live? Mirror CTF/MotionCor convention:
# <MAGELLON_HOME>/<session>/topaz_picks/<image_stem>/picks.json
# <MAGELLON_HOME>/<session>/topaz_denoised/<image_stem>.mrc
# ---------------------------------------------------------------------------

def _picks_json_path(input_file: str, session: Optional[str]) -> str:
    image_dir = os.path.dirname(os.path.abspath(input_file))
    base = os.path.splitext(os.path.basename(input_file))[0]
    parent = (
        os.path.join("/magellon", session, "topaz_picks", base)
        if session
        else os.path.join(image_dir, "topaz_picks", base)
    )
    return os.path.join(parent, "picks.json")


def _denoised_mrc_path(input_file: str, override: Optional[str], session: Optional[str]) -> str:
    if override:
        return override
    image_dir = os.path.dirname(os.path.abspath(input_file))
    base = os.path.splitext(os.path.basename(input_file))[0]
    if session:
        return os.path.join("/magellon", session, "topaz_denoised", f"{base}.mrc")
    return os.path.join(image_dir, f"{base}_denoised.mrc")


# ---------------------------------------------------------------------------
# TopazPickPlugin
# ---------------------------------------------------------------------------

class TopazPickPlugin(PluginBase[TopazPickInput, ParticlePickingOutput]):
    capabilities = _CAPABILITIES
    supported_transports = _TRANSPORTS
    default_transport = Transport.RMQ
    isolation = IsolationLevel.CONTAINER
    resource_hints = _RESOURCES
    tags = ["topaz", "particle-picking", "cryo-em"]

    def get_info(self) -> PluginInfo:
        return PluginInfo(
            name="Topaz Particle Picking",
            version="1.0.0",
            developer="Behdad Khoshbin b.khoshbin@gmail.com",
            description=(
                "High-mag particle picking via topaz CNN detectors. "
                "Vendors topaz internals (GPL-3.0); inference via ONNX, no PyTorch."
            ),
        )

    @classmethod
    def input_schema(cls) -> Type[TopazPickInput]:
        return TopazPickInput

    @classmethod
    def output_schema(cls) -> Type[ParticlePickingOutput]:
        return ParticlePickingOutput

    def execute(
        self,
        input_data: TopazPickInput,
        *,
        reporter: ProgressReporter = NullReporter(),
    ) -> ParticlePickingOutput:
        step = _make_reporter("pick")
        if step is not None:
            _emit(step.started())
        try:
            opts = input_data.engine_opts or {}
            model     = str(opts.get("model", "resnet16"))
            radius    = int(opts.get("radius", 14))
            threshold = float(opts.get("threshold", -3.0))
            scale     = int(opts.get("scale", 8))

            if step is not None:
                _emit(step.progress(10.0, "preprocessing micrograph"))

            picks = run_pick(
                input_data.input_file,
                model=model,
                radius=radius,
                threshold=threshold,
                scale=scale,
            )

            # Persist picks.json — canonical artifact downstream tools read.
            session = (get_active_task().session_name if get_active_task() else None)
            json_path = _picks_json_path(input_data.input_file, session)
            os.makedirs(os.path.dirname(json_path), exist_ok=True)
            import json
            with open(json_path, "w") as f:
                json.dump(picks, f, indent=2)

            if step is not None:
                _emit(step.progress(95.0, f"found {len(picks)} particles"))
                _emit(step.completed(output_files=[json_path]))

            # Inline picks for small result sets (saves a downstream fetch);
            # cap to avoid blowing up the bus envelope.
            INLINE_LIMIT = 5000
            inline = (
                [Particle(**p) for p in picks]
                if len(picks) <= INLINE_LIMIT
                else None
            )

            return ParticlePickingOutput(
                num_particles=len(picks),
                particles_json_path=json_path,
                picks=inline,
            )
        except Exception as exc:
            if step is not None:
                _emit(step.failed(error=str(exc)))
            raise


# ---------------------------------------------------------------------------
# TopazDenoisePlugin
# ---------------------------------------------------------------------------

class TopazDenoisePlugin(PluginBase[MicrographDenoiseInput, MicrographDenoisingOutput]):
    capabilities = _CAPABILITIES
    supported_transports = _TRANSPORTS
    default_transport = Transport.RMQ
    isolation = IsolationLevel.CONTAINER
    resource_hints = _RESOURCES
    tags = ["topaz-denoise", "denoising", "cryo-em"]

    def get_info(self) -> PluginInfo:
        return PluginInfo(
            name="Topaz-Denoise",
            version="1.0.0",
            developer="Behdad Khoshbin b.khoshbin@gmail.com",
            description=(
                "Per-micrograph denoising via topaz UNet. "
                "ONNX inference, patch+stitch driver, no PyTorch."
            ),
        )

    @classmethod
    def input_schema(cls) -> Type[MicrographDenoiseInput]:
        return MicrographDenoiseInput

    @classmethod
    def output_schema(cls) -> Type[MicrographDenoisingOutput]:
        return MicrographDenoisingOutput

    def execute(
        self,
        input_data: MicrographDenoiseInput,
        *,
        reporter: ProgressReporter = NullReporter(),
    ) -> MicrographDenoisingOutput:
        step = _make_reporter("denoise")
        if step is not None:
            _emit(step.started())
        try:
            opts = input_data.engine_opts or {}
            model      = str(opts.get("model", "unet"))
            patch_size = int(opts.get("patch_size", 1024))
            padding    = int(opts.get("padding", 128))

            session = (get_active_task().session_name if get_active_task() else None)
            output_path = _denoised_mrc_path(
                input_data.input_file, input_data.output_file, session,
            )

            if step is not None:
                _emit(step.progress(10.0, f"denoising in {patch_size}px patches"))

            stats = run_denoise(
                input_data.input_file,
                output_path,
                model=model,
                patch_size=patch_size,
                padding=padding,
            )

            if step is not None:
                _emit(step.progress(95.0, "writing denoised MRC"))
                _emit(step.completed(output_files=[output_path]))

            return MicrographDenoisingOutput(
                output_path=stats["output"],
                source_image_path=stats["input"],
                model=stats["model"],
                image_shape=stats["shape"],
                pixel_min=stats["min"],
                pixel_max=stats["max"],
                pixel_mean=stats["mean"],
                pixel_std=stats["std"],
            )
        except Exception as exc:
            if step is not None:
                _emit(step.failed(error=str(exc)))
            raise


# ---------------------------------------------------------------------------
# Runner — same ContextVar trick as ptolemy
# ---------------------------------------------------------------------------

class TopazBrokerRunner(PluginBrokerRunner):
    def _handle_task(self, envelope) -> None:
        task = self._task_from_envelope(envelope)
        token = _active_task.set(task)
        try:
            super()._handle_task(envelope)
        finally:
            _active_task.reset(token)

    def _process(self, body: bytes) -> bytes:
        task = TaskMessage.model_validate_json(body.decode("utf-8"))
        token = _active_task.set(task)
        try:
            self._apply_pending_config()
            validated = self.plugin.input_schema().model_validate(task.data)
            plugin_output = self.plugin.run(validated)
            result = self.result_factory(task, plugin_output)
            self._stamp_provenance(result)
            return result.model_dump_json().encode("utf-8")
        finally:
            _active_task.reset(token)


# ---------------------------------------------------------------------------
# Result factories
# ---------------------------------------------------------------------------

def build_pick_result(task: TaskMessage, output: ParticlePickingOutput) -> TaskResultMessage:
    data = task.data or {}
    input_file = data.get("input_file", "")
    out_files = []
    if output.particles_json_path:
        out_files.append(OutputFile(
            name=os.path.basename(output.particles_json_path),
            path=output.particles_json_path,
            required=True,
        ))
    return TaskResultMessage(
        worker_instance_id=task.worker_instance_id,
        job_id=task.job_id,
        task_id=task.id,
        image_path=input_file,
        session_id=task.session_id,
        session_name=task.session_name,
        code=200,
        message=f"Topaz picked {output.num_particles} particles",
        type=task.type,
        output_data={
            "num_particles":       output.num_particles,
            "particles_json_path": output.particles_json_path,
            "picks":               [p.model_dump() for p in (output.picks or [])],
            **output.extras,
        },
        output_files=out_files,
    )


def build_denoise_result(task: TaskMessage, output: MicrographDenoisingOutput) -> TaskResultMessage:
    data = task.data or {}
    input_file = data.get("input_file", "")
    return TaskResultMessage(
        worker_instance_id=task.worker_instance_id,
        job_id=task.job_id,
        task_id=task.id,
        image_path=input_file,
        session_id=task.session_id,
        session_name=task.session_name,
        code=200,
        message=f"Topaz-Denoise wrote {output.output_path}",
        type=task.type,
        output_data=output.model_dump(),
        output_files=[OutputFile(
            name=os.path.basename(output.output_path),
            path=output.output_path,
            required=True,
        )],
    )


__all__ = [
    "TopazPickPlugin",
    "TopazDenoisePlugin",
    "TopazBrokerRunner",
    "build_pick_result",
    "build_denoise_result",
    "get_active_task",
]
