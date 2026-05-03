"""Broker-native topaz plugin — two PluginBase classes, one container.

Serves two categories from a single process:

* ``TOPAZ_PARTICLE_PICKING`` — high-mag MRC -> ranked particles (Topaz CNN)
* ``MICROGRAPH_DENOISING``   — high-mag MRC -> cleaned MRC (Topaz-Denoise UNet)

Phase 1b (2026-05-03): the per-plugin ``_active_task`` ContextVar,
daemon-thread asyncio loop, ``_emit`` / ``_make_reporter`` helpers,
and ``TopazBrokerRunner`` subclass are gone. The same plumbing now
lives in :mod:`magellon_sdk.runner.active_task` and is set by
:class:`PluginBrokerRunner` for every plugin. Back-compat shims at
the bottom keep the old import names working for one release.
"""
from __future__ import annotations

import logging
import os
from typing import Optional, Type

from magellon_sdk.base import PluginBase
from magellon_sdk.categories.outputs import (
    MicrographDenoisingOutput,
    Particle,
    ParticlePickingOutput,
)
from magellon_sdk.models import OutputFile, PluginInfo, TaskMessage, TaskResultMessage
from magellon_sdk.models.manifest import (
    Capability,
    IsolationLevel,
    ResourceHints,
    Transport,
)
from magellon_sdk.models.tasks import MicrographDenoiseInput, TopazPickInput
from magellon_sdk.progress import NullReporter, ProgressReporter
from magellon_sdk.runner import current_task, emit_step, make_step_reporter

from plugin.compute import run_denoise, run_pick
from plugin.events import STEP_NAME, get_publisher

logger = logging.getLogger(__name__)


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
        step = make_step_reporter(f"{STEP_NAME}.pick", get_publisher)
        if step is not None:
            emit_step(step.started())
        try:
            opts = input_data.engine_opts or {}
            model     = str(opts.get("model", "resnet16"))
            radius    = int(opts.get("radius", 14))
            threshold = float(opts.get("threshold", -3.0))
            scale     = int(opts.get("scale", 8))

            if step is not None:
                emit_step(step.progress(10.0, "preprocessing micrograph"))

            picks = run_pick(
                input_data.input_file,
                model=model,
                radius=radius,
                threshold=threshold,
                scale=scale,
            )

            # Persist picks.json — canonical artifact downstream tools read.
            active = current_task()
            session = active.session_name if active else None
            json_path = _picks_json_path(input_data.input_file, session)
            os.makedirs(os.path.dirname(json_path), exist_ok=True)
            import json
            with open(json_path, "w") as f:
                json.dump(picks, f, indent=2)

            if step is not None:
                emit_step(step.progress(95.0, f"found {len(picks)} particles"))
                emit_step(step.completed(output_files=[json_path]))

            # Per ratified rule 1 (project_artifact_bus_invariants.md,
            # 2026-05-03): bus carries refs and summaries only. The
            # pre-Phase-1c inline-picks path was a size cliff (≤5000
            # inline, then path-only) — the consultant flagged it as
            # the canonical example of the rule we ratified against.
            # Consumers read ``particles_json_path`` for the picks.
            return ParticlePickingOutput(
                num_particles=len(picks),
                particles_json_path=json_path,
                picks=None,
            )
        except Exception as exc:
            if step is not None:
                emit_step(step.failed(error=str(exc)))
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
        step = make_step_reporter(f"{STEP_NAME}.denoise", get_publisher)
        if step is not None:
            emit_step(step.started())
        try:
            opts = input_data.engine_opts or {}
            model      = str(opts.get("model", "unet"))
            patch_size = int(opts.get("patch_size", 1024))
            padding    = int(opts.get("padding", 128))

            active = current_task()
            session = active.session_name if active else None
            output_path = _denoised_mrc_path(
                input_data.input_file, input_data.output_file, session,
            )

            if step is not None:
                emit_step(step.progress(10.0, f"denoising in {patch_size}px patches"))

            stats = run_denoise(
                input_data.input_file,
                output_path,
                model=model,
                patch_size=patch_size,
                padding=padding,
            )

            if step is not None:
                emit_step(step.progress(95.0, "writing denoised MRC"))
                emit_step(step.completed(output_files=[output_path]))

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
                emit_step(step.failed(error=str(exc)))
            raise


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
    # Per rule 1: result envelope carries the path + scalar summary
    # (num_particles). Picks themselves stay on disk; consumers read
    # the JSON file to materialise the per-particle records.
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


# ---------------------------------------------------------------------------
# Back-compat shims — Phase 1b absorbed these into the SDK runner.
# Remove in 2026-Q3 when downstream callers (main.py, tests) have
# migrated.
# ---------------------------------------------------------------------------

from magellon_sdk.runner import PluginBrokerRunner as TopazBrokerRunner  # noqa: E402
from magellon_sdk.runner.active_task import current_task as get_active_task  # noqa: E402
from magellon_sdk.runner.active_task import (  # noqa: E402,F401
    _active_task,
    get_step_event_loop as _get_loop,
)


__all__ = [
    "TopazPickPlugin",
    "TopazDenoisePlugin",
    "TopazBrokerRunner",
    "build_pick_result",
    "build_denoise_result",
    "get_active_task",
]
