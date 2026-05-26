"""External BoxNet CNN particle picker.

Third backend under PARTICLE_PICKING — sits alongside the in-process
template picker and the external template-picker. The dispatcher's
backend axis (X.1, 2026-04-27) routes via ``TaskMessage.target_backend``;
operators pick boxnet-picker when they want a CNN-based picker that
doesn't need per-dataset templates.

Vendored algorithm lives in ``plugin/algorithm.py`` — verbatim graph
trace from eval_micrograph / Warp BoxNet v2, validated against the
upstream by Sandbox/particle_picking_boxnet/parity_check.py.
"""
from __future__ import annotations

import logging
import os
from typing import Type

from magellon_sdk.base import PluginBase
from magellon_sdk.categories.outputs import ParticlePickingOutput
from magellon_sdk.models import OutputFile, PluginInfo, TaskMessage, TaskResultMessage
from magellon_sdk.models.manifest import (
    Capability,
    IsolationLevel,
    ResourceHints,
    Transport,
)
from magellon_sdk.progress import NullReporter, ProgressReporter
from magellon_sdk.runner import emit_step, make_step_reporter

from plugin.compute import run_boxnet_pick
from plugin.events import STEP_NAME, get_publisher
from plugin.models import BoxnetPickerInput

logger = logging.getLogger(__name__)


class BoxnetPickerPlugin(PluginBase[BoxnetPickerInput, ParticlePickingOutput]):
    """Warp BoxNet v2 CNN particle picker.

    Inputs (via :class:`BoxnetPickerInput`):
      * ``image_path`` — MRC to pick on (required).
      * ``threshold`` — particle-channel probability cutoff (default 0.3).
      * ``min_distance`` — NMS spacing in preprocessed pixels (default 14).
      * ``scale`` — input downsample factor (default 8 — matches BoxNet
        training resolution for a ~1 Å/pixel micrograph).
      * ``device`` — ``cuda`` / ``cpu`` / ``auto``.
      * ``output_dir`` — override location for ``particles.json``.

    Output is a :class:`ParticlePickingOutput` with
    ``particles_json_path`` set; ``picks`` is omitted (rule 1: refs only
    on bus, no inline file content).
    """

    capabilities = [
        Capability.CPU_INTENSIVE,
        Capability.IDEMPOTENT,
        Capability.PROGRESS_REPORTING,
        # PT-4: expose sync HTTP endpoint alongside the bus consumer.
        # Plugin manager / particle-picking UI calls SYNC for the
        # "run-on-one-image" feature. PREVIEW is not enabled here —
        # BoxNet doesn't have a cheap retune knob (the threshold IS
        # the only knob and we already accept it inline).
        Capability.SYNC,
    ]
    supported_transports = [
        Transport.RMQ,
        Transport.NATS,
        Transport.HTTP,
        Transport.IN_PROCESS,
    ]
    default_transport = Transport.RMQ
    isolation = IsolationLevel.CONTAINER
    resource_hints = ResourceHints(
        memory_mb=2048, cpu_cores=2, typical_duration_seconds=10.0
    )
    tags = ["boxnet", "particle-picking", "cnn", "cryo-em"]

    def get_info(self) -> PluginInfo:
        return PluginInfo(
            name="BoxNet Picker",
            version="0.1.0",
            developer="Behdad Khoshbin b.khoshbin@gmail.com",
            description=(
                "Warp BoxNet v2 CNN particle picker. Produces a 3-class "
                "per-pixel mask (background / particle / dirt); emits "
                "centroids via local-maxima peak detection on the "
                "particle channel."
            ),
        )

    @classmethod
    def input_schema(cls) -> Type[BoxnetPickerInput]:
        return BoxnetPickerInput

    @classmethod
    def output_schema(cls) -> Type[ParticlePickingOutput]:
        return ParticlePickingOutput

    def execute(
        self,
        input_data: BoxnetPickerInput,
        *,
        reporter: ProgressReporter = NullReporter(),
    ) -> ParticlePickingOutput:
        if not input_data.image_path:
            raise ValueError("boxnet-picker: image_path is required")

        step = make_step_reporter(STEP_NAME, get_publisher)
        if step is not None:
            emit_step(step.started())
        try:
            if step is not None:
                emit_step(step.progress(
                    15.0,
                    f"BoxNet forward (scale={input_data.scale}, "
                    f"device={input_data.device})",
                ))

            summary = run_boxnet_pick(
                image_path=input_data.image_path,
                threshold=float(input_data.threshold),
                min_distance=int(input_data.min_distance),
                scale=int(input_data.scale),
                device=input_data.device,
                invert=bool(input_data.invert),
                output_dir=input_data.output_dir,
            )

            if step is not None:
                emit_step(step.progress(
                    95.0,
                    f"found {summary['num_particles']} particles",
                ))
                emit_step(step.completed(
                    output_files=[summary["particles_json_path"]],
                ))

            return ParticlePickingOutput(
                num_particles=summary["num_particles"],
                particles_json_path=summary["particles_json_path"],
                image_shape=summary["image_shape"],
                picks=None,
            )
        except Exception as exc:
            if step is not None:
                emit_step(step.failed(error=str(exc)))
            raise

    # PT-4: SYNC capability — sync alternative to bus dispatch. Same
    # compute as ``execute()`` minus the step-event machinery.
    def execute_sync(
        self, input_data: BoxnetPickerInput,
    ) -> ParticlePickingOutput:
        return self.execute(input_data, reporter=NullReporter())


def build_pick_result(
    task: TaskMessage, output: ParticlePickingOutput
) -> TaskResultMessage:
    import uuid as _uuid
    files = []
    if output.particles_json_path:
        files.append(
            OutputFile(
                name=os.path.basename(output.particles_json_path),
                path=output.particles_json_path,
                required=True,
            )
        )
    data = task.data if isinstance(task.data, dict) else {}
    image_id = None
    raw_id = data.get("image_id")
    if raw_id is not None:
        try:
            image_id = _uuid.UUID(str(raw_id))
        except (ValueError, AttributeError):
            pass
    return TaskResultMessage(
        worker_instance_id=task.worker_instance_id,
        job_id=task.job_id,
        task_id=task.id,
        image_id=image_id,
        image_path=data.get("image_path", ""),
        session_id=task.session_id,
        session_name=task.session_name,
        code=200,
        message=f"BoxNet picker found {output.num_particles} particles",
        type=task.type,
        output_data={
            "num_particles": output.num_particles,
            "particles_json_path": output.particles_json_path,
            "image_shape": output.image_shape,
            "ipp_name": data.get("ipp_name", "Auto-pick"),
            **output.extras,
        },
        output_files=files,
    )


__all__ = [
    "BoxnetPickerPlugin",
    "build_pick_result",
]
